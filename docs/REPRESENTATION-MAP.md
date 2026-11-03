# Linked representations, revision linked-1

Canonical source bytes and parsed assertions are authoritative for this prototype. Projections reorganize those assertions; they neither validate readings nor fill missing linguistic layers. Schema 2 / parser conservative-3 / projection linked-1 supersede the previous implementation, not its frozen snapshots. The parser revision additionally makes unsupported exported-sign tokens blocking (e.g. `B/C` is not a sign identity).

| Organization | Kind | Link / scope |
|---|---|---|
| `source_record`, `source_binding` | canonical parsed source and binding | namespace, snapshot ID, raw SHA256, source locator |
| `sequence_version`, `line`, `occurrence` | canonical represented order | sequence field, line ordinal, position, UTF-8 source span; gaps/unsupported positions remain rows |
| `ordered_position` | SQL view | all occurrence context plus zero-based sequence position; line boundaries remain explicit |
| `posting` | optional indexed materialization | namespace + snapshot + field + uncertainty policy + token ID → occurrence → sequence/witness/artifact/source |
| `ngram` | optional indexed materialization | configured lengths 2–5; overlapping same-line windows; occurrence IDs, start/end positions, stable match span ID and all context links |
| `nodes`, `portable_edge` | SQL views | typed IDs and reversible edge traversal; provenance, claim subject and translation placement edges supplement canonical edges |
| `catalog_alias` | SQL view | exact source-attributed claim → subject artifact; exact target key → separate candidate catalog artifact(s) |
| `translation_context` | SQL view | source text/language/granularity/locator → sequence context, witness, artifact and source |
| `projection_registry` | derived metadata | revision/config, source binding hash, canonical-table hash, exact optional asset inventory |

Reading IDs are scoped to namespace, snapshot and field. Sign postings use the existing source-derived `SignType` IDs; their list namespace/revision is retained in `sign_type`. A label is a scoped lookup convenience, never a cross-source identity merge. ATF positions and `signs` positions have no inferred correspondence. `sequence_position` counts represented positions, not ancient signs or words.

Source-policy n-grams retain null identities/readings for gaps and unsupported positions. `?` matches exactly one represented position, including an unknown-length loss. Exact tokens cannot jump blockers; strict windows require every original position to be explicitly intact/certain. Excluded positions never cause concatenation. Alternatives are opaque blockers, not enumerated hypotheses. Match IDs match graph-query span IDs; projection row IDs additionally bind configuration and policy.

## Runnable CLI recipes (memory only)

Use the existing interpreter with `-B`. No network or corpus writes are involved:

```sh
PY=/Users/danieliser/.local/share/cuneiform-research/venv/bin/python
$PY -B -m cuneiform explore ebl fixtures/ebl-synthetic.json
# Copy the report's ebl/atf snapshot_id into S (demo IDs are reproducible raw-byte hashes).
S=demo:d75dd4f3b3af3665d958d8ac982b8c9a
$PY -B -m cuneiform explore ebl fixtures/ebl-synthetic.json postings A --namespace ebl --snapshot "$S"
$PY -B -m cuneiform explore ebl fixtures/ebl-synthetic.json motifs '["A","?","C"]' --namespace ebl --snapshot "$S" --limit 2
$PY -B -m cuneiform explore ebl fixtures/ebl-synthetic.json motifs '["A","?","C"]' --namespace ebl --snapshot "$S" --limit 2 --offset 2
$PY -B -m cuneiform explore ebl fixtures/ebl-synthetic.json aliases cdli:P000001 --also-cdli fixtures/cdli-synthetic.csv
$PY -B -m cuneiform explore ebl fixtures/ebl-synthetic.json catalog cdli:P000001 --also-cdli fixtures/cdli-synthetic.csv
$PY -B -m cuneiform explore ebl fixtures/ebl-synthetic.json translations Synthetic
$PY -B -m cuneiform demo ebl fixtures/ebl-synthetic.json A B C
```

