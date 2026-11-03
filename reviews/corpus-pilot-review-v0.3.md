# Corpus pilot review v0.3: independent recheck of the R1–R5 fix round

- **Scope:** narrow recheck of fix commit `63f42216243141f4b10cdfd3d7ddd514c85b63d7` against `reviews/corpus-pilot-review-v0.2.md` R1–R5 and `docs/CORPUS-REVIEW-v0.2-DISPOSITION.md`. B1 and B3 were independently closed at `94af111` by Q-020 and were not re-audited. This is not a broad new audit.
- **Reviewer:** review sub-agent. It did not take part in the fix. It made no code, doc, checker or queue edits, no commits, no delegations and no memory-store writes. It owns only this file.
- **Date:** 2026-11-03.
- **Code under review:** all harness and suite runs used a clean `git archive 63f4221` export. The negative control used a clean `git archive 94af111` export. The live checkout's uncommitted files (`QUEUE.md`, atlas docs, `scripts/check_model_atlas.py`) belong to the atlas agent and were not touched or used.
- **Scratch:** `~/.local/share/cuneiform-research/scratch/review-v0.3/` (`scripts/`, `work/`). Each run's stores were deleted right after the run. Peak use was about 254 MB during one harness run, which went over my 200 MiB budget until I trimmed it; every later run stayed under it. Final use is about 3 MB. Free space stayed at 127 GiB, above the 10 GiB floor.
- **Real store:** read-only. The fingerprint is unchanged (§7).

## 1. Decision

**ACCEPT for the authorized local cooperating-writer pilot. No concrete blocker remains. R1–R5 are closed at `63f4221`.**

| Finding | Verdict | Basis |
|---|---|---|
| R1: symlinked store entries bypass the ledger | **Closed** | §2: same-ID/different-bytes and different-ID links are refused on all 9 CLI read verbs, the `snapshots` listing, 15 API reads, re-import and adopt. Covers links into another ledgered store, `..` escapes, payload file and payload directory links, and dangling destinations. Honest labels for relocations. |
| R2: cohort reads not ledger-bound; no cohort recovery | **Closed** | §3: after a kill at `after-rename`, every cohort read, audit, import and rebuild refuses. Recovery commits exactly the reserved bytes. `after-reserve` → `complete` and `discard` both work. |
| R3: writer inside a live reserve→commit window fails | **Closed** | §4: the second writer waits and reuses. Recovery started in the window finds nothing to recover. A killed reservation is still refused at once. Cohort builders build once. |
| R4: untyped refusal for absent entries | **Closed** | §5: `reserved`, `published-missing`, `abandoned`, `not-found` are typed on the API and CLI paths for snapshots and cohorts. Outside a store a missing path is still `FileNotFoundError`. |
| R5: modes not flushed; `fsync_dir` skips silently | **Closed (modes). `fsync_dir` skip: stated limit, not material here** | §6 |

**UI re-pin: yes, the UI may re-pin to `63f4221`.** See §9 for the consumer notes.

## 2. R1: store membership and symlinks (closed)

Harness `scripts/v03.py`, cases `r1a`–`r1e`, run against both exports. Results are in `work/results-63f4221.json` and `work/results-94af111.json`.

| Case | `63f4221` | `94af111` (negative control) |
|---|---|---|
| r1a: `snapshots/<SID>` linked to an out-of-store copy of a different same-ID build (ledger `da7c8654…`, link `63957c26…`) | All 9 CLI verbs (`manifest`, `scope`, `query`, `lookup report`, `lookup postings`, `parity`, `trace`, `export-graph`, `catalog-link`) exit 2 with no traceback. `snapshots` lists `verified: false, state: symlinked-entry`. No export written. All 15 API reads raise `PublicationError('symlinked-entry')`: `resolve_snapshot`, plus `verify`, `verified`, `scope`, `lookup_snapshot`, `connect`, `trace` and `motif` on the plain path, and `verify`, `verified`, `scope`, `connect`, `parity`, `trace` and `catalog_link` on `store_path`. Re-import refuses `symlinked-entry`. `publication-adopt` refuses. `publication-status` lists the link under `symlinked_entries`. | 24 reads served the other build's bytes; for example, CLI `manifest` returned `946a9cea…`, not the ledger's `31827b96…`. An export was written. |
| r1b: link to the *other ledgered store's* entry for the same ID | 0 reads served | All 26 reads served, including `resolve_snapshot` and `snapshots`, because the target sits beside a ledger. This variant was not in v0.2 and is also closed. |
| r1c: `<store>/sub/../<SID>`, with `sub` linked outside next to another build's copy | `verify` and `verified` refuse `symlinked-entry` | served as `standalone-not-ledger-checked` with the other bytes |
| r1d: `raw` replaced by a link to identical bytes; `parquet/` replaced by a link to an identical copy | refused (`symlinked-entry`; CLI exit 2) | served `ledgered` |
| r1d: dangling link at the destination (published ID / fresh ID) | re-import and resolve refuse `symlinked-entry`; a fresh import refuses `unledgered` | `published-missing` / `FileNotFoundError` / `NotADirectoryError` |
| r1e (c11c): `snapshots/X` linked to a copy of Y; then a real directory X holding Y | 0 reads served in both forms (`symlinked-entry`; real directory: `misplaced` or `snapshot identity mismatch`) | the link form served 18 reads, including `scope X` and `query X` |

