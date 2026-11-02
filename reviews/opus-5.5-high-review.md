# Independent review: SPEC-v0.1 and MULTIMODAL-MCP-ADDENDUM-v0.1

Reviewer: Claude Opus 5.5 (high), independent reviewer, 2026-11-02.
Scope: research-design review of `SPEC-v0.1.md` (§ refs "S§") and `MULTIMODAL-MCP-ADDENDUM-v0.1.md` (§ refs "A§"). Neither draft was edited. No data was downloaded beyond public documentation pages and the LREC-COLING 2024 paper PDF. No code was built and no models were run.

Evidence labels used below:
- **[V]** verified this session from a primary public source (listed in §9)
- **[K]** established domain knowledge that was not re-fetched this session; verify before relying on it in v0.2
- **[H]** hypothesis; needs a pilot or source audit
- **[U]** unknown

---

## 0. Bottom line

**Recommended decision: Proceed only after re-scoping (conditional go).** The evidence discipline is strong: rights per asset, snapshot manifests, the split between occurrence and type and between witness and artifact, and "counts are not probabilities." The scope and the centre of gravity are wrong:

1. **The retrieval experiment (S§10.B) is the weakest contribution for us, yet the spec treats it as the "first measurable research experiment."** eBL already built and published this capability. Its synthetic benchmark is near ceiling (P@3 up to 0.94 [V]). The task that matters is open-set prospective discovery, which needs eBL-level expert verification we do not have. Demote it to a baseline reproduction plus integrity check.
2. **The graph models evidence in the wrong direction for transliteration-derived data.** In the eBL data, sign identity (ABZ number) is *derived from the editor's reading* by a sign-list lookup [V]. The spec models `Occurrence → IDENTIFIED_AS → SignType` and then `HAS_READING` as if the sign came first. This breaks the "interpretation dependency" feature at its root (§2.1).
3. **The layer that explains translation disagreement is missing: words and lemmas.** Signs do not have English meanings. Words and lemmas do. Without a Word/Lemma layer, "dependency of a translation on a sign interpretation" collapses to "this line's translation depends on this line." That result is trivial (§2.2).
4. **The addendum roughly doubles the scope.** It adds an image-annotation viewer, cross-modal learned retrieval and a 10-tool MCP server to a project with no ingested data, no verified sign-level coordinates and no reviewer. Symbol↔English vector retrieval also targets the wrong unit (§6).
5. **ORACC is missing.** It is the main open, lemmatized, translated, CC BY-SA corpus with per-project JSON [V]. It is the natural source for the Word/Lemma/English bridge and for a second edition of the same object.

**Recommended contribution (§1):** a **variant- and dependency-audited motif workbench** over one eBL chapter family. It would provide:
- motif counts with explicit uncertainty bounds
- witness-variant tables at aligned lines
- traces from a translation line to the witness readings it rests on, including which tokens are restored, damaged or editorially uncertain
- a review-priority list evaluated against *actual later editorial revisions* (snapshot diff)

Fragment retrieval stays a reproduced baseline. Multimodal work is limited to metadata and to displaying existing regions. MCP is limited to four or five read tools.

---

## 1. Strongest contribution and alternatives

| Candidate | Novelty versus existing work | Feasibility without an Assyriologist | Measurable? | Verdict |
|---|---|---|---|---|
| Fragment/parallel retrieval (S§1.3, S§10.B) | Low. eBL n-gram matcher and paper exist [V]. eBL uses it internally on ~27k fragments, and expert inspection of its top 300 for one chapter found 3 new manuscripts [V] | Low. The gold standard is expert confirmation | Synthetic only, and that is near ceiling | **Demote** to reproduction and baseline |
| Contextual motif exploration (S§1.1) | Low-to-moderate. n-gram counting is not novel. Uncertainty-bounded counts with witness de-duplication and source click-through are uncommon as an open tool [H] | High for counts. Low for interpretation | Integrity yes; insight only with a reviewer | **Keep**, framed as a tool, not discovery |
| Variant explorer at aligned lines (new) | Moderate. Computational textual criticism exists. eBL's chapter UI likely shows manuscript variants per line [U: check how far the eBL UI already does this] | High. eBL chapters align manuscripts by line [V: chapters hold per-manuscript sequences] | Yes. Diff classification on hand-labelled lines | **Core of MVP** |
| Interpretation-dependency trace (S§1.2) | Moderate *if* it reaches word/lemma level and restoration basis. Trivial if it stays line-level | Medium. Lemmatization coverage of the cohort is unknown [U] | Yes. Recall of witness/lemma links on hand-checked lines | **Core of MVP**, re-modelled (§2) |
| Review prioritization (S§1, optional fourth) | Moderate when evaluated against real editorial revisions | Medium. Needs two snapshots of the same records | **Yes, with no expert needed**: predict which tokens editors later changed | **Promote** from optional to a measured experiment |
| Cross-modal symbol↔English (A§2) | Low as an embedding demo; high-risk as research | Very low. Sign-level paired data is tiny or unknown | Not without reviewed alignments, which do not exist | **Cut** from v0.2 and park with entry criteria |

