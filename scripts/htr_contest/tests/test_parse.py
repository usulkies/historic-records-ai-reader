import pytest
from parse import ParseError, extract_entries

E = '[{"register_no": "6", "surname": "Ostern"}]'

@pytest.mark.parametrize("raw", [
    E,
    f"Here is the transcription:\n```json\n{E}\n```\nDone.",
    '{"entries": ' + E + "}",
    f"Sure! {E} Let me know.",
])
def test_extracts_from_common_wrappings(raw):
    assert extract_entries(raw) == [{"register_no": "6", "surname": "Ostern"}]

@pytest.mark.parametrize("raw", ["", "   \n", "I cannot read this image.", '{"note": "x"}'])
def test_failures_raise(raw):
    with pytest.raises(ParseError):
        extract_entries(raw)

def test_empty_list_is_valid():
    assert extract_entries("[]") == []

OSTERN = {"register_no": "6", "surname": "Ostern"}
ILLEGIBLE_VALUE = {"register_no": "6", "surname": "Ostern [illegible]"}

@pytest.mark.parametrize("raw, expected", [
    ("Note: line 3 is [illegible].\n" + E, [OSTERN]),
    (E + "\nSee [notes].", [OSTERN]),
    ('[{"register_no": "6", "surname": "Ostern [illegible]"}]', [ILLEGIBLE_VALUE]),
    ("```text\nnot json [x]\n```\nand\n```json\n" + E + "\n```", [OSTERN]),
])
def test_brackets_in_prose_or_values_do_not_break_parsing(raw, expected):
    assert extract_entries(raw) == expected

CUT_OFF = '[{"surname":{"best":"A","alternatives":[],"reason":"r"}},{"surname":"B'

def test_cut_off_reply_with_inner_empty_list_raises():
    with pytest.raises(ParseError):
        extract_entries(CUT_OFF)

def test_prose_empty_list_before_real_json_returns_entries():
    assert extract_entries("Nothing found yet: [] but here:\n" + E) == [OSTERN]

@pytest.mark.parametrize("raw", ["[]", "  []\n", '{"entries": []}', "```json\n[]\n```"])
def test_whole_reply_empty_list_is_valid(raw):
    assert extract_entries(raw) == []

def test_empty_list_inside_prose_is_not_accepted():
    with pytest.raises(ParseError):
        extract_entries("I could not read it, so [] is my answer.")
