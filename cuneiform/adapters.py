"""Small inspected contracts, deliberately conservative about unsupported layers."""
import csv
import io
import json
import re
from typing import Any
from .model import PARSER_VERSION, canonical, digest, identity

RIGHTS = {
 'ebl': {'status':'unresolved-conflict','claims':['Zenodo 10018951: CC BY 4.0','JOHD paper: CC BY-NC-SA 4.0'], 'reuse':'not cleared; text/annotations/photos have distinct grants'},
 'ebl-atf': {'status':'unknown','reuse':'local caller-supplied ATF; rights not inferred'},
 'cdli': {'status':'unknown','reuse':'historical GitHub catalog; no data grant established'},
 'oracc': {'status':'unverified-project','reuse':'review reports CC BY-SA 3.0; individual project not verified'},
}
RIGHTS['ebl-cohort'] = RIGHTS['ebl']

IGNORE_CONFLICTS = {'witness', 'sign_type'}

# conservative-4 ATF line gate (eBL-ATF grammar, docs/PARSER-REVISIONS.md). A text line is `line-number. text`; a line
# starting with '#' (translation, note, comment), '$' (state), '&' or '@' (structure) is never a text line, and a label
# outside eBL's line-number grammar is excluded rather than guessed. conservative-3 accepted any first run ending in '.'
# and so stored 129 `#tr…`/`#note`/`#Vgl` lines of the eBL release as text lines.
TEXT_LINE = re.compile(r"([^\s]+)\.\s+(.*)")
_SINGLE_LINE_NUMBER = r"(?:[A-Za-z]\+)?\d+['′’]?[A-Za-z]?"
LINE_NUMBER = re.compile(rf"{_SINGLE_LINE_NUMBER}(?:-{_SINGLE_LINE_NUMBER})?")
NON_TEXT_PREFIXES = ('#', '$', '&', '@')
# @-line classes (eBL-ATF `at-line`). Only a surface sets the surface; an object or seal starts a new carrier whose
# surface is not stated; discourse, heading and division markers are document structure inside the current surface
# and column. Any other @-line (e.g. `@end of column`) leaves the surface and column unknown. The raw @-line itself is
# kept in the record and accounted as a non-token exclusion; it is never copied into `line.surface`.
_STATUS = r"\s*[!?'*]*"
SURFACE_MARKER = re.compile(rf"(?:obverse|reverse|left|right|top|bottom|edge(?: [a-z])?|face \S+|surface .+){_STATUS}")
OBJECT_MARKER = re.compile(rf"(?:tablet|envelope|prism|bulla|fragment .+|object .+|seal \d+){_STATUS}")
STRUCTURE_MARKER = re.compile(rf"(?:catchline|colophon|date|signatures?|summary|witnesses|h\d+(?: .*)?|m=division .+){_STATUS}")


def at_line_state(body: str, surface: str | None, column: str | None) -> tuple[str | None, str | None]:
    """(surface, column) after the @-line `@<body>`."""
    if body.startswith('column '): return surface, body[7:]
    if SURFACE_MARKER.fullmatch(body): return body, None
    if STRUCTURE_MARKER.fullmatch(body): return surface, column
    return None, None   # object, seal or unrecognized marker: the surface is not stated


