# Implementation handoff

2026-11-02. Sole implementation writer completed the authorized graph/ingestion foundation through the in-memory milestone. Parent owns independent review and any further delivery. No running worker, scheduled continuation, remote or deployed service remains.

## Delivered

- Typed canonical SQL tables, schema/parser and typed edge registry; DuckDB node/NEXT/token graph projections.
- Conservative eBL JSON/ATF adapter, separate source-derived sign sequences, source trace and metadata aliases; CDLI catalog adapter; ORACC inspection-only with import refusal.
- Gap-safe exact/wildcard/bounded-position queries, count denominators, source evidence labels and strict physical evidence filter.
- Implemented persistent immutable snapshot manifests/raw/Parquet/DuckDB path, exact URL allowlisting, byte/reserve guards, dry-run estimates and schema-version check.
- External runtime configuration; synthetic fixtures and runnable tests; source-by-source [ingestion design and rights ledger](docs/INGESTION-DESIGN.md).

## Executed evidence

Commands were run from `/Users/danieliser/Projects/Fun/cuneiform-research` with `/Users/danieliser/.local/share/cuneiform-research/venv/bin/python` (Python 3.13, DuckDB 1.4.3).

Final default suite:

```
python -m unittest discover -s tests -v
Ran 15 tests in 4.685s
OK (skipped=1)
```

**14 passed; one disk-backed integration test skipped.** The actual eBL sample test ran and passed, rather than skipping. The machine-specific absolute evidence directory is optional on other machines. Test output: `~/.local/share/cuneiform-research/evidence/tests-final.txt`.

Verified in-memory behavior: deterministic IDs; source UTF-8 locator round-trip for every synthetic and frozen-example position; explicit per-record rejection accounting; duplicate aliases without merges; unavailable layers empty; translation granularity unresolved; source-derived sign attribution; exact graph/array count parity for lengths 2–5; wildcard and bounded gaps; strict exclusions do not rewire NEXT; allowlist/input-size/reserve refusal; dry-run reports block without creating output.

The first test run exposed a byte-offset increment bug; corrected, then all-position round-trip tests passed. Initial graph validation used an unnecessary wide union join exceeding the test's 64 MiB memory budget; replaced with bounded endpoint/type validation over fetched node IDs and edges. No disk spilling was enabled. A manually miscounted synthetic wildcard expectation was corrected from 10 to 11 after inspecting the two matches in the first line and remaining fixture positions. No linguistic result was claimed.

Pyright on `cuneiform/storage.py`: **0 diagnostics** after fixing one optional count-row typing issue. This is a file-specific diagnostic result, not a project-wide typecheck claim.

Actual CLI/API exercises:

| Input | Actual result |
|---|---|
| Synthetic eBL fixture | `A B C`: graph=6, array=6; `A ? C`: 11; `A C`: 0; 2 rejected records |
| Frozen eBL README embedded example | 1 record, 1 artifact, 1 witness, 2 sequences, 34 lines, 541 represented positions, 96 sign types, 9 translations, 1 alias claim, 106 exclusions, 1,433 edges; graph/array `ABZ215 ABZ13` = 3 |
| Live eBL K.1 | 1 metadata record/artifact and CDLI alias; no supplied ATF, no invented witness or tokens |
| CDLI first three complete CSV rows | 3 separate artifacts and 3 museum-label alias claims; no text/witness layers |

Actual sample bytes examined: complete frozen README 12,355 bytes; complete live eBL K.1 JSON 11,108 bytes; CDLI CSV prefix 16,384 bytes; eBL ATF specification prefix 16,384 bytes; small official GitHub directory inventories and official eBL API example. No full fragments.json, project ZIP, bulk catalog, images or weights. Small raw evidence stays external, not committed. `evidence/source-receipts.json` records URLs, SHA256, byte scope, derived sample extraction and failed ORACC requests. Full demo outputs are alongside it.

## Disk accounting and blocked checks

Initial filesystem available: **4,701,548 KiB (4.484 GiB)**. The environment installed DuckDB's 13.7 MB wheel without pip cache; task runtime footprint is approximately **50 MiB**.

First attempted persisted fixture import returned exactly:

```
error: free-space reserve would be violated
```

Then `df` showed **2,524,352 KiB (2.407 GiB)**, later **1,939,492 KiB (1.850 GiB)**, while this task's runtime remained about 50 MiB. No snapshot was created; no unrelated files were removed. Parent instructed continuation in memory with at most 10 MiB further small code/docs/checkpoint writes and allowed disk verification to remain blocked.

Latest pre-commit measurement: runtime **50,984 KiB (49.79 MiB)**; project **328 KiB** before this checkpoint/git metadata. Filesystem had rebounded to **3,482,996 KiB (3.322 GiB)**. That rebound does not mean disk checks ran: final writes remained within the parent's 10 MiB allowance. The disk integration test requires 64 MiB admission headroom and can create multiple snapshot copies, so it was not enabled. No further dependencies or downloads were installed/acquired after the parent's storage steering. Total task-owned files remain far below the 500 MiB cap; unrelated volume usage is not attributed to this task.

