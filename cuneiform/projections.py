"""Disposable, bounded organizations over canonical source rows; no inferred alignments."""
from dataclasses import asdict, dataclass
import json
from .model import canonical, digest, identity

REVISION = 'linked-1'
OPTIONAL_TABLES = {'posting', 'ngram'}
# Defaults stay small (20,000 / 100,000); corpus snapshots opt into larger ceilings explicitly. The hard caps admit the
# full eligible eBL release (Q-023: ~5.6M positions, ~20M derived rows measured by stage) with headroom.
HARD_MAX_POSITIONS = 12_000_000
HARD_MAX_ROWS = 80_000_000

@dataclass(frozen=True)
class ProjectionConfig:
    fields: tuple[str, ...] = ('atf', 'signs')
    policies: tuple[str, ...] = ('source', 'strict')
    lengths: tuple[int, ...] = (2, 3, 4, 5)
    postings: bool = True
    ngrams: bool = True
    max_positions: int = 20000
    max_rows: int = 100000

    def validate(self):
        if type(self.postings) is not bool or type(self.ngrams) is not bool:
            raise ValueError('projection switches must be booleans')
        if not self.fields or not set(self.fields) <= {'atf','signs'} or len(set(self.fields)) != len(self.fields):
            raise ValueError('unique fields atf/signs required')
        if not self.policies or not set(self.policies) <= {'source','strict'} or len(set(self.policies)) != len(self.policies):
            raise ValueError('unique policies source/strict required')
        if not set(self.lengths) <= {2,3,4,5} or len(set(self.lengths)) != len(self.lengths):
            raise ValueError('unique ngram lengths 2–5 required')
        if type(self.max_positions) is not int or type(self.max_rows) is not int or not 1 <= self.max_positions <= HARD_MAX_POSITIONS or not 1 <= self.max_rows <= HARD_MAX_ROWS:
            raise ValueError('projection budget exceeds hard cap')


def rows(db, sql, args=()):
    cursor = db.execute(sql,args)
    names = [d[0] for d in cursor.description]
    return [dict(zip(names,row)) for row in cursor.fetchall()]


def canonical_hash(db):
    """Fingerprint all canonical tables, including claims/edges/uncertainty edits. Streams in batches."""
    tables = [r[0] for r in db.execute("SELECT table_name FROM information_schema.tables WHERE table_type='BASE TABLE' ORDER BY table_name").fetchall() if r[0] not in OPTIONAL_TABLES | {'projection_registry'}]
    import hashlib
    h = hashlib.sha256()
    for table in tables:
        h.update(table.encode())
        # Canonical schema columns are scalar; sorted JSON gives stable independent order.
        cursor = db.execute(f'SELECT * FROM {table} ORDER BY 1')
        while batch := cursor.fetchmany(10000):
            for value in batch: h.update(canonical(value).encode())
    return h.hexdigest()


# Read-only connections whose graph.duckdb bytes were just verified against a manifest that recorded the
# freeze-time registry hashes. Membership replaces the O(corpus) recomputation, never the check itself.
import weakref
FROZEN_VERIFIED: 'weakref.WeakSet' = weakref.WeakSet()


def mark_frozen_verified(db, recorded: dict) -> None:
    entry = rows(db,'SELECT id,revision,canonical_hash,source_hash FROM projection_registry')
    if len(entry)!=1 or entry[0]['revision']!=REVISION or {k: entry[0][k] for k in ('id','canonical_hash','source_hash')}!=recorded:
        raise ValueError('projection registry does not match the hashes recorded in the verified manifest')
    if db.execute("SELECT current_setting('access_mode')").fetchone()[0]!='read_only':
        raise ValueError('frozen fast path requires a read-only connection')
    FROZEN_VERIFIED.add(db)


def assert_fresh(db):
    entry = rows(db,'SELECT * FROM projection_registry')
    if len(entry)!=1 or entry[0]['revision']!=REVISION:
        raise ValueError('missing or stale projections; rebuild in a new workspace')
    if db in FROZEN_VERIFIED:
        return dict(entry[0], freshness='frozen-verified: graph.duckdb sha256 matched manifest; registry hashes recorded at freeze')
    if entry[0]['canonical_hash']!=canonical_hash(db):
        raise ValueError('missing or stale projections; rebuild in a new workspace')
    return dict(entry[0], freshness='recomputed canonical hash')


POSITION_COLUMNS = 'o.id,o.field,o.line_id,o.sequence_id,o.position,o.reading,o.preservation,o.certainty,o.namespace,o.snapshot_id,o.witness_id,o.artifact_id,o.source_record_id'


