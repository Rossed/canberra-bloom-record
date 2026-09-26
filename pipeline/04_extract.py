"""Extract plants and metadata from every IFTW brochure in data/raw -> data/brochures.json

Convention across all eras (1997-2016): featured plants are in bold (usually bold+italic),
often followed by a garden bed reference "[Section N]". Non-bold italic binomials are
incidental mentions (e.g. hybrid parents) and are recorded separately.
"""
import os, re, json, html, datetime, collections
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
BASE = "https://www.anbg.gov.au/gardens/visiting/iftw/iftw-archive/"
wayback = json.load(open(os.path.join(ROOT, "data", "wayback_recovered.json")))
links = json.load(open(os.path.join(ROOT, "data", "download_log.json")))["links"]

MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                      "september", "october", "november", "december"], 1)}


def date_from_filename(f):
    m = re.match(r"iftw[-.](\d{2,4})[-.](\d{1,2})[-.](\d{1,2})\.html", f)
    y, mo, d = (int(x) for x in m.groups())
    if y < 100:
        y += 1900 if y > 50 else 2000
    return datetime.date(y, mo, d)


class Flat(HTMLParser):
    """Flatten HTML to text with per-character bold/italic/caption flags."""
    RESET = {"td", "tr", "table", "li", "ol", "ul", "p", "h1", "h2", "h3"}
    BLOCK = {"p", "br", "li", "div", "tr", "td", "table", "h1", "h2", "h3", "h4", "ol", "ul", "hr", "center"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.chars, self.b, self.i, self.cap, self.li = [], [], [], [], []
        self.bd = self.id = 0
        self.capdepth = 0
        self.font_stack = []
        self.skip = 0
        self.li_n = 0
        self.img_alts = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "title"):
            self.skip += 1
        if tag in ("b", "strong"):
            self.bd += 1
        elif tag in ("i", "em"):
            self.id += 1
        elif tag == "font":
            small = (a.get("size") or "").strip().startswith("-")
            self.font_stack.append(small)
            self.capdepth += small
        elif tag == "li":
            self.li_n += 1
        elif tag == "img" and a.get("alt"):
            self.img_alts.append(a["alt"])
        if tag in self.RESET:
            self.bd = self.id = 0
        if tag in self.BLOCK:
            self._emit("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "title"):
            self.skip = max(0, self.skip - 1)
        if tag in ("b", "strong"):
            self.bd = max(0, self.bd - 1)
        elif tag in ("i", "em"):
            self.id = max(0, self.id - 1)
        elif tag == "font" and self.font_stack:
            self.capdepth -= self.font_stack.pop()
        if tag in self.RESET or tag == "p":
            self.bd = self.id = 0
            if tag in ("td", "table", "tr"):
                self.capdepth, self.font_stack = 0, []
        if tag in self.BLOCK:
            self._emit("\n")

    def _emit(self, s):
        for ch in s:
            self.chars.append(ch)
            self.b.append(self.bd > 0)
            self.i.append(self.id > 0)
            self.cap.append(self.capdepth > 0)
            self.li.append(self.li_n)

    def handle_data(self, data):
        if self.skip:
            return
        data = data.replace("\r", " ").replace("\n", " ").replace("\xa0", " ")
        self._emit(data)


QUOTES = str.maketrans({"‘": "'", "’": "'", "`": "'", "´": "'", "“": '"', "”": '"',
                        "\x91": "'", "\x92": "'", "\x93": '"', "\x94": '"', "–": "-", "—": "-"})
RANK = {"subsp": "subsp.", "ssp": "subsp.", "var": "var.", "f": "f.", "forma": "f."}


def clean_name(raw):
    s = raw.translate(QUOTES)
    s = re.sub(r"\s+", " ", s).strip(" ,.;:-!?")
    s = re.sub(r"\s*\.\s*$", "", s)
    s = re.sub(r"(?<=\w)\s*'\s*", lambda m: " '" if False else m.group(0), s)
    s = re.sub(r"\b(subsp|ssp|var|f)\s*\.?\s+", lambda m: RANK[m.group(1)] + " ", s)
    s = re.sub(r"\s+x\s+(?=[a-zA-Z'])", " × ", s)
    s = re.sub(r"\s*×\s*", " × ", s)
    s = s.replace("''", "'")
    s = re.sub(r"\s+'", " '", s)
    s = re.sub(r"'\s*$", "'", s)
    return s.strip()


NOT_GENUS = {"The", "This", "These", "Look", "See", "On", "In", "At", "Go", "Near", "Further", "Also", "Just", "Some",
             "Many", "Here", "There", "Note", "Today", "Walk", "Enjoy", "Continue", "Turn", "Return", "Rock", "Main",
             "Section", "Sections", "Visitor", "Please", "Friends", "Gardens", "Australian", "National", "Botanic",
             "Click", "IFTW", "Welcome", "Spring", "Summer", "Autumn", "Winter", "Happy", "Merry", "Christmas", "New",
             "Easter", "Guided", "Plants", "Flowers", "Flower", "Week", "Map", "Sydney", "Canberra", "Great", "Top",
             "Red", "White", "Yellow", "Pink", "Blue", "Purple", "Orange", "Green", "Please", "NB", "Note", "Tuesday",
             "Monday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "Photo", "Photos", "Rainforest",
             "Eucalypt", "Eucalypts", "Banksias", "Grevilleas", "Wattles", "Orchids", "Daisies", "Heath", "Beware"}


KNOWN_GENERA = set()


def split_concat(name):
    t = name.split(" ")
    g = t[0]
    if g not in KNOWN_GENERA and re.fullmatch(r"[A-Z][a-z]+", g):
        for n in range(len(g) - 2, 3, -1):
            if g[:n] in KNOWN_GENERA:
                return " ".join([g[:n], g[n:]] + t[1:])
    return name


def parse_name(name, last_genus_by_initial):
    """Return dict(genus, species_key, taxon_key, cultivar, infra, note) or None if not a plant name."""
    s = split_concat(name)
    note = None
    m = re.search(r"\(([^)]*)\)", s)
    if m:
        note = m.group(1).strip()
        s = (s[:m.start()] + s[m.end():]).strip()
    s = re.sub(r"\s+", " ", s).strip(" ,.;:")
    toks = s.split(" ")
    if not toks or not toks[0]:
        return None
    g = toks[0]
    # abbreviated genus e.g. "G. sericea"
    if re.fullmatch(r"[A-Z]\.", g):
        full = last_genus_by_initial.get(g[0])
        if not full:
            return None
        toks[0] = g = full
    if g.startswith("×") or g == "×":
        return None
    if not re.fullmatch(r"[A-Z][a-z]+(-[a-z]+)?", g) or g in NOT_GENUS:
        return None
    rest = toks[1:]
    cultivar = None
    cm = re.search(r"'(.+)'|'(.+)$", " ".join(rest))
    if cm:
        cultivar = (cm.group(1) or cm.group(2)).strip()
    epithet = None
    infra = None
    words = [w for w in rest]
    if words and re.fullmatch(r"[a-z][a-z-]+", words[0]) and words[0] not in ("species", "sp", "spp", "sp.", "spp.", "and", "or", "hybrid", "hybrids", "cultivar", "cultivars", "form"):
        epithet = words[0]
    elif words and words[0] == "×" and len(words) > 1 and re.fullmatch(r"[a-z][a-z-]+", words[1]):
        epithet = "× " + words[1]
    if epithet:
        for j, w in enumerate(words):
            if w in ("subsp.", "var.", "f.") and j + 1 < len(words) and re.fullmatch(r"[a-z][a-z-]+", words[j + 1]):
                infra = f"{w} {words[j + 1]}"
                break
        hyb = re.search(r"× ([A-Z]?[a-z.]*\s?[a-z-]+)", " ".join(words[1:]))
        if hyb and not epithet.startswith("×"):
            epithet = f"{epithet} × {hyb.group(1).strip()}"
    if epithet:
        species_key = f"{g} {epithet}"
    elif cultivar:
        species_key = f"{g} '{cultivar}'"
    else:
        species_key = f"{g} sp."
    taxon_key = species_key
    if infra and epithet:
        taxon_key += " " + infra
    if cultivar and epithet:
        taxon_key += f" '{cultivar}'"
    return dict(genus=g, epithet=epithet, species_key=species_key, taxon_key=taxon_key, cultivar=cultivar,
                infra=infra, note=note)


COLOURS = ["red", "scarlet", "crimson", "pink", "rose", "magenta", "orange", "apricot", "yellow", "gold", "golden",
           "lemon", "cream", "white", "green", "lime", "blue", "mauve", "purple", "violet", "lilac", "lavender",
           "maroon", "burgundy", "brown", "bronze", "apricot"]
COLOUR_NORM = {"scarlet": "red", "crimson": "red", "rose": "pink", "magenta": "pink", "gold": "yellow",
               "golden": "yellow", "lemon": "yellow", "lime": "green", "violet": "purple", "lilac": "mauve",
               "lavender": "mauve", "maroon": "red", "burgundy": "red", "apricot": "orange", "bronze": "brown"}
STAGE_EARLY = re.compile(r"\b(buds?|budding|first flowers?|just (?:starting|beginning|opening|coming)|starting to (?:flower|bloom|open)|beginning to (?:flower|bloom|open)|about to (?:flower|bloom|open)|early flowers?|opening|first bloom)\b", re.I)
STAGE_LATE = re.compile(r"\b(last (?:few )?flowers?|finishing|fading|still (?:in )?(?:flower|flowering|blooming|has)|remaining flowers|end of (?:its|the) flowering|past (?:its|their) best|spent flowers|almost finished)\b", re.I)
STAGE_PEAK = re.compile(r"\b(covered in|smothered|laden|masses of|mass of|in full (?:flower|bloom)|profusion|peak|ablaze|carpet of)\b", re.I)
FRUIT = re.compile(r"\b(fruits?|fruiting|berries|berry|seed ?pods?|capsules?|cones|drupes?|nuts)\b", re.I)
FLOWERW = re.compile(r"\b(flower\w*|bloom\w*|blossom\w*|petals?|bells?|spikes?|heads?|catkins?|daisies|daisy|brushes|bottlebrush\w*|spider|pompoms?|balls?|stars?|tubular|candles?)\b", re.I)
WEATHER = {"frost": r"\bfrost", "rain": r"\brain", "drought": r"\bdrought", "dry": r"\bdry\b|\bdry (?:spell|weather|conditions)",
           "heat": r"\bheat(?:wave)?\b|\bhot\b", "cold": r"\bcold\b|\bchilly\b", "snow": r"\bsnow", "wind": r"\bwind(?:y|s)?\b",
           "storm": r"\bstorm", "warm": r"\bwarm", "hail": r"\bhail\b", "smoke/fire": r"\bbushfires?\b|\bsmoke\b"}
FAUNA = ["honeyeater", "spinebill", "wattlebird", "wren", "robin", "rosella", "gang-gang", "cockatoo", "currawong",
         "bower", "thornbill", "pardalote", "whistler", "lyrebird", "frog", "lizard", "dragon", "skink", "wallaby",
         "butterfl", "bee", "beetle", "moth", "possum", "kookaburra", "magpie", "parrot", "lorikeet", "king-parrot",
         "silvereye", "chough", "friarbird", "bird"]


def extract(f):
    raw = open(os.path.join(RAW, f), "rb").read().decode("cp1252", errors="replace")
    p = Flat()
    p.feed(raw)
    T = "".join(p.chars)
    B, I, C, L = p.b, p.i, p.cap, p.li
    title = re.search(r"(?is)<title>(.*?)</title>", raw)
    title = re.sub(r"\s+", " ", html.unescape(title.group(1))).strip() if title else ""

    # ---- locate body ----
    low = T.lower()
    start = 0
    for mk in ["past issues of", "are in bold type", "refer to garden bed", "refer to garden bed 'sections'",
               "refer to garden bed sections", "news-sheet prepared by", "news sheet prepared by"]:
        k = low.rfind(mk, 0, len(low) // 2 + 3000)
        if k > start:
            start = k + len(mk)
    end = len(T)
    for mk in ["return to:", "previous 'in flower' weeks", "\nhome\n| ", "copyright", "back to top", "updated ",
               "last updated", "view past issues"]:
        k = low.find(mk, start + 200)
        if k != -1 and k < end:
            end = k
    body = T[start:end]

    date = date_from_filename(f)
    heading_date = None
    m = re.search(r"(\d{1,2})(?:\s*(?:-|–|to)\s*\d{1,2})?\s*(?:st|nd|rd|th)?\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s*,?\s*(\d{4})?",
                  T[max(0, start - 400):start + 800], re.I)
    date_range = None
    if m:
        heading_date = m.group(0).strip()
    rm = re.search(r"(\d{1,2})\s*(?:January|February|March|April|May|June|July|August|September|October|November|December)?\s*(?:-|–|to)\s*(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)",
                   T[max(0, start - 400):start + 800], re.I)
    if rm:
        date_range = rm.group(0)

    def run(M, strict):
        # ---- bold spans ----
        spans = []
        k = start
        while k < end:
            if M[k] and T[k].strip():
                j = k
                while j < end and (M[j] or not T[j].strip() and j + 1 < end and M[j + 1]):
                    j += 1
                spans.append([k, j])
                cult = re.match(r"\s?(['‘’`\x91][^'‘’`\x92\n]{2,30}['‘’`\x92])", T[j:j + 40]) if spans else None
                if cult and not M[j]:
                    spans[-1][1] = j + cult.end()
                k = j
            else:
                k += 1
        # merge spans separated by whitespace where the 2nd continues a name (cultivar, rank, form, ×)
        merged = []
        for s in spans:
            if merged:
                gap = T[merged[-1][1]:s[0]]
                nxt = T[s[0]:s[1]].strip()
                if len(gap) <= 3 and not gap.strip() and re.match(r"^(['‘’`\x91(×]|subsp|ssp|var\b|f\.|[a-z])", nxt):
                    merged[-1][1] = s[1]
                    continue
            merged.append(s)

        plants, captions, seen_first = [], [], {}
        genus_by_initial = {}
        candidates = []
        for a, bnd in merged:
            text = T[a:bnd]
            in_cap = sum(C[a:bnd]) > (bnd - a) / 2
            has_ital = any(I[a:bnd])
            after = T[bnd:bnd + 60]
            sect = re.match(r"\s*[,.]?\s*\[\s*S\w*ctions?\s*([^\]]*)\]", after, re.I)
            name = clean_name(text)
            if not name or len(name) > 90 or len(name) < 4:
                continue
            candidates.append((a, bnd, name, in_cap, has_ital, sect))

        # pass 1: learn genera from strong candidates (italic or followed by section)
        genera = set()
        for a, bnd, name, in_cap, ital, sect in candidates:
            tok = name.split(" ")[0]
            if (ital or sect) and re.fullmatch(r"[A-Z][a-z]+", tok) and tok not in NOT_GENUS:
                genera.add(tok)

        starts = sorted(c[0] for c in candidates)
        for a, bnd, name, in_cap, ital, sect in candidates:
            nxt_bold = next((x for x in starts if x > a), end)
            tok = name.split(" ")[0]
            if not (ital or sect or tok in genera or re.fullmatch(r"[A-Z]\.", tok)) or (strict and not (sect or tok in KNOWN_GENERA)):
                continue
            parsed = parse_name(name, genus_by_initial)
            if not parsed:
                continue
            genus_by_initial[parsed["genus"][0]] = parsed["genus"]
            if in_cap:
                captions.append(name)
                continue
            sections = []
            if sect:
                sections = re.findall(r"\d+[A-Za-z]?", sect.group(1))
            # context sentence
            s0 = max(T.rfind(". ", start, a), T.rfind("\n", start, a)) + 1
            e0 = bnd
            for m2 in re.finditer(r"[.!?](\s|$)|\n", T[bnd:min(end, bnd + 600)]):
                e0 = bnd + m2.end()
                if T[bnd:e0].count("[") == T[bnd:e0].count("]"):
                    break
            ctx = re.sub(r"\s+", " ", T[s0:e0]).strip()
            post = re.sub(r"\s+", " ", T[bnd:min(e0, nxt_bold)])
            common = None
            cm = re.match(r"\s*(?:\[[^\]]*\])?\s*(?:,|\()\s*(?:or |the |commonly known as |known as |also known as )?((?:[A-Z][\w'’-]+)(?:[ -](?:[A-Z][\w'’-]+|of|the)){0,3})\s*[,)]", post)
            if cm and cm.group(1).split(" ")[0] not in NOT_GENUS | {"Section", "Sections"} and not cm.group(1).startswith(parsed["genus"]):
                common = cm.group(1)
            cm2 = re.search(r"(?:commonly |also )?known as (?:the )?((?:[A-Z][\w'’-]+)(?:[ -](?:[A-Z][\w'’-]+|of|the)){0,3})", ctx)
            if not common and cm2:
                common = cm2.group(1)
            colours = sorted({COLOUR_NORM.get(c, c) for c in COLOURS if re.search(r"\b" + c + r"\b", post, re.I)})
            stage = "early" if STAGE_EARLY.search(post) else "late" if STAGE_LATE.search(post) else "peak" if STAGE_PEAK.search(post) else None
            phase = "flowering"
            if FRUIT.search(post) and not FLOWERW.search(post):
                phase = "fruit/foliage"
            elif re.search(r"\bfoliage\b|\bleaves\b", post, re.I) and not FLOWERW.search(post) and not colours:
                phase = "fruit/foliage"
            plants.append(dict(raw=re.sub(r"\s+", " ", T[a:bnd]).strip(), name=name, **parsed, sections=sections,
                               list_no=L[a] if L[a] else None, italic=ital, common_name=common, colours=colours,
                               stage=stage, phase=phase, context=ctx[:500]))

        return plants, captions

    plants, captions = run(B, False)
    mode = "bold"
    ital_sect, _ = run(I, True)
    if len(plants) < 3:
        p2, c2 = ital_sect, _
        if len(p2) > len(plants):
            plants, captions, mode = p2, c2, "italic-fallback"

    # dedupe exact taxon repeats within brochure (keep first, count)
    uniq = collections.OrderedDict()
    for pl in plants:
        k2 = pl["taxon_key"]
        if k2 in uniq:
            uniq[k2]["mentions"] += 1
            uniq[k2]["sections"] = sorted(set(uniq[k2]["sections"]) | set(pl["sections"]))
        else:
            pl["mentions"] = 1
            uniq[k2] = pl
    plants = list(uniq.values())

    # incidental italic mentions (non-bold binomials)
    incidental = set()
    k = start
    while k < end:
        if I[k] and not B[k]:
            j = k
            while j < end and I[j] and not B[j]:
                j += 1
            nm = clean_name(T[k:j])
            if re.fullmatch(r"[A-Z][a-z]+ [a-z-]+(?: (?:subsp|var)\. [a-z-]+)?", nm) and nm.split()[0] not in NOT_GENUS:
                if nm not in uniq and nm not in captions:
                    incidental.add(nm)
            k = j
        else:
            k += 1

    bl = body.lower()
    weather = sorted(w for w, rx in WEATHER.items() if re.search(rx, bl))
    fauna = sorted({fa.rstrip("-") for fa in FAUNA if fa in bl})
    tail = re.sub(r"\s+", " ", body[-400:]).strip()
    author = None
    am = re.search(r"([A-Z][a-z]+(?: [A-Z]\.?)?(?: [A-Z][a-zA-Z'-]+)+)\s*\.?\s*$", re.sub(r"\s+", " ", body).strip()[-120:])
    if am and not any(w in am.group(1) for w in ["Section", "Garden", "Centre", "Australian", "Road", "Path"]):
        author = am.group(1)
    paras = [re.sub(r"\s+", " ", x).strip() for x in body.split("\n") if len(x.strip()) > 40]
    intro = paras[0][:400] if paras else ""
    words = len(re.findall(r"\w+", body))

    have = {pl["taxon_key"] for pl in plants}
    possible_misses = sorted({pl["name"] for pl in ital_sect if pl["taxon_key"] not in have and pl["sections"]})
    qa_section_refs = len(re.findall(r"\[\s*S\w*ctions?", body, re.I))
    qa_plants_with_section = sum(1 for pl in plants if pl["sections"])
    flags = []
    if possible_misses:
        pass  # landmarks (tree ferns, conifers) are intentionally non-bold; shown separately in the UI
    if mode != "bold":
        flags.append("plants marked in italics not bold (fallback parser used)")
    if len(plants) < 5:
        flags.append("few plants extracted (<5)")
    if not any(pl["sections"] for pl in plants):
        flags.append("no [Section] refs found")
    if heading_date:
        hm = re.search(r"(\d{1,2})\D+?(" + "|".join(MONTHS) + ")", heading_date, re.I)
        if hm:
            hd_m = MONTHS[hm.group(2).lower()]
            if hd_m != date.month and abs(hd_m - date.month) % 11 > 1:
                flags.append(f"heading date '{heading_date}' disagrees with filename")
    return dict(id=f.replace(".html", ""), file=f, url=BASE + f, source="wayback" if f in wayback else "anbg",
                source_url=wayback.get(f, BASE + f), date=date.isoformat(), year=date.year, doy=date.timetuple().tm_yday,
                title=title, heading_date=heading_date, date_range=date_range, author=author, intro=intro, words=words,
                photo_captions=sorted(set(captions) | {clean_name(x) for x in p.img_alts if re.match(r"[A-Z][a-z]+ [a-z'‘]", x) and "click" not in x.lower() and "image" not in x.lower()}), weather_mentions=weather, fauna_mentions=fauna,
                extraction_mode=mode, qa_section_refs=qa_section_refs, qa_plants_with_section=qa_plants_with_section, possible_misses=possible_misses, plants=plants, incidental_mentions=sorted(incidental), n_plants=len(plants), flags=flags)


if __name__ == "__main__":
    import collections as _c
    gc = _c.Counter()
    for f in links:
        if os.path.exists(os.path.join(RAW, f)):
            for pl in extract(f)["plants"]:
                gc[pl["genus"]] += 1
    KNOWN_GENERA.update(g for g, n in gc.items() if n >= 5)
    out = []
    for f in links:
        if not os.path.exists(os.path.join(RAW, f)):
            continue
        try:
            out.append(extract(f))
        except Exception as e:
            print("ERROR", f, e)
            raise
    out.sort(key=lambda r: r["date"])
    for r in out:
        r["series"] = "IFTW"
    json.dump(out, open(os.path.join(ROOT, "data", "extract_iftw.json"), "w"), indent=0, ensure_ascii=False)
    n = sum(r["n_plants"] for r in out)
    print(len(out), "brochures", n, "plant records", len({p['species_key'] for r in out for p in r['plants']}), "species keys")
    print("flagged:", collections.Counter(fl.split("'")[0] for r in out for fl in r["flags"]))
