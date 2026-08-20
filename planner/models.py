"""D8 Autonomous Planning Substrate - Domain Models (§3.6, §8.1).

Deeply immutable dataclasses for state projection, strategy representation,
fencing-bound runtime envelopes, risk assessment, and lease management.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Optional, Sequence, Tuple

from domain.models import (
    _freeze_nested,
    _validate_iso8601,
    _validate_pattern,
)
from domain.types import (
    HEX_40_PATTERN,
    HEX_64_PATTERN,
    OBLIGATION_ID_PATTERN,
    TASK_ID_PATTERN,
)
from controller.token import ExecutionContext, compute_action_digest


class PlanStatus(str, Enum):
    """Lifecycle states of a plan artifact according to D0 (§8.1)."""
    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class PlanNode:
    """An individual execution node in the planner's DAG strategy."""
    node_id: str
    obligation_id: str
    action_type: str
    target: str
    purpose: str
    execution_context: ExecutionContext
    parameters: Mapping[str, Any] = field(default_factory=dict)
    prerequisites: Tuple[str, ...] = field(default_factory=tuple)
    estimated_cost_usd: float = 0.0
    timeout_seconds: int = 60
    node_digest: str = ""

    def __post_init__(self):
        if not self.node_id:
            raise ValueError("node_id cannot be empty.")
        _validate_pattern(self.obligation_id, OBLIGATION_ID_PATTERN, "obligation_id")
        if not self.action_type:
            raise ValueError("action_type cannot be empty.")
        if not self.target:
            raise ValueError("target cannot be empty.")
        if not self.purpose:
            raise ValueError("purpose cannot be empty.")
        if not isinstance(self.execution_context, ExecutionContext):
            raise TypeError("execution_context must be an ExecutionContext instance.")
        if self.estimated_cost_usd < 0.0:
            raise ValueError("estimated_cost_usd cannot be negative.")
        if self.timeout_seconds < 1:
            raise ValueError("timeout_seconds must be >= 1.")

        object.__setattr__(self, "prerequisites", tuple(self.prerequisites))
        object.__setattr__(self, "parameters", _freeze_nested(self.parameters))

        expected_digest = compute_action_digest(
            action_type=self.action_type,
            target=self.target,
            purpose=self.purpose,
            parameters=self.parameters,
        )
        if not self.node_digest:
            object.__setattr__(self, "node_digest", expected_digest)
        elif self.node_digest != expected_digest:
            raise ValueError(f"node_digest mismatch: '{self.node_digest}' != '{expected_digest}'")
        _validate_pattern(self.node_digest, HEX_64_PATTERN, "node_digest")


@dataclass(frozen=True)
class ExecutionStrategyArtifact:
    """Canonical executable DAG artifact containing exact nodes and dependency edges."""
    strategy_id: str
    plan_id: str
    plan_revision: int
    nodes: Tuple[PlanNode, ...]
    dependency_edges: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)
    strategy_digest: str = ""

    def __post_init__(self):
        if not self.strategy_id:
            raise ValueError("strategy_id cannot be empty.")
        if not self.plan_id:
            raise ValueError("plan_id cannot be empty.")
        if not isinstance(self.plan_revision, int) or self.plan_revision < 1:
            raise ValueError("plan_revision must be an integer >= 1.")
        if not self.nodes:
            raise ValueError("Execution strategy must contain at least one node.")
        for node in self.nodes:
            if not isinstance(node, PlanNode):
                raise TypeError("nodes must contain only PlanNode instances.")

        object.__setattr__(self, "nodes", tuple(self.nodes))
        object.__setattr__(self, "dependency_edges", tuple(self.dependency_edges))


