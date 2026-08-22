"""
S-Class Orchestrator Models & Taxonomy Definitions.

Defines the 14 reasoning modes, skill playbooks, routing decisions, and state snapshots.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Tuple, Dict, Any, Optional, Sequence

from domain.models import Obligation, Claim, AssessmentReceipt
from claim.reducer import ClaimReductionState


class ReasoningMode(str, Enum):
    """Canonical 14 S-Class Software Engineering Reasoning Modes."""
    DISCOVER = "DISCOVER"
    SPECIFY = "SPECIFY"
    DECOMPOSE = "DECOMPOSE"
    ARCHITECT = "ARCHITECT"
    PLAN = "PLAN"
    IMPLEMENT = "IMPLEMENT"
    VERIFY = "VERIFY"
    DIAGNOSE = "DIAGNOSE"
    REPAIR = "REPAIR"
    REVIEW = "REVIEW"
    REGRESS = "REGRESS"
    CONVERGE = "CONVERGE"
    CLOSE = "CLOSE"
    ESCALATE = "ESCALATE"


@dataclass(frozen=True)
class SkillPlaybook:
    """Deterministic engineering procedure playbook."""
    skill_id: str
    name: str
    purpose: str
    guidelines: Tuple[str, ...]
    required_capabilities: Tuple[str, ...]
    target_action_type: str


@dataclass(frozen=True)
class RoutingDecision:
    """Result of state optimizer routing derivation."""
    mode: ReasoningMode
    active_frontier_ids: Tuple[str, ...]
    selected_skill: Optional[SkillPlaybook]
    target_provider_type: str
    target_model_tier: str
    reasoning_objective: str
    required_capabilities: Tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class OrchestrationStateSnapshot:
    """Canonical immutable state snapshot evaluated by the Optimizer."""
    task_id: str
    source_sha: str
    policy_version: int
    obligations: Tuple[Obligation, ...] = field(default_factory=tuple)
    claims: Tuple[Claim, ...] = field(default_factory=tuple)
    claim_states: Dict[str, ClaimReductionState] = field(default_factory=dict)
    latest_receipts: Dict[str, AssessmentReceipt] = field(default_factory=dict)
    ready_obligation_ids: Tuple[str, ...] = field(default_factory=tuple)
    satisfied_obligation_ids: Tuple[str, ...] = field(default_factory=tuple)
    failed_obligation_ids: Tuple[str, ...] = field(default_factory=tuple)
    repair_attempts_by_obligation: Dict[str, int] = field(default_factory=dict)
    turn_index: int = 1
    max_turns: int = 10
    remaining_budget_units: float = 10.0
    has_unhandled_syntax_error: bool = False
    has_oscillation_detected: bool = False
