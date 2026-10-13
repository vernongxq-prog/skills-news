"""每次运行：抓 RSS → 去重 → 抽关键词 → 每个词和自己的 7 天基线比 → 升级时提醒 → 写 state/。

用法：python -m radar.scan                      # 正常
      python -m radar.scan --dry-run            # 不发提醒
      python -m radar.scan --feeds-dir DIR      # 用本地 RSS 文件（测试）
"""
import argparse, hashlib, json, os, re, sqlite3, sys, time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser, requests
from . import config
from .keywords import extract

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state"
DB = STATE / "radar.db"
JST = timezone(timedelta(hours=9))
LEVELS = {"watch": 0, "rising": 1, "high": 2}

def db_init():
    STATE.mkdir(exist_ok=True)
    c = sqlite3.connect(DB)
    c.executescript("""
    CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, title TEXT, url TEXT, source TEXT, published TEXT, seen_at TEXT);
    CREATE TABLE IF NOT EXISTS kw_hits(kw TEXT, event_id TEXT, published TEXT, PRIMARY KEY(kw, event_id));
    CREATE INDEX IF NOT EXISTS kw_pub ON kw_hits(kw, published);
    CREATE TABLE IF NOT EXISTS keywords(kw TEXT PRIMARY KEY, first_seen TEXT, last_seen TEXT, consecutive_runs INTEGER,
        last_run TEXT, level TEXT, alerted_level TEXT, alerted_at TEXT);
    CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, ts TEXT, new_events INTEGER, alerts TEXT);
    """)
    return c

def iter_feeds(feeds_dir=None):
    if feeds_dir:
        for p in sorted(Path(feeds_dir).glob("*.xml")):
            yield p.stem, p.read_bytes()
        return
    srcs = list(config.RSS_FEEDS) + [("GN:" + q, config.google_news_rss(q)) for q in config.GOOGLE_NEWS_QUERIES]
    for name, url in srcs:
        try:
            r = requests.get(url, timeout=20, headers={"User-Agent": "jp-risk-radar/2.0"})
            if r.ok and r.content:
                yield name, r.content
            else:
                print(f"[skip] {name}: HTTP {r.status_code}", file=sys.stderr)
        except Exception as e:
            print(f"[skip] {name}: {e}", file=sys.stderr)

def parse_entries(name, raw):
    f = feedparser.parse(raw)
    for e in f.entries[: config.MAX_PER_FEED]:
        url, title = e.get("link") or "", (e.get("title") or "").strip()
        if not url or not title:
            continue
        pub = None
        for k in ("published_parsed", "updated_parsed"):
            if e.get(k):
                pub = datetime.fromtimestamp(time.mktime(e[k]), tz=timezone.utc).astimezone(JST); break
        src = name
        if name.startswith("GN:") and " - " in title:
            title, src = title.rsplit(" - ", 1)
        yield dict(title=title, url=url, source=src, published=(pub or datetime.now(JST)).isoformat())

def level_for(d24, baseline, consecutive):
    T = config.THRESH
    ratio = d24 / max(baseline, 0.5)
    if (d24 >= T["high_docs_24h"] and ratio >= T["high_ratio"]) or consecutive >= T["high_consecutive"]:
        return "high", ratio
    if (d24 >= T["min_docs_24h"] and ratio >= T["rising_ratio"]) or (consecutive >= T["rising_consecutive"] and d24 >= T["min_docs_24h"]):
        return "rising", ratio
    return "watch", ratio

def covered_by_longer(c, kws, since, thresh=0.8):
    """短词（不正/アクセス）的命中若 ≥80% 都出现在同一个包含它的长词（不正アクセス）里，就视为碎片，不单独报。"""
    hits = defaultdict(set)
    for kw, eid in c.execute("SELECT kw,event_id FROM kw_hits WHERE published>=?", (since,)):
        hits[kw].add(eid)
    out = set()
    for kw in kws:
        h = hits.get(kw)
        if not h:
            continue
        # 规则 1：单个长词就覆盖了它 ≥80% 命中 → 碎片（不正 ⊂ 不正アクセス）
        # 规则 2：两字词被「多个」长词合起来覆盖 ≥80% 也算碎片（個人 ⊂ 個人情報 + 個人情報漏えい）
        # 三字以上的词（漏えい）即使被多个不同长词分别覆盖也保留——那正是跨事件的共同信号
        union = set()
        for other, oh in hits.items():
            if other != kw and kw in other and len(other) > len(kw):
                if len(oh & h) / len(h) >= thresh:
                    out.add(kw); break
                union |= oh
        if kw not in out and len(kw) <= 2 and len(union & h) / len(h) >= thresh:
            out.add(kw)
    return out

