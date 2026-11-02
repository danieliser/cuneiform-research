import json
from pathlib import Path
import unittest
from test_foundation import build, ROOT
from cuneiform.adapters import RIGHTS
from cuneiform.model import digest
from cuneiform.query import trace_rows
from cuneiform.storage import Config, import_source, inspect

class TraceAdmissionTests(unittest.TestCase):
    def test_trace_resolves_source_and_unknowns(self):
        raw=(ROOT/'fixtures/ebl-synthetic.json').read_bytes();db=build()
        try:
            oid=db.execute("SELECT id FROM occurrence WHERE raw='{d}EN.LIL₂'").fetchone()[0]
            trace=trace_rows(db,raw,{'source':'ebl','raw_sha256':digest(raw),'rights':RIGHTS['ebl']},oid)
            self.assertEqual(trace['resolved_raw'],'{d}EN.LIL₂')
            self.assertEqual(trace['token']['kind'],'unsupported')
            self.assertEqual(trace['words'],[])
            self.assertEqual(trace['record_locator'],'/fragments/0')
            with self.assertRaisesRegex(ValueError,'unknown'):trace_rows(db,raw,{},'unknown')
        finally: db.close()

    def test_dry_run_reports_block_without_writes(self):
        root=ROOT/'must-not-be-created'
        result=import_source('ebl',ROOT/'fixtures/ebl-synthetic.json',Config(root,reserve_bytes=10**18),dry_run=True)
        self.assertIn('reserve',result['admission'])
        self.assertGreater(result['estimated_additional_bytes'],result['bytes'])
        self.assertFalse(root.exists())

    def test_input_cap_before_loading(self):
        with self.assertRaisesRegex(ValueError,'cap'):inspect('ebl',ROOT/'fixtures/ebl-synthetic.json',Config(ROOT,max_input_bytes=10))
