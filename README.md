# Cuneiform graph and ingestion foundation

A runnable local Python/DuckDB foundation for the authoritative [SPEC-v0.2](SPEC-v0.2.md). It preserves source readings, uncertainty and provenance while exposing typed graph edges and gap-safe motifs. This is a narrow implementation, not the full research workbench.

**Current delivery:** local graph and conservative eBL/CDLI adapters exercised on fixtures and small actual samples. Parent review fixes are applied; all 19 tests pass, including guarded disk-backed fixture import, idempotence, relocation, Parquet readback and tamper rejection. ORACC remains inspection-only. No bulk corpus, remote service, UI, MCP, images or models. See CHECKPOINT.md for historical limitations and the latest validation addendum.

## Run now without corpus writes

Python 3.11+ and `duckdb==1.4.3` are the only runtime requirements. This machine already has a working external environment:

```sh
cd /Users/danieliser/Projects/Fun/cuneiform-research
PY=/Users/danieliser/.local/share/cuneiform-research/venv/bin/python
$PY -m cuneiform demo ebl fixtures/ebl-synthetic.json A B C
$PY -m cuneiform demo ebl fixtures/ebl-synthetic.json A '?' C
$PY -m cuneiform demo cdli fixtures/cdli-synthetic.csv A B
$PY -m unittest discover -s tests -v
```

Expected synthetic graph/array counts: `A B C` = **6**, `A ? C` = **11**, `A C` = **0**. `?` explicitly permits one represented position, including a gap/unsupported position. Demo output includes counts, graph matches and an exact raw-source trace. Runtime remains in memory and DuckDB disk spill is disabled. The test suite includes a gated disk test that skips by default; the actual-source test skips on machines without the private local evidence files.

The real frozen README example can also be exercised without disk ingestion:

```sh
EVIDENCE=/Users/danieliser/.local/share/cuneiform-research/evidence
$PY -m cuneiform demo ebl "$EVIDENCE/ebl-frozen-example.json" ABZ215 ABZ13 --field signs
$PY -m cuneiform demo ebl "$EVIDENCE/ebl-one" A B
$PY -m cuneiform demo cdli "$EVIDENCE/cdli-three.csv" A B
```

These are small privately retained inspection samples, not a downloaded corpus. Full receipts include URLs, hashes, byte counts and failures in `evidence/source-receipts.json`. No real corpus text is packaged in repository fixtures.

## Persistent commands after storage admission

Default root: `~/.local/share/cuneiform-research`. Override with `CUNEIFORM_STORAGE_ROOT` or global `--root /approved/external/path`. Keep runtime data outside Projects. Long-term storage is undecided; no new volume is assumed. Bulk ingestion remains deferred; every write admission still enforces the reserve.

On a future machine with sufficient approved space, install into an external virtual environment with `python3 -m venv "$ROOT/venv"` and `"$ROOT/venv/bin/pip" install --no-cache-dir duckdb==1.4.3`. This session's installed environment used roughly 50 MiB, far below the 500 MiB task cap.

```sh
# Read-only inspection and dry-run report work even when admission is blocked.
$PY -m cuneiform inspect ebl fixtures/ebl-synthetic.json
$PY -m cuneiform import ebl fixtures/ebl-synthetic.json --dry-run --source-url synthetic:fixture

# Run only after reserve is restored. Import will still enforce it.
$PY -m cuneiform import ebl fixtures/ebl-synthetic.json --source-url synthetic:fixture
# Set SNAP to the snapshot ID printed by that command.
$PY -m cuneiform manifest "$SNAP"
$PY -m cuneiform query "$SNAP" A B C
$PY -m cuneiform query "$SNAP" A '?' C
$PY -m cuneiform query "$SNAP" A B C --max-skip 2
$PY -m cuneiform query "$SNAP" A B C --strict
# Set OCC to an occurrence ID returned in a match.
$PY -m cuneiform trace "$SNAP" "$OCC"
CUNEIFORM_RUN_DISK_TESTS=1 $PY -m unittest discover -s tests -v
```

