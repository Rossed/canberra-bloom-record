"""Extract plants from Friends of the ANBG "Flowers, Fruit & Foliage" PDFs -> data/extract_fff.json

Same convention as In Flower This Week: each numbered stop ("1.", "2." in bold) names its plant(s) in
bold italics. PDFs are two-column, so text is split into numbered stops rather than read top to bottom.
Name cleaning/parsing is shared with 04_extract.py so both series are treated identically.
"""
import os, re, json, datetime, collections, importlib.util
import pymupdf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("ex", os.path.join(ROOT, "pipeline", "04_extract.py"))
ex = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ex)

LOG = json.load(open(os.path.join(ROOT, "data", "fff", "download_log.json")))
IFTW = json.load(open(os.path.join(ROOT, "data", "extract_iftw.json")))
LAST_IFTW = max(r["date"] for r in IFTW)
gc = collections.Counter(p["genus"] for r in IFTW for p in r["plants"])
ex.KNOWN_GENERA.update(g for g, n in gc.items() if n >= 5)
MON = "January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec"


# Some 2019-20 leaflets were made with "Microsoft Print to PDF", whose embedded fonts map every
# character 29 code points low (")HDWXULQJ" = "Featuring"). Bold/italic flags survive, so we shift back.
SHIFT_SPECIAL = {"µ": "‘", "¶": "’", "p": "é", "³": "“", "´": "”", "±": "–", "²": "—"}


def unshift(t):
    return "".join(SHIFT_SPECIAL.get(ch, " " if ch == " " else chr(ord(ch) + 29) if ord(ch) < 0x62 else ch) for ch in t)


def is_shifted(doc):
    raw = " ".join(p.get_text() for p in doc)
    return raw.count(" the ") + raw.count("The ") < unshift(raw).count("WKH") and "WKH" in raw or \
        (raw.count("the") < 5 and unshift(raw).count("the") > 20)


def stream(path):
    """Concatenate all text spans with per-char bold/italic flags; lines joined by spaces."""
    doc = pymupdf.open(path)
    shifted = is_shifted(doc)
    T, B, I = [], [], []
    for page in doc:
        for blk in page.get_text("dict")["blocks"]:
            for ln in blk.get("lines", []):
                for sp in ln["spans"]:
                    t = sp["text"]
                    if shifted and sp["font"].startswith("CIDFont"):
                        t = unshift(t)
                    t = t.replace("\xa0", " ")
                    bold = bool(sp["flags"] & 16) or "bold" in sp["font"].lower() or "black" in sp["font"].lower()
                    ital = bool(sp["flags"] & 2) or "italic" in sp["font"].lower() or "oblique" in sp["font"].lower()
                    for ch in t:
                        T.append(ch); B.append(bold); I.append(ital)
                T.append(" "); B.append(False); I.append(False)
            T.append("\n"); B.append(False); I.append(False)
    return "".join(T), B, I, doc.page_count, shifted


