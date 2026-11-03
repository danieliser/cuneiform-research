# Publication protocol (ledger format 2)

Code: `cuneiform/publication.py`, used by `storage.publish` (snapshots, `<root>/snapshots`) and `corpus.build_cohort` (cohorts, `<root>/derived/cohorts`). Introduced 2026-11-03 to fix review blockers B1–B3 in `reviews/corpus-pilot-review-v0.1.md`.

## Write order

All ledger appends run under an exclusive `flock` on `<folder>/.publication.lock`. A per-ID build lock (`<folder>/.locks/<id>.lock`) makes concurrent writers of one ID build it once. The second writer waits, then reuses the published result (`reused: true, raced: true`).

1. Build a complete `.pending-<uuid>` stage. `fsync` every file and directory, then seal the stage read-only (files 0444, directories 0555).
2. Append `reserve` with `manifest_sha256`, `manifest_file_sha256` (the SHA-256 of the `manifest.json` bytes), the stage name and the writer pid/host. `fsync` it, plus `F_FULLFSYNC` on macOS, which also acts as a barrier for step 1.
3. `rename(stage, dest)`, then `fsync` the folder.
4. Append `commit` and `fsync` it.

If the rename raises while the stage is still present and `dest` is absent, the writer appends `abort`. POSIX rename is atomic, so nothing became visible. The ID is free again, and the history stays in the ledger.

## States per ID

| State | How | Readers | Writers |
|---|---|---|---|
| unpublished | no record | refuse a directory in a store (`not-in-ledger`) | may build; refuse an existing unrecorded directory (`unledgered`) |
| reserved | `reserve`, no `commit` | refuse (`not committed`) | refuse (`reserved but never committed`) |
| published | `commit`, `adopt`, or a legacy record | serve only if the manifest equals the record (and the file bytes, where recorded) | reuse if the directory matches; refuse if missing (`restore the exact published bytes`) |
| aborted | `abort` after `reserve` | — | may build again |
| abandoned | `abandon` | refuse | refuse permanently (`burned`) |
| conflict | an impossible sequence | refuse | refuse |

Legacy records have no `event` key. They are the d6049e2 publisher's entries and the 2026-11-03 backfill of the five pilot snapshots, and they mean "published". Backfilled entries are served as `ledgered-legacy-backfilled`. Their `published_at` is the manifest build time copied by the backfill, not an observed publication time. The two same-ID-rebuild incident IDs carry `incident`. Historical entries are never rewritten.

## Explicit recovery (nothing is automatic)

```sh
python -m cuneiform publication-status [SID]                    # read-only: states, open reservations, leftover stages
python -m cuneiform publication-recover SID                     # read-only plan: what is safe
python -m cuneiform publication-recover SID --action commit   --reason ...   # directory present and equal to the reservation
python -m cuneiform publication-recover SID --action complete --reason ...   # directory absent, reserved stage intact: rename it, commit
python -m cuneiform publication-recover SID --action discard  --reason ...   # directory absent, reserved stage intact: abort, remove stage
python -m cuneiform publication-recover SID --action abandon  --reason ...   # directory and stage both gone: burn the ID
python -m cuneiform publication-adopt SID --reason ...          # ledger an existing unrecorded directory (history unknown)
python -m cuneiform publication-repair-ledger --reason ...      # acknowledge a torn final record, append-only
python -m cuneiform publication-clean-stage .pending-...        # remove one named stage that no reservation names
```

Recovery commits only the reserved bytes. A directory that differs from the reservation offers no action, and you must move it aside first. If neither the directory nor the stage survives, the ID may have been visible and then deleted, so `abandon` is the only option. A torn final ledger record is tolerated by readers, because it is either an append in progress or a crash. Writers refuse to append after it until it has been acknowledged. The torn bytes stay in the file as evidence. An unparseable line in the middle of the ledger refuses every decision.

If cleaning up a failed build fails, the original exception is re-raised with a note, and `<folder>/.recovery/<stage>.json` records the stage, both errors and the command to run next. A stage named by an open reservation is kept for recovery.

## Reads and relocation

- `storage.verify(path)`: a directory beside a ledger (or lock) is in a store and is always ledger-checked. A copy anywhere else verifies its content only, and `storage.verified(path)['publication']` labels it `standalone-not-ledger-checked`.
- `storage.resolve_snapshot(config, sid)` requires the ledger. The CLI's read verbs use `store_path`, so the store must have a ledger, and each call hashes the snapshot once.
- To put a relocated copy into another store, adopt it explicitly. A restored copy is served only if it equals the published record.

## Limits

This is an application-level protocol for cooperating writers on one host. The same owner can still `chmod`, rename, edit or delete files and the ledger, and root can do anything. Read-only modes are not immutable flags. The ledger records what writers observed; it is not a signature. A deleted ledger makes a store look empty to the writer side. Readers that go through `store_path`/`resolve_snapshot` refuse a store without a ledger, but a path-based read that finds neither a ledger nor a lock treats the directory as a standalone copy. Payload files use `fsync`; the ledger also uses `F_FULLFSYNC`. Format-1 (legacy) entries bind the canonical manifest digest only, not the `manifest.json` file bytes.
