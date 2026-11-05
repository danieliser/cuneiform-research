"""Store-read and cohort publication regressions for reviews/corpus-pilot-review-v0.2.md R1-R5.

R1: a store entry is ledger-checked whether it is reached lexically or through symlinks; a symlinked or escaping
    entry is refused on every store read (CLI and API), and ID X can never be served as Y. Relocated copies still
    verify at their own path with the standalone label.
R2: cohorts are ledger-checked on read (verify_cohort, audit, import); an interrupted cohort is recovered only through
    the explicit publication-* verbs with --store cohorts, which bind the reserved bytes.
R3: a writer arriving inside another live writer's reserve->commit window waits and reuses instead of failing.
R4: an absent store entry raises a typed PublicationError naming its ledger state.
R5: seal flushes the final read-only modes.

Disk tests need CUNEIFORM_RUN_DISK_TESTS=1 and write only to a temporary tree under <runtime>/scratch.
"""
import hashlib
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
from cuneiform.publication import KILL_ENV, LEDGER, PAUSE_ENV, Ledger, PublicationError
from cuneiform.storage import Config, MiB, import_source, resolve_snapshot, store_path, verify, verified
from cuneiform.model import digest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_corpus_pilot import write_parent   # noqa: E402
from test_publication import cli, run_child, unlock   # noqa: E402

FIX = ROOT/'fixtures/ebl-synthetic.json'
RUNTIME = Path.home()/'.local/share/cuneiform-research'


def admission_config():
    """Runtime-root admission for disk tests: the default task budget, unless CUNEIFORM_TEST_MAX_TOTAL_GIB names an explicit
    larger budget the owner authorized for this root (Q-023: 41 GiB, after the full eBL import). Never lowers the reserve."""
    gib = os.environ.get('CUNEIFORM_TEST_MAX_TOTAL_GIB')
    return Config(RUNTIME, max_total_bytes=int(float(gib) * 1024**3)) if gib else Config(RUNTIME)
DISK = os.environ.get('CUNEIFORM_RUN_DISK_TESTS') == '1'

COHORT_CHILD = """
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from cuneiform.corpus import build_cohort, RULE_DEFAULT
start = float(sys.argv[5])
import time
while time.time() < start: pass
m = build_cohort(Path(sys.argv[2]), json.loads(sys.argv[3]), 1, Path(sys.argv[4]), RULE_DEFAULT)
print(json.dumps({'cohort_id': m['cohort_id'], 'manifest_sha256': m['manifest_sha256'], 'publication': m['publication']['status']}))
"""


def tree(path: Path) -> dict:
    """Byte and mode fingerprint of a directory (lstat; file SHA-256)."""
    out = {}
    for p in sorted([path, *path.rglob('*')]):
        st = os.lstat(p)
        rec = [oct(st.st_mode)]
        if p.is_file() and not p.is_symlink(): rec.append(hashlib.sha256(p.read_bytes()).hexdigest())
        out[str(p.relative_to(path))] = rec
    return out


def make_link(link: Path, target: Path):
    """Replace a store entry (a real directory or a link) with a symlink to ``target``."""
    if link.is_symlink(): link.unlink()
    elif link.exists(): unlock(link); shutil.rmtree(link)
    os.symlink(target, link)


