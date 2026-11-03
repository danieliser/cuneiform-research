"""Immutable local snapshots; bounded acquisition; relocatable hash references."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
import shutil
import time
import urllib.request
import uuid
import duckdb
from .adapters import Builder, RIGHTS, ingest, records
from .projections import ProjectionConfig, REVISION, assert_fresh, build as build_projections
from .model import SCHEMA_VERSION, PARSER_VERSION, canonical, digest, identity

MiB=1024**2
SELECTION_SOURCES={'oracc-selection','cdli-selection'}
# Bumped whenever manifest/payload contract changes, so a revised build can never reuse an existing snapshot ID.
SNAPSHOT_CONTRACT='manifest-3'
LEDGER='.publication-ledger.jsonl'


def snapshot_identity(*parts, contract: str | None=SNAPSHOT_CONTRACT) -> str:
    return identity('snapshot',*parts,*([{'snapshot_contract':contract}] if contract else []))
GiB=1024**3

@dataclass(frozen=True)
class Config:
    root: Path
    max_input_bytes: int = 2*MiB
    # Task-owned root budget and filesystem reserve (2026-11-03 authorization: <=5 GiB owned, >=10 GiB free).
    max_total_bytes: int = 5*GiB
    reserve_bytes: int = 10*GiB

    def used(self) -> int:
        return sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file()) if self.root.exists() else 0

    def guard(self, additional: int) -> None:
        ancestor=self.root
        while not ancestor.exists(): ancestor=ancestor.parent
        if self.used()+additional>self.max_total_bytes: raise ValueError('storage byte budget exceeded')
        if shutil.disk_usage(ancestor).free-additional<self.reserve_bytes: raise ValueError('free-space reserve would be violated')


def read_bounded(path: Path, config: Config) -> bytes:
    with path.open('rb') as handle:
        data = handle.read(config.max_input_bytes + 1)
    if len(data) > config.max_input_bytes:
        raise ValueError('input exceeds bounded local import cap')
    return data


def file_sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as handle:
        while block:=handle.read(1<<20): h.update(block)
    return h.hexdigest()


def inspect_bytes(source: str, data: bytes) -> dict:
    size=len(data)
    rows=records(source,data)
    return {'bytes':size,'sha256':digest(data),'records':len(rows),'first_keys':list(rows[0][1]) if rows and isinstance(rows[0][1],dict) else [],'source':source,'import_status':'experimental-inspection-only' if source=='oracc' else 'supported-conservative-subset','estimated_additional_bytes':size*100+8*MiB,'rights':RIGHTS[source]}


def inspect(source: str, path: Path, config: Config) -> dict:
    return inspect_bytes(source, read_bounded(path, config))


def verify(snapshot: Path, expected_sid: str | None=None) -> dict:
    manifest=json.loads((snapshot/'manifest.json').read_text())
    if manifest.get('schema_version') not in {'1',SCHEMA_VERSION}:
        raise ValueError('unsupported schema version; explicit migration required')
    required={'snapshot_id','parser_version','namespace','source','source_url','record_id','raw_sha256','source_bytes','rights','counts','files','manifest_sha256'}
    if not required <= manifest.keys(): raise ValueError('incomplete manifest')
    unsigned={k:v for k,v in manifest.items() if k!='manifest_sha256'}
    if digest(canonical(unsigned).encode())!=manifest['manifest_sha256']: raise ValueError('manifest integrity failure')
    legacy=manifest['schema_version']=='1'
    if manifest['parser_version']!=('conservative-2' if legacy else PARSER_VERSION): raise ValueError('unsupported parser version')
    parts=[manifest['namespace'],manifest['source'],manifest['raw_sha256'],manifest['schema_version'],manifest['parser_version'],manifest['record_id'],manifest['source_url']]
    projection_config=None
    if not legacy:
        spec=manifest.get('projection_spec')
        if not isinstance(spec,dict) or spec.get('revision')!=REVISION: raise ValueError('unsupported projection revision')
        projection_config=ProjectionConfig(**spec['config']); projection_config.validate()
        parts.append(spec)
    sid=snapshot_identity(*parts,contract=manifest.get('snapshot_contract'))
    if sid!=manifest['snapshot_id'] or (expected_sid is not None and sid!=expected_sid): raise ValueError('snapshot identity mismatch')
    tables=set(re.findall(r'CREATE TABLE (\w+)',Path(__file__).with_name('schema.sql').read_text()))
    if legacy:
        tables -= {'source_binding','projection_registry'}
    else:
        assert projection_config is not None
        tables |= set(projection_assets(projection_config))
    required_files={'raw','graph.duckdb'} | {f'parquet/{t}.parquet' for t in tables}
    if manifest['source']=='ebl-cohort':
        cohort=manifest.get('cohort')
        if not isinstance(cohort,dict) or cohort.get('cohort_id')!=manifest['record_id']: raise ValueError('cohort snapshot lacks bound cohort identity')
        required_files.add('cohort.json')
    if manifest['source'] in SELECTION_SOURCES:
        selection=manifest.get('selection')
        if not isinstance(selection,dict) or selection.get('selection_id')!=manifest['record_id']: raise ValueError('selection snapshot lacks bound selection identity')
        required_files.add('selection.json')
    if set(manifest['files'])!=required_files or set(manifest['counts'])!=tables: raise ValueError('incomplete payload inventory')
    if manifest['files']['raw']!=manifest['raw_sha256']: raise ValueError('raw hash mismatch')
    if (snapshot/'raw').stat().st_size!=manifest['source_bytes']: raise ValueError('snapshot integrity failure: raw size mismatch')
    for name,expected in manifest['files'].items():
        if Path(name).is_absolute() or '..' in Path(name).parts: raise ValueError('unsafe manifest path')
        if file_sha256(snapshot/name)!=expected: raise ValueError('snapshot integrity failure: '+name)
    if manifest['source']=='ebl-cohort':
        bound=json.loads((snapshot/'cohort.json').read_text())
        body={k:v for k,v in bound.items() if k!='manifest_sha256'}
        if digest(canonical(body).encode())!=bound.get('manifest_sha256') or bound['manifest_sha256']!=manifest['cohort']['manifest_sha256'] or bound['payload']['sha256']!=manifest['raw_sha256'] or bound['cohort_id']!=manifest['record_id']:
            raise ValueError('cohort binding mismatch')
    if manifest['source'] in SELECTION_SOURCES:
        bound=json.loads((snapshot/'selection.json').read_text())
        body={k:v for k,v in bound.items() if k!='manifest_sha256'}
        if digest(canonical(body).encode())!=bound.get('manifest_sha256') or bound['manifest_sha256']!=manifest['selection']['manifest_sha256'] or bound['payload_sha256']!=manifest['raw_sha256'] or bound['selection_id']!=manifest['record_id']:
            raise ValueError('selection binding mismatch')
    return manifest


def import_source(source: str, path: Path, config: Config, namespace: str | None=None, record_id: str | None=None, source_url: str | None=None, dry_run: bool=False, projections: ProjectionConfig=ProjectionConfig()) -> dict:
    projections.validate()
    projection_spec={'revision':REVISION,'config':asdict(projections)}
    data=read_bounded(path,config)
    info=inspect_bytes(source,data)
    namespace=namespace or source
    # Record the explicit source citation in identity: a different attribution must not silently reuse a manifest.
    sid=snapshot_identity(namespace,source,digest(data),SCHEMA_VERSION,PARSER_VERSION,record_id,source_url,projection_spec)
    dest=config.root/'snapshots'/sid
    if dest.exists(): return {'snapshot':sid,'reused':True,'manifest':verify(dest,sid)}
    assert_unpublished(config,sid)
    if dry_run:
        try:
            config.guard(info['estimated_additional_bytes']); admission='allowed'
        except ValueError as exc: admission=str(exc)
        return dict(info,snapshot=sid,dry_run=True,admission=admission)
    config.guard(info['estimated_additional_bytes'])
    if source=='oracc': raise ValueError('ORACC import disabled pending verified per-project contract; use inspect')
    def load(db, stage):
        ingest(Builder(db,sid,namespace,spool_dir=stage/'spool'),source,data,record_id)
    meta={'namespace':namespace,'source':source,'source_url':source_url,'record_id':record_id,'rights':RIGHTS[source]}
    return materialize(config,sid,data,load,projections,projection_spec,meta)


def materialize(config: Config, sid: str, data: bytes, load, projections: ProjectionConfig, projection_spec: dict, meta: dict, extra_files: dict | None=None, memory: str='128MB') -> dict:
    """Stage, ingest, validate, project, export, hash and atomically publish one immutable snapshot."""
    dest=config.root/'snapshots'/sid
    dest.parent.mkdir(parents=True,exist_ok=True)
    stage=dest.parent/('.pending-'+uuid.uuid4().hex)
    stage.mkdir()
    timings={}
    try:
        (stage/'raw').write_bytes(data)
        for name,content in (extra_files or {}).items(): (stage/name).write_bytes(content)
        db=duckdb.connect(str(stage/'graph.duckdb'))
        try:
            db.execute(f"SET memory_limit='{memory}'")
            db.execute("SET threads=1")
            db.execute("SET max_temp_directory_size='0B'")
            db.execute(Path(__file__).with_name('schema.sql').read_text())
            t=time.monotonic(); load(db,stage); timings['ingest_s']=round(time.monotonic()-t,3)
            t=time.monotonic(); validate_graph(db); timings['validate_s']=round(time.monotonic()-t,3)
            t=time.monotonic(); build_projections(db,projections,spool_dir=stage/'spool'); timings['projections_s']=round(time.monotonic()-t,3)
            fresh=assert_fresh(db)
            meta=dict(meta,projection_registry={k:fresh[k] for k in ('id','canonical_hash','source_hash')})
            counts={}
            for (table,) in db.execute("SELECT table_name FROM information_schema.tables WHERE table_type='BASE TABLE'").fetchall():
                row=db.execute(f'SELECT count(*) FROM {table}').fetchone()
                assert row is not None
                counts[table]=row[0]
            t=time.monotonic()
            (stage/'parquet').mkdir()
            for table in counts:
                target=str(stage/'parquet'/f'{table}.parquet').replace("'","''")
                db.execute(f"COPY {table} TO '{target}' (FORMAT PARQUET)")
            timings['parquet_s']=round(time.monotonic()-t,3)
        finally: db.close()
        spool=stage/'spool'
        if spool.exists():
            if any(spool.iterdir()): raise ValueError('unloaded spool files remain')
            spool.rmdir()
        files={str(p.relative_to(stage)):file_sha256(p) for p in stage.rglob('*') if p.is_file()}
        manifest={'snapshot_contract':SNAPSHOT_CONTRACT,'projection_spec':projection_spec,'snapshot_id':sid,'schema_version':SCHEMA_VERSION,'parser_version':PARSER_VERSION,**meta,'retrieved_or_imported_at':datetime.now(timezone.utc).isoformat(),'raw_sha256':digest(data),'source_bytes':len(data),'files':files,'counts':counts,'source_locator_contract':'JSON pointer or CSV logical row; token offsets UTF-8 bytes in decoded source field','coverage':'conservative subset; unsupported positions retained; no linguistic validation','storage_paths':'relative to snapshot directory','build_timings':timings,'snapshot_payload_bytes':sum((stage/f).stat().st_size for f in files)}
        manifest['manifest_sha256']=digest(canonical(manifest).encode())
        (stage/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
        config.guard(0)
        publish(config,stage,dest,manifest)
        return {'snapshot':sid,'reused':False,'manifest':manifest}
    except BaseException:
        if stage.exists(): shutil.rmtree(stage)
        raise


# Corpus snapshots raise only the explicit ceilings; defaults for small imports are unchanged.
CORPUS_PROJECTIONS = ProjectionConfig(max_positions=2_000_000, max_rows=20_000_000)


def import_cohort(cohort_dir: Path, config: Config, projections: ProjectionConfig=CORPUS_PROJECTIONS, namespace: str='ebl', parent_path: Path | None=None, batch: int=200, memory: str='1GB', max_payload_bytes: int=512*MiB) -> dict:
    """Chunked import of a verified cohort: records stream one at a time; rows spool per batch.

    Snapshot raw = cohort payload (exact parent slices). cohort.json is copied in and bound by hash, so the
    snapshot stays relocatable and traceable to parent byte ranges without using the 2 MiB small-input path.
    """
    from .corpus import verify_cohort, iter_array
    from .adapters import ingest_record
    projections.validate()
    cohort=verify_cohort(cohort_dir,parent_path)
    payload_path=cohort_dir/'payload.json'
    if payload_path.stat().st_size>max_payload_bytes: raise ValueError('cohort payload exceeds corpus import cap')
    data=payload_path.read_bytes()
    projection_spec={'revision':REVISION,'config':asdict(projections)}
    source='ebl-cohort'; record_id=cohort['cohort_id']; source_url=cohort['parent'].get('url')
    sid=snapshot_identity(namespace,source,digest(data),SCHEMA_VERSION,PARSER_VERSION,record_id,source_url,projection_spec)
    dest=config.root/'snapshots'/sid
    if dest.exists(): return {'snapshot':sid,'reused':True,'manifest':verify(dest,sid)}
    assert_unpublished(config,sid)
    # Admission estimate before writing: 200x payload + 64 MiB (observed builds are well below; see CHECKPOINT).
    config.guard(len(data)*200+64*MiB)
    bound=(cohort_dir/'manifest.json').read_bytes()
    stats={'records':0,'rejected':0,'batches':0,'batch_size':batch}
    def load(db, stage):
        builder=Builder(db,sid,namespace,spool_dir=stage/'spool')
        builder.raw_sha256=digest(data)
        pending=0
        for item in iter_array(payload_path):
            stats['records']+=1
            if not ingest_record(builder,source,item['pointer'],item['value']): stats['rejected']+=1
            pending+=1
            if pending>=batch:
                builder.flush(); stats['batches']+=1; pending=0
        if pending: builder.flush(); stats['batches']+=1
    meta={'namespace':namespace,'source':source,'source_url':source_url,'record_id':record_id,'rights':cohort.get('rights') or RIGHTS['ebl'],
          'cohort':{'cohort_id':cohort['cohort_id'],'manifest_sha256':cohort['manifest_sha256'],'size':cohort['size'],'rule':cohort['rule'],'parent':cohort['parent']},
          'ingestion':stats}
    return materialize(config,sid,data,load,projections,projection_spec,meta,{'cohort.json':bound},memory)


TABLE_OF = {'Artifact':'artifact','Witness':'witness','Composition':'composition','Passage':'passage','SequenceVersion':'sequence_version','Line':'line','SignOccurrence':'occurrence','WordToken':'word_token','Lemma':'lemma','Sense':'sense','TranslationSegment':'translation_segment','SourceRecord':'source_record','SignType':'sign_type','Claim':'claim'}


def validate_graph(db) -> None:
    """Endpoint existence and typed endpoints per edge kind via single-table semi-joins (bounded memory)."""
    from .model import EDGE_TYPES
    for (kind,) in db.execute('SELECT DISTINCT kind FROM edge ORDER BY 1').fetchall():
        if kind not in EDGE_TYPES: raise ValueError('invalid endpoint types: '+kind)
        src,dst=(TABLE_OF[t] for t in EDGE_TYPES[kind])
        bad=db.execute(f'SELECT count(*) FROM edge e WHERE e.kind=? AND (NOT EXISTS (SELECT 1 FROM {src} s WHERE s.id=e.source_id) OR NOT EXISTS (SELECT 1 FROM {dst} d WHERE d.id=e.target_id))',[kind]).fetchone()[0]
        if bad:
            # Error path only: distinguish a missing endpoint from an endpoint of the wrong type.
            missing=db.execute('SELECT count(*) FROM edge e WHERE e.kind=? AND (e.source_id NOT IN (SELECT id FROM nodes) OR e.target_id NOT IN (SELECT id FROM nodes))',[kind]).fetchone()[0]
            raise ValueError('dangling graph edges' if missing else 'invalid endpoint types: '+kind)
    bad=db.execute("SELECT count(*) FROM next_position e JOIN occurrence a ON a.id=e.source_id JOIN occurrence b ON b.id=e.target_id WHERE a.line_id<>b.line_id OR b.position<>a.position+1").fetchone()[0]
    if bad: raise ValueError('NEXT must connect adjacent represented positions in one line')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('redirect denied; explicitly allow and request final URL')


def fetch(url: str, allowlist: Path, config: Config, limit: int=256*1024) -> dict:
    allowed=json.loads(allowlist.read_text())
    if url not in allowed or not url.startswith('https://'): raise ValueError('URL not in explicit HTTPS allowlist')
    if limit<1 or limit>config.max_input_bytes: raise ValueError('invalid download byte limit')
    config.guard(limit)
    request=urllib.request.Request(url,headers={'User-Agent':'cuneiform-research/0.1 bounded-inspection','Accept-Encoding':'identity'})
    chunks=[]; total=0
    with urllib.request.build_opener(NoRedirect()).open(request,timeout=20) as response:
        length=response.headers.get('Content-Length')
        if length and int(length)>limit: raise ValueError('response Content-Length exceeds limit')
        while True:
            block=response.read(min(16384,limit-total+1))
            if not block: break
            total+=len(block)
            if total>limit: raise ValueError('stream exceeded byte limit; nothing retained')
            chunks.append(block)
    data=b''.join(chunks); sha=digest(data)
    config.guard(len(data))
    target=config.root/'downloads'/sha
    target.parent.mkdir(parents=True,exist_ok=True)
    try:
        with target.open('xb') as out: out.write(data)
    except FileExistsError:
        if digest(target.read_bytes())!=sha: raise ValueError('existing download corrupted')
    return {'path':str(target),'bytes':len(data),'sha256':sha,'source_url':url,'rights':'not inferred from public access'}


def resolve_snapshot(config: Config, sid: str) -> Path:
    if not sid.startswith('snapshot:') or any(c not in '0123456789abcdef' for c in sid[9:]) or len(sid)!=41:
        raise ValueError('invalid snapshot ID')
    result=config.root/'snapshots'/sid
    verify(result,sid)
    return result


def _ledger(config: Config) -> list[dict]:
    path=config.root/'snapshots'/LEDGER
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def assert_unpublished(config: Config, sid: str) -> None:
    if any(e['snapshot_id']==sid for e in _ledger(config)):
        raise ValueError(f'{sid} was already published (ledger) but is missing from the store; restore it, never rebuild under the same ID')


def publish(config: Config, stage: Path, dest: Path, manifest: dict) -> None:
    """Atomic, exclusive, append-only publication: one rename of a complete staged directory, then read-only.

    The ledger records every published ID; an ID that was ever published can never be published again, even if
    its directory is deleted. Revisions must change the identity (parser, projection config, contract, payload).
    """
    import fcntl, os
    folder=dest.parent
    with (folder/'.publication.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        try:
            assert_unpublished(config,manifest['snapshot_id'])
            if dest.exists(): raise ValueError('snapshot directory already exists; refusing replacement')
            for p in sorted(stage.rglob('*'),reverse=True): os.chmod(p,0o444 if p.is_file() else 0o555)
            stage.rename(dest)   # same filesystem: atomic; readers see nothing or the complete snapshot
            os.chmod(dest,0o555)
            entry={'snapshot_id':manifest['snapshot_id'],'manifest_sha256':manifest['manifest_sha256'],'snapshot_contract':manifest.get('snapshot_contract'),'published_at':datetime.now(timezone.utc).isoformat()}
            with (folder/LEDGER).open('a') as out:
                out.write(json.dumps(entry)+'\n'); out.flush(); os.fsync(out.fileno())
        finally:
            fcntl.flock(lock,fcntl.LOCK_UN)


def projection_assets(config):
    return (['posting'] if config.postings else []) + (['ngram'] if config.ngrams else [])
