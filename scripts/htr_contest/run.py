"""Run every contestant on every keyed image, one at a time, caching each result.

Usage: python3 -I scripts/htr_contest/run.py [--only NAME] [--image ID] [--runs 2] [--retry-failed] [--prompt FILE]
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from contestants import CONTESTANTS  # noqa: E402
from parse import ParseError, extract_entries  # noqa: E402
from score import load_key  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports" / "htr-contest"
RATE_LIMIT_RE = re.compile(r"429|rate.?limit|quota|usage limit", re.I)
MAX_TRIES = 4


class UsageLimit(Exception):
    """Every retry of a run was still rate-limited: the CLI's quota is spent for this session."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _image_path(key) -> Path:
    src = Path(key["image"])
    return src if src.is_absolute() else ROOT / src


def _text(value) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else value


def _kill_group(proc):
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def run_in_group(cmd, timeout=None, capture_output=True, **kw):
    """subprocess.run, but the whole process group dies with it: CLIs spawn helpers that outlive their parent."""
    pipe = subprocess.PIPE if capture_output else None
    with subprocess.Popen(cmd, stdout=pipe, stderr=pipe, start_new_session=True, **kw) as proc:
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_group(proc)
            out, err = proc.communicate()
            raise subprocess.TimeoutExpired(cmd, timeout, output=out, stderr=err) from None
        except BaseException:
            # The new session keeps Ctrl-C from reaching the CLI, so it must be killed here.
            _kill_group(proc)
            proc.wait()
            raise
    return subprocess.CompletedProcess(cmd, proc.returncode, out, err)


def _keep_workdir(workdir: Path, keep: Path, output_file):
    """Copy the scratch files; returns an error message instead of raising so the run's record is still written."""
    try:
        files = [f for f in workdir.iterdir() if not f.name.startswith("page.")]
        if any(f.name != output_file for f in files):
            keep.mkdir(parents=True)
            for f in files:
                # Never follow links: a model could point one at files outside its folder.
                if f.is_dir() and not f.is_symlink():
                    shutil.copytree(f, keep / f.name, symlinks=True)
                else:
                    shutil.copy2(f, keep / f.name, follow_symlinks=False)
    except Exception as exc:  # noqa: BLE001
        return f"{type(exc).__name__}: {exc}"
    return None


def _execute(contestant, key, prompt, executor, keep):
    workdir = tempfile.mkdtemp(prefix="htr-")
    try:
        src = _image_path(key)
        image_name = "page" + src.suffix.lower()
        shutil.copy(src, Path(workdir) / image_name)
        command = contestant.command(prompt, image_name, workdir)
        started, waits, attempts = time.time(), [], []
        stdout = stderr = ""
        exit_code, exec_error, limited = None, None, False
        for attempt in range(MAX_TRIES):
            try:
                proc = executor(command, cwd=workdir, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=contestant.timeout)
            except subprocess.TimeoutExpired as exc:
                stdout, stderr, exit_code, limited = _text(exc.stdout), _text(exc.stderr), None, False
                exec_error = f"timeout {contestant.timeout}s"
                break
            except OSError as exc:
                stdout, stderr, exit_code, exec_error = "", "", None, f"{type(exc).__name__}: {exc}"
                limited = False
                break
            stdout, stderr, exit_code = proc.stdout, proc.stderr, proc.returncode
            limited = exit_code != 0 and bool(RATE_LIMIT_RE.search(contestant.limit_text(stdout) + stderr))
            if not limited or attempt == MAX_TRIES - 1:
                break
            wait = 30 * 2 ** attempt
            print(f"[rate-limit] {contestant.name}: waiting {wait}s (try {attempt + 1}/{MAX_TRIES})")
            attempts.append((attempt + 1, stdout, stderr))
            waits.append(wait)
            time.sleep(wait)
        out = Path(workdir) / contestant.output_file if contestant.output_file else None
        if out and out.exists():
            raw = out.read_text()
        else:
            raw = contestant.raw_reply(stdout)
        return {"raw": raw, "usage_limited": limited,
                "workdir_error": _keep_workdir(Path(workdir), keep, contestant.output_file),
                "stdout": stdout, "stderr": stderr, "exit_code": exit_code, "exec_error": exec_error,
                "command": [a.replace(prompt, "<prompt>") for a in command],
                "duration_s": round(time.time() - started - sum(waits), 1), "rate_limit_waits": waits,
                "attempts": attempts, "image_name": image_name}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _archive_previous(target: Path):
    # A retried failure keeps its earlier artifacts for later study instead of overwriting them.
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S.%f")
    for f in sorted(target.parent.glob(target.stem + ".*")):
        if ".prev-" in f.name:
            continue
        dest, n = f.with_name(f"{f.name}.prev-{stamp}"), 1
        while dest.exists():
            dest = f.with_name(f"{f.name}.prev-{stamp}-{n}")
            n += 1
        f.rename(dest)


