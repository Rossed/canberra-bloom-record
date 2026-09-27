"""Build the shareable PDF report -> site/report/canberra-bloom-record.pdf

Everything is drawn from the same data the website uses (site/data/analysis.json, data/brochures.json),
so the report always matches the site. Charts are re-drawn with matplotlib for print; text is set with
reportlab in the site's typefaces (Spectral, IBM Plex Sans, IBM Plex Mono; SIL Open Font Licence).
"""
import os, json, glob, datetime, collections, io, re
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Image, Table, TableStyle,
                                PageBreak, KeepTogether, NextPageTemplate, CondPageBreak, Flowable)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, "data", "fonts")
OUT_DIR = os.path.join(ROOT, "site", "report")
OUT = os.path.join(OUT_DIR, "canberra-bloom-record.pdf")
SITE = "https://rossed.github.io/canberra-bloom-record/"
REPO = "https://github.com/Rossed/canberra-bloom-record"
os.makedirs(OUT_DIR, exist_ok=True)

A = json.load(open(os.path.join(ROOT, "site", "data", "analysis.json")))
D = json.load(open(os.path.join(ROOT, "data", "brochures.json")))
C, R, S = A["community"], A["community"]["robustness"], A["species"]
LY = A["last_full_year"]

# ---------------------------------------------------------------- palette & type (matches the site's light theme)
INK, INK2, INK3 = "#1b2420", "#4b5751", "#7a857f"
BG2, LINE = "#eef1ec", "#dde2dc"
ACCENT, ACCENT_SOFT = "#3d6b58", "#e2ece6"
EARLY, LATE, NEUTRAL = "#2a78d6", "#eb6834", "#8a918c"
SERIES2 = "#9dbfae"

for name, f in [("Spectral", "Spectral-Regular"), ("Spectral-It", "Spectral-Italic"), ("Spectral-SB", "Spectral-SemiBold"),
                ("Spectral-SBIt", "Spectral-SemiBoldItalic"), ("Plex", "IBMPlexSans-Regular"), ("Plex-Md", "IBMPlexSans-Medium"),
                ("Plex-SB", "IBMPlexSans-SemiBold"), ("Plex-It", "IBMPlexSans-Italic"), ("Plex-B", "IBMPlexSans-Bold"),
                ("Mono", "IBMPlexMono-Regular"), ("Mono-Md", "IBMPlexMono-Medium")]:
    pdfmetrics.registerFont(TTFont(name, os.path.join(FONTS, f + ".ttf")))
addMapping("Plex", 0, 0, "Plex"); addMapping("Plex", 1, 0, "Plex-SB"); addMapping("Plex", 0, 1, "Plex-It"); addMapping("Plex", 1, 1, "Plex-B")
addMapping("Spectral", 0, 0, "Spectral"); addMapping("Spectral", 0, 1, "Spectral-It"); addMapping("Spectral", 1, 0, "Spectral-SB"); addMapping("Spectral", 1, 1, "Spectral-SBIt")
for f in glob.glob(os.path.join(FONTS, "*.ttf")):
    font_manager.fontManager.addfont(f)
plt.rcParams.update({
    "font.family": "IBM Plex Sans", "font.size": 8.5, "axes.edgecolor": LINE, "axes.labelcolor": INK2, "xtick.color": INK2,
    "ytick.color": INK2, "axes.grid": True, "grid.color": "#e6eae5", "grid.linewidth": 0.6, "axes.spines.top": False,
    "axes.spines.right": False, "axes.spines.left": False, "axes.axisbelow": True, "xtick.major.size": 0, "ytick.major.size": 0,
    "axes.titlesize": 9, "legend.frameon": False, "legend.fontsize": 8, "figure.dpi": 100, "savefig.dpi": 250,
})

st = {
    "body": ParagraphStyle("body", fontName="Plex", fontSize=10, leading=15.2, textColor=INK, spaceAfter=7),
    "lead": ParagraphStyle("lead", fontName="Spectral", fontSize=13.5, leading=19.5, textColor=INK, spaceAfter=10),
    "h1": ParagraphStyle("h1", fontName="Spectral-SB", fontSize=24, leading=28, textColor=INK, spaceBefore=0, spaceAfter=10),
    "h2": ParagraphStyle("h2", fontName="Spectral-SB", fontSize=15, leading=19, textColor=INK, spaceBefore=12, spaceAfter=6),
    "h3": ParagraphStyle("h3", fontName="Plex-SB", fontSize=10.5, leading=14, textColor=INK, spaceBefore=8, spaceAfter=3),
    "eyebrow": ParagraphStyle("eyebrow", fontName="Plex-Md", fontSize=7.5, leading=10, textColor=INK3, spaceAfter=3),
    "cap": ParagraphStyle("cap", fontName="Plex", fontSize=8.3, leading=11.8, textColor=INK2, spaceAfter=10),
    "small": ParagraphStyle("small", fontName="Plex", fontSize=8.3, leading=11.5, textColor=INK2),
    "cell": ParagraphStyle("cell", fontName="Plex", fontSize=8.3, leading=10.8, textColor=INK),
    "cellnum": ParagraphStyle("cellnum", fontName="Mono", fontSize=8.1, leading=10.8, textColor=INK, alignment=2),
    "cellhead": ParagraphStyle("cellhead", fontName="Plex-Md", fontSize=7.2, leading=9.2, textColor=INK3),
    "cellheadnum": ParagraphStyle("cellheadnum", fontName="Plex-Md", fontSize=7.2, leading=9.2, textColor=INK3, alignment=2),
    "big": ParagraphStyle("big", fontName="Spectral-SB", fontSize=17, leading=22.5, textColor=INK, spaceAfter=10),
    "bullet": ParagraphStyle("bullet", fontName="Plex", fontSize=10, leading=15, textColor=INK, leftIndent=13, bulletIndent=0, spaceAfter=5),
    "statv": ParagraphStyle("statv", fontName="Mono-Md", fontSize=15, leading=18, textColor=INK),
    "statl": ParagraphStyle("statl", fontName="Plex", fontSize=7.8, leading=10.2, textColor=INK2),
}


