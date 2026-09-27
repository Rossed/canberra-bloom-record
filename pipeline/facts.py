"""Single source of truth for every headline figure and phrase.

The website (via site/data/facts.json), the PDF report (11_report.py) and the consistency check
(12_check_consistency.py) all take their key numbers and wording from build_facts(), so a change
made here, or in the analysis behind it, reaches every page and the report together.
"""
import os, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sgn(x, d=1):
    return ("+" if x > 0 else "−" if x < 0 else "") + f"{abs(x):.{d}f}"


def rng(lo, hi, d=1):
    return f"{sgn(lo, d)} to {sgn(hi, d)}"


def fraction_words(x):
    return "a tenth" if x < 0.15 else "a fifth" if x < 0.23 else "a quarter" if x < 0.29 else "a third" if x < 0.42 else "half" if x < 0.6 else "most"


def year_list(ys):
    ys = [str(y) for y in sorted(ys)]
    return ", ".join(ys[:-1]) + " and " + ys[-1] if len(ys) > 1 else (ys[0] if ys else "")


def name_list(xs):
    return ", ".join(xs[:-1]) + " and " + xs[-1] if len(xs) > 1 else (xs[0] if xs else "none")


def build_facts(A=None, D=None):
    A = A or json.load(open(os.path.join(ROOT, "site", "data", "analysis.json")))
    D = D or json.load(open(os.path.join(ROOT, "data", "brochures.json")))
    C, R, S = A["community"], A["community"]["robustness"], A["species"]
    LY = A["last_full_year"]
    allp = [p for r in D for p in r["plants"]]
    SH = [s for s in S if not s["long_flowering"]]
    W = C["window_sensitivity"]
    w60 = next(w for w in W if w["window"] == 60); w180 = next(w for w in W if w["window"] == 180)
    obs = R["all_years"]["mean_days_per_decade"]
    expLo, expHi = w60["sens_mean"] * w60["warming_per_decade"], w180["sens_mean"] * w180["warming_per_decade"]
    shLo, shHi = expLo / obs, expHi / obs
    yrs = sorted([y for y in C["yearly"] if y["n"] >= A["params"]["min_year_n"] and y["year"] <= LY], key=lambda y: y["anom_mean"])
    FT = A["family_test"]
    clearF = [f["family"] for f in A["families"] if f["hi"] < 0 and f["q"] < 0.1]
    fab = next((f for f in A["families"] if f["family"] == "Fabaceae"), None)
    acacia = next((g for g in A["genera"] if g["genus"] == "Acacia"), None)
    ct = A["climate_trends"]
    earlyM = sum(1 for s in SH if s["slope_mean"] < 0)
    last_date = max(r["date"] for r in D)
    report_pdf = os.path.join(ROOT, "site", "report", "canberra-bloom-record.pdf")
    try:
        import pymupdf
        report_pages = pymupdf.open(report_pdf).page_count
    except Exception:
        report_pages = None
    total = round(abs(obs) * (LY + 1 - 1997) / 10)
    f = {
        # coverage
        "first_year": "1997", "last_year": str(LY + 1), "span": f"1997–{LY + 1}",
        "n_leaflets": f"{len(D):,}", "n_iftw": f"{sum(1 for r in D if r.get('series') == 'IFTW'):,}",
        "n_fff": f"{sum(1 for r in D if r.get('series') == 'FFF'):,}", "n_wayback": f"{sum(1 for r in D if r['source'] == 'wayback'):,}",
        "n_records": f"{len(allp):,}", "n_taxa": f"{len(S):,}", "n_flagged": f"{sum(1 for r in D if r['flags']):,}",
        "pct_species": f"{100 * sum(1 for p in allp if p.get('accepted_species')) / len(allp):.0f}%",
        "n_renamed": f"{sum(1 for p in allp if p.get('renamed')):,}",
        # headline
        "shift": sgn(obs), "shift_abs_round": f"{abs(obs):.0f}", "shift_ci": rng(R["all_years"]["mean_lo"], R["all_years"]["mean_hi"]),
        "shift_total_words": "two weeks" if 12 <= total <= 17 else f"{total} days", "shift_total_days": str(total),
        "thinned_first": sgn(R["thinned_fortnightly"]["days_per_decade"]),
        "thinned_first_ci": rng(R["thinned_fortnightly"]["lo"], R["thinned_fortnightly"]["hi"]),
        "raw_first": sgn(R["all_years"]["days_per_decade"]),
        "n_short": str(len(SH)), "n_short_earlier": str(earlyM), "pct_short_earlier": f"{round(100 * earlyM / len(SH))}%",
        "q_earlier": str(sum(1 for s in S if s["q_mean"] < .1 and s["slope_mean"] < 0)),
        "q_later": str(sum(1 for s in S if s["q_mean"] < .1 and s["slope_mean"] > 0)),
        # climate
        "warming": f"{ct['annual']['per_decade']:+.2f} °C".replace("+", "+"), "warming_1dp": f"{ct['annual']['per_decade']:.1f} °C",
        "warming_words": f"about {fraction_words(ct['annual']['per_decade'])} of a degree",
        "warming_spring": f"{ct['spring']['per_decade']:+.2f} °C",
        "sens_range": f"{abs(w60['sens_mean']):.1f}–{abs(w180['sens_mean']):.1f}",
        "expected_range": rng(expLo, expHi),
        "share": f"{round(100 * shLo)}–{round(100 * shHi)}%",
        "share_words": fraction_words(shLo) if fraction_words(shLo) == fraction_words(shHi) else f"{fraction_words(shLo)} to {fraction_words(shHi)}",
        "year_r": sgn(C['year_corr_mean']['annual']['r'], 2), "year_r_detrended": sgn(C['year_corr_mean']['annual_detrended']['r'], 2),
        "rain_r": sgn(C['year_corr_mean']['rain_annual_detrended']['r'], 2),
        "earliest_years": year_list([y["year"] for y in yrs[:3]]), "latest_years": year_list([y["year"] for y in yrs[-3:]]),
        "handover_step": sgn(C["series_step_mean"]["friends_series"]["coef"]),
        # families
        "family_share": f"{round(100 * FT['share_between'])}%", "family_perm_p": f"{FT['permutation_p']:.3f}",
        "family_n_clear": str(len(clearF)), "family_clear": name_list(clearF), "family_n": str(FT["n_families"]),
        "family_within_sd": f"±{FT['within_sd']:.0f}", "family_noise_sd": f"±{FT['noise_se']:.0f}", "family_true_sd": f"±{FT['true_sd']:.0f}",
        "fabaceae_shift": sgn(fab["mean_slope"]) if fab else "", "acacia_shift": sgn(acacia["mean_slope"]) if acacia else "",
        "genus_p": f"{FT['genus_kruskal_p']:.3f}",
        # report
        "report_pages": str(report_pages) if report_pages else "",
        "last_leaflet": last_date,
    }
    # plain-language sentences shared word-for-word by the front page, the Findings summary and the report summary
    f["sentence_shift"] = f"The plants in the Gardens now flower about {f['shift_abs_round']} days earlier per decade than in 1997, roughly {f['shift_total_words']} over the whole period."
    f["sentence_warming"] = f"Canberra has warmed by {f['warming_words']} each decade since 1997, and in warmer years plants flowered {f['sens_range']} days earlier for each degree of extra warmth."
    f["sentence_share"] = f"On these figures, warming accounts for roughly {f['share_words']} of the change ({f['share']}). Rainfall made no clear difference."
    f["sentence_families"] = (f"Plant families are not shifting in their own distinctive ways: family explains only {f['family_share']} of the differences between species. "
                              f"Most families are moving earlier along with the garden as a whole, and the wattles are the main exception.")
    return f


def write_facts(path=None):
    f = build_facts()
    json.dump(f, open(path or os.path.join(ROOT, "site", "data", "facts.json"), "w"), indent=1, ensure_ascii=False)
    return f


if __name__ == "__main__":
    for k, v in write_facts().items():
        print(f"{k:20} {v}")
