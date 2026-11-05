"""Corpus pilot regressions: streaming scan, cohorts, chunked import, freshness fast path, ORACC/CDLI mapping.

Disk-writing tests need CUNEIFORM_RUN_DISK_TESTS=1 and only remove their own temporary tree under the runtime root.
Real-data checks skip unless the acquired raw objects and delivered snapshots exist on this machine.
"""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import duckdb
from cuneiform.adapters import Builder, ingest
from cuneiform.corpus import iter_array, record_stats, build_cohort, verify_cohort, RULE_DEFAULT
from cuneiform.model import canonical, digest
from cuneiform.projections import FROZEN_VERIFIED, ProjectionConfig, assert_fresh, build, canonical_hash, lookup, mark_frozen_verified
from cuneiform.storage import Config, MiB, validate_graph

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = Path.home()/'.local/share/cuneiform-research'


def admission_config():
    """Runtime-root admission for disk tests: the default task budget, unless CUNEIFORM_TEST_MAX_TOTAL_GIB names an explicit
    larger budget the owner authorized for this root (Q-023: 41 GiB, after the full eBL import). Never lowers the reserve."""
    gib = os.environ.get('CUNEIFORM_TEST_MAX_TOTAL_GIB')
    return Config(RUNTIME, max_total_bytes=int(float(gib) * 1024**3)) if gib else Config(RUNTIME)
DISK = os.environ.get('CUNEIFORM_RUN_DISK_TESTS') == '1'
PARENT_SHA = '4e970d8713315ca9559fb9dfd79956d5b19b1debb9941c22f8bed0339745d753'
SNAPSHOTS = {'ebl30': 'snapshot:ce127437339109285185a534145edf50', 'ebl300': 'snapshot:84971360d212834e0b7acbeac1e56abe',
             'ebl_ccpo': 'snapshot:c316e7cbbaf8a7fca7705f0efa5c4a07', 'oracc': 'snapshot:edaab55c1a39cc65ad7c76e6d12547a7', 'cdli': 'snapshot:fc7c350439f9edfee61b5f35bdd4d65a'}


def memory_db():
    db = duckdb.connect(':memory:')
    db.execute("SET memory_limit='128MB'"); db.execute('SET threads=1'); db.execute("SET max_temp_directory_size='0B'")
    db.execute((ROOT/'cuneiform/schema.sql').read_text())
    return db


TRICKY = [{'_id': 'R1', 'atf': '1. A B C\n2. A ] [ C', 'signs': 'A B', 'note': 'brackets ] [ } { , in strings', 'esc': 'quote " backslash \\ tab\t'},
          {'_id': 'R2', 'atf': '1. ša₂ A', 'signs': '', 'uni': 'Ḫ ṣ 𒀭 š'},
          {'_id': 'R1', 'atf': '1. A B', 'signs': ''}]


def write_parent(directory: Path, rows=TRICKY, wrap=False, ascii_escape=False) -> Path:
    body = ',\n  '.join(json.dumps(r, ensure_ascii=ascii_escape) for r in rows)
    text = ('{ "fragments" : [\n  ' + body + '\n] }\n') if wrap else ('[\n  ' + body + '\n]\n')
    path = directory/'parent.json'; path.write_bytes(text.encode('utf-8')); return path


