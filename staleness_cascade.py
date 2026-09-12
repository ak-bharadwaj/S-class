"""
S-Class V12: Staleness Invalidation Cascade Engine (staleness_cascade.py)

Inspects modified files and symbol diffs, computes downstream affected claims
and tests via the Codebase Knowledge Graph, and marks dependent claims as STALE.
Prevents AI agents from operating on stale, invalid verification assumptions.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List, Set
from codebase_graph_db import CodebaseGraphDB
from graph_traversal import GraphTraversalEngine
from ast_graph_extractor import ASTGraphExtractor

logger = logging.getLogger("sclass_staleness_cascade")


class StalenessCascadeEngine:
    """
    Detects code changes, walks the dependency graph, and cascades STALE status
    to dependent verification claims and test obligations.
    """

    DEFAULT_CLAIMS_FILE = os.path.join(".agents", "claim_status.json")

    def __init__(
        self,
        workspace_dir: Optional[str] = None,
        graph_db: Optional[CodebaseGraphDB] = None,
        traversal: Optional[GraphTraversalEngine] = None,
    ):
        self.workspace_dir = workspace_dir or os.getcwd()
        self.graph_db = graph_db or CodebaseGraphDB(workspace_dir=self.workspace_dir)
        self.traversal = traversal or GraphTraversalEngine(self.graph_db)
        self.extractor = ASTGraphExtractor(self.graph_db, workspace_dir=self.workspace_dir)
        self.claims_file = os.path.join(self.workspace_dir, self.DEFAULT_CLAIMS_FILE)

    def load_claims(self) -> Dict[str, Any]:
        if os.path.exists(self.claims_file):
            try:
                with open(self.claims_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"claims": {}, "last_updated": ""}

    def save_claims(self, claims_data: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self.claims_file), exist_ok=True)
        claims_data["last_updated"] = CodebaseGraphDB.now_iso()
        with open(self.claims_file, "w", encoding="utf-8") as f:
            json.dump(claims_data, f, indent=2)

    def register_claim(
        self,
        claim_id: str,
        description: str,
        target_symbols: List[str],
        status: str = "VERIFIED",
    ) -> Dict[str, Any]:
        """Registers a verified claim tied to specific symbols."""
        data = self.load_claims()
        data["claims"][claim_id] = {
            "claim_id": claim_id,
            "description": description,
            "status": status,
            "target_symbols": target_symbols,
            "registered_at": CodebaseGraphDB.now_iso(),
            "invalidated_at": None,
        }
        self.save_claims(data)
        return data["claims"][claim_id]

    def invalidate_for_file(self, file_path: str) -> Dict[str, Any]:
        """
        Invalidates claims affected by modifications to a specific file.
        Uses blast radius traversal to find affected symbols.
        """
        rel_path = os.path.relpath(file_path, self.workspace_dir).replace("\\", "/") if os.path.isabs(file_path) else file_path
        file_node_id = f"file::{rel_path}"

        # 1. Compute blast radius
        blast = self.traversal.blast_radius(file_node_id, max_hops=3)
        affected_symbol_ids = {file_node_id}
        for imp in blast.get("impacted_nodes", []):
            affected_symbol_ids.add(imp["id"])

        # Also find symbols directly defined in file
        nodes_in_file = self.graph_db.get_nodes_by_file(rel_path)
        for n in nodes_in_file:
            affected_symbol_ids.add(n["id"])

        # 2. Mark claims as STALE
        claims_data = self.load_claims()
        stale_claim_ids = []

        for cid, cinfo in claims_data.get("claims", {}).items():
            syms = cinfo.get("target_symbols", [])
            # If any symbol associated with claim is in affected symbols
            if any(s in affected_symbol_ids for s in syms) or not syms:
                cinfo["status"] = "STALE"
                cinfo["invalidated_at"] = CodebaseGraphDB.now_iso()
                cinfo["invalidated_by_file"] = rel_path
                stale_claim_ids.append(cid)

        if stale_claim_ids:
            self.save_claims(claims_data)

        # 3. Generate reverification suggestions
        reverification_commands = []
        if blast.get("affected_tests"):
            reverification_commands.append("python -m pytest " + " ".join(blast["affected_tests"][:3]))
        else:
            reverification_commands.append("python -m pytest tests/")

        return {
            "file": rel_path,
            "affected_symbols_count": len(affected_symbol_ids),
            "stale_claims_count": len(stale_claim_ids),
            "stale_claim_ids": stale_claim_ids,
            "affected_routes": blast.get("affected_routes", []),
            "reverification_commands": reverification_commands,
        }
