import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

import run
from contestants import CONTESTANTS, GENEALOGY_ROOT, LOOK_NOTE, TOOLS_NOTE, Contestant
from run import UsageLimit, run_one

def fake(stdout, code=0):
    return lambda cmd, **kw: subprocess.CompletedProcess(cmd, code, stdout=stdout, stderr="")

def setup(tmp_path):
    img = tmp_path / "page.jpg"
    img.write_bytes(b"jpg")
    return {"image_id": "t", "image": str(img), "lang": "de-pl", "source": {}, "entries": []}

def test_contestant_roster():
    assert len(CONTESTANTS) == 26 and len({c.name for c in CONTESTANTS}) == 26
    assert sum(c.mode == "tools" for c in CONTESTANTS) == 13
    assert all(c.name.endswith("+tools") == (c.mode == "tools") for c in CONTESTANTS)

def test_notes_in_text_and_masked():
    look, tools = Contestant("m", "claude", "x"), Contestant("m+tools", "claude", "x", "tools")
    assert f"P\n\n{LOOK_NOTE}\n\nImage file: ./p.jpg" == look.command("P", "p.jpg", "/w")[2]
    assert f"P\n\n{TOOLS_NOTE}\n\nImage file: ./p.jpg" == tools.command("P", "p.jpg", "/w")[2]
    assert (look.timeout, tools.timeout) == (900, 1800)

def test_tools_commands():
    t = lambda cli: Contestant("m+tools", cli, "mod", "tools").command("P", "p.jpg", "/w")  # noqa: E731
    settings = {"sandbox": {"enabled": True, "autoAllowBashIfSandboxed": True,
                            "filesystem": {"denyRead": [str(Path(run.__file__).resolve().parents[2])]}}}
    assert t("claude")[3:] == ["--model", "mod", "--tools", "Read,Bash,Write",
                              "--allowedTools", "Read(./**),Edit(./**),Bash",
                              "--strict-mcp-config", "--setting-sources", "project", "--settings",
                              json.dumps(settings), "--output-format", "stream-json", "--verbose"]
    assert GENEALOGY_ROOT == str(Path(run.__file__).resolve().parents[2])
    assert Contestant("m", "claude", "mod").command("P", "p.jpg", "/w")[-2:] == ["--output-format", "text"]
    assert t("agy")[3:] == ["--model", "mod", "--sandbox", "--dangerously-skip-permissions",
                           "--output-format", "stream-json"]
    assert t("codex")[t("codex").index("-s") + 1] == "workspace-write" and "--json" in t("codex")
    look = Contestant("m", "codex", "mod").command("P", "p.jpg", "/w")
    assert look[look.index("-s") + 1] == "read-only" and "--json" not in look
    assert Contestant("m", "agy", "mod").command("P", "p.jpg", "/w")[3:] == ["--model", "mod", "--mode", "plan", "--sandbox"]
    assert Contestant("m", "claude", "mod").command("P", "p.jpg", "/w")[3:6] == ["--model", "mod", "--tools"]

def test_codex_feature_flags_both_modes():
    for mode in ("look", "tools"):
        cmd = Contestant("m", "codex", "mod", mode).command("P", "p.jpg", "/w")
        pairs = list(zip(cmd, cmd[1:]))
        for flag in ("mcp_servers={}", "features.plugins=false", "features.apps=false", "features.remote_plugin=false"):
            assert ("-c", flag) in pairs

def test_run_one_passes_mode_timeout(tmp_path):
    seen = []

    def spy(cmd, **kw):
        seen.append(kw["timeout"])
        return subprocess.CompletedProcess(cmd, 0, stdout='[{"a": 1}]', stderr="")

    for c in (Contestant("m", "claude", "x"), Contestant("m+tools", "claude", "x", "tools")):
        run_one(c, setup(tmp_path), 1, tmp_path / "runs", "P", executor=spy, pause=0)
    assert seen == [900, 1800]

def test_tools_timeout_message(tmp_path):
    def timeout(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 1800)

    c = Contestant("m+tools", "claude", "x", "tools")
    assert "timeout 1800s" in run_one(c, setup(tmp_path), 1, tmp_path / "runs", "P", executor=timeout, pause=0)["error"]

