# Cuneiform symbol and evidence workbench

Version: 0.1 — 2026-11-02. Status: proposal awaiting independent review.

## 1. Decision and intended contribution

Build a small, reproducible graph of symbol occurrences and the evidence used to interpret them. Use it to explore recurring sequences, compare readings, and retrieve related passages. The graph connects physical objects, document witnesses, positions, sign identities, motifs, editions, translations and claims. Historical-person graphs are a later integration.

The best fit for our skills is source integration, deterministic identities, evidence lineage, versioned interpretation, fast exploratory queries, and an effective human review interface. Treat Assyriological judgments as supplied or reviewed by specialists.

Three capabilities share the same foundation:

1. **Contextual pattern discovery:** find exact and bounded-gap sequences, recurring templates, and substitutions; compare their prevalence across periods, places, genres and manuscript groups. This is the primary exploratory experience Daniel proposed.
2. **Reading dependency explorer:** inspect which readings and translations depend on a particular sign interpretation; show alternatives and contradictions. This is the first review workflow.
3. **Fragment and parallel retrieval:** use patterns plus independently available context to rank related passages and return inspectable alignments. This is the first measurable research experiment.

An optional fourth capability is **review prioritization**: rank uncertain sign occurrences by how many downstream claims they affect and how much alternative interpretations change retrieval. This is an engineering hypothesis, not a claim of decipherment. Start with explicit impact counts; probabilistic information gain requires calibrated probabilities and an explicit decision model.

No claim of a new graph formalism, first cuneiform graph, or novel n-gram discovery is made. Success can be a useful open evidence bundle and research interface even if retrieval accuracy does not improve. A graph need not outperform a sequence index for counting n-grams.

## 2. Existing work and baseline

- eBL's public ngram-matcher supplies sign-sequence retrieval, optional OCR input, overlap inspection and several scoring variants. Its documentation describes ABZ-coded fragment strings and chapter/manuscript data. Reproduce the relevant behavior on our frozen inputs before attributing any benefit to new features. [S1]
- Its published foundation is *Reconstruction of Cuneiform Literary Texts as Text Matching* (LREC-COLING 2024). [S2]
- ProtoSnap aligns sign prototypes to photographed forms; use it as possible later visual evidence, not a required new model to train. [S3]
- Existing graph-based recognition represents the internal wedge structure of signs. That is a different graph scale from our occurrence-to-document-to-interpretation model. [S4]
- Prosobab demonstrates separating attestations from resolved identities; this is a useful methodological precedent rather than our initial corpus. [S5]

Our candidate distinction is the ability to combine these layers while preserving ambiguity and exact supporting occurrences. Whether existing platforms already support the same workflows remains an explicit discovery question.

## 3. Data selection and access plan

### Primary corpus: eBL, one bounded literary cohort

Begin with a source audit of 30 fragment/witness records. For the first benchmark, target 300–1,000 physical fragments with usable sign sequences and source IDs, plus a 20–50-witness close-reading subset with passage relationships and translation coverage. These are sampling targets, not verified availability counts.

Choose one composition/chapter family only after verifying overlapping witnesses and access to its editions. Standard Babylonian Gilgamesh is a candidate, not a committed selection. Include same-period and same-genre distractors outside the selected work. Broader pattern discovery requires a larger, stratified corpus later; one composition cannot support language-wide frequency claims.

| Source | Planned use | Verified access/format evidence | Unresolved before ingestion |
|---|---|---|---|
| eBL transliterated-fragments [S6] | Source ATF, stable fragment IDs and available metadata | Public Python example reads a paginated endpoint with `fragments` and `totalCount`; each processed record has `atf` | Live endpoint response, full field coverage, snapshot availability and dataset rights |
| eBL ngram-matcher data interface [S1] | ABZ-coded sequences, chapter and witness associations, retrieval baseline | README examples expose fragment `_id`/`signs`; chapter-level sign strings and manuscript metadata | Full schema, sign-to-ATF alignment, stable witness IDs, export completeness |
| eBL corpus editions | Passage alignments and translations for close reading | Platform and matcher refer to chapters/manuscripts | Translation export fields, granularity, edition revision history, licenses; do not assume all present |
| eBL OCRed signs, Zenodo 14009952 [S7] | Later image/detection evidence | Named JSON release, approximately 220 MB; model-generated detections | Actual JSON schema, coordinates, image identifiers, score availability, license and overlap with cohort |
| CuneiML [S8] | Later independent adapter and cross-collection evaluation | Documented JSON links images, face crops, metadata and text representations | Obtain data artifact; verify overlaps and language; face bounding boxes are not individual-sign annotations |
| CDLI [S9] | Catalog crosswalks and permitted images | Catalog/ATF repository exists; README labels last update August 2022 | Freshness, ID equivalence, per-image terms and working image URLs |

