# AI readers: model performance by record type

**As of 2026-10-11.** Read this on demand, when choosing an AI reader or updating the picks. SKILL.md carries the picks. This file holds the evidence behind them, the rules that produce them, and how to refresh them when a new model or a new kind of record arrives.

Source: the HTR model contest of 2026-10-10/11.
- Design: `docs/superpowers/specs/2026-10-10-htr-model-contest-design.md`.
- Leaderboard (all pages pooled): `reports/htr-contest/leaderboard.md`.
- Data: `reports/htr-contest/scores/model-performance.json` (per contestant × record type) and `scores/fields.csv` (per field reading).

Method:
- 13 models × 2 modes. **look** = the model only views the image. **+tools** = it may also crop, rotate and zoom with Python in its temp folder.
- Each contestant read each of 4 keyed pages twice, blind (no names, places or dates), with the prompt in `transcription-prompt.md`.
- Scores compare the readings with the published JRI-Poland index for the page, after adjudication. There was 1 ruling: on the index page, in the entry for act 21 (Гольдбергъ), JRI has "Хава" but the scan reads "Хана" (key wrong).

## 1. Picks

**Scan mode**: find one person in many pages. Metric = `name_findable_with_alts`, the share of name fields where the best reading **or an alternative** is within ~1 letter in 5 of the index.

| Record type | Default | Fallback 1 | Fallback 2 | Best on another CLI |
|---|---|---|---|---|
| galician_table (**provisional**) | claude-sonnet · 1.00 · 18 s | claude-opus+tools · 1.00 · 30 s · 58k tok | claude-sonnet+tools · 1.00 · 21 s · 42k | gemini-3.1-pro · 1.00 · 100 s |
| polish_narrative | claude-sonnet · 0.84 · 33 s | claude-fable+tools · 0.97 · 129 s · 254k | claude-fable · 0.88 · 85 s | none close (gemini-3.1-pro 0.56 · 154 s ⁺) |
| russian_narrative (**provisional**) | claude-opus · 0.69 · 37 s | claude-opus+tools · 0.56 · 59 s · 125k | claude-fable+tools · 0.56 · 200 s · 456k | none close (gpt-6.1-sol+tools 0.44 · 120 s ⁺) |
| russian_index | claude-opus+tools · 0.90 · 66 s · 87k | claude-fable+tools · 0.92 · 178 s · 322k | claude-fable · 0.75 · 126 s ⁺ | none close (gpt-6-astra+tools 0.55 · 169 s ⁺) |

**Proof mode**: transcribe one located entry for a conclusion. Metric = `accuracy`.

| Record type | Default | Fallback 1 | Fallback 2 | Second reader on another CLI |
|---|---|---|---|---|
| galician_table (**provisional**) | claude-opus+tools · 1.00 · 30 s · 58k tok | claude-sonnet · 1.00 · 18 s | claude-sonnet+tools · 1.00 · 21 s · 42k | gemini-3.1-pro · 1.00 · 100 s |
| polish_narrative | claude-fable+tools · 0.92 · 129 s · 254k | claude-opus+tools · 0.84 · 59 s · 137k | claude-fable · 0.86 · 85 s | gemini-3.1-pro+tools · 0.82 · 418 s · 681k |
| russian_narrative (**provisional**) | claude-opus · 0.81 · 37 s | claude-opus+tools · 0.77 · 59 s · 125k | gpt-6.1-sol+tools · 0.77 · 120 s · 283k | gpt-6.1-sol+tools (same) |
| russian_index | claude-opus+tools · 0.895 · 66 s · 87k | claude-fable+tools · 0.855 · 178 s · 322k | claude-fable · 0.76 · 126 s ⁺ | gpt-6-astra+tools · 0.61 · 169 s · 277k ⁺ |

Reading a cell:
- Each cell gives the contestant, its metric, seconds per page, and tokens per page where the CLI reported them. Look-only Claude and Gemini runs report no tokens.
- ⁺ = outside the window (rule 2 below), filled in because fewer models came close.
- On index pages, proof mode should read the act an index line points to: the line itself is not evidence of the event.

### How the picks are computed (`python3 -I scripts/htr_contest/performance.py picks`)
1. **Eligible:** no failed run and 2 runs on that record type. Scan mode also requires ≤ 300 s per page; at 300 s, a 150-page year takes 12.5 h.
2. **Window:** metric ≥ best − 0.15 (scan) or best − 0.10 (proof).
3. **Rank** the window by **value = metric − w · log2(max(time_s, 30) / 30)**. Each doubling of time above 30 s costs w: **w = 0.10 for scan, 0.05 for proof**. Below 30 s, CLI start-up dominates. Ties (to 3 decimals):
   - scan: a look-only model first (a tools run loops over crops and spends far more quota per page), then the higher accuracy over all 4 pages, then the faster model;
   - proof: the higher accuracy over all 4 pages, because an easy page cannot rank the leaders, then the faster model.
4. If fewer than 3 models are in the window, the rest are filled by metric alone (⁺).
5. **Best on another CLI** applies the same rule to the other CLIs' models. Use it when one plan's quota is spent, or as an independent second reader in proof mode (section 4).

Why the two modes differ:
- A scan's cost multiplies by the page count, so time weighs double.
- A scan only needs the person's names to be findable; dates, house numbers and the confident-wrong penalty do not matter. The metric counts alternatives because `find_person.py` searches them.
- Proof mode needs every field right.

