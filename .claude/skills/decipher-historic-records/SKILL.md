---
name: decipher-historic-records
description: Use when reading a scanned vital record (birth/marriage/death register, metrical book, census, gravestone) from any country — fetching the scan, locating the entry, reading old handwriting, transcribing column-by-column, translating, and grading the evidence — or when scanning many unindexed register pages for one person, or choosing an AI model to read a scan. Has format sheets for Austrian-Galician Jewish registers and interwar Polish registers, and contest-validated AI reader picks per record type; extend with new formats as they are met.
---

# Deciphering Historic Records

## Workflow (every record)
1. **Get the pointer** from the index (JRI-Poland, Gesher Galicia, FamilySearch): town, year, type, akt/entry no., sygnatura/film, image no. No index entry? → **Scan mode** below.
2. **Fetch the full-resolution scan** into `documents/vital-records/scans/` (naming convention: `<ARCHIVE>_<fond>_<sygn>_<image>.jpg`). One request every ≥3 s.
3. **Locate the entry**: read the page at ~1600px to find the entry number, then crop that row at full resolution (`scripts/crop_record.py`). Rows written vertically need rotation: try `--rotate 90`, if text is upside-down use `270`.
4. **Identify the form**: printed column headers give the meaning, even when the handwriting is hard. Map every column before reading the handwriting.
5. **Transcribe literally**, column by column, in the original language. Mark uncertain letters with `[?]` and unreadable ones with `[…]`. Never "correct" names. If a conclusion will rest on the reading, also get a blind AI reading (**Proof mode** below).
6. **Translate** each column; then list **what the record proves** and **what it does not**.
7. **Check against the index**: indexes contain errors (sex, age, akt number). Note every discrepancy and say which source is right (the scan wins). The index is one more reader, not an answer key: JRI has "Хава" where the Warsaw 1878 scan reads "Хана".
8. **Grade**: primary/secondary info, direct/indirect evidence, and a confidence level (confirmed / probable / possible / speculative). Identity matches ("is this our Leib?") need evidence FOR and AGAINST.
9. **Cite** (Evidence Explained style): district, register, year, entry no., page; archive, fond, sygnatura, image; index ID; access date. For an AI reading, add the reader, mode, prompt sha256 (first 12 characters) and run date.

## AI readers: scan mode and proof mode
An AI reading is a lead, like an index entry: confirm every hit on the scan (steps 4–8). There are two jobs with different goals:
- **Scan mode**: find one person in many unindexed pages (a year of births). Goal: **no false negatives**, then speed and plan quota.
- **Proof mode**: transcribe one located entry that a conclusion will rest on. Goal: accuracy.

**Always.** The contest numbers behind the picks hold only under these rules:
- Run readers with `python3 -I scripts/htr_contest/transcribe.py --reader <pick> --out media/transcripts/<register> <pages…>`.
  - It sends the validated prompt byte for byte (it refuses an edited prompt.md), one page per call, blind, in an empty temp folder.
  - It caches every reading (rerun the command to resume) and backs off on rate limits.
  - Run one job at a time per CLI; different CLIs may run in parallel.
- Never tell a reader whom we are looking for, and never shorten or paraphrase the prompt.
- The blind reading must come from `transcribe.py`, never from this session or a subagent: both know the family names. Your own reading (step 5) is one more reader, not a blind one.
- Keep the `{"best","alternatives","reason"}` format. Alternatives decided picks: claude-sonnet finds 0.84 of Polish names with them and 0.72 without.
- Prompt, exact commands, isolation flags: [references/transcription-prompt.md](references/transcription-prompt.md).

Every row rests on **one keyed page** read twice by each model; on a narrative page one name moves a score by about 0.10.

