"""
S-Class V12: Zero-Infrastructure Codebase Knowledge Graph (CKG) Database Engine
(codebase_graph_db.py)

Authoritative embedded SQLite WAL storage engine for codebase topology:
- Nodes (Files, Modules, Classes, Functions, Routes, Models, Requirements, ADRs)
- Edges (DEFINES, IMPORTS, CALLS, INHERITS, USES_MODEL, HANDLES, SATISFIES, AFFECTS, DEPENDS_ON)
- High performance tuning: WAL mode, 64MB cache, 256MB mmap, B-Tree composite indexes.
"""

import os
import json
import sqlite3
import hashlib
import logging
from typing import Dict, Any, Optional, List, Tuple, Set
from datetime import datetime, timezone

import contextlib

logger = logging.getLogger("sclass_codebase_graph_db")


class CodebaseGraphDB:
    """
    Embedded SQLite Knowledge Graph Database for codebase entities and dependencies.
    Stored at `.agents/codebase_graph.db` with zero external service dependencies.
    """

    DEFAULT_DB_REL_PATH = os.path.join(".agents", "codebase_graph.db")

    def __init__(self, db_path: Optional[str] = None, workspace_dir: Optional[str] = None):
        if db_path:
            self.db_path = db_path
        else:
            base_dir = workspace_dir or os.getcwd()
            self.db_path = os.path.join(base_dir, self.DEFAULT_DB_REL_PATH)

        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        self._init_db()

    @contextlib.contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        # PRAGMA performance tuning
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA cache_size = -64000;")  # ~64MB
        conn.execute("PRAGMA mmap_size = 268435456;")  # 256MB
        conn.execute("PRAGMA temp_store = MEMORY;")
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initializes database schema and indexes."""
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    file_path TEXT,
                    start_line INTEGER DEFAULT 0,
                    end_line INTEGER DEFAULT 0,
                    docstring TEXT DEFAULT '',
                    signature TEXT DEFAULT '',
                    content_hash TEXT DEFAULT '',
                    metadata_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS edges (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    metadata_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (source_id) REFERENCES nodes(id) ON DELETE CASCADE,
                    FOREIGN KEY (target_id) REFERENCES nodes(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_nodes_type_file ON nodes(type, file_path);
                CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes(name);
                CREATE INDEX IF NOT EXISTS idx_nodes_file ON nodes(file_path);
                CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id, relation);
                CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id, relation);
                CREATE INDEX IF NOT EXISTS idx_edges_relation ON edges(relation);
            """)

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def upsert_node(
        self,
        node_id: str,
        name: str,
        node_type: str,
        file_path: Optional[str] = None,
        start_line: int = 0,
        end_line: int = 0,
        docstring: str = "",
        signature: str = "",
        content_hash: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Inserts or updates a node in the graph."""
        now = self.now_iso()
        meta_json = json.dumps(metadata or {})
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO nodes (id, name, type, file_path, start_line, end_line, docstring, signature, content_hash, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    type = excluded.type,
                    file_path = excluded.file_path,
                    start_line = excluded.start_line,
                    end_line = excluded.end_line,
                    docstring = excluded.docstring,
                    signature = excluded.signature,
                    content_hash = excluded.content_hash,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at;
                """,
                (node_id, name, node_type.upper(), file_path or "", start_line, end_line, docstring or "", signature or "", content_hash or "", meta_json, now, now)
            )
        return node_id

    def upsert_nodes_batch(self, nodes_data: List[Dict[str, Any]]) -> int:
        """Batch inserts or updates nodes."""
        if not nodes_data:
            return 0
        now = self.now_iso()
        rows = [
            (
                n["id"],
                n["name"],
                n["type"].upper(),
                n.get("file_path", ""),
                n.get("start_line", 0),
                n.get("end_line", 0),
                n.get("docstring", ""),
                n.get("signature", ""),
                n.get("content_hash", ""),
                json.dumps(n.get("metadata", {})),
                now,
                now,
            )
            for n in nodes_data
        ]
        with self._get_connection() as conn:
            conn.executemany(
                """
                INSERT INTO nodes (id, name, type, file_path, start_line, end_line, docstring, signature, content_hash, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    type = excluded.type,
                    file_path = excluded.file_path,
                    start_line = excluded.start_line,
                    end_line = excluded.end_line,
                    docstring = excluded.docstring,
                    signature = excluded.signature,
                    content_hash = excluded.content_hash,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at;
                """,
                rows,
            )
        return len(rows)

    def upsert_edge(
        self,
        source_id: str,
        target_id: str,
        relation: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Inserts or updates an edge between two nodes."""
        relation_clean = relation.upper()
        edge_id = f"{source_id}->{relation_clean}->{target_id}"
        now = self.now_iso()
        meta_json = json.dumps(metadata or {})
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO edges (id, source_id, target_id, relation, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    metadata_json = excluded.metadata_json;
                """,
                (edge_id, source_id, target_id, relation_clean, meta_json, now),
            )
        return edge_id

    def upsert_edges_batch(self, edges_data: List[Dict[str, Any]]) -> int:
        """Batch inserts or updates edges."""
        if not edges_data:
            return 0
        now = self.now_iso()
        rows = [
            (
                f"{e['source_id']}->{e['relation'].upper()}->{e['target_id']}",
                e["source_id"],
                e["target_id"],
                e["relation"].upper(),
                json.dumps(e.get("metadata", {})),
                now,
            )
            for e in edges_data
        ]
        with self._get_connection() as conn:
            conn.executemany(
                """
                INSERT INTO edges (id, source_id, target_id, relation, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    metadata_json = excluded.metadata_json;
                """,
                rows,
            )
        return len(rows)

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single node by ID."""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,))
            row = cur.fetchone()
            if row:
                d = dict(row)
                d["metadata"] = json.loads(d.pop("metadata_json") or "{}")
                return d
        return None

    def get_nodes_by_type(self, node_type: str) -> List[Dict[str, Any]]:
        """Retrieves all nodes of a given type."""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM nodes WHERE type = ?", (node_type.upper(),))
            results = []
            for row in cur.fetchall():
                d = dict(row)
                d["metadata"] = json.loads(d.pop("metadata_json") or "{}")
                results.append(d)
            return results

    def get_nodes_by_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Retrieves all nodes defined in a specific file."""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM nodes WHERE file_path = ?", (file_path,))
            results = []
            for row in cur.fetchall():
                d = dict(row)
                d["metadata"] = json.loads(d.pop("metadata_json") or "{}")
                results.append(d)
            return results

    def get_edges(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        relation: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Queries edges with optional filters."""
        query = "SELECT * FROM edges WHERE 1=1"
        params: List[Any] = []
        if source_id:
            query += " AND source_id = ?"
            params.append(source_id)
        if target_id:
            query += " AND target_id = ?"
            params.append(target_id)
        if relation:
            query += " AND relation = ?"
            params.append(relation.upper())

        with self._get_connection() as conn:
            cur = conn.execute(query, params)
            results = []
            for row in cur.fetchall():
                d = dict(row)
                d["metadata"] = json.loads(d.pop("metadata_json") or "{}")
                results.append(d)
            return results

    def delete_file_nodes(self, file_path: str) -> int:
        """Deletes all nodes defined in a file and cascades edge deletion."""
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM nodes WHERE file_path = ?", (file_path,))
            return cur.rowcount

    def record_decision(
        self,
        adr_id: str,
        title: str,
        status: str,
        rationale: str,
        rejected_alternatives: Optional[List[str]] = None,
        affected_symbol_ids: Optional[List[str]] = None,
        affected_files: Optional[List[str]] = None,
    ) -> str:
        """
        Records an Architecture Decision Record (ADR) into the graph and links it
        to affected symbols and files via AFFECTS edges.
        """
        meta = {
            "title": title,
            "status": status,
            "rationale": rationale,
            "rejected_alternatives": rejected_alternatives or [],
            "affected_files": affected_files or [],
        }
        node_id = f"adr::{adr_id}"
        self.upsert_node(
            node_id=node_id,
            name=title,
            node_type="ADR",
            docstring=rationale,
            metadata=meta,
        )

        for sym_id in affected_symbol_ids or []:
            if self.get_node(sym_id):
                self.upsert_edge(source_id=node_id, target_id=sym_id, relation="AFFECTS")

        for fpath in affected_files or []:
            f_node_id = f"file::{fpath}"
            if self.get_node(f_node_id):
                self.upsert_edge(source_id=node_id, target_id=f_node_id, relation="AFFECTS")

        return node_id

    def get_stats(self) -> Dict[str, Any]:
        """Returns summary statistics of the knowledge graph."""
        with self._get_connection() as conn:
            cur_nodes = conn.execute("SELECT type, count(*) as cnt FROM nodes GROUP BY type")
            node_counts = {r["type"]: r["cnt"] for r in cur_nodes.fetchall()}
            cur_edges = conn.execute("SELECT relation, count(*) as cnt FROM edges GROUP BY relation")
            edge_counts = {r["relation"]: r["cnt"] for r in cur_edges.fetchall()}
            total_nodes = sum(node_counts.values())
            total_edges = sum(edge_counts.values())
            return {
                "total_nodes": total_nodes,
                "total_edges": total_edges,
                "nodes_by_type": node_counts,
                "edges_by_relation": edge_counts,
                "db_path": self.db_path,
            }

    def clear(self) -> None:
        """Clears all nodes and edges in the database."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM edges;")
            conn.execute("DELETE FROM nodes;")