**Not runtime-verified:** disk-backed import success, persistent idempotence, byte-change snapshot creation, relocation, Parquet readback and tamper detection. Code and gated tests exist for these; do not call them passed. Initial frozen/source predecessors remain unchanged (SHA256 checked again before handoff).

## Review and exact resume commands

Try the working in-memory slice now:

```sh
cd /Users/danieliser/Projects/Fun/cuneiform-research
PY=/Users/danieliser/.local/share/cuneiform-research/venv/bin/python
$PY -m cuneiform demo ebl fixtures/ebl-synthetic.json A B C
$PY -m unittest discover -s tests -v
$PY -m cuneiform import ebl fixtures/ebl-synthetic.json --dry-run --source-url synthetic:fixture
```

After parent review and an approved storage/write budget, with the 3 GiB reserve intact:

```sh
CUNEIFORM_RUN_DISK_TESTS=1 $PY -m unittest discover -s tests -v
$PY -m cuneiform import ebl fixtures/ebl-synthetic.json --source-url synthetic:fixture
# Copy the emitted snapshot ID into SNAP.
$PY -m cuneiform manifest "$SNAP"
$PY -m cuneiform query "$SNAP" A B C
$PY -m cuneiform query "$SNAP" A B C --max-skip 2
# Copy a returned occurrence ID into OCC.
$PY -m cuneiform trace "$SNAP" "$OCC"
```

Do not enable the larger disk test merely because a transient `df` reading improves under the final small-write allowance. The test still enforces reserve, never overrides it, and removes only its own temporary directory under external runtime storage. A configurable external root exists, but no unapproved volume or deployment target is invented.

## Remaining decisions and limitations

1. Parent independent code/model review; this is the writer's evidence, not independent approval.
2. Approve durable storage and disk verification budget. No full snapshot/corpus acquisition until separately scoped.
3. Resolve actual eBL grant; verify ORACC selected-project formats/terms and current CDLI preferred export/license. Public endpoint access is not a reuse grant.
4. Full eBL grammar and sign-list provenance/alignment, ORACC Word/Lemma/Sense bridge, and source-aligned translations remain incomplete. Current opaque components block paths; they are not asserted individual signs.
5. Alternative compatibility/global bounds, cross-snapshot deduplication, composition/passage membership, lemma motif queries and complete SPEC-v0.2/MCP work remain future phases. Translation spans are explicitly unresolved, not word-level English evidence.

No automatic continuation is promised after handoff. Parent can review files and choose the next authorized milestone without redoing the small source audit.

## Local repository and secret scan

Initialized Git only inside `cuneiform-research`, with no remote. Initial Gitleaks scan found one false positive at frozen `SPEC-v0.1.md:56`: ordinary editorial-notation prose. Inspected the line; preserved the predecessor and recorded only that exact rule/path/line fingerprint in `.gitleaksignore`. The final scan passed after that narrow exception (zero remaining findings). No broad scanner suppression or external publication is involved.


## Parent review fixes and validation (2026-11-02)

Supersedes the earlier disk-verification limitation: available space recovered above the reserve, and parent admitted the small fixture integration run under the original 500 MiB cap. All 19 tests passed with CUNEIFORM_RUN_DISK_TESTS=1 (4.936s); no bulk downloads. The test removes only its own fixture workspace.

Fixed all four review findings: lines containing unsupported removal/gloss span delimiters conservatively block every token; extent-qualified translations are retained with unresolved alignment and unsupported translation syntax is accounted; manifest verification requires all typed payloads, binds identity and parser/schema, checks raw length/hash and metadata digest; input is read once with a cap+1 bounded read for inspection, hash and import. Parser revision is conservative-2. Manifest digest detects inconsistent changes, not authenticated malicious coordinated rewrites; independent trusted receipts remain necessary for authenticity. Snapshot verification accepts relocation but import reuse and ID resolution enforce the requested snapshot ID.

Regression tests cover each review finding. Disk tests additionally verified import/reuse, changed bytes, relocation, Parquet and tamper rejection. An initial relocation mismatch exposed a path-dependent check, corrected by passing expected snapshot identity separately; a tamper error-label mismatch was corrected. Final suite green. This remains a narrow structural prototype: ORACC mappings, full ATF grammar, 30-record audit, lemma layer population, MCP and complete SPEC remain unfinished. Images/bulk ingestion stay deferred; long-term storage undecided.

## Linked projection slice — implementation handoff (2026-11-02)

Implemented locally from clean `3ead790de75a61140cd254edcf67fed1c02ccac8`, sole writer, no subagents. Parent independent review remains pending. Frozen specs/reviews are unchanged. No remote/publish, downloads, dependency installs, corpus writes, images, embeddings, UI or service work occurred.

Delivered schema **2**, parser **conservative-3**, projection **linked-1**:

