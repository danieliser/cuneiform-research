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
    verify(path)
    return duckdb.connect(str(path/'graph.duckdb'),read_only=True)


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


def trace_rows(db, raw: bytes, manifest: dict, occurrence_id: str, *, verified_manifest: bool=False) -> dict:
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
    source_rows=dict(records(manifest['source'],raw))
    record=source_rows[source[1]]
    if canonical(record)!=canonical(json.loads(source[2])): raise ValueError('trace source record mismatch')
    field_bytes=record[token['field']].encode('utf-8')
    selected=field_bytes[token['start_byte']:token['end_byte']].decode('utf-8')
    if selected!=token['raw']: raise ValueError('source token round-trip failed')
    translations=db.execute('SELECT text,language,granularity,locator FROM translation_segment WHERE sequence_id=?',[token['sequence_id']]).fetchall()
    edges=db.execute('SELECT kind,target_id,qualification FROM edge WHERE source_id=?',[occurrence_id]).fetchall()
    return {'token':token,'source_key':source[0],'raw_sha256':manifest['raw_sha256'],'raw_file':'raw','record_locator':source[1],'decoded_field':token['field'],'utf8_span':[token['start_byte'],token['end_byte']],'resolved_raw':selected,'edges':edges,'translations_in_sequence_unaligned':translations,'words':[],'senses':[],'images':[],'rights':manifest['rights'],'rights_attribution':'verified snapshot manifest; not an authenticated license grant' if verified_manifest else 'caller-supplied; not authenticated'}


def trace(path: Path, occurrence_id: str) -> dict:
    manifest=verify(path); db=connect(path)
    try: return trace_rows(db,(path/'raw').read_bytes(),manifest,occurrence_id,verified_manifest=True)
    finally: db.close()
