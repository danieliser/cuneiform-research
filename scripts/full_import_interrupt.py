"""Q-023 trouble case on a scratch root: hard-kill (SIGKILL) a corpus import at given delays, then report what is left.

Only the child process this script starts is killed. Expected: nothing published, no reservation, the ledger intact,
one orphan .pending-* stage per kill (removable with publication-clean-stage), and a later run builds normally.
Usage: python -B scripts/full_import_interrupt.py --root SCRATCH_ROOT --cohort COHORT_ID --kill-after 12 60 --out E.json
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def cli(root, *args, check=True):
    cmd = [sys.executable, '-B', '-m', 'cuneiform', '--root', str(root), '--max-total-gib', '12', '--reserve-gib', '30', *args]
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    if check and r.returncode: raise SystemExit(r.stderr)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, required=True); ap.add_argument('--cohort', required=True)
    ap.add_argument('--kill-after', type=float, nargs='+', required=True); ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    root = a.root.expanduser().resolve()
    if 'scratch' not in root.parts: raise SystemExit('refusing: trouble cases run only on a scratch root')
    snaps = root/'snapshots'
    events = []
    for delay in a.kill_after:
        before = {p.name for p in snaps.glob('.pending-*')}
        child = subprocess.Popen([sys.executable, '-B', '-m', 'cuneiform', '--root', str(root), '--max-total-gib', '12', '--reserve-gib', '30',
                                  'corpus-import', a.cohort, '--projections', 'full', '--memory', '8GB'], cwd=REPO, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            child.wait(timeout=delay); events.append({'kill_after_s': delay, 'killed': False, 'note': 'finished before the kill', 'rc': child.returncode}); continue
        except subprocess.TimeoutExpired:
            pass
        new = sorted({p.name for p in snaps.glob('.pending-*')} - before)
        files = sorted(str(f.relative_to(snaps)) for s in new for f in (snaps/s).rglob('*') if f.is_file())
        child.kill(); child.wait()
        events.append({'kill_after_s': delay, 'killed': True, 'rc': child.returncode, 'new_stages': new, 'stage_files_at_kill': files[:40]})
    status = json.loads(cli(root, 'publication-status').stdout)
    listing = json.loads(cli(root, 'snapshots').stdout)
    t = time.monotonic(); rebuilt = cli(root, 'corpus-import', a.cohort, '--projections', 'full', '--memory', '8GB'); rebuild_s = round(time.monotonic() - t, 1)
    result = json.loads(rebuilt.stdout)
    cleaned = []
    for st in status['stages']:
        r = cli(root, 'publication-clean-stage', st['stage'], '--min-age-s', '0', check=False)
        cleaned.append({'stage': st['stage'], 'rc': r.returncode, 'out': (r.stdout or r.stderr).strip()[-300:]})
    after = json.loads(cli(root, 'publication-status').stdout)
    out = {'events': events,
           'after_kills': {'ledger_states': [(s['snapshot'], s['state']) for s in status['snapshots']], 'stages': status['stages'], 'torn_tail': status['torn_tail'],
                           'unledgered_directories': status['unledgered_directories'], 'snapshots_verified': [(s['snapshot'], s['verified']) for s in listing]},
           'rebuild': {'snapshot': result['snapshot'], 'reused': result['reused'], 'seconds': rebuild_s},
           'clean_stage': cleaned,
           'final': {'ledger_states': [(s['snapshot'], s['state']) for s in after['snapshots']], 'stages': after['stages'], 'torn_tail': after['torn_tail']}}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open('x') as h: h.write(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
