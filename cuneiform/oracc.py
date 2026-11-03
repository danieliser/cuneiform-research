"""ORACC official per-project JSON export (oracc.museum.upenn.edu/json/<project>.zip), contract oracc-cdl-1.

Verified against the acquired ccpo export and doc/opendata/json (2019 revision):
  catalogue.json  members{P: {...}}  -> Artifact + attributed alias Claims (CDLI only when xproject=CDLI; eBL key only by
                                        positional pairing of external_resources / external_resources_key lists)
  corpusjson/P.json  cdl tree; node 'l' = one lemmatized word instance -> WordToken
       f.cf / f.gw / f.pos / f.lang -> Lemma (scoped to project + snapshot); f.sense -> Sense (English contextual sense)
       Word -> Sense is an explicit source assertion per instance (IN_SENSE). gw/sense are lexical glosses, NOT translation.
  Provenance (oracc-cdl-2): Lemma and Sense rows are shared by every attestation, so they carry no instance data.
       Sense.source_locator is a sense-key locator (lemma key + sense) plus a labelled first-attestation pointer.
       Each instance's own sig/inst/norm/epos and payload pointer live on its LEMMATIZED_AS and IN_SENSE edges.
       oracc-cdl-1 (snapshot:edaab55c…) stored the first attesting instance's sig on the Sense row; it is not rewritten.
  Translation text: absent from the JSON export (metadata.formats lists tr-en only). No TranslationSegment is created.
  Graphemes (f.gdl) are retained in raw JSON; sign-level occurrences are not mapped in this adapter revision.

Snapshot raw = JSON array of exact decompressed member bytes [metadata.json, catalogue.json, selected texts...];
selection.json binds each element to the parent zip sha256, member name, CRC and byte range.
"""
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import json
import zipfile
from .adapters import Builder
from .model import PARSER_VERSION, SCHEMA_VERSION, canonical, digest, identity

ADAPTER = 'oracc-cdl-2'
MAX_MEMBER = 16 * 1024 * 1024
MAX_SELECTION = 256 * 1024 * 1024


def _zip(root: Path, receipt_id: str):
    from .acquire import load_receipt, verify_raw
    receipt = load_receipt(root, receipt_id)
    path = verify_raw(root, receipt['sha256'], receipt['bytes'])
    return zipfile.ZipFile(path), receipt


def _member(z: zipfile.ZipFile, name: str) -> bytes:
    info = z.getinfo(name)
    if info.file_size > MAX_MEMBER: raise ValueError(f'zip member exceeds cap: {name}')
    data = z.read(name)  # zipfile checks CRC-32
    if len(data) != info.file_size: raise ValueError('zip member size mismatch')
    return data


def inspect_export(root: Path, receipt_id: str) -> dict:
    z, receipt = _zip(root, receipt_id)
    with z:
        names = z.namelist()
        project = names[0].split('/')[0]
        meta = json.loads(_member(z, f'{project}/metadata.json'))
        cat = json.loads(_member(z, f'{project}/catalogue.json'))
        corpus = json.loads(_member(z, f'{project}/corpus.json'))
        texts = sorted(corpus['members'])
        sample = json.loads(_member(z, f'{project}/' + corpus['members'][texts[0]]))
        counts = {'l': 0, 'with_cf': 0, 'with_sense': 0}
        def walk(x):
            if isinstance(x, dict):
                if x.get('node') == 'l':
                    counts['l'] += 1; f = x.get('f', {}); counts['with_cf'] += bool(f.get('cf')); counts['with_sense'] += bool(f.get('sense'))
                for v in x.values(): walk(v)
            elif isinstance(x, list):
                for v in x: walk(v)
        walk(sample)
    return {'adapter': ADAPTER, 'receipt_id': receipt_id, 'zip_sha256': receipt['sha256'], 'project': project, 'members': len(names),
            'uncompressed_bytes': sum(i.file_size for i in zipfile.ZipFile(root/'raw'/'sha256'/receipt['sha256']).infolist()),
            'config': {k: meta['config'].get(k) for k in ('pathname', 'name', 'abbrev', 'project-type', 'public')},
            'external_project_abbrev': meta['config'].get('options', {}).get('external-proj-abbrev'),
            'formats': {k: len(v) for k, v in meta.get('formats', {}).items()}, 'catalogue_members': len(cat['members']),
            'corpus_texts': len(texts), 'stated_license': {'catalogue': cat.get('license'), 'catalogue_url': cat.get('license-url'), 'text_sample': sample.get('license'), 'timestamp': cat.get('UTC-timestamp')},
            'sample_text': {'textid': texts[0], 'lemma_nodes': counts},
            'translation_text_in_json': False, 'note': 'Translation listed per metadata.formats but no translation text in JSON members.'}


