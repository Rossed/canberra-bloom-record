"""Resolve every extracted name to an accepted taxon via the ALA name-matching service (cached).
Adds to each plant: accepted_species, accepted_name, family, match_type, vernacular, analysis_key."""
import os, re, json, urllib.request, urllib.parse, concurrent.futures as cf, time, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "ala_cache.json")
cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
# both series: ANBG "In Flower This Week" (1997-2016) and Friends "Flowers, Fruit & Foliage" (2016-)
d = json.load(open(os.path.join(ROOT, "data", "extract_iftw.json")))
fff = os.path.join(ROOT, "data", "extract_fff.json")
if os.path.exists(fff):
    d += json.load(open(fff))
d.sort(key=lambda r: r["date"])

def query_for(p):
    if p["epithet"] and "×" not in p["epithet"]:
        q = f"{p['genus']} {p['epithet']}"
        if p["infra"]:
            q += " " + p["infra"]
        return q
    return p["genus"]

def ala(q):
    if q in cache:
        return q, cache[q]
    url = "https://api.ala.org.au/namematching/api/searchByClassification?kingdom=Plantae&scientificName=" + urllib.parse.quote(q)
    for a in range(4):
        try:
            r = json.load(urllib.request.urlopen(url, timeout=30))
            keep = {k: r.get(k) for k in ["success", "scientificName", "rank", "matchType", "family", "genus", "species",
                                          "vernacularName", "synonymType", "issues", "order"]}
            return q, keep
        except Exception as e:
            time.sleep(2 + a * 3)
    return q, None

# retry failures (e.g. plant/animal homonyms like Scaevola) with kingdom=Plantae
for q in [q for q, v in cache.items() if not (v or {}).get("success")]:
    del cache[q]
qs = sorted({query_for(p) for r in d for p in r["plants"]} - set(cache))
print("querying", len(qs))
with cf.ThreadPoolExecutor(4) as ex:
    for i, (q, res) in enumerate(ex.map(ala, qs)):
        if res is not None:
            cache[q] = res
        if i % 250 == 0:
            json.dump(cache, open(CACHE, "w"))
json.dump(cache, open(CACHE, "w"), indent=0)

# reviewer corrections exported from the site's "Check accuracy" screen (see 08_apply_validation.py)
OV_PATH = os.path.join(ROOT, "data", "name_overrides.json")
overrides = json.load(open(OV_PATH)) if os.path.exists(OV_PATH) else {}
stats = collections.Counter()
for r in d:
    for p in r["plants"]:
        res = cache.get(query_for(p)) or {}
        ok = bool(res.get("success") and res.get("family"))
        hybrid = "×" in p["name"] or "×" in (p["epithet"] or "")
        if hybrid:
            species, src = None, None
        elif p["species_key"] in overrides:
            species, src = overrides[p["species_key"]], "reviewer override"
        elif ok and res.get("rank") not in ("genus", "family") and res.get("matchType") != "higherMatch":
            species, src = res.get("species"), "ALA accepted"
        elif ok and p["epithet"] and not hybrid:
            species, src = f"{p['genus'] if res.get('matchType') != 'fuzzyMatch' else res.get('genus')} {p['epithet']}", "as written (ALA matched genus only)"
        else:
            species, src = None, None
        p["accepted_name"] = res.get("scientificName") if ok else None
        p["accepted_species"] = species
        p["species_source"] = src
        p["family"] = res.get("family") if ok else None
        p["match_type"] = res.get("matchType") if res else "no-response"
        p["vernacular"] = res.get("vernacularName") if ok else None
        p["renamed"] = bool(species and src == "ALA accepted" and species != f"{p['genus']} {p['epithet']}" and not p["cultivar"])
        # Analysis rule: a record is used only if the leaflet prints BOTH the genus (in full) and the species name.
        raw = p["raw"].strip(" ,.;:").replace("\u2018", "'").replace("\u2019", "'")
        genus_abbrev = bool(re.match(r"^[A-Z]\.\s", raw))
        if hybrid:
            p["analysis_key"], p["excluded"] = None, "hybrid (not analysed)"
        elif not p["epithet"]:
            p["analysis_key"] = None
            p["excluded"] = "no species name printed (genus and cultivar only)" if p["cultivar"] else "no species name printed (genus only)"
        elif genus_abbrev:
            p["analysis_key"], p["excluded"] = None, "genus abbreviated in the leaflet (not printed in full)"
        elif not species:
            p["analysis_key"], p["excluded"] = None, "name not recognised by the Atlas of Living Australia"
        elif p["cultivar"]:
            p["analysis_key"], p["excluded"] = f"{species} '{p['cultivar']}'", None
        else:
            p["analysis_key"], p["excluded"] = species, None
        stats["species" if species else "genus-only" if p["family"] else "unmatched"] += 1
        stats["renamed"] += p["renamed"]
json.dump(d, open(os.path.join(ROOT, "data", "brochures.json"), "w"), indent=0, ensure_ascii=False)
print(stats)
un = collections.Counter(p["name"] for r in d for p in r["plants"] if not p["family"])
print("unmatched sample:", un.most_common(40))
rn = collections.Counter((p["species_key"], p["accepted_species"]) for r in d for p in r["plants"] if p["renamed"])
print("renamed sample:", rn.most_common(25))
