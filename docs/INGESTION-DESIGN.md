# Source ingestion design and evidence

2026-11-02. Implementation foundation, not the complete SPEC-v0.2 milestone. Sole writer; independent parent review pending. Long-term storage destination remains undecided. No source corpus is redistributed here: repository fixtures are explicitly synthetic. Local inspected bytes and receipts are under `~/.local/share/cuneiform-research/evidence/`.

## Common acquisition and storage contract

The implemented CLI defaults to `CUNEIFORM_STORAGE_ROOT` or `~/.local/share/cuneiform-research`. Relative snapshot paths make relocation possible without changing identities. Keep the configured root outside Projects. No service, network database, image acquisition, model, embedding, MCP or UI is included.

`inspect` reads a local input up to 2 MiB and reports its structure, raw SHA256, rights and a deliberately conservative growth estimate (100 × input + 8 MiB). `import --dry-run` also reports admission failure without writing. `fetch` accepts only exact HTTPS URLs listed in an explicitly supplied JSON allowlist, rejects redirects, streams at most the requested byte limit (default 256 KiB), and retains nothing on overflow. It does not crawl, follow image references or retry. TLS validation stays enabled. Both download and persistent import require 3 GiB reserve and a 500 MiB root budget, including files already in that root. Concurrent unrelated disk use can consume headroom after admission; checks are admission safeguards, not disk reservations. No global cross-process reservation service exists.

Persistent layout (implemented, disk-backed verification blocked):

```
<root>/snapshots/snapshot:<hash>/
  raw
  manifest.json
  graph.duckdb
  parquet/<typed-table>.parquet
```

An import stages its own directory, closes DuckDB, hashes every payload, then renames the stage to a new snapshot directory. Existing snapshots are verified and reused, never overwritten. Interrupted stages have `.pending-*` names and are not queryable snapshots; no automatic cleanup of unknown stages. There is no active/latest mutable alias. No migration mutates an old snapshot: future parser/schema versions must create new projections. The root budget and reserve are checked before writes; the current task stopped persistent import at this gate.

Snapshot identity includes raw bytes hash, source namespace, adapter name, schema/parser versions, explicit record ID and source citation. Paths and import timestamps are excluded. Artifact IDs are source-namespaced catalog identities; witness/sequence/occurrence IDs are versioned source identities and locators. Cross-source equivalence is a Claim, never a name-based merge. Repeated local input with a different citation intentionally has a different snapshot. Raw JSON contains all unknown/unmapped fields. Rejections are accounted separately; duplicate identities within one input are rejected, not deduplicated silently.

Provenance uses a raw-file checksum, source record JSON pointer (or logical CSV row), decoded source string field, and UTF-8 byte offsets **within that decoded string**. Offsets are not misrepresented as offsets in escaped JSON bytes. Source trace reparses the retained raw file and verifies that the selected slice equals the stored token. CSV rows refer to logical records, not physical newline numbers when fields contain newlines.

## eBL frozen JSON and live single records

Primary sources examined:

- Frozen release README: https://zenodo.org/records/10018951/files/README.md?download=1 — complete 12,355 bytes. Contains a `fragments` wrapper and one example record `1868,0523.2`; the embedded example was extracted locally. This is **not** an inspection of the complete 73.9 MB `fragments.json` snapshot.
- Official API client: https://raw.githubusercontent.com/ElectronicBabylonianLiterature/transliterated-fragments/main/ebl/example.py — inspected with web fetch. It uses `fragments`, `totalCount`, `atf`. Its first-batch API retrieves 1,000 records per README; we did not call that endpoint.
- Single live record: https://www.ebl.lmu.de/api/fragments/K.1 — complete 11,108 bytes. Contains `museumNumber`, `externalNumbers.cdliNumber=P237754`, empty `atf` and `signs`, plus raw metadata. No witness/text was invented. OCR-related fields in raw metadata are not ingested as graph evidence.
- ATF specification: https://raw.githubusercontent.com/ElectronicBabylonianLiterature/ebl-api/master/docs/ebl-atf.md — first 16,384 bytes only. Confirms eBL flavor differs from ORACC and grammar complexity; not claimed to be fully read or implemented.
- Release overview: https://zenodo.org/records/10018951 ; data-paper grant reference: https://openhumanitiesdata.metajnl.com/articles/10.5334/johd.148 . Conflicting grant statements are carried from authoritative project spec/review; this implementation did not re-adjudicate grants.