The last command compares graph, independent sequence-array and materialized-index counts (6 each). Hand fixture expectations additionally test 11 wildcard windows, zero `A C` windows, 3 overlapping `A A` matches in `A A A A`, and 12 `A` postings. Count parity is structural evidence, not validation of parsing or linguistics.

Use IDs returned above as `value` with `sequence`, `occurrence`, `reverse-postings`, `reverse-motifs`, `neighbors`, or `nodes`. `nodes` also accepts a node kind such as `SignType`. `aliases` accepts an artifact ID for reverse traversal. `translations` accepts a literal substring, translation ID, sequence ID or source-record ID. A translation result can then be followed through `sequence` and `neighbors`; this is contextual navigation, not word-level translation alignment. For source lookup:

```sh
# Replace SOURCE and offsets with a returned occurrence's exact source_record_id/start_byte/end_byte.
$PY -B -m cuneiform explore ebl fixtures/ebl-synthetic.json span '{"source_record_id":"SOURCE","start":10,"end":11}' --field atf
```

Lookup lists default to 20, maximum 100, and return truncation/next-offset metadata (span lookup returns its first bounded page). Motif count covers all matching configured windows even when results are paged. No Cartesian pattern expansion occurs. This is a small bounded-input implementation, not a corpus-scale performance claim. Existing graph motif matching still materializes internal matches within the bounded input.

## Python API recipes

For an existing in-memory canonical connection `db`:

```python
from cuneiform.projections import ProjectionConfig, build, lookup, source_span, report
build(db, ProjectionConfig(fields=('atf',), policies=('source',), lengths=(2, 3)))
report(db)  # scopes, registry, source-level missing-layer coverage
hits = lookup(db, 'postings', 'A', namespace='ebl', snapshot=snapshot_id)
p = hits['rows'][0]
lookup(db, 'sequence', p['sequence_id'])
lookup(db, 'reverse-motifs', p['occurrence_id'])
source_span(db, p['source_record_id'], 'atf', p['start_byte'], p['end_byte'])
```

`trace_rows(db, raw, manifest, occurrence_id)` round-trips the exact raw token. For a verified persisted schema-2 snapshot, use `cuneiform.query.connect(snapshot_path)` and the same lookup functions without rebuilding. Stored schema-1 snapshots remain readable by existing `query`/`trace`; new organization views are not silently injected into them.

The summary report shows at most 20 coverage records and flags truncation; the Python `coverage(db)` function returns the full bounded-input coverage ledger. Coverage reports source records with zero supplied word/lemma layers, translation totals and unresolved translation totals. Zero supplied rows means **unavailable**, not a linguistic count of zero. The retained eBL example has nine source strings with unresolved spans; their locator identifies the original translation line, not the translated passage. CDLI has metadata only. No ORACC mapping is enabled.

## Bounds, invalidation and storage

`ProjectionConfig` selects fields, policies, lengths and optional postings/ngrams. Hard ceilings: 20,000 represented positions and 100,000 total materialized rows; lower caller limits are allowed. Only configured windows are built, at most four lengths × two policies per position, plus postings. Budget failure occurs before replacement. Successful rebuild replaces derived tables and registry in one transaction. Configuration changes alter projection IDs; canonical edits invalidate lookups until rebuild. Original occurrence-based match span IDs remain stable when only policy/configuration changes.

The registry hashes all canonical tables (including edges, claims and uncertainty), plus separately sorted raw-source bindings. It is a consistency check, not authentication. No inferred external source authenticity is claimed. Do not mutate canonical source tables in a frozen snapshot. Rebuild is allowed only in memory or import-owned `.pending-*` staging; a frozen persistent database is refused. Re-importing retained raw input with a new schema/parser/projection configuration creates a distinct snapshot identity. There is no in-place migration or automatic rewrite.

New manifests bind projection revision/configuration into snapshot identity and derive their exact payload inventory from the canonical tables plus enabled optional assets. Every materialized table, including registry/postings/ngrams when enabled, is exported to Parquet by the existing generic export loop. Views are recreated from the versioned SQL; they are not redundant Parquet assets. Schema-1 verification uses its original mandatory inventory/parser contract. Checksum/digest integrity is not authenticated integrity against coordinated rewrites.

