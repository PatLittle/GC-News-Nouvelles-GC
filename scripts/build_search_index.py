#!/usr/bin/env python3
import csv, json, re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEWS_CSV = ROOT / "combined_news.csv"
QUOTES_CSV = ROOT / "combined_news_quotes.csv"
IMAGES_CSV = ROOT / "combined_news_images.csv"
OUT_JSON = ROOT / "docs" / "search-data.json"
RAW_BASE = "https://raw.githubusercontent.com/PatLittle/GC-News-Nouvelles-GC/main/"

EXCLUDED_IMAGE_FILENAMES = {
    "1740510181215.png", "1670521263418.jpg", "1659473302212.jpg", "1690916130422.jpg",
    "1690916350787.jpg", "1776957674516.jpg", "1690916184988.jpg", "1690915715898.jpg", "1678892852520.jpg", "1688133723724.jpg"
}

KEEP_TITLES = {
"Chief of the Defence Staff","Minister of Municipal Affairs","CEO and General Secretary of Canada Soccer",
"Minister of Environment and Climate Change and Minister responsible for the Regional Development Corporation"
}

def norm(v): return (v or "").strip()
def low(v): return norm(v).lower()
def rows(p):
    with p.open("r",encoding="utf-8-sig",newline="") as f: return list(csv.DictReader(f))

def parse_date(v):
    v=norm(v)
    for fmt in ("%Y-%m-%d","%Y-%m-%d %H:%M:%S","%Y/%m/%d","%d-%m-%Y"):
        try: return datetime.strptime(v[:19],fmt).date().isoformat()
        except: pass
    return v[:10] if v else ""

def split_list(v):
    if not norm(v): return []
    return [x.strip() for x in re.split(r",\s+(?=[A-Z])", norm(v)) if x.strip()]

HONORIFICS_RE = re.compile(r"^(?:The Honourable|His worship|His Worship|Her Worship|His Excellency|The Rt\. Hon\.|The Hon\.|The Right Honourable)\s+", re.IGNORECASE)

def strip_honorifics(name):
    n = norm(name)
    prev = None
    while n and n != prev:
        prev = n
        n = HONORIFICS_RE.sub("", n).strip()
    return n

def tokenize(*parts):
    c="".join(ch if ch.isalnum() else " " for ch in " ".join(low(p) for p in parts if p))
    return sorted({t for t in c.split() if len(t)>1})

def parse_speaker_title_org(raw_speaker, raw_org, quote_text):
    sp=norm(raw_speaker); org=norm(raw_org)
    if not sp and quote_text:
        m=re.search(r"[\-–]\s*([^,\n]{2,80})(?:,\s*(.{2,200}))?$", quote_text)
        if m: sp, org = norm(m.group(1)), norm(m.group(2))
    if '<em>' in sp.lower() or '</em>' in sp.lower(): sp=''
    if sp and sp.lower() in low(quote_text):
        if len(sp.split())>4 and not any(k.lower() in sp.lower() for k in ["minister","parliamentary","member"]): sp=''
    if org in KEEP_TITLES or org.startswith("Parliamentary Secretary to the Minister of") or org.startswith("Member of Parliament for"):
        return sp, org, ""
    return sp, org, ""

news_rows, quote_rows, image_rows = rows(NEWS_CSV), rows(QUOTES_CSV), rows(IMAGES_CSV)
articles={}
for r in news_rows:
    h=norm(r.get('hash') or r.get('HASH'))
    if not h: continue
    articles[h]={"hash":h,"title":norm(r.get('TITLE_TEXT_EN') or r.get('TITLE_EN')),"url":norm(r.get('TITLE_URL_EN') or r.get('URL')),
                 "date":parse_date(r.get('PUBDATE') or r.get('DATE')),"dept_en":norm(r.get('DEPT_EN')),"type_en":norm(r.get('TYPE_EN')),
                 "topic_en":split_list(r.get('TOPIC_EN')),"subject_en":split_list(r.get('SUBJECT_EN'))}

quotes=[]; images=[]; qidx=defaultdict(list); iidx=defaultdict(list)
for i,r in enumerate(quote_rows):
    h=norm(r.get('hash') or r.get('HASH')); a=articles.get(h,{})
    qt=norm(r.get('QUOTE_EN') or r.get('QUOTE_TEXT') or r.get('TEXT'))
    sp,title,org=parse_speaker_title_org(r.get('SPEAKER_NAME_EN') or r.get('SPEAKER_EN'), r.get('SPEAKER_ORGANIZATION_EN') or r.get('ORG'), qt)
    sp = strip_honorifics(sp)
    raw_title = norm(r.get('SPEAKER_TITLE_EN'))
    if raw_title:
        title = raw_title
    q={"id":f"q{i}","hash":h,"quote_text":qt,"speaker":sp,"speaker_title":title,"org":org,
       "date":a.get('date',parse_date(r.get('PUBDATE'))),"dept_en":a.get('dept_en',''),"type_en":a.get('type_en',''),
       "topic_en":a.get('topic_en',[]),"subject_en":a.get('subject_en',[]),"article_title":a.get('title',''),"article_url":a.get('url','')}
    quotes.append(q)
    for t in tokenize(qt,sp,title,org,q['dept_en']," ".join(q['topic_en'])," ".join(q['subject_en'])): qidx[t].append(q['id'])

for i,r in enumerate(image_rows):
    h=norm(r.get('hash') or r.get('HASH')); a=articles.get(h,{})
    fp=norm(r.get('FILE_PATH')); ext=fp.rsplit('.',1)[-1].lower() if '.' in fp else ''
    if fp.rsplit('/',1)[-1] in EXCLUDED_IMAGE_FILENAMES:
        continue
    im={"id":f"img{i}","hash":h,"alt_text":norm(r.get('ALT_TEXT_EN') or r.get('ALT_TEXT')),"file_type":ext,"file_path":fp,"url":f"{RAW_BASE}{fp}" if fp else "",
        "date":a.get('date',parse_date(r.get('PUBDATE'))),"dept_en":a.get('dept_en',''),"type_en":a.get('type_en',''),
        "topic_en":a.get('topic_en',[]),"subject_en":a.get('subject_en',[]),"article_title":a.get('title',''),"article_url":a.get('url','')}
    images.append(im)
    for t in tokenize(im['alt_text'],im['file_type'],im['dept_en']," ".join(im['topic_en'])," ".join(im['subject_en'])): iidx[t].append(im['id'])

facets={
"dept_en":sorted({x['dept_en'] for x in quotes+images if x.get('dept_en')}),
"topic_en":sorted({t for x in quotes+images for t in x.get('topic_en',[])}),
"subject_en":sorted({s for x in quotes+images for s in x.get('subject_en',[])}),
"speaker":sorted({x['speaker'] for x in quotes if x.get('speaker')}),
"org":sorted({x['org'] for x in quotes if x.get('org')}),
"file_type":sorted({x['file_type'] for x in images if x.get('file_type')})
}
payload={"meta":{"generated_at_utc":datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z'),"counts":{"articles":len(articles),"quotes":len(quotes),"images":len(images)}},"articles":list(articles.values()),"quotes":quotes,"images":images,"facets":facets,"indexes":{"quote_tokens":dict(qidx),"image_tokens":dict(iidx)}}
OUT_JSON.parent.mkdir(parents=True,exist_ok=True)
OUT_JSON.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print(f"Wrote {OUT_JSON} with {len(quotes)} quotes and {len(images)} images")
