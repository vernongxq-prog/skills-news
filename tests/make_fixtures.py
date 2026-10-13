"""round0 = 7 天安静背景；round1-3 = 漏えい话题逐轮升温。真实 RSS 会重复旧条目，所以每轮都带上之前的全部。"""
from pathlib import Path
from email.utils import format_datetime
from datetime import datetime, timedelta, timezone
JST = timezone(timedelta(hours=9))
now = datetime(2026, 10, 13, 9, 0, tzinfo=JST)

background = []
for d in range(7, 0, -1):
    base = now - timedelta(days=d)
    background += [
        (f"円相場 一時1ドル150円台 {d}", f"https://ex.jp/bg{d}a", "NHK 経済", base),
        (f"大リーグ 大谷翔平 本塁打 {d}", f"https://ex.jp/bg{d}b", "NHK 主要", base + timedelta(hours=1)),
        (f"気象庁 大雨 警戒 呼びかけ {d}", f"https://ex.jp/bg{d}c", "Yahoo 国内", base + timedelta(hours=2)),
    ]
background.append(("中小企業で個人情報漏えい 100件", "https://ex.jp/bg_leak", "ScanNetSecurity", now - timedelta(days=4)))

rounds = {
 1: [("焼肉きんぐに不正アクセス、1078万人分の情報流出", "https://ex.jp/a1", "ITmedia", now),
     ("円相場 小幅続伸", "https://ex.jp/a2", "NHK 経済", now)],
 2: [("ブックオフに不正アクセス 643万件情報漏えいの可能性", "https://ex.jp/b1", "共同通信", now + timedelta(hours=1)),
     ("スカイチケット 個人情報1400万件流出か", "https://ex.jp/b2", "NHK 主要", now + timedelta(hours=1)),
     ("ブックオフに不正アクセス 643万件情報漏えいの可能性", "https://ex.jp/b1-dup", "Yahoo 国内", now + timedelta(hours=1))],  # 转载去重
 3: [("JR東日本とビューカード 600万件の会員情報漏えいか", "https://ex.jp/c1", "TBS NEWS DIG", now + timedelta(hours=2)),
     ("政府 大量の個人情報を扱う事業者に脆弱性対策を要請", "https://ex.jp/c2", "NHK 政治", now + timedelta(hours=2)),
     ("ローソン 215万件の個人情報漏えい 不正アクセスが原因", "https://ex.jp/c3", "テレ朝news", now + timedelta(hours=2))],
}
def write(r, items):
    d = Path(__file__).parent / f"fixtures/round{r}"; d.mkdir(parents=True, exist_ok=True)
    xml = ['<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>t</title>']
    for t, u, s, p in items:
        xml.append(f"<item><title>{t} - {s}</title><link>{u}</link><pubDate>{format_datetime(p)}</pubDate></item>")
    xml.append("</channel></rss>")
    (d / "GN:test.xml").write_text("".join(xml), encoding="utf-8")
write(0, background)
acc = list(background)
for r in (1, 2, 3):
    acc += rounds[r]; write(r, acc)
print("ok")
