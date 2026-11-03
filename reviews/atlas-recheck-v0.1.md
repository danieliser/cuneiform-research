# Independent re-check of the atlas and checker (Q-019)

- **Reviewed:** commits `fd54419` (atlas revision 2, checker, Q-004 fixes) and `11be81d` (queue record), against the fixed backend at `d6049e2`. The code under `cuneiform/`, `tests/`, `fixtures/` and `sources/` is identical at `d6049e2` and `11be81d` (`git diff --quiet`, exit 0).
- **Reviewer:** an independent review sub-agent, not the Q-003 or Q-018 builder. Date: 2026-11-03, about 10:20–10:40Z.
- **Inputs read:** AGENTS.md, QUEUE.md, `docs/model-atlas.json`, the generated Markdown and HTML blocks (through the checker), `scripts/check_model_atlas.py` (read in full), `reviews/atlas-review-v0.1.md` and `reviews/corpus-pilot-review-v0.1.md`.
- **Writes:** this file and factual lines in QUEUE.md. No atlas, checker, backend, test or UI edits. Nothing staged or committed. No downloads, installs, disk tests, shared services or image work, and no agents started.
- **Scratch:** `~/.local/share/cuneiform-research/scratch/review-q019/` (git-ignored data root). It holds a clean `git archive` export of `11be81d` (`base/`), copies of the three snapshots' `graph.duckdb`, manifests and Parquet (`copies/`, `dataroot/`), and the scripts `count_claims.py`, `mutations.py`, `done_sha_proto.py` and `fingerprint.py`, plus their outputs.
- **Published store:** fingerprinted (path, size, mtime, ctime, mode and SHA-256 of every entry under `snapshots/`). Before my reads and after the mutation runs it was `65fe1d56…24b1af` (141 entries) both times. All reads of snapshot data used copies. The final fingerprint (~10:45Z, 172 entries) differs only by additions from someone else. At 10:36:22Z a new snapshot `snapshot:5e51403b0d7dcdb90cb429d444e6a23b` (`oracc-selection`, `snapshot_contract: manifest-3`) was published with `.locks/`, `.publication.lock`, and two ledger lines in a new format (`ledger_format: 2`, `event: reserve` then `event: commit`). My code was `d6049e2`, which has no reserve events, and my only test run was in-memory, so the writer is the backend fix code (`44ddaeb1`; there is a `scratch/q005-fix/` directory). The five original snapshots are byte-identical, and the first 1,808 bytes of the ledger hash to the earlier value, so the earlier rows are intact (append-only).

## Verdict

**The checker and atlas are sound at `d6049e2` for every claim they make today.** Every check I could reproduce passed, and all 30 `corpus` claims are true by my own row counts. The Q-004 fixes behave as described for the code forms they target.

**The checker is weaker than its own description.** Its docstring and AGENTS.md say unsupported forms fail rather than pass an incomplete inventory. 16 of my 19 adversarial mutations passed silently. None of those forms exist in `d6049e2`, so no current claim is wrong. They are drift risks for the next contract change, which is already under way: the backend fix task `44ddaeb1` has uncommitted edits in this checkout.

The substantive gaps are R1 (corpus counts trust writer-signed manifests and unhashed Parquet, and incident IDs can be cited), R2–R4 (manifest-key and rights analysis follow names, not values), R5 (the baseline commit is never resolved or compared with the code being checked) and R10 (the publication-ledger summary states a guarantee the Q-005 review disproved). R6–R9 are hardening and documentation.

## Evidence (reviewer-observed)

| Command (repo root unless noted) | Result |
|---|---|
| `python3 scripts/check_model_atlas.py --git-ref d6049e2` | `model atlas: OK`, exit 0 |
| `<venv>/python -B scripts/check_model_atlas.py --git-ref d6049e2 --runtime` | `model atlas: OK (runtime population checked)`, exit 0. Drives `cdli`, `ebl`, `ebl-cohort`, `oracc-selection`; `cdli-selection`, `ebl-atf` and `oracc` are listed as unexercised with reasons. |
| `python3 scripts/check_model_atlas.py --self-test --git-ref d6049e2` | 34/34, exit 0 |
| `<venv>/python -B -m unittest discover -s tests` in the clean `11be81d` export | `Ran 43 tests in 14.338s`, `OK (skipped=5)` |
| `python3 scripts/check_model_atlas.py --git-ref HEAD` at 10:34Z | `model atlas: OK` |
| `python3 scripts/check_model_atlas.py` (live tree, 10:34Z) | 4 errors from the backend fixer's uncommitted edits. See "Synchronization requirements". |
| `<venv>/python -I scratch/review-q019/scripts/count_claims.py` | 30 corpus entries, 49 evidence items, **0 mismatches** |
| `<venv>/python -I scratch/review-q019/scripts/mutations.py` | 3/3 controls caught; 16 evasions passed (table under R1–R6) |

