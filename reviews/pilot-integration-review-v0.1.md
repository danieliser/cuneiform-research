# Pilot integration review v0.1: UI `f68f340` on accepted backend `63f4221`

- **Reviewed:** sibling `cuneiform-ui` commit `f68f340` ("Re-pin to accepted backend 63f4221; …"), served live on `http://127.0.0.1:8740/`, against backend `63f4221` (accepted for the local cooperating-writer pilot by `reviews/corpus-pilot-review-v0.3.md`). Research checkout at `e124672` (atlas revision 4, baseline `63f4221`).
- **Reviewer:** an independent review sub-agent, not the UI writer (task 1359e965 and its predecessors) and not the backend or atlas workers. Date: 2026-11-03.
- **Scope:** a targeted integration check that closes Q-008 and the Q-006 follow-ups (N-1 to N-7 and the re-pin) for the local pilot. This is not a new broad audit. The UI review v0.2 (`../cuneiform-ui/reviews/ui-review-v0.2.md`, committed in `f68f340`) and the backend review v0.3 were read and not repeated.
- **Writes:** this file and `QUEUE.md` only. No backend, UI, atlas, checker or test edits. No generated-doc regeneration (the parent moved that to the checker worker). No delegation, downloads, outbound probes or shared services. `reviews/atlas-recheck-v0.2.md` (task 11ea0527) was read and not staged or changed.
- **Scratch:** `~/Projects/skill-workspaces/cuneiform-pilot-integration/v0.1/`: `fp.py`, `backend_check.py`, `live_http.py`, outputs `fp-before.json`, `fp-after.json`, `status.json`, `backend-check.json`, `backend-trace.json`, `live-http.json`, `ui-test.log`, `browser-coverage.png`.
- **Real store:** read only. Fingerprint of `snapshots/` (with the ledger), `derived/cohorts`, `derived/exports`, `receipts`, `raw` and `trust` (path, size, mtime, mode, SHA-256): **327 entries, digest `43d88967…`, identical before and after** every check below, including the UI test run and the browser session. This covers more paths than the UI writer's 262-entry fingerprint, so the two counts are not comparable.

## 1. Decision

**Accept the UI ↔ backend integration for the local pilot.** I found no blocking regression. Every check below was run by me, either against the pinned backend directly or against the live server, and the two agree.

This accepts a local, read-only pilot on one host. It does not mean the full SPEC is done. Images, the full corpus, MCP, temporal implementation and source rights stay open (§8).

## 2. Pin and live version

| Check | Result |
|---|---|
| `bin/cuneiform-ui status` | UI running (pid 21857) on `http://127.0.0.1:8740/`; FalkorDB on the internal network with no ports; relay on `redis://127.0.0.1:26380` with ACL auth required; Browser 23001 disabled; backend source `~/.local/share/cuneiform-ui/backend-pin/63f42216243141f4b10cdfd3d7ddd514c85b63d7` |
| Pin export vs `git archive 63f4221 cuneiform fixtures pyproject.toml` | SHA-256 of all 22 code files identical (`diff` empty). Every file and directory is read-only (no `u+w` bit). |
| `bin/cuneiform-ui` `PIN_COMMIT`, `server/bridge.py` `TESTED_COMMITS` | both `63f42216243141f4b10cdfd3d7ddd514c85b63d7`; `git rev-parse 63f4221` in this repo gives the same SHA |
| Live `/api/status` `backend` | commit `63f42216…`, compatibility `tested`, problems `[]` |
| UI checkout | `git status` clean at `f68f340` |

## 3. Six snapshots: live server vs backend

For each ID, I called `storage.verified(storage.store_path(cfg, sid), ledger='require')` from the pinned export, on its own and outside the UI, and compared it with the live `/api/status`.

| Snapshot | Live status | Live publication | Backend `manifest_sha256` = live version | Backend source / adapter |
|---|---|---|---|---|
| `ce127437…` (cohort 30) | ready | legacy-incident (backend `ledgered-legacy-backfilled`) | yes (`54ee6523…`) | ebl-cohort |
| `84971360…` (cohort 300) | ready | legacy-incident (backend `ledgered-legacy-backfilled`) | yes (`5f5bbeaa…`) | ebl-cohort |
| `c316e7cb…` (cohort 51) | ready | ledgered-legacy-backfilled | yes (`075f6140…`) | ebl-cohort |
| `fc7c3504…` (CDLI 51) | ready | ledgered-legacy-backfilled | yes (`49ee7411…`) | cdli-selection, `cdli-artifact-json-1` |
| `edaab55c…` (ORACC 51) | ready, superseded for sense provenance | ledgered-legacy-backfilled | yes (`be6b46f4…`) | oracc-selection, `oracc-cdl-1` |
| `5e51403b…` (ORACC 51) | ready | ledgered (manifest file bytes bound) | yes (`48bdc39e…`) | oracc-selection, `oracc-cdl-2` |

