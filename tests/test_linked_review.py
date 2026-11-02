import unittest
from test_foundation import build as database
from cuneiform.adapters import Builder, ingest
from cuneiform.model import digest
from cuneiform.projections import build, lookup
from cuneiform.query import motif, array_count, trace_rows

class LinkedReviewTests(unittest.TestCase):
    def test_wrong_source_and_manifest_rejected(self):
        first=b'{"_id":"FIRST","atf":"1. A B"}'
        second=b'{"_id":"SECOND","atf":"1. A C"}'
        db=database(data=first)
        try:
            oid=db.execute('SELECT id FROM occurrence WHERE position=0').fetchone()[0]
            with self.assertRaisesRegex(ValueError,'binding'):
                trace_rows(db,second,{'source':'ebl','raw_sha256':digest(second),'rights':{}},oid)
            with self.assertRaisesRegex(ValueError,'hash'):
                trace_rows(db,first,{'source':'ebl','raw_sha256':digest(second),'rights':{}},oid)
            result=trace_rows(db,first,{'source':'ebl','raw_sha256':digest(first),'rights':{}},oid)
            self.assertIn('caller-supplied',result['rights_attribution'])
        finally: db.close()

    def test_multiple_text_scopes_refused(self):
        db=database(data=b'{"_id":"FIRST","atf":"1. A B C"}')
        try:
            ingest(Builder(db,'other-snapshot','other'),'ebl',b'{"_id":"SECOND","atf":"1. A B C"}')
            for fn in [motif,array_count]:
                with self.assertRaisesRegex(ValueError,'multiple query scopes'): fn(db,['A','B','C'])
            build(db)
            self.assertEqual(lookup(db,'motifs','["A","B","C"]',namespace='ebl',snapshot='test-snapshot')['count'],1)
        finally: db.close()

    def test_strict_opaque_wildcard_parity(self):
        db=database(data=b'{"_id":"T","atf":"1. A |B.C| D"}')
        try:
            db.execute("UPDATE occurrence SET preservation='intact',certainty='certain'")
            build(db)
            self.assertEqual(motif(db,['A','?','D'],strict=True)['occurrences'],0)
            self.assertEqual(lookup(db,'motifs','["A","?","D"]',namespace='ebl',snapshot='test-snapshot',policy='strict')['count'],0)
            self.assertEqual(motif(db,['A','?','D'])['occurrences'],1)
        finally: db.close()