def run_one(contestant, key, run_no, runs_dir, prompt, executor=run_in_group, pause=5,
            retry_failed=False, cli_version=""):
    target = Path(runs_dir) / key["image_id"] / f"{contestant.name}__run{run_no}.json"
    prompt_sha = _sha256(prompt.encode())
    if target.exists():
        cached = json.loads(target.read_text())
        if cached["status"] == "ok" or not retry_failed:
            if cached.get("prompt_sha256") != prompt_sha:
                print(f"warning: {target.name} cached under another prompt (prompt changed); reusing it")
            return cached
    # Also covers artifacts left by a run stopped at the usage limit, which has no record.
    _archive_previous(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    prompts_dir = Path(runs_dir) / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / f"{prompt_sha[:12]}.md").write_text(prompt)
    started_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    res = _execute(contestant, key, prompt, executor, target.with_suffix(".workdir"))
    for suffix in ("raw", "stdout", "stderr"):
        target.with_suffix(f".{suffix}.txt").write_text(res[suffix] or "")
    for k, out, err in res["attempts"]:
        target.with_suffix(f".attempt{k}.stdout.txt").write_text(out or "")
        target.with_suffix(f".attempt{k}.stderr.txt").write_text(err or "")
    if res["workdir_error"]:
        target.with_suffix(".workdir-error.txt").write_text(res["workdir_error"])
    if res["usage_limited"]:
        raise UsageLimit(contestant.cli)
    record = {"contestant": contestant.name, "cli": contestant.cli, "model": contestant.model,
              "cli_version": cli_version, "image_id": key["image_id"], "image": key["image"],
              "image_sha256": _sha256(_image_path(key).read_bytes()), "run": run_no,
              "prompt_sha256": prompt_sha, "started_at": started_at,
              **{k: res[k] for k in ("command", "exit_code", "duration_s", "rate_limit_waits")},
              "status": "ok", "error": None, "workdir_error": res["workdir_error"], "entries": []}
    try:
        record["entries"] = extract_entries(res["raw"])
    except ParseError as exc:
        record.update(status="failed", error=f"{exc}; exit={res['exit_code']}")
    if res["exec_error"]:
        record.update(status="failed", entries=[],
                      error=f"{res['exec_error']}; {record['error'] or ''}".rstrip("; "))
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=1))
    os.replace(tmp, target)
    print(f"{record['status']:6} {contestant.name} {key['image_id']} run{run_no} ({res['duration_s']}s)")
    time.sleep(pause)
    return record


def _cli_version(cli) -> str:
    try:
        return subprocess.run([cli, "--version"], capture_output=True, text=True, timeout=60).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return "missing"


def run_all(keys, contestants, runs, runs_dir, prompt, versions=None, **kw):
    stopped = set()
    for key in keys:
        for run_no in range(1, runs + 1):
            for c in contestants:
                if c.cli in stopped:
                    continue
                try:
                    run_one(c, key, run_no, runs_dir, prompt, cli_version=(versions or {}).get(c.cli, ""), **kw)
                except UsageLimit:
                    stopped.add(c.cli)
                    print(f"[stopped: usage limit] {c.cli} — skipping remaining {c.cli} runs this session")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--image")
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--retry-failed", action="store_true")
    ap.add_argument("--prompt", type=Path, default=Path(__file__).parent / "prompt.md",
                    help="a prompt variant to test; prompt.md itself must stay the validated prompt")
    args = ap.parse_args()
    names = [c.name for c in CONTESTANTS]
    if args.only and args.only not in names:
        sys.exit(f"unknown contestant {args.only!r}; valid names: {', '.join(names)}")
    prompt = args.prompt.read_text()
    keys = [k for k in map(load_key, sorted((REPORT_DIR / "key").glob("*.json")))
            if not args.image or k["image_id"] == args.image]
    roster = [c for c in CONTESTANTS if not args.only or c.name == args.only]
    versions = {cli: _cli_version(cli) for cli in {c.cli for c in roster}}
    run_all(keys, roster, args.runs, REPORT_DIR / "runs", prompt, versions, retry_failed=args.retry_failed)


if __name__ == "__main__":
    main()
