# Publication protocol (ledger format 2)

Code: `cuneiform/publication.py`, used by `storage.publish` (snapshots, `<root>/snapshots`) and `corpus.build_cohort` (cohorts, `<root>/derived/cohorts`). Introduced 2026-11-03 to fix review blockers B1–B3 in `reviews/corpus-pilot-review-v0.1.md`. Store reads, cohort reads and the reserve→commit wait were tightened for `reviews/corpus-pilot-review-v0.2.md` R1–R5 ([disposition](CORPUS-REVIEW-v0.2-DISPOSITION.md)).

## Write order

All ledger appends run under an exclusive `flock` on `<folder>/.publication.lock`. A per-ID build lock (`<folder>/.locks/<id>.lock`) is held for the whole build, from the first decision through `commit`. Snapshots and cohorts both use it, and so does `publication-recover`. Lock order is always build lock, then ledger lock. Concurrent writers of one ID build it once: the others wait and then reuse the published result. A writer whose pre-check finds `reserved` waits for that build lock and decides again, so a live writer's reserve→commit window is never mistaken for an interruption. Only a reservation that no live process holds is refused.

1. Build a complete `.pending-<uuid>` stage. Seal it read-only (files 0444, directories 0555) and `fsync` every file and directory after its final mode change, so contents and modes are both flushed. A stage containing a symlink is refused.
2. Append `reserve` with `manifest_sha256`, `manifest_file_sha256` (the SHA-256 of the `manifest.json` bytes), the stage name and the writer pid/host. `fsync` it, plus `F_FULLFSYNC` on macOS, which also acts as a barrier for step 1.
3. `rename(stage, dest)`, then `fsync` the folder.
4. Append `commit` and `fsync` it.

If the rename raises while the stage is still present and `dest` is absent, the writer appends `abort`. POSIX rename is atomic, so nothing became visible. The ID is free again, and the history stays in the ledger.

## States per ID

| State | How | Readers | Writers |
|---|---|---|---|
| unpublished | no record | refuse a directory in a store (`not-in-ledger`) | may build; refuse an existing unrecorded directory (`unledgered`) |
| reserved | `reserve`, no `commit` | refuse (`reserved`) | wait for the build lock; reuse if the live writer committed, else refuse (`reserved but never committed`) |
| published | `commit`, `adopt`, or a legacy record | serve only if the manifest equals the record (and the file bytes, where recorded) | reuse if the directory matches; refuse if missing (`restore the exact published bytes`) |
| aborted | `abort` after `reserve` | — | may build again |
| abandoned | `abandon` | refuse | refuse permanently (`burned`) |
| conflict | an impossible sequence | refuse | refuse |

Legacy records have no `event` key. They are the d6049e2 publisher's entries and the 2026-11-03 backfill of the five pilot snapshots, and they mean "published". Backfilled entries are served as `ledgered-legacy-backfilled`. Their `published_at` is the manifest build time copied by the backfill, not an observed publication time. The two same-ID-rebuild incident IDs carry `incident`. Historical entries are never rewritten.

## Explicit recovery (nothing is automatic)

Every verb takes `--store snapshots` (the default, `<root>/snapshots`) or `--store cohorts` (`<root>/derived/cohorts`, IDs `cohort:<32 hex>`). Cohort recovery uses the same machinery with the cohort ledger. Its content check verifies the cohort manifest, the payload and every member slice, requires the manifest's `cohort_id` to equal the requested ID, and compares the slices with the receipt-bound parent raw object when that object is present under `<root>/raw`.

```sh
python -m cuneiform publication-status [SID]                    # read-only: states, open reservations, leftover stages, symlinked entries
python -m cuneiform publication-recover SID                     # read-only plan: what is safe
python -m cuneiform publication-recover SID --action commit   --reason ...   # directory present and equal to the reservation
python -m cuneiform publication-recover SID --action complete --reason ...   # directory absent, reserved stage intact: rename it, commit
python -m cuneiform publication-recover SID --action discard  --reason ...   # directory absent, reserved stage intact: abort, remove stage
python -m cuneiform publication-recover SID --action abandon  --reason ...   # directory and stage both gone: burn the ID
python -m cuneiform publication-adopt SID --reason ...          # ledger an existing unrecorded directory (history unknown)
python -m cuneiform publication-repair-ledger --reason ...      # acknowledge a torn final record, append-only
python -m cuneiform publication-clean-stage .pending-...        # remove one named stage that no reservation names
python -m cuneiform publication-recover COHORT_ID --store cohorts --action commit --reason ...   # same, for an interrupted cohort
```

