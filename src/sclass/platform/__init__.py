"""
S-Class Platform Optimization Core (B.3)

Provides platform architecture profiling, compensation policies, performance budgeting,
dynamic control reconciliation, and platform comparative benchmarking.
"""

from __future__ import annotations

from sclass.platform.profile import (
    PlatformProfile,
    ExecutionStyle,
    ContextStyle,
    ConcurrencyModel,
    LongHorizonModel,
    CheckpointModel,
    ToolModel,
)
from sclass.platform.policy import (
    CompensationPolicy,
    ObservationLevel,
    VerificationLevel,
    CheckpointLevel,
    InterruptionPolicy,
    EscalationPolicy,
)
from sclass.platform.budget import (
    PerformanceBudget,
    BudgetLimits,
    OverheadConsumption,
    ReliabilityGain,
)
from sclass.platform.archetypes import (
    get_archetype,
    register_archetype,
    list_archetypes,
    get_codex_profile,
    get_codex_compensation_policy,
    get_claude_code_profile,
    get_claude_code_compensation_policy,
    get_antigravity_profile,
    get_antigravity_compensation_policy,
)
from sclass.platform.engine import (
    PlatformOptimizationEngine,
    ControlPolicy,
)
from sclass.platform.benchmark import (
    PlatformComparisonBenchmark,
    PlatformComparisonResult,
    PlatformMetrics,
    CIThresholds,
    ProductSLA,
    calculate_distribution,
)

__all__ = [
    # Profile
    "PlatformProfile",
    "ExecutionStyle",
    "ContextStyle",
    "ConcurrencyModel",
    "LongHorizonModel",
    "CheckpointModel",
    "ToolModel",
    # Policy
    "CompensationPolicy",
    "ObservationLevel",
    "VerificationLevel",
    "CheckpointLevel",
    "InterruptionPolicy",
    "EscalationPolicy",
    # Budget
    "PerformanceBudget",
    "BudgetLimits",
    "OverheadConsumption",
    "ReliabilityGain",
    # Archetypes
    "get_archetype",
    "register_archetype",
    "list_archetypes",
    "get_codex_profile",
    "get_codex_compensation_policy",
    "get_claude_code_profile",
    "get_claude_code_compensation_policy",
    "get_antigravity_profile",
    "get_antigravity_compensation_policy",
    # Engine
    "PlatformOptimizationEngine",
    "ControlPolicy",
    # Benchmark
    "PlatformComparisonBenchmark",
    "PlatformComparisonResult",
    "PlatformMetrics",
    "CIThresholds",
    "ProductSLA",
    "calculate_distribution",
]
