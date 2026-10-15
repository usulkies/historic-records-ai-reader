"""The contest roster and how each CLI is invoked headlessly on one image."""
import json
from dataclasses import dataclass
from pathlib import Path

LOOK_NOTE = "Look at the image only: do not run commands or scripts, and do not create files."
TOOLS_NOTE = ("You may run commands (for example Python with Pillow) to rotate, crop or enlarge parts of the "
              "image. Write files only inside the current folder. Do not access the network or any other folder.")
GENEALOGY_ROOT = str(Path(__file__).resolve().parents[2])
# The sandbox alone still lets Bash read the user's files; denyRead walls off the research repo.
CLAUDE_SANDBOX = json.dumps({"sandbox": {"enabled": True, "autoAllowBashIfSandboxed": True,
                                         "filesystem": {"denyRead": [GENEALOGY_ROOT]}}})
CODEX_OFF = ["-c", "mcp_servers={}", "-c", "features.plugins=false", "-c", "features.apps=false",
             "-c", "features.remote_plugin=false"]


@dataclass(frozen=True)
class Contestant:
    name: str
    cli: str
    model: str
    mode: str = "look"

    @property
    def output_file(self):
        return "last_message.txt" if self.cli == "codex" else None

    @property
    def streams(self) -> bool:
        """Tools runs of claude and agy stream a JSON event trace so the tool calls are kept."""
        return self.mode == "tools" and self.cli in ("claude", "agy")

    def _result_event(self, stdout):
        """The final result event; for agy, its nested "result" object, which holds status and response."""
        if self.cli == "claude":
            return _last_event(stdout, lambda e: e.get("type") == "result")
        event = _last_event(stdout, lambda e: e.get("event") == "result")
        return event["result"] if event and isinstance(event.get("result"), dict) else None

    def raw_reply(self, stdout: str) -> str:
        """The answer text in stdout."""
        if self.mode != "tools":
            return stdout
        if not self.streams:
            return ""  # codex: the answer is only in the -o file; stdout is the --json event trace
        event = self._result_event(stdout) or {}
        if self.cli == "claude":
            return event["result"] if isinstance(event.get("result"), str) else ""
        return str(event.get("response") or "") if event.get("status") != "ERROR" else ""

    def limit_text(self, stdout: str) -> str:
        """Where a usage-limit message can appear; tool output in a trace may mention "quota" innocently."""
        if not self.streams:
            return stdout
        event = self._result_event(stdout)
        return json.dumps(event, ensure_ascii=False) if event else ""

    @property
    def timeout(self) -> int:
        return 1800 if self.mode == "tools" else 900

    def command(self, prompt: str, image_name: str, workdir: str) -> list[str]:
        tools = self.mode == "tools"
        text = f"{prompt}\n\n{TOOLS_NOTE if tools else LOOK_NOTE}\n\nImage file: ./{image_name}"
        if self.cli == "claude":
            cmd = ["claude", "-p", text, "--model", self.model, "--tools", "Read,Bash,Write" if tools else "Read"]
            if tools:
                # Claude Code ignores Write(...) allow rules; Edit(...) is the rule that covers writes.
                cmd += ["--allowedTools", "Read(./**),Edit(./**),Bash"]
            cmd += ["--strict-mcp-config", "--setting-sources", "project"]
            if tools:
                return cmd + ["--settings", CLAUDE_SANDBOX, "--output-format", "stream-json", "--verbose"]
            return cmd + ["--output-format", "text"]
        if self.cli == "codex":
            return ["codex", "exec", *(["--json"] if tools else []), "--skip-git-repo-check", "--ephemeral",
                    "-s", "workspace-write" if tools else "read-only",
                    "-m", self.model, "-C", workdir, "-i", image_name, "-o", self.output_file,
                    *CODEX_OFF, text]
        if tools:
            return ["agy", "-p", text, "--model", self.model, "--sandbox", "--dangerously-skip-permissions",
                    "--output-format", "stream-json"]
        # Plan mode keeps agy read-only; see Task 5 Step 6 for the verified flags.
        return ["agy", "-p", text, "--model", self.model, "--mode", "plan", "--sandbox"]


def _last_event(stdout, is_result):
    """The last result event of a JSON-lines stream; None when the stream never finished."""
    result = None
    for line in (stdout or "").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and is_result(event):
            result = event
    return result


_LOOK = (
    [Contestant(f"claude-{m}", "claude", f"claude-{m}-5-5") for m in ("opus", "sonnet", "haiku")]
    + [Contestant("claude-fable", "claude", "claude-fable-5-1")]
    + [Contestant(m, "codex", m) for m in ("gpt-6.1-sol", "gpt-6-astra", "gpt-6-sol", "gpt-6-luna",
                                           "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna")]
    + [Contestant("gemini-3.1-pro", "agy", "gemini-3.1-pro-high"),
       Contestant("gemini-3.8-flash", "agy", "gemini-3.8-flash-high")]
)
CONTESTANTS = _LOOK + [Contestant(f"{c.name}+tools", c.cli, c.model, "tools") for c in _LOOK]