- Canonical source binding stores snapshot/raw hash; ordered-position/source-span views retain exact source locators, line boundaries, gaps and unsupported positions.
- Indexed postings by scoped reading or source-derived sign ID; optional configured 2–5-gram windows with stable graph-compatible match span IDs, occurrence lists and source/witness/artifact links. Separate source/strict policies; no Cartesian alternatives or rewiring across exclusions.
- Executable typed node/edge views, reversible provenance/claim/translation-placement links, exact catalog-key candidate lookup preserving competing alias claims, translation text/context lookup and missing-layer coverage.
- Registry with configuration/revision/source/canonical hashes, stale detection and atomic bounded rebuild. Defaults cap 20,000 positions / 100,000 derived rows; budget failures leave the existing projection intact. Frozen persistent database rebuilds are refused; new imports bind projection configuration into a new snapshot ID.
- Variable manifest inventories retain all mandatory canonical assets and include only configured derived tables. Generic persistent export includes every materialized table. Legacy schema-1/conservative-2 verification retains the original inventory contract, with no rewriting.
- `explore` CLI supports report, postings, motifs, sequence, occurrence, reverse-postings, reverse-motifs, aliases, catalog, translations, nodes, neighbors and source span. [Representation map](docs/REPRESENTATION-MAP.md) supplies CLI/API recipes and the portable graph export contract.

Parser change: unsupported strings in exported `signs` now block matching and no longer create a SignType/MAPS_TO_SIGN assertion. They previously passed through the derived-sign shortcut (e.g. `B/C`). Real exported sign identifiers remain source-derived, not visual evidence. All four prior review regressions remain green. Full source grammar and compatible alternatives remain unsupported.

Executed with existing `/Users/danieliser/.local/share/cuneiform-research/venv/bin/python -B`, in-memory DuckDB with disk spill disabled:

```
CUNEIFORM_RUN_DISK_TESTS=0 .../python -B -m unittest discover -s tests -v
Ran 28 tests in 10.103s
OK (skipped=1)
```

**27 passed, 1 disk integration test deliberately skipped.** Includes old fixture/review tests and nine projection tests: independent hand counts, overlapping motifs, unknown-length losses, unsupported alternatives, strict exclusions, namespace/field separation, source-span trace roundtrip, graph/array/index parity, duplicate aliases and exact cross-source lookup, unresolved translation coverage, bounded paging, stale rejection, deterministic rebuild, atomic budget refusal, optional assets and mocked schema-1/schema-2 manifest inventories. The actual retained eBL test ran (not skipped). Mocked payload verification is not disk/Parquet evidence.

Actual source exercises using only already-retained files:

| Input | Index / array / graph motif count | Postings / n-gram rows | Coverage |
|---|---|---|---|
| Synthetic eBL `A B C` | 6 / 6 / 6 | 35 / 47 | 1 unresolved translation; 0 supplied words/lemmas |
| Frozen eBL example `ABZ215 ABZ13`, signs | 3 / 3 / 3 | 375 / 1,824 | 9 unresolved translations; 0 supplied words/lemmas |
| Retained live eBL K.1 metadata, `A B` | 0 / 0 / 0 | 0 / 0 | no supplied sequences or translations |
| Retained three CDLI rows, `A B` | 0 / 0 / 0 | 0 / 0 | three artifacts, no supplied text layers |

CLI subprocess smoke: `explore ... motifs '["A","?","C"]' --limit 2` returned 2 rows, total 11, truncated=true; combined fixture alias lookup returned two separate claims; translation substring lookup returned one unresolved string. Existing graph matches and new indexed matches share span IDs. Twelve A postings matched both canonical positions and graph HAS_OCCURRENCE endpoints. Separate overlapping `A A A A` fixture yielded three `A A` matches. No linguistic accuracy is implied by count parity.

First new suite run caught a reserved SQL alias (`sequences`) in coverage; quoted the alias and reran successfully. Python-work/Pyright diagnostics: `projections.py` 0 diagnostics; `storage.py` initially reported a possibly-unbound branch variable, then 0 after explicit initialization/assertion. These are file-specific diagnostics, not a project-wide typecheck claim.

Disk evidence: start available **1,774,836 KiB**, later **1,762,320 KiB** (~1.68 GiB), below the 3 GiB reserve. Import dry-run returned exactly `free-space reserve would be violated`. Runtime footprint **50,992 KiB**; repository before final checkpoint/commit **760 KiB**, including Git. Added code/docs/tests remain well below 10 MiB and task-owned total below 500 MiB. No cleanup or new volume was used.

**Unverified new disk behavior:** schema-2 import, optional projection Parquet export/readback, persistent snapshot reuse/relocation and frozen-database rebuild refusal. Historical schema-1 parent disk success is preserved above, not extended to these changes. Portable graph export is a contract over executable views; no FalkorDB service or live FalkorDB validation occurred. ORACC, word/lemma/sense population, translation alignment, image evidence, alternative-aware bounds and the full SPEC remain future work. Source rights remain unresolved as previously documented.

Final report smoke passed after bounding summary coverage to 20 rows with a truncation flag. Frozen specifications and every review file were compared byte-for-byte against baseline Git contents and matched. `git diff --check` passed. `gitleaks dir . --redact --no-banner` scanned approximately 316 KB with **no leaks found**, retaining only the existing narrow frozen-spec false-positive exception. Local commit only; no remote action.

