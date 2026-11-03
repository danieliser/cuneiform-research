# Independent atlas review v0.1 (Q-004)

Reviewed on 2026-11-03. The reviewer is not the Q-003 builder. The review covers the uncommitted Q-003 files (atlas task `8d17b311`): `docs/model-atlas.json`, `docs/MODEL-ATLAS.md`, `docs/model-atlas.html`, `QUEUE.md`, `scripts/check_model_atlas.py`, `AGENTS.md` and `CLAUDE.md`. They were compared with committed code at baseline `2ab620b` (HEAD) and with the live working tree, where corpus task `64821742` is still editing backend files.

Only this file and factual status lines in `QUEUE.md` were written. I made no atlas, backend or UI edits, started no agents, and did not stage or commit anything. There were no downloads, installs, disk tests or shared-service changes. Runtime checks used in-memory DuckDB through the project venv and read the retained samples without changing them.

## Verdict

The workflow and checker are sound at the baseline and safe to adopt. Six things need fixing before or during the Q-007 sync. Two are checker blind spots that would let a careless sync remove true manifest keys (F1) or miss new rights namespaces (F2). The others are a status claim nobody observed (F5), self-test cases that break when the sync lands (F6), stale UI and FalkorDB statements (F7), and one gap in the temporal model that could add false precision (F8). The temporal proposal also gates routine decisions on the user without need (F9).

## Evidence

| Command | Result |
|---|---|
| `python3 scripts/check_model_atlas.py --git-ref HEAD` | `model atlas: OK`, exit 0 |
| `venv/bin/python -B scripts/check_model_atlas.py --git-ref HEAD --runtime` | `model atlas: OK (runtime population checked)`, exit 0; samples were found, e.g. `view:portable_edge` 124 synthetic / 1458 sample |
| `python3 scripts/check_model_atlas.py --self-test` (defaults to HEAD) | 11/11 cases behaved as expected, exit 0 |
| `python3 scripts/check_model_atlas.py` (live tree) | 10 errors, 2 warnings, exit 1 (listed under "Live-tree drift") |
| `venv/bin/python -B scripts/check_model_atlas.py --runtime` (live tree) | The same 10 static errors. There were no runtime population mismatches, so the eBL and CDLI counts still match the atlas claims on the live code. |
| `git -C ../cuneiform-ui log --oneline -1` | `567ea14 Local read-only Cuneiform Workbench UI with isolated FalkorDB projection` |
| `curl 127.0.0.1:8740/` and `curl 127.0.0.1:23001/` | HTTP 200 for both |
| `grep` for external `src`/`href` in `docs/model-atlas.html` | none (the file is self-contained). I did not render it in a browser. |

Atlas shape: 101 entries. Populated: 63 `none`, 36 `sample`, 2 `synthetic`. Verified: 51 `none`, 48 `unit`, 2 `disk`. 15 entries are `proposed`.

## Findings

### F1 — P1 — Manifest-key check misreads a dict spread, so a naive sync would delete true keys

**Location:** `scripts/check_model_atlas.py:164–172`; live `cuneiform/storage.py:134` (`meta={...}`) and `:176` (`manifest={..., **meta, ...}`).

The checker collects only constant keys from dict literals assigned to `manifest`. The live code moved `namespace`, `source`, `source_url`, `record_id` and `rights` into a local `meta` dict and spreads it with `**meta`. The checker therefore reports these five keys as "extra" in the atlas, although every manifest still contains them (`verify()` at `storage.py:67` requires all five). If someone makes the checker pass by deleting those fields, the atlas becomes wrong. The conditional keys `cohort` (eBL cohort import) and `selection` (ORACC selection) are also invisible because they live in other `meta` dicts.

**Fix:** Resolve `**name` spreads against same-function `name = {...}` literals. Model `cohort` and `selection` as optional per-source keys (for example `"optional_for": "ebl-cohort"`). Alternatively, take the required set from the literal `required={...}` in `verify()`.

### F2 — P1 — Rights-namespace check passes when new namespaces are added

