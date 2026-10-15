import json
import pytest
from score import load_key, match_entries, score_run

KEY = {"image_id": "t", "image": "x.jpg", "lang": "de-pl", "source": {"index": "JRI-Poland"},
       "entries": [{"register_no": "6", "surname": "Ostern", "given_names": "Dawid", "father": "Leib",
                    "date_iso": "1894-01-15"},
                   {"register_no": "7", "surname": "Stein", "given_names": "Feige"}]}

def test_perfect_run_scores_one():
    assert score_run(KEY["entries"], KEY).score == pytest.approx(1.0)

def test_zero_entries_scores_zero():
    result = score_run([], KEY)
    assert result.score == 0 and result.extras == 0

def test_extra_father_tokens_get_full_credit():
    preds = [dict(KEY["entries"][0], father="Leib Nussenbaum"), KEY["entries"][1]]
    assert score_run(preds, KEY).score == pytest.approx(1.0)

def _date_points(value):
    run = score_run([dict(KEY["entries"][0], date_iso=value), KEY["entries"][1]], KEY)
    return next(f for f in run.fields if f.field == "date_iso"), run

def test_possible_readings_points():
    rescued, run = _date_points({"best": "1894-02-15", "alternatives": ["1894-01-15"], "reason": "faded"})
    hedged, _ = _date_points({"best": "1894-02-15", "alternatives": ["1894-03-15"]})
    confident, _ = _date_points("1894-02-15")
    assert (rescued.points, hedged.points, confident.points) == (0.5, 0.0, -0.25)
    assert rescued.rescued and run.rescue_rate == 1.0

def test_only_three_alternatives_count():
    capped, _ = _date_points({"best": "1894-02-15",
                              "alternatives": ["1894-03-15", "1894-04-15", "1894-05-15", "1894-01-15"]})
    assert capped.points == 0.0 and not capped.rescued

def test_correct_best_with_alternatives_scores_full():
    field, run = _date_points({"best": "1894-01-15", "alternatives": ["1894-07-15"]})
    assert field.points == 1.0 and run.hedge_rate > 0

def test_match_falls_back_to_surname_when_register_missing():
    pairs, extras = match_entries([{"surname": "Stein", "given_names": "Feige"}], KEY["entries"], "de-pl")
    assert pairs[1][1] is not None and pairs[0][1] is None and extras == 0

def test_unmatched_predictions_count_as_extras():
    preds = KEY["entries"] + [{"register_no": "99", "surname": "Kohn"}]
    assert score_run(preds, KEY).extras == 1

def test_partial_date_key_compares_known_parts():
    key = dict(KEY, entries=[{"register_no": "6", "date_iso": "1894"}])
    assert score_run([{"register_no": "6", "date_iso": "1894-03-02"}], key).score == pytest.approx(1.0)

def test_load_key_rejects_missing_fields(tmp_path):
    p = tmp_path / "k.json"
    p.write_text(json.dumps({"image_id": "t", "entries": []}))
    with pytest.raises(ValueError):
        load_key(p)


def _match(key_entry, pred):
    return match_entries([pred], [key_entry], "de-pl")


def test_fallback_rejects_unrelated_surname():
    pairs, extras = _match({"register_no": "6", "surname": "Ostern"}, {"surname": "Kohn"})
    assert pairs[0][1] is None and extras == 1


def test_fallback_accepts_near_surname_with_extra_field():
    pairs, extras = _match({"register_no": "6", "surname": "Ostern"},
                           {"surname": "Osterm", "given_names": "Dawid"})
    assert pairs[0][1] is not None and extras == 0


def test_fallback_uses_date_when_key_has_it():
    pairs, _ = _match({"register_no": "6", "surname": "Ostern", "date_iso": "1894-01-15"},
                      {"surname": "Ostern", "date_iso": "1894-01-15"})
    assert pairs[0][1] is not None


def test_fallback_needs_identifying_fields():
    pairs, extras = _match({"register_no": "6", "father": "Leib"}, {"father": "Leib"})
    assert pairs[0][1] is None and extras == 1


def _name_field(key_entry, pred_entry, field):
    key = dict(KEY, entries=[key_entry])
    run = score_run([pred_entry], key)
    return next(f for f in run.fields if f.field == field)


def test_rescue_never_lowers_score():
    k = {"register_no": "6", "surname": "Nussenbaum"}
    good = _name_field(k, {"register_no": "6", "surname": {"best": "Nusenbaum", "alternatives": ["Nussenbaum"]}}, "surname")
    bad = _name_field(k, {"register_no": "6", "surname": {"best": "Nusenbaum", "alternatives": ["Nusbaum"]}}, "surname")
    assert good.points >= bad.points and good.rescued
    assert good.points == pytest.approx(max(good.base, 0.5))


def _father(key, pred):
    return _name_field({"register_no": "6", "father": key}, {"register_no": "6", "father": pred}, "father").base


def test_long_prediction_costs_nothing_extra():
    assert _father("Leib", "Leib Mendel Chaim Nussenbaum") == 1.0
    assert _father("Breindel Zuckerberg", "Breindel Tochter des Lender und der Rachel Zuckerberg") == 1.0