def notify(text, dry):
    print("---- ALERT ----\n" + text)
    if dry:
        return
    if os.getenv("SLACK_WEBHOOK_URL"):
        requests.post(os.environ["SLACK_WEBHOOK_URL"], json={"text": text}, timeout=15)
    if os.getenv("DISCORD_WEBHOOK_URL"):
        for i in range(0, len(text), 1900):
            requests.post(os.environ["DISCORD_WEBHOOK_URL"], json={"content": text[i:i+1900]}, timeout=15)
    if os.getenv("GITHUB_TOKEN") and os.getenv("GITHUB_REPOSITORY"):
        r = requests.post(f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/issues",
                          headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "Accept": "application/vnd.github+json"},
                          json={"title": text.split("\n", 1)[0], "body": text, "labels": ["radar-alert"]}, timeout=15)
        if not r.ok:
            print(f"[warn] issue create failed: {r.status_code} {r.text[:200]}", file=sys.stderr)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--feeds-dir")
    ap.add_argument("--now")
    a = ap.parse_args()
    now = datetime.fromisoformat(a.now) if a.now else datetime.now(JST)
    run_id = now.strftime("%Y%m%d-%H%M")
    c = db_init()
    prev = c.execute("SELECT id FROM runs ORDER BY ts DESC LIMIT 1").fetchone()
    prev_run = prev[0] if prev else None
    watch = set((ROOT / "data" / "watchwords.txt").read_text(encoding="utf-8").split()) if (ROOT / "data" / "watchwords.txt").exists() else set()

    new_events, touched = 0, set()
    for name, raw in iter_feeds(a.feeds_dir):
        for e in parse_entries(name, raw):
            eid = hashlib.sha1(e["url"].encode()).hexdigest()[:16]
            if c.execute("SELECT 1 FROM events WHERE id=?", (eid,)).fetchone():
                continue
            # 同标题不同 URL（转载）也算重复
            if c.execute("SELECT 1 FROM events WHERE title=? AND published>=?", (e["title"], (now - timedelta(days=3)).isoformat())).fetchone():
                continue
            c.execute("INSERT INTO events VALUES (?,?,?,?,?,?)", (eid, e["title"], e["url"], e["source"], e["published"], now.isoformat()))
            new_events += 1
            for kw in extract(e["title"]):
                c.execute("INSERT OR IGNORE INTO kw_hits VALUES (?,?,?)", (kw, eid, e["published"]))
                touched.add(kw)

    t24, t7 = (now - timedelta(hours=24)).isoformat(), (now - timedelta(days=8)).isoformat()
    redundant = covered_by_longer(c, touched, t24)
    alerts, alerted = [], []
    for kw in touched:
        d24 = c.execute("SELECT COUNT(*) FROM kw_hits WHERE kw=? AND published>=?", (kw, t24)).fetchone()[0]
        d7 = c.execute("SELECT COUNT(*) FROM kw_hits WHERE kw=? AND published>=? AND published<?", (kw, t7, t24)).fetchone()[0]
        baseline = d7 / 7.0
        row = c.execute("SELECT consecutive_runs,last_run,alerted_level,first_seen FROM keywords WHERE kw=?", (kw,)).fetchone()
        consecutive = (row[0] + 1) if row and row[1] == prev_run else 1
        al = row[2] if row else "watch"
        first = row[3] if row else now.isoformat()
        level, ratio = level_for(d24, baseline, consecutive)
        new_al = level if LEVELS[level] > LEVELS[al] else al
        c.execute("INSERT OR REPLACE INTO keywords VALUES (?,?,?,?,?,?,?,?)",
                  (kw, first, now.isoformat(), consecutive, run_id, level, new_al, now.isoformat() if new_al != al else (c.execute("SELECT alerted_at FROM keywords WHERE kw=?", (kw,)).fetchone() or [None])[0]))
        if kw in redundant:
            continue
        if LEVELS[level] > LEVELS[al] or (kw in watch and d24 >= config.THRESH["min_docs_24h"] and al == "watch"):
            samples = c.execute("SELECT e.title,e.url,e.source FROM kw_hits k JOIN events e ON e.id=k.event_id WHERE k.kw=? AND k.published>=? ORDER BY k.published DESC LIMIT 3", (kw, t24)).fetchall()
            tag = "🔴 高" if level == "high" else "🟠 上升"
            alerts.append("\n".join([f"{tag}  **{kw}**" + ("  ⭐関注词" if kw in watch else ""),
                                     f"24h {d24} 条 / 过去 7 天日均 {baseline:.1f} 条（×{ratio:.1f}）/ 连续 {consecutive} 轮有新报道"]
                                    + [f"  ・{t}（{s}）{u}" for t, u, s in samples]))
            alerted.append(kw)

    if alerts:
        notify(f"📡 radar {now.strftime('%m/%d %H:%M')} JST 新提醒 {len(alerts)} 件\n\n" + "\n\n".join(alerts), a.dry_run)
    c.execute("INSERT OR REPLACE INTO runs VALUES (?,?,?,?)", (run_id, now.isoformat(), new_events, json.dumps(alerted, ensure_ascii=False)))
    cutoff = (now - timedelta(days=config.RETENTION_DAYS)).isoformat()
    c.execute("DELETE FROM kw_hits WHERE published<?", (cutoff,))
    c.execute("DELETE FROM events WHERE published<?", (cutoff,))
    c.commit()
    write_summary(c, now, watch)
    print(f"run {run_id}: {new_events} new, {len(touched)} keywords touched, {len(alerts)} alerts")