Scope choices: eBL is the initial data backbone. Do not combine CuneiML's predominantly different material or Elamite DeepScribe data into the same linguistic cohort by default. Syrian/Eblaite/Ugaritic corpora need separate adapters and expert decisions about sign inventories.

Rights are recorded per asset: code, text edition, image, annotation and derived dataset. An MIT/CC0 code repository does not license museum photographs or upstream editions. No blanket redistribution claim. Missing rights become `unknown`; public artifact release waits for a resolved asset manifest. Private inspection and public redistribution are distinct decisions.

### Acquisition contract

Each acquisition saves `source_url`, source record ID, retrieval UTC time, source version/commit/DOI where present, HTTP status, content type, byte count, SHA-256, license URL/text reference and importer version. Store raw bytes unchanged. Freeze the corpus membership and exclusions in a manifest. Record inaccessible or unparsable rows; never quietly drop them.

Validate pagination using source IDs, duplicate counts, missing boundaries and the declared total. The published example is an access reference, not a trusted completeness implementation. Preserve raw ATF alongside parsed tokens, uncertainty/damage markers, surface/column/line boundaries and exact character offsets.

Source sign encodings remain namespaced (e.g. ABZ identifier versus Unicode versus a catalog sign ID). A conversion is a versioned mapping assertion. Unicode generated from transliteration is derived evidence and must not be presented as independent visual confirmation.

## 4. Physical, textual and interpretive identities

Keep these distinctions explicit:

- **Artifact:** a physical tablet or fragment with collection identifiers. Two catalog records may refer to one artifact; equivalence needs a source assertion.
- **Witness:** one manuscript's textual contribution. An artifact can contain multiple texts; a joined witness can span multiple artifacts.
- **Composition / Passage:** an abstract work and a stable source-defined passage within an edition. Several witnesses can attest it.
- **SequenceVersion:** a particular source/edition's ordered transcription of a witness segment. Two editions of one artifact are not two independent ancient attestations.
- **Occurrence:** one token position inside that sequence, not the global identity of a sign. It may be a sign token, damaged trace, gap, numeral or boundary-sensitive compound.
- **SignType:** a namespaced sign identity. The same sign can occur many times on one tablet. Its possible readings are not identical to its visual shape.

An occurrence extracted from text is not automatically a physically located image region. Alignment between them can be missing or disputed. Historical dates use interval bounds, calendar/source notation and uncertainty; do not force BCE dates into ordinary UTC timestamp fields. Acquisition and review timestamps are ordinary UTC.

## 5. Nodes and minimum properties

All IDs are deterministic from source namespace, source ID and versioned locator; never silently merge by display name. Retain foreign IDs as crosswalks. IDs for derived objects include the algorithm/configuration and input snapshot identities.

| Node | Minimum properties |
|---|---|
| Artifact | `id`, collection and museum number, source IDs, object kind |
| Witness | `id`, source witness ID, language/dialect as attributed, artifact association status |
| SequenceVersion | `id`, witness ID, source revision, parser version, edition ID, raw digest, boundary policy |
| Line | `id`, sequence ID, surface, column, source line label, line ordinal |
| Occurrence | `id`, sequence ID, line ID, token ordinal, source offsets, raw token, token kind, preservation state |
| SignType | `id`, namespace, canonical source key, optional Unicode and display label |
| Reading | `id`, written value, language, reading kind; normalization policy |
| Image / Region | source image hash, dimensions; region geometry, coordinate system, crop transform |
| Composition / Passage | source work/edition identity; passage locator and language stage |
| TranslationSegment | exact text, target language, author/source, version, segment locator |
| Pattern | expression/AST, inventory namespace, length/gap limits, boundary and ambiguity policy |
| PatternMatch | pattern ID, ordered occurrence IDs, sequence ID, alignment/cost and run ID |
| Alignment | ordered source/target spans, method, score kind, source or run, review state |
| Claim | subject, predicate, object or value; asserted/proposed/rejected/superseded state; attribution and evidence |
| SourceRecord / Edition | URL, record ID, snapshot hash, license, publication/retrieval dates |
| AnalysisRun | code revision, parameters, corpus manifest, model identifier if used, reproducibility info |
| ReviewDecision | actor, timestamp, decision, rationale, superseded decision if applicable |

