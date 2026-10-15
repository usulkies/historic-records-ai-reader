import csv
import json

import pytest

import find_person as fp
from find_person import compile_query, coverage, dm_codes, judge, load_pages, match, validate_query, word_match

# Published Daitch-Mokotoff codes (Mokotoff/Sack chart examples).
DM_REFERENCE = {"moskowitz": {"645740"}, "peters": {"739400", "734000"}, "auerbach": {"097500", "097400"},
                "lipshitz": {"874400"}, "kleinman": {"586660"}, "topf": {"370000"}, "breuer": {"791900"},
                "augsburg": {"054795"}, "halberstadt": {"587943", "587433"},
                "jackson": {"154600", "454600", "145460", "445460"}}


def q(**kw):
    return compile_query(validate_query(kw))


def test_dm_codes_match_published_chart():
    for word, codes in DM_REFERENCE.items():
        assert dm_codes(word) == codes, word
    assert {c for w in ("sulkes", "szulkes", "sulkies", "zulkes", "shulkes") for c in dm_codes(w)} == {"485400"}
    assert dm_codes(fp.normalize("Шидловеръ", "ru")) & dm_codes(fp.normalize("Shidlover", "de-pl"))


def test_word_match_tolerates_misreadings_not_different_names():
    assert word_match("wajbrajt", "wegbrajt") == "edit 2"
    assert word_match("leib", "lejb") == "edit 1"  # one letter off in a 4-letter name: below 0.8 similarity
    assert word_match("feige", "fania") is None  # a meaning pair: the query must list both
    assert word_match("kac", "herz") is None  # too short a sound code to count
    assert word_match("kac", "kacow") == "exact, inflected"


def test_unehelich_child_found_by_mothers_surname():
    entry = {"register_no": "7", "given_names": "Josef", "mother": "Breindel Zuckerberg"}
    tier, why, _ = judge(entry, q(surnames=["Cukierberg"], given_names=["Yosef"]))
    assert tier == "A" and any(w.startswith("mother zuckerberg") for w in why)


def test_cyrillic_transcript_found_by_english_spelling():
    entry = {"surname": "Шидловеръ", "given_names": "Борухъ Гершъ", "father": "Ицекъ Ноехъ"}
    assert judge(entry, q(surnames=["Shidlover"], given_names=["Borukh"]))[0] == "A"


def test_alternative_readings_are_searched():
    entry = {"surname": {"best": "Wegbrant", "alternatives": ["Wegbrajt"], "reason": "x"}, "given_names": "Mosiek"}
    tier, why, _ = judge(entry, q(surnames=["Wegbreit"], given_names=["Moshe"]))
    assert tier == "A" and any("alternative" in w for w in why)


def test_tiers():
    query = q(surnames=["Piper"], given_names=["Abraham"], father=["Gawryel"], years=[1848, 1848])
    assert judge({"surname": "Pieper", "given_names": "Szmul"}, query)[0] == "B"
    assert judge({"surname": "Rząd", "given_names": "Abraham", "father": "Gawryel"}, query)[0] == "B"
    assert judge({"surname": "Rząd", "given_names": "Abraham"}, query)[0] == "C"
    assert judge({"surname": "Rząd", "given_names": "Mosiek", "other_columns": "witness Piper"}, query)[:3:2] == \
        ("B", ["surname only in other columns (witness, godparent?)"])
    tier, _, notes = judge({"surname": "[illegible]", "given_names": "Abraham"}, query)
    assert tier == "B" and "surname unreadable" in notes
    assert judge({"surname": "Tygiel", "given_names": "Binem"}, query)[0] is None


def test_out_of_range_year_demotes_never_drops():
    query = q(surnames=["Tygiel"], given_names=["Binem"], years=[1848, 1848])
    assert judge({"surname": "Tygiel", "given_names": "Binem", "date_iso": "1834-09-16"}, query)[0] == "B"
    assert judge({"surname": "Tygiel", "given_names": "Binem", "date_iso": "1847-09-16"}, query)[0] == "A"
    assert judge({"surname": "Rząd", "given_names": "Binem", "date_iso": "1834-09-16"}, query)[0] == "C"


def test_out_of_range_surname_hit_is_still_listed_by_default():
    entries = [{"register_no": "3", "surname": "Sulkies", "given_names": "[illegible]", "date_iso": "1875-02-01"},
               {"register_no": "4", "surname": "Sulkies", "given_names": "Chana", "date_iso": "1847-09-16"}]
    found = match({"p": [("r", "ok", entries)]}, q(surnames=["Sulkies"], given_names=["Moshe"], years=[1878, 1880]))
    assert [(c["register_no"], c["tier"]) for c in found] == [("3", "B"), ("4", "B")]
    assert all(any(n.startswith("date ") for n in c["notes"]) for c in found)


@pytest.mark.parametrize("query, written", [("Sztajn", "Stein"), ("Stein", "Sztajn"), ("Wajs", "Weiss"),
                                            ("Weiss", "Wajs"), ("Fajn", "Fein"), ("Fein", "Fajn"),
                                            ("Sztajn", "Steiner"), ("Fajga", "Feige"), ("Stein", "Штейнъ")])
def test_yiddish_diphthongs_match_both_ways(query, written):
    lang = "ru" if written[0] > "z" else "de-pl"
    assert judge({"surname": written}, q(surnames=[query], lang=lang))[0] == "B"


@pytest.mark.parametrize("query, written", [("Stein", "Ruchli z Sztajnów"), ("Kac", "Kaców"),
                                            ("Sulkies", "Sulkiesówna"), ("Ostern", "Osternowa")])
def test_polish_case_endings_are_stripped(query, written):
    tier, why, _ = judge({"surname": "Rząd", "mother": written}, q(surnames=[query, query + "x"]))
    assert tier == "B" and why[0].startswith("mother")


