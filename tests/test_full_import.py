"""Q-023 full-import regressions: per-record parent accounting (cohort-2), all-eligible scope label, projection ceilings,
the mid-build free-space guard, and memory-limit validation.

Disk tests need CUNEIFORM_RUN_DISK_TESTS=1 and write only into their own temporary tree under the runtime scratch.
"""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock
from cuneiform import storage
from cuneiform.corpus import accounting, build_cohort, iter_array, verify_cohort, RULE_DEFAULT
from cuneiform.model import canonical, digest
from cuneiform.projections import HARD_MAX_POSITIONS, HARD_MAX_ROWS, ProjectionConfig
from cuneiform.storage import FULL_PROJECTIONS, Config, MiB

from tests.test_corpus_pilot import ROOT, RUNTIME, DISK, write_parent


def admission_config():
    """Runtime-root admission for disk tests: the default task budget, unless CUNEIFORM_TEST_MAX_TOTAL_GIB names an explicit
    larger budget the owner authorized for this root (Q-023: 41 GiB, after the full eBL import). Never lowers the reserve."""
    gib = os.environ.get('CUNEIFORM_TEST_MAX_TOTAL_GIB')
    return Config(RUNTIME, max_total_bytes=int(float(gib) * 1024**3)) if gib else Config(RUNTIME)


def manifest(members, excluded, parent_records, size=None, eligible=None):
    reasons = {}
    for e in excluded: reasons[e['reason']] = reasons.get(e['reason'], 0) + 1
    return {'format': 'cohort-2', 'size': size, 'rule': dict(RULE_DEFAULT), 'parent_records': parent_records,
            'eligible_records': len(members) if eligible is None else eligible, 'excluded_by_reason': reasons,
            'records': [{'parent_index': i} for i in members], 'excluded_records': excluded}


def ex(i, reason='r'):
    return {'parent_index': i, 'reason': reason}


class AccountingTests(unittest.TestCase):
    def test_complete_partition_and_every_defect(self):
        ok = accounting(manifest([0, 2, 3], [ex(1), ex(4, 's')], 5))
        self.assertEqual((ok['status'], ok['members'], ok['excluded_records']), ('complete-partition', 3, 2))
        cases = {'duplicate parent index': manifest([0, 0, 3], [ex(1), ex(4)], 5),
                 'both member and excluded': manifest([0, 1, 3], [ex(1), ex(4)], 5),
                 'out of range': manifest([0, 2, 9], [ex(1), ex(4)], 5),
                 'eligible \\+ excluded': manifest([0, 2], [ex(1), ex(4)], 5),
                 'reasons disagree': dict(manifest([0, 2, 3], [ex(1), ex(4)], 5), excluded_by_reason={'r': 1})}
        for message, m in cases.items():
            with self.subTest(message), self.assertRaisesRegex(ValueError, message): accounting(m)
        sized = accounting(manifest([0], [ex(1)], 5, size=1, eligible=4))
        self.assertEqual((sized['status'], sized['eligible_not_selected']), ('members-plus-excluded', 3))
        self.assertEqual(accounting({'format': 'cohort-1', 'parent_records': 5, 'eligible_records': 4, 'excluded_by_reason': {'r': 1}})['status'], 'reason-totals-only')

    def test_ceilings_and_memory_validation(self):
        FULL_PROJECTIONS.validate()
        self.assertEqual((FULL_PROJECTIONS.max_positions, FULL_PROJECTIONS.max_rows), (HARD_MAX_POSITIONS, HARD_MAX_ROWS))
        with self.assertRaisesRegex(ValueError, 'hard cap'): ProjectionConfig(max_positions=HARD_MAX_POSITIONS + 1).validate()
        with self.assertRaisesRegex(ValueError, 'hard cap'): ProjectionConfig(max_rows=HARD_MAX_ROWS + 1).validate()
        for bad in ("8GB'; SELECT 1; --", '0GB', '8 GB', '100000GB'):
            with self.subTest(bad), self.assertRaisesRegex(ValueError, 'memory limit'):
                storage.import_cohort(Path('/nonexistent'), Config(Path('/nonexistent')), memory=bad)


