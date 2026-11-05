"""Q-023 staged full-import qualification: build (select + import) and check one stage, writing an evidence JSON.

  build  select a cohort (--size N or --all-eligible) and import it with the full projection preset, sampling peak
         transient disk under <root>/snapshots and process peak RSS. Run under `/usr/bin/time -l` for an OS-level RSS.
  check  read-only checks of a published stage snapshot: record accounting, ID uniqueness, Parquet/table integrity,
         parent byte traces (escaped Unicode, unsupported and gap positions), stratified graph/array/index parity,
         per-record subset equality against a reference snapshot (the 300 cohort), and lookup latency.

Everything goes through the package's public functions; the snapshot store is only read by `check`.
Usage: python -B scripts/full_import_stage.py build|check --root R --receipt RID (--size N | --all-eligible) --out E.json
"""
import argparse
import json
import os
import resource
import shutil
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.dont_write_bytecode = True

from cuneiform import storage, corpus  # noqa: E402
from cuneiform.model import canonical  # noqa: E402

GiB = 1024**3


def tree_bytes(path: Path) -> int:
    total = 0
    for dirpath, _, files in os.walk(path):
        for f in files:
            try: total += os.lstat(os.path.join(dirpath, f)).st_size
            except FileNotFoundError: pass
    return total


def peak_rss_bytes() -> int:
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r if sys.platform == 'darwin' else r * 1024


class DiskSampler(threading.Thread):
    """Samples bytes under <root>/snapshots/.pending-* (the build stage) and filesystem free space."""
    def __init__(self, root: Path, every: float = 2.0):
        super().__init__(daemon=True); self.root, self.every = root, every
        self.peak_stage = 0; self.min_free = shutil.disk_usage(root).free; self.samples = 0; self.stop = threading.Event()

    def run(self):
        while not self.stop.wait(self.every):
            stage = sum(tree_bytes(p) for p in (self.root/'snapshots').glob('.pending-*'))
            self.peak_stage = max(self.peak_stage, stage); self.min_free = min(self.min_free, shutil.disk_usage(self.root).free); self.samples += 1


def build(args) -> dict:
    cfg = storage.Config(args.root, max_total_bytes=int(args.max_total_gib*GiB), reserve_bytes=int(args.reserve_gib*GiB))
    before = {'root_bytes': tree_bytes(args.root), 'free_bytes': shutil.disk_usage(args.root).free}
    t = time.monotonic()
    cohort = corpus.select_cohort(args.root, args.receipt, None if args.all_eligible else args.size)
    select_s = round(time.monotonic() - t, 1)
    acc = corpus.accounting(cohort)
    sampler = DiskSampler(args.root); sampler.start()
    t = time.monotonic()
    from cuneiform.acquire import raw_path
    result = storage.import_cohort(Path(cohort['directory']), cfg, storage.PROJECTION_PRESETS[args.projections],
                                   parent_path=raw_path(args.root, cohort['parent']['sha256']), memory=args.memory, cohort_ledger='store')
    import_s = round(time.monotonic() - t, 1)
    sampler.stop.set(); sampler.join()
    m = result['manifest']
    after = {'root_bytes': tree_bytes(args.root), 'free_bytes': shutil.disk_usage(args.root).free}
    return {'stage': 'build', 'root': str(args.root), 'cohort_id': cohort['cohort_id'], 'cohort_size': len(cohort['records']), 'accounting': acc,
            'snapshot': result['snapshot'], 'reused': result['reused'], 'counts': m['counts'], 'ingestion': m.get('ingestion'),
            'build_timings': m.get('build_timings'), 'snapshot_payload_bytes': m.get('snapshot_payload_bytes'),
            'select_s': select_s, 'import_s': import_s, 'process_peak_rss_bytes': peak_rss_bytes(),
            'peak_stage_bytes_sampled': sampler.peak_stage, 'min_free_bytes_sampled': sampler.min_free, 'disk_samples': sampler.samples,
            'before': before, 'after': after, 'retained_delta_bytes': after['root_bytes'] - before['root_bytes'],
            'budget': {'max_total_bytes': cfg.max_total_bytes, 'reserve_bytes': cfg.reserve_bytes}, 'projections': args.projections, 'memory': args.memory}


