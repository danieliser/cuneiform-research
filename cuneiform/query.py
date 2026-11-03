"""Bounded exact graph motifs over represented positions, with an independent array oracle."""
from pathlib import Path
import json
import duckdb
from .adapters import records
from .model import identity, digest, canonical
from .storage import verify


def connect(path: Path | duckdb.DuckDBPyConnection):
    if isinstance(path, duckdb.DuckDBPyConnection):
        return path.cursor()
    return open_verified(path, verify(path))


def open_verified(path: Path, manifest: dict):
    """Open graph.duckdb read-only for a manifest the caller has just verified in this same call (no second hash pass)."""
    db=duckdb.connect(str(path/'graph.duckdb'),read_only=True)
    if manifest['schema_version']!='1':
        registry=db.execute('SELECT revision,config FROM projection_registry').fetchall()
        spec=manifest['projection_spec']
        if len(registry)!=1 or registry[0][0]!=spec['revision'] or json.loads(registry[0][1])!=spec['config']:
            db.close(); raise ValueError('projection registry does not match manifest projection specification')
        if 'projection_registry' in manifest:
            from .projections import mark_frozen_verified
            try: mark_frozen_verified(db,manifest['projection_registry'])
            except ValueError: db.close(); raise
    return db


def require_single_scope(db, field):
    has_binding=db.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='source_binding'").fetchone()[0]
    if has_binding:
        scopes=db.execute('SELECT DISTINCT r.namespace,b.snapshot_id FROM token_context t JOIN source_record r ON r.id=t.source_record_id JOIN source_binding b ON b.source_record_id=r.id WHERE t.field=?',[field]).fetchall()
    else:
        # Legacy persisted inputs are single-snapshot; namespace must still be unique.
        scopes=db.execute('SELECT DISTINCT r.namespace FROM token_context t JOIN source_record r ON r.id=t.source_record_id WHERE t.field=?',[field]).fetchall()
    if len(scopes)>1:
        raise ValueError('multiple query scopes; use scoped projection lookup or a single-scope connection')


def motif(path: Path | duckdb.DuckDBPyConnection, pattern: list[str], field: str='atf', strict: bool=False, max_skip: int=0) -> dict:
    if not 2<=len(pattern)<=5 or not 0<=max_skip<=2: raise ValueError('motif length 2–5; max skip 0–2')
    # max_skip applies only before the last item: A B [0..n represented positions] C.
    db=connect(path)
    try:
        require_single_scope(db,field)
        matches={}
        for skip in range(max_skip+1):
            positions=list(pattern[:-1])+['?']*skip+[pattern[-1]]
            sql='SELECT '+','.join(f't{i}.id' for i in range(len(positions)))+',t0.witness_id,t0.artifact_id,t0.sequence_id,t0.line_id FROM token_context t0 '
            args=[]
            for i in range(1,len(positions)):
                sql+=f'JOIN next_position e{i} ON e{i}.source_id=t{i-1}.id JOIN token_context t{i} ON t{i}.id=e{i}.target_id '
            where=['t0.field=?']; args.append(field)
            for i,token in enumerate(positions):
                if token!='?':
                    where.append(f't{i}.reading=?'); args.append(token)
                # Wildcard deliberately includes gaps; strict excludes all unknown physical preservation.
                if strict: where.append(f"t{i}.preservation='intact' AND t{i}.certainty='certain' AND t{i}.reading IS NOT NULL")
            for row in db.execute(sql+'WHERE '+' AND '.join(where),args).fetchall():
                ids=list(row[:-4]); key=identity('match',ids[0],ids[-1])
                matches[key]={'id':key,'occurrences':ids,'witness':row[-4],'artifact':row[-3],'sequence':row[-2],'line':row[-1],'skipped_represented_positions':skip}
        denominator=db.execute('SELECT count(*),count(DISTINCT witness_id),count(DISTINCT artifact_id),count(DISTINCT sequence_id) FROM token_context WHERE field=?',[field]).fetchone()
        return {'pattern':pattern,'field':field,'evidence':'source editorial readings' if field=='atf' else 'source-derived sign IDs, not image evidence','policy':'strict physical evidence' if strict else 'source readings including editorial uncertainty','cross_line':False,'gap_extent':'represented positions, NOT ancient sign count; unknown-length gap counts as one position','occurrences':len(matches),'witnesses':len({m['witness'] for m in matches.values()}),'artifacts':len({m['artifact'] for m in matches.values()}),'compositions':None,'denominators':dict(zip(['represented_positions','witnesses','artifacts','sequences'],denominator)),'certain_physical_evidence_count':sum(all(db.execute("SELECT preservation='intact' AND certainty='certain' FROM occurrence WHERE id=?",[oid]).fetchone()[0] for oid in m['occurrences']) for m in matches.values()),'bounds':'unresolved; compatible alternative assignments not evaluated','matches_truncated':len(matches)>100,'matches':list(matches.values())[:100]}
    finally: db.close()


