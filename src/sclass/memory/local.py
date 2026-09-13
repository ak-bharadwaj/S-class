"""
S-Class Memory: Zero-Infrastructure Local SQLite Memory Provider.
Implements remember, recall, search, forget, and retrieve, separating CONTEXT/HYPOTHESIS from VERIFIED_FACT.
"""

from __future__ import annotations
import os
import json
import sqlite3
from typing import List, Optional

from sclass.memory.provider import MemoryProvider, MemoryItem, MemoryType
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
                memory_type TEXT NOT NULL DEFAULT 'context',
                evidence_pointer TEXT,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)
            # Migration check: add columns if table existed without them
            cursor = conn.execute("PRAGMA table_info(memories);")
            columns = [row[1] for row in cursor.fetchall()]
            if "memory_type" not in columns:
                try:
                    conn.execute("ALTER TABLE memories ADD COLUMN memory_type TEXT NOT NULL DEFAULT 'context';")
                except Exception:
                    pass
            if "evidence_pointer" not in columns:
                try:
                    conn.execute("ALTER TABLE memories ADD COLUMN evidence_pointer TEXT;")
                except Exception:
                    pass
            conn.commit()

    def remember(self, item: MemoryItem) -> None:
        """
        Stores a memory item. Enforces that VERIFIED_FACT items have an evidence pointer.
        """
        mem_type = item.memory_type.value if isinstance(item.memory_type, MemoryType) else str(item.memory_type)
        if mem_type == MemoryType.VERIFIED_FACT.value and not item.evidence_pointer:
            raise ValueError("VERIFIED_FACT memory requires a cryptographic evidence pointer.")

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
            INSERT INTO memories (key, content, category, memory_type, evidence_pointer, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                content = excluded.content,
                category = excluded.category,
                memory_type = excluded.memory_type,
                evidence_pointer = excluded.evidence_pointer,
                metadata_json = excluded.metadata_json,
                created_at = excluded.created_at;
            """, (
                item.key,
                item.content,
                item.category,
                mem_type,
                item.evidence_pointer,
                json.dumps(item.metadata),
                item.created_at,
            ))
            conn.commit()

    def recall(self, key: str) -> Optional[MemoryItem]:
        """Retrieves a specific memory item by key."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM memories WHERE key = ?;", (key,)).fetchone()
            if not row:
                return None
            return MemoryItem(
                key=row["key"],
                content=row["content"],
                category=row["category"],
                memory_type=row["memory_type"] if "memory_type" in row.keys() else MemoryType.CONTEXT.value,
                evidence_pointer=row["evidence_pointer"] if "evidence_pointer" in row.keys() else None,
                metadata=json.loads(row["metadata_json"]),
                created_at=row["created_at"],
            )

    def search(
        self,
        query: str,
        limit: int = 5,
        memory_type: Optional[str] = None,
    ) -> List[MemoryItem]:
        """Searches memory items matching query, optionally filtered by memory_type."""
        q_norm = f"%{query.lower()}%"
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if memory_type:
                m_type = memory_type.value if isinstance(memory_type, MemoryType) else str(memory_type)
                rows = conn.execute("""
                SELECT * FROM memories
                WHERE (LOWER(content) LIKE ? OR LOWER(category) LIKE ? OR LOWER(key) LIKE ?)
                  AND memory_type = ?
                ORDER BY created_at DESC
                LIMIT ?;
                """, (q_norm, q_norm, q_norm, m_type, limit)).fetchall()
            else:
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
                    memory_type=r["memory_type"] if "memory_type" in r.keys() else MemoryType.CONTEXT.value,
                    evidence_pointer=r["evidence_pointer"] if "evidence_pointer" in r.keys() else None,
                    metadata=json.loads(r["metadata_json"]),
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    def retrieve(self, query: str, limit: int = 5) -> List[MemoryItem]:
        """Backwards-compatible retrieval alias for search."""
        return self.search(query=query, limit=limit)

    def forget(self, key: str) -> bool:
        """Deletes a memory item by key."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("DELETE FROM memories WHERE key = ?;", (key,))
            conn.commit()
            return cur.rowcount > 0
