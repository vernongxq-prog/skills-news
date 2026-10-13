"""配置：新闻源、停用词、阈值。改这里就够了。"""
from urllib.parse import quote

# ---- 新闻源 RSS（失效的会自动跳过并在日志里标出）----
RSS_FEEDS = [
    ("NHK 主要", "https://www.nhk.or.jp/rss/news/cat0.xml"),
    ("NHK 社会", "https://www.nhk.or.jp/rss/news/cat1.xml"),
    ("NHK 経済", "https://www.nhk.or.jp/rss/news/cat5.xml"),
    ("NHK 政治", "https://www.nhk.or.jp/rss/news/cat4.xml"),
    ("NHK 科学文化", "https://www.nhk.or.jp/rss/news/cat3.xml"),
    ("Yahoo 国内", "https://news.yahoo.co.jp/rss/topics/domestic.xml"),
    ("Yahoo 経済", "https://news.yahoo.co.jp/rss/topics/business.xml"),
    ("Yahoo IT", "https://news.yahoo.co.jp/rss/topics/it.xml"),
    ("Yahoo 主要", "https://news.yahoo.co.jp/rss/topics/top-picks.xml"),
    ("日テレ", "https://news.ntv.co.jp/rss"),
    ("ITmedia", "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml"),
    ("INTERNET Watch", "https://internet.watch.impress.co.jp/data/rss/1.0/iw/feed.rdf"),
    ("ScanNetSecurity", "https://scan.netsecurity.ne.jp/rss/index.rdf"),
    ("Security NEXT", "https://www.security-next.com/feed"),
]

# TBS / ANN / FNN 等没有稳定 RSS，用 Google News 按媒体名拉
GOOGLE_NEWS_QUERIES = [
    "TBS NEWS DIG when:1d",
    "テレ朝news when:1d",
    "FNNプライムオンライン when:1d",
    "日経 企業 when:1d",
    "共同通信 経済 when:1d",
    "時事通信 経済 when:1d",
]

def google_news_rss(q: str) -> str:
    return f"https://news.google.com/rss/search?q={quote(q)}&hl=ja&gl=JP&ceid=JP:ja"

MAX_PER_FEED = 60
RETENTION_DAYS = 45

# ---- 关键词抽取 ----
MIN_LEN = 2                 # 单字词丢掉
MAX_COMPOUND = 4            # 连续名词最多合并几个
# 太泛的词：每天都出现，不构成"话题"
STOPWORDS = set("""
ニュース 速報 日本 国内 東京 政府 国 今日 きょう あす 午前 午後 今年 来年 昨年 最新 発表 会見 記者 報道 取材 関係 可能性
会社 企業 株式会社 社 氏 さん 人 者 件 円 万 億 年 月 日 時 分 県 市 区 町 村 都 府 道 一部 全国 各地 影響 対応 対策
情報 問題 状況 事態 方針 計画 予定 動き 声 理由 背景 内容 中 後 前 上 下 向け 中心 以上 以下 以降 以来 ため こと もの
NHK Yahoo ヤフー TBS NEWS DIG テレ朝 news FNN プライムオンライン 日テレ 共同通信 時事通信 日経 ITmedia Watch
首相 大臣 総理 委員会 国会 党 自民党 野党 与党 議員 選挙
世界 米国 アメリカ 中国 韓国 ロシア ウクライナ 欧州 EU 国際
警察 警視庁 容疑者 逮捕 男 女 男性 女性 歳 死亡 けが 事件 事故
""".split())

# ---- 热度判定 ----
THRESH = {
    "min_docs_24h": 3,      # 24h 内至少几条不同报道才算话题
    "rising_ratio": 2.0,    # 24h 条数 / 7 天日均 ≥ 2 → rising
    "high_ratio": 4.0,      # ≥ 4 且 24h ≥ 6 → high
    "high_docs_24h": 6,
    "rising_consecutive": 3,  # 连续 N 轮扫描都有新报道
    "high_consecutive": 6,
}
TOP_N = 40  # summary 里列多少个词