**Honest labels for lexical membership and relocation (r1c):**

| Read | Result |
|---|---|
| a real entry reached through a symlink to the store folder | served, `ledgered` |
| an outside link pointing into a store entry | served, `ledgered`, checked against that store |
| a real copy relocated outside every store | served, `standalone-not-ledger-checked` (`ledger='require'` refuses `not-in-ledger`) |
| an outside link to that relocated copy | served, `standalone-not-ledger-checked` |

Code read: `publication.locate_entry` uses both the lexical parent and the resolved parent, and refuses a lexical store entry unless `realpath == <realpath(store)>/<name>`. `verify` and `verified` call it before any hashing. `publication_of` adds `assert_no_symlinks` over `manifest.json` and every manifest file path, including intermediate directories. `StoreEntry` forces `require` and `expected_sid`. Even where it degrades to a plain `Path`, the lexical `auto` check still ledger-checks the entry and enforces `name == snapshot_id`. Network verbs (`trace-word`, `cdli-import --from-snapshot`, `oracc-import --texts-from-snapshot`) were checked by reading the code only, not run: each passes `store_path(...)` into `verify` or `connect`.

## 3. R2: cohorts (closed)

Each case used a runtime-shaped scratch root (`raw/sha256/<parent>` plus `derived/cohorts`) built from the synthetic parent.

- **r2a, hard kill at `after-rename`** (exit 137; ledger `[reserve]`; directory present). These all refuse with `reserved`: `verify_cohort` in auto, store and require modes and with the default; `audit(verify_cohort())`; CLI `corpus-audit` (JSON and `--markdown`); CLI `corpus-import`; API `import_cohort`; and a fresh `build_cohort` process. The CLI exits 2 with no traceback, and the message names `publication-status … --store cohorts`. **No snapshot store is created** by either import path. `publication-status --store cohorts` offers `[commit]`. `abandon` is refused. Snapshot verbs reject the cohort ID (`invalid snapshot ID`). After `--action commit`, ledger `[reserve, commit]`:
  - the tree fingerprint (lstat modes plus file SHA-256) is **identical** before and after recovery
  - the commit's `manifest_sha256` equals the reservation's
  - the commit's `manifest_file_sha256` equals the reservation's
  - the on-disk `manifest.json` SHA-256 equals the reservation's
  - the served `manifest_sha256` equals the reservation's, labelled `ledgered-recovered`
  - `corpus-audit` and `corpus-import` then succeed (`snapshot:fad04e1a…`)
- **r2b, hard kill at `after-reserve`** (no directory; one stage). The absent read refuses `reserved`, and the plan is `[complete, discard]`. After `complete`, the cohort tree equals the stage tree byte for byte, and the served and file digests equal the reservation (`ledgered-recovered`). After `discard`, the ledger is `[reserve, abort]` with 0 stages, and a rebuild publishes `ledgered`.
- **Negative control:** at `94af111` the same r2a state is served by `verify_cohort`, `audit`, `corpus-audit` and `corpus-import`, which publishes `snapshot:fad04e1a…` from the uncommitted cohort. That is the v0.2 defect.
- **Labels (`scripts/extras.py`):**

| Cohort read | Result |
|---|---|
| relocated copy outside a store, `auto` | served, `standalone-not-ledger-checked` |
| relocated copy outside a store, `require` | refused, `not-in-ledger` |
| symlinked entry in a ledgered cohort store | refused (`symlinked-entry`) by `verify_cohort`, CLI audit and CLI import; listed under `symlinked_entries` |
| pre-ledger store (no ledger, no lock), `store` mode | served, `unledgered-pre-ledger-cohort-store` |
| pre-ledger store, `require` | refused |

## 4. R3: contention (closed)

The writer was held with a `FAULT_HOOK` sleep, which works on both revisions, rather than the new test-only `PAUSE_AT`. So the negative control did not depend on the builder's hook.

