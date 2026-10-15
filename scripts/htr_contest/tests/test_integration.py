import json
import subprocess

import report
from contestants import CONTESTANTS
from run import run_one

ENTRY = '[{"register_no": "6", "surname": "%s", "given_names": "Dawid"}]'
REPLIES = {"claude-haiku": ENTRY % "Ostern", "claude-sonnet": ENTRY % "Ostern", "gemini-3.1-pro": ENTRY % "Osten"}


def fake_cli(cmd, cwd, **kw):
    if cmd[0] == "codex":
        open(f"{cwd}/last_message.txt", "w").write(ENTRY % "Ostern")
        return subprocess.CompletedProcess(cmd, 0, stdout="log noise", stderr="")
    if "stream-json" in cmd:
        stream = json.dumps({"type": "result", "result": ENTRY % "Ostern"})
        return subprocess.CompletedProcess(cmd, 0, stdout=stream, stderr="")
    name = next(c.name for c in CONTESTANTS if c.model == cmd[cmd.index("--model") + 1] and c.mode == "look")
    return subprocess.CompletedProcess(cmd, 0, stdout=REPLIES[name], stderr="")


def test_runs_flow_into_flags_and_leaderboard(tmp_path, monkeypatch):
    img = tmp_path / "page.jpg"
    img.write_bytes(b"jpg")
    key = {"image_id": "t", "image": str(img), "lang": "de-pl", "source": "s",
           "entries": [{"register_no": "6", "surname": "Osten", "given_names": "Dawid"}]}
    (tmp_path / "key").mkdir()
    (tmp_path / "key" / "t.json").write_text(json.dumps(key))
    monkeypatch.setattr(report, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(report, "ADJ_FILE", tmp_path / "adjudication.json")
    monkeypatch.setattr(report, "SCORES_DIR", tmp_path / "scores")
    names = ["claude-haiku", "claude-sonnet", "gemini-3.1-pro", "gpt-6-luna", "claude-opus+tools"]
    for c in (c for c in CONTESTANTS if c.name in names):
        assert run_one(c, key, 1, tmp_path / "runs", "P", executor=fake_cli, pause=0)["status"] == "ok"

    report.cmd_flags()
    flags = json.loads((tmp_path / "adjudication.json").read_text())
    assert [(f["entry_idx"], f["field"], f["majority_value"]) for f in flags] == [(0, "surname", "Ostern")]

    report.cmd_leaderboard()
    board = (tmp_path / "leaderboard.md").read_text()
    for name in [*names, "vote", "vote+tools"]:
        assert f"| {name} |" in board
    assert "Warning: missing runs" not in board
    assert (tmp_path / "scores" / "fields.csv").read_text().count("\n") > 1
