"""Find one person in AI transcripts of register pages: deterministic, recall-first name matching.

Usage:
  python3 -I scripts/htr_contest/find_person.py match QUERY.json PATH... [--min-tier A|B|C] [--json]
  python3 -I scripts/htr_contest/find_person.py coverage PATH...
  python3 -I scripts/htr_contest/find_person.py eval [--lean] [--write FILE]

PATH is a run record written by transcribe.py or run.py (`*__runN.json`), a bare JSON entry list, or a
folder of them. QUERY.json keys: label, surnames (required), given_names, father, mother, other_names
(each a list of spellings), years ([from, to]), lang (de-pl, ru or hu; default de-pl).
"""
import argparse
import csv
import json
import re
import statistics
import sys
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from normalize import ILLEGIBLE_RE, MAX_ALTERNATIVES, VARIANTS, best, normalize, normalize_number  # noqa: E402

CONTEST = Path(__file__).resolve().parents[2] / "reports" / "htr-contest"
NAME_FIELDS = ("surname", "given_names", "father", "mother")
# The columns a query's surnames are searched in; an unreadable one means the entry was not fully screened.
SCREEN_FIELDS = ("surname", "father", "mother")
NAME_KEYS = ("surnames", "given_names", "father", "mother", "other_names")
QUERY_KEYS = {"label", "years", "lang", *NAME_KEYS}
TIERS = ("A", "B", "C")
RECORD_RE = re.compile(r"__run\d+\.json$")
# Register boilerplate that models copy into name fields; it must never count as a name match.
STOP = {"z", "ze", "domu", "corka", "syn", "wdowa", "wdowiec", "lat", "urodzona", "zona", "geb", "geborene",
        "tochter", "sohn", "des", "der", "die", "und", "witwe", "aus", "urozdennaja", "urozd", "iz", "docz",
        "filia", "filius"}
APOSTROPHES = re.compile(r"['’ʼ]")