- **r3a:** writer A was held 5 s at `after-rename`. During the window the ledger was `[reserve]` and a reader refused with `reserved`. Writer B and `publication-recover --action commit` both started inside the window.
  - Result: A `reused: false`. B `reused: true` with **A's manifest** (`f38f69d5…`) after waiting 4.6 s. Recovery exits 2 with `no open reservation (state published)`.
  - Final state: ledger `[reserve, commit]`, 1 directory, 0 stages.
  - At `94af111`, B fails at once with `reserved … (interrupted, or in progress)`.
- **r3b:** after a hard kill at `after-reserve`, a new writer is refused with `reserved` within 0.0 s. A dead holder releases the `flock`, so there is no hang.
- **r3c:** 4 simultaneous writers × 3 trials. Every trial: 4/4 succeed, 1 build, 1 manifest, ledger `[reserve, commit]`.
- **r3d, cohorts:**
  - 3 simultaneous builders: 3/3 succeed with one manifest and ledger `[reserve, commit]`. At `94af111`, one fails with `ledger-mismatch`.
  - Paused window: B waits and returns A's manifest. At `94af111`, B fails with `reserved`.
- **Lock order** (read): build lock, then ledger lock, in `materialize`, `publish_dir`, `recover` and `build_cohort`. `existing_snapshot(locked=False)` is never called while that process already holds the same build lock (`materialize` passes `locked=True`). So no self-deadlock on the flock is possible.

## 5. R4: typed missing entries (closed)

| Absent entry | `resolve_snapshot` / `verify(plain)` / `scope(store_path)` | CLI `manifest` |
|---|---|---|
| reserved (kill `after-reserve`) | `PublicationError('reserved')` | exit 2, no traceback |
| published, directory deleted | `published-missing` | exit 2 |
| abandoned (kill `after-rename`, delete, `abandon`) | `abandoned`; a rebuild is also refused `abandoned` | exit 2 |
| never seen | `not-found` | exit 2 |
| outside any store | `FileNotFoundError` (unchanged, as documented) | n/a |
| cohort never seen (`corpus-audit`, `corpus-import`) | n/a | exit 2, `not in the store …` |

At `94af111` all three store forms raise `FileNotFoundError`.

## 6. R5: durability (modes closed; `fsync_dir` assessed)

- **Mode flush (r5).** I traced `os.chmod` and `os.fsync` during a real `import_source` at `63f4221`. All 27 read-only chmods in the stage are followed by an fsync of the same path, the last stage operation is the stage directory's fsync, and the `reserve` append comes after every stage operation. At `94af111`, all 27 paths are chmodded after their last fsync, and the last stage operation is a chmod. The seal also refuses a stage that contains a symlink.
- **`fsync_dir` silent skip (stated limit; not material for this pilot).**
  - On this APFS data volume, directory `fsync` succeeds (checked directly), so the skip branch is not taken in the pilot.
  - On a filesystem that rejects directory fsync, the effect is that a rename might not survive a power loss. The ordering still holds: the reservation is `F_FULLFSYNC`ed before the rename. A lost rename leaves `reserved` plus a stage (`complete`/`discard`), or neither (`abandon`, ID burned). Both fail closed and never serve other bytes.
  - Recommendation: when the pilot moves to another filesystem or host, have the skip leave a visible note in the receipt or the log. This does not block the pilot.

## 7. Real store (read-only)

- **Fingerprint** of `snapshots/`, `derived/cohorts`, `derived/exports` and `receipts/` (path, size, mtime_ns, ctime_ns, mode, file SHA-256): 266 entries before (taken before any suite run). This equals the Q-020 `fp-after.json` exactly. After all suite runs (which include the read-only real-store tests) and my reads: **266 entries, 0 differences**. Ledger SHA-256 `6d359b74907bb3ae…`, unchanged. No `.locks` or ledger was created in `derived/cohorts`.
- **Reads at `63f4221`.**
  - `resolve_snapshot` plus `verified` on all 6 IDs: `5e51403b…` is `ledgered` and bytes-bound (`48bdc39e…` / file `e4923286…`). The five legacy IDs are `ledgered-legacy-backfilled`, with the incident flag only on `84971360…` and `ce127437…`. This matches v0.2 §6.
  - CLI `snapshots`: 6/6 verified. CLI `manifest` and `scope`: exit 0 for all 6.
  - `publication-status`: 6 `published`, no torn tail, no unledgered or symlinked entries, no stages. `publication-status --store cohorts`: no ledger, 3 unledgered directories.
  - CLI `corpus-audit` on all 3 cohorts: exit 0, labelled `unledgered-pre-ledger-cohort-store`.
