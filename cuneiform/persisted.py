"""Canonical query paths over verified persisted snapshots (read-only), plus portable graph export."""
from datetime import datetime, timezone
from pathlib import Path
import json
import time
import duckdb
from .model import canonical, digest, identity
from .query import connect, motif, array_count
from .storage import verify, file_sha256
from .projections import lookup, report

EXPORTER = 'portable-graph-1'


def scope(path: Path, manifest: dict | None=None) -> dict:
    """What population a snapshot's counts describe. Cohort and selection snapshots are samples, never the corpus."""
    manifest = manifest or verify(path)
    src = manifest['source']
    base = {'snapshot_id': manifest['snapshot_id'], 'source': src, 'namespace': manifest['namespace'], 'snapshot_contract': manifest.get('snapshot_contract'),
            'records_in_snapshot': manifest['counts'].get('source_record'), 'rights_status': manifest['rights'].get('status')}
    if src == 'ebl-cohort':
        c = json.loads((path/'cohort.json').read_text())   # bound to the manifest by hash in verify()
        p = c['parent']
        size = len(c['records'])
        base.update({'kind': 'rule-selected cohort', 'cohort_id': c['cohort_id'], 'cohort_size': size, 'eligible_records': c['eligible_records'], 'parent_records': c['parent_records'],
                     'excluded_by_reason': c['excluded_by_reason'], 'rule': c['rule'], 'selector': c['selector'], 'parser_version': c['parser_version'],
                     'parent': {k: p.get(k) for k in ('sha256', 'md5', 'bytes', 'url', 'receipt_id', 'label', 'acquired_at')}, 'provenance': c['provenance'],
                     'label': f"COHORT {size}/{c['eligible_records']:,} eligible of {c['parent_records']:,}",
                     'scope_note': f"Counts are within a {size}-record cohort selected by rule {c['rule']['name']} (ordered by {c['rule']['order']}) from {c['eligible_records']:,} eligible of {c['parent_records']:,} parent records. They are not corpus frequencies."})
    elif src in ('oracc-selection', 'cdli-selection'):
        sel = json.loads((path/'selection.json').read_text())
        n = len(sel['members']) - (2 if src == 'oracc-selection' else 0)
        base.update({'kind': 'explicit selection', 'selection_id': sel['selection_id'], 'selection_rule': sel['selection_rule'], 'selected': n,
                     'parent': sel.get('parent') or {'members': len(sel['members']), 'receipts': 'one receipt per member (see selection.json)'},
                     'label': f'SELECTION {n}', 'scope_note': f'Counts are within {n} explicitly selected {"ORACC texts" if src == "oracc-selection" else "CDLI catalog records"}; not project or catalog totals.'})
    else:
        base.update({'kind': 'single input', 'label': 'INPUT', 'scope_note': 'Counts are within this one imported input file.'})
    return base


def lookup_snapshot(path: Path, organization: str, value: str='', *, namespace=None, snapshot=None, **options) -> dict:
    manifest = verify(path)
    db = connect(path)
    try:
        started = time.monotonic()
        if organization == 'report':
            result = report(db)
        else:
            # A verified snapshot has exactly one textual scope: default the explicit scope from its manifest.
            result = lookup(db, organization, value, namespace=namespace or manifest['namespace'], snapshot=snapshot or manifest['snapshot_id'], **options)
        return dict(result, snapshot=manifest['snapshot_id'], scope=scope(path, manifest), latency_ms=round((time.monotonic() - started) * 1000, 1))
    finally:
        db.close()


def parity(path: Path, pattern: list[str], field: str='signs') -> dict:
    """Independent graph traversal, sequence-array scan and materialized n-gram index counts for one motif."""
    manifest = verify(path)
    out = {'snapshot': manifest['snapshot_id'], 'pattern': pattern, 'field': field, 'scope': scope(path, manifest)}
    t = time.monotonic(); graph = motif(path, pattern, field); out['graph_ms'] = round((time.monotonic() - t) * 1000, 1)
    t = time.monotonic(); out['array'] = array_count(path, pattern, field); out['array_ms'] = round((time.monotonic() - t) * 1000, 1)
    db = connect(path)
    try:
        t = time.monotonic()
        indexed = lookup(db, 'motifs', canonical(pattern), namespace=manifest['namespace'], snapshot=manifest['snapshot_id'], field=field, limit=1)
        out['index_ms'] = round((time.monotonic() - t) * 1000, 1)
    finally:
        db.close()
    out.update({'graph': graph['occurrences'], 'index': indexed['count'], 'witnesses': graph['witnesses'], 'artifacts': graph['artifacts'],
                'denominators': graph['denominators'], 'evidence': graph['evidence'], 'policy': graph['policy'], 'gap_extent': graph['gap_extent'],
                'parity': graph['occurrences'] == out['array'] == indexed['count'], 'example_match': graph['matches'][0] if graph['matches'] else None})
    return out


