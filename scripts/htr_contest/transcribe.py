"""Transcribe register pages with one contest-tested reader, using the contest prompt unchanged.

Usage: python3 -I scripts/htr_contest/transcribe.py --reader NAME --out DIR PAGE... [--runs 1] [--retry-failed]

Each page runs blind and alone in an empty temp folder, with the same flags, timeouts and rate-limit backoff
as the contest. Results are cached as DIR/<page stem>/<reader>__runN.json: rerun the same command to resume.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from contestants import CONTESTANTS  # noqa: E402
from run import UsageLimit, _cli_version, run_one  # noqa: E402

PROMPT_FILE = Path(__file__).with_name("prompt.md")
# Every number in the skill's model-performance.md was measured with this prompt; test variants with
# `run.py --prompt FILE`, never by editing prompt.md.
VALIDATED_PROMPT_SHA256 = "8bc8b65ce9a0e3e2baf726277c68598f0bbbccd5ab5e390a92a99194dd0c0ea8"
PROMPT_GUIDE = ".claude/skills/decipher-historic-records/references/transcription-prompt.md"


def validated_prompt():
    prompt = PROMPT_FILE.read_text()
    if hashlib.sha256(prompt.encode()).hexdigest() != VALIDATED_PROMPT_SHA256:
        sys.exit(f"{PROMPT_FILE} is not the contest-validated prompt (sha256 {VALIDATED_PROMPT_SHA256[:12]}): "
                 f"restore it from git or from {PROMPT_GUIDE}")
    return prompt


def transcribe(reader, pages, out, runs=1, retry_failed=False, runner=run_one, cli_version=""):
    """Run `reader` on every page; returns the run records. Stops at the CLI's usage limit."""
    prompt = validated_prompt()
    for page in pages:
        for run_no in range(1, runs + 1):
            cached = Path(out) / page.stem / f"{reader.name}__run{run_no}.json"
            # run_one reuses a cached reading made with any prompt; a scan must not.
            if cached.exists() and json.loads(cached.read_text()).get("prompt_sha256") != VALIDATED_PROMPT_SHA256:
                sys.exit(f"{cached} was read with another prompt: move it aside, then rerun")
    records = []
    for page in pages:
        for run_no in range(1, runs + 1):
            records.append(runner(reader, {"image_id": page.stem, "image": str(page)}, run_no, out, prompt,
                                  retry_failed=retry_failed, cli_version=cli_version))
    return records


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reader", required=True, help="contestant name from contestants.py, e.g. claude-opus+tools")
    ap.add_argument("--out", required=True)
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--retry-failed", action="store_true")
    ap.add_argument("pages", nargs="+")
    args = ap.parse_args()
    roster = {c.name: c for c in CONTESTANTS}
    if args.reader not in roster:
        sys.exit(f"unknown reader {args.reader!r}; valid: {', '.join(roster)}")
    pages = [Path(p).resolve() for p in args.pages]
    missing = [str(p) for p in pages if not p.is_file()]
    if missing:
        sys.exit(f"missing pages: {missing}")
    if len({p.stem for p in pages}) != len(pages):
        sys.exit("two pages share a file name; results are cached by it")
    if args.runs < 1:
        sys.exit("--runs must be at least 1")
    reader = roster[args.reader]
    try:
        records = transcribe(reader, pages, args.out, args.runs, args.retry_failed,
                             cli_version=_cli_version(reader.cli))
    except UsageLimit:
        sys.exit(f"[usage limit] {reader.cli} quota spent; rerun the same command later to resume from the cache")
    failed = [r["image_id"] for r in records if r["status"] != "ok"]
    print(f"{len(records)} readings, {len(failed)} failed{': ' + ', '.join(failed) if failed else ''}. "
          f"Next: find_person.py coverage {args.out}")


if __name__ == "__main__":
    main()