I did not run the disk tests. The backend fixer is active in this store, and a disk run would compete with it for the storage guard. The `disk (UNVERIFIED)` labels therefore remain correct as rendered. The Q-005 reviewer reports a disk run at `d6049e2` (`Ran 43 tests in 16.007s OK`). That observer is independent of the claimant, but I did not read the run back. See S4.

## Corpus claims: independent read of 30 entries

`count_claims.py` opens **copies** of each `graph.duckdb` read-only and counts rows itself. It does not use manifest counts. It counts edges by `kind` from the `edge` table and compares them with the exported `edge.parquet`. It recomputes every `files` hash against the originals, recomputes the manifest self-digest with its own canonical JSON, and compares `manifest_sha256` with the publication ledger.

| Snapshot | Source | Self-digest | Payload hashes | Ledger match | Incident row | Manifest counts = DB rows | DB edges = Parquet edges |
|---|---|---|---|---|---|---|---|
| `c316e7cb…` | `ebl-cohort` | ok | all ok, no unlisted files | yes | no | yes | yes |
| `edaab55c…` | `oracc-selection` | ok | all ok, no unlisted files | yes | no | yes | yes |
| `fc7c3504…` | `cdli-selection` | ok | all ok, no unlisted files | yes | no | yes | yes |

All 49 cited counts equal my counts, for example `word_token` 6,888, `LEMMATIZED_AS` and `IN_SENSE` 4,544 each, `NEXT` 18,418, `ngram` 62,152, and claims 51/105/334. None of the three cited snapshots is one of the two rebuilt incident IDs. The claims are honest. The checker's own way of confirming them is weaker (R1).

Claims not made are also honest. Every non-empty table in each snapshot is either claimed or view-derived. `fc7c3504` has 0 edges, so it supports only table claims. Lemma and sense rows exist only in `edaab55c`. `node:Composition`, `node:Passage`, `edge:HAS_SIGN` and `edge:TRANSLATES` are 0 everywhere and stay `none`.

Real manifest keys against the atlas: all five manifests use only atlas-listed keys. Every non-optional atlas key is present except `snapshot_contract`, which the atlas field note says is absent from the five legacy-identity manifests. That is accurate.

## Temporal model and precision

Sound. I found nothing that infers historical precision.

- `value:TemporalExtent`, `node:DateClaim`, `node:ChronologyScheme`, `value:temporal-role` and `temporal:source-validity` are all `proposed` / `implemented: none` / `populated: none`. `precision` now offers `as-printed` (the default for printed ranges) and `unknown`, and the note says round numbers never imply century precision. `approximate` does not widen bounds. Astronomical years are set only when the source states an absolute year. `end_bound` is open for `ff.`.
- TD-1 to TD-7 carry accepted decision records with the escalation trigger. They are `documented`, and none claims an implementation.
- **Real data:** the only claim predicate in all three snapshots is `catalog_alias`, with 0 date-like predicates. Raw temporal fields are retained verbatim in `source_record.raw_json`. CDLI has `period` (an object, for example `"period":"Neo-Assyrian (ca. 911-612 BC)","time_range":"ca. 911-612 BC"`) and `dates`. eBL has `script.period`, `periodModifier`, `date` and `datesInText`.
- `temporal:system-time` is `verified: disk`, rendered UNVERIFIED, with an honest note.
- Documentation gap (R9): both temporal facets still describe the CSV headers and the single retained eBL record. They do not describe the JSON shapes now persisted.

## Baseline vs new backend changes

