#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync.py — 把「醫療稽核」研究資料夾裡給老人看的卡片，正規化搬進 GitHub Pages repo，
          並自動產生首頁 index.html。

設計原則（拍板版）：
  1. 白名單：只認 *_for_elders.html（含裸 for_elders.html），研究產物(.json/.py/.md/.txt/.log)一律不進。
  2. 以「資料夾名」為主鍵，不必先改亂七八糟的原始檔名。
  3. 只改「副本」，原始研究資料夾永遠不動。
  4. 老人可讀性修正只做三件事，用字串取代，出錯重跑即可：
       - color:#999                         → color:#5c5044          （頁尾灰字對比不足）
       - background:#e8a04a;color:#fff       → background:#f0d090;color:#5c1a00 （表格白字橘底對比不足）
       - font-family:"Microsoft JhengHei",sans-serif → 補齊跨平台字體 stack
       - 內文 font-size:16px/17px            → 18px  （老人最小字級）
     ※ 邊框用的 #e8a04a（border-left）刻意保留，不誤傷。
  5. 每頁注入「‹ 回首頁」大按鈕；主題入口頁再注入子主題延伸閱讀連結。
  6. meta.json 由本腳本自動草擬、status 預設 draft（安全預設，忘了翻牌不會誤上線）；
     已存在的 meta.json 只更新 subtopics 清單，不覆蓋你手填的 title/emoji/summary/status。
  7. 首頁只收錄 status == "published" 的主題。

用法：
  python3 build/sync.py <主題資料夾名>     # 搬單一主題（新增主題時用）
  python3 build/sync.py --all              # 全部重搬
  python3 build/sync.py --index-only       # 只重產首頁（改完 meta.json status 後用）
