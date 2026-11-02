# Independent linked-projections review v0.1

Reviewed commit `9eab086698158a097615170ae9188797dbe2b3fe` on 2026-11-02. HEAD matched and the checkout was initially clean. Read applicable global/Projects AGENTS (no project-local AGENTS found), README, REPRESENTATION-MAP, final CHECKPOINT section, SPEC-v0.2, previous implementation review, specification review and disposition. This is a review, not implementation approval or a full-SPEC acceptance.

Only this report was written. No implementation edits, delegates, installs, downloads, corpus writes, remote/publication actions or persistent integration tests. All reproductions used `/Users/danieliser/.local/share/cuneiform-research/venv/bin/python -B` and in-memory DuckDB with spill disabled. No reserve bypass. Filesystem reported 1,754,168 KiB available, below 3 GiB.

## Prioritized findings

### 1. P2 — The public trace helper can attribute another input's bytes/hash/rights to an occurrence

**Location:** `cuneiform/query.py:53–65`, especially 58–65; schema-2 binding available at `cuneiform/schema.sql:24`.

`trace_rows` chooses a record from caller-supplied raw bytes using the stored locator, checks only the selected token string, and returns the caller's hash and rights alongside the database's source identity. It never checks the raw hash against the occurrence's `source_binding`, nor even verifies the supplied manifest hash against supplied bytes. In the newly documented shared-connection workflow, choosing the wrong input can silently produce a false provenance packet whenever the same token occupies the same offset. The helper is explicitly recommended in REPRESENTATION-MAP.

**Reproduced without canonical edits:** ingest FIRST with `1. A B` in ebl/test-snapshot and SECOND with `1. A C` in other/second. Trace FIRST's A using SECOND's raw and manifest. Result: `source_key='FIRST'`, `resolved_raw='A'`, SECOND's SHA256, and SECOND's rights. The stored source binding still correctly holds FIRST's SHA256. No error.

**Suggested fix:** on schema 2, bind the occurrence's source record to its snapshot/raw hash, compare the supplied bytes and manifest to that binding before resolving the token, and reject mismatches. Preserve a deliberate legacy-schema path. Rights cannot be authenticated from a raw hash alone; use the matching verified snapshot manifest or explicitly label caller-supplied attribution.

**Scope:** inherited helper behavior newly relevant to linked multi-input API use; verified single-snapshot disk `trace()` ordinarily supplies matching data itself. No evidence of corruption in existing snapshots or the current demo.

### 2. P2 — Graph and array APIs silently pool scopes that indexed lookup requires callers to separate

**Location:** `cuneiform/query.py:17–38,43–49`; contrast `cuneiform/projections.py:128–149`.

`motif(db, ...)` and `array_count(db, ...)` accept a shared connection but filter only by field. There is no namespace/snapshot selector or multi-scope refusal. The index requires both. On a connection containing two textual namespaces/snapshots, graph and array totals silently aggregate them, including the graph's witness/artifact/sequence denominators, while the equivalent scoped indexed query counts one. Graph output does not identify this pooling policy. README's statement that all queries select one explicit snapshot is therefore too broad for the Python API.

**Reproduced:** ebl/test-snapshot contains one `A B C`; other/other-snapshot contains another. Scoped ebl index count = **1**, graph = **2**, array = **2**. Neither matcher crosses a line or stitches the sources together; this is scope pooling, not a false adjacency or ID collision.

**Suggested fix:** accept and enforce the same explicit scope for graph/array queries, or reject multi-scope connections and document the single-snapshot restriction. Preserve schema-1 path compatibility. Include a two-text-source parity test; the current mixed eBL/CDLI fixture has text only on eBL and cannot expose this discrepancy.

**Scope:** inherited query limitation exposed by the linked shared-connection organization. Current `demo` and persisted `query` use one input snapshot, so this does not invalidate their reported 6/6/6 result.

### 3. P2 — Strict wildcard eligibility differs between graph and n-gram projections

**Location:** `cuneiform/projections.py:78–91`; `cuneiform/query.py:30–34`.

The strict n-gram builder requires every position to have a non-null reading as well as intact/certain flags. The graph matcher requires the flags but allows a wildcard to cover a null-reading position. An intact, certain but unsupported compound can thus match `?` in the graph and disappear from the indexed result. Unsupported parsing and physical/editorial uncertainty are distinct axes; the schema and validator allow this state.