### Why "why translations disagree" needs reframing
Daniel likes this most, and as phrased it is the hardest to source. Open, line-aligned, *independent* multiple translations of the same passage are rare:
- An eBL chapter has one edition translation [K].
- ORACC typically has one translation per text [K].
- CDLI and ORACC frequently share ATF for the same P-number [K], so they are not independent.

Feasible substitutes:
1. **Reading disagreement between witnesses** of the same composite line (eBL chapter manuscripts) [V: data exists]. "Translation X rests on witness A's reading. Witness B reads differently here."
2. **Reading disagreement between two transliterations of the same artifact**: the eBL Fragmentarium transliteration versus the eBL corpus manuscript line, or ORACC versus CDLI for one P-number. Independence must be audited [H].
3. **Historical versus modern translation.** One example is a public-domain early-20th-century translation of a tablet of *Enūma eliš* or Gilgamesh compared with the modern eBL edition. The disagreements often trace to *later-joined fragments and changed readings*. That links fragments, readings and translations in exactly the way Daniel described. [H. Public-domain status depends on jurisdiction, author death date and translator. Old line numbering needs manual alignment. eBL translation reuse rights are U.]

Option 3 is the most compelling demo and the most manual. Scope it to one tablet and about 50 lines.

---

## 2. Graph contracts: correctness and complexity (S§4–S§7)

### 2.1 P0: invert the reading/sign dependency for text-sourced data (S§5, S§6 `IDENTIFIED_AS`, `HAS_READING`)
**Verified:** the eBL ABZ sequences are produced by "assigning [a reading] the index of a sign with a matching reading or name from Borger (1988)" (LREC 2024, §4.1). The editor's primary act is the *reading* (value plus index, e.g. `u₂` vs `u`). Sign identity follows from a versioned sign-list mapping. For image-sourced (OCR) data the direction reverses: shape gives the sign, and context gives the reading.

**Fix:**
- For text sources, store the editor's reading on the Occurrence as primary source data (`raw_token`, `value`, `index`, `role`).
- Derive `SignType` with `MAPS_TO {signlist_version}`, which is a deterministic mapping and not a scholarly claim.
- Reserve `IDENTIFIED_AS` claims for image or OCR evidence and for explicit sign-name transliterations (`x(ABZ...)`, `|A×B|`).
- Values that map ambiguously, or that sign lists disagree on, become explicit alternatives.

Without this, "change one sign interpretation" (query 7) edits the wrong layer.

### 2.2 P0: add Word and Lemma layers (S§5, S§6, S§7 queries 4 and 7)
`Reading` (S§5) conflates sign values with word-level interpretation. The translation dependency chain is:

`Region? → SignOccurrence (reading) → WordToken (grouped signs, with determinatives and phonetic complements) → Lemma claim (citation form, guide word, POS, sense) → TranslationSegment`.

ORACC lemmatization carries English guide words and senses per lemma [K]. eBL lemmatizes against its dictionary [K; coverage in cohort U]. This is the honest word-level English bridge, and it also replaces the addendum's learned symbol↔English space (§6).

**Fix:**
- Add `WordToken` (ordered, with `word_ordinal` and a span of sign occurrences).
- Add `Lemma` (namespaced: ORACC/ePSD/eBL dictionary) with `LEMMATIZED_AS` claims.
- `TRANSLATES` targets a line or line range unless a finer source alignment exists.

### 2.3 P1: stop reifying every source-asserted fact as a Claim (S§6 first paragraph, S§5 Claim)
At scale, one Claim plus SUPPORTED_BY plus PROPOSED_BY per token assertion produces 3–5× edge inflation. It adds no information, because provenance is uniform across a SequenceVersion.

**Fix: "claims on demand."** Source-transcribed facts are typed columns or edges that inherit provenance from their `SequenceVersion` and `SourceRecord`. Reify a `Claim` only for:
- alternatives
- cross-source alignments or equivalences
- derived or model outputs
- anything a reviewer touches

Merge `Alignment` into `Claim` as a subtype. Two near-identical evidence-bearing node kinds will drift apart.