def fmt(x, d=1):
    if x is None:
        return "–"
    return ("+" if x > 0 else "−" if x < 0 else "") + f"{abs(x):.{d}f}"


def pf(p):
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def sci(name):
    """Italicise genus/epithets; keep ranks and cultivar names roman (botanical convention)."""
    out = []
    for tok in re.findall(r"'[^']*'?|\S+", name or ""):
        if tok.startswith("'") or tok in ("subsp.", "var.", "f.", "sp.", "×"):
            out.append(esc(tok.replace("'", "‘", 1)[:-1] + "’" if tok.endswith("'") and len(tok) > 1 else tok))
        else:
            out.append(f'<font name="Spectral-It" size="+0.6">{esc(tok)}</font>')
    return " ".join(out)


def P(text, style="body"):
    return Paragraph(text, st[style])


def bullets(items):
    return [Paragraph(t, st["bullet"], bulletText="•") for t in items]


# ---------------------------------------------------------------- charts
FIG = []
_YR = sorted([y for y in C["yearly"] if y["n"] >= A["params"]["min_year_n"] and y["year"] <= LY], key=lambda y: y["anom_mean"])
EARLY_YEARS = sorted(y["year"] for y in _YR[:3]); LATE_YEARS = sorted(y["year"] for y in _YR[-3:])


def yearlist(ys):
    ys = [str(y) for y in ys]
    return ", ".join(ys[:-1]) + " and " + ys[-1] if len(ys) > 1 else ys[0]


def fig_to_image(fig, width_mm):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    img = Image(buf)
    ratio = img.imageHeight / img.imageWidth
    img.drawWidth = width_mm * mm
    img.drawHeight = width_mm * mm * ratio
    return img


def style_ax(ax, xlabel=None, ylabel=None):
    if xlabel: ax.set_xlabel(xlabel, fontsize=8, color=INK3)
    if ylabel: ax.set_ylabel(ylabel, fontsize=8, color=INK3)
    ax.tick_params(labelsize=7.8)


def chart_leaflets():
    by = collections.defaultdict(lambda: [0, 0])
    for r in D:
        by[r["year"]][0 if r.get("series") == "IFTW" else 1] += 1
    ys = sorted(by)
    fig, ax = plt.subplots(figsize=(7.2, 2.3))
    a = [by[y][0] for y in ys]; b = [by[y][1] for y in ys]
    ax.bar(ys, a, color=ACCENT, width=0.72, label="In Flower This Week (ANBG)")
    ax.bar(ys, b, bottom=a, color=SERIES2, width=0.72, label="Flowers, Fruit & Foliage (Friends)")
    ax.legend(loc="upper right", ncol=2, bbox_to_anchor=(1, 1.18))
    ax.set_xlim(1996.3, max(ys) + 0.7); ax.grid(axis="x", visible=False)
    style_ax(ax, None, "leaflets per year")
    return fig_to_image(fig, 170)


def chart_yearly():
    Y = [y for y in C["yearly"] if y["n"] >= A["params"]["min_year_n"]]
    xs = np.array([y["year"] for y in Y]); ys = np.array([y["anom_mean"] for y in Y])
    b = np.polyfit(xs, ys, 1)
    fig, ax = plt.subplots(figsize=(7.2, 2.9))
    ax.bar(xs, ys, color=[EARLY if v < 0 else LATE for v in ys], width=0.72)
    ax.plot([xs.min(), xs.max()], np.polyval(b, [xs.min(), xs.max()]), color=INK, lw=1.6, ls=(0, (5, 3)))
    ax.axvline(2016.6, color=NEUTRAL, lw=0.9, ls=":")
    ax.text(2016.8, ys.max() + 1, "Friends' leaflets\nfrom Aug 2016", fontsize=7, color=INK3, va="top")
    ax.axhline(0, color=INK3, lw=0.6)
    for yr in EARLY_YEARS + LATE_YEARS:
        if yr in xs:
            v = ys[list(xs).index(yr)]
            ax.annotate(str(yr), (yr, v), xytext=(0, -9 if v < 0 else 3), textcoords="offset points", ha="center", fontsize=6.8, color=INK3)
    ax.grid(axis="x", visible=False)
    style_ax(ax, None, "days vs each plant's average")
    return fig_to_image(fig, 170)


def chart_robust():
    rows = [("All leaflets, 1997–now", R["all_years"]), ("Weekly years thinned to fortnightly", R["thinned_fortnightly"]),
            ("Weekly era only, 1997–2013", R["weekly_1997_2013"]), ("Stable leaflet length, 2003–2013", R["stable_effort_2003_2013"]),
            ("Plants with a defined season only", R["short_season_only"]), ("ANBG leaflets only, 1997–2016", R["iftw_1997_2016"]),
            ("Friends leaflets only, 2016–now", R["friends_2016_now"])]
    fig, ax = plt.subplots(figsize=(7.2, 3.1))
    for i, (lab, r) in enumerate(rows):
        y = len(rows) - 1 - i
        ax.plot([r["mean_lo"], r["mean_hi"]], [y + 0.14] * 2, color=ACCENT, lw=3.2, alpha=0.35, solid_capstyle="round")
        ax.plot(r["mean_days_per_decade"], y + 0.14, "o", color=ACCENT, ms=6, mec="white", mew=1.2)
        ax.plot([r["lo"], r["hi"]], [y - 0.14] * 2, color=INK3, lw=3.2, alpha=0.3, solid_capstyle="round")
        ax.plot(r["days_per_decade"], y - 0.14, "o", color=INK3, ms=6, mec="white", mew=1.2)
    ax.set_yticks(range(len(rows))); ax.set_yticklabels([r[0] for r in rows][::-1], fontsize=8)
    ax.axvline(0, color=INK3, lw=0.8)
    ax.set_xlim(-30, 15); ax.grid(axis="y", visible=False)
    ax.plot([], [], "o", color=ACCENT, label="Mid-flowering date"); ax.plot([], [], "o", color=INK3, label="First appearance")
    ax.legend(loc="lower right", fontsize=7.5)
    style_ax(ax, "shift in days per decade (negative = earlier); dot = estimate, bar = 95% confidence interval")
    return fig_to_image(fig, 170)


