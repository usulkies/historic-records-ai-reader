# Validated transcription prompt and commands

**As of 2026-10-11.** Every number in `model-performance.md` was measured with exactly this prompt, these mode notes and these command lines, in the HTR contest of 2026-10-10/11. Change any of them and the scores, the picks and the scan recall no longer apply.

**In normal use, type none of this.** `scripts/htr_contest/transcribe.py` sends it byte for byte:
- it reads `scripts/htr_contest/prompt.md`, refuses to run if its sha256 is not the validated one (`VALIDATED_PROMPT_SHA256`), and builds each command from `contestants.py`;
- it refuses a cached reading made with another prompt;
- one page per call, in a fresh temp folder;
- the contest's timeouts, rate-limit backoff and cache.

This file is the record of what was validated, and the fallback for running a CLI by hand.

- **Prompt file:** `scripts/htr_contest/prompt.md`, sha256 `8bc8b65ce9a0e3e2baf726277c68598f0bbbccd5ab5e390a92a99194dd0c0ea8`. The contest's run records carry this hash as `prompt_sha256`.
  - `transcribe.py` checks it; by hand: `shasum -a 256 scripts/htr_contest/prompt.md`.
  - If the hash differs, prompt.md was edited after the contest. Restore it from git or from the block below.
  - `tests/test_transcribe.py` checks that prompt.md, the hash and the copies in this file agree.
- **Text sent** = `<prompt.md> + "\n\n" + <mode note> + "\n\nImage file: ./page.<ext>"`, exactly as `Contestant.command()` builds it. prompt.md already ends with a newline, so its last line is followed by two blank lines.
  - The image is copied unchanged into an empty temp folder as `page.<ext>` (extension in lower case).
  - The model's working folder is that temp folder.

## The prompt (verbatim copy of prompt.md)

```text
You are transcribing one page of a 19th/20th-century civil or religious vital-records register (births, marriages, deaths, or an alphabetical name index). The page image is the file named in the last line of this message. Read it with your file-reading tool. Do not search the web.

Transcribe literally: keep the original language, script and spelling. Do not translate, modernize or guess from outside knowledge.

Return ONLY a JSON array, one object per register entry (or per index line), with these keys:
- "register_no": entry number as written
- "surname", "given_names": of the main person (child, deceased, groom; for marriages put the bride in other_columns)
- "date_iso": main event date (birth, death or marriage, not circumcision or burial) as YYYY-MM-DD; write unknown digits as X; if two calendars are given, use the later (Gregorian) date
- "date_as_written": the date exactly as written
- "father", "mother": full names as written, or null
- "house_no", "place": as written, or null
- "other_columns": everything else in the row, as plain text

When you are sure of a field, give it as a plain string. When you are not sure, give it as an object:
{"best": "<most likely reading>", "alternatives": ["<up to 3 other plausible readings>"], "reason": "<one short sentence: what evidence you used>"}
Use the page's own evidence to resolve unclear letters: the same name or number written elsewhere in this entry or on this page (a father's surname, a witness, a repeated house number), and names and spellings common in the region and community. Only the first 3 alternatives count.

Write [illegible] for parts you cannot read at all. Use null for empty columns. No commentary outside the JSON.
```

## Mode notes (verbatim, `LOOK_NOTE` / `TOOLS_NOTE` in `contestants.py`)

Look mode (contestant `<name>`):
```text
Look at the image only: do not run commands or scripts, and do not create files.
```
Tools mode (contestant `<name>+tools`):
```text
You may run commands (for example Python with Pillow) to rotate, crop or enlarge parts of the image. Write files only inside the current folder. Do not access the network or any other folder.
```

## Why it must not be shortened or "improved"
- **The alternatives format won picks.** Its `{"best", "alternatives", "reason"}` objects matter:
  - claude-opus (look-only) scored 0.811 on the Russian narrative page with alternatives, and 0.705 from best readings only.
  - On the Polish page, without alternatives, gemini-3.1-pro+tools (best-only 0.805) would overtake claude-opus+tools (0.791).
  - The fast scan default for Polish acts, claude-sonnet, finds 0.84 of names only because its alternatives hold 4 of the 32 name readings. Its best readings alone find 0.72, and the pick would go to a model 4× slower.
  - `find_person.py` searches the alternatives, so dropping them loses names the reader did see.
