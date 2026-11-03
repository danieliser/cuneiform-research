# Independent re-check of the Q-021 R3 fix (atlas-recheck-v0.2 B1, N2)

- **Reviewed:** commit `e53ab3a` (`scripts/check_model_atlas.py` signing-site analysis: `digest_origin()`, `mutator_writes()`, `written_after()`, `snapshot_manifests()`, and the 18 new analyzer self-tests). The backend `63f4221` and the local UI `f68f340` were already independently accepted (`reviews/corpus-pilot-review-v0.3.md`, `reviews/pilot-integration-review-v0.1.md`). I did not reopen them, and I did not repeat broad security or corpus audits.
- **Reviewer:** an independent review sub-agent. It did not build the R3 fix, the Q-021 repair or the Q-018 checker, and it did not write the Q-019 or v0.2 reports. Date: 2026-11-03.
- **Scope:** exactly what `reviews/atlas-recheck-v0.2.md` asked for after the B1 fix: the reviewer's `scripts/mut.py R3`, `--self-test`, and a moved-baseline check of the hidden forms and controls. I also checked a local name bound to a computed digest; the dict keyword, spread and `update` variants; copied-digest parameter controls in the `publish_dir` style; and the refusal of unsupported rebinding. N1 (atlas wording) is outside this scope. The atlas text was not re-read against the data.
- **Inputs read:** AGENTS.md, QUEUE.md (header, summary, Q-003, Q-018, Q-019, Q-021), `reviews/atlas-recheck-v0.2.md`, the "Addendum: atlas-recheck-v0.2" in `docs/ATLAS-RECHECK-v0.1-DISPOSITION.md`, the `e53ab3a` diff of the checker, `call_site_args()`, and the `manifest_sha256` writes in `cuneiform/*.py`. I also read the repair worker's scratch `INDEX.md`, `mut_r3.py` and `r3_moved.py`. I read its scripts, but I did not run them; my harness is my own.
- **Writes:** this file and the factual Q-003, Q-018, Q-019 and Q-021 closure in `QUEUE.md`. No checker, atlas, backend, test, UI or other review edits.
- **Scratch:** `~/.local/share/cuneiform-research/scratch/review-q021-r3/` (6.1 MiB). It holds `export/` (`git archive e53ab3a`), `clone/` (a local `git clone` of the checkout at `e53ab3a`; per-case scratch commits only, never pushed), `old_checker_e124672.py`, `scripts/` (`mut.py`, a copy of the v0.2 reviewer's harness with only `R`, `BASE` and `DR` repointed; `r3_moved_review.py`, my harness; `fingerprint.py`) and the outputs listed below. `mut.py` read the v0.2 reviewer's `review-q021/dr` data root for its baseline line only. No R3 case forges data.
- **Real store:** read only. Fingerprint (path, size, mtime, ctime, mode and SHA-256 under `snapshots/`): 172 entries, `6ba1c85c…`, byte-identical before and after.

## Verdict

**ACCEPT. R3 is closed for the bounded package checker.** With the baseline moved to each case's own commit, every hidden form I tried fails with a specific error and none reports staleness. That covers a local name, a keyword, a spread, `update`, `setdefault`, `setitem`, a parameter and a module name. Every rebinding form I tried is refused as `Unsupported`, never treated as a copy. The real `publish_dir` digest parameter, and two parameter controls built like it, still pass. The `e124672` checker passes all 31 of these failing cases, so the fix is what makes the difference. The remaining limits are listed below. None of them is an ordinary refactor of today's signing code, and they agree with the documented rule that a subscript or attribute read is a copy.

## Evidence (reviewer-observed)

| Command | Result |
|---|---|
| `python3 scripts/check_model_atlas.py --self-test` in the checkout (HEAD `e53ab3a`, clean) | 65/65, exit 0 (`selftest-checkout.out`) |
| same in a fresh local clone at `e53ab3a` | 65/65, exit 0 (`selftest-clone.out`) |
| same in the `git archive` export (no `.git`) | exits 1 at `git archive HEAD`: fails closed without a repository, as the disposition says |
| `python3 scripts/check_model_atlas.py --repo <checkout>` in the export | `model atlas: OK` (warning: `../cuneiform-ui` not beside the export) |
| `<venv>/python -B scripts/check_model_atlas.py --repo <checkout> --runtime` in the export (real store, read only) | `model atlas: OK (runtime population checked)`, 7.6 s |
| `<venv>/python -I scratch/review-q021-r3/scripts/mut.py R3` (v0.2 reviewer's cases on the `e53ab3a` export) | baseline `(0, [])`; **7/7 CAUGHT** on a specific rule (`mut-r3.out`). At `e124672` four of these passed |
| `python3 -I scratch/review-q021-r3/scripts/r3_moved_review.py` (my moved-baseline harness, 39 cases) | 19/19 forms CAUGHT, 12/12 unsupported forms CAUGHT with their specific message, 4/4 controls PASS-OK. Staleness errors in all 39 cases: 0. The `e124672` checker passes every one of the 31 failing cases (`r3-moved-review.out`) |
| same, `limit` cases only | 5 declared limits pass silently; one probe (`h.hexdigest()`) is caught, so it is not a limit (`r3-moved-limits.out`) |
| store fingerprint before and after | identical |
| `git status --porcelain` in the checkout before my edits | clean; HEAD `e53ab3a` |

I did not run the backend or UI suites. The code under `cuneiform/`, `tests/`, `fixtures/` and `sources/` is unchanged since `63f4221`, and `e53ab3a` changes only the checker, atlas, docs and queue.

## Moved-baseline harness

How each case runs: a fresh checkout of the clone at `e53ab3a`, then one code change, committed. `baseline_commit` and every `63f4221` run's `code_ref` are then rebound to that commit, and `--write` regenerates the docs. Both the `e53ab3a` checker and the `e124672` checker then run statically, with `--repo` set to the clone. A case counts as **CAUGHT** only on exit 1, with an error that contains the expected key or message and no staleness error.

### Hidden signing forms (expected: key drift that names the new key)

| Form, appended to `cuneiform/storage.py` | New checker | `e124672` |
|---|---|---|
| `d = digest(...)`; `body['manifest_sha256'] = d` (v0.2 B1 reproduction) | CAUGHT `r_k1` | passed |
| `d = digest(...)`; `dict(body, manifest_sha256=d)` | CAUGHT | passed |
| `d = digest(...)`; `{**body, 'manifest_sha256': d}` | CAUGHT | passed |
| `body.update(manifest_sha256=digest(...))` | CAUGHT | passed |
| `body.update(manifest_sha256=d)` | CAUGHT | passed |
| `body.update({'manifest_sha256': d})` | CAUGHT | passed |
| `body.update({'manifest_sha256': d, 'r_k7b': 1})`: the update's own key is reported too | CAUGHT (`r_c6`, `r_k7b`) | passed |
| `dict.update(body, manifest_sha256=d)` | CAUGHT | passed |
| `body.setdefault('manifest_sha256', d)` | CAUGHT | passed |
| `body.__setitem__('manifest_sha256', d)` | CAUGHT | passed |
| `operator.setitem(body, 'manifest_sha256', d)` | CAUGHT | passed |
| helper `_put(rec, x)` called with `digest(...)` | CAUGHT | passed |
| helper called with a local name bound to `digest(...)` | CAUGHT | passed |
| helper called with keyword arguments (`rec=body, x=digest(...)`) | CAUGHT | passed |
| helper with two callers, one passing a copy and one a computed digest | CAUGHT | passed |
| module-level `_R = digest(b'')`, written into a snapshot-keyed record | CAUGHT | passed |
| `d, n = digest(...), 1` (literal tuple unpacking resolves to the digest) | CAUGHT | passed |
| parameter rebound to `digest(...)` before the write (the local binding is the site) | CAUGHT | passed |
| the real `storage.py` `publish_dir` caller changed to pass `digest(b'r')` | CAUGHT: `Unsupported` at `cuneiform/publication.py:364` (non-constant `ledger.key` dict key), so the ledger row became a site | passed |

### Unsupported binding forms (expected: refused with the specific message, never treated as a copy)

| Form | Message |
|---|---|
| local bound twice (copy, then digest) | "`d` is bound more than once" |
| local bound in `if/else` | "`d` is bound conditionally" |
| local bound only in `if` | "`d` is bound conditionally" |
| local bound by a `for` loop | "`d` bound by a loop" |
| local bound by a walrus | "`d` bound by an assignment expression" |
| `d, n = helper(body)` | "`d` bound by unpacking a non-literal value" |
| parameter rebound after the write | "parameter `x` is rebound in `_r_put20b`" |
| parameter conditionally rebound before the write | "`x` is bound conditionally" |
| parameter of a function with no call sites | "`x` is a parameter of `_r_put21`, which has no call sites in the package" |
| parameter of a function that is passed as a callback | "`_r_put22` is referenced without being called" |
| unresolvable name | "cannot resolve name `_r_nowhere`" |
| module name rebound through `global` | "`_R_G24` is bound more than once" |

The old checker passed all 12.

### Controls (must pass with no errors)

| Control | New checker | `e124672` |
|---|---|---|
| `publish_dir`-style row: `def _r_row(sid, manifest_sha256): return {'snapshot_id': sid, 'manifest_sha256': manifest_sha256, ...}`, called with `m['manifest_sha256']` | PASS-OK | PASS-OK |
| same pattern, with the copied digest first bound to a local name (`d = m['manifest_sha256']`) and then passed | PASS-OK | PASS-OK |
| snapshot-keyed record spread with `m['manifest_sha256']` (copied subscript) | PASS-OK | PASS-OK |
| baseline moved, no code change (real `publish_dir` at `publication.py:349`, callers `corpus.py:327` and `storage.py:485`) | PASS-OK | PASS-OK |

My results agree with the repair worker's addendum: its 7 hidden forms are caught, its 2 controls pass, and there is no staleness. My controls add what that harness lacked: copied-digest parameter cases, and the real `publish_dir` caller made to pass a computed digest.

One harness note: my first mixed-caller case passed `body` to the helper twice. The checker refused it because `body` escapes, so the case did not isolate the rule. I rebuilt it with a separate record per caller, and only the rebuilt run is reported above. My first run also stopped at the controls on a string-format bug in my own script. Both are fixed in `r3-moved-review.out`.

## Bounded limits (observed; not blockers)

Each of these passes silently with both checkers. This is a bounded analyzer for the package's own signing code, not a Python verifier.

| Limit | Observed | Status |
|---|---|---|
| L1. A non-constant key: `k = 'manifest_sha256'; body[k] = d` | passed | listed in the addendum |
| L2. A write reached through `getattr`: `getattr(body, 'update')(manifest_sha256=d)` | passed | listed in the addendum (`getattr`/`setattr`) |
| L3. A signing helper outside `cuneiform/*.py` (`scripts/r_sign.py`) | passed | listed in the addendum |
| L4. A digest computed elsewhere and read back through a subscript: `d = [digest(...)]; body['manifest_sha256'] = d[0]`, or `body['manifest_sha256'] = _h(body)['sha']` where `_h` returns `{'sha': digest(...)}` | passed | **not named in the addendum's limits line.** It follows the documented rule that "an attribute, a subscript or a `.get(...)` is a copy", which keeps ledger rows and receipts from being sites. Today no package write uses this shape (every `manifest_sha256` subscript value in `cuneiform/*.py` reads `manifest`, `selection`, `m`, `st` or `e`). |

Not a limit: `h = hashlib.sha256(...); body['manifest_sha256'] = h.hexdigest()` is a call, so the checker treats it as computed and reports it.

L4 is the same family as B1, but it is a different shape: B1 used a bare temporary name, and L4 boxes the digest in a container or a helper's return value. I judge it out of scope for "ordinary refactor" under the v0.2 standard. It is recorded so the limit is known (N3).

## Findings

### N3 — P3, not blocking — name L4 in the documented limits

The addendum's "Limits" line names non-constant keys, `getattr`/`setattr` and code outside `cuneiform/*.py`. It should also say that a digest read back through a subscript or attribute of a container or helper result is classified as a copy. At the next checker touch, the owner can extend the line, or resolve a subscript of a local dict literal or a package-call return value when that is cheap. Owner: checker owner, optional.

### N4 — P3, not blocking — one self-test matches loosely

The self-test "a conditionally bound digest name is unsupported" accepts any problem that contains `bound`, which would also match "bound more than once". My harness saw the specific message "`d` is bound conditionally" for both the `if/else` and the `if`-only forms, so the behaviour is right. Only the self-test's assertion is loose. Owner: checker owner, optional.

### R3 closure

| Item | Status |
|---|---|
| v0.2 B1 (digest held in a local name) | **Closed**: reproduced form caught with the baseline moved; the old checker printed `model atlas: OK` |
| `.update(manifest_sha256=…)` / `setdefault` (v0.2 fix request) | **Closed**: both caught, plus `update({…})`, `dict.update`, `__setitem__` and `[operator.]setitem` |
| Parameter origin (v0.2 fix request: "a parameter binding stays a copy" for `publish_dir`) | **Closed and refined**: a parameter takes the origin of its call-site arguments. The copied `publish_dir` controls pass, and a computed argument is caught. No-caller, callback, nested and `*args` cases fail closed |
| Unresolvable or rebound names (v0.2: "raise `Unsupported`") | **Closed**: 12/12 refused with specific messages |
| v0.2 N2 (key added after signing) | **Closed**: `mut.py` "key added AFTER signing" fails with "`manifest` gets key `r_after` after it is signed" |
| v0.2 N1 | Not re-checked (atlas wording, out of scope) |

With v0.2's R1, R2 and R4–R10 dispositions, all of Q-019 R1–R10 are now closed or accepted. R7 remains documented trust.

## Dispositions requested

| ID | Sev | Owner | Blocks |
|---|---|---|---|
| N3 | P3 | Checker owner, optional | none |
| N4 | P3 | Checker owner, optional | none |

## Reproduce

```sh
S=~/.local/share/cuneiform-research/scratch/review-q021-r3
PY=~/.local/share/cuneiform-research/venv/bin/python
REPO=/Users/danieliser/Projects/Fun/cuneiform-research
python3 -I $S/scripts/fingerprint.py $S/fp-check.json          # compare with fp-before.json
(cd $REPO && python3 scripts/check_model_atlas.py --self-test)  # 65/65
$PY -I $S/scripts/mut.py R3                                    # 7/7 CAUGHT
python3 -I $S/scripts/r3_moved_review.py                       # 39 cases, ~2 min; or a group: form, unsup, control, limit
```
