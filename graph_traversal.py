"""
S-Class V12: Recursive CTE & NetworkX Graph Traversal Engine (graph_traversal.py)

Performs high-performance graph analytics over the Codebase Knowledge Graph (CKG):
- Blast Radius & Impact Analysis (Recursive CTE with cycle detection & risk scoring 0-10)
- Upstream Call Hierarchy (Sinks to Controllers)
- Circular Dependency & Import Loop Detection
- Shortest Execution Path Analysis
- Precision 1-Hop AST Neighborhood Context
"""

import json
import sqlite3
import logging
from typing import Dict, Any, Optional, List, Set, Tuple
import networkx as nx
from codebase_graph_db import CodebaseGraphDB

logger = logging.getLogger("sclass_graph_traversal")


class GraphTraversalEngine:
    """
    Graph Traversal and Impact Analysis Engine powered by SQLite Recursive CTEs
    and NetworkX algorithms.
    """

    def __init__(self, graph_db: Optional[CodebaseGraphDB] = None):
        self.graph_db = graph_db or CodebaseGraphDB()

    def get_neighborhood(self, node_id: str) -> Dict[str, Any]:
        """
        Retrieves precision 1-hop AST context for a node:
        definition, signature, docstring, callers, callees, imports, and definitions.
        """
        node = self.graph_db.get_node(node_id)
        if not node:
            return {"error": f"Node '{node_id}' not found in knowledge graph."}

        incoming_edges = self.graph_db.get_edges(target_id=node_id)
        outgoing_edges = self.graph_db.get_edges(source_id=node_id)

        incoming_nodes = []
        for e in incoming_edges:
            src = self.graph_db.get_node(e["source_id"])
            if src:
                incoming_nodes.append({
                    "relation": e["relation"],
                    "node_id": src["id"],
                    "name": src["name"],
                    "type": src["type"],
                    "file_path": src["file_path"],
                })

        outgoing_nodes = []
        for e in outgoing_edges:
            tgt = self.graph_db.get_node(e["target_id"])
            if tgt:
                outgoing_nodes.append({
                    "relation": e["relation"],
                    "node_id": tgt["id"],
                    "name": tgt["name"],
                    "type": tgt["type"],
                    "file_path": tgt["file_path"],
                })

        return {
            "node": node,
            "incoming": incoming_nodes,
            "outgoing": outgoing_nodes,
            "incoming_count": len(incoming_nodes),
            "outgoing_count": len(outgoing_nodes),
        }

    def blast_radius(
        self,
        node_id: str,
        max_hops: int = 3,
        direction: str = "downstream",
    ) -> Dict[str, Any]:
        """
        Computes downstream (or upstream) blast radius using SQLite Recursive CTEs.
        Prevents infinite loops via path cycle tracking.
        Returns impacted nodes, affected routes, affected tests, and a calculated Risk Score (0-10).
        """
        root_node = self.graph_db.get_node(node_id)
        if not root_node:
            return {
                "root_id": node_id,
                "risk_score": 0.0,
                "impacted_nodes": [],
                "affected_routes": [],
                "affected_tests": [],
                "affected_models": [],
                "total_impacted": 0,
            }

        # Recursive CTE query for downstream or upstream traversal with exact-boundary cycle detection
        if direction == "upstream":
            query = """
            WITH RECURSIVE traversal(node_id, hop, path) AS (
                SELECT source_id, 1, '|' || ? || '|' || source_id || '|'
                FROM edges
                WHERE target_id = ?
                UNION
                SELECT e.source_id, t.hop + 1, t.path || e.source_id || '|'
                FROM edges e
                JOIN traversal t ON e.target_id = t.node_id
                WHERE t.hop < ? AND instr(t.path, '|' || e.source_id || '|') = 0
            )
            SELECT DISTINCT t.node_id, MIN(t.hop) as distance, t.path, n.name, n.type, n.file_path
            FROM traversal t
            JOIN nodes n ON t.node_id = n.id
            GROUP BY t.node_id
            ORDER BY distance ASC;
            """
        else:
            query = """
            WITH RECURSIVE traversal(node_id, hop, path) AS (
                SELECT target_id, 1, '|' || ? || '|' || target_id || '|'
                FROM edges
                WHERE source_id = ?
                UNION
                SELECT e.target_id, t.hop + 1, t.path || e.target_id || '|'
                FROM edges e
                JOIN traversal t ON e.source_id = t.node_id
                WHERE t.hop < ? AND instr(t.path, '|' || e.target_id || '|') = 0
            )
            SELECT DISTINCT t.node_id, MIN(t.hop) as distance, t.path, n.name, n.type, n.file_path
            FROM traversal t
            JOIN nodes n ON t.node_id = n.id
            GROUP BY t.node_id
            ORDER BY distance ASC;
            """

        with self.graph_db._get_connection() as conn:
            cur = conn.execute(query, (node_id, node_id, max_hops))
            rows = cur.fetchall()

        impacted: List[Dict[str, Any]] = []
        affected_routes: List[str] = []
        affected_tests: List[str] = []
        affected_models: List[str] = []

        for r in rows:
            raw_path = r["path"] or ""
            clean_path = raw_path.strip("|").replace("|", "->") if raw_path else ""
            item = {
                "id": r["node_id"],
                "name": r["name"],
                "type": r["type"],
                "file_path": r["file_path"],
                "distance": r["distance"],
                "path": clean_path,
            }
            impacted.append(item)
            ntype = r["type"].upper()
            fp = (r["file_path"] or "").lower()

            if ntype == "ROUTE" or "api" in fp:
                affected_routes.append(r["name"])
            if "test" in fp or "spec" in fp or ntype == "TEST":
                affected_tests.append(r["name"])
            if ntype == "MODEL" or "schema" in fp or "model" in fp:
                affected_models.append(r["name"])

        # Calculate Risk Score (0.0 to 10.0)
        risk = 1.0  # Baseline
        risk += min(4.0, len(impacted) * 0.4)
        if affected_routes:
            risk += min(2.5, len(affected_routes) * 1.0)
        if affected_models:
            risk += min(2.0, len(affected_models) * 1.0)
        if not affected_tests and len(impacted) > 2:
            risk += 1.0  # Uncovered risk penalty
        risk_score = round(min(10.0, max(0.0, risk)), 2)

        return {
            "root_id": node_id,
            "root_name": root_node.get("name"),
            "risk_score": risk_score,
            "impacted_nodes": impacted,
            "affected_routes": sorted(list(set(affected_routes))),
            "affected_tests": sorted(list(set(affected_tests))),
            "affected_models": sorted(list(set(affected_models))),
            "total_impacted": len(impacted),
            "max_hops": max_hops,
            "direction": direction,
        }

    def upstream_call_hierarchy(self, sink_id: str, max_hops: int = 5) -> List[Dict[str, Any]]:
        """Traces callers backwards from a database/sink operation to user-facing controllers."""
        res = self.blast_radius(node_id=sink_id, max_hops=max_hops, direction="upstream")
        return res.get("impacted_nodes", [])

    def to_networkx_graph(self) -> nx.DiGraph:
        """Constructs an in-memory NetworkX DiGraph representation of nodes and edges."""
        G = nx.DiGraph()
        with self.graph_db._get_connection() as conn:
            cur_nodes = conn.execute("SELECT id, name, type, file_path FROM nodes")
            for n in cur_nodes.fetchall():
                G.add_node(n["id"], name=n["name"], type=n["type"], file_path=n["file_path"])

            cur_edges = conn.execute("SELECT source_id, target_id, relation FROM edges")
            for e in cur_edges.fetchall():
                G.add_edge(e["source_id"], e["target_id"], relation=e["relation"])
        return G

    def find_cycles(self) -> List[List[str]]:
        """
        Detects circular dependencies in the codebase graph (e.g. module/file import cycles).
        """
        G = self.to_networkx_graph()
        cycles = list(nx.simple_cycles(G))
        # Filter out self-loops if any
        return [c for c in cycles if len(c) > 1]

    def shortest_path(self, source_id: str, target_id: str) -> Optional[List[str]]:
        """Finds the shortest directed path between two entities."""
        G = self.to_networkx_graph()
        try:
            return nx.shortest_path(G, source=source_id, target=target_id)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None