- **"Only the first 3 alternatives count"** matches the scorer (`normalize.MAX_ALTERNATIVES`) and the matcher. More guesses would only add false hits.
- **"Transcribe literally ... original language, script and spelling"** keeps the clerk's spellings. `normalize()` then romanizes Cyrillic the way JRI-Poland indexes it, so index spellings and transcripts compare. This is the design rationale; it was not tested separately.
- **The in-page evidence sentence** ("the same name or number written elsewhere ...") and **`reason`** were part of the validated whole. They were never measured separately, so keep them.
- **Not tested.** Each of the following would need a new contest round:
  - naming the target person, place or date in the prompt (the risk: a reader that knows the name may "see" it);
  - a shorter names-only prompt;
  - several pages per call;
  - cropping the page for the reader;
  - another output format;
  - reading the page in this session or in a subagent, which knows the family surnames. That is why the contest ran Claude through the CLI.
- **To test a change** (for example a lighter names-only prompt for scans, which could be faster):
  1. Work on a git branch. Write the variant to its own file and run `run.py --prompt <file>`; never edit prompt.md, which `transcribe.py` would refuse to send.
  2. Move `reports/htr-contest/runs/` aside: `run.py` reuses cached runs and only warns when the prompt changed.
  3. Run the scan and proof picks on all keyed pages, 2 runs each.
  4. Adopt the variant only if accuracy, findability and `find_person.py eval` recall do not drop for any record type, and time falls clearly (≥ 25 %).

## Readers and model ids

| Contestant (also `+tools`) | CLI | `--model` / `-m` |
|---|---|---|
| claude-opus | claude | `claude-opus-5-5` |
| claude-sonnet | claude | `claude-sonnet-5-5` |
| claude-haiku | claude | `claude-haiku-5-5` |
| claude-fable | claude | `claude-fable-5-1` |
| gpt-6.1-sol | codex | `gpt-6.1-sol` |
| gpt-6-astra | codex | `gpt-6-astra` |
| gpt-6-sol | codex | `gpt-6-sol` |
| gpt-6-luna | codex | `gpt-6-luna` |
| gpt-5.6-sol | codex | `gpt-5.6-sol` |
| gpt-5.6-terra | codex | `gpt-5.6-terra` |
| gpt-5.6-luna | codex | `gpt-5.6-luna` |
| gemini-3.1-pro | agy | `gemini-3.1-pro-high` |
| gemini-3.8-flash | agy | `gemini-3.8-flash-high` |

