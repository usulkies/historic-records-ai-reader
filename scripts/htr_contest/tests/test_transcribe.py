import functools
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

import find_person
import transcribe
from contestants import CONTESTANTS, LOOK_NOTE, TOOLS_NOTE
from run import run_one

READER = next(c for c in CONTESTANTS if c.name == "claude-sonnet")
GUIDE = Path(__file__).resolve().parents[3] / transcribe.PROMPT_GUIDE
REPLY = json.dumps([{"register_no": "7", "surname": {"best": "Kac", "alternatives": ["Katz"], "reason": "r"}}])


def test_sends_the_contest_prompt_unchanged(tmp_path):
    seen = []
    page = tmp_path / "AGAD_300_1363_0007.jpg"
    page.write_bytes(b"jpg")
    transcribe.transcribe(READER, [page], tmp_path / "out", runs=2,
                          runner=lambda *a, **kw: seen.append((a, kw)) or {"status": "ok"})
    assert [a[2] for a, _ in seen] == [1, 2]
    assert all(a[1] == {"image_id": "AGAD_300_1363_0007", "image": str(page)} for a, _ in seen)
    assert all(hashlib.sha256(a[4].encode()).hexdigest() == transcribe.VALIDATED_PROMPT_SHA256 for a, _ in seen)


def test_validated_prompt_and_its_reference_copy_agree():
    prompt = transcribe.PROMPT_FILE.read_text()
    assert hashlib.sha256(prompt.encode()).hexdigest() == transcribe.VALIDATED_PROMPT_SHA256
    blocks = re.findall(r"^```text\n(.*?)^```$", GUIDE.read_text(), re.S | re.M)
    assert blocks[:3] == [prompt, LOOK_NOTE + "\n", TOOLS_NOTE + "\n"]


def test_refuses_an_edited_prompt(tmp_path, monkeypatch):
    variant = tmp_path / "prompt.md"
    variant.write_text(transcribe.PROMPT_FILE.read_text() + "Read only the names.\n")
    monkeypatch.setattr(transcribe, "PROMPT_FILE", variant)
    with pytest.raises(SystemExit, match="not the contest-validated prompt"):
        transcribe.transcribe(READER, [], tmp_path / "out", runner=lambda *a, **kw: {"status": "ok"})


def test_refuses_a_cached_reading_made_with_another_prompt(tmp_path):
    page = tmp_path / "p0007.jpg"
    page.write_bytes(b"jpg")
    cached = tmp_path / "out" / "p0007" / "claude-sonnet__run1.json"
    cached.parent.mkdir(parents=True)
    cached.write_text(json.dumps({"status": "ok", "prompt_sha256": "0" * 64, "entries": []}))
    with pytest.raises(SystemExit, match="read with another prompt"):
        transcribe.transcribe(READER, [page], tmp_path / "out", runner=lambda *a, **kw: {"status": "ok"})


def test_records_are_what_find_person_reads(tmp_path):
    page = tmp_path / "p0007.jpg"
    page.write_bytes(b"jpg")
    fake = lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout=REPLY, stderr="")  # noqa: E731
    out = tmp_path / "out"
    transcribe.transcribe(READER, [page], out, runner=functools.partial(run_one, executor=fake, pause=0))
    assert (out / "p0007" / "claude-sonnet__run1.json").is_file()
    found = find_person.match(find_person.load_pages([out]),
                              find_person.compile_query(find_person.validate_query({"surnames": ["Katz"]})))
    assert [(c["page"], c["register_no"], c["tier"]) for c in found] == [("p0007", "7", "B")]


@pytest.mark.parametrize("argv, message", [
    (["--reader", "nobody", "--out", "o", "x.jpg"], "unknown reader"),
    (["--reader", "claude-sonnet", "--out", "o", "missing.jpg"], "missing pages"),
])
def test_rejects_bad_arguments(monkeypatch, argv, message):
    monkeypatch.setattr(sys, "argv", ["transcribe.py", *argv])
    with pytest.raises(SystemExit, match=message):
        transcribe.main()


def test_rejects_pages_sharing_a_cache_name(monkeypatch, tmp_path):
    for d in ("a", "b"):
        (tmp_path / d).mkdir()
        (tmp_path / d / "0005.jpg").write_bytes(b"jpg")
    monkeypatch.setattr(sys, "argv", ["transcribe.py", "--reader", "claude-sonnet", "--out", "o",
                                      str(tmp_path / "a" / "0005.jpg"), str(tmp_path / "b" / "0005.jpg")])
    with pytest.raises(SystemExit, match="share a file name"):
        transcribe.main()
