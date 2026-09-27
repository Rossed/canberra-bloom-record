"""Consistency check: the website and the PDF report must say the same thing.

Renders every page of the site in headless Chrome (so all script-filled text is included), extracts the
PDF text, then checks that
  1. every shared figure/sentence from facts.py appears everywhere it should,
  2. no retired claim or wording has crept back in,
  3. no page shows broken values (NaN, undefined) or a section that failed to draw.
Exits non-zero on any failure, so run_all.sh and the GitHub deploy both stop.

Usage: python3 pipeline/12_check_consistency.py [--chrome PATH]
"""
import os, re, sys, json, html, socket, subprocess, threading, functools, http.server
import pymupdf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
from facts import build_facts

CHROME_CANDIDATES = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]
chrome = sys.argv[sys.argv.index("--chrome") + 1] if "--chrome" in sys.argv else next(
    (c for c in CHROME_CANDIDATES if os.path.exists(c) or subprocess.run(["which", c], capture_output=True).returncode == 0), None)
if not chrome:
    sys.exit("No Chrome/Chromium found; pass --chrome PATH")

# ---- where each shared fact must appear -------------------------------------------------------------
# about = "How this was made", extraction = "Leaflets", analysis = "Findings", check = "Check accuracy", report = PDF
REQUIRED = {
    "sentence_shift": ["about", "analysis", "report"],
    "sentence_warming": ["about", "analysis", "report"],
    "sentence_share": ["about", "analysis", "report"],
    "sentence_families": ["about", "analysis", "report"],
    "shift_ci": ["analysis", "report"],
    "thinned_first_ci": ["analysis", "report"],
    "share": ["analysis", "report"],
    "sens_range": ["about", "analysis", "report"],
    "n_leaflets": ["extraction", "analysis", "report"],
    "n_iftw": ["about", "extraction", "report"],
    "n_fff": ["about", "extraction", "report"],
    "n_wayback": ["about", "extraction", "report"],
    "n_records": ["about", "extraction", "report"],
    "n_taxa": ["about", "analysis", "report"],
    "n_flagged": ["extraction", "report"],
    "earliest_years": ["analysis", "report"],
    "latest_years": ["analysis", "report"],
    "family_share": ["analysis", "report"],
    "family_clear": ["analysis", "report"],
    "year_r": ["analysis", "report"],
    "rain_r": ["analysis", "report"],
    "handover_step": ["analysis", "report"],
    "sentence_rule": ["about", "analysis", "report"],
    "n_used": ["extraction", "analysis", "report"],
}
# ---- wording that must never come back ---------------------------------------------------------------
FORBIDDEN = [
    r"\bbrochures?\b", r"wet years (tend|tended)? ?to flower later", r"wetter[- ]than[- ](usual|trend) years flowered later",
    r"about 11 pages", r"2009, 2013 and 2023", r"\bNaN\b", r"\bundefined\b", r"\bnull\b", r"\bInfinity\b",
    r"couldn't be drawn",                        # a Findings section failed (see safely() in index.html)
    r"Couldn't load the data files",
]
PAGES = ["about", "extraction", "analysis", "check"]


def norm(t):
    t = html.unescape(t).replace(" ", " ")
    return re.sub(r"\s+", " ", t).strip()


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); return s.getsockname()[1]


def serve(port):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    handler = functools.partial(Quiet, directory=os.path.join(ROOT, "site"))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def render(port, view):
    dom = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--virtual-time-budget=20000",
                          "--dump-dom", f"http://127.0.0.1:{port}/#{view}"], capture_output=True, text=True, timeout=120).stdout
    m = re.search(r'<div id="view-%s"[^>]*>(.*?)(<!-- =+ [A-Z ]+ =+ -->|</main>)' % view, dom, re.S)
    if not m:
        return ""
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", m.group(1), flags=re.S)
    return norm(re.sub(r"<[^>]+>", " ", body))


def main():
    F = build_facts()
    port = free_port(); srv = serve(port)
    text = {v: render(port, v) for v in PAGES}
    srv.shutdown()
    text["report"] = norm(" ".join(p.get_text() for p in pymupdf.open(os.path.join(ROOT, "site", "report", "canberra-bloom-record.pdf"))))
    # report pages mentioned on the front page must match the real PDF
    F["report_pages_phrase"] = f"{F['report_pages']} pages"
    REQUIRED["report_pages_phrase"] = ["about"]
    problems = []
    # the website's copy of the facts must match a fresh calculation from the data
    site_facts = json.load(open(os.path.join(ROOT, "site", "data", "facts.json")))
    for k, v in build_facts().items():
        if site_facts.get(k) != v:
            problems.append(f"[facts.json] '{k}' is stale: site has “{str(site_facts.get(k))[:60]}”, data gives “{str(v)[:60]}” (run pipeline/facts.py)")
    for v in PAGES:
        if len(text[v]) < 500:
            problems.append(f"[{v}] page rendered almost no text ({len(text[v])} chars): the page script probably failed")
    for key, places in REQUIRED.items():
        val = norm(str(F.get(key, "")))
        if not val:
            problems.append(f"[facts] '{key}' is empty"); continue
        for pl in places:
            if val not in text[pl]:
                problems.append(f"[{pl}] missing {key}: “{val[:90]}”")
    # every assumption must appear, word for word, on the Findings page and in the report
    for a in F["assumptions"]:
        for pl in ("analysis", "report"):
            for part in (a["title"], a["rule"][:80]):
                if norm(part) not in text[pl]:
                    problems.append(f"[{pl}] assumption missing or reworded: “{part[:70]}”")
    for pat in FORBIDDEN:
        for pl, t in text.items():
            for m in re.finditer(pat, t, re.I):
                ctx = t[max(0, m.start() - 50): m.end() + 50]
                problems.append(f"[{pl}] forbidden “{m.group(0)}” … {ctx} …")
                break
    json.dump({k: len(v) for k, v in text.items()}, open(os.path.join(ROOT, "data", "consistency_last_run.json"), "w"))
    if problems:
        print(f"CONSISTENCY CHECK FAILED ({len(problems)} problems):")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print(f"Consistency check passed: {sum(len(v) for v in REQUIRED.values())} fact placements verified across "
          f"{len(PAGES)} site pages and the {F['report_pages']}-page report; no retired wording found.")


if __name__ == "__main__":
    main()
