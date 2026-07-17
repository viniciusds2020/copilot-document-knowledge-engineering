import json
import sqlite3
from pathlib import Path

from .models import Document


class Repository:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._init()

    def connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init(self):
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY, sha256 TEXT UNIQUE, payload TEXT NOT NULL)""")

    def save(self, document: Document):
        with self.connect() as db:
            db.execute(
                "INSERT INTO documents(id, sha256, payload) VALUES (?, ?, ?)",
                (document.id, document.sha256, document.model_dump_json()),
            )

    def list(self) -> list[Document]:
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM documents ORDER BY rowid DESC").fetchall()
        return [Document.model_validate(json.loads(row["payload"])) for row in rows]

    def get(self, document_id: str) -> Document | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT payload FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
        return Document.model_validate(json.loads(row["payload"])) if row else None

    def update(self, document: Document):
        with self.connect() as db:
            db.execute(
                "UPDATE documents SET payload = ? WHERE id = ?",
                (document.model_dump_json(), document.id),
            )
