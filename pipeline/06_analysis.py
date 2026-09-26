"""Phenology analysis: which plants are flowering earlier over time, and is temperature/rainfall the reason?
Inputs: data/brochures.json (after 05_taxonomy), data/climate/canberra_daily.csv
Output: site/data/analysis.json
"""
import os, json, csv, datetime, collections, math
import numpy as np
from scipy import stats
import statsmodels.api as sm

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = json.load(open(os.path.join(ROOT, "data", "brochures.json")))
MIN_SEASONS, MIN_SPAN, MAX_GAP, TEMP_WINDOW, LONG_DAYS = 8, 10, 28, 60, 150

# ---------------- climate ----------------
clim = {}
for r in csv.DictReader(open(os.path.join(ROOT, "data", "climate", "canberra_daily.csv"))):
    d = datetime.date.fromisoformat(r["date"])
    tmax, tmin = r["tmax"], r["tmin"]
    clim[d] = dict(tmean=(float(tmax) + float(tmin)) / 2 if tmax and tmin else None,
                   tmax=float(tmax) if tmax else None, tmin=float(tmin) if tmin else None,
                   rain=float(r["rain"]) if r["rain"] else None)


def window_mean(end, days, var="tmean"):
    vals = [clim.get(end - datetime.timedelta(i), {}).get(var) for i in range(1, days + 1)]
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if len(vals) > days * 0.8 else None


def window_sum(end, days, var="rain"):
    vals = [clim.get(end - datetime.timedelta(i), {}).get(var) for i in range(1, days + 1)]
    vals = [v for v in vals if v is not None]
    return sum(vals) if len(vals) > days * 0.8 else None