class ScannerTests(unittest.TestCase):
    def test_exact_byte_ranges_across_tiny_chunks_and_envelopes(self):
        with tempfile.TemporaryDirectory() as d:
            for wrap in (False, True):
                for escape in (False, True):
                    path = write_parent(Path(d), wrap=wrap, ascii_escape=escape); data = path.read_bytes()
                    for chunk in (1, 3, 7, 1 << 20):
                        items = list(iter_array(path, chunk=chunk))
                        self.assertEqual([i['value'] for i in items], TRICKY)
                        for i in items:
                            self.assertEqual(data[i['start']:i['end']], i['raw'])
                            self.assertEqual(json.loads(i['raw']), i['value'])
                        self.assertEqual(items[1]['pointer'], ('/fragments' if wrap else '') + '/1')

    def test_structural_refusals(self):
        cases = {b'[1, {"a":1}]': 'non-object', b'[{"a":1}] x': 'trailing', b'[{"a":1}': 'truncated|malformed', b'{"other":[]}': 'envelope',
                 b'[{"a":1} {"b":2}]': 'separator', b'[{"a":"\xff"}]': None}
        with tempfile.TemporaryDirectory() as d:
            for raw, message in cases.items():
                p = Path(d)/'bad.json'; p.write_bytes(raw)
                with self.subTest(raw=raw):
                    if message is None:
                        with self.assertRaises(UnicodeDecodeError): list(iter_array(p))
                    else:
                        with self.assertRaisesRegex(ValueError, message): list(iter_array(p))

    def test_record_stats_match_real_import(self):
        rows = json.loads((ROOT/'fixtures/ebl-synthetic.json').read_text())
        rows = rows['fragments'] if isinstance(rows, dict) else rows
        for i, row in enumerate(rows):
            stats = record_stats(f'/{i}', row)
            db = memory_db()
            ingest(Builder(db, 's', 'ebl'), 'ebl', json.dumps([row]).encode())
            if stats['rejected']:
                self.assertEqual(db.execute('SELECT count(*) FROM rejection').fetchone()[0], 1); continue
            for field in ('atf', 'signs'):
                got = dict(db.execute('SELECT kind,count(*) FROM token_context WHERE field=? GROUP BY 1', [field]).fetchall())
                self.assertEqual(got, stats[field]['kinds'])
            self.assertEqual(db.execute('SELECT count(*) FROM translation_segment').fetchone()[0], stats['translations']['segments'])
            db.close()


class GraphValidationTests(unittest.TestCase):
    def test_dangling_and_wrong_type_edges_are_refused(self):
        db = memory_db()
        ingest(Builder(db, 's', 'ebl'), 'ebl', b'{"_id":"T","atf":"1. A B"}')
        validate_graph(db)
        occ, line = db.execute('SELECT o.id,o.line_id FROM occurrence o LIMIT 1').fetchone()
        rid = db.execute('SELECT id FROM source_record').fetchone()[0]
        db.execute("INSERT INTO edge VALUES ('e1',?,'nowhere','NEXT',?,'{}')", [occ, rid])
        with self.assertRaisesRegex(ValueError, 'dangling'): validate_graph(db)
        db.execute("DELETE FROM edge WHERE id='e1'")
        db.execute("INSERT INTO edge VALUES ('e2',?,?,'NEXT',?,'{}')", [occ, line, rid])
        with self.assertRaisesRegex(ValueError, 'invalid endpoint types: NEXT'): validate_graph(db)
        db.close()


def oracc_payload():
    fx = json.loads((ROOT/'fixtures/oracc-synthetic.json').read_text())
    docs = [fx['metadata'], fx['catalogue']] + fx['texts']
    parts, members, offset = [b'[\n'], [], 2
    for i, d in enumerate(docs):
        data = json.dumps(d, ensure_ascii=False).encode()
        if i: parts.append(b',\n'); offset += 2
        members.append({'payload_pointer': f'/{i}', 'payload_start': offset, 'payload_end': offset + len(data), 'member': f'synth/{i}.json', 'sha256': digest(data)})
        parts.append(data); offset += len(data)
    parts.append(b'\n]\n')
    return b''.join(parts), members


