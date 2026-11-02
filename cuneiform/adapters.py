"""Small inspected contracts, deliberately conservative about unsupported layers."""
import csv
import io
import json
import re
from typing import Any
from .model import PARSER_VERSION, canonical, identity

RIGHTS = {
 'ebl': {'status':'unresolved-conflict','claims':['Zenodo 10018951: CC BY 4.0','JOHD paper: CC BY-NC-SA 4.0'], 'reuse':'not cleared; text/annotations/photos have distinct grants'},
 'ebl-atf': {'status':'unknown','reuse':'local caller-supplied ATF; rights not inferred'},
 'cdli': {'status':'unknown','reuse':'historical GitHub catalog; no data grant established'},
 'oracc': {'status':'unverified-project','reuse':'review reports CC BY-SA 3.0; individual project not verified'},
}

class Builder:
    def __init__(self, db: Any, snapshot: str, namespace: str):
        self.db, self.snapshot, self.namespace = db, snapshot, namespace
        self.seen: set[str] = set()

    def add(self, table: str, *values: object) -> None:
        self.db.execute(f'INSERT INTO {table} VALUES ({",".join("?" for _ in values)})', values)

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
        self.add('artifact',aid,rid,key,canonical(raw))
        return rid,aid

    def alias(self, record: str, artifact: str, target: str, locator: str) -> None:
        self.add('claim',identity('claim',record,locator,target),record,artifact,'catalog_alias',target,'source-attributed-unreviewed','Source crosswalk; no identity merge or independence assertion',canonical({'locator':locator,'independence':'unknown'}))

    def sequence(self, record: str, artifact: str, field: str, evidence: str) -> tuple[str,str]:
        # A local fragment reading contribution, NOT inferred composition membership.
        wid=identity('witness',record)
        self.db.execute('INSERT INTO witness VALUES (?,?,?,?) ON CONFLICT DO NOTHING',[wid,record,artifact,'source fragment contribution; composition unknown'])
        if not self.db.execute("SELECT 1 FROM edge WHERE kind='ON_ARTIFACT' AND source_id=?",[wid]).fetchone():
            self.edge('ON_ARTIFACT',wid,artifact,record)
        sid=identity('sequence',record,field,PARSER_VERSION)
        self.add('sequence_version',sid,record,wid,field,PARSER_VERSION,evidence)
        self.edge('HAS_SEQUENCE',wid,sid,record)
        return wid,sid

    def text(self, record: str, artifact: str, field: str, text: str, derived: bool=False) -> None:
        _,sid=self.sequence(record,artifact,field,'source-derived-sign-list' if derived else 'editorial-transliteration')
        offset=0; previous_line=None; ordinal=0; surface=None; column=None
        for source_line_no, rawline in enumerate(text.splitlines(keepends=True)):
            line=rawline.rstrip('\r\n'); match=re.match(r"([^\s]+)\.\s+(.*)",line)
            if line.startswith('@column '): column=line[8:]
            elif line.startswith('@'): surface=line[1:]; column=None
            if line.startswith('#tr.'):
                tm=re.match(r'#tr\.([a-z-]+):\s*(.*)',line)
                if tm:
                    # The README demonstrates translations spanning preceding multiple lines.
                    # Preserve placement; do not falsely assert single-line alignment.
                    self.add('translation_segment',identity('translation',sid,source_line_no),record,sid,tm[1],tm[2],None,'unresolved-span',f'{field}:utf8:{offset}:{offset+len(line.encode())}')
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
            for position,m in enumerate(re.finditer(r'\S+',body)):
                raw=m[0]; start=offset+len(line[:begin+m.start()].encode()); end=start+len(raw.encode())
                restored=bracket_depth>0 or '[' in raw
                bracket_depth=max(0,bracket_depth+raw.count('[')-raw.count(']'))
                stripped=raw.strip('[]?#')
                gap=stripped in {'x','X','...','…','(x)'}
                simple=bool(re.fullmatch(r'[^\W\d][\w₀-₉]*',stripped))
                kind='gap' if gap else ('derived_sign' if derived else ('reading' if simple else 'unsupported'))
                reading=None if kind in {'gap','unsupported'} else stripped
                preservation='unknown' if derived else ('lost' if restored else ('damaged' if '#' in raw else 'unknown'))
                certainty='unknown' if derived or kind!='reading' else ('uncertain' if '?' in raw else 'unmarked')
                oid=identity('occurrence',lid,position)
                self.add('occurrence',oid,lid,position,raw,reading,kind,preservation,certainty,'unknown',start,end)
                self.edge('HAS_OCCURRENCE',lid,oid,record)
                if previous: self.edge('NEXT',previous,oid,record,extent='represented-position',boundary='same-line')
                previous=oid
                if kind=='unsupported': self.exclude(record,f'{field}:utf8:{start}:{end}','unsupported compound/segmentation; retained as blocking position')
                if derived and not gap:
                    st=identity('sign',self.namespace,self.snapshot,stripped)
                    self.db.execute('INSERT INTO sign_type VALUES (?,?,?,?) ON CONFLICT DO NOTHING',[st,'ebl-export-signs',self.snapshot,stripped])
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


def ingest(builder: Builder, source: str, data: bytes, record_id: str | None=None) -> None:
    if source=='oracc':
        raise ValueError('ORACC import unverified: inspect local JSON only; no invented field mapping')
    for locator,row in records(source,data):
        try:
            # Validate before any mutation so rejection never leaves partial records.
            if not isinstance(row,dict): raise ValueError('record must be an object')
            if source in {'ebl','ebl-atf'}:
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
        except ValueError as exc:
            builder.add('rejection',identity('reject',builder.snapshot,locator),locator,str(exc),canonical(row))