def chart_hist():
    SH = [s for s in S if not s["long_flowering"]]
    v = np.clip([s["slope_mean"] for s in SH], -40, 39.9)
    bins = np.arange(-40, 44, 4)
    fig, ax = plt.subplots(figsize=(3.6, 2.6))
    n, edges, patches = ax.hist(v, bins=bins, rwidth=0.9)
    for p, e in zip(patches, edges[:-1]):
        p.set_facecolor(EARLY if e < 0 else LATE)
    ax.axvline(0, color=INK3, lw=0.8); ax.grid(axis="x", visible=False)
    style_ax(ax, "mid-flowering shift, days per decade", "number of plants")
    return fig_to_image(fig, 82)


def chart_families():
    F = A["families"]
    fig, ax = plt.subplots(figsize=(3.6, 0.2 * len(F) + 0.8))
    ys = range(len(F))
    ax.barh(list(ys), [f["mean_slope"] for f in F], color=[EARLY if f["mean_slope"] < 0 else LATE for f in F], height=0.6)
    ax.set_yticks(list(ys)); ax.set_yticklabels([f"{f['family']} ({f['n']})" for f in F], fontsize=7.4, fontfamily="Spectral")
    ax.invert_yaxis(); ax.axvline(0, color=INK3, lw=0.8); ax.grid(axis="y", visible=False)
    style_ax(ax, "average shift, days per decade")
    return fig_to_image(fig, 82)


def chart_species(s):
    st_ = s["season_start"]
    cov = [x for x in s["seasons"] if x["covered"]]
    fig, ax = plt.subplots(figsize=(7.2, 2.7))
    pts = np.array([[p[0], p[1]] for p in s["points"]], dtype=float)
    ax.scatter(pts[:, 0], pts[:, 1], s=9, color=NEUTRAL, zorder=2, label="each leaflet mention")
    ax.scatter([x["season"] for x in cov], [x["mean"] for x in cov], s=34, color=ACCENT, edgecolor="white", lw=1, zorder=3, label="mid-flowering date that year")
    b = np.polyfit([x["season"] for x in cov], [x["mean"] for x in cov], 1)
    x0, x1 = cov[0]["season"], cov[-1]["season"]
    ax.plot([x0, x1], np.polyval(b, [x0, x1]), color=INK, lw=1.5, zorder=4, label="trend")
    ax.invert_yaxis()
    ref = datetime.date(2001, 1, 1)
    ticks = ax.get_yticks()
    ax.set_yticks(ticks)
    ax.set_yticklabels([(ref + datetime.timedelta(days=int((t + st_) % 365))).strftime("%-d %b") for t in ticks])
    ax.set_ylim(max(pts[:, 1].max() + 8, 0), max(pts[:, 1].min() - 8, 0))
    ax.legend(loc="upper center", ncol=3, bbox_to_anchor=(0.5, 1.16), fontsize=7.5)
    style_ax(ax, None, "date (earlier ↑)")
    return fig_to_image(fig, 170)


def chart_temp():
    cl = [c for c in A["climate"] if 1996 <= c["year"] <= LY]
    fig, ax = plt.subplots(figsize=(3.6, 2.6))
    for k, lab, col in [("spring", "Spring (Sep–Nov)", ACCENT), ("annual", "Annual mean", INK3), ("winter", "Winter (Jun–Aug)", EARLY)]:
        xs = np.array([c["year"] for c in cl]); ys = np.array([c[k] for c in cl])
        ax.plot(xs, ys, color=col, lw=1.4, label=lab)
        b = np.polyfit(xs, ys, 1); ax.plot([xs[0], xs[-1]], np.polyval(b, [xs[0], xs[-1]]), color=col, lw=0.8, ls="--")
    ax.legend(loc="upper left", fontsize=7, ncol=1, bbox_to_anchor=(0, 1.02))
    ax.set_ylim(4.5, 17.5)
    style_ax(ax, None, "mean temperature °C")
    return fig_to_image(fig, 82)


def chart_rain():
    cl = [c for c in A["climate"] if 1996 <= c["year"] <= LY and c["rain_annual"] is not None]
    xs = [c["year"] for c in cl]; a = [c["rain_winter_spring"] for c in cl]; b = [c["rain_annual"] - c["rain_winter_spring"] for c in cl]
    fig, ax = plt.subplots(figsize=(3.6, 2.6))
    ax.bar(xs, a, color=ACCENT, width=0.72, label="Jun–Nov"); ax.bar(xs, b, bottom=a, color="#c9cfca", width=0.72, label="Rest of year")
    ax.legend(loc="upper left", fontsize=7, ncol=2); ax.grid(axis="x", visible=False)
    ax.set_ylim(0, max(np.add(a, b)) * 1.18)
    style_ax(ax, None, "rainfall, mm")
    return fig_to_image(fig, 82)


def chart_scatter():
    cy = {c["year"]: c for c in A["climate"]}
    Y = [y for y in C["yearly"] if y["n"] >= A["params"]["min_year_n"] and y["year"] in cy and y["year"] <= LY]
    xs = np.array([cy[y["year"]]["annual"] for y in Y]); ys = np.array([y["anom_mean"] for y in Y])
    fig, ax = plt.subplots(figsize=(3.6, 2.6))
    ax.scatter(xs, ys, s=30, c=[EARLY if v < 0 else LATE for v in ys], edgecolor="white", lw=0.8, zorder=3)
    b = np.polyfit(xs, ys, 1); xx = np.array([xs.min(), xs.max()]); ax.plot(xx, np.polyval(b, xx), color=INK, lw=1.4)
    for y, x, v in zip([y["year"] for y in Y], xs, ys):
        if y in EARLY_YEARS + LATE_YEARS:
            ax.annotate(str(y), (x, v), xytext=(4, 2), textcoords="offset points", fontsize=6.5, color=INK3)
    ax.axhline(0, color=INK3, lw=0.6)
    style_ax(ax, "annual mean temperature °C", "flowering index, days")
    return fig_to_image(fig, 82)