**Current disk limit:** schema-2 persistent import, its new Parquet exports, and new persistent rebuild refusal are not disk-runtime-verified. In-memory tests exercise inventory validation with mocked payload reads; those are not Parquet readback. Historical parent disk proof applies only to schema 1. The 3 GiB reserve and 500 MiB budget remain enforced; no disk tests or corpus writes are authorized in this slice.

## Portable graph export contract (no FalkorDB runtime)

An admitted future export can `COPY (SELECT * FROM nodes ORDER BY id)` and `COPY (SELECT * FROM portable_edge ORDER BY id)` to Parquet alongside the canonical table Parquets. This contract uses the same IDs without relabeling or merging:

- Node: `id` (global key), `kind` (type); properties come from the corresponding typed canonical table keyed by `id`.
- Edge: `id`, `source_id`, `target_id`, `kind`, `source_record_id`, JSON `qualification`. Both endpoints must exist in `nodes`.
- Added relationship types: `ATTRIBUTED_TO` (Artifact/SequenceVersion/Claim/TranslationSegment → SourceRecord), `CLAIM_SUBJECT` (Claim → Artifact), `PLACED_IN_SEQUENCE` (TranslationSegment → SequenceVersion). The last explicitly carries unresolved alignment. Original relationship types remain defined in `model.EDGE_TYPES`.
- Import receipt: source snapshot IDs/raw hashes, schema/parser/projection versions, configuration, table hashes and row counts. Discard/rebuild the derived graph from these inputs; never use graph labels as identity keys.
- Alias targets remain claim strings. Exact catalog-key lookup yields candidates without an equivalence edge. Missing catalog targets remain unresolved strings; duplicate claims remain separate nodes.

This is an executable SQL view plus a portable export contract, not a running FalkorDB deployment. No FalkorDB install/container/service or live validation occurred. Actual node/edge Parquet export is deferred under the disk guard, as are all new persisted projection exports.

### Reviewed query restrictions

Graph `motif` and array counting require one textual namespace/snapshot per connection/field and reject multi-scope inputs. Use explicitly scoped projection lookup for shared multi-source connections. Strict graph and index windows require readable, intact, certain positions, including wildcard positions; source-policy wildcards can cover opaque positions. `trace_rows` checks bytes against the occurrence source binding and supplied hash, then checks the complete located record. Its rights metadata is labeled caller-supplied; `trace` uses the verified snapshot manifest. Neither path authenticates a legal grant.


## Persisted corpus paths and backend contract (2026-11-03)

This section supersedes the "Current disk limit" and "no FalkorDB runtime / export deferred" notes above: persistent schema-2 snapshots, optional-asset Parquet readback, relocation, frozen rebuild refusal and the portable export are now exercised on real data (see CHECKPOINT). Versions: schema `2`, parser `conservative-3`, projection `linked-1` (row IDs unchanged; the hard ceilings were raised to 2,000,000 positions / 20,000,000 rows for explicit corpus configs, defaults unchanged), manifest contract `manifest-3`, exporter `portable-graph-1`, adapters `ebl-cohort` (`cohort-1`), `oracc-cdl-2` (`oracc-cdl-1` in `snapshot:edaab55c…`, superseded by `snapshot:5e51403b…`; see below), `cdli-artifact-json-1`.

Read-only Python API for consumers such as the UI. Open nothing else and never write into `<root>/snapshots`:

| Call | Returns |
|---|---|
| `storage.verify(path, sid)` | verified manifest; refuses any byte, identity or binding mismatch. Inside a store (a publication ledger beside the directory) it also refuses anything that is not the ledger's committed manifest: unledgered, uncommitted (interrupted), abandoned or replaced copies. Copies outside any store verify content only |
| `storage.verified(path, sid)` | `{manifest, publication}`; `publication.status` is `ledgered`, `ledgered-recovered`, `adopted`, `ledgered-legacy`, `ledgered-legacy-backfilled` (with `incident` and `published_at_semantics` where relevant) or `standalone-not-ledger-checked` |
| `storage.resolve_snapshot(config, sid)` | store path, verified with the ledger required |
| `persisted.scope(path)` | population the counts describe: `kind` (`rule-selected cohort` / `explicit selection` / `single input`), `label` (e.g. `COHORT 300/20,896 eligible of 23,289`), `scope_note`, cohort size, eligible and parent denominators, exclusions, rule, selector, parent sha/md5/bytes/url/receipt |
| `persisted.lookup_snapshot(path, organization, value, field=, policy=, limit=, offset=)` | the organizations above plus `words` and `lemmas`; every response carries `scope` (now with `publication` and `input_identity`), `latency_ms` (**query-only**, `latency_scope: 'query-only'`) and `timing` (`verify_ms`, `query_ms`, `end_to_end_ms`). A `namespace`/`snapshot` override that cannot match raises `persisted.ScopeMismatch`; an organization whose layer has no rows raises `persisted.LayerUnavailable` (never an empty result) |
| `persisted.parity(path, pattern, field)` | graph, array and index counts with denominators, scope and timings |
| `query.trace(path, occurrence_id, parent_root=<research root>)` | token trace; for cohorts `parent_trace` with `status` (`verified` / `parent-raw-unavailable` / `parent-raw-not-requested`), parent receipt/url/pointer/record byte range, and `parent_file_byte_span` (absolute, half-open, over the JSON-escaped token) |
| `oracc.trace_word(path, word_id, parent_root=<research root>)` | word → lemma → sense round trip in payload and parent zip member |
| `persisted.catalog_link([paths], key)` | exact-key alias claims and catalog artifacts per snapshot; never a merge |
| `persisted.export_graph(path, config)` | `derived/exports/<export id>/{nodes,edges}.parquet` + `receipt.json` (counts by kind, file hashes, dangling = 0) |

`parent_root` is the research root (`~/.local/share/cuneiform-research`), not `root/raw`. The CLI mirrors all of these (`scope`, `lookup`, `parity`, `trace`, `trace-word`, `catalog-link`, `export-graph`, `snapshots`) with JSON output.

**Discovery rules.** Only `<root>/snapshots/snapshot:<32 hex>` directories are snapshots. `.pending-*` stages are never snapshots. A snapshot directory appears through a single atomic rename of a complete build and is then read-only. `snapshots/.publication-ledger.jsonl` records every reservation and publication (protocol: [PUBLICATION-PROTOCOL.md](PUBLICATION-PROTOCOL.md)); an ID reserved for some bytes is never published with other bytes. Serve only what `storage.verify` accepts inside the store; a ledger mismatch is an error, not a new cache key. Key caches by `(snapshot_id, manifest_sha256)` only after that check. `.locks/` and `.recovery/` are writer bookkeeping, not snapshots. `scope.input_identity` is equal for a legacy snapshot and a manifest-3 rebuild of the same inputs; use it to group, never to merge. Test and exploration stores live in temporary roots elsewhere and are not snapshots of the research root.

**New organizations.** `words VALUE` matches a word ID, form, citation form, lemma ID, English sense gloss or source record. It returns word → lemma → contextual sense with `gloss_status = 'lexical gloss; not a translation'`. `lemmas [VALUE]` returns lemma rows with attestation counts, attesting records and the list of senses. Coverage rows add `lemmatized_words` and `words_with_sense`. `lemmas` there counts first-attestation attribution, not distinct lemmas used.

**Freshness.** `assert_fresh` returns `freshness`. `frozen-verified` means the connection is read-only, its `graph.duckdb` SHA256 was verified against the manifest in this process, and the registry matches the hashes recorded at freeze (`manifest.projection_registry`, asserted fresh before publication). Anything else recomputes the canonical hash: measured 1.26 s per lookup at 300 records, against 0.04 s for a frozen-verified lookup and 0.10 s for connect+verify. Connections that are writable or opened outside `query.connect` always recompute.
