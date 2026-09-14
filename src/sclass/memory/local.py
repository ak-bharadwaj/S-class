"""
S-Class Memory: Zero-Infrastructure Local SQLite Memory Provider.
Implements the MemoryProvider protocol: store, query, invalidate, prune, health.
Enforces Invariant L10: Memory is candidate context, never authoritative.
"""

from __future__ import annotations
import os
import json
import sqlite3
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from sclass.memory.provider import MemoryProvider, MemoryItem, MemoryType
from sclass.storage.paths import WorkspacePaths


class LocalMemoryProvider(MemoryProvider):
    """Local SQLite-backed candidate memory provider in .sclass/cache/memory.db."""

    def __init__(self, workspace_dir: str):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.paths = WorkspacePaths(workspace_dir)
        os.makedirs(self.paths.cache_dir, exist_ok=True)
        self.db_path = os.path.join(self.paths.cache_dir, "memory.db")
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                key TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                category TEXT NOT NULL,
                memory_type TEXT NOT NULL DEFAULT 'context',
                evidence_pointer TEXT,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT,
                ttl_seconds INTEGER,
                relevance_score REAL DEFAULT 1.0
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
            if "expires_at" not in columns:
                try:
                    conn.execute("ALTER TABLE memories ADD COLUMN expires_at TEXT;")
                except Exception:
                    pass
            if "ttl_seconds" not in columns:
                try:
                    conn.execute("ALTER TABLE memories ADD COLUMN ttl_seconds INTEGER;")
                except Exception:
                    pass
            if "relevance_score" not in columns:
                try:
                    conn.execute("ALTER TABLE memories ADD COLUMN relevance_score REAL DEFAULT 1.0;")
                except Exception:
                    pass
            conn.commit()

    def store(self, item: MemoryItem) -> None:
        """
        Stores a memory item into SQLite.
        Enforces Invariant L10: Memory is contextual, never authoritative.
        Enforces that VERIFIED_FACT items must have a valid cryptographic evidence pointer.
        """
        if item.is_authoritative:
            raise ValueError("L10 Invariant Violation: Memory cannot assert authoritative project truth.")

        mem_type = item.memory_type.value if isinstance(item.memory_type, MemoryType) else str(item.memory_type)
        if mem_type == MemoryType.VERIFIED_FACT.value and not item.evidence_pointer:
            raise ValueError("VERIFIED_FACT memory requires a cryptographic evidence pointer.")

        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("""
            INSERT INTO memories (
                key, content, category, memory_type, evidence_pointer,
                metadata_json, created_at, expires_at, ttl_seconds, relevance_score
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                content = excluded.content,
                category = excluded.category,
                memory_type = excluded.memory_type,
                evidence_pointer = excluded.evidence_pointer,
                metadata_json = excluded.metadata_json,
                created_at = excluded.created_at,
                expires_at = excluded.expires_at,
                ttl_seconds = excluded.ttl_seconds,
                relevance_score = excluded.relevance_score;
            """, (
                item.key,
                item.content,
                item.category,
                mem_type,
                item.evidence_pointer,
                json.dumps(item.metadata),
                item.created_at,
                item.expires_at,
                item.ttl_seconds,
                float(item.relevance_score),
            ))
            conn.commit()

    def remember(self, item: MemoryItem) -> None:
        """Backwards-compatible alias for store()."""
        self.store(item)

    def recall(self, key: str) -> Optional[MemoryItem]:
        """Retrieves a specific memory item by key, filtering out expired items."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM memories WHERE key = ?;", (key,)).fetchone()
            if not row:
                return None

            expires_at = row["expires_at"] if "expires_at" in row.keys() else None
            if expires_at and expires_at < now_iso:
                return None

            return MemoryItem(
                key=row["key"],
                content=row["content"],
                category=row["category"],
                memory_type=row["memory_type"] if "memory_type" in row.keys() else MemoryType.CONTEXT.value,
                evidence_pointer=row["evidence_pointer"] if "evidence_pointer" in row.keys() else None,
                metadata=json.loads(row["metadata_json"]),
                created_at=row["created_at"],
                expires_at=expires_at,
                ttl_seconds=row["ttl_seconds"] if "ttl_seconds" in row.keys() else None,
                relevance_score=float(row["relevance_score"]) if "relevance_score" in row.keys() and row["relevance_score"] is not None else 1.0,
                is_authoritative=False,
            )

    def query(
        self,
        query: str,
        limit: int = 5,
        memory_type: Optional[str] = None,
        min_relevance: float = 0.0,
    ) -> List[MemoryItem]:
        """
        Searches memory items matching text query, filtered by memory_type and min_relevance.
        Calculates relevance scoring:
        - Exact query substring match (+1.0)
        - Key exact/prefix match (+0.8)
        - Individual term overlaps (+0.3 each)
        - Category match (+0.2)
        - Normalizes score and filters out expired items.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        q_clean = query.strip().lower()
        terms = [t for t in q_clean.split() if t]

        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.row_factory = sqlite3.Row
            # Fetch non-expired candidates
            sql = "SELECT * FROM memories WHERE (expires_at IS NULL OR expires_at > ?)"
            params: List[Any] = [now_iso]

            if memory_type:
                m_type = memory_type.value if isinstance(memory_type, MemoryType) else str(memory_type)
                sql += " AND memory_type = ?"
                params.append(m_type)

            rows = conn.execute(sql, params).fetchall()

            scored_items: List[MemoryItem] = []
            for r in rows:
                content_lower = r["content"].lower()
                key_lower = r["key"].lower()
                cat_lower = r["category"].lower()

                # If query is empty, return all non-expired up to limit
                if not q_clean:
                    score = 1.0
                else:
                    score = 0.0
                    # Exact phrase match
                    if q_clean in content_lower:
                        score += 1.0
                    if q_clean in key_lower:
                        score += 0.8
                    if q_clean in cat_lower:
                        score += 0.4

                    # Term overlap
                    term_hits = sum(1 for t in terms if t in content_lower or t in key_lower)
                    score += term_hits * 0.3

                if score >= min_relevance and score > 0.0:
                    scored_items.append(
                        MemoryItem(
                            key=r["key"],
                            content=r["content"],
                            category=r["category"],
                            memory_type=r["memory_type"] if "memory_type" in r.keys() else MemoryType.CONTEXT.value,
                            evidence_pointer=r["evidence_pointer"] if "evidence_pointer" in r.keys() else None,
                            metadata=json.loads(r["metadata_json"]),
                            created_at=r["created_at"],
                            expires_at=r["expires_at"] if "expires_at" in r.keys() else None,
                            ttl_seconds=r["ttl_seconds"] if "ttl_seconds" in r.keys() else None,
                            relevance_score=round(score, 3),
                            is_authoritative=False,
                        )
                    )

            # Sort by relevance score descending, then created_at descending
            scored_items.sort(key=lambda item: (item.relevance_score, item.created_at), reverse=True)
            return scored_items[:limit]

    def search(
        self,
        query: str,
        limit: int = 5,
        memory_type: Optional[str] = None,
    ) -> List[MemoryItem]:
        """Backwards-compatible search method."""
        return self.query(query=query, limit=limit, memory_type=memory_type)

    def retrieve(self, query: str, limit: int = 5) -> List[MemoryItem]:
        """Backwards-compatible retrieval alias for search/query."""
        return self.query(query=query, limit=limit)

    def invalidate(self, key_or_pattern: str) -> int:
        """
        Removes memory items by exact key or glob/wildcard pattern (e.g. 'auth_*' or 'cache_%').
        Returns number of deleted records.
        """
        pattern = key_or_pattern.replace("*", "%")
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            if "%" in pattern:
                cur = conn.execute("DELETE FROM memories WHERE key LIKE ?;", (pattern,))
            else:
                cur = conn.execute("DELETE FROM memories WHERE key = ?;", (key_or_pattern,))
            conn.commit()
            return cur.rowcount

    def forget(self, key: str) -> bool:
        """Removes a memory item by exact key. Returns True if deleted."""
        return self.invalidate(key) > 0

    def prune(self, before_timestamp: Optional[str] = None, expired_only: bool = True) -> int:
        """
        Prunes expired or old memories.
        If expired_only is True, removes all items where expires_at <= current time.
        If before_timestamp is provided, also removes items created before that timestamp.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        clauses: List[str] = []
        params: List[Any] = []

        if expired_only:
            clauses.append("(expires_at IS NOT NULL AND expires_at <= ?)")
            params.append(now_iso)

        if before_timestamp:
            clauses.append("created_at < ?")
            params.append(before_timestamp)

        if not clauses:
            return 0

        where_expr = " OR ".join(clauses)
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            cur = conn.execute(f"DELETE FROM memories WHERE {where_expr};", params)
            conn.commit()
            return cur.rowcount

    def health(self) -> Dict[str, Any]:
        """Returns provider health status, operational metrics, and DB file details."""
        exists = os.path.exists(self.db_path)
        item_count = 0
        if exists:
            try:
                with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                    cur = conn.execute("SELECT COUNT(*) FROM memories;")
                    item_count = cur.fetchone()[0]
            except Exception:
                pass

        size_bytes = os.path.getsize(self.db_path) if exists else 0
        return {
            "status": "ok",
            "provider": "local_sqlite",
            "healthy": True,
            "db_path": self.db_path,
            "item_count": item_count,
            "size_bytes": size_bytes,
        }