def _lines(db, fields):
    """Stream configured positions one line at a time in (sequence, line ordinal, position) order."""
    names = [c.split('.')[1] for c in POSITION_COLUMNS.split(',')] + ['sign']
    cursor = db.execute(f"SELECT {POSITION_COLUMNS},m.target_id FROM ordered_position o LEFT JOIN edge m ON m.source_id=o.id AND m.kind='MAPS_TO_SIGN' WHERE o.field IN (SELECT unnest(?::VARCHAR[])) ORDER BY o.sequence_id,o.ordinal,o.position", [list(fields)])
    current, line = None, []
    while batch := cursor.fetchmany(20000):
        for values in batch:
            p = dict(zip(names, values))
            if p['line_id'] != current and line:
                yield line; line = []
            current = p['line_id']; line.append(p)
    if line: yield line


def build(db, config=ProjectionConfig(), spool_dir=None, check=None):
    """Replace optional projections atomically. spool_dir (import staging only) enables bulk loading.
    check (import staging only) is called every 5,000 lines, e.g. to refuse when the free-space reserve is reached."""
    config.validate()
    from pathlib import Path
    from .bulk import Spool
    for _,_,filename in db.execute('PRAGMA database_list').fetchall():
        if filename and not Path(filename).parent.name.startswith('.pending-'):
            raise ValueError('cannot rebuild a frozen database; use memory or new import staging')
    fingerprint = canonical_hash(db)
    source_hash = digest(canonical(db.execute('SELECT * FROM source_binding ORDER BY 1').fetchall()).encode())
    projection_id = identity('projection',REVISION,asdict(config),source_hash,fingerprint)
    # Count before any mutation. Expansion is linear in configured lengths/policies.
    total_positions = db.execute('SELECT count(*) FROM ordered_position').fetchone()[0]
    if total_positions>config.max_positions: raise ValueError('projection position budget exceeded')
    assets = sorted((['posting'] if config.postings else []) + (['ngram'] if config.ngrams else []))
    # Derived tables are created inside the final transaction; spools only stage rows.
    posting_cols = [('id','VARCHAR'),('namespace','VARCHAR'),('snapshot_id','VARCHAR'),('field','VARCHAR'),('policy','VARCHAR'),('token_id','VARCHAR'),('label','VARCHAR'),('occurrence_id','VARCHAR')]
    ngram_cols = [('id','VARCHAR'),('match_id','VARCHAR'),('namespace','VARCHAR'),('snapshot_id','VARCHAR'),('field','VARCHAR'),('policy','VARCHAR'),('length','INTEGER'),('token_ids','JSON'),('readings','JSON'),('occurrence_ids','JSON'),('sequence_id','VARCHAR'),('line_id','VARCHAR'),('start_position','INTEGER'),('end_position','INTEGER'),('witness_id','VARCHAR'),('artifact_id','VARCHAR'),('source_record_id','VARCHAR')]
    posts = Spool.detached('posting', posting_cols, spool_dir)
    grams = Spool.detached('ngram', ngram_cols, spool_dir)
    try:
        for number, line in enumerate(_lines(db, config.fields)):
            if check is not None and number % 5000 == 0: check()
            for policy in config.policies:
                def eligible(p):
                    return p['reading'] is not None and (policy=='source' or (p['preservation']=='intact' and p['certainty']=='certain'))
                def key(p):
                    return p['sign'] if p['field']=='signs' else identity('reading',p['namespace'],p['snapshot_id'],p['field'],p['reading'])
                for i,p in enumerate(line):
                    scope = (p['namespace'],p['snapshot_id'],p['field'],policy)
                    if config.postings and eligible(p) and key(p):
                        posts.append((identity('posting',projection_id,p['id'],policy),*scope,key(p),p['reading'],p['id']))
                    if config.ngrams:
                        for n in config.lengths:
                            window = line[i:i+n]
                            if len(window)!=n: continue
                            # Keep blockers in windows; do not enumerate their possible readings.
                            if policy=='strict' and not all(eligible(w) for w in window): continue
                            ids = [w['id'] for w in window]
                            keys = [key(w) if eligible(w) else None for w in window]
                            values = [w['reading'] if eligible(w) else None for w in window]
                            grams.append((identity('ngram',projection_id,policy,ids),identity('match',ids[0],ids[-1]),*scope,n,canonical(keys),canonical(values),canonical(ids),p['sequence_id'],p['line_id'],p['position'],window[-1]['position'],p['witness_id'],p['artifact_id'],p['source_record_id']))
                    if posts.count+grams.count>config.max_rows: raise ValueError('projection row budget exceeded; nothing replaced')
        db.execute('BEGIN TRANSACTION')
        try:
            for table in OPTIONAL_TABLES: db.execute(f'DROP TABLE IF EXISTS {table}')
            if config.postings:
                db.execute('CREATE TABLE posting(id VARCHAR PRIMARY KEY, namespace VARCHAR, snapshot_id VARCHAR, field VARCHAR, policy VARCHAR, token_id VARCHAR, label VARCHAR, occurrence_id VARCHAR)')
                posts.attach(db).load()
                db.execute('CREATE INDEX posting_identity ON posting(namespace,snapshot_id,field,policy,token_id)')
                db.execute('CREATE INDEX posting_occurrence ON posting(occurrence_id)')
            if config.ngrams:
                db.execute('CREATE TABLE ngram(id VARCHAR PRIMARY KEY, match_id VARCHAR, namespace VARCHAR, snapshot_id VARCHAR, field VARCHAR, policy VARCHAR, length INTEGER, token_ids JSON, readings JSON, occurrence_ids JSON, sequence_id VARCHAR, line_id VARCHAR, start_position INTEGER, end_position INTEGER, witness_id VARCHAR, artifact_id VARCHAR, source_record_id VARCHAR)')
                grams.attach(db).load()
                db.execute('CREATE INDEX ngram_scope ON ngram(namespace,snapshot_id,field,policy,length)')
            db.execute('DELETE FROM projection_registry')
            db.execute('INSERT INTO projection_registry VALUES (?,?,?,?,?,?)',[projection_id,REVISION,canonical(asdict(config)),source_hash,fingerprint,canonical(assets)])
            db.execute('COMMIT')
        except BaseException:
            db.execute('ROLLBACK')
            raise
    finally:
        posts.discard(); grams.discard()
    return {'id':projection_id,'revision':REVISION,'assets':assets,'postings':posts.count if config.postings else 0,'ngrams':grams.count if config.ngrams else 0,'canonical_hash':fingerprint,'source_hash':source_hash,'config':asdict(config)}