# Daitch-Mokotoff Soundex chart (Mokotoff/Sack, as used by JewishGen "Sounds Like").
# pattern: (at start, before a vowel, elsewhere); a list holds both codings of an ambiguous letter.
DM = {
    "a": ("0", "", ""), "ai": ("0", "1", ""), "aj": ("0", "1", ""), "ay": ("0", "1", ""), "au": ("0", "7", ""),
    "b": ("7", "7", "7"), "c": [("5", "5", "5"), ("4", "4", "4")], "ch": [("5", "5", "5"), ("4", "4", "4")],
    "chs": ("5", "54", "54"), "ck": [("5", "5", "5"), ("45", "45", "45")], "cs": ("4", "4", "4"),
    "csz": ("4", "4", "4"), "cz": ("4", "4", "4"), "czs": ("4", "4", "4"), "d": ("3", "3", "3"),
    "drs": ("4", "4", "4"), "drz": ("4", "4", "4"), "ds": ("4", "4", "4"), "dsh": ("4", "4", "4"),
    "dsz": ("4", "4", "4"), "dt": ("3", "3", "3"), "dz": ("4", "4", "4"), "dzh": ("4", "4", "4"),
    "dzs": ("4", "4", "4"), "e": ("0", "", ""), "ei": ("0", "1", ""), "ej": ("0", "1", ""), "ey": ("0", "1", ""),
    "eu": ("1", "1", ""), "f": ("7", "7", "7"), "fb": ("7", "7", "7"), "g": ("5", "5", "5"), "h": ("5", "5", ""),
    "i": ("0", "", ""), "ia": ("1", "", ""), "ie": ("1", "", ""), "io": ("1", "", ""), "iu": ("1", "", ""),
    "j": [("1", "", ""), ("4", "4", "4")], "k": ("5", "5", "5"), "kh": ("5", "5", "5"), "ks": ("5", "54", "54"),
    "l": ("8", "8", "8"), "m": ("6", "6", "6"), "mn": ("66", "66", "66"), "n": ("6", "6", "6"),
    "nm": ("66", "66", "66"), "o": ("0", "", ""), "oi": ("0", "1", ""), "oj": ("0", "1", ""), "oy": ("0", "1", ""),
    "p": ("7", "7", "7"), "pf": ("7", "7", "7"), "ph": ("7", "7", "7"), "q": ("5", "5", "5"), "r": ("9", "9", "9"),
    "rs": [("94", "94", "94"), ("4", "4", "4")], "rz": [("94", "94", "94"), ("4", "4", "4")],
    "s": ("4", "4", "4"), "sch": ("4", "4", "4"), "schd": ("2", "43", "43"), "scht": ("2", "43", "43"),
    "schtch": ("2", "4", "4"), "schtsch": ("2", "4", "4"), "schtsh": ("2", "4", "4"), "sd": ("2", "43", "43"),
    "sh": ("4", "4", "4"), "shch": ("2", "4", "4"), "shd": ("2", "43", "43"), "sht": ("2", "43", "43"),
    "shtch": ("2", "4", "4"), "shtsh": ("2", "4", "4"), "st": ("2", "43", "43"), "stch": ("2", "4", "4"),
    "strs": ("2", "4", "4"), "strz": ("2", "4", "4"), "stsch": ("2", "4", "4"), "stsh": ("2", "4", "4"),
    "sz": ("4", "4", "4"), "szcs": ("2", "4", "4"), "szcz": ("2", "4", "4"), "szd": ("2", "43", "43"),
    "szt": ("2", "43", "43"), "t": ("3", "3", "3"), "tc": ("4", "4", "4"), "tch": ("4", "4", "4"),
    "th": ("3", "3", "3"), "trs": ("4", "4", "4"), "trz": ("4", "4", "4"), "ts": ("4", "4", "4"),
    "tsch": ("4", "4", "4"), "tsh": ("4", "4", "4"), "tsz": ("4", "4", "4"), "ttch": ("4", "4", "4"),
    "tts": ("4", "4", "4"), "ttsch": ("4", "4", "4"), "ttsz": ("4", "4", "4"), "ttz": ("4", "4", "4"),
    "tz": ("4", "4", "4"), "tzs": ("4", "4", "4"), "u": ("0", "", ""), "ue": ("0", "", ""), "ui": ("0", "1", ""),
    "uj": ("0", "1", ""), "uy": ("0", "1", ""), "v": ("7", "7", "7"), "w": ("7", "7", "7"),
    "x": ("5", "54", "54"), "y": ("1", "", ""), "z": ("4", "4", "4"), "zd": ("2", "43", "43"),
    "zdz": ("2", "4", "4"), "zdzh": ("2", "4", "4"), "zh": ("4", "4", "4"), "zhd": ("2", "43", "43"),
    "zhdzh": ("2", "4", "4"), "zs": ("4", "4", "4"), "zsch": ("4", "4", "4"), "zsh": ("4", "4", "4"),
}
DM_LONGEST = max(map(len, DM))
# Codes with fewer significant digits (Katz = 54) collide with too many unrelated names.
DM_MIN_DIGITS = 3
# Yiddish/German spellings as Polish and Russian clerks wrote them (Weiss = Wajs, Leib = Lejb, Stein = Sztajn),
# mapped to one form on both sides of a comparison.
DIPHTHONGS = re.compile(r"ei|ey|ej|ay|ai")
INITIAL_SZ = re.compile(r"^sz(?=[tp])")
# The query is also expanded one-sidedly: mapping both sides can push a misreading out of the edit band
# (query Wegbreit vs read Wejbajt is 2 edits from Wegbrajt, but 3 once Wejbajt becomes Wajbajt).
ORTHOGRAPHY = (("ei", "aj"), ("ei", "ej"), ("ey", "aj"), ("ey", "ej"), ("ay", "aj"), ("oy", "oj"), ("ai", "aj"))
# Polish and Russian case and feminine endings (Sztajnów, Sulkiesówna, Osternowa, Ruchli).
ENDINGS = ("ownej", "owny", "owna", "owej", "owa", "ow", "ych", "ich", "ego", "a", "y", "i", "u")
# English-style transliterations a researcher types, and the civil forms clerks wrote (Yitzhak ~ Icek, Tsvi ~ Cwi).
TRANSLITERATION = ((re.compile(r"^y"), "j"), (re.compile(r"^y"), ""), (re.compile(r"kh"), "ch"),
                   (re.compile(r"ts"), "c"), (re.compile(r"(?<=[aeiou])h$"), ""))