`--max-skip 2` means `A B [0–2 represented positions] C`, not 0–2 reconstructed ancient signs. Unknown-length losses remain one unknown-extent represented position. Exact patterns cannot jump them. All queries are line-local and select one explicit snapshot plus sequence field; ATF and derived-sign sequences are never mixed. Match IDs deduplicate identical spans. Counts report witness/artifact support and represented-position denominators; composition coverage is unknown. The returned match list is capped at 100, with a truncation flag; counts still cover the bounded input.

`--strict` requires explicitly `intact` and `certain` positions. Current eBL subset does not assert either from an absence of editorial marks, so strict real-source counts are zero. Default source-reading counts include uncertain/restored readings and are labeled accordingly. Certain physical evidence count is separate. Alternative-aware global bounds remain unresolved, not invented confidence intervals.

Other commands:

```sh
$PY -m cuneiform inspect oracc /path/to/small-local-project-record.json
$PY -m cuneiform import ebl-atf /path/to/local.atf --record-id SOURCE-ID --namespace source-edition
# Download is opt-in, bounded and reserve-gated; not needed for existing demos.
$PY -m cuneiform fetch 'https://www.ebl.lmu.de/api/fragments/K.1' --allowlist fixtures/allowlist.json --max-bytes 32768
```

Import byte cap is 2 MiB. Defaults enforce a 500 MiB root budget and 3 GiB free reserve. Existing dependencies/data under that root count toward the budget. Downloads require exact HTTPS allowlisting, reject redirects and do not retry. Persistent import uses new staging directories and validates existing snapshots before reuse. Whole-file malformed JSON/CSV aborts before a snapshot; per-record mapping rejections are stored in `rejection` alongside raw values. No automatic destructive cleanup or migrations.

## Implemented graph and source limits

[Typed SQL schema](cuneiform/schema.sql) and [version/edge registry](cuneiform/model.py) separate Artifact, Witness, Composition/Passage, SequenceVersion/Line, editorial SignOccurrence, WordToken/Lemma/Sense, TranslationSegment, SourceRecord, SignType and exceptional Claim. `nodes`, `next_position`, and `token_context` are executable DuckDB graph views. Persistent export writes each typed base table to Parquet without pyarrow. Paths never enter source/node identities.

| Source | Actually exercised | Populated layers | Limits/rights |
|---|---|---|---|
| eBL frozen README example | One complete embedded record, in memory | metadata, separate ATF and source-derived signs, translation strings, alias claim | Full frozen JSON envelope unverified; ATF parser is conservative subset; Zenodo/paper license conflict unresolved |
| eBL live K.1 | One bounded 11,108-byte response | artifact metadata and CDLI alias | Empty text; no witness fabricated; photos/OCR not followed |
| CDLI historical CSV | 16 KiB prefix, first three complete rows | metadata/artifacts and museum aliases | No name-based merges; freshness and data rights unknown |
| ORACC | Failed official docs requests; local JSON inspection path | none | Import refuses; no verified word/lemma/English mapping or project license |
| Synthetic fixtures | uncertainty, gaps, alternatives, compounds, duplicate aliases | structural/query tests | Engineering fixtures, not philological evidence |

ATF compounds, determinatives, numerals and alternatives are retained as opaque blocking positions rather than falsely split signs. Raw metadata and editorial marks remain recoverable. `signs` labels are source-attributed reading derivations, never image evidence; no alignment to ATF positions is invented. Translation placement is known but its span is unresolved, so no word-level translation edge exists. Unavailable Composition/Passage/Word/Lemma/Sense layers stay empty. Interpretation branching and alternative-hypothesis evaluation are deferred.

See [source-by-source ingestion design](docs/INGESTION-DESIGN.md) for exact format evidence, rights ledger, identity/version rules, acquisition/resume strategy and remaining gates. See [checkpoint](CHECKPOINT.md) for test output, disk measurements and parent-review handoff. Frozen specs and review predecessors remain unchanged.
