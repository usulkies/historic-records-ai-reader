"""Majority-vote contestant built from single-model runs, and run-to-run consistency."""
from collections import Counter

from normalize import best
from score import field_value, keyed, match_entries_for_key, scored_fields


def majority(values, field, lang):
    # An illegible marker normalizes to "", so it abstains instead of voting.
    present = [best(v) for v in values if field_value(field, best(v), lang)]
    if not present:
        return None
    counts = Counter(field_value(field, v, lang) for v in present)
    top = counts.most_common(2)
    if len(top) > 1 and top[0][1] == top[1][1]:
        return None
    return next(v for v in present if field_value(field, v, lang) == top[0][0])


def vote(runs, key):
    # Alignment uses the key's entry order only; voted values come from the models alone.
    lang = key["lang"]
    aligned = [match_entries_for_key(run, key)[0] for run in runs]
    voted = []
    for idx in range(len(key["entries"])):
        entry = {}
        for field in scored_fields(key):
            value = majority([(pairs[idx][1] or {}).get(field) for pairs in aligned], field, lang)
            if value is not None:
                entry[field] = value
        voted.append(entry)
    return voted


def consistency(run_a, run_b, key) -> float:
    lang = key["lang"]
    a, _ = match_entries_for_key(run_a, key)
    b, _ = match_entries_for_key(run_b, key)
    same = total = 0
    for (k, pa), (_, pb) in zip(a, b):
        for field in scored_fields(key):
            if not keyed(k, field, lang):
                continue
            total += 1
            same += field_value(field, (pa or {}).get(field), lang) == field_value(field, (pb or {}).get(field), lang)
    return same / total if total else 0.0