def test_ok_run_saved(tmp_path):
    c = Contestant("claude-haiku", "claude", "claude-haiku-5-5")
    rec = run_one(c, setup(tmp_path), 1, tmp_path / "runs", "P", executor=fake('[{"surname": "X"}]'), pause=0)
    assert rec["status"] == "ok" and rec["entries"] == [{"surname": "X"}]
    for suffix in ("raw", "stdout", "stderr"):
        assert (tmp_path / f"runs/t/claude-haiku__run1.{suffix}.txt").exists()
    assert rec["model"] == "claude-haiku-5-5" and rec["exit_code"] == 0 and len(rec["image_sha256"]) == 64
    assert "<prompt>" in " ".join(rec["command"])
    assert (tmp_path / f"runs/prompts/{rec['prompt_sha256'][:12]}.md").read_text() == "P"

def test_empty_exit_zero_is_failed_and_not_rerun(tmp_path):
    c = Contestant("gemini-pro", "agy", "gemini-3.1-pro-high")
    key = setup(tmp_path)
    assert run_one(c, key, 1, tmp_path / "runs", "P", executor=fake(""), pause=0)["status"] == "failed"
    again = run_one(c, key, 1, tmp_path / "runs", "P", executor=fake('[{"a": 1}]'), pause=0)
    assert again["status"] == "failed"
    retried = run_one(c, key, 1, tmp_path / "runs", "P", executor=fake('[{"a": 1}]'), pause=0, retry_failed=True)
    assert retried["status"] == "ok"
    assert list((tmp_path / "runs/t").glob("gemini-pro__run1.json.prev-*"))  # failed attempt kept


LONG = "Transcribe this page carefully and return JSON."

def test_timeout_and_missing_cli_fail_without_crash(tmp_path):
    c = Contestant("claude-haiku", "claude", "claude-haiku-5-5")
    key = setup(tmp_path)

    def timeout(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 900, output=b"partial", stderr=None)

    rec = run_one(c, key, 1, tmp_path / "runs", LONG, executor=timeout, pause=0)
    assert rec["status"] == "failed" and rec["exit_code"] is None and "timeout" in rec["error"]
    for suffix in ("raw", "stdout", "stderr"):
        assert (tmp_path / f"runs/t/claude-haiku__run1.{suffix}.txt").exists()
    assert (tmp_path / "runs/t/claude-haiku__run1.stdout.txt").read_text() == "partial"

    def missing(cmd, **kw):
        raise FileNotFoundError("claude")

    rec = run_one(c, key, 2, tmp_path / "runs", LONG, executor=missing, pause=0)
    assert rec["status"] == "failed" and "FileNotFoundError" in rec["error"]

def test_codex_isolated_and_output_file_preferred(tmp_path):
    c = Contestant("gpt-6-luna", "codex", "gpt-6-luna")
    cmd = c.command(LONG, "page.jpg", "/w")
    assert cmd[cmd.index("-c") + 1] == "mcp_servers={}" and cmd.index("-c") < len(cmd) - 1

    def writes(cmd, cwd, **kw):
        open(f"{cwd}/last_message.txt", "w").write('[{"surname": "FromFile"}]')
        return subprocess.CompletedProcess(cmd, 0, stdout="noise", stderr="")

    rec = run_one(c, setup(tmp_path), 1, tmp_path / "runs", LONG, executor=writes, pause=0)
    assert rec["entries"] == [{"surname": "FromFile"}]

def test_prompt_masked_with_suffix_only_where_present(tmp_path):
    c = Contestant("claude-haiku", "claude", "claude-haiku-5-5")
    rec = run_one(c, setup(tmp_path), 1, tmp_path / "runs", LONG, executor=fake("[]"), pause=0)
    assert f"<prompt>\n\n{LOOK_NOTE}\n\nImage file: ./page.jpg" in rec["command"]
    assert "--model" in rec["command"]

def test_rate_limit_backoff(tmp_path, monkeypatch):
    sleeps = []
    monkeypatch.setattr("run.time.sleep", sleeps.append)
    c = Contestant("claude-haiku", "claude", "claude-haiku-5-5")
    always = fake("429 rate limit", code=1)
    with pytest.raises(UsageLimit):
        run_one(c, setup(tmp_path), 1, tmp_path / "runs", LONG, executor=always, pause=0)
    assert sleeps[:3] == [30, 60, 120]
    d = tmp_path / "runs/t"
    assert not (d / "claude-haiku__run1.json").exists()
    for suffix in ("raw", "stdout", "stderr"):
        assert (d / f"claude-haiku__run1.{suffix}.txt").exists()
    for k in (1, 2, 3):
        assert (d / f"claude-haiku__run1.attempt{k}.stdout.txt").exists()
        assert (d / f"claude-haiku__run1.attempt{k}.stderr.txt").exists()
    assert not (d / "claude-haiku__run1.attempt4.stdout.txt").exists()