# normalize() maps German ck to k, which turns Polish c+k (Icka, Icko) into "ika". The matcher keeps ck:
# Daitch-Mokotoff codes it both ways, so Zucker still meets Cukier.
MATCH_VARIANTS = {lang: [v for v in rules if v != ("ck", "k")] for lang, rules in VARIANTS.items()}


@lru_cache(maxsize=None)
def dm_codes(word: str) -> frozenset:
    w = "".join(c for c in word if "a" <= c <= "z")
    branches, i = [("", None)], 0
    while i < len(w):
        n = next((n for n in range(min(DM_LONGEST, len(w) - i), 0, -1) if w[i:i + n] in DM), 0)
        if not n:
            i += 1
            continue
        pat, nxt = w[i:i + n], w[i + n:i + n + 1]
        pos = 0 if i == 0 else 1 if nxt and nxt in "aeiouy" else 2
        rules = DM[pat] if isinstance(DM[pat], list) else [DM[pat]]
        # A sound coded like the one before it is coded once (Lippmann = 8766); an uncoded vowel separates them.
        branches = list(dict.fromkeys(
            (code + rep if rep != last or pat in ("mn", "nm") else code, rep)
            for code, last in branches for rep in (r[pos] for r in rules)))
        i += n
    return frozenset((c + "000000")[:6] for c, _ in branches)


def levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def edit_band(n: int) -> int:
    """Edits tolerated for a query word of n letters: one misread letter in a short name, more in long ones."""
    return 1 if n <= 4 else 2 if n <= 8 else 3


def canonical(word: str) -> str:
    return INITIAL_SZ.sub("s", DIPHTHONGS.sub("aj", word.replace("oy", "oj")))


def _plain_match(q, w, band):
    for a, b in ((q, w), (canonical(q), canonical(w))):
        if abs(len(a) - len(b)) <= band and (d := levenshtein(a, b)) <= band:
            return "exact" if d == 0 else f"edit {d}"
    shared = [c for c in dm_codes(q) & dm_codes(w) if len(c.rstrip("0")) >= DM_MIN_DIGITS]
    return f"D-M {min(shared)}" if shared and min(len(q), len(w)) >= 3 else None


@lru_cache(maxsize=None)
def word_match(q: str, w: str):
    """Why query word q matches transcribed word w, or None."""
    band = edit_band(len(q))
    stems = (w[:-len(e)] for e in ENDINGS if w.endswith(e) and len(w) - len(e) >= 3)
    return _plain_match(q, w, band) or next(
        (f"{why}, inflected" for stem in stems if (why := _plain_match(q, stem, band))), None)


def _normalize(text, lang):
    t = normalize(APOSTROPHES.sub("", str(text or "")), "hu")  # "hu" applies no spelling variants
    for old, new in MATCH_VARIANTS[lang]:
        t = t.replace(old, new)
    return t


def words(text, lang, stop=True):
    return [w for w in _normalize(text, lang).split()
            if not (stop and w in STOP) and not w.isdigit() and len(w) > 1]


def fragments(text, lang):
    """Letters a reader wrote next to [illegible]: ("prefix", "sul") for "Sul[illegible]", ("suffix", "kies")
    for "[illegible]kies". A fragment under 3 letters could fit too many names to count."""
    parts, out = ILLEGIBLE_RE.split(str(text or "")), []
    for i, part in enumerate(parts):
        if i < len(parts) - 1 and part and not part[-1].isspace():
            out += [("prefix", w[-1]) for w in [words(part.split()[-1], lang)] if w]
        if i > 0 and part and not part[0].isspace():
            out += [("suffix", w[0]) for w in [words(part.split()[0], lang)] if w]
    return [(kind, f) for kind, f in out if len(f) >= 3]


def _fragment_fits(kind, frag, q):
    fits = str.startswith if kind == "prefix" else str.endswith
    return fits(q, frag) or fits(canonical(q), canonical(frag))