def _external_ebl(entry: dict) -> tuple[list[str], str | None]:
    res = [x.strip() for x in entry.get('external_resources', '').split(';')] if entry.get('external_resources') else []
    keys = [x.strip() for x in entry.get('external_resources_key', '').split(';')] if entry.get('external_resources_key') else []
    if len(res) != len(keys): return [], 'external_resources/external_resources_key length mismatch; no eBL claim'
    return [k for r, k in zip(res, keys) if r == 'eBL' and k], None


def select_texts(z, project: str, *, texts: list[str], match_keys: set[str] | None, max_texts: int) -> list[str]:
    corpus = json.loads(_member(z, f'{project}/corpus.json'))['members']
    chosen = set(texts)
    unknown = chosen - set(corpus)
    if unknown: raise ValueError('texts not in project corpus: ' + ', '.join(sorted(unknown)[:5]))
    if match_keys is not None: chosen |= {t for t in corpus if f'cdli:{t}' in match_keys}
    if not chosen: raise ValueError('no texts selected')
    if len(chosen) > max_texts: raise ValueError(f'{len(chosen)} texts exceed --max-texts {max_texts}')
    return sorted(chosen)


def import_project(config, receipt_id: str, project: str, *, texts: list[str] = (), match_snapshot: Path | None = None, max_texts: int = 100) -> dict:
    from .projections import ProjectionConfig, REVISION
    from .storage import existing_snapshot, materialize, snapshot_identity
    z, receipt = _zip(config.root, receipt_id)
    match = None
    if match_snapshot is not None:
        from .query import connect
        db = connect(match_snapshot)   # verifies (ledger-checked inside a store)
        try: match = {k for (k,) in db.execute("SELECT DISTINCT object_key FROM claim WHERE predicate='catalog_alias' AND object_key LIKE 'cdli:%'").fetchall()}
        finally: db.close()
    with z:
        corpus = json.loads(_member(z, f'{project}/corpus.json'))['members']
        chosen = select_texts(z, project, texts=list(texts), match_keys=match, max_texts=max_texts)
        names = [f'{project}/metadata.json', f'{project}/catalogue.json'] + [f'{project}/' + corpus[t] for t in chosen]
        members, parts, offset = [], [b'[\n'], 2
        for i, name in enumerate(names):
            data = _member(z, name)
            json.loads(data)  # each member must be one complete JSON value
            if i: parts.append(b',\n'); offset += 2
            info = z.getinfo(name)
            members.append({'payload_index': i, 'payload_pointer': f'/{i}', 'member': name, 'crc32': f'{info.CRC:08x}', 'bytes': len(data), 'sha256': digest(data), 'payload_start': offset, 'payload_end': offset + len(data)})
            parts.append(data); offset += len(data)
            if offset > MAX_SELECTION: raise ValueError('selection exceeds cap')
        parts.append(b'\n]\n')
    payload = b''.join(parts)
    namespace = f'oracc/{project}'
    selection = {'adapter': ADAPTER, 'project': project, 'texts': chosen, 'selection_rule': 'explicit texts' + (' + texts whose P-number equals a cdli alias claim in snapshot ' + match_snapshot.name if match_snapshot else ''),
                 'parent': {'sha256': receipt['sha256'], 'bytes': receipt['bytes'], 'url': receipt['url'], 'receipt_id': receipt['receipt_id'], 'acquired_at': receipt['finished_at'], 'last_modified': receipt['response_headers'].get('last-modified')},
                 'members': members, 'payload_sha256': digest(payload)}
    selection['selection_id'] = identity('oracc-selection', canonical(selection))
    selection['manifest_sha256'] = digest(canonical(selection).encode())
    projections = ProjectionConfig()
    projection_spec = {'revision': REVISION, 'config': asdict(projections)}
    source = 'oracc-selection'; record_id = selection['selection_id']; url = receipt['url']
    sid = snapshot_identity(namespace, source, digest(payload), SCHEMA_VERSION, PARSER_VERSION, record_id, url, projection_spec)
    if (existing := existing_snapshot(config, sid)): return existing
    config.guard(len(payload) * 50 + 64 * 1024 * 1024)
    stats = {}

    def load(db, stage):
        b = Builder(db, sid, namespace, spool_dir=stage/'spool'); b.raw_sha256 = digest(payload)
        stats.update(map_selection(b, payload, members, project))
        b.flush()
    rights = {'status': 'source-stated', 'claims': [{'source': f'{project} catalogue.json / corpusjson license field', 'license': 'CC0 1.0 (\"This data is released under the CC0 license\")'},
                                                   {'source': 'oracc.museum.upenn.edu documentation page footer', 'license': 'CC BY-SA 3.0 (documentation site)'}],
              'reuse': 'source states CC0 for these JSON data; per-text scholarly attribution still expected; not legally reviewed', 'authentication': 'hash binds bytes, not a grant'}
    meta = {'namespace': namespace, 'source': source, 'source_url': url, 'record_id': record_id, 'rights': rights, 'adapter': ADAPTER,
            'selection': {'selection_id': record_id, 'manifest_sha256': selection['manifest_sha256'], 'texts': len(chosen), 'parent': selection['parent']}, 'ingestion': stats}
    result = materialize(config, sid, payload, load, projections, projection_spec, meta, {'selection.json': json.dumps(selection, ensure_ascii=False, indent=1).encode() + b'\n'}, memory='1GB')
    return {'snapshot': result['snapshot'], 'reused': result['reused'], 'counts': result['manifest']['counts'], 'ingestion': stats, 'texts': chosen}


