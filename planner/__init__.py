from planner.models import (
    Plan,
    PlanStatus,
    PlanNode,
    ExecutionStrategyArtifact,
    PlannerStateContent,
    PlannerStateProjectionMetadata,
    PlannerStateView,
    PlanRuntimeEnvelope,
    PlannerRiskAssessment,
    PlanQualityScore,
    GenerationProvenance,
    PlanningLease,
)
from planner.fingerprint import (
    canonicalize_json,
    compute_plan_semantic_fingerprint,
    compute_execution_strategy_fingerprint,
    compute_planner_state_digest,
    SCLASS_PLAN_INTENT_DOMAIN_SEPARATOR,
    SCLASS_EXEC_STRATEGY_DOMAIN_SEPARATOR,
    SCLASS_PLANNER_STATE_DOMAIN_SEPARATOR,
)
from planner.lease import (
    PlanningLeaseManager,
    LeaseAcquisitionError,
    LeaseValidationError,
    LeaseCorruptionError,
)
from planner.projector import StateProjector
from planner.generator import (
    CandidateGenerator,
    DeterministicRuleGenerator,
    GeneratorProtocol,
)
from planner.dependency import (
    DependencyPlanner,
    DependencyCycleError,
)
from planner.evaluator import (
    HardConstraintGate,
    PlanEvaluator,
    MAX_GOVERNED_BLAST_RADIUS,
)
from planner.convergence import (
    ConvergenceMonitor,
    ReplanningBudgetExceededError,
    PlanOscillationDetectedError,
    SpontaneousReplanningError,
)
from planner.emitter import ProposalEmitter
from planner.session import (
    PlannerSession,
    NoAdmissiblePlanError,
)

# Backwards-compatible legacy workflow exports
try:
    import importlib.util
    import os
    _root_planner_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "planner.py")
    if os.path.exists(_root_planner_path):
        _spec = importlib.util.spec_from_file_location("_legacy_root_planner", _root_planner_path)
        if _spec and _spec.loader:
            _legacy_mod = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_legacy_mod)
            WorkflowProfile = getattr(_legacy_mod, "WorkflowProfile", None)
            WorkflowPlan = getattr(_legacy_mod, "WorkflowPlan", None)
            PROFILE_SEQUENCES = getattr(_legacy_mod, "PROFILE_SEQUENCES", None)
            PROFILE_TRANSITIONS = getattr(_legacy_mod, "PROFILE_TRANSITIONS", None)
            MetaPlanner = getattr(_legacy_mod, "MetaPlanner", None)
except Exception:
    pass

__all__ = [
    "PlanStatus",
    "PlanNode",
    "ExecutionStrategyArtifact",
    "PlannerStateContent",
    "PlannerStateProjectionMetadata",
    "PlannerStateView",
    "PlanRuntimeEnvelope",
    "PlannerRiskAssessment",
    "PlanQualityScore",
    "GenerationProvenance",
    "PlanningLease",
    "canonicalize_json",
    "compute_plan_semantic_fingerprint",
    "compute_execution_strategy_fingerprint",
    "compute_planner_state_digest",
    "SCLASS_PLAN_INTENT_DOMAIN_SEPARATOR",
    "SCLASS_EXEC_STRATEGY_DOMAIN_SEPARATOR",
    "SCLASS_PLANNER_STATE_DOMAIN_SEPARATOR",
    "PlanningLeaseManager",
    "LeaseAcquisitionError",
    "LeaseValidationError",
    "StateProjector",
    "CandidateGenerator",
    "DeterministicRuleGenerator",
    "GeneratorProtocol",
    "DependencyPlanner",
    "DependencyCycleError",
    "HardConstraintGate",
    "PlanEvaluator",
    "MAX_GOVERNED_BLAST_RADIUS",
    "ConvergenceMonitor",
    "ReplanningBudgetExceededError",
    "PlanOscillationDetectedError",
    "SpontaneousReplanningError",
    "ProposalEmitter",
    "PlannerSession",
    "NoAdmissiblePlanError",
]
