"""Immutable local snapshots; bounded acquisition; relocatable hash references."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import time
import urllib.request
import uuid
import duckdb
from .adapters import Builder, RIGHTS, ingest, records
from .projections import ProjectionConfig, REVISION, assert_fresh, build as build_projections
from .model import SCHEMA_VERSION, PARSER_VERSION, READABLE_PARSER_VERSIONS, canonical, digest, identity

MiB=1024**2
SELECTION_SOURCES={'oracc-selection','cdli-selection'}
# Bumped whenever manifest/payload contract changes, so a revised build can never reuse an existing snapshot ID.
SNAPSHOT_CONTRACT='manifest-3'
from . import publication as _publication
from .publication import LOCK, Ledger, PublicationError, assert_no_symlinks, build_lock, check_published, discard_stage, locate_entry, missing_entry, publish_dir, seal
LEDGER=_publication.LEDGER   # append-only publication ledger file name (protocol in cuneiform/publication.py)


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

    def guard_free(self) -> None:
        """Cheap mid-build check (no directory walk): refuse once free space falls below the reserve."""
        ancestor=self.root
        while not ancestor.exists(): ancestor=ancestor.parent
        if shutil.disk_usage(ancestor).free<self.reserve_bytes: raise ValueError('free-space reserve reached during build; nothing published')


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


def in_store(snapshot: Path) -> bool:
    """A directory whose lexical or resolved parent holds a publication ledger (or lock) is in a store and is
    ledger-checked on every read. Raises PublicationError('symlinked-entry') for a symlinked store entry."""
    return locate_entry(snapshot) is not None


class StoreEntry(type(Path())):
    """A snapshot path named by its store and ID (from store_path/resolve_snapshot). Reads of it always run with
    ledger='require' and expected_sid=<its ID>, so a store read can never be served as a standalone copy or as another
    ID. Paths derived from it (/, parent, resolve) are plain paths."""
    store_sid: str

    def with_segments(self, *segments):
        return Path(*segments)


def store_entry(config: 'Config', sid: str) -> StoreEntry:
    entry=StoreEntry(config.root/'snapshots'/valid_sid(sid)); entry.store_sid=sid
    return entry


def _store_read(snapshot, expected_sid, ledger):
    """Apply a StoreEntry's explicit expectations: its own ID and a required ledger."""
    if isinstance(snapshot,StoreEntry):
        if expected_sid is not None and expected_sid!=snapshot.store_sid: raise ValueError('snapshot identity mismatch')
        return snapshot.store_sid,('require' if ledger=='auto' else ledger)
    return expected_sid,ledger


STANDALONE={'status':'standalone-not-ledger-checked','ledger_checked':False,
            'note':'content verified only (every payload hash, identity and bindings); this directory is not inside a store (no publication ledger or lock beside its path or its resolved path), so it is not checked against what was published'}


def verified(snapshot: Path, expected_sid: str | None=None, *, ledger: str='auto') -> dict:
    """Content verification plus publication check. ledger: 'auto' (checked when the directory is in a store),
    'require' (must be ledgered and match), or 'skip' (content only; caller labels the result as not ledger-checked)."""
    if ledger not in ('auto','require','skip'): raise ValueError('ledger mode must be auto, require or skip')
    expected_sid,ledger=_store_read(snapshot,expected_sid,ledger)
    if ledger!='skip': locate_entry(snapshot)   # refuse a symlinked/escaping store entry before hashing it
    manifest=verify_content(snapshot,expected_sid)
    return {'manifest':manifest,'publication':publication_of(snapshot,manifest,ledger)}


def verify_content(snapshot: Path, expected_sid: str | None=None) -> dict:
    """Relocatable content verification only: manifest digest, identity, inventory, every file hash, bindings."""
    return verify(snapshot,expected_sid,ledger='skip')


