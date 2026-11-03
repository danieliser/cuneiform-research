# QUEUE — cuneiform-research

The active work queue. Read it with [docs/MODEL-ATLAS.md](docs/MODEL-ATLAS.md) before any edit. The rules are in [AGENTS.md](AGENTS.md).

- **Updated:** 2026-11-03 ~10:27Z by the atlas sync worker (Q-007/Q-018), which the parent made queue writer for this synchronization. Earlier the same day: the Q-003 atlas worker wrote the queue, and the Q-004 reviewer corrected status lines (see `reviews/atlas-review-v0.1.md`).
- **Baseline:** commit `d6049e2` (schema `2`, parser `conservative-3`, projection `linked-1`, snapshot contract `manifest-3`). The atlas worker ran the in-memory suite on a clean export of `d6049e2`: 43 ran, OK, 5 disk tests skipped. The corpus worker reports all 43 passing with disk tests enabled (UNVERIFIED, not re-run here). Previous baseline `2ab620b`: the parent observed 31 tests passing with disk tests enabled (11.869s), which is historical evidence for that commit only.
- **Queue writer:** one writer at a time. The parent grants it. Workers report claims, evidence and blockers in their task thread or handoff, and the queue writer copies them here with attribution. A worker may edit only its own task block, and only when the parent grants it queue ownership.
- **Status words:** `TODO`, `READY`, `IN_PROGRESS`, `BLOCKED`, `IN_REVIEW`, `DONE`, `DEFERRED`. Add `UNVERIFIED` when a status came from someone else and nobody here has read it back.
- **Priority:** P0 = active or blocking, P1 = next, P2 = planned, P3 = deferred.
- **Consistency check:** `python3 scripts/check_model_atlas.py`. It checks task IDs, the summary table against the task blocks, dependencies, every backticked model ID, and that each `DONE` block cites a backticked commit SHA. It cannot check whether evidence is attributed correctly.

## Summary

