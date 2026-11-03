"""Exact bulk loading. Python row inserts cost ~0.2 ms/row in DuckDB 1.4; corpus imports spool JSONL instead.

Spool files live only inside an import-owned staging directory and are deleted before payload hashing.
Without a spool directory (in-memory demos/tests) rows use parameterized executemany.
"""
from pathlib import Path
import json
import uuid

DELIMITER = '\x01'  # JSON escapes every control character, so one JSON array is one CSV field.
CASTS = {'VARCHAR': '{}', 'INTEGER': '({})::INTEGER', 'BIGINT': '({})::BIGINT', 'JSON': '({})::JSON', 'BOOLEAN': '({})::BOOLEAN', 'DOUBLE': '({})::DOUBLE'}


def columns(db, table: str) -> list[tuple[str, str]]:
    found = db.execute("SELECT column_name,data_type FROM information_schema.columns WHERE table_name=? AND table_schema='main' ORDER BY ordinal_position", [table]).fetchall()
    if not found: raise ValueError('unknown table: ' + table)
    return found


class Spool:
    """Append rows for one table to a JSONL file, then load once. Bounded Python memory."""
    def __init__(self, db, table: str, directory: Path | None, ignore_conflicts: bool=False, cols: list[tuple[str, str]] | None=None):
        self.db, self.table, self.ignore = db, table, ignore_conflicts
        self.cols = cols if cols is not None else columns(db, table)
        self.count = 0
        self.rows: list[tuple] = []
        self.path = None if directory is None else Path(directory)/f'{table}-{uuid.uuid4().hex}.jsonl'
        self.handle = None
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.handle = self.path.open('x', encoding='utf-8')

    @classmethod
    def detached(cls, table: str, cols: list[tuple[str, str]], directory: Path | None) -> 'Spool':
        """Stage rows for a table that will be (re)created later in a transaction; call attach(db) before load()."""
        return cls(None, table, directory, cols=cols)

    def attach(self, db) -> 'Spool':
        self.db = db
        return self

    def append(self, row: tuple) -> None:
        if len(row) != len(self.cols): raise ValueError(f'{self.table}: expected {len(self.cols)} values')
        self.count += 1
        if self.handle is None: self.rows.append(row)
        else: self.handle.write(json.dumps(list(row), ensure_ascii=False) + '\n')

    def discard(self) -> None:
        if self.handle is not None:
            self.handle.close(); self.handle = None
        if self.path is not None and self.path.exists(): self.path.unlink()
        self.rows = []

    def load(self) -> int:
        verb = 'INSERT OR IGNORE INTO' if self.ignore else 'INSERT INTO'
        try:
            if self.handle is None:
                if self.rows:
                    self.db.executemany(f'{verb} {self.table} VALUES ({",".join("?" for _ in self.cols)})', self.rows)
                return self.count
            self.handle.close(); self.handle = None
            if self.count:
                exprs = []
                for i, (name, kind) in enumerate(self.cols):
                    if kind not in CASTS: raise ValueError(f'unsupported bulk column type {kind}')
                    exprs.append(CASTS[kind].format(f"j->>{i}") + f' AS "{name}"')
                literal = str(self.path).replace("'", "''")
                self.db.execute(f"{verb} {self.table} SELECT {','.join(exprs)} FROM (SELECT column0::JSON j FROM read_csv('{literal}', columns={{'column0':'VARCHAR'}}, delim='{DELIMITER}', quote='', escape='', header=false, auto_detect=false, max_line_size=8388608, buffer_size=33554432))")
            return self.count
        finally:
            self.discard()


def insert_rows(db, table: str, rows, directory: Path | None=None, ignore_conflicts: bool=False) -> int:
    spool = Spool(db, table, directory, ignore_conflicts)
    try:
        for row in rows: spool.append(tuple(row))
    except BaseException:
        spool.discard(); raise
    return spool.load()
