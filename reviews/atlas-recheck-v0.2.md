# Independent re-check of the Q-021 atlas repair (Q-019 R1–R10)

- **Reviewed:** commit `e124672` (checker, atlas revision 4, queue, disposition), against backend `63f4221`. The backend was already accepted by `reviews/corpus-pilot-review-v0.3.md`; I did not re-audit it.
- **Reviewer:** an independent review sub-agent. It is not the Q-021 repair worker or the Q-019 reviewer. Date: 2026-11-03.
- **Scope:** a limited regression check of R1–R10, as `reviews/atlas-recheck-v0.1.md` defines them, and of the dispositions in `docs/ATLAS-RECHECK-v0.1-DISPOSITION.md`. This is not a new broad audit. The original 30 `corpus` claims were not recounted; Q-019 found them true and the cited snapshots are byte-identical.
- **Inputs read:** AGENTS.md, QUEUE.md (header, Q-019 to Q-022), `reviews/atlas-recheck-v0.1.md`, the disposition, `scripts/check_model_atlas.py` (Git, escape analysis, signing sites, registry and rights, the evidence reader, `check()` git binding), the Q-021 scratch `INDEX.md` and `scripts/mutations.py`, and the atlas entries for the temporal facets and `artifact:publication-ledger`.
- **Writes:** this file only. No atlas, checker, queue, backend or test edits. No commits, delegation, downloads, shared services or image work.
- **Scratch:** `~/.local/share/cuneiform-research/scratch/review-q021/`. It holds `export/` (clean `git archive e124672`), `clone/` (local `git clone` of the checkout, plus two scratch-only branches `side` and `r3-repro`), `dr/` (APFS clones of the three cited snapshots and the ledger, 95 MiB), `v-nodisk/` and `v-noschema/`, `scripts/` (`mut.py`, `temporal.py`, `fingerprint.py`) and outputs (`mut*.out`, `selftest-*.out`). Forged data used per-case clones of `dr/`, deleted after each case. Each case used at most about 190 MiB of apparent size.
- **Real store:** read only. The fingerprint (path, size, mtime, ctime, mode and SHA-256 under `snapshots/`, 172 entries) was `6ba1c85c…` before and after, byte-identical.

## Verdict

**NOT ACCEPTED. One concrete blocker remains, in R3 (signing-site detection).** R1, R2, R4, R5, R6, R8 and R10 are closed. R7 is accepted as documented trust. R9 has one small wording error (P3, not blocking).

R3 is only partly closed. A new signed construction path is found only when the digest is computed inline. If the digest goes through a local variable first (`d = digest(...); x['manifest_sha256'] = d`), the path is invisible. Its keys are never compared with the atlas, so this is the R3 failure class again. Reproduced end to end with the baseline moved, the checker prints `model atlas: OK`. See B1.

## Evidence (reviewer-observed)

| Command | Result |
|---|---|
| `python3 scripts/check_model_atlas.py` in the export, no `.git` | exit 1. "git: no repository … commit-bound evidence is refused", plus every `DONE` refused (fails closed, as R5 and R6 intend) |
| same with `--repo <checkout>` | `model atlas: OK` (warning: `../cuneiform-ui` not beside the export) |
| `<venv>/python -B scripts/check_model_atlas.py --repo <checkout> --runtime` in the export (real store, read only) | `model atlas: OK (runtime population checked)`, 8.9 s |
| same, `--data-root scratch/review-q021/dr` | OK |
| fresh `git clone` of the checkout (`e124672`): `check` and `--runtime` (real store) | both OK. The fresh clone is portable: `accepted_by` review files are committed |
| `python3 scripts/check_model_atlas.py --self-test` in the fresh clone and in the checkout | 47/47 each, exit 0 |
| R8: `v-nodisk` (all 4 `disk` lowered to `unit`) and `v-noschema` (both schema-only tables marked `implemented: code`); `check`, then `--self-test --git-ref WORKTREE` | `check` OK on both; self-test 46/46 on both. The schema-only cases ran on the synthetic fallback table |
| `<venv>/python -I scratch/review-q021/scripts/mut.py` (50 cases, my own harness, cases listed below) | 0 harness errors. Every planned mutation behaved as listed below |
| store fingerprint before and after | identical |
| `git status --porcelain` in the checkout before and after | clean except this file. HEAD is `e124672` |