def map_selection(b: Builder, payload: bytes, members: list[dict], project: str) -> dict:
    meta = json.loads(payload[members[0]['payload_start']:members[0]['payload_end']])
    catalogue = json.loads(payload[members[1]['payload_start']:members[1]['payload_end']])
    revision = catalogue.get('UTC-timestamp', 'unknown')
    tr_listed = set(meta.get('formats', {}).get('tr-en', []))
    stats = {'texts': 0, 'words': 0, 'lemmatized_words': 0, 'words_with_sense': 0, 'lemmas': 0, 'senses': 0, 'cdli_claims': 0, 'ebl_claims': 0, 'translation_listed_but_absent': 0}
    lemmas, senses = set(), set()
    for m in members[2:]:
        doc = json.loads(payload[m['payload_start']:m['payload_end']])
        textid = doc['textid']; entry = catalogue['members'].get(textid, {})
        rid = identity('source', b.namespace, b.snapshot, textid, m['payload_pointer'])
        aid = identity('artifact', b.namespace, textid)
        b.add('source_record', rid, b.namespace, textid, m['payload_pointer'], canonical(doc))
        b.add('source_binding', rid, b.snapshot, b.raw_sha256)
        b.add('artifact', aid, rid, textid, canonical(dict(entry, _catalogue_pointer=f'/1/members/{textid}')))
        if entry.get('xproject') == 'CDLI' and textid.startswith('P'):
            b.add('claim', identity('claim', rid, 'xproject', textid), rid, aid, 'catalog_alias', 'cdli:' + textid, 'source-attributed-unreviewed',
                  'ORACC catalogue entry declares xproject=CDLI for this P-number text ID; no identity merge', canonical({'locator': f'/1/members/{textid}/xproject', 'uri': entry.get('uri'), 'independence': 'unknown'}))
            stats['cdli_claims'] += 1
        keys, problem = _external_ebl(entry)
        if problem: b.exclude(rid, f'/1/members/{textid}/external_resources', problem)
        for k in keys:
            b.add('claim', identity('claim', rid, 'ebl', k), rid, aid, 'catalog_alias', 'ebl:' + k, 'source-attributed-unreviewed',
                  'ORACC catalogue external_resources lists eBL with this key (positional pairing of two parallel lists); no identity merge',
                  canonical({'locator': f'/1/members/{textid}/external_resources_key', 'pairing': 'positional', 'independence': 'unknown'}))
            stats['ebl_claims'] += 1
        wid = identity('witness', rid)
        b.add('witness', wid, rid, aid, f'ORACC {project} edition of {textid}; composition unknown')
        b.edge('ON_ARTIFACT', wid, aid, rid)
        sid = identity('sequence', rid, 'oracc-lem', ADAPTER)
        b.add('sequence_version', sid, rid, wid, 'oracc-lem', ADAPTER, 'source-lemmatization')
        b.edge('HAS_SEQUENCE', wid, sid, rid)
        if textid in tr_listed:
            b.exclude(rid, '/0/formats/tr-en', 'English translation listed in project metadata; translation text absent from JSON export')
            stats['translation_listed_but_absent'] += 1
        stats['texts'] += 1
        order = 0; line = None

        def walk(x, path):
            nonlocal order, line
            if isinstance(x, dict):
                if x.get('node') == 'd' and x.get('type') == 'line-start': line = x.get('label')
                if x.get('node') == 'l': word(x, path)
                for k, v in x.items():
                    if isinstance(v, (dict, list)): walk(v, f'{path}/{k}')
            elif isinstance(x, list):
                for i, v in enumerate(x): walk(v, f'{path}/{i}')

        def word(node, path):
            nonlocal order
            f = node.get('f', {}) if isinstance(node.get('f'), dict) else {}
            wid_ = identity('word', sid, node.get('id'), path)
            locator = canonical({'payload_pointer': m['payload_pointer'] + path, 'word_id': node.get('id'), 'ref': node.get('ref'), 'line_label': line, 'frag': node.get('frag'), 'order': order})
            b.add('word_token', wid_, sid, locator, f.get('form'), 'ORACC cdl l-node (source word instance); graphemes in source f.gdl, not mapped')
            b.edge('HAS_WORD', sid, wid_, rid, order=order, line_label=line)
            order += 1; stats['words'] += 1
            cf = f.get('cf')
            if not cf:
                b.exclude(rid, m['payload_pointer'] + path, f'word without citation form (pos={f.get("pos")}); no lemma asserted'); return
            lid = identity('lemma', b.namespace, b.snapshot, f.get('lang'), cf, f.get('gw'), f.get('pos'))
            if lid not in lemmas:
                lemmas.add(lid); stats['lemmas'] += 1
                # Lemma rows are attributed to the first attesting text in sorted selection order; every attestation is an edge.
                b.add('lemma', lid, rid, b.namespace, cf, f.get('lang'), f.get('pos'), f'{project}@{revision}')
            b.edge('LEMMATIZED_AS', wid_, lid, rid, sig=node.get('sig'), inst=node.get('inst'), epos=f.get('epos'), norm=f.get('norm'), guideword=f.get('gw'))
            stats['lemmatized_words'] += 1
            if f.get('sense'):
                sense_id = identity('sense', lid, f['sense'])
                if sense_id not in senses:
                    senses.add(sense_id); stats['senses'] += 1
                        # Shared node: a sense-level locator only. The first attestation is a labelled pointer, never its sig.
                    b.add('sense', sense_id, lid, f.get('gw'), f['sense'], canonical({
                        'locator_kind': 'oracc-sense-key', 'project': project, 'lemma_key': {'lang': f.get('lang'), 'cf': cf, 'gw': f.get('gw'), 'pos': f.get('pos')},
                        'sense': f['sense'], 'first_attestation_in_selection': {'word_id': wid_, 'payload_pointer': m['payload_pointer'] + path},
                        'instance_attribution': 'per occurrence on LEMMATIZED_AS / IN_SENSE edge qualification (sig, inst, norm, epos)'}))
                    b.edge('HAS_SENSE', lid, sense_id, rid, attribution='source record of the first attestation in selection order; the sense is shared by all attestations')
                b.edge('IN_SENSE', wid_, sense_id, rid, basis='ORACC contextual sense on this lemmatization instance; English lexical gloss, not a translation',
                       sig=node.get('sig'), inst=node.get('inst'), payload_pointer=m['payload_pointer'] + path)
                stats['words_with_sense'] += 1

        walk(doc.get('cdl', []), '/cdl')
        b.commit()
    return stats


