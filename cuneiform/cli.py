import argparse
import json
import os
from pathlib import Path
from .storage import Config, fetch, import_source, inspect, resolve_snapshot, store_path, verify
from .query import motif, trace

REPO=Path(__file__).resolve().parents[1]
ORGANIZATIONS=['report','span','postings','motifs','sequence','occurrence','reverse-postings','reverse-motifs','aliases','catalog','translations','neighbors','nodes','words','lemmas']


def scope_args(p):
    p.add_argument('--namespace');p.add_argument('--snapshot');p.add_argument('--field',choices=['atf','signs'],default='atf');p.add_argument('--policy',choices=['source','strict'],default='source');p.add_argument('--limit',type=int,default=20);p.add_argument('--offset',type=int,default=0)


def main() -> None:
    parser=argparse.ArgumentParser(description='Bounded source-preserving cuneiform graph and corpus pilot')
    parser.add_argument('--root',type=Path,default=Path(os.environ.get('CUNEIFORM_STORAGE_ROOT',str(Path.home()/'.local/share/cuneiform-research'))))
    parser.add_argument('--max-total-gib',type=float,help='explicit task budget for all bytes under --root (default 5 GiB)')
    parser.add_argument('--reserve-gib',type=float,help='explicit free-space reserve kept on the filesystem (default 10 GiB)')
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('inspect','import'):
        p=sub.add_parser(name); p.add_argument('source',choices=['ebl','ebl-atf','cdli','oracc']); p.add_argument('path',type=Path)
        if name=='import':
            p.add_argument('--namespace');p.add_argument('--record-id');p.add_argument('--source-url');p.add_argument('--dry-run',action='store_true')
    p=sub.add_parser('demo');p.add_argument('source',choices=['ebl','cdli']);p.add_argument('path',type=Path);p.add_argument('pattern',nargs='+');p.add_argument('--field',choices=['atf','signs'],default='atf')
    p=sub.add_parser('explore',help='in-memory organizations over a small local input');p.add_argument('source',choices=['ebl','cdli']);p.add_argument('path',type=Path);p.add_argument('organization',nargs='?',default='report',choices=ORGANIZATIONS[:13]);p.add_argument('value',nargs='?',default='');p.add_argument('--also-cdli',type=Path);scope_args(p)
    p=sub.add_parser('fetch');p.add_argument('url');p.add_argument('--allowlist',type=Path,required=True);p.add_argument('--max-bytes',type=int,default=256*1024)
    p=sub.add_parser('acquire',help='checksum-verified download into the immutable raw store');p.add_argument('url');p.add_argument('--allowlist',type=Path,default=REPO/'sources/allowlist.json');p.add_argument('--max-bytes',type=int,required=True);p.add_argument('--expect-md5');p.add_argument('--expect-sha256');p.add_argument('--expect-bytes',type=int);p.add_argument('--label',default='');p.add_argument('--rights',type=Path,help='JSON rights ledger entry');p.add_argument('--context',default='{}',help='JSON object recorded verbatim');p.add_argument('--chain-intermediate',type=Path,help='one verified intermediate certificate a server omits')
    sub.add_parser('receipts',help='list verified acquisition receipts')
    p=sub.add_parser('corpus-inspect',help='streaming whole-file inspection of an acquired eBL JSON export');p.add_argument('receipt')
    p=sub.add_parser('corpus-select',help='deterministic cohort extraction with immutable manifest');p.add_argument('receipt');p.add_argument('--size',type=int);p.add_argument('--all-eligible',action='store_true',help='every eligible record of the parent (size=None), with per-record exclusion accounting');p.add_argument('--cdli-from-oracc',help='ORACC export receipt: keep only exact cdliNumber matches with its corpus');p.add_argument('--project')
    p=sub.add_parser('corpus-audit',help='per-record feasibility audit for a cohort');p.add_argument('cohort');p.add_argument('--markdown',action='store_true')
    p=sub.add_parser('corpus-accounting',help='exhaustive parent-record accounting of a cohort (members + excluded records with reasons)');p.add_argument('cohort')
    p=sub.add_parser('corpus-import',help='chunked import of a cohort into an immutable snapshot');p.add_argument('cohort');p.add_argument('--batch',type=int,default=200)
    p.add_argument('--projections',choices=['corpus','full'],default='corpus',help='projection ceiling preset (part of the snapshot ID)');p.add_argument('--memory',default='1GB',help='DuckDB memory limit for the build (no spill)')
    sub.add_parser('snapshots',help='list and verify persisted snapshots (ledger-checked)')
    p=sub.add_parser('publication-status',help='ledger state, open reservations and leftover stages (read-only)');p.add_argument('snapshot',nargs='?')
    p=sub.add_parser('publication-recover',help='resolve an interrupted reservation; never publishes bytes other than the reserved ones');p.add_argument('snapshot');p.add_argument('--action',choices=['inspect','commit','complete','discard','abandon'],default='inspect');p.add_argument('--reason',default='')
    p=sub.add_parser('publication-adopt',help='explicitly ledger an existing snapshot directory that has no ledger record');p.add_argument('snapshot');p.add_argument('--reason',required=True)
    p=sub.add_parser('publication-repair-ledger',help='append-only acknowledgement of a torn final ledger record');p.add_argument('--reason',required=True)
    p=sub.add_parser('publication-clean-stage',help='remove one named leftover .pending-* stage that no reservation names');p.add_argument('stage');p.add_argument('--min-age-s',type=int,default=600)
    for name in ('publication-status','publication-recover','publication-adopt','publication-repair-ledger','publication-clean-stage'):
        sub.choices[name].add_argument('--store',choices=['snapshots','cohorts'],default='snapshots',help='which ledgered store: <root>/snapshots (default) or <root>/derived/cohorts')
    p=sub.add_parser('scope',help='population a snapshot describes (cohort size, eligible/parent denominators, parent receipt)');p.add_argument('snapshot')
    p=sub.add_parser('manifest');p.add_argument('snapshot')
    p=sub.add_parser('lookup',help='bounded organizations over a persisted snapshot');p.add_argument('snapshot');p.add_argument('organization',choices=ORGANIZATIONS);p.add_argument('value',nargs='?',default='');scope_args(p)
    p=sub.add_parser('query');p.add_argument('snapshot');p.add_argument('pattern',nargs='+');p.add_argument('--field',choices=['atf','signs'],default='atf');p.add_argument('--strict',action='store_true');p.add_argument('--max-skip',type=int,default=0)
    p=sub.add_parser('parity',help='graph / sequence-array / materialized-index motif counts on one snapshot');p.add_argument('snapshot');p.add_argument('pattern');p.add_argument('--field',choices=['atf','signs'],default='signs')
    p=sub.add_parser('trace');p.add_argument('snapshot');p.add_argument('occurrence')
    p=sub.add_parser('trace-word',help='re-resolve an ORACC WordToken in payload and parent zip');p.add_argument('snapshot');p.add_argument('word')
    p=sub.add_parser('export-graph',help='portable node/edge Parquet export with receipt');p.add_argument('snapshot')
    p=sub.add_parser('catalog-link',help='exact catalog-key candidates across snapshots; never merges');p.add_argument('key');p.add_argument('--snapshot',action='append',required=True)
    p=sub.add_parser('cdli-import',help='bounded CDLI artifact JSON for exact P-numbers claimed in a snapshot');p.add_argument('--from-snapshot',required=True);p.add_argument('--allowlist',type=Path,required=True);p.add_argument('--max-records',type=int,default=100)
    p=sub.add_parser('oracc-inspect',help='inspect an acquired ORACC project JSON export');p.add_argument('receipt')
    p=sub.add_parser('oracc-import',help='import selected texts of an acquired ORACC project export');p.add_argument('receipt');p.add_argument('--project',required=True);p.add_argument('--text',action='append',default=[]);p.add_argument('--texts-from-snapshot',help='select project texts whose P-number matches cdli alias claims in this snapshot');p.add_argument('--max-texts',type=int,default=100)
    args=parser.parse_args()
    budget={}
    if args.max_total_gib is not None: budget['max_total_bytes']=int(args.max_total_gib*1024**3)
    if args.reserve_gib is not None: budget['reserve_bytes']=int(args.reserve_gib*1024**3)
    cfg=Config(args.root.expanduser().resolve(),**budget)
    try:
        result=dispatch(args,cfg)
        if isinstance(result,str): print(result,end='')
        else: print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
    except (ValueError,OSError,KeyError) as exc:
        parser.exit(2,f'error: {exc}\n')


