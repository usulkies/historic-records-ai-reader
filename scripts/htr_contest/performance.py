"""Per-model metrics for each record type, and the default + 2 fallback models per record type and mode.

Usage:
  python3 -I scripts/htr_contest/performance.py collect   # runs/ -> scores/model-performance.json
  python3 -I scripts/htr_contest/performance.py tables    # markdown tables for the skill's model-performance.md
  python3 -I scripts/htr_contest/performance.py picks     # picks per record type, scan and proof mode

A key's record type is its "page_type" field, or PAGE_TYPES below for the first four keys.
"""
import argparse
import json
import math
import re
import statistics
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from normalize import best, readings  # noqa: E402
from report import adjudicate, check_rulings  # noqa: E402
from score import NAME_FIELDS, _name_similarity, load_key, score_run  # noqa: E402
from vote import consistency  # noqa: E402

REPORT_DIR = Path(__file__).resolve().parents[2] / "reports" / "htr-contest"
PERF_FILE = REPORT_DIR / "scores" / "model-performance.json"
RECORD_RE = re.compile(r"__run\d+\.json$")
PAGE_TYPES = {"ah-szczerzec-b1894-0005": "galician_table", "pl-warszawa-b1848-043-046": "polish_narrative",
              "ru-warszawa-b1878-012-013": "russian_narrative", "ru-warszawa-b1878-sku1": "russian_index"}
NEAR = 0.8
# Below this many seconds CLI start-up dominates, so speed differences don't count.
TIME_FLOOR_S = 30
# Scan reads hundreds of pages, so time weighs double and slow models are out; proof reads one entry.
MODES = {
    "scan": {"metric": "name_findable_with_alts", "window": 0.15, "time_weight": 0.10, "max_time_s": 300,
             "prefer_look": True},
    "proof": {"metric": "accuracy", "window": 0.10, "time_weight": 0.05, "max_time_s": None, "prefer_look": False},
}
DEFINITIONS = {
    "accuracy": "weighted field score vs published index key (adjudicated), mean of 2 runs, failed run = 0",
    "accuracy_best_only": "same answers with alternatives stripped (best reading treated as confident)",
    "alt_gain": "accuracy - accuracy_best_only (what the possible-readings format earned)",
    "name_exact": "share of name fields whose best reading matches every key name word exactly (after spelling normalization)",
    "name_near": "share of name fields whose best reading is >=0.8 word similarity (~1 letter off in 5)",
    "name_findable_with_alts": "share of name fields where best OR an alternative is >=0.8 similar: would a fuzzy search find the person",
    "consistency": "share of key fields where run 1 and run 2 agree",
    "time_s": "mean wall-clock seconds per page, failed runs included",
    "tokens": "mean tokens per successful run as the CLI reports them (Claude: incl. cache reads); null = not reported",
    "hedge_rate": "share of answered fields given with alternatives",
    "rescue_rate": "share of wrong-but-hedged fields where an alternative was right",
    "made_up_entries": "mean entries per run that pair with no key entry",
}


def value(metric, time_s, time_weight):
    """The metric minus time_weight per doubling of time above TIME_FLOOR_S."""
    return metric - time_weight * math.log2(max(time_s, TIME_FLOOR_S) / TIME_FLOOR_S)


def tokens(stem: Path):
    """Tokens one run used, parsed from its saved CLI output; None when the CLI did not report them."""
    out, err = (f.read_text(errors="replace") if f.exists() else "" for f in
                (stem.with_name(stem.name + ".stdout.txt"), stem.with_name(stem.name + ".stderr.txt")))
    m = re.search(r"tokens used\s*\n?\s*([\d,]+)", out + "\n" + err)
    if m:
        return int(m.group(1).replace(",", ""))
    total = None
    for line in out.splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(e, dict):
            continue
        u = e.get("usage")
        if e.get("type") == "turn.completed" and isinstance(u, dict):
            total = (total or 0) + u.get("input_tokens", 0) + u.get("output_tokens", 0)
        elif e.get("type") == "result" and isinstance(u, dict):
            total = sum(u.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens",
                                              "cache_read_input_tokens", "output_tokens"))
        elif e.get("event") == "result" and isinstance(e.get("result"), dict) \
                and isinstance(e["result"].get("usage"), dict):
            u = e["result"]["usage"]
            total = u.get("total_tokens", 0) + u.get("cache_read_tokens", 0)
    return total


def _strip_alternatives(entries):
    return [{f: best(v) for f, v in e.items()} for e in entries]


def _r(x, nd=3):
    return round(x, nd) if x is not None else None