class OraccMappingTests(unittest.TestCase):
    def test_words_lemmas_senses_and_claims_without_invented_translation(self):
        from cuneiform.oracc import map_selection
        payload, members = oracc_payload()
        db = memory_db(); b = Builder(db, 'snap', 'oracc/synth'); b.raw_sha256 = digest(payload)
        stats = map_selection(b, payload, members, 'synth'); b.flush(); validate_graph(db)
        self.assertEqual((stats['words'], stats['lemmatized_words'], stats['lemmas'], stats['senses']), (4, 3, 1, 2))
        # One lemma shared across texts; two contextual senses; each lemmatized word points at exactly its own sense.
        self.assertEqual(db.execute("SELECT count(*) FROM edge WHERE kind='IN_SENSE'").fetchone()[0], 3)
        self.assertEqual(sorted(r[0] for r in db.execute("SELECT s.gloss FROM edge e JOIN sense s ON s.id=e.target_id WHERE e.kind='IN_SENSE'").fetchall()), ['for', 'to', 'to'])
        self.assertEqual(db.execute('SELECT count(*) FROM translation_segment').fetchone()[0], 0)
        reasons = [r[0] for r in db.execute('SELECT reason FROM exclusion ORDER BY 1').fetchall()]
        self.assertIn('English translation listed in project metadata; translation text absent from JSON export', reasons)
        self.assertTrue(any(r.startswith('word without citation form') for r in reasons))
        self.assertTrue(any('length mismatch' in r for r in reasons))  # P900002 lists 2 resources but 1 key: no eBL claim
        self.assertEqual(sorted(r[0] for r in db.execute("SELECT object_key FROM claim").fetchall()), ['cdli:P900001', 'cdli:P900002', 'ebl:X.1'])
        build(db)
        words = lookup(db, 'words', 'ana')
        self.assertEqual(len(words['rows']), 3)
        self.assertTrue(all(r['gloss_status'] == 'lexical gloss; not a translation' for r in words['rows']))
        self.assertEqual(lookup(db, 'lemmas', 'ana')['rows'][0]['attestations'], 3)
        db.close()


class CdliMappingTests(unittest.TestCase):
    def test_catalog_only_claims_and_rejection(self):
        from cuneiform.cdli_api import map_records
        docs = [[{'id': 1, 'museum_no': 'BM 1', 'external_resources': [{'external_resource': {'abbrev': 'eBL'}, 'external_resource_key': 'BM.1'}, {'external_resource': {'abbrev': 'CCP'}, 'external_resource_key': 'P000001'}]}], {'not': 'a list'}]
        parts, members, offset = [b'['], [], 1
        for i, d in enumerate(docs):
            data = json.dumps(d).encode()
            if i: parts.append(b','); offset += 1
            members.append({'payload_pointer': f'/{i}', 'payload_start': offset, 'payload_end': offset + len(data)}); parts.append(data); offset += len(data)
        payload = b''.join(parts + [b']'])
        db = memory_db(); b = Builder(db, 'snap', 'cdli'); b.raw_sha256 = digest(payload)
        stats = map_records(b, payload, members); b.flush(); validate_graph(db)
        self.assertEqual(stats, {'records': 1, 'rejected': 1, 'claims': 3})
        self.assertEqual(sorted(r[0] for r in db.execute('SELECT object_key FROM claim').fetchall()), ['catalog-label:BM 1', 'ebl:BM.1', 'external:CCP:P000001'])
        self.assertEqual(db.execute('SELECT catalog_key FROM artifact').fetchone()[0], 'P000001')
        self.assertEqual(db.execute('SELECT count(*) FROM witness').fetchone()[0], 0)
        db.close()


