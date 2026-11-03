# Source feasibility audit — eBL frozen text export, ORACC ccpo, CDLI

Generated 2026-11-03 from real acquired bytes by `cuneiform corpus-inspect` / `corpus-audit` (inspector `ebl-inspect-1`, parser `conservative-3`). Metadata identifiers and counts only; no source text is reproduced here. Counts describe what the conservative adapter maps, not linguistic quality.

## eBL whole-file inspection (all 23,289 records)

Parent: Zenodo record 10018951 `fragments.json`, 73,854,507 bytes, MD5 `71538e2d86c8ba6d47f499892bb3e5d3` (matches record API), SHA256 `4e970d8713315ca9559fb9dfd79956d5b19b1debb9941c22f8bed0339745d753`, receipt `receipt:66b5c94472b500317dbebd173bc149d3`. Streaming scan: 95.1 s, peak memory ≈48 MB (`/usr/bin/time -l`).

- Envelope: **top-level JSON array**. The README example's `{"fragments": [...]}` wrapper does not match the file.
- Every record has the same 23 keys (`date` additionally in 39). No word, lemma, sense, alignment or image fields exist in the export.
- Record bytes: median 2,042, p90 5,609, p99 19,457, max 144,909.
- Duplicate `_id`: K.5808 ×2 (byte-identical). Both copies are excluded from cohorts; the adapter would reject the second.
- Adapter rejections: 0. Records with numbered ATF text: 23,223; with translation lines: 1,560; with a CDLI number: 18,610.
- ATF positions: reading 457,604 / gap 482,933 / unsupported 921,847. Hyphenated words, determinatives and compounds remain opaque blocking positions.
- `signs` positions: source-derived sign 2,441,041 / gap 245,643 / unsupported 50,287. These are reading-derived labels, not visual evidence.
- ATF and `signs` line counts agree in 22,877 of 23,223 records with text. Agreement is observed only; no position alignment is asserted.
- `editedInOraccProject`: ccp=459, saao=167. Translation language tags (top): en 22,932, de 594, ar 481, em 2.

## Cohorts (rule `usable-text-v1`)

Eligible: unique `_id`; not rejected; ≥1 numbered ATF line; ≥10 eligible positions (ATF readings + source-derived signs); ≥2 adjacent eligible pairs; ≤256 KiB. Order: `sha256(parent_sha256 + ":" + _id)`, so each smaller cohort is a prefix of a larger one (checked: the 30 are the first 30 of the 300). 20,896 of 23,289 records are eligible.

| cohort | records | payload bytes | snapshot |
|---|---|---|---|
| `cohort:9abad6ce3e28e1c3c50794fb30b917bd` | 30 | 125,599 | `snapshot:ce127437339109285185a534145edf50` |
| `cohort:4e86952ece628b06f9280fe72aafe65d` | 300 | 1,123,168 | `snapshot:84971360d212834e0b7acbeac1e56abe` |
| `cohort:ea91baae8f0dbbeedf555f5ab6e6c5a0` (+ exact P-number filter: ORACC ccpo corpus) | 51 | 289,575 | `snapshot:c316e7cbbaf8a7fca7705f0efa5c4a07` |

300-record coverage: cdli_number 231/300, period 291/300, genre 146/300, publication 52/300, oracc_project_field 13/300, translation_lines 23/300, signs_atf_line_count_equal 292/300. Positions: atf:unsupported 16,109, atf:gap 8,409, signs:derived_sign 42,683, signs:gap 5,106, translation_segments 366, atf:reading 7,708, signs:unsupported 808.

## Initial 30-record cohort audit `cohort:9abad6ce3e28e1c3c50794fb30b917bd`

Parent sha256 `4e970d8713315ca9559fb9dfd79956d5b19b1debb9941c22f8bed0339745d753`; 23289 parent records, 20896 eligible under `usable-text-v1`; 30 selected by `sha256(parent_sha256 + ":" + source_key) ascending`.

## Field coverage

| field | records |
|---|---|
| cdli_number | 24/30 |
| period | 30/30 |
| genre | 15/30 |
| publication | 4/30 |
| oracc_project_field | 2/30 |
| translation_lines | 2/30 |
| signs_atf_line_count_equal | 29/30 |

## Unknown / unavailable layers

