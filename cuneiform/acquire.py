"""Checksum-verified acquisition into an immutable content-addressed raw store.

<root>/raw/sha256/<hex>          read-only bytes, never rewritten
<root>/receipts/<receipt>.json   one immutable receipt per acquisition event (URL, time, headers, hashes, rights)

No crawling, retries, redirects or rights inference. Public access is not a reuse grant.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import ssl
import stat
import urllib.request
import uuid
from .model import canonical, digest, identity

ACQUIRER = 'acquire-1'
KEPT_HEADERS = ('content-length', 'content-type', 'last-modified', 'etag', 'date', 'content-disposition', 'content-md5')


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def raw_path(root: Path, sha256: str) -> Path:
    if len(sha256) != 64 or any(c not in '0123456789abcdef' for c in sha256): raise ValueError('invalid sha256')
    return root/'raw'/'sha256'/sha256


def hash_file(path: Path) -> dict:
    md5, sha = hashlib.md5(), hashlib.sha256(); size = 0
    with path.open('rb') as handle:
        while block := handle.read(1 << 20):
            md5.update(block); sha.update(block); size += len(block)
    return {'bytes': size, 'md5': md5.hexdigest(), 'sha256': sha.hexdigest()}


def verify_raw(root: Path, sha256: str, expected_bytes: int | None=None) -> Path:
    path = raw_path(root, sha256)
    if not path.is_file(): raise ValueError('raw object unavailable: ' + sha256)
    seen = hash_file(path)
    if seen['sha256'] != sha256 or (expected_bytes is not None and seen['bytes'] != expected_bytes):
        raise ValueError('raw object integrity failure: ' + sha256)
    return path


def write_receipt(root: Path, receipt: dict) -> dict:
    receipt = dict(receipt)
    receipt['receipt_id'] = identity('receipt', canonical({k: v for k, v in receipt.items() if k != 'receipt_id'}))
    receipt['receipt_sha256'] = digest(canonical(receipt).encode())
    target = root/'receipts'/(receipt['receipt_id'].replace(':', '-') + '.json')
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('x', encoding='utf-8') as out: out.write(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    return receipt


def load_receipt(root: Path, receipt_id: str) -> dict:
    receipt = json.loads((root/'receipts'/(receipt_id.replace(':', '-') + '.json')).read_text())
    body = {k: v for k, v in receipt.items() if k != 'receipt_sha256'}
    if digest(canonical(body).encode()) != receipt.get('receipt_sha256'): raise ValueError('receipt integrity failure')
    return receipt


def receipts(root: Path) -> list[dict]:
    folder = root/'receipts'
    return [load_receipt(root, json.loads(p.read_text())['receipt_id']) for p in sorted(folder.glob('*.json'))] if folder.exists() else []


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError(f'redirect denied ({code} -> {newurl}); explicitly allow and request the final URL')


def acquire(url: str, allowlist: Path, config, *, max_bytes: int, expect_md5: str | None=None, expect_sha256: str | None=None,
            expect_bytes: int | None=None, label: str='', rights: dict | None=None, context: dict | None=None, timeout: int=60,
            chain_intermediate: Path | None=None) -> dict:
    """Stream one allowlisted HTTPS URL. Partial bytes never enter the raw store; mismatches retain nothing."""
    allowed = json.loads(Path(allowlist).read_text())
    if not url.startswith('https://') or url not in allowed: raise ValueError('URL not in explicit HTTPS allowlist')
    if max_bytes < 1: raise ValueError('invalid byte limit')
    config.guard(max_bytes)
    root = config.root
    staging = root/'raw'/'.incoming'; staging.mkdir(parents=True, exist_ok=True)
    partial = staging/(uuid.uuid4().hex + '.partial')
    started = now()
    request = urllib.request.Request(url, headers={'User-Agent': 'cuneiform-research/0.2 checksum-verified-acquisition', 'Accept-Encoding': 'identity'})
    md5, sha = hashlib.md5(), hashlib.sha256(); total = 0
    tls, handlers = tls_context(chain_intermediate)
    try:
        with urllib.request.build_opener(NoRedirect(), *handlers).open(request, timeout=timeout) as response, partial.open('xb') as out:
            status = response.status
            headers = {k.lower(): v for k, v in response.headers.items() if k.lower() in KEPT_HEADERS}
            declared = response.headers.get('Content-Length')
            if declared and int(declared) > max_bytes: raise ValueError('response Content-Length exceeds limit')
            while block := response.read(min(1 << 20, max_bytes - total + 1)):
                total += len(block)
                if total > max_bytes: raise ValueError('stream exceeded byte limit; nothing retained')
                md5.update(block); sha.update(block); out.write(block)
        observed = {'bytes': total, 'md5': md5.hexdigest(), 'sha256': sha.hexdigest()}
        checks = {'md5': expect_md5, 'sha256': expect_sha256, 'bytes': expect_bytes}
        for key, want in checks.items():
            if want is not None and observed[key] != want: raise ValueError(f'checksum mismatch: {key} expected {want}, observed {observed[key]}')
        target = raw_path(root, observed['sha256'])
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            verify_raw(root, observed['sha256'], total); partial.unlink(); stored = 'already-present-verified'
        else:
            os.chmod(partial, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            os.link(partial, target); partial.unlink(); stored = 'new'
    except BaseException:
        if partial.exists(): partial.unlink()
        raise
    receipt = {'acquirer': ACQUIRER, 'label': label, 'url': url, 'http_status': status, 'response_headers': headers,
               'started_at': started, 'finished_at': now(), **observed,
               'expected': {k: v for k, v in checks.items() if v is not None},
               'checks': 'all supplied expectations matched' if any(v is not None for v in checks.values()) else 'no expectation supplied',
               'raw_object': f'raw/sha256/{observed["sha256"]}', 'storage': stored, 'tls': tls,
               'rights': rights or {'status': 'unknown', 'note': 'not inferred from public access'},
               'context': context or {}}
    return write_receipt(root, receipt)


def tls_context(chain_intermediate: Path | None):
    """Default verification. Optionally add ONE non-self-signed intermediate a server omits; trust must still end at a system root."""
    if chain_intermediate is None:
        return {'verification': 'default system trust'}, []
    pem = Path(chain_intermediate).read_bytes()
    if pem.count(b'BEGIN CERTIFICATE') != 1: raise ValueError('supply exactly one intermediate certificate')
    decoded = ssl._ssl._test_decode_cert(str(chain_intermediate))
    if decoded['subject'] == decoded['issuer']: raise ValueError('self-signed certificate refused; only a missing intermediate may be supplied')
    ctx = ssl.create_default_context()
    ctx.verify_flags &= ~getattr(ssl, 'VERIFY_X509_PARTIAL_CHAIN', 0)
    ctx.load_verify_locations(cafile=str(chain_intermediate))
    info = {'verification': 'enabled; hostname checked; chain must terminate at a system root (partial-chain disabled)',
            'supplemental_intermediate_sha256': hashlib.sha256(pem).hexdigest(),
            'supplemental_intermediate_subject': dict(x[0] for x in decoded['subject']).get('commonName'),
            'supplemental_intermediate_issuer': dict(x[0] for x in decoded['issuer']).get('commonName'),
            'reason': 'server presents leaf only; intermediate obtained from leaf AIA CA Issuers URL and verified against system roots'}
    return info, [urllib.request.HTTPSHandler(context=ctx)]
