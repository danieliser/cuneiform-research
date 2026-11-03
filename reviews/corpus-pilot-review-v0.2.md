# Corpus pilot review v0.2: Q-020 independent recheck of the Q-005 fix round

- **Task:** Q-020. Independent recheck of fix commit `94af111` (task `44ddaeb1`) against `reviews/corpus-pilot-review-v0.1.md` B1–B3, plus the F4–F12 dispositions in `docs/CORPUS-REVIEW-v0.1-DISPOSITION.md`.
- **Reviewer:** Q-020 review sub-agent. It did not take part in the fix, made no implementation edits, commits or delegations, and owns only this file.
- **Date:** 2026-11-03.
- **Code under review:** `94af111b513af4737f135087bec7ae994650efad`. All harness runs used a clean `git archive 94af111` export. The live checkout had only `QUEUE.md` and `scripts/check_model_atlas.py` modified (the atlas owner's files) and no backend changes.
- **Scratch:** `~/.local/share/cuneiform-research/scratch/review-q020/` (see its `INDEX.md`). Peak use was 578 MB for a moment, which went over my 500 MiB budget until I trimmed it. Final use is 1.4 MB: the scripts and JSON results are kept, and the scratch stores and snapshot copies are deleted. Free space stayed at 129 GiB or more throughout.
- **Real store:** never written, chmodded, deleted or opened for writing. See §6.

## 1. Decision

**Not yet accepted. B1 and B3 are closed. B2 stays open on one narrow residual (R1). The fix is small.**

| Blocker | Verdict | Basis |
|---|---|---|
| B1: ledger appended after the publish rename | **Closed** | §2: 9 independent crash and boundary cases, including boundaries the builder's tests do not cover (inside `seal`, and inside `publication-recover --action complete`), plus an fsync operation-order trace |
| B2: ledger not consulted on read or restore | **Open, R1 (Medium)** | §3: store reads through `store_path` (CLI `manifest`, `scope`, `query`, `lookup`, and the other `store_path` verbs) serve a **symlinked** store entry as `standalone-not-ledger-checked`, including different bytes under a published ID. Every other read and restore case passes. |
| B3: cleanup after the read-only chmod leaks the stage and masks the error | **Closed** | §4: 5 cases, covering the original-error type, notes, receipt, and seal failure after a full read-only chmod |

The parent should dispatch the UI re-pin only after the R1 fix commit. The UI calls `storage.verify(path)` in `auto` mode, which is the same code path. R2 and R3 are not blockers for snapshot publication. I recommend fixing R2 before the next cohort build.

## 2. B1: crash boundaries, durability, burned IDs (closed)

Harness: `scripts/adversarial.py` (run 2; run 1 had a harness `-I`/`sys.path` bug that broke the CLI calls, so it was fixed and rerun). Child processes are hard-killed with `os._exit(137)` through `CUNEIFORM_TEST_KILL_AT`, or through my own monkeypatches where the code has no fault point.

| Case | Injection | Observed |
|---|---|---|
| c01 | kill `after-reserve` | ledger `[reserve]`, no dest, one stage named by the reservation. Reader refuses, CLI `manifest` exits 2, a re-import refuses with `reserved`. The plan is `[complete, discard]`, and `--action commit` is refused. `complete` is served as `ledgered-recovered`, and the served `manifest_sha256` **and** the `manifest.json` file SHA-256 equal the reservation exactly. |
| c02 | kill `after-reserve`, then flip one byte of the reserved stage's `graph.duckdb` | plan `[abandon]` (stage observation: `snapshot integrity failure: graph.duckdb`). `complete` and `discard` are both refused. After `abandon`, a rebuild is refused with `abandoned` and adopt is refused. |
| c03 | kill `after-rename`, then delete dest | the reader refuses `reserved`. The plan is `[abandon]` only; `discard` is refused and a rebuild is refused. After `abandon`, a rebuild is refused with `abandoned`: **the ID stays burned even with both the stage and dest missing.** |
| c04 | kill `after-rename`, then replace dest with a valid same-ID build from another store | plan `[]` (`matches_reservation: false`). `commit` and `adopt` are refused, and the reader refuses. |
| c05a | kill inside `seal` after 3 chmods (my monkeypatch) | no ledger record, one unnamed stage listed by `publication-status`. `publication-clean-stage --min-age-s 0` removes it, and a rebuild publishes. |
| c05b | kill inside `publication.recover(..., 'complete')` after its rename, before its commit append | still `reserved`, dest present. The plan is `[commit]`; `commit` is then served as `ledgered-recovered`. |
| c13 | `KeyboardInterrupt` subclass raised at `rename`; `RuntimeError` at `after-reserve` | rename: the original type surfaces, ledger `[reserve, abort]`, no stage, no dest. After-reserve: the original type surfaces with a note that the stage is kept, ledger `[reserve]`, and recovery offers `[complete, discard]`. |
| c19 | adopt against a published ID (other bytes present / dest missing); an unledgered dir in a ledgered store | both adopts refused. The unledgered dir is refused by readers (`not-in-ledger`) and writers (`unledgered`) until adopted, and is then labelled `adopted` with `published_at_semantics: unknown`. |
| op trace | `scripts/op_trace.py` wraps `os.fsync`, `F_FULLFSYNC`, `chmod`, `rename` and ledger writes | 25 file and 2 directory fsyncs of the stage, then 27 chmods (0444/0555), then the `reserve` write, `fsync` + `F_FULLFSYNC` of the ledger, `fsync(snapshots)`, `rename`, `fsync(snapshots)`, the `commit` write, `fsync` + `F_FULLFSYNC`, `fsync(snapshots)`. **The reserve is durable before the rename, and the directory is fsynced after it.** |

Torn and corrupt ledger:

| Case | Observed |
|---|---|
| c06: half a commit record appended without a newline after kill `after-rename` | readers refuse (`reserved`). The writer and `publication-recover --action commit` refuse with `ledger-torn` until `publication-repair-ledger`. Then `commit` serves `ledgered-recovered`. The torn bytes are still in the file. |
| c08: unparseable first line | readers and writers both refuse with `ledger-corrupt`. |
| c07 (note): a complete commit line with no trailing newline | readers serve it, labelled `ledger_tail: unterminated final record …`. This cannot reassign bytes, because a commit must match the durable reservation. A reader racing the final append may serve the ID a moment before the commit is fsynced; if the crash then drops it, readers refuse again. |

Concurrency: c16 ran 4 simultaneous writers × 3 trials. In every trial all 4 succeeded, there was 1 build, the ledger was `[reserve, commit]`, there was 1 directory and no stages. c18 ran two different IDs concurrently and both published. See R3 for the one window that fails.

## 3. B2: read paths (open on R1)

Passing cases:

- c09: deleting a published dir makes rebuilds refuse with `published-missing`. Restoring the exact bytes serves `ledgered`. A re-indented `manifest.json` with the same canonical digest is refused with `ledger-mismatch` (file bytes are bound for format 2).
- c12: every CLI read verb refuses a reserved ID: `manifest`, `scope`, `lookup`, `query`, `parity` and `export-graph` all exit 2, and `snapshots` lists it `verified: false`.
- c19 / c20: an unledgered directory is refused. With the ledger deleted (an owner action, out of scope), `resolve_snapshot` and the CLI refuse with `not-in-ledger`, the writer refuses with `unledgered`, and a path read with no ledger and no lock is labelled `standalone-not-ledger-checked` as documented.

### R1 (Medium, blocks B2): symlinked store entries bypass the ledger on `store_path` reads

**Defect.** `storage.in_store` (`cuneiform/storage.py:74–77`) decides "in a store" from `os.path.dirname(os.path.realpath(snapshot))`. `publication_of` (`:97–106`) returns the standalone label when that resolved parent has no ledger. `store_path` (`:395–400`) only checks that the store's ledger exists and returns the path. The read functions then call `verify(path)` in `auto` mode: `query.connect` (`cuneiform/query.py:13`), `persisted.lookup_snapshot` / `scope` / `export_graph` (`cuneiform/persisted.py:44–47, 103, 125, 165`). So a store entry `snapshots/<SID>` that is a **symlink** to a directory outside any store is content-verified only and served as `standalone-not-ledger-checked` from inside a ledgered store. A real directory at the same path is refused. `resolve_snapshot` (`ledger='require'`), the `snapshots` verb (`require`) and writers do refuse it, so the read verbs and the listing disagree.

**Reproduction** (`scripts/symlink_swap.py`, scratch only):

1. Import `fixtures/ebl-synthetic.json` into store A, and again into store B. Both give the same ID `snapshot:e1722070…`; the manifests differ (A `0d7efebc…`, B `7f0201aa…`).
2. Copy B's directory to `external/<SID>`. In A, move the published directory aside and replace it with `ln -s external/<SID> snapshots/<SID>`.
3. `python -m cuneiform --root A manifest <SID>` exits **0** and returns `manifest_sha256` **`7f0201aa…`**, not the ledger's `0d7efebc…`. `scope`, `query` and `lookup <SID> report` also exit 0, labelled `standalone-not-ledger-checked`. `resolve_snapshot`, `snapshots` and a re-import refuse with `not-in-ledger`.
4. Variant c11c (`scripts/symlink_other_id.py`): `snapshots/X` linked to a copy of a *different* snapshot Y. `scope X` exits 0 and returns Y's scope, and `query X` exits 0. `manifest` (identity check) and `lookup` (snapshot override) catch it.

**Why in scope.** This is not the out-of-scope owner/root adversary. It is the same class of action as "copy a second build into the store", which the fix explicitly defends (`test_replaced_build_refused_…`). The protocol text promises "a directory beside a ledger … is always ledger-checked" (`docs/PUBLICATION-PROTOCOL.md`, Reads). A symlink is also the obvious way an operator would relocate a snapshot to another volume on a 93%-full disk. The result is the incident class itself: one ID, different bytes, served from the store.

**Suggested fix** (owner's choice): have `store_path` and `resolve_snapshot` refuse an entry that `is_symlink()` (or whose realpath parent is not the store folder), *or* decide "in a store" from the lexical parent (`os.path.dirname(os.path.abspath(p))`) and require the realpath name to equal the ID. Add the c11b and c11c cases as regressions. The UI should call `verified(path, ledger='require')` for store paths.

## 4. B3: cleanup and errors (closed)

| Case | Observed |
|---|---|
| c13 | see §2. The original exception type is preserved for both `BaseException` and `Exception` subclasses. |
| c14a: `seal` raises after making the whole stage 0444/0555 | the original `SealBoom` surfaces, no stage remains, no ledger record. File modes are untouched; only directories get u+rwx back. |
| c14b: failure at `before-reserve` plus `shutil.rmtree` raising `PermissionError` | the original `Orig` surfaces with the note `stage cleanup failed (PermissionError…)`. `.recovery/<stage>.json` holds `original_error`, `cleanup_error`, `action`. `publication-clean-stage --min-age-s 0` then removes the stage. |
| c15 | `publication-clean-stage` refuses a reservation-named stage, a non-stage name and a `../` name, and the stage is kept. |

Minor points (not blockers): the clean-stage guard is age-only (600 s default, measured from the directory mtime). It neither checks the per-ID build lock nor checks whether the writer is still alive. Also, after a successful clean-stage the `.recovery/*.json` receipt stays behind as a stale record.

## 5. Non-blocking findings

### R2 (Low–Medium): cohort reads are not ledger-bound, and an interrupted cohort has no recovery path

Reproduction (`scripts/cohort_uncommitted.py`): `build_cohort` hard-killed at `after-rename` leaves cohort state `reserved` with the directory present. `verify_cohort` succeeds on it, `audit` runs, and `storage.import_cohort` builds and **publishes a new snapshot** (`snapshot:fad04e1a…` in scratch) from the uncommitted cohort.

Code: `cuneiform/corpus.py:311` (`verify_cohort` has no ledger check); `cuneiform/cli.py:89–98` (`corpus-audit`, `corpus-import`); `cuneiform/storage.py:303`. The `publication-*` verbs only open the snapshot ledger (`cuneiform/cli.py:149`), so a reserved cohort ID cannot be recovered through the CLI, and `build_cohort` refuses it forever.

Impact is limited: cohort payload bytes are verified slices of the receipt-bound parent, and the snapshot binds `cohort.json` by hash. The F9 disposition "Fixed for new cohorts" overstates this, though; "writes ledgered, reads not" is accurate. `build_cohort` also has no per-ID build lock, so concurrent cohort builders lose with `ledger-mismatch` (`created_at` differs) rather than reusing. I read this; I did not run it.

### R3 (Low): a writer arriving inside another writer's reserve→commit window fails instead of waiting

Reproduction c17: writer A pauses 4 s at `after-rename` (fault hook). Writer B started during the pause fails with `PublicationError(state='reserved')` and the message "reserved but never committed (interrupted, or in progress)". After A commits, a third writer reuses the snapshot. The cause is the pre-check before the build lock (`cuneiform/storage.py:175, 310`; `cuneiform/oracc.py:129` → `existing_snapshot` at `:407–417`). The window is milliseconds in practice (rename, dir fsync, `F_FULLFSYNC`). It fails closed and does not corrupt anything, but the F5 claim "both succeed" holds only outside this window. The builder's concurrency test (2 trials) does not reach it. Fix: on `reserved`, take the build lock and re-check before refusing.

### R4 (Low): untyped refusal for a reserved ID whose directory is absent

c01: `resolve_snapshot` on a reserved ID with no directory raises `FileNotFoundError` from `verify` reading `manifest.json` (`cuneiform/storage.py:114`), not a `PublicationError(state='reserved')`. It still refuses. The UI should not depend on `.state` existing for every refusal.

### R5 (Info): durability details

`seal` fsyncs file contents and directories and then chmods without a later fsync, so read-only modes may not survive a power loss. Content hashes still protect the bytes. `fsync_dir` (`cuneiform/publication.py:80–87`) silently skips on `OSError`. Neither weakens the reserve-before-rename ordering shown by the op trace.

## 6. Real store: read-only evidence

- **Before and after this review:** a fingerprint of `snapshots/`, `derived/cohorts`, `derived/exports` and `receipts/` (path, size, mtime_ns, ctime_ns, mode, SHA-256 of every file) gave **266 entries before and after, 0 differences**. The ledger SHA-256 is `6d359b74…` before and after, and its first 1,808 bytes hash to `e5bdb93e…`, the pre-fix value.
- **Original five vs the independent Q-019 pre-fix fingerprint** (`scratch/review-q019/fingerprint-before.json`): 140 entries, 130 with file SHA-256, all with identical size, mode, mtime and ctime. `snapshot:84971360…`, `c316e7cb…`, `ce127437…`, `edaab55c…` and `fc7c3504…` are unchanged by the fix round.
- **Ledger-bound reads at 94af111** (`scripts/real_store_read.py`): all 6 IDs verify through `resolve_snapshot`. The five are `ledgered-legacy-backfilled`, with `manifest_file_bytes_bound: false` and the incident flag on `ce127437…` and `84971360…` only. `snapshot:5e51403b0d7dcdb90cb429d444e6a23b` is `ledgered` and bytes-bound: `manifest_sha256` `48bdc39e…` and `manifest.json` SHA-256 `e4923286…` equal its reserve and commit records. It has exactly one reserve and one commit (10:36:22.97Z / 10:36:22.98Z); it was never rebuilt.
- **Legacy vs format-2 binding** (c10, scratch): with a legacy-shaped record, a re-indented `manifest.json` (same canonical digest) is **served**. With a format-2 record it is refused (c09). In both formats the canonical `manifest_sha256` covers every payload file hash, so payload bytes are bound. The legacy gap is the `manifest.json` file bytes and formatting only. The backfilled `published_at` is a copied build time, labelled as such.

## 7. New ORACC snapshot `snapshot:5e51403b0d7dcdb90cb429d444e6a23b` (verified; stays pending)

`scripts/oracc_check.py` ran against scratch copies, with the raw zip read-only:

- **Raw and source links:** the zip `raw/sha256/c728b1f6…` SHA-256 equals receipt `receipt:0ca4ede9…` and `selection.parent`. All 53 selection members match their zip members, both by SHA-256 and parsed. The snapshot `raw` SHA-256 `5bced9bc…` equals `selection.payload_sha256` and `manifest.raw_sha256`, and is byte-identical to the old snapshot's raw.
- **All 4,544 analyzed words:** for each `IN_SENSE` edge, `payload_pointer` equals the word's own locator pointer (4,544), and `sig` and `inst` equal the raw node at that pointer (4,544 each; 36 raw nodes have no `sig`, and the edge has none either). `LEMMATIZED_AS.sig` equals `IN_SENSE.sig` (4,544). The edge `source_record_id` is the word's own text (4,544). The sense key (`cf`, `gw`, `pos`, `lang`, `sense`) equals the raw `f` (0 mismatches).
- **Sense rows:** 1,317 rows. **0** hold an instance sig (old snapshot: **1,309**). All 1,317 `first_attestation_in_selection` pointers resolve to an attestation of that sense. I did not check that the pointer is the *earliest* attestation.
- **Old vs new:** the same 6,888 word locators and the same lemma and sense assignment for all 4,544. Old Sense rows whose sig differs from the word's own sig: **1,380**, plus 36 words with no own sig. **1,380 + 36 = 1,416** explains the gap between the v0.1 review's 1,416 and the writer's 1,380: both are right under their own definitions. `snapshot:edaab55c…` is unchanged and still carries the misattribution, so discovery should label it.
- **Remaining provenance semantics (deferred, schema):** `Lemma.source_record_id` and `HAS_SENSE.source_record_id` name the *first attesting text*. **399 of 1,122 lemmas** and **406 of 1,317 senses** are attested in more than one text, so those IDs are one attestation among several, not the lemma's source. Every value is at least one of the attesting texts (1,122/1,122, 1,317/1,317). `HAS_SENSE` carries the `attribution` note (1,317/1,317). The `Lemma` row has no equivalent label. Per-occurrence provenance is complete on `LEMMATIZED_AS`/`IN_SENSE`.

Status: content and provenance are verified for this selection (51 texts, `oracc/ccpo`). Per instructions it is **not** promoted to `verified`; that is the parent's call.

## 8. Typed errors, timing, labels, exports

From `scripts/read_checks.py`, on a scratch store holding adopted copies of `5e51403b…` and `c316e7cb…`:

- **Typed errors:** `ScopeMismatch` for `namespace=ebl` on ORACC, `snapshot=<other>` on ORACC, and `namespace=oracc/ccpo` on eBL. `LayerUnavailable` for `postings` on ORACC (no `occurrence` rows), `translations` on ORACC (export lists `tr-en` but ships none) and `words` on eBL. A loaded layer with no match (`lemmas zzzz…`) returns `rows: []`. CLI: both error types exit 2 with their messages.
- **Timing:** each of 12 calls hashes `graph.duckdb` exactly once (I counted `storage.file_sha256` calls independently). `latency_ms == timing.query_ms`, `latency_scope: query-only`, and `verify_ms + query_ms ≤ end_to_end_ms` for every call. For example, ORACC `lemmas`: 20.5 / 6.8 / 36.2 ms; eBL `parity`: verify 29.5 ms, end to end 69.4 ms.
- **Labels:** the store copy is `adopted`; the out-of-store copy is `standalone-not-ledger-checked` (but see R1 for symlinks in a store).
- **Graph export:** `export-graph` on `5e51403b…` wrote nodes 9,636 and edges 17,707, equal to `nodes` and `portable_edge`, with node IDs equal as sets. The second run returned `reused: true`. No snapshot file was modified.
- **Snapshot Parquet readback:** 22 tables, 0 mismatches against the DuckDB tables and `manifest.counts`.
- **Same-ID mutation claims:** the 94af111 CHECKPOINT, disposition and protocol text make none. The new ID is a new `manifest-3` ID, and the old ORACC ID is explicitly not rewritten (confirmed by fingerprint).

## 9. Tests and independence

- `CUNEIFORM_RUN_DISK_TESTS=1 …/venv/bin/python -B -m unittest discover -s tests -v` on the live checkout at `94af111` (only `QUEUE.md` modified at the time): **Ran 59 tests in 30.048s, OK, 0 skipped**.
- The same 59 in **reverse order** from the clean export: **OK (27.889s)**. Each of the 16 `test_publication.py` tests run **in isolation**: 16/16 OK.
- **Independence:** disk tests each use a fresh `tempfile` directory under `<runtime>/scratch`, `tearDown` resets `FAULT_HOOK` and unlocks, and no test depends on another's state. Two tests read the real store (`RealStoreReadOnlyTests`, the delivered-snapshot pilot test); they are read-only, and my before/after fingerprint shows no change. They skip on other machines and hard-code the five legacy IDs.
- **Coverage gaps the builder's tests leave** (covered here): kill inside `seal` (c05a), kill inside recovery (c05b), a tampered reserved stage (c02), other-build bytes at a reserved dest (c04), symlinked store entries (R1), the reserve→commit window (R3), the cohort read path (R2), and legacy-record formatting tolerance (c10). The CHECKPOINT line "crash tests hard-kill … at every protocol boundary" is true for `publish_dir`'s four kill points only.
- **Checker at 94af111** (`python3 scripts/check_model_atlas.py` on the clean export): **2 errors**, `edge:HAS_SENSE` qualification `[] != ['attribution']` and `edge:IN_SENSE` `['basis'] != ['basis','inst','payload_pointer','sig']`. This is the expected atlas drift and belongs to the atlas owner. Q-020's acceptance clause "checker passing at the new baseline" is not yet met.

## 10. Limits stated

- **Scope:** an application-level protocol for cooperating writers on one host. The same owner can edit or delete the ledger, chmod, rename or replace files; root can do anything. Neither case was tested as an adversary. c20 only records the behaviour after a ledger deletion. Read-only modes are not immutable flags, and the ledger is an observation log, not a signature.
- **Visible but uncommitted:** an uncommitted directory is visible in the store between rename and commit. Ledger-checked readers refuse it, but anyone can `cp -R` it in that window. If the rename is then lost and the stage is `discard`ed, a copy could exist of bytes the ID was never committed to. Such a copy carries the `standalone` label.
- **Binding strength:** legacy-backfilled records bind the canonical digest only (§6). Format-2 records bind the exact `manifest.json` bytes.
- **Not done:** I ran no downloads, network calls, image work, UI mutation, corpus rebuild, multi-host test or real power-loss test (crashes are process kills, and fsync ordering is shown by trace, not by pulling power).

## 11. Recommended queue statuses (for the atlas/queue owner)

- **Q-020:** `BLOCKED` on R1. B1 and B3 verified closed at `94af111`. B2 is open on R1 (symlinked store entries are served by `store_path` reads without the ledger). Re-check needed: R1 fix commit with the c11b/c11c regressions, then the atlas sync with the checker passing, plus a `verification_runs` entry for this disk run (observer Q-020, commit `94af111`, 59 OK, `read_back: true`).
- **Q-005:** `IN_REVIEW`. B1 and B3 closed by Q-020; B2 open (R1). F4 and F6–F8, F10–F12 accepted as disposed. F5 accepted except R3. F9 is partial (R2).
- **Q-001:** `IN_PROGRESS`, needing a narrow fix round for R1 (required), with R3 and R2 recommended and R4 optional.
- **UI re-pin (Q-002/Q-006):** wait for the R1 fix commit. The UI should use `verified(..., ledger='require')` for store paths, read format-2 lines, and treat `snapshot:edaab55c…` as superseded by `snapshot:5e51403b…` for sense provenance.
- **`snapshot:5e51403b0d7dcdb90cb429d444e6a23b`:** content and provenance verified by Q-020 (§7). It stays pending; no automatic promotion.