def contestant_row(name, recs, key, page_type):
    """recs: [(stem path, run record)] of one contestant on one keyed page."""
    lang = key["lang"]
    acc, acc_best, times, toks, hedge, rescue, extras, ok_entries = [], [], [], [], [], [], [], []
    exact = near = findable = total_names = 0
    for stem, r in recs:
        times.append(r["duration_s"] or 0)
        if r["status"] != "ok":
            acc.append(0.0)
            acc_best.append(0.0)
            continue
        s = score_run(r["entries"], key)
        acc.append(s.score)
        hedge.append(s.hedge_rate)
        rescue.append(s.rescue_rate)
        extras.append(s.extras)
        acc_best.append(score_run(_strip_alternatives(r["entries"]), key).score)
        t = tokens(stem)
        if t is not None:
            toks.append(t)
        ok_entries.append(r["entries"])
        for f in s.fields:
            if f.field not in NAME_FIELDS:
                continue
            total_names += 1
            b = best(f.pred_value)
            bs = _name_similarity(b, f.key_value, lang) if b else 0.0
            alls = max([_name_similarity(x, f.key_value, lang) for x in readings(f.pred_value)] or [0.0])
            exact += bs >= 0.999
            near += bs >= NEAR
            findable += alls >= NEAR
    names = (lambda n: round(n / total_names, 3)) if total_names else (lambda n: None)
    return {"contestant": name, "model": name.replace("+tools", ""),
            "mode": "tools" if name.endswith("+tools") else "look", "cli": recs[0][1]["cli"],
            "page_type": page_type, "image_id": key["image_id"], "lang": lang, "runs": len(recs),
            "failed": sum(r["status"] != "ok" for _, r in recs),
            "accuracy": round(statistics.mean(acc), 3), "accuracy_best_only": round(statistics.mean(acc_best), 3),
            "alt_gain": round(statistics.mean(acc) - statistics.mean(acc_best), 3),
            "time_s": round(statistics.mean(times)), "tokens": round(statistics.mean(toks)) if toks else None,
            "hedge_rate": _r(statistics.mean(hedge)) if hedge else None,
            "rescue_rate": _r(statistics.mean(rescue)) if rescue else None,
            "made_up_entries": round(statistics.mean(extras), 1) if extras else None,
            "name_exact": names(exact), "name_near": names(near), "name_findable_with_alts": names(findable),
            "consistency": _r(consistency(ok_entries[0], ok_entries[1], key)) if len(ok_entries) >= 2 else None}


def collect(report_dir=REPORT_DIR):
    adj = report_dir / "adjudication.json"
    flags = json.loads(adj.read_text()) if adj.exists() else []
    check_rulings(flags)
    rows = []
    for path in sorted((report_dir / "key").glob("*.json")):
        raw_key = load_key(path)
        page_type = raw_key.get("page_type") or PAGE_TYPES.get(raw_key["image_id"])
        if not page_type:
            sys.exit(f"{path}: give the key a \"page_type\" (e.g. \"polish_narrative\") so its runs can be grouped")
        key, by = adjudicate(raw_key, flags), {}
        for p in sorted((report_dir / "runs" / raw_key["image_id"]).glob("*__run*.json")):
            if RECORD_RE.search(p.name):
                rec = json.loads(p.read_text())
                by.setdefault(rec["contestant"], []).append((p.with_suffix(""), rec))
        rows += [contestant_row(name, recs, key, page_type) for name, recs in by.items()]
    return rows


def pooled(rows):
    """One row per contestant and record type: a type keyed on several pages averages them, page by page."""
    groups = {}
    for r in rows:
        groups.setdefault((r["contestant"], r["page_type"]), []).append(r)
    out = []
    for group in groups.values():
        row = dict(group[0], image_id=", ".join(r["image_id"] for r in group),
                   runs=sum(r["runs"] for r in group), failed=sum(r["failed"] for r in group))
        for c in ("accuracy", "accuracy_best_only", "alt_gain", "name_exact", "name_near", "name_findable_with_alts",
                  "time_s", "tokens", "hedge_rate", "rescue_rate", "made_up_entries", "consistency"):
            vals = [r[c] for r in group if r[c] is not None]
            row[c] = (round(statistics.mean(vals)) if c in ("time_s", "tokens") else round(statistics.mean(vals), 3)) \
                if vals else None
        out.append(row)
    return out


def _rank(cands, cfg, overall, by_value=True):
    """[(row, value, in_window)] best first. A page every leader aces cannot rank them, so ties go to the
    model with the best accuracy over all pages, then to the faster one. In scan mode a look-only model wins
    a tie first: a tools run loops over crops and spends far more of the plan's quota on every page."""
    metric = cfg["metric"]

    def order(r):
        lead = round(value(r[metric], r["time_s"], cfg["time_weight"]), 3) if by_value else r[metric]
        tools_last = r["mode"] != "look" if cfg["prefer_look"] else False
        return (-lead, tools_last, -round(overall[r["contestant"]], 3), r["time_s"])
    return [(r, value(r[metric], r["time_s"], cfg["time_weight"]), r["_in_window"]) for r in sorted(cands, key=order)]


