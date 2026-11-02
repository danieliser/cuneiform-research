# Cuneiform symbol and evidence workbench

2026-11-02 · v0.2 · Parent synthesis after independent Claude Opus 5.5 high review.

This is the authoritative specification. It incorporates and supersedes SPEC-v0.1.md and MULTIMODAL-MCP-ADDENDUM-v0.1.md; both remain frozen for provenance. The review is preserved separately. No corpus, running graph, MCP server, learned alignment or benchmark result has been produced. v0.2 has not had a second independent review.

## 1. Intended result

Give people and agents a queryable graph linking individual symbol occurrences, ordered passages, recurring patterns, physical fragments, scholarly readings, words, dictionary senses, translations, source images and tablet metadata. A result should answer both “where does this occur?” and “what evidence supports this interpretation?”

The strongest initial contribution is **pattern exploration with explicit uncertainty and interpretation dependencies**. Users can count motifs, inspect variants, follow their English interpretations, and identify readings whose reconsideration would affect many results. Fragment retrieval is an existing capability to reproduce and extend experimentally. Finding new physical joins still needs qualified assessment.

Keep the user's full roadmap: translation vectors, visual symbol vectors, bidirectional search, source-image coordinates, and agent access through MCP. Stage these by data availability. Building a graph is an engineering choice; its scientific contribution must be established through tasks and evidence.

## 2. Research questions and first demonstrations

1. **Motifs and variants:** Which sequences recur across independent witnesses? Which positions admit substitutions? How much do motif counts change when restored or uncertain readings are excluded?
2. **Interpretation dependencies:** Which words, senses, translations and matches depend on a disputed reading? Are two supporting passages independent, or does one restoration derive from the other?
3. **Review priorities:** Can witness disagreement and dependency impact help locate records that later receive substantive editorial changes?
4. **Bidirectional evidence search:** Can an English query reach relevant words, sign occurrences and images, and can a crop reach candidate signs and contextual readings?

First demonstration: a small manuscript family with aligned passages, selectable sign/lemma motifs, alternative readings and source click-through. A second, conditional demonstration compares an older openly reusable translation with a modern edition over roughly 20–50 lines. Differences in wording, underlying reading and newly available evidence must be distinguished. Historical and modern translations are candidate sources, not yet verified assets.

## 3. Source selection and admission

Start with a 30-record feasibility audit. Select one eBL chapter family only after confirming usable witness alignments, translations and word analysis. A Standard Babylonian Gilgamesh or Enūma eliš tablet is a candidate. Target 20–50 witnesses for close reading; expand to 300–1,000 fragments and matched distractors only if the actual corpus supports it. These are scope targets, not observed counts.