@pytest.mark.parametrize("written", ["Sul[illegible]", "[illegible]kies", "Moszek Sul[illegible]"])
def test_partly_illegible_surname_matches_by_its_letters(written):
    tier, why, _ = judge({"surname": written, "given_names": "Lejb"}, q(surnames=["Sulkies"], given_names=["Moshe"]))
    assert tier == "B" and "partial" in why[0]


def test_partly_illegible_entry_is_never_hidden():
    query = q(surnames=["Sulkies"], given_names=["Moszek"])
    tier, _, notes = judge({"surname": "Su[illegible]es", "given_names": "Moszek"}, query)
    assert tier == "B" and "surname, father or mother partly unreadable" in notes
    assert judge({"surname": "Su[illegible]es", "given_names": "Lejb"}, query)[0] is None


def test_given_name_transliterations_and_civil_forms():
    for typed, written in (("Yitzhak", "Icek"), ("Yitzhak", "Ицекъ"), ("Hannah", "Chana"), ("Tsvi", "Цви"),
                           ("Icek", "Icka"), ("Ze'ev", "Зеевъ"), ("Nata", "Nata")):
        lang = "ru" if written[0] > "z" else "de-pl"
        assert judge({"surname": "Kac", "given_names": written}, q(surnames=["Kac"], given_names=[typed], lang=lang))[0] \
            == "A", (typed, written)


def test_query_key_with_no_searchable_word_warns(capsys):
    assert q(surnames=["Kac"], father=["z"])[1]["father"] == []
    assert "'father'" in capsys.readouterr().err


def test_surname_not_matched_in_childs_given_names():
    assert judge({"surname": "Kac", "given_names": "Wolf"}, q(surnames=["Wolf"]))[0] is None


@pytest.mark.parametrize("bad", [{"surnames": "Sulkies"}, {"surnames": []}, {"surnames": ["X"], "town": "Y"},
                                 {"surnames": ["X"], "years": [1890]}, {"surnames": ["X"], "years": [1891, 1890]},
                                 {"surnames": ["X"], "lang": "yi"}, {"surnames": ["X"], "father": "Leib"}])
def test_query_validation(bad):
    with pytest.raises(ValueError):
        validate_query(bad)


def _record(path, image_id, entries, status="ok", reader="claude-sonnet"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"contestant": reader, "image_id": image_id, "status": status, "entries": entries}))


def test_load_pages_reads_only_run_records(tmp_path):
    _record(tmp_path / "p1" / "claude-sonnet__run1.json", "p1", [{"register_no": "1", "surname": "Piper"}])
    _record(tmp_path / "p1" / "claude-sonnet__run1.workdir" / "x__run1.json", "p1", [{"surname": "Fake"}])
    (tmp_path / "p1" / "claude-sonnet__run1.json.prev-20261011").write_text("[]")
    _record(tmp_path / "p1" / "claude-opus__run1.json", "p1", [{"register_no": "1", "surname": "Pieper"}],
            reader="claude-opus")
    pages = load_pages([tmp_path])
    assert list(pages) == ["p1"] and sorted(r for r, _, _ in pages["p1"]) == ["claude-opus", "claude-sonnet"]
    found = match(pages, q(surnames=["Piper"]))
    assert [(c["tier"], c["reader"]) for c in found] == [("B", "claude-opus"), ("B", "claude-sonnet")]


def test_coverage_names_what_a_no_hit_does_not_cover(tmp_path):
    _record(tmp_path / "p1" / "r__run1.json", "p1", [{"register_no": str(n), "surname": "Kac"} for n in (1, 2, 5, 7, 8, 9)])
    _record(tmp_path / "p2" / "r__run1.json", "p2", [], status="failed")
    _record(tmp_path / "p3" / "r__run1.json", "p3", [{"register_no": "6", "surname": "[illegible]"}])
    text = "\n".join(coverage(load_pages([tmp_path])))
    assert "p2: no successful reading" in text and "missing: 3-4" in text
    assert "p3 entry 6 (claude-sonnet): no legible surname" in text
    assert "p3: 1 entries vs median 3.5" in text


def test_coverage_lists_partly_illegible_and_unromanized_names(tmp_path):
    _record(tmp_path / "p1" / "r__run1.json", "p1", [{"register_no": "1", "surname": "Sul[illegible]"},
                                                      {"register_no": "2", "surname": "זולקעס", "given_names": "משה"},
                                                      {"register_no": "3", "surname": "Kac"}])
    text = "\n".join(coverage(load_pages([tmp_path])))
    assert "entry 1 (claude-sonnet): surname, father or mother partly [illegible]" in text
    assert "entry 2 (claude-sonnet): names in a script the matcher does not romanize" in text
    assert "entry 3" not in text


def test_scan_recall_replays_key_people(tmp_path):
    fields = tmp_path / "fields.csv"
    cols = ["contestant", "run", "image_id", "key_set", "register_no", "field", "key_value", "best", "alternatives"]
    rows = [("m", run, "img", "adjudicated", no, f, key, pred, "")
            for run in ("1", "2") for no, f, key, pred in
            (("1", "surname", "Tygiel", "Tygiel"), ("1", "given_names", "Binem", "Binem"),
             ("2", "surname", "Piper", "Kac"), ("2", "given_names", "Abraham", "Szmul"))]
    with open(fields, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    out = fp.scan_recall(fields, {"img": {"lang": "de-pl"}}, {"img": "polish_narrative"})
    assert out == [{"contestant": "m", "page_type": "polish_narrative", "queries": 8, "scan_recall_any": 0.5,
                    "scan_recall_strong": 0.5, "false_hits_per_query": 0.0, "decoys_per_query": 1}]