| Record type (evidence) | Scan: default → fallback 1 → fallback 2 | Proof: default → fallback 1 → fallback 2 | Proof: 2nd reader (other CLI) |
|---|---|---|---|
| Galician table, Kurrent/Latin (1 page, 2 entries; **provisional**: easy key, 7 contestants (5 models) averaged 1.00) | claude-sonnet (18 s/page) → claude-opus+tools (30 s) → claude-sonnet+tools | claude-opus+tools → claude-sonnet → claude-sonnet+tools | gemini-3.1-pro |
| Polish narrative act, Congress Poland before 1868 (1 page, 4 acts) | claude-sonnet (33 s) → claude-fable+tools (129 s) → claude-fable | claude-fable+tools → claude-opus+tools → claude-fable | gemini-3.1-pro+tools (7 min) |
| Russian narrative act, 1868–1917 (1 page, 2 acts; **provisional**: the picks are 1–2 names apart) | claude-opus (37 s) → claude-opus+tools → claude-fable+tools | claude-opus → claude-opus+tools → gpt-6.1-sol+tools | gpt-6.1-sol+tools |
| Russian alphabetical index of a volume (1 page, 30 lines) | claude-opus+tools (66 s) → claude-fable+tools → claude-fable | an index line only points: prove from the act | – |
| Not yet tested (interwar tables, deaths, marriages, Hungarian, Hebrew…) | the nearest tested type's picks, marked "unvalidated"; `find_person.py` reads Latin and Cyrillic only, so for Hebrew script put Hebrew spellings in the query | claude-opus+tools; AI readings alone at most **probable** | Latin script: gemini-3.1-pro+tools; Cyrillic: gpt-6.1-sol+tools |

Fallback 1 re-reads what the default failed, and double-checks a no-hit. Fallback 2 is for when neither of the first two can run. The other-CLI reader gives an independent second reading, or covers for a spent plan quota.

**Pick rule:** near the best metric, the highest metric − time cost wins; scan ties go to look-only (fewer tokens), proof ties to all-pages accuracy. Parameters and the command (`performance.py picks`): [references/model-performance.md](references/model-performance.md) §1.

**Avoid:** claude-haiku, gpt-5.6-*, gpt-6-luna and look-only GPT. Gemini is slow: 100–607 s/page look-only, 307–1254 s with tools (it hit the 30-min cap on Russian acts).

Every model's metrics, sample sizes, caveats, and how to update the picks for a new model or record type are in [references/model-performance.md](references/model-performance.md). Read it on demand.

### Scan mode: find one person in unindexed pages
1. **Indexes first.** Search JRI-Poland, Geneteka, Gesher Galicia, FamilySearch and JewishGen (`references/how-to-search/`). Scan only the registers and years no index covers. Note every spelling the indexes give the surname in that region: those are the clerks' spellings.
2. **Write a query** in `branches/<branch>/scan-queries/<person>.json`. Keys: `label`, `surnames`, `given_names`, `father`, `mother`, `other_names` (each a list), `years` [from, to], `lang` (`de-pl` / `ru` / `hu`).
   - List every form: family, index and clerk spellings, Hebrew/Yiddish/civil pairs and diminutives (Feige/Fania/Fajga; Leib/Lejb/Aryeh/Leon), and the civil forms clerks wrote (Abram, Icek/Icko/Ica, Chana, Cwi, Mowsza/Moszek).
   - The matcher handles spelling and sound, **not meaning**, so list name pairs yourself. Mismatch ≠ elimination.
   - Give the parents' given names whenever they are known: they find the entry when the surname is misread. Without them, replay recall on Russian acts fell from 1.00 to 0.50 for fallback 1.
   - Galician "unehelich": put both parents' surnames in `surnames`.
   - Put the mother's maiden name and other relatives in `other_names`.
   - Sibling search: leave `given_names` empty and give both parents.
