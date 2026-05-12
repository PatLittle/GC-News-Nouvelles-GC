#!/usr/bin/env python3
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEWS_CSV = ROOT / "combined_news.csv"
QUOTES_CSV = ROOT / "combined_news_quotes.csv"
IMAGES_CSV = ROOT / "combined_news_images.csv"
OUT_JSON = ROOT / "docs" / "search-data.json"
RAW_BASE = "https://raw.githubusercontent.com/PatLittle/GC-News-Nouvelles-GC/main/"


def norm(v): return (v or "").strip()
def low(v): return norm(v).lower()

def parse_date(v):
    v = norm(v)
    if not v:
        return ""
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(v[:19], fmt).date().isoformat()
        except ValueError:
            pass
    return v[:10]


def rows(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def tokenize(*parts):
    cleaned = "".join(ch if ch.isalnum() else " " for ch in " ".join(low(p) for p in parts if p))
    return sorted({t for t in cleaned.split() if len(t) > 1})


news_rows = rows(NEWS_CSV)
quote_rows = rows(QUOTES_CSV)
image_rows = rows(IMAGES_CSV)

articles = {}
for r in news_rows:
    h = norm(r.get("hash") or r.get("HASH"))
    if not h:
        continue
    articles[h] = {
        "hash": h,
        "title": norm(r.get("TITLE_TEXT_EN") or r.get("TITLE_EN") or r.get("TITLE")),
        "url": norm(r.get("TITLE_URL_EN") or r.get("URL") or r.get("NEWS_URL")),
        "date": parse_date(r.get("PUBDATE") or r.get("PUBLISHED_AT") or r.get("DATE")),
        "dept_en": norm(r.get("DEPT_EN")),
        "topic_en": norm(r.get("TOPIC_EN")),
        "subject_en": norm(r.get("SUBJECT_EN")),
    }

quotes, images = [], []
q_index, i_index = defaultdict(list), defaultdict(list)

for i, r in enumerate(quote_rows):
    h = norm(r.get("hash") or r.get("HASH"))
    a = articles.get(h, {})
    q = {
        "id": f"q{i}", "hash": h,
        "date": a.get("date", parse_date(r.get("PUBDATE"))),
        "dept_en": a.get("dept_en", ""), "topic_en": a.get("topic_en", ""), "subject_en": a.get("subject_en", ""),
        "quote_text": norm(r.get("QUOTE_EN") or r.get("QUOTE_TEXT") or r.get("TEXT")),
        "speaker": norm(r.get("SPEAKER_NAME_EN") or r.get("SPEAKER_EN") or r.get("SPEAKER")),
        "org": norm(r.get("SPEAKER_ORGANIZATION_EN") or r.get("ORG") or r.get("ORGANIZATION")),
    }
    quotes.append(q)
    for t in tokenize(q["quote_text"], q["speaker"], q["org"], q["dept_en"], q["topic_en"], q["subject_en"]):
        q_index[t].append(q["id"])

for i, r in enumerate(image_rows):
    h = norm(r.get("hash") or r.get("HASH"))
    a = articles.get(h, {})
    fp = norm(r.get("FILE_PATH") or r.get("IMAGE_PATH"))
    ext = fp.rsplit('.', 1)[-1].lower() if '.' in fp else ''
    im = {
        "id": f"img{i}", "hash": h,
        "date": a.get("date", parse_date(r.get("PUBDATE"))),
        "dept_en": a.get("dept_en", ""), "topic_en": a.get("topic_en", ""), "subject_en": a.get("subject_en", ""),
        "alt_text": norm(r.get("ALT_TEXT_EN") or r.get("ALT_TEXT") or r.get("alt")),
        "file_type": ext, "file_path": fp,
        "url": f"{RAW_BASE}{fp}" if fp else "",
    }
    images.append(im)
    for t in tokenize(im["alt_text"], im["file_type"], im["dept_en"], im["topic_en"], im["subject_en"]):
        i_index[t].append(im["id"])

facets = {
    "dept_en": sorted({x["dept_en"] for x in quotes + images if x.get("dept_en")}),
    "topic_en": sorted({x["topic_en"] for x in quotes + images if x.get("topic_en")}),
    "subject_en": sorted({x["subject_en"] for x in quotes + images if x.get("subject_en")}),
    "speaker": sorted({x["speaker"] for x in quotes if x.get("speaker")}),
    "org": sorted({x["org"] for x in quotes if x.get("org")}),
}

payload = {
    "meta": {"generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
             "counts": {"articles": len(articles), "quotes": len(quotes), "images": len(images)}},
    "articles": list(articles.values()), "quotes": quotes, "images": images,
    "facets": facets,
    "indexes": {"quote_tokens": dict(q_index), "image_tokens": dict(i_index)},
}

OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
with OUT_JSON.open("w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
print(f"Wrote {OUT_JSON} with {len(quotes)} quotes and {len(images)} images")
