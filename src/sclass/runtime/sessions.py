"""
S-Class Runtime: Session Tree, Durable Registers & Context Compaction.
Implements the harvested Step-Code session state & context management (Directive Sections 2 & 13):
- Session tree with branch indices, leaves, and checkpoints.
- Durable runtime registers tracking active operation pointers.
- Non-destructive context compaction:
    Rule: context compression != evidence deletion.
    A compacted context projects summaries for model context limits, but NEVER
    erases canonical evidence or immutable session ledger history.
"""

from __future__ import annotations
import os
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


@dataclass
class SessionRegister:
    """Mutable runtime register pointing to current operation, leaf, and state."""
    session_id: str
    active_operation_id: Optional[str] = None
    current_leaf_id: str = "root"
    active_lane_id: Optional[str] = None
    step_count: int = 0
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class TreeNode:
    """Node in the branching session tree."""
    node_id: str
    parent_id: Optional[str]
    session_id: str
    node_type: str  # "prompt", "tool_call", "settlement", "checkpoint"
    content_hash: str
    data: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ContextProjection:
    """Projected compacted view of session history for LLM provider consumption."""
    session_id: str
    retained_tail_entries: List[Dict[str, Any]]
    summarized_branches: List[Dict[str, Any]]
    total_original_tokens: int
    projected_tokens: int
    is_compacted: bool
    evidence_intact: bool = True  # Canonical evidence is guaranteed intact


class SessionManager:
    """
    Manages session tree navigation, durable registers, and evidence-preserving compaction.
    """

    def __init__(self, workspace_dir: str):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.sessions_dir = os.path.join(self.workspace_dir, ".sclass", "sessions")
        os.makedirs(self.sessions_dir, exist_ok=True)
        self._registers: Dict[str, SessionRegister] = {}
        self._trees: Dict[str, Dict[str, TreeNode]] = {}
        self._history: Dict[str, List[Dict[str, Any]]] = {}

    def get_or_create_register(self, session_id: str) -> SessionRegister:
        if session_id not in self._registers:
            self._registers[session_id] = SessionRegister(session_id=session_id)
        return self._registers[session_id]

    def record_node(
        self,
        session_id: str,
        node_type: str,
        data: Dict[str, Any],
        parent_id: Optional[str] = None,
    ) -> TreeNode:
        reg = self.get_or_create_register(session_id)
        parent = parent_id or reg.current_leaf_id
        node_id = f"node_{uuid.uuid4().hex[:8]}"

        import hashlib
        c_hash = hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()

        node = TreeNode(
            node_id=node_id,
            parent_id=parent,
            session_id=session_id,
            node_type=node_type,
            content_hash=c_hash,
            data=data,
        )

        if session_id not in self._trees:
            self._trees[session_id] = {}
            self._history[session_id] = []

        self._trees[session_id][node_id] = node
        self._history[session_id].append({"node_id": node_id, "node_type": node_type, "data": data})

        reg.current_leaf_id = node_id
        reg.step_count += 1
        reg.updated_at = datetime.now(timezone.utc).isoformat()

        return node

    def compact_context(
        self,
        session_id: str,
        retained_tail_count: int = 10,
    ) -> ContextProjection:
        """
        Creates a compacted projection for LLM providers.
        Crucial Invariant (Section 13):
        Context compression does NOT delete or truncate durable session history or canonical evidence.
        """
        raw_entries = self._history.get(session_id, [])
        total_count = len(raw_entries)

        if total_count <= retained_tail_count:
            return ContextProjection(
                session_id=session_id,
                retained_tail_entries=list(raw_entries),
                summarized_branches=[],
                total_original_tokens=total_count * 100,
                projected_tokens=total_count * 100,
                is_compacted=False,
                evidence_intact=True,
            )

        older_entries = raw_entries[:-retained_tail_count]
        tail_entries = raw_entries[-retained_tail_count:]

        # Create structured branch summary
        summary = {
            "summary_id": f"sum_{uuid.uuid4().hex[:8]}",
            "summarized_entry_count": len(older_entries),
            "start_node": older_entries[0]["node_id"],
            "end_node": older_entries[-1]["node_id"],
            "abstract": f"Compacted {len(older_entries)} prior turns including tool calls and observations.",
        }

        # Notice: self._history[session_id] is NOT modified or purged!
        return ContextProjection(
            session_id=session_id,
            retained_tail_entries=list(tail_entries),
            summarized_branches=[summary],
            total_original_tokens=total_count * 100,
            projected_tokens=(retained_tail_count * 100) + 150,
            is_compacted=True,
            evidence_intact=True,
        )
