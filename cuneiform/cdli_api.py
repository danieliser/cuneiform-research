"""CDLI current framework artifact metadata (https://cdli.earth/artifacts/<id>.json), contract cdli-artifact-json-1.

Bounded: exact P-numbers taken from existing attributed alias claims; each record is one allowlisted acquisition with a
receipt. Catalog-only: Artifact + attributed alias Claims (museum/accession labels, structured external_resources).
No witness, text or name-based merge. Inscriptions are not fetched in this revision.
"""
from dataclasses import asdict
from pathlib import Path
import json
import re
import time
from .adapters import Builder
from .model import PARSER_VERSION, SCHEMA_VERSION, canonical, digest, identity

ADAPTER = 'cdli-artifact-json-1'
BASE = 'https://cdli.earth/artifacts/{}.json'
RIGHTS = {'status': 'source-stated-terms', 'claims': [{'source': 'https://cdli.earth/terms-of-use (acquired 2026-11-03)', 'statement': 'Transliterations and translations may be freely copied, aggregated and re-used according to common and fair academic practice; mention CDLI and https://cdli.earth for considerable re-use. Images: non-commercial; photographs owned by holding institutions.'}],
          'reuse': 'catalog metadata not separately licensed in the terms; attribution required in practice; not legally reviewed', 'authentication': 'hash binds bytes, not a grant'}


def pnumbers_from_snapshot(path: Path) -> list[str]:
    from .query import connect
    db = connect(path)
    try: keys = [k for (k,) in db.execute("SELECT DISTINCT object_key FROM claim WHERE predicate='catalog_alias' AND object_key LIKE 'cdli:P%' ORDER BY 1").fetchall()]
    finally: db.close()
    return [k[5:] for k in keys if re.fullmatch(r'cdli:P\d{6}', k)]


def fetch(config, pnumbers: list[str], allowlist: Path, delay: float = 1.0, max_records: int = 100) -> list[dict]:
    from .acquire import acquire, receipts
    if len(pnumbers) > max_records: raise ValueError('too many records for bounded CDLI acquisition')
    have = {r['url']: r for r in receipts(config.root) if r['label'].startswith('cdli-artifact-json')}
    out = []
    for p in pnumbers:
        url = BASE.format(int(p[1:]))
        if url in have: out.append(have[url]); continue
        out.append(acquire(url, allowlist, config, max_bytes=1 << 20, label='cdli-artifact-json:' + p, rights=RIGHTS,
                           context={'adapter': ADAPTER, 'pnumber': p, 'selection': 'exact P-number from attributed alias claims'}))
        time.sleep(delay)
    return out


def import_artifacts(config, receipt_list: list[dict]) -> dict:
    from .acquire import verify_raw
    from .projections import ProjectionConfig, REVISION
    from .storage import existing_snapshot, materialize, snapshot_identity
    members, parts, offset = [], [b'[\n'], 2
    for i, r in enumerate(sorted(receipt_list, key=lambda r: r['url'])):
        data = verify_raw(config.root, r['sha256'], r['bytes']).read_bytes()
        json.loads(data)
        if i: parts.append(b',\n'); offset += 2
        members.append({'payload_index': i, 'payload_pointer': f'/{i}', 'url': r['url'], 'receipt_id': r['receipt_id'], 'sha256': r['sha256'], 'bytes': len(data), 'acquired_at': r['finished_at'], 'payload_start': offset, 'payload_end': offset + len(data)})
        parts.append(data); offset += len(data)
    parts.append(b'\n]\n'); payload = b''.join(parts)
    selection = {'adapter': ADAPTER, 'members': members, 'payload_sha256': digest(payload), 'selection_rule': 'exact P-numbers from attributed alias claims'}
    selection['selection_id'] = identity('cdli-selection', canonical(selection))
    selection['manifest_sha256'] = digest(canonical(selection).encode())
    projections = ProjectionConfig(); spec = {'revision': REVISION, 'config': asdict(projections)}
    source, ns = 'cdli-selection', 'cdli'
    sid = snapshot_identity(ns, source, digest(payload), SCHEMA_VERSION, PARSER_VERSION, selection['selection_id'], 'https://cdli.earth/artifacts/', spec)
    if (existing := existing_snapshot(config, sid)): return existing
    stats = {}

    def load(db, stage):
        b = Builder(db, sid, ns, spool_dir=stage/'spool'); b.raw_sha256 = digest(payload)
        stats.update(map_records(b, payload, members))
        b.flush()
    meta = {'namespace': ns, 'source': source, 'source_url': 'https://cdli.earth/artifacts/', 'record_id': selection['selection_id'], 'rights': RIGHTS, 'adapter': ADAPTER,
            'selection': {'selection_id': selection['selection_id'], 'manifest_sha256': selection['manifest_sha256'], 'records': len(members)}, 'ingestion': stats}
    r = materialize(config, sid, payload, load, projections, spec, meta, {'selection.json': json.dumps(selection, ensure_ascii=False, indent=1).encode() + b'\n'})
    return {'snapshot': r['snapshot'], 'reused': r['reused'], 'counts': r['manifest']['counts'], 'ingestion': stats}


def map_records(b: Builder, payload: bytes, members: list[dict]) -> dict:
    stats = {'records': 0, 'rejected': 0, 'claims': 0}
    for m in members:
        doc = json.loads(payload[m['payload_start']:m['payload_end']])
        try:
            if not isinstance(doc, list) or len(doc) != 1 or not isinstance(doc[0], dict) or not isinstance(doc[0].get('id'), int): raise ValueError('expected one artifact object')
            row = doc[0]; key = 'P' + str(row['id']).zfill(6)
            rid, aid = b.record(key, m['payload_pointer'], doc)
            for field in ('museum_no', 'accession_no'):
                if row.get(field): b.alias(rid, aid, 'catalog-label:' + row[field], f"{m['payload_pointer']}/0/{field}"); stats['claims'] += 1
            for j, e in enumerate(row.get('external_resources') or []):
                abbrev = (e.get('external_resource') or {}).get('abbrev'); k = e.get('external_resource_key')
                if abbrev and k:
                    b.alias(rid, aid, ('ebl:' if abbrev == 'eBL' else f'external:{abbrev}:') + k, f"{m['payload_pointer']}/0/external_resources/{j}"); stats['claims'] += 1
            b.exclude(rid, m['payload_pointer'], 'catalog record only; inscription/text not fetched')
            b.commit(); stats['records'] += 1
        except ValueError as exc:
            b.discard(); b.add('rejection', identity('reject', b.snapshot, m['payload_pointer']), m['payload_pointer'], str(exc), canonical(doc)); b.commit(); stats['rejected'] += 1
    return stats