# Interactive lookups never filter ordered_position by a non-partition column: its row_number() window would then be
# computed for every position in the snapshot before the filter (O(corpus) memory; Q-023 measured OOM at 256 MB on 5,000
# records). They resolve the window's partition key (sequence_id) first and pass it as a literal, which DuckDB pushes below
# the window, or read token_context when no window column is needed. Results are identical.
SCOPES_SQL = ('SELECT DISTINCT r.namespace,b.snapshot_id,t.field FROM token_context t JOIN source_record r ON r.id=t.source_record_id '
              'JOIN source_binding b ON b.source_record_id=r.id ORDER BY 1,2,3')


def bounded(db, sql, args=(), limit=20, offset=0):
    if not 1 <= limit <= 100 or not 0 <= offset <= 100000: raise ValueError('limit 1–100; offset 0–100000')
    found = rows(db,sql+' LIMIT ? OFFSET ?',[*args,limit+1,offset])
    return {'rows':found[:limit],'truncated':len(found)>limit,'next_offset':offset+limit if len(found)>limit else None}


def lookup(db, organization, value='', *, namespace=None, snapshot=None, field='atf', policy='source', limit=20, offset=0):
    """Bounded named recipes; SQL stays internal. Reverse lookup accepts exact IDs."""
    if field not in {'atf','signs'} or policy not in {'source','strict'}: raise ValueError('invalid sequence scope')
    if organization in {'postings','motifs'}:
        entry=assert_fresh(db)
        asset='posting' if organization=='postings' else 'ngram'
        if asset not in json.loads(entry['assets']): raise ValueError('projection not configured')
        if namespace is None or snapshot is None: raise ValueError('explicit namespace and snapshot required')
        configured=json.loads(entry['config'])
        if field not in configured['fields'] or policy not in configured['policies']:
            raise ValueError('projection scope not configured')
        if organization=='postings':
            # Page the posting rows first, then fetch their positions by ID: joining the token_context view to the whole
            # posting table builds corpus-sized hash tables (OOM at 256 MB on the full release). Same rows and order.
            page=bounded(db,'SELECT * FROM posting p WHERE p.namespace=? AND p.snapshot_id=? AND p.field=? AND p.policy=? AND (p.token_id=? OR p.label=?) ORDER BY p.id',[namespace,snapshot,field,policy,value,value],limit,offset)
            ids=[r['occurrence_id'] for r in page['rows']]
            cols=('sequence_id','line_id','position','witness_id','artifact_id','source_record_id','start_byte','end_byte')
            found={r['id']:r for r in rows(db,f"SELECT id,{','.join(cols)} FROM token_context WHERE id IN ({','.join('?'*len(ids))})",ids)} if ids else {}
            page['rows']=[dict(r,**{c:found[r['occurrence_id']][c] for c in cols}) for r in page['rows'] if r['occurrence_id'] in found]
            return page
        pattern=json.loads(value)
        if not isinstance(pattern,list) or not 2<=len(pattern)<=5 or not all(isinstance(v,str) for v in pattern): raise ValueError('pattern must be 2–5 strings')
        cfg=json.loads(entry['config'])
        if field not in cfg['fields'] or policy not in cfg['policies'] or len(pattern) not in cfg['lengths']:
            raise ValueError('projection scope not configured')
        where='namespace=? AND snapshot_id=? AND field=? AND policy=? AND length=?'
        args=[namespace,snapshot,field,policy,len(pattern)]
        for i,token in enumerate(pattern):
            if token!='?':
                where+=f' AND json_extract_string(readings,\'$[{i}]\')=?';args.append(token)
        count=db.execute('SELECT count(*) FROM ngram WHERE '+where,args).fetchone()[0]
        result=bounded(db,'SELECT * FROM ngram WHERE '+where+' ORDER BY sequence_id,start_position',args,limit,offset)
        return dict(result,count=count,gap_extent='represented positions, not ancient sign count')
    if organization=='span':
        span=json.loads(value)
        return source_span(db,span['source_record_id'],field,span['start'],span['end'],limit)
    recipes={
      'sequence': ('SELECT * FROM ordered_position WHERE sequence_id=? ORDER BY ordinal,position',[value]),
      'reverse-postings': ('SELECT * FROM posting WHERE occurrence_id=? ORDER BY id',[value]),
      'reverse-motifs': ('SELECT * FROM ngram WHERE json_contains(occurrence_ids,?) ORDER BY id',[canonical(value)]),
      'aliases': ('SELECT * FROM catalog_alias WHERE object_key=? OR subject_id=? ORDER BY id',[value,value]),
      'catalog': ("SELECT a.*,r.namespace,b.snapshot_id FROM artifact a JOIN source_record r ON r.id=a.source_record_id JOIN source_binding b ON b.source_record_id=r.id WHERE r.namespace || ':' || a.catalog_key=? ORDER BY a.id",[value]),
      'translations': ('SELECT * FROM translation_context WHERE contains(lower(text),lower(?)) OR id=? OR sequence_id=? OR source_record_id=? ORDER BY id',[value]*4),
      'neighbors': ('SELECT * FROM portable_edge WHERE source_id=? OR target_id=? ORDER BY id',[value,value]),
      'nodes': ('SELECT * FROM nodes WHERE id=? OR kind=? ORDER BY id',[value,value]),
      # Word -> lemma -> contextual sense, exactly as the source asserts; senses are English lexical glosses, not translations.
      'words': ("""SELECT w.id word_id,w.form,w.source_locator,s.source_record_id,s.witness_id,a.artifact_id,l.id lemma_id,l.citation_form,l.language,l.pos,
                    se.id sense_id,se.guideword,se.gloss sense_gloss,'lexical gloss; not a translation' gloss_status
             FROM word_token w JOIN sequence_version s ON s.id=w.sequence_id JOIN witness a ON a.id=s.witness_id
             LEFT JOIN edge el ON el.kind='LEMMATIZED_AS' AND el.source_id=w.id LEFT JOIN lemma l ON l.id=el.target_id
             LEFT JOIN edge es ON es.kind='IN_SENSE' AND es.source_id=w.id LEFT JOIN sense se ON se.id=es.target_id
             WHERE w.id=? OR w.form=? OR l.citation_form=? OR l.id=? OR se.gloss=? OR s.source_record_id=?
             ORDER BY s.source_record_id,CAST(json_extract(w.source_locator,'$.order') AS INTEGER)""",[value]*6),
      'lemmas': ("""SELECT l.*,(SELECT count(*) FROM edge e WHERE e.kind='LEMMATIZED_AS' AND e.target_id=l.id) attestations,
                     (SELECT count(DISTINCT e.source_record_id) FROM edge e WHERE e.kind='LEMMATIZED_AS' AND e.target_id=l.id) attesting_records,
                     (SELECT list(s.gloss ORDER BY s.gloss) FROM sense s WHERE s.lemma_id=l.id) senses
              FROM lemma l WHERE l.id=? OR l.citation_form=? OR ?='' ORDER BY attestations DESC,l.id""",[value]*3),
    }
    if organization=='occurrence':
        recipes['occurrence']=('SELECT * FROM ordered_position WHERE sequence_id=? AND id=? ORDER BY id',[_sequence_of(db,value),value])
    if organization not in recipes: raise ValueError('unknown organization')
    if organization.startswith('reverse-'):
        entry=assert_fresh(db)
        if ('posting' if organization=='reverse-postings' else 'ngram') not in json.loads(entry['assets']): raise ValueError('projection not configured')
    sql,args=recipes[organization]
    return bounded(db,sql,args,limit,offset)


