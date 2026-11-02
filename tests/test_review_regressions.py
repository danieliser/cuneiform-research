import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from test_foundation import build
from cuneiform.query import motif
from cuneiform.model import SCHEMA_VERSION
from cuneiform.storage import Config, import_source, read_bounded, verify

class ReviewRegressions(unittest.TestCase):
    def test_unsupported_spans_block_interior(self):
        for text in ['<<A B C D>>', '{(A B C D)}']:
            db=build(data=json.dumps({'_id':'T','atf':'1. '+text}).encode())
            try:
                self.assertEqual(motif(db,['B','C'])['occurrences'],0)
                self.assertEqual(db.execute('select count(*) from exclusion').fetchone()[0],4)
            finally: db.close()

    def test_translation_extent_and_unrecognized_accounting(self):
        db=build(data=json.dumps({'_id':'T','atf':'1. A B\n#tr.en.(1): translation\n#tr.invalid syntax'}).encode())
        try:
            self.assertEqual(db.execute('select text,granularity from translation_segment').fetchall(), [('translation','unresolved-span')])
            self.assertEqual(db.execute('select count(*) from exclusion').fetchone()[0],1)
        finally: db.close()

    def test_incomplete_manifest_rejected(self):
        with patch.object(Path,'read_text',return_value=json.dumps({'schema_version':SCHEMA_VERSION,'files':{}})):
            with self.assertRaisesRegex(ValueError,'incomplete manifest'): verify(Path('/nonexistent'))

    def test_input_bounded_and_single_read(self):
        cfg=Config(Path('/nonexistent'),max_input_bytes=100)
        with patch.object(Path,'open',return_value=io.BytesIO(b'x'*101)):
            with self.assertRaisesRegex(ValueError,'input exceeds'): read_bounded(Path('unused'),cfg)
        data=b'{"_id":"T","atf":"1. A B"}'
        with patch.object(Path,'open',return_value=io.BytesIO(data)) as opened, patch.object(Path,'exists',return_value=False), patch.object(Config,'guard'):
            result=import_source('ebl',Path('unused'),cfg,dry_run=True)
            self.assertEqual(result['bytes'],len(data))
            self.assertEqual(opened.call_count,1)