I did not re-run the 70-test suite. The backend is unchanged at `63f4221` and was independently run by the v0.3 reviewer. I did not re-run the Q-021 worker's `mutations.py`, because its forge step copies its whole 0.7 GB data root, which is over my 200 MiB budget. My harness covers the same Q-019 rows independently.

## Mutation results (each on a clean copy of the `e124672` export, judged on errors other than staleness)

| Area | Mutation | Outcome |
|---|---|---|
| R1 | `fc7c3504` manifest count 334→777, re-signed, atlas count edited | caught: manifest digest ≠ ledger record, ≠ atlas pin |
| R1 | same plus the ledger digest and atlas pin rewritten (Parquet intact) | caught: "manifest counts claim=777, hashed Parquet has 334 rows" |
| R1 | `c316e7cb` `occurrence.parquet` trimmed to 100 rows, atlas counts edited | caught: "does not match its manifest hash" |
| R1 | `edaab55c` `edge.parquet` with `IN_SENSE` dropped, `files` hash re-signed, ledger untouched | caught: digest ≠ ledger, ≠ pin |
| R1 | listed payload file deleted | caught: listed but missing |
| R1 | cite incident `ce127437` | caught statically: status `incident` |
| R1 | incident relabelled `accepted`, with a review that names it | caught at runtime: ledger marks a rebuild incident |
| R1 | the same, plus the `incident` flag stripped from the ledger | refused (no served bytes in my data root); a full coordinated forgery is the documented limit |
| R1 | duplicate legacy ledger row; `adopt` event appended; unparseable middle record | all refused (conflict, conflict, unparseable) |
| R1 | `accepted_by` names a review that never mentions the ID | caught: "never mentions fc7c3504" |
| R1 | edge-kind evidence for a kind with 0 edges | caught: "the hashed payload has 0" |
| R2 | in `import_source` after `meta=…`: alias; helper; `dict.update(meta,…)`; `meta.__setitem__`; walrus alias; tuple-loop alias; `operator.setitem`; closure write | all 8 caught as unsupported (escape or mutator) |
| R3 | new helper returning `{**body, 'manifest_sha256': digest(...)}` | caught: key drift |
| R3 | new helper, `body['manifest_sha256'] = digest(...)` inline (control) | caught: key drift |
| R3 | new helper, `d = digest(...)`, then `body['manifest_sha256'] = d` | **passed** (stale only) |
| R3 | new helper, `d = digest(...)`, then `dict(body, manifest_sha256=d)` | **passed** (stale only) |
| R3 | new helper, `d = digest(...)`, then `{**body, 'manifest_sha256': d}` | **passed** (stale only) |
| R3 | new helper, `body.update(manifest_sha256=digest(...))` | **passed** (stale only) |
| R3 | key added to the import manifest after its signing line | passed (stale only). See N2 |
| R4 | local alias of `RIGHTS`; `adapters.RIGHTS.update` through a module alias; `RIGHTS` passed to a helper | all caught |
| R4 | `'rights': RIGHTS.get(source, {'status':'cc0'})` in `import_source` (fallback grant) | caught: computed kind must use exactly `RIGHTS[source]` |
| R4 | `RIGHTS['ebl'].status` → `cc0` in the literal | caught: status ≠ atlas, and the `ebl-cohort` statement hash changed |
| R4 | `cdli_api.RIGHTS` text widened; `ebl-cohort` fallback replaced by an inline grant | caught: statement changed |
| R4 | atlas `rights_status['oracc-selection']` → `cc0` (runtime) | caught: manifest `rights.status 'source-stated'` ≠ atlas |
| R5 | baseline is a tree ID, nonexistent hex, or task ID `44ddaeb1`; run `code_ref` has 6 hex characters | all caught: "does not resolve" |
| R5 | baseline moved back to the real commit `94af111` | caught: stale in 5 files |
| R5 | comment-only edit in `tests/`; new untracked file in `fixtures/`; all `63f4221` runs removed | caught: baseline stale, or "entries rest on old runs" |
| R5 | control: edits to `docs/` and `README.md` only | passes, as designed |
| R6 | `DONE` (Q-010, a block with no commit tokens) citing only a task ID, a tree ID, a blob ID, or a commit on an unmerged side branch (`--repo` = reviewer clone) | all caught |
| R6 | control: the same block citing `63f4221` | passes |

