"""Trim brochures.json into the compact form the website loads."""
import os, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = json.load(open(os.path.join(ROOT, "data", "brochures.json")))
out = []
for r in D:
    out.append(dict(id=r["id"], d=r["date"], url=r["source_url"], src=r["source"], hd=r["heading_date"], dr=r["date_range"],
                    au=r["author"], intro=r["intro"][:300], np=r["n_plants"], fl=r["flags"], mode=r["extraction_mode"],
                    wx=r["weather_mentions"], fa=r["fauna_mentions"], cap=r["photo_captions"], lm=r["possible_misses"],
                    inc=r["incidental_mentions"], qs=r["qa_section_refs"], qp=r["qa_plants_with_section"],
                    p=[[pl["list_no"], pl["raw"], pl["taxon_key"], pl.get("accepted_species"), pl.get("species_source"),
                        pl.get("family"), pl.get("renamed"), ",".join(pl["sections"]), pl.get("common_name") or pl.get("vernacular"),
                        ",".join(pl["colours"]), pl["stage"], pl["phase"], pl["context"][:260], pl.get("analysis_key")]
                       for pl in r["plants"]]))
json.dump(out, open(os.path.join(ROOT, "site", "data", "brochures.json"), "w"), separators=(",", ":"), ensure_ascii=False)
print(os.path.getsize(os.path.join(ROOT, "site", "data", "brochures.json")) / 1e6, "MB")
