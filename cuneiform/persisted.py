"""Canonical query paths over verified persisted snapshots (read-only), plus portable graph export."""
from datetime import datetime, timezone
from pathlib import Path
import json
import time
import duckdb
from .model import canonical, digest, identity
from .query import connect, open_verified, motif, array_count
from .storage import verify, verified, file_sha256, publication_of, snapshot_identity
from .projections import lookup, report

LATENCY_NOTE = 'latency_ms is query-only (SQL after the snapshot was verified); end_to_end_ms includes verification, which hashes every payload file'


class ScopeMismatch(ValueError):
    """A caller-supplied namespace/snapshot cannot match the verified snapshot: an error, never an empty result."""


class LayerUnavailable(ValueError):
    """The snapshot has no rows for the layer an organization reads. Unavailable is not zero."""
    def __init__(self, organization: str, table: str, source: str):
        super().__init__(f'layer unavailable: {organization!r} reads {table}, which has no rows in this {source} snapshot (not loaded; not a zero count)')
        self.organization, self.table, self.source = organization, table, source


# Organization -> canonical table whose emptiness means the layer was never loaded in this snapshot.
LAYER_OF = {'words': 'word_token', 'lemmas': 'lemma', 'translations': 'translation_segment', 'sequence': 'occurrence', 'occurrence': 'occurrence',
            'span': 'occurrence', 'postings': 'occurrence', 'motifs': 'occurrence', 'reverse-postings': 'occurrence', 'reverse-motifs': 'occurrence',
            'catalog': 'artifact'}


def input_identity(manifest: dict) -> str:
    """Contract-independent identity of a snapshot's inputs: equal for a legacy snapshot and a manifest-3 rebuild of the
    same inputs (the legacy ID formula). Lets discovery group same-input snapshots without merging them."""
    parts = [manifest['namespace'], manifest['source'], manifest['raw_sha256'], manifest['schema_version'], manifest['parser_version'], manifest['record_id'], manifest['source_url']]
    if manifest['schema_version'] != '1': parts.append(manifest['projection_spec'])
    return snapshot_identity(*parts, contract=None)

EXPORTER = 'portable-graph-1'


