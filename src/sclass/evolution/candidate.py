"""
S-Class Evolution: Evolution Candidate Schema & Hypothesis Edits.
Implements the candidate data model required by Directive Sections 19, 20, and 35:
- EvolutionStatus lifecycle states:
    DRAFT, CRITIC_REJECTED, SMOKE_FAILED, EVALUATED, VERIFICATION_PENDING,
    ADMISSIBLE, ACCEPTED, REJECTED, INVALID, QUARANTINED.
- HypothesisEdit:
    edit_id, component, hypothesis, mechanism, diff, predicted affected tasks,
    predicted risk, predicted cost effect.
- EvolutionCandidate:
    candidate_id, parent_commit, candidate_commit, worktree, round, edits,
    hypotheses, component_set, smoke_result, critic_result, evaluation_id,
    verification_id, status.
"""

from __future__ import annotations
import uuid
import json
import hashlib
from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set


class EvolutionStatus(str, Enum):
    DRAFT = "DRAFT"
    CRITIC_REJECTED = "CRITIC_REJECTED"
    SMOKE_FAILED = "SMOKE_FAILED"
    EVALUATED = "EVALUATED"
    VERIFICATION_PENDING = "VERIFICATION_PENDING"
    ADMISSIBLE = "ADMISSIBLE"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    INVALID = "INVALID"
    QUARANTINED = "QUARANTINED"


@dataclass(frozen=True)
class HypothesisEdit:
    """Hypothesis-driven structural edit proposed for a candidate."""
    edit_id: str
    component: str
    hypothesis: str
    mechanism: str
    diff: str
    predicted_affected_tasks: List[str] = field(default_factory=list)
    predicted_risk: str = "LOW"
    predicted_cost_effect: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> HypothesisEdit:
        return cls(**data)


@dataclass
class EvolutionCandidate:
    """Authoritative representation of a harness evolution candidate."""
    candidate_id: str
    parent_commit: str
    candidate_commit: str
    worktree: str
    round: int
    edits: List[HypothesisEdit] = field(default_factory=list)
    hypotheses: List[str] = field(default_factory=list)
    component_set: Set[str] = field(default_factory=set)
    smoke_result: Optional[Dict[str, Any]] = None
    critic_result: Optional[Dict[str, Any]] = None
    evaluation_id: Optional[str] = None
    verification_id: Optional[str] = None
    status: EvolutionStatus = EvolutionStatus.DRAFT
    score_delta_s: float = 0.0
    cost_delta_c: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "parent_commit": self.parent_commit,
            "candidate_commit": self.candidate_commit,
            "worktree": self.worktree,
            "round": self.round,
            "edits": [e.to_dict() for e in self.edits],
            "hypotheses": list(self.hypotheses),
            "component_set": sorted(list(self.component_set)),
            "smoke_result": self.smoke_result,
            "critic_result": self.critic_result,
            "evaluation_id": self.evaluation_id,
            "verification_id": self.verification_id,
            "status": self.status.value,
            "score_delta_s": self.score_delta_s,
            "cost_delta_c": self.cost_delta_c,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EvolutionCandidate:
        edits = [HypothesisEdit.from_dict(e) for e in data.get("edits", [])]
        st_val = data.get("status", EvolutionStatus.DRAFT.value)
        status = EvolutionStatus(st_val) if st_val in EvolutionStatus._value2member_map_ else EvolutionStatus.INVALID
        return cls(
            candidate_id=data["candidate_id"],
            parent_commit=data.get("parent_commit", ""),
            candidate_commit=data.get("candidate_commit", ""),
            worktree=data.get("worktree", ""),
            round=data.get("round", 0),
            edits=edits,
            hypotheses=data.get("hypotheses", []),
            component_set=set(data.get("component_set", [])),
            smoke_result=data.get("smoke_result"),
            critic_result=data.get("critic_result"),
            evaluation_id=data.get("evaluation_id"),
            verification_id=data.get("verification_id"),
            status=status,
            score_delta_s=float(data.get("score_delta_s", 0.0)),
            cost_delta_c=float(data.get("cost_delta_c", 0.0)),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
        )