## Parent linked-review corrections

Fixed the three P2 findings in reviews/linked-projections-review-v0.1.md: source traces validate raw hash/source binding and whole record before attaching provenance; graph/array APIs reject pooled textual namespace/snapshot scopes (scoped lookup remains available); strict graph wildcard matching requires non-null readings, matching indexed eligibility. Added three regressions reproducing the original failures. Rights attribution distinguishes caller-supplied metadata from verified snapshot manifests; no authentication claim. Disk remains below the 3 GiB reserve, so schema-2 persistent validation stays deferred.

Parent rerun: 31 tests in 10.129s, 30 passed and one disk test skipped. Secret scan passed (336 KB scanned); diff whitespace check passed. No downloads, service changes or corpus writes.


## Persisted text-corpus pilot — implementation handoff (2026-11-03)

Sole implementation writer (QUEUE Q-001), base `2ab620b`, no child agents. Parent independent review is pending; this is the writer's evidence, not approval. Atlas/QUEUE files (`AGENTS.md`, `CLAUDE.md`, `QUEUE.md`, `docs/MODEL-ATLAS.md`, `docs/model-atlas.*`, `scripts/`, `reviews/atlas-review-v0.1.md`) belong to the atlas worker and were neither edited nor committed here.

**Model IDs affected:** `node:SourceRecord`, `node:Artifact`, `node:Witness`, `node:SequenceVersion`, `node:Line`, `node:SignOccurrence`, `node:SignType`, `node:TranslationSegment`, `node:Claim` (now populated from real data); `node:WordToken`, `node:Lemma`, `node:Sense` (now populated from ORACC); `edge:HAS_WORD`, `edge:LEMMATIZED_AS`, `edge:HAS_SENSE` (now written, with new qualification keys); new `edge:IN_SENSE` (WordToken→Sense); `artifact:snapshot-manifest` (new keys `snapshot_contract`, `projection_registry`, `build_timings`, `snapshot_payload_bytes`, `cohort`, `selection`, `ingestion`, `adapter`; new sources `ebl-cohort`, `oracc-selection`, `cdli-selection`); `contract:portable-graph-export` (implemented); `query:lookup` (`words`, `lemmas`, `scope`); `query:trace` (parent byte span); `view:portable_edge` (unchanged SQL). The atlas checker reports exactly this drift (10 errors at this tree); Q-007 owns the atlas sync.

### What was built

- `acquire`: allowlisted, checksum-verified downloads into a read-only content-addressed store, with immutable receipts; an explicit verified-intermediate option for ORACC's incomplete TLS chain.
- `corpus`: bounded-memory streaming JSON array scanner with exact byte offsets; whole-file inspection using the real adapter; deterministic cohort extraction (`usable-text-v1`, optional exact P-number filter) into immutable manifests with byte-identical parent slices; per-record audit.
- `storage.import_cohort`: chunked, record-atomic import with spooled bulk loading (single-row DuckDB inserts cost ~0.2 ms/row; spooled loads take ~0.08 s per 100k rows). Shared `materialize` and `publish`: atomic, exclusive, ledgered, read-only.
- `oracc` (`oracc-cdl-1`), `cdli_api` (`cdli-artifact-json-1`), `persisted` (scope, lookups, parity, export, catalog link), `query.trace` parent byte spans, `trace-word`.
- Projection builder streams positions per line and spools rows. Output is byte-identical to the previous build on every retained input (baseline canonical/projection row hashes compared before and after the refactor). The graph validator now uses per-kind semi-joins.

### Actual data and measurements

All on this machine with `~/.local/share/cuneiform-research/venv/bin/python -B` (Python 3.13.12, DuckDB 1.4.3). Times are wall clock (`/usr/bin/time -l`).

| Step | Result |
|---|---|
| eBL `fragments.json` acquire | 73,854,507 B, MD5/size matched record API, 41 s; `receipt:66b5c94472b500317dbebd173bc149d3` |
| Whole-file inspection | 23,289 records, 95 s, peak 48 MB; 1 duplicate key (K.5808 ×2, byte-identical), 0 adapter rejections |
| Cohort select 30 / 300 | 100 s / 93 s, peak ≤54 MB; 20,896 eligible; 30 = first 30 of 300 |
| Import 30 → `snapshot:ce127437339109285185a534145edf50` | 2.5 s, peak 419 MB, 32 MB on disk |
| Import 300 → `snapshot:84971360d212834e0b7acbeac1e56abe` | 20.3 s, peak 632 MB, 174 MB on disk; 80,823 positions, 215,271 edges, 223,799 n-grams |
| eBL∩ccpo cohort (51) → `snapshot:c316e7cbbaf8a7fca7705f0efa5c4a07` | 55 MB |
| ORACC ccpo 51 texts → `snapshot:edaab55c1a39cc65ad7c76e6d12547a7` | 1.4 s, peak 242 MB, 36 MB |
| CDLI 51 records → `snapshot:fc7c350439f9edfee61b5f35bdd4d65a` | 84 s (1 s spacing), 6 MB |
| Parity at 300 records | graph = array = index for 7 motifs, e.g. `ABZ480 ABZ13` 201 (38/300 witnesses), `ABZ411×3` 174, `ABZ115 ? ABZ597` 104, `DIŠ ina` 45, `ina ? ana` 29. Graph ~150–180 ms, array ~150–170 ms, index ~10–12 ms |
| Lookup latency at 300 | 1.28 s → 0.043 s after the frozen-verified freshness path; connect+verify 0.10 s |
| Trace | `BM.34584` token `ina]` → parent `/4573`, file bytes [24,411,382, 24,411,386); `ša₂` → bytes `ša₂` [13,442,912, 13,442,925); both read back directly from the parent file |
| Graph exports | 5 exports, 0 dangling edges; 300-record export 93,831 nodes / 217,365 edges in 0.6 s |
| Runtime root | 479 MiB total (snapshots 302, raw 91, derived 35, venv 50); filesystem 152 GiB free |

