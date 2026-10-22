"""SQLite persistence for workspaces.

A workspace holds imports (with their raw records), manual duplicate
decisions and filter settings. Every change bumps ``version`` so computed
results can be cached per version. The schema is deliberately small so it
can move to PostgreSQL later without touching the analysis code.
"""

from __future__ import annotations

import json
import secrets
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from bibliomap.schema import ParseWarning, Record, SourceFormat
from bibliomap.workspace.dedup import StoredRecord
from bibliomap.workspace.filters import FilterSpec

_SCHEMA = """
CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 0,
    filters TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    source_format TEXT NOT NULL,
    origin TEXT,
    record_count INTEGER NOT NULL,
    warnings TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    import_id INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS records_by_workspace ON records(workspace_id);
CREATE TABLE IF NOT EXISTS dedup_decisions (
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    record_a INTEGER NOT NULL,
    record_b INTEGER NOT NULL,
    same INTEGER NOT NULL,
    decided_at TEXT NOT NULL,
    PRIMARY KEY (workspace_id, record_a, record_b)
);
"""

# Default PRISMA source labels; RIS and BibTeX can come from any database, so
# those imports are labelled with their file name instead.
DEFAULT_LABELS = {
    SourceFormat.WOS: "Web of Science",
    SourceFormat.SCOPUS: "Scopus",
    SourceFormat.PUBMED: "PubMed",
    SourceFormat.LENS: "Lens.org",
    SourceFormat.OPENALEX: "OpenAlex",
}


class Workspace(BaseModel):
    id: str
    name: str
    created_at: str
    version: int
    filters: FilterSpec


class ImportInfo(BaseModel):
    id: int
    label: str
    source_format: SourceFormat
    origin: str | None
    record_count: int
    warnings: list[ParseWarning]
    created_at: str


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class WorkspaceNotFoundError(LookupError):
    pass