Notes on the harness: my first anchor for R2 hit the `inspect` return line, and two of my Parquet swaps first rewrote empty tables, which gave identical bytes. I corrected both, and only the corrected runs appear above (`mut2.out`, `mut3.out`, `mut4.out`; the first run is `mut.out`). The `adopt` case cannot isolate the format-2 adopt rule, because the cited snapshots have legacy rows. It is refused as a conflict instead.

## Findings

### B1 — P2, blocker for R3 closure — a digest held in a local name hides a new signed construction path

**Where:** `scripts/check_model_atlas.py:545–550` (`computed`) and `:564–576` (`snapshot_manifests`). `computed()` treats every `ast.Name` value as "copied from another record". A local variable holding a freshly computed digest is not a copy. `<x>.update(manifest_sha256=…)` and `.setdefault` are not looked at at all. The only exception is the hard-coded `manifest = {...}` name rule (`:577–579`), which is why the four current writers pass.

**Reproduction** (scratch clone only; branch `r3-repro`, commit `ac42a78eae`, never pushed):

```sh
cd ~/.local/share/cuneiform-research/scratch/review-q021/clone
git checkout r3-repro            # adds to cuneiform/storage.py:
#   def _r_sign2(sid):
#       body={'snapshot_id':sid,'r_namesite':1}
#       d=digest(canonical(body).encode())
#       body['manifest_sha256']=d
#       return body
# then, as a real sync would: baseline_commit and the 63f4221 runs' code_ref -> ac42a78eae
python3 scripts/check_model_atlas.py            # model atlas: OK, exit 0
<venv>/python -B scripts/check_model_atlas.py --runtime   # OK (runtime population checked)
grep -c r_namesite docs/model-atlas.json        # 0: the new manifest key is undeclared
```

With the digest inline (`body['manifest_sha256']=digest(...)`), the same helper fails with "manifest keys drift: code writes ['r_namesite']". So the result depends only on whether a temporary variable is used. That is an ordinary refactor, not an exotic form, so I do not treat it as theorem-prover scope. It repeats R3 as reported ("new signing sites are invisible unless …"). The disposition's narrowing ("copies from other records (name, …) are not sites") is right for ledger rows and receipts. It is wrong for a name bound in the same scope to a computed value.

**Fix (bounded):** when the value is an `ast.Name`, resolve it with `find_binding` in its scope:
- A `value` binding whose expression is `computed()` (recursively) makes the write a signing site.
- A parameter binding stays a copy. This covers the only Name-valued writes in today's code: `publication.py:364/374/383`, the `publish_dir(..., manifest_sha256, ...)` parameter. I enumerated them by AST, so the fix creates no false positive today.
- A binding that cannot be resolved raises `Unsupported`.

Also treat `<x>.update(manifest_sha256=<computed>)` and `setdefault('manifest_sha256', …)` as sites, or as `Unsupported`. Add the four forms from the table above as analyzer self-tests. Then re-run this harness (`scripts/mut.py R3`).

### N1 — P3, not blocking (R9 wording) — eBL `date` is absent, not present-and-null

`facet:ebl-temporal-fields` says "date and datesInText are present as fields" and "date is null … in all 51". In copies of `c316e7cb` `source_record.raw_json` (51 records), `datesInText` is a key in 51/51, with value `[]` in all 51, but `date` is a key in **0/51**. Everything else in both facets matches my read (`scratch/review-q021/scripts/temporal.py`):

- **CDLI:** `period` object keys `{id,name,period,sequence,time_range}`, 41 present and 10 null; `dates` `[]` in 51/51; `dates_referenced` null in 50 and `'Artaxerxes.19.11.23'` in 1.
- **eBL:** `script` keys `{period,periodModifier,sortKey,uncertain}`; periods 24/20/3 plus two others (Persian 2, Hellenistic 2); `periodModifier` `'None'` in 51/51; no `archaeology`; 374 `record` events with keys `{date,type,user}`.