def test_retry_archives_all_artifacts(tmp_path):
    c = Contestant("gemini-pro", "agy", "gemini-3.1-pro-high")
    key = setup(tmp_path)
    run_one(c, key, 1, tmp_path / "runs", LONG, executor=fake(""), pause=0)
    run_one(c, key, 1, tmp_path / "runs", LONG, executor=fake('[{"a": 1}]'), pause=0, retry_failed=True)
    for suffix in ("json", "raw.txt", "stdout.txt", "stderr.txt"):
        assert list((tmp_path / "runs/t").glob(f"gemini-pro__run1.{suffix}.prev-*"))


def test_executor_gets_replacing_utf8_decoding(tmp_path):
    seen = {}

    def spy(cmd, **kw):
        seen.update(kw)
        return subprocess.CompletedProcess(cmd, 0, stdout="[]", stderr="")

    run_one(Contestant("m", "claude", "x"), setup(tmp_path), 1, tmp_path / "runs", "P", executor=spy, pause=0)
    assert seen["encoding"] == "utf-8" and seen["errors"] == "replace" and seen["text"]


def test_default_executor_kills_process_group_on_timeout(tmp_path):
    started = time.time()
    with pytest.raises(subprocess.TimeoutExpired):
        run.run_in_group(["sh", "-c", "sleep 30 & sleep 30"], cwd=tmp_path, capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=0.5)
    assert time.time() - started < 10
    done = run.run_in_group(["sh", "-c", "printf 'ok\\377'"], cwd=tmp_path, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=10)
    assert done.returncode == 0 and done.stdout.startswith("ok")


def test_tools_workdir_kept_and_archived_on_retry(tmp_path):
    c = Contestant("m+tools", "claude", "x", "tools")
    key = setup(tmp_path)

    def tool_user(cmd, cwd, **kw):
        open(f"{cwd}/crop.png", "w").write("png")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    run_one(c, key, 1, tmp_path / "runs", "P", executor=tool_user, pause=0)
    kept = tmp_path / "runs/t/m+tools__run1.workdir"
    assert sorted(p.name for p in kept.iterdir()) == ["crop.png"]
    run_one(c, key, 1, tmp_path / "runs", "P", executor=fake("[]"), pause=0, retry_failed=True)
    assert not kept.exists() and list((tmp_path / "runs/t").glob("m+tools__run1.workdir.prev-*"))


def test_workdir_not_kept_when_only_image_and_codex_output(tmp_path):
    c = Contestant("g", "codex", "g")

    def writes(cmd, cwd, **kw):
        open(f"{cwd}/last_message.txt", "w").write("[]")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    run_one(c, setup(tmp_path), 1, tmp_path / "runs", "P", executor=writes, pause=0)
    assert not (tmp_path / "runs/t/g__run1.workdir").exists()

    def writes_more(cmd, cwd, **kw):
        open(f"{cwd}/last_message.txt", "w").write("[]")
        open(f"{cwd}/notes.txt", "w").write("n")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    run_one(c, setup(tmp_path), 2, tmp_path / "runs", "P", executor=writes_more, pause=0)
    kept = tmp_path / "runs/t/g__run2.workdir"
    assert sorted(p.name for p in kept.iterdir()) == ["last_message.txt", "notes.txt"]


def test_load_runs_ignores_workdir_copies(tmp_path):
    import report
    c = Contestant("m+tools", "claude", "x", "tools")

    def tool_user(cmd, cwd, **kw):
        open(f"{cwd}/x__run1.json", "w").write("not json {")
        return subprocess.CompletedProcess(cmd, 0, stdout=STREAM, stderr="")

    run_one(c, setup(tmp_path), 1, tmp_path / "runs", "P", executor=tool_user, pause=0)
    assert (tmp_path / "runs/t/m+tools__run1.workdir/x__run1.json").exists()
    assert list(report._load_runs(tmp_path)["t"]) == [("m+tools", 1)]


