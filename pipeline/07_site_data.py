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

# every printed name that ALA mapped to a different accepted species, for reviewer checking
import collections
ren = collections.OrderedDict()
for r in D:
    for pl in r["plants"]:
        if pl.get("renamed") or pl.get("species_source") == "reviewer override":
            k = (pl["species_key"], pl["accepted_species"])
            e = ren.setdefault(k, dict(printed=pl["species_key"], accepted=pl["accepted_species"], family=pl.get("family"),
                                       n=0, cross_genus=pl["genus"] != (pl["accepted_species"] or " ").split()[0],
                                       source=pl.get("species_source"), example=r["id"]))
            e["n"] += 1
json.dump(sorted(ren.values(), key=lambda e: (not e["cross_genus"], -e["n"])), open(os.path.join(ROOT, "site", "data", "renames.json"), "w"),
          separators=(",", ":"), ensure_ascii=False)
print(len(ren), "renamed names;", sum(e["cross_genus"] for e in ren.values()), "change genus")