Strict-policy windows are 0, because no eBL position is asserted intact+certain. ATF reading motifs are sparse, because hyphenated words remain opaque blockers. These are the expected conservative outcomes, not defects.

### Tests

```
CUNEIFORM_RUN_DISK_TESTS=1 .../python -B -m unittest discover -s tests   ->  Ran 43 tests in 15.4s  OK
.../python -B -m unittest discover -s tests                              ->  Ran 43 tests  OK (skipped=5)
```

New regressions cover: scanner byte ranges at chunk sizes 1/3/7 with escaped/unescaped Unicode and both envelopes, and its structural refusals; adapter-stat/import agreement; dangling and wrong-type edge refusal; ORACC mapping (shared lemma, per-word senses, unlemmatized words, list-length mismatch, no translations); CDLI mapping and rejection; cohort determinism/prefix/duplicate exclusion; chunked (batch=1) vs whole-input canonical hash equality; parent-verified trace; relocation; parent and payload tamper detection; spool vs executemany equality; all five projection configurations with Parquet readback; frozen fast path vs writable recompute and stale detection; ledger refusal after deletion; read-only publication; encoded-span mapping; and the delivered real snapshots (gated on presence). Disk tests write only into temporary roots and delete them.

### Incident: same-ID snapshot rebuild (reported by UI review F-4, verified here)

At ~09:44Z I published `snapshot:ce127437…` and `snapshot:84971360…`. At ~09:46Z I deleted both directories and re-imported them under the same IDs, to add freeze-time registry hashes to the manifest. Each build was a complete staged directory published by one rename, so no file was written in place. The deletion and republication still violated immutability: readers saw different bytes under one ID. The other three snapshots were published once and never touched. First-version bytes were not retained, because I deleted them. The UI reviewer's size/mtime observations are the surviving evidence, and the first-run counts in my transcript equal the current manifests. Record: `~/.local/share/cuneiform-research/evidence/incident-2026-11-03-same-id-rebuild.json`.

Remediation (tested): an append-only `snapshots/.publication-ledger.jsonl` written under an exclusive lock, which refuses any ID ever published, even after deletion; read-only published trees; manifest contract `manifest-3` included in new snapshot IDs (older manifests keep the legacy formula and still verify). The five existing snapshots were backfilled into the ledger (the two rebuilt ones carry an `incident` note), made read-only without byte changes, and re-verified. From here on, revisions get new IDs only.

### Remaining limitations

eBL rights conflict unresolved. ORACC CC0 statement and CDLI terms are recorded, not legally reviewed. ATF grammar subset: hyphenated words, determinatives, compounds and numerals are blockers. No signs↔ATF alignment and no translation alignment. ORACC graphemes are unmapped and its JSON carries no translation text. Only one ORACC project (ccpo) is imported. CDLI inscriptions were not fetched. No compositions, passages, dates, joins, images or embeddings. Cohorts are hash-ordered samples filtered for usable text, not representative corpus statistics. Full-corpus import was not attempted: at the measured ~155x payload ratio (174 MB for 1.12 MB at 300 records) one full-file snapshot would be roughly 11 GB, above the 5 GiB budget, so storage layout (e.g. Parquet-only or dropping duplicated raw_json) is a later decision. FalkorDB/MCP are next tasks. No remote push, release or publication.

## Q-005 review fixes — publication protocol and read contract (2026-11-03)

Backend fix worker, baseline `d6049e2` (the tree includes the atlas-only commits `fd54419` and `11be81d`). Dispositions for every finding: [docs/CORPUS-REVIEW-v0.1-DISPOSITION.md](docs/CORPUS-REVIEW-v0.1-DISPOSITION.md). Protocol: [docs/PUBLICATION-PROTOCOL.md](docs/PUBLICATION-PROTOCOL.md). This is writer evidence and awaits the parent's independent recheck.

