# Independent review — persisted text-corpus pilot (Q-005)

- **Reviewed:** commit `d6049e2` ("Persist reproducible eBL/ORACC/CDLI text-corpus pilot with immutable publication"), base `2ab620b`. The atlas worker's untracked files were not reviewed. Atlas drift is out of scope here and belongs to Q-007.
- **Reviewer:** an independent review sub-agent, not the Q-001 builder. Date: 2026-11-03.
- **Real data:** the runtime root `~/.local/share/cuneiform-research`, opened read-only. That covers the 5 published snapshots, the publication ledger, the eBL parent `raw/sha256/4e970d87…`, the ORACC zip `raw/sha256/c728b1f6…`, `derived/cohorts`, `derived/exports` and the incident record. Nothing was downloaded.
- **Writes:** this file only. All scratch work stayed in `scratch/review-q005/`, which peaked at about 181 MiB during the rebuild check and holds 64 KiB of review scripts and outputs now. Every scratch store was deleted. Free space stayed at about 143 GB. A fingerprint of the published tree (path, size, mtime and mode of every file, plus the ledger SHA256) was taken before the tests and compared again at the end. It was unchanged.

## Verdict

**Accept the corpus pilot's data surfaces as a pilot. Accept the immutability remediation only after B1–B3 below are fixed.**

Every data claim I could check independently was correct. That covers cohort selection and accounting, parent byte spans, escaped UTF-8 traces, ORACC member provenance, word/lemma/sense counts, the gloss/translation separation, exact-key crosswalks, scope labels, Parquet content and exports. I found one attribution defect (F4) and some performance reporting that understates real latency (F7).

The publication remediation fixes the exact mechanism behind the incident: deleting a snapshot and re-running the import is now refused. But it does not yet deliver its stated guarantee, "an ID that was ever published can never be published again." A crash in a short window defeats it (B1). The ledger is also never consulted when a snapshot is read or "restored" (B2). Both reproduced in scratch.

### Remaining blockers (exact)

| # | Blocker | Minimum fix | Proof required |
|---|---|---|---|
| B1 | `storage.py:323-327`: `publish()` renames the stage into place **before** it appends to the ledger. If the process dies between those steps, a readable, verifying snapshot exists with no ledger entry. After the directory is deleted, the same ID republishes with different manifest bytes. This is the incident class again. | Append a fsynced ledger entry (status `reserved` or `published`) **before** the rename, still under the lock. A ledger entry without a directory then blocks rebuilds, as intended. Also make `assert_unpublished`/`publish` refuse, or loudly adopt, any `snapshot:*` directory that is missing from the ledger. | A regression that kills the process after the rename, then shows that delete + reimport is refused. |
| B2 | `verify()` (`storage.py:71-121`), `resolve_snapshot()` (`:291-296`), `query.connect`, `persisted.*` and CLI `snapshots` (`cli.py:98`) never read the ledger. A different, self-consistent build placed under a ledgered ID verifies and resolves without complaint. The refusal message (`:306`) even tells the operator to "restore it", and nothing checks that the restored copy is the one that was published. | When a snapshot is resolved under a root, require the ledger's `manifest_sha256` to equal the served manifest's. Keep `verify(path)` relocatable for copies outside a root, but label those as "not ledger-checked". | A regression that copies a second build of the same ID into the store and shows `resolve_snapshot` refusing it. |
| B3 | `storage.py:322` + `:192-194`: the stage is made read-only (0555/0444) **before** the rename. If the rename (or anything after the chmod) fails, `shutil.rmtree(stage)` raises `PermissionError`. That masks the original error and leaves a `.pending-*` stage on disk. | Restore write permission before the cleanup rmtree (or chmod after the rename succeeds), and re-raise the original exception. | A regression that makes the rename fail and asserts the original error is raised and no stage remains. |

B1 and B2 are the difference between a store protected by an application-level convention and one that actually enforces "never republish an ID". B3 is a hygiene bug in the same code path. Everything else below is P2/P3 and is not blocking.

