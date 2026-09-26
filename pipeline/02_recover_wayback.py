"""Recover brochures that 404 on the live site from the Wayback Machine (old /iftw.old/ URL scheme)."""
import json, os, re, time, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
log = json.load(open(os.path.join(ROOT, "data", "download_log.json")))
cdx = {}
for line in open(os.path.join(ROOT, "data", "wayback_cdx_iftw.txt")):
    orig, ts, code = line.split()
    key = re.sub(r"^https?://(www\.)?anbg\.gov\.au(:80)?", "", orig)
    cdx.setdefault(key, ts)  # earliest capture
# keep earlier recoveries: once a file is cached, 01_download no longer reports it as a failure
REC_PATH = os.path.join(ROOT, "data", "wayback_recovered.json")
recovered = json.load(open(REC_PATH)) if os.path.exists(REC_PATH) else {}
for f, _ in [x for x in log["failures"] if x[0] not in recovered]:
    m = re.match(r"iftw-(\d+)-(\d\d)-(\d\d)\.html", f)
    y, mo, d = m.groups()
    cands = [f"/iftw.old/iftw_{y[-2:]}_{mo}_{d}.html", f"/iftw.old/iftw-{y}-{mo}-{d}.htm",
             f"/iftw.old/iftw-{y}-{mo}-{d}.html", f"/iftw.old/iftw-{y[-2:]}-{mo}-{d}.html"]
    hit = next((c for c in cands if c in cdx), None)
    if not hit:
        print("no wayback copy:", f); continue
    url = f"http://web.archive.org/web/{cdx[hit]}id_/http://www.anbg.gov.au{hit}"
    for a in range(4):
        try:
            data = urllib.request.urlopen(url, timeout=60).read(); break
        except Exception as e:
            print("retry", f, e); time.sleep(5)
    else:
        continue
    open(os.path.join(RAW, f), "wb").write(data)
    recovered[f] = url
    time.sleep(1)
json.dump(recovered, open(os.path.join(ROOT, "data", "wayback_recovered.json"), "w"), indent=1)
print("recovered", len(recovered), "of", len(log["failures"]))
