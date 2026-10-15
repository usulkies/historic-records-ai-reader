import json

import pytest

import performance
from performance import collect, picks, pooled, render_tables, value


def row(name, acc, time_s, cli="claude", pt="t", findable=None, failed=0, runs=2, image_id="img"):
    return {"contestant": name, "cli": cli, "page_type": pt, "image_id": image_id, "accuracy": acc,
            "name_findable_with_alts": acc if findable is None else findable, "time_s": time_s, "failed": failed,
            "runs": runs, "mode": "look", **{c: None for c in ("accuracy_best_only", "alt_gain", "name_exact",
            "name_near", "tokens", "hedge_rate", "rescue_rate", "made_up_entries", "consistency")}}


def names(p):
    return [(r["contestant"], in_window) for r, _, in_window in p]


def test_value_costs_a_fixed_amount_per_doubling_above_the_floor():
    assert value(0.9, 10, 0.05) == value(0.9, 30, 0.05) == 0.9
    assert value(0.9, 60, 0.05) == pytest.approx(0.85)
    assert value(1.0, 120, 0.10) == pytest.approx(0.8)


def test_proof_picks_window_value_and_tie_break():
    rows = [row("a", 0.90, 120), row("b", 0.88, 30), row("c", 0.85, 60, cli="codex"), row("d", 0.70, 30, cli="agy"),
            row("e", 0.95, 30, failed=1)]
    p = picks(rows, "proof")["t"]
    # a and c tie on value (0.80); a is more accurate over all pages.
    assert names(p["picks"]) == [("b", True), ("a", True), ("c", True)]
    assert p["other_cli"][0]["contestant"] == "c"


def test_fill_outside_window_is_marked():
    p = picks([row("x", 0.9, 30), row("y", 0.5, 30, cli="agy"), row("z", 0.6, 300)], "proof")["t"]
    assert names(p["picks"]) == [("x", True), ("z", False), ("y", False)]
    assert names([p["other_cli"]]) == [("y", False)]


def test_scan_mode_drops_slow_models_and_weighs_time_more():
    rows = [row("fast", 0.80, 30, findable=0.85), row("slow", 0.95, 400, findable=0.95),
            row("mid", 0.90, 120, findable=0.95)]
    assert names(picks(rows, "scan")["t"]["picks"]) == [("fast", True), ("mid", True)]
    assert names(picks(rows, "proof")["t"]["picks"]) == [("mid", True), ("slow", True), ("fast", False)]


def test_scan_ties_go_to_look_only_proof_ties_to_all_pages_accuracy():
    rows = [dict(row("strong+tools", 1.0, 30), mode="tools"), row("fast", 1.0, 18),
            dict(row("strong+tools", 0.9, 30, pt="other"), mode="tools"), row("fast", 0.5, 18, pt="other")]
    assert names(picks(rows, "scan")["t"]["picks"]) == [("fast", True), ("strong+tools", True)]
    assert names(picks(rows, "proof")["t"]["picks"]) == [("strong+tools", True), ("fast", True)]


def test_pages_of_one_record_type_are_averaged():
    rows = pooled([row("a", 1.0, 30, image_id="p1"), row("a", 0.5, 90, image_id="p2", failed=1)])
    assert len(rows) == 1 and rows[0]["accuracy"] == 0.75 and rows[0]["time_s"] == 60
    assert rows[0]["runs"] == 4 and rows[0]["failed"] == 1 and rows[0]["image_id"] == "p1, p2"


def test_tables_have_every_contestant():
    text = render_tables([row("a", 0.9, 30), row("b", 0.8, 60)])
    assert text.startswith("### t") and text.count("\n| a |") + text.count("\n| b |") == 2


def _write_run(d, name, run, entries, status="ok", usage=None):
    stem = d / f"{name}__run{run}"
    (d / f"{name}__run{run}.json").write_text(json.dumps(
        {"contestant": name, "cli": "claude", "run": run, "status": status, "duration_s": 40, "entries": entries}))
    events = [{"type": "result", "usage": usage}] if usage else []
    stem.with_name(stem.name + ".stdout.txt").write_text("\n".join(json.dumps(e) for e in events))
    stem.with_name(stem.name + ".stderr.txt").write_text("")


def test_collect_scores_runs_against_the_adjudicated_key(tmp_path):
    (tmp_path / "key").mkdir()
    key = {"image_id": "k", "image": "x.jpg", "lang": "de-pl", "source": {}, "page_type": "polish_narrative",
           "entries": [{"register_no": "1", "surname": "Piper", "given_names": "Abraham"}]}
    (tmp_path / "key" / "k.json").write_text(json.dumps(key))
    d = tmp_path / "runs" / "k"
    d.mkdir(parents=True)
    unsure = {"best": "Pieper", "alternatives": ["Piper"], "reason": "r"}
    _write_run(d, "m+tools", 1, [{"register_no": "1", "surname": unsure, "given_names": "Abraham"}],
               usage={"input_tokens": 10, "cache_read_input_tokens": 5, "output_tokens": 1})
    _write_run(d, "m+tools", 2, [], status="failed")
    (d / "m+tools__run1.json.prev-20261011").write_text("{}")
    [r] = collect(tmp_path)
    assert (r["page_type"], r["mode"], r["runs"], r["failed"], r["tokens"]) == ("polish_narrative", "tools", 2, 1, 16)
    assert r["name_findable_with_alts"] == 1.0 and r["name_exact"] == 0.5 and r["alt_gain"] > 0
    assert r["consistency"] is None and r["accuracy"] < 0.5


def test_collect_needs_a_record_type(tmp_path):
    (tmp_path / "key").mkdir()
    (tmp_path / "key" / "new.json").write_text(json.dumps(
        {"image_id": "new", "image": "x.jpg", "lang": "hu", "source": {}, "entries": []}))
    with pytest.raises(SystemExit, match="page_type"):
        collect(tmp_path)


def test_known_keys_have_record_types():
    assert set(performance.PAGE_TYPES.values()) == {"galician_table", "polish_narrative", "russian_narrative",
                                                    "russian_index"}
