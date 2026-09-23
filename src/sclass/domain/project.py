"""
S-Class Domain: Project Boundary, ProjectCheckpoint, and VerifiedProjectState.
Authoritative state representation for workspace lifecycle and cross-agent handoffs.
"""

from __future__ import annotations
import os
import uuid
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple, Union


@dataclass(frozen=True)
class ProjectBoundary:
    """Defines the authoritative root and security boundary for a workspace."""
    root_path: str
    sclass_dir: str = field(init=False)
    agents_dir: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "root_path", os.path.abspath(self.root_path))
        object.__setattr__(self, "sclass_dir", os.path.join(self.root_path, ".sclass"))
        object.__setattr__(self, "agents_dir", os.path.join(self.root_path, ".agents"))

    def contains(self, target_path: str) -> bool:
        """Determines if a target path is strictly contained within the project boundary."""
        try:
            abs_target = os.path.abspath(target_path)
            return os.path.commonpath([self.root_path, abs_target]) == self.root_path
        except (ValueError, OSError):
            return False


@dataclass(frozen=True)
class ProjectCheckpoint:
    """
    Authoritative point-in-time state checkpoint enabling zero-drift cross-agent handoff.
    Captures verified facts, repository head, working tree fingerprint, blockers, and constraints.
    """
    repository_head: str
    working_tree_fingerprint: str
    active_task: Optional[str]
    verified_tasks: tuple[str, ...]
    rejected_claims: tuple[str, ...]
    blockers: tuple[str, ...]
    relevant_files: tuple[str, ...]
    constraints: tuple[str, ...]
    next_action: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    checkpoint_id: str = field(default_factory=lambda: f"chk_{uuid.uuid4().hex[:12]}")

    def compute_checkpoint_hash(self) -> str:
        payload = (
            f"{self.repository_head}|{self.working_tree_fingerprint}|{self.active_task}|"
            f"{','.join(self.verified_tasks)}|{','.join(self.rejected_claims)}|"
            f"{','.join(self.blockers)}|{self.next_action}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "repository_head": self.repository_head,
            "working_tree_fingerprint": self.working_tree_fingerprint,
            "active_task": self.active_task,
            "verified_tasks": list(self.verified_tasks),
            "rejected_claims": list(self.rejected_claims),
            "blockers": list(self.blockers),
            "relevant_files": list(self.relevant_files),
            "constraints": list(self.constraints),
            "next_action": self.next_action,
            "timestamp": self.timestamp,
            "checkpoint_hash": self.compute_checkpoint_hash(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProjectCheckpoint:
        return cls(
            repository_head=data.get("repository_head", ""),
            working_tree_fingerprint=data.get("working_tree_fingerprint", ""),
            active_task=data.get("active_task"),
            verified_tasks=tuple(data.get("verified_tasks", [])),
            rejected_claims=tuple(data.get("rejected_claims", [])),
            blockers=tuple(data.get("blockers", [])),
            relevant_files=tuple(data.get("relevant_files", [])),
            constraints=tuple(data.get("constraints", [])),
            next_action=data.get("next_action", ""),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            checkpoint_id=data.get("checkpoint_id", f"chk_{uuid.uuid4().hex[:12]}"),
        )


@dataclass
class VerifiedProjectState:
    """
    Authoritative project state tracking verified facts rather than unverified agent claims (B.11 Universal Truth Layer).

    Structure (B.11):
    VerifiedProjectState
    ├── repository
    ├── workspace
    ├── current_revision
    ├── verified_claims
    ├── evidence
    ├── invalidated_claims
    ├── pending_verification
    ├── agent_context_summary
    └── handoff
    """
    # Universal Truth Layer Core (B.11)
    repository: str = ""
    workspace: str = ""
    current_revision: str = ""
    verified_claims: List[Dict[str, Any]] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    invalidated_claims: List[Dict[str, Any]] = field(default_factory=list)
    pending_verification: List[Dict[str, Any]] = field(default_factory=list)
    agent_context_summary: str = ""
    handoff: Optional[Dict[str, Any]] = None

    # Canonical Assurance Plane Fields (Section 15)
    active_obligations: List[Dict[str, Any]] = field(default_factory=list)
    invalidated_obligations: List[Dict[str, Any]] = field(default_factory=list)
    evidence_lineage: Dict[str, List[str]] = field(default_factory=dict)
    assumptions: List[Dict[str, Any]] = field(default_factory=list)
    verification_history: List[Dict[str, Any]] = field(default_factory=list)
    active_regressions: List[Dict[str, Any]] = field(default_factory=list)
    frontier: List[Dict[str, Any]] = field(default_factory=list)
    workspace_identity: str = ""
    relevant_project_version: str = ""

    # Backward compatibility fields
    goal: str = ""
    active_plan: List[str] = field(default_factory=list)
    active_task: Optional[str] = None
    verified_tasks: List[str] = field(default_factory=list)
    rejected_claims: List[str] = field(default_factory=list)
    blocked_tasks: List[str] = field(default_factory=list)
    recent_decisions: List[Dict[str, Any]] = field(default_factory=list)
    repository_checkpoint: Optional[str] = None
    verification_checkpoint: Optional[str] = None
    next_action: str = ""

    def mark_task_verified(self, task_id: str, verification_event_id: str) -> None:
        """Only marks task verified when backed by an authoritative verification event."""
        if task_id not in self.verified_tasks:
            self.verified_tasks.append(task_id)
        self.verification_checkpoint = verification_event_id

    def record_rejected_claim(self, claim_id: str) -> None:
        if claim_id not in self.rejected_claims:
            self.rejected_claims.append(claim_id)

    def record_verified_claim(
        self,
        claim: Union[Any, Dict[str, Any]],
        receipt: Optional[Union[Any, Dict[str, Any]]] = None,
    ) -> None:
        """Records a verified claim along with authoritative evidence receipt (B.11)."""
        c_dict = claim.to_dict() if hasattr(claim, "to_dict") else (dict(claim) if isinstance(claim, dict) else {"statement": str(claim)})
        cid = c_dict.get("claim_id") or c_dict.get("id")

        # Remove from pending if present
        if cid:
            self.pending_verification = [p for p in self.pending_verification if (p.get("claim_id") or p.get("id")) != cid]

        # Record evidence
        if receipt is not None:
            r_dict = receipt.to_dict() if hasattr(receipt, "to_dict") else (dict(receipt) if isinstance(receipt, dict) else {"receipt_id": str(receipt)})
            c_dict["evidence_receipt_id"] = r_dict.get("receipt_id")
            c_dict["receipt_hash"] = r_dict.get("receipt_hash")
            if r_dict not in self.evidence:
                self.evidence.append(r_dict)

        self.verified_claims.append(c_dict)

        # Track in verified_tasks if task_id associated
        task_id = c_dict.get("task_id")
        if task_id and task_id not in self.verified_tasks:
            self.verified_tasks.append(task_id)

    def record_invalidated_claim(
        self,
        claim_or_id: Union[str, Any, Dict[str, Any]],
        reason: str = "Claim rejected or invalidated by workspace divergence",
    ) -> None:
        """Records a claim as invalidated/rejected."""
        cid = claim_or_id if isinstance(claim_or_id, str) else (
            getattr(claim_or_id, "claim_id", None) or (claim_or_id.get("claim_id") if isinstance(claim_or_id, dict) else str(claim_or_id))
        )
        task_id = claim_or_id.get("task_id") if isinstance(claim_or_id, dict) else getattr(claim_or_id, "task_id", None)
        if cid:
            self.record_rejected_claim(cid)
            # Find matching verified claim before removing to preserve task_id if possible
            if not task_id:
                for c in self.verified_claims:
                    if (c.get("claim_id") or c.get("id")) == cid:
                        task_id = c.get("task_id")
                        break
            # Remove from verified_claims
            self.verified_claims = [c for c in self.verified_claims if (c.get("claim_id") or c.get("id")) != cid]
            self.pending_verification = [p for p in self.pending_verification if (p.get("claim_id") or p.get("id")) != cid]
            if task_id:
                # If no other verified claims remain for this task, remove from verified_tasks
                remaining_task_claims = [c for c in self.verified_claims if c.get("task_id") == task_id]
                if not remaining_task_claims and task_id in self.verified_tasks:
                    self.verified_tasks.remove(task_id)

        inv_record = {
            "claim_id": cid,
            "task_id": task_id,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if isinstance(claim_or_id, dict):
            inv_record["claim_details"] = claim_or_id
        self.invalidated_claims.append(inv_record)

    def record_pending_verification(self, claim: Union[Any, Dict[str, Any]]) -> None:
        """Adds a proposed claim to pending verification."""
        c_dict = claim.to_dict() if hasattr(claim, "to_dict") else (dict(claim) if isinstance(claim, dict) else {"statement": str(claim)})
        self.pending_verification.append(c_dict)

    def invalidate_on_workspace_mutation(self, new_fingerprint: str) -> List[str]:
        """
        Invalidates verified claims if workspace mutates after observation without corresponding proof.
        Returns list of invalidated claim IDs.
        """
        if not self.current_revision or self.current_revision == new_fingerprint:
            self.current_revision = new_fingerprint
            return []

        # Workspace mutated: invalidate claims tied to earlier revision
        invalidated_ids: List[str] = []
        for c in list(self.verified_claims):
            cid = c.get("claim_id") or c.get("id") or "unknown_claim"
            invalidated_ids.append(cid)
            self.record_invalidated_claim(
                c,
                reason=f"Workspace mutated from revision '{self.current_revision}' to '{new_fingerprint}' without verified observation",
            )

        self.current_revision = new_fingerprint
        return invalidated_ids

    def add_obligation(self, obligation: Any) -> None:
        o_dict = obligation.to_dict() if hasattr(obligation, "to_dict") else dict(obligation)
        oid = o_dict.get("obligation_id")
        self.active_obligations = [o for o in self.active_obligations if o.get("obligation_id") != oid]
        self.active_obligations.append(o_dict)

    def record_assumption(self, statement: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        rec = {
            "assumption_id": f"asmp_{uuid.uuid4().hex[:8]}",
            "statement": statement,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": dict(metadata or {}),
        }
        self.assumptions.append(rec)
        return rec

    def record_regression(self, regression: Dict[str, Any]) -> None:
        self.active_regressions.append(dict(regression))

    def update_frontier(self, frontier_items: List[Dict[str, Any]]) -> None:
        self.frontier = [dict(f) for f in frontier_items]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "repository": self.repository,
            "workspace": self.workspace,
            "current_revision": self.current_revision,
            "verified_claims": list(self.verified_claims),
            "evidence": list(self.evidence),
            "invalidated_claims": list(self.invalidated_claims),
            "pending_verification": list(self.pending_verification),
            "agent_context_summary": self.agent_context_summary,
            "handoff": dict(self.handoff) if self.handoff else None,
            "active_obligations": list(self.active_obligations),
            "invalidated_obligations": list(self.invalidated_obligations),
            "evidence_lineage": dict(self.evidence_lineage),
            "assumptions": list(self.assumptions),
            "verification_history": list(self.verification_history),
            "active_regressions": list(self.active_regressions),
            "frontier": list(self.frontier),
            "workspace_identity": self.workspace_identity,
            "relevant_project_version": self.relevant_project_version,
            "goal": self.goal,
            "active_plan": list(self.active_plan),
            "active_task": self.active_task,
            "verified_tasks": list(self.verified_tasks),
            "rejected_claims": list(self.rejected_claims),
            "blocked_tasks": list(self.blocked_tasks),
            "recent_decisions": list(self.recent_decisions),
            "repository_checkpoint": self.repository_checkpoint,
            "verification_checkpoint": self.verification_checkpoint,
            "next_action": self.next_action,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> VerifiedProjectState:
        return cls(
            repository=data.get("repository", ""),
            workspace=data.get("workspace", ""),
            current_revision=data.get("current_revision", ""),
            verified_claims=list(data.get("verified_claims", [])),
            evidence=list(data.get("evidence", [])),
            invalidated_claims=list(data.get("invalidated_claims", [])),
            pending_verification=list(data.get("pending_verification", [])),
            agent_context_summary=data.get("agent_context_summary", ""),
            handoff=data.get("handoff"),
            active_obligations=list(data.get("active_obligations", [])),
            invalidated_obligations=list(data.get("invalidated_obligations", [])),
            evidence_lineage=dict(data.get("evidence_lineage", {})),
            assumptions=list(data.get("assumptions", [])),
            verification_history=list(data.get("verification_history", [])),
            active_regressions=list(data.get("active_regressions", [])),
            frontier=list(data.get("frontier", [])),
            workspace_identity=data.get("workspace_identity", ""),
            relevant_project_version=data.get("relevant_project_version", ""),
            goal=data.get("goal", ""),
            active_plan=list(data.get("active_plan", [])),
            active_task=data.get("active_task"),
            verified_tasks=list(data.get("verified_tasks", [])),
            rejected_claims=list(data.get("rejected_claims", [])),
            blocked_tasks=list(data.get("blocked_tasks", [])),
            recent_decisions=list(data.get("recent_decisions", [])),
            repository_checkpoint=data.get("repository_checkpoint"),
            verification_checkpoint=data.get("verification_checkpoint"),
            next_action=data.get("next_action", ""),
        )

    @classmethod
    def from_json(cls, s: str) -> VerifiedProjectState:
        return cls.from_dict(json.loads(s))


@dataclass
class Project:
    """Authoritative representation of the developer project."""
    project_id: str
    name: str
    boundary: ProjectBoundary
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    active_agent: Optional[str] = None
    current_goal: Optional[str] = None
    state: Optional[VerifiedProjectState] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "name": self.name,
            "root_path": self.boundary.root_path,
            "created_at": self.created_at,
            "active_agent": self.active_agent,
            "current_goal": self.current_goal,
            "metadata": self.metadata,
            "state": self.state.to_dict() if self.state else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Project:
        state_data = data.get("state")
        return cls(
            project_id=data["project_id"],
            name=data["name"],
            boundary=ProjectBoundary(data["root_path"]),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            metadata=data.get("metadata", {}),
            active_agent=data.get("active_agent"),
            current_goal=data.get("current_goal"),
            state=VerifiedProjectState.from_dict(state_data) if state_data else None,
        )
