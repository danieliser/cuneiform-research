# Reading aids: sources, checks and limits (Q-025)

What the sibling workbench (`cuneiform-ui`, Q-025) uses to explain readings, draw standardized glyphs and place the source's translations, and how each piece was checked. No backend code, schema, snapshot or projection changed; the backend pin stays `057a0b7`. Dataset: `snapshot:965aa26214dc0388dd3af1be367d2acc` (full eligible eBL release, 20,896 of 23,289 records).

Reference downloads were authorized by the owner for this task (small public files, no accounts, no paid services). Raw copies and receipts are kept outside git in `cuneiform-research/.output/q025-refs/` (15 MB, ignored). Only small derived tables are committed, in `cuneiform-ui/server/refdata/`.

## 1. Translation placement (line level)

The backend stores 23,984 translation segments with granularity `unresolved-span` and a locator that is the byte span of the whole `#tr…:` line in the record's ATF. The workbench places them at line level using eBL's own rule, read from the eBL code at commit `36c41664a3cde0c0ed227fa1755eaeaa74a0f817`:

- `ebl/transliteration/domain/labels_validator.py` (sha256 `4656a5a8…`): a translation line belongs to the text line immediately before it; `#tr.en.(r 3):` covers every text line from that one through the line named in the extent, inclusive; a translation before any text line is an error.
- `ebl/transliteration/domain/translation_line.py` (sha256 `0d4b5720…`): the extent is `(labels line-number)`, labels being surface and column.
- The eBL-ATF specification (`docs/ebl-atf.md`, sha256 `be7c5ccf…`) defines `translation-line = '#tr', ['.', language], ['.', extent], ': ', markup` and refers to the ORACC translation guide (fetched, sha256 `e1338a52…`), which documents interlinear `#tr.<lang>:` lines but not eBL's extent form.

This is line placement only. Nothing aligns words of a translation with signs.

Full-corpus check (`cuneiform-ui/tools/check_translation_placement.py`, an independent re-scan of each record's raw ATF text lines):

| Status | Segments |
|---|---|
| covers the line before it (`line`) | 21,971 |
| extent located, several lines (`extent`) | 1,457 |
| extent not among this edition's line labels (`extent-unresolved`, shown at its first line, extent text quoted) | 556 |
| first placed line differs from the raw scan | 0 |
| extent line count differs from the raw scan | 0 |

Most unresolved extents use forms outside eBL's grammar (for example `(1 2-6)`, `(col 1 3)`, `(b 2)`); they are reported, not guessed.

**Backend finding (not fixed here):** parser `conservative-3` keeps some comment lines as text lines. When an extent contains `. ` (for example `#tr.en.(b.e. 1):`) or for some `#note:` lines, the line gets a label such as `#tr.en.(b.e`. 129 such `line` rows in 49 texts carry 2,258 `occurrence` positions made from English or note words. Placement skips them; the tablet view labels them. A backend fix would change counts and needs its own queue task.

## 2. Standardized glyphs (ABZ number → Unicode)

The release's `signs` field uses Borger's ABZ numbers without a stated sign-list revision (`MAPS_TO_SIGN` qualification `sign_list_revision: unknown`).

- **ORACC OSL** (`oracc/osl` commit `9b5f358c29636a3c23c505e19a2f58dd2e9687ef`, `00lib/osl.asl`, sha256 `b1555336…`, CC0 stated in the file). Its active `ABZL` list is Mittermayer's *Altbabylonische Zeichenliste* (2006), not Borger's ABZ; Borger's ABZ appears only as a commented-out list definition. OSL therefore cannot map eBL ABZ numbers by itself and is used only to cross-check code points by sign name. (OSL's `SLLHA` numbers often equal ABZ numbers, but it is a different list and was not used.)
- **eBL sign list** (public API, no authentication): `GET https://www.ebl.lmu.de/api/signs?listsName=ABZ&listsNumber=<n>` for each of the 421 ABZ labels in the snapshot, fetched 2026-11-05 22:35Z at a low rate (421 responses, 9.8 MB; receipts sha256 `e8414488…`; combined response hash `fab078b3…`). Each record gives the sign name, its list numbers (ABZ, MZL, HZL, OBZL, SLLHA), Unicode code points and sign values. Only these facts are committed (`sign-map.json`, 243 KB, sha256 `fcb39355…`); the MZL and logogram texts are not copied. eBL states no separate licence for the sign-list API; it is used here for local reference only.
- **Font**: Noto Sans Cuneiform v2.001, official release `notofonts/cuneiform` (zip sha256 `b686250d…`), unhinted OTF 434 KB (sha256 `ac997e70…`) with `OFL.txt`. Extracted by member name; the zip contains `../` entries and was never unpacked.

