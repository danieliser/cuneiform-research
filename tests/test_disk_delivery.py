"""Run only after reserve is restored: CUNEIFORM_RUN_DISK_TESTS=1 python -m unittest ..."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import duckdb
from cuneiform.storage import Config, import_source, resolve_snapshot, verify, MiB
from cuneiform.query import motif, trace

ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(os.environ.get('CUNEIFORM_RUN_DISK_TESTS')=='1','disk verification explicitly gated; 3 GiB reserve required')
class DiskDeliveryTests(unittest.TestCase):
    def test_snapshot_idempotence_relocation_parquet_and_tamper(self):
        base=Path.home()/'.local/share/cuneiform-research'
        # Default task budget unless CUNEIFORM_TEST_MAX_TOTAL_GIB names an explicit authorized one (Q-023: 41 GiB).
        gib=os.environ.get('CUNEIFORM_TEST_MAX_TOTAL_GIB')
        (Config(base,max_total_bytes=int(float(gib)*1024**3)) if gib else Config(base)).guard(64*MiB)
        # Only this test-owned tree is removed; never unrelated runtime data.
        with tempfile.TemporaryDirectory(prefix='disk-test-',dir=base) as directory:
            root=Path(directory)
            cfg=Config(root/'store')
            first=import_source('ebl',ROOT/'fixtures/ebl-synthetic.json',cfg)
            again=import_source('ebl',ROOT/'fixtures/ebl-synthetic.json',cfg)
            self.assertEqual(first['snapshot'],again['snapshot']);self.assertTrue(again['reused'])
            snapshot=resolve_snapshot(cfg,first['snapshot'])
            before=(snapshot/'manifest.json').read_bytes()
            changed=root/'changed.json'
            changed.write_bytes((ROOT/'fixtures/ebl-synthetic.json').read_bytes()+b'\n')
            newer=import_source('ebl',changed,cfg)
            self.assertNotEqual(first['snapshot'],newer['snapshot'])
            self.assertEqual(before,(snapshot/'manifest.json').read_bytes())
            relocated=root/'relocated'
            shutil.copytree(snapshot,relocated)
            self.assertEqual(verify(snapshot),verify(relocated))
            result=motif(relocated,['A','B','C'])
            self.assertEqual(result['occurrences'],6)
            self.assertEqual(trace(relocated,result['matches'][0]['occurrences'][0])['resolved_raw'],'A')
            db=duckdb.connect(':memory:')
            try:
                for table,count in first['manifest']['counts'].items():
                    observed=db.execute('SELECT count(*) FROM read_parquet(?)',[str(relocated/'parquet'/f'{table}.parquet')]).fetchone()[0]
                    self.assertEqual(count,observed)
            finally: db.close()
            # Published payloads are read-only; tampering requires an explicit permission change.
            with self.assertRaises(PermissionError): (relocated/'raw').write_bytes(b'tampered')
            os.chmod(relocated,0o755); os.chmod(relocated/'raw',0o644)
            (relocated/'raw').write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError,'integrity'): verify(relocated)