def dispatch(args, cfg):
    c=args.command
    if c=='explore':
        from .projections import explore
        return explore(args.source,args.path,cfg,args.organization,args.value,also_cdli=args.also_cdli,namespace=args.namespace,snapshot=args.snapshot,field=args.field,policy=args.policy,limit=args.limit,offset=args.offset)
    if c=='demo':
        from .demo import run
        return run(args.source,args.path,cfg,args.pattern,args.field)
    if c=='inspect': return inspect(args.source,args.path,cfg)
    if c=='import': return import_source(args.source,args.path,cfg,args.namespace,args.record_id,args.source_url,args.dry_run)
    if c=='fetch': return fetch(args.url,args.allowlist,cfg,args.max_bytes)
    if c=='acquire':
        from .acquire import acquire
        rights=json.loads(args.rights.read_text()) if args.rights else None
        return acquire(args.url,args.allowlist,cfg,max_bytes=args.max_bytes,expect_md5=args.expect_md5,expect_sha256=args.expect_sha256,expect_bytes=args.expect_bytes,label=args.label,rights=rights,context=json.loads(args.context),chain_intermediate=args.chain_intermediate)
    if c=='receipts':
        from .acquire import receipts
        return [{k:r[k] for k in ('receipt_id','label','url','bytes','sha256','md5','finished_at','storage','checks')} for r in receipts(cfg.root)]
    if c=='corpus-inspect':
        from .corpus import inspect_parent
        report=inspect_parent(cfg.root,args.receipt)
        return {k:report[k] for k in report if k not in ('key_types',)}
    if c=='corpus-select':
        from .corpus import select_cohort, oracc_filtered_rule, RULE_DEFAULT
        if args.all_eligible and (args.size is not None or args.cdli_from_oracc): raise ValueError('--all-eligible excludes --size and key filters')
        if args.size is None and not args.cdli_from_oracc and not args.all_eligible: raise ValueError('--size required unless --all-eligible or an exact key filter is given')
        rule=oracc_filtered_rule(cfg.root,args.cdli_from_oracc,args.project) if args.cdli_from_oracc else RULE_DEFAULT
        m=select_cohort(cfg.root,args.receipt,args.size,rule)
        return {k:m[k] for k in ('cohort_id','directory','size','parent_records','eligible_records','excluded_by_reason','payload','rule','verified_parent_slices')}
    if c=='corpus-audit':
        from .corpus import audit, audit_markdown, cohort_path, verify_cohort
        report=audit(verify_cohort(cohort_path(cfg.root,args.cohort),ledger='store'))
        return audit_markdown(report) if args.markdown else report
    if c=='corpus-accounting':
        from .corpus import accounting, cohort_path, verify_cohort
        from .acquire import raw_path
        directory=cohort_path(cfg.root,args.cohort)
        declared=json.loads((directory/'manifest.json').read_text())
        parent=raw_path(cfg.root,declared['parent']['sha256'])
        m=verify_cohort(directory,parent if parent.exists() else None,ledger='store')
        return dict(accounting(m),cohort_id=m['cohort_id'],verified_parent_slices=m['verified_parent_slices'],publication=m['publication'])
    if c=='corpus-import':
        from .corpus import cohort_path, raise_missing_cohort
        from .acquire import raw_path
        from .storage import import_cohort
        directory=cohort_path(cfg.root,args.cohort)
        if not os.path.lexists(directory/'manifest.json'): raise_missing_cohort(directory)
        parent=json.loads((directory/'manifest.json').read_text())['parent']
        from .storage import PROJECTION_PRESETS
        r=import_cohort(directory,cfg,PROJECTION_PRESETS[args.projections],parent_path=raw_path(cfg.root,parent['sha256']),batch=args.batch,memory=args.memory,cohort_ledger='store')
        m=r['manifest']
        return {'snapshot':r['snapshot'],'reused':r['reused'],'counts':m['counts'],'ingestion':m.get('ingestion'),'build_timings':m.get('build_timings'),'snapshot_payload_bytes':m.get('snapshot_payload_bytes')}
    if c=='snapshots':
        out=[]
        for d in sorted((cfg.root/'snapshots').glob('snapshot:*')) if (cfg.root/'snapshots').exists() else []:
            try:
                from .storage import verified
                from .persisted import scope
                v=verified(d,d.name,ledger='require'); m=v['manifest']
                sc=scope(d,m)
                out.append({'scope_label':sc['label'],'scope_note':sc['scope_note'],'manifest_sha256':m['manifest_sha256'],'snapshot':d.name,'source':m['source'],'namespace':m['namespace'],'record_id':m['record_id'],'imported':m['retrieved_or_imported_at'],'occurrences':m['counts'].get('occurrence'),'bytes':m.get('snapshot_payload_bytes'),'verified':True,'publication':v['publication'],'input_identity':sc['input_identity']})
            except (ValueError,OSError,KeyError) as exc: out.append({'snapshot':d.name,'verified':False,'error':str(exc),'state':getattr(exc,'state',None)})
        return out
    if c.startswith('publication-'): return publication_command(args,cfg)
    if c=='manifest': return verify(store_path(cfg,args.snapshot),args.snapshot)
    if c=='scope':
        from .persisted import scope
        return scope(store_path(cfg,args.snapshot))
    if c=='lookup':
        from .persisted import lookup_snapshot
        return lookup_snapshot(store_path(cfg,args.snapshot),args.organization,args.value,namespace=args.namespace,snapshot=args.snapshot,field=args.field,policy=args.policy,limit=args.limit,offset=args.offset)
    if c=='query': return motif(store_path(cfg,args.snapshot),args.pattern,args.field,args.strict,args.max_skip)
    if c=='parity':
        from .persisted import parity
        return parity(store_path(cfg,args.snapshot),json.loads(args.pattern),args.field)
    if c=='trace': return trace(store_path(cfg,args.snapshot),args.occurrence,parent_root=cfg.root)
    if c=='trace-word':
        from .oracc import trace_word
        return trace_word(store_path(cfg,args.snapshot),args.word,parent_root=cfg.root)
    if c=='export-graph':
        from .persisted import export_graph
        return export_graph(store_path(cfg,args.snapshot),cfg)
    if c=='catalog-link':
        from .persisted import catalog_link
        return catalog_link([store_path(cfg,s) for s in args.snapshot],args.key)
    if c=='cdli-import':
        from .cdli_api import fetch as cdli_fetch, import_artifacts, pnumbers_from_snapshot
        got=cdli_fetch(cfg,pnumbers_from_snapshot(store_path(cfg,args.from_snapshot)),args.allowlist,max_records=args.max_records)
        return import_artifacts(cfg,got)
    if c=='oracc-inspect':
        from .oracc import inspect_export
        return inspect_export(cfg.root,args.receipt)
    if c=='oracc-import':
        from .oracc import import_project
        return import_project(cfg,args.receipt,args.project,texts=args.text,match_snapshot=store_path(cfg,args.texts_from_snapshot) if args.texts_from_snapshot else None,max_texts=args.max_texts)
    raise ValueError('unknown command')