def _tagged_readings(value):
    """(text, is_alternative) for the best reading and up to 3 alternatives: much of the recall is in the alternatives."""
    if isinstance(value, dict):
        alts = [a for a in value.get("alternatives") or [] if isinstance(a, str) and a][:MAX_ALTERNATIVES]
        return [(value.get("best"), False)] + [(a, True) for a in alts]
    return [(value, False)] if value else []


def validate_query(q, where="query"):
    """The query as given, or ValueError naming what is wrong."""
    if not isinstance(q, dict):
        raise ValueError(f"{where}: must be a JSON object")
    unknown = set(q) - QUERY_KEYS
    if unknown:
        raise ValueError(f"{where}: unknown keys {sorted(unknown)}; allowed: {sorted(QUERY_KEYS)}")
    for k in NAME_KEYS:
        v = q.get(k, [])
        if not isinstance(v, list) or not all(isinstance(s, str) for s in v):
            raise ValueError(f"{where}: '{k}' must be a list of spellings")
    if not any(s.strip() for s in q.get("surnames", [])):
        raise ValueError(f"{where}: 'surnames' must list at least one spelling")
    years = q.get("years")
    if years is not None and not (isinstance(years, list) and len(years) == 2
                                  and all(isinstance(y, int) for y in years) and years[0] <= years[1]):
        raise ValueError(f"{where}: 'years' must be [from, to]")
    if q.get("lang", "de-pl") not in VARIANTS:
        raise ValueError(f"{where}: 'lang' must be one of {sorted(VARIANTS)}")
    return q


def spellings(word):
    out = {word}
    for old, new in ORTHOGRAPHY:
        out |= {w.replace(old, new) for w in out}
    for pattern, new in TRANSLITERATION:
        out |= {v for w in out if len(v := pattern.sub(new, w)) > 1}
    return out


def compile_query(q):
    lang = q.get("lang", "de-pl")
    # Query words skip the boilerplate list: a researcher's "Nata" is a name, not register text.
    parts = {k: sorted({v for s in q.get(k, []) for w in words(s, lang, stop=False) for v in spellings(w)})
             for k in NAME_KEYS}
    for k in (k for k in NAME_KEYS if any(s.strip() for s in q.get(k, [])) and not parts[k]):
        print(f"warning: query '{k}' {q[k]} has no searchable word; it is ignored", file=sys.stderr)
    return lang, parts, q.get("years")


def _closeness(why):
    return 0 if why.startswith("exact") else int(m.group(1)) if (m := re.match(r"edit (\d+)", why)) else 9


def _hits(qwords, entry, fields, lang):
    out, seen = [], set()
    for f in fields:
        for text, is_alt in _tagged_readings(entry.get(f)):
            alt = ", alternative" if is_alt else ""
            for w in words(text, lang):
                found = [(why, qw) for qw in qwords if (why := word_match(qw, w))]
                if found and (f, w) not in seen:
                    seen.add((f, w))
                    why, qw = min(found, key=lambda t: _closeness(t[0]))
                    out.append(f"{f} {w}~{qw} ({why}{alt})")
            for kind, frag in fragments(text, lang):
                shown = f"{frag}[…]" if kind == "prefix" else f"[…]{frag}"
                qw = next((qw for qw in qwords if _fragment_fits(kind, frag, qw)), None)
                if qw and (f, shown) not in seen:
                    seen.add((f, shown))
                    out.append(f"{f} {shown}~{qw} (partial{alt})")
    return out


def unscreened(entry, lang):
    """Why a no-hit cannot rule the entry out: no usable surname, father or mother word, or one partly [illegible]."""
    readings = [t for f in SCREEN_FIELDS for t, _ in _tagged_readings(entry.get(f))]
    if not any(words(t, lang) for t in readings):
        return "unreadable"
    if any(ILLEGIBLE_RE.search(str(t or "")) for t in readings):
        return "partly unreadable"
    return None


def foreign_script(entry, lang):
    """True when a name is in a script normalize() does not romanize (Hebrew), so a Latin query cannot meet it."""
    return any(not ("a" <= c <= "z") for f in NAME_FIELDS for t, _ in _tagged_readings(entry.get(f))
               for w in words(t, lang, stop=False) for c in w if c.isalpha())


