# Canberra Bloom Record

Extraction + phenology analysis of the Australian National Botanic Gardens flower-walk leaflets, 1997 to today:
- ANBG "In Flower This Week" archive: 899 web pages, Apr 1997 – Aug 2016
- Friends of the ANBG "Flowers, Fruit & Foliage": 248 PDFs, Aug 2016 – now (listed at friendsanbg.org.au and the older mirror at more.id.au; dead links recovered from the Wayback Machine)

- `data/raw/` – every brochure HTML (847 from anbg.gov.au, 52 recovered from the Wayback Machine; see `data/wayback_recovered.json`)
- `data/brochures.json` – full extraction (plants, sections, colours, stage, context, ALA taxonomy, flags)
- `data/ala_cache.json` – Atlas of Living Australia name-matching responses
- `data/fff/` – Friends leaflet indexes, download log (PDFs themselves are not committed; `09_fff_download.py` fetches them)
- `data/extract_iftw.json`, `data/extract_fff.json` – raw extractions; `05_taxonomy.py` merges them into `data/brochures.json`
- `data/climate/` – BOM ACORN-SAT v2.6 Canberra (070351) Tmax/Tmin via BOM anon FTP (to Dec 2024), then ERA5 bias-corrected per month (see `splice_check.json`); ERA5 rainfall via Open-Meteo
- `pipeline/01…07` – numbered steps; `./run_all.sh` rebuilds everything
- `site/` – static website (page 1 extraction validation, page 2 analysis). `python3 -m http.server 8765 --directory site`

Live site: https://rossed.github.io/canberra-bloom-record/

Note: `data/raw/` (original ANBG HTML) and `data/fff/pdf/` (Friends PDFs) are not committed; the download scripts fetch them.
Credits: leaflets © Australian National Botanic Gardens and Friends of the ANBG volunteers; taxonomy from ALA; temperature BOM ACORN-SAT; rainfall ERA5 via Open-Meteo.

## Checking accuracy
The site's **3 · Check accuracy** page lets a reviewer mark a stratified random sample (one brochure per year) against the originals and review ALA name changes. Put exported result files in `validation/`, then:

    python3 pipeline/08_apply_validation.py   # prints precision / recall / name accuracy with 95% CIs, writes data/name_overrides.json
    python3 pipeline/05_taxonomy.py && python3 pipeline/06_analysis.py && python3 pipeline/07_site_data.py