def chart_window():
    W = C["window_sensitivity"]
    fig, ax = plt.subplots(figsize=(3.6, 2.6))
    for i, w in enumerate(W):
        ax.plot([i, i], [w["lo_mean"], w["hi_mean"]], color=ACCENT, lw=6, alpha=0.3, solid_capstyle="round")
        ax.plot(i, w["sens_mean"], "o", color=INK, ms=5.5, mec="white", mew=1)
    ax.set_xticks(range(len(W))); ax.set_xticklabels([f"{w['window']} d" for w in W])
    ax.axhline(0, color=INK3, lw=0.6); ax.grid(axis="x", visible=False)
    style_ax(ax, "warm-up period before flowering", "days earlier per °C")
    return fig_to_image(fig, 82)


# ---------------------------------------------------------------- flowables
class Rule(Flowable):
    def __init__(self, width, color=LINE, thickness=0.7, space=4):
        super().__init__(); self.width, self.color, self.thickness, self.space = width, color, thickness, space

    def wrap(self, *a):
        return self.width, self.space * 2

    def draw(self):
        self.canv.setStrokeColor(colors.HexColor(self.color)); self.canv.setLineWidth(self.thickness)
        self.canv.line(0, self.space, self.width, self.space)


def stat_band(items, width):
    cells = [[Table([[P(v, "statv")], [P(l, "statl")]], colWidths=[width / len(items) - 8], style=[("LEFTPADDING", (0, 0), (-1, -1), 0),
             ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]) for v, l in items]]
    t = Table(cells, colWidths=[width / len(items)] * len(items))
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(BG2)), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LINEBEFORE", (1, 0), (-1, -1), 0.8, colors.white), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                           ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
    return t


def callout(flow, width, bg=ACCENT_SOFT, border=ACCENT):
    t = Table([[flow]], colWidths=[width])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(bg)), ("LINEBEFORE", (0, 0), (0, -1), 2.5, colors.HexColor(border)),
                           ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                           ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return t


def data_table(header, rows, widths, numcols=()):
    data = [[P(h, "cellheadnum" if i in numcols else "cellhead") for i, h in enumerate(header)]]
    for r in rows:
        data.append([c if isinstance(c, Flowable) else P(str(c), "cellnum" if i in numcols else "cell") for i, c in enumerate(r)])
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor(INK3)), ("LINEBELOW", (0, 1), (-1, -1), 0.4, colors.HexColor(LINE)),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                           ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))
    return t


def two_up(left, right, width):
    t = Table([[left, right]], colWidths=[width / 2, width / 2])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (0, -1), 8),
                           ("RIGHTPADDING", (1, 0), (1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0)]))
    return t


# ---------------------------------------------------------------- page templates
PAGE_W, PAGE_H = A4
M_L, M_R, M_T, M_B = 20 * mm, 20 * mm, 22 * mm, 20 * mm
W = PAGE_W - M_L - M_R
GEN = datetime.date.today().strftime("%-d %B %Y")


def on_cover(c, doc):
    c.saveState()
    c.setFillColor(colors.HexColor(ACCENT)); c.rect(0, PAGE_H - 92 * mm, PAGE_W, 92 * mm, stroke=0, fill=1)
    # a quiet phenology motif: one dot per leaflet, placed by year (x) and day of year (y)
    c.setFillColor(colors.HexColor("#7fa592"))
    x0, x1, y0, y1 = M_L, PAGE_W - M_R, PAGE_H - 80 * mm, PAGE_H - 14 * mm
    for r in D:
        x = x0 + (r["year"] - 1997 + r["doy"] / 366) / (LY + 2 - 1997) * (x1 - x0)
        y = y0 + (r["n_plants"] / 40) * (y1 - y0) * 0.9
        c.circle(x, min(y, y1), 0.95, stroke=0, fill=1)
    c.setFillColor(colors.HexColor("#d7e5dd")); c.setFont("Plex", 7)
    c.drawString(M_L, PAGE_H - 85 * mm, f"Each dot is one leaflet: its date (left to right, 1997–{LY + 1}) and how many plants it featured (bottom to top).")
    c.drawString(M_L, PAGE_H - 88.5 * mm, "The flat line from 2014 is a change of format: leaflets became a fixed walk of 15 stops, published fortnightly.")
    c.setFillColor(colors.HexColor(INK3)); c.setFont("Plex", 8)
    c.drawString(M_L, 14 * mm, f"Generated {GEN}  ·  {SITE}")
    c.restoreState()


def on_page(c, doc):
    c.saveState()
    c.setFont("Plex", 7.5); c.setFillColor(colors.HexColor(INK3))
    c.drawString(M_L, PAGE_H - 12 * mm, "CANBERRA BLOOM RECORD")
    c.drawRightString(PAGE_W - M_R, PAGE_H - 12 * mm, "Flowering times at the Australian National Botanic Gardens, 1997–" + str(LY + 1))
    c.setStrokeColor(colors.HexColor(LINE)); c.setLineWidth(0.6); c.line(M_L, PAGE_H - 14 * mm, PAGE_W - M_R, PAGE_H - 14 * mm)
    c.drawString(M_L, 11 * mm, f"Generated {GEN}  ·  {SITE}")
    c.drawRightString(PAGE_W - M_R, 11 * mm, str(doc.page))
    c.restoreState()


doc = BaseDocTemplate(OUT, pagesize=A4, leftMargin=M_L, rightMargin=M_R, topMargin=M_T, bottomMargin=M_B,
                      title="Canberra Bloom Record: are the Gardens' plants flowering earlier?", author="Canberra Bloom Record",
                      subject="Flowering times at the Australian National Botanic Gardens from volunteer flower-walk leaflets, 1997–" + str(LY + 1))
