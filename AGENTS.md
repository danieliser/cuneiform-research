# Agent workflow — cuneiform-research

These rules apply to this repository. Global rules still apply.

## Before any edit

1. Read [QUEUE.md](QUEUE.md) and [docs/MODEL-ATLAS.md](docs/MODEL-ATLAS.md). Use [docs/model-atlas.html](docs/model-atlas.html) for a visual map. Read the [SPEC-v0.2](SPEC-v0.2.md) sections that your task touches.
2. Work on one queue task. Its block names the files and model IDs (for example `node:SignOccurrence`, `edge:NEXT`) that are in scope. If no task covers your work, ask the parent to add one. Do not widen scope silently.
3. Claim the task through the parent. The parent records the owner, thread and file list in QUEUE.md. QUEUE.md has one writer at a time, so do not edit another task's block. Only one live session may write to a checkout; use a git worktree for parallel work.

## While working

- In handoffs and commit messages, say which model IDs a change affects, for example `Model: node:Artifact, facet:artifact-metadata`.
- **Planned is not loaded.** Never describe a schema-only or proposed layer as data. An empty table means the layer is unavailable. Never raise a `populated` or `verified` status beyond what you observed.
- Never invent ancient dates, alignments, sign identities, rights grants or identity merges. The model rules are listed under "Invariants" in the atlas.
- Do not edit these files: `SPEC-v0.1.md`, `SPEC-v0.2.md`, `MULTIMODAL-MCP-ADDENDUM-v0.1.md`, and everything under `reviews/`. Add a new review file instead of changing an existing one.

## Keep the atlas in sync (only when the contract or coverage changes)

`docs/model-atlas.json` is the canonical model. The Markdown generated block and the HTML data block come from it.

Update the JSON in the same change if you alter any of these:

- `cuneiform/schema.sql`: tables, columns or views
- `cuneiform/model.py`: `NodeKind`, `EDGE_TYPES` or versions
- adapter writes: which tables or edges get rows, and edge qualification keys
- projection tables, revision or configuration
- manifest keys, manifest construction paths (`materialize` callers, `meta` dicts) or `storage.verify()` required keys
- rights namespaces, per-snapshot rights statements, or new source kinds and snapshot import paths
- CLI verbs, lookup recipes, trace outputs or export contracts (the checker does not see these, so check them by hand)
- what an exercised input actually populates, including new real snapshots cited as `corpus_evidence`
- test runs you rely on for a `verified` level: add a `verification_runs` entry with the observer, commit, command and result

Then run:

```sh
python3 scripts/check_model_atlas.py --write    # regenerate docs/MODEL-ATLAS.md block + HTML data
python3 scripts/check_model_atlas.py            # must print "model atlas: OK"
/Users/danieliser/.local/share/cuneiform-research/venv/bin/python -B scripts/check_model_atlas.py --runtime
```

- Refactors, tests and documentation that leave the contract and coverage unchanged need no atlas edit. The checker proves that.
- A QUEUE-only change needs no atlas edit. Run the checker anyway, because it validates queue IDs and references.
- While another worker has uncommitted code changes, add `--git-ref HEAD`. This checks committed code with your atlas and queue files overlaid on it.
- `--self-test` shows the checker catching deliberate mismatches in a temporary copy (`--git-ref WORKTREE` for uncommitted code).
- If the checker reports "unsupported static analysis", rewrite the code into a form it can resolve. Do not delete true keys or entries to make it pass. A `static_contracts` declaration is the last resort and must cite a test and the SHA-256 of the exact files.
- Never raise `populated` to `corpus` without `corpus_evidence` you read yourself (snapshot ID, table or edge kind, count). Unknown evidence is not success.
- A `verification_runs` entry reported by the implementer gets `read_back: false`, which renders as UNVERIFIED. Only the parent or a worker who ran it sets `read_back: true`.

## Evidence before done

- A task is `DONE` only with acceptance evidence: the exact command, its result and the commit SHA. Statuses supplied by someone else stay marked `UNVERIFIED` until read back. The checker enforces only that a `DONE` block contains a backticked commit SHA; the evidence and `UNVERIFIED` rules depend on you.
- Published snapshot IDs are permanent. Never delete and rebuild a published snapshot under the same ID; a revision gets a new ID (see `artifact:publication-ledger`).
- Record dependencies and blockers in the task block (`Depends on`, `Next step / blockers`). A blocked dependency blocks the task.
- Ship work by commit only. Do not commit while another worker is writing to git or the index. Hand the parent an exact list of owned files.
- Run tests with `/Users/danieliser/.local/share/cuneiform-research/venv/bin/python -B -m unittest discover -s tests`. Disk tests need `CUNEIFORM_RUN_DISK_TESTS=1` and admission under the storage guard. For this full-corpus runtime, also set `CUNEIFORM_TEST_MAX_TOTAL_GIB=41` (the authorized test budget); otherwise the default 5 GiB cap refuses admission.
- Do not download data, install dependencies or do image work unless the task explicitly authorizes it.