## Findings

Severity: **P1** breaks a stated guarantee; **P2** is a misleading result or a real failure mode; **P3** is hardening or documentation.

| ID | Sev | Where | Finding | Reproduction (scratch) |
|---|---|---|---|---|
| F1 = B1 | P1 | `cuneiform/storage.py:323-327` | Crash window between the publish rename and the ledger append. Afterwards the published ID can be deleted and republished. | `pub_fixtures.py` case A: I made the second `datetime.now()` call raise (it runs only after `stage.rename`). The result was 1 published directory and 0 ledger entries, and `verify` passed. After `rm`, `import_source` built the **same ID** with a **different `manifest_sha256`** and `reused: false`. |
| F2 = B2 | P1 | `storage.py:71-121, 291-296`; `cli.py:98`; `persisted.py`/`query.connect` | The ledger is write-side only. Readers cannot tell a same-ID replacement from the published bytes. The "Key caches by `(snapshot_id, manifest_sha256)`" contract in REPRESENTATION-MAP lets a replaced snapshot through as a new cache key, not as an error. | Case D: two independent builds of the same fixture produced the same ID with different `manifest_sha256` (`6265afcb…` in the ledger, `80e07e73…` served). I copied the second build over the first: `resolve_snapshot` accepted it. (`graph.duckdb` was byte-identical. Only `manifest.json` differed: the timestamp and build timings.) |
| F3 = B3 | P2 | `storage.py:192-194, 322` | Failure cleanup after the read-only chmod raises `PermissionError`, hides the cause, and leaks the stage. | Case B: a simulated `OSError` on rename surfaced as `PermissionError: … .pending-…/parquet`. One `.pending-*` stage (53,953 bytes) was left behind. |
| F4 | P2 | `cuneiform/oracc.py:216` | `Sense.source_locator` stores the **first attesting instance's `sig`**, which contains that instance's written form and normalization (e.g. `@ccpo%akk-x-stdbab:E₂=bītu[house//house]N'N$bīt`). It is presented as a property of the shared Sense node. For 1,416 of the 4,544 `IN_SENSE` instances (31%), the word's own `sig` differs from the one stored on its Sense. The per-instance `sig` is preserved correctly on `LEMMATIZED_AS.qualification`. Only the Sense row misattributes. | `real_checks.py` → `oracc_db.instance_sig_differs_from_sense_row_sig = 1416`. Fix: store a sense-level locator (lemma key + sense) or the first-attestation pointer, labelled as such. Do not store an instance `sig`. |
| F5 | P3 | `storage.py:304-306` | When two writers race on the same ID, the loser gets "already published (ledger) but is missing from the store; restore it", while the snapshot is present. Nothing was corrupted: 1 directory, 1 ledger entry, no leftover stages in 3/3 trials. The message is wrong, and both writers paid for a full build. | Case C, 3 trials, 2 concurrent processes each. |
| F6 | P3 | `storage.py:299-301` | A torn ledger line (a crash mid-write) makes every later publication fail with `JSONDecodeError`. This fails closed, which is correct. But there is no repair path or diagnostic. | Case F. |
| F7 | P2 | `persisted.py:41-51, 56-72`; CHECKPOINT/REPRESENTATION-MAP latency rows | The returned `latency_ms` covers only the SQL. `lookup_snapshot` hashes the whole snapshot twice (`verify()` itself, then `connect()`, which calls `verify()` again) before the timer starts. `parity` verifies 4 times. | At 300 records: `postings` reported `latency_ms` 43.1, but the end-to-end call took **232 ms**. `parity` component timings were 167/159/11 ms; end-to-end **528 ms**. `trace` with parent verification: 328–371 ms per call (it hashes the 73.9 MB parent each time). `trace_word`: 67 ms. The documented numbers are true for what they time, but a UI that shows `latency_ms` understates the actual call by about 5×. Either pass the verified manifest through or report `verify_ms` alongside. |
| F8 | P3 | `persisted.py:50`, `projections.lookup` | A caller-supplied `namespace`/`snapshot` override that cannot match the verified snapshot returns empty rows instead of an error. Example: `postings` on the eBL-300 snapshot with `namespace='oracc/ccpo'` gave 0 rows. `words` on an eBL snapshot (which has no word layer) also returns `rows: []` with no `unavailable` marker in the response. That conflicts with the rule that unavailable layers render as unavailable, never as zero. | `api_checks.py` → `wrong_namespace_postings`, `ebl_words_lookup`. |
| F9 | P3 | `cuneiform/corpus.py:248-287` | Cohort directories under `derived/cohorts` are mutable (0644/0755) and have no ledger. Snapshots are not affected, because each snapshot carries its own hash-bound `cohort.json` copy, and I confirmed all three match the derived copies. But a deleted cohort is rebuilt under the same cohort ID with a different `created_at`/`manifest_sha256`. | Inspection only. |
| F10 | P3 | `storage.py:71-121` | `manifest.json` file bytes are not covered by any hash. Only its canonical self-digest is checked. Appending whitespace to `manifest.json` still verifies, and the ledger value is unchanged. This is harmless semantically, but "byte-for-byte" claims rest on the canonical digest, not on file bytes. | Case E. |
| F11 | P3 | Current code vs. existing IDs | The five published IDs use the legacy formula (`snapshot_contract: null`). Current code mints `manifest-3` IDs, so re-importing the same cohort creates a **second** snapshot of identical content under a new ID (for example, my scratch rebuilds got `snapshot:da9b0fc9…` and `snapshot:b36f1378…`). This is correct under the new rule, but discovery and the UI will show both unless the scope or label distinguishes them. | `perf_rebuild.py`. |
| F12 | P3 | Process | The ledger backfill that adopted the five existing snapshots is not in the repository: `grep backfill` finds nothing in `cuneiform/`, `tests/` or `scripts/`. For backfilled entries, `published_at` is the manifest's `retrieved_or_imported_at` (its build time), not an observed publication time. For the two incident IDs it is the time of the **second** build. The entries carry `backfilled: true` and an `incident` note, which is honest, but this is writer-only provenance. | Ledger vs. manifests. |