3. **The volume's own index comes first.** Russian-era books end with an alphabetical index (алфавитный указатель / skorowidz).
   - Read it with the index pick into `media/transcripts/<register>-index/` (apart from the acts, so `coverage` of the acts stays true), and match it.
   - Open the acts it names first. Act numbers on index lines are unvalidated: try ±2 and look-alike digits.
   - If none of them is the person, or the index has no hit, scan every act page of the year (step 5). A hit for a relative or namesake is not a hit for the target, and indexes omit and misread entries.
4. **Estimate, then ask.** Cost = pages × s/page (120 pages × 33 s ≈ 66 min with claude-sonnet).
   - Ask the researcher before anything over ~1 h or ~50 pages, and before bulk-downloading a register.
   - Before downloading, run `df -g /System/Volumes/Data` and stop below 8 GB free. Space downloads ≥ 3 s apart, and keep bulk scans in `media/scans/<register>/`.
5. **Transcribe** with the scan default. Then run `python3 -I scripts/htr_contest/find_person.py coverage media/transcripts/<register>` on the act folder. It lists failed or thin pages, number gaps, and entries whose names are unreadable, partly [illegible] or in a script it cannot romanize; re-read those with fallback 1 or check them by eye.
   - Audit the isolation: `grep -rlE '<your-repo>|\.claude/projects' media/transcripts/<register> --exclude='*__run*.json*'` must print nothing. A hit means a reader looked outside its folder: drop that reading.
6. **Match:** `python3 -I scripts/htr_contest/find_person.py match <query> media/transcripts/<register>`.
   - It searches every reader's best reading **and every alternative**, within a small edit distance or a shared Daitch–Mokotoff code. It also strips Polish/Russian endings (Sztajnów, Sulkiesówna) and matches the letters beside an [illegible] (Sul[illegible]).
   - Sound codes count only with ≥ 3 digits, so for short surnames (Kac, Wajs) list every spelling yourself.
   - Tier **A** = surname + another name.
   - Tier **B** = the surname alone; two other names; the surname only in other columns (a witness or godparent?); or one name where a surname, father or mother reading is (partly) unreadable.
   - Tier **C** = one name only; hidden unless `--min-tier C`.
   - A date outside `years` ± 2 turns an A into a B, with a note; it never hides a hit (late registrations, misread years).
7. **Escalate.** Every A goes to proof mode. For every B, look at the crop and escalate if a second fact fits (parent, date, house, place). A witness or godparent with the surname is a lead.
8. **No candidate?** Re-read the likeliest pages (expected date ± 6 months) with fallback 1 and match again.
   - Then run `match --min-tier C --json` and review every C hit dated in that window, or whose father's or mother's given name fits: a surname misread beyond the tolerance leaves only a C.
   - Then log a **scoped negative** in the session's research log: register, pages, readers, prompt sha256, query spellings, unscreened entries, how many C hits were reviewed, date. It is evidence about this scan, not about the person.
   - If a plan's quota runs out, pause and resume. Never finish a scan with a model outside the picks.

### Proof mode: evidence-grade reading of a located entry
1. **Columns first.** Map the columns (step 4) **before** looking at any model output. Then run the proof default on the whole page as downloaded (never a crop), and match its entry to the located row by entry no. and a name.
2. **Add the 2nd reader (other CLI)** when any decisive field (names, parents, date, house no.):
   - is hedged;
   - differs from the index, or is missing from it;
   - contradicts another source;
   - or the record type is untested.
