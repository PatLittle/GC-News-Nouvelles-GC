#!/usr/bin/env python3
"""
Scrape English and French half-masting notices from canada.ca, merge by hidden id, and save combined CSV to data/half_masting_combined.csv
Requirements: requests, beautifulsoup4
"""

import os
import sys
import csv
from typing import Dict, List

import requests
from bs4 import BeautifulSoup

URLS = {
    'en': 'https://www.canada.ca/en/canadian-heritage/services/half-masting-notices.html',
    'fr': 'https://www.canada.ca/fr/patrimoine-canadien/services/avis-mise-berne.html',
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}


def clean_text(node):
    if node is None:
        return ''
    # Join stripped strings to collapse whitespace
    return ' '.join(node.stripped_strings)


def scrape(url: str) -> List[Dict[str, str]]:
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.content, 'html.parser')

    rows = []
    # Look for table body rows
    for tbody in soup.find_all('tbody'):
        for tr in tbody.find_all('tr'):
            tds = tr.find_all('td')
            if not tds:
                continue

            # id is expected in a span.hidden inside the first column
            id_span = tr.find('span', class_='hidden')
            row_id = id_span.get_text(strip=True) if id_span else None

            # Fallback: generate a stable id from the first column text
            if not row_id:
                first_text = clean_text(tds[0]) if len(tds) > 0 else ''
                row_id = 'gen-' + str(abs(hash(first_text)))

            notice = clean_text(tds[0]) if len(tds) > 0 else ''
            period = clean_text(tds[1]) if len(tds) > 1 else ''
            location = clean_text(tds[2]) if len(tds) > 2 else ''
            details = clean_text(tds[3]) if len(tds) > 3 else ''

            rows.append({
                'id': row_id,
                'notice': notice,
                'period': period,
                'location': location,
                'details': details,
            })
    return rows


def merge_rows(en_rows: List[Dict[str, str]], fr_rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    en_map: Dict[str, dict] = {r['id']: r for r in en_rows}
    fr_map: Dict[str, dict] = {r['id']: r for r in fr_rows}

    all_ids = sorted(set(en_map) | set(fr_map))
    merged = []
    for _id in all_ids:
        en = en_map.get(_id, {})
        fr = fr_map.get(_id, {})
        merged.append({
            'id': _id,
            'notice_en': en.get('notice', ''),
            'period_en': en.get('period', ''),
            'location_en': en.get('location', ''),
            'details_en': en.get('details', ''),
            'notice_fr': fr.get('notice', ''),
            'period_fr': fr.get('period', ''),
            'location_fr': fr.get('location', ''),
            'details_fr': fr.get('details', ''),
        })
    return merged


def write_csv(path: str, rows: List[Dict[str, str]]):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fieldnames = [
        'id',
        'notice_en', 'period_en', 'location_en', 'details_en',
        'notice_fr', 'period_fr', 'location_fr', 'details_fr',
    ]
    with open(path, 'w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


if __name__ == '__main__':
    try:
        en_rows = scrape(URLS['en'])
        fr_rows = scrape(URLS['fr'])
    except Exception as e:
        print('Error scraping pages:', e, file=sys.stderr)
        sys.exit(1)

    merged = merge_rows(en_rows, fr_rows)
    out_path = 'data/half_masting_combined.csv'
    write_csv(out_path, merged)

    print(f'EN rows: {len(en_rows)}, FR rows: {len(fr_rows)}, merged: {len(merged)}')