## Incident (same-ID rebuild of `ce127437…` and `84971360…`)

**What I verified about the current state:**

- All 5 snapshots pass `storage.verify(path, sid)`. For each, the ledger `manifest_sha256`, the incident record's `manifest_sha256` and its `graph_duckdb_sha256` equal the files on disk now (recomputed by me). There are no unlisted files, and no file or directory has any write bit (0 writable paths in all 5).
- **ctime evidence (kernel-set, not settable by user tools):** every file I sampled across the snapshots, and the ledger, has ctime 04:59:35 EST (09:59:35Z), the moment of the backfill chmod. No inode in those snapshots has changed since then. This is the strongest evidence available that the current bytes have not changed since the remediation.
- **Before 09:59:35Z** the evidence is weaker. It consists of mtimes (forgeable) and one independent observation: the UI reviewer recorded `ce127437…/manifest.json` at 8,092 bytes with mtime 04:46:08, and the file today is 8,092 bytes with mtime 04:46:08. Nothing independent covers `84971360…` between 09:46 and 09:59Z, or the other three before 09:59Z, beyond the writer's own record.

**What cannot be established:**

- **The first-version bytes are not recovered.** No copy exists under `cuneiform-research`. The UI review (`cuneiform-ui/reviews/ui-review-v0.1.md:17`) says it ran checks on "a byte-identical copy of `snapshot:ce127437…`" kept in its workspace. I searched `cuneiform-ui`, `~/.local/share/cuneiform-ui`, `skill-workspaces` and `/tmp` for that ID and for `graph.duckdb` files over 20 MB, and found nothing. Whether that copy was the first or second version, and whether it still exists, is unknown. **Lead for the parent:** ask the UI reviewer. Even if it turns up, it would be a copy whose hash the UI reviewer recorded, not a recovery proven against a pre-incident hash, because no hash of the first version was ever recorded.
- **Self-hashes prove internal consistency, not authenticity.** The manifest digest, cohort digest, ledger and incident record are all written by the same process that built the data. A coordinated rewrite would pass all of them. Only the external MD5 for eBL (Zenodo record API), the ORACC `Last-Modified`/zip SHA from acquisition, and the CDLI receipts tie data back to sources, and those are acquisition-time records, not signatures.

