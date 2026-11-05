"""conservative-4 ATF line gate and @-line surfaces (reviews/reading-aids-review-v0.1.md F1 and its surface note).

The fixture holds the review's malformed translation, note and comment forms next to genuine text lines with every
label shape eBL's line-number grammar allows (prime, letter suffix, `a+1`, ranges)."""
import json
from pathlib import Path
import unittest
from cuneiform.adapters import LINE_NUMBER, at_line_state, ingest_record
from cuneiform.corpus import _Tally, cohort_identity, record_stats
from cuneiform.model import PARSER_VERSION, READABLE_PARSER_VERSIONS

ROOT = Path(__file__).resolve().parents[1]
RECORDS = json.loads((ROOT/'fixtures/ebl-comment-lines.json').read_text())


def rows(record):
    tally = _Tally()
    assert ingest_record(tally, 'ebl', '/0', record)
    return tally.last


def atf_lines(r):
    atf = {sid for sid, _, _, field, *_ in r['sequence_version'] if field == 'atf'}
    return [row for row in r['line'] if row[1] in atf]


class ParserGateTests(unittest.TestCase):
    def setUp(self):
        self.r = rows(RECORDS[0])
        self.text = RECORDS[0]['atf']
        self.lines = atf_lines(self.r)

    def test_version(self):
        self.assertEqual(PARSER_VERSION, 'conservative-4')
        self.assertEqual(READABLE_PARSER_VERSIONS, ('conservative-3', 'conservative-4'))

    def test_only_numbered_lines_are_text_lines(self):
        self.assertEqual([l[3] for l in self.lines], ['1', '2', '3', "4'", '5', 'a+1', '1a', '2-3', '4′', '6'])
        self.assertEqual([l[2] for l in self.lines], list(range(10)))
        self.assertFalse([l for l in self.r['line'] if (l[3] or '')[:1] in '#$&@'])

    def test_comment_lines_have_no_positions(self):
        source = self.text.encode()
        lines_by_id = {l[0]: l for l in self.lines}
        atf = [o for o in self.r['occurrence'] if o[1] in lines_by_id]
        self.assertEqual(len(atf), 14)
        for oid, lid, position, raw, *_, start, end in atf:
            self.assertEqual(source[start:end].decode(), raw)
        for oid, lid, *_ in atf:
            begin = lines_by_id[lid][6]
            line = source[begin:].split(b'\n', 1)[0].decode()
            self.assertFalse(line.startswith(('#', '$', '&', '@')), line)

    def test_english_words_removed_but_same_ancient_readings_kept(self):
        ids = {l[0] for l in self.lines}
        readings = [o[4] for o in self.r['occurrence'] if o[1] in ids]
        for english in ('There', 'will', 'never', 'lawsuit.', 'quarter', 'silver', 'Gloss', 'KADP', 'tablet', 'of', 'Urama;'):
            self.assertNotIn(english, readings)
        # `he`, `I`, `ina`, `ša` are not blacklisted: they stay wherever a numbered line holds them.
        self.assertEqual(readings.count('he'), 2)
        self.assertEqual(readings.count('I'), 1)
        self.assertEqual(readings.count('ina'), 3)
        self.assertEqual(readings.count('ša'), 2)

    def test_translations_and_exclusions_are_explicit(self):
        tr = sorted((t[3], t[4]) for t in self.r['translation_segment'])
        self.assertEqual(tr, [('en', '. .. Nunamnir(?) ...'), ('en', 'There will never be any lawsuit.'), ('en', 'tablet of he')])
        self.assertTrue(all(t[6] == 'unresolved-span' for t in self.r['translation_segment']))
        reasons = {}
        for _, _, locator, reason in self.r['exclusion']:
            if ':line:' in locator: reasons[int(locator.rsplit(':', 1)[1])] = reason
        unsupported = 'unsupported translation syntax retained in raw'
        non_token = 'non-token ATF line retained in raw; no cross-line matching'
        lines = self.text.splitlines()
        for no in (3, 4, 5): self.assertEqual(reasons[no], unsupported, lines[no])          # dot-form #tr: excluded, not guessed
        for no in (7, 8, 13, 14, 15): self.assertEqual(reasons[no], non_token, lines[no])     # #note. / #Vgl. / $ / & / #note:
        for no in (2, 6, 12): self.assertNotIn(no, reasons)                                  # parsed translations
        self.assertEqual(len(self.r['translation_segment']) + sum(r == unsupported for r in reasons.values()), sum(l.startswith('#tr') for l in lines))

    def test_surfaces_come_only_from_surface_markers(self):
        got = {l[3]: (l[4], l[5]) for l in self.lines}
        self.assertEqual(got['1'], ('obverse', None))
        self.assertEqual(got['3'], ('obverse', None))       # @colophon is document structure, not a surface
        self.assertEqual(got["4'"], ('obverse', '2'))       # @date keeps surface and column
        self.assertEqual(got['5'], (None, None))            # @seal 1 starts a carrier whose surface is not stated
        self.assertEqual(got['a+1'], ('reverse?', None))
        self.assertEqual(got['6'], (None, None))            # unrecognized @end of column: surface unknown

    def test_at_line_classes(self):
        cases = {'obverse': ('obverse', None), 'reverse!': ('reverse!', None), 'edge': ('edge', None), 'edge a': ('edge a', None),
                 "face a'": ("face a'", None), 'surface side b 90 degrees': ('surface side b 90 degrees', None),
                 'column 3?': ('S', '3?'), 'colophon': ('S', 'C'), 'catchline': ('S', 'C'), 'witnesses': ('S', 'C'),
                 'm=division §1a': ('S', 'C'), 'h1': ('S', 'C'), 'tablet': (None, None), 'envelope': (None, None),
                 'fragment 2': (None, None), 'object seal 1': (None, None), 'seal 2': (None, None), 'end of side': (None, None)}
        for body, expected in cases.items():
            with self.subTest(body=body): self.assertEqual(at_line_state(body, 'S', 'C'), expected)

    def test_signs_layer_unchanged_and_line_counts_agree(self):
        signs = {sid for sid, _, _, field, *_ in self.r['sequence_version'] if field == 'signs'}
        self.assertEqual(sum(l[1] in signs for l in self.r['line']), len(self.lines))
        stats = record_stats('/0', RECORDS[0])
        self.assertEqual(stats['atf']['lines'], stats['signs']['lines'])

    def test_line_number_grammar(self):
        for ok in ('1', "1'", '1′', '1’', '12a', 'a+1', "a+1'", '1-2', "1'-2'", 'b+3a'):
            self.assertTrue(LINE_NUMBER.fullmatch(ok), ok)
        for bad in ('#tr.en', '#note', '#Vgl', '$', 'b', '1.2', 'o', 'i', '1)', ''):
            self.assertFalse(LINE_NUMBER.fullmatch(bad), bad)

    def test_label_outside_grammar_is_excluded_not_parsed(self):
        r = rows(RECORDS[1])
        self.assertEqual([l[3] for l in atf_lines(r)], ['1'])
        reasons = [e[3] for e in r['exclusion'] if ':line:' in e[2]]
        self.assertEqual(reasons.count('ATF line label outside eBL line-number grammar retained in raw'), 2)
        self.assertEqual([o[4] for o in r['occurrence']], ['ina'])

    def test_superseded_cohort_identity_still_verifies(self):
        parent = {'sha256': '0' * 64}
        old = cohort_identity(parent, {'name': 'r'}, None, 'cohort-2', 'conservative-3')
        self.assertNotEqual(old, cohort_identity(parent, {'name': 'r'}, None, 'cohort-2'))
        with self.assertRaisesRegex(ValueError, 'parser'): cohort_identity(parent, {'name': 'r'}, None, 'cohort-2', 'conservative-2')

    def test_superseded_snapshot_manifest_still_verifies(self):
        """Published conservative-3 snapshots (e.g. 965aa262) stay readable; unknown parser versions are refused."""
        import re
        from dataclasses import asdict
        from types import SimpleNamespace
        from unittest.mock import patch
        from cuneiform.model import SCHEMA_VERSION, canonical, digest
        from cuneiform.projections import REVISION, ProjectionConfig
        from cuneiform.storage import snapshot_identity, verify
        cfg = ProjectionConfig(); spec = {'revision': REVISION, 'config': asdict(cfg)}
        tables = set(re.findall(r'CREATE TABLE (\w+)', (ROOT/'cuneiform/schema.sql').read_text())) | {'ngram', 'posting'}
        payload = b'fixture'; sha = digest(payload)
        def check(parser):
            sid = snapshot_identity('ebl', 'ebl', sha, SCHEMA_VERSION, parser, None, None, spec)
            m = dict(snapshot_id=sid, snapshot_contract='manifest-3', schema_version=SCHEMA_VERSION, parser_version=parser, namespace='ebl', source='ebl',
                     source_url=None, record_id=None, raw_sha256=sha, source_bytes=len(payload), rights={}, counts={t: 0 for t in tables},
                     files={n: sha for n in {'raw', 'graph.duckdb'} | {f'parquet/{t}.parquet' for t in tables}}, projection_spec=spec)
            m['manifest_sha256'] = digest(canonical(m).encode())
            original = Path.read_text
            with patch.object(Path, 'read_text', lambda p, *a, **kw: json.dumps(m) if p.name == 'manifest.json' else original(p, *a, **kw)), \
                 patch.object(Path, 'read_bytes', return_value=payload), patch('cuneiform.storage.file_sha256', return_value=sha), \
                 patch.object(Path, 'stat', return_value=SimpleNamespace(st_size=len(payload))):
                return verify(Path('/nonexistent'), sid)['snapshot_id'] == sid
        self.assertTrue(check('conservative-3'))
        self.assertTrue(check('conservative-4'))
        with self.assertRaisesRegex(ValueError, 'unsupported parser version'): check('conservative-9')


if __name__ == '__main__':
    unittest.main()
