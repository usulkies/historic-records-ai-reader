from vote import consistency, majority, vote

KEY = {"lang": "de-pl", "entries": [{"register_no": "6", "surname": "Ostern"}]}


def test_majority_and_tie():
    assert majority(["Ostern", {"best": "Ostern", "alternatives": ["Osten"]}, "Osten"], "surname", "de-pl") == "Ostern"
    assert majority(["Ostern", "Osten"], "surname", "de-pl") is None
    assert majority([None, None], "surname", "de-pl") is None


def test_vote_builds_one_entry_per_key_entry():
    runs = [[{"register_no": "6", "surname": "Ostern"}], [{"register_no": "6", "surname": "Ostern"}],
            [{"register_no": "6", "surname": "Osten"}]]
    assert vote(runs, KEY) == [{"register_no": "6", "surname": "Ostern"}]


def test_consistency():
    a = [{"register_no": "6", "surname": "Ostern"}]
    assert consistency(a, a, KEY) == 1.0
    assert consistency(a, [{"register_no": "6", "surname": "Osten"}], KEY) == 0.5


def test_illegible_marker_never_wins_the_vote():
    assert majority(["[illegible]", "[illegible]", "Ostern"], "surname", "de-pl") == "Ostern"
    assert majority(["[illegible]", "[illegible]"], "surname", "de-pl") is None


def test_vote_and_consistency_honour_names_matching():
    from test_score import NAMES_KEY, LINE_PREDS
    assert [e["surname"] for e in vote([LINE_PREDS] * 3, NAMES_KEY)] == ["Kowalski", "Nowak", "Zielinski"]
    assert consistency(LINE_PREDS, LINE_PREDS, NAMES_KEY) == 1.0
    changed = [dict(p, surname="Zzz") if i == 0 else p for i, p in enumerate(LINE_PREDS)]
    assert consistency(LINE_PREDS, changed, NAMES_KEY) < 1.0


def test_names_key_vote_and_consistency_skip_register_no():
    from test_score import NAMES_KEY, LINE_PREDS
    assert all("register_no" not in e for e in vote([LINE_PREDS] * 3, NAMES_KEY))
    shifted = [dict(p, register_no="9") for p in LINE_PREDS]
    assert consistency(LINE_PREDS, shifted, NAMES_KEY) == 1.0