Recovery commits only the reserved bytes. A directory that differs from the reservation, or that is (or contains) a symlink, offers no action, and you must move it aside first. Recovery never changes the bytes or modes of the directory it commits. Adoption refuses a symlinked entry, an entry containing symlinks, and an entry whose manifest identity differs from the requested ID. If neither the directory nor the stage survives, the ID may have been visible and then deleted, so `abandon` is the only option. A torn final ledger record is tolerated by readers, because it is either an append in progress or a crash. Writers refuse to append after it until it has been acknowledged. The torn bytes stay in the file as evidence. An unparseable line in the middle of the ledger refuses every decision.

If cleaning up a failed build fails, the original exception is re-raised with a note, and `<folder>/.recovery/<stage>.json` records the stage, both errors and the command to run next. A stage named by an open reservation is kept for recovery.

## Reads and relocation

- **Store membership** (`publication.locate_entry`): a directory is in a store when its *lexical* parent or its *resolved* parent holds a ledger or lock. A lexical store entry must be a real directory that resolves to `<store>/<name>`. A symlinked entry, or a path that escapes through a symlinked component or `..`, is refused (`symlinked-entry`) before any hashing. A path outside a store that resolves into a store entry is ledger-checked against that store. A whole store reached through a symlinked folder (for example, a store moved to another volume) is still ledger-checked.
- **In a store:** the entry name must equal the manifest ID (`misplaced` otherwise). No payload file, nor any directory on the way to one, may be a symlink. The ledger must exist (a lock with no ledger refuses with `not-in-ledger`). The manifest must equal the ledger's published record.
- `storage.verify(path)` / `verified(path)` in `auto` mode: a store entry is always ledger-checked. A copy outside every store verifies its content only, and `verified(path)['publication']` labels it `standalone-not-ledger-checked`.
- **CLI and API store reads.** `store_path(config, sid)` and `resolve_snapshot(config, sid)` return a `StoreEntry`. Every read of a `StoreEntry` (`manifest`, `scope`, `lookup`, `query`, `parity`, `trace`, `trace-word`, `export-graph`, `catalog-link`, `cdli-import --from-snapshot`, `oracc-import --texts-from-snapshot`) runs with `ledger='require'` and `expected_sid=<sid>`. A store entry therefore can never be served with the standalone label or as another ID. Each call still hashes the snapshot once.
- **Absent entries:** a store read of a missing entry raises a `PublicationError` whose `.state` is `reserved`, `published-missing`, `abandoned`, `conflict` or `not-found`. Outside a store, a missing path is still a `FileNotFoundError`.
- **Cohorts:** `corpus.verify_cohort(dir, parent, ledger=...)` applies the same rules with the cohort ledger. `corpus-audit` and `corpus-import` read with `ledger='store'`. In a ledgered cohort store, a reserved, aborted, abandoned, conflicting, unrecorded, misplaced or symlinked cohort is refused with the exact recovery command, and nothing is built from it. A cohort store that has neither a ledger nor a lock (the three cohorts that predate the cohort ledger) is labelled `unledgered-pre-ledger-cohort-store`; `ledger='require'` refuses it. Once any new cohort is built in such a store, its ledger exists, and the older cohorts are refused until they are adopted explicitly with `publication-adopt <id> --store cohorts`.
- To put a relocated copy into a store, copy the real files in and adopt them explicitly. Do not symlink. A restored copy is served only if it equals the published record.

## Limits

This is an application-level protocol for cooperating writers on one host. The same owner can still `chmod`, rename, edit or delete files and the ledger, and root can do anything. Read-only modes are not immutable flags. The ledger records what writers observed; it is not a signature. A deleted ledger makes a store look empty to the writer side. Readers that go through `store_path`/`resolve_snapshot` refuse a store without a ledger, and a folder that still has its lock refuses every read. A path-based `auto` read that finds neither a ledger nor a lock, beside the path or beside its resolved path, treats the directory as a standalone copy and labels it so. Symlink checks run at read time, so an entry swapped for a link after a successful read is caught on the next read, not retroactively. Payload files use `fsync`; the ledger also uses `F_FULLFSYNC`. Format-1 (legacy) entries bind the canonical manifest digest only, not the `manifest.json` file bytes.
