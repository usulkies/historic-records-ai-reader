"""Adjudication flags and the leaderboard.

Usage: python3 -I scripts/htr_contest/report.py flags|leaderboard
"""
import copy
import csv
import json
import os
import re
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from contestants import GENEALOGY_ROOT  # noqa: E402
from normalize import best, readings, reason  # noqa: E402
from score import field_matches, field_value, keyed, load_key, match_entries_for_key, score_run, scored_fields  # noqa: E402
from vote import consistency, majority, vote  # noqa: E402

REPORT_DIR = Path(__file__).resolve().parents[2] / "reports" / "htr-contest"
ADJ_FILE = REPORT_DIR / "adjudication.json"
SCORES_DIR = REPORT_DIR / "scores"


def find_flags(key, contestant_runs):
    """contestant_runs: list of (contestant, entries) pairs."""
    lang, flags = key["lang"], []
    names = [n for n, _ in contestant_runs]
    aligned = [match_entries_for_key(r, key)[0] for _, r in contestant_runs]
    for idx, k in enumerate(key["entries"]):
        for field in scored_fields(key):
            if not keyed(k, field, lang):
                continue
            values = [(pairs[idx][1] or {}).get(field) for pairs in aligned]
            winner = majority(values, field, lang)
            agree = sum(field_value(field, v, lang) == field_value(field, winner, lang) for v in values)
            if winner and agree * 2 > len(values) and field_matches(field, winner, k[field], lang) < 1:
                flags.append({"image_id": key["image_id"], "entry_idx": idx, "register_no": k.get("register_no"),
                              "field": field,
                              "key_value": k[field], "majority_value": winner,
                              "readings": [{"contestant": n, "value": v} for n, v in zip(names, values) if v not in (None, "")],
                              "ruling": None, "stale": False})
    return flags


def entry_idx(key, flag):
    """The key entry a flag refers to; flags written before entry_idx existed fall back to a unique register_no."""
    if "entry_idx" in flag:
        return flag["entry_idx"]
    no = flag.get("register_no")
    hits = [i for i, e in enumerate(key["entries"]) if no not in (None, "") and e.get("register_no") == no]
    return hits[0] if len(hits) == 1 else None


def adjudicate(key, flags):
    fixed = copy.deepcopy(key)
    for f in flags:
        if f["ruling"] == "key_wrong" and not f.get("stale") and f["image_id"] == key["image_id"]:
            idx = entry_idx(key, f)
            if idx is None or idx >= len(fixed["entries"]):
                continue
            entry, field = fixed["entries"][idx], f["field"]
            if field_value(field, entry.get(field), key["lang"]) != field_value(field, f["key_value"], key["lang"]):
                # The key was edited since the ruling; the ruling was about a value no longer there.
                print(f"warning: skipped ruling for image_id={f['image_id']} entry_idx={idx} field={field}: "
                      f"key now {entry.get(field)!r}, flag was raised against {f['key_value']!r}")
                continue
            entry[field] = f["majority_value"]
    return fixed


def field_rows(contestant, run, image_id, key_set, run_score):
    return [{"contestant": contestant, "run": run, "image_id": image_id, "key_set": key_set,
             "register_no": r.register_no, "field": r.field, "key_value": r.key_value,
             "best": best(r.pred_value), "alternatives": " | ".join(readings(r.pred_value)[1:]),
             "reason": reason(r.pred_value), "base": round(r.base, 4), "points": round(r.points, 4),
             "weight": r.weight, "uncertain": r.uncertain, "rescued": r.rescued}
            for r in run_score.fields]


RECORD_RE = re.compile(r"__run\d+\.json$")


def _load_runs(report_dir=None):
    report_dir = report_dir or REPORT_DIR
    runs = defaultdict(dict)  # image_id -> {(contestant, run): record}
    # Archived .prev-*, transient .tmp and runs/prompts/ must never be read as records.
    for p in (report_dir / "runs").glob("*/*__run*.json"):
        if p.parent.name == "prompts" or not RECORD_RE.search(p.name):
            continue
        rec = json.loads(p.read_text())
        runs[rec["image_id"]][(rec["contestant"], rec["run"])] = rec
    return runs


def mode_of(name):
    return "tools" if name.endswith("+tools") else "look"


def _ok_first_runs(records, mode=None):
    return [(name, r["entries"]) for (name, n), r in sorted(records.items())
            if n == 1 and r["status"] == "ok" and (mode is None or mode_of(name) == mode)]


