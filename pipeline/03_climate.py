"""Climate data for Canberra.
Temperature: BOM ACORN-SAT v2.6.0 homogenised daily Tmax/Tmin, station 070351 (Canberra Airport),
  via the Bureau's anonymous FTP (the BOM website blocks scripted access and directs users to FTP).
  ACORN-SAT currently ends 31 Dec 2024. Later days are filled from ERA5 reanalysis at the ANBG site,
  bias-corrected per calendar month against ACORN over 1990-2024 (agreement is reported in splice_check.json).
Rainfall: ERA5 reanalysis via Open-Meteo archive API at ANBG coordinates (BOM rainfall isn't on anon FTP)."""
import os, tarfile, io, csv, json, urllib.request, datetime, collections
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "climate")
FTP = "ftp://ftp.bom.gov.au/anon/home/ncc/www/change/ACORN_SAT_daily/acorn_sat_v2.6.0_daily_{}.tar.gz"
acorn = collections.defaultdict(dict)
for var in ["tmax", "tmin"]:
    local = os.path.join(OUT, f"acorn_070351_{var}.csv")
    if not os.path.exists(local):
        tgz = urllib.request.urlopen(FTP.format(var), timeout=300).read()
        tf = tarfile.open(fileobj=io.BytesIO(tgz))
        m = next(m for m in tf.getmembers() if "070351" in m.name)
        open(local, "wb").write(tf.extractfile(m).read())
    for r in csv.reader(open(local)):
        if r and r[0][:2] in ("19", "20") and len(r) > 1 and r[1].strip():
            try:
                acorn[r[0]][var] = float(r[1])
            except ValueError:
                pass

END = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
era_local = os.path.join(OUT, "era5_anbg.json")
refresh = not os.path.exists(era_local) or json.load(open(era_local))["daily"]["time"][-1] < END
if refresh:
    url = ("https://archive-api.open-meteo.com/v1/archive?latitude=-35.278&longitude=149.109"
           f"&start_date=1990-01-01&end_date={END}&daily=precipitation_sum,temperature_2m_mean,temperature_2m_max,temperature_2m_min"
           "&timezone=Australia%2FSydney")
    open(era_local, "wb").write(urllib.request.urlopen(url, timeout=300).read())
era = json.load(open(era_local))["daily"]
E = {d: dict(rain=p, tmean=t, tmax=x, tmin=n) for d, p, t, x, n in zip(era["time"], era["precipitation_sum"], era["temperature_2m_mean"],
                                                                      era["temperature_2m_max"], era["temperature_2m_min"])}
acorn_end = max(d for d in acorn if "tmax" in acorn[d] and "tmin" in acorn[d])

# monthly bias correction (ACORN - ERA5) from the overlap
off = {}
check = {}
for var in ["tmax", "tmin"]:
    diffs = collections.defaultdict(list)
    for d, a in acorn.items():
        if "1990" <= d <= acorn_end and var in a and E.get(d, {}).get(var) is not None:
            diffs[int(d[5:7])].append(a[var] - E[d][var])
    off[var] = {m: float(np.mean(v)) for m, v in diffs.items()}
    # agreement of monthly-mean anomalies after correction
    mon = collections.defaultdict(lambda: [[], []])
    for d, a in acorn.items():
        if "1990" <= d <= acorn_end and var in a and E.get(d, {}).get(var) is not None:
            mon[d[:7]][0].append(a[var]); mon[d[:7]][1].append(E[d][var] + off[var][int(d[5:7])])
    keys = sorted(mon)
    am = np.array([np.mean(mon[k][0]) for k in keys]); em = np.array([np.mean(mon[k][1]) for k in keys])
    clim_a = {m: am[[int(k[5:7]) == m for k in keys]].mean() for m in range(1, 13)}
    aa = am - np.array([clim_a[int(k[5:7])] for k in keys]); ea = em - np.array([clim_a[int(k[5:7])] for k in keys])
    check[var] = dict(monthly_anomaly_r=float(np.corrcoef(aa, ea)[0, 1]), monthly_rmse_c=float(np.sqrt(np.mean((am - em) ** 2))),
                      monthly_offsets=off[var])
check["acorn_end"] = acorn_end
check["era5_end"] = era["time"][-1]
json.dump(check, open(os.path.join(OUT, "splice_check.json"), "w"), indent=1)

days = sorted(set(acorn) | set(E))
with open(os.path.join(OUT, "canberra_daily.csv"), "w") as f:
    f.write("date,tmax,tmin,rain,era5_tmean,temp_source\n")
    for d in days:
        if d < "1990-01-01":
            continue
        a, e = acorn.get(d, {}), E.get(d, {})
        if "tmax" in a and "tmin" in a:
            tx, tn, src = a["tmax"], a["tmin"], "acorn"
        elif d > acorn_end and e.get("tmax") is not None:
            tx, tn, src = round(e["tmax"] + off["tmax"][int(d[5:7])], 2), round(e["tmin"] + off["tmin"][int(d[5:7])], 2), "era5_adj"
        else:
            tx = tn = src = ""
        f.write(",".join(str(x) for x in [d, tx, tn, e.get("rain", "") if e.get("rain") is not None else "",
                                          e.get("tmean", "") if e.get("tmean") is not None else "", src]) + "\n")
print("ACORN ends", acorn_end, "| ERA5 ends", era["time"][-1])
print({v: {k: round(x, 3) for k, x in check[v].items() if k != "monthly_offsets"} for v in ["tmax", "tmin"]})
