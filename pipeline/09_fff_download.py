"""Download every Friends of the ANBG "Flowers, Fruit & Foliage" (FFF) leaflet (Aug 2016 - present).

Sources (both index pages are saved to data/fff/):
  - old Friends site mirror  https://www.more.id.au/fbg1/pages.php?p=718   (2016 - Feb 2025; PDF links now dead)
  - current Friends site      https://fanbg.wpenginepowered.com/discover-the-gardens/flowers-fruit-and-foliage-walks/ (2022 - now)
Dead links are recovered from the Wayback Machine. Output: data/fff/pdf/FFF_YYYY-MM-DD.pdf + data/fff/download_log.json
"""
import os, re, json, time, datetime, html, urllib.request, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "fff")
PDF = os.path.join(OUT, "pdf")
os.makedirs(PDF, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}
INDEXES = {"index_old.html": "https://www.more.id.au/fbg1/pages.php?p=718",
           "index_new.html": "https://fanbg.wpenginepowered.com/discover-the-gardens/flowers-fruit-and-foliage-walks/"}
MON = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def get(url, timeout=90):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def date_from_name(url):
    n = urllib.parse.unquote(url.split("/")[-1]).lower()
    m = re.search(r"(20\d\d)[-_](\d{1,2})[-_](\d{1,2})", n)
    if m:
        return datetime.date(*map(int, m.groups()))
    m = re.search(r"(20\d\d)(\d\d)(\d\d)", n)
    if m:
        return datetime.date(*map(int, m.groups()))
    m = re.search(r"(\d{1,2})[ -]([a-z]{3})[a-z]*[ -](\d{2,4})", n)
    if m and m.group(2) in MON:
        y = int(m.group(3)); y = y + 2000 if y < 100 else y
        return datetime.date(y, MON[m.group(2)], int(m.group(1)))
    return None