@dataclass(frozen=True)
class PlannerStateContent:
    """Pure domain state consumed by D8. Exclusively determines planner_state_digest."""
    task_id: str
    milestones: Tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    claims: Tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    obligations: Tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    executable_frontier: Tuple[str, ...] = field(default_factory=tuple)
    blocked_frontier: Tuple[str, ...] = field(default_factory=tuple)
    evidence_digests: Tuple[str, ...] = field(default_factory=tuple)
    active_policies: Tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    state_version: int = 0
    state_digest: str = ""

    def __post_init__(self):
        _validate_pattern(self.task_id, TASK_ID_PATTERN, "task_id")
        if not isinstance(self.state_version, int) or self.state_version < 0:
            raise ValueError("state_version must be an integer >= 0.")
        if self.state_digest:
            _validate_pattern(self.state_digest, HEX_64_PATTERN, "state_digest")

        object.__setattr__(self, "milestones", _freeze_nested(self.milestones))
        object.__setattr__(self, "claims", _freeze_nested(self.claims))
        object.__setattr__(self, "obligations", _freeze_nested(self.obligations))
        object.__setattr__(self, "executable_frontier", tuple(self.executable_frontier))
        object.__setattr__(self, "blocked_frontier", tuple(self.blocked_frontier))
        object.__setattr__(self, "evidence_digests", tuple(self.evidence_digests))
        object.__setattr__(self, "active_policies", _freeze_nested(self.active_policies))


@dataclass(frozen=True)
class PlannerStateProjectionMetadata:
    """Volatile telemetry metadata strictly excluded from planner_state_digest."""
    projected_at: str
    projection_latency_ms: float = 0.0
    worker_id: str = ""

    def __post_init__(self):
        _validate_iso8601(self.projected_at, "projected_at")
        if self.projection_latency_ms < 0.0:
            raise ValueError("projection_latency_ms cannot be negative.")


@dataclass(frozen=True)
class PlannerStateView:
    """Combined immutable state view delivered to CandidateGenerator and PlanEvaluator."""
    content: PlannerStateContent
    metadata: PlannerStateProjectionMetadata
    planner_state_digest: str = ""

    def __post_init__(self):
        if not isinstance(self.content, PlannerStateContent):
            raise TypeError("content must be a PlannerStateContent instance.")
        if not isinstance(self.metadata, PlannerStateProjectionMetadata):
            raise TypeError("metadata must be a PlannerStateProjectionMetadata instance.")
        if self.planner_state_digest:
            _validate_pattern(self.planner_state_digest, HEX_64_PATTERN, "planner_state_digest")


@dataclass(frozen=True)
class PlanRuntimeEnvelope:
    """Runtime envelope binding the D0 Plan, ExecutionStrategy, and active fencing coordinates."""
    strategy: ExecutionStrategyArtifact
    fencing_token: int
    lease_epoch: int
    owner_id: str
    state_version: int
    state_digest: str
    planner_state_digest: str
    plan_semantic_fingerprint: str = ""
    execution_strategy_fingerprint: str = ""
    status: PlanStatus = PlanStatus.DRAFT

    def __post_init__(self):
        if not isinstance(self.strategy, ExecutionStrategyArtifact):
            raise TypeError("strategy must be an ExecutionStrategyArtifact instance.")
        if not isinstance(self.fencing_token, int) or self.fencing_token < 0:
            raise ValueError("fencing_token must be an integer >= 0.")
        if not isinstance(self.lease_epoch, int) or self.lease_epoch < 0:
            raise ValueError("lease_epoch must be an integer >= 0.")
        if not self.owner_id:
            raise ValueError("owner_id cannot be empty.")
        if not isinstance(self.state_version, int) or self.state_version < 0:
            raise ValueError("state_version must be an integer >= 0.")
        _validate_pattern(self.state_digest, HEX_64_PATTERN, "state_digest")
        _validate_pattern(self.planner_state_digest, HEX_64_PATTERN, "planner_state_digest")
        if self.plan_semantic_fingerprint:
            _validate_pattern(self.plan_semantic_fingerprint, HEX_64_PATTERN, "plan_semantic_fingerprint")
        if self.execution_strategy_fingerprint:
            _validate_pattern(self.execution_strategy_fingerprint, HEX_64_PATTERN, "execution_strategy_fingerprint")
        if not isinstance(self.status, PlanStatus):
            raise TypeError(f"Invalid PlanStatus: {self.status}")


