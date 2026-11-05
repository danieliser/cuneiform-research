# Model atlas

This is the agent-readable map of the cuneiform evidence model. For every part of the model it gives the documents, artifacts and witnesses; the signs, readings and occurrences; the sequences, n-grams and patterns; the words, lemmas, senses and translations; claims; time; media; and interfaces. It also records how much of each part is modeled, implemented, populated and verified. The visual version is [model-atlas.html](model-atlas.html), a standalone file that needs no server. Active work is in [QUEUE.md](../QUEUE.md).

## Canonical source and drift rule

- [`docs/model-atlas.json`](model-atlas.json) is the **only canonical machine model**. Everything below the generated marker in this file, and the data block embedded in `model-atlas.html`, is regenerated from it.
- Code is the authority for what exists. `python3 scripts/check_model_atlas.py` fails if any of these drift: schema tables and columns, views, `NodeKind`, `EDGE_TYPES` (literal and `EDGE_TYPES[...] =` entries), edge kinds written by the adapters and their qualification keys, `portable_edge` kinds, snapshot-manifest keys on every construction path (with `**` spreads followed through call sites, and per-source optional keys), the keys `storage.verify()` requires, rights namespaces (literal and `RIGHTS[...] =` entries), every source kind the code dispatches on, versions, and the generated files.
- Static analysis fails closed for the forms it tracks. If a manifest, rights or edge registry is built in a form the checker cannot resolve (for example `manifest.update(x)`, `**helper()`, an alias such as `alias = meta`, passing the dict to a helper, `dict.update(meta, …)`, or a local alias of `RIGHTS`), the check fails instead of passing an incomplete inventory. Any write of a computed `manifest_sha256` is a signing site, whatever the variable is called. Each per-snapshot rights statement is fingerprinted (`statement_sha256`), and a computed source kind must use exactly `RIGHTS[source]`. The only way past an unsupported form is a declared `static_contracts` entry that cites a test and the SHA-256 of the exact files.
- **Limits of the static checks.** They are a bounded drift detector for the code shapes this package uses, not a general Python analyzer. Dynamic dispatch, `getattr`/`setattr`, `exec`, mutation through objects outside the tracked names, and code outside `cuneiform/*.py` are not modelled. When the checker reports "unsupported static analysis", rewrite the code into a supported form rather than growing the analyzer.
- Every source kind needs a rights entry or a declared per-snapshot rights source, and either a `--runtime` input or a `runtime_unexercised` reason.
- `verified` levels must be backed by a recorded run in `verification_runs`. The checker resolves `baseline_commit` and every run's `code_ref` with git (7–40 hex naming a commit; task IDs, trees and unknown hex are refused) and compares each run's tree under `cuneiform/`, `tests/`, `fixtures/` and `sources/` with the checked code. Doc-only commits keep runs current. Any code edit after the baseline reports "baseline stale" until the runs are redone and the baseline moves. Each run names its observer. A level whose runs were all reported by the implementer renders as **UNVERIFIED**. Pass `--repo` when `--root` is an export without `.git`.
- `--runtime` (run with the project venv, which has duckdb) drives the real adapters for `ebl`, `cdli`, `ebl-cohort` and `oracc-selection` on synthetic fixtures and the retained samples in memory. It fails if any `populated` claim is above or below what was observed, or if a `sample` claim cannot be checked because samples are missing.
- **Corpus evidence** may cite only snapshots listed as `accepted` in `corpus_snapshots`, with a `reviews/` file that read them. Incident (same-ID rebuild) and pending-review snapshots are listed so that they cannot be cited. `--runtime` reads each cited snapshot read-only with the checker's own reader (`corpus-evidence-reader-1`): a plain ledger publication (legacy row, or reserve then commit), no incident note, the manifest digest pinned in the atlas, the manifest.json bytes for format-2 rows, every payload hash, no unlisted files, and row counts from the hashed Parquet, which must equal both the manifest counts and the cited count. It also checks manifest keys against the atlas fields and `rights.status` against `rights_status`, then cross-checks the backend's own `storage.verified(..., ledger='require')`. Manifest counts are never trusted on their own. Limit: the same owner can rewrite Parquet, manifest, ledger and the atlas pin consistently; the ledger records what writers observed and is not a signature.
- `--self-test` injects deliberate mismatches into a temporary copy and confirms that each one is caught. Targets are chosen at run time, so the cases survive model changes; `--git-ref WORKTREE` runs them against uncommitted code.
- Edit the JSON, run `--write`, then run `--check`. Do not hand-edit the generated block or the HTML data block.

## How to read a status

Every entry has four status dimensions that move independently:

| Dimension | Values | Meaning |
|---|---|---|
| modeled | `specified`, `documented`, `proposed` | Where the concept comes from: SPEC-v0.2, an implementation contract doc, or a proposal in this atlas that is waiting for a decision |
| implemented | `none`, `schema`, `code` | `schema` means the table or edge type exists but nothing writes to it, so it is empty by construction |
| populated | `none`, `synthetic`, `sample`, `corpus` | The highest level of real rows actually observed. `corpus` means rows cited by count in a persisted pilot snapshot. The pilot snapshots are hash-ordered cohorts and selections, **not the full corpus**. |
| verified | `none`, `unit`, `disk`, `reviewed` | Executed checks, each backed by a recorded run with its observer. `disk (UNVERIFIED)` means only the implementer reported the run. **Nothing is at `reviewed`.** |

Planned and proposed layers are never loaded data. A table that is empty because of its schema means the layer is unavailable. It does not mean the corpus lacks that layer. For example, zero lemmas means there is no lemma source, not that no words exist.

## Invariants every change must preserve

1. **Source first.** Raw bytes, source records and their locators are authoritative. Projections reorganize them. They never validate readings or fill in missing linguistic layers.
2. **Deterministic, scoped IDs** of the form `identity(kind, …)`, which is a 32-hex prefix of a SHA-256 over canonical JSON. Paths and timestamps never enter IDs. Cross-source equivalence is a Claim, never a merge.
3. **Represented positions are not ancient signs.** Gaps and opaque tokens stay positions, exact patterns never jump them, and `?` matches one represented position.
4. **ATF and source-derived signs are never aligned implicitly.** Translations are placed in a sequence, not aligned.
5. **Uncertainty is never upgraded.** A token without marks is `unmarked`/`unknown`, never `certain`/`intact`.
6. **Immutable snapshots.** Any new bytes, schema, parser or projection configuration create a new snapshot. There are no in-place migrations.
7. **Rights stay unresolved until a grant is established.** Public access is not permission.

## Temporal model

Status: **decisions accepted, nothing implemented.** The parent accepted the conservative defaults TD-1 to TD-7 on 2026-11-03 (Q-014). The value and claim shapes below stay `proposed` until Q-015 implements them. No temporal schema exists. Today the system records only processing time: the manifest's `retrieved_or_imported_at`, which is excluded from IDs. Every source date is kept only as raw JSON. The decisions and the implementation work are tracked as Q-014 and Q-015 in [QUEUE.md](../QUEUE.md).

**What can be dated.** These are different questions and are never merged:

| Role | Example question | Typical source assertion | Nature |
|---|---|---|---|
| content-event | When did the events referred to in the text happen? | date formulas, `dates_referenced` | valid time, attributed |
| composition | When was the work composed? | scholarly attribution | valid time, attributed |
| production | When was this artifact inscribed? | catalog `period`, script period | valid time, attributed |
| copy | When was this witness copied? | colophon, paleography | valid time, attributed |
| excavation/find | When was it found? | excavation records | valid time, attributed |
| acquisition/custody | When did an institution acquire or hold it? | accession and acquisition history | valid-time interval |
| publication/revision | When was an edition or catalog entry published or revised? | `publication_date`, `date_updated`, reference years | valid time of the source |
| knowledge | Since when has this system known the fact? | snapshot containing it | system time (snapshot boundary) |
| processing | When were the bytes retrieved or imported, or the projection built? | manifest timestamp | system time; never in IDs |

**Proposed shape.** A `node:DateClaim` is a Claim with predicate `dated_to`. It records the subject, the temporal role, the basis and a citation of the source, and holds a `value:TemporalExtent`. The extent keeps the verbatim string, the calendar and era convention, start and end years each with its own `closed`/`open`/`unknown` bound, a precision, an `approximate` flag, any structured native date, and the ID of the parsing rule. Competing datings remain separate claims. Nothing is averaged and no winner is chosen.

**Precision is never forced.** A range printed by a source gets precision `as-printed`: the bounds are kept exactly as printed, with no claim about the precision they imply. `unknown` is used when precision cannot be determined. Round numbers never imply century precision. A CDLI period gloss such as `Uruk III (ca. 3200-3000 BC)` is the catalog's chronology convention, printed on every row of that period. Its basis is `catalog-period-gloss`; it is not a dating of the object, and repeated copies of it are one assertion, not many.

**Observed raw shapes.** Persisted pilot JSON (structure only; no value is parsed or interpreted):

- CDLI artifact JSON (`snapshot:fc7c3504…`, 51 records): `period` is an object `{id, name, period, sequence, time_range}` (41) or null (10), for example `Neo-Assyrian (ca. 911-612 BC)` with `time_range` `ca. 911-612 BC`. `dates` is an empty list in all 51. `dates_referenced` is null in 50 and the regnal-style string `Artaxerxes.19.11.23` in one. `accession_no` values such as `1883-01-18, 0722` are registration numbers, not dates.
- eBL fragment JSON (`snapshot:c316e7cb…`, 51 records): `script` is `{period, periodModifier, sortKey, uncertain}`. `date` is null and `datesInText` is empty in all 51. `record` lists editorial events `{date, type, user}`, which are eBL system time, never ancient dates.

From the small retained CSV and K.1 samples (kept raw today):

- CDLI `period` gives a label plus a printed approximate range, for example `Uruk III (ca. 3200-3000 BC)`.
- `date_of_origin` and `dates_referenced` use the sentinel `00.00.00.00` or are empty.
- `publication_date` can be `1993` or `2015ff.`, which has an open end.
- `date_entered` uses a US-style system date, `12/4/2001`.
- `date_updated` is ISO.
- eBL records have `script.period` (`Neo-Babylonian`) with `periodModifier`, null `archaeology.date` and `findspot.date`, and numeric publication years under `references[].document.issued`.

**Accepted decisions** (Q-014, parent, 2026-11-03). Details are in the `decision:` entries below. A user decision is needed only if someone proposes a default `node:ChronologyScheme`, a calendar-conversion authority, or a departure from these choices. Unresolved historical chronology stays source-qualified and is never guessed.

- **TD-1.** Store astronomical year integers (1 BCE = 0) and display BCE/CE. Keep the verbatim string and the source era convention, so `BC-historical` has no year 0.
- **TD-2.** Bounds are explicit and precision is explicit, defaulting to `as-printed`. `ca.` sets a flag but does not widen the range. `ff.` makes the end open. Never invent midpoints, months or days.
- **TD-3.** A range printed by the source becomes a source-attributed approximate extent. Any other mapping from a label to an interval is a derived claim that cites a versioned `node:ChronologyScheme`, and no default chronology is chosen.
- **TD-4.** Native calendar and regnal dates are stored as structured native values. Converting them to Julian dates is a separate claim that cites its authority. No authority is adopted, so no conversions are produced.
- **TD-5.** Sentinels and empty strings mean unknown. Ambiguous system dates are parsed only under a format declared for that source.
- **TD-6.** Bitemporal model: the source asserts valid time, the snapshot that contains a fact gives knowledge time, and processing time lives in manifests. Timestamps never enter IDs.
- **TD-7.** Reuse the `claim` table with typed details first. Promote to its own table only if query needs justify it.

## Generated reference

<!-- ATLAS:BEGIN generated by scripts/check_model_atlas.py --write; do not edit by hand -->
Atlas revision 7 · updated 2026-11-05 · baseline `057a0b7` · schema `2` / parser `conservative-3` / projection `linked-1` · 107 entries.

### Status counts by domain