def publication_command(args, cfg):
    import time
    from .publication import adopt, discard_stage, inspect_reservation, recover
    c=args.command
    if args.store=='cohorts':
        # Same reserve/commit machinery, rooted at <root>/derived/cohorts with the cohort ledger (key cohort_id). The check
        # content-verifies the cohort, requires its identity to equal the requested ID, and compares member slices with
        # the receipt-bound parent raw object when it is present.
        from .corpus import cohort_check, cohort_ledger, valid_cid
        folder=cfg.root/'derived'/'cohorts'; ledger=cohort_ledger(folder); valid=valid_cid; check=cohort_check(cfg.root); pattern='cohort-*'
    else:
        from .storage import store_ledger, valid_sid, verify_content
        folder=cfg.root/'snapshots'; ledger=store_ledger(cfg); valid=valid_sid; check=verify_content; pattern='snapshot:*'
    if c=='publication-status':
        entries,tail=ledger.scan()
        ids=[valid(args.snapshot)] if args.snapshot else ledger.ids()
        states=[]
        for sid in ids:
            st=ledger.status(sid,entries)
            states.append({'id':sid,'snapshot' if args.store=='snapshots' else 'cohort':sid,'state':st.state,'kind':st.kind,'manifest_sha256':st.manifest_sha256,
                           'directory_present':os.path.lexists(folder/ledger.dirname(sid)),'reason':st.reason,
                           **({'recovery':inspect_reservation(ledger,sid,folder,check)} if st.state=='reserved' else {})})
        known={ledger.dirname(i) for i in ledger.ids()}
        entries_on_disk=sorted(folder.glob(pattern)) if folder.exists() else []
        ids_known=set(ledger.ids())
        stages=[{'stage':d.name,'age_s':round(time.time()-d.stat().st_mtime),'named_by_reservation':any(ledger.status(i,entries).stage==d.name for i in ids_known)} for d in sorted(folder.glob('.pending-*'))] if folder.exists() else []
        return {'store':args.store,'ledger':str(ledger.path),'ledger_exists':ledger.exists(),'torn_tail':tail,'snapshots' if args.store=='snapshots' else 'cohorts':states,
                'unledgered_directories':[d.name for d in entries_on_disk if d.name not in known],
                'symlinked_entries':[d.name for d in entries_on_disk if d.is_symlink()],'stages':stages,
                'limits':'application-level protocol for cooperating writers; same-owner OS access and root can still alter files and the ledger'}
    if c=='publication-recover':
        sid=valid(args.snapshot)
        if args.action=='inspect': return inspect_reservation(ledger,sid,folder,check)
        if not args.reason: raise ValueError('--reason is required for a recovery action')
        return recover(ledger,sid,folder,args.action,check,args.reason)
    if c=='publication-adopt': return adopt(ledger,valid(args.snapshot),folder,check,args.reason)
    if c=='publication-repair-ledger': return ledger.repair_tail(args.reason)
    if c=='publication-clean-stage':
        name=args.stage
        if not name.startswith('.pending-') or '/' in name: raise ValueError(f'only a .pending-* stage name inside the {args.store} store is accepted')
        stage=folder/name
        if not stage.is_dir(): raise ValueError(f'{stage} does not exist')
        with ledger.locked():
            entries=ledger.writer_scan()
            if any(ledger.status(i,entries).state=='reserved' and ledger.status(i,entries).stage==name for i in ledger.ids()):
                raise ValueError(f'{name} is named by an open reservation; use publication-recover')
            if time.time()-stage.stat().st_mtime<args.min_age_s: raise ValueError(f'{name} is younger than {args.min_age_s}s and may belong to a live build')
            discard_stage(stage)
        return {'removed':str(stage)}
    raise ValueError('unknown command')

if __name__=='__main__': main()