3. **Check inside the entry, even when the readers agree.**
   - Dates: registration vs event date, digits vs written-out words, two calendars (use the later).
   - The child's surname = the father's (Galician unehelich: the mother's). The mother's name is the weakest field.
   - Readers can share a mistake: Warsaw 1848 act 43 is an 1834 birth, and claude-opus, claude-opus+tools and gpt-6.1-sol+tools each read 1847-09-16 in one run without a hedge.
4. **Settle disagreements on the full-resolution crop.** Test each candidate (each reader's best + alternatives, your reading, the index) letter by letter against the same letters elsewhere in this clerk's hand.
   - A Claude hedge means "unresolved": its hedged best reading is right only 0.35–0.5 of the time, so test every alternative.
   - GPT alternatives rarely hold the answer.
   - A Gemini 3.1 Pro plain string is not a confidence claim.
   - No candidate fits → `[?]`. Still disputed → show the researcher the crop.
5. **Grade each decisive reading.** Brackets give the share exact in the contest.
   - **Confirmed:** two readers on different CLIs agree, both plain (0.97, measured on 67 fields, only 5 of them on Russian acts), or a plain reading equals the published index; in both cases step 3 must pass.
   - **Probable:** the readers agree but one hedged; or two Claude readers, or two runs of one reader, agree (0.91–0.95); or there is one plain blind reading and no index.
   - **Possible:** the readers disagree and the image favours one, or only you see it.
   - **Speculative:** illegible, or resting on the name we hoped for.

   A reading you favour against both blind readers is at most possible until the researcher has seen the crop. A conclusion is never stronger than its weakest decisive reading.

### Reading whole books (bulk pipeline; measured on Białystok registers 1906–42, Oct 2026)
- **Keep claude-opus+tools for bulk reading.** Its ≈74k tokens per page are mostly cache reads: ≈$0.25 per page equivalent, 40–80 s. Tiles cut by code and read look-only cost more (4 tiles ≈$0.36 per page, and the lower tiles lose the page header, and with it the dates); 2 halves cost ≈$0.18 per page but misread names that opus+tools got right.
- **Throughput is limited by the plan's 5-hour window and by the network, not by the CLI.** 10 parallel readers ≈ 470 pages/h; 16 readers once filled the 5-hour window. Prefetch upcoming scans from cloud storage in the background, and stop the batch at a weekly-usage threshold.
- **Tools-mode logs are heavy**: each stdout embeds every crop the reader viewed as base64 (~4 MB per page), plus a work folder of crops (~3 MB per page). Compress the logs with xz (≈40%); the crops are scratch and can be dropped; keep both out of backups.
- **A symlinked scan must keep its link name as the page id** (`Path.absolute()`, not `resolve()`), or results land under the target's file name and a pipeline that checks for finished pages re-reads them forever.
- **Blind readers still miss decisive short words**: "ur. w Gródku" (born in Gródek) was read as "w Grodnie" (Grodno) by opus+tools and on a first look. Zoom every birthplace, maiden name and parent name that will drive a search, even on a page the readers agree on.

## Reading the handwriting
- **German Kurrent** (Galicia until ~1890s, mixed with Latin script): `e` looks like `n`; long `ſ` looks like `f`; `h` has a loop below the line; `ü/ö` umlaut is a breve or two strokes. Names are usually in **Latin script** even within a Kurrent text — use that switch to spot names.
- **Polish interwar** (1918–39), Latin script: watch `ł`, `ż/ź`, and the written-out ordinal dates (`dziewiątego czerwca` = 9 June).
- **Russian** (Congress Poland 1868–1917): see the region-russia-pale skill; pre-1918 orthography (ѣ, і, ъ).
- **Hebrew/Yiddish** headstones: see the jewish-naming skill.
- When unsure of a word, compare the same word elsewhere on the page (the same clerk writes "Szczerzec" twenty times).
- A wavy line in a column = "nothing / not applicable", not an illegible entry.

## Format sheets

### Galicia, Jewish births (Austrian form, 1877–~1918), German/Polish bilingual header
| Col | Header (DE / PL) | Notes |
|-----|------------------|-------|
| 1 | Fortlaufende Zahl / Liczba porządkowa | entry (akt) no. |
| 2 | Der Geburt: Tag, Monat, Jahr, Ort, Haus-Nr. | birth date + place + house no. |
| 3 | Der Beschneidung oder Namens-Beilegung | circumcision / naming date + place |
| 4 | Name, Geschlecht (männlich/weiblich) | child |
| 5 | ehelich / angeblich ehelich / unehelich | **"unehelich" usually = religious-only marriage, not true illegitimacy**. Child takes the mother's surname; JRI shows it as `[FATHER / MOTHER]` |
| 6 | Father: name, occupation, residence | often blank when "unehelich" |
| 7 | Mother: name, her parents, residence | **gold: maternal grandparents**. Watch for a note "Dieselbe lebte mit X nach mosaischem Ritus" = the father, by religious marriage |
| 8 | Pathen / Sandek / Schames | godparents/sandek (often relatives!) |
| 9 | Beschneider | mohel |
| 10 | Hebamme | midwife |
| 11 | Todt geborene Kinder | stillborn |
| 12 | Anmerkung | later notes: legitimation, name changes, marriage, death — always read |

Useful words: *Jäner* = January; *Tochter des* = daughter of; *Pächter / Mühlpächter* = leaseholder / mill-leaseholder; *Wirth* = innkeeper/farmer; *Handelsmann / Geschäftsmann* = trader; *Schulsänger* = synagogue cantor; *Hebamme* = midwife; *nach mosaischem Ritus* = by Jewish rite.

### Interwar Poland, Jewish deaths (Księga zmarłych, Polish form, 1920s–30s)
| Col | Header | Notes |
|-----|--------|-------|
| 1 | Liczba porządkowa | entry no. |
| 2 | Data i liczba karty oględzin… | inspection place/date, card no., examiner |
| 3 | Śmierci: godzina, dzień, miesiąc, rok, miejsce i nr domu | death time, date (written out), place + house |
| 4 | Pogrzebu: dzień, miesiąc, rok, miejsce | burial — gives the **cemetery town** |
| 5 | Zmarłego: imię, nazwisko, stan, zatrudnienie; imiona rodziców | deceased; **parents only for children/unmarried** |
| 5b | Miejsce zamieszkania | residence |
| 6 | Płeć: męska / żeńska | sex — indexes get this wrong; trust the column |
| 7 | Wiek: lat / miesięcy | age (often ±1 yr) |
| 8 | Stan: wolny / żonaty, zamężna / wdowiec, wdowa | marital status |
| 9 | Choroba i rodzaj śmierci | cause |
| 10 | Uwaga | notes |

Useful words: *kupiec* = merchant; *zarobnik* = labourer; *rolnik* = farmer; *właściciel(ka)* = owner; *dziecko* = child; *zapalenie płuc / opłucnej* = pneumonia / pleurisy; *starość* = old age; *wada / niedomoga serca* = heart failure.

## Fetching scans — AGAD Fond 300 (Galician Jewish registers)
- JRI-Poland "View Image" links go to `legacy.jri-poland.org/databases/agadimage3.php?dba=…&syg=<sygn>&…`, which redirects to the AGAD album `agadd2.home.net.pl/metrykalia/300_new/album/<sygn>/#img=<file>`.
- Full-resolution file: `…/album/<sygn>/slides/<file>.jpg` (thumbnails in `/thumbs/`). The file prefix varies by volume (`PL_1_300_<sygn>_NNNN` or `1_300_0_0_<sygn>_NNNN`) — read it from the redirect URL.
- "View **Nearby** Image" opens image 0001, not the entry. The JRI "Page" column ≈ register page; scan image = page + 1 or so. Fetch neighbours until the entry no. matches.
- Free, no login. Gesher Galicia AGD covers other fonds (TsDIAL/DALO); scans there need membership — ask the user to log in.

## Extending this skill
Whenever a new record type or country comes up (Russian metrical books, Romanian civil records, Hungarian registers, Israeli/Mandate documents, headstones), add a format sheet here with the column map, key vocabulary, and the access route that worked. Keep each sheet ≤40 lines. For AI reading of a new record type or language, key one page and follow "Updating" in [references/model-performance.md](references/model-performance.md).
