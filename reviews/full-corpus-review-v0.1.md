# Q-023 full eligible eBL import — independent acceptance review v0.1

- **Reviewer:** Q-023 review sub-agent (independent of the writer; no subagents), 2026-11-05 ~10:58–11:39Z.
- **Under review:** research `5c7a01b` (code), `057a0b7` (tests), `aabe567` (atlas rev 6, docs, queue); UI `2be365e` + `4dcc416` (pin `057a0b7`); `snapshot:965aa26214dc0388dd3af1be367d2acc` (manifest `44a20685…`), `cohort:4e532850276b7960e67f149f6463afcf`, adoption of `cohort:4e86952e…`, `cohort:9abad6ce…`, `cohort:ea91baae…`.
- **Mode:** read-only on canonical data, code and services. No rebuild, download, restart or outreach. The only write outside scratch is this file. QUEUE and atlas are unchanged; nothing was committed.
- **Scratch:** `~/.local/share/cuneiform-research/scratch/review-q023/` (INDEX.md; 0.5 MB retained). Peak additional physical disk was about 0.5 GB, because the 9.5 GB attack copy was an APFS clone (`cp -c`, free space changed by 128 KB). Free space stayed at 201 GiB or more.

## Verdict

| Surface | Decision |
|---|---|
| Full-text import (`snapshot:965aa262…` + `cohort:4e532850…` + adoptions) | **ACCEPT** for the authorized local research scope: every eligible record of the fixed eBL release Zenodo 10018951 `fragments.json` under `usable-text-v1`, parsed by `conservative-3`. |
| Local UI (`4dcc416` on pin `057a0b7`, live on 8740) | **ACCEPT** for the local cooperating-writer workbench. Four non-blocking findings (N1–N4). |
| Integrity-cache tradeoff (>2 GiB: stat + manifest bytes + ledger per request, full re-hash at discovery and hourly) | **Acceptable** under the local cooperating-writer threat model (details below). |

**Blockers: none.**

This accepts software and data integrity only. It makes no claim of scientific validity. "Full" means the eligible records of one fixed eBL release. It is not all of eBL, ORACC or CDLI, and it includes no images and no validated similarity method.

## 1. Canonical stores before and after

`fingerprint.py` covered `snapshots/ derived/ raw/ receipts/ trust/ evidence/ runs/`: 414 entries, each with size, mtime_ns, ctime_ns, inode, mode, nlink and the sha256 of every file (`--hash-all`, 9.5 GB hashed once, 6.5 s).

- `fp-before.json` (10:58Z) vs `fp-after.json` (11:36Z, full hash again): **0 differences**. A stat-only `fp-final.json` taken after the last read-only DuckDB attach also showed 0 differences.
- The six earlier snapshots match the earlier independent reviewer's fingerprint (`scratch/review-q021-r3/fp-after.json`, 2026-11-03): **170/170 entries identical** (size, mtime, mode, sha256). Only `.locks/` and the ledger differ.
- Snapshot ledger: 9 lines. The first 7 hash to `6d359b74907bb3ae…`, the earlier reviewer's value. The 2 appended lines are reserve and commit of `965aa262…` with manifest `44a20685…`.
- Full snapshot: all 25 files hash equal to their `manifest.files` entries, and their sizes sum to `snapshot_payload_bytes` 9,544,585,737.

## 2. Adoption of the three pre-ledger cohorts

For each adopted cohort, `manifest.json` sha256 equals the `cohort.json` bound inside its snapshot (`d9412778…` → `84971360…`, `882b2055…` → `ce127437…`, `cc874259…` → `c316e7cb…`). Each value also matches the 2026-11-03 reviewer fingerprint, and each matches the `manifest_file_sha256` in the cohort ledger `adopt` rows. Each `payload.json` equals its snapshot's `raw`. Bytes are preserved. Note: the adopted directories keep their original writable modes (0755/0644), unlike new 0555/0444 entries. That is consistent with "do not touch", but they are not chmod-protected (non-blocking).

## 3. Data coverage and accounting, recounted from raw

`recount.py` loads the parent independently with `json.load`, not the project's streaming scanner:

- Parent 73,854,507 B, sha256 `4e970d87…`, md5 `71538e2d…`: a top-level array of **23,289** records.
- cohort-2 manifest: 20,896 members + 2,393 excluded = **23,289**. Indices are unique and cover `range(23289)` exactly. For every record, the slice `[parent_start, parent_end)` hashes to `record_sha256`, decodes equal to `data[index]`, and has `_id == source_key` (**0 mismatches**). The bytes between records are exactly `,` (23,288 times), with `[` before the first and `]` after the last. This is a byte-exact partition of the parent.
- Reasons: 2,171 fewer positions, 154 fewer pairs, 66 no numbered ATF line, 2 duplicate. A heuristic "numbered line" regex finds none in the 66 records and some in every other excluded record. Its 3 misses among members are `a+1.` line labels, which is a heuristic gap, not a bug.
- **Duplicate semantics:** `K.5808` appears at indices 999 and 1000, and the two copies are **byte-identical**. Rule `require_unique_source_key` excludes both, so this text is absent from the full snapshot. That is a conservative coverage choice, not a defect (caveat C3).
- Eligibility recomputed from the imported rows (my SQL over `occurrence`/`line`/`sequence_version`): all 20,896 members have at least 10 eligible positions (minimum 10) and at least 2 eligible adjacent pairs (minimum 2). Maximum member size is 144,909 B, under the 262,144 cap. No adapter rejections.

## 4. Rows, uniqueness, graph, index and arrays (`dbcheck.py`, own SQL, read-only)

- All 22 base tables: `count(*) == count(distinct key)` and both equal the manifest counts. `nodes` view: 5,317,336 unique. Edges with a missing source or target node: **0**.
- **Closed form, all source-policy n-grams:** for each field and length n=2..5, `count(ngram) == Σ_lines max(0, L−n+1)`, equal in all 8 cases (for example signs/2 2,403,529; atf/5 689,774). Postings: atf = positions with a reading (454,057), signs = positions with a reading and a `MAPS_TO_SIGN` edge (2,429,757). There are 0 sign readings without a sign edge. Positions per line are contiguous 0..L−1.
- **Motifs:** 28 cases. These are the writer's 8 plus my own stratified picks: bigram ranks 1/10/100/1000/10000 and a singleton per field, trigram ranks 1/50/500, and a wildcard singleton. My `lead()` window count equals the `ngram` index count in **28/28** (for example `ABZ411 ABZ411` 29,166; `ABZ480 ABZ13` 7,170; `ABZ579 ABZ13` 5,363; `ina E₂ NA` 536; `ṬU ? ABZ75` 1). Graph-engine parity was checked live (§7).
- **Offsets, every position (`offsets.py`):** for all **4,542,153** occurrences, the UTF-8 slice `[start_byte, end_byte)` of the decoded parent field reproduces `raw` exactly. That is 0 mismatches across reading, unsupported, gap and derived_sign, including 597,080 non-ASCII tokens. All 629,335 line spans fall inside their field, and every occurrence falls inside its line span.
- **Subset consistency (`subset.py`):** all 300 records of `snapshot:84971360…` are present. Position tuples (field, line ordinal and label, position, raw, kind, reading, preservation, certainty, byte span) 80,823 = 80,823, and n-gram windows 223,799 = 223,799, both with `EXCEPT ALL` = 0 in each direction. Whole-snapshot `ABZ480 ABZ13` is 201 → 7,170, as expected for a superset.
- Parquet: the writer's row-hash equality covers all 22 files. I did not re-hash the Parquet contents a second time. My full file sha256 pass (§1) binds them to the manifest, and the DuckDB checks above bind the table contents.

## 5. Why strict = 0 (semantics, not an import bug)

The data has **no** position with `preservation='intact'` and none with `certainty='certain'`: 0 strict-eligible positions, and 0 strict postings or n-grams. The cause is the adapter (`cuneiform/adapters.py:137-138`):

- preservation is `lost` if restored, `damaged` if `#`, otherwise `unknown`;
- certainty is `uncertain` if `?`, otherwise `unmarked`;
- derived signs are always `unknown`/`unknown`.

