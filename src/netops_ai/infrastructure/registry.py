"""SQLite document catalog; vector contents remain in Qdrant."""

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from netops_ai.domain.retrieval import IndexedDocument, RetrievalError


class DocumentRegistry:
    def __init__(self, path: Path, fingerprint: str) -> None:
        self.path = path
        with closing(self._connect()) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)")
            db.execute("""CREATE TABLE IF NOT EXISTS documents (
                document_id TEXT PRIMARY KEY, filename TEXT NOT NULL,
                page_count INTEGER NOT NULL, chunk_count INTEGER NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending', 'indexed', 'failed')),
                created_at TEXT NOT NULL
            )""")
            existing = db.execute("SELECT value FROM config WHERE key='pipeline'").fetchone()
            if existing and existing[0] != fingerprint:
                raise RetrievalError(
                    "incompatible_index",
                    "A configuração difere da base existente. Restaure a configuração "
                    "anterior ou escolha outro NETOPS_DATA_DIR para uma nova base.",
                    409,
                )
            db.execute("INSERT OR IGNORE INTO config VALUES ('pipeline', ?)", (fingerprint,))

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def get(self, document_id: str) -> IndexedDocument | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM documents WHERE document_id=?", (document_id,)
            ).fetchone()
        return IndexedDocument(**dict(row)) if row else None

    def list_documents(self) -> list[IndexedDocument]:
        with closing(self._connect()) as db:
            rows = db.execute("SELECT * FROM documents ORDER BY created_at, document_id").fetchall()
        return [IndexedDocument(**dict(row)) for row in rows]

    def start(self, document_id: str, filename: str, pages: int, chunks: int) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                """INSERT INTO documents VALUES (?, ?, ?, ?, 'pending', ?)
                ON CONFLICT(document_id) DO UPDATE SET
                filename=excluded.filename, page_count=excluded.page_count,
                chunk_count=excluded.chunk_count, status='pending'
            """,
                (document_id, filename, pages, chunks, datetime.now(UTC).isoformat()),
            )

    def set_status(self, document_id: str, status: str) -> None:
        with closing(self._connect()) as db, db:
            db.execute("UPDATE documents SET status=? WHERE document_id=?", (status, document_id))
