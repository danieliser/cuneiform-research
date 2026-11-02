# Multimodal retrieval, source coordinates and agent access

2026-11-02. User-directed extension to SPEC-v0.1.md; proposed contracts, not implemented functionality. Incorporate into the next reviewed specification while preserving the original draft.

## 1. Intended workflow

An agent or researcher can start with an English word/passage, a photographed symbol/region, a sign sequence or a tablet ID. Retrieve candidates, traverse their source evidence, compare readings and inspect the actual marked image region. Save a proposed interpretation with explicit provenance for review.

Examples:

- English concept → translated passages → aligned source spans → symbol occurrences → image crops and usage contexts.
- Image crop → visually similar sign occurrences → candidate sign identities/readings → aligned translations and contextual English descriptions.
- Tablet → findspot/origin/collection metadata → editions and translation coverage → recurring patterns → related fragments.

The graph connects evidence across modalities. Text and image vector indexes supply ranked candidate neighbors. Optional CNN/transformer encoders or learned cross-modal alignment are later experiments using the same evidence model.

## 2. Embedding and alignment model

Store an `EmbeddingRecord` for each embedded object: stable object/version ID, modality, model/version, preprocessing revision, dimensions, metric, input hash, vector-store reference, creation run and intended task. Never compare incompatible model spaces or mix revisions silently. Embeddings are derived data, not assertions that two objects mean the same thing.

Initial independent indexes:

1. Translation segments and contextual glosses for English semantic retrieval. Preserve source language, translation version/author and whether a gloss is human or machine produced. Keep word-query context and alternative senses visible.
2. Sign/line crops for visual similarity. Preserve image hash, region geometry, preprocessing, orientation, lighting information where known and detection source. A sign prototype and a real photographed occurrence are different kinds of input.

**Stage 1 — graph-mediated bidirectional search:** retrieve in one modality, then follow evidenced alignments to the other. Return the alignment granularity: sign, word, phrase, line, passage or document. A passage about grain does not label every sign in that passage as “grain.” Do not assume one sign equals one English word; readings can be syllabic, logographic, determinative or compound, and translations can paraphrase.

**Stage 2 — learned alignment:** evaluate a shared image/text embedding space or a reranker trained on reviewed occurrence/span pairs. Use independently supported positive pairs and hard negatives such as the same sign with another contextual reading, similar-looking signs, and unrelated passages with shared formulae. Weak passage-level labels remain weak supervision. Frozen general-purpose encoders are baselines, not presumed cuneiform experts.

**Stage 3 — sequence/vision model:** compare a CNN or vision transformer encoder combined with a contextual sequence model only if the pilot establishes sufficient paired data and error analysis supports it. Architecture selection follows the task and data; no specific paid provider/model is chosen in this spec.

Do not use an English translation generated from a candidate reading as independent evidence that the reading is correct. All generated glosses and synthetic data retain their input dependencies. Benchmark whole-artifact and composition-family holdouts, and keep all photos/augmentations of the same physical object in the same partition.

## 3. Image geometry and live coordinate resolution

Add `ImageVersion`, `Canvas` where supplied, `Region`, and `GeometricTransform` records. An ImageVersion has immutable byte hash, pixel width/height, orientation, source URL, rights and acquisition metadata. A Region has a pixel bounding box or polygon in one declared parent-image coordinate system. Store normalized coordinates only as an additional convenience, not a replacement for explicit pixel geometry.

Transforms record crop origin, scaling, rotation and any perspective warp between original, cropped, derived and displayed images. A viewer resolves pointer coordinates through the inverse transform to source pixels, then looks up intersecting regions. Round-trip tests must locate the same region after zoom, resize, rotation and crop operations. Unsupported transformations return an explicit error rather than approximate coordinates.

Each symbol occurrence may map to zero, one or multiple regions; each region can participate in competing segmentation/alignment hypotheses. Line crops do not imply known per-sign boxes. Overlapping detections are retained with detector identity and score. Reviewed coordinates remain distinguishable from model-generated ones.