class BoundedLookupTests(unittest.TestCase):
    def test_partition_first_lookups_equal_the_original_window_filtered_sql(self):
        from cuneiform.adapters import Builder, ingest
        from cuneiform.projections import SCOPES_SQL, build, lookup, source_span
        from cuneiform.storage import validate_graph
        from tests.test_corpus_pilot import memory_db
        db = memory_db()
        ingest(Builder(db, 'snap', 'ebl'), 'ebl', (ROOT/'fixtures/ebl-synthetic.json').read_bytes()); validate_graph(db); build(db)

        def rows(sql, args=()):
            cur = db.execute(sql, args); names = [d[0] for d in cur.description]
            return [dict(zip(names, r)) for r in cur.fetchall()]
        occs = rows('SELECT id, source_record_id, field, start_byte, end_byte, reading FROM ordered_position')
        self.assertGreater(len(occs), 20)
        for o in occs:
            self.assertEqual(lookup(db, 'occurrence', o['id'], limit=5)['rows'], rows('SELECT * FROM ordered_position WHERE id=? ORDER BY id', [o['id']]))
            self.assertEqual(source_span(db, o['source_record_id'], o['field'], o['start_byte'], o['end_byte'] + 4, 50)['rows'],
                             rows('SELECT * FROM ordered_position WHERE source_record_id=? AND field=? AND start_byte<? AND end_byte>? ORDER BY ordinal,position LIMIT 50',
                                  [o['source_record_id'], o['field'], o['end_byte'] + 4, o['start_byte']]))
        self.assertEqual(lookup(db, 'occurrence', 'occurrence:' + '0'*32)['rows'], [])
        self.assertEqual(source_span(db, 'source-record:none', 'atf', 0, 10)['rows'], [])
        self.assertEqual(rows(SCOPES_SQL), rows('SELECT DISTINCT namespace,snapshot_id,field FROM ordered_position ORDER BY 1,2,3'))
        old_postings = ('SELECT p.*,o.sequence_id,o.line_id,o.position,o.witness_id,o.artifact_id,o.source_record_id,o.start_byte,o.end_byte FROM posting p '
                        "JOIN ordered_position o ON o.id=p.occurrence_id WHERE p.namespace=? AND p.snapshot_id=? AND p.field=? AND p.policy='source' "
                        'AND (p.token_id=? OR p.label=?) ORDER BY p.id LIMIT 100')
        for label in {o['reading'] for o in occs if o['reading']}:
            for field in ('atf', 'signs'):
                self.assertEqual(lookup(db, 'postings', label, namespace='ebl', snapshot='snap', field=field, limit=100)['rows'],
                                 rows(old_postings, ['ebl', 'snap', field, label, label]))
        db.close()


