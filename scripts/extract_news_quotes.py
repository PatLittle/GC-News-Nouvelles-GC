import argparse
import csv
import json
import logging
import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, List, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


QUOTE_OUTPUT_FIELDS = [
    "id",
    "hash",
    "PUBDATE",
    "TITLE_URL_EN",
    "TITLE_URL_FR",
    "QUOTE_INDEX",
    "QUOTE_EN",
    "SPEAKER_EN",
    "QUOTE_FR",
    "SPEAKER_FR",
]

IMAGE_OUTPUT_FIELDS = [
    "id",
    "hash",
    "PUBDATE",
    "TITLE_URL_EN",
    "TITLE_URL_FR",
    "IMAGE_INDEX",
    "FILENAME",
    "ALT_TEXT_EN",
    "ALT_TEXT_FR",
    "FILE_PATH",
]

ARTICLE_KEY_FIELDS = ["hash", "PUBDATE", "TITLE_URL_EN", "TITLE_URL_FR"]
COUNT_FIELDS = ["QUOTE_COUNT", "IMAGE_COUNT"]
HEADING_TARGETS = {
    "en": {"quotes"},
    "fr": {"citations"},
}
QUOTE_MARKS = {
    '"',
    "'",
    "\u201c",
    "\u201d",
    "\u201e",
    "\u00ab",
    "\u00bb",
    "\u2018",
    "\u2019",
}
SKIP_IMAGE_BASENAMES = {"wmms-blk.svg", "sig-blk-en.svg"}
ARTICLE_IMAGE_DIR = os.path.join("data", "news_images")
STATE_VERSION = 3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract quote sections and article images from bilingual Canada.ca news articles."
    )
    parser.add_argument("--input", default="combined_news.csv")
    parser.add_argument("--quotes-output", default="combined_news_quotes.csv")
    parser.add_argument("--images-output", default="combined_news_images.csv")
    parser.add_argument("--state", default="data/news_quotes_state.json")
    parser.add_argument("--images-dir", default=ARTICLE_IMAGE_DIR)
    parser.add_argument("--full-rebuild", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-workers", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=30)
    return parser.parse_args()


def make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": (
                "GC-News-Nouvelles-GC quote and image extractor "
                "(https://github.com/PatLittle/GC-News-Nouvelles-GC)"
            )
        }
    )
    return session


def normalize_space(value: str) -> str:
    if value is None:
        return ""
    value = value.replace("\xa0", " ").replace("\u202f", " ").replace("\r", " ")
    return re.sub(r"\s+", " ", value).strip()


def strip_outer_quotes(value: str) -> str:
    value = normalize_space(value)
    while len(value) >= 2 and value[0] in QUOTE_MARKS and value[-1] in QUOTE_MARKS:
        value = value[1:-1].strip()
    return value


def clean_speaker(value: str) -> str:
    return re.sub(r"^[\-\u2013\u2014\s]+", "", normalize_space(value))


def article_key(row: Dict[str, str]) -> str:
    return "|".join(normalize_space(row.get(field, "")) for field in ARTICLE_KEY_FIELDS)


def image_directory_for_hash(images_dir: str, article_hash: str) -> str:
    return os.path.join(images_dir, article_hash)


def ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def load_input_rows(path: str) -> Tuple[List[Dict[str, str]], List[str]]:
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    return rows, fieldnames


