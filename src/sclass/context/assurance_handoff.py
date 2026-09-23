"""
S-Class Context: Runtime-Independent Assurance Handoff Object (Section 22).
Encapsulates canonical verified state, technical obligations, open frontiers,
and active leases for cross-agent execution continuity.

Invariants:
1. Handoff carries canonical verified truth, never conversational transcript bloat (Law L9).
2. Any agent runtime (Step-Code, Claude Code, Codex, Custom) can resume from this object.
3. Cryptographically bound to the underlying verified project state.
"""

from __future__ import annotations
import uuid
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Union

from sclass.domain.project import VerifiedProjectState
from sclass.domain.obligations import TechnicalObligation, ObligationStatus
from sclass.core.errors import HandoffIntegrityError


@dataclass(frozen=True)
class AssuranceHandoff:
    """
    Authoritative cross-agent handoff object.
    Carries canonical verified state across heterogeneous agent runtimes.
    """
    task_id: str
    verified_project_state_ref: str
    verified_claims: Tuple[Dict[str, Any], ...]
    active_obligations: Tuple[Dict[str, Any], ...]
    stale_claims: Tuple[Dict[str, Any], ...]
    failed_claims: Tuple[Dict[str, Any], ...]
    open_frontier: Tuple[Dict[str, Any], ...]
    evidence_references: Tuple[str, ...]
    workspace_identity: str
    recovery_state: Optional[Dict[str, Any]]
    active_leases: Tuple[Dict[str, Any], ...]
    required_next_actions: Tuple[str, ...]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    handoff_id: str = field(default_factory=lambda: f"hndf_{uuid.uuid4().hex[:12]}")
    handoff_hash: str = field(init=False)

    def __init__(
        self,
        task_id: str,
        verified_project_state_ref: str,
        verified_claims: Union[List[Dict[str, Any]], Tuple[Dict[str, Any], ...]] = (),
        active_obligations: Union[List[Dict[str, Any]], Tuple[Dict[str, Any], ...]] = (),
        stale_claims: Union[List[Dict[str, Any]], Tuple[Dict[str, Any], ...]] = (),
        failed_claims: Union[List[Dict[str, Any]], Tuple[Dict[str, Any], ...]] = (),
        open_frontier: Union[List[Dict[str, Any]], Tuple[Dict[str, Any], ...]] = (),
        evidence_references: Union[List[str], Tuple[str, ...]] = (),
        workspace_identity: str = "",
        recovery_state: Optional[Dict[str, Any]] = None,
        active_leases: Union[List[Dict[str, Any]], Tuple[Dict[str, Any], ...]] = (),
        required_next_actions: Union[List[str], Tuple[str, ...]] = (),
        timestamp: Optional[str] = None,
        handoff_id: Optional[str] = None,
        handoff_hash: Optional[str] = None,
    ):
        hid = handoff_id or f"hndf_{uuid.uuid4().hex[:12]}"
        ts = timestamp or datetime.now(timezone.utc).isoformat()

        object.__setattr__(self, "task_id", task_id)
        object.__setattr__(self, "verified_project_state_ref", verified_project_state_ref)
        object.__setattr__(self, "verified_claims", tuple(verified_claims))
        object.__setattr__(self, "active_obligations", tuple(active_obligations))
        object.__setattr__(self, "stale_claims", tuple(stale_claims))
        object.__setattr__(self, "failed_claims", tuple(failed_claims))
        object.__setattr__(self, "open_frontier", tuple(open_frontier))
        object.__setattr__(self, "evidence_references", tuple(evidence_references))
        object.__setattr__(self, "workspace_identity", workspace_identity)
        object.__setattr__(self, "recovery_state", recovery_state)
        object.__setattr__(self, "active_leases", tuple(active_leases))
        object.__setattr__(self, "required_next_actions", tuple(required_next_actions))
        object.__setattr__(self, "timestamp", ts)
        object.__setattr__(self, "handoff_id", hid)

        computed = self.compute_hash()
        if handoff_hash and handoff_hash != computed:
            raise HandoffIntegrityError(f"Handoff integrity check failed: {handoff_hash} != {computed}")
        object.__setattr__(self, "handoff_hash", computed)

    def compute_hash(self) -> str:
        payload = (
            f"{self.task_id}|{self.verified_project_state_ref}|{len(self.verified_claims)}|"
            f"{len(self.active_obligations)}|{len(self.stale_claims)}|{len(self.open_frontier)}|"
            f"{self.workspace_identity}|{','.join(self.evidence_references)}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "handoff_id": self.handoff_id,
            "task_id": self.task_id,
            "verified_project_state_ref": self.verified_project_state_ref,
            "verified_claims": list(self.verified_claims),
            "active_obligations": list(self.active_obligations),
            "stale_claims": list(self.stale_claims),
            "failed_claims": list(self.failed_claims),
            "open_frontier": list(self.open_frontier),
            "evidence_references": list(self.evidence_references),
            "workspace_identity": self.workspace_identity,
            "recovery_state": self.recovery_state,
            "active_leases": list(self.active_leases),
            "required_next_actions": list(self.required_next_actions),
            "timestamp": self.timestamp,
            "handoff_hash": self.handoff_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AssuranceHandoff:
        return cls(
            task_id=data["task_id"],
            verified_project_state_ref=data.get("verified_project_state_ref", ""),
            verified_claims=data.get("verified_claims", []),
            active_obligations=data.get("active_obligations", []),
            stale_claims=data.get("stale_claims", []),
            failed_claims=data.get("failed_claims", []),
            open_frontier=data.get("open_frontier", []),
            evidence_references=data.get("evidence_references", []),
            workspace_identity=data.get("workspace_identity", ""),
            recovery_state=data.get("recovery_state"),
            active_leases=data.get("active_leases", []),
            required_next_actions=data.get("required_next_actions", []),
            timestamp=data.get("timestamp"),
            handoff_id=data.get("handoff_id"),
            handoff_hash=data.get("handoff_hash"),
        )

    def to_markdown(self) -> str:
        lines = [
            f"# S-Class Assurance Handoff ({self.task_id})",
            f"**Handoff ID**: `{self.handoff_id}` | **Workspace**: `{self.workspace_identity}`",
            f"**State Ref**: `{self.verified_project_state_ref}`",
            "",
            "## 1. Verified Claims",
        ]
        if self.verified_claims:
            for c in self.verified_claims:
                lines.append(f"- [x] `{c.get('claim_id')}`: {c.get('statement')}")
        else:
            lines.append("- (No claims verified yet)")

        lines.extend(["", "## 2. Active Technical Obligations"])
        if self.active_obligations:
            for ob in self.active_obligations:
                status = ob.get("status", "PENDING")
                lines.append(f"- [{ 'x' if status == 'SATISFIED' else ' ' }] `{ob.get('obligation_id')}`: {ob.get('title')} ({status})")
        else:
            lines.append("- (None)")

        lines.extend(["", "## 3. Open Verification Frontier"])
        if self.open_frontier:
            for f in self.open_frontier:
                lines.append(f"- [!] `{f.get('target')}`: {f.get('reason')}")
        else:
            lines.append("- (Clean frontier: zero unresolved items)")

        lines.extend(["", "## 4. Required Next Actions"])
        if self.required_next_actions:
            for a in self.required_next_actions:
                lines.append(f"1. {a}")
        else:
            lines.append("- (No immediate actions required)")

        return "\n".join(lines)


def assemble_assurance_handoff(
    task_id: str,
    state: VerifiedProjectState,
    obligations: Optional[List[TechnicalObligation]] = None,
    active_leases: Optional[List[Dict[str, Any]]] = None,
    recovery_state: Optional[Dict[str, Any]] = None,
    required_next_actions: Optional[List[str]] = None,
) -> AssuranceHandoff:
    """
    Constructs an authoritative AssuranceHandoff object from canonical S-Class state.
    """
    stale = list(state.invalidated_claims)
    failed = [
        c for c in state.invalidated_claims
        if "fail" in str(c.get("reason", "")).lower() or c.get("status") == "FAILED"
    ]
    for cid in state.rejected_claims:
        if not any((c.get("claim_id") or c.get("id")) == cid for c in failed):
            failed.append({"claim_id": cid, "status": "FAILED", "reason": "Claim rejected"})
    ev_refs = [
        ev.get("receipt_id") or ev.get("id") or "ev"
        for ev in state.evidence
        if isinstance(ev, dict)
    ]
    obs_dicts = [
        o.to_dict() if hasattr(o, "to_dict") else dict(o)
        for o in (obligations or [])
    ]

    return AssuranceHandoff(
        task_id=task_id,
        verified_project_state_ref=state.current_revision or state.repository_checkpoint or "ref_head",
        verified_claims=list(state.verified_claims),
        active_obligations=obs_dicts,
        stale_claims=stale,
        failed_claims=failed,
        open_frontier=list(state.frontier),
        evidence_references=ev_refs,
        workspace_identity=state.workspace or state.workspace_identity or "",
        recovery_state=recovery_state,
        active_leases=list(active_leases or []),
        required_next_actions=list(required_next_actions or []),
    )