@unittest.skipUnless(DISK, 'disk verification explicitly gated')
class FullImportDiskTests(unittest.TestCase):
    def setUp(self):
        admission_config().guard(256*MiB)
        self.tmp = tempfile.TemporaryDirectory(prefix='q023-test-', dir=RUNTIME/'scratch' if (RUNTIME/'scratch').exists() else RUNTIME)
        self.base = Path(self.tmp.name)

    def tearDown(self):
        for dirpath, dirs, files in os.walk(self.base):
            for name in dirs + files: os.chmod(os.path.join(dirpath, name), 0o755)
        self.tmp.cleanup()

    def parent(self):
        rows = json.loads((ROOT/'fixtures/ebl-synthetic.json').read_text())
        rows = (rows['fragments'] if isinstance(rows, dict) else rows) + [
            {'_id': 'DUP', 'atf': '1. A B C A B C A B C D'}, {'_id': 'DUP', 'atf': '1. A B C A B C A B C D'},
            {'_id': 'UNI', 'atf': '1. ša₂ A B C A B C A B C\n2. A ? C', 'signs': 'ABZ1 ABZ2 ABZ3'}, {'_id': 'NOTEXT', 'atf': ''}]
        path = write_parent(self.base, rows, ascii_escape=True)   # \\u escapes in the parent, as in parts of the eBL file
        cfg = Config(self.base/'store'); target = cfg.root/'raw'/'sha256'/digest(path.read_bytes())
        target.parent.mkdir(parents=True); shutil.copy(path, target)
        return target, {'sha256': digest(path.read_bytes()), 'url': 'synthetic:parent', 'label': 'synthetic-release', 'receipt_id': 'receipt:synthetic', 'rights': {'status': 'synthetic'}}, cfg

    def test_all_eligible_cohort_accounts_for_every_parent_record_and_labels_scope(self):
        from cuneiform.persisted import scope
        from cuneiform.query import trace
        path, parent, cfg = self.parent()
        rule = dict(RULE_DEFAULT, min_eligible_positions=3, min_eligible_pairs=1)
        cohort = build_cohort(path, parent, None, cfg.root/'derived'/'cohorts', rule)
        n = sum(1 for _ in iter_array(path))
        acc = accounting(cohort)
        self.assertEqual((cohort['format'], acc['status'], acc['parent_records']), ('cohort-2', 'complete-partition', n))
        indices = sorted([m['parent_index'] for m in cohort['records']] + [e['parent_index'] for e in cohort['excluded_records']])
        self.assertEqual(indices, list(range(n)))
        reasons = {e['source_key']: e['reason'] for e in cohort['excluded_records']}
        self.assertEqual(reasons['DUP'], 'duplicate source key in parent (all copies excluded)')
        self.assertEqual(reasons['NOTEXT'], 'no numbered ATF text line')
        self.assertTrue(verify_cohort(Path(cohort['directory']), path)['verified_parent_slices'])
        # Import with the full preset; scope names the fixed release, eligible count and exclusion reasons.
        result = storage.import_cohort(Path(cohort['directory']), cfg, FULL_PROJECTIONS, parent_path=path)
        snap = storage.store_path(cfg, result['snapshot'])
        sc = scope(snap)
        self.assertEqual(sc['kind'], 'all eligible records of a fixed release')
        self.assertTrue(sc['label'].startswith(f"FULL ELIGIBLE {len(cohort['records']):,}/{n:,} · synthetic-release"))
        self.assertIn('conservative', sc['scope_note']); self.assertIn('not linguistic completeness', sc['scope_note'])
        self.assertEqual(sc['accounting']['status'], 'complete-partition')
        import duckdb
        db = duckdb.connect(str(snap/'graph.duckdb'), read_only=True)
        occ = db.execute("SELECT o.id FROM occurrence o WHERE o.raw='ša₂'").fetchone()[0]; db.close()
        pt = trace(snap, occ, parent_root=cfg.root)['parent_trace']
        self.assertEqual((pt['status'], pt['parent_file_fragment']), ('verified', '\\u0161a\\u2082'))
        # Tampering with one excluded record's accounting is detected even when the manifest digest is re-signed.
        moved = self.base/'tampered'; shutil.copytree(cohort['directory'], moved)
        for p in (moved, moved/'manifest.json'): os.chmod(p, 0o755)
        m = json.loads((moved/'manifest.json').read_text()); m.pop('manifest_sha256'); m.pop('publication', None); m.pop('directory', None); m.pop('verified_parent_slices', None)
        m['excluded_records'][0]['record_sha256'] = '0'*64
        m['manifest_sha256'] = digest(canonical(m).encode()); (moved/'manifest.json').write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError, 'excluded parent slice mismatch'): verify_cohort(moved, path, ledger='skip')
        m['excluded_records'] = m['excluded_records'][1:]; m.pop('manifest_sha256'); m['manifest_sha256'] = digest(canonical(m).encode())
        (moved/'manifest.json').write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError, 'cohort accounting'): verify_cohort(moved, path, ledger='skip')

    def test_free_space_guard_refuses_mid_build_and_publishes_nothing(self):
        path, parent, cfg = self.parent()
        rule = dict(RULE_DEFAULT, min_eligible_positions=3, min_eligible_pairs=1)
        cohort = build_cohort(path, parent, None, cfg.root/'derived'/'cohorts', rule)
        real = shutil.disk_usage
        free = {'n': 0}
        def shrinking(p):
            u = real(p); free['n'] += 1
            # Admission sees ample space; every later mid-build check sees the reserve gone.
            return u if free['n'] <= 1 else type(u)(u.total, u.total, 0)
        with mock.patch.object(storage.shutil, 'disk_usage', shrinking), self.assertRaisesRegex(ValueError, 'free-space reserve reached during build'):
            storage.import_cohort(Path(cohort['directory']), Config(cfg.root, reserve_bytes=1), FULL_PROJECTIONS, parent_path=path, batch=1)
        snaps = cfg.root/'snapshots'
        self.assertEqual(sorted(p.name for p in snaps.iterdir() if not p.name.startswith('.locks')), ['.publication-ledger.jsonl'] if (snaps/'.publication-ledger.jsonl').exists() else [])
        self.assertEqual(list(snaps.glob('.pending-*')), [])
        self.assertEqual(list(snaps.glob('snapshot:*')), [])


if __name__ == '__main__':
    unittest.main()
