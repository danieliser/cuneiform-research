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
