# Parser revisions and superseded snapshots

The canonical record of parser defects that changed what a published snapshot contains, and of which snapshot
supersedes which. Published snapshots are never edited or deleted (see `artifact:publication-ledger`), so a defect
in a published snapshot is recorded here, not repaired in place. A UI or report that shows a superseded snapshot
should link to the matching section below.

## conservative-3 → conservative-4 (Q-026, 2026-11-05)

**Status:** the new snapshot is built and checked by its writer and is **pending independent review**. The old
snapshot stays published, accepted for its engineering scope (Q-023), and readable.

| | Superseded | Replacement (pending review) |
|---|---|---|
| Snapshot | `snapshot:965aa26214dc0388dd3af1be367d2acc` | `NEW_SID` |
| Manifest sha256 | `44a20685b069802c46a2b9c158239ccf369c5f5f566f7267ad8a86dc298e3c84` | `NEW_MANIFEST` |
| Cohort | `cohort:4e532850276b7960e67f149f6463afcf` | `cohort:b07f1ade15656c9cc09b0750e48697f9` |
| Parser | `conservative-3` (built by `5c7a01b`, read by pin `057a0b7`) | `conservative-4` (built by `6e548c1`) |
| Source | eBL Zenodo 10018951 `fragments.json`, sha256 `4e970d87…d753`, receipt `receipt:66b5c944…` | same bytes, same receipt |
| Members | 20,896 of 23,289 | 20,896 of 23,289, the same records with the same reasons for exclusion |

### What was wrong in conservative-3

Found by `reviews/reading-aids-review-v0.1.md` (F1 and its surface note), then recounted independently from the
raw release for this revision.

1. **Comment lines stored as text lines.** `adapters.py` took any line whose first run without spaces ended in `.`
   as a numbered text line. 129 lines in 49 records were `#tr…`, `#note.` or `#Vgl.` lines: 57 translations with an
   extent or text containing `. `, 63 dot-form `#tr.en.`/`#tr. en:`/`#tr.ar.` lines, 8 `#note.` lines and 1 `#Vgl.`
   line. They added 2,258 positions (1,579 `reading`, 626 `unsupported`, 53 `gap`), 1,579 postings and 7,779 n-grams
   to the `atf` layer. Most of these are English words (`the`, `of`), and some inflate genuine readings (`he` 20 of
   28 positions, `I` 13 of 27). **The `atf` readings layer of `965aa262` is therefore not pure transliteration:**
   129 of its 629,335 lines are translation or note text. The `signs` layer is clean (eBL has no sign rows for these
   lines), and translations were already stored separately, so their rows are unaffected.
2. **Structure markers stored as surfaces.** Every `@` line other than `@column` became `line.surface`. In the 20,896
   members, 8,108 `atf` lines carried a marker that eBL's ATF grammar does not define as a surface: `colophon` 5,796,
   `date` 1,207, `seal 1` 523, `catchline` 266, `tablet` 116, `end of column` 101, and smaller groups. The real
   surface was lost for those lines. (The review counted 8,362 rows in 41 kinds. The difference, 254 rows in 12
   kinds, is `@surface …` and `@face …`, which the grammar does define as surfaces, so they are kept.)

### What conservative-4 does

From the retained eBL-ATF grammar (`.output/q025-refs/ebl-api/ebl-atf.md`, sha256 `be7c5ccf…`):

- A text line is `line-number. text`, where the line number is `[letter+]digits[prime][letter]`, optionally a
  range. A line starting with `#`, `$`, `&` or `@` is never a text line. Every genuine label in the release
  (325,739 lines) fits this grammar, so nothing else changes. A label outside the grammar is excluded with the
  reason "ATF line label outside eBL line-number grammar retained in raw" (0 in this release).
- Translations are unchanged: 23,984 segments, all `unresolved-span`, each keeping its source record, language, raw
  text and byte locator. No line or word alignment is added. The 63 dot-form `#tr` lines stay excluded as
  "unsupported translation syntax retained in raw". They are not reinterpreted as translations.
- Only surface markers (obverse, reverse, left, right, top, bottom, edge, face …, surface …, with status flags) set
  the surface. Discourse markers (colophon, date, catchline, signature(s), summary, witnesses), headings and
  `m=division` keep the current surface and column. Object and seal markers (tablet, envelope, prism, bulla,
  fragment …, object …, seal N), and any marker the grammar does not define (such as `end of column`), leave the
  surface and column **unknown** (NULL). No surface is inferred. Every raw `@` line stays in the record and in the
  non-token exclusion accounting.
- Sequence IDs include the parser version, so every sequence, line, occurrence, edge, posting and n-gram ID is new.
  Source records, artifacts and claims keep the same content; artifact IDs are unchanged.

### Exact changes (members only; independently recounted)

Writer-reported dry run: 129 lines, 2,258 positions, 1,579 postings and 7,779 n-grams removed. Full snapshot verification was interrupted at project closure; no independent acceptance is claimed.

### Consumers

- **Benchmarks** (`cuneiform-benchmarks` `0be7e12`, cb-protocol-1) are bound to `965aa262` by snapshot ID, manifest
  sha256 `44a20685…` and backend pin `057a0b7`. Those results stay bound to the old data, which is unchanged.
  The signs layer was unchanged in the writer's dry run. Benchmark results remain tied to the original snapshot.
- **UI** (`cuneiform-ui`) reads the old snapshot through pin `057a0b7`. A conservative-4 snapshot needs a new pin and
  `conservative-4` in the UI's supported parser set. Until then the live UI lists the new snapshot as incompatible
  and keeps serving the old one.
- **Readers of the old snapshot** should drop `line.label LIKE '#%'` rows (and their positions, postings and
  n-grams) from `atf` counts, and should not read `line.surface` as a physical surface when it is a structure
  marker.