**Location:** `scripts/check_model_atlas.py:182` reads only the `RIGHTS = {...}` literal; live `cuneiform/adapters.py:15` adds `RIGHTS['ebl-cohort'] = RIGHTS['ebl']`. The cohort import also takes `cohort.get('rights')` (`storage.py`, cohort `meta`).

The live tree adds the rights namespace `ebl-cohort`, and an `oracc-selection` source exists in `verify()`, yet the rights check stays green. `concept:rights-ledger` lists only `ebl, ebl-atf, cdli, oracc`. Rights are invariant 7, so a silent pass here is worse than a noisy one.

**Fix:** Also collect `RIGHTS[<const>] = ...` subscript assignments. Check that every `source` string compared in `storage.verify()` has a rights entry or a declared per-snapshot rights source.

### F3 — P2 — Runtime population check never runs the new adapters

**Location:** `scripts/check_model_atlas.py:49–50` (`SYNTHETIC` and `SAMPLES` cover only `ebl` and `cdli`).

After the sync, `node:WordToken`, `node:Lemma`, `node:Sense` and `edge:IN_SENSE` will be `implemented: code`. The runtime check will see 0 rows for them, so the only claim it accepts is `populated: none`. That is honest, but no claim above `none` can ever be verified.

**Fix:** In Q-007, add the corpus worker's ORACC fixture, if one exists under `tests/` or `fixtures/`, to `SYNTHETIC` with its adapter kind. If there is none, keep `populated: none` and record why in `evidence_notes`.

### F4 — P2 — `populated: corpus` bypasses the check

**Location:** `scripts/check_model_atlas.py:508–509`.

A `corpus` claim produces only a warning, even when the entry has 0 synthetic and 0 sample rows. No entry claims `corpus` today. The corpus worker's output is the first thing likely to tempt one.

**Fix:** Make `corpus` require an evidence reference to a snapshot manifest or receipt (snapshot ID plus count), and fail when synthetic and sample rows are both 0 and that reference is missing.

### F5 — P2 — Two `verified: disk` claims were reported by the parent, not observed

**Location:** atlas entries `artifact:snapshot-manifest` and `temporal:system-time` (notes: "Disk level parent-reported"). The evidence is `tests/test_disk_delivery.py::test_snapshot_idempotence_relocation_parquet_and_tamper`, which was skipped in the atlas worker's in-memory run (QUEUE baseline line).

AGENTS.md says "Never raise a `populated` or `verified` status beyond what you observed" and "Statuses supplied by someone else stay marked `UNVERIFIED`". The atlas cannot express UNVERIFIED, so the claim reads as observed.

**Fix:** Lower both to `unit` where a unit test exists. Otherwise add a `verified_by` or `unverified: true` field that the renderer shows and the checker allows only alongside a note. Restore `disk` after someone runs the disk test under the storage guard and records the result.

### F6 — P2 — Self-test cases are tied to `lemma` staying schema-only and will break at Q-007

**Location:** `scripts/check_model_atlas.py:664–672`.

The cases "populated claim on schema-only table" and "undeclared write into schema-only table" anchor on `lemma` having `implemented: schema`. The live tree now writes `lemma`. After the sync, the first case raises `AssertionError` (anchor missing), so the self-test crashes rather than reporting FAIL. The second reports FAIL because the write is no longer undeclared. In the live tree, `composition` and `passage` are still schema-only. Also, `--self-test` always uses `HEAD` (`args.git_ref or 'HEAD'`), so it cannot test uncommitted code. That is fine, but the help text should say so.

**Fix:** Pick the target at run time (the first atlas table entry with `implemented: schema`) or retarget to `composition`. Catch anchor errors and report them as FAIL.

### F7 — P2 — UI and FalkorDB statements are stale

**Location:** atlas `interface:ui` ("Not read back: the path did not exist"; `modeled: proposed`, `implemented: none`); `service:falkordb-projection` ("Not installed or validated"); QUEUE Q-009 blocker ("Installing FalkorDB or running a container needs explicit user approval").

The sibling `cuneiform-ui` exists at commit `567ea14` and serves `127.0.0.1:8740`. Its commit message and the parent's notes describe an isolated FalkorDB projection (Browser on `:23001`, which answers HTTP 200). That is a running local FalkorDB instance in the sibling repo, independent of this repo's planned `contract:portable-graph-export`. The independent UI review (`bc133950`) is still running, so nothing about it is verified.

