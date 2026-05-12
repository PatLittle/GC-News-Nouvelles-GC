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


def norm(value: str) -> str:
    return (value or "").strip()


def norm_lower(value: str) -> str:
    return norm(value).lower()


def parse_date(value: str) -> str:
    val = norm(value)
    if not val:
        return ""
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(val[:19], fmt).date().isoformat()
        except ValueError:
            continue
    return val[:10]


def read_rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def tokenize(*parts: str):
    bag = " ".join(norm_lower(p) for p in parts if p)
    cleaned = "".join(ch if ch.isalnum() else " " for ch in bag)
    return sorted({t for t in cleaned.split() if len(t) > 1})


news_rows = read_rows(NEWS_CSV)
quote_rows = read_rows(QUOTES_CSV)
image_rows = read_rows(IMAGES_CSV)

articles = {}
for row in news_rows:
    article_id = norm(row.get("ID") or row.get("id"))
    if not article_id:
        continue
    articles[article_id] = {
        "id": article_id,
        "title": norm(row.get("TITLE_EN") or row.get("TITLE") or row.get("title")),
        "date": parse_date(row.get("PUBLISHED_AT") or row.get("DATE") or row.get("date")),
        "dept_en": norm(row.get("DEPT_EN")),
        "topic_en": norm(row.get("TOPIC_EN")),
        "subject_en": norm(row.get("SUBJECT_EN")),
        "url": norm(row.get("URL") or row.get("NEWS_URL")),
    }

quotes = []
images = []
quote_token_index = defaultdict(list)
image_token_index = defaultdict(list)

for i, row in enumerate(quote_rows):
    article_id = norm(row.get("ID") or row.get("article_id"))
    q = {
        "id": f"q{i}",
        "article_id": article_id,
        "date": articles.get(article_id, {}).get("date", ""),
        "dept_en": articles.get(article_id, {}).get("dept_en", ""),
        "topic_en": articles.get(article_id, {}).get("topic_en", ""),
        "subject_en": articles.get(article_id, {}).get("subject_en", ""),
        "quote_text": norm(row.get("QUOTE_TEXT") or row.get("quote") or row.get("TEXT")),
        "speaker": norm(row.get("SPEAKER") or row.get("quote_speaker")),
        "org": norm(row.get("ORG") or row.get("quote_org") or row.get("ORGANIZATION")),
    }
    quotes.append(q)
    for tk in tokenize(q["quote_text"], q["speaker"], q["org"], q["dept_en"], q["topic_en"], q["subject_en"]):
        quote_token_index[tk].append(q["id"])

for i, row in enumerate(image_rows):
    article_id = norm(row.get("ID") or row.get("article_id"))
    file_path = norm(row.get("FILE_PATH") or row.get("file_path") or row.get("IMAGE_PATH"))
    ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
    img = {
        "id": f"img{i}",
        "article_id": article_id,
        "date": articles.get(article_id, {}).get("date", ""),
        "dept_en": articles.get(article_id, {}).get("dept_en", ""),
        "topic_en": articles.get(article_id, {}).get("topic_en", ""),
        "subject_en": articles.get(article_id, {}).get("subject_en", ""),
        "alt_text": norm(row.get("ALT_TEXT") or row.get("alt") or row.get("IMG_ALT")),
        "file_type": ext,
        "file_path": file_path,
        "url": f"{RAW_BASE}{file_path}" if file_path else "",
    }
    images.append(img)
    for tk in tokenize(img["alt_text"], img["file_type"], img["dept_en"], img["topic_en"], img["subject_en"]):
        image_token_index[tk].append(img["id"])

payload = {
    "meta": {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z"),
        "counts": {"articles": len(articles), "quotes": len(quotes), "images": len(images)},
    },
    "articles": list(articles.values()),
    "quotes": quotes,
    "images": images,
    "indexes": {
        "quote_tokens": {k: v for k, v in quote_token_index.items()},
        "image_tokens": {k: v for k, v in image_token_index.items()},
    },
}

OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
with OUT_JSON.open("w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))

print(f"Wrote {OUT_JSON} with {len(quotes)} quotes and {len(images)} images")