def publication_of(snapshot: Path, manifest: dict, ledger: str='auto') -> dict:
    """Ledger check for an already content-verified manifest (no re-hashing of payload files)."""
    if isinstance(snapshot,StoreEntry) and manifest['snapshot_id']!=snapshot.store_sid:
        raise PublicationError(f'store entry {snapshot.store_sid} holds the manifest of {manifest["snapshot_id"]}; refusing','misplaced')
    _,ledger=_store_read(snapshot,None,ledger)
    if ledger=='skip': return dict(STANDALONE)
    entry=locate_entry(snapshot)
    if entry is None:
        if ledger=='require':
            raise PublicationError(f'{snapshot} is not inside a snapshot store (no publication ledger beside it); a store read requires the ledger','not-in-ledger')
        return dict(STANDALONE)
    folder,name=entry
    if name!=manifest['snapshot_id']:
        raise PublicationError(f'store directory {name} holds the manifest of {manifest["snapshot_id"]}; refusing','misplaced')
    if not os.path.exists(folder/LEDGER):
        raise PublicationError(f'{manifest["snapshot_id"]}: store {folder} has no publication ledger; refusing to serve unledgered snapshots','not-in-ledger')
    assert_no_symlinks(folder/name,['manifest.json',*manifest['files']])
    return check_published(Ledger(folder),manifest['snapshot_id'],manifest,folder/name/'manifest.json')


def verify(snapshot: Path, expected_sid: str | None=None, *, ledger: str='auto') -> dict:
    """Return the verified manifest: manifest digest, identity, inventory, every file hash and bindings (relocatable).
    Inside a store (ledger beside the directory) the manifest must also be the ledger's published one; ledger='skip'
    is content-only and ledger='require' refuses anything not ledgered."""
    if ledger not in ('auto','require','skip'): raise ValueError('ledger mode must be auto, require or skip')
    expected_sid,ledger=_store_read(snapshot,expected_sid,ledger)
    if ledger!='skip': locate_entry(snapshot)   # refuse a symlinked/escaping store entry before hashing it
    if not os.path.lexists(Path(snapshot)/'manifest.json') and lexical_store_entry(snapshot): raise_missing(snapshot)
    manifest=json.loads((snapshot/'manifest.json').read_text())
    if manifest.get('schema_version') not in {'1',SCHEMA_VERSION}:
        raise ValueError('unsupported schema version; explicit migration required')
    required={'snapshot_id','parser_version','namespace','source','source_url','record_id','raw_sha256','source_bytes','rights','counts','files','manifest_sha256'}
    if not required <= manifest.keys(): raise ValueError('incomplete manifest')
    unsigned={k:v for k,v in manifest.items() if k!='manifest_sha256'}
    if digest(canonical(unsigned).encode())!=manifest['manifest_sha256']: raise ValueError('manifest integrity failure')
    legacy=manifest['schema_version']=='1'
    if manifest['parser_version'] not in (('conservative-2',) if legacy else READABLE_PARSER_VERSIONS): raise ValueError('unsupported parser version')
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
    publication_of(snapshot,manifest,ledger)
    return manifest


def lexical_store_entry(snapshot) -> bool:
    from .publication import is_store_folder
    return isinstance(snapshot,StoreEntry) or is_store_folder(os.path.dirname(os.path.abspath(snapshot)))


def raise_missing(snapshot) -> None:
    """A store read of an absent entry (or an entry without manifest.json) raises a typed PublicationError naming the
    ledger state (reserved, published-missing, abandoned, not-found). Outside a store it stays FileNotFoundError."""
    lex=Path(os.path.abspath(snapshot))
    if lexical_store_entry(snapshot):
        folder=Path(os.path.realpath(lex.parent))
        try: err=missing_entry(Ledger(folder),lex.name,lex)
        except (ValueError,OSError) as exc: err=PublicationError(f'{lex} is absent and its ledger could not be read ({exc})','not-found')
        raise err
    raise FileNotFoundError(f'{Path(snapshot)/"manifest.json"} does not exist')


def import_source(source: str, path: Path, config: Config, namespace: str | None=None, record_id: str | None=None, source_url: str | None=None, dry_run: bool=False, projections: ProjectionConfig=ProjectionConfig()) -> dict:
    projections.validate()
    projection_spec={'revision':REVISION,'config':asdict(projections)}
    data=read_bounded(path,config)
    info=inspect_bytes(source,data)
    namespace=namespace or source
    # Record the explicit source citation in identity: a different attribution must not silently reuse a manifest.
    sid=snapshot_identity(namespace,source,digest(data),SCHEMA_VERSION,PARSER_VERSION,record_id,source_url,projection_spec)
    if (existing:=existing_snapshot(config,sid)): return existing
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
    with build_lock(dest.parent,sid):
        # Another cooperating writer may have published this ID while we waited: reuse, never build twice.
        if (existing:=existing_snapshot(config,sid,locked=True)): return dict(existing,raced=True)
        return _materialize(config,sid,data,load,projections,projection_spec,meta,extra_files,memory,dest)


