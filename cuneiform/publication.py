"""Durable, fail-closed publication ledger for immutable directories (snapshots, cohorts).

Protocol (ledger format 2), all ledger appends under an exclusive flock on <folder>/.publication.lock:

  1. The writer builds a complete stage directory, fsyncs every file and directory, and makes it read-only.
  2. ``reserve`` is appended and fsynced (F_FULLFSYNC where available). From now on the ID is never free for
     different bytes: the reservation binds manifest_sha256 and the manifest file's own SHA-256.
  3. The stage is renamed into place (atomic on one filesystem) and the parent directory is fsynced.
  4. ``commit`` is appended and fsynced. Only now do ledger-checked readers serve the ID.

A crash between 2 and 4 leaves a reservation without a commit. Readers refuse it and writers refuse to rebuild it.
Only an explicit ``recover`` clears it, and recovery never publishes bytes other than the reserved ones:

  * directory present and matching the reservation  -> ``commit`` (recovered)
  * directory absent, reserved stage still present  -> ``complete`` (rename the reserved stage, then commit)
                                                       or ``discard`` (``abort``: the ID was never visible)
  * directory absent and stage absent               -> ``abandon`` only: the ID may have been visible and then
                                                       deleted, so it is burned permanently

``abort`` is also written by a writer that observed its own rename fail with the stage still in place.
``adopt`` explicitly ledgers an existing directory that has no entry (publication time and history unknown).
Legacy records (no ``event`` key, written before format 2 or by the 2026-11-03 backfill) mean "published".

Limits, stated plainly: this is an application-level protocol for cooperating writers on one host. Same-owner OS
access (chmod, editing or deleting the ledger, renames) and root can defeat it; read-only modes and the ledger are
not tamper-proof. The ledger records what writers observed; it is not a signature.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import fcntl
import hashlib
import json
import os
import socket

LEDGER = '.publication-ledger.jsonl'
LOCK = '.publication.lock'
FORMAT = 2
# Fault injection for crash tests only: CUNEIFORM_TEST_KILL_AT=<point> hard-exits the process at that point
# (no except/finally handlers run). FAULT_HOOK lets in-process tests raise at a point instead.
KILL_ENV = 'CUNEIFORM_TEST_KILL_AT'
PAUSE_ENV = 'CUNEIFORM_TEST_PAUSE_AT'   # '<point>:<seconds>': sleep there (concurrency tests hold a writer in a window)
FAULT_HOOK = None


def fault(point: str) -> None:
    if os.environ.get(KILL_ENV) == point:
        os._exit(137)
    pause = os.environ.get(PAUSE_ENV, '')
    if pause.partition(':')[0] == point:
        import time
        time.sleep(float(pause.partition(':')[2] or 0))
    if FAULT_HOOK is not None:
        FAULT_HOOK(point)


class PublicationError(ValueError):
    """A publication-state refusal. ``state`` is the ledger state that caused it."""
    def __init__(self, message: str, state: str = 'error'):
        super().__init__(message)
        self.state = state


class LedgerCorrupt(PublicationError):
    def __init__(self, message: str):
        super().__init__(message, 'ledger-corrupt')


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def full_fsync(fd: int) -> None:
    """fsync, plus F_FULLFSYNC on macOS so the drive cache is flushed (also a barrier for earlier fsyncs)."""
    os.fsync(fd)
    if hasattr(fcntl, 'F_FULLFSYNC'):
        try: fcntl.fcntl(fd, fcntl.F_FULLFSYNC)
        except OSError: pass


def fsync_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try: os.fsync(fd)
    except OSError: pass
    finally: os.close(fd)


def seal(stage: Path) -> None:
    """Make a complete stage read-only (files 0444, dirs 0555), then fsync every file and directory, so the contents
    and the final modes are both flushed before the reservation (whose F_FULLFSYNC is the barrier on macOS)."""
    paths = sorted(stage.rglob('*'), reverse=True)   # deepest first: children before their directory
    for p in paths:
        if p.is_symlink(): raise PublicationError(f'stage {stage} contains a symlink ({p.relative_to(stage)}); refusing to publish it', 'symlinked-entry')
    for p in paths:
        if p.is_file():
            os.chmod(p, 0o444)
            with p.open('rb') as handle: os.fsync(handle.fileno())
    for p in [*paths, stage]:
        if p.is_dir():
            os.chmod(p, 0o555); fsync_dir(p)


def is_store_folder(folder) -> bool:
    """A folder holding a publication ledger or lock is a store: every directory directly inside it is ledger-checked."""
    return os.path.exists(os.path.join(folder, LEDGER)) or os.path.exists(os.path.join(folder, LOCK))


def locate_entry(path) -> tuple[Path, str] | None:
    """(store folder, entry name) for a directory read, or None for a copy outside any store.

    Store membership is decided from the lexical parent AND the resolved parent, so a store entry can never become a
    standalone copy by being a symlink, and a path outside a store that resolves into one is still ledger-checked.
    A lexical store entry must be a real directory that resolves to <store>/<name>: a symlinked entry, or a path that
    escapes through a symlinked component or '..', is refused."""
    lex = Path(os.path.abspath(path)); real = Path(os.path.realpath(path))
    if is_store_folder(lex.parent):
        folder = Path(os.path.realpath(lex.parent))
        if os.path.islink(lex) or os.path.islink(path) or real != folder/lex.name:
            raise PublicationError(f'store entry {lex} is a symlink or resolves outside its store ({real}); store entries must be real '
                                   'directories inside the store. Refusing. Move the link aside; to use a relocated copy, read it at its own '
                                   'path (standalone, not ledger-checked) or adopt a real copy into a store explicitly.', 'symlinked-entry')
        return folder, lex.name
    if is_store_folder(real.parent):
        return real.parent, real.name
    return None


def assert_no_symlinks(entry: Path, names) -> None:
    """Refuse a store entry whose payload paths (or any directory on the way to them) are symlinks."""
    for name in names:
        p = entry
        for part in Path(name).parts:
            p = p/part
            if p.is_symlink():
                raise PublicationError(f'store entry {entry} has a symlink at {p.relative_to(entry)}; store payloads must be real files. Refusing.', 'symlinked-entry')


def build_lock(folder: Path, ident: str):
    """Per-ID exclusive build lock (<folder>/.locks/<id>.lock). Writers of one ID build it once; the loser reuses the
    result. Recovery takes it too, so a writer never sees another live process's reserve->commit window as an
    interruption. Lock order everywhere: build lock, then the ledger lock."""
    @contextmanager
    def held():
        locks = Path(folder)/'.locks'; locks.mkdir(parents=True, exist_ok=True)
        with (locks/(ident.replace(':', '-') + '.lock')).open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try: yield
            finally: fcntl.flock(handle, fcntl.LOCK_UN)
    return held()


def missing_entry(ledger: 'Ledger', ident: str, dest: Path) -> 'PublicationError':
    """Typed refusal for a store entry whose directory (or manifest) is absent, naming its ledger state."""
    try: st = ledger.status(ident)
    except PublicationError as exc: return exc
    if st.state in ('published', 'reserved', 'abandoned', 'conflict'):
        err = refusal(st, dest, ledger.label)
        if st.state == 'reserved':
            err.add_note(f'{dest} is absent; see `{recover_hint(ledger, ident)}`')
        return err
    return PublicationError(f'{ledger.label} {ident} is not in the store {ledger.folder} (ledger state {st.state}; no directory {dest.name})', 'not-found')


def recover_hint(ledger: 'Ledger', ident: str, action: str = '') -> str:
    store = '' if ledger.label == 'snapshot' else f' --store {ledger.label}s'
    return f'python -m cuneiform publication-recover {ident}{store}' + (f' --action {action} --reason ...' if action else '')


def file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        while block := handle.read(1 << 20): h.update(block)
    return h.hexdigest()


@dataclass
class Status:
    sid: str
    state: str = 'unpublished'   # unpublished | reserved | published | aborted | abandoned | conflict
    kind: str | None = None      # published only: ledgered | legacy | legacy-backfilled | recovered | adopted
    manifest_sha256: str | None = None
    manifest_file_sha256: str | None = None
    published_at: str | None = None
    stage: str | None = None
    reason: str | None = None
    entries: list = field(default_factory=list)


class Ledger:
    def __init__(self, folder: Path, key: str = 'snapshot_id', label: str = 'snapshot', dirname=None):
        self.folder = Path(folder); self.key = key; self.label = label
        self.dirname = dirname or (lambda ident: ident)   # ID -> directory name inside the folder
        self.path = self.folder/LEDGER

    def exists(self) -> bool:
        return self.path.exists()

    # ---- reading ----
    def scan(self) -> tuple[list[dict], dict | None]:
        """Parse the ledger. Returns (entries, unterminated_tail). Raises LedgerCorrupt on an unacknowledged bad line.

        An unterminated final segment is either a concurrent append in progress or a torn write. Readers ignore it
        when it does not parse (a torn reserve means the rename never happened; a torn commit leaves a reservation
        that readers refuse). Writers refuse to append after it until ``repair_tail`` acknowledges it.
        """
        if not self.path.exists(): return [], None
        data = self.path.read_bytes()
        entries, bad, tail, offset = [], [], None, 0
        segments = data.split(b'\n')
        for i, seg in enumerate(segments):
            terminated = i < len(segments) - 1
            start = offset; offset += len(seg) + (1 if terminated else 0)
            if not seg.strip(): continue
            try:
                value = json.loads(seg)
                if not isinstance(value, dict): raise ValueError('not an object')
            except ValueError:
                value = None
            if not terminated:
                tail = {'offset': start, 'length': len(seg), 'sha256': hashlib.sha256(seg).hexdigest(), 'parsed': value is not None,
                        'fragment': seg[:512].decode('utf-8', 'replace')}
                if value is not None: entries.append(dict(value, _offset=start, _unterminated=True))
                continue
            if value is None: bad.append({'offset': start, 'sha256': hashlib.sha256(seg).hexdigest()}); continue
            entries.append(dict(value, _offset=start))
        acknowledged = {(e.get('torn_offset'), e.get('torn_sha256')) for e in entries if e.get('event') == 'torn-tail-acknowledged'}
        unacknowledged = [b for b in bad if (b['offset'], b['sha256']) not in acknowledged]
        if unacknowledged:
            raise LedgerCorrupt(f'publication ledger {self.path} has unparseable record(s) at byte offset(s) '
                                f'{[b["offset"] for b in unacknowledged]}; refusing all {self.label} publication decisions. '
                                'Inspect the file; nothing was changed.')
        return entries, tail

    def status(self, sid: str, entries: list[dict] | None = None) -> Status:
        if entries is None: entries, _ = self.scan()
        st = Status(sid)
        for e in entries:
            if e.get(self.key) != sid: continue
            st.entries.append({k: v for k, v in e.items() if not k.startswith('_')})
            ev = e.get('event')
            if st.state == 'conflict': continue
            if ev is None:   # legacy record: published
                if st.state != 'unpublished':
                    st.state, st.reason = 'conflict', 'more than one legacy publication record for this ID'
                    continue
                st.state = 'published'; st.kind = 'legacy-backfilled' if e.get('backfilled') else 'legacy'
                st.manifest_sha256 = e.get('manifest_sha256'); st.published_at = e.get('published_at')
            elif ev == 'reserve':
                if st.state not in ('unpublished', 'aborted'):
                    st.state, st.reason = 'conflict', f'reserve recorded while state was {st.state}'; continue
                st.state = 'reserved'; st.manifest_sha256 = e.get('manifest_sha256'); st.manifest_file_sha256 = e.get('manifest_file_sha256')
                st.stage = e.get('stage'); st.kind = None
            elif ev == 'commit':
                if st.state != 'reserved' or e.get('manifest_sha256') != st.manifest_sha256:
                    st.state, st.reason = 'conflict', 'commit without a matching reservation'; continue
                st.state = 'published'; st.kind = 'recovered' if e.get('recovered') else 'ledgered'; st.published_at = e.get('published_at')
            elif ev in ('abort', 'abandon'):
                if st.state != 'reserved':
                    st.state, st.reason = 'conflict', f'{ev} without an open reservation'; continue
                st.state = 'aborted' if ev == 'abort' else 'abandoned'
            elif ev == 'adopt':
                if st.state != 'unpublished':
                    st.state, st.reason = 'conflict', f'adopt recorded while state was {st.state}'; continue
                st.state = 'published'; st.kind = 'adopted'; st.manifest_sha256 = e.get('manifest_sha256')
                st.manifest_file_sha256 = e.get('manifest_file_sha256'); st.published_at = None
            else:
                st.state, st.reason = 'conflict', f'unknown ledger event {ev!r}'
        return st

    def ids(self) -> list[str]:
        entries, _ = self.scan()
        return sorted({e[self.key] for e in entries if self.key in e})

    # ---- writing ----
    @contextmanager
    def locked(self):
        self.folder.mkdir(parents=True, exist_ok=True)
        with (self.folder/LOCK).open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try: yield self
            finally: fcntl.flock(lock, fcntl.LOCK_UN)

    def writer_scan(self) -> list[dict]:
        """Call only while locked. No concurrent append can exist, so an unterminated tail is a torn write."""
        entries, tail = self.scan()
        if tail is not None:
            raise PublicationError(f'publication ledger {self.path} ends with a torn record at byte {tail["offset"]} '
                                   f'(sha256 {tail["sha256"][:16]}…, parsed={tail["parsed"]}). Refusing to append. Inspect it, then run '
                                   '`python -m cuneiform publication-repair-ledger --reason ...` to acknowledge it append-only.', 'ledger-torn')
        return entries

    def append(self, record: dict) -> dict:
        """Call only while locked, after writer_scan()."""
        record = dict({'ledger_format': FORMAT}, **record)
        line = (json.dumps(record, ensure_ascii=False, sort_keys=True) + '\n').encode()
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            view = memoryview(line)
            while view: view = view[os.write(fd, view):]
            full_fsync(fd)
        finally:
            os.close(fd)
        fsync_dir(self.folder)
        return record

    def repair_tail(self, reason: str) -> dict:
        """Append-only acknowledgement of a torn final record. The torn bytes stay in the file as evidence."""
        with self.locked():
            entries, tail = self.scan()
            if tail is None: raise PublicationError('ledger has no torn final record; nothing to acknowledge', 'no-op')
            fd = os.open(self.path, os.O_WRONLY | os.O_APPEND)
            try: os.write(fd, b'\n'); full_fsync(fd)
            finally: os.close(fd)
            return self.append({'event': 'torn-tail-acknowledged', 'torn_offset': tail['offset'], 'torn_length': tail['length'],
                                'torn_sha256': tail['sha256'], 'torn_parsed_as_record': tail['parsed'], 'torn_fragment': tail['fragment'],
                                'reason': reason, 'acknowledged_at': now(), 'writer': writer()})


def writer() -> dict:
    return {'pid': os.getpid(), 'host': socket.gethostname()}


def refusal(st: Status, dest: Path, label: str = 'snapshot') -> PublicationError:
    sid = st.sid
    if st.state == 'published':
        return PublicationError(f'{sid} was already published (ledger, manifest_sha256 {st.manifest_sha256}) but its directory is missing '
                                f'from {dest.parent}. Restore the exact published bytes from a copy you trust (a restored copy is served '
                                'only if its manifest matches the ledger), or leave it missing. Never rebuild under the same ID.', 'published-missing')
    if st.state == 'reserved':
        store = '' if label == 'snapshot' else f' --store {label}s'
        return PublicationError(f'publication of {label} {sid} was reserved but never committed (interrupted: no live writer holds its build lock). '
                                f'The ID cannot be rebuilt or read. Inspect with `python -m cuneiform publication-status {sid}{store}` and '
                                f'resolve with `python -m cuneiform publication-recover {sid}{store} --action ... --reason ...`.', 'reserved')
    if st.state == 'abandoned':
        return PublicationError(f'{sid} was reserved and its bytes were lost before commit; the ID is burned permanently. '
                                'A rebuild needs a new identity (revise the contract or inputs).', 'abandoned')
    if st.state == 'conflict':
        return PublicationError(f'publication ledger conflict for {sid}: {st.reason}. Refusing; inspect the ledger.', 'conflict')
    return PublicationError(f'{label} {sid} is not publishable in state {st.state}', st.state)


def publish_dir(ledger: Ledger, stage: Path, dest: Path, sid: str, manifest_sha256: str, manifest_file_sha256: str, matches) -> str:
    """Reserve, rename and commit one sealed stage. Returns 'published', or 'raced' when another writer already published
    matching bytes (``matches(dest)`` returns True); the caller then discards its stage."""
    with ledger.locked():
        st = ledger.status(sid, ledger.writer_scan())
        if st.state == 'published':
            if os.path.lexists(dest) and matches(dest): return 'raced'
            if os.path.lexists(dest):
                raise PublicationError(f'{sid} is published but the directory in the store does not match the ledger; refusing', 'ledger-mismatch')
            raise refusal(st, dest, ledger.label)
        if st.state not in ('unpublished', 'aborted'): raise refusal(st, dest, ledger.label)
        if os.path.lexists(dest):
            raise PublicationError(f'{dest} exists but {sid} has no publication record. Refusing to replace or reuse it. If it is the '
                                   f'intended bytes, run `python -m cuneiform publication-adopt {sid} --reason ...`; otherwise move it aside.', 'unledgered')
        fault('before-reserve')
        ledger.append({'event': 'reserve', ledger.key: sid, 'manifest_sha256': manifest_sha256, 'manifest_file_sha256': manifest_file_sha256,
                       'stage': stage.name, 'reserved_at': now(), 'writer': writer()})
        fault('after-reserve')
        try:
            fault('rename')
            os.rename(stage, dest)
        except BaseException as exc:
            # POSIX rename is atomic: with the stage still present and no destination, nothing became visible.
            if stage.exists() and not os.path.lexists(dest):
                try:
                    ledger.append({'event': 'abort', ledger.key: sid, 'manifest_sha256': manifest_sha256, 'stage': stage.name,
                                   'reason': f'{type(exc).__name__}: {exc}'[:500], 'aborted_at': now(), 'writer': writer()})
                except BaseException as ledger_exc:
                    exc.add_note(f'could not record abort for {sid} ({ledger_exc!r}); the reservation stays open and the stage {stage} '
                                 f'is kept for `python -m cuneiform publication-recover {sid}`')
            raise
        fsync_dir(dest.parent)
        fault('after-rename')
        try:
            ledger.append({'event': 'commit', ledger.key: sid, 'manifest_sha256': manifest_sha256, 'manifest_file_sha256': manifest_file_sha256,
                           'published_at': now(), 'writer': writer()})
        except BaseException as exc:
            exc.add_note(f'{dest} is in place but its publication was not committed; ledger-checked readers refuse it. '
                         f'Run `python -m cuneiform publication-recover {sid} --action commit` after checking it.')
            raise
        fault('after-commit')
        return 'published'


def inspect_reservation(ledger: Ledger, sid: str, folder: Path, check) -> dict:
    """What recovery could do for an open reservation. ``check(path, sid)`` content-verifies a directory and returns
    its manifest (or raises). Read-only."""
    st = ledger.status(sid)
    out = {'id': sid, 'state': st.state, 'reason': st.reason, 'reserved_manifest_sha256': st.manifest_sha256, 'entries': st.entries}
    if st.state != 'reserved':
        out['actions'] = []
        return out
    dest = folder/ledger.dirname(sid)
    stage = folder/st.stage if st.stage else None
    def observe(path):
        if path is None or not os.path.lexists(path): return {'present': False}
        if path.is_symlink() or any(q.is_symlink() for q in path.rglob('*')):
            return {'present': True, 'symlink': True, 'content_verified': False, 'matches_reservation': False,
                    'error': f'{path.name} is or contains a symlink; only a real directory of real files can be recovered'}
        try:
            m = check(path, sid)
            fsha = file_digest(path/'manifest.json') if (path/'manifest.json').exists() else None
            ok = m.get('manifest_sha256') == st.manifest_sha256 and (st.manifest_file_sha256 is None or fsha == st.manifest_file_sha256)
            return {'present': True, 'content_verified': True, 'manifest_sha256': m.get('manifest_sha256'), 'manifest_file_sha256': fsha, 'matches_reservation': ok}
        except (ValueError, OSError, KeyError) as exc:
            return {'present': True, 'content_verified': False, 'error': str(exc), 'matches_reservation': False}
    out['directory'] = dict(observe(dest), path=str(dest))
    out['stage'] = dict(observe(stage), path=str(stage) if stage else None)
    if out['directory']['present']:
        out['actions'] = ['commit'] if out['directory']['matches_reservation'] else []
        if not out['actions']:
            out['note'] = 'directory differs from the reservation; move it aside before recovery. Different bytes are never committed.'
    elif out['stage']['present'] and out['stage']['matches_reservation']:
        out['actions'] = ['complete', 'discard']
    else:
        out['actions'] = ['abandon']
        out['note'] = 'neither the directory nor the reserved stage survives; the ID may have been visible, so it can only be burned.'
    return out


def recover(ledger: Ledger, sid: str, folder: Path, action: str, check, reason: str) -> dict:
    if action not in ('commit', 'complete', 'discard', 'abandon'): raise PublicationError('unknown recovery action', 'error')
    with build_lock(folder, sid), ledger.locked():
        ledger.writer_scan()
        # Holding the build and ledger locks: no cooperating writer is between reserve and commit, so an open reservation
        # is an interruption.
        plan = inspect_reservation(ledger, sid, folder, check)
        if plan['state'] != 'reserved':
            raise PublicationError(f'{sid} has no open reservation (state {plan["state"]}); nothing to recover', plan['state'])
        if action not in plan['actions']:
            raise PublicationError(f'recovery action {action!r} is not safe for {sid}; allowed: {plan["actions"] or "none"}. {plan.get("note", "")}', 'refused')
        st = ledger.status(sid)
        observed = {'directory': plan['directory'], 'stage': plan['stage']}
        base = {ledger.key: sid, 'manifest_sha256': st.manifest_sha256, 'recovered': True, 'reason': reason, 'observed': observed, 'writer': writer()}
        if action == 'complete':
            os.rename(folder/st.stage, folder/ledger.dirname(sid)); fsync_dir(folder)
        if action in ('commit', 'complete'):
            record = ledger.append(dict(base, event='commit', manifest_file_sha256=st.manifest_file_sha256, published_at=now(), recovery_action=action))
        elif action == 'discard':
            record = ledger.append(dict(base, event='abort', aborted_at=now(), recovery_action=action))
            discard_stage(folder/st.stage)
        else:
            record = ledger.append(dict(base, event='abandon', abandoned_at=now(), recovery_action=action))
        return {'id': sid, 'action': action, 'ledger_record': record, 'state_after': ledger.status(sid).state}


def adopt(ledger: Ledger, sid: str, folder: Path, check, reason: str) -> dict:
    dest = folder/ledger.dirname(sid)
    with ledger.locked():
        st = ledger.status(sid, ledger.writer_scan())
        if st.state != 'unpublished': raise PublicationError(f'{sid} already has ledger state {st.state}; adoption is only for unrecorded directories', st.state)
        if dest.is_symlink(): raise PublicationError(f'{dest} is a symlink; only a real directory inside the store can be adopted', 'symlinked-entry')
        if not dest.is_dir(): raise PublicationError(f'{dest} does not exist; nothing to adopt', 'missing')
        if any(q.is_symlink() for q in dest.rglob('*')): raise PublicationError(f'{dest} contains symlinks; only real files can be adopted', 'symlinked-entry')
        manifest = check(dest, sid)
        return ledger.append({'event': 'adopt', ledger.key: sid, 'manifest_sha256': manifest['manifest_sha256'],
                              'manifest_file_sha256': file_digest(dest/'manifest.json'), 'adopted_at': now(), 'reason': reason,
                              'note': 'existing directory ledgered explicitly; its publication time and any earlier history are unknown',
                              'writer': writer()})


def discard_stage(stage: Path) -> None:
    """Remove one owned stage directory. Only directories get u+rwx back (unlinking needs it); file modes are untouched."""
    import shutil
    if not stage.exists(): return
    for top, dirs, _ in os.walk(stage):
        os.chmod(top, 0o700)
        for d in dirs:
            p = Path(top)/d
            if not p.is_symlink(): os.chmod(p, 0o700)
    shutil.rmtree(stage)


def check_published(ledger: Ledger, sid: str, manifest: dict, manifest_path: Path) -> dict:
    """Reader check: the served manifest must be the one the ledger published. Returns a publication label."""
    entries, tail = ledger.scan()
    st = ledger.status(sid, entries)
    if st.state != 'published':
        store = '' if ledger.label == 'snapshot' else f' --store {ledger.label}s'
        if st.state == 'unpublished':
            raise PublicationError(f'{ledger.label} {sid} is in a ledgered store ({ledger.folder}) but has no publication record; refusing to serve it. '
                                   f'Adopt it explicitly (`python -m cuneiform publication-adopt {sid}{store} --reason ...`) or move it out of the store.', 'not-in-ledger')
        if st.state == 'reserved':
            raise PublicationError(f'{ledger.label} {sid} publication is not committed (in progress or interrupted); refusing to serve it. '
                                   f'Inspect with `python -m cuneiform publication-status {sid}{store}`; resolve an interruption with '
                                   f'`python -m cuneiform publication-recover {sid}{store} --action ... --reason ...`.', 'reserved')
        raise refusal(st, manifest_path.parent, ledger.label)
    if manifest.get('manifest_sha256') != st.manifest_sha256:
        raise PublicationError(f'{sid}: served manifest_sha256 {manifest.get("manifest_sha256")} differs from the published '
                               f'{st.manifest_sha256}; this is not the published snapshot. Refusing it (restore the exact published bytes or move it aside).',
                               'ledger-mismatch')
    file_sha = None
    if st.manifest_file_sha256 is not None:
        file_sha = file_digest(manifest_path)
        if file_sha != st.manifest_file_sha256:
            raise PublicationError(f'{sid}: manifest.json bytes differ from the published file (sha256 {file_sha} vs {st.manifest_file_sha256}); refusing.',
                                   'ledger-mismatch')
    label = {'ledgered': 'ledgered', 'recovered': 'ledgered-recovered', 'adopted': 'adopted',
             'legacy': 'ledgered-legacy', 'legacy-backfilled': 'ledgered-legacy-backfilled'}[st.kind]
    out = {'status': label, 'ledger_checked': True, 'ledger': str(ledger.path), 'manifest_sha256': st.manifest_sha256,
           'manifest_file_bytes_bound': st.manifest_file_sha256 is not None, 'published_at': st.published_at,
           'binding': 'served manifest_sha256 (which covers every payload file hash) equals the ledger record' +
                      ('; manifest.json bytes equal the reserved file' if st.manifest_file_sha256 else '; manifest.json file bytes are not bound for this entry (canonical digest only)')}
    if st.kind == 'legacy-backfilled':
        first = st.entries[0]
        out['published_at_semantics'] = 'manifest build time copied by the 2026-11-03 backfill, not an observed publication time'
        out['backfilled_at'] = first.get('backfilled_at')
        if first.get('incident'): out['incident'] = first['incident']
    if st.kind == 'adopted':
        out['published_at_semantics'] = 'unknown; adopted explicitly from an existing directory'
    if tail is not None:
        out['ledger_tail'] = 'unterminated final record (append in progress or torn write); ignored for this read'
    return out
