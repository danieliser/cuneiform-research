# Reading aids review v0.1 (Q-025) and parser contamination finding

Independent review, 2026-11-05. Reviewer: review sub-agent (no subagents used). Read-only on code, canonical data and services.

- UI `cuneiform-ui` `6354880` (live on 127.0.0.1:8740; working tree clean before and after).
- Research `251377e` (`docs/READING-AIDS-SOURCES.md`, QUEUE Q-025 `IN_REVIEW`). Backend pin `057a0b7`.
- Dataset `snapshot:965aa26214dc0388dd3af1be367d2acc`, read only through its `parquet/` exports (no DuckDB file lock, no copy, no hashing per test).
- Benchmarks `cuneiform-benchmarks` `0be7e12`, read only.
- Retained references `.output/q025-refs/` (no downloads). Hashes re-checked: `labels_validator.py` `4656a5a8…`, `translation_line.py` `0d4b5720…`, `ebl-atf.md` `be7c5ccf…`, `osl.asl` `b1555336…`, Noto zip `b686250d…`, BAPLAR recordings page `51a4796f…`. All match the doc.
- Scratch: `cuneiform-research/.output/q025-review/` (ignored, 0.9 MB; scripts, outputs and the full affected-ID lists). Peak memory of any check was 620 MB.

## Verdicts

| Subject | Verdict |
|---|---|
| UI reading aids for browsing (explorations, placed translations, glyphs, reading panel, pronunciation) | **CONDITIONAL ACCEPT.** Four small UI fixes (C1–C4 below). None needs a backend change. |
| Corpus linguistic quality (ATF readings layer as "transliteration only") | **NOT ACCEPTED.** 129 non-text lines are stored as text lines (F1). Small, but it blocks any claim that the ATF readings layer contains only transliteration. A canonical fix needs a new parser version and a new immutable snapshot. |
| Prior engineering acceptance of snapshot `965aa262` (Q-023) | **Still holds.** Projections, postings and n-grams faithfully match the stored rows. The defect is in what the parser stored, not in the projection or the publication. |
| Benchmarks A–D (`0be7e12`) | **Unaffected** in measured results (F1, impact section). |
| Q-024 common flows (in scope here) | No regression seen. Deep links work on load, but in-page hash changes do not re-render (N5). |

Tests: `bin/cuneiform-ui test` passed: 24 isolation checks ok, then `Ran 72 tests in 231.331s`, `OK`, 0 skipped, 0 failures. Log: `.output/q025-review/ui-test.log`. The suite does not cover F1's leak paths, C2 or C3.

Some claims below need a philologist (marked **[philologist]**). I checked them against the retained source texts, not against independent scholarship.

## Findings, most severe first

### F1. Parser stores translation and note lines as text lines (backend, `conservative-3`). Severity: high for research claims, low for browsing

Reproduced independently from the Parquet exports: **129 `line` rows in 49 records**, all with a label starting `#`. They hold **2,258 occurrences** (1,579 `reading`, 626 `unsupported`, 53 `gap`), **1,579 postings** (`atf`/`source`) and **7,779 n-grams** (`atf`/`source`: 2,129 / 2,002 / 1,878 / 1,770 for lengths 2–5). The `strict` policy has none, as expected. The builder's counts (129 / 49 / 2,258) are exact.

**Root cause.** `cuneiform/adapters.py:104`: `re.match(r"([^\s]+)\.\s+(.*)", line)` accepts any line whose first run without spaces ends in `.` followed by whitespace. Only `@` lines are filtered out first (`:105–106`). `#tr…` lines are recorded as translations (`:107–114`) and then also fall through to the text-line path (`:115–122`), because the check at `:115` only skips lines that *fail* the line regex. Seven forms match:

| Raw form (scan of all 20,896 raw ATF texts) | Rows | Also stored as a translation? |
|---|---|---|
| `#tr.en.(r.e. iii 4'): …`, `(l.e. …)`, `(b.e. …)`, `(t.e. …)`, `#tr.en:. …` (extent or text containing `. `) | 57 | yes (`:108` matches) |
| `#tr.en. Urama;`, `#tr.ar. …`, `#tr. en: …` (dot instead of colon) | 63 | **no**: excluded as "unsupported translation syntax" and *also* stored as a text line |
| `#note. Gloss between signs.` | 8 | n/a |
| `#Vgl. KADP 33 Vs. 6-7` | 1 | n/a |

The builder said this happens "when an extent contains `. `". That covers only 57 of the 129 rows; 72 have no extent at all. No other label shape is affected: every label not starting with `#` matches a line-number pattern (checked across all 314,884 ATF lines).

**Signs field: not contaminated.** In all 49 records the `signs` line count equals the clean ATF line count. eBL's own sign layer has no row for these lines. Two consequences: (a) the `signs` data is clean; (b) any consumer that pairs ATF and `signs` lines *by ordinal* goes out of step after the first contaminated line in those 49 records. `tools/check_sign_map.py:67` filters `#` labels before pairing, so it is correct. No UI path pairs the two by ordinal.

**Effect on genuine readings.** The 1,579 contaminated readings cover 517 distinct values. 489 of them (1,416 positions) occur nowhere else: English words such as `the` 129 and `of` 121. The other 28 values (163 positions) also occur as real readings, and inflate them:

| Value | Contaminated / total ATF positions |
|---|---|
| `he` | 20 / 28 (71%) |
| `I` | 13 / 27 |
| `let` | 5 / 20 |
| `as` | 5 / 28 |
| `in` | 22 / 199 |
| `is` | 17 / 184 |
| `a` | 27 / 2,903 |
| `i` | 8 / 677 |
| `me` | 7 / 537 |
| `KAŠ` | 2 / 832 |
| `ša` | 1 / 3,414 |

Of 6,071 distinct contaminated n-gram patterns, 51 also occur in genuine lines (327 contaminated rows).

**Requested queries: zero impact.** `DIŠ`, `ina`, `DIŠ ina`, `ABZ480` and `ABZ13` have 0 contaminated positions. The two ABZ labels are in the `signs` field, which is clean.

**Benchmarks: zero measured impact.** Stages B, C and D train and score on `signs` only. ATF is loaded but used only for exact-duplicate family grouping (`bench/core.py:301–312`), and then set to `None`. Removing the `#` lines from the 49 records creates 0 new exact duplicates. Stage A has 12 ATF exact queries; none contains a contaminated reading. Its brute-force-versus-index parity holds because both sides read the same rows.

**UI: "skips and labels them" is only partly true.**
- Labelled correctly: the tablet view ("A translation or note line that the backend parser kept as text (conservative-3); not part of the transliteration"), translation placement (`translations.py:55`) and omen openings (`explorations.py:202`).
- **Not filtered:** every path built on `posting`/`ngram`. That covers sequence search, usage counts, suggestions (`questions.py:110–121, 170–173, 266, 295, 314, 607`), and the reading panel's positions, genre counts and translated examples (`explorations.py:300–358`).
- Live result: `/api/reading?text=he` reports **28 positions on 11 tablets**. Its first "translated example" is **YBC.2394 line `#tr.en.(r.e`**, an English translation line shown as transliteration next to itself as its own "translation" (`status: extent`, 5 lines). `I` (YBC.2394, NBC.5345) and `let` (IM.49225, YBC.2394) behave the same way. The cause: `load_text` keeps comment rows in `order`, so the cover lookup at `explorations.py:338–339` finds the translation spanning the comment row.
- `GenreIndex` line totals (`reading_aids.py`, `count(*)` over `line`) also include the 129 rows.

