"""Q-023: independent byte check of the three pre-ledger cohorts before their explicit adoption (read-only).

For each cohort directory under <root>/derived/cohorts: recompute the manifest digest and cohort identity, hash the
payload, compare every member slice with the receipt-bound parent raw file, count members, and compare the manifest
bytes with the cohort.json bound into every snapshot that cites it. Also writes a stat+sha256 fingerprint of every
file in the cohort store (before or after adoption). This script never writes into the store.
Usage: python -B scripts/q023_adopt_precheck.py --root R --out E.json [--phase before|after]
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.dont_write_bytecode = True
from cuneiform.model import canonical, digest, identity  # noqa: E402

COHORTS = ['cohort:4e86952ece628b06f9280fe72aafe65d', 'cohort:9abad6ce3e28e1c3c50794fb30b917bd', 'cohort:ea91baae8f0dbbeedf555f5ab6e6c5a0']


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        while b := f.read(1 << 20): h.update(b)
    return h.hexdigest()


def fingerprint(folder: Path) -> list:
    out = []
    for p in sorted(folder.rglob('*')):
        st = os.lstat(p)
        out.append({'path': str(p.relative_to(folder)), 'size': st.st_size, 'mtime_ns': st.st_mtime_ns, 'mode': oct(st.st_mode),
                    'sha256': sha(p) if p.is_file() and not p.is_symlink() else None})
    return out


def check(root: Path, cid: str) -> dict:
    d = root/'derived'/'cohorts'/cid.replace(':', '-')
    mbytes = (d/'manifest.json').read_bytes(); m = json.loads(mbytes)
    body = {k: v for k, v in m.items() if k != 'manifest_sha256'}
    # Independent recomputation of the cohort-1 identity formula (format, selector, parser, parent sha, rule, size).
    ident = identity('cohort', m['format'], m['selector'], m['parser_version'], m['parent']['sha256'], m['rule'], m['size'])
    payload = (d/'payload.json').read_bytes()
    parent = root/'raw'/'sha256'/m['parent']['sha256']
    pbytes = parent.read_bytes()
    slices_ok = parent_ok = 0
    for r in m['records']:
        s = payload[r['payload_start']:r['payload_end']]
        slices_ok += hashlib.sha256(s).hexdigest() == r['record_sha256']
        parent_ok += pbytes[r['parent_start']:r['parent_end']] == s
    bound = []
    for snap in sorted((root/'snapshots').glob('snapshot:*')):
        cj = snap/'cohort.json'
        if cj.is_file() and json.loads(cj.read_text()).get('cohort_id') == cid:
            bound.append({'snapshot': snap.name, 'cohort_json_byte_identical': cj.read_bytes() == mbytes})
    return {'cohort_id': cid, 'format': m['format'], 'size': m['size'], 'members': len(m['records']),
            'manifest_digest_ok': digest(canonical(body).encode()) == m['manifest_sha256'], 'identity_ok': ident == cid == m['cohort_id'],
            'payload_sha256_ok': hashlib.sha256(payload).hexdigest() == m['payload']['sha256'] and len(payload) == m['payload']['bytes'],
            'parent_sha256_ok': hashlib.sha256(pbytes).hexdigest() == m['parent']['sha256'],
            'member_slices_ok': f'{slices_ok}/{len(m["records"])}', 'parent_byte_ranges_ok': f'{parent_ok}/{len(m["records"])}',
            'payload_member_count_ok': len(json.loads(payload)) == len(m['records']),
            'manifest_sha256': m['manifest_sha256'], 'manifest_file_sha256': hashlib.sha256(mbytes).hexdigest(), 'bound_in_snapshots': bound,
            'ok': (digest(canonical(body).encode()) == m['manifest_sha256'] and ident == cid and slices_ok == parent_ok == len(m['records'])
                   and hashlib.sha256(payload).hexdigest() == m['payload']['sha256'] and all(b['cohort_json_byte_identical'] for b in bound) and bool(bound))}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--root', type=Path, required=True); ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--phase', choices=['before', 'after'], default='before')
    a = ap.parse_args(); root = a.root.expanduser().resolve()
    out = {'phase': a.phase, 'fingerprint': fingerprint(root/'derived'/'cohorts')}
    if a.phase == 'before': out['checks'] = [check(root, c) for c in COHORTS]; out['all_ok'] = all(c['ok'] for c in out['checks'])
    with a.out.open('x') as h: h.write(json.dumps(out, indent=1) + '\n')
    print(json.dumps({k: v for k, v in out.items() if k != 'fingerprint'} | {'fingerprint_entries': len(out['fingerprint'])}, indent=1))


if __name__ == '__main__':
    main()