On fetching a source URL again, verify its bytes or a trustworthy version identifier. A changed image requires a new ImageVersion and coordinate revalidation. Old boxes must not be drawn on new pixels silently. “Live coordinates” means resolving the displayed, identified image version; it does not mean treating a mutable URL as a stable image.

Use IIIF region retrieval and manifests when a provider offers them; IIIF support is not assumed for all collections. A W3C Web Annotation-compatible target/selector export can preserve source-region links. Our canonical geometry remains explicit even where a source has no IIIF service.

## 4. Document and tablet metadata

Extend Artifact/Witness metadata through source-attributed claims and preserve conflicting values:

| Field group | Representation |
|---|---|
| Identifiers | museum/accession ID, excavation number, CDLI/eBL/source IDs and reviewed equivalence claims |
| Find context | excavated findspot, site, trench/locus/context, coordinates with precision, excavation campaign and source |
| Ancient context | proposed place of writing, archive attribution, ancient place names and source-specific geographic mappings |
| Current custody | institution/collection, catalog URL, location history where documented |
| Dating | source date expression, proposed calendar conversion, range, period, uncertainty, basis and conflicting claims |
| Language/script | attributed language/dialect, script tradition, period-specific sign inventory; mixed-language spans where available |
| Object | material, dimensions, surfaces, damage, fragment/join claims and image coverage |
| Content | source genre, composition attribution, synopsis and bibliography |
| Edition | publication citation, editor, revision, transliteration/transcription coverage and access/rights |
| Translation | language, author/publisher, citation, version, target spans, coverage, review attribution, human/machine origin and access/rights |

Do not collapse findspot, inferred origin and current collection location into one `location`. Missing archaeological provenance is a retained state.

Translation status is a derived, queryable summary of positive source evidence: `published_translation_located`, `partial_translation_located`, `machine_draft_only`, `no_translation_located_in_searched_sources`, or `unknown`. Scope every summary to a target language, searched sources, corpus snapshot and time. “No translation located” does not mean never translated. Full/partial coverage must name its denominator (surviving edited text, a passage, or an entire work); missing coverage stays unknown. An “official” label is permitted only as an attributed institutional designation, not inferred from a website's appearance.

Additional relationships: `HAS_IMAGE_VERSION`, `HAS_REGION`, `TRANSFORMED_FROM`, `HAS_EMBEDDING`, `ALIGNED_WITH` (backed by Alignment), `FOUND_AT`, `WRITTEN_AT`, `HELD_BY`, `HAS_EDITION`, and `HAS_TRANSLATION`. Geographic and textual assertions use the existing Claim/evidence machinery.

## 5. MCP tool surface

Use the current maintained SDK when implementation begins; transport/version will be selected then. Begin local with bounded read tools and separate proposal-writing permissions. Tool annotations describe intent; server code enforces permissions, limits and resource access. No arbitrary Cypher, SQL, filesystem path or network URL execution tool in the initial interface.

All reads require a frozen `snapshot_id` (or return the resolved snapshot when explicitly requesting latest), return stable IDs, evidence locators, source status and cursor pagination where needed. Limits default to 20 results, max 100; traversal depth max 4, motif length max 12, bounded gap max 5, with a server timeout and explicit truncation flags. These are initial operational bounds, subject to measured tuning.