def export_graph(path: Path, config) -> dict:
    """Write nodes/edges Parquet (same IDs as canonical tables) under <root>/derived/exports. Never touches the snapshot."""
    manifest = verify(path)
    eid = identity('graph-export', EXPORTER, manifest['snapshot_id'], manifest['manifest_sha256'])
    target = config.root/'derived'/'exports'/eid.replace(':', '-')
    if target.exists():
        receipt = json.loads((target/'receipt.json').read_text())
        for name, sha in receipt['files'].items():
            if file_sha256(target/name) != sha: raise ValueError('graph export integrity failure: ' + name)
        return dict(receipt, reused=True)
    config.guard(manifest.get('snapshot_payload_bytes', 0))
    stage = target.parent/('.pending-' + target.name)
    stage.mkdir(parents=True)
    try:
        db = connect(path)
        try:
            dangling = db.execute('SELECT count(*) FROM portable_edge e WHERE NOT EXISTS (SELECT 1 FROM nodes n WHERE n.id=e.source_id) OR NOT EXISTS (SELECT 1 FROM nodes n WHERE n.id=e.target_id)').fetchone()[0]
            if dangling: raise ValueError(f'{dangling} portable edges have missing endpoints; export refused')
            for name, sql in (('nodes.parquet', 'SELECT * FROM nodes ORDER BY id'), ('edges.parquet', 'SELECT * FROM portable_edge ORDER BY id')):
                literal = str(stage/name).replace("'", "''")
                db.execute(f"COPY ({sql}) TO '{literal}' (FORMAT PARQUET)")
            node_kinds = dict(db.execute('SELECT kind,count(*) FROM nodes GROUP BY 1 ORDER BY 1').fetchall())
            edge_kinds = dict(db.execute('SELECT kind,count(*) FROM portable_edge GROUP BY 1 ORDER BY 1').fetchall())
        finally:
            db.close()
        files = {n: file_sha256(stage/n) for n in ('nodes.parquet', 'edges.parquet')}
        receipt = {'export_id': eid, 'exporter': EXPORTER, 'snapshot_id': manifest['snapshot_id'], 'snapshot_manifest_sha256': manifest['manifest_sha256'],
                   'raw_sha256': manifest['raw_sha256'], 'schema_version': manifest['schema_version'], 'parser_version': manifest['parser_version'],
                   'projection_spec': manifest.get('projection_spec'), 'node_kinds': node_kinds, 'edge_kinds': edge_kinds, 'dangling_edges': 0, 'files': files,
                   'contract': 'node(id,kind); edge(id,source_id,target_id,kind,source_record_id,qualification JSON). Properties: join snapshot parquet/<table>.parquet on id. Labels are never identities; rebuild from snapshot, never edit.',
                   'created_at': datetime.now(timezone.utc).isoformat()}
        (stage/'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
        stage.rename(target)
        return dict(receipt, directory=str(target))
    except BaseException:
        import shutil; shutil.rmtree(stage, ignore_errors=True); raise


def catalog_link(paths: list[Path], key: str) -> dict:
    """Exact catalog key across separately verified snapshots: alias claims and catalog artifacts as candidates only."""
    out = []
    for path in paths:
        manifest = verify(path)
        db = connect(path)
        try:
            claims = [dict(zip(['claim_id','subject_artifact','object_key','status','rationale','details'], r)) for r in db.execute("SELECT id,subject_id,object_key,status,rationale,details FROM claim WHERE predicate='catalog_alias' AND object_key=? ORDER BY id", [key]).fetchall()]
            for c in claims:
                c['subject_catalog_key'] = db.execute('SELECT catalog_key FROM artifact WHERE id=?', [c['subject_artifact']]).fetchone()[0]
            artifacts = [dict(zip(['artifact_id','catalog_key','namespace'], r)) for r in db.execute("SELECT a.id,a.catalog_key,r.namespace FROM artifact a JOIN source_record r ON r.id=a.source_record_id WHERE r.namespace || ':' || a.catalog_key=? ORDER BY a.id", [key]).fetchall()]
        finally:
            db.close()
        out.append({'snapshot': manifest['snapshot_id'], 'source': manifest['source'], 'namespace': manifest['namespace'], 'alias_claims': claims, 'catalog_artifacts': artifacts})
    return {'key': key, 'snapshots': out, 'merge': 'none; identical keys are candidate links. Independence of sources unknown.',
            'alias_claims_total': sum(len(s['alias_claims']) for s in out), 'catalog_artifacts_total': sum(len(s['catalog_artifacts']) for s in out)}