**Other formats that lose translations.** These are not contamination but reduce translation coverage. 148 `#tr.` lines in non-standard syntax are excluded entirely: 85 such as `#tr.en(r i 8'):` and `#tr.en Total:`, plus the 63 above. About 125 more (`#tren:`, `#tr(2):`, `#tr(r 7):`; 130 lines starting `#tr` without a dot, a few of them empty or `#traces only`) are excluded as non-token lines. The UI therefore says "No source translation covers this example" for some lines that do have a translation in a non-standard form.

**Related parser artifact (not fixed, not blocking).** Every `@` line that is not `@column` becomes the *surface* (`adapters.py:106`). As a result, 8,362 ATF line rows in 41 label kinds carry a non-surface label as their surface, for example `colophon` 5,796 rows in 1,491 records, `date` 1,207, `seal 1` 523, `catchline` 266, `end of column` 101. The true surface is lost, and the tablet view shows "COLOPHON" or "DATE" as the surface heading. I did not measure how many of the 556 unresolved extents this causes.

**Narrow canonical fix (recommendation only; no code changed).**
1. In `Builder.text`, decide line kind before applying the line-number regex. A line starting with `#` (translation, note or comment), `$` or `&` is never a text line. A text-line label must match eBL's line-number grammar, roughly `^(?:[A-Za-z]\+)?\d+[a-z]?'*(?:-…)?$` plus `a+1`-style prefixes. Keep the existing exclusion bookkeeping.
2. Separately, for a later task: accept `#tr.<lang>.` (dot instead of colon) only if the parent decides to. Otherwise keep excluding it but never store it as a line. Treat `@colophon`, `@date`, `@seal N`, `@catchline` and similar as structure markers, not surfaces.
3. Bump `PARSER_VERSION` to `conservative-4` (sequence IDs include the parser version: `adapters.py:95`). Build a **new** snapshot ID from the same raw bytes. Do not mutate or republish `965aa262`. The atlas changes (adapter writes and coverage), so run `check_model_atlas.py`.
4. Expected deltas on the full release: `line` −129, `occurrence` −2,258, `posting` −1,579, `ngram` −7,779, `exclusion` +129 or so (one per removed line), edges in proportion. The `signs` field and all `signs` projections should be byte-identical. If the step-2 surface fix is included, only `line.surface` and `column_label` change for the 8,362 rows.

**Fixtures (to add with the fix):** one ATF text with these lines, asserting 0 text lines and 0 occurrences for every `#` line and unchanged rows for the real lines:
```
@obverse
1. a-na
#tr.en.(b.e. 1): There will never be any lawsuit.
#tr.en. Urama;
#tr. en: A quarter (mina) of silver
#tr.ar. خدمة
#tr.en:. .. Nunamnir(?) ...
#note. Gloss between signs.
#Vgl. KADP 33 Vs. 6-7
2. i-na
@colophon
3. DUB
```
Add an assertion that the `atf` text-line count equals the `signs` line count for a record with a `signs` field, and one that line 3 keeps a real surface (step 2 only).

**UI fix now, without waiting for the backend (C1):** add `AND NOT starts_with(coalesce(l.label,''),'#')` (through `token_context` or `line`) on every posting/ngram path, or drop comment rows before building `order` in `load_text`. Test: on a fixture with one contaminated line containing `he`, the reading panel for `he` must return no example from that line, and its position count must exclude it, or state "N positions are in lines the parser misfiled".

### F2. "Line N" overstates alignment for translations without an extent (UI). Severity: medium

eBL's rule, read from the retained `labels_validator.py`: a translation without an extent records the range `(current text index)` only. The UI implements this faithfully: my eBL-exact re-implementation agrees on all 21,971 single-line placements. In this corpus, though, editors often put one translation after the *last* line of a passage. The flagship medical example **K.2354** shows "ENGLISH · SOURCE EDITION · LINE 4" next to a translation that plainly renders lines 1–4 ("If a man's cranium retains heat…"). The raw ATF has `#tr.en:` with no extent after line 4, following `#note` lines.