| ID | P | Status | Title | Owner / thread | Depends |
|---|---|---|---|---|---|
| Q-000 | P0 | `DONE` | Baseline graph/ingestion foundation through linked-1 | Parent (prior workers) | — |
| Q-001 | P0 | `IN_REVIEW` | Corpus implementation worker (delivered `d6049e2`, review pending) | [corpus task 64821742](t3-thread://v2/7121f9cd-51d1-4941-95dd-f191951535d5/thread:delegated-task:command%3Amcp%3Afbac0162-ea66-4328-897b-ed1aece634c3%3Adelegate-task%3A64821742-a8c5-4d12-a3e1-58f13dc925f0) | Q-000 |
| Q-002 | P0 | `IN_PROGRESS` | UI worker, sibling `cuneiform-ui` (fix round active, UNVERIFIED) | [UI task 53dbd053](t3-thread://v2/7121f9cd-51d1-4941-95dd-f191951535d5/thread:delegated-task:command%3Amcp%3Afbac0162-ea66-4328-897b-ed1aece634c3%3Adelegate-task%3A53dbd053-4014-4ac7-9f7c-0089424cbbde); fixes by task b13b7efc | Q-000 |
| Q-003 | P0 | `IN_REVIEW` | Model atlas, queue, agent workflow and drift checker | Atlas documentation worker, task 8d17b311; fixes in Q-018 | Q-000 |
| Q-004 | P0 | `DONE` | Independent review of Q-003 (dispositions recorded, committed `fd54419`) | Review sub-agent (not the Q-003 builder) | Q-003 |
| Q-005 | P1 | `IN_PROGRESS` | Independent review of the corpus worker's output, incl. publication safeguards (UNVERIFIED) | Corpus reviewer (assigned by parent; not read back) | Q-001 |
| Q-006 | P1 | `IN_REVIEW` | Independent review of the UI worker's output (findings reported, fixes pending, UNVERIFIED) | UI review task bc133950 | Q-002 |
| Q-007 | P0 | `DONE` | Sync the atlas to Q-001 changes and make a coordinated commit (`fd54419`) | Atlas sync worker (Q-018), granted by the parent | Q-001, Q-003 |
| Q-008 | P1 | `TODO` | Corpus ↔ UI integration contract | Parent → assigned worker | Q-001, Q-002, Q-007 |
| Q-009 | P2 | `TODO` | FalkorDB graph projection (isolated, local) | Unassigned | Q-007, Q-008 |
| Q-010 | P2 | `TODO` | Initial MCP read slice | Unassigned | Q-007 |
| Q-011 | P2 | `IN_REVIEW` | ORACC source contract audit, then Word/Lemma/Sense adapter (ccpo pilot delivered) | Corpus worker (Q-001); review in Q-005 | Q-000, Q-001 |
| Q-012 | P2 | `IN_REVIEW` | eBL source-specific ingestion and 30-record feasibility audit (delivered) | Corpus worker (Q-001); review in Q-005 | Q-001 |
| Q-013 | P2 | `IN_REVIEW` | CDLI current export, pinned revision and terms (catalog JSON for 51 records) | Corpus worker (Q-001); review in Q-005 | Q-000, Q-001 |
| Q-014 | P1 | `DONE` | Temporal model decisions TD-1 to TD-7 (accepted by parent, recorded `fd54419`) | Parent; recorded by Q-018 | Q-003 |
| Q-015 | P2 | `READY` | Temporal implementation: raw date fields to attributed DateClaims | Unassigned | Q-014, Q-007 |
| Q-016 | P3 | `DEFERRED` | Images, regions, OCR and embeddings | — | Q-012 |
| Q-017 | P2 | `TODO` | Hypothesis groups and alternative-aware bounds | Unassigned | Q-007 |
| Q-018 | P0 | `IN_REVIEW` | Atlas review fixes (Q-004 F1–F11) and Q-007 sync implementation | Atlas review-fix and sync sub-agent | Q-004 |
| Q-019 | P1 | `TODO` | Independent re-check of the Q-018 checker and atlas changes | Unassigned reviewer (not the Q-018 builder) | Q-018 |

## Q-000 — Baseline graph/ingestion foundation through linked-1

- **Status:** `DONE`
- **Priority:** P0
- **Owner / thread:** Parent; earlier implementation workers.
- **Depends on:** —
- **Scope:** Commits `54470be`, `3ead790`, `9eab086` and `2ab620b`: the foundation, including `node:SignOccurrence`, `table:ngram`, `view:portable_edge` and `artifact:snapshot-manifest`.
- **Acceptance evidence:** CHECKPOINT.md records the passing suites and the review fixes. On 2026-11-03 the parent observed 31 tests passing at `2ab620b` with disk tests enabled (11.869s). The Q-003 atlas worker re-ran the in-memory suite (30 passed, 1 skipped), and the Q-018 worker did the same on a clean export (31 ran, OK, skipped=1, 12.049s).
- **Next step / blockers:** None. Frozen specs and reviews stay unchanged.

## Q-001 — Corpus implementation worker

- **Status:** `IN_REVIEW`: delivered at `d6049e2` and stopped writing (parent, 2026-11-03). Independent review is Q-005.
- **Priority:** P0
- **Owner / thread:** Corpus worker, task `64821742`, [thread](t3-thread://v2/7121f9cd-51d1-4941-95dd-f191951535d5/thread:delegated-task:command%3Amcp%3Afbac0162-ea66-4328-897b-ed1aece634c3%3Adelegate-task%3A64821742-a8c5-4d12-a3e1-58f13dc925f0)
- **Depends on:** Q-000
- **Scope:** Commit `d6049e2` ("Persist reproducible eBL/ORACC/CDLI text-corpus pilot with immutable publication"): acquisition receipts, streaming eBL inspection, deterministic cohorts, chunked cohort import, ORACC ccpo words/lemmas/senses with `edge:IN_SENSE`, CDLI catalog JSON, publication ledger (`artifact:publication-ledger`), manifest contract `manifest-3`, snapshot scope, parent-file traces, portable Parquet export (`contract:portable-graph-export`). Details in CHECKPOINT.md and docs/SOURCE-AUDIT.md.
- **Acceptance evidence:**
  - Read back by the atlas worker: the commit and its file list; the in-memory suite on a clean export of `d6049e2` (43 ran, OK, skipped=5, 14.340s); `storage.verify()` passing on all five snapshots, which re-hashes every payload file; manifest table counts and edge-kind counts from each snapshot's edge Parquet; the five ledger rows. All reads were read-only.
  - Reported by the corpus worker, UNVERIFIED: all 43 tests pass with `CUNEIFORM_RUN_DISK_TESTS=1` (15.4s), including the disk-gated publication-ledger, cohort and persisted-projection tests. Acquisition, timing and parity measurements in CHECKPOINT.md.
- **Incident (same-ID rebuild):** At ~09:44Z the worker published `snapshot:ce127437…` and `snapshot:84971360…`, deleted both at ~09:46Z and rebuilt them under the same IDs. Readers could see different bytes under one ID, which violates immutability. First-version bytes are lost. The UI reviewer's size and mtime observations are the surviving evidence. The record is `~/.local/share/cuneiform-research/evidence/incident-2026-11-03-same-id-rebuild.json`. Remediation (ledger, read-only trees, `manifest-3` identity) is tested only by the worker's own disk run. The atlas cites only the three snapshots that were published once (`c316e7cb`, `edaab55c`, `fc7c3504`) as corpus evidence.
- **Next step / blockers:** Q-005 review. No further rebuilds of existing IDs.

## Q-002 — UI worker (sibling cuneiform-ui)

- **Status:** `IN_PROGRESS` (UNVERIFIED: the parent reports UI fix worker b13b7efc active; not read back beyond the sibling's git status). The earlier delivery at `567ea14` was reviewed in Q-006.
- **Priority:** P0
- **Owner / thread:** UI worker, task `53dbd053`, [thread](t3-thread://v2/7121f9cd-51d1-4941-95dd-f191951535d5/thread:delegated-task:command%3Amcp%3Afbac0162-ea66-4328-897b-ed1aece634c3%3Adelegate-task%3A53dbd053-4014-4ac7-9f7c-0089424cbbde); fix round by task b13b7efc.
- **Depends on:** Q-000
- **Scope:** Sibling repository `/Users/danieliser/Projects/Fun/cuneiform-ui`. HEAD is still `567ea14`. At ~10:21Z its working tree had uncommitted changes in `bin/cuneiform-ui`, `server/` and `tests/` (git status, read only). The parent and the Q-004 reviewer reported HTTP 200 on `127.0.0.1:8740` and `:23001`; not re-probed here. Atlas entries: `interface:ui` (implemented in the sibling, verified none) and `service:falkordb-projection`.
- **Acceptance evidence:** A UI build or run plus a screenshot that uses the read-only surfaces (`query:lookup`, `query:trace`). Planned layers must not appear as loaded data.
- **Next step / blockers:** Fix-round handoff with its own file list and commit, then the Q-006 re-check.

## Q-003 — Model atlas, queue, agent workflow and drift checker

- **Status:** `IN_REVIEW`
- **Priority:** P0
- **Owner / thread:** Atlas documentation worker, task `8d17b311`. Review findings were fixed under Q-018.
- **Depends on:** Q-000
- **Scope:** `docs/model-atlas.json` (canonical), `docs/MODEL-ATLAS.md`, `docs/model-atlas.html`, `scripts/check_model_atlas.py`, `QUEUE.md`, `AGENTS.md` and `CLAUDE.md`.
- **Acceptance evidence:** The original handoff passed the checker, `--runtime` and an 11/11 self-test at `2ab620b`. Current evidence is in Q-018.
- **Next step / blockers:** Independent re-check of the fixed checker and atlas (Q-019).

## Q-004 — Independent review of Q-003

- **Status:** `DONE`: every finding has a disposition below; the review file and the fixes were committed in `fd54419`. Re-check of the fixes is Q-019.
- **Priority:** P0
- **Owner / thread:** Review sub-agent, not the Q-003 builder.
- **Depends on:** Q-003
- **Scope:** Compare the atlas with the code; check status honesty, temporal precision, checker blind spots and the HTML.
- **Acceptance evidence:** `reviews/atlas-review-v0.1.md` (11 findings), unchanged. Dispositions, all implemented in Q-018 unless noted:
  - **F1 fixed.** Manifest keys come from every signed dict that carries `snapshot_id`. `**` spreads, `dict(meta, k=...)`, subscript keys and function parameters are resolved through all call sites, and per-source optional keys are modeled (`presence`, `sources`). `storage.verify()`'s required keys are cross-checked against every path. Unresolvable forms fail the check, unless a fingerprinted `static_contracts` entry exists. No true keys were removed: the atlas now lists 26 keys, 4 of them optional per source.
  - **F2 fixed.** Rights keys include `RIGHTS[<const>] = ...` from any module that imports the registry. Registry mutations the analyzer cannot follow fail the check. Every source kind the code dispatches on (`ebl-cohort`, `oracc-selection`, `cdli-selection` and the original four) needs a registry entry or a declared per-snapshot rights source.
  - **F3 fixed.** `--runtime` drives the real adapters for `ebl-cohort` (`ingest_record`) and `oracc-selection` (`oracc.map_selection` on `fixtures/oracc-synthetic.json`), one database per input. Source kinds with no input (`ebl-atf`, `oracc`, `cdli-selection`) need a written reason in `runtime_unexercised`, or the static check fails.
  - **F4 fixed.** `populated: corpus` needs `corpus_evidence` (snapshot ID, table or edge kind, count, observer). It is allowed only for tables and `model.EDGE_TYPES` edges. `--runtime` re-reads the manifest counts or the exported edge Parquet and fails on any mismatch or unreadable snapshot. A missing-samples run now fails `sample` claims instead of passing them.
  - **F5 fixed.** `verification_runs` records who observed each run, at which commit, and whether it was read back. `verified: disk` must name its runs. Runs at another commit do not support current claims. The parent's 2ab620b disk run is kept as attributed history. The current disk level rests on the corpus worker's own run and renders as `disk (UNVERIFIED)`.
  - **F6 fixed.** Self-test targets are chosen at run time from the atlas and code, and edits use regex or AST positions instead of fixed text. A crashing case reports FAIL. `--git-ref WORKTREE` tests uncommitted code against a baseline error set. There are 34 cases, including new ones for F1, F2, F4, F5 and F11.
  - **F7 fixed.** `interface:ui` is implemented in the sibling (cited as `../cuneiform-ui` at `567ea14`, which the checker resolves), with verified none. `service:falkordb-projection` and Q-009 describe the sibling's separate FalkorDB instance. No approval blocker was removed without a parent decision.
  - **F8 fixed.** `value:TemporalExtent` precision adds `as-printed` (the default for printed ranges) and `unknown`. `node:DateClaim` basis adds `catalog-period-gloss`. `value:source-independence` says a repeated gloss is one assertion.
  - **F9 accepted.** The parent owns TD-1 to TD-7 as routine conservative defaults (Q-014), with an explicit trigger for escalating to the user.
  - **F10 fixed.** `Spool.detached('<table>')` and `Spool('<table>')` count as literal writes.
  - **F11 partly fixed.** The checker now requires a backticked commit SHA in every `DONE` block. Limitation: a backticked hex task ID also satisfies it. AGENTS.md now says which rules are enforced only by documentation.
- **Next step / blockers:** None. Q-019 re-checks the fixes.

## Q-005 — Independent review of the corpus worker's output

- **Status:** `IN_PROGRESS` (UNVERIFIED: an untracked `reviews/corpus-pilot-review-v0.1.md` appeared in this checkout at ~10:25Z; not read here, owner not read back).
- **Priority:** P1
- **Owner / thread:** Corpus reviewer assigned by the parent, not the corpus worker.
- **Depends on:** Q-001
- **Scope:** The `d6049e2` diff and its tests, including a re-run with disk tests enabled under the storage guard. The publication safeguards after the same-ID incident: ledger refusal after deletion, read-only trees, `manifest-3` identity, and the backfilled ledger rows. Rights statements: the ORACC CC0 statement is a code literal quoting the catalogue license field, and the CDLI terms text. Cohort determinism and representativeness claims. The atlas claims made by Q-007, especially the 30 `corpus` entries and the `disk (UNVERIFIED)` levels.
- **Acceptance evidence:** A new review file under `reviews/` with findings and dispositions, and the suite re-run by the reviewer. When the disk run is read back, it is recorded in `verification_runs` with `read_back: true`.
- **Next step / blockers:** Review handoff with its file list. The atlas worker did not stage or commit the review file.

## Q-006 — Independent review of the UI worker's output

- **Status:** `IN_REVIEW` (UNVERIFIED: findings exist but were not read in full here). Review task `bc133950` reported findings. F-4, the same-ID snapshot rebuild, is cited in CHECKPOINT.md and the incident record, and the sibling has an untracked `reviews/ui-review-v0.1.md`. Fixes are in progress under Q-002.
- **Priority:** P1
- **Owner / thread:** UI review task `bc133950`.
- **Depends on:** Q-002
- **Scope:** The UI repository, its use of the read-only surfaces, and how it labels unavailable or planned layers.
- **Acceptance evidence:** Review findings and a screenshot or run log, plus a re-check of the b13b7efc fixes.
- **Next step / blockers:** Q-002 fix handoff.

## Q-007 — Sync the atlas to Q-001 changes and make a coordinated commit

- **Status:** `DONE`: committed in `fd54419`.
- **Priority:** P0
- **Owner / thread:** Atlas sync worker (Q-018), granted by the parent after Q-001 stopped writing at `d6049e2`.
- **Depends on:** Q-001, Q-003
- **Scope:** Atlas revision 2 at baseline `d6049e2`: `node:WordToken`, `node:Lemma`, `node:Sense`, `edge:HAS_WORD`, `edge:LEMMATIZED_AS` and `edge:HAS_SENSE` raised to code with qualification keys from code; new `edge:IN_SENSE`; 26 manifest keys, 4 optional per source; rights for `ebl-cohort`, plus per-snapshot rights for `oracc-selection` and `cdli-selection`; new `artifact:publication-ledger` (with the incident), `artifact:acquisition-receipt`, `artifact:cohort-manifest`, `artifact:selection-manifest` and `value:snapshot-scope`; `contract:portable-graph-export` implemented (no test, so verified none); `query:lookup`, `query:trace` and `interface:cli` updated; 30 entries raised to `corpus` with evidence from the three snapshots that were published once; verification runs recorded. The corpus worker's files were not edited.
- **Acceptance evidence:** At `d6049e2`, with the code identical to HEAD: `python3 scripts/check_model_atlas.py` gives `model atlas: OK`; `<venv>/python -B scripts/check_model_atlas.py --runtime` gives `model atlas: OK (runtime population checked)`; `python3 scripts/check_model_atlas.py --self-test` gives 34/34; the in-memory suite gives 43 ran, OK, skipped=5. `gitleaks dir` over the eight committed files: no leaks found. Commit `fd54419` contains only atlas, checker, queue, AGENTS/CLAUDE and the Q-004 review file.
- **Next step / blockers:** None. The atlas claims are part of the Q-005 and Q-019 reviews. Future contract changes follow AGENTS.md.

## Q-008 — Corpus ↔ UI integration contract

- **Status:** `TODO`
- **Priority:** P1
- **Owner / thread:** Parent assigns a worker.
- **Depends on:** Q-001, Q-002, Q-007
- **Scope:** Define the read-only API or export the UI consumes, based on `query:lookup`, `query:trace`, `value:snapshot-scope`, `view:portable_edge` and `contract:portable-graph-export`, with model IDs carried through. Unavailable layers render as unavailable, never as zero. Decide whether the UI's FalkorDB instance is the `service:falkordb-projection` or a separate consumer.
- **Acceptance evidence:** A UI exercise against a real snapshot. `interface:ui` is updated in the atlas.
- **Next step / blockers:** Q-001 review (Q-005) and the Q-002 fix round.

## Q-009 — FalkorDB graph projection (isolated, local)

- **Status:** `TODO`
- **Priority:** P2
- **Owner / thread:** Unassigned.
- **Depends on:** Q-007, Q-008
- **Scope:** Load `contract:portable-graph-export` (implemented in `d6049e2`, untested) into an isolated FalkorDB as `service:falkordb-projection`. No CompanyKit or shared-service changes.
- **Acceptance evidence:** Node and edge counts match between DuckDB and FalkorDB, a traversal returns the same results as the SQL views, and the graph can be discarded and rebuilt from the receipt. A unit test for `export_graph`.
- **Next step / blockers:** An isolated FalkorDB already runs for the sibling UI (`567ea14`, Browser on `:23001`). Q-008 decides whether Q-009 reuses it. Starting any additional container still needs parent approval.

## Q-010 — Initial MCP read slice

- **Status:** `TODO`
- **Priority:** P2
- **Owner / thread:** Unassigned.
- **Depends on:** Q-007
- **Scope:** `service:mcp-read-slice` with five read tools over `query:lookup`, `query:trace` and `query:motif`, plus a local, append-only `proposal_create` (see `node:ReviewDecision`). Pin the SDK version when implementing.
- **Acceptance evidence:** A real MCP client discovers the tools and runs bounded queries. Typed errors and pagination are exercised.
- **Next step / blockers:** Pick the SDK and transport.

## Q-011 — ORACC source contract audit, then Word/Lemma/Sense adapter

- **Status:** `IN_REVIEW`: delivered by Q-001 at `d6049e2`; independent review in Q-005.
- **Priority:** P2
- **Owner / thread:** Corpus worker (Q-001).
- **Depends on:** Q-000, Q-001
- **Scope:** ORACC ccpo official JSON export (`receipt:0ca4ede9…`), 51 texts selected by exact P-number overlap → `snapshot:edaab55c…`: `node:WordToken` 6,888, `node:Lemma` 1,122, `node:Sense` 1,317, `edge:LEMMATIZED_AS` and `edge:IN_SENSE` 4,544 each (counts read back by the atlas worker). ORACC JSON has no translation text, so no `node:TranslationSegment` is created. Graphemes are not mapped to `node:SignOccurrence`. `edge:HAS_SIGN` and `edge:TRANSLATES` stay unwritten.
- **Acceptance evidence:** Receipt and field mapping in docs/SOURCE-AUDIT.md; unit test `test_words_lemmas_senses_and_claims_without_invented_translation` (passes in the atlas worker's run); atlas statuses raised in Q-007.
- **Next step / blockers:** Q-005. Only one ORACC project is imported. The CC0 statement is recorded, not legally reviewed.

## Q-012 — eBL source-specific ingestion and 30-record feasibility audit

- **Status:** `IN_REVIEW`: delivered by Q-001 at `d6049e2`; independent review in Q-005.
- **Priority:** P2
- **Owner / thread:** Corpus worker (Q-001).
- **Depends on:** Q-001
- **Scope:** The frozen eBL `fragments.json` envelope was verified (a top-level array, not the README wrapper). There is a whole-file inspection, a 30-record audit and cohorts of 30, 300 and 51 (docs/SOURCE-AUDIT.md). `node:Composition`, `node:Passage`, `edge:ATTESTS` and `node:Edition` remain unpopulated, because composition membership is not inferred.
- **Acceptance evidence:** Rights and coverage ledger, receipts and exclusion accounting in SOURCE-AUDIT; atlas population updated in Q-007.
- **Next step / blockers:** Q-005. The eBL rights conflict is unresolved (`concept:rights-ledger`). A full-corpus import (about 11 GB per snapshot at the measured ratio) exceeds the 5 GiB budget and needs a storage-layout decision.

## Q-013 — CDLI current export, pinned revision and terms

- **Status:** `IN_REVIEW`: partly delivered by Q-001 at `d6049e2`; independent review in Q-005.
- **Priority:** P2
- **Owner / thread:** Corpus worker (Q-001).
- **Depends on:** Q-000, Q-001
- **Scope:** cdli.earth per-artifact JSON for the 51 overlap P-numbers, with 51 receipts → `snapshot:fc7c3504…` (51 artifacts, 334 attributed claims, no text). Terms of Use recorded. Raw temporal and place fields (`facet:cdli-temporal-fields`) stay raw.
- **Acceptance evidence:** Receipts and terms in docs/SOURCE-AUDIT.md; unit test `test_catalog_only_claims_and_rejection`.
- **Next step / blockers:** Q-005. Inscriptions were not fetched. Per-record receipts pin the acquired bytes, but not a CDLI release.

## Q-014 — Temporal model decisions TD-1 to TD-7

- **Status:** `DONE`: accepted by the parent, recorded in the atlas and committed in `fd54419`.
- **Priority:** P1
- **Owner / thread:** Parent (routine engineering defaults); recorded by Q-018.
- **Depends on:** Q-003
- **Scope:** `decision:TD-1` through `decision:TD-7`, `value:TemporalExtent`, `node:DateClaim`, `node:ChronologyScheme`, `value:temporal-role`, `node:Place` and `node:Custodian`.
- **Decisions (accepted 2026-11-03, parent):**
  - TD-1: astronomical year integers (1 BCE = 0), source era convention kept, raw string always kept.
  - TD-2: explicit bounds and precision. Precision defaults to `as-printed` for printed ranges, or `unknown`. `ca.` sets a flag without widening, `ff.` opens the end, and there are no midpoints or default days or months.
  - TD-3: only ranges the source prints become extents (basis `catalog-period-gloss`). No default chronology.
  - TD-4: native calendar values only. No conversion authority is adopted, so no conversions are made.
  - TD-5: sentinels and empty strings mean unknown. System dates parse only under a declared per-source format.
  - TD-6: the snapshot is the knowledge-time boundary. Processing time stays in manifests and receipts.
  - TD-7: reuse the claim table with typed details. Competing datings stay separate, and no winner is chosen.
  - Escalate to the user if anyone proposes a default `node:ChronologyScheme`, a calendar-conversion authority, or a departure from these choices. Unresolved historical chronology stays source-qualified and is never guessed.
- **Acceptance evidence:** Each `decision:` entry carries a `decision_record` and is `modeled: documented`. The value and claim shapes stay `proposed` and `implemented: none`. No temporal schema exists, and none is claimed.
- **Next step / blockers:** None. Q-015 may start.

## Q-015 — Temporal implementation: raw date fields to attributed DateClaims

- **Status:** `READY`
- **Priority:** P2
- **Owner / thread:** Unassigned.
- **Depends on:** Q-014, Q-007
- **Scope:** Turn the CDLI and eBL raw temporal fields (`facet:cdli-temporal-fields`, `facet:ebl-temporal-fields`) into source-attributed claims under the Q-014 decisions. Sentinels and ambiguous values stay raw. Competing datings stay separate claims.
- **Acceptance evidence:** Tests for sentinels, open bounds such as `2015ff.`, `as-printed` approximate BC ranges, catalog period glosses, and competing claims. Atlas statuses and the runtime check are updated.
- **Next step / blockers:** Assign a worker. Q-014 and Q-007 landed in `fd54419`.

## Q-016 — Images, regions, OCR and embeddings

- **Status:** `DEFERRED`
- **Priority:** P3
- **Owner / thread:** —
- **Depends on:** Q-012
- **Scope:** `node:ImageVersion`, `node:Region`, `node:EmbeddingRecord`, `edge:HAS_IMAGE_VERSION`, `edge:HAS_REGION`, `edge:IDENTIFIED_AS`, `edge:HAS_EMBEDDING` and `edge:ALIGNED_WITH`.
- **Acceptance evidence:** None until the work is un-deferred.
- **Next step / blockers:** The user explicitly deferred this work. No image downloads, OCR weights or embeddings.

## Q-017 — Hypothesis groups and alternative-aware bounds

- **Status:** `TODO`
- **Priority:** P2
- **Owner / thread:** Unassigned.
- **Depends on:** Q-007
- **Scope:** `concept:hypothesis-group`, `concept:compatible-bounds`, `edge:RESTORED_FROM` and `edge:DEPENDS_ON`. Today alternatives are opaque blocking positions (`value:uncertainty-fields`).
- **Acceptance evidence:** The alternative fixtures listed in SPEC §10 pass, and bounds that cannot be resolved are labeled as unresolved.
- **Next step / blockers:** Needs source grammar support for alternatives (related to Q-012).

## Q-018 — Atlas review fixes (Q-004 F1–F11) and Q-007 sync implementation

- **Status:** `IN_REVIEW`: delivered in `fd54419`; independent re-check is Q-019.
- **Priority:** P0
- **Owner / thread:** Atlas review-fix and sync sub-agent, delegated by the parent (the worker cannot see its own task ID). Builder of these changes, so it does not review them.
- **Depends on:** Q-004
- **Scope:** Owned files only: `scripts/check_model_atlas.py`, `docs/model-atlas.json`, `docs/MODEL-ATLAS.md`, `docs/model-atlas.html`, `QUEUE.md` and `AGENTS.md`. It also commits the unchanged `CLAUDE.md` and `reviews/atlas-review-v0.1.md`. No backend, test, fixture or UI files were edited.
- **Acceptance evidence:**
  - Before the corpus commit, only the original checker ran at `2ab620b` (`OK`; 10 live-tree drift errors, as the review lists). The new checker was first run after HEAD had moved to `d6049e2`. Its first run, before the sync, reported 70 errors: the expected drift (word/lemma/sense layers, `edge:IN_SENSE`, 8 missing manifest keys, the `ebl-cohort` rights key, two undeclared per-snapshot rights sources, five source kinds without runtime coverage) plus the verification-run records the atlas did not have yet. It reported no false "extra" manifest keys.
  - At `d6049e2`: `check` OK; `--runtime` OK (drives `ebl`, `cdli`, `ebl-cohort` and `oracc-selection`, and re-reads 30 corpus citations); `--self-test` 34/34. A one-off negative run with a wrong `edge:IN_SENSE` count and an unreadable snapshot ID failed as expected (3 errors). The viewer was rendered in headless Chrome from the local file and shows the UNVERIFIED labels, decision records and corpus evidence.
  - In-memory suite: 31 ran, OK, skipped=1 at `2ab620b`; 43 ran, OK, skipped=5 at `d6049e2` (both from clean exports).
- **Next step / blockers:** Q-019.

## Q-019 — Independent re-check of the Q-018 checker and atlas changes

- **Status:** `TODO`
- **Priority:** P1
- **Owner / thread:** Unassigned reviewer, not the Q-018 builder.
- **Depends on:** Q-018
- **Scope:** Try to make the checker pass something it should fail: manifest construction forms, rights registry forms, source kinds, corpus evidence and verification runs. Check that the 30 `corpus` claims, the `disk (UNVERIFIED)` labels, the F7 UI wording and the Q-014 decision records are honest.
- **Acceptance evidence:** A new review file under `reviews/` with dispositions.
- **Next step / blockers:** Assign a reviewer.