| Tool | Typed input essentials | Result / purpose |
|---|---|---|
| `corpus_search` | text, language/period/genre/place/status filters, snapshot, cursor, limit | Artifact/witness IDs with metadata claims and coverage; semantic search opt-in |
| `record_get` | record ID, requested sections, snapshot | Artifact/witness metadata, editions, translations, images and source-attributed conflicts |
| `sequence_get` | witness + sequence version, surface/line range, hypothesis policy | Ordered occurrences, gaps, reading alternatives and source spans |
| `pattern_search` | bounded pattern AST, cohort, match/ambiguity policy, snapshot, cursor | Counts, denominators, exact matches, method; counts never labeled probabilities |
| `similarity_search` | query kind `english_text|image_region|sign_sequence`, text or stored region ID or bounded image upload handle, target kind, model-space ID, filters, limit | Candidates with separate lexical/visual/semantic scores, graph paths and alignment granularity |
| `image_region_get` | stored image/version ID, region ID or bounded pixel geometry, desired output size | Permitted crop as image content/resource plus coordinate transform and occurrence IDs |
| `evidence_trace` | entity/claim/translation ID, direction, relationship allowlist, depth, limit | Bounded dependency/support paths with assertions and contradictions |
| `analysis_start` / `analysis_get` | allowlisted job type, frozen inputs and config / returned job ID | Reproducible large motif or retrieval job, status and result references; no unbounded synchronous scans |
| `proposal_create` | subject, typed predicate, target/value, evidence IDs, rationale, base revision, idempotency key | Creates a proposed claim, never accepted scholarly truth |
| `proposal_review` | proposal ID, decision, rationale, reviewer identity, expected revision, idempotency key | Authorized review record; cannot grant itself reviewer privileges |

Expose immutable source records, schemas, manifests, query recipes and reports as MCP resources with asset rights enforced on content retrieval. A small discovery resource explains supported fields and filter semantics. Return useful typed errors: `unknown_id`, `snapshot_mismatch`, `image_version_changed`, `alignment_unavailable`, `incompatible_embedding_space`, `unsupported_transform`, `rights_restricted`, `budget_exceeded`, `revision_conflict`. Partial evidence returns explicit missing fields rather than fabricated defaults.

Semantic search over translation passages and cross-modal symbol retrieval must be separate reported stages. Do not describe the latter as available just because two vector collections exist. Analysis jobs can run deterministic computations under configured limits; paid model execution requires an explicitly configured budget and authorized provider path.

## 6. Agent acceptance exercises

1. Find a known motif and retrieve its exact positions and source regions through MCP. Counts agree with independent sequence-array results.
2. Given an English passage query, retrieve its known translated passage and navigate to the correct source span. Report passage-level alignment when finer alignment is absent.
3. Given a held-out image crop, retrieve independently labeled sign candidates and show contextual reading alternatives without declaring one English meaning.
4. Given a tablet with incomplete metadata, report findspot, inferred origin, custody and translation status without conflating missing evidence with negative facts.
5. Trace an alternative reading to affected translation segments and save a proposal. Test repeated idempotency keys, stale revisions and unauthorized review attempts.
6. Change a source-image version in a fixture; stale coordinate requests must fail explicitly. Exercise actual MCP client tool discovery, image output and resource loading, not just direct function calls.

Evaluation adds text-to-image and image-to-text Recall@k on reviewed alignments, results by alignment granularity, abstention/coverage, and specialist relevance judgments. A separate lexical path baseline tests whether vector retrieval adds useful evidence beyond known dictionary/translation links. No historical discovery is established by embedding proximity.

## 7. Sequencing and open feasibility questions

Add metadata and region/transform contracts to the source audit immediately. Include English translation search plus graph-mediated source navigation in the first interface when translations are available. Add visual nearest-neighbor retrieval after a verified crop/alignment subset exists. Build only the MCP tools needed for this vertical slice first; defer asynchronous training and learned shared-space models until paired-data and baseline results justify them.

Source constraints still apply: image availability and rights, image version identifiers, sign-level coordinates, translation alignment and a qualified reviewer are unverified for the proposed cohort. These are fields to audit, not assumed capabilities of eBL/CDLI.

References inspected for design direction: https://modelcontextprotocol.io/specification/2025-06-18/server/tools ; https://iiif.io/api/image/3.0/ ; https://www.w3.org/TR/annotation-model/ . Pin and recheck implementation documentation before selecting an SDK/transport. This addendum specifies no installed server or trained model.