**Model IDs affected:** `artifact:publication-ledger` (format 2: reserve/commit/abort/abandon/adopt, `cuneiform/publication.py`), `artifact:snapshot-manifest` (reads are ledger-bound in a store; no manifest key changes), `edge:IN_SENSE` (qualification `sig`, `inst`, `payload_pointer`), `edge:HAS_SENSE` (qualification `attribution`), `node:Sense` (`source_locator` is a sense-key locator, adapter `oracc-cdl-2`), `query:lookup` (`ScopeMismatch`, `LayerUnavailable`, `timing`, `scope.publication`, `scope.input_identity`), `query:trace` (`timing`, `publication`), CLI `publication-*` verbs, cohort ledger.

- B1–B3 fixed. F4–F11 fixed or labelled. F12 is documented, not reconstructed. Lemma and HAS_SENSE first-attestation `source_record_id` is deferred, because it needs a schema change.
- New real snapshot `snapshot:5e51403b0d7dcdb90cb429d444e6a23b` (ORACC ccpo, `oracc-cdl-2`, 51 texts, same receipt and match snapshot as `snapshot:edaab55c…`): 1.6 s, 282 MB peak RSS. Counts are equal to the old snapshot. 0 Sense rows carry an instance sig, and 0 of 4,544 `IN_SENSE` sigs differ from the word's own `LEMMATIZED_AS` sig. The five pilot snapshots, their manifests, modes and ledger records are byte-unchanged (fingerprint and ledger-prefix SHA `e5bdb93e…`).
- Tests: `CUNEIFORM_RUN_DISK_TESTS=1 …/python -B -m unittest discover -s tests` → `Ran 59 tests … OK`. In-memory run → `Ran 59 tests … OK (skipped=17)`. 16 new tests are in `tests/test_publication.py`; the crash tests hard-kill child processes at every protocol boundary.
- Limits: this is an application-level protocol for cooperating writers on one host. Same-owner OS access, ledger edits or deletion, and root are not prevented. The first-version bytes of the two incident IDs are not recovered.

## Q-020 residuals R1–R5 — store reads, cohort reads, reserve→commit wait (2026-11-03)

Backend fix worker, baseline `94af111`. Dispositions: [docs/CORPUS-REVIEW-v0.2-DISPOSITION.md](docs/CORPUS-REVIEW-v0.2-DISPOSITION.md). Protocol reads section rewritten: [docs/PUBLICATION-PROTOCOL.md](docs/PUBLICATION-PROTOCOL.md). This is writer evidence and awaits the parent's independent recheck. Atlas files were not edited; the drift is listed in the disposition.

**Model IDs affected:** `artifact:publication-ledger` (cohort recovery through `--store cohorts`; build lock taken by recovery; a writer waits on `reserved`), `artifact:snapshot-manifest` (read contract only: symlinked, misplaced and absent store entries refused with a typed error; no manifest key change), cohort artifact (`verify_cohort` is ledger-checked and returns `publication`), CLI `publication-*` (`--store`), `corpus-audit` (`publication`), `concept:rights-ledger` (fingerprint of `ebl-cohort` changes only through the `verify_cohort(..., ledger=cohort_ledger)` binding; rights text unchanged).

- R1 fixed: store membership comes from the lexical and the resolved parent. Symlinked or escaping entries and payload symlinks are refused. `store_path`/`resolve_snapshot` reads are `ledger='require'` and bound to their ID. R2 fixed: cohort reads, audit and import are ledger-checked, and explicit cohort recovery and adoption are available. R3 fixed: a writer waits on the build lock and decides again; recovery holds the build lock; cohort builds hold a build lock. R4 and R5 fixed (R5: `fsync_dir` unchanged).
- Tests: `CUNEIFORM_RUN_DISK_TESTS=1 …/python -B -m unittest discover -s tests -v` → `Ran 70 tests … OK` (59 existing + 11 new in `tests/test_store_reads.py`, 0 skipped). The same 70 in reverse order also pass. The 11 new tests all fail at `94af111` (negative control). The reviewer's `symlink_swap.py`, `symlink_other_id.py` and `cohort_uncommitted.py` show every case refused.
- Real store: read-only. All 6 IDs verify with their unchanged labels. The 3 cohorts audit as `unledgered-pre-ledger-cohort-store`. The fingerprint (266 entries) is identical before and after, and the ledger SHA-256 is still `6d359b74…`. Building any new cohort in the real store creates the cohort ledger; the three older cohorts then need an explicit owner adoption.

## Q-023 full eligible eBL import — implementation handoff (2026-11-05)

Full-import implementation sub-agent, sole writer and sole QUEUE writer for Q-023 (parent grant), base `7a7baf3`. This is writer evidence; an independent reviewer decides acceptance. Evidence files: `~/.local/share/cuneiform-research/scratch/q023-full-import/{evidence,logs}/` (index in its `INDEX.md`).