def write_input_rows(path: str, fieldnames: List[str], rows: List[Dict[str, str]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_existing_rows(path: str, extra_fields: List[str]) -> Dict[str, List[Dict[str, str]]]:
    if not os.path.exists(path):
        return {}

    grouped: Dict[str, List[Dict[str, str]]] = {}
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            key = article_key(row)
            grouped.setdefault(key, []).append(
                {
                    "hash": row.get("hash", ""),
                    "PUBDATE": row.get("PUBDATE", ""),
                    "TITLE_URL_EN": row.get("TITLE_URL_EN", ""),
                    "TITLE_URL_FR": row.get("TITLE_URL_FR", ""),
                    **{field: row.get(field, "") for field in extra_fields},
                }
            )

    return grouped


def load_state(path: str) -> Dict[str, Dict[str, str]]:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_state(path: str, state: Dict[str, Dict[str, str]]) -> None:
    ensure_parent_dir(path)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2, sort_keys=True)


def write_rows(path: str, fieldnames: List[str], rows: List[Dict[str, str]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for idx, row in enumerate(rows, start=1):
            row_out = dict(row)
            row_out["id"] = idx
            writer.writerow(row_out)


def heading_matches(text: str, lang: str) -> bool:
    return normalize_space(text).lower() in HEADING_TARGETS[lang]


def extract_quotes_from_html(html: str, lang: str) -> List[Tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    heading = None
    for candidate in soup.find_all(re.compile(r"^h[1-6]$")):
        if heading_matches(candidate.get_text(" ", strip=True), lang):
            heading = candidate
            break

    if heading is None:
        return []

    quote_blocks = []
    for element in heading.find_all_next():
        tag_name = getattr(element, "name", None)
        if tag_name and re.fullmatch(r"h[1-6]", tag_name):
            break
        if tag_name == "blockquote":
            quote_blocks.append(element)

    extracted: List[Tuple[str, str]] = []
    for block in quote_blocks:
        paragraphs = [
            normalize_space(p.get_text(" ", strip=True))
            for p in block.find_all("p")
            if normalize_space(p.get_text(" ", strip=True))
        ]

        if paragraphs:
            quote_text = strip_outer_quotes(paragraphs[0])
            speaker_text = clean_speaker(" ".join(paragraphs[1:]))
        else:
            lines = [
                normalize_space(text)
                for text in block.get_text("\n", strip=True).splitlines()
                if normalize_space(text)
            ]
            if not lines:
                continue
            quote_text = strip_outer_quotes(lines[0])
            speaker_text = clean_speaker(" ".join(lines[1:]))

        if quote_text:
            extracted.append((quote_text, speaker_text))

    return extracted


def find_article_container(soup: BeautifulSoup):
    return (
        soup.find(id="news-release-container")
        or soup.find(class_="news-release-container")
        or soup.find("main")
        or soup
    )


def is_skippable_image(src: str) -> bool:
    basename = os.path.basename(urlparse(src).path)
    return basename in SKIP_IMAGE_BASENAMES


def normalize_image_src(page_url: str, src: str) -> str:
    return urljoin(page_url, src)


def infer_extension(image_url: str, content_type: str) -> str:
    parsed_path = urlparse(image_url).path
    basename = os.path.basename(parsed_path)
    if "." in basename:
        ext = os.path.splitext(basename)[1].lower()
        if ext:
            return ext

    content_type = (content_type or "").split(";")[0].strip().lower()
    if content_type == "image/jpeg":
        return ".jpg"
    if content_type == "image/png":
        return ".png"
    if content_type == "image/gif":
        return ".gif"
    if content_type == "image/webp":
        return ".webp"
    if content_type == "image/svg+xml":
        return ".svg"
    return ".bin"


def extract_images_from_html(page_url: str, html: str) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    container = find_article_container(soup)
    images: List[Dict[str, str]] = []

    for img in container.find_all("img"):
        src = normalize_space(img.get("src"))
        if not src:
            continue
        src = normalize_image_src(page_url, src)
        if is_skippable_image(src):
            continue
        images.append(
            {
                "source_url": src,
                "alt_text": normalize_space(img.get("alt", "")),
            }
        )

    return images


def fetch_article_assets(
    session: requests.Session, url: str, lang: str, timeout: int
) -> Tuple[List[Tuple[str, str]], List[Dict[str, str]]]:
    if not normalize_space(url):
        return [], []

    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    html = response.text
    return extract_quotes_from_html(html, lang), extract_images_from_html(url, html)


def build_quote_rows(
    row: Dict[str, str],
    quotes_en: List[Tuple[str, str]],
    quotes_fr: List[Tuple[str, str]],
) -> List[Dict[str, str]]:
    count = max(len(quotes_en), len(quotes_fr))
    output_rows: List[Dict[str, str]] = []

    for quote_index in range(count):
        quote_en, speaker_en = quotes_en[quote_index] if quote_index < len(quotes_en) else ("", "")
        quote_fr, speaker_fr = quotes_fr[quote_index] if quote_index < len(quotes_fr) else ("", "")
        output_rows.append(
            {
                "hash": row.get("hash", ""),
                "PUBDATE": row.get("PUBDATE", ""),
                "TITLE_URL_EN": row.get("TITLE_URL_EN", ""),
                "TITLE_URL_FR": row.get("TITLE_URL_FR", ""),
                "QUOTE_INDEX": quote_index + 1,
                "QUOTE_EN": quote_en,
                "SPEAKER_EN": speaker_en,
                "QUOTE_FR": quote_fr,
                "SPEAKER_FR": speaker_fr,
            }
        )

    return output_rows


def build_image_rows(
    session: requests.Session,
    row: Dict[str, str],
    images_en: List[Dict[str, str]],
    images_fr: List[Dict[str, str]],
    images_dir: str,
    timeout: int,
) -> List[Dict[str, str]]:
    article_hash = row.get("hash", "")
    article_dir = image_directory_for_hash(images_dir, article_hash)
    if os.path.isdir(article_dir):
        shutil.rmtree(article_dir)
    os.makedirs(article_dir, exist_ok=True)

    count = max(len(images_en), len(images_fr))
    output_rows: List[Dict[str, str]] = []

    for image_index in range(count):
        image_en = images_en[image_index] if image_index < len(images_en) else {}
        image_fr = images_fr[image_index] if image_index < len(images_fr) else {}
        source_url = image_en.get("source_url") or image_fr.get("source_url")
        if not source_url:
            continue

        response = session.get(source_url, timeout=timeout)
        response.raise_for_status()
        extension = infer_extension(source_url, response.headers.get("Content-Type", ""))
        filename = f"{article_hash}_{image_index + 1:03d}{extension}"
        destination_path = os.path.join(article_dir, filename)
        with open(destination_path, "wb") as fh:
            fh.write(response.content)

        output_rows.append(
            {
                "hash": row.get("hash", ""),
                "PUBDATE": row.get("PUBDATE", ""),
                "TITLE_URL_EN": row.get("TITLE_URL_EN", ""),
                "TITLE_URL_FR": row.get("TITLE_URL_FR", ""),
                "IMAGE_INDEX": image_index + 1,
                "FILENAME": filename,
                "ALT_TEXT_EN": image_en.get("alt_text", ""),
                "ALT_TEXT_FR": image_fr.get("alt_text", ""),
                "FILE_PATH": destination_path.replace("\\", "/"),
            }
        )

    if not output_rows:
        shutil.rmtree(article_dir, ignore_errors=True)

    return output_rows


def valid_cached_state(cached_state: Dict[str, str]) -> bool:
    if not cached_state:
        return False
    if int(cached_state.get("version", 0)) < STATE_VERSION:
        return False
    if cached_state.get("status") not in {"ok", "not_found"}:
        return False
    return "quote_count" in cached_state and "image_count" in cached_state


def process_article(
    row: Dict[str, str], images_dir: str, timeout: int
) -> Tuple[str, List[Dict[str, str]], List[Dict[str, str]], Dict[str, str]]:
    key = article_key(row)
    session = make_session()

    try:
        quotes_en, images_en = fetch_article_assets(session, row.get("TITLE_URL_EN", ""), "en", timeout)
        quotes_fr, images_fr = fetch_article_assets(session, row.get("TITLE_URL_FR", ""), "fr", timeout)
    except requests.HTTPError as exc:
        status_code = getattr(exc.response, "status_code", None)
        if status_code == 404:
            shutil.rmtree(
                image_directory_for_hash(images_dir, row.get("hash", "")),
                ignore_errors=True,
            )
            state_row = {
                "version": STATE_VERSION,
                "hash": row.get("hash", ""),
                "PUBDATE": row.get("PUBDATE", ""),
                "TITLE_URL_EN": row.get("TITLE_URL_EN", ""),
                "TITLE_URL_FR": row.get("TITLE_URL_FR", ""),
                "quote_count": -1,
                "image_count": -1,
                "status": "not_found",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            return key, [], [], state_row
        raise

    quote_rows = build_quote_rows(row, quotes_en, quotes_fr)
    image_rows = build_image_rows(session, row, images_en, images_fr, images_dir, timeout)
    state_row = {
        "version": STATE_VERSION,
        "hash": row.get("hash", ""),
        "PUBDATE": row.get("PUBDATE", ""),
        "TITLE_URL_EN": row.get("TITLE_URL_EN", ""),
        "TITLE_URL_FR": row.get("TITLE_URL_FR", ""),
        "quote_count": len(quote_rows),
        "image_count": len(image_rows),
        "status": "ok",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return key, quote_rows, image_rows, state_row


def prune_to_current_keys(
    current_keys: set,
    existing_quotes: Dict[str, List[Dict[str, str]]],
    existing_images: Dict[str, List[Dict[str, str]]],
    state: Dict[str, Dict[str, str]],
) -> Tuple[Dict[str, List[Dict[str, str]]], Dict[str, List[Dict[str, str]]], Dict[str, Dict[str, str]]]:
    kept_quotes = {key: rows for key, rows in existing_quotes.items() if key in current_keys}
    kept_images = {key: rows for key, rows in existing_images.items() if key in current_keys}
    kept_state = {key: value for key, value in state.items() if key in current_keys}
    return kept_quotes, kept_images, kept_state


def cleanup_removed_article_dirs(images_dir: str, current_hashes: set) -> None:
    if not os.path.isdir(images_dir):
        return
    for entry in os.listdir(images_dir):
        full_path = os.path.join(images_dir, entry)
        if os.path.isdir(full_path) and entry not in current_hashes:
            shutil.rmtree(full_path, ignore_errors=True)


def apply_counts_to_input_rows(
    input_rows: List[Dict[str, str]],
    state: Dict[str, Dict[str, str]],
) -> None:
    for row in input_rows:
        key = article_key(row)
        cached_state = state.get(key)
        if valid_cached_state(cached_state):
            row["QUOTE_COUNT"] = str(cached_state.get("quote_count", ""))
            row["IMAGE_COUNT"] = str(cached_state.get("image_count", ""))
        else:
            row.setdefault("QUOTE_COUNT", "")
            row.setdefault("IMAGE_COUNT", "")


def ensure_count_fields(fieldnames: List[str]) -> List[str]:
    updated = list(fieldnames)
    for field in COUNT_FIELDS:
        if field not in updated:
            updated.append(field)
    return updated


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    input_rows, input_fieldnames = load_input_rows(args.input)
    current_keys = {article_key(row) for row in input_rows}
    current_hashes = {normalize_space(row.get("hash", "")) for row in input_rows}

    existing_quotes = {} if args.full_rebuild else load_existing_rows(
        args.quotes_output,
        ["QUOTE_INDEX", "QUOTE_EN", "SPEAKER_EN", "QUOTE_FR", "SPEAKER_FR"],
    )
    existing_images = {} if args.full_rebuild else load_existing_rows(
        args.images_output,
        ["IMAGE_INDEX", "FILENAME", "ALT_TEXT_EN", "ALT_TEXT_FR", "FILE_PATH"],
    )
    state = {} if args.full_rebuild else load_state(args.state)
    existing_quotes, existing_images, state = prune_to_current_keys(
        current_keys, existing_quotes, existing_images, state
    )

    rows_by_key_quotes: Dict[str, List[Dict[str, str]]] = {}
    rows_by_key_images: Dict[str, List[Dict[str, str]]] = {}
    rows_needing_fetch: List[Dict[str, str]] = []

    for row in input_rows:
        key = article_key(row)
        cached_state = state.get(key)
        if valid_cached_state(cached_state):
            rows_by_key_quotes[key] = existing_quotes.get(key, [])
            rows_by_key_images[key] = existing_images.get(key, [])
        else:
            rows_needing_fetch.append(row)

    if args.limit > 0:
        rows_to_fetch = rows_needing_fetch[: args.limit]
    else:
        rows_to_fetch = rows_needing_fetch

    logging.info(
        "Preparing quote and image extraction for %s articles (%s cached, %s to fetch this run, %s still pending).",
        len(input_rows),
        len(input_rows) - len(rows_needing_fetch),
        len(rows_to_fetch),
        max(len(rows_needing_fetch) - len(rows_to_fetch), 0),
    )

    os.makedirs(args.images_dir, exist_ok=True)
    cleanup_removed_article_dirs(args.images_dir, current_hashes)

    with ThreadPoolExecutor(max_workers=max(args.max_workers, 1)) as executor:
        future_to_key = {
            executor.submit(process_article, row, args.images_dir, args.timeout): article_key(row)
            for row in rows_to_fetch
        }
        for future in as_completed(future_to_key):
            key = future_to_key[future]
            try:
                article_key_value, quote_rows, image_rows, state_row = future.result()
            except Exception as exc:
                logging.warning("Failed to process %s: %s", key, exc)
                continue

            rows_by_key_quotes[article_key_value] = quote_rows
            rows_by_key_images[article_key_value] = image_rows
            state[article_key_value] = state_row

    ordered_quote_rows: List[Dict[str, str]] = []
    ordered_image_rows: List[Dict[str, str]] = []
    for row in input_rows:
        key = article_key(row)
        quote_rows = rows_by_key_quotes.get(key, [])
        image_rows = rows_by_key_images.get(key, [])
        quote_rows.sort(key=lambda value: int(value["QUOTE_INDEX"]))
        image_rows.sort(key=lambda value: int(value["IMAGE_INDEX"]))
        ordered_quote_rows.extend(quote_rows)
        ordered_image_rows.extend(image_rows)

    apply_counts_to_input_rows(input_rows, state)
    write_rows(args.quotes_output, QUOTE_OUTPUT_FIELDS, ordered_quote_rows)
    write_rows(args.images_output, IMAGE_OUTPUT_FIELDS, ordered_image_rows)
    write_state(args.state, state)
    write_input_rows(args.input, ensure_count_fields(input_fieldnames), input_rows)

    logging.info(
        "Wrote %s quote rows to %s and %s image rows to %s.",
        len(ordered_quote_rows),
        args.quotes_output,
        len(ordered_image_rows),
        args.images_output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
