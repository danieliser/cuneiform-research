"""Large frozen source files: streaming inspection and deterministic, immutable cohort extraction.

The parent raw object is never rewritten. Each record is located by exact parent byte range and array index.
A cohort payload is a JSON array whose elements are byte-identical slices of the parent file, so every decoded
field (and every UTF-8 token offset inside it) is identical in parent and cohort. Memory is bounded by one
read chunk plus one record; nothing loads the whole file.
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import codecs
import hashlib
import json
import re
from typing import Any, Iterator
from .adapters import Builder, ingest_record
from .model import PARSER_VERSION, canonical, digest, identity

SCANNER = 'json-array-stream-1'
INSPECTOR = 'ebl-inspect-1'
SELECTOR = 'ebl-cohort-select-1'
COHORT_FORMAT = 'cohort-1'
MAX_RECORD_BYTES = 4 * 1024 * 1024
WS = ' \t\r\n'


def iter_array(path: Path, *, chunk: int = 1 << 20, max_record_bytes: int = MAX_RECORD_BYTES) -> Iterator[dict]:
    """Yield each object element of a top-level JSON array (or a leading `{"fragments": [...]}` member).

    Each item: index, pointer, start/end parent byte offsets, exact raw bytes and the decoded object.
    Non-object elements, trailing data and invalid UTF-8 abort the whole scan: the envelope is not guessed.
    """
    decoder = json.JSONDecoder()
    utf8 = codecs.getincrementaldecoder('utf-8')(errors='strict')
    handle = Path(path).open('rb')
    state = {'buf': '', 'base': 0, 'eof': False}

    def fill() -> bool:
        if state['eof']: return False
        block = handle.read(chunk)
        state['eof'] = not block
        state['buf'] += utf8.decode(block, final=state['eof'])
        return bool(block)

    def skip(pos: int) -> int:
        while True:
            buf = state['buf']
            while pos < len(buf) and buf[pos] in WS: pos += 1
            if pos < len(buf) or not fill(): return pos

    def compact(pos: int) -> None:
        consumed = state['buf'][:pos]
        state['base'] += len(consumed.encode('utf-8'))
        state['buf'] = state['buf'][pos:]

    try:
        pos = skip(0)
        buf = state['buf']
        prefix = ''
        if buf[pos:pos+1] == '{':
            while not re.match(r'\{\s*"fragments"\s*:\s*\[', buf[pos:]) and len(buf) - pos < 4096 and fill(): buf = state['buf']
            match = re.match(r'\{\s*"fragments"\s*:\s*\[', state['buf'][pos:])
            if not match: raise ValueError('unsupported JSON envelope: object without leading "fragments" array')
            pos += match.end(); prefix = '/fragments'
        elif buf[pos:pos+1] == '[':
            pos += 1
        else:
            raise ValueError('unsupported JSON envelope: expected array')
        index = 0
        while True:
            pos = skip(pos)
            buf = state['buf']
            if pos >= len(buf): raise ValueError('truncated JSON array')
            if buf[pos] == ']': pos += 1; break
            if index:
                if buf[pos] != ',': raise ValueError(f'malformed array separator near byte {state["base"] + len(buf[:pos].encode())}')
                pos = skip(pos + 1); buf = state['buf']
            if buf[pos:pos+1] != '{': raise ValueError(f'non-object array element {index}; whole-file scan refused')
            while True:
                try:
                    value, end = decoder.raw_decode(state['buf'], pos); break
                except json.JSONDecodeError as exc:
                    if len(state['buf']) - pos > max_record_bytes * 4: raise ValueError(f'record {index} exceeds scan bound') from exc
                    if not fill(): raise ValueError(f'malformed JSON record {index}: {exc.msg}') from exc
            buf = state['buf']
            raw = buf[pos:end].encode('utf-8')
            if len(raw) > max_record_bytes: raise ValueError(f'record {index} exceeds per-record byte cap')
            start = state['base'] + len(buf[:pos].encode('utf-8'))
            yield {'index': index, 'pointer': f'{prefix}/{index}', 'start': start, 'end': start + len(raw), 'raw': raw, 'value': value}
            index += 1
            compact(end); pos = 0
        if prefix:
            pos = skip(pos)
            if state['buf'][pos:pos+1] != '}': raise ValueError('unsupported envelope: members after fragments array')
            pos += 1
        pos = skip(pos)
        if pos < len(state['buf']): raise ValueError('trailing data after JSON array')
    finally:
        handle.close()


class _Tally(Builder):
    """Runs the real adapter on one record without a database; counts what import would create."""
    def __init__(self):
        super().__init__(None, 'inspection', 'ebl')
        self.last: dict[str, list[tuple]] = {}

    def commit(self) -> None:
        self.last = self.pending; self.discard()

    def flush(self) -> dict[str, int]:
        return {}


def record_stats(locator: str, row: Any) -> dict:
    tally = _Tally()
    ok = ingest_record(tally, 'ebl-cohort', locator, row)
    rows = tally.last
    if not ok:
        return {'rejected': rows['rejection'][0][2]}
    fields = {sid: field for sid, _, _, field, _, _ in rows.get('sequence_version', [])}
    line_field = {lid: fields[sid] for lid, sid, *_ in rows.get('line', [])}
    out: dict[str, Any] = {'rejected': None}
    for field in ('atf', 'signs'):
        out[field] = {'lines': 0, 'positions': 0, 'kinds': Counter(), 'eligible_pairs': 0}
    for lid, field in line_field.items(): out[field]['lines'] += 1
    by_line: dict[str, list[str]] = {}
    for oid, lid, position, raw, reading, kind, *_ in rows.get('occurrence', []):
        f = out[line_field[lid]]; f['positions'] += 1; f['kinds'][kind] += 1
        by_line.setdefault(lid, []).append(kind)
    for lid, kinds in by_line.items():
        f = out[line_field[lid]]
        f['eligible_pairs'] += sum(a in {'reading', 'derived_sign'} and b in {'reading', 'derived_sign'} for a, b in zip(kinds, kinds[1:]))
    for field in ('atf', 'signs'): out[field]['kinds'] = dict(out[field]['kinds'])
    langs = Counter(t[3] for t in rows.get('translation_segment', []))
    out['translations'] = {'segments': sum(langs.values()), 'languages': dict(langs)}
    out['exclusions'] = dict(Counter(r[3] for r in rows.get('exclusion', [])))
    out['aliases'] = len(rows.get('claim', []))
    return out


def _quantiles(values: list[int]) -> dict:
    if not values: return {}
    values = sorted(values); n = len(values)
    return {'min': values[0], 'median': values[n // 2], 'p90': values[int(n * 0.9)], 'p99': values[int(n * 0.99)], 'max': values[-1], 'sum': sum(values)}


def describe(row: dict) -> dict:
    external = row.get('externalNumbers') if isinstance(row.get('externalNumbers'), dict) else {}
    genres = row.get('genres') if isinstance(row.get('genres'), list) else []
    script = row.get('script') if isinstance(row.get('script'), dict) else {}
    return {'source_key': row.get('_id'), 'cdli': external.get('cdliNumber') or None,
            'oracc_project_field': row.get('editedInOraccProject') or None, 'period': script.get('period'),
            'genre_top': sorted({tuple(g.get('category', [])[:2]) and '/'.join(g.get('category', [])[:2]) for g in genres if isinstance(g, dict)}),
            'publication_present': bool(row.get('publication'))}


def inspect_file(path: Path, *, parent_sha256: str, limit: int | None = None) -> dict:
    """Whole-file streaming inspection: structure, coverage, duplicates and adapter outcomes."""
    keys, types = Counter(), Counter()
    sizes, ids = [], Counter()
    first_index: dict[str, int] = {}
    hashes: dict[str, set] = {}
    kinds = {'atf': Counter(), 'signs': Counter()}
    agg = Counter(); tr_langs = Counter(); periods = Counter(); oracc = Counter(); genres = Counter(); exclusions = Counter(); rejections = Counter()
    md5, sha = hashlib.md5(), hashlib.sha256()
    count = 0
    for item in iter_array(path):
        row = item['value']; count += 1
        sizes.append(len(item['raw']))
        for k, v in row.items(): keys[k] += 1; types[f'{k}:{type(v).__name__}'] += 1
        key = row.get('_id'); ids[key] += 1; first_index.setdefault(key, item['index'])
        hashes.setdefault(key, set()).add(digest(item['raw']))
        d = describe(row)
        periods[d['period']] += 1; oracc[d['oracc_project_field']] += 1
        for g in d['genre_top'] or ['(none)']: genres[g] += 1
        agg['cdli_present'] += bool(d['cdli']); agg['publication_present'] += d['publication_present']
        s = record_stats(item['pointer'], row)
        if s['rejected']: rejections[s['rejected']] += 1; continue
        for field in ('atf', 'signs'):
            for kind, n in s[field]['kinds'].items(): kinds[field][kind] += n
            agg[f'{field}_lines'] += s[field]['lines']; agg[f'{field}_eligible_pairs'] += s[field]['eligible_pairs']
            agg[f'{field}_nonempty'] += bool(s[field]['lines'])
        agg['line_count_equal'] += s['atf']['lines'] == s['signs']['lines']
        agg['with_translation'] += bool(s['translations']['segments'])
        for lang, n in s['translations']['languages'].items(): tr_langs[lang] += n
        for reason, n in s['exclusions'].items(): exclusions[reason] += n
        if limit and count >= limit: break
    duplicates = [{'source_key': k, 'occurrences': n, 'byte_identical': len(hashes[k]) == 1, 'first_index': first_index[k]} for k, n in ids.items() if n > 1]
    return {'inspector': INSPECTOR, 'scanner': SCANNER, 'parser_version': PARSER_VERSION, 'parent_sha256': parent_sha256,
            'records': count, 'complete_scan': limit is None, 'record_bytes': _quantiles(sizes),
            'key_presence': dict(keys.most_common()), 'key_types': dict(types.most_common()),
            'duplicate_source_keys': duplicates, 'adapter_rejections': dict(rejections),
            'aggregates': dict(agg), 'position_kinds': {f: dict(c) for f, c in kinds.items()},
            'translation_segments_by_language_tag': dict(tr_langs.most_common()),
            'exclusions_by_reason': dict(exclusions.most_common()),
            'period': dict(periods.most_common()), 'oracc_project_field': {str(k): v for k, v in oracc.most_common()},
            'genre_top_level': dict(genres.most_common(30)),
            'absent_layers': {'word_segmentation': 'no field in export', 'lemmatization': 'no field in export',
                              'translation_alignment': 'only #tr lines inside ATF; span unresolved', 'images': 'not in export'},
            'notes': 'Counts reflect the conservative parser; unsupported positions are retained blockers, not rejected signs.'}


RULE_DEFAULT = {'name': 'usable-text-v1', 'min_eligible_positions': 10, 'min_eligible_pairs': 2, 'max_record_bytes': 262144,
                'require_unique_source_key': True, 'order': 'sha256(parent_sha256 + ":" + source_key) ascending'}


def eligibility(stats: dict, item: dict, rule: dict, duplicated: bool) -> str | None:
    if duplicated and rule['require_unique_source_key']: return 'duplicate source key in parent (all copies excluded)'
    if rule.get('cdli_in') is not None:
        external = item['value'].get('externalNumbers') if isinstance(item['value'].get('externalNumbers'), dict) else {}
        if external.get('cdliNumber') not in set(rule['cdli_in']['keys']): return 'outside exact cdliNumber filter'
    if stats['rejected']: return 'adapter rejection: ' + stats['rejected']
    if len(item['raw']) > rule['max_record_bytes']: return 'record exceeds cohort byte cap'
    if not stats['atf']['lines']: return 'no numbered ATF text line'
    eligible = stats['atf']['kinds'].get('reading', 0) + stats['signs']['kinds'].get('derived_sign', 0)
    if eligible < rule['min_eligible_positions']: return 'fewer eligible reading/sign positions than threshold'
    if stats['atf']['eligible_pairs'] + stats['signs']['eligible_pairs'] < rule['min_eligible_pairs']: return 'fewer adjacent eligible pairs than threshold'
    return None


def select(path: Path, parent: dict, size: int, rule: dict = RULE_DEFAULT) -> dict:
    """Two bounded passes: (1) duplicate keys; (2) eligibility + order key, retaining only the best `size` rows."""
    import heapq
    ids = Counter(item['value'].get('_id') for item in iter_array(path))
    duplicated = {k for k, n in ids.items() if n > 1}
    excluded = Counter(); eligible = 0; heap: list = []
    for item in iter_array(path):
        row = item['value']
        stats = record_stats(item['pointer'], row)
        reason = eligibility(stats, item, rule, row.get('_id') in duplicated)
        if reason: excluded[reason] += 1; continue
        eligible += 1
        order = hashlib.sha256(f'{parent["sha256"]}:{row["_id"]}'.encode()).hexdigest()
        entry = (order, item['index'], item['pointer'], item['start'], item['end'], digest(item['raw']), row['_id'], describe(row), stats)
        # Max-heap on order key keeps exactly the `size` smallest keys; memory is O(size).
        keyed = (-int(order, 16), item['index'], entry)
        if size is None or len(heap) < size: heapq.heappush(heap, keyed)
        elif keyed > heap[0]: heapq.heapreplace(heap, keyed)
    chosen = sorted((e for _, _, e in heap), key=lambda e: e[0])
    return {'eligible': eligible, 'excluded': dict(excluded.most_common()), 'parent_records': sum(ids.values()), 'chosen': chosen}


def cohort_identity(parent: dict, rule: dict, size: int) -> str:
    return identity('cohort', COHORT_FORMAT, SELECTOR, PARSER_VERSION, parent['sha256'], rule, size)


def build_cohort(path: Path, parent: dict, size: int | None, out_root: Path, rule: dict = RULE_DEFAULT) -> dict:
    """Write an immutable cohort directory (manifest.json + payload.json). Existing cohorts are verified, never rewritten.

    size=None selects every eligible record (used with an explicit key filter)."""
    cid = cohort_identity(parent, rule, size)
    target = out_root/cid.replace(':', '-')
    if target.exists(): return verify_cohort(target, path)
    picked = select(path, parent, size, rule)
    if size is not None and len(picked['chosen']) < size: raise ValueError(f'source supports only {len(picked["chosen"])} records under rule; requested {size}')
    stage = out_root/('.pending-' + cid.replace(':', '-'))
    stage.mkdir(parents=True)
    try:
        members = []; offset = 0
        sha = hashlib.sha256()
        with Path(path).open('rb') as parent_handle, (stage/'payload.json').open('xb') as out:
            def write(b: bytes):
                nonlocal offset
                out.write(b); sha.update(b); offset += len(b)
            write(b'[\n')
            for i, (order, index, pointer, start, end, record_sha, key, desc, stats) in enumerate(picked['chosen']):
                parent_handle.seek(start); raw = parent_handle.read(end - start)
                if digest(raw) != record_sha: raise ValueError('parent slice changed between passes')
                if i: write(b',\n')
                members.append({'cohort_index': i, 'payload_pointer': f'/{i}', 'payload_start': offset, 'payload_end': offset + len(raw),
                                'parent_index': index, 'parent_pointer': pointer, 'parent_start': start, 'parent_end': end,
                                'record_sha256': record_sha, 'source_key': key, 'order_key': order, 'metadata': desc, 'parser_stats': stats})
                write(raw)
            write(b'\n]\n')
        manifest = {'format': COHORT_FORMAT, 'selector': SELECTOR, 'parser_version': PARSER_VERSION, 'cohort_id': cid, 'size': size, 'rule': rule,
                    'parent': parent, 'parent_records': picked['parent_records'], 'eligible_records': picked['eligible'],
                    'excluded_by_reason': picked['excluded'], 'payload': {'file': 'payload.json', 'bytes': offset, 'sha256': sha.hexdigest()},
                    'records': members, 'created_at': datetime.now(timezone.utc).isoformat(),
                    'provenance': 'payload elements are byte-identical parent slices; parent bytes are authoritative',
                    'rights': parent.get('rights')}
        manifest['manifest_sha256'] = digest(canonical(manifest).encode())
        (stage/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + '\n')
        stage.rename(target)
    except BaseException:
        import shutil; shutil.rmtree(stage, ignore_errors=True); raise
    return verify_cohort(target, path)


def verify_cohort(directory: Path, parent_path: Path | None = None) -> dict:
    """Check manifest digest, payload hash, every member slice, and (when available) the parent byte ranges."""
    manifest = json.loads((directory/'manifest.json').read_text())
    body = {k: v for k, v in manifest.items() if k != 'manifest_sha256'}
    if digest(canonical(body).encode()) != manifest.get('manifest_sha256'): raise ValueError('cohort manifest integrity failure')
    if manifest['cohort_id'] != cohort_identity(manifest['parent'], manifest['rule'], manifest['size']): raise ValueError('cohort identity mismatch')
    payload = (directory/'payload.json').read_bytes()
    if digest(payload) != manifest['payload']['sha256'] or len(payload) != manifest['payload']['bytes']: raise ValueError('cohort payload integrity failure')
    parent = Path(parent_path).open('rb') if parent_path else None
    try:
        for m in manifest['records']:
            raw = payload[m['payload_start']:m['payload_end']]
            if digest(raw) != m['record_sha256']: raise ValueError('cohort member slice mismatch: ' + m['source_key'])
            if parent is not None:
                parent.seek(m['parent_start'])
                if parent.read(m['parent_end'] - m['parent_start']) != raw: raise ValueError('parent slice mismatch: ' + m['source_key'])
    finally:
        if parent: parent.close()
    if len(json.loads(payload)) != len(manifest['records']): raise ValueError('cohort payload member count mismatch')
    return dict(manifest, verified_parent_slices=parent_path is not None, directory=str(directory))


# ---- runtime-root layout: <root>/derived/{inspections,cohorts,audits} ----

def parent_from_receipt(root: Path, receipt_id: str) -> tuple[Path, dict]:
    from .acquire import load_receipt, verify_raw
    receipt = load_receipt(root, receipt_id)
    path = verify_raw(root, receipt['sha256'], receipt['bytes'])
    parent = {'sha256': receipt['sha256'], 'md5': receipt['md5'], 'bytes': receipt['bytes'], 'url': receipt['url'],
              'receipt_id': receipt['receipt_id'], 'label': receipt.get('label'), 'acquired_at': receipt['finished_at'],
              'rights': receipt['rights'], 'context': receipt.get('context', {})}
    return path, parent


def inspect_parent(root: Path, receipt_id: str) -> dict:
    """Immutable whole-file inspection report keyed by parent hash and inspector/parser versions."""
    path, parent = parent_from_receipt(root, receipt_id)
    rid = identity('inspection', INSPECTOR, SCANNER, PARSER_VERSION, parent['sha256'])
    target = root/'derived'/'inspections'/(rid.replace(':', '-') + '.json')
    if target.exists():
        report = json.loads(target.read_text())
        if digest(canonical({k: v for k, v in report.items() if k != 'report_sha256'}).encode()) != report['report_sha256']: raise ValueError('inspection report integrity failure')
        return dict(report, reused=True)
    import time
    t = time.monotonic()
    report = inspect_file(path, parent_sha256=parent['sha256'])
    report.update({'inspection_id': rid, 'parent': parent, 'elapsed_s': round(time.monotonic() - t, 1), 'created_at': datetime.now(timezone.utc).isoformat()})
    report['report_sha256'] = digest(canonical(report).encode())
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('x', encoding='utf-8') as out: out.write(json.dumps(report, ensure_ascii=False, indent=1) + '\n')
    return report


def cohort_path(root: Path, cohort_id: str) -> Path:
    if not re.fullmatch(r'cohort:[0-9a-f]{32}', cohort_id): raise ValueError('invalid cohort ID')
    return root/'derived'/'cohorts'/cohort_id.replace(':', '-')


def select_cohort(root: Path, receipt_id: str, size: int | None, rule: dict = RULE_DEFAULT) -> dict:
    path, parent = parent_from_receipt(root, receipt_id)
    return build_cohort(path, parent, size, root/'derived'/'cohorts', rule)


def oracc_filtered_rule(root: Path, oracc_receipt: str, project: str) -> dict:
    """Exact P-number set from an acquired ORACC project corpus.json; matching is by identifier only, never by name."""
    from .oracc import _zip, _member
    z, receipt = _zip(root, oracc_receipt)
    with z: keys = sorted(json.loads(_member(z, f'{project}/corpus.json'))['members'])
    return dict(RULE_DEFAULT, name='usable-text-v1+oracc-p-number-filter', cdli_in={'source': f'ORACC {project} corpus.json members', 'zip_sha256': receipt['sha256'], 'receipt_id': oracc_receipt, 'keys': keys})


def audit(manifest: dict) -> dict:
    """Per-record feasibility table for a cohort; counts come from the real adapter, unknowns stay explicit."""
    rows = []
    for m in manifest['records']:
        s, d = m['parser_stats'], m['metadata']
        rows.append({'cohort_index': m['cohort_index'], 'source_key': m['source_key'], 'parent_pointer': m['parent_pointer'],
                     'parent_bytes': m['parent_end'] - m['parent_start'], 'cdli': d['cdli'], 'period': d['period'], 'genre': d['genre_top'],
                     'oracc_project_field': d['oracc_project_field'], 'publication_present': d['publication_present'],
                     'atf_lines': s['atf']['lines'], 'atf_kinds': s['atf']['kinds'], 'signs_lines': s['signs']['lines'], 'signs_kinds': s['signs']['kinds'],
                     'eligible_pairs': s['atf']['eligible_pairs'] + s['signs']['eligible_pairs'], 'line_count_equal': s['atf']['lines'] == s['signs']['lines'],
                     'translations': s['translations'], 'exclusions': sum(s['exclusions'].values())})
    n = len(rows)
    def frac(pred): return f'{sum(1 for r in rows if pred(r))}/{n}'
    totals = Counter()
    for r in rows:
        for f in ('atf_kinds', 'signs_kinds'):
            for k, v in r[f].items(): totals[f'{f[:-6]}:{k}'] += v
        totals['translation_segments'] += r['translations']['segments']
    return {'cohort_id': manifest['cohort_id'], 'parent_sha256': manifest['parent']['sha256'], 'size': n, 'rule': manifest['rule'],
            'parent_records': manifest['parent_records'], 'eligible_records': manifest['eligible_records'], 'excluded_by_reason': manifest['excluded_by_reason'],
            'field_coverage': {'cdli_number': frac(lambda r: r['cdli']), 'period': frac(lambda r: r['period'] not in (None, 'None')), 'genre': frac(lambda r: r['genre']),
                               'publication': frac(lambda r: r['publication_present']), 'oracc_project_field': frac(lambda r: r['oracc_project_field']),
                               'translation_lines': frac(lambda r: r['translations']['segments']), 'signs_atf_line_count_equal': frac(lambda r: r['line_count_equal'])},
            'position_totals': dict(totals),
            'unknowns': {'word_segmentation': f'absent from export (0/{n})', 'lemma_or_sense': f'absent from export (0/{n})',
                         'translation_alignment': f'all {totals["translation_segments"]} segments unresolved-span; no word/line alignment asserted',
                         'signs_to_atf_alignment': 'line-count equality is observed only; no position alignment asserted',
                         'composition_membership': 'not inferred', 'images': 'not acquired'},
            'records': rows}


def audit_markdown(report: dict) -> str:
    lines = [f"# Cohort feasibility audit `{report['cohort_id']}`", '',
             f"Parent sha256 `{report['parent_sha256']}`; {report['parent_records']} parent records, {report['eligible_records']} eligible under `{report['rule']['name']}`; {report['size']} selected by `{report['rule']['order']}`.", '',
             '## Field coverage', '', '| field | records |', '|---|---|'] + [f'| {k} | {v} |' for k, v in report['field_coverage'].items()] + [
             '', '## Unknown / unavailable layers', ''] + [f'- **{k}**: {v}' for k, v in report['unknowns'].items()] + [
             '', '## Parent exclusions (whole file)', '', '| reason | records |', '|---|---|'] + [f'| {k} | {v} |' for k, v in report['excluded_by_reason'].items()] + [
             '', '## Records', '', '| # | source key | CDLI | period | genre | ATF lines | ATF reading/gap/unsupported | signs lines | sign/gap/unsupported | eligible pairs | tr segments | exclusions |', '|---|---|---|---|---|---|---|---|---|---|---|---|']
    for r in report['records']:
        a, s = r['atf_kinds'], r['signs_kinds']
        lines.append(f"| {r['cohort_index']} | {r['source_key']} | {r['cdli'] or '—'} | {r['period']} | {', '.join(r['genre']) or '—'} | {r['atf_lines']} | {a.get('reading',0)}/{a.get('gap',0)}/{a.get('unsupported',0)} | {r['signs_lines']} | {s.get('derived_sign',0)}/{s.get('gap',0)}/{s.get('unsupported',0)} | {r['eligible_pairs']} | {r['translations']['segments']} | {r['exclusions']} |")
    return '\n'.join(lines) + '\n'
