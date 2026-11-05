"""Publication protocol regressions (Q-005 review B1-B3, F4-F12).

Crash tests hard-kill a child process (os._exit, no handlers run) at each protocol boundary. Disk tests need
CUNEIFORM_RUN_DISK_TESTS=1 and write only to their own temporary tree under <runtime>/scratch; they never touch
the real snapshot store.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
import duckdb
from cuneiform import publication
from cuneiform.publication import KILL_ENV, LEDGER, Ledger, LedgerCorrupt, PublicationError
from cuneiform.storage import Config, MiB, import_source, resolve_snapshot, verify, verified

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
FIX = ROOT/'fixtures/ebl-synthetic.json'
RUNTIME = Path.home()/'.local/share/cuneiform-research'


def admission_config():
    """Runtime-root admission for disk tests: the default task budget, unless CUNEIFORM_TEST_MAX_TOTAL_GIB names an explicit
    larger budget the owner authorized for this root (Q-023: 41 GiB, after the full eBL import). Never lowers the reserve."""
    gib = os.environ.get('CUNEIFORM_TEST_MAX_TOTAL_GIB')
    return Config(RUNTIME, max_total_bytes=int(float(gib) * 1024**3)) if gib else Config(RUNTIME)
DISK = os.environ.get('CUNEIFORM_RUN_DISK_TESTS') == '1'
CHILD = """
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from cuneiform.storage import Config, import_source
start = float(sys.argv[4])
import time
while time.time() < start: pass
r = import_source('ebl', Path(sys.argv[2]), Config(Path(sys.argv[3])))
print(json.dumps({'snapshot': r['snapshot'], 'reused': r['reused'], 'raced': r.get('raced', False)}))
"""


def run_child(store: Path, kill: str | None = None, start: float = 0.0, fixture: Path = FIX):
    env = {k: v for k, v in os.environ.items() if k != KILL_ENV}
    if kill: env[KILL_ENV] = kill
    return subprocess.Popen([sys.executable, '-B', '-c', CHILD, str(ROOT), str(fixture), str(store), str(start)], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def unlock(path: Path):
    for p in [path, *path.rglob('*')]:
        if p.is_dir() and not p.is_symlink(): os.chmod(p, 0o755)


def events(cfg: Config, sid: str | None = None):
    path = cfg.root/'snapshots'/LEDGER
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []
    return [r.get('event') for r in rows if sid is None or r.get('snapshot_id') == sid]


def cli(cfg: Config, *args):
    out = subprocess.run([sys.executable, '-B', '-m', 'cuneiform', '--root', str(cfg.root), *args], cwd=ROOT, capture_output=True, text=True)
    return out.returncode, (json.loads(out.stdout) if out.returncode == 0 else out.stderr)


class LedgerStateTests(unittest.TestCase):
    """Pure ledger state machine; tiny files in a temporary directory."""
    def ledger(self, d, lines):
        (Path(d)/LEDGER).write_text(''.join(json.dumps(x) + '\n' for x in lines)); return Ledger(Path(d))

    def test_states_and_conflicts(self):
        with tempfile.TemporaryDirectory() as d:
            L = self.ledger(d, [{'snapshot_id': 'a', 'manifest_sha256': 'm', 'backfilled': True, 'incident': 'x'},
                                {'event': 'reserve', 'snapshot_id': 'b', 'manifest_sha256': 'm', 'stage': '.pending-1'},
                                {'event': 'reserve', 'snapshot_id': 'c', 'manifest_sha256': 'm'}, {'event': 'commit', 'snapshot_id': 'c', 'manifest_sha256': 'm'},
                                {'event': 'reserve', 'snapshot_id': 'd', 'manifest_sha256': 'm'}, {'event': 'abort', 'snapshot_id': 'd'},
                                {'event': 'reserve', 'snapshot_id': 'e', 'manifest_sha256': 'm'}, {'event': 'abandon', 'snapshot_id': 'e'},
                                {'snapshot_id': 'f', 'manifest_sha256': 'm'}, {'snapshot_id': 'f', 'manifest_sha256': 'n'},
                                {'event': 'commit', 'snapshot_id': 'g', 'manifest_sha256': 'm'},
                                {'event': 'reserve', 'snapshot_id': 'h', 'manifest_sha256': 'm'}, {'event': 'commit', 'snapshot_id': 'h', 'manifest_sha256': 'OTHER'}])
            got = {s: (L.status(s).state, L.status(s).kind) for s in 'abcdefghz'}
            self.assertEqual(got, {'a': ('published', 'legacy-backfilled'), 'b': ('reserved', None), 'c': ('published', 'ledgered'), 'd': ('aborted', None),
                                   'e': ('abandoned', None), 'f': ('conflict', 'legacy'), 'g': ('conflict', None), 'h': ('conflict', None), 'z': ('unpublished', None)})

    def test_torn_tail_tolerated_by_readers_refused_by_writers_and_corrupt_middle_refused(self):
        with tempfile.TemporaryDirectory() as d:
            L = self.ledger(d, [{'snapshot_id': 'a', 'manifest_sha256': 'm'}])
            with (Path(d)/LEDGER).open('a') as f: f.write('{"event": "reserve", "snapsh')
            entries, tail = L.scan()
            self.assertEqual(L.status('a', entries).state, 'published'); self.assertFalse(tail['parsed'])
            with L.locked():
                with self.assertRaisesRegex(PublicationError, 'torn record'): L.writer_scan()
            ack = L.repair_tail('test: torn by injected partial write')
            self.assertEqual(ack['event'], 'torn-tail-acknowledged')
            entries, tail = L.scan(); self.assertIsNone(tail)
            self.assertIn(b'"snapsh', (Path(d)/LEDGER).read_bytes())   # torn bytes kept as evidence
            with L.locked(): L.writer_scan()
            with (Path(d)/LEDGER).open('a') as f: f.write('garbage\n')
            with self.assertRaises(LedgerCorrupt): L.scan()


class OraccProvenanceTests(unittest.TestCase):
    def test_shared_sense_carries_no_instance_sig_and_occurrences_keep_their_own(self):
        from test_corpus_pilot import memory_db, oracc_payload
        from cuneiform.adapters import Builder
        from cuneiform.model import digest
        from cuneiform.oracc import map_selection
        payload, members = oracc_payload()
        # Give the two attestations of the shared sense 'to' different instance sigs (as in real ORACC data).
        text = payload.decode()
        first = '@synth%akk:a-na=ana[to//to]PRP\'PRP$ana'
        self.assertIn(first, text)
        doc = json.loads(payload)
        def walk(x):
            if isinstance(x, dict):
                if x.get('node') == 'l' and (x.get('f') or {}).get('sense') == 'to' and not x.get('sig'): x['sig'] = '@synth%akk:a-na=ana[to//to]PRP\'PRP$an-SECOND'
                for v in x.values(): walk(v)
            elif isinstance(x, list):
                for v in x: walk(v)
        walk(doc)
        parts, members, offset = [b'[\n'], [], 2
        for i, item in enumerate(doc):
            data = json.dumps(item, ensure_ascii=False).encode()
            if i: parts.append(b',\n'); offset += 2
            members.append({'payload_pointer': f'/{i}', 'payload_start': offset, 'payload_end': offset + len(data), 'member': f'synth/{i}.json', 'sha256': digest(data)})
            parts.append(data); offset += len(data)
        payload = b''.join(parts + [b'\n]\n'])
        db = memory_db(); b = Builder(db, 'snap', 'oracc/synth'); b.raw_sha256 = digest(payload)
        map_selection(b, payload, members, 'synth'); b.flush()
        for (loc,) in db.execute('SELECT source_locator FROM sense').fetchall():
            self.assertNotIn('@synth', loc)
            parsed = json.loads(loc)
            self.assertEqual(parsed['locator_kind'], 'oracc-sense-key')
            self.assertIn('first_attestation_in_selection', parsed)
        sigs = sorted(json.loads(q)['sig'] for (q,) in db.execute("SELECT e.qualification FROM edge e JOIN sense s ON s.id=e.target_id WHERE e.kind='IN_SENSE' AND s.gloss='to'").fetchall())
        self.assertEqual(sigs, sorted([first, first.replace('$ana', '$an-SECOND')]))
        lem = [json.loads(q).get('sig') for (q,) in db.execute("SELECT qualification FROM edge WHERE kind='LEMMATIZED_AS'").fetchall()]
        self.assertEqual(len(lem), 3); self.assertTrue(all(lem))
        db.close()


@unittest.skipUnless(DISK, 'disk verification explicitly gated')
class PublicationDiskTests(unittest.TestCase):
    def setUp(self):
        admission_config().guard(256*MiB)
        self.tmp = tempfile.TemporaryDirectory(prefix='publication-test-', dir=RUNTIME/'scratch')
        self.base = Path(self.tmp.name)

    def tearDown(self):
        publication.FAULT_HOOK = None
        unlock(self.base); self.tmp.cleanup()

    def store(self, name='store'):
        return Config(self.base/name)

    def sid(self, cfg):
        return import_source('ebl', FIX, cfg, dry_run=True)['snapshot']

    def kill_at(self, cfg, point):
        p = run_child(cfg.root, kill=point); p.communicate()
        self.assertEqual(p.returncode, 137, point)

    # ---- B1: crash windows ----
    def test_kill_after_rename_fails_closed_then_delete_cannot_republish(self):
        cfg = self.store(); sid = self.sid(cfg); snap = cfg.root/'snapshots'/sid
        self.kill_at(cfg, 'after-rename')
        self.assertTrue(snap.is_dir()); self.assertEqual(events(cfg, sid), ['reserve'])
        with self.assertRaisesRegex(PublicationError, 'not committed'): resolve_snapshot(cfg, sid)
        with self.assertRaisesRegex(PublicationError, 'not committed'): verify(snap)
        with self.assertRaisesRegex(PublicationError, 'reserved but never committed'): import_source('ebl', FIX, cfg)
        code, plan = cli(cfg, 'publication-recover', sid)
        self.assertEqual((code, plan['actions']), (0, ['commit']))
        unlock(snap); shutil.rmtree(snap)   # the review's incident sequence: delete, then rebuild
        with self.assertRaisesRegex(PublicationError, 'reserved but never committed'): import_source('ebl', FIX, cfg)
        code, plan = cli(cfg, 'publication-recover', sid); self.assertEqual(plan['actions'], ['abandon'])
        code, refused = cli(cfg, 'publication-recover', sid, '--action', 'commit', '--reason', 'try'); self.assertEqual(code, 2); self.assertIn('not safe', refused)
        code, done = cli(cfg, 'publication-recover', sid, '--action', 'abandon', '--reason', 'test: bytes lost after kill')
        self.assertEqual(done['state_after'], 'abandoned')
        with self.assertRaisesRegex(PublicationError, 'burned permanently'): import_source('ebl', FIX, cfg)
        self.assertFalse(snap.exists()); self.assertEqual(events(cfg, sid), ['reserve', 'abandon'])

    def test_kill_after_rename_explicit_commit_recovers_exact_reserved_bytes(self):
        cfg = self.store(); sid = self.sid(cfg); snap = cfg.root/'snapshots'/sid
        self.kill_at(cfg, 'after-rename')
        reserved = Ledger(cfg.root/'snapshots').status(sid).manifest_sha256
        code, done = cli(cfg, 'publication-recover', sid, '--action', 'commit', '--reason', 'test: directory verified after kill')
        self.assertEqual((code, done['state_after']), (0, 'published'))
        v = verified(resolve_snapshot(cfg, sid))
        self.assertEqual((v['manifest']['manifest_sha256'], v['publication']['status']), (reserved, 'ledgered-recovered'))
        self.assertTrue(import_source('ebl', FIX, cfg)['reused'])
        self.assertEqual(events(cfg, sid), ['reserve', 'commit'])

    def test_kill_after_reserve_stage_complete_or_discard(self):
        a = self.store('a'); sid = self.sid(a)
        self.kill_at(a, 'after-reserve')
        stage = a.root/'snapshots'/Ledger(a.root/'snapshots').status(sid).stage
        self.assertTrue(stage.is_dir()); self.assertFalse((a.root/'snapshots'/sid).exists())
        with self.assertRaisesRegex(PublicationError, 'reserved but never committed'): import_source('ebl', FIX, a)
        self.assertEqual(cli(a, 'publication-recover', sid)[1]['actions'], ['complete', 'discard'])
        cli(a, 'publication-recover', sid, '--action', 'complete', '--reason', 'test: reserved stage intact')
        self.assertFalse(stage.exists())
        self.assertEqual(verified(resolve_snapshot(a, sid))['publication']['status'], 'ledgered-recovered')
        b = self.store('b')
        self.kill_at(b, 'after-reserve')
        reserved = Ledger(b.root/'snapshots').status(sid).manifest_sha256
        cli(b, 'publication-recover', sid, '--action', 'discard', '--reason', 'test: never renamed')
        self.assertEqual(list((b.root/'snapshots').glob('.pending-*')), [])
        # The reserved bytes were never visible, so the ID is free again; history is kept.
        r = import_source('ebl', FIX, b)
        self.assertFalse(r['reused']); self.assertNotEqual(r['manifest']['manifest_sha256'], reserved)
        self.assertEqual(events(b, sid), ['reserve', 'abort', 'reserve', 'commit'])

    def test_kill_before_reserve_leaves_unnamed_stage_only(self):
        cfg = self.store(); sid = self.sid(cfg)
        self.kill_at(cfg, 'before-reserve')
        self.assertEqual(events(cfg), [])
        code, status = cli(cfg, 'publication-status')
        self.assertEqual([s['named_by_reservation'] for s in status['stages']], [False])
        self.assertFalse(import_source('ebl', FIX, cfg)['reused'])
        code, out = cli(cfg, 'publication-clean-stage', status['stages'][0]['stage'], '--min-age-s', '0'); self.assertEqual(code, 0)
        self.assertEqual(list((cfg.root/'snapshots').glob('.pending-*')), [])

    def test_kill_after_commit_is_published(self):
        cfg = self.store(); sid = self.sid(cfg)
        self.kill_at(cfg, 'after-commit')
        self.assertEqual(verified(resolve_snapshot(cfg, sid))['publication']['status'], 'ledgered')

    # ---- B2: reads bind the ledger's published identity ----
    def test_replaced_build_refused_restoration_bound_standalone_labelled(self):
        a, b = self.store('a'), self.store('b')
        ra = import_source('ebl', FIX, a); time.sleep(0.01); rb = import_source('ebl', FIX, b)
        sid = ra['snapshot']; self.assertEqual(sid, rb['snapshot'])
        self.assertNotEqual(ra['manifest']['manifest_sha256'], rb['manifest']['manifest_sha256'])
        snap = a.root/'snapshots'/sid; aside = self.base/'aside'/sid
        aside.parent.mkdir(); shutil.copytree(snap, aside); unlock(snap); shutil.rmtree(snap)
        shutil.copytree(b.root/'snapshots'/sid, snap)
        with self.assertRaisesRegex(PublicationError, 'not the published snapshot'): resolve_snapshot(a, sid)
        with self.assertRaisesRegex(PublicationError, 'not the published snapshot'): verify(snap, sid)
        from cuneiform.persisted import lookup_snapshot
        with self.assertRaisesRegex(PublicationError, 'not the published snapshot'): lookup_snapshot(snap, 'report')
        self.assertFalse(cli(a, 'snapshots')[1][0]['verified'])
        with self.assertRaisesRegex(PublicationError, 'directory in the store does not match'): _republish(a, sid)
        self.assertEqual(list((a.root/'snapshots').glob('.pending-*')), [])
        # A relocated copy outside any store still verifies, labelled as not ledger-checked.
        self.assertEqual(verified(aside)['publication']['status'], 'standalone-not-ledger-checked')
        # Restoring the exact published bytes is accepted.
        unlock(snap); shutil.rmtree(snap); shutil.copytree(aside, snap)
        self.assertEqual(verified(resolve_snapshot(a, sid))['publication']['status'], 'ledgered')
        # manifest.json file bytes are bound for format-2 entries (review F10).
        os.chmod(snap, 0o755); os.chmod(snap/'manifest.json', 0o644)
        with (snap/'manifest.json').open('a') as f: f.write(' ')
        self.assertEqual(verify(snap, sid, ledger='skip')['manifest_sha256'], ra['manifest']['manifest_sha256'])
        with self.assertRaisesRegex(PublicationError, 'manifest.json bytes differ'): resolve_snapshot(a, sid)

    def test_unledgered_directory_refused_until_explicitly_adopted(self):
        a, b = self.store('a'), self.store('b')
        r = import_source('ebl', FIX, a); import_source('ebl', FIX, b, record_id='other')
        sid = r['snapshot']; shutil.copytree(a.root/'snapshots'/sid, b.root/'snapshots'/sid)
        with self.assertRaisesRegex(PublicationError, 'no publication record'): resolve_snapshot(b, sid)
        with self.assertRaisesRegex(PublicationError, 'no publication record'): import_source('ebl', FIX, b)
        code, rec = cli(b, 'publication-adopt', sid, '--reason', 'test: copied from store a')
        self.assertEqual((code, rec['event']), (0, 'adopt'))
        self.assertEqual(verified(resolve_snapshot(b, sid))['publication']['status'], 'adopted')
        self.assertTrue(import_source('ebl', FIX, b)['reused'])

    # ---- B3: failure cleanup keeps the original error ----
    def test_rename_failure_raises_original_error_and_leaves_no_stage(self):
        cfg = self.store(); sid = self.sid(cfg)
        def hook(point):
            if point == 'rename': raise OSError(18, 'injected cross-device rename failure')
        publication.FAULT_HOOK = hook
        with self.assertRaisesRegex(OSError, 'injected cross-device') as ctx: import_source('ebl', FIX, cfg)
        self.assertNotIsInstance(ctx.exception, PermissionError)
        publication.FAULT_HOOK = None
        self.assertEqual(list((cfg.root/'snapshots').glob('.pending-*')), [])
        self.assertEqual(events(cfg, sid), ['reserve', 'abort'])
        self.assertFalse(import_source('ebl', FIX, cfg)['reused'])
        self.assertEqual(events(cfg, sid), ['reserve', 'abort', 'reserve', 'commit'])
        self.assertEqual(verified(resolve_snapshot(cfg, sid))['publication']['status'], 'ledgered')

    def test_cleanup_failure_keeps_original_error_and_writes_recovery_receipt(self):
        cfg = self.store()
        def hook(point):
            if point == 'rename': raise OSError(5, 'injected I/O failure')
        publication.FAULT_HOOK = hook
        with mock.patch('cuneiform.storage.discard_stage', side_effect=PermissionError('injected cleanup failure')):
            with self.assertRaisesRegex(OSError, 'injected I/O failure') as ctx: import_source('ebl', FIX, cfg)
        publication.FAULT_HOOK = None
        notes = ' '.join(getattr(ctx.exception, '__notes__', []))
        self.assertIn('stage cleanup failed', notes); self.assertIn('Recovery receipt', notes)
        receipts = list((cfg.root/'snapshots'/'.recovery').glob('*.json'))
        self.assertEqual(len(receipts), 1)
        receipt = json.loads(receipts[0].read_text())
        self.assertIn('injected I/O failure', receipt['original_error'])
        code, _ = cli(cfg, 'publication-clean-stage', Path(receipt['stage']).name, '--min-age-s', '0'); self.assertEqual(code, 0)
        self.assertEqual(list((cfg.root/'snapshots').glob('.pending-*')), [])

    # ---- F5: concurrent writers ----
    def test_concurrent_writers_publish_once_and_both_succeed(self):
        for trial in range(2):
            cfg = self.store(f'race{trial}'); start = time.time() + 1.0
            procs = [run_child(cfg.root, start=start) for _ in range(2)]
            outs = [p.communicate() for p in procs]
            self.assertEqual([p.returncode for p in procs], [0, 0], outs)
            results = [json.loads(o[0].strip().splitlines()[-1]) for o in outs]
            self.assertEqual(len({r['snapshot'] for r in results}), 1)
            self.assertEqual(sorted(r['reused'] for r in results), [False, True])
            self.assertEqual(events(cfg), ['reserve', 'commit'])
            self.assertEqual(len(list((cfg.root/'snapshots').glob('snapshot:*'))), 1)
            self.assertEqual(list((cfg.root/'snapshots').glob('.pending-*')), [])

    # ---- F7/F8/F11: one verification per call, labelled timings, typed scope/layer errors ----
    def test_lookup_verifies_once_labels_latency_and_types_errors(self):
        from cuneiform.persisted import LayerUnavailable, ScopeMismatch, lookup_snapshot, parity
        import cuneiform.storage as st
        cfg = self.store(); r = import_source('ebl', FIX, cfg); snap = resolve_snapshot(cfg, r['snapshot'])
        real = st.file_sha256; calls = []
        with mock.patch('cuneiform.storage.file_sha256', side_effect=lambda p: calls.append(Path(p).name) or real(p)):
            out = lookup_snapshot(snap, 'postings', 'A', field='atf')
            self.assertEqual(calls.count('graph.duckdb'), 1)
            calls.clear(); parity(snap, ['A', 'B'], 'atf'); self.assertEqual(calls.count('graph.duckdb'), 1)
        self.assertEqual(out['latency_scope'], 'query-only')
        self.assertLessEqual(out['timing']['query_ms'], out['timing']['end_to_end_ms'])
        self.assertEqual(out['scope']['publication']['status'], 'ledgered')
        self.assertTrue(out['scope']['input_identity'].startswith('snapshot:'))
        self.assertNotEqual(out['scope']['input_identity'], r['snapshot'])   # manifest-3 ID differs from the legacy-formula input identity
        with self.assertRaises(ScopeMismatch): lookup_snapshot(snap, 'postings', 'A', namespace='oracc/ccpo')
        with self.assertRaises(ScopeMismatch): lookup_snapshot(snap, 'postings', 'A', snapshot='snapshot:' + '0' * 32)
        with self.assertRaises(LayerUnavailable): lookup_snapshot(snap, 'words', 'ana')
        self.assertEqual(lookup_snapshot(snap, 'postings', 'NO-SUCH-READING')['rows'], [])   # loaded layer, real zero

    # ---- F9: new cohorts are ledgered and read-only ----
    def test_new_cohort_ledgered_read_only_and_not_rebuilt_after_delete(self):
        from test_corpus_pilot import write_parent
        from cuneiform.corpus import build_cohort, RULE_DEFAULT
        from cuneiform.model import digest
        rows = json.loads(FIX.read_text()); rows = rows['fragments'] if isinstance(rows, dict) else rows
        path = write_parent(self.base, rows); parent = {'sha256': digest(path.read_bytes()), 'url': 'synthetic:parent'}
        out = self.base/'cohorts'
        m = build_cohort(path, parent, 1, out, RULE_DEFAULT); directory = Path(m['directory'])
        self.assertTrue(all(p.stat().st_mode & 0o222 == 0 for p in [directory, *directory.rglob('*')]))
        self.assertEqual([e['event'] for e in map(json.loads, (out/LEDGER).read_text().splitlines())], ['reserve', 'commit'])
        self.assertEqual(build_cohort(path, parent, 1, out, RULE_DEFAULT)['manifest_sha256'], m['manifest_sha256'])
        unlock(directory); shutil.rmtree(directory)
        with self.assertRaisesRegex(PublicationError, 'already published'): build_cohort(path, parent, 1, out, RULE_DEFAULT)


def _republish(cfg, sid):
    """Drive publish() directly with a fresh build of the same ID while a mismatched directory sits in the store."""
    import cuneiform.storage as st
    with mock.patch.object(st, 'existing_snapshot', return_value=None):
        return import_source('ebl', FIX, cfg)


@unittest.skipUnless((RUNTIME/'snapshots'/LEDGER).exists(), 'real store not on this machine')
class RealStoreReadOnlyTests(unittest.TestCase):
    def test_existing_snapshots_serve_as_legacy_backfilled_with_incident_labels(self):
        from cuneiform.persisted import scope
        cfg = Config(RUNTIME)
        before = (RUNTIME/'snapshots'/LEDGER).read_bytes(); lock_before = (RUNTIME/'snapshots'/'.publication.lock').exists()
        ledger = Ledger(RUNTIME/'snapshots')
        incident = {'snapshot:ce127437339109285185a534145edf50', 'snapshot:84971360d212834e0b7acbeac1e56abe'}
        legacy = [sid for sid in ledger.ids() if ledger.status(sid).kind == 'legacy-backfilled']
        self.assertEqual(len(legacy), 5)
        for sid in legacy:
            sc = scope(resolve_snapshot(cfg, sid))
            self.assertEqual(sc['publication']['status'], 'ledgered-legacy-backfilled')
            self.assertEqual('incident' in sc['publication'], sid in incident)
            self.assertIn('not an observed publication time', sc['publication']['published_at_semantics'])
        # Reads never write: ledger bytes unchanged and no lock file created.
        self.assertEqual(before, (RUNTIME/'snapshots'/LEDGER).read_bytes())
        self.assertEqual(lock_before, (RUNTIME/'snapshots'/'.publication.lock').exists())


if __name__ == '__main__':
    unittest.main()
