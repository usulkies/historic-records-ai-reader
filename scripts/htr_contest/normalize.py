"""Canonical text forms so transcriptions and index keys compare on content, not orthography."""
import re
import unicodedata

ILLEGIBLE_RE = re.compile(r"\[illegible\]", re.I)
# More alternatives than this are ignored, so listing many guesses can't buy credit.
MAX_ALTERNATIVES = 3

# Polish-style romanization, matching how JRI-Poland indexes Russian-era records.
CYRILLIC = {
    "а": "a", "б": "b", "в": "w", "г": "g", "д": "d", "е": "e", "ё": "jo", "ж": "z",
    "з": "z", "и": "i", "і": "i", "й": "j", "к": "k", "л": "l", "м": "m", "н": "n",
    "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "ch",
    "ц": "c", "ч": "cz", "ш": "sz", "щ": "szcz", "ъ": "", "ы": "y", "ь": "", "ѣ": "e",
    "э": "e", "ю": "ju", "я": "ja", "ѳ": "f", "ѵ": "i",
}

# Ordered; applied to both sides. Hungarian gets none: its sz/cs mean different sounds.
VARIANTS = {
    "de-pl": [("tsch", "cz"), ("sch", "sz"), ("sh", "sz"), ("ck", "k"), ("tz", "c"),
              ("ph", "f"), ("v", "w")],
    "hu": [],
}
VARIANTS["ru"] = VARIANTS["de-pl"]


def best(value):
    return value.get("best") if isinstance(value, dict) else value


def _alternatives(value) -> list:
    if not isinstance(value, dict):
        return []
    return [a for a in value.get("alternatives") or [] if isinstance(a, str) and a][:MAX_ALTERNATIVES]


def readings(value) -> list:
    return [v for v in [best(value), *_alternatives(value)] if v]


def reason(value):
    return value.get("reason") if isinstance(value, dict) else None


def is_uncertain(value) -> bool:
    return bool(_alternatives(value)) or bool(ILLEGIBLE_RE.search(str(best(value) or "")))


def normalize(text, lang: str) -> str:
    if text is None:
        return ""
    t = ILLEGIBLE_RE.sub("", str(text)).lower()
    t = "".join(CYRILLIC.get(ch, ch) for ch in t)
    t = t.replace("ß", "ss").replace("ł", "l")
    t = "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))
    for old, new in VARIANTS[lang]:
        t = t.replace(old, new)
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def normalize_number(text) -> str:
    match = re.search(r"\d+[a-z]?", normalize(text, "hu"))
    return match.group(0) if match else ""
