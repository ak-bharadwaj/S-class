"""
S-Class Evolution Subsystem.
Implements the autonomous harness-evolution substrate (RRSI) strictly separated
from live runtime execution and bounded by S-Class assurance verification.
"""

from sclass.evolution.candidate import (
    EvolutionStatus,
    HypothesisEdit,
    EvolutionCandidate,
)
from sclass.evolution.components import (
    ComponentCategory,
    NON_EVOLVABLE_COMPONENTS,
    EVOLVABLE_COMPONENTS,
    is_component_evolvable,
)
from sclass.evolution.history import (
    HistoryEntry,
    EvolutionHistory,
)
from sclass.evolution.analyst import EvolutionAnalyst
from sclass.evolution.critic import (
    CriticResult,
    CandidateCritic,
)
from sclass.evolution.evaluator import (
    TrialOutcome,
    TrialResult,
    SmokeResult,
    CandidateEvaluationReport,
    CandidateEvaluator,
)
from sclass.evolution.calibration import (
    CalibrationRecord,
    NoiseCalibrator,
)
from sclass.evolution.selector import (
    DomainGuards,
    SelectionResult,
    CandidateSelector,
)
from sclass.evolution.domain import (
    DomainDatasets,
    Domain,
    SClassStandardCodingDomain,
)
from sclass.evolution.attribution import (
    AttributionRecord,
    AttributionTracker,
)
from sclass.evolution.frontier import (
    FrontierPoint,
    ParetoFrontier,
)
from sclass.evolution.readjudication import Readjudicator
from sclass.evolution.reevaluation import InfrastructureReevaluator
from sclass.evolution.gitops import (
    WorktreeHandle,
    GitWorktreeManager,
)
from sclass.evolution.engine import EvolutionEngine

__all__ = [
    "EvolutionStatus",
    "HypothesisEdit",
    "EvolutionCandidate",
    "ComponentCategory",
    "NON_EVOLVABLE_COMPONENTS",
    "EVOLVABLE_COMPONENTS",
    "is_component_evolvable",
    "HistoryEntry",
    "EvolutionHistory",
    "EvolutionAnalyst",
    "CriticResult",
    "CandidateCritic",
    "TrialOutcome",
    "TrialResult",
    "SmokeResult",
    "CandidateEvaluationReport",
    "CandidateEvaluator",
    "CalibrationRecord",
    "NoiseCalibrator",
    "DomainGuards",
    "SelectionResult",
    "CandidateSelector",
    "DomainDatasets",
    "Domain",
    "SClassStandardCodingDomain",
    "AttributionRecord",
    "AttributionTracker",
    "FrontierPoint",
    "ParetoFrontier",
    "Readjudicator",
    "InfrastructureReevaluator",
    "WorktreeHandle",
    "GitWorktreeManager",
    "EvolutionEngine",
]