The live ledger shows 7 records, no torn tail, not corrupt, and all six IDs `published`. The two incident IDs carry the incident note, which says the first-version bytes were not retained. The UI does not hide it.

## 4. ORACC: new `5e51403b` vs superseded `edaab55c`

Read directly from each snapshot's DuckDB, opened read-only after `verified(..., ledger='require')`:

| | `5e51403b…` (`oracc-cdl-2`) | `edaab55c…` (`oracc-cdl-1`) |
|---|---|---|
| Word tokens / Sense rows | 6,888 / 1,317 | 6,888 / 1,317 |
| `edge:IN_SENSE` links | 4,544 | 4,544 |
| `IN_SENSE` links carrying the word's own `sig` | **4,508** (36 have none in the source) | **0** |
| `IN_SENSE` sig ≠ the same word's `LEMMATIZED_AS` sig | 0 | 0 (none to compare) |
| `oracc.trace_word` parent | `verified`; ZIP `c728b1f6…`, member `ccpo/corpusjson/P393722.json` | `verified`; same ZIP, member `ccpo/corpusjson/P348643.json` |

The counts match the UI writer's CHECKPOINT figures and the backend v0.2/v0.3 reviews.

Live UI, for the same words:

- `/api/word` on `5e51403b…` returns the word's own `IN_SENSE` qualification: `sig` `@ccpo%akk-x-stdbab:AN.TA=eliš[above//above]AV'AV$eliš`, plus `inst` and `payload_pointer`. It also returns the parent trace `verified` and the gloss label "lexical sense label, not a translation".
- `/api/status` gives `edaab55c…` the field `superseded = {by: snapshot:5e51403b…, by_status: ready, for: sense provenance, by_adapter: oracc-cdl-2}`, and gives `5e51403b…` the matching `supersedes`. The picker shows "oracc-cdl-1 · edaab55c1a39 — superseded for sense provenance". Both stay listed and served, as v0.3 §11 requires.
- The match rule (`bridge._mark_supersession`) pairs the two snapshots only when the cdl-1 and cdl-2 selections have the same inputs. Here that holds: same receipt `receipt:0ca4ede9…` and the same 51 texts.

## 5. Cohort 300 `ABZ480 ABZ13`: query, original source trace, coverage, refresh

**Backend direct** (`persisted.parity(store_path(...84971360…), ['ABZ480','ABZ13'], 'signs')`): graph 201, array 201, index 201, parity true, 38 witnesses / 38 artifacts, denominators 48,597 represented positions and 300 sequences. Scope: `rule-selected cohort`, `cohort:4e86952e…`, size 300, `rights_status` unresolved-conflict.

**Live HTTP** (`POST /api/query`):

- Index engine: count 201, parity `{index 201, graph 201, ok}`, 25 rows. The scope note says the counts are within a 300-record cohort and "not corpus frequencies". End-to-end time was 209.9 ms.
- Graph engine: count 201, `materialized_cap_reached` true, retrievable 100.
- Offset 200 returns 1 row with `truncated` false.
- A stale version gets **409**. Arbitrary Cypher gets **403**. A foreign `Host` gets **421**, and a foreign `Origin` gets **403**.

**Original source trace.** I traced two occurrences and re-read each span myself from the raw parent object `raw/sha256/4e970d87…`, the eBL `fragments.json` with receipt `receipt:66b5c944…` and Zenodo URL `…/records/10018951/files/fragments.json/content`:

- Backend direct, `occurrence:e18a117a…` (BM.35491, parent pointer `/17499`): parent status `verified`. Bytes `[63353782, 63353788)` read `ABZ480`. The record range `[63353205, 63354974)` hashes to `a14ce482…`, the backend's `record_sha256`.
- Browser, first result row (YBC.4111, pointer `/17010`): "Parent object verified … absolute bytes [62293318, 62293324)". Those bytes read `ABZ480`, and the record range `[62291849, 62295828)` hashes to `a743de7e…`, the value the UI shows. The cohort payload round trip (UTF-8 bytes [735, 741) of field `signs`) is shown separately, and rights are shown as unresolved-conflict.

**Coverage paging.** `/api/coverage` returns `records 1–200 of 300`: 200 rows, next offset 200. Offset 200 returns `records 201–300 of 300`: 100 rows, no next page. The browser pager went 1–200 → 201–300 on the same dataset (`browser-coverage.png`).

**Refresh selection (N-1).** In the browser, with the 300-cohort selected and 25 result rows shown, I clicked **Refresh & re-verify** and sampled the page every second for 12 s. The dataset stayed `84971360…` and the rows stayed 25. "Re-verifying" showed only in the first second. No demo datasets appeared, and no STALE state occurred.

## 6. `ledger='require'` and fail-closed errors

**Code.** Every snapshot read in `server/bridge.py` uses one path: `storage.verified(storage.store_path(cfg, sid), ledger='require')`. This covers discovery (`_verify_and_publication`), every request (`_reverify_bytes`, before the read-only open) and the listing of ledger-only IDs (`_ledger_only`). Traces get the backend `StoreEntry`, so their own reads also run with `ledger='require'` and are bound to the ID.

Errors fail closed:

- A `ValueError` that carries a `PublicationError.state` retires the version with that typed state.
- A `ValueError` without a state is re-raised as a content failure.
- An `OSError` invalidates the version.
- A per-request refusal raises `VersionChanged`, which returns HTTP 409.
- A manifest digest that differs from the served version is refused.

This matches v0.3 §11, and it matches the Q-002 requirement on torn ledgers: only an unparseable unterminated final record is tolerated, an uncommitted reservation stays `reserved`, and an unparseable middle record refuses every ID.

**Hermetic tests.** The `LedgerFormatTest` and `SnapshotPathTest` cases build scratch research roots under the UI home. They publish fixtures with the real pinned backend (`storage.import_source` and `build_cohort`/`import_cohort`), then damage the scratch ledger or entry. They use no stand-in. The real store was untouched (fingerprint in the header). These cases passed in my run:

- `test_format2_snapshot_is_served_via_backend`
- `test_reserved_is_not_yet_available_without_backend_prose`
- `test_torn_commit_tail_fails_closed_and_is_reported`
- `test_unrelated_torn_tail_is_shown_on_served_snapshot`
- `test_corrupt_ledger_refuses_per_request_and_on_scan`
- `test_ledger_only_ids_are_typed`
- `test_symlinked_entries_and_id_mismatch_are_refused`
- `test_unledgered_snapshot_is_not_served`

## 7. Tests and isolation (run by me)

`bin/cuneiform-ui test` at `f68f340` with the live pin: **24/24 isolation checks `ok`**, plus the "unprobed" line for host, internet and DNS reachability. No connection was attempted, and active probes were not used. Then **`Ran 42 tests in 143.783s` → `OK`, 0 skipped**, exit 0. Log: `ui-test.log`.

The test graphs live in the UI's own isolated FalkorDB (prefix `cuneiform_test_`, cleanup asserted). No shared service was used.

## 8. Non-blocking notes

- **P1, test guard.** `Roots.import_fixture` and the cohort helpers call `skipTest` if the backend refuses the scratch import (for example, below the free-space reserve). A low-disk run would then report the fail-closed ledger tests as skipped, not failed. My run had 0 skipped, so the evidence stands. The acceptance rule should stay "42 OK, 0 skipped".
- **Legacy incident IDs.** `ce127437…` and `84971360…` are served with the incident banner. Their first-version bytes are lost, so results produced from those IDs before the rebuild cannot be reproduced. Superseding them with new `manifest-3` IDs is the parent's decision. It is not needed for the pilot.
- **FalkorDB.** `5e51403b…` has no projection yet. The two demo graphs are in the old format ("rebuild required"). The UI's FalkorDB stays a separate consumer: it is not `service:falkordb-projection`, and nothing here implements Q-009.
- **Cohort store.** The UI reads no cohort store, so v0.3 N2 (`ledger='store'` for cohort reads) does not apply to it. The three pre-ledger cohorts still need the parent's explicit adoption before any new cohort build.

## 9. Atlas changes requested (for the checker worker; not made here)

The parent reserved atlas edits and regeneration for the checker worker's handoff. Requested changes:

- `interface:ui`: cite `../cuneiform-ui` at `f68f340` with the pin `63f4221`.
  - `observed`: the live `8740` server, pin export byte-identical to `63f4221`, 6/6 snapshots ready with versions equal to the backend's, and the §4/§5 figures.
  - `review`: this file.
  - Summary: "local read-only pilot accepted against `63f4221`; not end-to-end SPEC".
  - Remove the "polish not yet re-reviewed" and "integration pending" wording.
  - `verified` may go no higher than what the checker's rules allow for a sibling run. The 42/0-skipped UI suite and the 24 isolation checks were run by this reviewer and can be recorded with `read_back: true`.
- `service:falkordb-projection`: replace `ca4b514` and the ":23001 Browser" wording with `f68f340`. The Browser stays disabled. The UI instance is a separate consumer, and Q-009 is still open.

## 10. Still open

Images, regions, OCR and embeddings (Q-016), full-corpus import, the planned FalkorDB projection (Q-009), MCP (Q-010), temporal implementation (Q-015), hypothesis bounds (Q-017), source rights (eBL unresolved-conflict; ORACC CC0 as stated by the source, not legally reviewed; CDLI terms), the legacy-incident IDs and cohort adoption above. The atlas checker blocker Q-021 R3 (`reviews/atlas-recheck-v0.2.md`) is separate and stays open.