Implemented input shapes: a single record, a list of records, or `{ "fragments": [...] }`; actual frozen file envelope remains unverified. Identity uses `_id`, or observed structured museum number when `_id` is absent. Record IDs and all bytes are snapshot-versioned. `externalNumbers.cdliNumber` makes an unreviewed attributed alias Claim. Other external IDs, joins, revision histories, geography and custody remain raw metadata; no accession-prefix geography inference.

ATF adapter recognizes numbered lines and simple standalone reading tokens. It does **not** split words at hyphens/dots or invent component-sign segmentation. Complex words, compounds, determinatives, alternatives and numerals become opaque unsupported positions with an exclusion reason. Gaps remain positions. Bracket context, `?` and `#` are conservatively retained as loss/uncertainty/damage cues; lack of marks is `unmarked` certainty and `unknown` physical preservation, never `intact/certain`. Restoration basis stays unknown. Line/surface/column labels and raw offsets are retained. No cross-line motifs are evaluated.

`signs` is a **separate** sequence of source-derived sign labels, with attributed `MAPS_TO_SIGN` edges. Sign-list revision is unknown; namespaced snapshot identity prevents false global inventory equivalence. No one-to-one connection to ATF tokens is assumed. The source's reading-to-sign conversion is not independent visual confirmation. Empty signs and text produce no sequences.

`#tr.en:` strings are retained with language and source placement, but `unresolved-span` granularity. The frozen example shows translations following several source lines; assigning each to just the preceding line would fabricate alignment. No `TRANSLATES` edge, WordToken, Lemma or Sense is manufactured. Source author remains unknown unless modeled from an explicit future contract. No composition/passage membership is inferred from descriptions.

Observed in-memory exercise: 1 source record, 1 artifact, 1 witness, 2 sequences, 34 lines, 541 represented positions, 96 source sign-label nodes, 9 translation segments, 1 alias claim, 0 rejected records, 106 exclusion entries, 1,433 edges. `ABZ215 ABZ13` in the signs sequence has graph=3 and array=3. Exclusions include non-token ATF lines and unsupported components, not necessarily 106 rejected signs. This is engineering evidence, not validated sign segmentation or translation coverage.

Acquisition next: frozen whole-file import needs explicit disk/corpus scope approval, file envelope check, expected upstream MD5 verification and corpus size planning. Keep the original raw frozen release; live records create separate snapshots. Prefer a hand-selected ID list and serial single-record retrieval. Future network continuation should retain per-record URL/hash/status, honor Retry-After, use bounded retries only after classifying failures, and resume by completed checksum receipt; current CLI deliberately has no automatic retries or bulk scheduler.

Rights: **unresolved conflict** between Zenodo CC BY 4.0 and paper CC BY-NC-SA 4.0. Picking the stricter string does not establish the applicable grant. Text, annotations, translations, images and code have separate rights. Private inspection does not establish redistribution permission. No full public data sample is committed.

## ORACC per-project JSON

Official documentation endpoints attempted:

- https://oracc.museum.upenn.edu/doc/opendata/
- https://oracc.museum.upenn.edu/doc/opendata/json/index.html
- https://build-oracc.museum.upenn.edu/doc/opendata/json/index.html

Web fetch timed out. Direct Python access to the JSON documentation failed certificate validation. Validation was not disabled. A bounded GitHub `oracc/oracc` doc-directory inventory was reachable but did not establish the project JSON contract. No further blind endpoint retries.

**Implemented status: experimental local JSON inspection only; import refuses explicitly.** No real ORACC JSON sample or English word-level alignment was verified. There is no fabricated ORACC fixture or mapper. Typed WordToken/Lemma/Sense/TranslationSegment tables and edge endpoints exist empty, ready for a verified contract. The frozen eBL example establishes translation strings only, not an ORACC word-to-English bridge.

The prior review reports `manifest.json`, `metadata.json` with `atf`/`lem`/`tr-en` ID lists and per-project `json.zip`. These remain **review-reported leads**, not field mappings verified by this implementation. Do not download entire ZIPs to discover one record while the reserve is blocked.