| Source | Role | Current evidence and remaining gate |
|---|---|---|
| eBL frozen fragments, [Zenodo 10018951](https://zenodo.org/records/10018951) | Reproducible historical source snapshot | Parent verified v2 dated 2023-10-18 and a 73.9 MB fragments.json. Contents and coverage have not been audited here |
| [eBL text interface](https://github.com/ElectronicBabylonianLiterature/transliterated-fragments) and corpus editions | ATF, current revisions, witness/passage relationships, translations where provided | Public access code documented; actual export field availability, historical revision content and alignment coverage remain gates |
| [ORACC open data](https://oracc.museum.upenn.edu/doc/opendata/) and [JSON documentation](https://oracc.museum.upenn.edu/doc/opendata/json/index.html) | Word/lemma/sense/gloss bridge and translated texts | Reviewer reports project exports and CC BY-SA 3.0. Parent requests returned HTTP 502; verify selected project files, rights and overlapping texts before use |
| [eBL n-gram matcher](https://github.com/ElectronicBabylonianLiterature/ngram-matcher) and [paper](https://aclanthology.org/2024.lrec-main.1197/) | Baseline method and sign-sequence format | Existing implementation includes OCR input and overlap reporting. Reviewer found no repository license file; code reuse rights need confirmation |
| [eBL OCR release](https://zenodo.org/records/14009952) | Later model-generated sign detections | Public named release; coordinates, label semantics, source-image mapping and cohort overlap unverified. Not assumed aligned to text tokens |
| [CuneiML](https://github.com/taineleau/CuneiML) | Later independent corpus adapter and image/text references | Documented face crops are not sign-level boxes. Unicode derived from transliterations is not independent visual evidence |
| [CDLI catalog](https://github.com/cdli-gh/data) and individual collection records | External IDs, provenance, period and image references | Repository README says August 2022 snapshot. Audit freshness, per-asset rights and crosswalks |

Freeze raw bytes, source IDs, retrieval times, checksums, source revisions, parser versions, rights records, cohort membership and exclusions. Keep failed/unparseable records in the accounting. Live updates create a new snapshot; they never overwrite the baseline.

Rights ledger: preserve the review-reported conflict between the eBL Zenodo license label and data-paper license. Mark the applicable terms unresolved; do not resolve the conflict merely by selecting the “stricter” string. Defer redistribution/commercial reuse until the applicable grant is established. Image, text, annotations and code have separate terms. ORACC project terms and downstream attribution/share-alike obligations require asset-specific verification. Missing license is not permission. This specification does not authorize publication or outreach.

## 4. Data model

Maintain a canonical source-preserving token table and typed node/edge tables. Deterministic IDs include source namespace, record identity, revision and locator as appropriate. Crosswalks and equivalence claims never merge records solely by display name.

| Object | Contract |
|---|---|
| Artifact | Physical tablet or fragment; accession IDs and source-attributed metadata |
| Witness | A manuscript contribution; can span joined artifacts or share an artifact with another text |
| Composition / Passage | Abstract work and edition-specific passage identity |
| SequenceVersion / Line | One source interpretation of a witness segment; surface, column, source line label/order, raw offsets, parser revision |
| SignOccurrence | Position in a particular sequence; raw source token, kind, editorial reading/value/index, role and uncertainty fields |
| WordToken | Edition-specific grouping of ordered sign occurrences; segmentation attribution and alternative grouping IDs |
| SignType | Namespaced sign-list identity, list revision and optional Unicode/display form |
| Lemma / Sense | Namespaced dictionary entry, citation form, part of speech, guideword/sense/gloss, language and dictionary version |
| TranslationSegment | Source-authored text with language, author, citation, revision and aligned span granularity |
| Pattern | Bounded expression over signs or lemmas; namespace, gap, boundary, segmentation and ambiguity policy |
| Claim | An alternative, interpretation, inferred link, model output or reviewed assertion with explicit provenance and status |
| SourceRecord / Edition | Immutable source content reference, exact locator, checksum, attribution and rights |
| ImageVersion / Region | Versioned pixels and explicit geometry; occurrence correspondence is a separate claim |
| EmbeddingRecord | Object/version, model-space ID, preprocessing, dimensions, metric, input hash and vector-store reference |

Manifest records represent CorpusSelection and AnalysisRun. Local append-only decisions carry reviewer identity, time, rationale and expected prior revision. A persisted PatternMatch is optional for saved evidence packets; bulk motif matches remain indexed rows/results.

### Evidence direction

For source transliterations, preserve the editor's reading as the source fact. A versioned sign-list conversion derives the SignType; the derivation does not independently confirm the reading. The LREC paper explicitly describes conversion from readings to ABZ identifiers. For images, detector/classifier output proposes a sign identity, then contextual analysis proposes a reading. Keep these two evidence paths distinct.

English interpretation normally follows contextual words and senses. Some signs function as logograms, so “signs never have meaning” is too absolute; still, a standalone shape is not guaranteed to identify one English word. A gloss belongs to a dictionary sense, while a translation can paraphrase a wider passage.

### Uncertainty and segmentation

Store physical preservation (`intact`, `damaged`, `lost`, `unknown`), editorial certainty, and restoration basis separately. Also retain raw editorial marks and parser-specific interpretations; do not flatten collation/correction marks into certainty scores. Restoration basis is `explicit`, `proposed`, or `unknown`, linked to its cited or hypothesized source.

Exclusive alternatives have hypothesis-group IDs and compatibility constraints. Word segmentation and sign inventory can differ across editions. Under a selected sign list, a compound sign can be one sign occurrence; multi-sign word spellings/logograms span several occurrences. Preserve the source's component structure and determinatives rather than inferring segmentation by splitting on punctuation. Numerals retain notation and system/value when supplied; unknown values remain unknown.

## 5. Edge registry

Direct source facts inherit SequenceVersion/SourceRecord provenance. Use explicit Claim records where alternatives, inference, independent sources or review require them; avoid a separate Claim for every deterministic containment edge.

| Edge | Endpoints and qualification |
|---|---|
| HAS_SEQUENCE / HAS_LINE / HAS_OCCURRENCE | Witness → sequence → line → occurrence; source positions retained |
| NEXT | Occurrence → occurrence, including gap/damaged tokens, in one line and sequence; immediate source order only |
| NEXT_LINE | Source line order; no implied continuity across surfaces or breaks |
| HAS_WORD / HAS_SIGN | Sequence → WordToken → ordered sign occurrences, qualified by segmentation hypothesis |
| MAPS_TO_SIGN | Source reading occurrence → SignType, with sign-list revision, mapping rule and ambiguity group |
| IDENTIFIED_AS | Image region → proposed SignType, with detection/classification claim; no implicit text alignment |
| LEMMATIZED_AS / HAS_SENSE | WordToken → Lemma → Sense, source-attributed or proposed |
| ON_ARTIFACT / ATTESTS | Witness → Artifact; witness span → Passage, each with attribution |
| TRANSLATES | TranslationSegment → word/span/passage; explicit alignment granularity |
| ALIGNED_WITH | Span ↔ span or occurrence ↔ region through an alignment Claim subtype |
| RESTORED_FROM | Reading/claim → supporting witness span or edition, explicit or proposed |
| DEPENDS_ON / SUPPORTED_BY | Interpretation or result → claim/source/span; support is not truth propagation |
| REVIEWED_BY / SUPERSEDES | Append-only review and version history |
| HAS_IMAGE_VERSION / HAS_REGION / HAS_EMBEDDING | Artifact → image → region; embeddable object → embedding |
| FOUND_AT / WRITTEN_AT / HELD_BY | Distinct attributed geographic/custody relationships |
| HAS_EDITION / HAS_TRANSLATION | Artifact/witness/passage → scholarly sources with coverage and attribution |

Physical-join claims group artifacts with provenance; they differ from duplicate-catalog identity, parallel passages and shared formulae. Source independence is `independent`, `derived`, or `unknown`. Identical text syndicated across catalogs never becomes independent corroboration.

## 6. Motif queries and count semantics

NEXT includes every represented position, including gaps. An exact sign query fails on an unreadable gap; it never jumps it. A bounded-gap pattern explicitly permits unknown/skipped spans under its declared extent policy. Word-boundary crossings are reported separately. Cross-line matching is off by default.

A materialized query projection selects a snapshot, one edition/sequence per witness, a compatible hypothesis policy and the boundary rules. Certain-only projections have exactly one selected sign identity per included position. Alternative-aware evaluation operates over compatible assignments, not Cartesian products of independent edges.

Required query recipes:

- Count exact sign motifs of length 2–5 and retrieve their exact source positions.
- Query `A ? C`, group middle alternatives and inspect manuscript variants.
- Query `A B [0–2 positions] C` under declared gap rules.
- Query word/lemma sequences where analysis exists; report unanalysed coverage.
- Trace motif occurrences to words, senses, translation spans, metadata and available image regions.
- Change an interpretation in a hypothetical branch and enumerate affected matches/claims without changing source records.

Each motif result reports occurrence support, distinct witnesses, deduplicated artifact support, composition support and denominators. Artifact totals come from distinct match-to-artifact associations, not counts after an expanding join. Overlapping matches have stable span IDs; multiple alternative paths to the same match do not inflate counts.

Return a certain-evidence count and conservative lower/upper bounds **over the represented compatible alternatives**. For exact bounds, minimize/maximize total support over globally compatible assignments; per-position possible matches cannot simply be summed when their choices conflict. If the matcher only computes a loose envelope, label it conservative/non-tight. Unknown-length losses and omitted alternatives mean these are not bounds on the original complete ancient text. Bound computation has a complexity budget and can return unresolved bounds rather than false precision.

Frequency is not semantic relatedness or join probability. First-stage output is descriptive. Larger stratified cohorts and held-out confirmation are prerequisites for enrichment testing; avoid pooling language traditions and copying practices as independent samples.

## 7. Bidirectional search and image coordinates

Keep three retrieval paths with labeled evidence:

1. English lexical/gloss lookup → Lemma/Sense → WordToken → SignOccurrence → evidenced Region.
2. English translation embedding search → TranslationSegment → aligned passage → source occurrences. Do not claim finer alignment than the source supports.
3. Image crop → visual neighbors/top-k sign candidates → attested occurrences → contextual readings/words/senses/translations. A candidate remains a candidate.

Separate text and image embedding spaces initially. Shared-space training or a reranker is a later experiment once reviewed paired spans/regions, usage rights, meaningful baselines and artifact-level leakage controls exist. A CNN/vision transformer plus sequence context remains a possible implementation. Freeze labeled train/dev/test identities before fitting; keep aliases, joins and photo augmentations together and audit any upstream model's training overlap.

Each image region references immutable pixels by hash and dimensions; geometry is in original pixel coordinates. First viewer supports boxes/polygons, crop offsets, resize and zoom with invertible transforms. Rotation/perspective support is later; requests fail explicitly until implemented. New bytes at the same URL create a new ImageVersion and require coordinate revalidation. IIIF and Web Annotation are interoperability options, not assumed source capabilities.

Use provided regions when available. A manually reviewed pilot of up to 50 occurrences is a possible alignment-feasibility exercise, not sufficient training-data evidence. Text-derived occurrences have no inferred image coordinates by default. An OCR-to-transliteration alignment is a scored, reviewable result. Every displayed crop identifies the source image and transformation.

## 8. Tablet metadata

At minimum: catalog IDs/crosswalks, custody, attributed period/language/genre, findspot, proposed origin, source editions, image availability and translation coverage. Unknown is explicit. Trench/locus/excavation details, dimensions and calibrated ancient-date intervals are retained where present, not manufactured from collection prefixes.

Translation status is per target language, source search scope, snapshot and coverage denominator: published translation located, partial translation located, machine draft only, no translation located in searched sources, or unknown. Record institution/editor review labels as source attributions. Never derive “never translated” from one database's missing translation field.

## 9. Storage and MCP

Canonical storage: immutable raw files plus typed Parquet token, node, edge and claim tables. DuckDB supports audits, counts and joins. A graph projection is part of the planned evidence interface; an isolated FalkorDB instance remains an option for traversals when query needs justify it. No live CompanyKit service changes. Sequence indexes and cached counts can coexist with graph queries. Materialize only bounded or saved pattern results.

First MCP slice has five read tools: `corpus_search`, `record_get`, `sequence_get`, `pattern_search`, and `evidence_trace`; add `proposal_create` with append-only, idempotent local writes. The next data-qualified slice adds `similarity_search` and `image_region_get`. Async analysis and authorized review tools follow demonstrated workflow needs.

Contracts: typed input/output schemas; resolved snapshot IDs; default 20/max 100 results; cursor pagination; bounded motif/gap lengths and traversal depth; timeouts/truncation markers; exact source locators. Errors distinguish unknown IDs, incompatible embedding spaces, missing alignment, changed image versions, unsupported geometry, rights restrictions and stale revisions. No generic query/code execution endpoint. Proposals never auto-promote themselves to scholarly truth. Actual SDK/spec/transport versions are selected and pinned at implementation time.

MCP resources expose manifests, schemas, source references and evidence packets. Server permissions and resource allowlists enforce access, not annotations or remote text. Model execution, if later added, uses an explicit configured budget and approved provider path.

## 10. Validation and research design

### Required integrity checks

- Exact parity among hand fixtures, independent array counting, token-table queries and NEXT projection for unambiguous motifs. Do not declare one untested implementation the oracle.
- Alternative fixtures: two sign assertions, incompatible global choices, overlapping patterns, unknown-length gaps, restored/damaged readings, compounds, determinatives and alternative word segmentation.
- Every included token resolves to unchanged raw bytes and source offsets; exclusions are enumerated. Mapping coverage is reported, not filled to meet a threshold.
- Audit metadata distinctions, translation coverage, alignment granularity and evidence independence on all 30 pilot records.
- Source-attributed dependency traces must show known versus proposed restoration basis. Cycles in proposed support are review flags, not automatic proof of an error.

### Baseline retrieval

Implement or permissibly run the published eBL method on frozen inputs. Compare output with a matched reference configuration when possible. A reproduction tolerance against the paper is meaningful only with matching data, split, sampling and metric definitions; a new corpus cannot be required to fall within ±0.02 of its published score. Record deviations explicitly. The paper's P@3 naming must be implemented according to its definition, not assumed identical to standard precision or recall.

The earlier generic +10% Recall@10 continuation threshold is withdrawn. First benchmark pipeline correctness; later select task-specific thresholds before experiments. True new matches and no-match cases require expert judgment. Similarity alone cannot certify a physical join.

Exclude restored and damaged-but-read tokens in a strict evidence view, while keeping the original complete source view for comparison. Exclusion must break motif paths, not concatenate surrounding tokens. Remove evaluation labels and reconstructed composites containing the target from inference. If identification timestamps/history are unavailable, disclose inability to establish pre-identification evidence. Logographic/lemma features must also be checked for editorial leakage.

### Review prioritization

Historical snapshot → current snapshot comparison is a candidate experiment. Confirm recoverable old text and reliable token alignment first. Separate substantive reading changes, formatting, annotation additions, new joins and deletions. Features use only baseline-time data and baseline-time dependencies; modern alignments cannot leak into ranking.

Compare uncertainty/damage flags, recency where known and random ranking against witness disagreement and dependency impact. Cluster by artifact/witness family. Use precision@k and effort-aware review yield with uncertainty intervals; leave unresolved token diffs unscored. An unchanged token is unlabeled, not proven correct. Revisions reflect editorial attention as well as interpretation changes. The defensible outcome is retrospective revision prioritization, not translation correctness or proven time savings.

### Language, visual and agent checks

Hand-check source alignments and mechanically detectable differences first; lexical/orthographic classification and new restorations require appropriate expertise. Historical translation alignment is reviewed before using it as a demo. Report inspection effort and missing coverage.

Image/English retrieval is evaluated only on reviewed correspondences with an explicit granularity and leakage audit. Test lexical bridges before claiming vectors add value. Exercise real MCP client discovery, bounded queries, resource/image loading, typed errors, stale revisions and idempotent proposals. Geometry round-trips are technical checks; they do not validate sign identity.

## 11. Delivery phases and decisions

1. **Feasibility:** 30-record evidence packet, selected corpus, rights/coverage ledger, available word and translation layers, existing-tool comparison. Stop dependent features if their sources are unavailable.
2. **Pattern/evidence core:** source-preserving graph model, sign/lemma motifs, uncertainty bounds, witness variant views, dependency traces and initial MCP slice.
3. **Retrieval and revision studies:** reproduced matching baseline and conditional historical revision experiment. Retain negative results; do not expand claims beyond the evaluation.
4. **Multimodal navigation:** usable translation vectors, rights-cleared regions, manual/source alignments, visual neighbors and image MCP tools.
5. **Learned cross-modal work:** proceed only after paired-data coverage, label quality and baseline failure modes justify training. No architecture or discovery claim is precommitted.

No implementation or corpus download is performed in this spec task. Primary outstanding dependencies are the actual source schemas, per-project rights, alignment coverage, old revision availability and specialist participation. Review prioritization and motif tools can still be technically useful when deeper linguistic validation is unavailable, but must be described at that level.

## 12. Review provenance

See [independent review](reviews/opus-5.5-high-review.md) and [disposition](reviews/disposition-v0.2.md). Primary documentation was checked in the preceding drafts and review. The parent independently revisited the frozen Zenodo record and LREC paper, while ORACC requests failed with HTTP 502. Review-only source facts remain attributed and require source-audit confirmation. No performance figures from the review are presented as our results.
