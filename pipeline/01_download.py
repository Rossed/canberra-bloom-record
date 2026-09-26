"""Download every IFTW brochure listed on the ANBG archive index (idempotent)."""
import re, os, time, concurrent.futures as cf, urllib.request, json
BASE = "https://www.anbg.gov.au/gardens/visiting/iftw/iftw-archive/"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
idx = os.path.join(ROOT, "data", "archive_index.html")
if not os.path.exists(idx):
    urllib.request.urlretrieve(BASE + "index.html", idx)
s = open(idx, encoding="latin-1").read()
links = re.findall(r'(?i)href\s*=\s*["\']?(iftw[^"\' >]+\.html)', s)
seen, files = set(), []
for l in links:
    if l not in seen:
        seen.add(l); files.append(l)
print(len(files), "brochure links")

def get(f):
    p = os.path.join(RAW, f)
    if os.path.exists(p) and os.path.getsize(p) > 1000:
        return f, "cached"
    for attempt in range(3):
        try:
            req = urllib.request.Request(BASE + f, headers={"User-Agent": "Mozilla/5.0 (research; iftw phenology)"})
            data = urllib.request.urlopen(req, timeout=30).read()
            open(p, "wb").write(data)
            return f, "ok"
        except Exception as e:
            err = str(e); time.sleep(2)
    return f, "FAIL " + err

with cf.ThreadPoolExecutor(6) as ex:
    res = list(ex.map(get, files))
fails = [r for r in res if r[1].startswith("FAIL")]
json.dump({"links": files, "failures": fails}, open(os.path.join(ROOT, "data", "download_log.json"), "w"), indent=1)
print("failures:", fails)