@unittest.skipUnless(DISK, 'disk verification explicitly gated')
class StoreReadTests(unittest.TestCase):
    def setUp(self):
        admission_config().guard(256*MiB)
        self.tmp = tempfile.TemporaryDirectory(prefix='store-read-test-', dir=RUNTIME/'scratch')
        self.base = Path(self.tmp.name)

    def tearDown(self):
        publication.FAULT_HOOK = None
        unlock(self.base); self.tmp.cleanup()

    def two_builds(self):
        """Same ID, different bytes (created_at differs) in stores a and b."""
        a, b = Config(self.base/'a'), Config(self.base/'b')
        ra = import_source('ebl', FIX, a); time.sleep(0.01); rb = import_source('ebl', FIX, b)
        self.assertEqual(ra['snapshot'], rb['snapshot'])
        self.assertNotEqual(ra['manifest']['manifest_sha256'], rb['manifest']['manifest_sha256'])
        return a, b, ra['snapshot'], ra['manifest']['manifest_sha256'], rb['manifest']['manifest_sha256']

    def assert_every_store_read_refused(self, cfg, sid, state, occurrence):
        """Every CLI read verb and API store read refuses the entry with ``state`` (nothing served)."""
        snap = cfg.root/'snapshots'/sid
        for args in (('manifest', sid), ('scope', sid), ('query', sid, 'A', 'B', 'C'), ('lookup', sid, 'report'), ('lookup', sid, 'postings', 'A'),
                     ('parity', sid, '["A","B"]', '--field', 'atf'), ('trace', sid, occurrence), ('export-graph', sid),
                     ('catalog-link', 'ebl:x', '--snapshot', sid)):
            code, out = cli(cfg, *args)
            self.assertEqual(code, 2, (args, out)); self.assertNotIn('Traceback', out)
        self.assertFalse((cfg.root/'derived'/'exports').exists())
        code, listing = cli(cfg, 'snapshots')
        row = next(r for r in listing if r['snapshot'] == sid)
        self.assertEqual((row['verified'], row['state']), (False, state))
        from cuneiform.persisted import lookup_snapshot, scope
        from cuneiform.query import connect, trace
        for call in (lambda: resolve_snapshot(cfg, sid), lambda: verify(snap), lambda: verified(snap), lambda: scope(snap),
                     lambda: lookup_snapshot(snap, 'report'), lambda: connect(snap), lambda: trace(snap, occurrence),
                     lambda: verify(store_path(cfg, sid)), lambda: scope(store_path(cfg, sid)), lambda: connect(store_path(cfg, sid))):
            with self.assertRaises(PublicationError) as ctx: call()
            self.assertEqual(ctx.exception.state, state)

    def occurrence(self, cfg, sid):
        db = duckdb.connect(str(cfg.root/'snapshots'/sid/'graph.duckdb'), read_only=True)
        try: return db.execute('SELECT id FROM occurrence ORDER BY id LIMIT 1').fetchone()[0]
        finally: db.close()

    # ---- R1: review c11b, same ID, different bytes behind a symlink ----
    def test_symlinked_entry_same_id_different_bytes_refused_everywhere(self):
        a, b, sid, ma, mb = self.two_builds(); occ = self.occurrence(a, sid)
        ext = self.base/'external'; ext.mkdir(); shutil.copytree(b.root/'snapshots'/sid, ext/sid)
        aside = self.base/'aside'; shutil.copytree(a.root/'snapshots'/sid, aside/sid)
        make_link(a.root/'snapshots'/sid, ext/sid)
        self.assert_every_store_read_refused(a, sid, 'symlinked-entry', occ)
        with self.assertRaises(PublicationError) as ctx: import_source('ebl', FIX, a)
        self.assertEqual(ctx.exception.state, 'symlinked-entry')
        code, status = cli(a, 'publication-status')
        self.assertEqual(status['symlinked_entries'], [sid])
        with self.assertRaises(PublicationError) as ctx:
            publication.adopt(Ledger(a.root/'snapshots'), sid, a.root/'snapshots', lambda p, s: verify(p, s, ledger='skip'), 'test')
        self.assertIn(ctx.exception.state, ('published', 'symlinked-entry'))
        # The relocated copy itself stays verifiable at its own path, honestly labelled; never as a store read.
        v = verified(ext/sid)
        self.assertEqual((v['manifest']['manifest_sha256'], v['publication']['status']), (mb, 'standalone-not-ledger-checked'))
        with self.assertRaises(PublicationError) as ctx: verify(ext/sid, ledger='require')
        self.assertEqual(ctx.exception.state, 'not-in-ledger')
        # Restoring the exact published bytes as a real directory serves the published manifest again.
        (a.root/'snapshots'/sid).unlink(); shutil.copytree(aside/sid, a.root/'snapshots'/sid)
        self.assertEqual(verified(resolve_snapshot(a, sid))['manifest']['manifest_sha256'], ma)
        code, m = cli(a, 'manifest', sid); self.assertEqual((code, m['manifest_sha256']), (0, ma))

    # ---- R1: review c11c, ID X linked to snapshot Y; and a real directory X holding Y ----
    def test_id_x_never_resolves_to_snapshot_y(self):
        a = Config(self.base/'a'); x = import_source('ebl', FIX, a)['snapshot']; occ = self.occurrence(a, x)
        alt = self.base/'alt.json'; alt.write_text(json.dumps(json.loads(FIX.read_text()), indent=2))
        b = Config(self.base/'b'); y = import_source('ebl', alt, b)['snapshot']; self.assertNotEqual(x, y)
        ext = self.base/'ext'; ext.mkdir(); shutil.copytree(b.root/'snapshots'/y, ext/y)
        snap = a.root/'snapshots'/x
        make_link(snap, ext/y)
        self.assert_every_store_read_refused(a, x, 'symlinked-entry', occ)
        # A real directory named X holding Y's bytes: refused as misplaced or as an identity mismatch, never served as Y.
        snap.unlink(); shutil.copytree(ext/y, snap)
        for args in (('manifest', x), ('scope', x), ('query', x, 'A', 'B', 'C'), ('lookup', x, 'report'), ('export-graph', x)):
            code, out = cli(a, *args); self.assertEqual(code, 2, args); self.assertRegex(out, 'identity mismatch|misplaced|holds the manifest')
        with self.assertRaisesRegex(PublicationError, 'holds the manifest'): verify(snap)
        with self.assertRaisesRegex(ValueError, 'identity mismatch'): verify(store_path(a, x))
        from cuneiform.persisted import scope
        with self.assertRaisesRegex(ValueError, 'identity mismatch'): scope(store_path(a, x))

    # ---- R1: nested and relocated path forms ----
    def test_nested_path_forms(self):
        a, b, sid, ma, mb = self.two_builds()
        snaps = a.root/'snapshots'
        # Lexical variants of a real entry are served as ledgered.
        (snaps/'sub').mkdir()
        for form in (snaps/'.'/sid, Path(str(snaps/sid) + '/'), snaps/'sub'/'..'/sid, Path(os.path.relpath(snaps/sid))):
            v = verified(form); self.assertEqual((v['manifest']['manifest_sha256'], v['publication']['status']), (ma, 'ledgered'), form)
        # '..' through a symlinked component that escapes the store: refused (lexically a store entry, resolves elsewhere).
        ext = self.base/'ext'; (ext/'inner').mkdir(parents=True); shutil.copytree(b.root/'snapshots'/sid, ext/sid)
        os.symlink(ext/'inner', snaps/'hop')
        with self.assertRaises(PublicationError) as ctx: verify(snaps/'hop'/'..'/sid)
        self.assertEqual(ctx.exception.state, 'symlinked-entry')
        # A path outside any store that resolves into a store entry is ledger-checked, never standalone.
        alias = self.base/'alias'; os.symlink(snaps/sid, alias)
        self.assertEqual(verified(alias)['publication']['status'], 'ledgered')
        # A whole store reached through a symlinked folder (store relocated to another volume) is still ledger-checked.
        moved = self.base/'volume'; moved.mkdir(); os.symlink(snaps, moved/'snapshots')
        v = verified(Config(moved).root/'snapshots'/sid); self.assertEqual(v['publication']['status'], 'ledgered')
        self.assertEqual(verified(resolve_snapshot(Config(moved), sid))['manifest']['manifest_sha256'], ma)
        # A symlinked payload file inside a real store entry is refused, even with identical bytes.
        copy = self.base/'copy'; copy.mkdir(); shutil.copytree(snaps/sid, copy/sid)
        unlock(snaps/sid); real = self.base/'graph.duckdb'; shutil.copy(snaps/sid/'graph.duckdb', real)
        os.unlink(snaps/sid/'graph.duckdb'); os.symlink(real, snaps/sid/'graph.duckdb')
        with self.assertRaises(PublicationError) as ctx: verify(snaps/sid)
        self.assertEqual(ctx.exception.state, 'symlinked-entry')
        code, out = cli(a, 'scope', sid); self.assertEqual(code, 2); self.assertIn('symlink', out)
        # A standalone copy with the same symlinked file verifies by content at its own path, labelled standalone.
        unlock(copy/sid); os.unlink(copy/sid/'graph.duckdb'); os.symlink(real, copy/sid/'graph.duckdb')
        self.assertEqual(verified(copy/sid)['publication']['status'], 'standalone-not-ledger-checked')
        # A folder with only a lock (ledger deleted) is still a store: reads refuse.
        (self.base/'lockonly').mkdir(); shutil.copytree(copy/sid, self.base/'lockonly'/sid, symlinks=True)
        (self.base/'lockonly'/'.publication.lock').touch()
        with self.assertRaises(PublicationError) as ctx: verify(self.base/'lockonly'/sid)
        self.assertEqual(ctx.exception.state, 'not-in-ledger')

    def test_dangling_symlink_and_symlinked_dest_on_writer_and_recovery_side(self):
        cfg = Config(self.base/'s'); sid = import_source('ebl', FIX, cfg, dry_run=True)['snapshot']
        (cfg.root/'snapshots').mkdir(parents=True)
        os.symlink(self.base/'nowhere', cfg.root/'snapshots'/sid)
        with self.assertRaises(PublicationError) as ctx: import_source('ebl', FIX, cfg)
        self.assertEqual(ctx.exception.state, 'unledgered')
        (cfg.root/'snapshots'/sid).unlink()
        # Kill after rename, then swap the reserved directory for a symlink to the same bytes: no recovery action.
        p = run_child(cfg.root, kill='after-rename'); p.communicate(); self.assertEqual(p.returncode, 137)
        moved = self.base/'moved'; os.chmod(cfg.root/'snapshots'/sid, 0o755)   # macOS: moving a directory needs write on it
        os.rename(cfg.root/'snapshots'/sid, moved); os.symlink(moved, cfg.root/'snapshots'/sid)
        code, plan = cli(cfg, 'publication-recover', sid)
        self.assertEqual((code, plan['actions'], plan['directory'].get('symlink')), (0, [], True))
        code, out = cli(cfg, 'publication-recover', sid, '--action', 'commit', '--reason', 'test'); self.assertEqual(code, 2)
        (cfg.root/'snapshots'/sid).unlink(); os.rename(moved, cfg.root/'snapshots'/sid)
        code, done = cli(cfg, 'publication-recover', sid, '--action', 'commit', '--reason', 'test: real directory restored')
        self.assertEqual(done['state_after'], 'published')

    # ---- R4: typed refusal for an absent store entry ----
    def test_absent_entry_refusals_are_typed(self):
        cfg = Config(self.base/'s'); sid = import_source('ebl', FIX, cfg, dry_run=True)['snapshot']
        p = run_child(cfg.root, kill='after-reserve'); p.communicate(); self.assertEqual(p.returncode, 137)
        self.assertFalse((cfg.root/'snapshots'/sid).exists())
        for call in (lambda: resolve_snapshot(cfg, sid), lambda: verify(store_path(cfg, sid)), lambda: verified(cfg.root/'snapshots'/sid)):
            with self.assertRaises(PublicationError) as ctx: call()
            self.assertEqual(ctx.exception.state, 'reserved')
        code, out = cli(cfg, 'manifest', sid); self.assertEqual(code, 2); self.assertIn('publication-recover', out)
        other = 'snapshot:' + '0'*32
        with self.assertRaises(PublicationError) as ctx: resolve_snapshot(cfg, other)
        self.assertEqual(ctx.exception.state, 'not-found')
        cli(cfg, 'publication-recover', sid, '--action', 'complete', '--reason', 'test')
        unlock(cfg.root/'snapshots'/sid); shutil.rmtree(cfg.root/'snapshots'/sid)
        with self.assertRaises(PublicationError) as ctx: resolve_snapshot(cfg, sid)
        self.assertEqual(ctx.exception.state, 'published-missing')
        with self.assertRaises(FileNotFoundError): verify(self.base/'not-a-store'/sid)   # outside a store: unchanged

    # ---- R3: a writer inside another live writer's reserve->commit window waits, then reuses ----
    def test_writer_and_recovery_inside_live_reserve_commit_window(self):
        cfg = Config(self.base/'s'); sid = import_source('ebl', FIX, cfg, dry_run=True)['snapshot']
        env = {k: v for k, v in os.environ.items() if k not in (KILL_ENV, PAUSE_ENV)}
        child = """
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from cuneiform.storage import Config, import_source
r = import_source('ebl', Path(sys.argv[2]), Config(Path(sys.argv[3])))
print(json.dumps({'reused': r['reused'], 'raced': r.get('raced', False), 'manifest_sha256': r['manifest']['manifest_sha256']}))
"""
        a = subprocess.Popen([sys.executable, '-B', '-c', child, str(ROOT), str(FIX), str(cfg.root)], env=dict(env, **{PAUSE_ENV: 'after-rename:5'}),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        ledger = cfg.root/'snapshots'/LEDGER
        deadline = time.time() + 60
        while time.time() < deadline and not (ledger.exists() and '"reserve"' in ledger.read_text() and (cfg.root/'snapshots'/sid).exists()): time.sleep(0.02)
        self.assertEqual(Ledger(cfg.root/'snapshots').status(sid).state, 'reserved')   # A is inside its window
        b = subprocess.Popen([sys.executable, '-B', '-c', child, str(ROOT), str(FIX), str(cfg.root)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        rec = subprocess.Popen([sys.executable, '-B', '-m', 'cuneiform', '--root', str(cfg.root), 'publication-recover', sid, '--action', 'commit', '--reason', 'race'],
                               cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        oa, ea = a.communicate(timeout=120); ob, eb = b.communicate(timeout=120); orc, erc = rec.communicate(timeout=120)
        self.assertEqual((a.returncode, b.returncode), (0, 0), (ea, eb))
        ra, rb = json.loads(oa), json.loads(ob)
        self.assertEqual((ra['reused'], rb['reused']), (False, True))
        self.assertEqual(ra['manifest_sha256'], rb['manifest_sha256'])
        # Recovery waited for the live writer's build lock and then found nothing to recover; it never committed.
        self.assertEqual(rec.returncode, 2); self.assertIn('no open reservation', erc)
        events = [json.loads(l).get('event') for l in ledger.read_text().splitlines()]
        self.assertEqual(events, ['reserve', 'commit'])

    # ---- R5: final modes are flushed ----
    def test_seal_fsyncs_after_final_modes(self):
        stage = self.base/'.pending-x'; (stage/'parquet').mkdir(parents=True)
        for name in ('raw', 'parquet/a.parquet', 'manifest.json'): (stage/name).write_bytes(b'x')
        log = []
        real_chmod, real_fsync = os.chmod, os.fsync
        def chmod(p, mode, *a, **k): log.append(('chmod', str(p))); return real_chmod(p, mode, *a, **k)
        def fsync_file(fd): log.append(('fsync', fd)); return real_fsync(fd)
        with mock.patch('os.chmod', chmod), mock.patch.object(publication.os, 'fsync', fsync_file):
            publication.seal(stage)
        first_fsync = next(i for i, e in enumerate(log) if e[0] == 'fsync')
        self.assertEqual(log[0][0], 'chmod'); self.assertLess(0, first_fsync)
        self.assertEqual(sum(1 for e in log if e[0] == 'chmod'), 5)   # 3 files, parquet/, the stage
        self.assertTrue(all(os.stat(p).st_mode & 0o222 == 0 for p in [stage, *stage.rglob('*')]))
        # Every chmod is followed (eventually) by an fsync: the last event is an fsync of the stage directory.
        self.assertEqual(log[-1][0], 'fsync')
        stage2 = self.base/'.pending-y'; stage2.mkdir(); os.symlink(stage/'raw', stage2/'raw')
        with self.assertRaises(PublicationError) as ctx: publication.seal(stage2)
        self.assertEqual(ctx.exception.state, 'symlinked-entry')


@unittest.skipUnless(DISK, 'disk verification explicitly gated')
class CohortPublicationTests(unittest.TestCase):
    def setUp(self):
        admission_config().guard(256*MiB)
        self.tmp = tempfile.TemporaryDirectory(prefix='cohort-pub-test-', dir=RUNTIME/'scratch')
        self.base = Path(self.tmp.name)
        rows = json.loads(FIX.read_text()); rows = rows['fragments'] if isinstance(rows, dict) else rows
        path = write_parent(self.base, rows)
        self.cfg = Config(self.base/'root')
        self.raw = self.cfg.root/'raw'/'sha256'/digest(path.read_bytes()); self.raw.parent.mkdir(parents=True); shutil.copy(path, self.raw)
        self.parent = {'sha256': digest(path.read_bytes()), 'url': 'synthetic:parent', 'receipt_id': 'receipt:synthetic', 'rights': {'status': 'synthetic'}}
        self.out = self.cfg.root/'derived'/'cohorts'

    def tearDown(self):
        unlock(self.base); self.tmp.cleanup()

    def child(self, kill=None, pause=None, start=0.0):
        env = {k: v for k, v in os.environ.items() if k not in (KILL_ENV, PAUSE_ENV)}
        if kill: env[KILL_ENV] = kill
        if pause: env[PAUSE_ENV] = pause
        return subprocess.Popen([sys.executable, '-B', '-c', COHORT_CHILD, str(ROOT), str(self.raw), json.dumps(self.parent), str(self.out), str(start)],
                                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def cid(self):
        from cuneiform.corpus import cohort_identity, RULE_DEFAULT
        return cohort_identity(self.parent, RULE_DEFAULT, 1)

    def ledger_rows(self):
        path = self.out/LEDGER
        return [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []

    # ---- R2: review c21, kill after rename; reads, audit and import refuse; explicit recovery binds the bytes ----
    def test_kill_after_rename_cohort_refused_then_recovered_with_byte_binding(self):
        from cuneiform.corpus import build_cohort, verify_cohort, RULE_DEFAULT
        from cuneiform.storage import import_cohort
        p = self.child(kill='after-rename'); p.communicate(); self.assertEqual(p.returncode, 137)
        cid = self.cid(); d = self.out/cid.replace(':', '-')
        self.assertTrue(d.is_dir()); self.assertEqual([r['event'] for r in self.ledger_rows()], ['reserve'])
        before = tree(d)
        for mode in ('auto', 'store', 'require'):
            with self.assertRaises(PublicationError) as ctx: verify_cohort(d, self.raw, ledger=mode)
            self.assertEqual(ctx.exception.state, 'reserved')
            self.assertIn(f'publication-recover {cid} --store cohorts', str(ctx.exception))
        for args in (('corpus-audit', cid), ('corpus-audit', cid, '--markdown'), ('corpus-import', cid)):
            code, out = cli(self.cfg, *args); self.assertEqual(code, 2, args); self.assertIn('--store cohorts', out)
        with self.assertRaises(PublicationError) as ctx: import_cohort(d, self.cfg, parent_path=self.raw)
        self.assertEqual(ctx.exception.state, 'reserved')
        self.assertFalse((self.cfg.root/'snapshots').exists())   # nothing was built from the uncommitted cohort
        with self.assertRaises(PublicationError) as ctx: build_cohort(self.raw, self.parent, 1, self.out, RULE_DEFAULT)
        self.assertEqual(ctx.exception.state, 'reserved')
        code, status = cli(self.cfg, 'publication-status', '--store', 'cohorts')
        self.assertEqual((status['cohorts'][0]['state'], status['cohorts'][0]['recovery']['actions']), ('reserved', ['commit']))
        self.assertEqual(status['cohorts'][0]['recovery']['directory']['matches_reservation'], True)
        # The snapshot store's verbs do not see cohort IDs.
        code, out = cli(self.cfg, 'publication-recover', cid); self.assertEqual(code, 2); self.assertIn('invalid snapshot ID', out)
        code, out = cli(self.cfg, 'publication-recover', cid, '--store', 'cohorts', '--action', 'abandon', '--reason', 'x'); self.assertEqual(code, 2)
        code, done = cli(self.cfg, 'publication-recover', cid, '--store', 'cohorts', '--action', 'commit', '--reason', 'test: verified after kill')
        self.assertEqual((code, done['state_after']), (0, 'published'))
        self.assertEqual(tree(d), before)   # recovery did not touch the cohort bytes or modes
        reserve, commit = self.ledger_rows()
        m = verify_cohort(d, self.raw, ledger='require')
        self.assertEqual(m['publication']['status'], 'ledgered-recovered')
        self.assertEqual((m['manifest_sha256'], commit['manifest_sha256'], commit['manifest_file_sha256']),
                         (reserve['manifest_sha256'], reserve['manifest_sha256'], reserve['manifest_file_sha256']))
        self.assertEqual(hashlib.sha256((d/'manifest.json').read_bytes()).hexdigest(), reserve['manifest_file_sha256'])
        code, report = cli(self.cfg, 'corpus-audit', cid); self.assertEqual((code, report['publication']['status']), (0, 'ledgered-recovered'))
        code, imported = cli(self.cfg, 'corpus-import', cid); self.assertEqual((code, imported['reused']), (0, False))
        self.assertEqual(build_cohort(self.raw, self.parent, 1, self.out, RULE_DEFAULT)['manifest_sha256'], reserve['manifest_sha256'])

    def test_kill_after_reserve_cohort_complete_and_discard(self):
        from cuneiform.corpus import build_cohort, verify_cohort, RULE_DEFAULT
        p = self.child(kill='after-reserve'); p.communicate(); self.assertEqual(p.returncode, 137)
        cid = self.cid(); d = self.out/cid.replace(':', '-')
        with self.assertRaises(PublicationError) as ctx: verify_cohort(d)
        self.assertEqual(ctx.exception.state, 'reserved')   # R4: absent entry, typed
        code, plan = cli(self.cfg, 'publication-recover', cid, '--store', 'cohorts')
        self.assertEqual(plan['actions'], ['complete', 'discard'])
        code, done = cli(self.cfg, 'publication-recover', cid, '--store', 'cohorts', '--action', 'complete', '--reason', 'test: stage intact')
        self.assertEqual(done['state_after'], 'published')
        reserve = self.ledger_rows()[0]
        m = verify_cohort(d, self.raw)
        self.assertEqual((m['manifest_sha256'], m['publication']['status']), (reserve['manifest_sha256'], 'ledgered-recovered'))
        # Discard path on a second interrupted build of another size: the ID is free again and rebuilds.
        other = Config(self.base/'root2'); out2 = other.root/'derived'/'cohorts'
        env = {k: v for k, v in os.environ.items() if k not in (KILL_ENV, PAUSE_ENV)}
        p = subprocess.Popen([sys.executable, '-B', '-c', COHORT_CHILD, str(ROOT), str(self.raw), json.dumps(self.parent), str(out2), '0'],
                             env=dict(env, **{KILL_ENV: 'after-reserve'}), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        p.communicate()
        code, done = cli(other, 'publication-recover', cid, '--store', 'cohorts', '--action', 'discard', '--reason', 'test')
        self.assertEqual(done['state_after'], 'aborted'); self.assertEqual(list(out2.glob('.pending-*')), [])
        self.assertEqual(build_cohort(self.raw, self.parent, 1, out2, RULE_DEFAULT)['publication']['status'], 'ledgered')

    def test_unrecorded_symlinked_misplaced_and_pre_ledger_cohorts(self):
        from cuneiform.corpus import build_cohort, verify_cohort, RULE_DEFAULT
        m = build_cohort(self.raw, self.parent, 1, self.out, RULE_DEFAULT); cid = m['cohort_id']; d = self.out/cid.replace(':', '-')
        self.assertEqual(m['publication']['status'], 'ledgered')
        # Pre-ledger cohort store (no ledger, no lock): explicit store reads label it; require refuses; auto calls it standalone.
        legacy = self.base/'legacy'/'derived'/'cohorts'; legacy.mkdir(parents=True); shutil.copytree(d, legacy/d.name)
        self.assertEqual(verify_cohort(legacy/d.name, ledger='store')['publication']['status'], 'unledgered-pre-ledger-cohort-store')
        self.assertEqual(verify_cohort(legacy/d.name)['publication']['status'], 'standalone-not-ledger-checked')
        with self.assertRaises(PublicationError) as ctx: verify_cohort(legacy/d.name, ledger='require')
        self.assertEqual(ctx.exception.state, 'not-in-ledger')
        code, report = cli(Config(self.base/'legacy'), 'corpus-audit', cid)
        self.assertEqual((code, report['publication']['status']), (0, 'unledgered-pre-ledger-cohort-store'))
        # The same unrecorded cohort inside a ledgered store is refused until adopted explicitly.
        other = Config(self.base/'o'); out2 = other.root/'derived'/'cohorts'; out2.mkdir(parents=True)
        (out2/LEDGER).write_text(''); shutil.copytree(d, out2/d.name)
        with self.assertRaises(PublicationError) as ctx: verify_cohort(out2/d.name)
        self.assertEqual(ctx.exception.state, 'not-in-ledger'); self.assertIn('--store cohorts', str(ctx.exception))
        with self.assertRaises(PublicationError): build_cohort(self.raw, self.parent, 1, out2, RULE_DEFAULT)
        code, adopted = cli(other, 'publication-adopt', cid, '--store', 'cohorts', '--reason', 'test: exact copy')
        self.assertEqual(code, 0, adopted)
        self.assertEqual(verify_cohort(out2/d.name)['publication']['status'], 'adopted')
        # Misplaced: directory named for cohort X holding another cohort's manifest; adopt and reads refuse.
        m3 = build_cohort(self.raw, self.parent, None, self.out, RULE_DEFAULT); d3 = self.out/m3['cohort_id'].replace(':', '-')
        third = Config(self.base/'t'); out3 = third.root/'derived'/'cohorts'; out3.mkdir(parents=True); (out3/LEDGER).write_text('')
        shutil.copytree(d3, out3/d.name)
        code, out = cli(third, 'publication-adopt', cid, '--store', 'cohorts', '--reason', 'x'); self.assertEqual(code, 2); self.assertIn('identity mismatch', out)
        with self.assertRaises(PublicationError) as ctx: verify_cohort(out3/d.name)
        self.assertEqual(ctx.exception.state, 'misplaced')
        # Symlinked cohort entry in a ledgered store: refused; the symlink target alone stays standalone.
        ext = self.base/'ext'; ext.mkdir(); shutil.copytree(d, ext/d.name)
        unlock(d); shutil.rmtree(d); os.symlink(ext/d.name, d)
        with self.assertRaises(PublicationError) as ctx: verify_cohort(d)
        self.assertEqual(ctx.exception.state, 'symlinked-entry')
        code, out = cli(self.cfg, 'corpus-audit', cid); self.assertEqual(code, 2); self.assertIn('symlink', out)
        self.assertEqual(verify_cohort(ext/d.name)['publication']['status'], 'standalone-not-ledger-checked')
        code, status = cli(self.cfg, 'publication-status', '--store', 'cohorts'); self.assertEqual(status['symlinked_entries'], [d.name])

    # ---- R3 for cohorts: concurrent builders of one cohort build it once ----
    def test_concurrent_cohort_builders_build_once(self):
        start = time.time() + 1.5
        procs = [self.child(start=start) for _ in range(3)]
        outs = [p.communicate(timeout=120) for p in procs]
        self.assertEqual([p.returncode for p in procs], [0, 0, 0], [e for _, e in outs])
        results = [json.loads(o) for o, _ in outs]
        self.assertEqual(len({r['manifest_sha256'] for r in results}), 1)
        self.assertEqual([r['event'] for r in self.ledger_rows()], ['reserve', 'commit'])
        self.assertEqual([p.name for p in self.out.iterdir() if not p.name.startswith('.')], [self.cid().replace(':', '-')])
        self.assertEqual(list(self.out.glob('.pending-*')), [])
        # A builder arriving while another is held inside its reserve->commit window waits and reuses.
        other = self.base/'root3'/'derived'/'cohorts'
        self.out = other
        a = self.child(pause='after-rename:2')
        deadline = time.time() + 60
        while time.time() < deadline and not ((other/LEDGER).exists() and '"reserve"' in (other/LEDGER).read_text()): time.sleep(0.02)
        b = self.child()
        (oa, ea), (ob, eb) = a.communicate(timeout=120), b.communicate(timeout=120)
        self.assertEqual((a.returncode, b.returncode), (0, 0), (ea, eb))
        self.assertEqual(json.loads(oa)['manifest_sha256'], json.loads(ob)['manifest_sha256'])
        self.assertEqual([r['event'] for r in self.ledger_rows()], ['reserve', 'commit'])


if __name__ == '__main__':
    unittest.main()