- **word_segmentation**: absent from export (0/30)
- **lemma_or_sense**: absent from export (0/30)
- **translation_alignment**: all 25 segments unresolved-span; no word/line alignment asserted
- **signs_to_atf_alignment**: line-count equality is observed only; no position alignment asserted
- **composition_membership**: not inferred
- **images**: not acquired

## Parent exclusions (whole file)

| reason | records |
|---|---|
| fewer eligible reading/sign positions than threshold | 2171 |
| fewer adjacent eligible pairs than threshold | 154 |
| no numbered ATF text line | 66 |
| duplicate source key in parent (all copies excluded) | 2 |

## Records

| # | source key | CDLI | period | genre | ATF lines | ATF reading/gap/unsupported | signs lines | sign/gap/unsupported | eligible pairs | tr segments | exclusions |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | K.19617 | P404416 | Neo-Assyrian | CANONICAL/Lexicography | 9 | 0/7/40 | 9 | 18/2/0 | 10 | 0 | 40 |
| 1 | K.2193 | P394252 | Neo-Assyrian | CANONICAL/Divination | 13 | 66/14/71 | 13 | 221/7/3 | 240 | 0 | 82 |
| 2 | K.3179 | P394854 | Neo-Assyrian | — | 228 | 331/138/926 | 228 | 1987/51/14 | 1727 | 0 | 956 |
| 3 | K.17480 | P402818 | Neo-Assyrian | — | 7 | 2/11/5 | 7 | 12/6/2 | 7 | 0 | 7 |
| 4 | BM.34797 | P370916 | Neo-Babylonian | — | 21 | 19/1/92 | 20 | 49/0/0 | 41 | 0 | 121 |
| 5 | K.2926 | P394731 | Neo-Assyrian | — | 13 | 21/23/11 | 13 | 56/9/0 | 52 | 0 | 15 |
| 6 | K.17904 | P403190 | Neo-Assyrian | — | 12 | 11/19/7 | 12 | 25/7/0 | 14 | 0 | 9 |
| 7 | K.2164 | P394227 | Neo-Assyrian | CANONICAL/Technical | 55 | 105/74/300 | 55 | 721/68/82 | 639 | 15 | 401 |
| 8 | BM.38657 | P471659 | Neo-Babylonian | CANONICAL/Lexicography, CANONICAL/Magic, CANONICAL/School Tablet | 15 | 14/7/74 | 15 | 112/6/1 | 98 | 0 | 85 |
| 9 | BM.128101 | P422859 | Neo-Assyrian | CANONICAL/Magic | 8 | 5/6/32 | 8 | 70/0/0 | 63 | 0 | 35 |
| 10 | BM.38772 | — | Neo-Babylonian | CANONICAL/Magic | 13 | 37/0/81 | 13 | 240/0/2 | 238 | 0 | 83 |
| 11 | BM.50347 | — | Neo-Babylonian | — | 8 | 5/0/17 | 8 | 47/0/4 | 35 | 0 | 24 |
| 12 | K.21149 | P419461 | Neo-Assyrian | OTHER/Uncertain | 6 | 6/20/5 | 6 | 10/9/2 | 8 | 0 | 7 |
| 13 | K.7451 | P238671 | Neo-Babylonian | — | 9 | 5/10/42 | 9 | 99/6/0 | 91 | 0 | 43 |
| 14 | K.6597 | P396666 | Neo-Assyrian | — | 16 | 52/20/55 | 16 | 161/11/4 | 160 | 0 | 65 |
| 15 | K.20010 | P418510 | Neo-Assyrian | CANONICAL/Divination | 9 | 3/20/12 | 9 | 13/2/5 | 7 | 0 | 17 |
| 16 | BM.36875 | — | Neo-Babylonian | — | 8 | 18/17/11 | 8 | 41/9/0 | 42 | 0 | 11 |
| 17 | K.21867 | P420082 | Neo-Assyrian | CANONICAL/Lexicography | 8 | 6/10/5 | 8 | 16/5/0 | 12 | 0 | 6 |
| 18 | BM.79949 | — | Neo-Babylonian | — | 5 | 1/2/23 | 5 | 53/3/0 | 47 | 0 | 29 |
| 19 | K.18300 | P403527 | Neo-Assyrian | — | 8 | 13/20/5 | 8 | 22/4/0 | 21 | 0 | 5 |
| 20 | 1880,0719.94 | P451974 | Neo-Assyrian | CANONICAL/Technical | 42 | 89/147/73 | 42 | 250/66/8 | 234 | 0 | 87 |
| 21 | U.3413 | P136710 | Ur III | — | 10 | 8/0/24 | 10 | 55/0/1 | 46 | 10 | 30 |
| 22 | K.6658 | P365880 | Neo-Assyrian | CANONICAL/Divination | 34 | 126/22/204 | 34 | 617/1/8 | 604 | 0 | 212 |
| 23 | BM.33541 | — | Hellenistic | — | 28 | 34/0/146 | 28 | 468/1/3 | 438 | 0 | 155 |
| 24 | K.12715 | P400008 | Neo-Assyrian | CANONICAL/Divination | 7 | 9/20/8 | 7 | 21/6/2 | 19 | 0 | 10 |
| 25 | BM.55598 | — | Neo-Babylonian | — | 9 | 21/24/19 | 9 | 68/5/0 | 71 | 0 | 20 |
| 26 | K.18594 | P403782 | Neo-Assyrian | CANONICAL/Technical | 8 | 6/27/3 | 8 | 12/12/0 | 8 | 0 | 4 |
| 27 | BM.35491 | P364367 | Neo-Babylonian | CANONICAL/Divination | 9 | 7/20/11 | 9 | 39/3/1 | 31 | 0 | 12 |
| 28 | K.19643 | P404438 | Neo-Assyrian | — | 4 | 0/4/8 | 4 | 13/0/1 | 9 | 0 | 12 |
| 29 | BM.82986 | P480104 | Neo-Babylonian | CANONICAL/Divination | 22 | 9/38/30 | 22 | 86/13/1 | 68 | 0 | 34 |

