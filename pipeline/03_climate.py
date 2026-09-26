"""Climate data for Canberra.
Temperature: BOM ACORN-SAT v2.6.0 homogenised daily Tmax/Tmin, station 070351 (Canberra Airport),
  via the Bureau's anonymous FTP (the BOM website blocks scripted access and directs users to FTP).
Rainfall: ERA5 reanalysis via Open-Meteo archive API at ANBG coordinates (BOM rainfall isn't on anon FTP)."""
import os, tarfile, io, csv, json, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "climate")
FTP = "ftp://ftp.bom.gov.au/anon/home/ncc/www/change/ACORN_SAT_daily/acorn_sat_v2.6.0_daily_{}.tar.gz"
data = {}
for var in ["tmax", "tmin"]:
    local = os.path.join(OUT, f"acorn_070351_{var}.csv")
    if not os.path.exists(local):
        tgz = urllib.request.urlopen(FTP.format(var), timeout=300).read()
        tf = tarfile.open(fileobj=io.BytesIO(tgz))
        m = next(m for m in tf.getmembers() if "070351" in m.name)
        open(local, "wb").write(tf.extractfile(m).read())
    for r in csv.reader(open(local)):
        if r and r[0][:2] in ("19", "20") and len(r) > 1 and r[1].strip():
            try: data.setdefault(r[0], {})[var] = float(r[1])
            except ValueError: pass
rain_local = os.path.join(OUT, "era5_rain_anbg.json")
if not os.path.exists(rain_local):
    url = ("https://archive-api.open-meteo.com/v1/archive?latitude=-35.278&longitude=149.109"
           "&start_date=1990-01-01&end_date=2016-12-31&daily=precipitation_sum,temperature_2m_mean&timezone=Australia%2FSydney")
    open(rain_local, "wb").write(urllib.request.urlopen(url, timeout=120).read())
era = json.load(open(rain_local))["daily"]
for d, p, t in zip(era["time"], era["precipitation_sum"], era["temperature_2m_mean"]):
    if p is not None: data.setdefault(d, {})["rain"] = p
    if t is not None: data.setdefault(d, {})["era5_tmean"] = t
with open(os.path.join(OUT, "canberra_daily.csv"), "w") as f:
    f.write("date,tmax,tmin,rain,era5_tmean\n")
    for d in sorted(data):
        if d < "1990-01-01": continue
        r = data[d]; f.write(",".join([d] + [str(r.get(k, "")) for k in ["tmax", "tmin", "rain", "era5_tmean"]]) + "\n")
print("days", sum(1 for d in data if d >= "1990"), "tmax days", sum(1 for d in data if d >= "1990" and "tmax" in data[d]))