Probability fields are optional and typed: model score, similarity, calibrated probability, or expert confidence. Missing probability is not zero. Do not turn an uncalibrated OCR score into a probability of historical relatedness.

## 6. Edge contracts

Structural edges are deterministic organization of a source representation. Semantic and cross-source relationships have Claim/Alignment records with evidence, even if a query projection exposes convenient edges.

| Edge | Endpoints | Meaning and mandatory qualification |
|---|---|---|
| HAS_SEQUENCE | Witness → SequenceVersion | One source interpretation/version |
| HAS_LINE | SequenceVersion → Line | Source order and surface/column retained |
| HAS_OCCURRENCE | Line → Occurrence | Exact locator and token position |
| NEXT | Occurrence → Occurrence | Consecutive tokens in the same sequence and line; no skipped damage |
| NEXT_LINE | Line → Line | Source line order; does not assert textual continuity across damage/surfaces |
| ON_ARTIFACT | Witness → Artifact | Attestation/assignment with provenance; many-to-many allowed |
| IDENTIFIED_AS | Occurrence → SignType | Source-specific sign assertion, claim ID, certainty and restoration status |
| HAS_READING | Occurrence or ordered span → Reading | Claim ID; allows compound and many-to-many readings |
| DEPICTS | Image → Artifact | Source attribution |
| LOCATED_IN | Occurrence → Region | Alignment claim; absent until evidenced |
| REGION_OF | Region → Image | Pixel geometry and transform |
| ATTESTS | Witness span → Passage | Source alignment; a composition is not a physical tablet |
| TRANSLATES | TranslationSegment → Passage or witness span | Explicit target and alignment granularity; never implied word-level alignment |
| MATCH_OF | PatternMatch → Pattern | Versioned matching rule |
| MATCH_MEMBER | PatternMatch → Occurrence | Ordered match positions and gap roles |
| SUPPORTED_BY | Claim → SourceRecord / Region / Alignment | Supporting locator, evidence role and lineage |
| DEPENDS_ON | Claim or derived artifact → Claim | Directed dependency for review impact; no automatic truth propagation |
| PROPOSED_BY | Claim → AnalysisRun or source attribution | Distinguish extraction, inference and scholarly assertion |
| REVIEWED_BY | Claim → ReviewDecision | Preserve disagreements and review history |
| SUPERSEDES | New version/claim → Old version/claim | History retained, old evidence addressable |

`PREVIOUS` is the reverse traversal of `NEXT`; no independently maintained duplicate edge. `CONTAINS_SIGN` and `SIMILAR_TO` may be derived summaries, but cannot establish sequence order or semantic equivalence. A physical join, parallel passage, duplicate catalog record and shared formula are four different predicates, never one generic relatedness fact.

Gap tokens carry known/min/max/unknown extent. Default matching stops at gaps. Explicit bounded-gap queries traverse the gap representation with a declared policy; deleting `x`, brackets, breaks or line markers must not create a false adjacency. Alternative readings belong to a coherent source hypothesis, not arbitrary combinations of choices from different editions.

## 7. Query behavior

Daniel's proposed triple count maps to occurrence paths, then groups by sign identities. Conceptual Cypher below is a contract illustration, not executed code. `CorpusSelection` fixes one sequence per witness, one sign assertion per included certain token, and consistent edge projection before the query runs.

```cypher
MATCH (s:CorpusSelection {id: $selection})-[:INCLUDES]->(v:SequenceVersion)
MATCH (v)-[:HAS_LINE]->(l:Line)-[:HAS_OCCURRENCE]->(a:Occurrence)
MATCH (a)-[:NEXT]->(b:Occurrence)-[:NEXT]->(c:Occurrence)
MATCH (a)-[:IDENTIFIED_AS]->(sa:SignType),
      (b)-[:IDENTIFIED_AS]->(sb:SignType),
      (c)-[:IDENTIFIED_AS]->(sc:SignType)
WHERE a.countable = true AND b.countable = true AND c.countable = true
RETURN sa.id, sb.id, sc.id,
       count(*) AS occurrences,
       count(DISTINCT v.witness_id) AS witnesses
ORDER BY witnesses DESC, occurrences DESC
```