def trace_word(snapshot: Path, word_id: str, parent_root: Path | None = None) -> dict:
    """Re-resolve a WordToken inside the snapshot payload and (optionally) inside the parent zip member."""
    from .storage import verify
    from .query import open_verified
    manifest = verify(snapshot)
    db = open_verified(snapshot, manifest)
    try:
        row = db.execute('SELECT w.source_locator,w.form,s.source_record_id FROM word_token w JOIN sequence_version s ON s.id=w.sequence_id WHERE w.id=?', [word_id]).fetchone()
        if row is None: raise ValueError('unknown word ID')
        lemma = db.execute("SELECT l.citation_form,l.language,l.pos,e.qualification FROM edge e JOIN lemma l ON l.id=e.target_id WHERE e.kind='LEMMATIZED_AS' AND e.source_id=?", [word_id]).fetchone()
        sense = db.execute("SELECT s.guideword,s.gloss FROM edge e JOIN sense s ON s.id=e.target_id WHERE e.kind='IN_SENSE' AND e.source_id=?", [word_id]).fetchone()
    finally:
        db.close()
    loc = json.loads(row[0])
    selection = json.loads((snapshot/'selection.json').read_text())
    pointer = loc['payload_pointer']; top = '/' + pointer.split('/')[1]
    member = next(m for m in selection['members'] if m['payload_pointer'] == top)
    raw = (snapshot/'raw').read_bytes()[member['payload_start']:member['payload_end']]
    if digest(raw) != member['sha256']: raise ValueError('payload member hash mismatch')
    node = json.loads(raw)
    for part in pointer.split('/')[2:]: node = node[int(part)] if isinstance(node, list) else node[part]
    f = node.get('f', {})
    if node.get('id') != loc['word_id'] or f.get('form') != row[1]: raise ValueError('word round-trip failed')
    if lemma and (f.get('cf'), f.get('lang'), f.get('pos')) != lemma[:3]: raise ValueError('lemma round-trip failed')
    if sense and (f.get('gw'), f.get('sense')) != sense: raise ValueError('sense round-trip failed')
    out = {'word_id': word_id, 'source_word_id': loc['word_id'], 'ref': loc['ref'], 'line_label': loc['line_label'], 'frag': loc['frag'], 'form': row[1],
           'lemma': {'cf': f.get('cf'), 'gw': f.get('gw'), 'pos': f.get('pos'), 'lang': f.get('lang')} if lemma else None,
           'sense_english_gloss': f.get('sense'), 'gloss_status': 'lexical sense label, not a translation', 'member': member['member'], 'member_sha256': member['sha256'],
           'payload_pointer': pointer, 'rights': manifest['rights']}
    if parent_root is not None:
        from .acquire import raw_path, hash_file
        zpath = raw_path(parent_root, selection['parent']['sha256'])
        if not zpath.is_file(): out['parent_trace'] = {'status': 'parent-raw-unavailable'}
        else:
            if hash_file(zpath)['sha256'] != selection['parent']['sha256']: raise ValueError('parent zip integrity failure')
            with zipfile.ZipFile(zpath) as z:
                if _member(z, member['member']) != raw: raise ValueError('parent zip member differs from payload member')
            out['parent_trace'] = {'status': 'verified', 'zip_sha256': selection['parent']['sha256'], 'member': member['member'], 'crc32': member['crc32']}
    return out