class Builder:
    """Collects one source record at a time; commit/discard keep rejected records free of partial rows.

    With spool_dir set (import-owned staging only), committed rows are spooled to JSONL and bulk loaded.
    """
    def __init__(self, db: Any, snapshot: str, namespace: str, spool_dir: Any=None):
        self.db, self.snapshot, self.namespace = db, snapshot, namespace
        self.seen: set[str] = set()
        self.raw_sha256 = ''
        self.spool_dir = spool_dir
        self.pending: dict[str, list[tuple]] = {}
        self.pending_keys: set[tuple[str, str]] = set()
        self.keys: set[tuple[str, str]] = set()
        self.spools: dict[str, Any] = {}

    def add(self, table: str, *values: object) -> None:
        self.pending.setdefault(table, []).append(values)

    def once(self, table: str, key: str) -> bool:
        """Deduplicate shared rows (witness, sign type, artifact link) inside committed+pending state."""
        marker = (table, key)
        if marker in self.keys or marker in self.pending_keys: return False
        self.pending_keys.add(marker); return True

    def commit(self) -> None:
        from .bulk import Spool
        for table, values in self.pending.items():
            if table not in self.spools:
                self.spools[table] = Spool(self.db, table, self.spool_dir, table in IGNORE_CONFLICTS)
            for row in values: self.spools[table].append(row)
        self.keys |= self.pending_keys
        self.discard()

    def discard(self) -> None:
        self.pending = {}; self.pending_keys = set()

    def flush(self) -> dict[str, int]:
        """Load committed rows in parent-before-child order. Returns rows loaded per table."""
        self.commit()
        order = ['source_record','source_binding','artifact','witness','composition','passage','sequence_version','line','occurrence','sign_type','word_token','lemma','sense','translation_segment','claim','edge','rejection','exclusion']
        loaded = {}
        try:
            for table in sorted(self.spools, key=lambda t: order.index(t) if t in order else len(order)):
                loaded[table] = self.spools[table].load()
        finally:
            for spool in self.spools.values(): spool.discard()
            self.spools = {}
        return loaded

    def edge(self, kind: str, a: str, b: str, record: str, **qualification: object) -> None:
        self.add('edge', identity('edge',kind,a,b),a,b,kind,record,canonical(qualification))

    def exclude(self, record: str, locator: str, reason: str) -> None:
        self.add('exclusion',identity('exclusion',record,locator,reason),record,locator,reason)

    def record(self, key: str, locator: str, raw: object) -> tuple[str,str]:
        if key in self.seen:
            raise ValueError('duplicate source identity in input; not merged')
        self.seen.add(key)
        rid = identity('source',self.namespace,self.snapshot,key,locator)
        aid = identity('artifact',self.namespace,key)
        self.add('source_record',rid,self.namespace,key,locator,canonical(raw))
        self.add('source_binding',rid,self.snapshot,self.raw_sha256)
        self.add('artifact',aid,rid,key,canonical(raw))
        return rid,aid

    def alias(self, record: str, artifact: str, target: str, locator: str) -> None:
        self.add('claim',identity('claim',record,locator,target),record,artifact,'catalog_alias',target,'source-attributed-unreviewed','Source crosswalk; no identity merge or independence assertion',canonical({'locator':locator,'independence':'unknown'}))

    def sequence(self, record: str, artifact: str, field: str, evidence: str) -> tuple[str,str]:
        # A local fragment reading contribution, NOT inferred composition membership.
        wid=identity('witness',record)
        if self.once('witness',wid):
            self.add('witness',wid,record,artifact,'source fragment contribution; composition unknown')
            self.edge('ON_ARTIFACT',wid,artifact,record)
        sid=identity('sequence',record,field,PARSER_VERSION)
        self.add('sequence_version',sid,record,wid,field,PARSER_VERSION,evidence)
        self.edge('HAS_SEQUENCE',wid,sid,record)
        return wid,sid

    def text(self, record: str, artifact: str, field: str, text: str, derived: bool=False) -> None:
        _,sid=self.sequence(record,artifact,field,'source-derived-sign-list' if derived else 'editorial-transliteration')
        offset=0; previous_line=None; ordinal=0; surface=None; column=None
        for source_line_no, rawline in enumerate(text.splitlines(keepends=True)):
            line=rawline.rstrip('\r\n')
            match=None if derived or line.startswith(NON_TEXT_PREFIXES) else TEXT_LINE.match(line)
            if line.startswith('@'): surface,column=at_line_state(line[1:],surface,column)
            if match and not LINE_NUMBER.fullmatch(match[1]):
                self.exclude(record,f'{field}:line:{source_line_no}','ATF line label outside eBL line-number grammar retained in raw')
                offset+=len(rawline.encode()); continue
            if line.startswith('#tr.'):
                tm=re.match(r'#tr\.([a-z-]+)(?:\.\([^)]*\))?:\s*(.*)',line)
                if tm:
                    # The README demonstrates translations spanning preceding multiple lines.
                    # Preserve placement; do not falsely assert single-line alignment.
                    self.add('translation_segment',identity('translation',sid,source_line_no),record,sid,tm[1],tm[2],None,'unresolved-span',f'{field}:utf8:{offset}:{offset+len(line.encode())}')
                else:
                    self.exclude(record,f'{field}:line:{source_line_no}','unsupported translation syntax retained in raw')
            if not derived and not match:
                if line and not line.startswith('#tr.'):
                    self.exclude(record,f'{field}:line:{source_line_no}','non-token ATF line retained in raw; no cross-line matching')
                offset+=len(rawline.encode()); continue
            body=line if derived else match[2]
            begin=0 if derived else match.start(2)
            lid=identity('line',sid,source_line_no)
            self.add('line',lid,sid,ordinal,str(ordinal+1) if derived else match[1],surface,column,offset,offset+len(line.encode()))
            self.edge('HAS_LINE',sid,lid,record)
            if previous_line: self.edge('NEXT_LINE',previous_line,lid,record,continuity='not-implied')
            previous_line=lid; ordinal+=1; previous=None; bracket_depth=0
            blocked_line=not derived and any(marker in body for marker in ('<<','>>','{(',')}'))
            for position,m in enumerate(re.finditer(r'\S+',body)):
                raw=m[0]; start=offset+len(line[:begin+m.start()].encode()); end=start+len(raw.encode())
                restored=bracket_depth>0 or '[' in raw
                bracket_depth=max(0,bracket_depth+raw.count('[')-raw.count(']'))
                stripped=raw.strip('[]?#')
                gap=stripped in {'x','X','...','…','(x)'}
                simple=bool(re.fullmatch(r'[^\W\d][\w₀-₉]*',stripped))
                kind='gap' if gap else (('derived_sign' if derived else 'reading') if simple else 'unsupported')
                if blocked_line: kind='unsupported'
                reading=None if kind in {'gap','unsupported'} else stripped
                preservation='unknown' if derived else ('lost' if restored else ('damaged' if '#' in raw else 'unknown'))
                certainty='unknown' if derived or kind!='reading' else ('uncertain' if '?' in raw else 'unmarked')
                oid=identity('occurrence',lid,position)
                self.add('occurrence',oid,lid,position,raw,reading,kind,preservation,certainty,'unknown',start,end)
                self.edge('HAS_OCCURRENCE',lid,oid,record)
                if previous: self.edge('NEXT',previous,oid,record,extent='represented-position',boundary='same-line')
                previous=oid
                if kind=='unsupported': self.exclude(record,f'{field}:utf8:{start}:{end}','unsupported compound/segmentation; retained as blocking position')
                if kind=='derived_sign':
                    st=identity('sign',self.namespace,self.snapshot,stripped)
                    if self.once('sign_type',st): self.add('sign_type',st,'ebl-export-signs',self.snapshot,stripped)
                    self.edge('MAPS_TO_SIGN',oid,st,record,rule='source supplied signs field; reading-derived, no image evidence',sign_list_revision='unknown',alignment_to_atf='unavailable')

            offset+=len(rawline.encode())