Why tokens are not in the formula:
- Look-only Claude and Gemini runs did not report tokens.
- Counts are not comparable across CLIs (Claude's include cache reads).
- Everything was billed to flat plans, so the real costs are quota and wall-clock time. Time stands in for both.
- Tools runs used 25.7k–1.77M tokens per page; that is why scan ties go to look-only (rule 3).

### Notes on the picks
- **galician_table is provisional.** The key has 2 entries and 6 fields (4 of them names).
  - 7 of 25 contestants (5 models) averaged 1.00 over 2 runs, and 12 had at least one perfect run, so the page cannot rank the leaders.
  - Scan ties go to look-only, so claude-sonnet (18 s) is the scan default and claude-opus+tools, the strongest reader over all pages, is fallback 1. Proof ties go to all-pages accuracy, so claude-opus+tools leads there.
  - claude-sonnet's look-only 1.00 was checked: it read only `page.jpg`, and its answer has details that are not in the key.
  - Key a harder Galician page (≥ 5 entries, every column) before trusting this row.
- **polish_narrative:**
  - claude-sonnet is the scan default **only because of its alternatives**. Its best readings find 0.72 of names; its alternatives raise that to 0.84, and the replay found all 4 people in both runs and both spellings (16 queries).
  - With best readings only, the default would be claude-fable+tools (129 s, 254k tokens per page).
  - For proof, claude-fable+tools leads (0.924 vs 0.860 for claude-fable, about one name), and only 1 of its 32 name readings was not findable.
- **russian_narrative is the hardest page, and provisional.** It has 2 acts (8 name fields). The scan default leads fallback 1 by 2 of 16 name readings, and the three proof picks are less than one name apart.
  - The best reader, claude-opus look-only, finds 0.69 of names. For claude-opus and claude-sonnet, tools mode does worse on this page; for claude-fable it does better (0.56 vs 0.31 findable).
  - Fallback 1 (claude-opus+tools) found only half the people when the query had no parents' names (section 3).
  - A no-hit here is weak evidence: re-read the likeliest pages with fallback 1 before logging a negative.
  - The mother's name is the field read worst.
- **russian_index** is the alphabetical index at the back of a Russian-era volume, about 30 names per page.
  - claude-opus+tools found 1.00 of the people in the replay; claude-sonnet found 0.68. Do not scan index pages with claude-sonnet.
  - Read a year's index pages first and open the acts they name first. If none is the person, scan every act page: an index hit may be a relative or namesake, and indexes omit and misread entries.
  - Act numbers on index lines were not scored (section 7).
- **Avoid** for every record type tested:
  - claude-haiku: best 0.645, and ≤ 0.357 off the Galician page.
  - all gpt-5.6-* models: best 0.635.
  - gpt-6-luna: best 0.510, and ≤ 0.125 off the Galician page.
  - look-only GPT models on narrative pages: ≤ 0.437.
- **Gemini** reads the Galician and Polish pages well but is slow: 100–607 s per page look-only, 307–1254 s with tools.
  - gemini-3.1-pro+tools hit the 30-minute cap twice on the Russian narrative page.
  - gemini-3.8-flash+tools was dropped (> 13 min per page; 24 min in a smoke test).
- **A majority vote does not pay.** vote+tools scored 0.805 overall, against 0.878 for the best single model, and it needs every model to run.
- **Every scan pick is a Claude model.** If the Claude plan limit hits mid-scan, pause and resume (`transcribe.py` caches finished pages). Never switch a scan to a model outside the window: its no-hit is worth little.

## 2. Did the alternatives format decide the picks?
Yes, in places. That is why the prompt must stay verbatim (`transcription-prompt.md`).

| Record type | Mode | With alternatives (as scored) | Best reading only |
|---|---|---|---|
| polish_narrative | scan | claude-sonnet → claude-fable+tools → claude-fable | claude-fable+tools → claude-opus+tools → claude-fable |
| polish_narrative | proof | claude-fable+tools → claude-opus+tools → claude-fable | claude-fable+tools → claude-fable ⁺ → gemini-3.1-pro+tools ⁺ (claude-opus+tools 0.791 falls below gemini's 0.805) |
| russian_narrative | proof | claude-opus 0.811 leads | claude-opus 0.705 still leads (gpt-6.1-sol+tools 0.660) |
| other types | both | unchanged | unchanged |

What the alternatives earned the winners (accuracy − best-only accuracy):
- claude-opus (look-only), Russian narrative: +0.106.
- claude-opus+tools: Polish +0.050, index +0.044.
- claude-fable+tools, Polish: +0.012.
- claude-sonnet, Polish findability: +0.125, i.e. 4 of 32 name readings were findable only through an alternative.

Rescue rates differ by provider. The alternatives of claude-opus, claude-fable and claude-sonnet rescue 6–16 % of their wrong hedged fields. Those of the two best GPT readers rescue ≤ 2 %: GPT alternatives rarely hold the answer.

## 3. Scan replay: does the matcher find the person?
`python3 -I scripts/htr_contest/find_person.py eval` replays every key person as a search over each contestant's real readings (best + alternatives, from `scores/fields.csv`). Each person is searched twice:
- in the index's spelling;
- in a researcher's spelling: English transliteration for Cyrillic (Shidlover), and forms like Wegbreit, Moshe or Dvora for Latin script.

**Queries include the key's father and mother given names.** Those names find the entry when the surname is misread (tier B, "two other names"). In a year-long scan they are often unknown; `eval --lean` searches the surname and given name only.

Each cell shows: **found at tier A or B / found at tier A · false hits per query**. False hits are counted among the 37 other key entries.

| Contestant | galician_table | polish_narrative | russian_narrative | russian_index |
|---|---|---|---|---|
| claude-fable+tools | 1.00 / 1.00 · 0.00 | 1.00 / 1.00 · 0.38 | 1.00 / 0.50 · 0.00 | 0.97 / 0.87 · 0.97 |
| claude-opus+tools | 1.00 / 1.00 · 0.25 | 1.00 / 1.00 · 0.12 | 1.00 / 0.50 · 0.00 | 1.00 / 0.83 · 1.08 |
| claude-opus | 1.00 / 1.00 · 0.25 | 1.00 / 0.88 · 0.19 | 1.00 / 1.00 · 0.50 | 0.83 / 0.70 · 1.22 |
| claude-fable | 1.00 / 1.00 · 0.25 | 1.00 / 0.94 · 0.25 | 1.00 / 0.50 · 0.00 | 0.85 / 0.75 · 0.95 |
| claude-sonnet | 1.00 / 1.00 · 0.25 | 1.00 / 1.00 · 0.44 | 1.00 / 1.00 · 0.00 | 0.68 / 0.62 · 1.03 |
| claude-sonnet+tools | 1.00 / 1.00 · 0.25 | 0.88 / 0.75 · 0.38 | 1.00 / 1.00 · 0.50 | 0.82 / 0.70 · 0.97 |
| gpt-6.1-sol+tools | 1.00 / 0.50 · 0.00 | 0.75 / 0.44 · 0.19 | 1.00 / 1.00 · 0.25 | 0.67 / 0.57 · 0.57 |
| gpt-6-astra+tools | 1.00 / 0.50 · 0.00 | 0.88 / 0.50 · 0.12 | 1.00 / 0.50 · 0.25 | 0.72 / 0.60 · 0.63 |
| gemini-3.1-pro+tools | 1.00 / 1.00 · 0.00 | 1.00 / 0.81 · 0.12 | 0.50 / 0.25 · 0.00 | 0.60 / 0.47 · 0.73 |
| gemini-3.8-flash | 1.00 / 1.00 · 0.00 | 0.88 / 0.75 · 0.25 | 0.50 / 0.00 · 0.00 | 0.47 / 0.35 · 0.74 |
| gemini-3.1-pro | 1.00 / 1.00 · 0.00 | 1.00 / 0.56 · 0.12 | 0.75 / 0.25 · 0.00 | 0.42 / 0.32 · 0.53 |
| gpt-6-sol+tools | 1.00 / 0.50 · 0.00 | 1.00 / 0.56 · 0.12 | 0.75 / 0.25 · 0.12 | 0.52 / 0.38 · 0.84 |
| gpt-6-astra | 1.00 / 0.00 · 0.12 | 0.69 / 0.25 · 0.25 | 1.00 / 0.00 · 0.00 | 0.35 / 0.28 · 0.55 |
| gpt-6.1-sol | 1.00 / 0.25 · 0.75 | 0.81 / 0.12 · 0.38 | 1.00 / 0.00 · 0.50 | 0.48 / 0.34 · 0.95 |
| gpt-5.6-sol+tools | 0.50 / 0.50 · 0.12 | 1.00 / 0.69 · 0.25 | 1.00 / 0.50 · 0.25 | 0.00 / 0.00 · 0.10 |
| gpt-6-sol | 1.00 / 0.00 · 0.25 | 0.44 / 0.31 · 0.69 | 0.00 / 0.00 · 0.00 | 0.28 / 0.17 · 0.65 |
| claude-haiku+tools | 0.62 / 0.50 · 0.25 | 0.75 / 0.25 · 0.25 | 0.00 / 0.00 · 0.25 | 0.25 / 0.17 · 0.68 |
| gpt-5.6-terra+tools | 0.50 / 0.50 · 0.25 | 0.62 / 0.19 · 0.44 | 0.25 / 0.00 · 0.50 | 0.00 / 0.00 · 0.25 |
| claude-haiku | 0.50 / 0.12 · 0.25 | 0.38 / 0.12 · 0.50 | 0.00 / 0.00 · 0.00 | 0.22 / 0.12 · 0.49 |
| gpt-5.6-sol | 1.00 / 0.00 · 0.50 | 0.38 / 0.00 · 1.00 | 0.00 / 0.00 · 0.50 | 0.16 / 0.07 · 0.39 |
| gpt-6-luna+tools | 0.25 / 0.00 · 0.25 | 0.25 / 0.00 · 0.56 | 0.00 / 0.00 · 0.00 | 0.05 / 0.00 · 0.36 |
| gpt-5.6-luna+tools | 0.88 / 0.00 · 0.00 | 0.00 / 0.00 · 0.00 | 0.00 / 0.00 · 0.00 | 0.00 / 0.00 · 0.00 |
| gpt-5.6-luna | 0.50 / 0.00 · 0.00 | 0.00 / 0.00 · 0.06 | 0.00 / 0.00 · 0.00 | 0.02 / 0.00 · 0.22 |
| gpt-6-luna | 0.25 / 0.00 · 0.00 | 0.00 / 0.00 · 0.00 | 0.00 / 0.00 · 0.00 | 0.00 / 0.00 · 0.12 |
| gpt-5.6-terra | 0.00 / 0.00 · 0.00 | 0.25 / 0.00 · 0.31 | 0.25 / 0.00 · 0.25 | 0.17 / 0.12 · 0.27 |

Lean queries (surname + given name only) for the scan picks, as found at A or B / found at A:

| Record type | Default | Fallback 1 | Fallback 2 |
|---|---|---|---|
| galician_table | claude-sonnet 1.00 / 1.00 | claude-opus+tools 1.00 / 1.00 | claude-sonnet+tools 1.00 / 1.00 |
| polish_narrative | claude-sonnet 1.00 / 0.88 | claude-fable+tools 1.00 / 1.00 | claude-fable 0.94 / 0.94 |
| russian_narrative | claude-opus 1.00 / 1.00 | claude-opus+tools **0.50** / 0.50 | claude-fable+tools **0.50** / 0.50 |
| russian_index | index lines name no parents: same as the full table | | |

How to read the replay:
- **Act pages:** with both parents' given names in the query, every top Claude reader flagged every target, including the fast claude-sonnet (18–33 s per page). Without them, the Russian-act fallbacks found only half (table above).
- **Index page:** recall needs the strong reader (claude-opus+tools 1.00, claude-sonnet 0.68).
- **False hits** run at about 1–3 per hundred decoy entries. On act pages most are entries where one name matches and a surname, father or mother reading is partly [illegible]: the matcher lists those as B rather than hide them.
- **The matching rule matters.** Against *perfect* transcriptions queried in the researcher's spelling, the edit band + Daitch–Mokotoff rule found 35 of 35 people at tier A. A plain ≥ 0.8 word-similarity rule (surname plus one other name) found 23 of 35. Example: Wegbreit vs Wegbrajt.
- Recall is a **lower bound**. A line the scorer could not pair with a key entry counts as a miss: all 38 of claude-sonnet's misses on the index page are such lines.
- The matcher was tuned on these same 38 people: the researcher spellings, the diphthong mapping (ei/ej → aj on both sides) and the short-code cutoff were chosen after seeing misses. The case endings (Sztajnów), the transliteration variants (Yitzhak ~ Icek) and the letters beside an [illegible] were added for cases this replay does not contain. Re-check on new keyed pages.
- False hits were measured on 37 decoys. A real register with common surnames (Goldberg, Rozenberg) will give longer tier-B lists.

## 4. Proof mode: what agreement and hedges mean
Computed from `scores/fields.csv`. Rules:
- Adjudicated key only. A field with no best reading is left out.
- "Exact" = full credit for the best reading (base ≥ 0.999). For names, every key name word matches after normalization; dates and numbers match exactly.
- "Plain" = given without alternatives.
- Two readers are paired on the same run number.
- "Agree" = equal after `normalize()`.
- Top Claude = claude-opus, claude-opus+tools, claude-fable, claude-fable+tools. Other provider = gpt-6.1-sol+tools, gpt-6-astra+tools, gemini-3.1-pro+tools.

| Situation | Exact | Reader pairs (distinct fields) |
|---|---|---|
| Top Claude + other-provider reader agree, both plain | 0.97 (Polish 0.996 = 243/244, index 0.95) | 800 (67: index 41, Polish 17, Russian act 5, Galician 4) |
| Two top Claude readers agree, both plain | 0.95 (Polish 0.91, index 0.96) | 490 (75: index 46, Polish 18, Russian act 5, Galician 6) |
| Two runs of one reader agree, both plain (11 readers) | 0.91 | 419 (83: index 51, Polish 20, Russian act 7, Galician 5) |
| Two runs disagree: run 1 exact / either run exact | 0.24 / 0.40 | 329 (76: index 47, Polish 16, Russian act 10, Galician 3) |

A pair is one field read by two readers in the same run (rows 1–2), or by one reader in both runs (rows 3–4), so one field counts once for every such pair. The evidence is thin on narrative acts: only 5 Russian-act fields stand behind the first row, and its one Polish miss is the act 43 date below.

When claude-opus+tools was wrong, how often did the other reader give the **same wrong reading**?
- claude-fable+tools: 31 % (n = 58).
- gemini-3.1-pro+tools: 14 % (n = 36).
- gpt-6.1-sol+tools: 10 % (n = 49).
- gpt-6-astra+tools: 10 % (n = 50).

A second reader from another provider repeats fewer of the first reader's mistakes.

| Reader | Plain readings: exact (n) | Hedged readings: best exact / any reading exact (n) |
|---|---|---|
| claude-opus | 0.86 (100) | 0.40 / 0.48 (86) |
| claude-opus+tools | 0.85 (134) | 0.43 / 0.49 (70) |
| claude-fable | 0.83 (103) | 0.42 / 0.56 (85) |
| claude-fable+tools | 0.78 (159) | 0.49 / 0.56 (41) |
| claude-sonnet | 0.65 (108) | 0.35 / 0.52 (60) |
| gpt-6.1-sol+tools | 0.74 (102) | 0.22 / 0.25 (69) |
| gpt-6-astra+tools | 0.86 (100) | 0.18 / 0.22 (72) |
| gemini-3.1-pro+tools | 0.73 (132) | 0.19 / 0.25 (16) |
| gemini-3.1-pro | 0.48 (143) | 0.33 / 0.50 (6) |
| gemini-3.8-flash | 0.60 (104) | 0.20 / 0.39 (44) |

What these signals mean, reader by reader:
- **A Claude hedge means "unresolved".** Test every alternative on the image.
- **A hedged GPT field is close to no reading.**
- **Gemini 3.1 Pro's plain strings are not a confidence claim.** It hedges only 6.5 % of fields.

Shared mistakes survive agreement. Warsaw 1848 act 43 registers an 1834 birth, yet claude-opus (run 1), claude-opus+tools (run 2) and gpt-6.1-sol+tools (run 1), among others, answered 1847-09-16 with no hedge.

## 5. Full tables (every contestant, every metric)
Generated by `python3 -I scripts/htr_contest/performance.py tables` from `model-performance.json`. Scan value and proof value apply the section 1 formula; they are computed for every row, eligible or not.

### galician_table

| Contestant | Mode | Acc | Best-only | Alt gain | Name exact | Name near | Findable | Time s | Tokens | Hedge | Rescue | Made-up | Cons. | Failed | Runs | Scan value | Proof value |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| claude-fable+tools | tools | 1.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 | 70 | 237026 | 0.083 | 0.000 | 0 | 1.000 | 0 | 2 | 0.878 | 0.939 |
| claude-opus+tools | tools | 1.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 | 30 | 57720 | 0.083 | 0.000 | 0 | 1.000 | 0 | 2 | 1.000 | 1.000 |
| claude-sonnet | look | 1.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 | 18 | – | 0.500 | 0.000 | 0 | 0.667 | 0 | 2 | 1.000 | 1.000 |
| claude-sonnet+tools | tools | 1.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 | 21 | 41512 | 0.250 | 0.000 | 0 | 0.667 | 0 | 2 | 1.000 | 1.000 |
| gemini-3.1-pro | look | 1.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 | 100 | – | 0.167 | 0.000 | 0 | 0.667 | 0 | 2 | 0.826 | 0.913 |
| gemini-3.1-pro+tools | tools | 1.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 | 307 | 493888 | 0.083 | 0.000 | 0 | 0.667 | 0 | 2 | 0.664 | 0.832 |
| gemini-3.8-flash | look | 1.000 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 | 344 | – | 0.333 | 0.000 | 0 | 1.000 | 0 | 2 | 0.648 | 0.824 |
| claude-fable | look | 0.870 | 0.870 | 0.000 | 0.750 | 0.750 | 0.750 | 49 | – | 0.333 | 0.000 | 0 | 0.667 | 0 | 2 | 0.679 | 0.835 |
| gpt-6-astra+tools | tools | 0.856 | 0.856 | 0.000 | 0.750 | 0.750 | 0.750 | 80 | 261020 | 0.000 | 0.000 | 0 | 0.667 | 0 | 2 | 0.608 | 0.785 |
| gpt-6-sol+tools | tools | 0.856 | 0.856 | 0.000 | 0.750 | 0.750 | 0.750 | 87 | 462938 | 0.000 | 0.000 | 0 | 0.667 | 0 | 2 | 0.596 | 0.779 |
| gpt-6.1-sol+tools | tools | 0.856 | 0.856 | 0.000 | 0.750 | 0.750 | 0.750 | 72 | 286586 | 0.083 | 0.000 | 0 | 0.667 | 0 | 2 | 0.624 | 0.793 |
| claude-opus | look | 0.840 | 0.790 | 0.050 | 0.750 | 0.750 | 0.750 | 28 | – | 0.417 | 0.000 | 0 | 0.500 | 0 | 2 | 0.750 | 0.840 |
| gpt-6.1-sol | look | 0.790 | 0.790 | 0.000 | 0.500 | 0.500 | 0.500 | 53 | 11825 | 0.333 | 0.000 | 0 | 0.667 | 0 | 2 | 0.418 | 0.749 |
| gpt-6-sol | look | 0.779 | 0.754 | 0.025 | 0.375 | 0.500 | 0.500 | 36 | 21494 | 0.500 | 0.000 | 0 | 0.667 | 0 | 2 | 0.474 | 0.766 |
| gpt-6-astra | look | 0.742 | 0.692 | 0.050 | 0.500 | 0.500 | 0.500 | 53 | 15304 | 0.333 | 0.000 | 0 | 0.833 | 0 | 2 | 0.418 | 0.701 |
| claude-haiku+tools | tools | 0.645 | 0.520 | 0.125 | 0.250 | 0.375 | 0.500 | 51 | 105418 | 0.417 | 0.000 | 0 | 0.500 | 0 | 2 | 0.423 | 0.607 |
| gpt-5.6-terra+tools | tools | 0.633 | 0.633 | 0.000 | 0.625 | 0.625 | 0.625 | 229 | 903668 | 0.083 | 0.000 | 0 | 0.333 | 0 | 2 | 0.332 | 0.486 |
| gpt-5.6-sol | look | 0.582 | 0.557 | 0.025 | 0.250 | 0.250 | 0.250 | 97 | 13706 | 0.417 | 0.000 | 0 | 0.833 | 0 | 2 | 0.081 | 0.497 |
| gpt-5.6-luna+tools | tools | 0.543 | 0.543 | 0.000 | 0.375 | 0.375 | 0.375 | 85 | 446277 | 0.000 | 0.000 | 0 | 0.500 | 0 | 2 | 0.225 | 0.468 |
| gpt-5.6-sol+tools | tools | 0.543 | 0.543 | 0.000 | 0.500 | 0.500 | 0.500 | 152 | 818126 | 0.000 | 0.000 | 0.5 | 0.167 | 0 | 2 | 0.266 | 0.426 |
| gpt-6-luna+tools | tools | 0.510 | 0.485 | 0.025 | 0.375 | 0.375 | 0.375 | 36 | 154878 | 0.100 | 0.000 | 0 | 0.667 | 0 | 2 | 0.349 | 0.497 |
| gpt-5.6-luna | look | 0.480 | 0.430 | 0.050 | 0.250 | 0.250 | 0.250 | 28 | 14713 | 0.583 | 0.000 | 0 | 0.833 | 0 | 2 | 0.250 | 0.480 |
| claude-haiku | look | 0.428 | 0.378 | 0.050 | 0.125 | 0.250 | 0.250 | 19 | – | 0.583 | 0.000 | 0.5 | 0.167 | 0 | 2 | 0.250 | 0.428 |
| gpt-6-luna | look | 0.358 | 0.283 | 0.075 | 0.250 | 0.250 | 0.250 | 22 | 10800 | 0.375 | 0.000 | 0 | 0.333 | 0 | 2 | 0.250 | 0.358 |
| gpt-5.6-terra | look | 0.099 | 0.074 | 0.025 | 0.000 | 0.000 | 0.000 | 37 | 8465 | 0.500 | 0.000 | 1 | 0.167 | 0 | 2 | -0.030 | 0.084 |

### polish_narrative

| Contestant | Mode | Acc | Best-only | Alt gain | Name exact | Name near | Findable | Time s | Tokens | Hedge | Rescue | Made-up | Cons. | Failed | Runs | Scan value | Proof value |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| claude-fable+tools | tools | 0.924 | 0.911 | 0.012 | 0.781 | 0.906 | 0.969 | 129 | 253984 | 0.229 | 0.000 | 0 | 0.917 | 0 | 2 | 0.759 | 0.819 |
| claude-fable | look | 0.860 | 0.810 | 0.050 | 0.594 | 0.781 | 0.875 | 85 | – | 0.354 | 0.250 | 0 | 0.792 | 0 | 2 | 0.725 | 0.785 |
| claude-opus+tools | tools | 0.841 | 0.791 | 0.050 | 0.594 | 0.781 | 0.812 | 59 | 136538 | 0.354 | 0.100 | 0 | 0.667 | 0 | 2 | 0.714 | 0.792 |
| gemini-3.1-pro+tools | tools | 0.824 | 0.805 | 0.019 | 0.719 | 0.781 | 0.781 | 418 | 681292 | 0.083 | 0.000 | 0 | 0.667 | 0 | 2 | 0.401 | 0.634 |
| claude-opus | look | 0.819 | 0.739 | 0.079 | 0.500 | 0.719 | 0.812 | 46 | – | 0.458 | 0.171 | 0 | 0.625 | 0 | 2 | 0.750 | 0.788 |
| claude-sonnet | look | 0.774 | 0.693 | 0.081 | 0.406 | 0.719 | 0.844 | 33 | – | 0.417 | 0.188 | 0 | 0.625 | 0 | 2 | 0.830 | 0.767 |
| claude-sonnet+tools | tools | 0.704 | 0.638 | 0.066 | 0.344 | 0.500 | 0.594 | 31 | 26882 | 0.354 | 0.100 | 0 | 0.542 | 0 | 2 | 0.589 | 0.702 |
| gemini-3.8-flash | look | 0.680 | 0.555 | 0.125 | 0.250 | 0.562 | 0.656 | 402 | – | 0.479 | 0.300 | 0 | 0.583 | 0 | 2 | 0.282 | 0.493 |
| gpt-6-astra+tools | tools | 0.675 | 0.562 | 0.113 | 0.312 | 0.469 | 0.469 | 117 | 235185 | 0.417 | 0.000 | 0 | 0.583 | 0 | 2 | 0.273 | 0.577 |
| gpt-6-sol+tools | tools | 0.659 | 0.562 | 0.097 | 0.281 | 0.406 | 0.469 | 170 | 1199320 | 0.396 | 0.000 | 0 | 0.417 | 0 | 2 | 0.219 | 0.534 |
| gpt-5.6-sol+tools | tools | 0.635 | 0.591 | 0.044 | 0.375 | 0.562 | 0.562 | 468 | 970632 | 0.208 | 0.000 | 0 | 0.375 | 0 | 2 | 0.166 | 0.437 |
| gpt-6.1-sol+tools | tools | 0.634 | 0.559 | 0.075 | 0.250 | 0.438 | 0.438 | 167 | 287354 | 0.312 | 0.000 | 0 | 0.542 | 0 | 2 | 0.190 | 0.510 |
| gemini-3.1-pro | look | 0.565 | 0.559 | 0.006 | 0.219 | 0.562 | 0.562 | 154 | – | 0.021 | 0.000 | 0 | 0.458 | 0 | 2 | 0.326 | 0.447 |
| gpt-6-astra | look | 0.424 | 0.324 | 0.100 | 0.125 | 0.250 | 0.250 | 86 | 13606 | 0.375 | 0.000 | 0 | 0.333 | 0 | 2 | 0.098 | 0.348 |
| gpt-6.1-sol | look | 0.359 | 0.296 | 0.062 | 0.031 | 0.156 | 0.156 | 109 | 14762 | 0.625 | 0.036 | 0 | 0.458 | 0 | 2 | -0.030 | 0.266 |
| claude-haiku+tools | tools | 0.357 | 0.295 | 0.062 | 0.250 | 0.281 | 0.281 | 28 | 30178 | 0.625 | 0.000 | 0 | 0.708 | 0 | 2 | 0.281 | 0.357 |
| gpt-5.6-terra+tools | tools | 0.314 | 0.245 | 0.069 | 0.125 | 0.219 | 0.219 | 303 | 753051 | 0.479 | 0.071 | 0 | 0.208 | 0 | 2 | -0.115 | 0.147 |
| claude-haiku | look | 0.298 | 0.192 | 0.106 | 0.125 | 0.156 | 0.156 | 23 | – | 0.571 | 0.000 | 0 | 0.458 | 0 | 2 | 0.156 | 0.298 |
| gpt-6-sol | look | 0.267 | 0.208 | 0.059 | 0.062 | 0.188 | 0.188 | 94 | 18126 | 0.583 | 0.045 | 0 | 0.167 | 0 | 2 | 0.023 | 0.185 |
| gpt-5.6-sol | look | 0.200 | 0.156 | 0.044 | 0.094 | 0.125 | 0.125 | 64 | 10576 | 0.625 | 0.000 | 0 | 0.417 | 0 | 2 | 0.016 | 0.145 |
| gpt-6-luna+tools | tools | 0.125 | 0.100 | 0.025 | 0.031 | 0.031 | 0.031 | 34 | 146796 | 0.412 | 0.000 | 0 | 0.500 | 0 | 2 | 0.013 | 0.116 |
| gpt-5.6-terra | look | 0.113 | 0.094 | 0.019 | 0.062 | 0.062 | 0.062 | 69 | 9608 | 0.527 | 0.000 | 0 | 0.458 | 0 | 2 | -0.058 | 0.053 |
| gpt-5.6-luna | look | 0.075 | 0.075 | 0.000 | 0.000 | 0.000 | 0.000 | 24 | 19618 | 0.568 | 0.000 | 0 | 0.833 | 0 | 2 | 0.000 | 0.075 |
| gpt-5.6-luna+tools | tools | 0.075 | 0.075 | 0.000 | 0.000 | 0.000 | 0.000 | 141 | 456736 | 0.667 | 0.000 | 0 | 1.000 | 0 | 2 | -0.223 | -0.037 |
| gpt-6-luna | look | 0.075 | 0.075 | 0.000 | 0.000 | 0.000 | 0.000 | 15 | 7768 | 0.667 | 0.000 | 0 | 0.917 | 0 | 2 | 0.000 | 0.075 |

### russian_index

| Contestant | Mode | Acc | Best-only | Alt gain | Name exact | Name near | Findable | Time s | Tokens | Hedge | Rescue | Made-up | Cons. | Failed | Runs | Scan value | Proof value |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| claude-opus+tools | tools | 0.895 | 0.851 | 0.044 | 0.695 | 0.873 | 0.898 | 66 | 87159 | 0.308 | 0.141 | 1 | 0.800 | 0 | 2 | 0.784 | 0.838 |
| claude-fable+tools | tools | 0.855 | 0.836 | 0.019 | 0.653 | 0.890 | 0.915 | 178 | 321652 | 0.147 | 0.325 | 2 | 0.850 | 0 | 2 | 0.658 | 0.727 |
| claude-fable | look | 0.760 | 0.698 | 0.062 | 0.551 | 0.712 | 0.754 | 126 | – | 0.489 | 0.312 | 5 | 0.583 | 0 | 2 | 0.547 | 0.656 |
| claude-opus | look | 0.725 | 0.666 | 0.059 | 0.534 | 0.661 | 0.746 | 60 | – | 0.412 | 0.132 | 6 | 0.683 | 0 | 2 | 0.646 | 0.675 |
| claude-sonnet+tools | tools | 0.655 | 0.634 | 0.021 | 0.458 | 0.576 | 0.593 | 34 | 38777 | 0.169 | 0.167 | 5.5 | 0.400 | 0 | 2 | 0.575 | 0.646 |
| gpt-6-astra+tools | tools | 0.614 | 0.555 | 0.059 | 0.432 | 0.525 | 0.551 | 169 | 277312 | 0.413 | 0.068 | 9.5 | 0.467 | 0 | 2 | 0.302 | 0.489 |
| gpt-6.1-sol+tools | tools | 0.585 | 0.516 | 0.069 | 0.356 | 0.517 | 0.534 | 124 | 202690 | 0.437 | 0.061 | 8.5 | 0.450 | 0 | 2 | 0.329 | 0.483 |
| claude-sonnet | look | 0.506 | 0.478 | 0.028 | 0.322 | 0.449 | 0.517 | 32 | – | 0.173 | 0.273 | 10.5 | 0.483 | 0 | 2 | 0.508 | 0.501 |
| gemini-3.1-pro+tools | tools | 0.500 | 0.485 | 0.015 | 0.364 | 0.483 | 0.492 | 558 | 764094 | 0.112 | 0.000 | 11 | 0.400 | 0 | 2 | 0.070 | 0.289 |
| gpt-6-sol+tools | tools | 0.420 | 0.359 | 0.061 | 0.220 | 0.339 | 0.347 | 173 | 749346 | 0.546 | 0.196 | 13 | 0.500 | 0 | 2 | 0.094 | 0.294 |
| gpt-6.1-sol | look | 0.401 | 0.357 | 0.044 | 0.254 | 0.331 | 0.331 | 123 | 23362 | 0.342 | 0.028 | 14 | 0.367 | 0 | 2 | 0.127 | 0.299 |
| gemini-3.8-flash | look | 0.352 | 0.339 | 0.014 | 0.237 | 0.322 | 0.331 | 607 | – | 0.111 | 0.375 | 14.5 | 0.567 | 0 | 2 | -0.103 | 0.135 |
| gemini-3.1-pro | look | 0.342 | 0.338 | 0.004 | 0.229 | 0.305 | 0.314 | 461 | – | 0.031 | 0.250 | 14.5 | 0.383 | 0 | 2 | -0.080 | 0.145 |
| gpt-6-astra | look | 0.315 | 0.286 | 0.029 | 0.195 | 0.246 | 0.246 | 132 | 16206 | 0.352 | 0.000 | 17 | 0.700 | 0 | 2 | 0.032 | 0.208 |
| gpt-6-sol | look | 0.210 | 0.183 | 0.027 | 0.110 | 0.178 | 0.178 | 100 | 18329 | 0.194 | 0.036 | 21 | 0.400 | 0 | 2 | 0.004 | 0.123 |
| claude-haiku+tools | tools | 0.193 | 0.158 | 0.036 | 0.110 | 0.153 | 0.161 | 42 | 57800 | 0.967 | 0.045 | 22 | 0.633 | 0 | 2 | 0.112 | 0.169 |
| claude-haiku | look | 0.158 | 0.127 | 0.032 | 0.085 | 0.119 | 0.119 | 31 | – | 1.000 | 0.050 | 23.5 | 0.667 | 0 | 2 | 0.114 | 0.156 |
| gpt-5.6-sol | look | 0.135 | 0.118 | 0.017 | 0.085 | 0.093 | 0.093 | 110 | 15360 | 0.478 | 0.000 | 23.5 | 0.717 | 0 | 2 | -0.094 | 0.041 |
| gpt-5.6-terra | look | 0.130 | 0.122 | 0.008 | 0.093 | 0.102 | 0.102 | 69 | 16534 | 0.256 | 0.000 | 24 | 0.733 | 0 | 2 | -0.018 | 0.070 |
| gpt-6-luna+tools | tools | 0.035 | 0.033 | 0.002 | 0.025 | 0.025 | 0.025 | 30 | 91860 | 0.500 | 0.000 | 28 | 0.883 | 0 | 2 | 0.025 | 0.035 |
| gpt-6-luna | look | 0.021 | 0.016 | 0.004 | 0.008 | 0.017 | 0.017 | 44 | 12759 | 0.250 | 0.000 | 14.5 | 0.933 | 0 | 2 | -0.038 | -0.007 |
| gpt-5.6-luna | look | 0.010 | 0.010 | 0.000 | 0.008 | 0.008 | 0.008 | 89 | 13249 | 0.000 | 0.000 | 29.5 | 0.967 | 0 | 2 | -0.149 | -0.068 |
| gpt-5.6-luna+tools | tools | 0.000 | 0.000 | 0.000 | – | – | – | 228 | – | – | – | – | – | 1 | 1 | – | -0.146 |
| gpt-5.6-sol+tools | tools | 0.000 | 0.000 | 0.000 | – | – | – | 1154 | – | – | – | – | – | 1 | 1 | – | -0.263 |
| gpt-5.6-terra+tools | tools | 0.000 | 0.000 | 0.000 | – | – | – | 228 | – | – | – | – | – | 1 | 1 | – | -0.146 |

### russian_narrative

| Contestant | Mode | Acc | Best-only | Alt gain | Name exact | Name near | Findable | Time s | Tokens | Hedge | Rescue | Made-up | Cons. | Failed | Runs | Scan value | Proof value |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| claude-opus | look | 0.811 | 0.705 | 0.106 | 0.500 | 0.625 | 0.688 | 37 | – | 0.708 | 0.125 | 0 | 0.667 | 0 | 2 | 0.658 | 0.796 |
| gpt-6.1-sol+tools | tools | 0.772 | 0.660 | 0.113 | 0.438 | 0.438 | 0.438 | 120 | 282945 | 0.625 | 0.000 | 0 | 0.583 | 0 | 2 | 0.238 | 0.672 |
| claude-opus+tools | tools | 0.769 | 0.644 | 0.125 | 0.375 | 0.562 | 0.562 | 59 | 125466 | 0.625 | 0.000 | 0 | 0.667 | 0 | 2 | 0.464 | 0.720 |
| claude-fable+tools | tools | 0.732 | 0.607 | 0.125 | 0.250 | 0.562 | 0.562 | 200 | 455664 | 0.500 | 0.000 | 0 | 0.583 | 0 | 2 | 0.288 | 0.595 |
| claude-sonnet | look | 0.669 | 0.557 | 0.113 | 0.375 | 0.438 | 0.438 | 22 | – | 0.784 | 0.100 | 0 | 0.500 | 0 | 2 | 0.438 | 0.669 |
| gpt-6-astra+tools | tools | 0.625 | 0.463 | 0.162 | 0.188 | 0.188 | 0.312 | 105 | 238456 | 0.583 | 0.000 | 0 | 0.583 | 0 | 2 | 0.131 | 0.535 |
| claude-fable | look | 0.606 | 0.456 | 0.150 | 0.188 | 0.188 | 0.312 | 92 | – | 0.542 | 0.083 | 0 | 0.333 | 0 | 2 | 0.150 | 0.525 |
| claude-sonnet+tools | tools | 0.536 | 0.436 | 0.100 | 0.312 | 0.312 | 0.375 | 26 | 25748 | 0.833 | 0.083 | 0 | 0.667 | 0 | 2 | 0.375 | 0.536 |
| gpt-5.6-sol+tools | tools | 0.453 | 0.378 | 0.075 | 0.188 | 0.312 | 0.312 | 387 | 1630278 | 0.394 | 0.000 | 0 | 0.167 | 0 | 2 | -0.057 | 0.269 |
| gemini-3.8-flash | look | 0.447 | 0.335 | 0.112 | 0.062 | 0.062 | 0.062 | 236 | – | 0.417 | 0.000 | 0 | 0.417 | 0 | 2 | -0.236 | 0.298 |
| gpt-6-astra | look | 0.437 | 0.412 | 0.025 | 0.188 | 0.188 | 0.188 | 76 | 12906 | 0.458 | 0.000 | 0 | 0.417 | 0 | 2 | 0.054 | 0.370 |
| gemini-3.1-pro | look | 0.411 | 0.399 | 0.012 | 0.188 | 0.188 | 0.188 | 112 | – | 0.042 | 0.000 | 0 | 0.333 | 0 | 2 | -0.002 | 0.316 |
| gpt-6.1-sol | look | 0.359 | 0.284 | 0.075 | 0.000 | 0.000 | 0.000 | 76 | 19642 | 0.542 | 0.000 | 0 | 0.167 | 0 | 2 | -0.134 | 0.292 |
| gemini-3.1-pro+tools | tools | 0.321 | 0.259 | 0.062 | 0.375 | 0.375 | 0.500 | 1254 | 1765400 | 0.250 | 0.333 | 0 | – | 1 | 2 | -0.039 | 0.052 |
| gpt-6-sol+tools | tools | 0.292 | 0.230 | 0.062 | 0.125 | 0.125 | 0.125 | 200 | 1522700 | 0.625 | 0.000 | 0 | 0.333 | 0 | 2 | -0.149 | 0.155 |
| claude-haiku | look | 0.144 | 0.106 | 0.038 | 0.000 | 0.000 | 0.000 | 14 | – | 0.633 | 0.000 | 0 | 0.500 | 0 | 2 | 0.000 | 0.144 |
| gpt-5.6-terra | look | 0.141 | 0.128 | 0.012 | 0.000 | 0.062 | 0.062 | 25 | 7870 | 0.333 | 0.062 | 0 | 0.667 | 0 | 2 | 0.062 | 0.141 |
| gpt-5.6-terra+tools | tools | 0.087 | 0.062 | 0.025 | 0.000 | 0.000 | 0.000 | 237 | 656123 | 0.458 | 0.000 | 0 | 0.333 | 0 | 2 | -0.298 | -0.062 |
| gpt-5.6-luna+tools | tools | 0.084 | 0.034 | 0.050 | 0.000 | 0.000 | 0.000 | 119 | 492100 | 0.333 | 0.000 | 0 | 0.833 | 0 | 2 | -0.199 | -0.015 |
| claude-haiku+tools | tools | 0.077 | 0.052 | 0.025 | 0.000 | 0.000 | 0.000 | 26 | 76509 | 0.625 | 0.000 | 0 | 0.583 | 0 | 2 | 0.000 | 0.077 |
| gpt-5.6-luna | look | 0.075 | 0.075 | 0.000 | 0.000 | 0.000 | 0.000 | 19 | 10018 | 0.600 | 0.000 | 0 | 1.000 | 0 | 2 | 0.000 | 0.075 |
| gpt-5.6-sol | look | 0.075 | 0.075 | 0.000 | 0.000 | 0.000 | 0.000 | 68 | 12212 | 0.583 | 0.000 | 0 | 0.833 | 0 | 2 | -0.118 | 0.016 |
| gpt-6-luna | look | 0.075 | 0.075 | 0.000 | 0.000 | 0.000 | 0.000 | 17 | 8415 | 0.500 | 0.000 | 0 | 1.000 | 0 | 2 | 0.000 | 0.075 |
| gpt-6-luna+tools | tools | 0.075 | 0.075 | 0.000 | 0.000 | 0.000 | 0.000 | 42 | 161175 | 0.550 | 0.000 | 0 | 1.000 | 0 | 2 | -0.049 | 0.051 |
| gpt-6-sol | look | 0.075 | 0.075 | 0.000 | 0.000 | 0.000 | 0.000 | 20 | 7094 | 0.583 | 0.000 | 0 | 1.000 | 0 | 2 | 0.000 | 0.075 |


## 6. Test pages and sample sizes
| Record type | Page (key in `reports/htr-contest/key/`) | Entries | Keyed fields (names) | Name readings per contestant | Replay queries |
|---|---|---|---|---|---|
| galician_table | `ah-szczerzec-b1894-0005`: Szczerzec 1894 births, Austrian table form, German Kurrent + Latin, sideways two-page spread (AGAD 300/1363) | 2 | 6 (4) | 8 | 8 |
| polish_narrative | `pl-warszawa-b1848-043-046`: Warsaw 1848 Jewish births, Polish narrative acts 43–46 | 4 | 24 (16) | 32 | 16 |
| russian_narrative | `ru-warszawa-b1878-012-013`: Warsaw 1878 births, Russian Cyrillic narrative acts 12–13 | 2 | 12 (8) | 16 | 8 |
| russian_index | `ru-warszawa-b1878-sku1`: same volume, narrative act 38 + alphabetical index lines 1–30 | 30 | 60 (59) | 118 | 120 |

## 7. Caveats
- **Samples are small:** one page per record type, 2 runs each. On the narrative pages a difference of 0.05–0.10 is about one name, and one more keyed page can flip a pick.
- **Keys are index values**, not the whole register. Columns JRI does not index (godparents, witnesses, most house numbers, notes) were not scored.
- **The index page was matched by name.** The prompt does not say which number column on an index page is the act number, so act numbers on index lines were not scored. Treat them as ±2, and watch for look-alike digits.
- **"Findable" is strict on short names.** One wrong letter in a 4-letter name scores 0.75 (Lejb vs Leib), which counts as not found. The matcher's edit band and Daitch–Mokotoff codes recover these, as the replay shows.
- **Name metrics count successful runs only;** accuracy counts a failed run as 0. Rows with failed > 0 are excluded from the picks.
- **Blind reading only.** Naming the target in the prompt, cropping the page for the reader, several pages per call, and reading in this session or a subagent were not tested.
- **Not yet tested at all:** marriages and deaths, Hungarian, Hebrew/Yiddish script, interwar Polish tables, headstones, and other archives' image quality.
- **Isolation:**
  - Claude ran with `--setting-sources project`, which keeps the global CLAUDE.md out (verified). In tools mode it also ran with a sandbox that denies reads of this repo.
  - codex still connected to the user's MCP servers at start-up despite `-c mcp_servers={}`. No MCP tool was ever called (traces audited). Next round, give codex its own `CODEX_HOME` (see `transcription-prompt.md`).
  - The tools-mode sandbox walls off this repo only. The auto-memory files under `~/.claude/projects/`, which name the families, stayed readable, and the audit searched only for the repo path.
- **The scores hold for this prompt only.** A changed prompt is a new contest round (section 9).

## 8. Metric definitions
- **Acc** (accuracy): weighted field score against the adjudicated key, mean of 2 runs; a failed run scores 0.
  - Names have weight 2. Dates, numbers and place have weight 1.
  - A confident wrong reading costs 0.25. A correct alternative earns at least 0.5.
- **Best-only:** the same answers with the alternatives stripped. **Alt gain** = Acc − Best-only.
- **Name exact / Name near:** share of name fields whose best reading matches every key name word exactly (after spelling normalization), or with ≥ 0.8 similarity (about 1 letter in 5 off).
- **Findable** (`name_findable_with_alts`): the same as Name near, but the best reading **or any alternative** may match. It answers: would a fuzzy search find the person?
- **Time s:** mean wall-clock seconds per page, failed runs included.
- **Tokens:** mean per successful run, as the CLI reports them; "–" = not reported.
- **Hedge:** share of answered fields given with alternatives.
- **Rescue:** share of wrong hedged fields where an alternative was right.
- **Made-up:** entries per run that pair with no key entry (invented or misplaced lines).
- **Cons.:** share of key fields where run 1 and run 2 agree.
- **Scan replay:** see section 3.

## 9. Updating (a new model, a new record type or language, a new prompt)
Reuse the harness in `scripts/htr_contest/`; never retype prompts or commands. Run one job at a time per CLI; different CLIs may run in parallel. Tools mode has a 30-minute cap per page.

**A new model:**
1. Add it to `_LOOK` in `scripts/htr_contest/contestants.py` (the `+tools` variant is generated). Check that its CLI still accepts the flags in `transcription-prompt.md`, and update `test_contestant_roster`.
2. Run `python3 -I scripts/htr_contest/run.py --only <name>`, then `--only <name>+tools`. Two runs on every keyed page are cached in `reports/htr-contest/runs/`.
3. Run `python3 -I scripts/htr_contest/report.py flags`. Rule on each new flag in `reports/htr-contest/adjudication.json` after checking the image (`key_wrong` / `key_right`). Then run `report.py leaderboard`, which rewrites `scores/fields.csv`.
4. Run `python3 -I scripts/htr_contest/performance.py collect`, then `picks` and `tables`. Before trusting the new JSON, diff it against the old one: rows for unchanged contestants must be identical.
5. Run `python3 -I scripts/htr_contest/find_person.py eval` and `eval --lean`, and refresh the section 3 tables. If section 4 matters for the new model, recompute it with the rules stated there.
6. Paste the outputs into sections 1, 3 and 5. Re-read the notes in sections 1–2. Update the picks table in SKILL.md, and the date at the top of this file.
7. Add a dated entry to `references/research-insights.md`, and commit (`research: htr-contest add <model>`).

**A new record type or language** (or a harder page for an existing type, such as the Galician one):
1. Pick a page with a published index and ≥ 5 entries, and fetch the scan into `documents/vital-records/scans/`.
2. Write `reports/htr-contest/key/<image_id>.json` from the published index **only**, never from this project's notes: some were written with Claude's help, which would bias the key toward Claude.
   - Required fields: `image_id`, `image`, `lang`, `source` (index, ids, url, accessed, archive, note), `entries`, and `"page_type"`.
   - Reuse an existing `page_type` to average the page into that row, or name a new type.
   - For an alphabetical index page, add `"match_on": "names"`.
3. For a new `lang`, add its spelling variants (and a transliteration table for a new script) to `normalize.py`, allow the language in `score.load_key`, and add tests; `find_person.py` takes its languages from `normalize.VARIANTS`. For the replay, add researcher-style spellings of the new key's Latin-script names to `RESEARCHER_SPELLING` in `find_person.py` (Cyrillic keys are transliterated automatically).
4. Run the leading contestants on it: `run.py --image <image_id> --only <name>`. Skip the models under "Avoid" unless the script is new to them. Then follow steps 3–7 above.

**A prompt change is a new contest round.**
- Test the variant with `run.py --prompt <file>`; never edit `prompt.md`, which `transcribe.py` refuses to send unless its sha256 is the validated one.
- `run.py` reuses cached runs even when the prompt changed (it only warns), so move `reports/htr-contest/runs/` aside first.
- Re-run every contestant that could be a pick, on every keyed page.
- Adopt the new prompt only if, for every record type, accuracy, findability and replay recall do not drop. Then replace `prompt.md`, its copy in `transcription-prompt.md` and `VALIDATED_PROMPT_SHA256` in `transcribe.py` together (`tests/test_transcribe.py` checks that they agree).
- `transcription-prompt.md` says what was validated and what was not.

**Next improvements:**
- Key a harder Galician page.
- Make look-only Claude runs report tokens. This needs `--output-format json` and a matching change to `Contestant.raw_reply`.
- Give codex its own `CODEX_HOME`.
- Score act numbers on index lines (it needs a prompt line saying which column is the act number).