def test_missing_key_word_is_penalised():
    got = _father("Breindel Zuckerberg", "Breindel")
    assert got == pytest.approx(0.5 + 0.5 * _father("Zuckerberg", "Breindel"))
    assert got < 0.75


def test_word_order_ignored():
    assert _father("Hersz Lajb", "Lajb Hersz") == 1.0


def test_partial_word_credit():
    assert _father("Ostern", "Osterm") == pytest.approx(1 - 1 / 6)


def test_date_zero_padding_and_wildcards():
    k = {"register_no": "6", "date_iso": "1894-01-15"}
    assert _name_field(k, {"register_no": "6", "date_iso": " 1894-1-15 "}, "date_iso").base == 1.0
    k2 = {"register_no": "6", "date_iso": "1894-01-15"}
    assert _name_field(k2, {"register_no": "6", "date_iso": "1894-XX-15"}, "date_iso").base == 0.0
    k3 = {"register_no": "6", "date_iso": "1894-01-XX"}
    assert _name_field(k3, {"register_no": "6", "date_iso": "1894-01-15"}, "date_iso").base == 1.0


def test_name_partial_credit():
    f = _name_field({"register_no": "6", "surname": "Ostern"}, {"register_no": "6", "surname": "Osterm"}, "surname")
    assert f.base == pytest.approx(1 - 1 / 6)


@pytest.mark.parametrize("field, pred, key_value, expected", [
    ("father", "Leib Nussenbaum", "Leib", 1.0),
    ("date_iso", "1890-05-12", "1890-05-XX", 1.0),
    ("date_iso", "1890-05-03", "1890-5-3", 1.0),
    ("surname", "Ostern", "Stein", None),
])
def test_field_matches_is_public_comparison(field, pred, key_value, expected):
    from score import field_matches
    got = field_matches(field, pred, key_value, "de-pl")
    assert got == expected if expected is not None else got < 1


def test_key_fields_with_empty_comparison_form_are_skipped():
    key = dict(KEY, entries=[{"register_no": "6", "surname": "Ostern", "father": "?", "date_iso": "?"}])
    fields = {r.field for r in score_run([{"register_no": "6", "surname": "Ostern"}], key).fields}
    assert fields == {"register_no", "surname"}


NAMES_KEY = {"image_id": "t", "image": "x.jpg", "lang": "ru", "source": {"index": "JRI-Poland"}, "match_on": "names",
             "entries": [{"register_no": "2", "surname": "Kowalski", "given_names": "Jan"},
                         {"register_no": "3", "surname": "Nowak", "given_names": "Piotr"},
                         {"register_no": "1", "surname": "Zielinski", "given_names": "Adam"}]}
LINE_PREDS = [{"register_no": "1", "surname": "Kowalski", "given_names": "Jan"},
              {"register_no": "2", "surname": "Nowak", "given_names": "Piotr"},
              {"register_no": "3", "surname": "Zielinski", "given_names": "Adam"}]


def test_names_key_pairs_by_name_ignoring_line_numbers():
    pairs, extras = match_entries(LINE_PREDS, NAMES_KEY["entries"], "ru", match_on="names")
    assert [p["surname"] for _, p in pairs] == ["Kowalski", "Nowak", "Zielinski"] and extras == 0


def test_names_key_full_credit_and_register_no_unscored():
    run = score_run(LINE_PREDS, NAMES_KEY)
    assert run.score == pytest.approx(1.0)
    assert "register_no" not in {r.field for r in run.fields}


def test_default_key_still_pairs_by_register_no_and_scores_it():
    key = {k: v for k, v in NAMES_KEY.items() if k != "match_on"}
    run = score_run(LINE_PREDS, key)
    assert "register_no" in {r.field for r in run.fields}
    assert run.score < 1.0


def test_explicit_register_no_match_on_is_default():
    key = dict(NAMES_KEY, match_on="register_no")
    assert score_run(LINE_PREDS, key).score == score_run(LINE_PREDS, {k: v for k, v in key.items() if k != "match_on"}).score


@pytest.mark.parametrize("bad", ["name", "", None, 3])
def test_load_key_rejects_invalid_match_on(tmp_path, bad):
    p = tmp_path / "k.json"
    p.write_text(json.dumps(dict(NAMES_KEY, match_on=bad)))
    with pytest.raises(ValueError):
        load_key(p)


def test_load_key_accepts_names_and_absent(tmp_path):
    p = tmp_path / "k.json"
    p.write_text(json.dumps(NAMES_KEY))
    assert load_key(p)["match_on"] == "names"


def test_fallback_pairs_best_first_not_in_key_order():
    entries = [{"surname": "Гольдбергъ", "given_names": "Айдель"},
               {"surname": "Гольдбергъ", "given_names": "Айдля"},
               {"surname": "Гольдбергъ", "given_names": "Хава"}]
    preds = [{"surname": "Гольдбергъ", "given_names": "Хава"},
             {"surname": "Гольдбергъ", "given_names": "Айдля"},
             {"surname": "Гольдбергъ", "given_names": "Ыъ"}]
    pairs, _ = match_entries(preds, entries, "ru", match_on="names")
    assert [p["given_names"] if p else None for _, p in pairs][1:] == ["Айдля", "Хава"]
