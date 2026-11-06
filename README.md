# Cuneiform graph and text-corpus pilot

**Project status:** experimental source archive. Start with the [Workbench demo](https://github.com/danieliser/cuneiform-ui#try-it-without-a-corpus-or-docker). The final value audit did not demonstrate a practical advantage for the tested construction. Corpus data is not included. No root software license has been selected. Historic runtime paths and snapshot inventories below describe the development environment, not an installation prerequisite. The conservative-4 full rebuild was produced but its verification was interrupted at closure; it is not independently accepted.

A local Python/DuckDB implementation of the authoritative [SPEC-v0.2](SPEC-v0.2.md). It preserves source readings, uncertainty and provenance; exposes typed graph edges, gap-safe motifs and portable graph exports; and now runs on **real persisted text data** from three sources. It is a pilot, not the full research workbench.

**Full release, parser revision (2026-11-05, Q-026, pending independent review):** `snapshot:224188c0…` rebuilds the same 20,896 eligible records with parser `conservative-4`, which no longer stores 129 `#tr`/`#note` comment lines as text lines and no longer records `@colophon`, `@date`, `@seal N` and similar markers as surfaces. See [docs/PARSER-REVISIONS.md](docs/PARSER-REVISIONS.md).

**Full release (2026-11-05, Q-023, accepted for its engineering scope; candidate correction in Q-026, not independently accepted):** `snapshot:965aa262…` holds all 20,896 records of the frozen eBL release that are eligible under `usable-text-v1` (2,393 of 23,289 excluded, each listed with its reason), with 4.5M positions, 12.3M n-grams and graph/array/index parity on stratified motifs. Its `atf` layer is **not pure transliteration**: 129 of its lines (49 records, 2,258 positions) are translation or note text, and writer reports 8,105 lines carry a structure marker as their surface. It stays published and readable for provenance (benchmarks are bound to it). See CHECKPOINT.md (Q-023) and [docs/PARSER-REVISIONS.md](docs/PARSER-REVISIONS.md).

**Pilot delivery (2026-11-03):** the complete frozen eBL text export (73.9 MB, MD5-verified) is acquired, inspected in full by streaming, and sampled into reproducible cohorts of 30 and 300 records. Those cohorts are persisted as immutable snapshots with Parquet, indexed postings/n-grams and parent-file byte traces. ORACC `ccpo` (official JSON export) supplies WordToken/Lemma/Sense for 51 texts that match eBL records by exact P-number. Bounded CDLI catalog records exist for the same 51 P-numbers. Source audit: [docs/SOURCE-AUDIT.md](docs/SOURCE-AUDIT.md). Contracts per source: [docs/INGESTION-DESIGN.md](docs/INGESTION-DESIGN.md). Organizations and query recipes: [docs/REPRESENTATION-MAP.md](docs/REPRESENTATION-MAP.md). Evidence and measurements: [CHECKPOINT.md](CHECKPOINT.md).

## Persisted pilot snapshots

Runtime root `~/.local/share/cuneiform-research` (override with `CUNEIFORM_STORAGE_ROOT` or `--root`). Nothing from the corpus is packaged in Git.

| Snapshot | Source / scope | Contents |
|---|---|---|
| `snapshot:224188c083b10d209823da36404e2266` | eBL **all 20,896 eligible** of 23,289, parser `conservative-4` (`cohort:b07f1ade…`); pending independent review | 4,539,895 positions, 12,284,601 n-grams, 2,882,235 postings, 12,163,000 edges, 23,984 unaligned translation lines; 9.5 GB |
| `snapshot:965aa26214dc0388dd3af1be367d2acc` | eBL **all 20,896 eligible** of 23,289 (`cohort:4e532850…`, format cohort-2, per-record exclusions), parser `conservative-3`, superseded in content (see PARSER-REVISIONS) | 4,542,153 positions, 12,292,380 n-grams, 2,883,814 postings, 12,167,645 edges, 23,984 unaligned translation lines; 9.5 GB |
| `snapshot:ce127437339109285185a534145edf50` | eBL cohort 30 of 20,896 eligible (`cohort:9abad6ce…`) | 10,148 positions, 28,330 n-grams, 25 unaligned translation lines |
| `snapshot:84971360d212834e0b7acbeac1e56abe` | eBL cohort 300 of 20,896 eligible (`cohort:4e86952e…`; the 30 are its first 30) | 80,823 positions, 223,799 n-grams, 50,391 postings, 366 unaligned translation lines |
| `snapshot:c316e7cbbaf8a7fca7705f0efa5c4a07` | eBL, all 51 eligible records whose `cdliNumber` is an ORACC ccpo text (`cohort:ea91baae…`) | 20,421 positions |
| `snapshot:edaab55c1a39cc65ad7c76e6d12547a7` | ORACC ccpo, those 51 texts | 6,888 words; 4,544 lemmatized words with contextual English sense; 1,122 lemmas; 1,317 senses |
| `snapshot:fc7c350439f9edfee61b5f35bdd4d65a` | CDLI cdli.earth catalog JSON, same 51 P-numbers | 51 artifacts, 334 attributed alias claims, no text |

Counts are **within the selected scope**. For cohorts and selections they are never corpus frequencies; for the full snapshot they are frequencies within the conservative parse of the eligible records of that one release. `scope` and every `lookup` response say so explicitly.

## Run

```sh
cd /Users/danieliser/Projects/Fun/cuneiform-research
PY=/Users/danieliser/.local/share/cuneiform-research/venv/bin/python   # Python 3.13, duckdb==1.4.3 only
c() { "$PY" -B -m cuneiform "$@"; }   # works in bash and zsh
S300=snapshot:84971360d212834e0b7acbeac1e56abe; ORACC=snapshot:edaab55c1a39cc65ad7c76e6d12547a7
EBL51=snapshot:c316e7cbbaf8a7fca7705f0efa5c4a07; CDLI=snapshot:fc7c350439f9edfee61b5f35bdd4d65a

c snapshots                                   # verify all; each row has a scope label
c scope $S300                                 # cohort size, eligible/parent denominators, rule, parent receipt
c lookup $S300 report
c lookup $S300 postings ABZ579 --field signs
c lookup $S300 motifs '["ABZ480","ABZ13"]' --field signs --limit 5
c lookup $S300 motifs '["ina","?","ana"]'     # ? = exactly one represented position
c parity $S300 '["ABZ480","ABZ13"]' --field signs   # graph / array / index: 201 / 201 / 201
c query  $S300 DIŠ ina                       # graph motif with denominators
c trace  $S300 occurrence:ee78553cad17f460f7ad9f287877021c   # payload -> parent Zenodo file byte span
c lookup $S300 translations "" --limit 3    # translation strings with unresolved spans
c lookup $ORACC lemmas --limit 5
c lookup $ORACC words šumma --limit 3
c trace-word $ORACC <word id from the previous command>      # payload -> parent zip member
c catalog-link cdli:P461271 --snapshot $EBL51 --snapshot $ORACC --snapshot $CDLI
c catalog-link ebl:BM.59739 --snapshot $EBL51 --snapshot $ORACC --snapshot $CDLI
c export-graph $S300                          # nodes/edges Parquet + receipt under derived/exports
$PY -B -m unittest discover -s tests                         # 43 tests; 5 disk tests skip
CUNEIFORM_RUN_DISK_TESTS=1 $PY -B -m unittest discover -s tests
```

Reproduce from scratch (acquisition is network work; each step writes immutable, checksum-verified outputs and refuses to rebuild a published snapshot ID):

```sh
c acquire https://zenodo.org/api/records/10018951/files/fragments.json/content --max-bytes 73854507 \
   --expect-md5 71538e2d86c8ba6d47f499892bb3e5d3 --expect-bytes 73854507 \
   --label ebl-zenodo-10018951-fragments.json --rights sources/rights/ebl-zenodo-10018951.json
c receipts
c corpus-inspect <receipt>                     # ~100 s, peak memory ~48 MB
c corpus-select  <receipt> --size 30           # then --size 300
c --max-total-gib 41 --reserve-gib 30 corpus-select <receipt> --all-eligible        # full release (cohort-2 accounting)
c corpus-accounting <cohort>                   # every parent record: member or excluded with reason
c --max-total-gib 41 --reserve-gib 30 corpus-import <cohort> --projections full --memory 16GB   # ~22 min, ~6 GB RSS
c corpus-audit   <cohort> --markdown
c corpus-import  <cohort>
# ORACC serves its leaf certificate without the intermediate; supply the verified intermediate (see INGESTION-DESIGN).
c acquire https://oracc.museum.upenn.edu/json/ccpo.zip --max-bytes 10006811 --expect-bytes 10006811 --chain-intermediate <InCommon RSA Server CA 2 PEM>
c corpus-select <ebl receipt> --cdli-from-oracc <ccpo receipt> --project ccpo
c oracc-import <ccpo receipt> --project ccpo --texts-from-snapshot <eBL overlap snapshot>
c cdli-import --from-snapshot <eBL overlap snapshot> --allowlist sources/allowlist-cdli-ccpo-overlap.json
```

The older in-memory demos still work unchanged: `c demo ebl fixtures/ebl-synthetic.json A B C` (6/6/6), `c explore ebl fixtures/ebl-synthetic.json`.

## Rules the implementation enforces

- **Immutable publication.** Builds are staged in `.pending-*`, published by one atomic rename, made read-only and recorded in an append-only ledger (`snapshots/.publication-ledger.jsonl`). An ID that was ever published can never be published again, even after deletion. IDs bind payload hash, namespace, source, schema/parser versions, record/cohort ID, citation, projection config and (new snapshots) the manifest contract `manifest-3`.
- **Provenance.** Raw bytes live in `raw/sha256/<hash>` with one receipt per acquisition (URL, time, headers, hashes, rights statements). Cohort payloads are byte-identical parent slices. `trace` re-hashes the parent file and returns the token's absolute byte span in it, covering the JSON-escaped encoding (e.g. `ša₂` for `ša₂`).
- **No invented layers.** Gaps and unsupported positions never concatenate. Readings are not converted into visual sign identities. ATF and `signs` are never aligned or pooled. Translation strings keep `unresolved-span`. ORACC senses are lexical glosses, not translations. Cross-source links are exact-key claims, never merges. Namespaces and snapshots are never pooled by graph/array queries.
- **Freshness without O(corpus) rehash.** A read-only connection whose `graph.duckdb` SHA256 was just verified against its manifest uses the registry hashes recorded at freeze time. Other connections recompute.
- **Budgets.** Default root budget 5 GiB, free-space reserve 10 GiB, checked before every write; `--max-total-gib`/`--reserve-gib` set an explicit task budget (Q-023: 41 / 30 GiB), and long builds re-check the free-space reserve during ingestion and projection. Small-input imports stay capped at 2 MiB. Cohort imports stream record by record.

## Limits

eBL rights are an unresolved conflict (Zenodo CC BY 4.0 vs data paper CC BY-NC-SA 4.0). The ORACC JSON states CC0 and the CDLI terms cover text reuse; neither was legally reviewed. The ATF parser is a conservative subset: hyphenated words are opaque blockers, so ATF reading motifs are sparse and source-derived `signs` carry most motifs. Strict physical-evidence counts are zero because the export never asserts intact+certain. ORACC translation text is absent from its JSON, and ORACC graphemes are not yet mapped to sign occurrences. No compositions, passages, dates, joins, images or embeddings exist. FalkorDB and MCP are later tasks (QUEUE Q-009/Q-010); the portable export is their input.