**What actually enforces immutability:**

| Mechanism | Kind | Holds against | Does not hold against |
|---|---|---|---|
| Publication ledger + `assert_unpublished` | Application-level, write side only | Re-running any `import_*` after a delete (tested: refused) | Crash window (B1); any copy or restore that bypasses `publish` (B2); the ledger file being edited or deleted (it is 0644 in a writable directory) |
| `fcntl.flock` on `.publication.lock` | Advisory lock | Two cooperating writers (tested: 1 dir, 1 entry) | Non-cooperating writers. The lock file did not exist in the real store, so the backfill wrote the ledger without the lock. |
| Files 0444 / directories 0555 | OS permissions, same owner | Accidental in-place writes. `rm -rf` exited 1 and the directory survived. | `chmod -R u+w` by the owner (tested: a write then succeeded); **renaming a read-only snapshot directory** within `snapshots/` (tested: succeeded); root. These are not immutable flags (`chflags uchg`) and not a separate account. |
| `manifest-3` in new IDs | Convention | Contract changes that remember to bump `SNAPSHOT_CONTRACT` | A contract change that forgets the bump (the ledger then refuses a rebuild but still serves the old build) |

The incident record itself is accurate. It does not claim recovery, and it lists the same limits.

## Independent real-data verification (all passed unless noted)

These checks use my own code (`scratch/review-q005/real_checks.py`, `api_checks.py`), not the builder's tests.