def table_columns(db, table):
    return [r[0] for r in db.execute("SELECT column_name FROM information_schema.columns WHERE table_name=? AND table_schema='main' ORDER BY ordinal_position", [table]).fetchall()]


def check(args) -> dict:
    import duckdb
    from cuneiform.query import open_verified, motif, array_count, trace
    from cuneiform.persisted import lookup_snapshot, scope
    from cuneiform.projections import lookup
    cfg = storage.Config(args.root)
    out = {'stage': 'check', 'root': str(args.root), 'snapshot': args.snapshot}
    path = storage.store_path(cfg, args.snapshot)
    t = time.monotonic(); checked = storage.verified(path, ledger='require'); out['verify_s'] = round(time.monotonic() - t, 2)
    manifest = checked['manifest']; out['publication'] = checked['publication']['status']
    sc = scope(path, manifest); out['scope'] = {k: sc.get(k) for k in ('kind', 'label', 'scope_note', 'cohort_size', 'eligible_records', 'parent_records', 'excluded_by_reason', 'accounting')}
    cohort = json.loads((path/'cohort.json').read_text())
    acc = corpus.accounting(cohort)
    db = open_verified(path, manifest)
    try:
        db.execute("SET memory_limit='8GB'"); db.execute('SET threads=4')
        # 1. record accounting: one SourceRecord per cohort member, same keys and payload pointers.
        keys = {r[0]: r[1] for r in db.execute('SELECT locator,source_key FROM source_record').fetchall()}
        members = {m['payload_pointer']: m['source_key'] for m in cohort['records']}
        out['record_accounting'] = {'cohort': acc, 'source_records': len(keys), 'members': len(members), 'equal_member_keys': keys == members,
                                    'rejections': db.execute('SELECT count(*) FROM rejection').fetchone()[0]}
        # 2. ID uniqueness per table and across node tables.
        uniq = {}
        for table in manifest['counts']:
            cols = table_columns(db, table)
            if 'id' not in cols: continue
            n, d = db.execute(f'SELECT count(*),count(DISTINCT id) FROM {table}').fetchone()
            uniq[table] = {'rows': n, 'distinct_ids': d, 'unique': n == d}
        n, d = db.execute('SELECT count(*),count(DISTINCT id) FROM nodes').fetchone()
        uniq['@nodes_view'] = {'rows': n, 'distinct_ids': d, 'unique': n == d}
        out['id_uniqueness'] = uniq
        # 3. Parquet vs table: row count and an order-independent row hash, for every table in the manifest.
        pq = {}
        for table, count in manifest['counts'].items():
            cols = table_columns(db, table)
            expr = 'bit_xor(hash(' + ','.join(f'"{c}"' for c in cols) + '))'
            literal = str(path/'parquet'/f'{table}.parquet').replace("'", "''")
            a = db.execute(f'SELECT count(*),{expr} FROM {table}').fetchone()
            b = db.execute(f"SELECT count(*),{expr} FROM read_parquet('{literal}')").fetchone()
            pq[table] = {'manifest': count, 'table': a[0], 'parquet': b[0], 'row_hash_equal': a[1] == b[1], 'ok': count == a[0] == b[0] and a[1] == b[1]}
        out['parquet_integrity'] = {'tables': len(pq), 'all_ok': all(v['ok'] for v in pq.values()), 'detail': pq}
        # 4. Source traces: stratified by position kind and Unicode, spread over cohort order.
        samples = {}
        def pick(name, where, n):
            rows = db.execute(f"""SELECT id FROM (SELECT o.id, row_number() OVER (ORDER BY o.id) rn, count(*) OVER () c FROM occurrence o JOIN line l ON l.id=o.line_id
                                  JOIN sequence_version s ON s.id=l.sequence_id WHERE {where}) WHERE rn % greatest(1, c // {n}) = 0 ORDER BY rn LIMIT {n}""").fetchall()
            samples[name] = [r[0] for r in rows]
        pick('ascii_reading', "o.kind='reading' AND regexp_matches(o.raw,'^[ -~]+$')", 3)
        pick('non_ascii_reading', "o.kind='reading' AND NOT regexp_matches(o.raw,'^[ -~]+$')", 6)
        pick('derived_sign', "o.kind='derived_sign'", 3)
        pick('unsupported', "o.kind='unsupported'", 5)
        pick('gap', "o.kind='gap'", 3)
        traces = []
        for name, ids in samples.items():
            for oid in ids:
                t = time.monotonic(); r = trace(path, oid, parent_root=cfg.root); ms = round((time.monotonic() - t) * 1000)
                pt = r.get('parent_trace', {})
                traces.append({'stratum': name, 'occurrence': oid, 'source_key': r['source_key'], 'kind': r['token'].get('kind'), 'raw': r['resolved_raw'],
                               'status': pt.get('status'), 'parent_file_byte_span': pt.get('parent_file_byte_span'), 'parent_fragment': pt.get('parent_file_fragment'),
                               'escaped_in_parent': '\\u' in (pt.get('parent_file_fragment') or ''), 'end_to_end_ms': ms})
        out['traces'] = {'count': len(traces), 'all_verified': all(t['status'] == 'verified' for t in traces),
                         'escaped_unicode_traced': sum(t['escaped_in_parent'] for t in traces), 'detail': traces}
        # 5. Stratified motif parity (graph traversal / sequence arrays / n-gram index), deterministic on rerun.
        strata = []
        for field in ('signs', 'atf'):
            for length in (2, 3):
                ranked = db.execute("""SELECT readings,count(*) n FROM ngram WHERE field=? AND policy='source' AND length=? AND len(list_filter(json_extract_string(readings,'$[*]'), x -> x IS NULL))=0
                                       GROUP BY readings ORDER BY n DESC, readings""", [field, length]).fetchall()
                if not ranked: continue
                for label, idx in (('top', 0), ('p50', len(ranked)//2), ('rare', len(ranked)-1)):
                    strata.append((field, label, json.loads(ranked[idx][0])))
            if args.wildcards:
                strata.append((field, 'wildcard', args.wildcards[field]))
        parity = []
        for field, label, pattern in strata:
            t = time.monotonic(); g = motif(db, pattern, field)['occurrences']; gms = round((time.monotonic() - t) * 1000)
            t = time.monotonic(); a = array_count(db, pattern, field); ams = round((time.monotonic() - t) * 1000)
            t = time.monotonic(); i = lookup(db, 'motifs', canonical(pattern), namespace=manifest['namespace'], snapshot=manifest['snapshot_id'], field=field, limit=1)['count']; ims = round((time.monotonic() - t) * 1000)
            i2 = lookup(db, 'motifs', canonical(pattern), namespace=manifest['namespace'], snapshot=manifest['snapshot_id'], field=field, limit=1)['count']
            parity.append({'field': field, 'stratum': label, 'pattern': pattern, 'graph': g, 'array': a, 'index': i, 'index_rerun': i2, 'parity': g == a == i == i2,
                           'graph_ms': gms, 'array_ms': ams, 'index_ms': ims})
        out['parity'] = {'cases': len(parity), 'all_equal': bool(parity) and all(p['parity'] for p in parity), 'detail': parity}
        if len(parity) < 10: raise ValueError(f'stratified parity selected only {len(parity)} cases')
        # 6. Subset comparison with a reference snapshot whose records are a subset (cohorts are prefixes in one order).
        if args.reference:
            rpath = storage.store_path(storage.Config(args.reference_root or args.root), args.reference)
            rman = storage.verified(rpath, ledger='require')['manifest']
            rdb = open_verified(rpath, rman)
            per = {}
            q = """SELECT r.source_key, s.field, count(o.id) positions, count(DISTINCT l.id) lines FROM occurrence o JOIN line l ON l.id=o.line_id
                   JOIN sequence_version s ON s.id=l.sequence_id JOIN source_record r ON r.id=s.source_record_id GROUP BY 1,2"""
            qn = "SELECT r.source_key, n.field, n.length, count(*) FROM ngram n JOIN source_record r ON r.id=n.source_record_id WHERE n.policy='source' GROUP BY 1,2,3"
            try:
                ref_pos = {(k, f): (p, l) for k, f, p, l in rdb.execute(q).fetchall()}
                ref_ng = {(k, f, n): c for k, f, n, c in rdb.execute(qn).fetchall()}
                ref_keys = {r[0] for r in rdb.execute('SELECT source_key FROM source_record').fetchall()}
                ref_motifs = {}
                for field, pattern in args.reference_motifs:
                    ref_motifs[canonical([field, pattern])] = lookup(rdb, 'motifs', canonical(pattern), namespace=rman['namespace'], snapshot=rman['snapshot_id'], field=field, limit=1)['count']
            finally: rdb.close()
            keys_here = set(keys.values())
            pos = {(k, f): (p, l) for k, f, p, l in db.execute(q).fetchall() if k in ref_keys}
            ng = {(k, f, n): c for k, f, n, c in db.execute(qn).fetchall() if k in ref_keys}
            motifs_here = {}
            for field, pattern in args.reference_motifs:
                motifs_here[canonical([field, pattern])] = lookup(db, 'motifs', canonical(pattern), namespace=manifest['namespace'], snapshot=manifest['snapshot_id'], field=field, limit=1)['count']
            out['subset_reference'] = {'reference': args.reference, 'reference_records': len(ref_keys), 'all_reference_records_present': ref_keys <= keys_here,
                                       'per_record_positions_equal': pos == ref_pos, 'per_record_ngrams_equal': ng == ref_ng,
                                       'motifs': [{'motif': k, 'reference': ref_motifs[k], 'here': motifs_here[k], 'here_ge_reference': motifs_here[k] >= ref_motifs[k]} for k in ref_motifs],
                                       'note': 'reference counts are a subset population; equality is expected per record, not for whole-snapshot motif totals'}
    finally:
        db.close()
    # 7. Lookup latency through the public verified path (end_to_end includes hashing every payload file).
    lat = []
    for org, value, field in (('report', '', 'atf'), ('postings', 'ABZ579', 'signs'), ('motifs', '["ABZ480","ABZ13"]', 'signs'), ('motifs', '["ina","?","ana"]', 'atf'), ('translations', 'king', 'atf')):
        r = lookup_snapshot(path, org, value, field=field, limit=5)
        lat.append({'organization': org, 'value': value, 'field': field, 'count': r.get('count'), 'rows': len(r.get('rows', [])), **r['timing']})
    out['latency'] = lat
    out['ok'] = (out['record_accounting']['equal_member_keys'] and all(v['unique'] for v in uniq.values()) and out['parquet_integrity']['all_ok']
                 and out['traces']['all_verified'] and out['parity']['all_equal']
                 and (not args.reference or (out['subset_reference']['all_reference_records_present'] and out['subset_reference']['per_record_positions_equal']
                                             and out['subset_reference']['per_record_ngrams_equal'] and all(m['here_ge_reference'] for m in out['subset_reference']['motifs']))))
    out['process_peak_rss_bytes'] = peak_rss_bytes()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['build', 'check'])
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--receipt')
    ap.add_argument('--size', type=int)
    ap.add_argument('--all-eligible', action='store_true')
    ap.add_argument('--projections', default='full', choices=['corpus', 'full'])
    ap.add_argument('--memory', default='8GB')
    ap.add_argument('--max-total-gib', type=float, default=5.0)
    ap.add_argument('--reserve-gib', type=float, default=30.0)
    ap.add_argument('--snapshot')
    ap.add_argument('--reference'); ap.add_argument('--reference-root', type=Path)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    args.root = args.root.expanduser().resolve()
    args.wildcards = {'signs': ['ABZ115', '?', 'ABZ597'], 'atf': ['ina', '?', 'ana']}
    args.reference_motifs = [('signs', ['ABZ480', 'ABZ13']), ('signs', ['ABZ411', 'ABZ411', 'ABZ411']), ('signs', ['ABZ115', '?', 'ABZ597']),
                             ('atf', ['DIŠ', 'ina']), ('atf', ['ina', '?', 'ana'])]
    started = time.monotonic()
    result = build(args) if args.mode == 'build' else check(args)
    result['wall_s'] = round(time.monotonic() - started, 1)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x') as handle: handle.write(json.dumps(result, ensure_ascii=False, indent=1, default=str) + '\n')
    summary = {k: result.get(k) for k in ('snapshot', 'cohort_id', 'cohort_size', 'counts', 'import_s', 'process_peak_rss_bytes', 'peak_stage_bytes_sampled', 'retained_delta_bytes', 'ok', 'wall_s')}
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