def source_span(db, source_id, field, start, end, limit=20):
    if field not in {'atf','signs'} or start<0 or end<=start: raise ValueError('invalid half-open UTF-8 span')
    seqs=[r[0] for r in db.execute('SELECT id FROM sequence_version WHERE source_record_id=? AND field=? ORDER BY id',[source_id,field]).fetchall()]
    if not seqs: return {'rows':[],'truncated':False,'next_offset':None}
    return bounded(db,f"SELECT * FROM ordered_position WHERE sequence_id IN ({','.join('?'*len(seqs))}) AND source_record_id=? AND field=? AND start_byte<? AND end_byte>? ORDER BY ordinal,position",[*seqs,source_id,field,end,start],limit)


def _sequence_of(db, occurrence_id):
    found=db.execute('SELECT sequence_id FROM token_context WHERE id=?',[occurrence_id]).fetchone()
    return found[0] if found else None


def coverage(db):
    return rows(db,"""SELECT r.id source_record_id,r.namespace,b.snapshot_id,
      (SELECT count(*) FROM sequence_version s WHERE s.source_record_id=r.id) AS "sequences",
      (SELECT count(*) FROM word_token w JOIN sequence_version s ON w.sequence_id=s.id WHERE s.source_record_id=r.id) words,
      (SELECT count(*) FROM lemma l WHERE l.source_record_id=r.id) lemmas,
      (SELECT count(*) FROM edge e WHERE e.kind='LEMMATIZED_AS' AND e.source_record_id=r.id) lemmatized_words,
      (SELECT count(*) FROM edge e WHERE e.kind='IN_SENSE' AND e.source_record_id=r.id) words_with_sense,
      (SELECT count(*) FROM translation_segment t WHERE t.source_record_id=r.id) translations,
      (SELECT count(*) FROM translation_segment t WHERE t.source_record_id=r.id AND t.granularity='unresolved-span') unresolved_translations
      FROM source_record r JOIN source_binding b ON b.source_record_id=r.id ORDER BY r.id""")