- **Sound baseline (`d6049e2` code, `11be81d` atlas):** every check in the evidence table passes. The 30 corpus claims, the `disk (UNVERIFIED)` labels, the decision records and the F7 UI and FalkorDB wording (`567ea14`, verified none) were honest when committed.
- **Changed since:** at 10:34Z the live tree had uncommitted edits by the backend fix task `44ddaeb1`: `cdli_api.py`, `cli.py`, `corpus.py`, `oracc.py`, `persisted.py`, `query.py`, `storage.py`, `tests/test_corpus_pilot.py` and a new `cuneiform/publication.py`. I did not read them. The live checker already reports drift (see S1). The UI sibling moved to `ca4b514` (parent-reported: Browser `:23001` and freeform Cypher disabled). This review makes no claim about either change. Nothing here is final integration evidence.

## Findings

Severity: **P1** breaks a stated guarantee now; **P2** lets a wrong claim pass or misstates a guarantee; **P3** is hardening or documentation. Every "passed" row is a mutation in a scratch copy, run with `--root <copy>` (and `--runtime --data-root <scratch>` where marked).

| Mutation (scratch) | Expected | Observed |
|---|---|---|
| control: `**{k:v for k,v in meta.items()}` | fail | caught (unsupported) |
| control: `manifest \|= {...}` before signing | fail | caught (augmented assignment) |
| control: `meta['q019_sub']=1` in `import_source` | fail | caught (manifest keys drift) |
| `alias=meta; alias['q019_alias']=1` | fail | **passed** |
| `_q019_add(meta)` where the helper writes a key | fail | **passed** |
| `dict.update(meta, q019_du=1)` | fail | **passed** |
| new signed dict `{**body,'manifest_sha256':…}` not named `manifest` | fail | **passed** |
| `_r = RIGHTS; _r['q019-alias'] = {...}` | fail | **passed** |
| `cohort.get('rights') or {'status':'cc0-q019'}` (invented fallback grant) | fail | **passed** |
| new import path with `source = prefix + '-q019'` and inline `rights` | fail | **passed** |
| `cdli_api.RIGHTS` gains `'q019_license':'CC0'` | fail or flag | **passed** |
| runtime: `fc7c3504` manifest `counts.claim` → 999, re-signed; atlas 999 | fail | **passed** |
| runtime: `edaab55c` `edge.parquet` rewritten (half of `IN_SENSE` dropped), atlas updated | fail | **passed** |
| runtime: evidence cites incident snapshot `ce127437…` | fail | **passed** |
| runtime: corpus evidence observer "corpus worker (reported, not read back)" | flag | **passed** |
| run `code_ref` = `d` | fail | **passed** |
| `baseline_commit` and runs set to nonexistent `deadbee` | fail | **passed** |
| claimant run `corpus-worker-disk-d6049e2` flipped to `read_back: true` | flag | **passed** (by design) |
| `DONE` block whose only hex token is task ID `8d17b311` | fail | **passed** (known limitation) |

### R1 — P2 — Corpus runtime check trusts writer-signed counts and unhashed Parquet, and ignores the ledger

`corpus_check` (`check_model_atlas.py:1230–1266`) checks the manifest self-digest, then compares table claims with `manifest.counts` and edge claims with `parquet/edge.parquet`. It never checks the Parquet against `manifest.files`, never counts actual rows, and never reads `.publication-ledger.jsonl`. A re-signed manifest with any count passes. So does a swapped edge Parquet. So does an incident ID, although AGENTS.md and the atlas allow only once-published snapshots as evidence. The self-digest is a writer-only check (Q-005: "self-hashes prove internal consistency, not authenticity"). `storage.verify()` would not catch a forged count either, because counts are not compared with rows.

**Fix:** for each cited snapshot, (1) hash `parquet/<table>.parquet` (or `parquet/edge.parquet`) and require it to equal `manifest.files`; (2) count rows from that hashed Parquet, not from `counts`, and also require `counts` to agree; (3) require a ledger row whose `manifest_sha256` equals the served manifest, and refuse rows that carry `incident` unless the atlas explicitly allow-lists them. Reading hashed Parquet avoids opening `graph.duckdb` inside the read-only store. Add self-test cases for all three.

### R2 — P2 — Manifest-key analysis tracks names, not values