- **Parent file:** pure ASCII (all non-ASCII is JSON-escaped). An independent sequential `raw_decode` scan found 23,289 records and one duplicate key, `K.5808` ×2, which matches the builder.
- **Cohort byte spans:** all 381 members (30 + 300 + 51) match my independent scan for `parent_index`, `parent_start`/`parent_end` and `_id`. Every payload slice is byte-equal to the parent slice. Every `order_key` equals `sha256(parent_sha:_id)`, and members are sorted by it.
- **Accounting:** eligible + excluded = 23,289 for all three cohorts (20,896 + 2,171 + 154 + 66 + 2; and for ccpo, 51 + 23,236 + 2). Duplicates are never selected. The 30-record cohort is exactly the first 30 of the 300.
- **Selection correctness for 300:** 320 parent records have an order key at or below the 300th selected key. Re-running the rule's eligibility on the 20 that were not selected gave 18 "fewer eligible positions" and 2 "fewer adjacent pairs"; **0 eligible records were skipped**. (This re-uses the builder's eligibility function. It independently checks the heap selection, not the eligibility rule.)
- **ccpo filter:** exactly 51 parent records carry a `cdliNumber` in ORACC ccpo `corpus.json`. All 51 are in the cohort, with 51 distinct P-numbers.
- **Escaped UTF-8 traces:** the CHECKPOINT spans read back exactly. `[24,411,382, 24,411,386)` is `ina]`, and `[13,442,912, 13,442,925)` is the 13 bytes `ša₂`, which decodes to `ša₂`. In a sample of 35 occurrences (25 non-ASCII readings and signs, 10 gaps or unsupported positions), all 35 `parent_trace` results were `verified`. 27 of the fragments contain `\u` escapes. Each fragment decodes to `resolved_raw` and lies inside the record's parent byte range.
- **ORACC:** the zip SHA matches its receipt. All 53 selection members (metadata, catalogue and 51 texts) are byte-identical to the decompressed zip members, with matching CRC32. My own walk over the zip members gives 6,888 words, 4,544 with a citation form, 4,544 with a sense, 1,122 distinct `(lang, cf, gw, pos)` lemma keys and 1,317 distinct lemma+sense pairs. These equal the manifest and the DuckDB counts. No `TranslationSegment` rows exist, and there are no `TRANSLATES` edges or occurrences. The only translation-like zip member is `ccpo/index-tra.json`, an index, as the source audit says. The `words` lookup returns `gloss_status: 'lexical gloss; not a translation'`. `trace_word` verified 20 of 20 sampled words against the parent zip.
- **Crosswalks:** of the 51 eBL records' P-numbers, ORACC's eBL key agrees in 51 and CDLI's in 51. The 3 ORACC/CDLI eBL keys outside the cohort (`K.15255`, `K.237`, `K.6519`) are the same in both sources and stay unresolved. **No artifact ID is shared across the three snapshots**, so there are no merges. `catalog_link('cdli:P423302')` returns one alias claim each from eBL and ORACC and one CDLI catalog artifact, and its result reads "merge: none". Claim counts match the source audit: CDLI 95/54/185, ORACC 51 CDLI + 54 eBL.
- **Scope labels:** `COHORT 300/20,896 eligible of 23,289`, `COHORT 51/51 eligible of 23,289`, `SELECTION 51` (ORACC) and `SELECTION 51` (CDLI). Each scope note says the counts are not corpus or catalogue totals.
- **Parquet and optional projections:** for every table in all 5 snapshots, manifest count = Parquet count = DuckDB count. `EXCEPT ALL` in both directions shows 0 differing rows for `edge`, `occurrence`, `claim`, `word_token`, `posting` and `ngram`. The projection config, and therefore which optional tables exist, matches the manifest. The two `selection` snapshots use the default small caps, and the cohorts use the corpus caps.
- **Exports:** in all 5 exports, file hashes match the receipts, node and edge counts match the receipts, an independent dangling-edge check finds 0, and every export binds to the current ledgered `manifest_sha256`.
- **Parity:** `ABZ480 ABZ13` at 300 records gives graph = array = index = 201.
- **Rebuild in scratch (claims check):** cohort 30 took 2.07 s at 442 MB peak RSS, with 33.2 MB payload (claimed: 2.5 s, 419 MB, 32 MB). Cohort 300 took 14.9 s at 682 MB peak, with 182.5 MB payload (claimed: 20.3 s, 632 MB, 174 MB). Table counts equal the published manifests exactly. The payload ratio is about 162× (182.0 MB / 1.12 MB), not "~155×", so the full-file estimate is about 12 GB, not 11 GB. Both are well above the 5 GiB budget, so the conclusion stands.

### Tests

```
CUNEIFORM_RUN_DISK_TESTS=1 ~/.local/share/cuneiform-research/venv/bin/python -B -m unittest discover -s tests
Ran 43 tests in 16.007s   OK            (peak RSS 227 MB)
~/.local/share/cuneiform-research/venv/bin/python -B -m unittest discover -s tests
Ran 43 tests in 13.174s   OK (skipped=5)
```

The published-tree fingerprint was identical before and after the tests. The disk tests write only to `scratch/pilot-test-*` and `scratch/publish-test-*` and remove them afterwards (confirmed). **Coverage gaps:** there is no test for a crash between rename and ledger (B1), ledger-checked reads (B2), failure cleanup after the chmod (B3), concurrent writers, or a torn ledger.

## Resource limits and performance claims

