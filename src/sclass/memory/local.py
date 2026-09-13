"""
S-Class Memory: Zero-Infrastructure Local SQLite Memory Provider.
"""

from __future__ import annotations
import os
import json
import sqlite3
from typing import List, Optional

from sclass.memory.provider import MemoryProvider, MemoryItem
from sclass.storage.paths import WorkspacePaths


class LocalMemoryProvider(MemoryProvider):
    """Local SQLite-backed candidate memory provider in .sclass/cache/memory.db."""

    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir
        self.paths = WorkspacePaths(workspace_dir)
        os.makedirs(self.paths.cache_dir, exist_ok=True)
        self.db_path = os.path.join(self.paths.cache_dir, "memory.db")
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                key TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                category TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)
            conn.commit()

    def remember(self, item: MemoryItem) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
            INSERT INTO memories (key, content, category, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                content = excluded.content,
                category = excluded.category,
                metadata_json = excluded.metadata_json,
                created_at = excluded.created_at;
            """, (item.key, item.content, item.category, json.dumps(item.metadata), item.created_at))
            conn.commit()

    def retrieve(self, query: str, limit: int = 5) -> List[MemoryItem]:
        q_norm = f"%{query.lower()}%"
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
            SELECT * FROM memories
            WHERE LOWER(content) LIKE ? OR LOWER(category) LIKE ? OR LOWER(key) LIKE ?
            ORDER BY created_at DESC
            LIMIT ?;
            """, (q_norm, q_norm, q_norm, limit)).fetchall()

            return [
                MemoryItem(
                    key=r["key"],
                    content=r["content"],
                    category=r["category"],
                    metadata=json.loads(r["metadata_json"]),
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    def forget(self, key: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM memories WHERE key = ?;", (key,))
            conn.commit()
            return cur.rowcount > 0