Result per ABZ label (421 labels; positions are of the release's signs layer, 2,429,757 in total):

| Status | Labels | Positions | Shown |
|---|---|---|---|
| verified: one eBL sign, OSL gives the same code points for that name | 328 | 1,744,450 (71.8%) | glyph |
| same-glyph: several eBL sign names, one code point (e.g. ABZ 480: DIŠ, NIGIDA) | 5 | 83,554 (3.4%) | glyph, names listed |
| eBL-only: one sign, no OSL entry under that name to compare | 9 | 43,087 (1.8%) | glyph, marked eBL-only |
| ambiguous: several signs with different glyphs (e.g. ABZ 597 GAR/LIMMU, ABZ 69 BAD/TIL/IDIM, ABZ 537 DIB/LU) | 79 | 554,681 (22.8%) | no glyph; alternatives listed |
| conflict (single sign, eBL ≠ OSL) | 0 | 0 | — |

Five sign records disagree with OSL or are not fully encoded (for example `|GA₂×ZIZ₂|`: eBL U+123FA, OSL U+124C8); all sit inside ambiguous sets and are never drawn. The 228 non-ABZ labels (sign names or raw values the release did not resolve, 3,985 positions) are not looked up.

Transliteration tokens get glyphs through sign values instead: each written part (split at `-` `.` `+` and determinative braces) is looked up among the values of the fetched signs; a value listed by exactly one sign gives its glyph, otherwise none. Coverage over the 1,827,524 transliteration positions (`tools/glyph_coverage.py`): 1,022,323 fully drawn (83.0% of the 1,232,262 legible sign-bearing positions), 115,168 partly, 94,719 none (52 more have only ambiguous values) (mostly numbers, which are not looked up, and values missing from the fetched signs), 470,377 broken or unreadable, 124,885 non-sign tokens.

**Revision check against the release itself** (`tools/check_sign_map.py`): expanding each transliteration line into sign values, mapping them through the table to ABZ numbers and comparing with the release's own signs line, on 57,652 lines where both layers pair unambiguously and have equal length: 534,161 positions agree, 1,744 disagree (99.67%); 146 more positions have an ambiguous value with one agreeing candidate. The disagreements are mostly residual misalignment plus a few real revision differences (for example `eš₁₈`, `sig₅`, `zag₃`). 78% of lines were not comparable (unparsed compounds, numbers, unequal lengths), so this measures agreement where comparison is possible, not overall correctness.

A glyph is a standard Unicode character drawn by a font. It is not the tablet's handwriting, and the dataset has no photographs.

## 3. Reading explanations

- **ORACC ccpo lemmatization** (the served `oracc-cdl-2` snapshot `5e51403b…`, CC0 as stated in the ORACC files): exact written form → lemma (citation form, guideword, POS) → senses, with counts. For example `KUR` → mātu [land] 56×, erṣetu 2×, ēkallu 2×, niphu 2×; `ina` → ina [in] PRP 295× (senses in, at, from, on, by); `{d}UTU` → Šamaš 20×. Guidewords and senses are labelled dictionary glosses, never translations. ccpo has no word written `DIŠ`.
- **Curated notes** (`reading-notes.json`): one context-dependent sign (DIŠ: šumma ‘if’ at the start of omens, marked with a query by Borger; numeral 1/60; personal-name determinative; ana), each use citing R. Borger, *Mesopotamisches Zeichenlexikon* no. 748 as shown on the eBL sign page; and transliteration conventions (logogram, syllabic value, sub-index, determinative, flags) citing the eBL-ATF grammar. No universal English meaning is given for any sign.
- **Corpus context**: counts by source genre and up to three lines with the reading that a source English translation covers, the open tablet first. The translation is labelled as rendering the whole line or passage.

## 4. Pronunciation

Research result:

- A transliteration names signs; it is not pronunciation. Scholars write a separate normalized (transcribed) form. SOAS BAPLAR pages state this directly ("The transcription is based on the transliteration provided in R. Borger, *Babylonisch-assyrische Lesestücke*…").
- **SOAS, Babylonian and Assyrian Poetry and Literature: An Archive of Recordings** (`https://www.soas.ac.uk/baplar/recordings`, page sha256 `51a4796f…`): recordings by named Assyriologists (Hecker, Wasserman, West, Huehnergard, Wilcke and others) of Akkadian literary texts with normalized transcript and translation. They are modern scholarly readings, not ancient sound.

Implemented: a "Reading & pronunciation" section in the reading panel with (a) the ORACC ccpo citation form where one exists, labelled as a modern transcription; (b) four cited caveats (transliteration is not pronunciation; logograms are read as different words; the exact ancient sound is unknown and varied by period and region; recordings are informed modern readings); (c) a link to BAPLAR; (d) links to specific BAPLAR recordings only when the source genre names the same composition (Gilgameš, Enūma eliš, Ludlul bēl nēmeqi, Atraḫasīs, Anzû), labelled as another manuscript, not this tablet. Every link was checked (HTTP 200). Nothing is embedded or played, and no speech is synthesized.

Not implemented (follow-up): normalized forms for words ORACC ccpo does not lemmatize; period-specific phonology notes; per-line normalization. These need a lemmatized source for the eBL texts themselves, which the release does not supply.