cover_frame = Frame(M_L, M_B, W, PAGE_H - M_B - 100 * mm, id="cover")
body_frame = Frame(M_L, M_B, W, PAGE_H - M_T - M_B, id="body")
doc.addPageTemplates([PageTemplate("cover", [cover_frame], onPage=on_cover), PageTemplate("body", [body_frame], onPage=on_page)])

# ---------------------------------------------------------------- numbers used in the text
n_iftw = sum(1 for r in D if r.get("series") == "IFTW"); n_fff = sum(1 for r in D if r.get("series") == "FFF")
n_rec = sum(r["n_plants"] for r in D)
n_wb = sum(1 for r in D if r["source"] == "wayback")
allp = [p for r in D for p in r["plants"]]
pct_sp = 100 * sum(1 for p in allp if p.get("accepted_species")) / len(allp)
pct_fam = 100 * sum(1 for p in allp if p.get("family")) / len(allp)
n_ren = sum(1 for p in allp if p.get("renamed"))
n_flag = sum(1 for r in D if r["flags"])
W_ = C["window_sensitivity"]; w60 = next(w for w in W_ if w["window"] == 60); w180 = next(w for w in W_ if w["window"] == 180)
obs = R["all_years"]["mean_days_per_decade"]
expLo, expHi = w60["sens_mean"] * w60["warming_per_decade"], w180["sens_mean"] * w180["warming_per_decade"]
shLo, shHi = round(100 * expLo / obs), round(100 * expHi / obs)
SH = [s for s in S if not s["long_flowering"]]
earlyM = sum(1 for s in SH if s["slope_mean"] < 0)
qE = sum(1 for s in S if s["q_mean"] < .1 and s["slope_mean"] < 0); qL = sum(1 for s in S if s["q_mean"] < .1 and s["slope_mean"] > 0)
ct = A["climate_trends"]; yc = C["year_corr_mean"]; step = C["series_step_mean"]["friends_series"]
yrs_span = LY + 1 - 1997
total_days = round(abs(obs) * yrs_span / 10)
th = R["thinned_fortnightly"]; sp = A["climate_splice"]

# validation results, if any reviewer files have been added
val = None
vfiles = glob.glob(os.path.join(ROOT, "validation", "*.json"))
if vfiles:
    c_ = collections.Counter()
    for f in vfiles:
        for b in json.load(open(f)).get("brochures", {}).values():
            if b.get("done"):
                c_["done"] += 1
                for v in b.get("rows", {}).values():
                    c_[v["verdict"]] += 1
                c_["missed"] += len([m for m in b.get("missed", []) if m.strip()])
    found = c_["ok"] + c_["wrong_name"]
    if c_["done"]:
        val = dict(done=c_["done"], checked=found + c_["not_plant"], prec=found / max(1, found + c_["not_plant"]),
                   rec=found / max(1, found + c_["missed"]), name=c_["ok"] / max(1, found))

# ---------------------------------------------------------------- story
s = []
s += [NextPageTemplate("body")]
s += [Spacer(1, 4 * mm), P("A REPORT FROM THE CANBERRA BLOOM RECORD", "eyebrow"),
      Paragraph("Are the Gardens' plants<br/>flowering earlier?", ParagraphStyle("t", parent=st["h1"], fontSize=34, leading=38, spaceAfter=12)),
      P(f"Evidence from {n_iftw + n_fff:,} volunteer flower-walk leaflets written at the Australian National Botanic Gardens, Canberra, from 1997 to {LY + 1}.", "lead"),
      Spacer(1, 6 * mm),
      stat_band([(f"{fmt(obs)} days", "change in flowering time per decade, averaged over all plants"),
                 (f"{shLo}–{shHi}%", "of that change matched by Canberra's warming"),
                 (f"{len(S)}", "plants and cultivars with enough records to track"),
                 (f"{n_rec:,}", "records of a plant in flower on a given day")], W),
      Spacer(1, 10 * mm),
      P("<b>How to read this report.</b> The first two pages give the answer in plain language. The sections after that show the evidence, the charts behind it, and how much weight it can bear. A glossary at the end explains the few technical terms. Every figure here comes from the same data as the website, where each leaflet and each plant can be looked up and checked.", "body"),
      P(f'Website: <link href="{SITE}" color="{ACCENT}">{SITE}</link>', "small"),
      PageBreak()]

# ---- summary
s += [P("SUMMARY", "eyebrow"), P("The short answer", "h1"),
      Paragraph(f"The plants in the Gardens now flower about <font color='{EARLY}'>{abs(obs):.0f} days earlier per decade</font> than in 1997, roughly {total_days} days over the whole period. Warmer years flower earlier, and Canberra's warming accounts for roughly {shLo}–{shHi}% of the change.", st["big"]),
      P("<b>Where the evidence comes from.</b> Every week or two since 1997 a volunteer has walked through the Gardens and written a leaflet naming the plants in flower along the way. The Gardens published these as <i>In Flower This Week</i> until August 2016, and the Friends of the ANBG have continued them since as <i>Flowers, Fruit &amp; Foliage</i>. In every leaflet the featured plants are printed in bold. That makes it possible to list, for each plant, the dates it was in flower, year after year."),
      P("What was found", "h2")]
