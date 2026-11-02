import argparse
import json
import os
from pathlib import Path
from .storage import Config, fetch, import_source, inspect, resolve_snapshot, verify
from .query import motif, trace


def main() -> None:
    parser=argparse.ArgumentParser(description='Bounded source-preserving graph foundation')
    parser.add_argument('--root',type=Path,default=Path(os.environ.get('CUNEIFORM_STORAGE_ROOT',str(Path.home()/'.local/share/cuneiform-research'))))
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('inspect','import'):
        p=sub.add_parser(name); p.add_argument('source',choices=['ebl','ebl-atf','cdli','oracc']); p.add_argument('path',type=Path)
        if name=='import':
            p.add_argument('--namespace');p.add_argument('--record-id');p.add_argument('--source-url');p.add_argument('--dry-run',action='store_true')
    p=sub.add_parser('demo');p.add_argument('source',choices=['ebl','cdli']);p.add_argument('path',type=Path);p.add_argument('pattern',nargs='+');p.add_argument('--field',choices=['atf','signs'],default='atf')
    p=sub.add_parser('explore');p.add_argument('source',choices=['ebl','cdli']);p.add_argument('path',type=Path);p.add_argument('organization',nargs='?',default='report',choices=['report','span','postings','motifs','sequence','occurrence','reverse-postings','reverse-motifs','aliases','catalog','translations','neighbors','nodes']);p.add_argument('value',nargs='?',default='');p.add_argument('--also-cdli',type=Path);p.add_argument('--namespace');p.add_argument('--snapshot');p.add_argument('--field',choices=['atf','signs'],default='atf');p.add_argument('--policy',choices=['source','strict'],default='source');p.add_argument('--limit',type=int,default=20);p.add_argument('--offset',type=int,default=0)
    p=sub.add_parser('fetch');p.add_argument('url');p.add_argument('--allowlist',type=Path,required=True);p.add_argument('--max-bytes',type=int,default=256*1024)
    p=sub.add_parser('manifest');p.add_argument('snapshot')
    p=sub.add_parser('query');p.add_argument('snapshot');p.add_argument('pattern',nargs='+');p.add_argument('--field',choices=['atf','signs'],default='atf');p.add_argument('--strict',action='store_true');p.add_argument('--max-skip',type=int,default=0)
    p=sub.add_parser('trace');p.add_argument('snapshot');p.add_argument('occurrence')
    args=parser.parse_args();cfg=Config(args.root.expanduser().resolve())
    try:
        if args.command=='explore':
            from .projections import explore
            result=explore(args.source,args.path,cfg,args.organization,args.value,also_cdli=args.also_cdli,namespace=args.namespace,snapshot=args.snapshot,field=args.field,policy=args.policy,limit=args.limit,offset=args.offset)
        elif args.command=='demo':
            from .demo import run
            result=run(args.source,args.path,cfg,args.pattern,args.field)
        elif args.command=='inspect': result=inspect(args.source,args.path,cfg)
        elif args.command=='import': result=import_source(args.source,args.path,cfg,args.namespace,args.record_id,args.source_url,args.dry_run)
        elif args.command=='fetch': result=fetch(args.url,args.allowlist,cfg,args.max_bytes)
        elif args.command=='manifest': result=verify(resolve_snapshot(cfg,args.snapshot))
        elif args.command=='query': result=motif(resolve_snapshot(cfg,args.snapshot),args.pattern,args.field,args.strict,args.max_skip)
        else: result=trace(resolve_snapshot(cfg,args.snapshot),args.occurrence)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,OSError) as exc:
        parser.exit(2,f'error: {exc}\n')

if __name__=='__main__': main()
