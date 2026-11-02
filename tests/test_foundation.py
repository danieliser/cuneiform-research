import csv
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import duckdb
from cuneiform.adapters import Builder, ingest
from cuneiform.model import identity
from cuneiform.query import motif, array_count
from cuneiform.storage import Config, validate_graph, fetch

ROOT=Path(__file__).resolve().parents[1]


def build(source='ebl', data=None, namespace=None):
    db=duckdb.connect(':memory:')
    db.execute("SET memory_limit='64MB'")
    db.execute("SET threads=1")
    db.execute("SET max_temp_directory_size='0B'")
    db.execute((ROOT/'cuneiform/schema.sql').read_text())
    if data is None: data=(ROOT/'fixtures/ebl-synthetic.json').read_bytes()
    ingest(Builder(db,'test-snapshot',namespace or source),source,data)
    validate_graph(db)
    return db


class FoundationTests(unittest.TestCase):
    def setUp(self): self.db=build()
    def tearDown(self): self.db.close()

    def test_expected_counts_and_array_graph_parity(self):
        expected={('A','B','C'):6,('A','C'):0,('A','?','C'):11,('A','B','C','A'):1,('A','B','C','A','B'):1}
        for pattern,count in expected.items():
            with self.subTest(pattern=pattern):
                self.assertEqual(array_count(self.db,list(pattern)),count)
                self.assertEqual(motif(self.db,list(pattern))['occurrences'],count)

    def test_gaps_unknown_and_exclusions_never_bridge(self):
        self.assertEqual(motif(self.db,['A','C'])['occurrences'],0)
        self.assertEqual(motif(self.db,['A','C'],max_skip=1)['occurrences'],11)
        self.assertEqual(motif(self.db,['A','B','C'],strict=True)['occurrences'],0)
        self.assertGreater(self.db.execute('SELECT count(*) FROM exclusion').fetchone()[0],0)
        self.assertEqual(self.db.execute("SELECT count(*) FROM occurrence WHERE raw IN ('B/C','{d}EN.LIL₂','|KA×A|') AND kind='unsupported'").fetchone()[0],3)

    def test_strict_exclusions_do_not_rewire_next(self):
        # Explicit synthetic evidence assignment, never asserted for actual eBL data.
        self.db.execute("UPDATE occurrence SET preservation='intact',certainty='certain' WHERE preservation='unknown' AND certainty='unmarked'")
        self.assertEqual(motif(self.db,['A','B','C'],strict=True)['occurrences'],3)
        self.assertEqual(motif(self.db,['A','C'],strict=True)['occurrences'],0)

    def test_rejections_and_no_alias_merge(self):
        self.assertEqual(self.db.execute('SELECT count(*) FROM rejection').fetchone()[0],2)
        self.assertEqual(self.db.execute('SELECT count(*) FROM artifact').fetchone()[0],2)
        self.assertEqual(self.db.execute("SELECT count(*) FROM claim WHERE object_key='cdli:P000001'").fetchone()[0],2)
        self.assertEqual(motif(self.db,['A','B','C'])['artifacts'],2)

    def test_source_utf8_roundtrip_all_positions(self):
        for raw,start,end,field,source in self.db.execute('SELECT t.raw,t.start_byte,t.end_byte,t.field,s.raw_json FROM token_context t JOIN source_record s ON s.id=t.source_record_id').fetchall():
            self.assertEqual(json.loads(source)[field].encode()[start:end].decode(),raw)

    def test_deterministic_ids_and_empty_unavailable_layers(self):
        other=build()
        try: self.assertEqual(self.db.execute('SELECT * FROM nodes ORDER BY id').fetchall(),other.execute('SELECT * FROM nodes ORDER BY id').fetchall())
        finally: other.close()
        for table in ('composition','passage','word_token','lemma','sense'):
            self.assertEqual(self.db.execute(f'SELECT count(*) FROM {table}').fetchone()[0],0)
        self.assertEqual(identity('source','ebl','record'),identity('source','ebl','record'))

    def test_translation_granularity_and_sign_derivation(self):
        self.assertEqual(self.db.execute('SELECT DISTINCT granularity FROM translation_segment').fetchall(),[('unresolved-span',)])
        self.assertEqual(self.db.execute("SELECT count(*) FROM edge WHERE kind='TRANSLATES'").fetchone()[0],0)
        self.assertEqual(self.db.execute("SELECT count(*) FROM edge WHERE kind='MAPS_TO_SIGN'").fetchone()[0],5)

    def test_cdli_duplicate_labels_stay_separate(self):
        db=build('cdli',(ROOT/'fixtures/cdli-synthetic.csv').read_bytes())
        try:
            self.assertEqual(db.execute('SELECT count(*) FROM artifact').fetchone()[0],2)
            self.assertEqual(db.execute('SELECT count(*) FROM witness').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT count(*) FROM claim').fetchone()[0],4)
        finally: db.close()

    def test_oracc_explicitly_not_verified(self):
        with self.assertRaisesRegex(ValueError,'unverified'): build('oracc',b'{}')

    def test_budget_and_allowlist_fail_closed(self):
        cfg=Config(ROOT,max_total_bytes=0)
        with self.assertRaisesRegex(ValueError,'budget'): cfg.guard(1)
        cfg=Config(ROOT,reserve_bytes=10**18)
        with self.assertRaisesRegex(ValueError,'reserve'): cfg.guard(0)
        with self.assertRaisesRegex(ValueError,'allowlist'): fetch('https://example.com',ROOT/'fixtures/allowlist.json',cfg)

    def test_evidence_source_samples_when_present(self):
        evidence=Path.home()/'.local/share/cuneiform-research/evidence'
        sample=evidence/'ebl-frozen-example.json'
        if not sample.exists(): self.skipTest('private local evidence not supplied')
        db=build('ebl',sample.read_bytes())
        try:
            self.assertEqual(db.execute('SELECT count(*) FROM source_record').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT count(*) FROM rejection').fetchone()[0],0)
            self.assertGreater(db.execute('SELECT count(*) FROM occurrence').fetchone()[0],100)
            for raw,start,end,field,source in db.execute('SELECT t.raw,t.start_byte,t.end_byte,t.field,s.raw_json FROM token_context t JOIN source_record s ON s.id=t.source_record_id').fetchall():
                self.assertEqual(json.loads(source)[field].encode()[start:end].decode(),raw)
        finally: db.close()

if __name__=='__main__': unittest.main()
