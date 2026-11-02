"""Read-only, in-memory adapter/graph exercise, usable while disk ingestion is gated."""
from pathlib import Path
import duckdb
from .adapters import Builder, RIGHTS, ingest
from .model import digest, identity
from .query import motif, array_count, trace_rows
from .storage import Config, inspect, validate_graph


def run(source: str, path: Path, config: Config, pattern: list[str], field: str='atf') -> dict:
    info=inspect(source,path,config)
    raw=path.read_bytes()
    db=duckdb.connect(':memory:')
    try:
        db.execute("SET memory_limit='128MB'")
        db.execute("SET threads=1")
        db.execute("SET max_temp_directory_size='0B'")
        db.execute(Path(__file__).with_name('schema.sql').read_text())
        ingest(Builder(db,identity('demo',source,digest(raw)),source),source,raw)
        validate_graph(db)
        result=motif(db,pattern,field)
        array=array_count(db,pattern,field)
        if array!=result['occurrences']: raise ValueError('array/graph parity failed')
        counts={t:db.execute(f'SELECT count(*) FROM {t}').fetchone()[0] for t in ['source_record','artifact','witness','sequence_version','line','occurrence','sign_type','word_token','lemma','sense','translation_segment','claim','rejection','exclusion','edge']}
        occurrence=db.execute('SELECT id FROM occurrence ORDER BY id LIMIT 1').fetchone()
        trace=trace_rows(db,raw,{'source':source,'raw_sha256':digest(raw),'rights':RIGHTS[source]},occurrence[0]) if occurrence else None
        return {'mode':'in-memory; no snapshot or Parquet written','source_inspection':info,'counts':counts,'query':result,'array_count':array,'example_trace':trace}
    finally: db.close()