STREAM = "\n".join(json.dumps(x) for x in [
    {"type": "system", "subtype": "init"},
    {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash"}]}},
    {"type": "result", "subtype": "success", "result": '[{"surname": "Streamed"}]'},
]) + "\nnot json\n"


def test_claude_tools_raw_is_stream_result(tmp_path):
    c = Contestant("m+tools", "claude", "x", "tools")
    rec = run_one(c, setup(tmp_path), 1, tmp_path / "runs", "P", executor=fake(STREAM), pause=0)
    assert rec["entries"] == [{"surname": "Streamed"}]
    d = tmp_path / "runs/t"
    assert (d / "m+tools__run1.stdout.txt").read_text() == STREAM
    assert (d / "m+tools__run1.raw.txt").read_text() == '[{"surname": "Streamed"}]'
    no_result = run_one(c, setup(tmp_path), 2, tmp_path / "runs", "P",
                        executor=fake('{"type": "assistant"}\n[{"surname": "X"}]'), pause=0)
    assert no_result["status"] == "failed"


def test_usage_limit_stops_only_that_cli(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("run.time.sleep", lambda s: None)
    calls = []

    def executor(cmd, **kw):
        calls.append(cmd[0])
        if cmd[0] == "claude":
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="usage limit reached")
        return subprocess.CompletedProcess(cmd, 0, stdout="[]", stderr="")

    roster = [Contestant("c1", "claude", "x"), Contestant("g1", "agy", "y"), Contestant("c2", "claude", "x")]
    keys = [setup(tmp_path), dict(setup(tmp_path), image_id="u")]
    run.run_all(keys, roster, 1, tmp_path / "runs", "P", executor=executor, pause=0)
    assert calls.count("claude") == run.MAX_TRIES and calls.count("agy") == 2
    out = capsys.readouterr().out
    assert out.count("[stopped: usage limit] claude") == 1
    assert "skipping remaining claude runs this session" in out
    assert not list((tmp_path / "runs").glob("*/c*__run1.json"))


def test_cached_record_with_other_prompt_warns(tmp_path, capsys):
    c = Contestant("m", "claude", "x")
    run_one(c, setup(tmp_path), 1, tmp_path / "runs", "P", executor=fake("[]"), pause=0)
    capsys.readouterr()
    rec = run_one(c, setup(tmp_path), 1, tmp_path / "runs", "P2", executor=fake("[]"), pause=0)
    assert rec["status"] == "ok" and "prompt changed" in capsys.readouterr().out


def test_prompt_variant_comes_from_its_own_file(tmp_path, monkeypatch):
    variant = tmp_path / "variant.md"
    variant.write_text("Read the names only.\n")
    seen = []
    monkeypatch.setattr(run, "run_all", lambda keys, roster, runs, runs_dir, prompt, *a, **kw: seen.append(prompt))
    monkeypatch.setattr(run, "_cli_version", lambda cli: "test")
    monkeypatch.setattr(sys, "argv", ["run.py", "--only", "claude-opus", "--prompt", str(variant)])
    run.main()
    assert seen == ["Read the names only.\n"]


def test_only_unknown_name_exits_listing_valid(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["run.py", "--only", "nope"])
    with pytest.raises(SystemExit) as e:
        run.main()
    assert "nope" in str(e.value) and "claude-opus" in str(e.value)


def agy_result(status, response):
    """agy's real stream-json result line (trimmed from a live run): the answer is nested under "result"."""
    return json.dumps({"event": "result", "result": {
        "conversation_id": "fixture", "status": status, "response": response, "duration_seconds": 1468.74,
        "num_turns": 1, "usage": {"input_tokens": 445832, "output_tokens": 78497, "total_tokens": 524329}}})


AGY_STREAM = "\n".join([json.dumps({"event": "tool_call", "name": "shell"}),
                        agy_result("SUCCESS", '[{"surname": "Agy"}]')])


def test_agy_tools_raw_is_stream_response(tmp_path):
    c = Contestant("g+tools", "agy", "y", "tools")
    rec = run_one(c, setup(tmp_path), 1, tmp_path / "runs", "P", executor=fake(AGY_STREAM), pause=0)
    assert rec["entries"] == [{"surname": "Agy"}]
    assert (tmp_path / "runs/t/g+tools__run1.stdout.txt").read_text() == AGY_STREAM
    errored = AGY_STREAM + "\n" + agy_result("ERROR", '[{"surname": "Agy"}]')
    rec = run_one(c, setup(tmp_path), 2, tmp_path / "runs", "P", executor=fake(errored), pause=0)
    assert rec["status"] == "failed"
    look = Contestant("g", "agy", "y")
    assert run_one(look, setup(tmp_path), 1, tmp_path / "runs", "P", executor=fake('[{"a": 1}]'), pause=0)["status"] == "ok"


def test_codex_tools_raw_from_output_file_not_event_trace(tmp_path):
    c = Contestant("x+tools", "codex", "x", "tools")
    trace = json.dumps({"type": "item.completed", "item": {"text": "hi"}}) + "\n" + '[{"surname": "Trace"}]'
    rec = run_one(c, setup(tmp_path), 1, tmp_path / "runs", "P", executor=fake(trace), pause=0)
    assert rec["status"] == "failed"


def test_interrupt_kills_process_group(tmp_path, monkeypatch):
    procs = []

    def interrupted(self, timeout=None):
        procs.append(self)
        raise KeyboardInterrupt

    monkeypatch.setattr(subprocess.Popen, "communicate", interrupted)
    started = time.time()
    with pytest.raises(KeyboardInterrupt):
        run.run_in_group(["sh", "-c", "sleep 30 & sleep 30"], cwd=tmp_path, timeout=60)
    assert time.time() - started < 10 and procs[0].returncode == -9


def _writes_then(files, stdout="[]"):
    def executor(cmd, cwd, **kw):
        files(Path(cwd))
        return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")
    return executor


def test_workdir_symlinks_copied_not_followed(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("s")

    def files(cwd):
        (cwd / "link_dir").symlink_to(outside)
        (cwd / "dangling").symlink_to(tmp_path / "missing")
        (cwd / "crop.png").write_text("png")

    c = Contestant("m+tools", "claude", "x", "tools")
    rec = run_one(c, setup(tmp_path), 1, tmp_path / "runs", "P", executor=_writes_then(files, STREAM), pause=0)
    kept = tmp_path / "runs/t/m+tools__run1.workdir"
    assert (kept / "link_dir").is_symlink() and (kept / "dangling").is_symlink()
    assert (kept / "crop.png").read_text() == "png" and rec["status"] == "ok"
    assert (tmp_path / "runs/t/m+tools__run1.json").exists()


def test_workdir_copy_failure_never_blocks_record(tmp_path, monkeypatch):
    def broken(*a, **kw):
        raise OSError("disk full")

    monkeypatch.setattr(run.shutil, "copy2", broken)
    c = Contestant("m+tools", "claude", "x", "tools")
    rec = run_one(c, setup(tmp_path), 1, tmp_path / "runs", "P",
                  executor=_writes_then(lambda cwd: (cwd / "crop.png").write_text("png"), STREAM), pause=0)
    d = tmp_path / "runs/t"
    assert rec["status"] == "ok" and "disk full" in rec["workdir_error"]
    assert "disk full" in (d / "m+tools__run1.workdir-error.txt").read_text()
    for suffix in ("json", "raw.txt", "stdout.txt", "stderr.txt"):
        assert (d / f"m+tools__run1.{suffix}").exists()


def test_rate_limited_then_timeout_is_failed_not_stopped(tmp_path, monkeypatch):
    monkeypatch.setattr("run.time.sleep", lambda s: None)
    calls = []

    def executor(cmd, **kw):
        calls.append(1)
        if len(calls) == 1:
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="429 rate limit")
        raise subprocess.TimeoutExpired(cmd, 900)

    rec = run_one(Contestant("m", "claude", "x"), setup(tmp_path), 1, tmp_path / "runs", "P", executor=executor, pause=0)
    assert rec["status"] == "failed" and "timeout" in rec["error"]


def test_stream_limit_detection_ignores_tool_output(tmp_path, monkeypatch):
    monkeypatch.setattr("run.time.sleep", lambda s: None)
    trace = "\n".join(json.dumps(x) for x in [
        {"type": "user", "message": {"content": [{"type": "tool_result", "content": "disk quota: 3 GB"}]}},
        {"type": "result", "is_error": True, "result": "could not finish"}])
    calls = []

    def executor(cmd, **kw):
        calls.append(1)
        return subprocess.CompletedProcess(cmd, 1, stdout=trace, stderr="")

    c = Contestant("m+tools", "claude", "x", "tools")
    rec = run_one(c, setup(tmp_path), 1, tmp_path / "runs", "P", executor=executor, pause=0)
    assert rec["status"] == "failed" and len(calls) == 1
    limited = trace + "\n" + json.dumps({"type": "result", "is_error": True, "result": "usage limit reached"})
    with pytest.raises(UsageLimit):
        run_one(c, setup(tmp_path), 2, tmp_path / "runs", "P", executor=fake(limited, code=1), pause=0)
    agy = "\n".join([json.dumps({"event": "tool", "output": "quota"}),
                     agy_result("ERROR", "429 quota exceeded")])
    with pytest.raises(UsageLimit):
        run_one(Contestant("g+tools", "agy", "y", "tools"), setup(tmp_path), 1, tmp_path / "runs", "P",
                executor=fake(agy, code=1), pause=0)