def write_summary(c, now, watch):
    t24 = (now - timedelta(hours=24)).isoformat()
    rows = []
    recent = [r[0] for r in c.execute("SELECT kw FROM keywords WHERE last_seen>=?", ((now - timedelta(days=2)).isoformat(),))]
    redundant = covered_by_longer(c, recent, t24)
    for kw, level, cons, al_at in c.execute("SELECT kw,level,consecutive_runs,alerted_at FROM keywords WHERE last_seen>=?", ((now - timedelta(days=2)).isoformat(),)):
        d24 = c.execute("SELECT COUNT(*) FROM kw_hits WHERE kw=? AND published>=?", (kw, t24)).fetchone()[0]
        if (d24 < 2 and kw not in watch) or (kw in redundant and kw not in watch):
            continue
        days = [c.execute("SELECT COUNT(*) FROM kw_hits WHERE kw=? AND published>=? AND published<?",
                          (kw, (now - timedelta(days=i + 1)).isoformat(), (now - timedelta(days=i)).isoformat())).fetchone()[0] for i in range(6, -1, -1)]
        base = sum(days[:-1]) / 6.0
        samples = [dict(title=t, url=u, source=s, published=p) for t, u, s, p in c.execute(
            "SELECT e.title,e.url,e.source,e.published FROM kw_hits k JOIN events e ON e.id=k.event_id WHERE k.kw=? ORDER BY k.published DESC LIMIT 3", (kw,))]
        top = [samples[0]["title"], samples[0]["url"]] if samples else None
        rows.append(dict(kw=kw, level=level, d24=d24, baseline=round(base, 1), ratio=round(d24 / max(base, 0.5), 1), consecutive=cons, days=days,
                         latest=top, samples=samples, watch=kw in watch, alerted_at=al_at))
    rows.sort(key=lambda r: (LEVELS[r["level"]], r["ratio"], r["d24"]), reverse=True)
    rows = rows[: config.TOP_N]
    md = [f"# Risk Radar JP — 热词 {now.strftime('%Y-%m-%d %H:%M')} JST", "",
          "| 级别 | 关键词 | 24h | 日均 | 倍率 | 连续轮 | 近7天 | 最新 |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        spark = "".join(" ▁▂▃▄▅▆▇█"[min(8, round(d / max(max(r["days"]), 1) * 8))] for d in r["days"])
        md.append(f"| {r['level']}{' ⭐' if r['watch'] else ''} | {r['kw']} | {r['d24']} | {r['baseline']} | ×{r['ratio']} | {r['consecutive']} | `{spark}` | [{r['latest'][0][:36] if r['latest'] else ''}]({r['latest'][1] if r['latest'] else ''}) |")
    (STATE / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    shown = {r["kw"] for r in rows}
    events = []
    for eid, title, url, src, pub in c.execute("SELECT id,title,url,source,published FROM events WHERE published>=? ORDER BY published DESC LIMIT 150", (t24,)):
        kws = [k for (k,) in c.execute("SELECT kw FROM kw_hits WHERE event_id=?", (eid,)) if k in shown]
        events.append(dict(id=eid, title=title, url=url, source=src, published=pub, keywords=kws))
    last = c.execute("SELECT ts,new_events FROM runs ORDER BY ts DESC LIMIT 1").fetchone()
    (STATE / "latest.json").write_text(json.dumps(dict(generated=now.isoformat(), new_events=last[1] if last else 0,
                                                       keywords=rows, events=events), ensure_ascii=False, indent=1), encoding="utf-8")

if __name__ == "__main__":
    main()