Measured over all 21,971 single-line placements: **1,986 (9.0%) directly follow one or more text lines with no translation in the same language** (gap of 1: 1,149; 2: 358; 3 or more: 479; 10 or more: 65). Not every gap means a passage (broken lines are often left untranslated), but the label asserts more than the source does. The reading panel's caveat ("renders the whole line or passage") is good; the tablet and passage views lack it.

**Fix (C2):** when a `line` placement follows untranslated lines, label it "after line 4 · the source gives no range; it may also render earlier lines". Otherwise keep "line 4". Leave the data at `unresolved-span`. Test: a K.2354-shaped fixture (lines 1–4, one plain `#tr` after line 4) shows the hedged label; a text with a `#tr` after every line shows plain "line N".

### F3. Transliteration glyphs labelled "verified" check only the sign-name→code-point step (UI). Severity: medium **[philologist]**

The ABZ-number table is sound:
- I checked all 347 glyph-bearing ABZ signs against Unicode character names (Python `unicodedata` 15.1, an independent third source). 193 are exact simple-name matches. The other 154 are consistent compound or modifier encodings (`|GA₂×AN|` → GA2 TIMES AN, `@g` → GUNU, `&` → OVER, `%` → CROSSING, `@t` → TENU). No glyph identity was invented.
- Ambiguous sets fall closed: 79 labels have no glyph, including ABZ 597 GAR/LIMMU and ABZ 69 BAD/TIL/IDIM.
- The 9 eBL-only labels are marked "eBL sign list only" in the panel.
- The 649 old `sign_type` rows are not used as a denominator anywhere in the UI. The doc's denominators (421 labels; 2,429,757 positions) are correct.

The transliteration step is different. A value gets a glyph when exactly one *fetched* eBL sign lists it, and is then labelled `verified` whenever that sign's code point agrees with OSL *for the same sign name* (`reading_aids.py:61–63`). The **value→sign** attribution itself comes from eBL alone, and from only the 536 signs reachable through the 421 ABZ queries.

Cross-check against OSL values (retained `osl.asl`):
- Of 5,371 uniquely mapped values, OSL attributes 4,540 to the same sign name, has no entry for 512, and attributes **319** to a different or additional sign.
- Comparing code points for those 319: 88 are aliases with the same code point (for example MEŠ = `|ME.U.U.U|`). **208 values (9,995 part-positions, about 0.5%) would get a different code point under OSL**, for example:
  - `du₈`: GABA U+120EE vs DUH U+12083, 3,480 positions
  - `murub₄` / `muru₂`: MURUB₄ vs `UD@g`, 2,176
  - `de₂`: UMUM vs DE₂, 708
  - `kan₅`: `|KA×MI|` vs `|SAG×MI|`, 543
  - `mid`: BAD vs IDIM, 109
  - number signs such as `imin` and `limmu₂`, where both encodings exist
- OSL lists some values under several signs but eBL's fetched set has one: **`gu₃`** (KA or `|KA×GAR|`, 1,635 positions), `suhub₂`, and `ₓ` values such as `uₓ`, `zahₓ`, `munsubₓ`. These are collapsed to a single glyph.

Live: the `du₈` panel says "GABA · ABZ 167 · Glyph: eBL sign list, same code point in ORACC OSL". That is literally true for the name GABA, but OSL would draw `du₈` as DUH.

This is not invented identity: eBL treats GABA/DUH as one ABZ-167 sign. But "verified" claims a second source agreed on something it did not check. **Fix (C3):** for transliteration parts, compute a value-level check at build time: `agrees` if OSL lists the value under a sign with the same code points. For the 208 values, show the glyph as "eBL only (ORACC OSL attributes this value to another sign)". Never draw a single glyph for `ₓ` values. Keep "verified" for the ABZ-number view. Test: `du₈` and `gu₃` must not be labelled verified; `ina` (AŠ) and `KUR` stay verified.