def scope(path: Path, manifest: dict | None=None) -> dict:
    """What population a snapshot's counts describe. Cohort and selection snapshots are samples, never the corpus."""
    if manifest is None:
        checked = verified(path); manifest = checked['manifest']; publication = checked['publication']
    else:
        publication = publication_of(path, manifest)   # ledger check only; the caller verified content
    src = manifest['source']
    base = {'snapshot_id': manifest['snapshot_id'], 'source': src, 'namespace': manifest['namespace'], 'snapshot_contract': manifest.get('snapshot_contract'),
            'identity_formula': manifest.get('snapshot_contract') or 'legacy (pre-manifest-3)', 'input_identity': input_identity(manifest),
            'records_in_snapshot': manifest['counts'].get('source_record'), 'rights_status': manifest['rights'].get('status'), 'publication': publication}
    if src == 'ebl-cohort':
        c = json.loads((path/'cohort.json').read_text())   # bound to the manifest by hash in verify()
        p = c['parent']
        size = len(c['records'])
        base.update({'kind': 'rule-selected cohort', 'cohort_id': c['cohort_id'], 'cohort_size': size, 'eligible_records': c['eligible_records'], 'parent_records': c['parent_records'],
                     'excluded_by_reason': c['excluded_by_reason'], 'rule': c['rule'], 'selector': c['selector'], 'parser_version': c['parser_version'],
                     'parent': {k: p.get(k) for k in ('sha256', 'md5', 'bytes', 'url', 'receipt_id', 'label', 'acquired_at')}, 'provenance': c['provenance'],
                     'label': f"COHORT {size}/{c['eligible_records']:,} eligible of {c['parent_records']:,}",
                     'scope_note': f"Counts are within a {size}-record cohort selected by rule {c['rule']['name']} (ordered by {c['rule']['order']}) from {c['eligible_records']:,} eligible of {c['parent_records']:,} parent records. They are not corpus frequencies."})
        if c['size'] is None and c['rule'].get('cdli_in') is None:
            # All-eligible cohort of one fixed release: the population is the whole eligible release, still parser-bounded.
            from .corpus import accounting
            acc = accounting(c)
            release = p.get('label') or p.get('url') or p['sha256']
            excluded = c['parent_records'] - c['eligible_records']
            reasons = '; '.join(f'{k}: {v:,}' for k, v in c['excluded_by_reason'].items())
            base.update({'kind': 'all eligible records of a fixed release', 'accounting': acc,
                         'release': {'label': p.get('label'), 'url': p.get('url'), 'sha256': p['sha256'], 'md5': p.get('md5'), 'bytes': p.get('bytes'), 'receipt_id': p.get('receipt_id')},
                         'label': f"FULL ELIGIBLE {size:,}/{c['parent_records']:,} · {release}",
                         'scope_note': (f"Counts cover every record of the fixed release {release} (sha256 {p['sha256'][:12]}…) that is eligible under rule {c['rule']['name']}: "
                                        f"{size:,} of {c['parent_records']:,} parent records; {excluded:,} excluded ({reasons}). Parsing is conservative ({c['parser_version']}): "
                                        "unsupported grammar is kept as blocking positions, so counts are frequencies of represented positions within this conservative parse of "
                                        "eligible records. They are not linguistic completeness, and they exclude ineligible records and every other release or corpus.")})
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
    started = time.monotonic()
    checked = verified(path); manifest = checked['manifest']
    verify_ms = round((time.monotonic() - started) * 1000, 1)
    # A verified snapshot has exactly one textual scope. An explicit override that cannot match it is an error.
    if namespace is not None and namespace != manifest['namespace']:
        raise ScopeMismatch(f'namespace {namespace!r} is not this snapshot\'s namespace {manifest["namespace"]!r}')
    if snapshot is not None and snapshot != manifest['snapshot_id']:
        raise ScopeMismatch(f'snapshot {snapshot!r} is not the verified snapshot {manifest["snapshot_id"]}')
    table = LAYER_OF.get(organization)
    if table is not None and not manifest['counts'].get(table):
        raise LayerUnavailable(organization, table, manifest['source'])
    db = open_verified(path, manifest)
    try:
        t = time.monotonic()
        if organization == 'report':
            result = report(db)
        else:
            result = lookup(db, organization, value, namespace=manifest['namespace'], snapshot=manifest['snapshot_id'], **options)
        query_ms = round((time.monotonic() - t) * 1000, 1)
    finally:
        db.close()
    out = dict(result, snapshot=manifest['snapshot_id'], scope=scope(path, manifest))
    out.update(latency_ms=query_ms, latency_scope='query-only',
               timing={'verify_ms': verify_ms, 'query_ms': query_ms, 'end_to_end_ms': round((time.monotonic() - started) * 1000, 1), 'note': LATENCY_NOTE})
    return out


def parity(path: Path, pattern: list[str], field: str='signs') -> dict:
    """Independent graph traversal, sequence-array scan and materialized n-gram index counts for one motif."""
    started = time.monotonic()
    manifest = verify(path)
    verify_ms = round((time.monotonic() - started) * 1000, 1)
    out = {'snapshot': manifest['snapshot_id'], 'pattern': pattern, 'field': field, 'scope': scope(path, manifest)}
    db = open_verified(path, manifest)   # one verification for all three paths
    try:
        t = time.monotonic(); graph = motif(db, pattern, field); out['graph_ms'] = round((time.monotonic() - t) * 1000, 1)
        t = time.monotonic(); out['array'] = array_count(db, pattern, field); out['array_ms'] = round((time.monotonic() - t) * 1000, 1)
        t = time.monotonic()
        indexed = lookup(db, 'motifs', canonical(pattern), namespace=manifest['namespace'], snapshot=manifest['snapshot_id'], field=field, limit=1)
        out['index_ms'] = round((time.monotonic() - t) * 1000, 1)
    finally:
        db.close()
    out['timing'] = {'verify_ms': verify_ms, 'end_to_end_ms': round((time.monotonic() - started) * 1000, 1),
                     'note': 'graph_ms/array_ms/index_ms are query-only; end_to_end_ms includes the single snapshot verification'}
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
        db = open_verified(path, manifest)
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
        db = open_verified(path, manifest)
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