def judge(entry, compiled):
    """(tier, matched words, notes). A = surname plus another name; B = surname alone, or two other names; C = one."""
    lang, p, years = compiled
    # The child's own given-name field is left out: a surname must not match a child's first name.
    s = _hits(p["surnames"], entry, SCREEN_FIELDS, lang)
    s_elsewhere = [] if s else _hits(p["surnames"], entry, ("other_columns",), lang)
    others = [h for h in (_hits(p["given_names"], entry, ("given_names",), lang),
                          _hits(p["father"], entry, ("father",), lang),
                          _hits(p["mother"], entry, ("mother",), lang),
                          _hits(p["other_names"], entry, NAME_FIELDS + ("other_columns",), lang)) if h]
    tier = "A" if s and others else "B" if s or s_elsewhere or len(others) >= 2 else "C" if others else None
    notes = ["surname only in other columns (witness, godparent?)"] if s_elsewhere else []
    unread = unscreened(entry, lang)
    if tier == "C" and unread:
        tier = "B"
        notes.append("surname unreadable" if unread == "unreadable" else "surname, father or mother partly unreadable")
    year = re.match(r"(\d{4})", str(best(entry.get("date_iso")) or ""))
    if tier and years and year and not years[0] - 2 <= int(year.group(1)) <= years[1] + 2:
        # A only drops to B, which match() still lists: late registrations put old births in a later year's
        # book, and readers misread years.
        tier = "B" if tier == "A" else tier
        notes.append(f"date {year.group(1)} outside {years[0]}-{years[1]}")
    return tier, s + s_elsewhere + [h for hs in others for h in hs], notes


def load_pages(paths):
    """{page id: [(reader, status, entries)]}; several readers of one page are pooled, so a hit in any counts."""
    pages, files = defaultdict(list), []
    for p in map(Path, paths):
        # Only run records: a tools-mode .workdir may hold JSON files the model wrote itself.
        files += sorted(f for f in p.rglob("*__run*.json") if RECORD_RE.search(f.name)
                        and not any(part.endswith(".workdir") for part in f.parts)) if p.is_dir() else [p]
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(data, list):
            pages[f.stem].append(("?", "ok", data))
        elif isinstance(data, dict) and "entries" in data:
            pages[data.get("image_id", f.parent.name)].append(
                (data.get("contestant", "?"), data.get("status", "ok"), data["entries"]))
    return pages


def match(pages, compiled, min_tier="B"):
    found = []
    for page, reads in sorted(pages.items()):
        for reader, status, entries in reads:
            for line, e in enumerate(entries if status == "ok" else [], 1):
                tier, why, notes = judge(e, compiled)
                if tier and TIERS.index(tier) <= TIERS.index(min_tier):
                    found.append({"tier": tier, "page": page,
                                  "register_no": best(e.get("register_no")) or f"line {line}",
                                  "reader": reader, "why": why, "notes": notes,
                                  "readings": {f: best(e.get(f)) for f in NAME_FIELDS + ("date_iso",)}})
    return sorted(found, key=lambda c: (c["tier"], c["page"], str(c["register_no"])))


def coverage(pages, lang="de-pl"):
    """Lines naming what a no-hit does not cover: failed pages, unreadable entries, thin pages, number gaps."""
    numbers, lines, counts = set(), [], {}
    for page, reads in sorted(pages.items()):
        ok = [r for r in reads if r[1] == "ok"]
        if not ok:
            lines.append(f"- {page}: no successful reading ({', '.join(r[0] for r in reads)}): re-read it")
            continue
        counts[page] = max(len(e) for _, _, e in ok)
        for reader, _, entries in ok:
            for e in entries:
                n = normalize_number(best(e.get("register_no")))
                if n.isdigit():
                    numbers.add(int(n))
                no, unread = best(e.get("register_no")), unscreened(e, lang)
                if unread == "unreadable":
                    lines.append(f"- {page} entry {no} ({reader}): no legible surname, father or mother: "
                                 "read it by eye or re-read the page")
                elif unread:
                    lines.append(f"- {page} entry {no} ({reader}): surname, father or mother partly [illegible]: "
                                 "screened only by its legible letters; check it by eye")
                if foreign_script(e, lang):
                    lines.append(f"- {page} entry {no} ({reader}): names in a script the matcher does not "
                                 "romanize (Hebrew?): not screened; query in that script or read it by eye")
    if counts:
        med = statistics.median(counts.values())
        lines += [f"- {p}: {c} entries vs median {med:g}: entries may be skipped" for p, c in counts.items()
                  if c < med / 2]
    if numbers:
        lo, hi = min(numbers), max(numbers)
        missing = [n for n in range(lo, hi + 1) if n not in numbers]
        lines.append(f"- register numbers {lo}-{hi}; missing: {_ranges(missing) or 'none'} "
                     "(meaningful for act pages only: index pages list numbers out of order)")
    return [f"Pages: {len(pages)} ({len(counts)} read)"] + lines