s += bullets([
    f"<b>Flowering is earlier.</b> Across {len(S)} plants seen in at least eight years, the middle of each plant's flowering period moved {fmt(obs)} days per decade (95% confidence interval {fmt(R['all_years']['mean_lo'])} to {fmt(R['all_years']['mean_hi'])}). Of the {len(SH)} plants with a clear flowering season, {earlyM} ({round(100 * earlyM / len(SH))}%) moved earlier.",
    f"<b>The result holds when checked.</b> It holds when the weekly leaflets of the early years are thinned to match the later fortnightly ones, when long-flowering plants are left out, and within the Gardens' own leaflets alone. Nothing jumps at the 2016 handover to the Friends.",
    f"<b>Warmth brings flowering forward.</b> Canberra warmed by about {ct['annual']['per_decade']:.1f} °C per decade from 1997 to {LY}. In years that were warmer than usual before a plant's season, it flowered {abs(w60['sens_mean']):.0f}–{abs(w180['sens_mean']):.0f} days earlier per degree.",
    f"<b>Warming explains only part of the change.</b> Multiplying that sensitivity by the actual warming gives {fmt(expLo)} to {fmt(expHi)} days per decade, about {shLo}–{shHi}% of the {fmt(obs)} observed. Rainfall made no clear difference. The rest is probably the Gardens themselves changing (plants maturing, new plantings, watering) and changes in who wrote the leaflets and which paths they walked.",
])
s += [Spacer(1, 3 * mm), callout([P("How much weight does this bear?", "h3"),
      P("The leaflets were written to guide visitors, not as a scientific survey. A plant only appears when a volunteer chose to walk past it and mention it. The overall pattern across hundreds of plants is fairly robust. The result for any single plant is weak evidence and should be treated as a lead to follow up, not a finding. Read the whole report as a strong hint rather than proof.", "body")], W),
      PageBreak()]

# ---- 1. the leaflets
s += [P("1 · THE EVIDENCE", "eyebrow"), P("Thirty years of flower-walk leaflets", "h1"),
      P(f"The report draws on two series of leaflets that follow the same format. Both describe a short walk through the Gardens, stop by stop, with the plants in flower printed in bold."),
      data_table(["Series", "Published by", "Period", "Format", "Leaflets"],
                 [["<i>In Flower This Week</i>", "Australian National Botanic Gardens", "Apr 1997 – Aug 2016", "Web pages; weekly, fortnightly from 2014", f"{n_iftw}"],
                  ["<i>Flowers, Fruit &amp; Foliage</i>", "Friends of the ANBG", "Aug 2016 – " + datetime.date.fromisoformat(max(r['date'] for r in D)).strftime("%b %Y"), "PDF leaflets; fortnightly", f"{n_fff}"]],
                 [W * .22, W * .25, W * .19, W * .24, W * .10], numcols=(4,)),
      Spacer(1, 5 * mm), chart_leaflets(),
      P(f"Leaflets per year. The drop in 2014 is the switch from weekly to fortnightly leaflets. At the same time each leaflet became a fixed walk of 15 stops, down from an average of about 16–23 plants, so later years have about a third as many records. Section 2 explains how the analysis allows for this. {n_wb} leaflets are no longer on their original websites and were recovered from the Internet Archive's copies. There are no leaflets for April–June 2020 or mid-August to October 2021, the periods of COVID-19 restrictions in Canberra.", "cap"),
      P("Weather data", "h2"),
      P(f"Daily temperatures come from the Bureau of Meteorology's ACORN-SAT record for Canberra Airport, a long-running series that the Bureau adjusts for changes in instruments and location. It currently runs to {sp['acorn_end'][:4]}. For the months since then, the ERA5 global weather reanalysis for the Gardens' location was used, corrected month by month to match the Bureau's record (the two agree closely: r = {sp['r_tmax']:.2f}). Rainfall comes from ERA5 throughout."),
      PageBreak()]

# ---- 2. method
s += [P("2 · METHOD", "eyebrow"), P("From leaflets to flowering dates", "h1"),
      P("The process has five steps. Each was automated so it can be rerun and checked.")]
steps = [
    ("Collect every leaflet", f"All {n_iftw} Gardens web pages and {n_fff} Friends PDFs listed on the organisations' websites were downloaded. Where a link had gone dead, the Internet Archive's copy was used. Some early archived PDFs had been cut short at 1 MB, and for those the most complete copy was chosen."),
    ("Pick out the plants", f"A program read each leaflet and kept the words printed in bold that look like plant names. Italic Latin names and cultivar names in quotes, such as <i>Grevillea</i> ‘Lady O’, were joined up. The Friends' PDFs are laid out in two columns, so they were read stop by stop. Ten leaflets from 2019–20 stored their text in a scrambled form and were decoded. This gave {n_rec:,} records of a plant in flower on a given date."),
    ("Tidy the names", f"Botanists rename plants, and leaflets sometimes misspell them. Every name was checked against the Atlas of Living Australia, which gives the currently accepted name. For example, <i>Bracteantha bracteata</i> is now <i>Xerochrysum bracteatum</i>. {pct_sp:.0f}% of records were matched to a species and {pct_fam:.1f}% to at least a plant family. {n_ren:,} records were printed under an older name."),
    ("Work out flowering time", f"For each plant and each year, the middle of the dates it was mentioned is its <b>mid-flowering date</b>. Each plant's year starts at its quietest time, so summer bloomers aren't split at New Year. A year only counts if the leaflets covered that plant's season with no gap longer than {A['params']['max_gap']} days. Plants needed at least {A['params']['min_seasons']} such years spread over {A['params']['min_span']}+ years, which left {len(S)} plants and cultivars."),
    ("Compare with the weather", "For each plant and year, the average temperature in the weeks before its usual flowering start was compared with how early or late it flowered that year. Garden-wide results pool all plants, and the uncertainty allows for plants in the same year sharing the same weather, volunteer and route."),
]
for i, (h, t) in enumerate(steps, 1):
    num = Table([[Paragraph(str(i), ParagraphStyle("n", fontName="Spectral-SB", fontSize=13, leading=16, textColor=colors.white, alignment=TA_CENTER))]],
                colWidths=[8 * mm], rowHeights=[8 * mm])
    num.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(ACCENT)), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                             ("ROUNDEDCORNERS", [4, 4, 4, 4]), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
    row = Table([[num, [P(h, "h3"), P(t, "body")]]], colWidths=[13 * mm, W - 13 * mm])
    row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 2)]))
    s.append(KeepTogether(row))
