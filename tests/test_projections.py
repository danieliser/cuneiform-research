import json
from pathlib import Path
from dataclasses import asdict
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from test_foundation import build as canonical_db, ROOT
from cuneiform.adapters import Builder, ingest
from cuneiform.model import canonical, digest, identity, SCHEMA_VERSION, PARSER_VERSION
from cuneiform.projections import ProjectionConfig, REVISION, build, lookup, rows, source_span, coverage, assert_fresh
from cuneiform.query import motif, array_count, trace_rows
from cuneiform.storage import verify

class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.db=canonical_db()
        self.projection=build(self.db)
    def tearDown(self): self.db.close()
    def search(self, pattern, **kwargs):
        return lookup(self.db,'motifs',canonical(pattern),namespace='ebl',snapshot='test-snapshot',**kwargs)

    def test_independent_expectations_overlaps_and_blockers(self):
        for pattern,count in [(['A','B','C'],6),(['A','?','C'],11),(['A','C'],0),(['A','B','C','A'],1),(['A','B','C','A','B'],1)]:
            result=self.search(pattern)
            self.assertEqual(result['count'],count)
            self.assertEqual(array_count(self.db,pattern),count)
            graph=motif(self.db,pattern)
            self.assertEqual(graph['occurrences'],count)
            self.assertEqual({m['match_id'] for m in result['rows']},{m['id'] for m in graph['matches']})
        db=canonical_db(data=b'{"_id":"O","atf":"1. A A A A\\n2. A ... A\\n3. A B/C A"}')
        try:
            build(db)
            self.assertEqual(lookup(db,'motifs','["A","A"]',namespace='ebl',snapshot='test-snapshot')['count'],3)
            self.assertEqual(lookup(db,'motifs','["A","?","A"]',namespace='ebl',snapshot='test-snapshot')['count'],4)
        finally: db.close()

    def test_namespace_field_and_sign_identity_separation(self):
        ingest(Builder(self.db,'other-snapshot','other'),'ebl',b'{"_id":"X","atf":"1. A B","signs":"A B/C B"}')
        build(self.db)
        self.assertEqual(self.search(['A','B','C'])['count'],6)
        self.assertEqual(lookup(self.db,'motifs','["A","B"]',namespace='other',snapshot='other-snapshot',field='signs')['count'],0)
        self.assertEqual(lookup(self.db,'postings','B/C',namespace='other',snapshot='other-snapshot',field='signs')['rows'],[])
        self.assertEqual(self.db.execute("SELECT count(*) FROM sign_type WHERE label='B/C'").fetchone()[0],0)
        atf=lookup(self.db,'postings','A',namespace='other',snapshot='other-snapshot')['rows'][0]
        signs=lookup(self.db,'postings','A',namespace='other',snapshot='other-snapshot',field='signs')['rows'][0]
        self.assertNotEqual(atf['token_id'],signs['token_id'])
        self.assertTrue(signs['token_id'].startswith('sign:'))
        with self.assertRaisesRegex(ValueError,'explicit'): lookup(self.db,'postings','A')

    def test_strict_breaks_paths_and_stale_rebuild(self):
        self.assertEqual(self.search(['A','B','C'],policy='strict')['count'],0)
        self.db.execute("UPDATE occurrence SET preservation='intact',certainty='certain' WHERE preservation='unknown' AND certainty='unmarked'")
        with self.assertRaisesRegex(ValueError,'stale'): self.search(['A','B'])
        build(self.db)
        self.assertEqual(self.search(['A','B','C'],policy='strict')['count'],3)
        self.assertEqual(self.search(['A','C'],policy='strict')['count'],0)
        self.assertEqual({r['match_id'] for r in self.search(['A','B','C'],policy='strict')['rows']},{r['id'] for r in motif(self.db,['A','B','C'],strict=True)['matches']})

    def test_postings_match_canonical_and_graph_counts(self):
        postings=lookup(self.db,'postings','A',namespace='ebl',snapshot='test-snapshot',limit=100)['rows']
        expected=self.db.execute("SELECT id FROM ordered_position WHERE namespace='ebl' AND snapshot_id='test-snapshot' AND field='atf' AND reading='A'").fetchall()
        self.assertEqual({r['occurrence_id'] for r in postings},{r[0] for r in expected})
        graph=self.db.execute("SELECT e.target_id FROM edge e JOIN token_context t ON t.id=e.target_id WHERE e.kind='HAS_OCCURRENCE' AND t.field='atf' AND t.reading='A'").fetchall()
        self.assertEqual(len(postings),len(graph))
        self.assertEqual(len(postings),12)

    def test_trace_and_reverse_navigation(self):
        m=self.search(['A','?','C'])['rows'][0]
        oid=json.loads(m['occurrence_ids'])[1]
        p=lookup(self.db,'occurrence',oid)['rows'][0]
        result=source_span(self.db,p['source_record_id'],p['field'],p['start_byte'],p['end_byte'])
        self.assertEqual([r['id'] for r in result['rows']],[oid])
        raw=(ROOT/'fixtures/ebl-synthetic.json').read_bytes()
        self.assertEqual(trace_rows(self.db,raw,{'source':'ebl','raw_sha256':digest(raw),'rights':{}},oid)['resolved_raw'],p['raw'])
        self.assertIn(m['id'],{r['id'] for r in lookup(self.db,'reverse-motifs',oid)['rows']})
        self.assertTrue(lookup(self.db,'neighbors',oid)['rows'])
        self.assertTrue(lookup(self.db,'sequence',p['sequence_id'])['rows'])

    def test_alias_ambiguity_cross_source_and_translations(self):
        ingest(Builder(self.db,'cdli-snapshot','cdli'),'cdli',(ROOT/'fixtures/cdli-synthetic.csv').read_bytes())
        build(self.db)
        claims=lookup(self.db,'aliases','cdli:P000001')['rows']
        self.assertEqual(len(claims),2)
        self.assertEqual(len({r['subject_id'] for r in claims}),2)
        target=lookup(self.db,'catalog','cdli:P000001')['rows']
        self.assertEqual(len(target),1)
        self.assertNotIn(target[0]['id'],{r['subject_id'] for r in claims})
        t=lookup(self.db,'translations')['rows'][0]
        self.assertEqual(t['granularity'],'unresolved-span')
        self.assertTrue(t['locator'].startswith('atf:utf8:'))
        self.assertEqual(lookup(self.db,'translations',t['sequence_id'])['rows'][0]['id'],t['id'])
        self.assertTrue(all(r['words']==r['lemmas']==0 for r in coverage(self.db)))
        self.assertTrue(any(r['sequences']==r['translations']==0 for r in coverage(self.db)))
        self.assertEqual(self.db.execute("SELECT count(*) FROM portable_edge WHERE kind='TRANSLATES'").fetchone()[0],0)
        self.assertEqual(self.db.execute('SELECT count(*) FROM portable_edge e LEFT JOIN nodes n ON n.id=e.target_id WHERE n.id IS NULL').fetchone()[0],0)

    def test_caps_configuration_and_atomic_failure(self):
        old=assert_fresh(self.db)['id']
        with self.assertRaisesRegex(ValueError,'row budget'): build(self.db,ProjectionConfig(max_rows=1))
        self.assertEqual(assert_fresh(self.db)['id'],old)
        with self.assertRaisesRegex(ValueError,'position budget'): build(self.db,ProjectionConfig(max_positions=1))
        result=self.search(['A','?','C'],limit=2)
        self.assertEqual(result['count'],11); self.assertEqual(len(result['rows']),2)
        self.assertTrue(result['truncated']);self.assertEqual(result['next_offset'],2)
        self.assertEqual(len(self.search(['A','?','C'],limit=2,offset=10)['rows']),1)
        with self.assertRaises(ValueError): self.search(['A','B'],limit=101)
        self.assertEqual(build(self.db)['id'],old)
        build(self.db,ProjectionConfig(ngrams=False))
        self.assertEqual(self.db.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='ngram'").fetchone()[0],0)
        with self.assertRaisesRegex(ValueError,'not configured'):self.search(['A','B'])

    def test_real_retained_samples(self):
        evidence=Path.home()/'.local/share/cuneiform-research/evidence'
        if not (evidence/'ebl-frozen-example.json').exists(): self.skipTest('retained evidence absent')
        db=canonical_db(data=(evidence/'ebl-frozen-example.json').read_bytes())
        try:
            build(db)
            indexed=lookup(db,'motifs','["ABZ215","ABZ13"]',namespace='ebl',snapshot='test-snapshot',field='signs')
            self.assertEqual(indexed['count'],3)
            self.assertEqual(indexed['count'],motif(db,['ABZ215','ABZ13'],field='signs')['occurrences'])
            self.assertEqual(indexed['count'],array_count(db,['ABZ215','ABZ13'],field='signs'))
            self.assertEqual(coverage(db)[0]['unresolved_translations'],9)
        finally:db.close()

    def test_variable_manifest_inventory_without_disk(self):
        import re
        for cfg in [None,ProjectionConfig(),ProjectionConfig(ngrams=False),ProjectionConfig(ngrams=False,postings=False)]:
            spec={'revision':REVISION,'config':asdict(cfg)} if cfg else None
            tables=set(re.findall(r'CREATE TABLE (\w+)',(ROOT/'cuneiform/schema.sql').read_text()))
            if cfg is None: tables -= {'source_binding','projection_registry'}
            if cfg and cfg.ngrams:tables.add('ngram')
            if cfg and cfg.postings:tables.add('posting')
            payload=b'fixture';sha=digest(payload)
            version=SCHEMA_VERSION if cfg else '1'
            parser=PARSER_VERSION if cfg else 'conservative-2'
            sid=identity('snapshot','ebl','ebl',sha,version,parser,None,None,*([spec] if cfg else []))
            manifest=dict(snapshot_id=sid,schema_version=version,parser_version=parser,namespace='ebl',source='ebl',source_url=None,record_id=None,raw_sha256=sha,source_bytes=len(payload),rights={},counts={t:0 for t in tables},files={n:sha for n in {'raw','graph.duckdb'}|{f'parquet/{t}.parquet' for t in tables}},projection_spec=spec)
            def check(m):
                m['manifest_sha256']=digest(canonical({k:v for k,v in m.items() if k!='manifest_sha256'}).encode())
                original=Path.read_text
                with patch.object(Path,'read_text',lambda p,*a,**kw:json.dumps(m) if p.name=='manifest.json' else original(p,*a,**kw)),patch.object(Path,'read_bytes',return_value=payload),patch('cuneiform.storage.file_sha256',return_value=sha),patch.object(Path,'stat',return_value=SimpleNamespace(st_size=len(payload))):return verify(Path('/nonexistent'),sid)
            self.assertEqual(check(manifest)['snapshot_id'],sid)
            del manifest['files']['parquet/occurrence.parquet']
            with self.assertRaisesRegex(ValueError,'inventory'): check(manifest)
