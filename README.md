# pubmed-knowledge-share — 長輩健康知識卡

把 PubMed 文獻稽核整理成「給長輩看」的白話卡片，發布成 GitHub Pages。
面向高齡使用者：RWD、手機優先、大字級、高對比、導覽簡單。

網址：https://sesgigikimo.github.io/pubmed-knowledge-share/

## 結構

```
index.html            首頁（由 build/sync.py 自動產生，勿手改）
topics/<主題>/
  index.html          主題入口（總摘要 + 延伸閱讀）
  <子主題>.html        子主題卡片
  meta.json           標題、emoji、一句話摘要、status（draft/published）
build/sync.py         搬遷 + 正規化 + 修色 + 產生首頁的腳本
```

## 新增一個主題（3 步）

1. `python3 build/sync.py <主題資料夾名>`
   自動白名單複製 `*_for_elders.html`、正規化檔名、修配色/字級/字體、
   草擬 `meta.json`（預設 `status: draft`）、重產首頁。
2. 打開 `topics/<主題>/meta.json`，填標題/emoji/一句話摘要，
   本機 `python3 -m http.server` 預覽確認後，把 `status` 改成 `published`。
3. `git add . && git commit && git push`。

## 可讀性規格

內文 ≥18px、行高 1.75、對比 ≥ WCAG AA、觸控目標 ≥48px、
字體 `微軟正黑 / PingFang TC / Noto Sans TC / system-ui`、
維持可縮放（不鎖 `user-scalable`）。

## 免責

內容整理自公開醫學文獻，僅供參考，不能取代醫師與藥師的專業建議。