**Fix (Q-007, not now):** Change `interface:ui` to delivered in the sibling repo, keeping `verified: none` until `bc133950` reports. The checker resolves `files` under this repo only, so cite the sibling commit in `notes` or `evidence_notes`, not `files`. Update `service:falkordb-projection` and Q-009 to say whether the UI's projection replaces the planned one or is a separate consumer. Remove the "needs user approval" blocker if the parent confirms the UI work already covers it. I corrected only the queue status lines (see "Queue corrections").

### F8 — P2 — Temporal precision enum has no "as printed" or "unknown" value

**Location:** `value:TemporalExtent.fields.precision`, which allows `millennium | century | decade | year | month | day | period-label-only`.

For CDLI `Uruk III (ca. 3200-3000 BC)`, the parser must choose `century` or `year`. The source says neither. Round numbers do not prove century precision, and `year` claims too much. A forced choice adds precision that TD-2 forbids. Also, this range is CDLI's period gloss, printed identically on every row with that period. It is the catalog's chronology convention, not a dating of the object.

**Fix:** Add `as-printed` (or `unknown`) to `precision`. Treat it as the default for printed ranges. Set the DateClaim basis to something like `catalog-period-gloss`. Note under `value:source-independence` that repeated glosses are one assertion, not many corroborating ones. Everything else in TD-1 to TD-7 is consistent with "parsing never adds precision": the astronomical-year formula `1 − BC year` is correct, `ca.` does not widen, `ff.` gives an open end, sentinels are unknown, and there are no midpoints or default chronology.

### F9 — P2 — Q-014 requires a user decision for routine design defaults

**Location:** QUEUE Q-014 ("Parent / user decision"; "Until then nothing temporal may be implemented").

TD-1, TD-2, TD-5, TD-6 and TD-7 are ordinary engineering defaults. Each recommendation is the conservative option already implied by the atlas invariants. TD-3 and TD-4 recommend choosing nothing (no default chronology, no silent conversion), so they also need no user input now. A user decision is warranted only when someone proposes a default `node:ChronologyScheme` or a calendar-conversion authority, or wants to depart from a recommendation.

**Recommendation for the parent (I did not apply it, because it is a policy change rather than a factual correction):** Make Q-014 parent-owned and `READY`. Accept the recommended options after the F8 change. Record the escalation trigger above in the block. Allow Q-015 to proceed once Q-007 lands.

### F10 — P3 — Spooled projection writes always warn

The live `projections.py` writes `posting` and `ngram` through `Spool.detached('posting', ...)`, so the static check warns on every run. The runtime check confirms the counts, so this is noise rather than a gap. Teach `code_contract()` to treat `Spool.detached('<table>'` as a literal write.

### F11 — P3 — Queue rules on evidence are not checked by the script

`parse_queue` checks IDs, statuses, summary rows, dependencies and model IDs. It does not check that a `DONE` block contains a commit SHA, or that a status supplied by someone else carries `UNVERIFIED`. These rules are enforced only by documentation. That is acceptable, but `AGENTS.md` should not imply the checker enforces them.

## Agent workflow (AGENTS.md / CLAUDE.md)

The workflow is fit for use. `CLAUDE.md` is a one-line `@AGENTS.md` include, which matches the global convention. The single queue writer, one live session per checkout, `--git-ref HEAD` during another worker's uncommitted edits, commit-only shipping and the frozen-file list are all clear and match how this review had to run. One gap: AGENTS.md lists `cuneiform/schema.sql`, `model.py`, adapter writes, projections and manifest keys as sync triggers, but not new source kinds or rights namespaces (F2) or new `meta`/manifest construction paths (F1). Add "new source kinds, rights entries or snapshot import paths" to the trigger list.

## Live-tree drift (expected; corpus worker `64821742` still writing)

`python3 scripts/check_model_atlas.py` on the live tree:

- `node:WordToken`, `node:Lemma`, `node:Sense`: code writes `word_token`, `lemma`, `sense`; atlas says `implemented=schema`.
- `edge:HAS_WORD`, `edge:LEMMATIZED_AS`, `edge:HAS_SENSE`: code writes them; atlas says `implemented=schema`.
- `edge:HAS_WORD` qualification: atlas `['segmentation']`, code `['line_label','order']`.
- `edge:LEMMATIZED_AS` qualification: atlas `['attribution','status']`, code `['epos','guideword','inst','norm','sig']`.
- `EDGE_TYPES IN_SENSE` (`WordToken → Sense`, live `model.py:58–59`) has no atlas entry.
- `artifact:snapshot-manifest`: missing `build_timings` and `snapshot_payload_bytes`. The five "extra" keys are false (F1).
- Warnings: `table:posting` and `table:ngram` have no literal write (F10).

Untracked backend files in the live tree include `cuneiform/acquire.py`, `bulk.py`, `corpus.py`, `oracc.py`, `persisted.py` and `sources/`. Modified: `adapters.py`, `cli.py`, `model.py`, `projections.py`, `query.py`, `storage.py` and `tests/test_projections.py`. These belong to the corpus worker. This review neither edited nor read them in full.

## Sync requirements for Q-007 (do not apply while the corpus worker is writing)

1. Fix the checker first: F1 (spread-aware manifest keys plus optional per-source keys), F2 (subscript rights entries), F6 (self-test targets) and F10. Re-run `--self-test` and add one case each for F1 and F2.
2. Raise `node:WordToken`, `node:Lemma`, `node:Sense`, `edge:HAS_WORD`, `edge:LEMMATIZED_AS` and `edge:HAS_SENSE` to `implemented: code`. Set the qualification lists from the code. Keep `populated: none` unless a fixture exercised by `--runtime` shows rows (F3). Do not use `corpus` without receipt evidence (F4).
3. Add `edge:IN_SENSE` (`node:WordToken → node:Sense`, registry `model.EDGE_TYPES`), citing ORACC `f.sense` as the source assertion. Record it under Q-011.
4. Add `build_timings` and `snapshot_payload_bytes` to `artifact:snapshot-manifest`. Keep `namespace`, `source`, `source_url`, `record_id` and `rights`. Add `cohort` and `selection` as optional, source-specific keys.
5. Add `ebl-cohort` (and `oracc-selection` if it gets a `RIGHTS` entry) to `concept:rights-ledger.rights_keys`, with cohort rights inherited from `ebl` and therefore still unresolved.
6. Check whether the corpus worker added tables, views, CLI commands (`interface:cli` summary), query surfaces or projection configuration. The checker covers tables, views and edges, not CLI verbs or query functions.
7. Lower or annotate the two parent-reported `verified: disk` claims (F5).
8. Update `interface:ui` and `service:falkordb-projection` (F7). Add `precision: as-printed` and the gloss basis (F8).
9. Set `baseline_commit` to the Q-007 commit, bump `atlas_revision`, run `--write`, then `check` and `--runtime` with the venv. Run the unit suite and a secret scan. Record the SHA in Q-007.
10. Update the Q-011 scope or status if the ORACC adapter now exists. Note that `import_source` still refuses `oracc` ("disabled pending verified per-project contract", live `storage.py:130`), so the adapter must not be described as loaded data.

## Queue corrections made by this review

Only status facts were changed. Earlier text was kept, with new observations dated alongside it.

- Q-001: still `IN_PROGRESS` (UNVERIFIED for scope). Replaced the stale "working tree was still clean" sentence with the observed uncommitted backend changes and kept the original observation as history.
- Q-002: `IN_PROGRESS` → `IN_REVIEW`. Delivered at sibling commit `567ea14`, live on `:8740` and `:23001`, awaiting independent review `bc133950`. Not verified, not production.
- Q-003: owner thread now names atlas task `8d17b311` (completed, awaiting review). Status stays `IN_REVIEW`.
- Q-004: `TODO` → `IN_REVIEW`. This file was delivered uncommitted and awaits parent disposition.
- Q-006: `TODO` → `IN_PROGRESS`. Owner is UI review task `bc133950`.