@dataclass(frozen=True)
class PlannerRiskAssessment:
    """Detailed multidimensional risk assessment for candidate plans."""
    security_risk: float
    irreversible_risk: float
    blast_radius: float
    policy_violation_risk: float
    budget_overrun_risk: float
    dependency_violation_risk: float
    unverified_claim_risk: float
    is_acceptable: bool = True
    rejection_reasons: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self):
        for name in (
            "security_risk",
            "irreversible_risk",
            "blast_radius",
            "policy_violation_risk",
            "budget_overrun_risk",
            "dependency_violation_risk",
            "unverified_claim_risk",
        ):
            val = getattr(self, name)
            if not isinstance(val, (int, float)) or val < 0.0 or val > 1.0:
                raise ValueError(f"{name} must be a float in [0.0, 1.0], got {val}")
        object.__setattr__(self, "rejection_reasons", tuple(self.rejection_reasons))


@dataclass(frozen=True)
class PlanQualityScore:
    """Scalar evaluation and Pareto-ranking metrics for a candidate plan."""
    risk_assessment: PlannerRiskAssessment
    expected_cost_usd: float
    parallelism_factor: float
    estimated_duration_seconds: int
    claim_coverage: float
    progress_potential: float
    pareto_rank: int = 0

    def __post_init__(self):
        if not isinstance(self.risk_assessment, PlannerRiskAssessment):
            raise TypeError("risk_assessment must be a PlannerRiskAssessment instance.")
        if self.expected_cost_usd < 0.0:
            raise ValueError("expected_cost_usd cannot be negative.")
        if self.parallelism_factor < 0.0:
            raise ValueError("parallelism_factor cannot be negative.")
        if self.estimated_duration_seconds < 0:
            raise ValueError("estimated_duration_seconds cannot be negative.")
        if not (0.0 <= self.claim_coverage <= 1.0):
            raise ValueError("claim_coverage must be between 0.0 and 1.0.")
        if self.progress_potential < 0.0:
            raise ValueError("progress_potential cannot be negative.")
        if self.pareto_rank < 0:
            raise ValueError("pareto_rank cannot be negative.")


@dataclass(frozen=True)
class GenerationProvenance:
    """Provenance tracking for plan candidate synthesis."""
    generator_id: str
    model_id: str
    prompt_digest: str
    temperature: float
    generated_at: str
    candidate_index: int

    def __post_init__(self):
        if not self.generator_id:
            raise ValueError("generator_id cannot be empty.")
        if not self.model_id:
            raise ValueError("model_id cannot be empty.")
        _validate_pattern(self.prompt_digest, HEX_64_PATTERN, "prompt_digest")
        if self.temperature < 0.0:
            raise ValueError("temperature cannot be negative.")
        _validate_iso8601(self.generated_at, "generated_at")
        if self.candidate_index < 0:
            raise ValueError("candidate_index cannot be negative.")


@dataclass(frozen=True)
class PlanningLease:
    """Durable planning ownership lease for cross-worker mutual exclusion."""
    task_id: str
    owner_id: str
    lease_epoch: int
    fencing_token: int
    acquired_at: str
    expires_at: str
    is_active: bool = True

    def __post_init__(self):
        _validate_pattern(self.task_id, TASK_ID_PATTERN, "task_id")
        if not self.owner_id:
            raise ValueError("owner_id cannot be empty.")
        if not isinstance(self.lease_epoch, int) or self.lease_epoch < 0:
            raise ValueError("lease_epoch must be an integer >= 0.")
        if not isinstance(self.fencing_token, int) or self.fencing_token < 0:
            raise ValueError("fencing_token must be an integer >= 0.")
        _validate_iso8601(self.acquired_at, "acquired_at")
        _validate_iso8601(self.expires_at, "expires_at")