## ORACC ccpo (official JSON export)

`https://oracc.museum.upenn.edu/json/ccpo.zip`, 10,006,811 bytes, SHA256 `c728b1f6410a90cc90d6ea18125c9e2f11feab113bf382bb9a2e636debc79bae`, Last-Modified 2024-07-01, receipt `receipt:0ca4ede9acc4d972c3f6d5cf69d4b8af`. 209 catalogue entries, 208 corpus texts; metadata formats: atf 208, lem 207, tr-en 204. Every file states “This data is released under the CC0 license”; the documentation footer says CC BY-SA 3.0 for the site. Config `external-proj-abbrev` is `CCP`, which is supporting (not conclusive) evidence for eBL's `ccp` label.

- Overlap by exact identifiers: 51 ccpo texts have the P-number of an eBL record's `cdliNumber`. ORACC's catalogue eBL key agrees with that eBL record in all 51 (0 conflicts). Only 44 of eBL's 459 `ccp`-labelled records fall in the ccpo corpus.
- Imported 51 texts → `snapshot:edaab55c1a39cc65ad7c76e6d12547a7`: 6,888 source word instances, 4,544 lemmatized (each with its contextual English sense), 2,344 without citation form (excluded from Lemma, kept as WordToken), 1,122 lemmas, 1,317 senses, 51 CDLI claims, 54 eBL-key claims.
- **Translation text is absent from the JSON export** (only a stemmed translation index). All 51 imported texts list tr-en; each records that gap as an exclusion. No TranslationSegment is created. ORACC senses and guidewords are English lexical glosses, not translations.
- Grapheme lists (`f.gdl`) are kept in raw JSON and not mapped to SignOccurrence in this revision.

## CDLI (current framework, cdli.earth)

Per-artifact JSON `https://cdli.earth/artifacts/<id>.json` for exactly the 51 P-numbers claimed by the eBL overlap cohort; 51 receipts, serial requests at 1 s spacing. Imported → `snapshot:fc7c350439f9edfee61b5f35bdd4d65a`: 51 artifacts, 334 attributed claims (95 catalog labels, 54 eBL keys, 185 other external keys), 0 rejections, no text. In all 51 cases CDLI's eBL key names the eBL record whose own `cdliNumber` claim is that P-number; 3 further CDLI/ORACC eBL keys point at eBL records outside the cohort and stay unresolved. Terms of Use cover transliterations/translations (free academic reuse with attribution) and images (non-commercial). Catalog metadata is not separately licensed.

## Not established

Scholarly correctness of readings, sign identities or lemmatizations; compositions/passages; word or line alignment of any translation; signs↔ATF position alignment; physical joins; dates; images. Rights remain per-source statements: the eBL conflict is unresolved, and the ORACC CC0 statement and CDLI terms were not legally reviewed.