- **Not done:** no adoption of the three legacy cohorts, no cohort build and no `export-graph` against the real store. Building any cohort there creates the cohort ledger, which would make the three legacy cohorts refuse until they are adopted. That decision belongs to the parent.

## 8. Tests and regression evidence

- **Forward:** `CUNEIFORM_RUN_DISK_TESTS=1 …/venv/bin/python -B -m unittest discover -s tests -v` on the clean `63f4221` export: **Ran 70 tests in 40.787s, OK, 0 skipped** (`work/suite-forward.log`).
- **Reverse order:** all 70 flattened: **OK, 0 skipped** (`work/suite-reversed.log`).
- **Isolation:** each of the 11 `tests/test_store_reads.py` tests run alone: **11/11 OK** (`work/isolated.log`).
- **Negative control.** Instead of running the builder's 11 new tests at `94af111` (they import `PAUSE_ENV`, so they would fail on import, which proves nothing), I ran my own harness on both exports. Every R1–R5 defect reproduces at `94af111` and is fixed at `63f4221` (§2–§6). That independently confirms the disposition's "11/11 failing" claim in substance.
- **Atlas checker:** not run or assessed. It belongs to the atlas agent and is outside this decision.

## 9. Remaining non-blocking items

- **N1 (Low, wording): a reader's refusal can wrongly say the writer is gone.** When a live writer is between `reserve` and the rename, the directory is still absent. A reader's refusal in that window (`missing_entry` → `refusal`) says "interrupted: **no live writer holds its build lock**", but the writer is alive and then commits (`extras.py`: writer A finished `reused: false` 4.15 s later). The read still fails closed. Only the message is wrong for readers, because they never probe the lock. Fix: use neutral wording ("in progress or interrupted") on the read path. Until then, the UI should treat reader `reserved` as "not yet available", not as "interrupted".
- **N2 (Info): one cohort label is inaccurate through the API.** `import_cohort` and `verify_cohort` default to `auto`. That labels the real store's pre-ledger cohorts `standalone-not-ledger-checked` with the note "not inside a cohort store", which is inaccurate. The CLI passes `store` and gets the accurate `unledgered-pre-ledger-cohort-store`. Both say "not ledger-checked", so this is wording only. UI cohort reads should pass `ledger='store'`.
- **N3 (Info, carried from v0.2 §4):** `publication-clean-stage` is still guarded by age only and leaves its `.recovery/*.json` receipt behind. This was out of scope for this round.
- **Pre-ledger symlinks:** a symlinked cohort entry in a *pre-ledger* cohort store is served with the pre-ledger label. Nothing there is ledger-bound, the label says so, and this ends when the store gets a ledger.

## 10. Limits stated (assessed, not expanded)

- **Owner tampering and root.** Same-owner edits to the ledger, files or modes, and root, are outside the protocol by design and were not tested as an adversary. The protocol text says so. For a cooperating-writer pilot this is the agreed boundary, not a defect.
- **Time of read.** Symlink and ledger checks run when a read starts. An operator who swaps an entry between `verify` hashing and the DuckDB open is not detected for that read; the next read refuses. Cooperating writers never swap store entries, so this is not material for the pilot.
- **`fsync_dir`:** see §6.
- **Not done:** downloads, network verbs, shared services, images, UI, multi-host tests, real power-loss tests (crashes are process kills; ordering is shown by trace), atlas or checker work, and cohort adoption.

## 11. For the parent

- **Q-020 / Q-005:** R1–R5 are closed at `63f4221`. B1 and B3 stay closed from Q-020. **Accept** the backend for the local cooperating-writer pilot. Suggested `verification_runs` entry: observer review-v0.3, commit `63f4221`, 70 OK forward and reversed, 0 skipped, `read_back: true`, real-store fingerprint unchanged.
- **UI re-pin: allowed at `63f4221`.**
  - Read store snapshots via `resolve_snapshot`/`store_path`, or `verified(path, ledger='require')`.
  - Handle the new `PublicationError.state` values `symlinked-entry`, `misplaced` and `not-found`, alongside `reserved`, `published-missing` and `abandoned`.
  - Treat a reader's `reserved` as "not yet available" (N1).
  - Use `ledger='store'` for cohort reads (N2).
  - Keep treating `snapshot:edaab55c…` as superseded by `snapshot:5e51403b…` for sense provenance (v0.2 §7).
- **Legacy cohorts:** adopting `cohort-4e86952e…`, `cohort-9abad6ce…` and `cohort-ea91baae…` is the parent's explicit decision. Do not build a new cohort in the real store before that decision. A build creates the cohort ledger, and those three would then be refused until adopted.
