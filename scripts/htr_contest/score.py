"""Match model entries to answer-key entries and score them field by field."""
import json
from dataclasses import dataclass

from normalize import best, is_uncertain, normalize, normalize_number, readings

NAME_FIELDS = ("surname", "given_names", "father", "mother")
NUMBER_FIELDS = ("register_no", "house_no")
SCORED_FIELDS = NAME_FIELDS + NUMBER_FIELDS + ("date_iso", "place")
CONFIDENT_WRONG_PENALTY = 0.25
RESCUED_POINTS = 0.5
FALLBACK_MATCH_THRESHOLD = 0.6
MATCH_MODES = ("register_no", "names")
REQUIRED_KEY_FIELDS = ("image_id", "image", "lang", "source", "entries")


@dataclass
class FieldResult:
    register_no: str
    field: str
    key_value: str
    pred_value: str | None
    base: float
    points: float
    weight: int
    uncertain: bool
    rescued: bool


@dataclass
class RunScore:
    score: float
    fields: list
    extras: int
    hedge_rate: float
    rescue_rate: float


def load_key(path) -> dict:
    with open(path, encoding="utf-8") as f:
        key = json.load(f)
    missing = [k for k in REQUIRED_KEY_FIELDS if k not in key]
    if missing:
        raise ValueError(f"{path}: key missing {missing}")
    if key["lang"] not in ("de-pl", "ru", "hu"):
        raise ValueError(f"{path}: unknown lang {key['lang']!r}")
    if "match_on" in key and key["match_on"] not in MATCH_MODES:
        raise ValueError(f"{path}: match_on must be one of {MATCH_MODES}, got {key['match_on']!r}")
    # Flags and matching treat register_no as an entry's identity within one image.
    numbers = [str(e["register_no"]).strip() for e in key["entries"] if str(e.get("register_no") or "").strip()]
    dupes = sorted({n for n in numbers if numbers.count(n) > 1})
    if dupes:
        raise ValueError(f"{path}: duplicate register_no {dupes}")
    return key


def _levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _name_similarity(pred, key, lang) -> float:
    # Registers add words the index omits (father "Leib" vs "Leib Mendel Nussenbaum", "Tochter des ..."),
    # so score how well each key word is found in the prediction; extra or reordered words are free.
    k, p = normalize(key, lang).split(), normalize(pred, lang).split()
    if not k:
        return 1.0 if not p else 0.0
    if not p:
        return 0.0
    return sum(max(1 - min(_levenshtein(w, kw) / len(kw), 1) for w in p) for kw in k) / len(k)


def _date_part_matches(pred_part, key_part) -> bool:
    if key_part.upper() in ("X", "XX"):
        return True
    if key_part.isdigit() and pred_part.isdigit():
        return int(key_part) == int(pred_part)
    return key_part == pred_part


def _date_matches(pred, key) -> bool:
    p, k = str(pred or "").replace(" ", "").split("-"), str(key).replace(" ", "").split("-")
    return len(p) >= len(k) and all(_date_part_matches(pp, kp) for kp, pp in zip(k, p))


def field_value(field, value, lang) -> str:
    value = best(value)
    if field in NUMBER_FIELDS:
        return normalize_number(value)
    if field == "date_iso":
        # A date with no digits ("?", "unknown") says nothing, like an illegible name.
        text = str(value or "").strip()
        return text if any(c.isdigit() for c in text) else ""
    return normalize(value, lang)


def keyed(entry, field, lang) -> bool:
    """True when the key entry gives this field a value that can be compared."""
    return bool(field_value(field, entry.get(field), lang))


def field_matches(field, pred, key_value, lang) -> float:
    """Credit for one plain predicted value against the key's value; 1.0 is full credit."""
    if pred in (None, ""):
        return 0.0
    if field in NAME_FIELDS:
        return _name_similarity(pred, key_value, lang)
    if field == "date_iso":
        return float(_date_matches(pred, key_value))
    return float(field_value(field, pred, lang) == field_value(field, key_value, lang))


def _fallback_score(pred, key, lang):
    """Mean agreement over the identifying fields the key has; None if it has none."""
    parts = []
    for field in ("surname", "given_names"):
        if keyed(key, field, lang):
            parts.append(_name_similarity(best(pred.get(field)), key[field], lang))
    if keyed(key, "date_iso", lang):
        parts.append(float(_date_matches(best(pred.get("date_iso")), key["date_iso"])))
    return sum(parts) / len(parts) if parts else None


def match_entries(preds, key_entries, lang, match_on="register_no"):
    pairs, used = [], set()
    for k in key_entries:
        # On index pages register_no may be a line or an act number depending on the model,
        # so such keys pair by name only.
        hit = None if match_on == "names" else next((i for i, p in enumerate(preds) if i not in used and k.get("register_no")
                    and normalize_number(best(p.get("register_no"))) == normalize_number(k["register_no"])), None)
        if hit is not None:
            used.add(hit)
        pairs.append([k, hit])
    # Best-first over all pairs: key-order greedy lets a misread entry steal a same-surname sibling's line.
    scored = []
    for ki, (k, hit) in enumerate(pairs):
        if hit is None:
            scored += [(sc, ki, i) for i, p in enumerate(preds) if i not in used
                       if (sc := _fallback_score(p, k, lang)) is not None and sc >= FALLBACK_MATCH_THRESHOLD]
    for _, ki, i in sorted(scored, key=lambda t: (-t[0], t[1], t[2])):
        if pairs[ki][1] is None and i not in used:
            used.add(i)
            pairs[ki][1] = i
    return [(k, preds[i] if i is not None else None) for k, i in pairs], len(preds) - len(used)


def scored_fields(key):
    return tuple(f for f in SCORED_FIELDS if not (f == "register_no" and key.get("match_on") == "names"))


def match_entries_for_key(preds, key):
    return match_entries(preds, key["entries"], key["lang"], key.get("match_on", "register_no"))


def score_run(preds, key) -> RunScore:
    lang, results = key["lang"], []
    pairs, extras = match_entries_for_key(preds, key)
    for k, p in pairs:
        for field in scored_fields(key):
            if not keyed(k, field, lang):
                continue
            pred = (p or {}).get(field)
            uncertain = is_uncertain(pred)
            base = field_matches(field, best(pred), k[field], lang)
            rescued = base < 1 and any(field_matches(field, alt, k[field], lang) >= 1 for alt in readings(pred)[1:])
            if best(pred) in (None, ""):
                points = 0.0
            elif base >= 1:
                points = base
            elif rescued:
                points = max(base, RESCUED_POINTS)
            elif uncertain:
                points = base
            else:
                points = base - CONFIDENT_WRONG_PENALTY
            results.append(FieldResult(str(k.get("register_no", "")), field, k[field], pred, base, points,
                                       2 if field in NAME_FIELDS else 1, uncertain, rescued))
    max_points = sum(r.weight for r in results)
    score = sum(r.points * r.weight for r in results) / max_points if max_points else 0.0
    answered = [r for r in results if best(r.pred_value) not in (None, "")]
    hedge = sum(r.uncertain for r in answered) / len(answered) if answered else 0.0
    wrong_hedged = [r for r in answered if r.base < 1 and r.uncertain]
    rescue = sum(r.rescued for r in wrong_hedged) / len(wrong_hedged) if wrong_hedged else 0.0
    return RunScore(score, results, extras, hedge, rescue)