So `strict` is structurally empty for every eBL snapshot, whatever the data contains. It is an unavailable layer, not evidence that no pattern exists. The README and CHECKPOINT say so ("export never asserts intact+certain").

The UI handles this well. A strict query on the full release shows "0 matching windows", then **"Strict = 0 here because no signs position in this dataset is marked intact AND certain by the source (eBL does not assert certainty from an absence of editorial marks). See Coverage → position states"**. The Coverage tab has a "Position states (why strict may be empty)" table. Parity reads index 0, graph 0.

Spec gap (owner decision, not a defect): SPEC-v0.2 §169 wants strict to exclude *restored and damaged* readings. Under the usual ATF convention, an unmarked sign is read as preserved and certain as edited. Treating unmarked as `unknown` makes that view impossible. A third policy (for example "edited-unmarked": no `[ ]`, `#` or `?`) would be a new projection and policy decision. Do not infer `intact` silently.

## 6. Integrity-cache tradeoff (UI, snapshots above 2 GiB)

Code (`server/bridge.py`): each request stats every file (size, mtime_ns, inode, ctime_ns) before opening and after closing. It also compares `manifest.json` bytes with the hash taken at verification and runs the backend `publication_of(entry, manifest, 'require')`. Discovery (every 30 s) re-hashes everything on any stat or ledger-key change, and also re-hashes on a routine schedule when unchanged for more than 3,600 s.

Attacks on an APFS clone, through the real consumer path (`Backend` + `Explorer`, pin `057a0b7`; `attack.py`, results in `attack-results.md`):

| Case | Result |
|---|---|
| A1 same-length byte write in `graph.duckdb`, mode and mtime restored | refused (ctime); discovery's full re-hash then **fails** the snapshot; restoring the byte → ready |
| A2 same-size Parquet replaced by rename, mtime restored | refused (inode) |
| A3 same-length `manifest.json` edit, times restored | refused |
| A4 extra file in the entry; A5 hard link created (no byte change) | refused |
| L1 commit line removed; L2 same-length edit of the commit's `manifest_sha256`; L4 second reservation appended | refused (reserved / conflict / conflict) |
| L3 torn tail appended | served with an explicit "unterminated final ledger record" note |
| T1 byte write during a query | result discarded after close (409) |
| O1 metadata-preserving payload change (simulated by re-seeding the fingerprint) | **served** until the routine re-hash, which then retired the version, and later requests were refused |

An ordinary user process cannot change file bytes without changing ctime. ctime cannot be set with `utimes`; that takes a clock change or raw-device writes (root). So per-request detection covers every non-root mutation. The remaining gap is about one hour for an owner who deliberately preserves all metadata, or for silent media corruption. That is outside the accepted threat model, and the UI labels it truthfully on the dataset ("bounded-per-request … does not re-hash the payload") and on each request (`timing.breakdown.per_request_check`). Versioning, the 409 path and cache invalidation fail closed. One liveness defect: N1.

## 7. Live workbench 127.0.0.1:8740 (sequential read-only probes `live.py`; browser pass via a private preview tab, closed)

- `/api/status`: 7/7 ready. Backend `057a0b7`, `pinned_export: true`, `dirty: false`. The pin export matches `git show 057a0b7:<path>` (22/22 files, no extras). The full snapshot is titled `ebl · FULL ELIGIBLE 20,896/23,289 · ebl-zenodo-10018951-fragments.json · 965aa26214dc`, with version `44a20685…`, the full scope note (release, sha, rule, the 2,393 exclusions by reason, conservative-parse caveat) and accounting `complete-partition`.
- `ABZ480 ABZ13` (signs/source/index): **7,170**, 25 rows, truncated, next_offset 25. End to end **608 ms** (first request; writer 340–430 ms). With parity: index 7,170 = graph 7,170, **3.74 s** (writer 1.3–2.7 s). Graph engine 2.67 s. Last page `offset=7160`: 10 rows, not truncated. `limit=101` and `offset=100001` → 400.
- Postings `ABZ579`: 91,000 (194 ms). Report 765 ms: 5,317,336 nodes; 12,311,771 portable edges (= 12,167,645 edges plus provenance relations). Coverage pages through 20,896 records. SignType `ABZ411` neighborhood: 81,301 exact in-edges with a "+N hidden" aggregate (679 ms).
- Parent traces for 5 kinds I picked myself (escaped Unicode reading `DIŠ` → `DIŠ`, escaped unsupported `{giš}KIŠIB.LA₂`, gap `[...]`, derived `ABZ575`, signs unsupported `KISIM₅×GA` → `KISIM₅×GA`): all `verified`. In each case the returned parent byte span, sliced from the raw parent and JSON-decoded, equals the token. Each took **6.4–7.4 s** (the backend trace re-hashes 9.5 GB). Of the members' parent slices, 20,865 of 20,896 use `\u` escapes.
- Guards: stale version → 409 `dataset-version-changed`; foreign Host → 421; foreign Origin → 403; `/api/falkordb/query` → 403 (arbitrary Cypher disabled); FalkorDB load of the full snapshot → 400 "graph too large … 5317336 nodes / 12311771 edges; cap 150000/400000" (expected). Browser stays disabled. Internet egress was not probed, by instruction.

