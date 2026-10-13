# jp-risk-radar — 日本新闻热词雷达

每 15 分钟抓 NHK / Yahoo / TBS / ANN / FNN / 日テレ / 日経 / 共同 / ITmedia 等社会・経済・IT 新闻，
从标题里自动抽关键词，和每个词自己过去 7 天的基线比。**某个词开始涨，就提醒。**
不做公司/股票映射——那是你的活。

```
RSS + Google News → 去重 → janome 抽名词短语 → 24h 条数 vs 7 天日均 → 升级时提醒 → state/
```

## 部署

1. push 到 GitHub（私有可），成员加 collaborator
2. Actions → 启用 → 手动 Run 一次 `risk radar scan`
3. 之后每 15 分钟自动跑。提醒默认开 **Issue**（label `radar-alert`），成员 Watch → Custom → Issues 就能收邮件/手机推送，不需要任何 secret
4. 结果在 `state/`：
   - `summary.md` — 当前热词表（级别、24h 条数、日均、倍率、连续轮数、7 天 sparkline、最新标题）
   - `latest.json` — 给 Claude skill 读
   - `radar.db` — 历史

有 Slack / Discord 时加 secret `SLACK_WEBHOOK_URL` / `DISCORD_WEBHOOK_URL`。

## 提醒规则

| 级别 | 条件 |
|---|---|
| 🟠 rising | 24h ≥3 条不同报道 且 ≥ 日均 ×2；或连续 3 轮扫描都有新报道 |
| 🔴 high | 24h ≥6 条 且 ≥ 日均 ×4；或连续 6 轮 |

- 同一个词只在级别**上升**时提醒一次
- 碎片词自动吸收：「不正」「アクセス」被「不正アクセス」覆盖就不单独报；但「漏えい」这种跨多个事件（個人情報漏えい / 会員情報漏えい）的共同词会保留
- `data/watchwords.txt` 里的词 ⭐ 一旦 24h ≥3 条就报，不等倍率

调阈值：`radar/config.py` 的 `THRESH`。加/删新闻源、停用词：同一文件。

## 本地跑

```
pip install -r requirements.txt
python -m radar.scan --dry-run
python tests/make_fixtures.py
python -m radar.scan --dry-run --feeds-dir tests/fixtures/round0 --now 2026-10-12T09:00:00+09:00
python -m radar.scan --dry-run --feeds-dir tests/fixtures/round3 --now 2026-10-13T11:15:00+09:00
```

## 给团队成员装 Claude skill

**Claude Code**（仓库同时是 plugin marketplace）：
```
claude plugin marketplace add vernongxq-prog/skills-news
claude plugin install jp-risk-radar@jp-risk-radar
```
更新：`claude plugin update jp-risk-radar@jp-risk-radar`。

**claude.ai / 桌面 App**：把 `jp-risk-radar.skill` 发给对方，在 Claude 里上传保存。同一 org 管理员上传一次即可。

**其他 AI agent**：`plugins/jp-risk-radar/skills/jp-risk-radar/` 是纯 markdown，贴进 custom instructions 即可。