def _materialize(config, sid, data, load, projections, projection_spec, meta, extra_files, memory, dest) -> dict:
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
            t=time.monotonic(); build_projections(db,projections,spool_dir=stage/'spool',check=config.guard_free); timings['projections_s']=round(time.monotonic()-t,3)
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
        if publish(config,stage,dest,manifest)=='raced':
            discard_owned_stage(config,stage,sid,None)
            return {'snapshot':sid,'reused':True,'raced':True,'manifest':verify(dest,sid,ledger='require')}
        return {'snapshot':sid,'reused':False,'manifest':manifest}
    except BaseException as exc:
        discard_owned_stage(config,stage,sid,exc)
        raise


def discard_owned_stage(config: Config, stage: Path, sid: str, exc: BaseException | None) -> None:
    """Remove only the stage this call created. Never raises: a cleanup failure is attached to the original exception
    and written as a recovery receipt. A stage named by an open reservation is kept for explicit recovery."""
    if not stage.exists(): return
    try:
        st=Ledger(stage.parent).status(sid)
        if st.state=='reserved' and st.stage==stage.name:
            if exc is not None: exc.add_note(f'stage {stage} is named by the open reservation of {sid}; kept for `python -m cuneiform publication-recover {sid}`')
            return
    except (ValueError,OSError) as ledger_exc:
        if exc is not None: exc.add_note(f'could not read publication ledger during cleanup ({ledger_exc}); stage {stage} kept')
        return
    try:
        discard_stage(stage)
    except BaseException as cleanup_exc:
        receipt={'kind':'stage-cleanup-failure','stage':str(stage),'snapshot_id':sid,'at':datetime.now(timezone.utc).isoformat(),
                 'original_error':repr(exc) if exc is not None else None,'cleanup_error':repr(cleanup_exc),
                 'ledger_state':'no reservation names this stage; nothing was published from it',
                 'action':f'inspect, then: python -m cuneiform publication-clean-stage {stage.name}'}
        note=f'stage cleanup failed ({cleanup_exc!r}); {stage} remains. '
        try:
            target=stage.parent/'.recovery'/(stage.name+'.json'); target.parent.mkdir(exist_ok=True)
            target.write_text(json.dumps(receipt,indent=1)+'\n'); note+=f'Recovery receipt: {target}'
        except BaseException as receipt_exc:
            note+=f'Recovery receipt could not be written ({receipt_exc!r}): {json.dumps(receipt)}'
        if exc is not None: exc.add_note(note)
        else: raise


# Corpus snapshots raise only the explicit ceilings; defaults for small imports are unchanged.
CORPUS_PROJECTIONS = ProjectionConfig(max_positions=2_000_000, max_rows=20_000_000)
# Full eligible release (Q-023): same fields, policies and lengths; only the ceilings differ (they are part of the ID).
FULL_PROJECTIONS = ProjectionConfig(max_positions=12_000_000, max_rows=80_000_000)
PROJECTION_PRESETS = {'corpus': CORPUS_PROJECTIONS, 'full': FULL_PROJECTIONS}


def import_cohort(cohort_dir: Path, config: Config, projections: ProjectionConfig=CORPUS_PROJECTIONS, namespace: str='ebl', parent_path: Path | None=None, batch: int=200, memory: str='1GB', max_payload_bytes: int=512*MiB, cohort_ledger: str='auto') -> dict:
    """Chunked import of a verified cohort: records stream one at a time; rows spool per batch.

    Snapshot raw = cohort payload (exact parent slices). cohort.json is copied in and bound by hash, so the
    snapshot stays relocatable and traceable to parent byte ranges without using the 2 MiB small-input path.
    The cohort must pass its publication check (``cohort_ledger``, see corpus.verify_cohort): an uncommitted,
    abandoned or unrecorded cohort in a ledgered cohort store is refused before anything is built.
    """
    from .corpus import verify_cohort, iter_array
    from .adapters import ingest_record
    projections.validate()
    if not re.fullmatch(r'[1-9][0-9]{0,4}(MB|GB|MiB|GiB)',memory): raise ValueError('memory limit must look like 512MB or 8GB')
    cohort=verify_cohort(cohort_dir,parent_path,ledger=cohort_ledger)
    payload_path=cohort_dir/'payload.json'
    if payload_path.stat().st_size>max_payload_bytes: raise ValueError('cohort payload exceeds corpus import cap')
    data=payload_path.read_bytes()
    projection_spec={'revision':REVISION,'config':asdict(projections)}
    source='ebl-cohort'; record_id=cohort['cohort_id']; source_url=cohort['parent'].get('url')
    sid=snapshot_identity(namespace,source,digest(data),SCHEMA_VERSION,PARSER_VERSION,record_id,source_url,projection_spec)
    if (existing:=existing_snapshot(config,sid)): return existing
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
                config.guard_free()
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