class WorkspaceStore:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript(_SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        # One short-lived connection per operation keeps request threads
        # independent; WAL lets readers proceed during writes.
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys = ON")
            db.execute("PRAGMA journal_mode = WAL")
            yield db
            db.commit()
        finally:
            db.close()

    @staticmethod
    def _bump(db: sqlite3.Connection, workspace_id: str) -> None:
        db.execute("UPDATE workspaces SET version = version + 1 WHERE id = ?", (workspace_id,))

    @staticmethod
    def _require(db: sqlite3.Connection, workspace_id: str) -> sqlite3.Row:
        row: sqlite3.Row | None = db.execute(
            "SELECT * FROM workspaces WHERE id = ?", (workspace_id,)
        ).fetchone()
        if row is None:
            raise WorkspaceNotFoundError(workspace_id)
        return row

    # --- workspaces -------------------------------------------------------

    def create_workspace(self, name: str) -> Workspace:
        # Unguessable id: until accounts exist, knowing the id is the access key.
        workspace_id = secrets.token_urlsafe(16)
        with self._connect() as db:
            db.execute(
                "INSERT INTO workspaces (id, name, created_at) VALUES (?, ?, ?)",
                (workspace_id, name, _now()),
            )
        return self.get_workspace(workspace_id)

    def get_workspace(self, workspace_id: str) -> Workspace:
        with self._connect() as db:
            row = self._require(db, workspace_id)
        return Workspace(
            id=row["id"],
            name=row["name"],
            created_at=row["created_at"],
            version=row["version"],
            filters=FilterSpec.model_validate_json(row["filters"]),
        )

    def set_filters(self, workspace_id: str, spec: FilterSpec) -> None:
        with self._connect() as db:
            self._require(db, workspace_id)
            db.execute(
                "UPDATE workspaces SET filters = ? WHERE id = ?",
                (spec.model_dump_json(), workspace_id),
            )
            self._bump(db, workspace_id)

    # --- imports ----------------------------------------------------------

    def add_import(
        self,
        workspace_id: str,
        *,
        source_format: SourceFormat,
        records: list[Record],
        warnings: list[ParseWarning],
        origin: str | None,
        label: str | None = None,
    ) -> ImportInfo:
        label = label or DEFAULT_LABELS.get(source_format) or origin or source_format.value
        with self._connect() as db:
            self._require(db, workspace_id)
            cursor = db.execute(
                "INSERT INTO imports (workspace_id, label, source_format, origin, record_count,"
                " warnings, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    workspace_id,
                    label,
                    source_format.value,
                    origin,
                    len(records),
                    json.dumps([w.model_dump() for w in warnings]),
                    _now(),
                ),
            )
            import_id = cursor.lastrowid
            db.executemany(
                "INSERT INTO records (workspace_id, import_id, data) VALUES (?, ?, ?)",
                [(workspace_id, import_id, r.model_dump_json()) for r in records],
            )
            self._bump(db, workspace_id)
        assert import_id is not None
        return self._get_import(workspace_id, import_id)

    def _get_import(self, workspace_id: str, import_id: int) -> ImportInfo:
        return next(i for i in self.list_imports(workspace_id) if i.id == import_id)

    def list_imports(self, workspace_id: str) -> list[ImportInfo]:
        with self._connect() as db:
            self._require(db, workspace_id)
            rows = db.execute(
                "SELECT * FROM imports WHERE workspace_id = ? ORDER BY id", (workspace_id,)
            ).fetchall()
        return [
            ImportInfo(
                id=row["id"],
                label=row["label"],
                source_format=SourceFormat(row["source_format"]),
                origin=row["origin"],
                record_count=row["record_count"],
                warnings=[ParseWarning(**w) for w in json.loads(row["warnings"])],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def rename_import(self, workspace_id: str, import_id: int, label: str) -> None:
        with self._connect() as db:
            self._require(db, workspace_id)
            db.execute(
                "UPDATE imports SET label = ? WHERE id = ? AND workspace_id = ?",
                (label, import_id, workspace_id),
            )
            self._bump(db, workspace_id)

    def delete_import(self, workspace_id: str, import_id: int) -> bool:
        with self._connect() as db:
            self._require(db, workspace_id)
            ids = [
                row[0]
                for row in db.execute(
                    "SELECT id FROM records WHERE import_id = ? AND workspace_id = ?",
                    (import_id, workspace_id),
                )
            ]
            deleted = db.execute(
                "DELETE FROM imports WHERE id = ? AND workspace_id = ?", (import_id, workspace_id)
            ).rowcount
            if ids:
                marks = ",".join("?" * len(ids))
                # Decisions about deleted records no longer mean anything.
                db.execute(
                    f"DELETE FROM dedup_decisions WHERE workspace_id = ?"
                    f" AND (record_a IN ({marks}) OR record_b IN ({marks}))",
                    (workspace_id, *ids, *ids),
                )
            self._bump(db, workspace_id)
        return deleted > 0

    def load_records(self, workspace_id: str) -> list[StoredRecord]:
        with self._connect() as db:
            self._require(db, workspace_id)
            rows = db.execute(
                "SELECT id, import_id, data FROM records WHERE workspace_id = ? ORDER BY id",
                (workspace_id,),
            ).fetchall()
        return [
            StoredRecord(
                id=row["id"],
                import_id=row["import_id"],
                record=Record.model_validate_json(row["data"]),
            )
            for row in rows
        ]

    # --- duplicate decisions ----------------------------------------------

    def set_decision(self, workspace_id: str, record_a: int, record_b: int, same: bool) -> None:
        a, b = sorted((record_a, record_b))
        with self._connect() as db:
            self._require(db, workspace_id)
            db.execute(
                "INSERT INTO dedup_decisions (workspace_id, record_a, record_b, same, decided_at)"
                " VALUES (?, ?, ?, ?, ?) ON CONFLICT(workspace_id, record_a, record_b)"
                " DO UPDATE SET same = excluded.same, decided_at = excluded.decided_at",
                (workspace_id, a, b, int(same), _now()),
            )
            self._bump(db, workspace_id)

    def delete_decision(self, workspace_id: str, record_a: int, record_b: int) -> None:
        a, b = sorted((record_a, record_b))
        with self._connect() as db:
            self._require(db, workspace_id)
            db.execute(
                "DELETE FROM dedup_decisions WHERE workspace_id = ? AND record_a = ?"
                " AND record_b = ?",
                (workspace_id, a, b),
            )
            self._bump(db, workspace_id)

    def decisions(self, workspace_id: str) -> dict[tuple[int, int], bool]:
        with self._connect() as db:
            self._require(db, workspace_id)
            rows = db.execute(
                "SELECT record_a, record_b, same FROM dedup_decisions WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchall()
        return {(row[0], row[1]): bool(row[2]) for row in rows}