def picks(rows, mode, n=3):
    """{page_type: {"picks": [(row, value, in_window)], "other_cli": (row, value, in_window) | None}}.

    Eligible: no failed run, 2+ runs, under the mode's time cap. Within `window` of the best metric, rank by
    value; if fewer than n are that close, fill by the metric alone (in_window False)."""
    cfg, metric = MODES[mode], MODES[mode]["metric"]
    overall = {}
    for r in rows:
        overall.setdefault(r["contestant"], []).append(r["accuracy"])
    overall = {c: statistics.mean(a) for c, a in overall.items()}
    out, rows = {}, pooled(rows)
    for pt in sorted({r["page_type"] for r in rows}):
        pool = [dict(r) for r in rows if r["page_type"] == pt and r["failed"] == 0 and r["runs"] >= 2
                and r.get(metric) is not None and (cfg["max_time_s"] is None or r["time_s"] <= cfg["max_time_s"])]
        top = max((r[metric] for r in pool), default=None)
        for r in pool:
            r["_in_window"] = r[metric] >= top - cfg["window"] - 1e-9
        near = [r for r in pool if r["_in_window"]]
        chosen = _rank(near, cfg, overall)[:n]
        chosen += _rank([r for r in pool if not r["_in_window"]], cfg, overall, by_value=False)[:n - len(chosen)]
        others = [r for r in pool if chosen and r["cli"] != chosen[0][0]["cli"]]
        other = (_rank([r for r in others if r["_in_window"]], cfg, overall)
                 or _rank(others, cfg, overall, by_value=False) or [None])[0]
        out[pt] = {"picks": chosen, "other_cli": other}
    return out


def _cell(pick, metric):
    if pick is None:
        return "–"
    r, v, in_window = pick
    return f"{r['contestant']} {r[metric]:.2f} · {r['time_s']} s{'' if in_window else ' ⁺'}"


def render_picks(rows):
    lines = []
    for mode, cfg in MODES.items():
        lines += [f"**{mode}** (metric `{cfg['metric']}`, window {cfg['window']}, time weight {cfg['time_weight']}"
                  f"{', max ' + str(cfg['max_time_s']) + ' s/page' if cfg['max_time_s'] else ''})", "",
                  "| Record type | Default | Fallback 1 | Fallback 2 | Best on another CLI |", "|---|---|---|---|---|"]
        for pt, p in picks(rows, mode).items():
            cells = [_cell(c, cfg["metric"]) for c in p["picks"]] + ["–"] * (3 - len(p["picks"]))
            lines.append(f"| {pt} | {' | '.join(cells)} | {_cell(p['other_cli'], cfg['metric'])} |")
        lines.append("")
    return "\n".join(lines)


COLUMNS = (("accuracy", "Acc"), ("accuracy_best_only", "Best-only"), ("alt_gain", "Alt gain"),
           ("name_exact", "Name exact"), ("name_near", "Name near"), ("name_findable_with_alts", "Findable"),
           ("time_s", "Time s"), ("tokens", "Tokens"), ("hedge_rate", "Hedge"), ("rescue_rate", "Rescue"),
           ("made_up_entries", "Made-up"), ("consistency", "Cons."), ("failed", "Failed"), ("runs", "Runs"))


def _fmt(v, column):
    if v is None:
        return "–"
    if column in ("time_s", "tokens", "failed", "runs"):
        return str(v)
    return f"{v:g}" if column == "made_up_entries" else f"{v:.3f}"


def render_tables(rows):
    lines, rows = [], pooled(rows)
    for pt in sorted({r["page_type"] for r in rows}):
        sub = sorted((r for r in rows if r["page_type"] == pt), key=lambda r: (-r["accuracy"], r["contestant"]))
        lines += [f"### {pt}", "", "| Contestant | Mode | " + " | ".join(h for _, h in COLUMNS) +
                  " | Scan value | Proof value |", "|---" * (len(COLUMNS) + 4) + "|"]
        for r in sub:
            vals = [_fmt(r[c], c) for c, _ in COLUMNS]
            scan = r["name_findable_with_alts"]
            sv = "–" if scan is None else f"{value(scan, r['time_s'], MODES['scan']['time_weight']):.3f}"
            pv = f"{value(r['accuracy'], r['time_s'], MODES['proof']['time_weight']):.3f}"
            lines.append(f"| {r['contestant']} | {r['mode']} | " + " | ".join(vals) + f" | {sv} | {pv} |")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("collect", "tables", "picks"))
    args = ap.parse_args()
    if args.cmd == "collect":
        rows = collect()
        PERF_FILE.write_text(json.dumps({"generated": date.today().isoformat(),
                                         "value_formula": "metric - time_weight*log2(max(time_s,30)/30)",
                                         "modes": MODES, "definitions": DEFINITIONS, "rows": rows},
                                        ensure_ascii=False, indent=1))
        print(f"{len(rows)} rows -> {PERF_FILE}")
        return
    rows = json.loads(PERF_FILE.read_text())["rows"]
    print(render_tables(rows) if args.cmd == "tables" else render_picks(rows))


if __name__ == "__main__":
    main()