**Reproduced:** ingest `1. A |B.C| D`, set its three positions to preservation=intact and certainty=certain in memory, validate and rebuild. The compound remains kind=unsupported, reading=NULL. Strict `A ? D`: indexed count **0**, graph count **1**. No positions were removed or concatenated. This uses explicit test annotations, not a claim that the current adapter supplies certain physical evidence.

**Suggested fix:** choose and document one strict wildcard rule, then implement it consistently. If every strict window requires readable positions, reject null readings in graph strict matching too. If explicit wildcard positions may be intact but opaque, separate physical eligibility from reading eligibility in n-gram construction. Test unsupported positions as well as uncertain readable positions.

**Scope:** default imported real-source positions currently have unknown/unmarked flags, so current strict real-source counts remain zero; the discrepancy arises once the supported in-memory certainty-edit/rebuild path is exercised.

## Minimal reproduction for findings 1–3

Run from the repository with the existing interpreter; this writes no fixture or database:

```sh
/Users/danieliser/.local/share/cuneiform-research/venv/bin/python -B - <<'PY'
import sys
sys.path.insert(0, 'tests')
from test_foundation import build as canonical_db
from cuneiform.adapters import Builder, ingest
from cuneiform.model import digest
from cuneiform.projections import build, lookup
from cuneiform.query import motif, array_count, trace_rows
from cuneiform.storage import validate_graph

first = b'{"_id":"FIRST","atf":"1. A B"}'
second = b'{"_id":"SECOND","atf":"1. A C"}'
db = canonical_db(data=first)
ingest(Builder(db, 'second', 'other'), 'ebl', second)
oid = db.execute("SELECT t.id FROM token_context t JOIN source_record r ON r.id=t.source_record_id WHERE r.source_key='FIRST' AND t.position=0").fetchone()[0]
r = trace_rows(db, second, {'source':'ebl','raw_sha256':digest(second),'rights':{'status':'different-source'}}, oid)
print('trace:', r['source_key'], r['resolved_raw'], r['raw_sha256']==digest(second), r['rights'])
db.close()

db = canonical_db(data=b'{"_id":"FIRST","atf":"1. A B C"}')
ingest(Builder(db, 'other-snapshot', 'other'), 'ebl', b'{"_id":"SECOND","atf":"1. A B C"}')
build(db)
print('scope:', lookup(db,'motifs','["A","B","C"]',namespace='ebl',snapshot='test-snapshot')['count'], motif(db,['A','B','C'])['occurrences'], array_count(db,['A','B','C']))
db.close()

db = canonical_db(data=b'{"_id":"T","atf":"1. A |B.C| D"}')
db.execute("UPDATE occurrence SET preservation='intact',certainty='certain'")
validate_graph(db)
build(db)
print('strict:', lookup(db,'motifs','["A","?","D"]',namespace='ebl',snapshot='test-snapshot',policy='strict')['count'], motif(db,['A','?','D'],strict=True)['occurrences'])
db.close()
PY
```

Observed: `trace: FIRST A True {'status': 'different-source'}`, `scope: 1 2 2`, `strict: 0 1`.

## Executed evidence and coverage

- Full existing suite: `CUNEIFORM_RUN_DISK_TESTS=0 .../python -B -m unittest discover -s tests -v`: **28 tests in 10.034s, 27 passed, one disk test skipped**. Actual retained eBL test ran. Previous four implementation-review regressions remain green.
- CLI subprocess smoke, all with `-B`: wildcard motifs with limit=2/offset=2 returned total=11, two rows, next_offset=4; combined alias lookup returned two distinct claims; translation substring lookup returned one unresolved-span string. Real CLI parsing/dispatch was exercised, not just functions.
- **Rollback after mutation:** wrapped the in-memory connection to raise RuntimeError immediately before `INSERT INTO projection_registry`; rebuilt with ngrams disabled, so existing derived tables had already been dropped/replaced in the transaction. Rollback restored the exact previous registry row and the old ngram table (nine rows in that test). This extends the suite's pre-mutation budget-refusal evidence to an actual mid-transaction exception. Not evidence of power-loss recovery or concurrent-writer safety.
- **Independent traversal:** on a simple A B C fixture, deleted NEXT edges in memory and rebuilt. Index/array/graph A B counts became **1/1/0**. Graph execution genuinely depends on adjacency edges; arrays and index derive order from canonical positions. All still share adapter interpretation and canonical order, so parity does not independently validate parsing or philology. The validator checks existing NEXT edges, not their completeness.
- **Schema-1 runtime compatibility in memory:** loaded the previous commit's schema and adapter source through `git show`, executed them in memory with parser conservative-2, then used current motif/array functions. Registry remained `('1','conservative-2')`; both A B counts were 1. No schema-2 views were injected. Suite additionally checks mocked legacy/schema-2 payload inventories. This is not disk-backed compatibility proof.
- Existing tests cover hand counts, overlaps, source wildcard blockers, strict readable-position exclusions, sign/reading separation, canonical byte spans, reverse navigation, ambiguous aliases, unresolved translations, deterministic rebuilds, canonical-edit staleness and optional assets. The retained sample gives ABZ215/ABZ13 counts **3/3/3** and nine unresolved translation strings; no word alignment or English meaning is inferred.