`CorpusSelection` and its `INCLUDES` edges are derived manifests, not source evidence. Projection invariants guarantee the NEXT path stays on this line and sequence. Every result supports a second query returning exact occurrence IDs, source locators and available image regions.

The required query catalog:

1. Exact 2–5-sign motifs, overlapping occurrence count, distinct witnesses and distinct compositions, with cohort denominators.
2. `A B [0–2 tokens] C` with explicit boundary and damage handling; count one matched span once even if alternative paths reach it.
3. `A ? C` grouped by middle sign and period/genre; unknown damaged slots are not a sign category with a guessed reading.
4. Same motif across witnesses with different readings/translations; return evidence for proposed correspondences.
5. Unusually enriched motifs by cohort compared with a matched background; keep rare-count uncertainty visible.
6. Candidate fragments ranked by rare shared patterns plus compatible ordering; return aligned spans, not only a score.
7. Remove/change one interpretation in a hypothetical branch and list dependent matches, translations and claims needing review.
8. Find high-impact uncertain occurrences worth specialist inspection.

Frequency is evidence of recurrence, not a probability of shared meaning or physical joining. Report occurrence frequency, independent-document support and a declared enrichment measure separately. Background controls should preserve language/stage, genre, sequence lengths and relevant sign frequencies. Use held-out data to confirm exploratory patterns and control multiple testing. Catalog duplicates and repeated editions count once per physical/witness unit; copies of a work are reported as copies, not independent events.

## 8. Storage and execution

Proposed local architecture: immutable source files plus typed Parquet node/edge/assertion tables; DuckDB for audits, joins and full-corpus counts; an isolated FalkorDB graph projection for interactive traversals if query tests justify it. No dependency on or writes to live CompanyKit services. A graph-only prototype is acceptable at small scale; benchmark before adding infrastructure.

Sequence arrays and inverted n-gram indexes handle repeated large scans. Store selected PatternMatch nodes for results users inspect, not every conceivable subsequence. The graph is the common evidence model; bulk counts need not be recomputed by expensive graph traversal on every request. Do not promise that one expressive query has low computational cost.

Index IDs, sequence/line/position, sign namespace/key and source record. Use bounded path lengths and candidate retrieval before alignment. Estimate cardinality from the pilot: N occurrences imply approximately N NEXT edges, plus actual assertion and evidence links. Avoid quadratic all-pairs similarities and all-length motif materialization. Record disk, memory and latency with dataset sizes and hardware.

## 9. Human review experience

An inspectable result has four synchronized views: source tablet/line or image crop, token sequence with damage and alternatives, matching passages and differences, and readings/translations with explicit dependencies. Users can filter a cohort, select a motif and examine its actual occurrences.

Show whether text is copied from a scholarly source, produced by deterministic conversion, OCR-predicted, or model-proposed. Missing images or translations remain visibly absent. Review decisions create new records, not overwrites. Export a compact evidence packet containing IDs, links, spans, methods, alternative explanations and unresolved questions.

## 10. Experiments and acceptance criteria

### A. Data and query integrity (mandatory)

Use hand-checked fixtures for repeated signs, duplicate catalogs, multiple editions, compounds, alternate readings, cross-line boundaries, restored text, and unknown-length gaps. Prove exact agreement between independently computed token-array counts and graph motif counts on these cases. Every displayed occurrence must resolve to an unchanged source span. These checks establish representation integrity, not linguistic correctness.

Pilot audit covers all 30 selected records and reports every parse exclusion, ambiguous crosswalk and missing field. The baseline count view includes source-transcribed certain tokens only; reconstructed and OCR hypotheses are opt-in projections. A scholar's reading may still be wrong; source certainty is recorded as attribution.

### B. Fragment retrieval (research)

Freeze known relationships and data partitions before tuning. Hold out entire artifacts and duplicate catalog aliases; prevent alternate editions and composites containing the held-out witness from leaking into the reference representation. Remove target ATTESTS/join/composition labels from inference features. Keep a separate evaluation-only gold table.

For known-work retrieval, retain independent witnesses of the same composition as legitimate references. For generalization, add a composition-family holdout. These answer different questions and must be reported separately. Artificially damaged text is a secondary stress test, not the only benchmark.