**Model IDs affected:** `artifact:cohort-manifest` (format `cohort-2`: `excluded_records`, `corpus.accounting`), `value:snapshot-scope` (kind `all eligible records of a fixed release`, label `FULL ELIGIBLE …`), `query:lookup` (bounded, partition-first reads; `SCOPES_SQL`), `table:projection_registry` (FULL preset 12M / 80M; hard caps raised to match), `interface:cli` (`--max-total-gib`, `--reserve-gib`, `corpus-select --all-eligible`, `corpus-accounting`, `corpus-import --projections/--memory`), `interface:ui` (sibling). No schema, parser, projection-revision or manifest-key change; snapshot contract stays `manifest-3`.

### Result

`snapshot:965aa26214dc0388dd3af1be367d2acc` (manifest `44a20685…`, ledger format 2 reserve+commit 2026-11-05T10:19:55Z) holds **every record of the fixed eBL release** Zenodo 10018951 `fragments.json` (73,854,507 B, MD5 `71538e2d…`, sha256 `4e970d87…`, receipt `receipt:66b5c944…`) that is eligible under `usable-text-v1`, from `cohort:4e532850276b7960e67f149f6463afcf`:

| Accounting (independently recounted by a fresh streaming pass) | Records |
|---|---|
| Parent records | 23,289 |
| Members (eligible, imported, 0 adapter rejections) | 20,896 |
| Excluded: fewer eligible reading/sign positions than threshold | 2,171 |
| Excluded: fewer adjacent eligible pairs than threshold | 154 |
| Excluded: no numbered ATF text line | 66 |
| Excluded: duplicate source key in parent (both K.5808 copies) | 2 |

Every parent index is exactly one member or one excluded record (`accounting.status = complete-partition`); excluded records keep pointer, byte range, record sha256 and reason, and verification re-reads each excluded slice from the parent. The parent raw object is retained unchanged in `raw/sha256/`.

Counts: occurrence 4,542,153; edge 12,167,645; ngram 12,292,380; posting 2,883,814; line 629,335; sequence_version 41,792; translation_segment 23,984 (all `unresolved-span`); exclusion (unsupported-position records) 1,051,657; claim 16,735; sign_type 649; word_token/lemma/sense 0 (absent from the export).

### Staged qualification (1k → 5k → full), same code and FULL preset

Stages 1k and 5k ran in a scratch root (`scratch/q023-full-import/stage-root`, own ledgers, never served); full ran in the real store. DuckDB memory cap 8 GB (stages) / 16 GB (full), spill disabled. Peak RSS from `/usr/bin/time -l`.

| Stage | Positions | n-grams | Import | Peak RSS | Peak stage | Retained |
|---|---|---|---|---|---|---|
| 1,000 | 231,480 | 628,905 | 43.6 s | 0.87 GB | 0.69 GB | 0.51 GB |
| 5,000 | 1,099,968 | 2,989,080 | 214.8 s | 2.55 GB | 3.32 GB | 2.36 GB |
| 20,896 (full) | 4,542,153 | 12,292,380 | 1,253.5 s (ingest 482, validate 7, projections 593, Parquet 27) + select 95 s | 6.25 GB | 13.80 GB | 9.64 GB |

Checks at every stage (`scripts/full_import_stage.py check`, all `ok: true`): record accounting and member-key equality; ID uniqueness in all 21 ID tables and the `nodes` view; Parquet = table row count and order-independent row hash for all 22 tables; 20 parent-file byte traces stratified by kind (full: 20/20 `verified`, 8 through `\uXXXX` escapes such as `DIŠ` → `DIŠ`, `ša₂` → `ša₂`, 5 unsupported-grammar tokens such as `{iti}BARA₂`, `AN-e`, `[...]-ri`, plus gaps and derived signs); 14 stratified motifs (top / median / rarest bigram and trigram per field, plus wildcards) with graph = array = index = index rerun (full: e.g. `ABZ411 ABZ411` 29,166; `DIŠ ina` 4,657; `ABZ115 ? ABZ597` 1,081; `ina ? ana` 359; rare cases 1); subset comparison with the 300-record snapshot `84971360…`: all 300 records present, per-record position and n-gram counts equal, whole-snapshot motif counts larger (`ABZ480 ABZ13` 201 → 7,170) as expected for a superset. Full check: 219 s, 5.06 GB peak RSS, verification of the 9.5 GB snapshot 5.3 s.

Interruption (scratch, 1,500-record cohort, `scripts/full_import_interrupt.py`): SIGKILL at 12 s (ingestion) and 60 s (after ingestion) left one orphan `.pending-*` stage each, no ledger record, no torn tail, every other snapshot verified; the rerun built normally and `publication-clean-stage` removed both orphans. The mid-build free-space guard and every accounting defect are unit-tested (`tests/test_full_import.py`).

Root-caused failures: (1) at 5k, interactive lookups (`occurrence`, `postings`, `span`, report scopes) hit the UI's 256 MB DuckDB bound because they filtered `ordered_position` by a non-partition column, so its `row_number()` window ran over every position first; they now resolve `sequence_id` first (pushed below the window) or page posting rows before joining positions. Same rows: `test_partition_first_lookups_equal_the_original_window_filtered_sql`. (2) After the import the 5 GiB default admission refused all 29 disk tests (root 14.4 GB); the default stays, and `CUNEIFORM_TEST_MAX_TOTAL_GIB` names an explicit budget. (3) My first 1k parity check selected only wildcard cases (a NULL-handling filter bug in the harness); fixed and the harness now refuses fewer than 10 cases.