| Domain | Entries | Implemented code / schema / none | Populated (synthetic or sample) | Verified (unit or disk) |
|---|---|---|---|---|
| [Sources, snapshots & provenance](#domain-provenance) | 13 | 13 / 0 / 0 | 7 | 11 |
| [Artifacts, witnesses & compositions](#domain-documents) | 17 | 3 / 3 / 11 | 3 | 5 |
| [Sequences, lines & sign occurrences](#domain-signs) | 11 | 11 / 0 / 0 | 11 | 11 |
| [Positions, postings, n-grams & patterns](#domain-patterns) | 14 | 11 / 0 / 3 | 7 | 11 |
| [Words, lemmas, senses & translations](#domain-linguistic) | 12 | 10 / 2 / 0 | 10 | 10 |
| [Claims, alternatives & dependencies](#domain-claims) | 10 | 4 / 0 / 6 | 4 | 4 |
| [Temporal model (decisions accepted, not implemented)](#domain-temporal) | 15 | 1 / 0 / 14 | 0 | 1 |
| [Images, regions & embeddings (deferred)](#domain-media) | 7 | 0 / 0 / 7 | 0 | 0 |
| [Graph storage, export & agent interfaces](#domain-interfaces) | 8 | 6 / 0 / 2 | 3 | 4 |

### Verification runs

A `verified` status is backed by these recorded runs. Each run names who observed it and at which commit. A run at an older commit is historical evidence, not proof about present code.

| Run | Level | Outcome | Observer | Read back | Date | Code | Command | Result | Attribution |
|---|---|---|---|---|---|---|---|---|---|
| `parent-full-disk-2ab620b` | disk | pass | Parent orchestrator | yes | 2026-11-03 | `2ab620b` | `CUNEIFORM_RUN_DISK_TESTS=1 <venv>/python -B -m unittest discover -s tests` | Ran 31 tests in 11.869s, OK | Observed by the parent before the corpus edits and reported to the atlas workers. Historical: proves the 2ab620b code, not the current baseline. |
| `q003-inmemory-2ab620b` | unit | pass | Atlas worker, task 8d17b311 (Q-003) | yes | 2026-11-03 | `2ab620b` | `<venv>/python -B -m unittest discover -s tests` | Ran 31: 30 passed, 1 disk test skipped | Recorded in QUEUE.md at Q-003. Historical. |
| `q018-inmemory-2ab620b` | unit | pass | Atlas review-fix worker (Q-018) | yes | 2026-11-03 | `2ab620b` | `<venv>/python -B -m unittest discover -s tests (clean git archive export of HEAD at 09:57Z)` | Ran 31 tests in 12.049s, OK (skipped=1) | Own observation. Historical. |
| `corpus-worker-disk-d6049e2` | disk | pass | Corpus worker, task 64821742 (Q-001) | no (UNVERIFIED) | 2026-11-03 | `d6049e2` | `CUNEIFORM_RUN_DISK_TESTS=1 <venv>/python -B -m unittest discover -s tests` | Ran 43 tests in 15.4s, OK | UNVERIFIED: reported by the implementer in CHECKPOINT.md at d6049e2. The atlas worker did not re-run the disk tests. Independent corpus review (Q-005) pending. |
| `q007-inmemory-d6049e2` | unit | pass | Atlas sync worker (Q-007/Q-018) | yes | 2026-11-03 | `d6049e2` | `<venv>/python -B -m unittest discover -s tests (clean git archive export of d6049e2 at 10:10Z)` | Ran 43 tests in 14.340s, OK (skipped=5: four corpus disk tests incl. the publication-ledger test, and the snapshot disk test) | Own observation. Unit level only; it reads the five real snapshots read-only in test_snapshots_verify_parity_and_traces. |
| `q005-reviewer-disk-d6049e2` | disk | pass | Q-005 corpus reviewer (independent of the corpus worker) | yes | 2026-11-03 | `d6049e2` | `CUNEIFORM_RUN_DISK_TESTS=1 <venv>/python -B -m unittest discover -s tests` | Ran 43 tests in 16.007s, OK (in-memory run: 13.174s, OK, skipped=5) | Recorded in reviews/corpus-pilot-review-v0.1.md by its independent reviewer; accepted by the parent as independent evidence for d6049e2 (Q-019 S4). Not re-run by the atlas worker. Historical once the baseline moved to 94af111. |
| `backend-fix-disk-94af111` | disk | pass | Backend fix worker, task 44ddaeb1 (Q-001 fix round) | no (UNVERIFIED) | 2026-11-03 | `94af111` | `CUNEIFORM_RUN_DISK_TESTS=1 <venv>/python -B -m unittest discover -s tests` | Ran 59 tests, OK (in-memory: 59, OK, skipped=17) | UNVERIFIED as a claimant report: CHECKPOINT.md and docs/CORPUS-REVIEW-v0.1-DISPOSITION.md at 94af111. |
| `q020-disk-94af111` | disk | pass | Q-020 review sub-agent (independent of fix task 44ddaeb1) | yes | 2026-11-03 | `94af111` | `CUNEIFORM_RUN_DISK_TESTS=1 <venv>/python -B -m unittest discover -s tests -v (live checkout at 94af111; only QUEUE.md modified)` | Ran 59 tests in 30.048s, OK, 0 skipped | Recorded in reviews/corpus-pilot-review-v0.2.md by the independent reviewer; recorded with read_back true on the parent's instruction. The same review keeps Q-005 B2 open (its R1), so this run is test evidence, not acceptance. |
| `q021-inmemory-94af111` | unit | pass | Atlas repair worker (Q-021) | yes | 2026-11-03 | `94af111` | `<venv>/python -B -m unittest discover -s tests (clean git archive export of 94af111 at 11:02Z)` | Ran 59 tests in 14.890s, OK (skipped=17) | Own observation. |
| `backend-q022-disk-63f4221` | disk | pass | Q-022 backend fix worker (Q-020 R1-R5 round) | no (UNVERIFIED) | 2026-11-03 | `63f4221` | `CUNEIFORM_RUN_DISK_TESTS=1 <venv>/python -B -m unittest discover -s tests (forward and reversed order)` | Ran 70 tests, OK (59 + 11 new in tests/test_store_reads.py); 11/11 new fail on a 94af111 export | UNVERIFIED as a claimant report: commit message of 63f4221 and docs/CORPUS-REVIEW-v0.2-DISPOSITION.md. |
| `q021-disk-63f4221` | disk | pass | Atlas repair worker (Q-021) | yes | 2026-11-03 | `63f4221` | `CUNEIFORM_RUN_DISK_TESTS=1 <venv>/python -B -m unittest discover -s tests (clean git archive export of 63f4221)` | Ran 70 tests in 40.735s, OK, 0 skipped. Real store fingerprint (266 entries: snapshots, derived/cohorts, derived/exports, receipts) identical before and after; ledger SHA-256 6d359b74… unchanged. | Own observation. Test evidence for the code, not acceptance of the publication guarantee. |
| `q021-inmemory-63f4221` | unit | pass | Atlas repair worker (Q-021) | yes | 2026-11-03 | `63f4221` | `<venv>/python -B -m unittest discover -s tests (clean git archive export of 63f4221)` | Ran 70 tests in 14.325s, OK (skipped=28) | Own observation. |
| `review-v03-disk-63f4221` | disk | pass | Final publication review c5df3251 (independent of the Q-022 fix worker) | yes | 2026-11-03 | `63f4221` | `CUNEIFORM_RUN_DISK_TESTS=1 <venv>/python -B -m unittest discover -s tests -v (clean git archive export of 63f4221), plus reversed order and the 11 store-read tests one by one` | Ran 70 tests in 40.787s, OK, 0 skipped; reversed 70 OK, 0 skipped; 11/11 isolated OK. Real-store fingerprint 266 entries, 0 differences; ledger SHA-256 6d359b74… unchanged. | Recorded from reviews/corpus-pilot-review-v0.3.md §8 and §7 on the parent's instruction (independent reviewer). Not re-run by the atlas worker; its own run q021-disk-63f4221 gives the same 70 OK. |
| `q023-writer-inmemory-057a0b7` | unit | pass | Q-023 full-import implementation sub-agent (the writer) | no (UNVERIFIED) | 2026-11-05 | `057a0b7` | `<venv>/python -B -m unittest discover -s tests (clean git archive export of 057a0b7)` | Ran 75 tests in 14.5s, OK (skipped=30) | UNVERIFIED: implementer-reported; the independent Q-023 reviewer re-runs it. |
| `q023-writer-disk-057a0b7` | disk | pass | Q-023 full-import implementation sub-agent (the writer) | no (UNVERIFIED) | 2026-11-05 | `057a0b7` | `CUNEIFORM_TEST_MAX_TOTAL_GIB=41 CUNEIFORM_RUN_DISK_TESTS=1 <venv>/python -B -m unittest discover -s tests (clean git archive export of 057a0b7)` | Ran 75 tests in 44.8s, OK, 0 skipped (70 earlier + 5 new in tests/test_full_import.py). Without the explicit budget variable, the 29 disk tests error at admission (root 14.4 GB > default 5 GiB), by design. | UNVERIFIED: implementer-reported; the independent Q-023 reviewer re-runs it. |
| `q023-reviewer-inmemory-057a0b7` | unit | pass | Independent full-corpus reviewer c0273cbf | yes | 2026-11-05 | `057a0b7` | `<venv>/python -B -m unittest discover -s tests (clean git archive export of 057a0b7)` | Ran 75, OK, skipped=30, 14.8 s | Independent run read back from reviews/full-corpus-review-v0.1.md section 9; original writer run retained. |
| `q023-reviewer-disk-057a0b7` | disk | pass | Independent full-corpus reviewer c0273cbf | yes | 2026-11-05 | `057a0b7` | `CUNEIFORM_TEST_MAX_TOTAL_GIB=41 CUNEIFORM_RUN_DISK_TESTS=1 <venv>/python -B -m unittest discover -s tests (clean git archive export of 057a0b7)` | Ran 75, OK, 0 skipped, 42.9 s | Independent run read back from reviews/full-corpus-review-v0.1.md section 9; original writer run retained. |

### Corpus snapshots (evidence eligibility)

Only `accepted` snapshots may be cited as `corpus_evidence`. `--runtime` reads each cited one with the checker's own reader (`corpus-evidence-reader-1`): ledger record, pinned manifest digest, every payload hash, and row counts from the hashed Parquet, then cross-checks the backend read verifier. Incident and pending-review snapshots are listed so that they cannot be cited by mistake.

| Snapshot | Status | Source | Ledger | Writer code | Accepted by | Note |
|---|---|---|---|---|---|---|
| `snapshot:5e51403b0d7dcdb90cb429d444e6a23b` | accepted | oracc-selection | ledgered | 94af111 | reviews/corpus-pilot-review-v0.2.md, reviews/corpus-pilot-review-v0.3.md | ORACC ccpo rebuilt by adapter oracc-cdl-2 (Q-005 F4 fix), ledger format 2 reserve/commit at 10:36:22Z. Q-020 (v0.2 §7) verified its content and all 4,544 IN_SENSE source links against the raw nodes; v0.3 verified it ledgered and bytes-bound at 63f4221 and accepted the publication for the pilot. Its sense provenance supersedes edaab55c. Not yet cited as corpus_evidence (edaab55c counts are equal and remain cited). |
| `snapshot:965aa26214dc0388dd3af1be367d2acc` | accepted | ebl-cohort | ledgered | 5c7a01b | reviews/full-corpus-review-v0.1.md | Q-023 full eligible eBL release: cohort:4e532850... (cohort-2, size=None, rule usable-text-v1), 20,896 of 23,289 parent records, 2,393 excluded with per-record reasons (2,171 / 154 / 66 / 2). Projection preset full (12M positions / 80M rows). Ledger format 2 reserve+commit 2026-11-05T10:19:55Z. Counts (writer-observed): occurrence 4,542,153; edge 12,167,645; ngram 12,292,380; posting 2,883,814; line 629,335; translation_segment 23,984; exclusion 1,051,657; claim 16,735; sign_type 649. Built by the 5c7a01b tree (build code equal to 057a0b7; 057a0b7 changed tests and lookups only). Not cited as corpus_evidence until an independent review reads it. Independently accepted for fixed-release eligible text scope on 2026-11-05; all 4,542,153 offsets and 28 motif counts verified. Strict evidence remains unavailable under conservative-3. |
| `snapshot:c316e7cbbaf8a7fca7705f0efa5c4a07` | accepted | ebl-cohort | legacy-backfilled | d6049e2 | reviews/atlas-recheck-v0.1.md | eBL∩ccpo P-number cohort (51 records). Published once; ledger row backfilled at ~09:59Z. Q-019 recounted every cited count from copies of its rows (0 mismatches). Q-005 accepted the pilot data surfaces. |
| `snapshot:edaab55c1a39cc65ad7c76e6d12547a7` | accepted | oracc-selection | legacy-backfilled | d6049e2 | reviews/atlas-recheck-v0.1.md | ORACC ccpo, adapter oracc-cdl-1, 51 texts. Counts recounted by Q-019 and still valid. Superseded by snapshot:5e51403b for sense provenance: 1,309 Sense rows carry an instance sig (Q-005 F4), which is not the oracc-cdl-2 contract. Kept, never deleted. |
| `snapshot:fc7c350439f9edfee61b5f35bdd4d65a` | accepted | cdli-selection | legacy-backfilled | d6049e2 | reviews/atlas-recheck-v0.1.md | CDLI artifact JSON selection, 51 artifacts, catalog claims only (0 edges). Counts recounted by Q-019. |
| `snapshot:84971360d212834e0b7acbeac1e56abe` | incident | ebl-cohort | legacy-backfilled | d6049e2 | — | Deleted and rebuilt under the same ID at ~09:46Z (UI review F-4). First-version bytes not retained. Never evidence; kept, never deleted. |
| `snapshot:ce127437339109285185a534145edf50` | incident | ebl | legacy-backfilled | d6049e2 | — | Deleted and rebuilt under the same ID at ~09:46Z (UI review F-4). First-version bytes not retained. Never evidence; kept, never deleted. |

### Runtime coverage

`--runtime` builds in-memory inputs for: `cdli`, `ebl`, `ebl-cohort`, `oracc-selection`. These source kinds are not exercised, so no population above `none` can be verified for rows only they produce:

- `cdli-selection`: cdli_api.map_records has no fixture file; tests/test_corpus_pilot.py::test_catalog_only_claims_and_rejection builds inline data.
- `ebl-atf`: No fixture file. The local caller-supplied ATF path is exercised only by unit tests.
- `oracc`: Refused by design: adapters.ingest raises for generic ORACC JSON. ORACC data enters only as oracc-selection.

<a id="domain-provenance"></a>
### Sources, snapshots & provenance

Immutable raw bytes, source records, snapshot bindings, manifests, rights and accounting of rejected/excluded input.

| ID | Kind | Modeled | Implemented | Populated | Verified | Backing | Queue |
|---|---|---|---|---|---|---|---|
| `node:SourceRecord` | node | specified | code | corpus | unit | table `source_record` | Q-011, Q-012, Q-013, Q-005 |
| `table:source_binding` | table | documented | code | corpus | unit | table `source_binding` | — |
| `table:registry` | table | documented | code | corpus | unit | table `registry` | — |
| `table:rejection` | table | specified | code | synthetic | unit | table `rejection` | — |
| `table:exclusion` | table | specified | code | corpus | unit | table `exclusion` | — |
| `artifact:snapshot-manifest` | artifact | specified | code | synthetic | disk | `cuneiform/storage.py::StoreEntry`, `cuneiform/storage.py::import_cohort`, `cuneiform/storage.py::import_source`, `cuneiform/storage.py::materialize`, `cuneiform/storage.py::snapshot_identity`, `cuneiform/storage.py::store_entry`, `cuneiform/storage.py::verified`, `cuneiform/storage.py::verify`, `cuneiform/storage.py::verify_content` | Q-012, Q-001, Q-005 |
| `artifact:publication-ledger` | artifact | documented | code | none | disk | `cuneiform/publication.py::LEDGER`, `cuneiform/publication.py::Ledger`, `cuneiform/publication.py::PublicationError`, `cuneiform/publication.py::adopt`, `cuneiform/publication.py::build_lock`, `cuneiform/publication.py::check_published`, `cuneiform/publication.py::locate_entry`, `cuneiform/publication.py::missing_entry`, `cuneiform/publication.py::publish_dir`, `cuneiform/publication.py::recover`, `cuneiform/storage.py::LEDGER`, `cuneiform/storage.py::StoreEntry`, `cuneiform/storage.py::existing_snapshot`, `cuneiform/storage.py::publish`, `cuneiform/storage.py::resolve_snapshot`, `cuneiform/storage.py::store_entry`, `cuneiform/storage.py::store_path`, `cuneiform/storage.py::verified` | Q-001, Q-005, Q-020, Q-022 |
| `artifact:acquisition-receipt` | artifact | documented | code | none | none | `cuneiform/acquire.py::acquire`, `cuneiform/acquire.py::write_receipt`, `cuneiform/acquire.py::verify_raw` | Q-005, Q-013 |
| `artifact:cohort-manifest` | artifact | documented | code | none | disk | `cuneiform/corpus.py::build_cohort`, `cuneiform/corpus.py::iter_array`, `cuneiform/corpus.py::verify_cohort`, `cuneiform/storage.py::import_cohort`, `cuneiform/corpus.py::accounting` | Q-005, Q-012, Q-020, Q-022, Q-023 |
| `artifact:selection-manifest` | artifact | documented | code | none | none | `cuneiform/oracc.py::import_project`, `cuneiform/cdli_api.py::import_artifacts` | Q-005, Q-011, Q-013 |
| `concept:rights-ledger` | concept | specified | code | none | unit | `cuneiform/adapters.py::RIGHTS`, `cuneiform/cdli_api.py::RIGHTS` | Q-011, Q-012, Q-013, Q-005 |
| `value:SourceLocator` | value | documented | code | none | unit | `cuneiform/model.py::SourceLocator`, `cuneiform/query.py::trace_rows` | — |
| `edge:ATTRIBUTED_TO` | edge | documented | code | sample | unit | portable_edge | Q-009 |

#### `node:SourceRecord` — SourceRecord

One parsed input record (eBL JSON object, local ATF file, or CDLI logical CSV row) with its complete raw JSON retained.

- **Identity:** identity('source', namespace, snapshot_id, source_key, locator). Snapshot-scoped: the same upstream record in another snapshot is a different SourceRecord.
- **Scope:** One namespace + snapshot. source_key is the eBL _id / museum number, an explicit --record-id for ATF, or a normalized CDLI P-number.
- **Versioning:** New bytes, schema, parser or projection config create a new snapshot and therefore new SourceRecord IDs. No in-place migration.
- **Provenance:** Self: raw_json is the complete source object; locator is a JSON pointer or logical CSV row. Raw file hash in source_binding.
- **Uncertainty:** None asserted. Unknown/unmapped fields stay inside raw_json.
- **Coverage:** Pilot snapshots: eBL cohorts (ebl-cohort), ORACC ccpo selection (oracc-selection, oracc-cdl-1) and CDLI cdli.earth catalog JSON (cdli-selection); retained samples and synthetic fixtures in memory. Generic ORACC JSON import stays refused.
- **Files:** `cuneiform/schema.sql`, `cuneiform/adapters.py`
- **Evidence:** `tests/test_foundation.py::test_deterministic_ids_and_empty_unavailable_layers`, `tests/test_foundation.py::test_source_utf8_roundtrip_all_positions`, `tests/test_projections.py::test_real_retained_samples`
- **Corpus evidence:** `snapshot:c316e7cbbaf8a7fca7705f0efa5c4a07` source_record=51; `snapshot:edaab55c1a39cc65ad7c76e6d12547a7` source_record=51; `snapshot:fc7c350439f9edfee61b5f35bdd4d65a` source_record=51 (read by Q-007/Q-018 atlas worker (read-only storage.verify + manifest counts / exported edge Parquet), 2026-11-03)
- **Sources:** SPEC-v0.2.md §4, docs/INGESTION-DESIGN.md

| Field | Type | Nullable | Key | Note |
|---|---|---|---|---|
| `id` | VARCHAR | False | PK | source:<32 hex> |
| `namespace` | VARCHAR | False | — | Adapter namespace, e.g. ebl, ebl-atf, cdli, or caller --namespace. |
| `source_key` | VARCHAR | False | — | Upstream record identity as normalized by the adapter. |
| `locator` | VARCHAR | False | — | JSON pointer (/fragments/0) or csv:row:N; empty string for single-object input. |
| `raw_json` | JSON | False | — | Canonical JSON of the full source object, including unmapped fields. |

#### `table:source_binding` — source_binding

Binds each SourceRecord to its snapshot ID and the SHA-256 of the raw input bytes.

- **Identity:** Keyed by source_record_id (1:1).
- **Scope:** Snapshot.
- **Provenance:** raw_sha256 is computed over the whole input file before parsing.
- **Files:** `cuneiform/schema.sql`, `cuneiform/adapters.py`
- **Evidence:** `tests/test_linked_review.py::test_wrong_source_and_manifest_rejected`, `tests/test_projections.py::test_trace_and_reverse_navigation`
- **Corpus evidence:** `snapshot:c316e7cbbaf8a7fca7705f0efa5c4a07` source_binding=51; `snapshot:edaab55c1a39cc65ad7c76e6d12547a7` source_binding=51; `snapshot:fc7c350439f9edfee61b5f35bdd4d65a` source_binding=51 (read by Q-007/Q-018 atlas worker (read-only storage.verify + manifest counts / exported edge Parquet), 2026-11-03)
- **Sources:** docs/REPRESENTATION-MAP.md

| Field | Type | Nullable | Key | Note |
|---|---|---|---|---|
| `source_record_id` | VARCHAR | False | PK | FK source_record.id |
| `snapshot_id` | VARCHAR | False | — | snapshot:<hex> for persistent imports; demo:<hex> for in-memory runs. |
| `raw_sha256` | VARCHAR | False | — | SHA-256 of the raw input bytes. |

#### `table:registry` — registry (schema/parser version)

Single row recording schema version and parser version of the database.

- **Identity:** version (PK).
- **Versioning:** Must equal model.SCHEMA_VERSION / PARSER_VERSION; checked by scripts/check_model_atlas.py.
- **Files:** `cuneiform/schema.sql`
- **Evidence:** `tests/test_projections.py::test_variable_manifest_inventory_without_disk`
- **Corpus evidence:** `snapshot:c316e7cbbaf8a7fca7705f0efa5c4a07` registry=1; `snapshot:edaab55c1a39cc65ad7c76e6d12547a7` registry=1; `snapshot:fc7c350439f9edfee61b5f35bdd4d65a` registry=1 (read by Q-007/Q-018 atlas worker (read-only storage.verify + manifest counts / exported edge Parquet), 2026-11-03)
- **Sources:** cuneiform/model.py

| Field | Type | Nullable | Key | Note |
|---|---|---|---|---|
| `version` | VARCHAR | False | PK | Schema version ('2'). |
| `parser_version` | VARCHAR | False | — | Parser version ('conservative-3'). |

#### `table:rejection` — rejection

Per-record mapping failures, retained with raw values and reason; nothing is silently dropped.

- **Identity:** identity('reject', snapshot_id, locator).
- **Scope:** Snapshot. Whole-file malformed JSON/CSV aborts before a snapshot instead.
- **Files:** `cuneiform/schema.sql`, `cuneiform/adapters.py`
- **Evidence:** `tests/test_foundation.py::test_rejections_and_no_alias_merge`
- **Sources:** SPEC-v0.2.md §3

| Field | Type | Nullable | Key | Note |
|---|---|---|---|---|
| `id` | VARCHAR | False | PK | — |
| `locator` | VARCHAR | False | — | — |
| `reason` | VARCHAR | False | — | — |
| `raw_json` | JSON | False | — | — |

#### `table:exclusion` — exclusion

Accounted exclusions inside accepted records: non-token ATF lines, unsupported compounds/segmentation, missing ATF, unsupported translation syntax.

- **Identity:** identity('exclusion', source_record_id, locator, reason).
- **Files:** `cuneiform/schema.sql`, `cuneiform/adapters.py`
- **Evidence:** `tests/test_review_regressions.py::test_translation_extent_and_unrecognized_accounting`, `tests/test_review_regressions.py::test_unsupported_spans_block_interior`
- **Corpus evidence:** `snapshot:c316e7cbbaf8a7fca7705f0efa5c4a07` exclusion=5223; `snapshot:edaab55c1a39cc65ad7c76e6d12547a7` exclusion=2395; `snapshot:fc7c350439f9edfee61b5f35bdd4d65a` exclusion=51 (read by Q-007/Q-018 atlas worker (read-only storage.verify + manifest counts / exported edge Parquet), 2026-11-03)
- **Sources:** SPEC-v0.2.md §10

| Field | Type | Nullable | Key | Note |
|---|---|---|---|---|
| `id` | VARCHAR | False | PK | — |
| `source_record_id` | VARCHAR | False | — | FK source_record.id |
| `locator` | VARCHAR | False | — | field:line:N or field:utf8:start:end |
| `reason` | VARCHAR | False | — | — |

#### `artifact:snapshot-manifest` — Snapshot manifest (manifest.json)

Per-snapshot manifest: identity inputs, contract, versions, rights, payload hashes, counts and build measurements. Built by storage.materialize for every source kind; layout raw / manifest.json / graph.duckdb / parquet/<table>.parquet plus cohort.json or selection.json when bound.

- **Identity:** New snapshots: snapshot_identity(namespace, source, raw_sha256, schema, parser, record_id, source_url, projection_spec) with contract 'manifest-3' included. The five pilot snapshots predate manifest-3 and keep the legacy formula (their ledger rows record snapshot_contract null). Paths and timestamps are excluded.
- **Versioning:** Immutable. Published once through the publication ledger (artifact:publication-ledger); a revision gets a new ID. Schema-1 manifests verify under their original inventory contract. At 63f4221 store membership is decided from the lexical and the resolved parent: a directory in or resolving into a store is ledger-checked, a symlinked or misplaced store entry is refused, and store_path/resolve_snapshot return a StoreEntry read with ledger='require' and its own ID. Copies outside every store stay content-only and labelled standalone-not-ledger-checked. The read contract changed; the manifest keys did not. Accepted at 63f4221 for the authorized local cooperating-writer pilot by the independent final review (reviews/corpus-pilot-review-v0.3.md, review c5df3251): R1-R5 closed. Not proven beyond that scope.
- **Provenance:** manifest_sha256 detects inconsistent edits; it is not authentication against coordinated rewrites.
- **Temporal:** retrieved_or_imported_at is system (ingestion) time in UTC. It is excluded from identity. See temporal:system-time.
- **Coverage:** Six real snapshots in the store: four accepted as evidence (eBL∩ccpo cohort c316e7cb, ORACC ccpo edaab55c, CDLI fc7c3504, and the oracc-cdl-2 rebuild 5e51403b, accepted by v0.3), two rebuilt under the same ID during the incident (ce127437, 84971360). See corpus_snapshots. Counts are evidence of rows; publication integrity is the ledger's pilot-scope guarantee.
- **Evidence notes:** Disk level rests on the corpus worker's own run at d6049e2 (UNVERIFIED, not read back) and, historically, on the parent's 2ab620b run. The atlas worker observed only the in-memory suite at d6049e2. The manifest is not rows, so its populated level is not raised to corpus; the five verified real manifests are listed under coverage.
- **Files:** `cuneiform/storage.py`, `cuneiform/oracc.py`, `cuneiform/cdli_api.py`
- **Evidence:** `tests/test_disk_delivery.py::test_snapshot_idempotence_relocation_parquet_and_tamper`, `tests/test_review_regressions.py::test_incomplete_manifest_rejected`, `tests/test_projections.py::test_variable_manifest_inventory_without_disk`, `tests/test_corpus_pilot.py::test_ledger_read_only_and_contract_identity`, `tests/test_corpus_pilot.py::test_snapshots_verify_parity_and_traces`
- **Verified by:** `q023-reviewer-disk-057a0b7` (Independent full-corpus reviewer c0273cbf, 2026-11-05, code `057a0b7`); `q023-reviewer-inmemory-057a0b7` (Independent full-corpus reviewer c0273cbf, 2026-11-05, code `057a0b7`); `review-v03-disk-63f4221` (Final publication review c5df3251 (independent of the Q-022 fix worker), 2026-11-03, code `63f4221`); `q021-disk-63f4221` (Atlas repair worker (Q-021), 2026-11-03, code `63f4221`); `backend-q022-disk-63f4221` (Q-022 backend fix worker (Q-020 R1-R5 round), 2026-11-03, code `63f4221`); `q020-disk-94af111` (Q-020 review sub-agent (independent of fix task 44ddaeb1), 2026-11-03, code `94af111`); `backend-fix-disk-94af111` (Backend fix worker, task 44ddaeb1 (Q-001 fix round), 2026-11-03, code `94af111`); `corpus-worker-disk-d6049e2` (Corpus worker, task 64821742 (Q-001), 2026-11-03, code `d6049e2`); `parent-full-disk-2ab620b` (Parent orchestrator, 2026-11-03, code `2ab620b`)
- **Sources:** docs/INGESTION-DESIGN.md, CHECKPOINT.md

| Field | Type | Nullable | Key | Note |
|---|---|---|---|---|
| `snapshot_contract` | string | — | — | 'manifest-3'; part of new snapshot IDs. Absent from the five pilot manifests (legacy identity); legacy_absent lets the runtime check accept that. |
| `projection_spec` | object | — | — | {revision, config} bound into snapshot identity. |
| `snapshot_id` | string | — | — | — |
| `schema_version` | string | — | — | — |
| `parser_version` | string | — | — | — |
| `namespace` | string | — | — | — |
| `source` | string | — | — | Source kind: ebl, ebl-atf, cdli, ebl-cohort, oracc-selection or cdli-selection. |
| `source_url` | string\|null | — | — | Caller-supplied citation; not verified. |
| `record_id` | string\|null | — | — | — |
| `rights` | object | — | — | adapters.RIGHTS[source] for import_source; per-snapshot statement for selections and cohorts (see concept:rights-ledger). Not a legal grant. |
| `adapter` | string | — | — | optional, only for cdli-selection, oracc-selection; Adapter contract, e.g. oracc-cdl-1 (edaab55c), oracc-cdl-2 (94af111 and later: sense-key locators, per-occurrence sig on IN_SENSE), cdli-artifact-json-1. |
| `cohort` | object | — | — | optional, only for ebl-cohort; cohort_id, manifest_sha256, size, rule, parent; bound to cohort.json by hash. |
| `selection` | object | — | — | optional, only for cdli-selection, oracc-selection; selection_id, manifest_sha256, size, parent; bound to selection.json by hash. |
| `ingestion` | object | — | — | optional, only for cdli-selection, ebl-cohort, oracc-selection; Record/rejection/batch statistics of the import. |
| `projection_registry` | object | — | — | id, canonical_hash, source_hash frozen at build time. |
| `retrieved_or_imported_at` | string (ISO 8601 UTC) | — | — | System time; never in IDs. |
| `raw_sha256` | string | — | — | — |
| `source_bytes` | integer | — | — | — |
| `files` | object | — | — | Relative path -> SHA-256 for every payload. |
| `counts` | object | — | — | Row count per materialized table. |
| `source_locator_contract` | string | — | — | — |
| `coverage` | string | — | — | — |
| `storage_paths` | string | — | — | — |
| `build_timings` | object | — | — | Seconds per stage (ingest, validate, projections, parquet). System measurement; never in IDs. |
| `snapshot_payload_bytes` | integer | — | — | Sum of payload file sizes. |
| `manifest_sha256` | string | — | — | — |

#### `artifact:publication-ledger` — Snapshot publication ledger (.publication-ledger.jsonl)

Append-only publication ledger under an exclusive lock (cuneiform/publication.py, format 2). Writers fsync a `reserve` (binding manifest_sha256 and the manifest.json bytes) before the rename, then a `commit`; interrupted publications fail closed until an explicit publication-recover. Guarantee: an ID that was ever published is never served or published with other bytes, for cooperating writers on one host. Accepted at 63f4221 for the authorized local cooperating-writer pilot by the independent final review (reviews/corpus-pilot-review-v0.3.md, review c5df3251): R1-R5 closed. Not proven beyond that scope.

- **Versioning:** Format 1: legacy rows with no event key (the d6049e2 publisher and the 2026-11-03 backfill of the five pilot snapshots), read as published. Format 2 (94af111): reserve, commit, abort, abandon, adopt and torn-tail-acknowledged events; 63f4221 adds no event kind. The cohort ledger under derived/cohorts uses the same format, reached through publication-* --store cohorts. Historical rows are never rewritten. The checker reads both formats itself (corpus-evidence-reader-1).
- **Provenance:** Added after the same-ID rebuild incident (UI review F-4): at ~09:44Z on 2026-11-03 snapshots ce127437 and 84971360 were published, deleted at ~09:46Z and rebuilt under the same IDs. First-version bytes were not retained, and no copy of them is known. Incident record: ~/.local/share/cuneiform-research/evidence/incident-2026-11-03-same-id-rebuild.json. Both IDs are kept and listed as incident in corpus_snapshots; they are never evidence.
- **Uncertainty:** Q-005 blockers at d6049e2: B1 crash window after the rename allowed a same-ID republish; B2 reads never consulted the ledger; B3 failed-publish cleanup masked the error. Q-020 (reviews/corpus-pilot-review-v0.2.md) closed B1 and B3 at 94af111 and kept B2 open on its R1 (a symlinked store entry served as standalone-not-ledger-checked), with R2 (cohort reads), R3 (reserve->commit window), R4 (untyped absent entries) and R5 (seal fsync order). Accepted at 63f4221 for the authorized local cooperating-writer pilot by the independent final review (reviews/corpus-pilot-review-v0.3.md, review c5df3251): R1-R5 closed. Not proven beyond that scope. Writer changes: store membership from the lexical and resolved parent; symlinked or escaping entries, payload symlinks and misplaced IDs refused with symlinked-entry or misplaced before hashing; StoreEntry reads always ledger=require with expected_sid; a writer that finds reserved waits on the per-ID build lock; typed refusals for absent entries; seal fsyncs after the final modes. fsync_dir still ignores OSError. Limits stated by the protocol: cooperating writers on one host; same-owner edits, ledger deletion and root are not prevented; symlink checks are time-of-read; the ledger is not a signature. Open, non-blocking (v0.3 §9): N1 a reader refusal inside a live reserve window says the writer is gone (wording; the read still fails closed); N2 API cohort reads default to auto and label pre-ledger cohorts standalone (wording); N3 publication-clean-stage is guarded by age only. Not tested: same-owner tampering, root, multi-host, real power loss (crashes are process kills).
- **Coverage:** Seven rows at 63f4221 (read by the atlas worker; ledger SHA-256 6d359b74… is unchanged since 94af111): five legacy rows backfilled at ~09:59Z (two carry the incident note) and one reserve plus one commit for snapshot:5e51403b at 10:36:22Z. Readers label the five ledgered-legacy-backfilled; their published_at is the manifest build time copied by the backfill, and their manifest.json file bytes are not bound (canonical digest only). derived/cohorts has no ledger or lock yet: its three cohorts read as unledgered-pre-ledger-cohort-store. Building any new cohort there creates the cohort ledger, after which those three are refused until the owner adopts them (writer statement, not done). Rows are file entries, not table rows, so populated stays none.
- **Files:** `cuneiform/publication.py`, `cuneiform/storage.py`, `cuneiform/corpus.py`, `docs/PUBLICATION-PROTOCOL.md`
- **Evidence:** `tests/test_publication.py::test_kill_after_rename_fails_closed_then_delete_cannot_republish`, `tests/test_publication.py::test_replaced_build_refused_restoration_bound_standalone_labelled`, `tests/test_publication.py::test_rename_failure_raises_original_error_and_leaves_no_stage`, `tests/test_publication.py::test_states_and_conflicts`, `tests/test_corpus_pilot.py::test_ledger_read_only_and_contract_identity`, `tests/test_store_reads.py::test_symlinked_entry_same_id_different_bytes_refused_everywhere`, `tests/test_store_reads.py::test_id_x_never_resolves_to_snapshot_y`, `tests/test_store_reads.py::test_nested_path_forms`, `tests/test_store_reads.py::test_dangling_symlink_and_symlinked_dest_on_writer_and_recovery_side`, `tests/test_store_reads.py::test_absent_entry_refusals_are_typed`, `tests/test_store_reads.py::test_writer_and_recovery_inside_live_reserve_commit_window`, `tests/test_store_reads.py::test_seal_fsyncs_after_final_modes`
- **Verified by:** `q023-reviewer-disk-057a0b7` (Independent full-corpus reviewer c0273cbf, 2026-11-05, code `057a0b7`); `q023-reviewer-inmemory-057a0b7` (Independent full-corpus reviewer c0273cbf, 2026-11-05, code `057a0b7`); `review-v03-disk-63f4221` (Final publication review c5df3251 (independent of the Q-022 fix worker), 2026-11-03, code `63f4221`); `q021-disk-63f4221` (Atlas repair worker (Q-021), 2026-11-03, code `63f4221`); `backend-q022-disk-63f4221` (Q-022 backend fix worker (Q-020 R1-R5 round), 2026-11-03, code `63f4221`); `q020-disk-94af111` (Q-020 review sub-agent (independent of fix task 44ddaeb1), 2026-11-03, code `94af111`); `backend-fix-disk-94af111` (Backend fix worker, task 44ddaeb1 (Q-001 fix round), 2026-11-03, code `94af111`); `corpus-worker-disk-d6049e2` (Corpus worker, task 64821742 (Q-001), 2026-11-03, code `d6049e2`)
- **Sources:** CHECKPOINT.md, docs/PUBLICATION-PROTOCOL.md, docs/CORPUS-REVIEW-v0.1-DISPOSITION.md, docs/CORPUS-REVIEW-v0.2-DISPOSITION.md, reviews/corpus-pilot-review-v0.3.md

#### `artifact:acquisition-receipt` — Acquisition receipt and content-addressed raw store

Allowlisted, checksum-verified download into a read-only raw/sha256 store with an immutable receipt (URL, bytes, hashes, kept response headers, timings, rights statement).

- **Temporal:** Receipt timestamps are processing time; they never enter IDs.
- **Coverage:** Receipts for the eBL fragments.json parent (receipt:66b5c944…), ORACC ccpo.zip (receipt:0ca4ede9…) and 51 CDLI artifact records, per SOURCE-AUDIT. Not re-read by the atlas worker.
- **Notes:** No unit test names acquire(); network paths are exercised only by the real acquisitions.
- **Files:** `cuneiform/acquire.py`, `sources/allowlist.json`
- **Sources:** docs/SOURCE-AUDIT.md, CHECKPOINT.md

#### `artifact:cohort-manifest` — eBL cohort manifest (cohort.json)

Deterministic rule-selected cohort (usable-text-v1, order sha256(parent_sha256 + ':' + _id)) with byte-identical parent slices, exclusion accounting and a self-hash. Format cohort-2 (Q-023) also lists every excluded parent record (index, pointer, byte range, record sha256, key, reason); corpus.accounting() proves members + exclusions partition the parent (all-eligible cohorts: exactly the eligible records). cohort-1 manifests still verify (identity uses the manifest's own format). Bound into ebl-cohort snapshots by hash.

- **Scope:** A cohort is a filtered, hash-ordered sample (20,896 of 23,289 records eligible), not representative corpus statistics.
- **Uncertainty:** Q-020 R2 (cohort reads not ledger-bound, no cohort recovery path). At 63f4221 the writer made verify_cohort(dir, parent, ledger=auto|store|require|skip) ledger-checked; corpus-audit and corpus-import read with ledger='store', import_cohort checks before building, build_cohort holds a per-ID build lock, and publication-* --store cohorts is the explicit recovery and adoption path. Accepted at 63f4221 for the authorized local cooperating-writer pilot by the independent final review (reviews/corpus-pilot-review-v0.3.md, review c5df3251): R1-R5 closed. Not proven beyond that scope. Each snapshot binds its own cohort.json by hash, which remains the authoritative copy. Prerequisite before any future cohort build in the real store: the owner must explicitly adopt cohort-4e86952e…, cohort-9abad6ce… and cohort-ea91baae… (publication-adopt --store cohorts). A build creates the cohort ledger, after which unadopted cohorts are refused. Not done; no cohort was built (v0.3 §7, §11; parent). Q-023 (writer, UNVERIFIED): the three pre-ledger cohorts were adopted with publication-adopt --store cohorts after each manifest digest, identity, payload hash, every member slice against the parent and the bound snapshot cohort.json were re-checked; cohort-2 and accounting() await the independent Q-023 review.
- **Coverage:** Four cohorts in the real store: 30, 300 and the 51-record eBL∩ccpo cohort (cohort-1, adopted into the new cohort ledger on 2026-11-05 after an independent byte check, scratch/q023-full-import/evidence/adopt-before.json; payload bytes unchanged) and the all-eligible cohort:4e532850... (cohort-2, 20,896 members + 2,393 excluded = 23,289). Scratch-only stage cohorts (1,000, 1,500, 5,000) live in scratch/q023-full-import/stage-root.
- **Files:** `cuneiform/corpus.py`, `cuneiform/publication.py`
- **Evidence:** `tests/test_corpus_pilot.py::test_cohort_determinism_prefix_trace_tamper_and_chunked_parity`, `tests/test_corpus_pilot.py::test_exact_byte_ranges_across_tiny_chunks_and_envelopes`, `tests/test_store_reads.py::test_kill_after_rename_cohort_refused_then_recovered_with_byte_binding`, `tests/test_store_reads.py::test_kill_after_reserve_cohort_complete_and_discard`, `tests/test_store_reads.py::test_unrecorded_symlinked_misplaced_and_pre_ledger_cohorts`, `tests/test_store_reads.py::test_concurrent_cohort_builders_build_once`, `tests/test_full_import.py::test_complete_partition_and_every_defect`, `tests/test_full_import.py::test_all_eligible_cohort_accounts_for_every_parent_record_and_labels_scope`
- **Verified by:** `q023-reviewer-disk-057a0b7` (Independent full-corpus reviewer c0273cbf, 2026-11-05, code `057a0b7`); `q023-reviewer-inmemory-057a0b7` (Independent full-corpus reviewer c0273cbf, 2026-11-05, code `057a0b7`); `review-v03-disk-63f4221` (Final publication review c5df3251 (independent of the Q-022 fix worker), 2026-11-03, code `63f4221`); `q021-disk-63f4221` (Atlas repair worker (Q-021), 2026-11-03, code `63f4221`); `backend-q022-disk-63f4221` (Q-022 backend fix worker (Q-020 R1-R5 round), 2026-11-03, code `63f4221`); `q020-disk-94af111` (Q-020 review sub-agent (independent of fix task 44ddaeb1), 2026-11-03, code `94af111`); `backend-fix-disk-94af111` (Backend fix worker, task 44ddaeb1 (Q-001 fix round), 2026-11-03, code `94af111`); `corpus-worker-disk-d6049e2` (Corpus worker, task 64821742 (Q-001), 2026-11-03, code `d6049e2`)
- **Sources:** docs/SOURCE-AUDIT.md, docs/CORPUS-REVIEW-v0.2-DISPOSITION.md

#### `artifact:selection-manifest` — ORACC / CDLI selection manifest (selection.json)

Explicit selection of export members (ORACC) or acquired records (CDLI) with payload byte offsets, member hashes, parent receipt and a self-hash. Bound into oracc-selection and cdli-selection snapshots by hash.

- **Coverage:** ORACC ccpo: 51 texts selected by exact P-number overlap with the eBL cohort. CDLI: the same 51 P-numbers.
- **Notes:** The import functions have no unit test; the mapping functions do (see node:WordToken, node:Claim).
- **Files:** `cuneiform/oracc.py`, `cuneiform/cdli_api.py`, `cuneiform/storage.py`
- **Sources:** docs/SOURCE-AUDIT.md

#### `concept:rights-ledger` — Rights ledger

Rights status copied into every manifest: a per-namespace registry (adapters.RIGHTS) plus per-snapshot statements for selection sources. Public access is not a reuse grant; a source statement is not a legal review.

- **Uncertainty:** No status is resolved. Text, annotations, translations, images and code carry separate terms.
- **Notes:** Not a table: populated stays none because the registry is a code constant. The five pilot manifests carry unresolved-conflict (eBL), source-stated (ORACC) and source-stated-terms (CDLI), read back by the atlas worker.
- **Values:** ebl: unresolved-conflict (Zenodo CC BY 4.0 vs data paper CC BY-NC-SA 4.0); ebl-atf: unknown; cdli: unknown; oracc: unverified-project; ebl-cohort: Alias of ebl (RIGHTS['ebl-cohort'] = RIGHTS['ebl']): unresolved-conflict. import_cohort prefers the cohort manifest's rights, which copy the parent receipt.
- **Per-snapshot rights sources:** `cdli-selection`: Per-snapshot statement cdli_api.RIGHTS: cdli.earth Terms of Use (academic reuse of transliterations and translations with attribution; images non-commercial). Catalog metadata not separately licensed. Not legally reviewed.; `ebl-cohort`: Per-snapshot statement written by storage.import_cohort: the cohort manifest's rights (copied from the parent receipt) or, if absent, RIGHTS['ebl']. The five pilot cohort manifests carry unresolved-conflict. Recorded, not legally reviewed. Hash moved at 63f4221 (was 84c9938a…) only because the fingerprinted binding of cohort became verify_cohort(cohort_dir, parent_path, ledger=cohort_ledger); the rights expression and every literal it reads are unchanged (AST text compared at 94af111 and 63f4221 by the atlas worker). No grant widened.; `oracc-selection`: Per-snapshot statement written by oracc.import_project: each ccpo file states 'released under the CC0 license'; the documentation footer says CC BY-SA 3.0. Recorded, not legally reviewed.
- **Expected rights status by source kind:** `cdli`: unknown; `cdli-selection`: source-stated-terms; `ebl`: unresolved-conflict; `ebl-atf`: unknown; `ebl-cohort`: unresolved-conflict; `oracc`: unverified-project; `oracc-selection`: source-stated
- **Files:** `cuneiform/adapters.py`, `cuneiform/oracc.py`, `cuneiform/cdli_api.py`, `sources/rights/ebl-zenodo-10018951.json`
- **Evidence:** `tests/test_trace_and_admission.py::test_trace_resolves_source_and_unknowns`
- **Sources:** SPEC-v0.2.md §3, docs/INGESTION-DESIGN.md

#### `value:SourceLocator` — Source locator contract

JSON pointer (or logical CSV row) plus UTF-8 byte offsets inside the decoded source string field, not offsets in escaped JSON bytes.

- **Notes:** The SourceLocator dataclass is declared but not used; the contract is carried by line/occurrence start_byte/end_byte, translation_segment.locator ('field:utf8:start:end') and exclusion.locator strings. trace_rows re-parses raw bytes and verifies the slice.
- **Files:** `cuneiform/model.py`, `cuneiform/query.py`
- **Evidence:** `tests/test_foundation.py::test_source_utf8_roundtrip_all_positions`, `tests/test_trace_and_admission.py::test_trace_resolves_source_and_unknowns`
- **Sources:** docs/INGESTION-DESIGN.md

#### `edge:ATTRIBUTED_TO` — ATTRIBUTED_TO

Provenance edge from an attributed object to its SourceRecord. Derived in the portable_edge view, not stored in edge.

- **Edge:** node:Artifact, node:SequenceVersion, node:Claim, node:TranslationSegment → node:SourceRecord · cardinality N:1 (each source object has exactly one) · qualification — · ID `'source-edge:' || <source object id>`
- **Files:** `cuneiform/schema.sql`
- **Evidence:** `tests/test_projections.py::test_trace_and_reverse_navigation`
- **Sources:** docs/REPRESENTATION-MAP.md

<a id="domain-documents"></a>
### Artifacts, witnesses & compositions

Physical tablets/fragments, manuscript contributions, abstract works/passages, metadata facets and custody/place relations.

| ID | Kind | Modeled | Implemented | Populated | Verified | Backing | Queue |
|---|---|---|---|---|---|---|---|
| `node:Artifact` | node | specified | code | corpus | unit | table `artifact` | Q-013, Q-015 |
| `node:Witness` | node | specified | code | corpus | unit | table `witness` | Q-012 |
| `edge:ON_ARTIFACT` | edge | specified | code | corpus | unit | model.EDGE_TYPES | — |
| `node:Composition` | node | specified | schema | none | unit | table `composition` | Q-012 |
| `node:Passage` | node | specified | schema | none | unit | table `passage` | Q-012 |
| `relation:passage.composition_id` | relation | documented | schema | none | none | table_column `passage.composition_id` | Q-012 |
| `edge:ATTESTS` | edge | specified | none | none | none | — | Q-012 |
| `node:Edition` | node | specified | none | none | none | — | Q-012, Q-014 |
| `edge:HAS_EDITION` | edge | specified | none | none | none | — | Q-012 |
| `edge:HAS_TRANSLATION` | edge | specified | none | none | none | — | Q-012, Q-013 |
| `facet:artifact-metadata` | facet | specified | none | none | none | — | Q-013, Q-015 |
| `node:Place` | node | proposed | none | none | none | — | Q-014, Q-015 |
| `node:Custodian` | node | proposed | none | none | none | — | Q-014, Q-015 |
| `edge:FOUND_AT` | edge | specified | none | none | none | — | Q-014, Q-015 |
| `edge:WRITTEN_AT` | edge | specified | none | none | none | — | Q-014, Q-015 |
| `edge:HELD_BY` | edge | specified | none | none | none | — | Q-014, Q-015 |
| `claim:physical-join` | claim | specified | none | none | none | — | Q-012 |

#### `node:Artifact` — Artifact

Physical tablet or fragment as identified by one source catalog. Source-attributed metadata retained raw.

- **Identity:** identity('artifact', namespace, source_key). Namespace-scoped and NOT snapshot-scoped: the same catalog key in two snapshots yields the same ID; metadata may differ per snapshot.
- **Scope:** One source namespace. Cross-catalog identity is only ever a catalog_alias Claim; no merge by display name or museum label.
- **Provenance:** source_record_id + ATTRIBUTED_TO.
- **Uncertainty:** Joins, duplicates and crosswalk equivalence are not asserted.
- **Coverage:** eBL (synthetic, frozen example, K.1), CDLI (synthetic, three rows).
- **Raw retained in:** artifact.metadata (complete raw record)
- **Files:** `cuneiform/schema.sql`, `cuneiform/adapters.py`
- **Evidence:** `tests/test_foundation.py::test_cdli_duplicate_labels_stay_separate`, `tests/test_projections.py::test_alias_ambiguity_cross_source_and_translations`
- **Corpus evidence:** `snapshot:c316e7cbbaf8a7fca7705f0efa5c4a07` artifact=51; `snapshot:edaab55c1a39cc65ad7c76e6d12547a7` artifact=51; `snapshot:fc7c350439f9edfee61b5f35bdd4d65a` artifact=51 (read by Q-007/Q-018 atlas worker (read-only storage.verify + manifest counts / exported edge Parquet), 2026-11-03)
- **Sources:** SPEC-v0.2.md §4, SPEC-v0.2.md §8

| Field | Type | Nullable | Key | Note |
|---|---|---|---|---|
| `id` | VARCHAR | False | PK | — |
| `source_record_id` | VARCHAR | False | — | FK source_record.id |
| `catalog_key` | VARCHAR | False | — | Source key; namespace:catalog_key is the exact catalog lookup key. |
| `metadata` | JSON | False | — | Raw source object. Temporal/place/custody facets are NOT typed yet (see facet:artifact-metadata). |

#### `node:Witness` — Witness

A manuscript contribution. Currently one per source record that supplies text: 'source fragment contribution; composition unknown'.

- **Identity:** identity('witness', source_record_id). Snapshot-scoped through the record.
- **Scope:** Created only when atf or signs text exists; catalog-only records get no witness.
- **Uncertainty:** Composition membership is unknown and never inferred from descriptions. Witnesses spanning joined artifacts are not modeled yet.
- **Files:** `cuneiform/schema.sql`, `cuneiform/adapters.py`
- **Evidence:** `tests/test_foundation.py::test_deterministic_ids_and_empty_unavailable_layers`
- **Corpus evidence:** `snapshot:c316e7cbbaf8a7fca7705f0efa5c4a07` witness=51; `snapshot:edaab55c1a39cc65ad7c76e6d12547a7` witness=51 (read by Q-007/Q-018 atlas worker (read-only storage.verify + manifest counts / exported edge Parquet), 2026-11-03)
- **Sources:** SPEC-v0.2.md §4

| Field | Type | Nullable | Key | Note |
|---|---|---|---|---|
| `id` | VARCHAR | False | PK | — |
| `source_record_id` | VARCHAR | False | — | — |
| `artifact_id` | VARCHAR | False | — | Exactly one artifact today (also ON_ARTIFACT edge). |
| `scope` | VARCHAR | False | — | Free-text scope statement. |

#### `edge:ON_ARTIFACT` — ON_ARTIFACT

Witness is written on an Artifact.

- **Edge:** node:Witness → node:Artifact · cardinality N:1; exactly one per witness today (spec allows joined artifacts later) · qualification — · ID `identity('edge', kind, source_id, target_id)`
- **Files:** `cuneiform/model.py`, `cuneiform/adapters.py`
- **Evidence:** `tests/test_foundation.py::test_deterministic_ids_and_empty_unavailable_layers`
- **Corpus evidence:** `snapshot:c316e7cbbaf8a7fca7705f0efa5c4a07` ON_ARTIFACT=51; `snapshot:edaab55c1a39cc65ad7c76e6d12547a7` ON_ARTIFACT=51 (read by Q-007/Q-018 atlas worker (read-only storage.verify + manifest counts / exported edge Parquet), 2026-11-03)
- **Sources:** SPEC-v0.2.md §5

#### `node:Composition` — Composition

Abstract work. Table exists; no adapter writes it.

- **Identity:** Not yet defined by code; must include namespace + source key + revision.
- **Notes:** Empty means unavailable. Motif results report compositions = null.
- **Files:** `cuneiform/schema.sql`
- **Evidence:** `tests/test_foundation.py::test_deterministic_ids_and_empty_unavailable_layers`
- **Sources:** SPEC-v0.2.md §4

| Field | Type | Nullable | Key | Note |
|---|---|---|---|---|
| `id` | VARCHAR | False | PK | — |
| `source_record_id` | VARCHAR | False | — | — |
| `source_key` | VARCHAR | False | — | — |

#### `node:Passage` — Passage

Edition-specific passage identity. Table exists; no adapter writes it.

- **Files:** `cuneiform/schema.sql`
- **Evidence:** `tests/test_foundation.py::test_deterministic_ids_and_empty_unavailable_layers`
- **Sources:** SPEC-v0.2.md §4

| Field | Type | Nullable | Key | Note |
|---|---|---|---|---|
| `id` | VARCHAR | False | PK | — |
| `source_record_id` | VARCHAR | False | — | — |
| `composition_id` | VARCHAR | True | — | FK composition.id; see relation:passage.composition_id |
| `source_key` | VARCHAR | False | — | — |

#### `relation:passage.composition_id` — Passage → Composition (FK only)

Foreign-key containment with no registered edge type, so it is invisible to portable_edge traversal.

- **Notes:** Decide whether to register a PART_OF edge when passages are populated.
- **Edge:** node:Passage → node:Composition · cardinality N:0..1 · qualification —
- **Files:** `cuneiform/schema.sql`
- **Sources:** cuneiform/schema.sql

#### `edge:ATTESTS` — ATTESTS

Witness span attests a Passage, with attribution.

- **Edge:** node:Witness → node:Passage · cardinality N:M, span-qualified · qualification span, attribution
- **Sources:** SPEC-v0.2.md §5

#### `node:Edition` — Edition

Scholarly edition/source with coverage and attribution (SPEC 'SourceRecord / Edition').

- **Temporal:** Publication and revision dates are source-attributed temporal claims (temporal role publication/revision).
- **Sources:** SPEC-v0.2.md §4

#### `edge:HAS_EDITION` — HAS_EDITION

Artifact/witness/passage → scholarly edition, with coverage and attribution.

- **Edge:** node:Artifact, node:Witness, node:Passage → node:Edition · cardinality N:M · qualification coverage, attribution
- **Sources:** SPEC-v0.2.md §5

#### `edge:HAS_TRANSLATION` — HAS_TRANSLATION

Artifact/witness/passage → published translation source, with coverage, target language and search scope.

- **Notes:** Never derive 'never translated' from one database's missing field (CDLI translation_source is a raw catalog assertion).
- **Edge:** node:Artifact, node:Witness, node:Passage → node:Edition · cardinality N:M · qualification coverage, language, search_scope
- **Sources:** SPEC-v0.2.md §5, SPEC-v0.2.md §8

#### `facet:artifact-metadata` — Typed artifact metadata facets

Catalog IDs, custody, attributed period/language/genre, findspot, proposed origin, dimensions, image availability, translation coverage. Retained raw only; no typed extraction.

- **Uncertainty:** Unknown stays explicit. No geography or period inferred from collection/accession prefixes.
- **Raw retained in:** artifact.metadata / source_record.raw_json
- **Sources:** SPEC-v0.2.md §8

#### `node:Place` — Place (proposed)

Namespaced place/findspot term (site, sector, building, room) as supplied by one source. Endpoint for FOUND_AT / WRITTEN_AT.

- **Identity:** Proposed: identity('place', namespace, source vocabulary key or verbatim label). No cross-source merge by name.
- **Notes:** Raw shapes observed in retained samples: eBL archaeology.findspot {site, sector, building, buildingType, room, levelLayerPhase, date}; CDLI provenience 'Uruk (mod. Warka)'.
- **Sources:** SPEC-v0.2.md §5, SPEC-v0.2.md §8

#### `node:Custodian` — Custodian (proposed)

Holding institution/collection as named by a source. Endpoint for HELD_BY.

- **Sources:** SPEC-v0.2.md §5

#### `edge:FOUND_AT` — FOUND_AT

Artifact found at a place (excavation/find), attributed, optionally with a find-time TemporalExtent.

- **Edge:** node:Artifact → node:Place · cardinality N:M (competing attributions stay separate) · qualification attribution, certainty, temporal_extent (role: excavation)
- **Sources:** SPEC-v0.2.md §5

#### `edge:WRITTEN_AT` — WRITTEN_AT

Proposed place of origin/inscription; distinct from findspot.

- **Edge:** node:Artifact → node:Place · cardinality N:M · qualification attribution, basis, temporal_extent (role: production)
- **Sources:** SPEC-v0.2.md §5

#### `edge:HELD_BY` — HELD_BY

Custody relation with an interval (acquisition to transfer/now), attributed.

- **Edge:** node:Artifact → node:Custodian · cardinality N:M over time · qualification attribution, accession_number, temporal_extent (role: custody)
- **Sources:** SPEC-v0.2.md §5

#### `claim:physical-join` — Physical-join claim

Groups artifacts as physically joined, with provenance. Differs from duplicate-catalog identity, parallel passages and shared formulae.

- **Raw retained in:** eBL joins / CDLI join_information stay raw.
- **Sources:** SPEC-v0.2.md §5

<a id="domain-signs"></a>
### Sequences, lines & sign occurrences

Source-ordered represented positions, readings, source-derived sign identities and uncertainty fields.

| ID | Kind | Modeled | Implemented | Populated | Verified | Backing | Queue |
|---|---|---|---|---|---|---|---|
| `node:SequenceVersion` | node | specified | code | corpus | unit | table `sequence_version` | — |
| `edge:HAS_SEQUENCE` | edge | specified | code | corpus | unit | model.EDGE_TYPES | — |
| `node:Line` | node | specified | code | corpus | unit | table `line` | — |
| `edge:HAS_LINE` | edge | specified | code | corpus | unit | model.EDGE_TYPES | — |
| `edge:NEXT_LINE` | edge | specified | code | corpus | unit | model.EDGE_TYPES | — |
| `node:SignOccurrence` | node | specified | code | corpus | unit | table `occurrence` | Q-012, Q-017 |
| `value:uncertainty-fields` | value | specified | code | sample | unit | table_column `occurrence.preservation` | Q-017 |
| `edge:HAS_OCCURRENCE` | edge | specified | code | corpus | unit | model.EDGE_TYPES | — |
| `edge:NEXT` | edge | specified | code | corpus | unit | model.EDGE_TYPES | — |
| `node:SignType` | node | specified | code | corpus | unit | table `sign_type` | Q-012 |
| `edge:MAPS_TO_SIGN` | edge | specified | code | corpus | unit | model.EDGE_TYPES | Q-012 |

#### `node:SequenceVersion` — SequenceVersion

One source interpretation of a witness segment for one field: 'atf' (editorial transliteration) or 'signs' (source-derived sign list). Never mixed.

- **Identity:** identity('sequence', source_record_id, field, PARSER_VERSION).
- **Versioning:** Parser version is part of identity.
- **Provenance:** source_record_id + ATTRIBUTED_TO.
- **Uncertainty:** ATF and signs positions have no inferred correspondence.
- **Files:** `cuneiform/schema.sql`, `cuneiform/adapters.py`
- **Evidence:** `tests/test_projections.py::test_namespace_field_and_sign_identity_separation`
- **Corpus evidence:** `snapshot:c316e7cbbaf8a7fca7705f0efa5c4a07` sequence_version=102; `snapshot:edaab55c1a39cc65ad7c76e6d12547a7` sequence_version=51 (read by Q-007/Q-018 atlas worker (read-only storage.verify + manifest counts / exported edge Parquet), 2026-11-03)
- **Sources:** SPEC-v0.2.md §4

| Field | Type | Nullable | Key | Note |
|---|---|---|---|---|
| `id` | VARCHAR | False | PK | — |
| `source_record_id` | VARCHAR | False | — | — |
| `witness_id` | VARCHAR | False | — | — |
| `field` | VARCHAR | False | — | 'atf' \| 'signs' |
| `parser_version` | VARCHAR | False | — | — |
| `evidence_kind` | VARCHAR | False | — | 'editorial-transliteration' \| 'source-derived-sign-list' |

#### `edge:HAS_SEQUENCE` — HAS_SEQUENCE

Witness → SequenceVersion.

- **Edge:** node:Witness → node:SequenceVersion · cardinality 1:1..2 today (atf, signs); 1:N in general · qualification — · ID `identity('edge', kind, source_id, target_id)`
- **Files:** `cuneiform/model.py`, `cuneiform/adapters.py`
- **Evidence:** `tests/test_foundation.py::test_deterministic_ids_and_empty_unavailable_layers`
- **Corpus evidence:** `snapshot:c316e7cbbaf8a7fca7705f0efa5c4a07` HAS_SEQUENCE=102; `snapshot:edaab55c1a39cc65ad7c76e6d12547a7` HAS_SEQUENCE=51 (read by Q-007/Q-018 atlas worker (read-only storage.verify + manifest counts / exported edge Parquet), 2026-11-03)
- **Sources:** SPEC-v0.2.md §5

#### `node:Line` — Line

A source line with label, surface/column context and UTF-8 offsets in the decoded field.

- **Identity:** identity('line', sequence_id, source_line_no) where source_line_no counts every physical line of the field (including non-token lines).
- **Files:** `cuneiform/schema.sql`, `cuneiform/adapters.py`
- **Evidence:** `tests/test_foundation.py::test_source_utf8_roundtrip_all_positions`
- **Corpus evidence:** `snapshot:c316e7cbbaf8a7fca7705f0efa5c4a07` line=2015 (read by Q-007/Q-018 atlas worker (read-only storage.verify + manifest counts / exported edge Parquet), 2026-11-03)
- **Sources:** SPEC-v0.2.md §4

| Field | Type | Nullable | Key | Note |
|---|---|---|---|---|
| `id` | VARCHAR | False | PK | — |
| `sequence_id` | VARCHAR | False | — | — |
| `ordinal` | INTEGER | False | — | 0-based order among token lines. |
| `label` | VARCHAR | True | — | Source label (e.g. '1', '2''); signs field uses ordinal+1. |
| `surface` | VARCHAR | True | — | From @obverse/@reverse etc. |
| `column_label` | VARCHAR | True | — | — |
| `start_byte` | BIGINT | False | — | — |
| `end_byte` | BIGINT | False | — | — |

#### `edge:HAS_LINE` — HAS_LINE

SequenceVersion → Line.

- **Edge:** node:SequenceVersion → node:Line · cardinality 1:N · qualification — · ID `identity('edge', kind, source_id, target_id)`
- **Files:** `cuneiform/model.py`, `cuneiform/adapters.py`
- **Evidence:** `tests/test_foundation.py::test_deterministic_ids_and_empty_unavailable_layers`
- **Corpus evidence:** `snapshot:c316e7cbbaf8a7fca7705f0efa5c4a07` HAS_LINE=2015 (read by Q-007/Q-018 atlas worker (read-only storage.verify + manifest counts / exported edge Parquet), 2026-11-03)
- **Sources:** SPEC-v0.2.md §5

#### `edge:NEXT_LINE` — NEXT_LINE

Source line order within one sequence. Continuity across surfaces/breaks is not implied.

- **Edge:** node:Line → node:Line · cardinality 0..1 : 0..1 (consecutive token lines) · qualification continuity · ID `identity('edge', kind, source_id, target_id)`
- **Files:** `cuneiform/model.py`, `cuneiform/adapters.py`
- **Evidence:** `tests/test_foundation.py::test_gaps_unknown_and_exclusions_never_bridge`
- **Corpus evidence:** `snapshot:c316e7cbbaf8a7fca7705f0efa5c4a07` NEXT_LINE=1913 (read by Q-007/Q-018 atlas worker (read-only storage.verify + manifest counts / exported edge Parquet), 2026-11-03)
- **Sources:** SPEC-v0.2.md §5

#### `node:SignOccurrence` — SignOccurrence (represented position)

One represented position in a line: a reading, a gap, an unsupported/opaque token, or a source-derived sign label. Positions count represented tokens, not ancient signs.

- **Identity:** identity('occurrence', line_id, position).
- **Provenance:** Inherited through line → sequence → source record; start_byte/end_byte slice the decoded field and are round-trip verified.
- **Uncertainty:** See value:uncertainty-fields. Compounds, determinatives, alternatives, numerals and lines containing <<, >>, {(, )} become opaque 'unsupported' blocking positions.
- **Files:** `cuneiform/schema.sql`, `cuneiform/adapters.py`
- **Evidence:** `tests/test_foundation.py::test_source_utf8_roundtrip_all_positions`, `tests/test_review_regressions.py::test_unsupported_spans_block_interior`
- **Corpus evidence:** `snapshot:c316e7cbbaf8a7fca7705f0efa5c4a07` occurrence=20421 (read by Q-007/Q-018 atlas worker (read-only storage.verify + manifest counts / exported edge Parquet), 2026-11-03)
- **Sources:** SPEC-v0.2.md §4, docs/INGESTION-DESIGN.md

| Field | Type | Nullable | Key | Note |
|---|---|---|---|---|
| `id` | VARCHAR | False | PK | — |
| `line_id` | VARCHAR | False | — | — |
| `position` | INTEGER | False | — | 0-based within line; UNIQUE(line_id, position). |
| `raw` | VARCHAR | False | — | Exact source token including editorial marks. |
| `reading` | VARCHAR | True | — | Mark-stripped reading; NULL for gap/unsupported. |
| `kind` | VARCHAR | False | — | CHECK: 'reading' \| 'gap' \| 'unsupported' \| 'derived_sign' |
| `preservation` | VARCHAR | False | — | Parser emits lost \| damaged \| unknown; never intact. |
| `certainty` | VARCHAR | False | — | Parser emits uncertain \| unmarked \| unknown; never certain. |
| `restoration_basis` | VARCHAR | False | — | Always 'unknown' today. |
| `start_byte` | BIGINT | False | — | — |
| `end_byte` | BIGINT | False | — | — |

#### `value:uncertainty-fields` — Uncertainty fields

Physical preservation, editorial certainty and restoration basis stored separately; raw marks retained.

- **Uncertainty:** Absence of editorial marks is 'unmarked'/'unknown', never 'intact'/'certain'. Consequence: strict-policy counts on real sources are zero by design.
- **Notes:** Value vocabulary of occurrence columns; populated reflects occurrence rows.
- **Values:** preservation (spec): intact | damaged | lost | unknown; certainty (implemented): uncertain | unmarked | unknown (+ 'certain' accepted by strict filters but never emitted); restoration_basis (spec): explicit | proposed | unknown (only unknown emitted)
- **Files:** `cuneiform/adapters.py`
- **Evidence:** `tests/test_foundation.py::test_strict_exclusions_do_not_rewire_next`, `tests/test_linked_review.py::test_strict_opaque_wildcard_parity`
- **Sources:** SPEC-v0.2.md §4

#### `edge:HAS_OCCURRENCE` — HAS_OCCURRENCE

Line → SignOccurrence.

- **Edge:** node:Line → node:SignOccurrence · cardinality 1:N · qualification — · ID `identity('edge', kind, source_id, target_id)`
- **Files:** `cuneiform/model.py`, `cuneiform/adapters.py`
- **Evidence:** `tests/test_projections.py::test_postings_match_canonical_and_graph_counts`
- **Corpus evidence:** `snapshot:c316e7cbbaf8a7fca7705f0efa5c4a07` HAS_OCCURRENCE=20421 (read by Q-007/Q-018 atlas worker (read-only storage.verify + manifest counts / exported edge Parquet), 2026-11-03)
- **Sources:** SPEC-v0.2.md §5

#### `edge:NEXT` — NEXT

Immediate source order between adjacent represented positions in one line, including gaps and unsupported positions. Never crosses lines; exclusions never rewire it.

- **Edge:** node:SignOccurrence → node:SignOccurrence · cardinality 0..1 : 0..1; validated adjacent in same line · qualification extent, boundary · ID `identity('edge', kind, source_id, target_id)`
- **Files:** `cuneiform/model.py`, `cuneiform/adapters.py`, `cuneiform/storage.py`
- **Evidence:** `tests/test_foundation.py::test_gaps_unknown_and_exclusions_never_bridge`, `tests/test_foundation.py::test_strict_exclusions_do_not_rewire_next`
- **Corpus evidence:** `snapshot:c316e7cbbaf8a7fca7705f0efa5c4a07` NEXT=18418 (read by Q-007/Q-018 atlas worker (read-only storage.verify + manifest counts / exported edge Parquet), 2026-11-03)
- **Sources:** SPEC-v0.2.md §5, SPEC-v0.2.md §6

#### `node:SignType` — SignType

Source-derived sign label from the eBL 'signs' field (e.g. ABZ identifiers). A reading-derived conversion, not visual evidence.

- **Identity:** identity('sign', adapter namespace, snapshot_id, label). Snapshot-scoped because the sign-list revision is unknown; no global inventory equivalence.
- **Versioning:** revision column stores the snapshot ID, standing in for the unknown sign-list revision.
- **Uncertainty:** Unsupported exported tokens (e.g. 'B/C') create no SignType.
- **Files:** `cuneiform/schema.sql`, `cuneiform/adapters.py`
- **Evidence:** `tests/test_foundation.py::test_translation_granularity_and_sign_derivation`, `tests/test_projections.py::test_namespace_field_and_sign_identity_separation`
- **Corpus evidence:** `snapshot:c316e7cbbaf8a7fca7705f0efa5c4a07` sign_type=263 (read by Q-007/Q-018 atlas worker (read-only storage.verify + manifest counts / exported edge Parquet), 2026-11-03)
- **Sources:** SPEC-v0.2.md §4

| Field | Type | Nullable | Key | Note |
|---|---|---|---|---|
| `id` | VARCHAR | False | PK | — |
| `namespace` | VARCHAR | False | — | 'ebl-export-signs' |
| `revision` | VARCHAR | False | — | Snapshot ID (sign-list revision unknown). |
| `label` | VARCHAR | False | — | — |

#### `edge:MAPS_TO_SIGN` — MAPS_TO_SIGN

Derived-sign occurrence → SignType, attributed to the source signs field. No alignment to ATF positions.

- **Edge:** node:SignOccurrence → node:SignType · cardinality N:1 (only kind='derived_sign' occurrences) · qualification rule, sign_list_revision, alignment_to_atf · ID `identity('edge', kind, source_id, target_id)`
- **Files:** `cuneiform/model.py`, `cuneiform/adapters.py`
- **Evidence:** `tests/test_foundation.py::test_translation_granularity_and_sign_derivation`
- **Corpus evidence:** `snapshot:c316e7cbbaf8a7fca7705f0efa5c4a07` MAPS_TO_SIGN=11439 (read by Q-007/Q-018 atlas worker (read-only storage.verify + manifest counts / exported edge Parquet), 2026-11-03)
- **Sources:** SPEC-v0.2.md §5

<a id="domain-patterns"></a>
### Positions, postings, n-grams & patterns

Disposable projections and query recipes over canonical rows: ordered positions, postings, bounded n-grams, motifs.

| ID | Kind | Modeled | Implemented | Populated | Verified | Backing | Queue |
|---|---|---|---|---|---|---|---|
| `view:ordered_position` | view | documented | code | sample | unit | view `ordered_position` | — |
| `view:token_context` | view | documented | code | sample | unit | view `token_context` | — |
| `view:next_position` | view | documented | code | sample | unit | view `next_position` | — |
| `table:posting` | table | documented | code | corpus | unit | table `posting` | — |
| `table:ngram` | table | documented | code | corpus | unit | table `ngram` | — |
| `table:projection_registry` | table | documented | code | corpus | unit | table `projection_registry` | Q-023 |
| `value:match-span-id` | value | specified | code | sample | unit | `cuneiform/query.py::motif`, `cuneiform/projections.py::build` | — |
| `query:motif` | query | specified | code | none | unit | `cuneiform/query.py::motif`, `cuneiform/query.py::array_count` | Q-010, Q-017 |
| `query:lookup` | query | documented | code | none | unit | `cuneiform/persisted.py::LayerUnavailable`, `cuneiform/persisted.py::ScopeMismatch`, `cuneiform/persisted.py::lookup_snapshot`, `cuneiform/projections.py::coverage`, `cuneiform/projections.py::lookup`, `cuneiform/projections.py::report`, `cuneiform/projections.py::source_span`, `cuneiform/projections.py::SCOPES_SQL` | Q-008, Q-010, Q-005, Q-023 |
| `query:trace` | query | specified | code | none | unit | `cuneiform/query.py::trace`, `cuneiform/query.py::trace_rows`, `cuneiform/oracc.py::trace_word` | Q-010, Q-005 |
| `value:snapshot-scope` | value | documented | code | none | unit | `cuneiform/persisted.py::scope` | Q-005, Q-008, Q-023 |
| `node:Pattern` | node | specified | none | none | none | — | Q-010, Q-017 |
| `node:PatternMatch` | node | specified | none | none | none | — | Q-010 |
| `concept:compatible-bounds` | concept | specified | none | none | none | — | Q-017 |

#### `view:ordered_position` — ordered_position

All occurrence context (line, sequence, witness, artifact, source, snapshot, raw hash) plus zero-based sequence_position. Line boundaries stay explicit.

- **Notes:** sequence_position counts represented positions, not ancient signs or words.
- **Files:** `cuneiform/schema.sql`
- **Evidence:** `tests/test_projections.py::test_trace_and_reverse_navigation`
- **Sources:** docs/REPRESENTATION-MAP.md

#### `view:token_context` — token_context

Occurrence joined to line, sequence, witness and artifact; base of graph motif queries.

- **Files:** `cuneiform/schema.sql`
- **Evidence:** `tests/test_foundation.py::test_expected_counts_and_array_graph_parity`
- **Sources:** README.md

#### `view:next_position` — next_position

NEXT edges as (source_id, target_id) for joins.

- **Files:** `cuneiform/schema.sql`
- **Evidence:** `tests/test_foundation.py::test_expected_counts_and_array_graph_parity`
- **Sources:** README.md

#### `table:posting` — posting (optional projection)

Indexed token → occurrence postings per namespace + snapshot + field + policy. Reading IDs are scoped; sign postings use SignType IDs.

- **Identity:** identity('posting', projection_id, occurrence_id, policy). token_id = identity('reading', namespace, snapshot_id, field, reading) for atf, or SignType ID for signs.
- **Scope:** Disposable; rebuilt with the projection. Label is a scoped lookup convenience, never cross-source identity.
- **Files:** `cuneiform/projections.py`
- **Evidence:** `tests/test_projections.py::test_postings_match_canonical_and_graph_counts`
- **Corpus evidence:** `snapshot:c316e7cbbaf8a7fca7705f0efa5c4a07` posting=13212 (read by Q-007/Q-018 atlas worker (read-only storage.verify + manifest counts / exported edge Parquet), 2026-11-03)
- **Sources:** docs/REPRESENTATION-MAP.md

| Field | Type | Nullable | Key | Note |
|---|---|---|---|---|
| `id` | VARCHAR | False | PK | — |
| `namespace` | VARCHAR | True | — | — |
| `snapshot_id` | VARCHAR | True | — | — |
| `field` | VARCHAR | True | — | — |
| `policy` | VARCHAR | True | — | 'source' \| 'strict' |
| `token_id` | VARCHAR | True | — | — |
| `label` | VARCHAR | True | — | — |
| `occurrence_id` | VARCHAR | True | — | — |

#### `table:ngram` — ngram (optional projection)

Overlapping same-line windows of configured lengths 2–5 with occurrence IDs, positions and context links. Blockers keep NULL identities; strict windows require every position eligible.

- **Identity:** identity('ngram', projection_id, policy, occurrence_ids); match_id = identity('match', first_occurrence_id, last_occurrence_id) shared with graph motif results.
- **Scope:** Bounded: max 20,000 positions / 100,000 derived rows; budget failures leave the existing projection intact.
- **Uncertainty:** Alternatives are opaque blockers, not enumerated hypotheses. '?' matches exactly one represented position.
- **Files:** `cuneiform/projections.py`
- **Evidence:** `tests/test_projections.py::test_independent_expectations_overlaps_and_blockers`, `tests/test_projections.py::test_caps_configuration_and_atomic_failure`
- **Corpus evidence:** `snapshot:c316e7cbbaf8a7fca7705f0efa5c4a07` ngram=62152 (read by Q-007/Q-018 atlas worker (read-only storage.verify + manifest counts / exported edge Parquet), 2026-11-03)
- **Sources:** docs/REPRESENTATION-MAP.md

| Field | Type | Nullable | Key | Note |
|---|---|---|---|---|
| `id` | VARCHAR | False | PK | — |
| `match_id` | VARCHAR | True | — | — |
| `namespace` | VARCHAR | True | — | — |
| `snapshot_id` | VARCHAR | True | — | — |
| `field` | VARCHAR | True | — | — |
| `policy` | VARCHAR | True | — | — |
| `length` | INTEGER | True | — | — |
| `token_ids` | JSON | True | — | — |
| `readings` | JSON | True | — | — |
| `occurrence_ids` | JSON | True | — | — |
| `sequence_id` | VARCHAR | True | — | — |
| `line_id` | VARCHAR | True | — | — |
| `start_position` | INTEGER | True | — | — |
| `end_position` | INTEGER | True | — | — |
| `witness_id` | VARCHAR | True | — | — |
| `artifact_id` | VARCHAR | True | — | — |
| `source_record_id` | VARCHAR | True | — | — |

#### `table:projection_registry` — projection_registry

Revision, configuration, source-binding hash, canonical-table hash and asset inventory of the current derived projection; stale detection. Configuration ceilings: defaults 20,000 positions / 100,000 rows; CORPUS preset 2M / 20M; FULL preset (Q-023) 12M / 80M, equal to the raised hard caps. Ceilings are part of the projection spec and so of the snapshot ID.

- **Identity:** identity('projection', REVISION, config, source_hash, canonical_hash).
- **Provenance:** Consistency check, not authentication.
- **Files:** `cuneiform/schema.sql`, `cuneiform/projections.py`
- **Evidence:** `tests/test_projections.py::test_strict_breaks_paths_and_stale_rebuild`
- **Corpus evidence:** `snapshot:c316e7cbbaf8a7fca7705f0efa5c4a07` projection_registry=1; `snapshot:edaab55c1a39cc65ad7c76e6d12547a7` projection_registry=1; `snapshot:fc7c350439f9edfee61b5f35bdd4d65a` projection_registry=1 (read by Q-007/Q-018 atlas worker (read-only storage.verify + manifest counts / exported edge Parquet), 2026-11-03)
- **Sources:** docs/REPRESENTATION-MAP.md

| Field | Type | Nullable | Key | Note |
|---|---|---|---|---|
| `id` | VARCHAR | False | PK | — |
| `revision` | VARCHAR | False | — | — |
| `config` | JSON | False | — | — |
| `source_hash` | VARCHAR | False | — | — |
| `canonical_hash` | VARCHAR | False | — | — |
| `assets` | JSON | False | — | — |

#### `value:match-span-id` — Match span ID

identity('match', first_occurrence_id, last_occurrence_id): stable across policy/config changes; shared by graph motif matches and ngram.match_id; deduplicates alternative paths to the same span.

- **Notes:** Value carried in ngram.match_id; populated reflects ngram rows.
- **Files:** `cuneiform/query.py`, `cuneiform/projections.py`
- **Evidence:** `tests/test_projections.py::test_postings_match_canonical_and_graph_counts`
- **Sources:** SPEC-v0.2.md §6

#### `query:motif` — Graph motif query

Exact / '?' / bounded-skip (0–2 represented positions before last item) motif over NEXT, lengths 2–5, single namespace/snapshot scope. Returns support, denominators and labelled-unresolved bounds. Results are not stored.

- **Uncertainty:** Compositions = null; bounds = 'unresolved; compatible alternative assignments not evaluated'; gap extent is represented positions, not ancient sign count.
- **Notes:** Runtime result, not rows: populated is 'none' by definition.
- **Files:** `cuneiform/query.py`
- **Evidence:** `tests/test_foundation.py::test_expected_counts_and_array_graph_parity`, `tests/test_linked_review.py::test_multiple_text_scopes_refused`
- **Sources:** SPEC-v0.2.md §6

#### `query:lookup` — Bounded lookup recipes

Named recipes: postings, motifs, span, sequence, occurrence, reverse-postings, reverse-motifs, aliases, catalog, translations, neighbors, nodes, words and lemmas. Default 20 / max 100 rows with truncation and next_offset. Lookups on a persisted snapshot also return its scope (value:snapshot-scope). Q-023: occurrence, span, postings and scope reads never filter the ordered_position window by a non-partition column (that computed the window for every position: OOM at 256 MB on 5,000 records); they resolve sequence_id first or page posting rows before joining positions. Same rows (regression test against the original SQL).

- **Notes:** Candidate backing for MCP read tools and the UI. Since 94af111: persisted.ScopeMismatch for a namespace/snapshot override that cannot match; persisted.LayerUnavailable when the layer table is empty (an empty table means the layer is unavailable, never zero); a loaded layer with no match returns rows []. Each call verifies the snapshot once; latency_ms is query-only (latency_scope) and timing adds verify_ms, query_ms and end_to_end_ms. At 63f4221 lookup_snapshot, query.connect and query.trace refuse a symlinked store entry (symlinked-entry) on both the plain path and the StoreEntry (writer-tested).
- **Files:** `cuneiform/projections.py`, `cuneiform/persisted.py`, `cuneiform/cli.py`
- **Evidence:** `tests/test_projections.py::test_trace_and_reverse_navigation`, `tests/test_projections.py::test_caps_configuration_and_atomic_failure`, `tests/test_corpus_pilot.py::test_words_lemmas_senses_and_claims_without_invented_translation`, `tests/test_publication.py::test_lookup_verifies_once_labels_latency_and_types_errors`, `tests/test_full_import.py::test_partition_first_lookups_equal_the_original_window_filtered_sql`
- **Sources:** docs/REPRESENTATION-MAP.md

#### `query:trace` — Evidence trace

Occurrence → raw bytes round-trip with source binding/hash and whole-record checks; returns edges and unaligned in-sequence translations. For cohort snapshots it also resolves the byte span in the original parent file (parent_trace); oracc.trace_word does the same for ORACC words. Occurrence traces return empty words/senses/images.

- **Notes:** Since 94af111 a trace returns timing (and parent_trace_ms for cohorts) and the publication label of the snapshot it read.
- **Files:** `cuneiform/query.py`, `cuneiform/oracc.py`
- **Evidence:** `tests/test_trace_and_admission.py::test_trace_resolves_source_and_unknowns`, `tests/test_linked_review.py::test_wrong_source_and_manifest_rejected`, `tests/test_corpus_pilot.py::test_snapshots_verify_parity_and_traces`
- **Sources:** SPEC-v0.2.md §6, SPEC-v0.2.md §9

#### `value:snapshot-scope` — Snapshot scope

Returned with every persisted lookup: scope kind (single input, rule-selected cohort, selection, or all eligible records of a fixed release), cohort size and eligible/parent denominators, so counts are never read as corpus-wide statistics. The all-eligible kind (Q-023) names the fixed release, the eligible count, every exclusion reason, the per-record accounting and the conservative-parse caveat (not linguistic completeness).

- **Notes:** Derived from the manifest, not rows. For the 300 cohort: 'rule-selected cohort', 300 of 20,896 eligible, 23,289 parent records. Since 94af111 scope also reports publication (the ledger label), identity_formula and input_identity (the contract-independent legacy-formula ID of the inputs, for grouping a legacy snapshot with a manifest-3 rebuild without merging them; ORACC pairs differ because the adapter is part of the selection ID).
- **Files:** `cuneiform/persisted.py`
- **Evidence:** `tests/test_corpus_pilot.py::test_snapshots_verify_parity_and_traces`, `tests/test_full_import.py::test_all_eligible_cohort_accounts_for_every_parent_record_and_labels_scope`
- **Sources:** CHECKPOINT.md

#### `node:Pattern` — Pattern

Bounded expression over signs or lemmas with namespace, gap, boundary, segmentation and ambiguity policy. Today patterns are transient query arguments.

- **Sources:** SPEC-v0.2.md §4

#### `node:PatternMatch` — PatternMatch (saved evidence)

Optional persisted match for saved evidence packets; bulk matches remain indexed rows/results.

- **Sources:** SPEC-v0.2.md §4

#### `concept:compatible-bounds` — Alternative-aware lower/upper bounds

Certain count plus min/max support over globally compatible alternative assignments, with a complexity budget and explicit unresolved result.

- **Sources:** SPEC-v0.2.md §6

<a id="domain-linguistic"></a>
### Words, lemmas, senses & translations

Word instances, dictionary bridge and source-authored translation text. The ORACC ccpo pilot populates words, lemmas and senses; translation strings come from eBL only (ORACC JSON carries none).

| ID | Kind | Modeled | Implemented | Populated | Verified | Backing | Queue |
|---|---|---|---|---|---|---|---|
| `node:WordToken` | node | specified | code | corpus | unit | table `word_token` | Q-011, Q-005 |
| `edge:HAS_WORD` | edge | specified | code | corpus | unit | model.EDGE_TYPES | Q-011, Q-005 |
| `edge:HAS_SIGN` | edge | specified | schema | none | none | model.EDGE_TYPES | Q-011 |
| `node:Lemma` | node | specified | code | corpus | unit | table `lemma` | Q-011, Q-005 |
| `edge:LEMMATIZED_AS` | edge | specified | code | corpus | unit | model.EDGE_TYPES | Q-011, Q-005 |
| `node:Sense` | node | specified | code | corpus | unit | table `sense` | Q-011, Q-005 |
| `edge:HAS_SENSE` | edge | specified | code | corpus | unit | model.EDGE_TYPES | Q-011, Q-005 |
| `edge:IN_SENSE` | edge | documented | code | corpus | unit | model.EDGE_TYPES | Q-005, Q-011 |
| `node:TranslationSegment` | node | specified | code | corpus | unit | table `translation_segment` | Q-011, Q-005 |
| `edge:PLACED_IN_SEQUENCE` | edge | documented | code | sample | unit | portable_edge | — |
| `edge:TRANSLATES` | edge | specified | schema | none | none | model.EDGE_TYPES | Q-011 |
| `view:translation_context` | view | documented | code | sample | unit | view `translation_context` | — |

#### `node:WordToken` — WordToken

Source word instance from an ORACC lemmatized text (cdl l-node): form, line label and order. ORACC's own segmentation; nothing is inferred by splitting. Graphemes stay in raw JSON and are not mapped to SignOccurrence.

- **Identity:** identity('word', sequence_id, ORACC node id, JSON path).
- **Uncertainty:** Segmentation is never inferred by splitting on punctuation; alternative groupings need hypothesis IDs.
- **Coverage:** ORACC ccpo, 51 texts: 6,888 word instances; 2,344 have no citation form and stay unlemmatized WordTokens.
- **Files:** `cuneiform/schema.sql`, `cuneiform/oracc.py`
- **Evidence:** `tests/test_foundation.py::test_deterministic_ids_and_empty_unavailable_layers`, `tests/test_corpus_pilot.py::test_words_lemmas_senses_and_claims_without_invented_translation`
- **Corpus evidence:** `snapshot:edaab55c1a39cc65ad7c76e6d12547a7` word_token=6888 (read by Q-007/Q-018 atlas worker (read-only storage.verify + manifest counts / exported edge Parquet), 2026-11-03)
- **Sources:** SPEC-v0.2.md §4

| Field | Type | Nullable | Key | Note |
|---|---|---|---|---|
| `id` | VARCHAR | False | PK | — |
| `sequence_id` | VARCHAR | False | — | — |
| `source_locator` | VARCHAR | False | — | — |
| `form` | VARCHAR | True | — | — |
| `segmentation` | VARCHAR | False | — | — |

#### `edge:HAS_WORD` — HAS_WORD

SequenceVersion → WordToken in ORACC's order, with its line label.

- **Edge:** node:SequenceVersion → node:WordToken · cardinality 1:N per source lemmatization sequence · qualification line_label, order
- **Files:** `cuneiform/model.py`, `cuneiform/oracc.py`
- **Evidence:** `tests/test_corpus_pilot.py::test_words_lemmas_senses_and_claims_without_invented_translation`
- **Corpus evidence:** `snapshot:edaab55c1a39cc65ad7c76e6d12547a7` HAS_WORD=6888 (read by Q-007/Q-018 atlas worker (read-only storage.verify + manifest counts / exported edge Parquet), 2026-11-03)
- **Sources:** SPEC-v0.2.md §5

#### `edge:HAS_SIGN` — HAS_SIGN

WordToken → ordered SignOccurrences. Only created when the source supplies explicit alignment. Registered, never written.

- **Edge:** node:WordToken → node:SignOccurrence · cardinality 1:N ordered · qualification order, segmentation
- **Files:** `cuneiform/model.py`
- **Sources:** SPEC-v0.2.md §5

#### `node:Lemma` — Lemma

Namespaced dictionary entry from ORACC lemmatization: citation form, language, POS and project revision. Shared by every word instance with the same entry in one snapshot.

- **Identity:** identity('lemma', namespace, snapshot, language, citation form, guideword, POS): snapshot-scoped, never merged across snapshots.
- **Coverage:** ORACC ccpo: 1,122 lemmas from 4,544 lemmatized word instances.
- **Notes:** Lemma.source_record_id still points at the first attesting text (schema NOT NULL, no project-level record); deferred schema change per Q-005 F4. Corpus evidence is snapshot:edaab55c (oracc-cdl-1, written by d6049e2); its counts are valid, but it is superseded by the accepted oracc-cdl-2 rebuild snapshot:5e51403b for sense provenance (same counts per Q-020; accepted by v0.3).
- **Files:** `cuneiform/schema.sql`, `cuneiform/oracc.py`
- **Evidence:** `tests/test_foundation.py::test_oracc_explicitly_not_verified`, `tests/test_corpus_pilot.py::test_words_lemmas_senses_and_claims_without_invented_translation`
- **Corpus evidence:** `snapshot:edaab55c1a39cc65ad7c76e6d12547a7` lemma=1122 (read by Q-007/Q-018 atlas worker (read-only storage.verify + manifest counts / exported edge Parquet), 2026-11-03)
- **Sources:** SPEC-v0.2.md §4

| Field | Type | Nullable | Key | Note |
|---|---|---|---|---|
| `id` | VARCHAR | False | PK | — |
| `source_record_id` | VARCHAR | False | — | — |
| `namespace` | VARCHAR | False | — | — |
| `citation_form` | VARCHAR | True | — | — |
| `language` | VARCHAR | True | — | — |
| `pos` | VARCHAR | True | — | — |
| `revision` | VARCHAR | False | — | — |

#### `edge:LEMMATIZED_AS` — LEMMATIZED_AS

WordToken → Lemma as asserted by the ORACC lemmatization (signature, instance, normalization, guideword, epos).

- **Edge:** node:WordToken → node:Lemma · cardinality N:1 per source analysis · qualification epos, guideword, inst, norm, sig
- **Files:** `cuneiform/model.py`, `cuneiform/oracc.py`
- **Evidence:** `tests/test_corpus_pilot.py::test_words_lemmas_senses_and_claims_without_invented_translation`
- **Corpus evidence:** `snapshot:edaab55c1a39cc65ad7c76e6d12547a7` LEMMATIZED_AS=4544 (read by Q-007/Q-018 atlas worker (read-only storage.verify + manifest counts / exported edge Parquet), 2026-11-03)
- **Sources:** SPEC-v0.2.md §5

#### `node:Sense` — Sense

Dictionary sense under a lemma: guideword and contextual English sense from ORACC. A gloss is a lexical gloss, never a translation.

- **Identity:** identity('sense', lemma_id, sense string).
- **Provenance:** oracc-cdl-1 (edaab55c) put an instance sig in source_locator for 1,309 shared Sense rows (Q-005 F4). oracc-cdl-2 (94af111) uses a sense-key locator (project, lemma key, sense) and a labelled first-attestation pointer, never an instance sig; per-occurrence sigs are on edge:IN_SENSE.
- **Coverage:** ORACC ccpo: 1,317 senses.
- **Notes:** Corpus evidence is snapshot:edaab55c (oracc-cdl-1, written by d6049e2); its counts are valid, but it is superseded by the accepted oracc-cdl-2 rebuild snapshot:5e51403b for sense provenance (same counts per Q-020; accepted by v0.3).
- **Files:** `cuneiform/schema.sql`, `cuneiform/oracc.py`
- **Evidence:** `tests/test_foundation.py::test_deterministic_ids_and_empty_unavailable_layers`, `tests/test_corpus_pilot.py::test_words_lemmas_senses_and_claims_without_invented_translation`
- **Corpus evidence:** `snapshot:edaab55c1a39cc65ad7c76e6d12547a7` sense=1317 (read by Q-007/Q-018 atlas worker (read-only storage.verify + manifest counts / exported edge Parquet), 2026-11-03)
- **Sources:** SPEC-v0.2.md §4

| Field | Type | Nullable | Key | Note |
|---|---|---|---|---|
| `id` | VARCHAR | False | PK | — |
| `lemma_id` | VARCHAR | False | — | — |
| `guideword` | VARCHAR | True | — | — |
| `gloss` | VARCHAR | True | — | — |
| `source_locator` | VARCHAR | False | — | — |

#### `edge:HAS_SENSE` — HAS_SENSE

Lemma → Sense, written once per distinct sense of a lemma.

- **Provenance:** Since oracc-cdl-2 the edge carries an attribution note: its source_record_id still names the first attesting text, because the schema has no project-level record (deferred schema change, Q-005 F4).
- **Notes:** Corpus evidence is snapshot:edaab55c (oracc-cdl-1, written by d6049e2); its counts are valid, but it is superseded by the accepted oracc-cdl-2 rebuild snapshot:5e51403b for sense provenance (same counts per Q-020; accepted by v0.3).
- **Edge:** node:Lemma → node:Sense · cardinality 1:N · qualification attribution
- **Files:** `cuneiform/model.py`, `cuneiform/oracc.py`
- **Evidence:** `tests/test_corpus_pilot.py::test_words_lemmas_senses_and_claims_without_invented_translation`
- **Corpus evidence:** `snapshot:edaab55c1a39cc65ad7c76e6d12547a7` HAS_SENSE=1317 (read by Q-007/Q-018 atlas worker (read-only storage.verify + manifest counts / exported edge Parquet), 2026-11-03)
- **Sources:** SPEC-v0.2.md §5

#### `edge:IN_SENSE` — IN_SENSE

WordToken → Sense: the contextual sense ORACC asserts for this lemmatization instance (f.sense). An English lexical gloss, not a translation and not an alignment.

- **Provenance:** Explicit per-instance source assertion. basis states that it is a gloss, not a translation. Since oracc-cdl-2 (94af111) each edge also carries the occurrence's own ORACC sig, inst and payload_pointer, so the instance signature lives on the occurrence, not on the shared Sense row (Q-005 F4).
- **Notes:** Corpus evidence is snapshot:edaab55c (oracc-cdl-1, written by d6049e2); its counts are valid, but it is superseded by the accepted oracc-cdl-2 rebuild snapshot:5e51403b for sense provenance (same counts per Q-020; accepted by v0.3). Q-020 checked all 4,544 IN_SENSE edges of 5e51403b against the raw nodes (0 mismatches).
- **Edge:** node:WordToken → node:Sense · cardinality N:1 (each lemmatized word points at exactly its own sense) · qualification basis, inst, payload_pointer, sig
- **Files:** `cuneiform/model.py`, `cuneiform/oracc.py`
- **Evidence:** `tests/test_corpus_pilot.py::test_words_lemmas_senses_and_claims_without_invented_translation`, `tests/test_corpus_pilot.py::test_snapshots_verify_parity_and_traces`
- **Corpus evidence:** `snapshot:edaab55c1a39cc65ad7c76e6d12547a7` IN_SENSE=4544 (read by Q-007/Q-018 atlas worker (read-only storage.verify + manifest counts / exported edge Parquet), 2026-11-03)
- **Sources:** docs/SOURCE-AUDIT.md, CHECKPOINT.md

#### `node:TranslationSegment` — TranslationSegment

Source-authored translation string (eBL '#tr.<lang>:' lines) with language and placement. Alignment granularity is 'unresolved-span'.

- **Identity:** identity('translation', sequence_id, source_line_no).
- **Provenance:** source_record_id + ATTRIBUTED_TO; locator 'field:utf8:start:end'.
- **Uncertainty:** A translation follows several source lines in the frozen example; assigning it to one line would fabricate alignment. author is NULL (no explicit contract).
- **Coverage:** eBL only (#tr lines; 80 segments in the eBL∩ccpo cohort). ORACC JSON exports carry no translation text, so ORACC imports create none and record the gap as an exclusion.
- **Files:** `cuneiform/schema.sql`, `cuneiform/adapters.py`
- **Evidence:** `tests/test_foundation.py::test_translation_granularity_and_sign_derivation`, `tests/test_review_regressions.py::test_translation_extent_and_unrecognized_accounting`
- **Corpus evidence:** `snapshot:c316e7cbbaf8a7fca7705f0efa5c4a07` translation_segment=80 (read by Q-007/Q-018 atlas worker (read-only storage.verify + manifest counts / exported edge Parquet), 2026-11-03)
- **Sources:** SPEC-v0.2.md §4, docs/INGESTION-DESIGN.md

| Field | Type | Nullable | Key | Note |
|---|---|---|---|---|
| `id` | VARCHAR | False | PK | — |
| `source_record_id` | VARCHAR | False | — | — |
| `sequence_id` | VARCHAR | True | — | Placement only (PLACED_IN_SEQUENCE). |
| `language` | VARCHAR | False | — | — |
| `text` | VARCHAR | False | — | — |
| `author` | VARCHAR | True | — | Always NULL today. |
| `granularity` | VARCHAR | False | — | 'unresolved-span' |
| `locator` | VARCHAR | False | — | — |

#### `edge:PLACED_IN_SEQUENCE` — PLACED_IN_SEQUENCE

TranslationSegment → SequenceVersion placement only; carries unresolved alignment explicitly.

- **Edge:** node:TranslationSegment → node:SequenceVersion · cardinality N:0..1 · qualification alignment · ID `'context-edge:' || translation_segment.id`
- **Files:** `cuneiform/schema.sql`
- **Evidence:** `tests/test_projections.py::test_alias_ambiguity_cross_source_and_translations`
- **Sources:** docs/REPRESENTATION-MAP.md

#### `edge:TRANSLATES` — TRANSLATES

TranslationSegment → Passage (registry). Spec allows word/span/passage targets with explicit granularity. Registered, never written.

- **Notes:** Registry only admits Passage targets; word/span targets need a registry change (Q-011).
- **Edge:** node:TranslationSegment → node:Passage · cardinality N:M · qualification granularity
- **Files:** `cuneiform/model.py`
- **Sources:** SPEC-v0.2.md §5

#### `view:translation_context` — translation_context

Translation text/language/granularity/locator joined to sequence, witness, artifact, source and snapshot.

- **Files:** `cuneiform/schema.sql`
- **Evidence:** `tests/test_projections.py::test_alias_ambiguity_cross_source_and_translations`
- **Sources:** docs/REPRESENTATION-MAP.md

<a id="domain-claims"></a>
### Claims, alternatives & dependencies

Attributed assertions, alternatives, restorations, review history and interpretation dependency edges.

| ID | Kind | Modeled | Implemented | Populated | Verified | Backing | Queue |
|---|---|---|---|---|---|---|---|
| `node:Claim` | node | specified | code | corpus | unit | table `claim` | Q-014, Q-017 |
| `view:catalog_alias` | view | documented | code | sample | unit | view `catalog_alias` | — |
| `edge:CLAIM_SUBJECT` | edge | documented | code | sample | unit | portable_edge | Q-014 |
| `value:source-independence` | value | specified | code | sample | unit | table_column `claim.details` | — |
| `concept:hypothesis-group` | concept | specified | none | none | none | — | Q-017 |
| `edge:ALIGNED_WITH` | edge | specified | none | none | none | — | Q-016 |
| `edge:RESTORED_FROM` | edge | specified | none | none | none | — | Q-017 |
| `edge:DEPENDS_ON` | edge | specified | none | none | none | — | Q-017 |
| `node:ReviewDecision` | node | specified | none | none | none | — | Q-010 |
| `edge:REVIEWED_BY` | edge | specified | none | none | none | — | Q-010 |

#### `node:Claim` — Claim

Attributed assertion with predicate, status and rationale. Only predicate 'catalog_alias' is written today.

- **Identity:** identity('claim', source_record_id, locator, object_key). Duplicate claims from different records stay separate nodes.
- **Provenance:** source_record_id + ATTRIBUTED_TO; details.locator.
- **Uncertainty:** status 'source-attributed-unreviewed'; details.independence 'unknown'.
- **Files:** `cuneiform/schema.sql`, `cuneiform/adapters.py`
- **Evidence:** `tests/test_foundation.py::test_rejections_and_no_alias_merge`, `tests/test_projections.py::test_alias_ambiguity_cross_source_and_translations`
- **Corpus evidence:** `snapshot:c316e7cbbaf8a7fca7705f0efa5c4a07` claim=51; `snapshot:edaab55c1a39cc65ad7c76e6d12547a7` claim=105; `snapshot:fc7c350439f9edfee61b5f35bdd4d65a` claim=334 (read by Q-007/Q-018 atlas worker (read-only storage.verify + manifest counts / exported edge Parquet), 2026-11-03)
- **Sources:** SPEC-v0.2.md §4

| Field | Type | Nullable | Key | Note |
|---|---|---|---|---|
| `id` | VARCHAR | False | PK | — |
| `source_record_id` | VARCHAR | False | — | — |
| `subject_id` | VARCHAR | False | — | Untyped reference; Artifact for catalog_alias. |
| `predicate` | VARCHAR | False | — | — |
| `object_key` | VARCHAR | False | — | Unresolved string, e.g. 'cdli:P000001' or 'catalog-label:...'. |
| `status` | VARCHAR | False | — | — |
| `rationale` | VARCHAR | False | — | — |
| `details` | JSON | False | — | — |

#### `view:catalog_alias` — catalog_alias

Source-attributed alias claims with namespace/snapshot. Exact target key lookup yields candidate artifacts without an equivalence edge.

- **Files:** `cuneiform/schema.sql`
- **Evidence:** `tests/test_projections.py::test_alias_ambiguity_cross_source_and_translations`
- **Sources:** docs/REPRESENTATION-MAP.md

#### `edge:CLAIM_SUBJECT` — CLAIM_SUBJECT

Claim → its subject (Artifact for catalog aliases). Derived in portable_edge.

- **Notes:** Target is claim.subject_id, untyped; Artifact is the only populated target. Future DateClaims would target Artifact/Witness/Composition/Edition.
- **Edge:** node:Claim → node:Artifact · cardinality N:1 · qualification — · ID `'claim-edge:' || claim.id`
- **Files:** `cuneiform/schema.sql`
- **Evidence:** `tests/test_projections.py::test_alias_ambiguity_cross_source_and_translations`
- **Sources:** docs/REPRESENTATION-MAP.md

#### `value:source-independence` — Source independence

independent | derived | unknown. Syndicated identical text is never independent corroboration. Alias claims record 'unknown'.

- **Notes:** Stored inside claim.details JSON; populated reflects claim rows. A gloss repeated on many records (for example a CDLI period range) is one assertion, not many corroborating ones.
- **Files:** `cuneiform/adapters.py`
- **Evidence:** `tests/test_projections.py::test_alias_ambiguity_cross_source_and_translations`
- **Sources:** SPEC-v0.2.md §5

#### `concept:hypothesis-group` — Hypothesis groups / exclusive alternatives

Exclusive alternatives with group IDs and compatibility constraints. Today alternatives are opaque blocking positions.

- **Sources:** SPEC-v0.2.md §4

#### `edge:ALIGNED_WITH` — ALIGNED_WITH

Span ↔ span or occurrence ↔ image region through an alignment Claim subtype.

- **Notes:** Endpoints also include span ↔ span (witness alignment).
- **Edge:** node:SignOccurrence → node:Region · cardinality N:M via alignment claim · qualification claim_id, score, granularity
- **Sources:** SPEC-v0.2.md §5

#### `edge:RESTORED_FROM` — RESTORED_FROM

Reading/claim → supporting witness span or edition, explicit or proposed.

- **Edge:** node:SignOccurrence → node:Witness · cardinality N:M · qualification basis, attribution
- **Sources:** SPEC-v0.2.md §5

#### `edge:DEPENDS_ON` — DEPENDS_ON / SUPPORTED_BY

Interpretation or result → claim/source/span. Support is not truth propagation; cycles are review flags.

- **Edge:** node:Claim → node:Claim · cardinality N:M · qualification kind (depends\|supports), attribution
- **Sources:** SPEC-v0.2.md §5

#### `node:ReviewDecision` — ReviewDecision (append-only)

Local append-only decision: reviewer identity, time, rationale, expected prior revision. Linked by REVIEWED_BY / SUPERSEDES.

- **Temporal:** Decision time is system/transaction time of the review, not source time.
- **Sources:** SPEC-v0.2.md §4, SPEC-v0.2.md §5

#### `edge:REVIEWED_BY` — REVIEWED_BY / SUPERSEDES

Append-only review and version history.

- **Edge:** node:Claim → node:ReviewDecision · cardinality N:M append-only · qualification expected_prior_revision
- **Sources:** SPEC-v0.2.md §5

<a id="domain-temporal"></a>
### Temporal model (decisions accepted, not implemented)

Separates source-asserted time of events/artifacts/custody/publication from system knowledge and processing time. Routine decisions TD-1 to TD-7 accepted by the parent (Q-014); no temporal schema is implemented.

| ID | Kind | Modeled | Implemented | Populated | Verified | Backing | Queue |
|---|---|---|---|---|---|---|---|
| `temporal:system-time` | value | documented | code | none | disk | `cuneiform/storage.py::materialize` | Q-014 |
| `temporal:source-validity` | value | proposed | none | none | none | — | Q-014, Q-015 |
| `value:TemporalExtent` | value | proposed | none | none | none | — | Q-014, Q-015 |
| `value:temporal-role` | value | proposed | none | none | none | — | Q-014 |
| `node:DateClaim` | node | proposed | none | none | none | — | Q-014, Q-015 |
| `node:ChronologyScheme` | node | proposed | none | none | none | — | Q-014 |
| `facet:cdli-temporal-fields` | facet | documented | none | none | none | — | Q-013, Q-015 |
| `facet:ebl-temporal-fields` | facet | documented | none | none | none | — | Q-012, Q-015 |
| `decision:TD-1` | decision | documented | none | none | none | — | Q-014 |
| `decision:TD-2` | decision | documented | none | none | none | — | Q-014 |
| `decision:TD-3` | decision | documented | none | none | none | — | Q-014 |
| `decision:TD-4` | decision | documented | none | none | none | — | Q-014 |
| `decision:TD-5` | decision | documented | none | none | none | — | Q-014 |
| `decision:TD-6` | decision | documented | none | none | none | — | Q-014 |
| `decision:TD-7` | decision | documented | none | none | none | — | Q-014 |

#### `temporal:system-time` — System (knowledge/processing) time

When this system acquired/imported bytes. Implemented only as manifest retrieved_or_imported_at (UTC). Excluded from every ID. No per-row recorded_at.

- **Temporal:** Transaction/knowledge time. The snapshot is the as-of boundary: a fact is 'known' from the snapshot that contains it. Projection build time is not recorded.
- **Notes:** Manifest value, not rows. Disk level rests on the corpus worker's UNVERIFIED d6049e2 run (historically the parent's 2ab620b run).
- **Files:** `cuneiform/storage.py`
- **Evidence:** `tests/test_disk_delivery.py::test_snapshot_idempotence_relocation_parquet_and_tamper`
- **Verified by:** `q023-reviewer-disk-057a0b7` (Independent full-corpus reviewer c0273cbf, 2026-11-05, code `057a0b7`); `q023-reviewer-inmemory-057a0b7` (Independent full-corpus reviewer c0273cbf, 2026-11-05, code `057a0b7`); `review-v03-disk-63f4221` (Final publication review c5df3251 (independent of the Q-022 fix worker), 2026-11-03, code `63f4221`); `q021-disk-63f4221` (Atlas repair worker (Q-021), 2026-11-03, code `63f4221`); `backend-q022-disk-63f4221` (Q-022 backend fix worker (Q-020 R1-R5 round), 2026-11-03, code `63f4221`); `q020-disk-94af111` (Q-020 review sub-agent (independent of fix task 44ddaeb1), 2026-11-03, code `94af111`); `backend-fix-disk-94af111` (Backend fix worker, task 44ddaeb1 (Q-001 fix round), 2026-11-03, code `94af111`); `corpus-worker-disk-d6049e2` (Corpus worker, task 64821742 (Q-001), 2026-11-03, code `d6049e2`); `parent-full-disk-2ab620b` (Parent orchestrator, 2026-11-03, code `2ab620b`)
- **Sources:** cuneiform/storage.py

#### `temporal:source-validity` — Source temporal validity

When the source asserted/revised the record (e.g. CDLI date_updated, eBL revision history, edition date) as distinct from when we retrieved it.

- **Temporal:** Valid-from of the source assertion. Does not date the artifact.
- **Raw retained in:** source_record.raw_json (CDLI date_entered, date_updated; eBL record history fields when present)
- **Notes:** Decisions accepted in Q-014; the shape stays proposed until Q-015 implements it. No temporal schema exists.
- **Sources:** SPEC-v0.2.md §3

#### `value:TemporalExtent` — TemporalExtent (proposed value type)

Verbatim source string plus optional parsed interval: start/end each {year, bound: closed|open|unknown}, precision (default as-printed), approximate flag, calendar, era convention, parse rule ID. Parsing never adds precision; the raw string is always kept.

- **Notes:** Decisions accepted in Q-014; the shape stays proposed until Q-015 implements it. No temporal schema exists.
- **Decisions:** `decision:TD-1`, `decision:TD-2`, `decision:TD-4`, `decision:TD-5`
- **Sources:** docs/MODEL-ATLAS.md#temporal-model

| Field | Type | Nullable | Key | Note |
|---|---|---|---|---|
| `raw` | string | — | — | Verbatim source text; always kept. |
| `calendar` | enum | — | — | native-regnal \| seleucid-era \| julian-proleptic \| gregorian \| catalog-year-label \| unknown |
| `era_convention` | enum | — | — | BC-historical (no year 0) \| astronomical \| CE \| unknown |
| `start_year_astronomical` | integer\|null | — | — | 1 BCE = 0, 2 BCE = -1; only when the source states an absolute year. |
| `start_bound` | enum | — | — | closed \| open \| unknown |
| `end_year_astronomical` | integer\|null | — | — | — |
| `end_bound` | enum | — | — | closed \| open \| unknown ('2015ff.' → open end) |
| `precision` | enum | — | — | as-printed \| unknown \| millennium \| century \| decade \| year \| month \| day \| period-label-only. as-printed (default for printed ranges) keeps the bounds exactly as printed and claims no precision; unknown when precision cannot be determined. Round numbers never imply century precision. |
| `approximate` | boolean | — | — | 'ca.' sets this; it does not widen numbers. |
| `native_date` | object\|null | — | — | Structured regnal/month/day formula as written; no conversion here. |
| `parse_rule` | string | — | — | Versioned parser rule ID; null when raw only. |

#### `value:temporal-role` — Temporal roles (what is being dated)

content-event (dates referenced in the text) · composition (work composed) · production (artifact inscribed) · copy (witness copied) · excavation/find · acquisition/accession · custody interval · publication (edition/catalog) · source-revision · retrieval/ingestion (system) · processing (system).

- **Notes:** A period label on a catalog record usually attributes production/script period, not content events. A composition date and a witness copy date are different claims and are never merged. Decisions accepted in Q-014; the shape stays proposed until Q-015 implements it. No temporal schema exists.
- **Decisions:** `decision:TD-6`
- **Sources:** SPEC-v0.2.md §8

#### `node:DateClaim` — DateClaim (proposed Claim subtype)

Claim with predicate 'dated_to': subject, temporal role, TemporalExtent, basis (catalog-period-gloss, date formula, paleography, archaeological context, prosopography), chronology scheme, attribution and status. Competing datings remain separate claims.

- **Identity:** Proposed: identity('claim', source_record_id, locator, 'dated_to', role, raw). Reuses claim table + CLAIM_SUBJECT if TD-7 accepts.
- **Provenance:** Mandatory source_record_id + exact locator of the raw field.
- **Uncertainty:** No averaging, midpoint or merge across sources. A derived envelope, if ever computed, is a separate derived claim. A CDLI period gloss such as 'Uruk III (ca. 3200-3000 BC)' is the catalog's chronology convention printed on every row of that period: basis catalog-period-gloss, precision as-printed, approximate; it is not a dating of the object.
- **Notes:** Decisions accepted in Q-014; the shape stays proposed until Q-015 implements it. No temporal schema exists.
- **Decisions:** `decision:TD-3`, `decision:TD-7`
- **Sources:** SPEC-v0.2.md §8

#### `node:ChronologyScheme` — ChronologyScheme / PeriodTerm (proposed)

Namespaced period vocabulary (e.g. a CDLI 'period' label, an eBL script period) and versioned period→interval schemes. Label-to-interval conversion is a derived claim citing a scheme; labels are never merged across sources by string.

- **Uncertainty:** Absolute Mesopotamian dates depend on competing chronologies; no scheme is selected by default.
- **Notes:** Decisions accepted in Q-014; the shape stays proposed until Q-015 implements it. No temporal schema exists.
- **Decisions:** `decision:TD-3`
- **Sources:** SPEC-v0.2.md §8

#### `facet:cdli-temporal-fields` — Observed CDLI temporal fields (raw only)

Persisted CDLI artifact JSON (cdli-selection, snapshot:fc7c3504, 51 records): period is an object {id, name, period, sequence, time_range} or null; dates is a list; dates_referenced is a string or null. The earlier retained CSV sample has the headers period, period_remarks, date_of_origin, dates_referenced, alternative_years, accounting_period, publication_date, publication_history, date_entered, date_updated, acquisition_history and excavation_no.

- **Raw retained in:** source_record.raw_json (JSON object per artifact) and artifact.metadata
- **Notes:** Observed in fc7c3504 (structure read from copies by the atlas worker, nothing parsed): period present in 41 of 51 and null in 10, e.g. name 'Neo-Assyrian', period 'Neo-Assyrian (ca. 911-612 BC)', time_range 'ca. 911-612 BC' (label plus a source-attributed approximate range); dates is [] in all 51; dates_referenced is null in 50 and a regnal-style string 'Artaxerxes.19.11.23' in 1, which is not interpreted. accession_no values such as '1883-01-18, 0722' are museum registration numbers, not dates. CSV sample shapes (three retained rows): date_of_origin '00.00.00.00' (sentinel = unknown) or empty, publication_date '1993' or '2015ff.' (open end), date_entered '12/4/2001', date_updated '2020-03-14'. All are catalog assertions, not verified dates.
- **Sources:** docs/INGESTION-DESIGN.md

#### `facet:ebl-temporal-fields` — Observed eBL temporal fields (raw only)

Persisted eBL fragment JSON (ebl-cohort, snapshot:c316e7cb, 51 records): script is {period, periodModifier, sortKey, uncertain}; datesInText is a key in all 51 records (value []), and there is no top-level date key in any of them; record is a list of {date, type, user} edit events. The retained K.1 sample also has archaeology.date, archaeology.findspot.date and references[].document.issued.date-parts.

- **Raw retained in:** artifact.metadata / source_record.raw_json for eBL records
- **Notes:** Observed in c316e7cb (structure only): script.period 'Neo-Assyrian' 24, 'Neo-Babylonian' 20, 'Late Babylonian' 3 and two other values; periodModifier 'None' in all 51; uncertain is a boolean. date: no such key in these 51 records (key absent, not null); datesInText is [] in all 51; no archaeology object. Key presence re-read for atlas-recheck-v0.2 N1 (Q-021 R3 repair worker, source_record.raw_json, no date parsed). record holds 374 eBL editorial events (ISO timestamps of edits): system/editorial time of the source, never an ancient date. Script period is a paleographic attribution, not an absolute date. Q-015 should be scoped against these JSON shapes.
- **Sources:** docs/INGESTION-DESIGN.md

#### `decision:TD-1` — TD-1 Year numbering and BCE convention

Store parsed absolute years as astronomical integers (1 BCE = 0); display BCE/CE; keep the verbatim string and the source era convention.

- **Recommendation:** Option 1. Catalog 'BC' years convert as astronomical = 1 − BC year; record era_convention='BC-historical'.
- **Decision record:** accepted by parent orchestrator (routine conservative default) on 2026-11-03 (Q-014): Option 1: astronomical integers (1 BCE = 0) plus source era convention plus raw string. Escalate to the user if: a default ChronologyScheme, a calendar-conversion authority, or any departure from this choice is proposed. Unresolved historical chronology stays source-qualified, never guessed.
- **Options:** Astronomical integers + era convention + raw (recommended); Signed historical years without year 0; ISO 8601 extended strings only

#### `decision:TD-2` — TD-2 Interval and precision semantics

Each bound is closed/open/unknown; precision is explicit; 'ca.' sets approximate without widening; 'ff.' gives an open end; never compute midpoints or default day/month.

- **Recommendation:** Option 1, optionally serializable to EDTF later. Widening rules would be invented precision.
- **Decision record:** accepted by parent orchestrator (routine conservative default) on 2026-11-03 (Q-014): Option 1 with precision as-printed/unknown added (Q-004 F8): explicit bounds and precision, ca. flags without widening, ff. opens the end, no midpoints or default day/month. Escalate to the user if: a default ChronologyScheme, a calendar-conversion authority, or any departure from this choice is proposed. Unresolved historical chronology stays source-qualified, never guessed.
- **Options:** Explicit bounds + precision + approximate flag (recommended); EDTF strings; Fuzzy numeric ranges with widening

#### `decision:TD-3` — TD-3 Period labels and chronologies

A period label is a namespaced term. A range printed by the source (e.g. '(ca. 3200-3000 BC)') becomes a source-attributed approximate extent. Any other label→interval mapping is a derived claim citing a ChronologyScheme.

- **Recommendation:** Option 1. No default chronology; competing schemes coexist.
- **Decision record:** accepted by parent orchestrator (routine conservative default) on 2026-11-03 (Q-014): Option 1: source-printed ranges only (basis catalog-period-gloss, precision as-printed); no default chronology. Escalate to the user if: a default ChronologyScheme, a calendar-conversion authority, or any departure from this choice is proposed. Unresolved historical chronology stays source-qualified, never guessed.
- **Options:** Source-printed ranges only + cited schemes as derived claims (recommended); Single global period table; Labels only, no intervals

#### `decision:TD-4` — TD-4 Native calendars

Regnal year/month/day formulas and era-based dates are stored as structured native values. Julian conversion only as a derived claim citing a conversion authority; no Gregorian by default.

- **Recommendation:** Option 1. Conversion requires an explicit, versioned authority and is never silent.
- **Decision record:** accepted by parent orchestrator (routine conservative default) on 2026-11-03 (Q-014): Option 1: native values only; no conversion authority adopted, so no conversion claims are produced. Escalate to the user if: a default ChronologyScheme, a calendar-conversion authority, or any departure from this choice is proposed. Unresolved historical chronology stays source-qualified, never guessed.
- **Options:** Native value + optional cited conversion claim (recommended); Convert on ingest; Ignore native dates

#### `decision:TD-5` — TD-5 Sentinels and system-date formats

'00.00.00.00', empty strings and 'None' are unknown, not dates. Ambiguous system dates (e.g. '12/4/2001') parse only under a declared per-source format; otherwise raw only.

- **Recommendation:** Option 1; heuristic parsing would invent month/day order.
- **Decision record:** accepted by parent orchestrator (routine conservative default) on 2026-11-03 (Q-014): Option 1: sentinels and empty strings are unknown; system dates parse only under a declared per-source format. Escalate to the user if: a default ChronologyScheme, a calendar-conversion authority, or any departure from this choice is proposed. Unresolved historical chronology stays source-qualified, never guessed.
- **Options:** Per-source declared formats + sentinel table (recommended); Heuristic date parsing

#### `decision:TD-6` — TD-6 Bitemporal separation

Valid time (what the source asserts about the past) is separate from knowledge time (snapshot that contains the assertion) and processing time (manifests/receipts). Timestamps never enter IDs.

- **Recommendation:** Option 1: consistent with immutable snapshots; per-row timestamps would break deterministic IDs/hashes.
- **Decision record:** accepted by parent orchestrator (routine conservative default) on 2026-11-03 (Q-014): Option 1: snapshot is the knowledge-time boundary; processing time stays in manifests and receipts. Escalate to the user if: a default ChronologyScheme, a calendar-conversion authority, or any departure from this choice is proposed. Unresolved historical chronology stays source-qualified, never guessed.
- **Options:** Snapshot as knowledge-time boundary + manifest times (recommended); Per-row recorded_at columns

#### `decision:TD-7` — TD-7 Competing datings and storage

Every dating is a separate attributed DateClaim in the claim table (predicate 'dated_to', TemporalExtent in details), linked via CLAIM_SUBJECT. Queries return all with attribution; no winner is chosen.

- **Recommendation:** Option 1 first; promote to a typed table only if query needs justify it. Columns on artifact would force a single winner.
- **Decision record:** accepted by parent orchestrator (routine conservative default) on 2026-11-03 (Q-014): Option 1: reuse the claim table with typed details; no winner is chosen. Escalate to the user if: a default ChronologyScheme, a calendar-conversion authority, or any departure from this choice is proposed. Unresolved historical chronology stays source-qualified, never guessed.
- **Options:** Reuse claim table with typed details (recommended); New date_claim table; Typed columns on artifact

<a id="domain-media"></a>
### Images, regions & embeddings (deferred)

Versioned pixels, explicit geometry, detector claims and vectors. Explicitly deferred; nothing implemented.

| ID | Kind | Modeled | Implemented | Populated | Verified | Backing | Queue |
|---|---|---|---|---|---|---|---|
| `node:ImageVersion` | node | specified | none | none | none | — | Q-016 |
| `node:Region` | node | specified | none | none | none | — | Q-016 |
| `node:EmbeddingRecord` | node | specified | none | none | none | — | Q-016 |
| `edge:HAS_IMAGE_VERSION` | edge | specified | none | none | none | — | Q-016 |
| `edge:HAS_REGION` | edge | specified | none | none | none | — | Q-016 |
| `edge:IDENTIFIED_AS` | edge | specified | none | none | none | — | Q-016 |
| `edge:HAS_EMBEDDING` | edge | specified | none | none | none | — | Q-016 |

#### `node:ImageVersion` — ImageVersion

Versioned pixels referenced by hash and dimensions; new bytes at the same URL make a new version.

- **Sources:** SPEC-v0.2.md §4, SPEC-v0.2.md §7

#### `node:Region` — Region

Explicit geometry in original pixel coordinates (boxes/polygons). Occurrence correspondence is a separate claim.

- **Sources:** SPEC-v0.2.md §7

#### `node:EmbeddingRecord` — EmbeddingRecord

Object/version, model-space ID, preprocessing, dimensions, metric, input hash and vector-store reference. Text and image spaces separate initially.

- **Sources:** SPEC-v0.2.md §4, SPEC-v0.2.md §7

#### `edge:HAS_IMAGE_VERSION` — HAS_IMAGE_VERSION

Artifact → versioned image pixels.

- **Edge:** node:Artifact → node:ImageVersion · cardinality 1:N; ImageVersion 1:N Region · qualification rights, image_hash
- **Sources:** SPEC-v0.2.md §5

#### `edge:HAS_REGION` — HAS_REGION

ImageVersion → Region with explicit geometry.

- **Edge:** node:ImageVersion → node:Region · cardinality 1:N · qualification geometry, transform
- **Sources:** SPEC-v0.2.md §5

#### `edge:IDENTIFIED_AS` — IDENTIFIED_AS

Region → proposed SignType via detection/classification claim; no implicit text alignment.

- **Edge:** node:Region → node:SignType · cardinality N:M top-k · qualification model_claim, score
- **Sources:** SPEC-v0.2.md §5

#### `edge:HAS_EMBEDDING` — HAS_EMBEDDING

Embeddable object → EmbeddingRecord.

- **Edge:** node:Region, node:TranslationSegment → node:EmbeddingRecord · cardinality 1:N per model space · qualification model_space
- **Sources:** SPEC-v0.2.md §5

<a id="domain-interfaces"></a>
### Graph storage, export & agent interfaces

Canonical edge table, node/edge views, portable Parquet export, CLI, FalkorDB projection plans, MCP and the sibling UI.

| ID | Kind | Modeled | Implemented | Populated | Verified | Backing | Queue |
|---|---|---|---|---|---|---|---|
| `table:edge` | table | specified | code | corpus | unit | table `edge` | Q-009 |
| `view:nodes` | view | documented | code | sample | unit | view `nodes` | Q-009 |
| `view:portable_edge` | view | documented | code | sample | unit | view `portable_edge` | Q-009 |
| `contract:portable-graph-export` | contract | documented | code | none | none | `cuneiform/persisted.py::export_graph`, `cuneiform/persisted.py::EXPORTER` | Q-009, Q-005 |
| `service:falkordb-projection` | service | specified | none | none | none | — | Q-009, Q-008 |
| `service:mcp-read-slice` | service | specified | none | none | none | — | Q-010 |
| `interface:cli` | interface | documented | code | none | unit | `cuneiform/cli.py::main` | Q-005, Q-020, Q-022, Q-023 |
| `interface:ui` | interface | documented | code | none | none | external `../cuneiform-ui`@`19c86b0` | Q-002, Q-006, Q-008, Q-023, Q-024 |

#### `table:edge` — edge (canonical edge store)

All adapter-written typed edges with attribution and JSON qualification. Endpoint types validated against model.EDGE_TYPES.

- **Identity:** identity('edge', kind, source_id, target_id).
- **Files:** `cuneiform/schema.sql`, `cuneiform/adapters.py`, `cuneiform/storage.py`
- **Evidence:** `tests/test_foundation.py::test_deterministic_ids_and_empty_unavailable_layers`
- **Corpus evidence:** `snapshot:c316e7cbbaf8a7fca7705f0efa5c4a07` edge=54359; `snapshot:edaab55c1a39cc65ad7c76e6d12547a7` edge=17395 (read by Q-007/Q-018 atlas worker (read-only storage.verify + manifest counts / exported edge Parquet), 2026-11-03)
- **Sources:** SPEC-v0.2.md §5

| Field | Type | Nullable | Key | Note |
|---|---|---|---|---|
| `id` | VARCHAR | False | PK | — |
| `source_id` | VARCHAR | False | — | — |
| `target_id` | VARCHAR | False | — | — |
| `kind` | VARCHAR | False | — | — |
| `source_record_id` | VARCHAR | False | — | — |
| `qualification` | JSON | False | — | — |

#### `view:nodes` — nodes

Typed node IDs (id, kind) over all 14 node tables; kind values equal model.NodeKind.

- **Files:** `cuneiform/schema.sql`
- **Evidence:** `tests/test_projections.py::test_trace_and_reverse_navigation`
- **Sources:** docs/REPRESENTATION-MAP.md

#### `view:portable_edge` — portable_edge

Canonical edges plus ATTRIBUTED_TO, CLAIM_SUBJECT and PLACED_IN_SEQUENCE; reversible traversal; never linguistic alignment.

- **Files:** `cuneiform/schema.sql`
- **Evidence:** `tests/test_projections.py::test_trace_and_reverse_navigation`
- **Sources:** docs/REPRESENTATION-MAP.md

#### `contract:portable-graph-export` — Portable graph export (Parquet)

COPY of nodes and portable_edge to Parquet with an import receipt (snapshot ID, manifest hash, raw hash, versions, counts, table hashes). Same IDs; no relabeling or merging. Exporter portable-graph-1.

- **Coverage:** Five export directories exist under derived/exports (listed by the atlas worker, not verified). The implementer reports 0 dangling edges and 93,831 nodes / 217,365 edges for the 300-record export.
- **Notes:** No unit test calls export_graph, so verified stays none. Export files are not rows; populated stays none.
- **Files:** `cuneiform/persisted.py`, `cuneiform/cli.py`
- **Sources:** docs/REPRESENTATION-MAP.md, CHECKPOINT.md

#### `service:falkordb-projection` — FalkorDB graph projection (isolated)

Disposable graph rebuilt from contract:portable-graph-export for traversals. Not implemented in this repository. The sibling UI (cuneiform-ui f68f340) runs its own isolated, authenticated FalkorDB behind bounded query templates, with no host ports, the Browser disabled and freeform Cypher refused. Per the integration review it is a separate consumer, not this projection; Q-009 stays open.

- **Notes:** The sibling instance is pilot-usable per reviews/pilot-integration-review-v0.1.md (5e51403b has no graph projection there yet; two demo graphs need a rebuild). Nothing here is implemented or verified.
- **Sources:** SPEC-v0.2.md §9, docs/REPRESENTATION-MAP.md, reviews/pilot-integration-review-v0.1.md

#### `service:mcp-read-slice` — MCP read slice

corpus_search, record_get, sequence_get, pattern_search, evidence_trace + append-only idempotent proposal_create. Typed schemas, resolved snapshot IDs, default 20 / max 100, cursors, bounded depth, typed errors.

- **Sources:** SPEC-v0.2.md §9

#### `interface:cli` — CLI (python -m cuneiform)

python -m cuneiform: demo, explore, fetch, acquire, receipts, corpus-inspect, corpus-select (--all-eligible), corpus-audit, corpus-accounting, corpus-import (--projections corpus|full, --memory), snapshots, publication-status, publication-recover, publication-adopt, publication-repair-ledger, publication-clean-stage, scope, manifest, lookup, query, parity, trace, trace-word, export-graph, catalog-link, cdli-import, oracc-inspect, oracc-import. Global --max-total-gib / --reserve-gib set an explicit task budget (defaults 5 / 10 GiB unchanged).

- **Notes:** Read verbs resolve snapshots through storage.store_path, which at 63f4221 returns a ledger-required StoreEntry and refuses symlinked or misplaced entries (exit 2, writer-tested). The publication-* verbs are the only recovery path; nothing is automatic (docs/PUBLICATION-PROTOCOL.md). Since 63f4221 they take --store {snapshots,cohorts}; publication-status adds store, symlinked_entries and a per-row id; corpus-audit JSON adds publication. Verb list read from cuneiform/cli.py at 63f4221 by the atlas worker (unchanged from 94af111).
- **Files:** `cuneiform/cli.py`
- **Evidence:** `tests/test_trace_and_admission.py::test_dry_run_reports_block_without_writes`
- **Sources:** README.md, docs/REPRESENTATION-MAP.md

#### `interface:ui` — Research UI (sibling cuneiform-ui)

Local read-only Cuneiform Workbench in the sibling repository cuneiform-ui at 19c86b0, pinned to backend 057a0b7 (Q-023 independently accepted by reviews/full-corpus-review-v0.1.md; pilot pin was 63f4221), with an isolated, authenticated FalkorDB behind bounded query templates. Default view: four declarative research questions (Q-024) answered over every match of the full eligible eBL snapshot; the motif query, graph, coverage and FalkorDB views remain. Not end-to-end SPEC.

- **Notes:** This checker resolves files under this repository only, so the UI is cited by commit. It consumes the read-only lookup/trace surface and these model IDs (Q-008). Every snapshot read goes through storage.verified(store_path(…), ledger='require'), and PublicationError states fail closed (typed state, 409 on a per-request refusal). The UI reads no cohort store, so v0.3 N2 does not apply. Open, not pilot blockers: the legacy-incident IDs ce127437 and 84971360 are served with the incident banner; 5e51403b has no FalkorDB projection yet; images, full corpus, MCP, temporal implementation and source rights stay open.
- **External:** `../cuneiform-ui` at `19c86b0` · Q-024 builder (UNVERIFIED, not independent): sibling commit 19c86b0 adds server/questions.py (GET /api/questions registry, POST /api/ask, /api/suggest, /api/tablets, /api/passage) reading table:posting, table:ngram, view:token_context, occurrence, line, artifact metadata and translation_segment with fixed parameterized SQL inside the existing bounded run (10 s, 512 MB, per-request integrity check, version binding, 409 when stale); no backend change, pin still 057a0b7. Live on 127.0.0.1:8740 (pid 26814): DIS ina 4,657 matches / 698 tablets / 4,530 lines; ina _ KUR 248 matches, 72 fillers; usage ina 44,334 with before 41,271 + line start 3,063; all 18 checked aggregates equal an independent lead/lag recomputation from canonical occurrence rows. UI suite 55 OK (0 skipped) with 24 isolation checks ok. Earlier (Q-023 writer, 4dcc416): 7/7 snapshots ready, index motifs with graph parity, parent byte trace verified; stale 409, foreign Host 421, Cypher 403; FalkorDB load of the full snapshot refused (5.3M nodes > 150k cap). · review: Accepted for the local read-only pilot by the integration review (reviews/pilot-integration-review-v0.1.md, committed in 2d746f7; Q-008), which also closed the Q-006 follow-ups (N-1 to N-7 and the re-pin to 63f4221). Earlier: re-review 05cfcd7b (sibling reviews/ui-review-v0.2.md) at ca4b514. Acceptance rule for later runs: 42 OK with 0 skipped, because low-disk fixture imports skip rather than fail (review §8, P1). The UI suite runs in the sibling, so it is not a verification_runs entry here (code_ref must resolve in this repository); verified stays none. Q-023 re-pin to 057a0b7 is writer-tested only; an independent reviewer must accept it before it counts as accepted.
- **Sources:** QUEUE.md, reviews/atlas-review-v0.1.md, reviews/pilot-integration-review-v0.1.md

### Edge registry (all edge entries)

| Edge | Source → Target | Cardinality | Qualification | Implemented | Populated |
|---|---|---|---|---|---|
| `edge:ATTRIBUTED_TO` | node:Artifact, node:SequenceVersion, node:Claim, node:TranslationSegment → node:SourceRecord | N:1 (each source object has exactly one) | — | code | sample |
| `edge:ON_ARTIFACT` | node:Witness → node:Artifact | N:1; exactly one per witness today (spec allows joined artifacts later) | — | code | corpus |
| `relation:passage.composition_id` | node:Passage → node:Composition | N:0..1 | — | schema | none |
| `edge:ATTESTS` | node:Witness → node:Passage | N:M, span-qualified | span, attribution | none | none |
| `edge:HAS_EDITION` | node:Artifact, node:Witness, node:Passage → node:Edition | N:M | coverage, attribution | none | none |
| `edge:HAS_TRANSLATION` | node:Artifact, node:Witness, node:Passage → node:Edition | N:M | coverage, language, search_scope | none | none |
| `edge:FOUND_AT` | node:Artifact → node:Place | N:M (competing attributions stay separate) | attribution, certainty, temporal_extent (role: excavation) | none | none |
| `edge:WRITTEN_AT` | node:Artifact → node:Place | N:M | attribution, basis, temporal_extent (role: production) | none | none |
| `edge:HELD_BY` | node:Artifact → node:Custodian | N:M over time | attribution, accession_number, temporal_extent (role: custody) | none | none |
| `edge:HAS_SEQUENCE` | node:Witness → node:SequenceVersion | 1:1..2 today (atf, signs); 1:N in general | — | code | corpus |
| `edge:HAS_LINE` | node:SequenceVersion → node:Line | 1:N | — | code | corpus |
| `edge:NEXT_LINE` | node:Line → node:Line | 0..1 : 0..1 (consecutive token lines) | continuity | code | corpus |
| `edge:HAS_OCCURRENCE` | node:Line → node:SignOccurrence | 1:N | — | code | corpus |
| `edge:NEXT` | node:SignOccurrence → node:SignOccurrence | 0..1 : 0..1; validated adjacent in same line | extent, boundary | code | corpus |
| `edge:MAPS_TO_SIGN` | node:SignOccurrence → node:SignType | N:1 (only kind='derived_sign' occurrences) | rule, sign_list_revision, alignment_to_atf | code | corpus |
| `edge:HAS_WORD` | node:SequenceVersion → node:WordToken | 1:N per source lemmatization sequence | line_label, order | code | corpus |
| `edge:HAS_SIGN` | node:WordToken → node:SignOccurrence | 1:N ordered | order, segmentation | schema | none |
| `edge:LEMMATIZED_AS` | node:WordToken → node:Lemma | N:1 per source analysis | epos, guideword, inst, norm, sig | code | corpus |
| `edge:HAS_SENSE` | node:Lemma → node:Sense | 1:N | attribution | code | corpus |
| `edge:IN_SENSE` | node:WordToken → node:Sense | N:1 (each lemmatized word points at exactly its own sense) | basis, inst, payload_pointer, sig | code | corpus |
| `edge:PLACED_IN_SEQUENCE` | node:TranslationSegment → node:SequenceVersion | N:0..1 | alignment | code | sample |
| `edge:TRANSLATES` | node:TranslationSegment → node:Passage | N:M | granularity | schema | none |
| `edge:CLAIM_SUBJECT` | node:Claim → node:Artifact | N:1 | — | code | sample |
| `edge:ALIGNED_WITH` | node:SignOccurrence → node:Region | N:M via alignment claim | claim_id, score, granularity | none | none |
| `edge:RESTORED_FROM` | node:SignOccurrence → node:Witness | N:M | basis, attribution | none | none |
| `edge:DEPENDS_ON` | node:Claim → node:Claim | N:M | kind (depends\|supports), attribution | none | none |
| `edge:REVIEWED_BY` | node:Claim → node:ReviewDecision | N:M append-only | expected_prior_revision | none | none |
| `edge:HAS_IMAGE_VERSION` | node:Artifact → node:ImageVersion | 1:N; ImageVersion 1:N Region | rights, image_hash | none | none |
| `edge:HAS_REGION` | node:ImageVersion → node:Region | 1:N | geometry, transform | none | none |
| `edge:IDENTIFIED_AS` | node:Region → node:SignType | N:M top-k | model_claim, score | none | none |
| `edge:HAS_EMBEDDING` | node:Region, node:TranslationSegment → node:EmbeddingRecord | 1:N per model space | model_space | none | none |
<!-- ATLAS:END -->