## 8. Scaling code changes (`5c7a01b`) and crash/retry

- `accounting()` proves a partition (unique, disjoint, in range, and eligible + excluded = parent). `verify_cohort` re-reads every excluded slice. Tests cover duplicate, overlap, range, count and reason disagreement, and a re-signed tamper of an excluded hash or record.
- Partition-first lookups (`occurrence`, `span`, `postings`, `SCOPES_SQL`) are equivalent to the old SQL on the fixture (test). On the full release they keep the UI within its 512 MB bound (live results above). Note: `postings` drops a posting whose occurrence is missing from `token_context` without adjusting `truncated`. That cannot happen with validated data (0 dangling, §4); cosmetic.
- `guard_free` runs every batch and every 5,000 projection lines. A mocked mid-build refusal publishes nothing (test). The memory string is validated by regex. Hard caps of 12M/80M admit 4.54M positions and about 15.2M derived rows.
- **SIGKILL, my own repro** (`full_import_interrupt.py` from a clean export, on a clone of the writer's stage root with a new 800-record cohort `cohort:d06ce818…`): kills at 6 s and 20 s left 2 orphan `.pending-*` stages, no ledger record, no torn tail. The rebuild (35.5 s) published `snapshot:c70dac49…` (ledger: one reserve plus one commit), and `publication-clean-stage` removed both orphans. This matches the writer's evidence. The reserve→commit window was not killed here; Q-020 R3 tests cover it.

## 9. Tests and checker (run by this reviewer)

| Command (cwd) | Result |
|---|---|
| `git archive 057a0b7 \| tar -x -C scratch/review-q023/export-057a0b7`; `~/.local/share/cuneiform-research/venv/bin/python -B -m unittest discover -s tests` | Ran 75, **OK (skipped=30)**, 14.8 s |
| same export, `CUNEIFORM_TEST_MAX_TOTAL_GIB=41 CUNEIFORM_RUN_DISK_TESTS=1 …/venv/bin/python -B -m unittest discover -s tests` | Ran 75, **OK, 0 skipped**, 42.9 s |
| same export, `CUNEIFORM_RUN_DISK_TESTS=1` only (default 5 GiB budget) | Ran 75, **FAILED (errors=29)**: `storage byte budget exceeded` at admission (root > 5 GiB). This is by design and is recorded by the writer; see N4. |
| `cuneiform-ui`: `bin/cuneiform-ui test` (pin 057a0b7) | Isolation checks **24 ok**, 0 FAIL (internet egress unprobed by design); unit/HTTP **Ran 44, OK**, 0 skipped, 158.8 s |
| research checkout `aabe567` (no code diff from `057a0b7` under cuneiform/, tests/, fixtures/): `python3 scripts/check_model_atlas.py` | `model atlas: OK` |
| `TMPDIR=<scratch> …/venv/bin/python -B scripts/check_model_atlas.py --runtime` | `model atlas: OK (runtime population checked)` |
| `TMPDIR=<scratch> python3 scripts/check_model_atlas.py --self-test` | `65/65 cases behaved as expected; real files untouched` |

The atlas correctly holds `snapshot:965aa262…` as `pending-review`, with the q023 writer runs at `read_back: false`. The two runs above match the writer's counts.

## Findings

Blockers: **none**.

**Non-blocking (software):**

- **N1 (low, UI liveness, fail-closed).** If a per-request ledger check retires a ready snapshot (for example `reserved`/`conflict`) and the ledger returns to its earlier bytes before the next 30 s scan, the dataset never re-verifies. `_check_unchanged` copies `@ledger` from the stored fingerprint, and `_retire` leaves `ds.fingerprint` as it was. The next `_consider` therefore sees `changed=False`, and `not-yet-available`/`refused` is neither due nor routine. Repro: `attack.py` case L1 then N-stuck. Remove the commit line, query (refused), restore the identical ledger bytes, run `discover()` twice → still `not-yet-available`; only a restart (simulated with `ds.fingerprint = {}`) recovers it. Impact: a spurious outage until restart. No wrong data is served. Fix: on a typed per-request retirement, store the ledger key observed at that read (or clear `ds.fingerprint`) so the next scan re-evaluates.
- **N2 (low, UI label).** With *Strict* selected, the "Frequent in dataset" panel (`web/app.js:439`) says "No indexed signs postings in this dataset." The full snapshot has 2.88M source postings; strict is empty only because no position is marked intact and certain. Suggested text: "No strict-policy postings: no position is marked intact AND certain (see Coverage → position states)". `/api/top` with strict returns empty lists and no note.
- **N3 (low, wording).** The generic authority line still says "Backend-verified snapshot (manifest + every file hash checked by storage.verify). Opened read-only per request." (`server/bridge.py:145`). README line 41 still says each response includes "re-hashing every snapshot file", and the `_reverify_bytes`/`run` docstrings say the same. The neighbouring "Per-request check" row is accurate. "re-verified in the background at most every 1 h" should read "about every hour (when the snapshot is unchanged; immediately after any stat or ledger change)". The strict note attributes the empty state to eBL ("eBL does not assert certainty…"), but the cause is this parser's mapping (`adapters.py:137-138`). Suggested text: "the conservative-3 parser does not infer intact/certain from absent editorial marks".
- **N4 (low, docs).** The AGENTS.md test command with `CUNEIFORM_RUN_DISK_TESTS=1` alone now yields 29 errors on this runtime root. Name `CUNEIFORM_TEST_MAX_TOTAL_GIB=<authorized budget>` next to that command in AGENTS.md/README.

**Source-coverage and model caveats (not bugs):**

- C1: Strict is structurally unavailable for eBL (§5). The spec's intended strict view (exclude restored and damaged readings) needs an owner decision on a new policy.
- C2: 2,393 of 23,289 records are excluded by rule (§3). Counts are frequencies of represented positions in a conservative parse: 914,921 atf positions are `unsupported` against 454,057 `reading`, so ATF motifs are sparse and `signs` carries most motifs.
- C3: Both byte-identical `K.5808` copies are excluded.
- C4: No word, lemma or sense layer (export has none). 23,984 translation segments, all `unresolved-span`.
- C5: ORACC is ccpo only (51) and CDLI is the 51-record crosswalk; no images; no similarity method. FalkorDB cannot hold the full graph; bounded DuckDB neighborhoods do.
- C6: eBL rights conflict unresolved; private local inspection only.

## Next steps (parent)

1. Record acceptance in QUEUE Q-023. Set the q023 runs to `read_back: true` where this review re-ran them (§9: in-memory 75 OK, 30 skipped; disk 75 OK, 0 skipped, 42.9 s; checker OK/runtime OK/self-test 65/65; UI 24 + 44 OK). Move `snapshot:965aa262…` to `accepted` in `corpus_snapshots`, citing this file and `aabe567`.
2. Small UI fixes N1–N3 (one round, no re-pin needed). N4 is a doc line.
3. Optional owner decision on C1, a third evidence policy.
4. The writer's 3.4 GiB `scratch/q023-full-import/stage-root/` may be removed now (owner decision). My scratch `scratch/review-q023/` (0.5 MB) is removable after the parent has read this review.
