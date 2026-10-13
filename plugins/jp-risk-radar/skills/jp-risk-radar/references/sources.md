# 媒体と検索クエリ

## 热词モードで回すクエリ（直近 24h）
`when:1d` を付けると鮮度が上がる。媒体名を入れて偏りを避ける。

- `NHK 社会 when:1d` / `NHK 経済 when:1d`
- `Yahoo ニュース 国内 when:1d` / `Yahoo ニュース 経済 when:1d`
- `TBS NEWS DIG when:1d` / `テレ朝news when:1d` / `FNN when:1d` / `日テレ when:1d`
- `日経 企業 when:1d` / `共同通信 経済 when:1d`
- `ITmedia when:1d` / `INTERNET Watch when:1d`（IT・セキュリティ）

## 深挖モード
- `<語> when:7d`、`<語> when:1d`、`<語> 発表`
- 一次情報は当事者のプレスリリース（お詫び・お知らせ・適時開示）

## 数え方
- 同じ事案の続報は 1 件。転載（Yahoo に載った NHK 記事）も 1 件
- 「件数」は**異なる見出し**の数。閲覧数ではない
- 「普段」はその語の過去 1 週間の 1 日あたり件数の感覚値。radar の出力があるときはその `baseline` を使う
