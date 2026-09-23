"""
S-Class Agent Fleet: Subagent Authority Scope & Symbol Leases (Section 24).
Governs subagents spawned by runtime harnesses (Step-Code parallel lanes / background workers).

Invariants:
1. Subagents are strictly bounded by parent obligation, workspace scope, and claim scope.
2. A subagent cannot establish or promote durable truth outside its authorized scope.
3. Symbol/file leases prevent conflicting mutations across concurrent workers.
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Set, Optional, Tuple, Union

from sclass.core.errors import SecurityViolationError


@dataclass
class SubagentAuthorityScope:
    """
    Authoritative boundary restricting what a subagent can access, mutate, or verify.
    """
    subagent_id: str
    parent_agent_id: str
    parent_obligation_id: str
    child_obligation_id: str
    authority_scope: Set[str] = field(default_factory=set)       # e.g. {"read_file", "test", "edit"}
    workspace_scope: Set[str] = field(default_factory=set)       # permitted subdirectories or files
    claim_scope: Set[str] = field(default_factory=set)           # permitted claim types (e.g. {"test_pass"})
    evidence_scope: Set[str] = field(default_factory=set)        # permitted verifiers
    lease_symbols: Set[str] = field(default_factory=set)         # AST symbols leased exclusively
    lease_files: Set[str] = field(default_factory=set)           # files leased exclusively
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def can_access_path(self, target_path: str) -> bool:
        if not self.workspace_scope:
            return True
        norm_target = os.path.normpath(target_path).replace("\\", "/").lower()
        for allowed in self.workspace_scope:
            norm_allowed = os.path.normpath(allowed).replace("\\", "/").lower()
            if norm_target == norm_allowed or norm_target.startswith(norm_allowed + "/"):
                return True
        return False

    def can_execute_action(self, action: str, target: str = "") -> bool:
        clean_action = (action or "").strip().lower()
        if self.authority_scope and clean_action not in self.authority_scope:
            return False
        if target and not self.can_access_path(target):
            return False
        return True

    def assert_can_execute(self, action: str, target: str = "") -> None:
        if not self.can_execute_action(action, target):
            raise SecurityViolationError(
                f"SUBAGENT AUTHORITY VIOLATION: Subagent '{self.subagent_id}' attempted action '{action}' on "
                f"target '{target}' outside permitted authority scope {list(self.authority_scope)} "
                f"or workspace scope {list(self.workspace_scope)}."
            )

    def can_propose_claim(self, claim_type: str, target: str = "") -> bool:
        clean_type = (claim_type or "").strip().lower()
        if self.claim_scope and clean_type not in self.claim_scope:
            return False
        if target and not self.can_access_path(target):
            return False
        return True

    def assert_can_create_truth(self, claim_type: str, target: str = "") -> None:
        """
        Enforces Section 24: A subagent cannot create durable truth outside its authority.
        """
        if not self.can_propose_claim(claim_type, target):
            raise SecurityViolationError(
                f"DURABLE TRUTH VIOLATION: Subagent '{self.subagent_id}' attempted to establish claim "
                f"'{claim_type}' on '{target}' outside its delegated authority scope. "
                "Subagents cannot create durable truth beyond their explicit boundaries."
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subagent_id": self.subagent_id,
            "parent_agent_id": self.parent_agent_id,
            "parent_obligation_id": self.parent_obligation_id,
            "child_obligation_id": self.child_obligation_id,
            "authority_scope": list(self.authority_scope),
            "workspace_scope": list(self.workspace_scope),
            "claim_scope": list(self.claim_scope),
            "evidence_scope": list(self.evidence_scope),
            "lease_symbols": list(self.lease_symbols),
            "lease_files": list(self.lease_files),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SubagentAuthorityScope:
        return cls(
            subagent_id=data["subagent_id"],
            parent_agent_id=data.get("parent_agent_id", "root"),
            parent_obligation_id=data.get("parent_obligation_id", ""),
            child_obligation_id=data.get("child_obligation_id", ""),
            authority_scope=set(data.get("authority_scope", [])),
            workspace_scope=set(data.get("workspace_scope", [])),
            claim_scope=set(data.get("claim_scope", [])),
            evidence_scope=set(data.get("evidence_scope", [])),
            lease_symbols=set(data.get("lease_symbols", [])),
            lease_files=set(data.get("lease_files", [])),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
        )