AUDIT_MAX_BYTES = 5 * 1024 * 1024


def isolation_hits(runs, report_dir=None):
    """Tools-mode artifacts that mention the research repo's path: evidence a model saw outside its folder."""
    report_dir = report_dir or REPORT_DIR
    hits = []
    for image_id, records in sorted(runs.items()):
        for name, run in sorted(k for k in records if mode_of(k[0]) == "tools"):
            stem = report_dir / "runs" / image_id / f"{name}__run{run}"
            workdir = stem.with_name(stem.name + ".workdir")
            files = [stem.with_name(stem.name + ".stdout.txt"),
                     *(sorted(p for p in workdir.rglob("*") if p.is_file()) if workdir.is_dir() else [])]
            for f in files:
                if f.is_file() and f.stat().st_size <= AUDIT_MAX_BYTES and \
                        GENEALOGY_ROOT in f.read_bytes().decode("utf-8", "replace"):
                    hits.append({"contestant": name, "image_id": image_id, "run": run,
                                 "file": f.relative_to(report_dir).as_posix()})
    return hits


RULINGS = (None, "key_wrong", "key_right")


def check_rulings(flags):
    for f in flags:
        if f.get("ruling") not in RULINGS:
            sys.exit(f"invalid ruling {f.get('ruling')!r} for image_id={f.get('image_id')} "
                     f"register_no={f.get('register_no')} field={f.get('field')}; use null, key_wrong or key_right")


def merge_flags(old, fresh, keys):
    """Rulings survive: a changed majority parks the old ruling in previous_ruling for a fresh decision; un-raised flags are carried forward as stale."""
    old_by, unmatched = {}, []
    for f in old:
        key = keys.get(f["image_id"])
        idx = entry_idx(key, f) if key else None
        ident = (f["image_id"], idx, f["field"])
        if idx is None or ident in old_by:
            unmatched.append(f)
        else:
            old_by[ident] = f
    merged = []
    for f in fresh:
        prev = old_by.pop((f["image_id"], f["entry_idx"], f["field"]), None)
        if prev is None:
            merged.append(f)
            continue
        kept = {**prev, "entry_idx": f["entry_idx"], "register_no": f["register_no"], "readings": f["readings"],
                "key_value": f["key_value"], "stale": False}
        lang = keys[f["image_id"]]["lang"]
        if field_value(f["field"], prev["majority_value"], lang) != field_value(f["field"], f["majority_value"], lang):
            kept.update(ruling=None, previous_ruling=prev["ruling"] or prev.get("previous_ruling"),
                        previous_majority_value=prev["majority_value"], majority_value=f["majority_value"])
        merged.append(kept)
    merged += [{**f, "stale": True} for f in [*old_by.values(), *unmatched]]
    return merged


def _load_keys():
    return {k["image_id"]: k for k in map(load_key, sorted((REPORT_DIR / "key").glob("*.json")))}


def _load_flags():
    flags = json.loads(ADJ_FILE.read_text()) if ADJ_FILE.exists() else []
    check_rulings(flags)
    return flags


def cmd_flags():
    keys, old = _load_keys(), _load_flags()
    fresh = []
    for image_id, records in _load_runs().items():
        if image_id not in keys:
            print(f"warning: runs for {image_id} have no key file; skipped")
            continue
        fresh += find_flags(keys[image_id], _ok_first_runs(records))
    flags = merge_flags(old, fresh, keys)
    text = json.dumps(flags, ensure_ascii=False, indent=1)
    if ADJ_FILE.exists() and ADJ_FILE.read_text() != text:
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S.%f")
        ADJ_FILE.with_name(f"{ADJ_FILE.name}.prev-{stamp}").write_bytes(ADJ_FILE.read_bytes())
    tmp = ADJ_FILE.with_name(ADJ_FILE.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, ADJ_FILE)
    live = [f for f in flags if not f.get("stale")]
    print(f"{len(live)} flags, {sum(f['ruling'] is None for f in live)} awaiting ruling, "
          f"{len(flags) - len(live)} stale -> {ADJ_FILE}")