`apply_mutations` (`:287–313`) watches only `name[...] = …`, `name.<mutator>()`, augmented assignment and `del` on the same name. Aliasing, passing the dict to a helper, and `dict.update(name, …)` all add keys without any error. This contradicts the docstring ("FAILS rather than passing an incomplete inventory").

**Fix (escape analysis):** between binding and use, every Load of the tracked name must be one of: a `**name` spread, `dict(name, …)`, a subscript read, a read-only method (`get`, `items`, `keys`, `values`), or the argument to the resolved materialize call. Anything else (assignment to another name, any other call argument, `dict.update`/`dict.setdefault` with the name first, attribute access outside that list) raises `Unsupported`. Re-run my alias, helper and `dict.update` mutations as self-test cases.

### R3 — P2 — New signing sites are invisible unless named `manifest` or written as `x['manifest_sha256'] = …`

`snapshot_manifests` (`:392–423`) finds sites only by those two forms. `{**body, 'manifest_sha256': …}` or `signed = dict(body, manifest_sha256=…)` introduces a whole construction path whose keys are never compared. This is the F1 failure class again, one level up.

**Fix:** also treat as sites any `ast.Dict` with a constant `'manifest_sha256'` or `'snapshot_id'` key and any `dict(…, manifest_sha256=…)`. Add the runtime cross-check I did by hand: for each cited snapshot, manifest keys ⊆ atlas fields, and non-optional fields ⊆ keys, with the documented legacy exception.

### R4 — P2 — Rights: aliases, per-snapshot fallbacks and computed source kinds pass silently

- `registry()` (`:438–474`) follows `RIGHTS`, its import aliases and module aliases. A local alias (`_r = RIGHTS`) is not followed.
- `rights_origin` (`:514–536`) classifies a non-registry value as `per-snapshot`. A per-snapshot origin is checked only when its source kind lacks a registry key. The `ebl-cohort` path can therefore swap its fallback for an invented grant: the label `ebl-cohort` is registered, so nothing compares the grant with anything.
- Source labels resolved to `'*'` (computed or caller-supplied) are removed before the rights and runtime-coverage checks (`:1064`, `:1087`). A new import path with a computed kind and an inline rights literal passes.
- Per-snapshot statements (`cdli_api.RIGHTS`, the ORACC literal at `oracc.py:137`) are not fingerprinted. AGENTS.md lists them as a manual sync trigger, so this last point is documented behaviour, not a silent bug.

Today's four resolved paths are correct: `import_source` uses `RIGHTS[source]` (fails closed with `KeyError` on unknown kinds), `ebl-cohort` uses the cohort rights or falls back to `RIGHTS['ebl']`, and ORACC and CDLI use declared per-snapshot statements. The real manifests carry `unresolved-conflict`, `source-stated` and `source-stated-terms`, which match the atlas notes.

**Fix:**
1. Apply R2's escape analysis to `RIGHTS`.
2. Any non-registry rights origin, including a fallback whose value is not a registry lookup, must be declared under `rights_sources.<kind>`, even for registered kinds.
3. A path whose source label is `'*'` must use exactly `RIGHTS[source]`; anything else is an error.
4. Store `statement_sha256` (a hash of `ast.dump` of the rights expression) in each `rights_sources` entry and fail on change.
5. At `--runtime`, compare each cited snapshot's `rights.status` with the status the atlas declares for that source.

### R5 — P2 — The baseline commit and run commits are never resolved or compared with the checked code

`current()` and `support()` (`:687–696`, `:816–818`) compare strings by prefix. A one-character `code_ref` matches. A nonexistent `baseline_commit` passes. Nothing checks that the code being checked equals the baseline code. When `44ddaeb1` commits a change that does not alter the contract, the checker will still print OK, and `verified: unit/disk` will rest on `d6049e2` runs against code that has changed. That conflicts with "no claim of final completion if the backend drifts".

**Fix:** resolve `baseline_commit` and every `code_ref` with `git -C <real_root> rev-parse --verify <x>^{commit}`, and require at least 7 hex characters. Then run `git diff --quiet <baseline> <checked ref> -- cuneiform tests fixtures sources`, using HEAD plus a dirty-tree check in live mode. If the code differs, report an error for every `verified` ≥ `unit` entry ("baseline stale: code changed since `<baseline>`"), or render it `STALE`, until the runs are redone and the baseline moves.