def records(source: str, data: bytes) -> list[tuple[str,Any]]:
    if source=='cdli':
        reader=csv.DictReader(io.StringIO(data.decode('utf-8')))
        if not reader.fieldnames or 'id_text' not in reader.fieldnames: raise ValueError('CDLI CSV needs observed id_text header')
        return [(f'csv:row:{i+2}',row) for i,row in enumerate(reader)]
    if source=='ebl-atf': return [('',{'_id':'sha256-local-atf','atf':data.decode('utf-8')})]
    doc=json.loads(data)
    if isinstance(doc,list): return [(f'/{i}',row) for i,row in enumerate(doc)]
    if isinstance(doc,dict) and 'fragments' in doc:
        if not isinstance(doc['fragments'],list): raise ValueError('fragments must be an array')
        return [(f'/fragments/{i}',row) for i,row in enumerate(doc['fragments'])]
    if isinstance(doc,dict): return [('',doc)]
    raise ValueError('expected JSON object or array')


TEXT_SOURCES = {'ebl', 'ebl-atf', 'ebl-cohort'}


def ingest_record(builder: Builder, source: str, locator: str, row: Any, record_id: str | None=None) -> bool:
    """Map one decoded source record atomically. Returns False when it was rejected (with raw accounting)."""
    try:
        # Validate before any mutation so rejection never leaves partial records.
        if not isinstance(row,dict): raise ValueError('record must be an object')
        if source in TEXT_SOURCES:
            museum=row.get('museumNumber',{})
            key=record_id if source=='ebl-atf' else row.get('_id')
            if not key and isinstance(museum,dict) and museum.get('prefix') and museum.get('number'):
                key=f"{museum['prefix']}.{museum['number']}{museum.get('suffix','')}"
            if not isinstance(key,str) or not key: raise ValueError('missing source record identity; ATF requires --record-id')
            for field in ('atf','signs'):
                if field in row and not isinstance(row[field],str): raise ValueError(f'{field} must be text')
            external=row.get('externalNumbers',{})
            if not isinstance(external,dict): raise ValueError('externalNumbers must be an object')
            rid,aid=builder.record(key,locator,row)
            cdli=external.get('cdliNumber')
            if isinstance(cdli,str) and cdli: builder.alias(rid,aid,'cdli:'+cdli,locator+'/externalNumbers/cdliNumber')
            for field in ('atf','signs'):
                if row.get(field): builder.text(rid,aid,field,row[field],field=='signs')
            if not row.get('atf'): builder.exclude(rid,locator+'/atf','no transliteration supplied')
        else:
            if None in row or any(v is None for v in row.values()): raise ValueError('malformed/truncated CSV row')
            key=row.get('id_text','').strip()
            if not re.fullmatch(r'\d+|P\d{6}',key): raise ValueError('unrecognized id_text')
            key=key if key.startswith('P') else 'P'+key.zfill(6)
            rid,aid=builder.record(key,locator,row)
            for field in ('museum_no','accession_no'):
                if row.get(field): builder.alias(rid,aid,'catalog-label:'+row[field],locator+'/'+field)
        builder.commit()
        return True
    except ValueError as exc:
        builder.discard()
        builder.add('rejection',identity('reject',builder.snapshot,locator),locator,str(exc),canonical(row))
        builder.commit()
        return False


def ingest(builder: Builder, source: str, data: bytes, record_id: str | None=None) -> None:
    """Small whole-input path (bounded by the caller's input cap)."""
    if source=='oracc':
        raise ValueError('generic ORACC JSON mapping unverified; use the project-export adapter in cuneiform.oracc')
    builder.raw_sha256 = digest(data)
    for locator,row in records(source,data):
        ingest_record(builder,source,locator,row,record_id)
    builder.flush()