No date was interpreted. Correct the wording at the next atlas touch ("date: no such key in these 51 records").

### N2 — P3, not blocking — keys added after the signing line are not tracked

Mutations count only between the binding and the signing site (`apply_mutations`, `bpos < npos < upos`). A key added after `manifest['manifest_sha256']=…` passes static analysis. In practice it breaks every self-hash, so `storage.verify`, the evidence reader and the disk tests would refuse every snapshot. That makes it loud at runtime, which is acceptable for a bounded checker. A one-line `Unsupported` for any later mutation in the same scope would close it, if cheap.

### R-by-R closure

| ID | Status in this re-check |
|---|---|
| R1 | **Closed.** Fake counts, swapped table and edge Parquet, rebuilt or relabelled incidents, ledger deletion, conflicts, unparseable records, unnamed `accepted_by` and absent edge kinds all refuse. The only pass is the documented coordinated forgery of every artifact. |
| R2 | **Closed** for every escape form I tried (8). |
| R3 | **Open (B1).** Literal and `dict()` sites with an inline digest are found. Sites whose digest goes through a local variable, and `.update(manifest_sha256=…)`, are not. |
| R4 | **Closed.** Aliases, module-alias `update`, helpers, `.get` fallback grants, literal status edits, statement text edits and runtime status mismatch all fail. |
| R5 | **Closed.** Trees, task IDs, unknown hex, short refs, an older real baseline, `tests/` and untracked `fixtures/` edits all fail. The doc-only control passes. With no `.git`, it fails closed. |
| R6 | **Closed.** Task, tree and blob IDs and non-ancestor commits are refused; a real ancestor is accepted. A block that already cites any ancestor commit passes by design (the disposition says so). |
| R7 | Accepted as documented trust (unchanged). |
| R8 | **Closed.** A no-disk atlas and a no-schema-only atlas are both valid, and both self-test 46/46. |
| R9 | **Closed with N1** (one field described wrongly). |
| R10 | **Closed.** `artifact:publication-ledger` scopes the guarantee to the cooperating-writer pilot accepted by v0.3. It states "Not proven beyond that scope" and lists the protocol limits. The two incident IDs stay `incident` and are never evidence. |

### Pins and portability

- The `corpus_snapshots` pins of the three cited snapshots equal their ledger rows and served manifests (runtime reader, real store and my clones). The `5e51403b` pin `48bdc39e…` equals its reserve and commit rows. Its `accepted_by` (v0.2, v0.3) exist and name it.
- `review-v03-disk-63f4221` (`read_back: true`, 70 OK, 40.787 s, 0 skipped) matches `reviews/corpus-pilot-review-v0.3.md` §8 and its decision "ACCEPT for the authorized local cooperating-writer pilot".
- `q021-disk-63f4221` is `read_back: true` as the worker's own run, which AGENTS.md allows. I did not re-run it.
- A fresh clone checks OK without the sibling UI repo; the missing sibling is only a warning. A `git archive` export fails closed until `--repo` is given, as the disposition says.

## Dispositions requested

| ID | Sev | Owner | Blocks |
|---|---|---|---|
| B1 | P2 | Checker owner (Q-021 follow-up) | Q-021 and Q-019 closure: R3 is not closed |
| N1 | P3 | Atlas owner, next touch | none |
| N2 | P3 | Checker owner, optional | none |

After the B1 fix, a re-check can be limited to `scripts/mut.py R3` and a self-test run.

## Reproduce

```sh
S=~/.local/share/cuneiform-research/scratch/review-q021
PY=~/.local/share/cuneiform-research/venv/bin/python
REPO=/Users/danieliser/Projects/Fun/cuneiform-research
python3 -I $S/scripts/fingerprint.py $S/fp-check.json      # compare with fp-before.json
(cd $S/export && python3 scripts/check_model_atlas.py --repo $REPO && $PY -B scripts/check_model_atlas.py --repo $REPO --runtime)
(cd $S/clone && git checkout -q main && python3 scripts/check_model_atlas.py --self-test)
$PY -I $S/scripts/mut.py            # all cases; or pass name filters, e.g. "R3"
$PY -I $S/scripts/temporal.py $S/dr
```