## Exact command lines
Run each one inside the temp folder that holds only the page. `$TEXT` is the text described at the top; build it from the repo root, never by retyping (`$(cat …)` would drop prompt.md's final newline):
```sh
TEXT="$(python3 -I -c 'import sys; sys.path.insert(0, "scripts/htr_contest"); import contestants as c; note = c.TOOLS_NOTE if sys.argv[1] == "tools" else c.LOOK_NOTE; sys.stdout.write(open("scripts/htr_contest/prompt.md").read() + "\n\n" + note + "\n\nImage file: ./page.jpg")' look)"
```
Pass `tools` instead of `look` for a `+tools` reader, and change `page.jpg` to the copied file's name. For codex, the answer is written to `last_message.txt`; claude and agy print it. Tools mode streams a JSON event trace, and the answer is in its final `result` event.

- **claude, look mode** (timeout 900 s; example model `claude-opus-5-5`):
  ```sh
  claude -p "$TEXT" --model claude-opus-5-5 --tools Read --strict-mcp-config --setting-sources project --output-format text
  ```
- **codex, look mode** (timeout 900 s; example model `gpt-6.1-sol`):
  ```sh
  codex exec --skip-git-repo-check --ephemeral -s read-only -m gpt-6.1-sol -C "$PWD" -i page.jpg -o last_message.txt -c 'mcp_servers={}' -c features.plugins=false -c features.apps=false -c features.remote_plugin=false "$TEXT"
  ```
- **agy, look mode** (timeout 900 s; example model `gemini-3.1-pro-high`):
  ```sh
  agy -p "$TEXT" --model gemini-3.1-pro-high --mode plan --sandbox
  ```
- **claude, tools mode** (timeout 1800 s; example model `claude-opus-5-5`):
  ```sh
  claude -p "$TEXT" --model claude-opus-5-5 --tools Read,Bash,Write --allowedTools 'Read(./**),Edit(./**),Bash' --strict-mcp-config --setting-sources project --settings '{"sandbox": {"enabled": true, "autoAllowBashIfSandboxed": true, "filesystem": {"denyRead": ["<your-repo>"]}}}' --output-format stream-json --verbose
  ```
- **codex, tools mode** (timeout 1800 s; example model `gpt-6.1-sol`):
  ```sh
  codex exec --json --skip-git-repo-check --ephemeral -s workspace-write -m gpt-6.1-sol -C "$PWD" -i page.jpg -o last_message.txt -c 'mcp_servers={}' -c features.plugins=false -c features.apps=false -c features.remote_plugin=false "$TEXT"
  ```
- **agy, tools mode** (timeout 1800 s; example model `gemini-3.1-pro-high`):
  ```sh
  agy -p "$TEXT" --model gemini-3.1-pro-high --sandbox --dangerously-skip-permissions --output-format stream-json
  ```

## Isolation: what keeps the reader blind
- **The temp folder** holds only `page.<ext>`. The model gets no names, places or dates, and no access to this repo.
- **claude:**
  - `--setting-sources project` loads only project settings, and the empty temp folder has none, so user-level settings and the global `~/.claude/CLAUDE.md` are not loaded. This was verified in the contest.
  - **Remaining gap:** the auto-memory files under `~/.claude/projects/` name the family surnames. In tools mode the sandbox's `denyRead` covers only this repo, so a reader's Bash could still read them. The audit below checks for it.
  - `--strict-mcp-config` with no MCP config means no MCP servers.
  - Look mode allows only the `Read` tool.
  - In tools mode, `--allowedTools 'Read(./**),Edit(./**),Bash'`; Claude Code ignores `Write(...)` allow rules, and `Edit` covers writes. The sandbox `denyRead` on `<your-repo>` is needed because the sandbox alone still lets Bash read the user's files.
- **codex:**
  - `--ephemeral`, `-s read-only` (look) or `workspace-write` (tools), and `-C` = the temp folder.
  - `-c mcp_servers={}` and the `features.*=false` flags.
  - **Known gap:** codex still connected to the user's MCP servers at start-up despite `mcp_servers={}`. No MCP tool was ever called (traces audited).
  - Fix for the next codex run (untested): give it its own config home holding only the login. For example, `mkdir -p ~/.codex-htr && cp ~/.codex/auth.json ~/.codex-htr/`, then `CODEX_HOME=~/.codex-htr python3 -I scripts/htr_contest/transcribe.py ...`. Check the first run's `.stdout.txt` for MCP start-up lines.
- **agy:**
  - Look mode is `--mode plan --sandbox` (read-only plan mode).
  - Tools mode is `--sandbox --dangerously-skip-permissions`, so tool calls run unprompted inside the sandbox.
- **Audit:**
  - Contest: `report.py leaderboard` lists any tools-mode output that mentions the repo path under "Isolation warnings". There were none.
  - Scans: after each `transcribe.py` run, `grep -rlE '<your-repo>|\.claude/projects' <out> --exclude='*__run*.json*'` must print nothing (the run records are left out because their command line names the repo in `denyRead`). A hit means the reader looked outside its folder: drop that reading.

## Running limits
- **Timeouts:** 900 s look, 1800 s tools (`Contestant.timeout`).
  - gemini-3.1-pro+tools hit 1800 s twice on the Russian narrative page.
  - gemini-3.8-flash+tools was dropped as too slow (> 13 min per page; 24 min in a smoke test).
  - gpt-5.6-sol/terra/luna+tools have no result on the index page (1 failed run each).
- **One job at a time per CLI** (rate limits); different CLIs may run in parallel.
- **Pauses and backoff:** the harness pauses 5 s between runs. On a rate-limit reply it waits 30, 60 and then 120 s, logging `[rate-limit]`. After 4 tries it stops that CLI; rerun the same command later, and the cache resumes it.
- **Billing:** all runs used flat subscriptions: the Claude Code plan, the ChatGPT plan via codex, and Google AI Pro via agy.
  - The ChatGPT plan hit its usage limit after about 53 runs overnight.
  - Claude runs took 14–200 s per page.
  - Estimate a scan as pages × the reader's `time_s` before starting.

## Output
- **The reply** is a JSON array, one object per entry or index line, with the keys `register_no`, `surname`, `given_names`, `date_iso`, `date_as_written`, `father`, `mother`, `house_no`, `place` and `other_columns`. Any value may be a `{"best", "alternatives", "reason"}` object.
- **Parsing:** `parse.extract_entries` reads the reply (`transcribe.py` does this). A reply with no JSON array is a failed run: rerun it with `--retry-failed`, and never fix it by hand.
- **Records:** `<out>/<page stem>/<reader>__runN.json` holds the parsed entries, `status`, `prompt_sha256`, `cli_version`, `image_sha256`, `started_at` and `duration_s`. Next to it are `.raw.txt`, `.stdout.txt` and `.stderr.txt`, plus a `.workdir/` with the reader's crops for tools runs.
- **Citing a reading:** give the reader, mode, CLI version, prompt sha256 (first 12 characters) and date. A reading is a lead, like an index entry. Confirm it on the scan before anything goes into the tree.