def ols(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    r = stats.linregress(x, y)
    return dict(slope=r.slope, intercept=r.intercept, p=r.pvalue, r=r.rvalue, se=r.stderr, n=len(x))


def bh(pvals):
    p = np.asarray(pvals, float)
    n = len(p)
    order = np.argsort(p)
    q = np.empty(n)
    prev = 1.0
    for rank, i in reversed(list(enumerate(order, 1))):
        prev = min(prev, p[i] * n / rank)
        q[i] = prev
    return q


REF = datetime.date(2001, 1, 1)  # non-leap reference year for labels


def dos_label(dos, start):
    doy = (dos + start) % 365
    return (REF + datetime.timedelta(int(round(doy)))).strftime("%d %b").lstrip("0")


# ---------------- observations ----------------
all_dates = sorted({datetime.date.fromisoformat(r["date"]) for r in D})


def doy0(d):  # 0..364 (Dec 31 of leap years folded to 364)
    return min((d - datetime.date(d.year, 1, 1)).days, 364)


obs = collections.defaultdict(list)
meta = {}
for r in D:
    d = datetime.date.fromisoformat(r["date"])
    for p in r["plants"]:
        k = p.get("analysis_key")
        if not k or p["phase"] != "flowering":
            continue
        obs[k].append(d)
        m = meta.setdefault(k, dict(family=p.get("family"), kind="cultivar" if p["cultivar"] else "species",
                                    vernacular=None, common=collections.Counter(), names_as_written=collections.Counter()))
        if p.get("vernacular"):
            m["vernacular"] = p["vernacular"]
        if p.get("common_name"):
            m["common"][p["common_name"]] += 1
        m["names_as_written"][p["name"]] += 1


def season_start(doys):
    h = np.zeros(365)
    for x in doys:
        h[x] += 1
    k = np.ones(61)
    sm_ = np.convolve(np.concatenate([h[-30:], h, h[:30]]), k, "valid")  # circular 61-day window
    mn = sm_.min()
    idx = np.where(sm_ == mn)[0]
    # middle of the longest run of minimal days
    runs, cur = [], [idx[0]]
    for a, b in zip(idx, idx[1:]):
        if b == a + 1:
            cur.append(b)
        else:
            runs.append(cur); cur = [b]
    runs.append(cur)
    best = max(runs, key=len)
    return int(best[len(best) // 2])


def season_of(d, start):
    dy = doy0(d)
    sy = d.year if dy >= start else d.year - 1
    return sy, (dy - start) % 365


def seasons_for(dates, start, sample_dates):
    """Per season-year metrics, with a coverage check against the brochure calendar."""
    by = collections.defaultdict(list)
    for d in dates:
        sy, dos = season_of(d, start)
        by[sy].append(dos)
    firsts = [min(v) for v in by.values()]
    lasts = [max(v) for v in by.values()]
    lo, hi = max(0, np.percentile(firsts, 10) - 30), min(364, np.percentile(lasts, 90) + 15)
    samp = collections.defaultdict(list)
    for d in sample_dates:
        sy, dos = season_of(d, start)
        samp[sy].append(dos)
    out = []
    for sy in sorted(by):
        s = sorted(x for x in samp.get(sy, []) if lo <= x <= hi)
        if not s:
            continue
        gaps = [s[0] - lo] + [b - a for a, b in zip(s, s[1:])] + [hi - s[-1]]
        covered = max(gaps) <= MAX_GAP
        v = sorted(by[sy])
        out.append(dict(season=sy, first=v[0], mean=float(np.mean(v)), last=v[-1], n=len(v), covered=covered,
                        max_gap=int(max(gaps))))
    return out, (lo, hi)


def analyse(sample_dates, year_max=None, keep=None):
    sample_set = set(sample_dates)
    res = {}
    for k, dates in obs.items():
        dates = [d for d in dates if d in sample_set and (year_max is None or d.year <= year_max)]
        if len(dates) < MIN_SEASONS:
            continue
        start = season_start([doy0(d) for d in dates])
        ss, win = seasons_for(dates, start, sample_dates)
        ok = [s for s in ss if s["covered"]]
        if len(ok) < MIN_SEASONS or ok[-1]["season"] - ok[0]["season"] < MIN_SPAN:
            continue
        yrs = [s["season"] for s in ok]
        f = ols(yrs, [s["first"] for s in ok])
        mn = ols(yrs, [s["mean"] for s in ok])
        ts = stats.theilslopes([s["first"] for s in ok], yrs)
        res[k] = dict(start=start, seasons=ss, window=win, first=f, mean=mn, theil_first=float(ts.slope))
    return res


main = analyse(all_dates)
weekly = analyse([d for d in all_dates if d.year <= 2013])
# thin 1997-2013 to fortnightly to match the post-2014 sampling rate
thin = [d for i, d in enumerate(all_dates) if d.year >= 2014 or i % 2 == 0]
thinned = analyse(thin)

keys = sorted(main)
SPREAD, LONG = {}, {}
for k in keys:
    dos = [season_of(d, main[k]["start"])[1] for d in obs[k]]
    SPREAD[k] = int(np.percentile(dos, 90) - np.percentile(dos, 10))
    LONG[k] = SPREAD[k] > LONG_DAYS
q_first = bh([main[k]["first"]["p"] for k in keys])
q_mean = bh([main[k]["mean"]["p"] for k in keys])

# ---------------- temperature linkage ----------------
species_out, pooled_rows = [], []
for i, k in enumerate(keys):
    a = main[k]
    ok = [s for s in a["seasons"] if s["covered"]]
    mean_first = float(np.mean([s["first"] for s in ok]))
    mean_mean = float(np.mean([s["mean"] for s in ok]))
    typical_onset_doy = int(round(a["start"] + mean_first)) % 365
    rows = []
    for s in a["seasons"]:
        # climatological onset date in that season-year
        onset = datetime.date(s["season"], 1, 1) + datetime.timedelta(a["start"] + int(round(mean_first)))
        t = window_mean(onset, TEMP_WINDOW)
        rn = window_sum(onset, 90)
        s["temp_window"] = round(t, 2) if t is not None else None
        s["rain_90d"] = round(rn, 1) if rn is not None else None
        s["first_label"] = dos_label(s["first"], a["start"])
        s["last_label"] = dos_label(s["last"], a["start"])
        if s["covered"] and t is not None:
            rows.append(s)
    sens = None
    if len(rows) >= MIN_SEASONS:
        tm = np.mean([r["temp_window"] for r in rows])
        rm = np.mean([r["rain_90d"] for r in rows if r["rain_90d"] is not None])
        sens = ols([r["temp_window"] - tm for r in rows], [r["first"] - mean_first for r in rows])
        for r in rows:
            pooled_rows.append(dict(key=k, year=r["season"], anom_first=r["first"] - mean_first,
                                    anom_mean=r["mean"] - mean_mean, temp_anom=r["temp_window"] - tm,
                                    rain_anom=(r["rain_90d"] - rm) if r["rain_90d"] is not None else None))
    # all individual mentions as (season, dos) for the raster plot
    pts = sorted({(season_of(d, a["start"])) for d in obs[k]})
    m = meta[k]
    common = m["vernacular"] or (m["common"].most_common(1)[0][0] if m["common"] else None)
    rob = {lab: (res[k]["first"]["slope"] * 10 if k in res else None) for lab, res in
           [("weekly_only", weekly), ("thinned_fortnightly", thinned)]}
    species_out.append(dict(
        key=k, kind=m["kind"], family=m["family"], common=common,
        names_as_written=[n for n, _ in m["names_as_written"].most_common(6)],
        n_mentions=len(obs[k]), n_seasons=len(ok), first_season=ok[0]["season"], last_season=ok[-1]["season"],
        season_start=a["start"], season_start_label=dos_label(0, a["start"]),
        typical_onset=dos_label(mean_first, a["start"]), typical_onset_doy=typical_onset_doy,
        typical_centroid=dos_label(mean_mean, a["start"]),
        slope_first=a["first"]["slope"] * 10, p_first=a["first"]["p"], q_first=float(q_first[i]), r_first=a["first"]["r"],
        slope_mean=a["mean"]["slope"] * 10, p_mean=a["mean"]["p"], q_mean=float(q_mean[i]),
        theil_first=a["theil_first"] * 10,
        flower_span=int(np.median([s["last"] - s["first"] + 1 for s in ok])),
        spread=SPREAD[k], long_flowering=LONG[k],
        temp_sens=(sens["slope"] if sens else None), temp_sens_p=(sens["p"] if sens else None),
        robustness=rob, seasons=a["seasons"], points=[[s, d] for s, d in pts], window=a["window"]))

# ---------------- pooled (community) models ----------------
def pooled(rows, y, xs):
    rows = [r for r in rows if all(r[x] is not None for x in xs)]
    X = sm.add_constant(np.array([[r[x] for x in xs] for r in rows], float))
    Y = np.array([r[y] for r in rows], float)
    # two-way clustering: species (repeated seasons) and year (shared weather, volunteer, route)
    groups = np.column_stack([[keys.index(r["key"]) for r in rows], [r["year"] for r in rows]])
    fit = sm.OLS(Y, X).fit(cov_type="cluster", cov_kwds={"groups": groups})
    return {name: dict(coef=float(fit.params[j + 1]), se=float(fit.bse[j + 1]), p=float(fit.pvalues[j + 1]),
                       lo=float(fit.conf_int()[j + 1][0]), hi=float(fit.conf_int()[j + 1][1])) for j, name in enumerate(xs)} | {"n": len(rows), "r2": float(fit.rsquared)}


community = dict(
    trend_first=pooled(pooled_rows, "anom_first", ["year"]),
    trend_mean=pooled(pooled_rows, "anom_mean", ["year"]),
    temp_first=pooled(pooled_rows, "anom_first", ["temp_anom"]),
    temp_rain_first=pooled(pooled_rows, "anom_first", ["temp_anom", "rain_anom"]),
    temp_rain_year_first=pooled(pooled_rows, "anom_first", ["temp_anom", "rain_anom", "year"]),
)
# temperature trend in the species-specific pre-onset windows
community["window_temp_trend"] = pooled(pooled_rows, "temp_anom", ["year"])
tt = community["window_temp_trend"]["year"]["coef"]
sens_ = community["temp_first"]["temp_anom"]["coef"]
obs_tr = community["trend_first"]["year"]["coef"]
community["attribution"] = dict(observed_days_per_decade=obs_tr * 10, temp_trend_c_per_decade=tt * 10,
                                 sensitivity_days_per_c=sens_, expected_from_temp_days_per_decade=sens_ * tt * 10,
                                 share_explained=(sens_ * tt / obs_tr) if obs_tr else None)

# yearly mean anomaly series (community index)
by_year = collections.defaultdict(list)
for r in pooled_rows:
    by_year[r["year"]].append(r)
community["yearly"] = [dict(year=y, n=len(v), anom_first=float(np.mean([r["anom_first"] for r in v])),
                            anom_first_se=float(np.std([r["anom_first"] for r in v], ddof=1) / math.sqrt(len(v))) if len(v) > 1 else None,
                            anom_mean=float(np.mean([r["anom_mean"] for r in v])),
                            temp_anom=float(np.mean([r["temp_anom"] for r in v])))
                       for y, v in sorted(by_year.items())]

# robustness of the pooled trend
def pooled_trend(res, short_only=False):
    rows = []
    if short_only:
        res = {k: a for k, a in res.items() if not LONG[k]}
    for k, a in res.items():
        ok = [s for s in a["seasons"] if s["covered"]]
        mf = np.mean([s["first"] for s in ok])
        rows += [dict(key=k, year=s["season"], a=s["first"] - mf) for s in ok]
    ks = sorted(res)
    X = sm.add_constant(np.array([r["year"] for r in rows], float))
    g2 = np.column_stack([[ks.index(r["key"]) for r in rows], [r["year"] for r in rows]])
    fit = sm.OLS(np.array([r["a"] for r in rows]), X).fit(cov_type="cluster", cov_kwds={"groups": g2})
    return dict(days_per_decade=float(fit.params[1] * 10), lo=float(fit.conf_int()[1][0] * 10), hi=float(fit.conf_int()[1][1] * 10),
                p=float(fit.pvalues[1]), n_species=len(res), n_obs=len(rows))


stable = analyse([d for d in all_dates if 2003 <= d.year <= 2013])
community["robustness"] = dict(all_years=pooled_trend(main), weekly_1997_2013=pooled_trend(weekly),
                               thinned_fortnightly=pooled_trend(thinned), stable_effort_2003_2013=pooled_trend(stable),
                               short_season_only=pooled_trend(main, True))

# temperature window sensitivity: mean temp over N days before each species' climatological onset
win_sens = []
for W in (30, 60, 90, 120, 180):
    rows = []
    for k in keys:
        a = main[k]
        ok = [s for s in a["seasons"] if s["covered"]]
        mf = np.mean([s["first"] for s in ok])
        tmp = []
        for s in ok:
            onset = datetime.date(s["season"], 1, 1) + datetime.timedelta(a["start"] + int(round(mf)))
            t = window_mean(onset, W)
            if t is not None:
                tmp.append((s, t))
        if len(tmp) < MIN_SEASONS:
            continue
        tm = np.mean([t for _, t in tmp])
        rows += [dict(key=k, year=s["season"], anom_first=s["first"] - mf, temp_anom=t - tm, rain_anom=0) for s, t in tmp]
    r1 = pooled(rows, "anom_first", ["temp_anom"])
    r2 = pooled(rows, "temp_anom", ["year"])
    win_sens.append(dict(window=W, sens=r1["temp_anom"]["coef"], lo=r1["temp_anom"]["lo"], hi=r1["temp_anom"]["hi"],
                         p=r1["temp_anom"]["p"], warming_per_decade=r2["year"]["coef"] * 10))
community["window_sensitivity"] = win_sens

# ---------------- climate summaries ----------------
years = range(1990, 2017)
climate = []
for y in years:
    def mean_months(ms, var, yy=y):
        v = [c[var] for d, c in clim.items() if d.year == yy and d.month in ms and c.get(var) is not None]
        return round(float(np.mean(v)), 2) if v else None

    def sum_months(ms, yy=y):
        v = [c["rain"] for d, c in clim.items() if d.year == yy and d.month in ms and c.get("rain") is not None]
        return round(float(np.sum(v)), 1) if v else None
    climate.append(dict(year=y, annual=mean_months(range(1, 13), "tmean"), winter=mean_months([6, 7, 8], "tmean"),
                        spring=mean_months([9, 10, 11], "tmean"), summer=mean_months([12, 1, 2], "tmean"),
                        autumn=mean_months([3, 4, 5], "tmean"), tmax_annual=mean_months(range(1, 13), "tmax"),
                        tmin_annual=mean_months(range(1, 13), "tmin"), rain_annual=sum_months(range(1, 13)),
                        rain_winter_spring=sum_months(range(6, 12))))
c9716 = [c for c in climate if 1997 <= c["year"] <= 2016]
# year-level correlation: community onset index vs seasonal climate of the same year
yi = {y["year"]: y for y in community["yearly"]}
cy = {c["year"]: c for c in climate}
community["year_corr"] = {}
for v in ["annual", "winter", "spring", "rain_annual", "rain_winter_spring"]:
    ys = [y for y in yi if y in cy and cy[y][v] is not None and yi[y]["n"] >= 50]
    r = stats.pearsonr([cy[y][v] for y in ys], [yi[y]["anom_first"] for y in ys])
    community["year_corr"][v] = dict(r=float(r[0]), p=float(r[1]), n=len(ys))
# detrended: does a warmer-than-trend year flower earlier than trend?
ys = [y for y in yi if y in cy and yi[y]["n"] >= 50]
def detr(v):
    v = np.asarray(v, float); b = np.polyfit(ys, v, 1); return v - np.polyval(b, ys)
for v in ["winter", "spring", "rain_winter_spring"]:
    r = stats.pearsonr(detr([cy[y][v] for y in ys]), detr([yi[y]["anom_first"] for y in ys]))
    community["year_corr"][v + "_detrended"] = dict(r=float(r[0]), p=float(r[1]), n=len(ys))
climate_trends = {v: ols([c["year"] for c in c9716], [c[v] for c in c9716]) for v in ["annual", "winter", "spring", "summer", "autumn", "tmax_annual", "tmin_annual", "rain_annual"]}
climate_trends = {k: dict(per_decade=v["slope"] * 10, p=v["p"]) for k, v in climate_trends.items()}

# family summary
fam = collections.defaultdict(list)
for s in species_out:
    if s["kind"] == "species" and s["family"]:
        fam[s["family"]].append(s["slope_first"])
families = sorted([dict(family=f, n=len(v), mean_slope=float(np.mean(v)), n_earlier=sum(x < 0 for x in v))
                   for f, v in fam.items() if len(v) >= 3], key=lambda x: x["mean_slope"])

# sampling effort per year
effort = collections.Counter(datetime.date.fromisoformat(r["date"]).year for r in D)
plants_per = collections.defaultdict(list)
for r in D:
    plants_per[r["year"]].append(r["n_plants"])
effort_out = [dict(year=y, brochures=effort[y], mean_plants=float(np.mean(plants_per[y]))) for y in sorted(effort)]

out = dict(generated=datetime.datetime.now().isoformat(timespec="seconds"),
           params=dict(long_days=LONG_DAYS, min_seasons=MIN_SEASONS, min_span=MIN_SPAN, max_gap=MAX_GAP, temp_window=TEMP_WINDOW),
           n_brochures=len(D), n_keys_total=len(obs), species=species_out, community=community,
           climate=climate, climate_trends=climate_trends, families=families, effort=effort_out)
os.makedirs(os.path.join(ROOT, "site", "data"), exist_ok=True)
json.dump(out, open(os.path.join(ROOT, "site", "data", "analysis.json"), "w"), separators=(",", ":"),
          default=lambda o: float(o) if isinstance(o, (np.floating,)) else int(o) if isinstance(o, np.integer) else bool(o) if isinstance(o, np.bool_) else str(o))

# console summary
sp = [s for s in species_out]
print(len(sp), "taxa analysed (", sum(s['kind'] == 'species' for s in sp), "species,", sum(s['kind'] == 'cultivar' for s in sp), "cultivars )")
print("earlier (slope<0):", sum(s["slope_first"] < 0 for s in sp), " p<0.05 earlier:", sum(s["slope_first"] < 0 and s["p_first"] < .05 for s in sp),
      " p<0.05 later:", sum(s["slope_first"] > 0 and s["p_first"] < .05 for s in sp), " q<0.1:", sum(s["q_first"] < .1 for s in sp))
for k, v in community.items():
    if k not in ("yearly",):  # noqa
        print(k, json.dumps(v, default=float)[:400])
print("climate trends", json.dumps(climate_trends, default=float))
print("families", families[:5], families[-3:])