### 2.4 P1: the example Cypher over-counts as written (S§7)
The `MATCH (a)-[:IDENTIFIED_AS]->(sa)` patterns are not scoped to the selection. Any occurrence with two sign assertions (an alternative, a second edition's mapping, or OCR) multiplies paths. The prose says "consistent edge projection before the query runs," but the query reads as if it runs on the full graph.

**Fix:** state that the query runs on a per-selection *projected subgraph*, or filter the edge by `{selection: $selection}` or `{assertion_set: ...}`. Add a fixture with two sign assertions on one token to test A. Counting `DISTINCT v.witness_id` is correct. Also report `count(DISTINCT artifact)` and `count(DISTINCT composition)` as S§7 item 1 already requires. The example omits them.

### 2.5 P1: NEXT and gap semantics contradict each other (S§5 Occurrence, S§6 NEXT, S§6 gap paragraph)
- S§5 says an Occurrence "may be a … gap."
- S§6 NEXT says "no skipped damage."
- S§6 also says default matching "stops at gaps."

So: are gap tokens nodes in the NEXT chain?

**Fix:**
- NEXT links *every* token position, including gap, `x` and broken-sign tokens, in source order within a line.
- `countable` and preservation flags decide matching, never edge deletion.
- Add a `boundary` property on NEXT (`intra_word`, `word`, `line_end` if cross-line projection is enabled).
- Sign trigrams that cross word boundaries are legitimate but behave differently from intra-word ones. Report them separately.

### 2.6 P1: uncertainty needs a three-axis taxonomy, not "preservation state" (S§5 Occurrence, S§10.A)
ATF flags encode at least three things that must not be mixed:
- **Physical preservation:** intact, damaged (`#` / ⸢⸣), lost (`[...]`).
- **Editorial certainty:** `?` uncertain, `!` corrected/sic, `*` collated.
- **Restoration basis:** a restored token is usually restored *from a parallel witness or composite*. That is itself an interpretation dependency, `RESTORED_FROM → Witness/Composite`, and usually implicit [H: basis rarely encoded per token; can be inferred by aligning restored spans to other witnesses].

Inferring restoration basis also gives the dependency explorer its best feature: **circular-support detection**. Example: witness A is restored from B, and B's reading at that spot is itself damaged or restored.

### 2.7 P2: alternatives should form a lattice with bounded counts (S§6 last sentence, S§7)
"Alternative readings belong to a coherent source hypothesis" is correct. Within one edition, ATF also allows local alternatives (`a/b`, `x(…)`, `?`).

**Fix:** model alternatives as exclusive groups at a position. Motif queries return a **[lower, upper] count**:
- lower = certain-only
- upper = any-alternative

Do not choose one alternative per query. This is cheap, honest and directly useful for "how much does this motif's prevalence depend on contested readings."

### 2.8 P2: compounds, logograms and determinatives (S§5, S§10.A fixture list)
Name the contracts explicitly:
- `|A×B|` and other compound graphemes form **one** SignType.
- Multi-sign logograms (`GIŠ.TUKUL`) are several sign occurrences in one WordToken.
- Determinatives are countable signs with `role=determinative`. Provide a projection that excludes them.
- Numerals carry value and system.

### 2.9 What to cut from the contracts in v0.2
Defer, but keep the schema stubs:
- `PatternMatch` persistence
- `Image`/`Region`/`DEPICTS`/`LOCATED_IN` until §6 entry criteria are met
- `CONTAINS_SIGN`
- `SIMILAR_TO`
- `REVIEWED_BY`/`ReviewDecision`: a JSONL review log suffices for the MVP
- `CorpusSelection` as graph nodes: it is a manifest file

Seventeen node kinds become about 11 in the MVP: Artifact, Witness, SequenceVersion, Line, SignOccurrence, WordToken, SignType, Lemma, TranslationSegment, Claim, SourceRecord. AnalysisRun can live in manifests.

### 2.10 Storage (S§8)
The spec already admits a graph is not needed for counting. Commit to that:
- **MVP = Parquet + DuckDB.** Adjacency is `(sequence_id, line_id, ordinal)` with `LEAD`/window functions. Motifs use a suffix array or n-gram index.
- A FalkorDB projection is optional and earns its place only for `evidence_trace` traversals.
- Daniel's NEXT relationships can still exist as a *projection* for the demo and the MCP, generated from the token table.

Acceptance A already requires agreement between array counts and graph counts. This makes the token table the oracle.

---

## 3. Occurrence/type and witness/artifact distinctions (S§4)

These distinctions are correct and are the spec's best part. Refinements:

- **eBL alignment:** a Fragmentarium record is keyed by museum number and lists `joins` [V: field present]. Corpus manuscripts are sigla that reference museum numbers and joins [K]. Model `JoinGroup` as a claim over Artifacts, because joins are asserted, dated and occasionally retracted. The JOHD paper reports 1,250 joins found while compiling the corpus [V]. This is a candidate gold source for physical-join evaluation, subject to the leakage notes in §5.
- **Two transliterations of one artifact:** the Fragmentarium ATF and the corpus manuscript line ATF may be by the same editor and copied [U]. Before treating them as two SequenceVersions with independent evidential weight, record an `independence` attribute (`independent`, `derived`, `unknown`).
- **Inferred findspot:** collection prefixes such as `K.` (Kuyunjik collection) are routinely read as "Nineveh." That is an *inferred origin*, not an excavated findspot [K]. Use it as the canonical fixture for A§4's "do not collapse findspot, inferred origin and custody."
- **Line ordering:** surface and column order is an editorial reconstruction for broken tablets. `line_ordinal` must be "source order," and cross-surface NEXT_LINE should never feed motif matching by default. The spec already says this; keep it.

---

## 4. Pattern statistics versus relatedness (S§7 last paragraph, S§10.D)

The spec's caveats are right. Add these, which are specific to the script:

1. **In syllabic Akkadian, sign n-grams mostly encode spellings of frequent words** (`a-na`, `i-na`, `ša`, verbal prefixes) [K]. A ranked list of sign trigrams will be dominated by orthography. Provide **two motif levels**:
   - sign-level, for orthography, substitution and retrieval
   - lemma-level, for formulae and phraseology

   S§7 query 3 (`A ? C` grouped by middle sign) is a strong *orthographic variant* tool at sign level.
2. **Dependence structure:** copies of one composition, school exercises and serialized tablets are not independent. Enrichment must use **witness-presence counts within compositions**, with composition as the clustering unit. Use exact tests (Fisher, or Bayesian lift with smoothing) and BH-FDR across candidate motifs. Pre-register the background stratification.
3. **Editor and convention confounds:** restoration practice and the choice of what to transliterate differ by editor. Value choice is mostly normalized away at sign level, which is a good argument for sign-level retrieval. Include `editor` in stratification.
4. **Relatedness:** a shared rare motif is evidence for *one of* several predicates: physical join, same composition, shared formula, or shared scribal school. S§6 correctly separates these. The ranking must also show *which composition-level explanation already accounts for the overlap*. Otherwise formulae such as incipits, colophons and epithets dominate.
5. **Cut S§7 query 5 (enrichment) from the MVP.** It needs the larger stratified corpus that S§3 says we will not have. Keep descriptive counts with denominators.

---

## 5. Benchmarks, leakage and baselines (S§10.B, A§2, A§6)

### Verified facts about the existing baseline (LREC-COLING 2024)
- Corpus: 159 eBL chapters with 1,402 manuscripts (mean 8.82 per chapter) and ~27,000 Fragmentarium fragments.
- Test set: 965 synthetic fragments cut from 100 manuscripts, with the source manuscript excluded from the chapter at evaluation time.
- Metric: P@3 over chapters.
  - BOW 0.14, LCS 0.90, Needleman-Wunsch 0.79.
  - n-gram variants 0.88–0.94 for n ≤ 3–5.
- The authors themselves note that the synthetic task "considerably simplifies the real task": every item matches exactly one chapter, while real fragments mostly match none.
- Realistic check: Maqlû compared against all fragments. Expert inspection of the top 300 (1.2%) found 3 new manuscripts.

### Consequences for S§10.B
- **The threshold of "≥10% relative Recall@10 improvement" is uninformative on the synthetic task.** The ceiling is about 0.94 at k=3. On the open-set task we cannot produce gold labels without experts. **Replace** the research claim with this: "reproduce the published synthetic setup within ±0.02 P@3 on our frozen snapshot." That becomes an integrity gate for our token pipeline, not a contribution.
- **Leakage sources the spec misses:**
  1. **Damaged-but-read signs (`#`/⸢⸣) are read *with knowledge of the identification*.** Excluding only `[restored]` text is insufficient. Run a strict-evidence projection that drops restored and damaged signs, and report both.
  2. **The transliteration was often produced or revised after identification.** The fragment's ATF can effectively be the chapter's manuscript line. Use eBL `record` edit history [V: field present] to attempt a **temporal split**: the fragment's transliteration state *before* the identification date [H: whether identification dates are recoverable is U].
  3. **Synthetic fragments come from manuscripts whose lineation follows the edition**, which flatters line-based methods.
  4. **eBL OCR models were trained on 1,610 eBL tablet images** [V]. Any visual evaluation must exclude those artifacts, and their joins, from test partitions. The addendum's "same object in same partition" rule (A§2) is necessary but not sufficient.
- **Baselines** for any retained retrieval comparison:
  - eBL n-gram (overlap, length-weighted)
  - BM25 over sign n-grams
  - Smith-Waterman local alignment on top-k candidates (LCS scored 0.90 in the paper)
  - the spec's "SQL with same information" control. Keep that one; it is the right instinct.
- **License caution on the baseline:** the ngram-matcher repo shows no LICENSE file [V]. Running it locally for comparison is reasonable. Vendoring or redistributing it is not. Reimplementing from the paper is safer.

### Review-priority experiment: promote it, and here is the evaluation that needs no expert
- **Ground truth = later editorial change.** Score tokens on the Zenodo snapshot (fragments as of 2023-09-01 [V]). Label positives as tokens whose reading, flags or restoration changed in the current eBL record. The cohort scale is a few hundred records. A full-corpus pull is not required.
- **Baselines:**
  - `?`/`!` flag only
  - damage flag only
  - random
  - "last-edited-longest-ago"
- **Ranker candidates:**
  - downstream impact (motif and translation fan-out)
  - witness disagreement at the aligned line
  - alternative-count
- **Metric:** precision@k and AUC with clustering by artifact. Pre-register k.
- **Bias caveat [H]:** revisions reflect editor attention and new joins as well as errors. Report the revision *type* (new join, collation, correction) where the `record` type permits.

This measures "would this list have pointed editors where they later went," which is a defensible, non-decipherment claim.

---

## 6. Multimodal and MCP addendum

### 6.1 What is right
- Embeddings are derived data with a model-space ID (A§2). Incompatible spaces produce an error.
- Graph-mediated retrieval is the default, and learned alignment is a later stage.
- Generated glosses are not independent evidence.
- Explicit pixel geometry and image-version hashes, with stale coordinates failing loudly (A§3).
- Translation status is scoped to the searched sources, snapshot and denominator (A§4).
- MCP:
  - frozen snapshots
  - no raw Cypher/SQL/URL tools
  - typed errors
  - server-enforced limits
  - proposals that never become accepted truth (A§5)

These are good contracts. Keep them as written.

### 6.2 P0: "symbol↔English" is the wrong unit (A§1 examples, A§2 Stages 2–3)
A sign does not have an English meaning. A *word in context* does. Image→English chains these steps:
1. detection (eBL OCR AP50 ≈ 0.43–0.45 for the 2025 retrained single-stage model [V: repo README])
2. sign classification
3. polyvalent reading choice (context-dependent)
4. word segmentation
5. lemmatization
6. sense

Errors compound at every step. A learned joint image–English space has no supervision at the level it claims. The only paired data is passage-level translation, which is weak, and lemma-level glosses that require sign-to-word alignment, which do not exist at scale [U].

**Fix: replace Stages 2–3 with deterministic bridges.**
- **English→source:** query lemma guide words, senses and glossaries (ORACC/eBL dictionary) → WordTokens → SignOccurrences → regions where they exist. Translation-passage embedding is a *secondary* recall aid at passage granularity, labelled as such.
- **Image→source:** crop → top-k sign candidates (existing eBL OCR model or nearest neighbours on reviewed crops) → user or agent picks → contextual readings at that sign's attested occurrences. Never return an English meaning for a sign.
- **Park learned alignment** with entry criteria:
  - ≥N reviewed occurrence↔region pairs from a rights-cleared set
  - a measured gap that the deterministic bridge fails to cover
  - a frozen leakage-safe split (§5 item 4)

### 6.3 P0: sign-level coordinates for a text cohort are likely absent (A§3, A§7)
- eBL OCR detections (Zenodo 14009952: 1,224,109 signs from ~75k photos, CC BY 4.0 [V]) are *model detections that are not aligned to transliteration tokens*. The field schema is [U].
- Aligning an OCR sign sequence to the editor's token sequence is itself a sequence-alignment problem with noisy input. That is a research task, not an ingest step.
- The 1,610-image annotated training set (Zenodo 10693501 [V exists]) has unknown license and per-sign label semantics [U]. It is also excluded from evaluation by construction (§5).
- **Rights:** eBL states that photographs require consent from the owning institutions [V: JOHD]. "Live displayed coordinates" on eBL photos may therefore be private-inspection-only. Public display needs a collection with an explicit image license and ideally IIIF. That is per institution and [U] for the cohort.

**Fix:**
- MVP shows *existing* regions only where a source supplies them, plus a manual annotation path for up to 50 occurrences on one rights-cleared image set.
- Geometry v1 is an axis-aligned box or polygon in original pixel space, plus a display scale and crop. Rotation and perspective return `unsupported_transform`, as A§3 already specifies.
- Cut `Canvas` and general `GeometricTransform` chains from v0.2.

### 6.4 P1: metadata (A§4)
The field table is thorough. It is also mostly unfillable from eBL alone, since find context is absent or inferred for most Kuyunjik material [K]. Source it from the CDLI catalogue (provenience, period, genre) via the CDLI crosswalk in eBL's `externalNumbers` [V: field present].

CDLI GitHub data shows **no stated data license** and was last updated in August 2022 [V]. Record it as `rights: unknown`, for private inspection only.

The MVP should cover:
- identifiers
- custody
- inferred origin vs findspot (with `unknown`)
- period and genre as attributed
- edition and translation coverage

Defer excavation context (trench/locus/campaign) and dating conversion.

Translation-status enum: keep it. Drop the "official" label entirely; there is no use case.

### 6.5 P1: the MCP surface is too large for a vertical slice (A§5)
Ten tools, including an authorization-bearing review write path and async jobs, before any data exists.

**MVP surface:**
- `record_get`
- `sequence_get`
- `pattern_search` (synchronous, bounded)
- `evidence_trace`
- `corpus_search` (lexical plus lemma-gloss; semantic search off)

Defer:
- `similarity_search` until §6.2 entry criteria are met
- `image_region_get` until rights-cleared regions exist
- `analysis_start`/`analysis_get`
- `proposal_review`

Keep `proposal_create` writing to a local append-only JSONL with idempotency keys. That exercises the contract without reviewer authorization.

The spec reference is MCP 2025-06-18. Pin the current spec revision at implementation time, as A§5 says.

### 6.6 P1: the addendum's evaluation cannot run as written (A§6)
"Text-to-image and image-to-text Recall@k on reviewed alignments" presumes reviewed alignments, and none exist. There is no named reviewer.

**Fix:** keep agent exercises 1, 2 (passage-level), 4, 5 (proposal_create only) and 6 as engineering acceptance. Move 3 and the cross-modal Recall@k to the parked stage. The lexical-path baseline (A§6 last paragraph) is the right control. Make it the primary path, not the baseline.

---

## 7. Data feasibility and rights (S§3, A§7): corrections and additions

| Asset | Verified facts | Issue for spec |
|---|---|---|
| eBL transliterated fragments | ~25k transliterated of 262,717 catalogue records. Fields include `atf`, `signs`, `record` (edit history), `joins`, `externalNumbers`, `genres`, `script`, `editedInOraccProject` [V]. **Frozen snapshot exists**: Zenodo 10018951 v2, 2023-10-18, `fragments.json` 73.9 MB [V] | S§3 plans live pagination and misses the frozen snapshot. Use the snapshot as the reproducible base and the live API only for the diff experiment |
| eBL data license | **Conflict [V]:** the Zenodo record says CC BY 4.0, while the JOHD data paper says `fragments.json` is CC BY-NC-SA 4.0. Code is MIT. Photos need institutional consent | Treat as **CC BY-NC-SA** (stricter) until eBL clarifies. NC-SA constrains derived-dataset release and any commercial use. Record the conflict in the rights manifest |
| eBL many transliterations are photo-based | "have not been checked against the originals in museums" [V] | Supports the editorial-certainty axis and the revision-based priority experiment |
| eBL corpus chapters | 159 chapters / 1,402 manuscripts at paper time [V]. Translation and lemmatization export fields [U] | Audit first. These drive the MVP |
| eBL ngram-matcher | No license file. Needs eBL API access. README warns the database changes constantly and to keep a local copy [V] | Reimplement from the paper for redistribution |
| eBL OCR signs | Zenodo 14009952, CC BY 4.0, 220 MB, 1,224,109 detections, ~75k photos [V]. Schema [U] | Model output, not ground truth. Not aligned to tokens |
| eBL OCR model and data | Detector AP50 ≈ 0.43–0.45 (README, 2025 models). Training set of 1,610 images (Zenodo 10693501). Repo license not shown [V] | Excludes those artifacts from visual test sets |
| ORACC | Site statement is CC BY-SA 3.0. Per-project `manifest.json`, `metadata.json` with `atf`/`lem`/`tr-en` P-number lists, and `json.zip` [V] | **Add** as the lemma/gloss/translation source and as a second edition. Per-project exceptions [U] |
| CDLI GitHub | `cdli_cat.csv`, `cdliatf_unblocked.atf`. Last updated August 2022. No data license stated [V] | Catalogue crosswalk only, private inspection, `rights: unknown` |
| Prior ML work to cite | Restoration: Fetaya et al. 2020 PNAS (LSTM, Achaemenid archival texts) [V] and Lazar et al. 2021 EMNLP (MLM, reported 89% hit@5) [V]. Translation: Gutherz et al. 2023 PNAS Nexus, Akkadian→English, about 36–37 BLEU4 [V] | Restoration models are the natural baseline for `A ? C` and alternatives. NMT output is a `machine_draft_only` translation source for A§4 and must never count as evidence |

---

## 8. Prioritized objections

| # | Pri | Ref | Objection | Fix |
|---|---|---|---|---|
| 1 | P0 | S§1.3, S§10.B, S§11.4 | Retrieval is positioned as the main measurable experiment. Existing work is near ceiling on synthetic data, and the open-set gold standard needs experts | Demote to baseline reproduction (±0.02 P@3) plus strict-evidence ablation. Pursue retrieval research only with an eBL collaborator |
| 2 | P0 | S§5–6 | Sign identity is derived from reading in text data. The graph inverts that | Reading on the occurrence; `MAPS_TO {signlist_version}`; `IDENTIFIED_AS` only for image or explicit sign names |
| 3 | P0 | S§5, S§7 q4/q7 | No Word/Lemma layer, so translation dependencies are trivial | Add WordToken, Lemma and `LEMMATIZED_AS`. Add ORACC |
| 4 | P0 | A§1–2 | Symbol↔English learned retrieval targets the wrong unit and has no supervision | Use deterministic lemma-gloss and OCR-candidate bridges. Park Stages 2–3 with entry criteria |
| 5 | P0 | A§3, A§7 | Sign-level coordinates and image display rights are unverified, and probably absent or private for eBL | Show existing regions only, plus ≤50 manual annotations on a rights-cleared set |
| 6 | P1 | S§3 | Live-API ingestion ignores the frozen Zenodo snapshot. The license conflict is unrecorded | Base on snapshot 10018951. Treat data as CC BY-NC-SA pending clarification |
| 7 | P1 | S§10.B | Leakage via damaged-but-read signs and post-identification transliteration | Strict-evidence projection. Temporal split via `record` history if dates are recoverable |
| 8 | P1 | S§6, S§5 | Per-token Claim reification inflates the graph without adding information | Claims on demand. Alignment becomes a Claim subtype |
| 9 | P1 | S§7 | The Cypher example over-counts when tokens have multiple assertions | Selection-scoped projection plus a fixture |
| 10 | P1 | S§5–6 | Gap and NEXT semantics contradict each other. No boundary typing | NEXT over all tokens, flags decide matching, `boundary` property |
| 11 | P1 | S§6 | Uncertainty is a single field | Three axes: preservation, editorial certainty, restoration basis (`RESTORED_FROM`) |
| 12 | P1 | S§1 optional fourth | Review priority uses "impact counts" with no evaluation | Evaluate against later editorial revisions (snapshot diff) versus flag baselines |
| 13 | P1 | A§5 | 10 MCP tools before data exists | Five read tools plus local `proposal_create` |
| 14 | P2 | S§7 q5, S§10.D | Enrichment needs a stratified corpus that is out of scope | Descriptive counts with bounds and denominators. Two motif levels |
| 15 | P2 | S§6 | Alternatives are chosen per query | Exclusive-group lattice with [lower, upper] counts |
| 16 | P2 | S§8 | Graph DB proposed before need is shown | Parquet + DuckDB oracle. NEXT projection for demo and MCP only |
| 17 | P2 | S§2 | Novelty check is limited to eBL tools | Verify what eBL's chapter and score UI and Fragmentarium sign search already offer before building the variant explorer [U] |
| 18 | P2 | A§4 | Metadata table is mostly unfillable | MVP field subset. CDLI as `rights: unknown` crosswalk |

---

## 9. Concrete MVP and measurable acceptance

**Name:** Variant- and dependency-audited motif workbench, v0.2 MVP. Text only.

**Cohort:** one eBL chapter family with many manuscripts, chosen after a feasibility audit of translation and lemmatization coverage. Candidates are one SB Gilgamesh tablet or one *Enūma eliš* tablet. Add Fragmentarium records for those manuscripts and the Zenodo 2023 snapshot as base, ORACC lemma/gloss data where the composition or lemmas are covered, and optionally one public-domain historical translation of ≤50 lines.

**In scope:**
1. Raw-preserving ingest: token tables (SignOccurrence, WordToken, Line, SequenceVersion) with byte offsets, the three-axis uncertainty model, versioned ABZ mapping, and alternatives as exclusive groups.
2. Motif queries (S§7 items 1–3) at sign and lemma level, with [lower, upper] bounds and witness/artifact/composition denominators.
3. Aligned-line variant table per composite line, with diff classes: orthographic, lexical, omission/addition, damage-only, restoration-only.
4. `evidence_trace`: translation line → composite line → witness readings → restored/damaged/uncertain status → inferred restoration source.
5. Review-priority list plus the snapshot-diff evaluation.
6. Five MCP read tools and a local `proposal_create`, exercised through a real MCP client.
7. Evidence-packet export.

**Out of scope:** images and regions beyond displaying any source-provided links, embeddings, learned alignment, retrieval research, FalkorDB unless traversal latency in DuckDB fails, enrichment statistics, public redistribution.

**Acceptance (proposed thresholds; set before the pilot):**

| ID | Criterion | Pass |
|---|---|---|
| M1 | Fixture suite (S§10.A list plus the two-assertion token, compounds, determinatives and the K.-number provenance case) | 100% |
| M2 | Token-table count = NEXT-projection count = independent array implementation, full cohort, all motif lengths 2–5 | Exact equality |
| M3 | Every token round-trips to unchanged raw ATF bytes | 100%, or listed exclusions with reasons |
| M4 | Reading→ABZ mapping coverage on non-lost tokens, unmapped listed | Report. Target ≥98% [proposed] |
| M5 | Baseline reproduction: our pipeline reruns the published synthetic setup | P@3 within ±0.02 of the paper's n-gram row |
| M6 | Diff classification on 200 hand-labelled witness differences | Precision ≥0.9 per class reported |
| M7 | `evidence_trace` on 20 translation lines: recall of contributing witness lines and of restored-token flags against a hand check | 100% witness lines; restoration-basis inference precision reported, no threshold |
| M8 | Review priority: precision@50 versus `?`-flag, damage-only and random baselines on later-revised tokens, artifact-clustered CI | Pre-registered. Continue only if the CI excludes the best baseline |
| M9 | MCP exercises (addendum 1, 2-passage, 4, 5-create, 6-stale-snapshot variant) via a real client | All pass. Typed errors observed |
| M10 | Rights manifest covers every asset in the evidence packet; the eBL license conflict is recorded | 100% of assets have a status, `unknown` allowed |

**Stop rules:**
- If the M4 audit shows that lemmatization or translation is missing for the chosen cohort, ship the sign-level variant workbench and label dependencies as line-level.
- If M8 fails to beat flag baselines, drop prioritization claims and keep the tool.
- If no specialist reviewer exists by the end of the MVP, publish nothing that is framed as philological insight.

---

## 10. Verified, hypotheses, unknowns (summary)

**Verified this session:**
- the eBL n-gram method and its evaluation numbers and limitations
- that the ABZ sequence is derived from readings
- eBL fragment fields: `record`, `joins`, `externalNumbers`
- the Zenodo snapshot and its CC BY 4.0 label, against the JOHD CC BY-NC-SA 4.0 statement
- that photos need consent
- the OCR dataset's size and license
- the OCR model's AP figures and training-set size
- that the ngram-matcher and cuneiform-ocr repos show no license file
- ORACC's CC BY-SA 3.0 statement and JSON manifest formats (`atf`/`lem`/`tr-en`)
- CDLI GitHub: no license, last updated August 2022
- the restoration and NMT papers

**Hypotheses:**
- restoration basis can be inferred by alignment
- identification dates are recoverable from `record` history
- revision-based ground truth is meaningful despite editor-attention bias
- a public-domain historical translation is usable and alignable
- uncertainty-bounded variant and motif tooling is not already available in eBL's UI

**Unknowns:**
- the eBL chapter export schema for translations and lemmatization
- lemmatization coverage in the cohort
- the license for eBL corpus translations
- the OCR JSON schema and coordinate semantics
- the license for the OCR training data
- per-project ORACC license exceptions
- independence between Fragmentarium and corpus transliterations of the same manuscript
- image rights and IIIF availability for the cohort's collections
- a specialist collaborator

### Sources (primary, inspected 2026-11-02)
- LREC-COLING 2024 paper (full PDF text): https://aclanthology.org/2024.lrec-main.1197/
- eBL ngram-matcher: https://github.com/ElectronicBabylonianLiterature/ngram-matcher
- eBL transliterated-fragments: https://github.com/ElectronicBabylonianLiterature/transliterated-fragments
- Zenodo snapshot: https://zenodo.org/records/10018951
- JOHD data paper (Cobanoglu et al. 2024): https://openhumanitiesdata.metajnl.com/articles/10.5334/johd.148
- eBL OCR signs: https://zenodo.org/records/14009952
- eBL OCR code and model: https://github.com/ElectronicBabylonianLiterature/cuneiform-ocr
- ORACC open data and JSON: https://oracc.museum.upenn.edu/doc/opendata/ and https://oracc.museum.upenn.edu/doc/opendata/json/index.html
- CDLI data: https://github.com/cdli-gh/data
- Fetaya et al. 2020: https://doi.org/10.1073/pnas.2003794117
- Lazar et al. 2021: https://aclanthology.org/2021.emnlp-main.384
- Gutherz et al. 2023: https://academic.oup.com/pnasnexus/article/2/5/pgad096/7147349