def extract(rec):
    path = os.path.join(ROOT, rec["path"])
    T, B, I, pages, shifted = stream(path)
    date = datetime.date.fromisoformat(rec["date"])
    # heading, e.g. "12 - 25 January 2022"
    hm = re.search(rf"(?<![\d])\b(\d{{1,2}})\s*(?:({MON})\w*\s*)?(?:(?:\d{{4}}|[‘'’]\d\d)\s*)?[-–—]\s*\d{{1,2}}\s*({MON})\w*\s*(\d{{4}})?", T)
    if not hm:
        hm = re.search(rf"\b(\d{{1,2}})\s+({MON})\w*\s+(20\d\d)", T)
    heading = re.sub(r"\s+", " ", hm.group(0)).strip() if hm else None
    au = re.search(r"Written and\s+illustrated\s+by\s+(?:ANBG\s+)?(?:Friends?\s+)?([A-Z][\w\s,&]+?)(?:\s{2,}|\n|$| A publication)", re.sub(r"\s+", " ", T) + " ")
    author = re.sub(r"\s+", " ", au.group(1)).strip() if au else None
    if "Walcott" in T:
        author = "Rosalind & Benjamin Walcott"
    intro = re.search(r"(Today we (?:will )?[^.]*?(?:\.|(?=\s+\d{1,2}\.\s)))", re.sub(r"\s+", " ", T))
    # numbered stops: bold "N." markers
    no_format = not any(B)
    stops = [(m.start(), int(m.group(1))) for m in re.finditer(r"(?<![\d.])(\d{1,2})\.\s", T) if B[m.start()] or no_format]
    stops.sort()
    bounds = [(a, stops[i + 1][0] if i + 1 < len(stops) else len(T), n) for i, (a, n) in enumerate(stops)]
    plants = []
    genus_by_initial = {}
    for a, b, n in bounds:
        seg = T[a:b]
        # an item runs until a big gap / next block that isn't part of it; trim at the next paragraph of boilerplate
        k = a
        spans = []
        while k < b:
            if B[k] and I[k] and T[k].strip():
                j = k
                while j < b and (B[j] or (not T[j].strip() and j + 1 < b and B[j + 1])):
                    if re.match(r"\d{1,2}\.\s", T[j:j + 4]) and (j == k or not T[j - 1].isalnum()):
                        break  # next numbered stop
                    j += 1
                spans.append([k, j]); k = j
            else:
                k += 1
        # merge a bold italic genus with following bold (non-italic) cultivar or continuation
        merged = []
        for s in spans:
            if merged:
                gap = T[merged[-1][1]:s[0]]
                nxt = T[s[0]:s[1]].strip()
                if len(gap) <= 3 and not gap.strip() and re.match(r"^(['‘’`(×]|subsp|ssp|var\b|f\.|[a-z])", nxt):
                    merged[-1][1] = s[1]; continue
            merged.append(s)
        if no_format:
            # PDF lost its font information: take known-genus names mentioned at this stop
            gx = "|".join(sorted(ex.KNOWN_GENERA, key=len, reverse=True))
            merged = [[m.start(), m.end()] for m in re.finditer(
                rf"\b(?:{gx})\s+(?:[a-z][a-z-]+|×)(?:\s+(?:subsp|var)\.\s+[a-z-]+)?(?:\s+[‘'][^’'\n]{{2,30}}[’'])?|\b(?:{gx})\s+[‘'][^’'\n]{{2,30}}[’']", seg)]
            merged = [[a + x, a + y] for x, y in merged[:2]]
        for s0, s1 in merged:
            # extend over a following bold non-italic cultivar name: **_Corymbia ficifolia_** **‘Dwarf Orange’**
            cm = re.match(r"\s*[‘'`]([^’'`]{2,40})[’'`]", T[s1:s1 + 50])
            if cm and B[s1 + cm.start(1)]:
                s1 = s1 + cm.end()
            name = ex.clean_name(re.sub(r"([a-z])-\s+([a-z])", r"\1\2", T[s0:s1]))  # re-join words hyphenated across lines
            if not name or len(name) < 4 or len(name) > 90:
                continue
            parsed = ex.parse_name(name, genus_by_initial)
            if not parsed:
                continue
            genus_by_initial[parsed["genus"][0]] = parsed["genus"]
            post = re.sub(r"\s+", " ", T[s1:b])
            ctx = re.sub(r"\s+", " ", seg).strip()
            common = None
            cm2 = re.match(r"\s*[,]?\s*(?:or |commonly known as |also known as |known as )(?:the )?((?:[A-Z][\w'’-]+)(?:[ -](?:[A-Z][\w'’-]+|of|the)){0,3})", post)
            if cm2:
                common = cm2.group(1)
            colours = sorted({ex.COLOUR_NORM.get(c, c) for c in ex.COLOURS if re.search(r"\b" + c + r"\b", post, re.I)})
            stage = "early" if ex.STAGE_EARLY.search(post) else "late" if ex.STAGE_LATE.search(post) else "peak" if ex.STAGE_PEAK.search(post) else None
            phase = "flowering"
            if ex.FRUIT.search(post) and not ex.FLOWERW.search(post):
                phase = "fruit/foliage"
            plants.append(dict(raw=re.sub(r"\s+", " ", T[s0:s1]).strip(), name=name, **parsed, sections=[], list_no=n,
                               italic=True, common_name=common, colours=colours, stage=stage, phase=phase, context=ctx[:500]))
    uniq = collections.OrderedDict()
    for pl in sorted(plants, key=lambda p: p["list_no"]):
        if pl["taxon_key"] in uniq:
            uniq[pl["taxon_key"]]["mentions"] += 1
        else:
            pl["mentions"] = 1; uniq[pl["taxon_key"]] = pl
    plants = list(uniq.values())
    nums = sorted({n for _, n in stops})
    missing_stops = sorted(set(range(1, max(nums) + 1)) - set(nums)) if nums else []
    stops_without_plant = sorted(set(nums) - {p["list_no"] for p in plants})
    body = re.sub(r"\s+", " ", T).lower()
    flags = []
    if len(plants) < 5:
        flags.append("few plants extracted (<5)")
    if shifted:
        flags.append("text decoded from shifted font encoding")
    if no_format:
        flags.append("PDF has no bold/italic information; names matched by pattern")
    if stops_without_plant:
        flags.append(f"{len(stops_without_plant)} numbered stop(s) with no plant found")
    if heading:
        hd = re.search(rf"(\d{{1,2}})\s*(?:({MON}))?", heading)
        try:
            end_days = {(date + datetime.timedelta(days=k)).day for k in (12, 13, 14)}  # some headings show the end date
            if abs(int(hd.group(1)) - date.day) > 3 and abs(int(hd.group(1)) - date.day) < 25 and int(hd.group(1)) not in end_days:
                flags.append(f"heading '{heading}' disagrees with file date")
        except Exception:
            pass
    fid = f"FFF_{rec['date']}"
    return dict(id=fid, file=os.path.basename(path), series="FFF", url=rec.get("source_url") or rec["hrefs"][0],
                source="wayback" if rec.get("status") == "wayback" else "friends", source_url=rec.get("source_url") or rec["hrefs"][0],
                date=rec["date"], year=date.year, doy=date.timetuple().tm_yday, title="Flowers, Fruit & Foliage",
                heading_date=heading, date_range=heading if heading and re.search(r"[-–—]", heading) else None, author=author, intro=(intro.group(1) if intro else "")[:400],
                words=len(re.findall(r"\w+", T)), photo_captions=[],
                weather_mentions=sorted(w for w, rx in ex.WEATHER.items() if re.search(rx, body)),
                fauna_mentions=sorted({fa.rstrip("-") for fa in ex.FAUNA if fa in body}),
                extraction_mode="pdf-bold-italic", qa_section_refs=len(nums), qa_plants_with_section=len({p["list_no"] for p in plants}),
                possible_misses=[], plants=plants, incidental_mentions=[], n_plants=len(plants), flags=flags,
                qa_stops=nums, qa_stops_without_plant=stops_without_plant, pages=pages, font_shift_decoded=shifted)


if __name__ == "__main__":
    out = []
    for rec in LOG["issues"]:
        if rec.get("status") == "missing":
            continue
        if rec["date"] <= (datetime.date.fromisoformat(LAST_IFTW) + datetime.timedelta(days=4)).isoformat():
            continue  # same fortnight as the final In Flower This Week page
        try:
            out.append(extract(rec))
        except Exception as e:
            print("ERROR", rec["date"], e)
    out.sort(key=lambda r: r["date"])
    json.dump(out, open(os.path.join(ROOT, "data", "extract_fff.json"), "w"), indent=0, ensure_ascii=False)
    print(len(out), "FFF leaflets", sum(r["n_plants"] for r in out), "plant records")
    print("flags:", collections.Counter(re.sub(r"\d+", "N", f.split("'")[0]) for r in out for f in r["flags"]))