def array_count(path: Path | duckdb.DuckDBPyConnection, pattern: list[str], field: str='atf') -> int:
    db=connect(path)
    try:
        require_single_scope(db,field)
        rows=db.execute('SELECT line_id,reading FROM token_context WHERE field=? ORDER BY line_id,position',[field]).fetchall()
        arrays={}
        for line,value in rows: arrays.setdefault(line,[]).append(value)
        return sum(all(want=='?' or want==got for want,got in zip(pattern,values[i:i+len(pattern)])) for values in arrays.values() for i in range(len(values)-len(pattern)+1))
    finally: db.close()


def trace_rows(db, raw: bytes, manifest: dict, occurrence_id: str, *, verified_manifest: bool=False, record_slice: tuple[int,int] | None=None) -> dict:
    cursor=db.execute('SELECT * FROM token_context WHERE id=?',[occurrence_id]); row=cursor.fetchone()
    if row is None: raise ValueError('unknown occurrence ID')
    token=dict(zip([d[0] for d in cursor.description],row))
    source=db.execute('SELECT source_key,locator,raw_json FROM source_record WHERE id=?',[token['source_record_id']]).fetchone()
    raw_hash=digest(raw)
    if manifest.get('raw_sha256')!=raw_hash: raise ValueError('trace raw hash mismatch')
    has_binding=db.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='source_binding'").fetchone()[0]
    if has_binding:
        binding=db.execute('SELECT snapshot_id,raw_sha256 FROM source_binding WHERE source_record_id=?',[token['source_record_id']]).fetchone()
        if binding is None or binding[1]!=raw_hash: raise ValueError('trace source binding mismatch')
        if manifest.get('snapshot_id',binding[0])!=binding[0]: raise ValueError('trace snapshot mismatch')
    if record_slice is None:
        record=dict(records(manifest['source'],raw))[source[1]]
    else:
        # Cohort payloads: decode only the bound member slice (bounded memory for large cohorts).
        record=json.loads(raw[record_slice[0]:record_slice[1]])
    if canonical(record)!=canonical(json.loads(source[2])): raise ValueError('trace source record mismatch')
    field_bytes=record[token['field']].encode('utf-8')
    selected=field_bytes[token['start_byte']:token['end_byte']].decode('utf-8')
    if selected!=token['raw']: raise ValueError('source token round-trip failed')
    translations=db.execute('SELECT text,language,granularity,locator FROM translation_segment WHERE sequence_id=?',[token['sequence_id']]).fetchall()
    edges=db.execute('SELECT kind,target_id,qualification FROM edge WHERE source_id=?',[occurrence_id]).fetchall()
    return {'token':token,'source_key':source[0],'raw_sha256':manifest['raw_sha256'],'raw_file':'raw','record_locator':source[1],'decoded_field':token['field'],'utf8_span':[token['start_byte'],token['end_byte']],'resolved_raw':selected,'edges':edges,'translations_in_sequence_unaligned':translations,'words':[],'senses':[],'images':[],'rights':manifest['rights'],'rights_attribution':'verified snapshot manifest; not an authenticated license grant' if verified_manifest else 'caller-supplied; not authenticated'}


def trace(path: Path, occurrence_id: str, parent_root: Path | None=None) -> dict:
    """Verified snapshot trace. Cohort snapshots additionally verify the token inside the parent raw object."""
    import time
    started=time.monotonic()
    from .storage import verified
    checked=verified(path); manifest=checked['manifest']
    verify_ms=round((time.monotonic()-started)*1000,1)
    db=open_verified(path,manifest)
    try:
        raw=(path/'raw').read_bytes()
        member=None
        if manifest['source']=='ebl-cohort':
            locator=db.execute('SELECT r.locator FROM token_context t JOIN source_record r ON r.id=t.source_record_id WHERE t.id=?',[occurrence_id]).fetchone()
            if locator is None: raise ValueError('unknown occurrence ID')
            cohort=json.loads((path/'cohort.json').read_text())
            member=next((m for m in cohort['records'] if m['payload_pointer']==locator[0]),None)
            if member is None: raise ValueError('occurrence record not bound in cohort manifest')
        result=trace_rows(db,raw,manifest,occurrence_id,verified_manifest=True,record_slice=(member['payload_start'],member['payload_end']) if member else None)
        t=time.monotonic()
        if member: result['parent_trace']=parent_trace(manifest,member,raw,result,parent_root)
        parent_ms=round((time.monotonic()-t)*1000,1)
        result['publication']=checked['publication']
        result['timing']={'verify_ms':verify_ms,'parent_trace_ms':parent_ms,'end_to_end_ms':round((time.monotonic()-started)*1000,1),
                          'note':'end_to_end_ms covers snapshot verification (every payload hash), the trace, and parent re-hash/re-read when requested'}
        return result
    finally: db.close()