The 99.67% agreement figure measures eBL's current list against eBL's own release (534,161 agree / 1,744 disagree on 57,652 of 266,564 comparable lines ≈ 21.6%; 1,931 records skipped for unequal line counts). The doc states this correctly ("measures agreement where comparison is possible, not overall correctness"). It is revision consistency, not independent verification. Keep that sentence next to the number wherever it is quoted. The sign-list revision remains unknown in the data, and the UI does not upgrade it.

### F4. Extent matching is looser than eBL's rule in 52 cases (UI). Severity: low

eBL looks up the exact `(column, surface, number)` triple anywhere in the text and rejects the line with "Extent … does not exist" otherwise (`_get_index` / `_validate_extent`). The UI ignores a missing column or surface and searches forward only (`translations.py:86–95`). My eBL-exact re-check: of the UI's 1,457 located extents, **1,405 resolve under eBL's rule and 52 do not**:
- 37 are "does not exist" under eBL. These are mostly `U.*` texts where the target line's stored surface is `date` or `colophon` (the F1 surface artifact).
- 15 have a flag inside the column (`o ii? 1'`) that eBL's grammar may not accept.

All 52 have exactly one candidate line, so no placement is a choice between alternatives. The 556 unresolved extents (525 outside the grammar, such as `1 1`; 31 not found) are quoted and shown at their first line, which is honest. **Fix:** report these 52 in a separate status, `extent-located-tolerant`, and correct the doc's "0 mismatches against an independent re-scan". That re-scan shares the UI's matching semantics, so it is not independent of them. Test: extent `15` with the target line on surface `date` returns the tolerant status.

### F5. Reading-note wording that the source does not support (UI). Severity: low **[philologist]**

Checked against the retained eBL MZL 748 text (`ebl-signs/dis.json`, field `mesZl`). The four DIŠ uses are supported:
- `DIŠ =^? šumma` "wenn (in Omina)", with Borger's query, and ¶ per Reiner, BPO
- numeral 1 and 60
- personal-name determinative
- `ana` marked "(n.)" = Neo-Assyrian

Three sentences need correcting:
- The `caution` sentence "The transliteration keeps DIŠ because the editor did not commit to one reading in the text itself" is not in the source and invents editorial intent. Writing DIŠ in capitals is the normal logogram convention.
- "In some first-millennium spellings" is broader than Borger's "(n.)".
- The omen view and the sequence example say "editors read DIŠ as šumma 'if'" without the query that the full note keeps.

**Fix (C4):** delete the caution sentence (or replace it with "Capitals give the sign name; the line's translation shows how the editor read it"); change the `ana` context to "In Neo-Assyrian spellings (Borger: n.)"; say "usually read šumma (Borger marks this with a query)" in the summaries. Test: snapshot the `reading-notes.json` strings.

Pronunciation and ORACC handling are sound:
- The citation form is labelled "a modern scholarly transcription, not a recording".
- The ORACC section says "How ORACC ccpo editors lemmatized this exact written form… dictionary glosses… not translations". It does not claim the occurrence is lemmatized.
- `DIŠ` correctly reports no ccpo form.
- BAPLAR is a link only, matched by composition and described as "another manuscript or edition, not this tablet". Nothing plays.

Minor: the header "Normalized form in ORACC ccpo: ina" could read "ORACC ccpo citation form (from other texts)".

### Non-blocking notes

- **N1.** In K.2439, every one of 96 translations repeats "The source says it runs to "1 N"; that label is not in this edition…". Collapse this into one note per tablet when every extent fails the same way.
- **N2.** The tablet header shows "Period Neo-Assyrian" without the qualifier the period tables carry ("the source catalogue's dating of each tablet, not a dating of the passage"). Add "(source catalogue)".
- **N3.** Language codes `ebn`, `enb`, `em`, `ed` (6 segments) are source typos. They are excluded from the `xl=en` explorations without notice.
- **N4.** 486 text lines have more than one translation starting there (several languages). Display is fine; noted for counts.
- **N5 (Q-024 flow).** In-page hash navigation (setting `location.hash` from the K.2354 view to `#view=questions&q=x:omens`) did not re-render until reload. Fresh loads of all three review links work.