def _ranges(ns):
    out, start = [], None
    for i, n in enumerate(ns):
        start = n if start is None else start
        if i + 1 == len(ns) or ns[i + 1] != n + 1:
            out.append(str(start) if start == n else f"{start}-{n}")
            start = None
    return ", ".join(out[:40]) + (" ..." if len(out) > 40 else "")


def cmd_match(args):
    try:
        q = validate_query(json.loads(Path(args.query).read_text(encoding="utf-8")), args.query)
    except (ValueError, OSError) as exc:
        sys.exit(str(exc))
    compiled = compile_query(q)
    pages = load_pages(args.paths)
    found = match(pages, compiled, args.min_tier)
    if args.json:
        print(json.dumps({"query": q, "candidates": found, "coverage": coverage(pages, compiled[0])},
                         ensure_ascii=False, indent=1))
        return
    print(f"# Candidates: {q.get('label', args.query)}\n")
    print("| Tier | Page | Entry | Reader | Matched | Best readings | Notes |\n|---|---|---|---|---|---|---|")
    for c in found:
        best_text = "; ".join(f"{k}: {v}" for k, v in c["readings"].items() if v)
        print(f"| {c['tier']} | {c['page']} | {c['register_no']} | {c['reader']} | {'; '.join(c['why'])} | "
              f"{best_text} | {'; '.join(c['notes'])} |")
    print("\n## Coverage\n\n" + "\n".join(coverage(pages, compiled[0])))


def cmd_coverage(args):
    print("\n".join(coverage(load_pages(args.paths))))


# Researcher-style spellings of the contest keys' Latin-script names; Cyrillic keys get an English transliteration.
RESEARCHER_SPELLING = {
    "Zuckerberg": "Cukierberg", "Josef": "Yosef", "Breindel": "Brayndel", "Katz": "Kac", "Chune": "Khuna",
    "Debora": "Dvora", "Tygiel": "Tigel", "Binem": "Bunim", "Zelik": "Selig", "Estera": "Esther",
    "Piper": "Pieper", "Abraham": "Avraham", "Gawryel": "Gavriel", "Dwoyra": "Dvora", "Ita": "Ite",
    "Rząd": "Rzond", "Hersz": "Hirsh", "Lajb": "Leib", "Moszek": "Moshe", "Wegbrajt": "Wegbreit",
    "Mosiek": "Moshe", "Lajzer": "Leizer", "Szmul": "Shmuel", "Bajla": "Beila",
}
ENGLISH = dict(zip("абвгдеёжзиійклмнопрстуфхцчшщъыьѣэюяj",
                   ["a", "b", "v", "g", "d", "e", "yo", "zh", "z", "i", "i", "y", "k", "l", "m", "n", "o", "p",
                    "r", "s", "t", "u", "f", "kh", "ts", "ch", "sh", "shch", "", "y", "", "e", "e", "yu", "ya",
                    "y"]))


