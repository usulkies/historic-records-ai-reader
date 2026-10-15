import json

import pytest

import report
from report import adjudicate, field_rows, find_flags
from score import score_run

KEY = {"image_id": "t", "lang": "de-pl", "entries": [{"register_no": "6", "surname": "Osten"}]}
UNSURE = {"best": "Ostern", "alternatives": ["Osten"], "reason": "r faint; Ostern in row 4"}
RUNS = [("a", [{"register_no": "6", "surname": "Ostern"}]), ("b", [{"register_no": "6", "surname": UNSURE}]),
        ("c", [{"register_no": "6", "surname": "Osten"}])]


def test_flags_majority_against_key():
    flags = find_flags(KEY, RUNS)
    assert [(f["field"], f["majority_value"]) for f in flags] == [("surname", "Ostern")]
    assert {"contestant": "b", "value": UNSURE} in flags[0]["readings"]


def test_no_flag_without_strict_majority():
    assert find_flags(KEY, RUNS[1:]) == []


def test_field_rows_flatten_possible_readings():
    rows = field_rows("m", 1, "t", "raw", score_run([{"register_no": "6", "surname": UNSURE}], KEY))
    surname = next(r for r in rows if r["field"] == "surname")
    assert surname["best"] == "Ostern" and surname["alternatives"] == "Osten" and surname["rescued"]
    assert surname["reason"].startswith("r faint") and {r["key_set"] for r in rows} == {"raw"}


def test_adjudicate_applies_only_key_wrong():
    flags = find_flags(KEY, RUNS)
    assert adjudicate(KEY, flags)["entries"][0]["surname"] == "Osten"
    flags[0]["ruling"] = "key_wrong"
    assert adjudicate(KEY, flags)["entries"][0]["surname"] == "Ostern"


def test_load_runs_only_reads_record_files(tmp_path):
    d = tmp_path / "runs" / "t"
    d.mkdir(parents=True)
    rec = {"contestant": "m", "run": 1, "image_id": "t", "status": "ok", "entries": []}
    (d / "m__run1.json").write_text(json.dumps(rec))
    for junk in ("m__run1.json.prev-20260101", "m__run1.json.tmp", "m__run1.attempt1.stdout.txt",
                 "m__run1.raw.txt", "m__run2.json.prev-20260101-1"):
        (d / junk).write_text("not json {")
    (tmp_path / "runs" / "prompts").mkdir()
    (tmp_path / "runs" / "prompts" / "abc__run1.json").write_text("not json {")
    assert list(report._load_runs(tmp_path)["t"]) == [("m", 1)]