### R6 — P3 — A `DONE` block accepts a hex task ID as its commit SHA (reproduced)

`SHA_TOKEN` (`:61`) accepts any backticked 7–40 hex token. `git cat-file -t` on `8d17b311`, `64821742`, `44ddaeb1` and `b13b7efc` gives "Not a valid object name". The mutation that marks Q-019 `DONE` citing only `8d17b311` passes.

**Proposed precise check** (prototype: `scratch/review-q019/scripts/done_sha_proto.py`; not applied):

```python
def commit_of(repo, token, head='HEAD'):
    r = subprocess.run(['git', '-C', str(repo), 'rev-parse', '--verify', '--quiet', f'{token}^{{commit}}'],
                       capture_output=True, text=True)
    if r.returncode:                      # unknown, ambiguous, or a tree/blob
        return None
    sha = r.stdout.strip()
    if subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', sha, head]).returncode:
        return None                       # a commit, but not in the checked history
    return sha
# DONE requires any(commit_of(real_root, t, ref) for t in SHA_TOKEN tokens in the block)
```

Use `real_root`, because `--git-ref` and self-test copies have no `.git`, and use the `--git-ref` value as `head`. If git is unavailable, fail closed. On the current QUEUE.md the prototype reports no false failures. It rejects the task-ID mutation, unknown hex, and a tree ID (`expected commit type, but the object dereferences to tree type`). Add a self-test case that cites only a task ID.

### R7 — P3 — `read_back` and `corpus_evidence.observer` are honour-system

Flipping the claimant's disk run to `read_back: true` passes, and so does an observer that says "reported, not read back". AGENTS.md says only the parent or the observing worker sets `read_back: true`. This is a documented, enforced-by-process rule and is acceptable. **Suggestion:** give `corpus_evidence` a `read_back` boolean and render unconfirmed evidence as UNVERIFIED, the same way runs are rendered.

### R8 — P3 — Some self-tests break on legitimate atlas evolution

I lowered the four `verified: disk` entries to `unit` (a valid atlas: `check` is OK). The self-test then fails "verified=disk without a named run" with `StopIteration` and reports 32/33. It reports FAIL rather than crashing, which F6 required. The two schema-only-table cases will fail the same way once `composition` and `passage` are implemented. **Fix:** when a case's target is absent, add a synthetic target to the copy (a temporary disk entry or schema-only table), or report `SKIP (precondition absent)`. A legitimate state should not fail the self-test. The ten analyzer cases are already independent of the real code, which is the right pattern.

### R9 — P3 — Temporal facets describe superseded shapes

`facet:cdli-temporal-fields` lists CSV headers from three retained rows. `facet:ebl-temporal-fields` describes one record. The persisted CDLI JSON has a `period` object (`name`, `period`, `time_range`, `sequence`) and `dates`. eBL records carry `datesInText`. This is harmless now (`implemented: none`), but Q-015 should be scoped against the JSON shapes. Documentation only.

### R10 — P2 — `artifact:publication-ledger` states a guarantee the Q-005 review disproved

The summary says: "An ID that was ever published can never be published again, even after deletion." The entry is `verified: disk`, rendered `disk (UNVERIFIED)`. Q-005 B1 reproduced a crash window after which the same ID republishes with different bytes. B2 found that reads never consult the ledger. B3 found that failed-publish cleanup raises `PermissionError`. The tests behind the disk level do not exercise those paths. The atlas was committed before the Q-005 file appeared, so this is timing, not dishonesty. It is still a false statement in the canonical model. **Fix (atlas owner, at the next sync):** call it the intended guarantee, cite Q-005 B1–B3 as open at `d6049e2`, and keep it until the `44ddaeb1` fixes are independently re-checked.

## Harmless documentation (no action needed for correctness)

- The `snapshot_contract` absence on the five legacy manifests is disclosed in the field note.
- `runtime_unexercised` reasons for `cdli-selection`, `ebl-atf` and `oracc` are accurate. `oracc` is refused by `adapters.ingest`.
- The `interface:ui` and `service:falkordb-projection` wording was honest for `567ea14`. It is now stale because the sibling is at `ca4b514`, where the parent reports the Browser on `:23001` is disabled (S3).

## Synchronization requirements (current)