@unittest.skipUnless(DISK, 'disk verification explicitly gated')
class CorpusDiskTests(unittest.TestCase):
    def setUp(self):
        admission_config().guard(256*MiB)
        self.tmp = tempfile.TemporaryDirectory(prefix='pilot-test-', dir=RUNTIME/'scratch' if (RUNTIME/'scratch').exists() else RUNTIME)
        self.base = Path(self.tmp.name)

    def tearDown(self): self.tmp.cleanup()

    def parent(self):
        rows = json.loads((ROOT/'fixtures/ebl-synthetic.json').read_text())
        rows = (rows['fragments'] if isinstance(rows, dict) else rows) + [{'_id': 'DUP', 'atf': '1. A B C A B C A B C D'}, {'_id': 'DUP', 'atf': '1. A B C A B C A B C D'},
                                                                        {'_id': 'EXTRA', 'atf': '1. A B C A B C A B C D\n2. A ? C', 'signs': 'ABZ1 ABZ2 ABZ3'}]
        path = write_parent(self.base, rows)
        cfg = Config(self.base/'store'); target = cfg.root/'raw'/'sha256'/digest(path.read_bytes())
        target.parent.mkdir(parents=True); shutil.copy(path, target)
        return target, {'sha256': digest(path.read_bytes()), 'url': 'synthetic:parent', 'receipt_id': 'receipt:synthetic', 'rights': {'status': 'synthetic'}}, cfg

    def test_cohort_determinism_prefix_trace_tamper_and_chunked_parity(self):
        from cuneiform.storage import import_cohort, verify
        from cuneiform.query import trace
        path, parent, cfg = self.parent()
        rule = dict(RULE_DEFAULT, min_eligible_positions=3, min_eligible_pairs=1)
        small = build_cohort(path, parent, 1, self.base/'cohorts', rule)
        big = build_cohort(path, parent, 2, self.base/'cohorts', rule)
        again = build_cohort(path, parent, 2, self.base/'cohorts', rule)
        self.assertEqual(big['cohort_id'], again['cohort_id'])
        self.assertEqual(small['records'][0]['source_key'], big['records'][0]['source_key'])
        self.assertNotIn('DUP', [m['source_key'] for m in big['records']])
        keys = [i['value'].get('_id') for i in iter_array(path)]
        self.assertEqual(big['excluded_by_reason']['duplicate source key in parent (all copies excluded)'], sum(keys.count(k) for k in set(keys) if keys.count(k) > 1))
        directory = Path(big['directory'])
        # Chunked import (batch=1) equals the whole-input adapter over the same payload bytes.
        result = import_cohort(directory, cfg, ProjectionConfig(max_positions=1000, max_rows=10000), parent_path=path, batch=1)
        snap = cfg.root/'snapshots'/result['snapshot']
        frozen = duckdb.connect(str(snap/'graph.duckdb'), read_only=True)
        db = memory_db(); ingest(Builder(db, result['snapshot'], 'ebl'), 'ebl-cohort', (directory/'payload.json').read_bytes())
        self.assertEqual(canonical_hash(frozen), canonical_hash(db)); frozen.close(); db.close()
        self.assertTrue(import_cohort(directory, cfg, ProjectionConfig(max_positions=1000, max_rows=10000), parent_path=path)['reused'])
        occ = duckdb.connect(str(snap/'graph.duckdb'), read_only=True).execute("SELECT id FROM occurrence WHERE kind='reading' ORDER BY id LIMIT 1").fetchone()[0]
        traced = trace(snap, occ, parent_root=cfg.root)
        self.assertEqual(traced['parent_trace']['status'], 'verified')
        self.assertEqual(trace(snap, occ)['parent_trace']['status'], 'parent-raw-not-requested')
        # Relocation keeps verification; tampering the parent or payload is detected.
        moved = self.base/'moved'; shutil.copytree(snap, moved)
        self.assertEqual(verify(moved)['snapshot_id'], result['snapshot'])
        os.chmod(path, 0o644); original = path.read_bytes(); path.write_bytes(original.replace(b'A B', b'A X')); self.assertNotEqual(original, path.read_bytes())
        with self.assertRaisesRegex(ValueError, 'parent'): trace(moved, occ, parent_root=cfg.root)
        with self.assertRaisesRegex(ValueError, 'parent slice mismatch'): verify_cohort(directory, path)
        # New cohorts are sealed read-only; tampering needs an explicit owner chmod and is still detected.
        payload = directory/'payload.json'
        with self.assertRaises(PermissionError): payload.write_bytes(b'x')
        os.chmod(directory, 0o755); os.chmod(payload, 0o644); payload.write_bytes(payload.read_bytes()[:-2] + b' ]')
        with self.assertRaisesRegex(ValueError, 'payload integrity'): verify_cohort(directory)

    def test_spool_load_equals_executemany(self):
        from cuneiform.bulk import insert_rows
        rows = [(f'id{i}', 'x"y,\\z\x01\n' if i % 3 else None, i, canonical({'k': [i, None, 'š']})) for i in range(500)]
        out = []
        for spool in (None, self.base/'spool'):
            db = duckdb.connect(':memory:'); db.execute('CREATE TABLE t(a VARCHAR, b VARCHAR, c BIGINT, d JSON)')
            insert_rows(db, 't', rows, spool); out.append(db.execute('SELECT * FROM t ORDER BY c').fetchall()); db.close()
        self.assertEqual(out[0], out[1]); self.assertEqual(out[0][1][1], rows[1][1])
        self.assertFalse(any((self.base/'spool').iterdir()))

    def test_persisted_projection_configs_parquet_and_frozen_fast_path(self):
        from cuneiform.storage import import_source
        from cuneiform.query import connect
        cfg = Config(self.base/'store')
        for pc in (ProjectionConfig(), ProjectionConfig(postings=False), ProjectionConfig(ngrams=False), ProjectionConfig(postings=False, ngrams=False), ProjectionConfig(fields=('atf',), policies=('source',), lengths=(3,))):
            r = import_source('ebl', ROOT/'fixtures/ebl-synthetic.json', cfg, projections=pc)
            snap = cfg.root/'snapshots'/r['snapshot']; m = r['manifest']
            self.assertEqual({'posting', 'ngram'} & set(m['counts']), {t for t, on in (('posting', pc.postings), ('ngram', pc.ngrams)) if on})
            pq = duckdb.connect()
            for table, count in m['counts'].items():
                self.assertEqual(pq.execute('SELECT count(*) FROM read_parquet(?)', [str(snap/'parquet'/f'{table}.parquet')]).fetchone()[0], count)
            pq.close()
            db = connect(snap)
            self.assertIn(db, FROZEN_VERIFIED)
            self.assertTrue(assert_fresh(db)['freshness'].startswith('frozen-verified'))
            if pc.ngrams and 3 in pc.lengths:
                self.assertEqual(lookup(db, 'motifs', '["A","B","C"]', namespace='ebl', snapshot=r['snapshot'])['count'], 6)
            with self.assertRaisesRegex(ValueError, 'frozen'): build(db, pc)
            db.close()
        with self.assertRaises(PermissionError): (snap/'graph.duckdb').open('ab')
        os.chmod(snap, 0o755); os.chmod(snap/'graph.duckdb', 0o644)  # explicit test-only tamper of a temporary store
        writable = duckdb.connect(str(snap/'graph.duckdb'))
        with self.assertRaisesRegex(ValueError, 'read-only'): mark_frozen_verified(writable, m['projection_registry'])
        self.assertNotIn(writable, FROZEN_VERIFIED)
        self.assertEqual(assert_fresh(writable)['freshness'], 'recomputed canonical hash')
        writable.execute("UPDATE occurrence SET certainty='certain' WHERE kind='reading'")
        with self.assertRaisesRegex(ValueError, 'stale'): assert_fresh(writable)
        writable.close()
        from cuneiform.storage import verify
        with self.assertRaisesRegex(ValueError, 'integrity'): verify(snap)