### Prerequisites done

- Pre-ledger cohorts `cohort:4e86952e…`, `cohort:9abad6ce…`, `cohort:ea91baae…` independently re-checked (`scripts/q023_adopt_precheck.py`: manifest digest, cohort-1 identity, payload hash, 300/30/51 member slices equal to parent bytes, cohort manifest byte-identical to each bound snapshot `cohort.json`), then adopted (`publication-adopt --store cohorts`). Before/after fingerprint of `derived/cohorts`: every prior file identical (size, mtime, mode, sha256); only the new ledger and lock appeared. Receipts: `evidence/adopt-*.json`.
- The six earlier snapshots were not touched: the snapshot-store fingerprint (172 entries) is identical except the ledger, whose first bytes still hash to `6d359b74…` with exactly two appended lines (reserve, commit of `965aa262…`).

### Resources

Disk: runtime root 1.1 GiB at start → 13.45 GiB now (full snapshot 9.0 GiB, its cohort 94 MB, scratch stages 3.4 GiB); peak during the full build about 17 GiB above start; free space never below 190 GiB (budget 40 GiB additional, ≥30 GiB free). CPU: single-threaded build. No downloads, images, embeddings, paid inference or public services.

### Workbench (sibling `cuneiform-ui` `2be365e`, `4dcc416`, pin `057a0b7`)

Live on 127.0.0.1:8740 (restarted UI process only; FalkorDB containers untouched): 7/7 snapshots ready, the full one labelled `FULL ELIGIBLE 20,896/23,289 · ebl-zenodo-10018951-fragments.json`. Snapshots above 2 GiB are re-hashed in full at discovery and hourly; each request checks every file's stat fingerprint, the `manifest.json` bytes and the ledger (labelled `bounded-per-request`). Large snapshots get a 512 MB per-request DuckDB bound (graph traversal needs it). Latency on the full release, server end to end: index motif 340–430 ms without parity, 1.3–2.7 s with the graph parity add-on (parity equal on all three probes); graph engine 2.4 s; postings `ABZ579` (91,000) 121 ms; report 0.64 s; occurrence + backend parent trace 6.2 s (the backend trace re-hashes 9.5 GB itself). Stale version 409, foreign Host 421, Cypher 403, FalkorDB load of the full snapshot refused (5.3M nodes > 150k cap). UI suite: 24 isolation checks ok, 44 tests OK, 0 skipped. Rollback: `git -C cuneiform-ui revert 4dcc416 2be365e`, `bin/cuneiform-ui ui-stop && bin/cuneiform-ui ui-start` (the 63f4221 pin export is still present).

### Tests and checker

`057a0b7` clean export: in-memory 75 OK (skipped=30); `CUNEIFORM_TEST_MAX_TOTAL_GIB=41 CUNEIFORM_RUN_DISK_TESTS=1` 75 OK, 0 skipped, 44.8 s. Atlas revision 6: `check` OK, `--runtime` OK, `--self-test` 65/65. Both runs are recorded `read_back: false` (implementer-reported).

### Limitations

Similarity: the full indexes (postings, 2–5-gram windows, graph edges) are the input a similarity method would need, but no similarity algorithm exists or is claimed. FalkorDB cannot hold the full graph under the UI caps; canonical DuckDB + Parquet and bounded DuckDB neighborhoods are the full-scale graph surface. Per-request verification of the full snapshot is stat + manifest + ledger, not a payload re-hash (a write that keeps size, mtime, inode and ctime would be caught only by the hourly re-hash). Parser limits are unchanged (conservative-3: hyphenated words, determinatives, compounds and numerals block; strict policy is 0 because the export never asserts intact+certain). Counts are frequencies of represented positions in eligible records, not linguistic completeness. ORACC is only ccpo (51 texts) and CDLI only the 51-record catalog crosswalk; neither collection is imported in full. eBL rights conflict (CC BY 4.0 vs CC BY-NC-SA 4.0) is unresolved and the restrictive notice is kept. Scope note cosmetic: a cohort with no exclusions prints `0 excluded ()`.

## Q-023 independent acceptance (2026-11-05)

Parent read `reviews/full-corpus-review-v0.1.md`: full eligible fixed-release import and local UI accepted with no blockers. Snapshot `965aa26214dc0388dd3af1be367d2acc` is now accepted in the atlas; independent run records are separate from unchanged writer records. The parent reran the atlas static and runtime checks successfully. Reviewer evidence includes all 4,542,153 token offsets, 28 motif counts, 75 disk tests without skips, and UI 44 tests plus 24 isolation checks. Source/strict-policy and other coverage limitations remain explicit. N4: AGENTS now documents the authorized 41 GiB disk-test setting. N1–N3 fixes are owned by the parent in the sibling UI. No snapshot, cohort or ledger data modified; scratch retained.