- **Limits in code:** `Config` defaults to 5 GiB owned and a 10 GiB reserve, and `guard` checks the whole root (including the venv). Admission estimates are 200× payload + 64 MiB for cohorts and 50× + 64 MiB for ORACC; the observed figure is ~162×. DuckDB uses `memory_limit` 1 GB for corpus imports, `threads=1` and `max_temp_directory_size='0B'`, so it does not spill to disk: an oversized import fails rather than swapping. Caps: 512 MiB cohort payload, 4 MiB per record, 16 MiB per ORACC member, 256 MiB per ORACC selection. Projection hard caps are 2M positions and 20M rows.
- **Honest:** runtime size (479 MiB; `du` shows 478.9 MiB), import times and memory, export sizes, and the not-attempted full-corpus scale.
- **Understated (F7):** per-call latency. Verification dominates every read path at about 0.1 s per full hash of a 182 MB snapshot, run 2–4 times per call. Trace adds a 73.9 MB parent hash per call.
- **Not proven:** memory headroom beyond 300 records. Peak was 682 MB against the 1 GB DuckDB cap, with no spill allowed. A cohort of about 3× the size will probably fail closed. That is acceptable, but it is unmeasured.

## Scientific and rights coverage limits (not bugs)

These are accurately disclosed in SOURCE-AUDIT and CHECKPOINT. I list them so they are not mistaken for defects or for results:

- Cohorts are hash-ordered samples filtered for usable text. They are not representative, and the counts are not corpus frequencies (the scope labels say so).
- In the ATF grammar subset, hyphenated words, determinatives, compounds and numerals are opaque blockers. That makes ATF reading motifs sparse. Strict-policy windows are 0 because eBL asserts no positions as intact+certain.
- eBL `signs` are reading-derived labels, not visual evidence. Signs↔ATF alignment is limited to observed line-count equality (292/300). There is no translation alignment.
- ORACC: one project (ccpo), 51 texts. Graphemes are unmapped. Senses are English lexical glosses, not translations, and the JSON contains no translation text. Lemma IDs are scoped per snapshot and per dialect tag (`akk-x-stdbab` and similar), so "the same" lemma in another project or dialect is a separate node by design. eBL keys come from positional pairing of two parallel lists. That pairing looks right in the 205 multi-resource entries I sampled, but it is a convention, not an explicit link.
- CDLI: catalogue metadata only. No inscriptions were fetched.
- No compositions, passages, dates, joins, images or embeddings.
- **Rights:** the eBL conflict (CC BY 4.0 on the record vs. CC BY-NC-SA 4.0 in the data paper) is unresolved. Manifests carry `unresolved-conflict` and the note "not cleared; private local research inspection only". The ORACC CC0 statement and the CDLI terms are recorded but have not been legally reviewed. Nothing here authorizes redistribution or publication.

## Evidence trust levels

| Evidence | Trust |
|---|---|
| My recomputed hashes, independent parent scan, zip comparison, Parquet `EXCEPT ALL`, crosswalk joins, trace samples, scratch fixtures, test runs | Reviewer-observed |
| Kernel ctime 09:59:35Z on snapshot inodes; UI reviewer's size/mtime for `ce127437…/manifest.json` | Independent, but partial |
| Zenodo MD5/size match, ORACC `Last-Modified`, CDLI receipts | External at acquisition time (receipts are self-hashed by the writer) |
| Manifest/cohort/selection self-digests, ledger, incident record, backfill (`published_at`, adoption), CHECKPOINT timings | Writer-only |

## Reproduce

```sh
cd /Users/danieliser/Projects/Fun/cuneiform-research
PY=~/.local/share/cuneiform-research/venv/bin/python
S=~/.local/share/cuneiform-research/scratch/review-q005
PYTHONPATH=$PWD $PY -B $S/real_checks.py     # read-only; ~2 s, ~1.5 GB peak (decodes the parent in one string)
PYTHONPATH=$PWD $PY -B $S/api_checks.py      # read-only; ~15 s
PYTHONPATH=$PWD $PY -B $S/pub_fixtures.py    # scratch stores only (scratch/review-q005/stores), removed at the end
PYTHONPATH=$PWD $PY -B $S/perf_rebuild.py cohort-4e86952ece628b06f9280fe72aafe65d snapshot:84971360d212834e0b7acbeac1e56abe   # writes ~180 MiB to scratch/review-q005/perf; delete it afterwards (chmod -R u+w first)
```
