"""Pull the entry list out of a model's free-form reply."""
import json
import re


class ParseError(Exception):
    pass


_DECODER = json.JSONDecoder()
FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def _as_entries(data):
    if isinstance(data, dict) and isinstance(data.get("entries"), list):
        data = data["entries"]
    if isinstance(data, list) and all(isinstance(e, dict) for e in data):
        return data
    return None


def _first_entries(text: str):
    # Decode at every opener rather than slicing first-to-last bracket: prose such
    # as "[illegible]" before or after the JSON would otherwise corrupt the slice.
    for i, ch in enumerate(text):
        if ch not in "[{":
            continue
        try:
            data, _ = _DECODER.raw_decode(text, i)
        except json.JSONDecodeError:
            continue
        entries = _as_entries(data)
        # An empty list anywhere else (e.g. "alternatives": [] in a cut-off reply) is not an answer.
        if entries:
            return entries
    return None


def _is_empty_answer(text: str) -> bool:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return False
    return data == [] or data == {"entries": []}


def extract_entries(raw: str) -> list[dict]:
    if not raw or not raw.strip():
        raise ParseError("empty output")
    fenced = FENCE_RE.findall(raw)
    for text in [*fenced, raw]:
        entries = _first_entries(text)
        if entries is not None:
            return entries
    only_fence = len(fenced) == 1 and not FENCE_RE.sub("", raw).strip()
    if _is_empty_answer((fenced[0] if only_fence else raw).strip()):
        return []
    raise ParseError("no JSON entry list found")
