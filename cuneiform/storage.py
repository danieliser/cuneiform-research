"""Immutable local snapshots; bounded acquisition; relocatable hash references."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import shutil
import urllib.request
import uuid
import duckdb
from .adapters import Builder, RIGHTS, ingest, records
from .projections import ProjectionConfig, REVISION, build as build_projections
from .model import SCHEMA_VERSION, PARSER_VERSION, canonical, digest, identity

MiB=1024**2
GiB=1024**3

@dataclass(frozen=True)
class Config:
    root: Path
    max_input_bytes: int = 2*MiB
    max_total_bytes: int = 500*MiB
    reserve_bytes: int = 3*GiB

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
    sid=identity('snapshot',*parts)
    if sid!=manifest['snapshot_id'] or (expected_sid is not None and sid!=expected_sid): raise ValueError('snapshot identity mismatch')
    import re
    tables=set(re.findall(r'CREATE TABLE (\w+)',Path(__file__).with_name('schema.sql').read_text()))
    if legacy:
        tables -= {'source_binding','projection_registry'}
    else:
        assert projection_config is not None
        tables |= set(projection_assets(projection_config))
    required_files={'raw','graph.duckdb'} | {f'parquet/{t}.parquet' for t in tables}
    if set(manifest['files'])!=required_files or set(manifest['counts'])!=tables: raise ValueError('incomplete payload inventory')
    if manifest['files']['raw']!=manifest['raw_sha256']: raise ValueError('raw hash mismatch')
    if (snapshot/'raw').stat().st_size!=manifest['source_bytes']: raise ValueError('snapshot integrity failure: raw size mismatch')
    for name,expected in manifest['files'].items():
        if Path(name).is_absolute() or '..' in Path(name).parts: raise ValueError('unsafe manifest path')
        if digest((snapshot/name).read_bytes())!=expected: raise ValueError('snapshot integrity failure: '+name)
    return manifest


def import_source(source: str, path: Path, config: Config, namespace: str | None=None, record_id: str | None=None, source_url: str | None=None, dry_run: bool=False, projections: ProjectionConfig=ProjectionConfig()) -> dict:
    projections.validate()
    projection_spec={'revision':REVISION,'config':asdict(projections)}
    data=read_bounded(path,config)
    info=inspect_bytes(source,data)
    namespace=namespace or source
    # Record the explicit source citation in identity: a different attribution must not silently reuse a manifest.
    sid=identity('snapshot',namespace,source,digest(data),SCHEMA_VERSION,PARSER_VERSION,record_id,source_url,projection_spec)
    dest=config.root/'snapshots'/sid
    if dest.exists(): return {'snapshot':sid,'reused':True,'manifest':verify(dest,sid)}
    if dry_run:
        try:
            config.guard(info['estimated_additional_bytes']); admission='allowed'
        except ValueError as exc: admission=str(exc)
        return dict(info,snapshot=sid,dry_run=True,admission=admission)
    config.guard(info['estimated_additional_bytes'])
    if source=='oracc': raise ValueError('ORACC import disabled pending verified per-project contract; use inspect')
    dest.parent.mkdir(parents=True,exist_ok=True)
    stage=dest.parent/('.pending-'+uuid.uuid4().hex)
    stage.mkdir()
    try:
        (stage/'raw').write_bytes(data)
        db=duckdb.connect(str(stage/'graph.duckdb'))
        try:
            db.execute("SET memory_limit='128MB'")
            db.execute("SET threads=1")
            db.execute("SET max_temp_directory_size='0B'")
            db.execute(Path(__file__).with_name('schema.sql').read_text())
            ingest(Builder(db,sid,namespace),source,data,record_id)
            validate_graph(db)
            build_projections(db,projections)
            counts={}
            for (table,) in db.execute("SELECT table_name FROM information_schema.tables WHERE table_type='BASE TABLE'").fetchall():
                row=db.execute(f'SELECT count(*) FROM {table}').fetchone()
                assert row is not None
                counts[table]=row[0]
            (stage/'parquet').mkdir()
            for table in counts:
                target=str(stage/'parquet'/f'{table}.parquet').replace("'","''")
                db.execute(f"COPY {table} TO '{target}' (FORMAT PARQUET)")
        finally: db.close()
        files={str(p.relative_to(stage)):digest(p.read_bytes()) for p in stage.rglob('*') if p.is_file()}
        manifest={'projection_spec':projection_spec,'snapshot_id':sid,'schema_version':SCHEMA_VERSION,'parser_version':PARSER_VERSION,'namespace':namespace,'source':source,'source_url':source_url,'record_id':record_id,'retrieved_or_imported_at':datetime.now(timezone.utc).isoformat(),'raw_sha256':digest(data),'source_bytes':len(data),'rights':RIGHTS[source],'files':files,'counts':counts,'source_locator_contract':'JSON pointer or CSV logical row; token offsets UTF-8 bytes in decoded source field','coverage':'conservative subset; unsupported positions retained; no linguistic validation','storage_paths':'relative to snapshot directory'}
        manifest['manifest_sha256']=digest(canonical(manifest).encode())
        (stage/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
        config.guard(0)
        # A same-ID concurrent writer must not replace an existing directory.
        stage.rename(dest)
        return {'snapshot':sid,'reused':False,'manifest':manifest}
    except BaseException:
        shutil.rmtree(stage)
        raise


def validate_graph(db) -> None:
    from .model import EDGE_TYPES
    nodes=dict(db.execute('SELECT id,kind FROM nodes').fetchall())
    for kind,src,dst in db.execute('SELECT kind,source_id,target_id FROM edge').fetchall():
        if src not in nodes or dst not in nodes: raise ValueError('dangling graph edges')
        if kind not in EDGE_TYPES or (nodes[src],nodes[dst])!=EDGE_TYPES[kind]:
            raise ValueError('invalid endpoint types: '+kind)
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


def projection_assets(config):
    return (['posting'] if config.postings else []) + (['ngram'] if config.ngrams else [])