def date_from_text(t):
    t = re.sub(r"\s+", " ", html.unescape(t)).lower()
    m = re.search(r"(\d{1,2})\s*([a-z]{3})?[a-z]*\.?\s*(\d{4})?\s*[-–—]", t)
    if not m:
        return None
    day = int(m.group(1))
    mons = [(x.start(), MON[x.group(1)]) for x in re.finditer(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*", t)]
    years = [int(y) for y in re.findall(r"\b(20\d\d)\b", t)]
    if not mons or not years:
        return None
    mon = MON[m.group(2)] if m.group(2) in MON else mons[0][1]
    year = years[0]
    if len(years) == 1 and mon == 12 and len(mons) > 1 and mons[-1][1] == 1:
        year -= 1  # "25 Dec - 7 Jan 2025"
    try:
        return datetime.date(year, mon, day)
    except ValueError:
        return None


links = []
for fname, url in INDEXES.items():
    p = os.path.join(OUT, fname)
    if not os.path.exists(p):
        open(p, "wb").write(get(url))
    s = open(p, encoding="utf-8", errors="replace").read()
    for href, text in re.findall(r'(?is)<a[^>]+href\s*=\s*["\']([^"\']+\.pdf)["\'][^>]*>(.*?)</a>', s):
        text = re.sub(r"<[^>]+>", " ", text)
        links.append(dict(href=html.unescape(href), text=re.sub(r"\s+", " ", html.unescape(text)).strip(), index=fname))

# one entry per PDF file; date from filename, else link text
by_file = {}
for l in links:
    key = urllib.parse.unquote(l["href"].split("/")[-1]).lower()
    e = by_file.setdefault(key, dict(file=key, hrefs=[], texts=[], index=set()))
    if l["href"] not in e["hrefs"]:
        e["hrefs"].append(l["href"])
    if re.search(r"\d", l["text"]) and l["text"] not in e["texts"]:
        e["texts"].append(l["text"])
    e["index"].add(l["index"])
issues = {}
problems = []
for e in by_file.values():
    dn = date_from_name(e["file"])
    dt = next((d for d in (date_from_text(t) for t in e["texts"]) if d), None)
    d = dn or dt
    if not d:
        problems.append(f"no date: {e['file']} {e['texts']}")
        continue
    if dn and dt and dn != dt:
        # leaflets start on a Wednesday; some filenames carry the end date or a typo
        pick = dt if (dt.weekday() == 2 and dn.weekday() != 2) else dn
        if abs((dn - dt).days) > 3:
            problems.append(f"filename {dn} vs link text {dt} ({e['texts'][0]}): using {pick}")
        d = pick
    # same fortnight listed twice (e.g. on both sites, or a re-upload) -> keep one, prefer the live site
    dup = next((k for k in issues if abs((k - d).days) <= 4), None)
    rec = dict(date=d.isoformat(), file=e["file"], hrefs=e["hrefs"], text=(e["texts"] or [""])[0], index=sorted(e["index"]))
    if dup:
        if "index_new.html" in e["index"] and "index_new.html" not in issues[dup]["index"]:
            issues[dup] = rec
        else:
            issues[dup].setdefault("alt_hrefs", []).extend(e["hrefs"])
        continue
    issues[d] = rec

# prefetched Wayback index of the old Drupal file store (one query instead of one per PDF)
CDX_PATH = os.path.join(OUT, "wayback_cdx_old.txt")
if not os.path.exists(CDX_PATH):
    open(CDX_PATH, "wb").write(get("http://web.archive.org/cdx/search/cdx?url=friendsanbg.org.au/sites/default/files/&matchType=prefix"
                                   "&output=txt&fl=original,timestamp,statuscode,mimetype&filter=statuscode:200&collapse=urlkey", 300))
cdx_idx = {}
for line in open(CDX_PATH):
    parts = line.split()
    if len(parts) >= 2:
        cdx_idx[urllib.parse.unquote(re.sub(r"^https?://(www\.)?|:80", "", parts[0])).lower()] = (parts[1], parts[0])


def wayback(url):
    k = urllib.parse.unquote(re.sub(r"^https?://(www\.)?|:80", "", url)).lower()
    if k in cdx_idx:
        ts, orig = cdx_idx[k]
        return f"https://web.archive.org/web/{ts}id_/{orig}"
    u = re.sub(r"^https?://(www\.)?", "", url)
    q = "http://web.archive.org/cdx/search/cdx?" + urllib.parse.urlencode(
        dict(url=u, output="json", fl="timestamp,original", filter="statuscode:200", limit="1"))
    for a in range(3):
        try:
            rows = json.loads(get(q, 60) or b"[]")
            if len(rows) > 1:
                ts, orig = rows[1]
                return f"https://web.archive.org/web/{ts}id_/{orig}"
            return None
        except Exception:
            time.sleep(4)
    return None


def wayback_all(url):
    """All complete-looking captures of a URL, largest first (early captures are sometimes truncated at 1 MB)."""
    u = re.sub(r"^https?://(www\.)?", "", url)
    q = "http://web.archive.org/cdx/search/cdx?" + urllib.parse.urlencode(
        dict(url=u, output="json", fl="timestamp,original,length", filter="statuscode:200"))
    for a in range(3):
        try:
            rows = json.loads(get(q, 90) or b"[]")[1:]
            rows.sort(key=lambda r: -int(r[2] or 0))
            return [f"https://web.archive.org/web/{ts}id_/{orig}" for ts, orig, _ in rows[:4]]
        except Exception:
            time.sleep(5 * (a + 1))
    return []


def valid_pdf(data):
    try:
        import pymupdf
        doc = pymupdf.open(stream=data, filetype="pdf")
        return doc.page_count > 0 and len(doc[0].get_text()) > 200
    except Exception:
        return False


def fetch(d):
    rec = issues[d]
    path = os.path.join(PDF, f"FFF_{d.isoformat()}.pdf")
    rec["path"] = os.path.relpath(path, ROOT)
    if os.path.exists(path) and os.path.getsize(path) > 10000 and valid_pdf(open(path, "rb").read()):
        rec.setdefault("status", "cached"); return rec
    got = None
    hrefs = rec["hrefs"] + rec.get("alt_hrefs", [])
    for href in hrefs:
        if "/sites/default/files/" in href:
            continue  # old Drupal store is gone; go straight to the Wayback Machine
        try:
            data = get(href.replace("http://", "https://"))
            if data[:4] == b"%PDF" and valid_pdf(data):
                got = (data, href, "live"); break
        except Exception:
            pass
    if not got:
        for href in hrefs:
            for wb in ([wayback(href)] + wayback_all(href)):
                if not wb:
                    continue
                for a in range(3):
                    try:
                        data = get(wb, 180)
                        if data[:4] == b"%PDF" and valid_pdf(data):
                            got = (data, wb, "wayback")
                        break
                    except Exception:
                        time.sleep(5 * (a + 1))
                if got:
                    break
            if got:
                break
    if got:
        open(path, "wb").write(got[0])
        rec.update(status=got[2], source_url=got[1])
    else:
        rec["status"] = "missing"
    print(d, rec["status"], flush=True)
    return rec


import concurrent.futures as cf
with cf.ThreadPoolExecutor(3) as pool:
    log = list(pool.map(fetch, sorted(issues)))
# keep "cached" entries' original source recorded from a previous run
prev = os.path.join(OUT, "download_log.json")
if os.path.exists(prev):
    old = {r["date"]: r for r in json.load(open(prev))["issues"]}
    for r in log:
        if r["status"] == "cached" and r["date"] in old and old[r["date"]].get("source_url"):
            r["status"], r["source_url"] = old[r["date"]]["status"], old[r["date"]]["source_url"]
        elif r["status"] == "cached":
            r["status"] = "wayback" if any("/sites/default/files/" in h for h in r["hrefs"]) else "live"
            r["source_url"] = (wayback(r["hrefs"][0]) if r["status"] == "wayback" else r["hrefs"][0])
json.dump(dict(issues=log, problems=problems), open(os.path.join(OUT, "download_log.json"), "w"), indent=1, default=list)
from collections import Counter
print(Counter(r["status"] for r in log), "problems:", len(problems))
for p in problems:
    print("  ", p)