Compare (1) eBL-compatible n-gram baseline, (2) same sequences with contextual constraints and ordered alignment, (3) alternative-reading-aware retrieval, and (4) optional visual evidence. Use identical corpus/split for paired comparisons; include a SQL/index implementation with the same information to isolate graph representation from added information.

Report Recall@10/@50, reciprocal rank, candidate-review burden, latency and clustered uncertainty intervals. Report physical joins, passage parallels and formulas separately. Unlabeled candidates are unjudged, not false matches. Suggested continuation threshold: at least 10% relative improvement in Recall@10 or 20% reduction in review burden at matched recall, with no unresolved leakage and adequate expert review. These are proposed decision thresholds, not expected results; revise before testing if pilot sample size makes them uninformative.

### C. Interpretation dependencies (workflow)

On 10–20 expert-selected ambiguous passages, trace alternative readings to their supporting evidence and downstream interpretations. Source material may lack explicit fine-grained dependencies; annotate these with attribution rather than pretending to extract established facts. Measure time and error rate for finding supporting evidence against the existing interface, and count dependency claims requiring correction. Without specialist participation, report only technical traceability and usability, not philological benefit.

### D. Pattern discovery (exploratory)

Freeze candidate rules on a discovery subset, confirm on a held-out subset, and have reviewers classify surfaced patterns as known formula, useful variant, artifact, uncertain or potentially novel. A candidate is not a discovery until prior scholarship and source evidence are checked. A graph count alone cannot justify a translation or relationship.

## 11. Delivery sequence and stop decisions

1. **Source feasibility packet:** sample records, schemas, rights matrix, coverage/crosswalk audit and selected cohort. Deliver even if a necessary source is unavailable.
2. **Occurrence graph and motif queries:** exact counts, gap semantics and source click-through on the bounded cohort. Requires A to pass.
3. **Dependency explorer:** a small set of explicitly sourced alternative readings and translation links. Scope follows verified data granularity.
4. **Retrieval experiment:** frozen baseline, ablations, results and reviewed candidate packets. Requires enough independently known examples.
5. **Visual extension:** add matched image regions and sign-shape embeddings only after actual alignment coverage and rights are confirmed.

If translations lack suitable alignment, ship passage-level dependencies and mark finer links unavailable. If only transliteration-derived signs are available, label the first experiment text-based. If evidence tracing is useful but retrieval shows no gain, retain the smaller tool and publish the negative result. If neither workflow improves, stop expanding the graph.

The immediate deliverable is this specification and independent review. Implementation, corpus-wide downloads, new paid model experiments, deployment and external outreach are later work, not performed by this document.

## 12. Evidence ledger and remaining questions

Sources below were inspected on 2026-11-02 through project documentation/web retrieval. No full data export, live graph, model run or benchmark was executed for this specification. Published counts elsewhere in the discussion are not our audited corpus counts.

- S1: https://github.com/ElectronicBabylonianLiterature/ngram-matcher — existing baseline, data examples and OCR option.
- S2: https://aclanthology.org/2024.lrec-main.1197/ — text-matching paper.
- S3: https://proceedings.iclr.cc/paper_files/paper/2025/file/dcc94df619b859a3f532eb0436f49a9b-Paper-Conference.pdf — ProtoSnap.
- S4: https://proceedings.mlr.press/v88/kriege18a.html — graph-based sign recognition.
- S5: https://prosobab.leidenuniv.nl/guide.php — evidence versus resolved identities.
- S6: https://github.com/ElectronicBabylonianLiterature/transliterated-fragments and https://raw.githubusercontent.com/ElectronicBabylonianLiterature/transliterated-fragments/main/ebl/example.py — documented text acquisition.
- S7: https://zenodo.org/records/14009952 — OCR dataset release; field schema not inspected.
- S8: https://github.com/taineleau/CuneiML — documented fields and image-rights separation.
- S9: https://github.com/cdli-gh/data — older bulk catalog/text snapshot.
- S10: https://corpus.writing-sumerian.assyriologie.uni-muenchen.de/help — search-indexed terminology distinguishes sign, grapheme and glyph; direct page extraction returned no text, so terminology should be verified with a specialist before finalizing a universal sign model.

Open: actual source coverage and licensing; alignment export; independent evaluation labels; sign-inventory mapping; compound segmentation; whether our workflow adds value over eBL tools; a suitable expert collaborator. None is resolved by adopting a graph database.
