#!/bin/sh
# Rebuild everything from scratch (downloads are cached in data/).
set -e
cd "$(dirname "$0")"
python3 pipeline/01_download.py
python3 pipeline/02_recover_wayback.py
python3 pipeline/03_climate.py
python3 pipeline/04_extract.py
python3 pipeline/05_taxonomy.py
python3 pipeline/06_analysis.py
python3 pipeline/07_site_data.py
[ -n "$(ls validation/*.json 2>/dev/null)" ] && python3 pipeline/08_apply_validation.py || true
echo "Done. Serve with: python3 -m http.server 8765 --directory site"
