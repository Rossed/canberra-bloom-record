# Canberra Bloom Record

Extraction + phenology analysis of the ANBG "In Flower This Week" archive (899 issues, Apr 1997 – Aug 2016).

- `data/raw/` – every brochure HTML (847 from anbg.gov.au, 52 recovered from the Wayback Machine; see `data/wayback_recovered.json`)
- `data/brochures.json` – full extraction (plants, sections, colours, stage, context, ALA taxonomy, flags)
- `data/ala_cache.json` – Atlas of Living Australia name-matching responses
- `data/climate/` – BOM ACORN-SAT v2.6 Canberra (070351) Tmax/Tmin via BOM anon FTP; ERA5 rainfall via Open-Meteo
- `pipeline/01…07` – numbered steps; `./run_all.sh` rebuilds everything
- `site/` – static website (page 1 extraction validation, page 2 analysis). `python3 -m http.server 8765 --directory site`

Live site: https://rossed.github.io/canberra-bloom-record/

Note: `data/raw/` (the original brochure HTML) is not committed; `pipeline/01_download.py` and `02_recover_wayback.py` fetch it.
Credits: brochures © Australian National Botanic Gardens volunteers; taxonomy from ALA; temperature BOM ACORN-SAT; rainfall ERA5 via Open-Meteo.