s += [P("Why the middle of flowering, not the first sighting?", "h2"),
      P(f"The most obvious measure would be the first date each year a plant appears. But in 2014 the leaflets went from weekly to fortnightly, and with half as many leaflets a plant tends to be spotted about a week later, even if nothing has changed. Taken at face value, first sightings show only {fmt(R['all_years']['days_per_decade'])} days per decade. When the early weekly years are thinned to fortnightly so both periods are sampled alike, first sightings show {fmt(th['days_per_decade'])} days per decade (95% CI {fmt(th['lo'])} to {fmt(th['hi'])}), close to the mid-flowering result. The mid-flowering date isn't thrown off by the sampling change, so it is the main measure in this report."),
      P("Checking the extraction", "h2"),
      P(f"The website's Leaflets page shows every leaflet next to the plants taken from it, and flags {n_flag} leaflets for a closer look. A Check accuracy page lets reviewers compare a random sample of leaflets with the originals." +
        (f" So far {val['done']} leaflets ({val['checked']} records) have been checked: {100 * val['prec']:.1f}% of extracted records were genuine featured plants, {100 * val['rec']:.1f}% of featured plants were found, and {100 * val['name']:.1f}% of names were correct." if val else
         " Reviewer results will be added to this report when they are available.")),
      PageBreak()]

# ---- 3. findings, garden-wide
yr = R["all_years"]
s += [P("3 · FINDINGS", "eyebrow"), P("The whole garden is flowering earlier", "h1"),
      P(f"The chart below combines all {yr['n_species']} plants. For each plant and year, it takes how many days earlier or later than that plant's usual mid-flowering date it flowered, then averages across plants. Bars below zero are years when the garden as a whole flowered early."),
      chart_yearly(),
      P(f"Garden-wide flowering index by year (years with at least {A['params']['min_year_n']} plant records). The dashed line is the trend: {fmt(obs)} days per decade (95% CI {fmt(yr['mean_lo'])} to {fmt(yr['mean_hi'])}). The earliest years were {yearlist(EARLY_YEARS)}, and the latest {yearlist(LATE_YEARS)}.", "cap"),
      P("Is the result robust?", "h2"),
      P("Changes in how the leaflets were produced could create a false trend. So the analysis was repeated on subsets of the data that each remove one possible distortion. Green shows the main measure (mid-flowering date) and grey the first-sighting measure. A result is solid when the green dots stay left of zero and their bars don't cross it."),
      chart_robust(),
      P(f"Each row repeats the garden-wide calculation on a subset. Only the Friends-only row, with just {R['friends_2016_now']['n_species']} plants over ten years, is too small to say anything. After allowing for the trend, the Friends' leaflets sit {fmt(step['coef'])} days from the Gardens' ones (p {pf(step['p'])}), so the handover did not create the result.", "cap"),
      PageBreak()]

# ---- 4. species
best = sorted([x for x in S if x["kind"] == "species" and not x["long_flowering"] and x["slope_mean"] < 0], key=lambda x: x["p_mean"])
ex = best[0]
s += [P("4 · WHICH PLANTS", "eyebrow"), P("Which plants are shifting", "h1"),
      P(f"Most plants moved earlier, but by different amounts, and a few moved later. The left chart shows the spread across the {len(SH)} plants with a clear flowering season. The right chart averages by plant family."),
      two_up([chart_hist(), P(f"{earlyM} of {len(SH)} plants ({round(100 * earlyM / len(SH))}%) moved earlier. If nothing were changing, about half would by chance.", "cap")],
             [chart_families(), P("Families with at least three wild species analysed. Numbers show how many species.", "cap")], W),
      P("One plant in detail", "h2"),
      P(f"<b>{sci(ex['key'])}</b>{(' (' + esc(ex['common']) + ')') if ex['common'] and not re.match(r'(?i)^(a|an) ', ex['common']) else ''} has the strongest evidence of an earlier shift among wild species. Each grey dot is one leaflet that mentioned it. The green dots mark the middle of each year's mentions."),
      chart_species(ex),
      P(f"Mid-flowering moved {fmt(ex['slope_mean'])} days per decade over {ex['n_seasons']} well-covered years ({ex['first_season']}–{ex['last_season']}). The earliest dates are at the top.", "cap"),
      PageBreak()]

top = sorted([x for x in SH if x["slope_mean"] < 0], key=lambda x: x["p_mean"])[:18]
later = sorted([x for x in SH if x["slope_mean"] > 0], key=lambda x: x["p_mean"])[:8]


def sp_row(x):
    common = x["common"] if x["common"] and not re.match(r"(?i)^(a|an) ", x["common"]) else ""
    return [P(sci(x["key"]) + (f"<br/><font color='{INK3}' size='7.5'>{esc(common)}</font>" if common else ""), "cell"), esc(x["family"] or "–"),
            x["typical_onset"], str(x["n_seasons"]), fmt(x["slope_mean"]), pf(x["p_mean"]), f"{x['q_mean']:.2f}"]


hdr = ["Plant", "Family", "Usually starts", "Years", "Shift (days/decade)", "p", "q"]
cw = [W * .34, W * .17, W * .13, W * .08, W * .12, W * .08, W * .08]
s += [P("4 · WHICH PLANTS (CONTINUED)", "eyebrow"), P("Plants with the clearest shifts", "h2"),
      P(f"These tables list the plants whose change is least likely to be chance, measured by the p value. With {len(S)} plants tested, a few will look significant by luck. The q value corrects for that: q below 0.1 means the shift is unlikely to be a false alarm. {qE} plants moved earlier and {qL} later with q below 0.1. Treat the rest as leads."),
      P("Moving earlier", "h3"), data_table(hdr, [sp_row(x) for x in top], cw, numcols=(3, 4, 5, 6)),
      Spacer(1, 4 * mm), KeepTogether([P("Moving later", "h3"), data_table(hdr, [sp_row(x) for x in later], cw, numcols=(3, 4, 5, 6))]),
      P("Long-flowering plants (in flower for more than about five months of the year) are left out. Their dates mostly reflect which weeks a volunteer happened to pass, not when they flowered. The full list of plants, with search and charts, is on the website's Findings page.", "cap"),
      PageBreak()]