def cmd_leaderboard():
    keys, flags = _load_keys(), _load_flags()
    rows = defaultdict(lambda: {"raw": [], "adj": [], "extras": 0, "hedge": [], "rescue": [], "cons": [],
                                "failed": 0, "max_run": 0, "per_image": defaultdict(list)})
    all_fields = []
    runs = _load_runs()
    for image_id, records in runs.items():
        if image_id not in keys:
            print(f"warning: runs for {image_id} have no key file; skipped")
            continue
        key, adj_key = keys[image_id], adjudicate(keys[image_id], flags)
        scored = dict(records)
        for mode in ("look", "tools"):
            voters = [e for _, e in _ok_first_runs(records, mode)]
            if not voters:
                continue
            vote_name = "vote" if mode == "look" else "vote+tools"
            scored[(vote_name, 1)] = {"status": "ok", "entries": vote(voters, key)}
            (SCORES_DIR / "vote").mkdir(parents=True, exist_ok=True)
            (SCORES_DIR / "vote" / f"{image_id}__{mode}.json").write_text(
                json.dumps(scored[(vote_name, 1)]["entries"], ensure_ascii=False, indent=1))
        for (name, run), rec in scored.items():
            row = rows[name]
            row["max_run"] = max(row["max_run"], run)
            if rec["status"] != "ok":
                row["failed"] += 1
                row["raw"].append(0.0)
                row["adj"].append(0.0)
                row["per_image"][image_id].append(0.0)
                continue
            raw, adj = score_run(rec["entries"], key), score_run(rec["entries"], adj_key)
            all_fields += field_rows(name, run, image_id, "raw", raw) + field_rows(name, run, image_id, "adjudicated", adj)
            row["raw"].append(raw.score)
            row["adj"].append(adj.score)
            row["per_image"][image_id].append(adj.score)
            row["extras"] += raw.extras
            row["hedge"].append(raw.hedge_rate)
            row["rescue"].append(adj.rescue_rate)
        for (name, run), rec in records.items():
            other = records.get((name, 2))
            if run == 1 and other and rec["status"] == other["status"] == "ok":
                rows[name]["cons"].append(consistency(rec["entries"], other["entries"], key))
    images = sorted(keys)
    mean = lambda xs: f"{statistics.mean(xs):.3f}" if xs else "–"  # noqa: E731
    # A contestant missing runs on some images is ranked on fewer, possibly easier, pages.
    runs_col = {name: f"{len(r['raw'])}/{len(keys) * r['max_run']}" for name, r in rows.items()}
    missing = [f"{name} ({runs_col[name]})" for name, r in sorted(rows.items())
               if len(r["raw"]) < len(keys) * r["max_run"]]
    lines = ["# Handwriting transcription contest — leaderboard", "",
             f"Flags awaiting ruling: {sum(f['ruling'] is None and not f.get('stale') for f in flags)}",
             f"Stale flags (need re-review): {sum(bool(f.get('stale')) for f in flags)}", "",
             *([f"Warning: missing runs for {', '.join(missing)}", ""] if missing else []),
             "| Rank | Contestant | Mode | Adjudicated | Raw | " + " | ".join(f"{i} ({keys[i]['lang']})" for i in images)
             + " | Made-up entries | Hedge rate | Rescue rate | Consistency | Failed runs | Runs |",
             "|" + "---|" * (11 + len(images))]
    ranked = sorted(rows.items(), key=lambda kv: -statistics.mean(kv[1]["adj"] or [0]))
    for rank, (name, r) in enumerate(ranked, 1):
        lines.append(f"| {rank} | {name} | {mode_of(name)} | {mean(r['adj'])} | {mean(r['raw'])} | "
                     + " | ".join(mean(r["per_image"][i]) for i in images)
                     + f" | {r['extras']} | {mean(r['hedge'])} | {mean(r['rescue'])} | {mean(r['cons'])}"
                     + f" | {r['failed']} | {runs_col[name]} |")
    hits = isolation_hits(runs)
    lines += ["", "## Isolation warnings", ""]
    lines += [f"- {h['contestant']} {h['image_id']} run{h['run']}: {h['file']}" for h in hits] or ["none"]
    (REPORT_DIR / "leaderboard.md").write_text("\n".join(lines) + "\n")
    SCORES_DIR.mkdir(parents=True, exist_ok=True)
    (SCORES_DIR / "isolation_warnings.json").write_text(json.dumps(hits, ensure_ascii=False, indent=1))
    with open(SCORES_DIR / "fields.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_fields[0]) if all_fields else ["contestant"])
        writer.writeheader()
        writer.writerows(all_fields)
    (SCORES_DIR / "summary.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    print("\n".join(lines))


if __name__ == "__main__":
    {"flags": cmd_flags, "leaderboard": cmd_leaderboard}[sys.argv[1]]()