def eval_queries(entry, lang, lean=False):
    """Two queries per key person: the index's spelling, and the spelling a researcher would type. Lean queries
    give only the surname and the given name, as when the parents are unknown."""
    surname = entry.get("surname") or " ".join((entry.get("mother") or "").split()[-1:])
    base = {"surnames": [surname], "given_names": [entry.get("given_names", "")],
            "father": [entry.get("father", "")], "mother": [entry.get("mother", "")], "lang": lang}
    if lang == "ru":
        alt = {k: ["".join(ENGLISH.get(c, c) for c in v[0].lower())] for k, v in base.items() if k != "lang"}
        alt["lang"] = "de-pl"
    else:
        alt = {k: [" ".join(RESEARCHER_SPELLING.get(w, w) for w in v[0].split())] for k, v in base.items()
               if k != "lang"}
        alt["lang"] = lang
    # Parents' surnames are searched as the surname, so only their given names stay in the parent keys.
    for q in (base, alt):
        for k in ("father", "mother"):
            q[k] = [" ".join(w for w in q[k][0].split() if w not in q["surnames"][0].split())] if not lean else []
    return [base, alt]


def scan_recall(fields_csv, keys, page_types, lean=False):
    """Per contestant and record type: share of key people a scan flags (tier A/B, and A only), and decoy hits."""
    key_names, preds = defaultdict(dict), defaultdict(lambda: defaultdict(dict))
    with open(fields_csv, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["key_set"] != "adjudicated" or r["field"] not in NAME_FIELDS or r["contestant"].startswith("vote"):
                continue
            ent = (r["image_id"], r["register_no"])
            key_names[ent][r["field"]] = r["key_value"]
            alts = [a for a in r["alternatives"].split(" | ") if a]
            preds[(r["contestant"], r["run"])][ent][r["field"]] = \
                {"best": r["best"], "alternatives": alts} if alts else (r["best"] or None)
    queries = {ent: [compile_query(q) for q in eval_queries(k, keys[ent[0]]["lang"], lean)]
               for ent, k in key_names.items()}
    rows = []
    for contestant in sorted({c for c, _ in preds}):
        stats = defaultdict(lambda: {"any": [], "strong": [], "false": []})
        for run in ("1", "2"):
            entries = preds.get((contestant, run))
            if entries is None:
                continue
            for ent, qs in queries.items():
                for compiled in qs:
                    tier = judge(entries.get(ent, {}), compiled)[0]
                    s = stats[page_types[ent[0]]]
                    s["any"].append(tier in ("A", "B"))
                    s["strong"].append(tier == "A")
                    s["false"].append(sum(judge(e, compiled)[0] in ("A", "B") for e2, e in entries.items() if e2 != ent))
        for pt, s in sorted(stats.items()):
            rows.append({"contestant": contestant, "page_type": pt, "queries": len(s["any"]),
                         "scan_recall_any": round(statistics.mean(s["any"]), 3),
                         "scan_recall_strong": round(statistics.mean(s["strong"]), 3),
                         "false_hits_per_query": round(statistics.mean(s["false"]), 2),
                         "decoys_per_query": len(key_names) - 1})
    return rows


def cmd_eval(args):
    """Replay every answer-key person as a query over the contest's transcriptions (scores/fields.csv)."""
    page_types = {r["image_id"]: r["page_type"] for r in
                  json.loads((CONTEST / "scores" / "model-performance.json").read_text())["rows"]}
    keys = {k["image_id"]: k for k in (json.loads(p.read_text()) for p in (CONTEST / "key").glob("*.json"))}
    rows = scan_recall(CONTEST / "scores" / "fields.csv", keys, page_types, args.lean)
    for r in rows:
        print(f"{r['page_type']:18} {r['contestant']:22} recall any={r['scan_recall_any']:.2f} "
              f"strong={r['scan_recall_strong']:.2f} false={r['false_hits_per_query']:.2f}/{r['decoys_per_query']} "
              f"(n={r['queries']})")
    if args.write:
        Path(args.write).write_text(json.dumps(rows, ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("match")
    m.add_argument("query")
    m.add_argument("paths", nargs="+")
    m.add_argument("--min-tier", choices=TIERS, default="B")
    m.add_argument("--json", action="store_true")
    sub.add_parser("coverage").add_argument("paths", nargs="+")
    e = sub.add_parser("eval")
    e.add_argument("--lean", action="store_true", help="query surname and given name only, no parents")
    e.add_argument("--write")
    args = ap.parse_args()
    {"match": cmd_match, "coverage": cmd_coverage, "eval": cmd_eval}[args.cmd](args)


if __name__ == "__main__":
    main()