class SpanMappingTests(unittest.TestCase):
    def test_encoded_spans_decode_to_tokens(self):
        import re
        from cuneiform.query import encoded_field_span
        for rec in [{'_id': 'a', 'atf': '1. me\u0161 [x] \U00012000 "q" e\u2082 a\\b'}, {'x': [1, {'atf': 'decoy'}], 'atf': '1. \u0161a ta'}]:
            for escape in (True, False):
                raw = json.dumps(rec, ensure_ascii=escape).encode()
                for m in re.finditer(r'\S+', rec['atf']):
                    s = len(rec['atf'][:m.start()].encode()); e = s + len(m[0].encode())
                    a, b = encoded_field_span(raw, 'atf', s, e)
                    self.assertEqual(json.loads(b'"' + raw[a:b] + b'"'), m[0])
        with self.assertRaisesRegex(ValueError, 'duplicate'): encoded_field_span(b'{"atf":"a","atf":"a"}', 'atf', 0, 1)


@unittest.skipUnless(DISK, 'disk verification explicitly gated')
class PublicationTests(unittest.TestCase):
    def test_ledger_read_only_and_contract_identity(self):
        from cuneiform.storage import import_source, snapshot_identity, verify, LEDGER
        from cuneiform.persisted import scope
        with tempfile.TemporaryDirectory(prefix='publish-test-', dir=RUNTIME/'scratch') as d:
            cfg = Config(Path(d)/'store')
            r = import_source('ebl', ROOT/'fixtures/ebl-synthetic.json', cfg)
            snap = cfg.root/'snapshots'/r['snapshot']
            self.assertEqual(r['manifest']['snapshot_contract'], 'manifest-3')
            ledger = [json.loads(l) for l in (cfg.root/'snapshots'/LEDGER).read_text().splitlines()]
            self.assertEqual([(e['event'], e['snapshot_id']) for e in ledger], [('reserve', r['snapshot']), ('commit', r['snapshot'])])
            self.assertEqual({e['manifest_sha256'] for e in ledger}, {r['manifest']['manifest_sha256']})
            self.assertEqual(snap.stat().st_mode & 0o777, 0o555)
            self.assertTrue(all(p.stat().st_mode & 0o222 == 0 for p in snap.rglob('*')))
            self.assertTrue(import_source('ebl', ROOT/'fixtures/ebl-synthetic.json', cfg)['reused'])
            self.assertEqual(scope(snap)['kind'], 'single input')
            # Deleting a published snapshot never permits republishing the same ID.
            for p in [snap, *snap.rglob('*')]: os.chmod(p, 0o755 if p.is_dir() else 0o644)
            shutil.rmtree(snap)
            with self.assertRaisesRegex(ValueError, 'already published'): import_source('ebl', ROOT/'fixtures/ebl-synthetic.json', cfg)
            self.assertFalse(snap.exists())
            # Legacy manifests (no snapshot_contract) still verify with the legacy identity formula.
            self.assertNotEqual(snapshot_identity('a', contract=None), snapshot_identity('a'))