- **S1 — backend drift (`44ddaeb1`, uncommitted).** At 10:34Z the live checker reported 4 errors: `artifact:publication-ledger` symbol `cuneiform/storage.py::LEDGER` not found; `edge:HAS_SENSE` qualification `[]` vs code `['attribution']`; `edge:IN_SENSE` qualification `['basis']` vs code `['basis','inst','payload_pointer','sig']`; `storage.verify()` no longer has a literal `required = {...}` (unsupported static analysis, fail closed, which is correct). The checker cannot see the changed CLI verbs (`cli.py` +56 lines) or new ledger read checks. Check them by hand. After `44ddaeb1` commits: update the atlas (including R10), add a `verification_runs` entry at the new commit, move `baseline_commit`, and re-run `check`, `--runtime` and `--self-test` at that commit. Until then the atlas describes `d6049e2` only. With R5 unfixed, the checker will not notice a contract-neutral code change on its own.
- **S2 — snapshots.** Unreviewed fix code has already published to the real store: `snapshot:5e51403b…` (ORACC ccpo selection, `manifest-3`, ledger format 2) at 10:36:22Z. It is a new ID, which the rules allow, but it is not evidence until Q-020 accepts the code that wrote it. Do not cite it as `corpus_evidence` before then. Readers of the ledger (the UI, the checker's R1 fix) must accept both the legacy rows and the `reserve`/`commit` rows. New backend code mints `manifest-3` IDs. Any rebuilt or re-imported snapshot gets a new ID and must be cited as new `corpus_evidence`. Existing IDs must never be rebuilt. The three cited snapshots remain valid evidence for `d6049e2` only.
- **S3 — UI sibling at `ca4b514`.** Update `interface:ui.external.commit` and the observed wording (the Browser on `:23001` and freeform Cypher are disabled per the parent), and update `service:falkordb-projection` and Q-009. Keep `verified: none` until the UI re-review accepts it. The integration is pinned to `d6049e2`; a pin upgrade follows `44ddaeb1`.
- **S4 — verification runs.** If the parent accepts the Q-005 reviewer's disk run (`d6049e2`, 43 OK, 16.007s) as independent, record it as its own run with that observer. Do not flip the claimant's run to `read_back: true`. That run would lift the `d6049e2` disk labels only, and S1 supersedes it once the baseline moves.
- **S5 — checker fixes.** R1–R6 change only `scripts/check_model_atlas.py` (Q-018 ownership), plus R4.4 `statement_sha256` fields in the atlas. Make them after `44ddaeb1` lands, or verify with `--git-ref HEAD`, so the backend fixer's tree is not disturbed. Re-run my `mutations.py` against the result; every row marked "passed" except R7's should then be caught.

## Dispositions requested

| ID | Sev | Proposed owner | Blocks |
|---|---|---|---|
| R1 | P2 | Checker owner (Q-018 successor) | Any new `corpus` claim after the next sync |
| R2, R3 | P2 | Checker owner | Trusting manifest-key OK after the backend change |
| R4 | P2 | Checker owner + atlas | Trusting rights OK after the backend change |
| R5 | P2 | Checker owner | Treating checker OK as proof that `verified` labels apply to new code |
| R10 | P2 | Atlas owner at S1 | Nothing in code; the canonical model must not overstate immutability |
| R6 | P3 | Checker owner | None (process rule covers it meanwhile) |
| R7, R8, R9 | P3 | Checker / Q-015 owner | None |

## Reproduce

```sh
cd /Users/danieliser/Projects/Fun/cuneiform-research
S=~/.local/share/cuneiform-research/scratch/review-q019
PY=~/.local/share/cuneiform-research/venv/bin/python
python3 scripts/check_model_atlas.py --git-ref d6049e2
$PY -B scripts/check_model_atlas.py --git-ref d6049e2 --runtime
python3 scripts/check_model_atlas.py --self-test --git-ref d6049e2
python3 -I $S/scripts/fingerprint.py $S/fingerprint-check.json          # compare with fingerprint-before.json
$PY -I $S/scripts/count_claims.py $PWD $S                               # reads copies in $S/copies only
$PY -I $S/scripts/mutations.py $S                                       # scratch copies under $S only
python3 -I $S/scripts/done_sha_proto.py $PWD QUEUE.md
```