"""

import json
import re
import shutil
import sys
from pathlib import Path

# ── 路徑設定 ───────────────────────────────────────────────────────────
SOURCE_ROOT = Path("/home/qct/local-llm-proxy/transcripts/citation-audits")
REPO_ROOT = Path(__file__).resolve().parent.parent
TOPICS_DIR = REPO_ROOT / "topics"

# ── 對照表 ─────────────────────────────────────────────────────────────
# 子主題英文段 → 中文標籤（首頁/延伸閱讀顯示用）
SUBTOPIC_ZH = {
    "cardiovascular": "心血管",
    "cognition": "認知",
    "inflammation": "發炎",
    "metabolic": "代謝",
    "osteoarthritis": "骨關節炎",
    "mortality": "全死因",
}

# 主題預設 emoji（猜不到就用 📄，之後可在 meta.json 手改）
TOPIC_EMOJI = {
    "olive": "🫒",
    "avocado": "🥑",
    "creatine": "💪",
    "fishoil": "🐟",
    "osteo-sarco": "🦴",
}

# 主題在首頁的顯示順序（沒列到的照字母序排在後面）
TOPIC_ORDER = ["olive", "avocado", "fishoil", "creatine", "osteo-sarco"]

# ── 老人可讀性修正（只改副本）─────────────────────────────────────────
FIXES = [
    ("color:#999", "color:#5c5044"),
    ("background:#e8a04a;color:#fff", "background:#f0d090;color:#5c1a00"),
    (
        'font-family:"Microsoft JhengHei",sans-serif',
        'font-family:"Microsoft JhengHei","PingFang TC","Heiti TC","Noto Sans TC",system-ui,sans-serif',
    ),
    ("font-size:16px", "font-size:18px"),
    ("font-size:17px", "font-size:18px"),
]

# 注入用的標記，避免重複注入（其實每次都從原檔重抄，不會重複，這裡當保險）
NAV_MARK = "<!--ELDER-NAV-->"

# ── 回首頁按鈕（注入在 <body> 之後）───────────────────────────────────
HOME_BTN = (
    NAV_MARK
    + '<a href="../../index.html" style="display:block;max-width:720px;margin:0 auto 16px;'
    "padding:16px 20px;background:#b8420f;color:#fff;font-size:20px;font-weight:bold;"
    'text-align:center;text-decoration:none;border-radius:14px;min-height:48px;'
    'box-sizing:border-box;">‹ 回首頁</a>'
)


def normalize_name(filename: str, topic: str):
    """回傳 (dest_filename, kind)；kind 為 'entry' 或 子主題英文段。"""
    if filename.endswith("_for_elders.html"):
        base = filename[: -len("_for_elders.html")]
    elif filename.endswith(".html"):
        base = filename[: -len(".html")]
    else:
        return None, None

    # 入口頁判定：等於主題名、含「總摘要」、裸 for_elders、或空字串
    if base in (topic, "", "for_elders") or "總摘要" in base:
        return "index.html", "entry"

    # 子主題：去掉「主題_」前綴，取英文段
    seg = base[len(topic) + 1:] if base.startswith(topic + "_") else base
    return f"{seg}.html", seg


def apply_fixes(html: str) -> str:
    for old, new in FIXES:
        html = html.replace(old, new)
    return html


def inject_nav(html: str, subtopic_links: str = "") -> str:
    """在 <body> 後注入回首頁按鈕；若是入口頁再於 </body> 前注入延伸閱讀。"""
    html = html.replace("<body>", "<body>\n" + HOME_BTN + "\n", 1)
    if subtopic_links:
        html = html.replace("</body>", subtopic_links + "\n</body>", 1)
    return html


def build_subtopic_block(subtopics: list) -> str:
    if not subtopics:
        return ""
    cards = "".join(
        f'<a href="{s["file"]}" style="display:block;max-width:720px;margin:0 auto 12px;'
        f"padding:18px 20px;background:#fff;border:2px solid #f0e0c0;border-radius:14px;"
        f"color:#b8420f;font-size:20px;font-weight:bold;text-decoration:none;"
        f'min-height:48px;box-sizing:border-box;box-shadow:0 2px 8px rgba(0,0,0,0.06);">'
        f'{s["label"]} ›</a>'
        for s in subtopics
    )
    return (
        '<div style="max-width:720px;margin:28px auto 0;">'
        '<h2 style="font-size:22px;color:#7a6a4a;text-align:center;margin-bottom:14px;">延伸閱讀</h2>'
        + cards
        + "</div>"
    )


def extract_title(html: str, fallback: str) -> str:
    m = re.search(r"<title>([^<]*)</title>", html)
    return m.group(1).strip() if m else fallback


def sync_topic(topic: str) -> bool:
    src = SOURCE_ROOT / topic
    if not src.is_dir():
        print(f"  ✗ 找不到來源資料夾：{src}")
        return False

    files = sorted(
        p.name
        for p in src.iterdir()
        if p.is_file() and p.name.endswith("_for_elders.html")
    )
    # 裸 for_elders.html 也算（osteo-sarco）
    if (src / "for_elders.html").exists() and "for_elders.html" not in files:
        files.append("for_elders.html")

    if not files:
        print(f"  ✗ {topic}：找不到任何 *_for_elders.html")
        return False

    dest_dir = TOPICS_DIR / topic
    dest_dir.mkdir(parents=True, exist_ok=True)

    entry_title = topic
    subtopics = []
    entry_src_html = None

    # 先掃一遍，區分入口頁與子主題
    parsed = []
    for fn in files:
        dest_name, kind = normalize_name(fn, topic)
        if dest_name is None:
            continue
        parsed.append((fn, dest_name, kind))

    # 收集子主題（供入口頁延伸閱讀 + meta）
    for fn, dest_name, kind in parsed:
        if kind != "entry":
            label = SUBTOPIC_ZH.get(kind, kind)
            subtopics.append({"file": dest_name, "label": label})
    subtopics.sort(key=lambda s: s["label"])

    subtopic_block = build_subtopic_block(subtopics)

    # 實際搬檔
    for fn, dest_name, kind in parsed:
        raw = (src / fn).read_text(encoding="utf-8")
        fixed = apply_fixes(raw)
        if kind == "entry":
            entry_title = extract_title(raw, topic)
            entry_src_html = inject_nav(fixed, subtopic_block)
            (dest_dir / "index.html").write_text(entry_src_html, encoding="utf-8")
        else:
            (dest_dir / dest_name).write_text(inject_nav(fixed), encoding="utf-8")
        print(f"    {fn}  →  topics/{topic}/{dest_name}")

    # 寫 / 更新 meta.json
    meta_path = dest_dir / "meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["subtopics"] = subtopics  # 只刷新子主題清單
        meta.setdefault("entry", "index.html")
    else:
        meta = {
            "title": entry_title,
            "emoji": TOPIC_EMOJI.get(topic, "📄"),
            "summary": "（請在此填一句話結論，確認後把 status 改成 published）",
            "status": "draft",
            "entry": "index.html",
            "subtopics": subtopics,
        }
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    flag = "✔ 已收錄" if meta.get("status") == "published" else "◽ draft（待翻牌）"
    print(f"  {flag}  {topic}  meta.json：{meta.get('title')}")
    return True


def build_index():
    """掃 topics/*/meta.json，只收 status==published，重產首頁。"""
    metas = []
    for meta_path in sorted(TOPICS_DIR.glob("*/meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["_slug"] = meta_path.parent.name
        metas.append(meta)

    published = [m for m in metas if m.get("status") == "published"]

    def order_key(m):
        slug = m["_slug"]
        return (TOPIC_ORDER.index(slug) if slug in TOPIC_ORDER else 999, slug)

    published.sort(key=order_key)

    cards = ""
    for m in published:
        cards += (
            f'<a class="topic" href="topics/{m["_slug"]}/index.html">'
            f'<span class="emoji">{m.get("emoji", "📄")}</span>'
            f'<span class="tt">{m.get("title", m["_slug"])}</span>'
            f'<span class="sum">{m.get("summary", "")}</span>'
            f"</a>\n"
        )

    if not cards:
        cards = '<p style="text-align:center;color:#7a6a4a;font-size:18px;">目前還沒有已發布的主題。</p>'

    total = len(published)
    draft = len(metas) - total
    html = INDEX_TEMPLATE.replace("{{CARDS}}", cards).replace(
        "{{COUNT}}", f"共 {total} 個主題" + (f"（另有 {draft} 個草稿）" if draft else "")
    )
    (REPO_ROOT / "index.html").write_text(html, encoding="utf-8")
    print(f"\n首頁已重產：index.html（已發布 {total}，草稿 {draft}）")


INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-Hant"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>健康知識卡</title>
<style>
:root{color-scheme:light;}
body{font-family:"Microsoft JhengHei","PingFang TC","Heiti TC","Noto Sans TC",system-ui,sans-serif;
  background:#fdf6ec;margin:0;padding:24px 16px;color:#3a3a3a;}
.head{max-width:720px;margin:0 auto 24px;text-align:center;}
.head h1{font-size:30px;color:#b8420f;margin:8px 0;line-height:1.4;}
.head p{font-size:18px;color:#7a6a4a;margin:4px 0;}
.topic{display:block;max-width:720px;margin:0 auto 16px;padding:24px;background:#fff;
  border:2px solid #f0e0c0;border-radius:18px;text-decoration:none;color:#3a3a3a;
  box-shadow:0 4px 16px rgba(0,0,0,0.08);min-height:48px;box-sizing:border-box;}
.topic .emoji{font-size:40px;display:block;text-align:center;}
.topic .tt{font-size:24px;font-weight:bold;color:#b8420f;display:block;text-align:center;margin:8px 0;line-height:1.4;}
.topic .sum{font-size:18px;color:#5c5044;display:block;text-align:center;line-height:1.7;}
.foot{max-width:720px;margin:28px auto 0;text-align:center;font-size:14px;color:#8a8074;line-height:1.7;}
</style></head><body>
<div class="head">
<h1>健康知識卡</h1>
<p>白話整理的營養與保健文獻，點主題看重點</p>
<p style="font-size:15px;">{{COUNT}}</p>
</div>
{{CARDS}}
<div class="foot">本站內容整理自公開醫學文獻，僅供參考，不能取代醫師與藥師的專業建議。<br>身體有狀況請找醫師討論。</div>
</body></html>
"""


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    if args[0] == "--index-only":
        build_index()
        return

    if args[0] == "--all":
        topics = sorted(p.name for p in SOURCE_ROOT.iterdir() if p.is_dir() and not p.name.startswith((".", "__")))
    else:
        topics = args

    print(f"來源：{SOURCE_ROOT}")
    print(f"輸出：{REPO_ROOT}\n")
    for t in topics:
        print(f"[{t}]")
        sync_topic(t)
        print()
    build_index()


if __name__ == "__main__":
    main()