## Identity, invalidation, bounds and export assessment

Canonical occurrence IDs are retained across organization links. Reading keys bind namespace/snapshot/field; sign keys retain their separate source-derived identity. Match-span IDs bind endpoints and remain stable across configuration changes; materialization IDs additionally bind projection configuration. Catalog aliases remain source-attributed claims and exact target candidates, without a merge or independence claim. Portable translation placement uses PLACED_IN_SEQUENCE with unresolved alignment, not TRANSLATES. These are appropriate distinctions for this slice.

Canonical hashing includes source bindings, edges, claims and uncertainty. Normal configuration changes through `build(config)` replace projections and change IDs; budget failures preserve old assets. One robustness limit: `assert_fresh` checks revision and canonical hash only. Directly altering registry config (e.g. lengths to [2]) leaves the old ID accepted as fresh; a previously valid length-3 lookup then says not configured. It does not authenticate/recompute config/source hashes or derived contents. This requires out-of-band SQL mutation, not a supported config change, so it is recorded as a limitation rather than an additional release defect. Frozen manifests' graph-file checksum provides a separate disk integrity check, not authenticated provenance.

Lookup output is paged to max 100; exact indexed totals are independent of page size. Bind parameters keep user values out of SQL syntax. Projection expansion has explicit position/row ceilings and no Cartesian alternatives. These are output/materialization bounds, not a general CPU/RSS guarantee: canonical hashing reads every canonical row before the position check, the adapters ingest before projection admission, and graph matching fetches all internal matches plus per-position evidence queries. DuckDB's memory setting does not cap Python objects. The docs already acknowledge bounded inputs and non-corpus-scale performance; no new timeout or corpus-scale claim should be made. Source-span lookup deliberately exposes only its first bounded page, as documented.

Schema-2 snapshot identity includes projection revision/configuration; mandatory assets plus enabled optional tables determine the inventory. The generic export loop includes projection_registry, source_binding and enabled posting/ngram tables. Views are SQL definitions rather than redundant materialized assets. The current legacy inventory subtraction matches the actual previous schema. Portable nodes/edges preserve identifiers and contextual qualifications; no FalkorDB execution occurred.

**Still unverified:** new schema-2 persistent import/reuse/relocation, optional Parquet readback, frozen-database rebuild refusal on an actual persistent connection, peak disk consumption and failure recovery on disk. The checkpoint correctly marks these unverified. Existing mock payload checks cannot establish Parquet validity. No persistent test was attempted, even if free space might transiently change. The 3 GiB admission guard remains a required boundary, not a finding to bypass.

## Safe handoff

Conditional acceptance as a narrow in-memory linked prototype, with the three P2 API/count-policy findings above. Current single-input demos and synthetic/default count claims are supported by rerun evidence. Fix or explicitly restrict the affected Python API paths before claiming scope-equivalent graph/index counts or cross-source provenance-safe traces. No P0/P1 defect was demonstrated in the current default CLI path.

ORACC import, word/lemma/sense population, actual translation alignment, compatible-alternative bounds, interpretation branches, full ATF grammar, images, MCP, bulk corpora, FalkorDB and full research/SPEC completion are openly deferred features, not regressions discovered by this review. Rights remain unresolved. Neither green structural tests nor this review establish linguistic correctness, independent scholarly corroboration, authenticated source provenance, schema-2 disk delivery or permission to publish.