def parent_trace(manifest: dict, member: dict, raw: bytes, result: dict, parent_root: Path | None) -> dict:
    """Re-read the parent raw object at the recorded byte range and re-resolve the token there."""
    from .acquire import raw_path, hash_file
    parent=manifest['cohort']['parent']
    out={'parent_sha256':parent['sha256'],'parent_receipt_id':parent.get('receipt_id'),'parent_url':parent.get('url'),'parent_pointer':member['parent_pointer'],'parent_byte_range':[member['parent_start'],member['parent_end']],'record_sha256':member['record_sha256']}
    slice_=raw[member['payload_start']:member['payload_end']]
    if digest(slice_)!=member['record_sha256']: raise ValueError('cohort member slice mismatch')
    if parent_root is None: return dict(out,status='parent-raw-not-requested')
    location=raw_path(parent_root,parent['sha256'])
    if not location.is_file(): return dict(out,status='parent-raw-unavailable')
    if hash_file(location)['sha256']!=parent['sha256']: raise ValueError('parent raw integrity failure')
    with location.open('rb') as handle:
        handle.seek(member['parent_start']); parent_bytes=handle.read(member['parent_end']-member['parent_start'])
    if parent_bytes!=slice_: raise ValueError('parent byte range does not match cohort member')
    field=json.loads(parent_bytes)[result['decoded_field']].encode('utf-8')
    start,end=result['utf8_span']
    if field[start:end].decode('utf-8')!=result['resolved_raw']: raise ValueError('parent token round-trip failed')
    a,b=encoded_field_span(parent_bytes,result['decoded_field'],start,end)
    fragment=parent_bytes[a:b]
    if json.loads(b'"'+fragment+b'"')!=result['resolved_raw']: raise ValueError('parent file byte span does not decode to the token')
    return dict(out,status='verified',resolved_raw_in_parent=result['resolved_raw'],
                parent_file_byte_span=[member['parent_start']+a,member['parent_start']+b],
                parent_file_fragment=fragment.decode('utf-8'),
                span_semantics='half-open byte offsets in the original parent file; they cover the JSON-escaped encoding of the token inside the field string literal (decoding the fragment as JSON string content yields resolved_raw)')


_ESCAPES={'"':'"','\\':'\\','/':'/','b':'\b','f':'\f','n':'\n','r':'\r','t':'\t'}


def encoded_field_span(raw: bytes, field: str, start: int, end: int) -> tuple[int,int]:
    """Map a UTF-8 span of a decoded top-level string field to byte offsets inside the encoded JSON record."""
    text=raw.decode('utf-8'); dec=json.JSONDecoder(); ws=' \t\r\n'; i=0
    def skip(k):
        while text[k] in ws: k+=1
        return k
    i=skip(i)
    if text[i]!='{': raise ValueError('record is not a JSON object')
    i+=1; found=None
    while True:
        i=skip(i)
        if text[i]=='}': break
        key,i=dec.raw_decode(text,i); i=skip(i)
        if text[i]!=':': raise ValueError('malformed record')
        i=skip(i+1); vstart=i; _,i=dec.raw_decode(text,i)
        if key==field:
            if found is not None: raise ValueError('duplicate field in record; span ambiguous')
            found=vstart
        i=skip(i)
        if text[i]==',': i+=1
    if found is None or text[found]!='"': raise ValueError('field is not a string literal')
    j=found+1; decoded=0; a=None
    while True:
        if decoded==start and a is None: a=j
        if decoded==end and a is not None: b=j; break
        if decoded>end or text[j]=='"': raise ValueError('span does not fall on encoded character boundaries')
        if text[j]=='\\':
            e=text[j+1]
            if e=='u':
                cp=int(text[j+2:j+6],16); n=6
                if 0xD800<=cp<0xDC00 and text[j+6:j+8]=='\\u':
                    cp=0x10000+((cp-0xD800)<<10)+(int(text[j+8:j+12],16)-0xDC00); n=12
                ch=chr(cp)
            else: ch=_ESCAPES[e]; n=2
        else: ch=text[j]; n=1
        decoded+=len(ch.encode('utf-8')); j+=n
    return len(text[:a].encode('utf-8')),len(text[:b].encode('utf-8'))