Next bounded audit: choose a project and single text with explicit public terms; acquire its manifest/metadata and one small JSON document through validated HTTPS; record project revision and exact record/word locators. Inspect lemma citation form, POS, language, guideword and contextual sense independently. A guideword is not automatically an English translation of an individual sign. Preserve source segmentation IDs and multiple analyses; only create HAS_SIGN or TRANSLATES edges when explicit source alignment supports them. Without sign segmentation, word/lemma and line translation layers can exist separately.

Identity: source project namespace + text ID + bytes/revision; dictionary namespace/version + supplied entry key for Lemma/Sense. Different project editions stay separate. Expected acquisition is serial per-project metadata then an explicit selected ID allowlist; restart from verified receipts. Rate limit, archive size and project-specific terms must be checked before implementation. Site CC BY-SA 3.0 is reviewer-reported; individual project exceptions, authorship and share-alike scope remain unresolved.

## CDLI catalog and crosswalks

Primary sources examined:

- https://raw.githubusercontent.com/cdli-gh/data/master/README.md — README explicitly says last update August 2022, UTF-8 CSV catalog and ATF text; no data license established here.
- https://api.github.com/repos/cdli-gh/data/contents — small directory inventory identifies `cdli_cat.csv`.
- https://media.githubusercontent.com/media/cdli-gh/data/master/cdli_cat.csv — read at most 16,384 bytes, closing the response immediately. This was a prefix inspection, not a full-file retrieval. The first three complete CSV records were reserialized into a local audit sample; prefix bytes remain the evidence predecessor.

Observed headers include `id_text`, `museum_no`, `accession_no`, `provenience`, `period`, `language`, `translation_source`, `join_information`, `collection` and `external_id`. Numeric `id_text` values 1/2/3 are explicitly projected into CDLI P-number namespace as P000001/P000002/P000003; this is an adapter normalization rule, not a source string. Preserve raw values. `id` and `id_text2` are not substituted as identifiers.

Implemented: CSV input, catalog record/artifact, raw attributed metadata, museum/accession alias claims. No witness from catalog-only records. No joining records with equal museum labels. No findspot-from-prefix inference. `translation_source` remains a raw catalog assertion; `no translation` does not mean a text has never been translated. Missing values remain empty strings/null as supplied. Malformed/truncated CSV rows are rejected with raw accounting. A syntactically complete last field of a truncated prefix is not detectable generically, so the audit explicitly selected only the first three complete logical records.

Actual sample: 3 source records, 3 artifacts, 3 museum-label claims, no witnesses or sequences, zero rejected records. Duplicate-label behavior is separately covered with synthetic fixtures. eBL-to-CDLI aliases remain claims keyed by catalog identity; future cross-snapshot federated resolution must select snapshots and preserve source independence as unknown.

Next: confirm current preferred catalog export and terms, pin a commit/release rather than mutable master, then acquire a bounded selected record set. Historical bulk repository data must not be silently labeled current. Resume by file checksum and record locator, never fuzzy museum-name matching. No full CSV, ATF dump or Git LFS clone was downloaded.

## Deferred image and model sources

CuneiML, eBL OCR and collection image APIs are future contracts only. Before any adapter, independently verify asset rights, snapshot identifiers, geometry units and source image hashes. Face crops do not establish per-sign regions; OCR labels do not establish editorial token alignment. No image downloads, OCR weights, embeddings, model execution or image-pack work occurred.

## Storage and research gates

The parent explicitly permits completion with disk-backed verification blocked. Actual disk reserve failed before snapshot import; later headroom rebounded, but the parent limited remaining writes to 10 MiB and explicitly accepted a blocked disk-verification handoff. In-memory adapter, trace and graph results are exercised. Persistent snapshot idempotence, relocation and Parquet readback have executable gated tests but are **not verified** until storage is approved and the reserve restored. See README and CHECKPOINT for exact commands.

Also deferred: full eBL grammar, sign inventory validation, compatible alternative assignment bounds, lemma motifs, source-aligned translations, physical join inference, 30-record cohort audit, linguistic review, cross-snapshot artifact deduplication, production scale/performance, full SPEC/MCP delivery. No structural success establishes scholarly truth.
