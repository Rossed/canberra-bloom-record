"""Fold reviewer results (exported from the site's "Check accuracy" screen) back into the pipeline.

Put exported files in validation/*.json, then run this script. It
  1. prints extraction accuracy (precision / recall with 95% Wilson intervals), overall and by era;
  2. writes data/name_overrides.json for every name change a reviewer marked wrong
     (the printed name is kept instead of ALA's accepted name). Re-run 05-07 afterwards.
"""
import os, json, glob, math, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, c - h, c + h)

files = sorted(glob.glob(os.path.join(ROOT, "validation", "*.json")))
if not files:
    raise SystemExit("No files in validation/. Export results from the site's Check accuracy screen first.")
by_era = collections.defaultdict(lambda: collections.Counter())
renames = {}
for f in files:
    data = json.load(open(f))
    who = data.get("reviewer") or os.path.basename(f)
    for bid, b in data.get("brochures", {}).items():
        if not b.get("done"):
            continue
        y = int(b.get("date", "0000")[:4])
        era = "1997-2004" if y < 2005 else "2005-2013" if y < 2014 else "2014-2016"
        c = by_era[era]
        for v in b.get("rows", {}).values():
            c[v["verdict"]] += 1
        c["missed"] += len([m for m in b.get("missed", []) if m.strip()])
        c["brochures"] += 1
    for key, v in data.get("renames", {}).items():
        renames.setdefault(key, []).append((who, v))

tot = collections.Counter()
for era, c in sorted(by_era.items()):
    tot.update(c)
for era, c in sorted(by_era.items()) + [("ALL", tot)]:
    found = c["ok"] + c["wrong_name"]
    prec = wilson(found, found + c["not_plant"])      # extracted records that really are featured plants
    rec = wilson(found, found + c["missed"])          # featured plants that were extracted
    name = wilson(c["ok"], found)                     # extracted plants whose name was parsed correctly
    checked = found + c["not_plant"]
    fmt = lambda t: "–" if t[0] is None else f"{100*t[0]:.1f}% ({100*t[1]:.1f}–{100*t[2]:.1f})"
    print(f"{era:10} brochures {c['brochures']:3}  records {checked:4}  precision {fmt(prec)}  recall {fmt(rec)}  name accuracy {fmt(name)}")

ov_path = os.path.join(ROOT, "data", "name_overrides.json")
overrides = json.load(open(ov_path)) if os.path.exists(ov_path) else {}
for key, votes in renames.items():
    printed, accepted = key.split(" -> ")
    wrong = [v for _, v in votes if v.get("verdict") == "wrong"]
    ok = [v for _, v in votes if v.get("verdict") == "ok"]
    if len(wrong) > len(ok):
        overrides[printed] = (wrong[-1].get("correct") or printed).strip()
    elif ok and printed in overrides:
        del overrides[printed]
json.dump(overrides, open(ov_path, "w"), indent=1, ensure_ascii=False)
print(f"{len(overrides)} name overrides in data/name_overrides.json -> re-run 05, 06, 07 to apply")