def report(db):
    entry=assert_fresh(db)
    covered=coverage(db)
    return {'coverage_total':len(covered),'coverage_truncated':len(covered)>20,'registry':entry,'scopes':rows(db,SCOPES_SQL),
            'coverage':covered[:20],'coverage_note':'Zero word/lemma counts mean unavailable, not zero linguistic words. Unresolved translations are sequence context, not aligned English evidence.',
            'nodes':db.execute('SELECT count(*) FROM nodes').fetchone()[0],
            'edges':db.execute('SELECT count(*) FROM portable_edge').fetchone()[0]}


def explore(source, path, storage_config, organization='report', value='', *, also_cdli=None, **options):
    """Bounded local input only; no persistent writes, network, or spill."""
    from pathlib import Path
    import duckdb
    from .adapters import Builder, ingest
    from .storage import read_bounded, validate_graph
    db=duckdb.connect(':memory:')
    try:
        db.execute("SET memory_limit='128MB'")
        db.execute('SET threads=1')
        db.execute("SET max_temp_directory_size='0B'")
        db.execute(Path(__file__).with_name('schema.sql').read_text())
        inputs=[(source,path)]+([('cdli',also_cdli)] if also_cdli else [])
        for kind,local in inputs:
            raw=read_bounded(local,storage_config)
            ingest(Builder(db,identity('demo',kind,digest(raw)),kind),kind,raw)
        validate_graph(db)
        build(db)
        if organization=='report': return report(db)
        return lookup(db,organization,value,**options)
    finally: db.close()