@unittest.skipUnless((RUNTIME/'raw/sha256'/PARENT_SHA).exists() and all((RUNTIME/'snapshots'/s).exists() for s in SNAPSHOTS.values()), 'delivered pilot snapshots not on this machine')
class DeliveredPilotTests(unittest.TestCase):
    def test_snapshots_verify_parity_and_traces(self):
        from cuneiform.storage import verify
        from cuneiform.persisted import parity
        from cuneiform.query import trace
        from cuneiform.oracc import trace_word
        manifests = {k: verify(RUNTIME/'snapshots'/s, s) for k, s in SNAPSHOTS.items()}
        self.assertEqual(manifests['ebl300']['counts']['source_record'], 300)
        self.assertEqual(manifests['ebl300']['cohort']['parent']['sha256'], PARENT_SHA)
        result = parity(RUNTIME/'snapshots'/SNAPSHOTS['ebl300'], ['ABZ480', 'ABZ13'], 'signs')
        self.assertTrue(result['parity']); self.assertEqual(result['graph'], 201)
        occ = result['example_match']['occurrences'][0]
        pt = trace(RUNTIME/'snapshots'/SNAPSHOTS['ebl300'], occ, parent_root=RUNTIME)['parent_trace']
        self.assertEqual(pt['status'], 'verified')
        with (RUNTIME/'raw/sha256'/PARENT_SHA).open('rb') as f:
            f.seek(pt['parent_file_byte_span'][0]); fragment = f.read(pt['parent_file_byte_span'][1] - pt['parent_file_byte_span'][0])
        self.assertEqual(json.loads(b'"' + fragment + b'"'), pt['resolved_raw_in_parent'])
        sc = result['scope']
        self.assertEqual((sc['kind'], sc['cohort_size'], sc['eligible_records'], sc['parent_records']), ('rule-selected cohort', 300, 20896, 23289))
        self.assertTrue(all(p.stat().st_mode & 0o222 == 0 for p in (RUNTIME/'snapshots'/SNAPSHOTS['ebl300']).rglob('*')))
        db = duckdb.connect(str(RUNTIME/'snapshots'/SNAPSHOTS['oracc']/'graph.duckdb'), read_only=True)
        word = db.execute("SELECT source_id FROM edge WHERE kind='IN_SENSE' ORDER BY id LIMIT 1").fetchone()[0]; db.close()
        self.assertEqual(trace_word(RUNTIME/'snapshots'/SNAPSHOTS['oracc'], word, parent_root=RUNTIME)['parent_trace']['status'], 'verified')