def valid_sid(sid: str) -> str:
    if not sid.startswith('snapshot:') or any(c not in '0123456789abcdef' for c in sid[9:]) or len(sid)!=41:
        raise ValueError('invalid snapshot ID')
    return sid


def resolve_snapshot(config: Config, sid: str) -> Path:
    """Store read: content-verified AND the ledger's published manifest. Unledgered, symlinked, misplaced or mismatched
    entries are refused. Returns a StoreEntry, so later reads of it stay ledger-required and bound to this ID."""
    result=store_entry(config,sid)
    verify(result,sid,ledger='require')
    return result


def store_path(config: Config, sid: str) -> Path:
    """Store location for a read that verifies itself (persisted/query functions call verify()). The StoreEntry makes
    every such read ledger='require' with expected_sid=sid: a symlinked, unledgered or other-ID entry is refused and can
    never be served with the standalone label."""
    result=store_entry(config,sid)
    if not os.path.exists(result.parent/LEDGER): raise PublicationError(f'store {result.parent} has no publication ledger; refusing','not-in-ledger')
    return result


def store_ledger(config: Config) -> Ledger:
    return Ledger(config.root/'snapshots')


def existing_snapshot(config: Config, sid: str, *, locked: bool=False) -> dict | None:
    """Writer-side decision before building: a reusable published snapshot, None (free to build), or a refusal.

    An open reservation may be another live writer between reserve and commit (it holds the per-ID build lock for the
    whole build). Unless the caller already holds that lock, wait for it and decide again: a live writer's result is
    reused, and only a reservation with no live writer (an interruption) is refused."""
    from .publication import refusal
    dest=config.root/'snapshots'/sid
    st=store_ledger(config).status(sid)
    if st.state=='reserved' and not locked:
        with build_lock(dest.parent,sid): return existing_snapshot(config,sid,locked=True)
    if st.state in ('unpublished','aborted') and not os.path.lexists(dest): return None
    if st.state=='published' and os.path.lexists(dest): return {'snapshot':sid,'reused':True,'manifest':verify(dest,sid,ledger='require')}
    if st.state in ('unpublished','aborted'):
        raise PublicationError(f'{dest} exists but {sid} has no publication record (for example, an interrupted pre-ledger-2 publish). '
                               f'Refusing to reuse or replace it. If it is the intended bytes run `python -m cuneiform publication-adopt {sid} --reason ...`; otherwise move it aside.','unledgered')
    raise refusal(st,dest)


def assert_unpublished(config: Config, sid: str) -> None:
    """Compatibility wrapper: refuse unless the ID is free to build."""
    if existing_snapshot(config,sid) is not None:
        raise PublicationError(f'{sid} is already published','published')


def publish(config: Config, stage: Path, dest: Path, manifest: dict) -> str:
    """Seal the stage, then reserve -> rename -> commit through the ledger (see cuneiform.publication).

    An ID that was ever reserved for some bytes is never published with different bytes, even after deletion or
    a crash. Revisions must change the identity (parser, projection config, contract, payload)."""
    seal(stage)
    from .publication import file_digest
    def matches(path):
        try: return verify(path,manifest['snapshot_id'],ledger='require')['manifest_sha256']==manifest['manifest_sha256']
        except (ValueError,OSError,KeyError): return False
    return publish_dir(store_ledger(config),stage,dest,manifest['snapshot_id'],manifest['manifest_sha256'],file_digest(stage/'manifest.json'),matches)


def projection_assets(config):
    return (['posting'] if config.postings else []) + (['ngram'] if config.ngrams else [])