def _setup(tmp_path, monkeypatch, majority="Ostern"):
    (tmp_path / "key").mkdir(exist_ok=True)
    (tmp_path / "runs" / "t").mkdir(parents=True, exist_ok=True)
    key = dict(KEY, image="x", source="s")
    (tmp_path / "key" / "t.json").write_text(json.dumps(key))
    for n in ("a", "b", "c"):
        val = majority if n != "c" else "Osten"
        rec = {"contestant": n, "run": 1, "image_id": "t", "status": "ok",
               "entries": [{"register_no": "6", "surname": val}]}
        (tmp_path / "runs" / "t" / f"{n}__run1.json").write_text(json.dumps(rec))
    monkeypatch.setattr(report, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(report, "ADJ_FILE", tmp_path / "adjudication.json")
    monkeypatch.setattr(report, "SCORES_DIR", tmp_path / "scores")


def _rule(tmp_path, ruling):
    p = tmp_path / "adjudication.json"
    flags = json.loads(p.read_text())
    flags[0]["ruling"] = ruling
    p.write_text(json.dumps(flags))


def test_ruling_preserved_and_prev_archived(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    report.cmd_flags()
    _rule(tmp_path, "key_wrong")
    report.cmd_flags()
    flags = json.loads((tmp_path / "adjudication.json").read_text())
    assert flags[0]["ruling"] == "key_wrong" and flags[0]["stale"] is False
    assert len(list(tmp_path.glob("adjudication.json.prev-*"))) == 1
    assert not (tmp_path / "adjudication.json.tmp").exists()


def test_unraised_flag_carried_forward_stale(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    report.cmd_flags()
    _rule(tmp_path, "key_wrong")
    _setup_runs_agree_with_key(tmp_path)
    report.cmd_flags()
    flags = json.loads((tmp_path / "adjudication.json").read_text())
    assert len(flags) == 1 and flags[0]["stale"] and flags[0]["ruling"] == "key_wrong"
    assert adjudicate(KEY, flags)["entries"][0]["surname"] == "Osten"


def _setup_runs_agree_with_key(tmp_path):
    for p in (tmp_path / "runs" / "t").glob("*__run1.json"):
        rec = json.loads(p.read_text())
        rec["entries"][0]["surname"] = "Osten"
        p.write_text(json.dumps(rec))


def test_changed_majority_requires_fresh_ruling(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    report.cmd_flags()
    _rule(tmp_path, "key_wrong")
    _setup(tmp_path, monkeypatch, majority="Ostermann")
    for _ in range(2):
        report.cmd_flags()
        flags = json.loads((tmp_path / "adjudication.json").read_text())
        f = flags[0]
        assert f["ruling"] is None and f["stale"] is False and f["previous_ruling"] == "key_wrong"
        assert f["previous_majority_value"] == "Ostern" and f["majority_value"] == "Ostermann"
        assert adjudicate(KEY, flags)["entries"][0]["surname"] == "Osten"


def test_identical_rerun_creates_no_archive(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    report.cmd_flags()
    report.cmd_flags()
    assert list(tmp_path.glob("adjudication.json.prev-*")) == []


def test_invalid_ruling_exits_naming_flag(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    report.cmd_flags()
    _rule(tmp_path, "wrong")
    for cmd in (report.cmd_flags, report.cmd_leaderboard):
        with pytest.raises(SystemExit) as e:
            cmd()
        assert "image_id=t" in str(e.value) and "register_no=6" in str(e.value) and "field=surname" in str(e.value)


def test_leaderboard_labels_lang_and_skips_unkeyed(tmp_path, monkeypatch, capsys):
    _setup(tmp_path, monkeypatch)
    (tmp_path / "runs" / "zz").mkdir()
    (tmp_path / "runs" / "zz" / "a__run1.json").write_text(json.dumps(
        {"contestant": "a", "run": 1, "image_id": "zz", "status": "ok", "entries": []}))
    report.cmd_leaderboard()
    out = (tmp_path / "leaderboard.md").read_text()
    assert "t (de-pl)" in out and "Stale flags" in out
    assert "runs for zz have no key file" in capsys.readouterr().out


def test_failed_run_counts_zero_per_image(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    p = tmp_path / "runs" / "t" / "a__run1.json"
    rec = json.loads(p.read_text())
    rec["status"] = "failed"
    p.write_text(json.dumps(rec))
    report.cmd_leaderboard()
    summary = json.loads((tmp_path / "scores" / "summary.json").read_text())
    assert summary["a"]["per_image"]["t"] == [0.0]


def test_mode_of():
    assert report.mode_of("claude-haiku+tools") == "tools" and report.mode_of("claude-haiku") == "look"


def test_vote_per_mode_and_mode_column(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    for n in ("x+tools", "y+tools", "z+tools"):
        rec = {"contestant": n, "run": 1, "image_id": "t", "status": "ok",
               "entries": [{"register_no": "6", "surname": "Zzz"}]}
        (tmp_path / "runs" / "t" / f"{n}__run1.json").write_text(json.dumps(rec))
    report.cmd_leaderboard()
    votes = tmp_path / "scores" / "vote"
    look = json.loads((votes / "t__look.json").read_text())
    tools = json.loads((votes / "t__tools.json").read_text())
    assert look[0]["surname"] != "Zzz" and tools[0]["surname"] == "Zzz"
    out = (tmp_path / "leaderboard.md").read_text()
    assert "| Rank | Contestant | Mode | Adjudicated | Raw |" in out
    assert "| vote+tools | tools |" in out and "| vote | look |" in out


def _runs_for(key, field, values):
    return [(f"m{i}", [{**k, field: v} for k in key["entries"]]) for i, v in enumerate(values)]


@pytest.mark.parametrize("field, key_value, majority_value", [
    ("father", "Leib", "Leib Nussenbaum"),
    ("date_iso", "1890-05-XX", "1890-05-12"),
    ("date_iso", "1890-5-3", "1890-05-03"),
])
def test_no_flag_when_majority_scores_full_credit(field, key_value, majority_value):
    key = {"image_id": "t", "lang": "de-pl", "entries": [{"register_no": "6", field: key_value}]}
    assert find_flags(key, _runs_for(key, field, [majority_value] * 3)) == []


UNNUMBERED = {"image_id": "t", "lang": "de-pl",
              "entries": [{"surname": "Osten", "given_names": "Abram"}, {"surname": "Stein", "given_names": "Feige"}]}
UNNUMBERED_RUNS = [(n, [{"surname": "Ostern", "given_names": "Abram"}, {"surname": "Steyn", "given_names": "Feige"}])
                   for n in "abc"]


def test_unnumbered_entries_get_distinct_flags_and_rulings():
    flags = find_flags(UNNUMBERED, UNNUMBERED_RUNS)
    assert [(f["entry_idx"], f["majority_value"]) for f in flags] == [(0, "Ostern"), (1, "Steyn")]
    assert len(report.merge_flags(flags, flags, {"t": UNNUMBERED})) == 2
    flags[1]["ruling"] = "key_wrong"
    fixed = adjudicate(UNNUMBERED, flags)
    assert [e["surname"] for e in fixed["entries"]] == ["Osten", "Steyn"]


def test_merge_compares_majority_by_comparison_form():
    old = find_flags(KEY, RUNS)
    old[0]["ruling"] = "key_wrong"
    fresh = find_flags(KEY, [(n, [{"register_no": "6", "surname": "OSTERN"}]) for n in "abc"])
    merged = report.merge_flags(old, fresh, {"t": KEY})
    assert merged[0]["ruling"] == "key_wrong" and "previous_ruling" not in merged[0]


def test_legacy_flag_migrates_by_unique_register_no():
    fresh = find_flags(KEY, RUNS)
    legacy = {k: v for k, v in fresh[0].items() if k != "entry_idx"} | {"ruling": "key_wrong"}
    merged = report.merge_flags([legacy], fresh, {"t": KEY})
    assert len(merged) == 1 and merged[0]["ruling"] == "key_wrong" and merged[0]["entry_idx"] == 0
    assert not merged[0]["stale"]


def test_legacy_flag_without_unique_register_no_is_stale():
    fresh = find_flags(UNNUMBERED, UNNUMBERED_RUNS)
    legacy = {k: v for k, v in fresh[0].items() if k != "entry_idx"} | {"ruling": "key_wrong"}
    merged = report.merge_flags([legacy], fresh, {"t": UNNUMBERED})
    assert len(merged) == 3 and [f["stale"] for f in merged] == [False, False, True]
    assert merged[2]["ruling"] == "key_wrong"
    assert [e["surname"] for e in adjudicate(UNNUMBERED, merged)["entries"]] == ["Osten", "Stein"]


def test_load_key_rejects_duplicate_register_numbers(tmp_path):
    from score import load_key
    p = tmp_path / "k.json"
    entries = [{"register_no": "6"}, {"register_no": "7"}, {"register_no": "6"}, {"register_no": ""}, {}, {}]
    p.write_text(json.dumps({"image_id": "t", "image": "x", "lang": "de-pl", "source": "s", "entries": entries}))
    with pytest.raises(ValueError, match="duplicate register_no.*'6'"):
        load_key(p)


def test_leaderboard_runs_column_and_missing_warning(tmp_path, monkeypatch, capsys):
    _setup(tmp_path, monkeypatch)
    (tmp_path / "key" / "u.json").write_text(json.dumps(dict(KEY, image_id="u", image="y", source="s")))
    (tmp_path / "runs" / "u").mkdir()
    for n, img, run in (("a", "t", 2), ("a", "u", 1), ("b", "u", 1), ("c", "u", 1)):
        rec = {"contestant": n, "run": run, "image_id": img, "status": "ok",
               "entries": [{"register_no": "6", "surname": "Osten"}]}
        (tmp_path / "runs" / img / f"{n}__run{run}.json").write_text(json.dumps(rec))
    report.cmd_leaderboard()
    out = (tmp_path / "leaderboard.md").read_text()
    assert "| Runs |" in out
    rows = {line.split(" | ")[1]: line for line in out.splitlines() if line.startswith("| ") and "Rank" not in line}
    assert "| 3/4 |" in rows["a"] and "| 2/2 |" in rows["b"] and "| 2/2 |" in rows["vote"]
    warning = next(line for line in out.splitlines() if line.startswith("Warning: missing runs"))
    assert "a (3/4)" in warning and "b" not in warning.replace("a (3/4)", "")


def _tools_record(tmp_path, name, stdout, mode_files=None):
    d = tmp_path / "runs" / "t"
    rec = {"contestant": name, "run": 1, "image_id": "t", "status": "ok",
           "entries": [{"register_no": "6", "surname": "Osten"}]}
    (d / f"{name}__run1.json").write_text(json.dumps(rec))
    (d / f"{name}__run1.stdout.txt").write_text(stdout)
    for rel, text in (mode_files or {}).items():
        f = d / f"{name}__run1.workdir" / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)


def test_isolation_audit_lists_tools_hits_only(tmp_path, monkeypatch, capsys):
    from contestants import GENEALOGY_ROOT
    _setup(tmp_path, monkeypatch)
    _tools_record(tmp_path, "x+tools", f"ls {GENEALOGY_ROOT}/people")
    _tools_record(tmp_path, "y+tools", "clean", {"sub/notes.txt": f"cat {GENEALOGY_ROOT}/x"})
    _tools_record(tmp_path, "z+tools", "clean", {"big.bin": GENEALOGY_ROOT + "x" * (5 * 1024 * 1024)})
    _tools_record(tmp_path, "a", f"look mode {GENEALOGY_ROOT}")
    report.cmd_leaderboard()
    hits = json.loads((tmp_path / "scores" / "isolation_warnings.json").read_text())
    assert [(h["contestant"], h["image_id"], h["run"], h["file"]) for h in hits] == [
        ("x+tools", "t", 1, "runs/t/x+tools__run1.stdout.txt"),
        ("y+tools", "t", 1, "runs/t/y+tools__run1.workdir/sub/notes.txt")]
    out = (tmp_path / "leaderboard.md").read_text()
    assert "## Isolation warnings" in out and "x+tools" in out.split("## Isolation warnings")[1]


def test_isolation_audit_clean_says_none(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _tools_record(tmp_path, "x+tools", "clean")
    report.cmd_leaderboard()
    assert json.loads((tmp_path / "scores" / "isolation_warnings.json").read_text()) == []
    assert (tmp_path / "leaderboard.md").read_text().split("## Isolation warnings")[1].strip() == "none"


def test_adjudicate_skips_ruling_when_key_value_changed(capsys):
    flags = find_flags(KEY, RUNS)
    flags[0]["ruling"] = "key_wrong"
    edited = {**KEY, "entries": [{"register_no": "6", "surname": "Ostrow"}]}
    assert adjudicate(edited, flags)["entries"][0]["surname"] == "Ostrow"
    out = capsys.readouterr().out
    assert "image_id=t" in out and "field=surname" in out and "Osten" in out
    same_form = {**KEY, "entries": [{"register_no": "6", "surname": "OSTEN"}]}
    assert adjudicate(same_form, flags)["entries"][0]["surname"] == "Ostern"


def test_find_flags_honours_names_matching():
    from test_score import NAMES_KEY, LINE_PREDS
    key = dict(NAMES_KEY, image_id="t", entries=[dict(e) for e in NAMES_KEY["entries"]])
    key["entries"][0]["given_names"] = "Jon"
    runs = [(n, LINE_PREDS) for n in "abc"]
    flags = find_flags(key, runs)
    assert [(f["entry_idx"], f["field"], f["majority_value"]) for f in flags] == [(0, "given_names", "Jan")]