## Daily-use flows observed (desktop 1280×800 and iPhone 12 Pro 390×844)

- **Medical passages** (`q=x:medicine&xv=passages&xl=en`): clear title, "455 texts · 86 with an English translation in the source", genre note ("about half of all texts carry no genre label"), glyph caveat before the first glyph. Each translation is labelled "ENGLISH TRANSLATION · SOURCE EDITION · LINE N". On mobile there is no horizontal overflow (document width = 390) and translations stack under their line. The only misleading item is F2 on its first card.
- **K.2354 → translation and glyphs → `ina`**: selecting a reading opens a bottom bar whose first action is "Explain this reading". The panel runs from convention, to sign (AŠ · ABZ 1 · U+12038), to ORACC glosses labelled as glosses, to corpus counts (44,334 on 8,360 tablets, the open tablet's line first), to pronunciation caveats. It is layered, not a wall. On mobile it is about 2,000 px tall, which is long but ordered.
- **Related question** ("Where else does it occur?"): `DIŠ` → 30,975 matches with KWIC lines and a "By period" view. Works.
- **Omens** (`q=x:omens`): "18,614 of 68,951 lines (27%) in 3,743 divination texts open with DIŠ". The opening table includes translated examples and honest "No source translation covers this example" rows. This path filters `#` lines correctly. Caveat F5 applies to its summary sentence.
- Nothing claims glyph = photograph or handwriting ("not this tablet's handwriting, and this dataset has no photographs" appears in each view). Gloss and translation are kept apart.

## Minimal next tasks

1. **UI (one task, about half a day):** C1 filter `#` rows on posting/ngram paths and in `load_text` examples; C2 hedged single-line label; C3 value-level glyph check with 208 values downgraded and `ₓ` never drawn; C4 note wording; F4 tolerant status; doc correction of "independent re-scan". Tests listed under each finding, plus a live check that `/api/reading?text=he` has no `#tr` example.
2. **Backend (separate queue task):** `conservative-4` text-line gate (and optionally the structure-marker surfaces) with the fixtures above, a new snapshot ID, and a recount matching the expected deltas exactly. Then re-run benchmark preflight. Signs projections must be identical, so B/C/D need no rerun unless the hashes differ.
3. **Philologist pass:** F3 value attributions (`du₈`, `murub₄`, `de₂`, `kan₅`, `mid`, `gu₃`, numbers) and F5 wording.

## Evidence index (`cuneiform-research/.output/q025-review/`)

| File | Content |
|---|---|
| `scripts/contam_lines.py` → `contam_lines.json` | the 129 line IDs, record IDs, labels, raw text |
| `scripts/contam_counts.py` → `contam_occurrences.parquet`, `contam_postings.parquet`, `contam_ngrams.parquet` | every affected occurrence, posting and n-gram ID |
| `scripts/contam_overlap.py` | overlap with genuine readings; signs-line equality |
| `scripts/tr_forms.py` → `tr_forms.txt` | all raw `#tr` forms and their handling |
| `scripts/placement_recheck.py` → `placement_recheck.txt`; `scripts/loose_extent.py` → `loose_extent.json` | eBL-exact placement re-implementation |
| `scripts/hidden_ambig.py`, `scripts/hidden_cp.py` → `hidden_ambig.json` | OSL value-level cross-check |
| `scripts/bench_impact.py` → `bench_impact.txt` | benchmark impact |
| `reading_{he,I,let,ina,du8,gu3}.json` | live API responses |
| `ui-test.log` | test run |

## Appendix: affected records (F1)

Columns: source key, record ID, contaminated line rows, occurrences, postings, n-grams, labels. Totals 129 / 2,258 / 1,579 / 7,779.

| Source key | Record | Lines | Occ. | Post. | N-grams | Labels |
|---|---|---|---|---|---|---|
| BM.36276 | `source:137dcff9be1187b0801840af9e465220` | 1 | 25 | 16 | 90 | `#tr.en.(b.e` |
| BM.38383 | `source:7a3e3c851f2d33cd6eb30c9ac7806cf8` | 5 | 15 | 10 | 15 | `#note` |
| BM.98543 | `source:a9b043a55c2fba2d3a44a4620d6064e1` | 13 | 94 | 53 | 251 | `#tr` |
| CBS.13618 | `source:50bf36f3e1852b1316cb44ba368ce59e` | 1 | 3 | 0 | 3 | `#tr.en:` |
| IM.135362 | `source:03b58a7c6e93908b1f79c5a3d3a0a67a` | 1 | 18 | 15 | 62 | `#tr.en.(b.e` |
| IM.208060 | `source:9157b24f6d34d38126dddad2c7737899` | 1 | 2 | 1 | 1 | `#tr.ar` |
| IM.208066 | `source:1f815731e244dbde8a0d37388a79ac37` | 1 | 4 | 3 | 6 | `#tr.ar` |
| IM.208078 | `source:068f75132c783dce4830c08fbee01db7` | 1 | 3 | 3 | 3 | `#tr.ar` |
| IM.43650 | `source:48e43d87a619f6d680712ce96d52c51a` | 1 | 1 | 0 | 0 | `#tr.en` |
| IM.43652 | `source:12f42ff685ca510bac19a72cfe1e9f63` | 1 | 4 | 1 | 6 | `#tr.en` |
| IM.43653 | `source:4f65c73eca3a706b0c4db3bad2048578` | 1 | 7 | 5 | 18 | `#tr.en` |
| IM.49225 | `source:15a9281844f80d9244fd098cf4fef802` | 2 | 19 | 15 | 56 | `#tr.en.(l.e` |
| IM.49535 | `source:d4e793437b7b82159a5607172e54c426` | 1 | 16 | 7 | 54 | `#tr.en` |
| IM.61432 | `source:07d4d96bd99ffa646e716332647e96c9` | 1 | 12 | 4 | 38 | `#tr.en` |
| IM.75922 | `source:ecdaacf8d924a07307a5ed64aacbe6c4` | 1 | 25 | 13 | 90 | `#tr.en.(t.e` |
| IM.75999 | `source:23d7554bab2c28bd690291bce8d5d790` | 1 | 21 | 11 | 74 | `#tr.en.(t.e` |
| IM.76844 | `source:2931a5eb8b489bd2615d0904b762e485` | 1 | 14 | 8 | 46 | `#tr.en.(t.e` |
| IM.76988 | `source:58dd52759cd77610baca687996311228` | 1 | 21 | 11 | 74 | `#tr.en.(t.e` |
| K.2290 | `source:4e429bb17bd95e02339bdeef2a0debce` | 1 | 8 | 5 | 22 | `#note` |
| K.2419 | `source:90db9ce5c2f49f9558e6ca732738c8d8` | 1 | 8 | 5 | 22 | `#note` |
| K.2777 | `source:79a7d2b18c285088c45f0380785ea9de` | 1 | 19 | 15 | 66 | `#tr` |
| K.4095 | `source:366b36e19f2cc320d4e574d6ca8a24fc` | 1 | 10 | 4 | 30 | `#note` |
| K.7845 | `source:343a1225d28598020e2d92df5c7f1a4a` | 1 | 4 | 1 | 6 | `#Vgl` |
| MLC.1804 | `source:8075e52e45574d004a6ceeded23563ae` | 1 | 23 | 14 | 82 | `#tr.en.(b.e` |
| MLC.2626 | `source:5e66b7b93104c8384d1fbf5995ddfc20` | 1 | 4 | 0 | 6 | `#tr.en` |
| NBC.1120 | `source:8fb3262fd1844ed50cc9964d95b1978d` | 1 | 21 | 15 | 74 | `#tr.en.(b.e` |
| NBC.3678 | `source:ef74f1171c3cdff02e5dab0e053173d1` | 1 | 21 | 12 | 74 | `#tr.en` |
| NBC.5345 | `source:ae5918a057e2907915e354b9712cd506` | 2 | 37 | 25 | 128 | `#tr.en.(l.e` |
| NBC.6869 | `source:3107254024d6ebf3d66f22822601622f` | 4 | 56 | 36 | 184 | `#tr.en` |
| NCBT.84 | `source:4257a56802a1cb878454d347d5cdb48d` | 1 | 11 | 5 | 34 | `#tr.en.(b.e` |
| Rm-II.109 | `source:fecc3378217a4b3971ac0d7359c3c55f` | 1 | 21 | 11 | 74 | `#tr` |
| U.17246g | `source:8f531eba96f1af73aa095d3f35b9521a` | 2 | 5 | 3 | 4 | `#tr.en` |
| U.17249.20 | `source:617e6ef80e4c9dbf24df06ef43d29835` | 1 | 1 | 0 | 0 | `#tr.en` |
| U.3623 | `source:ede9839b1533bea177d8760a173e3d97` | 1 | 3 | 2 | 3 | `#tr.en` |
| U.3738 | `source:6a53a117e5eea5c16d49ebd5a8bc4e65` | 1 | 2 | 1 | 1 | `#tr.en` |
| U.3779 | `source:f6f33c6441377d87517d0ee9b04dc610` | 1 | 3 | 2 | 3 | `#tr.en` |
| U.3887 | `source:2cd280540c2747cdef2014c21dcaa0f4` | 1 | 4 | 2 | 6 | `#tr.en` |
| U.4030 | `source:62e69f9705538df0eff89e7a7a9b7b8a` | 1 | 4 | 2 | 6 | `#tr.en` |
| U.4137 | `source:db92653b585b9d806a9939040eceb7c7` | 1 | 3 | 2 | 3 | `#tr.en` |
| U.4220 | `source:84b7cedbfeceae5017e7af560b0868ac` | 1 | 6 | 2 | 14 | `#tr.en` |
| U.4415 | `source:1a7f032f0734b6e0a8ef31bc37cad3c9` | 1 | 4 | 2 | 6 | `#tr.en` |
| U.4629 | `source:6898b340b6b0abe217df0f74eebae903` | 1 | 5 | 2 | 10 | `#tr.en` |
| U.4976 | `source:9cca619ed7d8426d669ca2a5b677623b` | 1 | 4 | 2 | 6 | `#tr.en` |
| YBC.11389 | `source:91859a4e1ff14b2f58a91d6efa5755f7` | 7 | 247 | 171 | 918 | `#tr.en` |
| YBC.2394 | `source:75d574dcb21724799cfd290e3b84d253` | 41 | 1047 | 808 | 3778 | `#tr.en.(b.e`, `#tr.en.(l.e`, `#tr.en.(r.e` |
| YBC.4110 | `source:0d7c5c0e591a9aa6dd643ef4ab7df2f3` | 1 | 33 | 23 | 122 | `#tr.en.(b.e` |
| YBC.7489 | `source:5b3013e0f0d4d45513e1eab345893587` | 1 | 62 | 40 | 238 | `#tr.en.(b.e` |
| YBC.754 | `source:44e2cd2caf4687371114f4e0d8bd91a7` | 3 | 32 | 22 | 98 | `#tr.en` |
| YBC.9839 | `source:5f415b6113e9fc119c627f542c7e84d7` | 11 | 246 | 169 | 874 | `#tr.en` |