# ---- 5. why
trm = C["temp_rain_year_mean"]
s += [P("5 · WHY", "eyebrow"), P("Is it the warming?", "h1"),
      P(f"Canberra has warmed over the period, especially in winter and spring. Warmer years clearly flower earlier. But the warming is modest, and on its own it accounts for only part of the change."),
      two_up([chart_temp(), P(f"Canberra seasonal mean temperature with trend lines. Per decade, 1997–{LY}: annual {fmt(ct['annual']['per_decade'], 2)} °C, winter {fmt(ct['winter']['per_decade'], 2)}, spring {fmt(ct['spring']['per_decade'], 2)}.", "cap")],
             [chart_rain(), P("Rainfall. The Millennium Drought lasted until 2009. 2010 and the La Niña years of 2021–22 were very wet. Unlike temperature, rainfall shows no clear link with flowering time.", "cap")], W),
      two_up([chart_scatter(), P(f"Each dot is a year. Warmer years flowered earlier (r = {yc['annual']['r']:.2f}). With the long-term trend removed from both, the link remains (r = {yc['annual_detrended']['r']:.2f}, p {pf(yc['annual_detrended']['p'])}).", "cap")],
             [chart_window(), P(f"Days earlier per °C, depending on how long a warm-up before flowering is measured. Longer periods show stronger effects, up to {abs(w180['sens_mean']):.1f} days per °C.", "cap")], W),
      PageBreak(), P("5 · WHY (CONTINUED)", "eyebrow"), P("Putting it together", "h2")]
s += bullets([
    f"<b>How much can warming explain?</b> Plants flower {abs(w60['sens_mean']):.1f}–{abs(w180['sens_mean']):.1f} days earlier per °C, and the relevant periods warmed about {w180['warming_per_decade']:.2f}–{w60['warming_per_decade']:.2f} °C per decade. That predicts {fmt(expLo)} to {fmt(expHi)} days per decade, against {fmt(obs)} observed, or about {shLo}–{shHi}%.",
    f"<b>The rest isn't explained by weather.</b> With temperature, rainfall and time in one model, a shift of {fmt(trm['year']['coef'] * 10)} days per decade remains. This is a lower bound on warming's share, because a fixed warm-up period only approximates when each plant responds.",
    f"<b>Rainfall makes no clear difference.</b> Neither wetter years (r = {yc['rain_annual_detrended']['r']:.2f} after removing trends) nor rain before each plant's own season shows a consistent effect on flowering time.",
    "<b>Other likely causes.</b> The garden is maturing and watered, which can make plants less tied to the weather. New plantings and cultivars are often chosen because they flower early or for long periods. The volunteers and their routes changed over time. The leaflets can't separate these effects.",
])
s += [Spacer(1, 6 * mm), Rule(W), Spacer(1, 2 * mm)]

# ---- 6. limitations
s += [P("6 · LIMITATIONS", "eyebrow"), P("What this can and can't tell us", "h1")]
s += bullets([
    "<b>The leaflets are not a survey.</b> A plant is recorded only when a volunteer chose to feature it. Its absence in a given week means little.",
    "<b>Single plants are weak evidence.</b> With hundreds of plants tested, some will show large shifts by chance. Only the q values guard against that, and only a handful of plants pass.",
    "<b>The way the leaflets were made changed.</b> The switch to fortnightly leaflets in 2014, longer leaflets in the 2000s, new writers and new routes could all nudge the results. The checks in section 3 remove each of these in turn, and the result held.",
    "<b>Automated reading makes mistakes.</b> The website shows every extracted plant beside its leaflet so errors can be found, and a checking page measures the error rate.",
    f"<b>Weather is measured at the airport.</b> Canberra Airport is about 8 km from the Gardens. Year-to-year changes track well, but the Gardens' own conditions differ, and it is irrigated. Temperatures after {sp['acorn_end'][:4]} come from a weather model, not the Bureau's adjusted record.",
    "<b>Correlation is not proof of cause.</b> Warm years flowering early fits a warming effect, but the leaflets alone can't rule out other explanations.",
])
s += [PageBreak(), P("GLOSSARY AND CREDITS", "eyebrow"), P("Glossary", "h2")]
gl = [("Mid-flowering date", "The middle of the dates a plant was mentioned in a given year. The main measure in this report."),
      ("First appearance", "The first date in a year a plant was mentioned. Affected by how often leaflets were published."),
      ("Days per decade", "How much a date moved, on average, for every ten years that passed. Negative means earlier."),
      ("95% confidence interval", "The range the true value probably lies in. If it doesn't include zero, the change is unlikely to be chance."),
      ("p value", "How likely a result this large would be if nothing were really changing. Below 0.05 is usually called significant."),
      ("q value", "A p value adjusted for testing many plants at once. Below 0.1 means the result is unlikely to be a false alarm."),
      ("r (correlation)", "How closely two things move together, from −1 to +1. Zero means no relationship."),
      ("Taxon, cultivar", "A taxon is any named plant group, here usually a species. A cultivar is a named garden variety, written in quotes."),
      ("ACORN-SAT, ERA5", "The Bureau of Meteorology's adjusted temperature record, and a global weather reanalysis used to fill recent months and rainfall.")]
s += [data_table(["Term", "Meaning"], [[f"<b>{a}</b>", b] for a, b in gl], [W * .26, W * .74])]
s += [P("Credits and sources", "h2"),
      P(f"Leaflets written by the volunteers of the Australian National Botanic Gardens and the Friends of the ANBG. Short excerpts are used for analysis only. Plant names: Atlas of Living Australia. Temperature: Bureau of Meteorology ACORN-SAT (CC BY). Rainfall and recent temperature: Copernicus ERA5 via Open-Meteo (CC BY 4.0). The website, code and processed data are at <link href='{SITE}' color='{ACCENT}'>{SITE}</link> and <link href='{REPO}' color='{ACCENT}'>{REPO}</link>. Report generated {GEN}.", "small")]

doc.build(s)
print("wrote", os.path.relpath(OUT, ROOT), f"{os.path.getsize(OUT) / 1e6:.1f} MB")
