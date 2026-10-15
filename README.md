# Historic records AI reader

A [Claude Code](https://claude.com/claude-code) skill and scripts for reading scanned genealogical records with AI: civil and religious registers of births, marriages and deaths, metrical books, alphabetical indexes and gravestones. It was built for Jewish family research in Poland, Galicia and the Russian Empire, and is shared freely for anyone doing similar work.

## What it does
- **Blind transcription.** `scripts/htr_contest/transcribe.py` sends one page at a time to an AI reader, with a fixed prompt. Each run happens in an empty folder, so the reader never knows whom you are looking for. Every register entry comes back as JSON. When the reader is unsure of a field, it returns the best reading, up to three alternatives, and the reason.
- **Finding a person.** `scripts/htr_contest/find_person.py` searches the transcriptions by spelling distance and Daitch–Mokotoff sound code. It checks every alternative reading too, and it handles Polish and Russian case endings. Give it the parents' given names and it finds people even when the surname was misread.
- **Choosing a model.** The skill (`.claude/skills/decipher-historic-records/SKILL.md`) says which reader to use for which record type. The picks come from a blind contest of 13 model configurations against hand-made answer keys; the results are in `references/model-performance.md`.
- **Proof.** The skill also covers checking a reading against the image, grading the evidence (confirmed / probable / possible / speculative), and format sheets for several register layouts.

## Using it
1. Install [Claude Code](https://claude.com/claude-code) and clone this repository. The skill loads automatically when you work inside the folder.
2. Ask Claude Code, in plain language, to read a scan or to look for a person in a set of pages. The skill guides it through the steps.
3. To run the scripts directly:
   ```
   python3 -I scripts/htr_contest/transcribe.py --reader claude-opus+tools --out transcripts/<book> scans/<book>/*.jpg
   python3 -I scripts/htr_contest/find_person.py match query.json transcripts/<book>
   ```
   The reader names are listed in `scripts/htr_contest/contestants.py`. They need the matching command-line tools installed and signed in: `claude`, and optionally `codex` or `gemini`.
4. Tests: `python3 -m pytest scripts/htr_contest/tests`.

## Honest limits
- AI readings are machine output. Treat a single reading as a finding aid. Before relying on a record, prove it on the image and with a second reader.
- The contest keys are small (a few pages per record type). Record types that were not tested are marked as such in the skill.
- Do not edit `prompt.md`: the scores apply only to the exact validated prompt, and `transcribe.py` refuses to run with a changed one.

## Credits and licence
Written with Claude Code (Anthropic) for and with Uziel Sulkies (JewishGen researcher #314258). MIT licence: see `LICENSE`.
