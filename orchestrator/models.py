"""
S-Class Orchestration Models & Architecture Taxonomy.

Defines the complete canonical data models for:
- 14 Reasoning Modes
- 9 Skill Categories & Skill Playbooks
- 4 Model Tiers & Dynamic Provider Routing
- Governed Plan-as-Artifact (StrategicPlanArtifact, PlanStage, PlanStatus)
- Task Risk, Repository Facts, and Verification Profiles (with zero manufactured facts)
- Bounded Context Slices & Immutable State Snapshots
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Tuple, Dict, Any, Optional, Sequence, Mapping
import hashlib

from domain.models import Obligation, Claim, AssessmentReceipt, Policy
from claim.reducer import ClaimReductionState
from planner.models import PlanStatus


class ReasoningMode(str, Enum):
    """Canonical 14 S-Class Software Engineering Reasoning Modes."""
    DISCOVER = "DISCOVER"
    SPECIFY = "SPECIFY"
    ARCHITECT = "ARCHITECT"
    PLAN = "PLAN"
    DECOMPOSE = "DECOMPOSE"
    IMPLEMENT = "IMPLEMENT"
    VERIFY = "VERIFY"
    DIAGNOSE = "DIAGNOSE"
    REPAIR = "REPAIR"
    REPLAN = "REPLAN"
    REVIEW = "REVIEW"
    REGRESS = "REGRESS"
    CONVERGE = "CONVERGE"
    CLOSE = "CLOSE"
    ESCALATE = "ESCALATE"


class SkillCategory(str, Enum):
    """Canonical 9 Engineering Skill Taxonomy Categories."""
    CORE_ENGINEERING = "CORE_ENGINEERING"
    DOMAIN = "DOMAIN"
    VERIFICATION = "VERIFICATION"
    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"
    REVIEW = "REVIEW"
    DIAGNOSIS = "DIAGNOSIS"
    PRODUCT_UI = "PRODUCT_UI"
    REFERENCE = "REFERENCE"


class ModelTier(str, Enum):
    """Target cognitive capability tier for model routing."""
    REASONING_PRO = "REASONING_PRO"           # Deep architectural reasoning, multi-step planning, diagnosis
    CODE_FAST = "CODE_FAST"                   # Fast, precise code generation and minimal diff formulation
    EVALUATOR_ACCURATE = "EVALUATOR_ACCURATE" # Strict verification evaluation, receipt checks
    LOCAL_DETERMINISTIC = "LOCAL_DETERMINISTIC" # Non-LLM rule/state derivation


class ArtifactType(str, Enum):
    """Expected governed artifact output from a reasoning turn."""
    REPO_INVENTORY = "REPO_INVENTORY"
    SPECIFICATION = "SPECIFICATION"
    ARCHITECTURE_DESIGN = "ARCHITECTURE_DESIGN"
    STRATEGIC_PLAN = "STRATEGIC_PLAN"
    OBLIGATION_DAG = "OBLIGATION_DAG"
    CODE_PATCH = "CODE_PATCH"
    TEST_HARNESS = "TEST_HARNESS"
    ROOT_CAUSE_DIAGNOSIS = "ROOT_CAUSE_DIAGNOSIS"
    REPAIR_PATCH = "REPAIR_PATCH"
    REVISED_PLAN = "REVISED_PLAN"
    REVIEW_REPORT = "REVIEW_REPORT"
    REGRESSION_REPORT = "REGRESSION_REPORT"
    CONVERGENCE_ASSESSMENT = "CONVERGENCE_ASSESSMENT"
    CLOSURE_RECEIPT = "CLOSURE_RECEIPT"
    ESCALATION_RECEIPT = "ESCALATION_RECEIPT"


class SkillAdoptionStatus(str, Enum):
    """Classification of adopted skills relative to S-Class master plan."""
    INTEGRATE = "INTEGRATE"
    ADAPT = "ADAPT"
    REBUILD = "REBUILD"
    REJECT = "REJECT"


@dataclass(frozen=True)
class SkillPlaybook:
    """Deterministic engineering procedure playbook."""
    skill_id: str
    name: str
    category: SkillCategory
    adoption_status: SkillAdoptionStatus
    purpose: str
    prerequisites: Tuple[str, ...]
    inputs: Tuple[str, ...]
    guidelines: Tuple[str, ...]
    procedure: Tuple[str, ...]
    required_capabilities: Tuple[str, ...]
    target_action_type: str
    expected_artifact_type: ArtifactType
    evidence_requirements: Tuple[str, ...]
    applicable_modes: Tuple[ReasoningMode, ...]
    verification_procedure: str


@dataclass(frozen=True)
class PlanStage:
    """A distinct milestone stage within a governed StrategicPlanArtifact."""
    stage_id: str
    title: str
    target_obligation_ids: Tuple[str, ...]
    prerequisite_stage_ids: Tuple[str, ...]
    description: str
    verification_gate: str
    evidence_types_required: Tuple[str, ...] = ("EXECUTION_OBSERVATION",)


@dataclass(frozen=True)
class StrategicPlanArtifact:
    """
    Governed Plan-as-Artifact generated during PLAN / REPLAN modes.
    Contains explicit claims, stages, dependency graph, risks, and verification requirements.
    Validated deterministically outside the LLM.
    """
    plan_id: str
    task_id: str
    version: int
    strategy_name: str
    rationale: str
    plan_claims: Tuple[str, ...]
    stages: Tuple[PlanStage, ...]
    dependency_edges: Tuple[Tuple[str, str], ...]
    evidence_requirements: Tuple[str, ...]
    identified_risks: Tuple[str, ...]
    potential_contradictions: Tuple[str, ...]
    revision_lineage: Tuple[str, ...]
    status: PlanStatus = PlanStatus.DRAFT
    estimated_risk_score: Optional[float] = None
    plan_digest: str = ""
    created_at_iso: str = ""

    def __post_init__(self):
        if not self.plan_digest:
            payload = (
                f"{self.plan_id}:{self.task_id}:{self.version}:{self.strategy_name}:"
                f"{','.join(self.plan_claims)}:{len(self.stages)}"
            )
            digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            object.__setattr__(self, "plan_digest", digest)


@dataclass(frozen=True)
class TaskRiskAssessment:
    """
    Evaluated risk profile of a task slice.
    All fields are None/UNKNOWN unless established by authoritative discovery/policy.
    Zero manufactured default constants.
    """
    criticality_score: Optional[float] = None
    blast_radius: str = "UNKNOWN"
    complexity_score: Optional[float] = None
    requires_formal_verification: Optional[bool] = None


@dataclass(frozen=True)
class RepositoryFacts:
    """
    Discovered facts regarding the target repository and workspace.
    Zero manufactured default constants.
    """
    languages: Tuple[str, ...] = field(default_factory=tuple)
    dirty_working_tree: Optional[bool] = None
    has_test_framework: Optional[bool] = None
    test_framework_name: str = "UNKNOWN"
    estimated_symbol_count: Optional[int] = None


@dataclass(frozen=True)
class VerificationProfile:
    """
    Required verification rigor for claim satisfaction.
    Zero manufactured default constants.
    """
    requires_unit_tests: Optional[bool] = None
    requires_property_tests: Optional[bool] = None
    requires_regression_run: Optional[bool] = None
    requires_security_audit: Optional[bool] = None
    requires_soak_test: Optional[bool] = None


@dataclass(frozen=True)
class ContextSliceSpec:
    """Specifies the exact bounded context to build for a model turn."""
    include_governance_header: bool = True
    target_obligation_ids: Tuple[str, ...] = field(default_factory=tuple)
    target_symbol_files: Tuple[str, ...] = field(default_factory=tuple)
    include_diagnostics: bool = False
    max_diagnostic_lines: int = 15
    include_turn_history: bool = True
    max_turn_history_count: int = 3
    max_total_tokens_budget: int = 4096


@dataclass(frozen=True)
class RoutingDecision:
    """Multi-factor optimization and routing decision output."""
    mode: ReasoningMode
    active_frontier_ids: Tuple[str, ...]
    selected_skills: Tuple[SkillPlaybook, ...]
    target_provider_type: str
    target_model_tier: ModelTier
    reasoning_objective: str
    required_capabilities: Tuple[str, ...]
    expected_artifact_type: ArtifactType
    verification_requirement: str
    context_slice_spec: ContextSliceSpec
    rationale: str


@dataclass(frozen=True)
class OrchestrationStateSnapshot:
    """
    Canonical immutable state snapshot evaluated by the Multi-Factor State Optimizer.
    All state fields are read-only projections of authoritative D1/D2/D4/D8 state.
    """
    task_id: str
    source_sha: str
    policy_version: int
    obligations: Tuple[Obligation, ...] = field(default_factory=tuple)
    claims: Tuple[Claim, ...] = field(default_factory=tuple)
    policies: Tuple[Policy, ...] = field(default_factory=tuple)
    claim_states: Mapping[str, ClaimReductionState] = field(default_factory=dict)
    latest_receipts: Mapping[str, AssessmentReceipt] = field(default_factory=dict)
    ready_obligation_ids: Tuple[str, ...] = field(default_factory=tuple)
    satisfied_obligation_ids: Tuple[str, ...] = field(default_factory=tuple)
    failed_obligation_ids: Tuple[str, ...] = field(default_factory=tuple)
    active_plan: Optional[StrategicPlanArtifact] = None
    repository_facts: RepositoryFacts = field(default_factory=RepositoryFacts)
    task_risk: TaskRiskAssessment = field(default_factory=TaskRiskAssessment)
    verification_profile: VerificationProfile = field(default_factory=VerificationProfile)
    available_providers: Tuple[str, ...] = ("gemini", "openai", "anthropic", "local")
    repair_attempts_by_obligation: Mapping[str, int] = field(default_factory=dict)
    turn_index: int = 1
    max_turns: int = 10
    remaining_budget_units: float = 10.0
    has_unhandled_syntax_error: bool = False
    has_oscillation_detected: bool = False
