"""
S-Class Platform Archetype: OpenAI Codex

Current evidence shows Codex is increasingly optimized around long-running work,
parallel agents, persistent sessions and a continuously improved harness. OpenAI
reports that a large majority of sampled users delegate tasks lasting over an hour,
and its current Agents API exposes long sessions, subagents, and context management.

S-Class Principle:
"Let Codex run. Make the result more trustworthy."
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


def get_codex_profile() -> PlatformProfile:
    """Generate canonical Codex platform profile based on empirical harness characteristics."""
    return PlatformProfile(
        platform_id="codex",
        version="2026.1",
        capabilities=[
            "long_horizon_autonomy",
            "repository_exploration",
            "terminal_execution",
            "multi_step_iteration",
            "parallel_work",
            "agents_api",
            "subagents",
            "persistent_sessions",
            "filesystem_manipulation",
        ],
        execution_style=ExecutionStyle.AUTONOMOUS_LONG_HORIZON.value,
        context_style=ContextStyle.PERSISTENT_SESSION.value,
        concurrency_model=ConcurrencyModel.PARALLEL_AGENTS.value,
        long_horizon_model=LongHorizonModel.AUTONOMOUS_SESSION.value,
        checkpoint_model=CheckpointModel.HARNESS_NATIVE.value,
        tool_model=ToolModel.AGENTS_API_TOOLS.value,
        native_strengths=[
            "long-horizon autonomy",
            "repository exploration",
            "terminal execution",
            "multi-step iteration",
            "parallel work",
        ],
        metadata={
            "vendor": "OpenAI",
            "harness_generation": "Agents API v2",
            "empirical_horizon_target_hours": 1.5,
        },
    )


def get_codex_compensation_policy() -> CompensationPolicy:
    """
    Generate Codex compensation policy.
    
    Principle: Let Codex run. Make the result more trustworthy.
    Preserves autonomy; compensates accuracy and regression gating; avoids micro-interruptions.
    """
    return CompensationPolicy(
        preserve=[
            "long-horizon autonomy",
            "repository exploration",
            "terminal execution",
            "multi-step iteration",
            "parallel work",
        ],
        compensate=[
            "accuracy",
            "regression detection",
            "scope drift",
            "verification",
            "fast feedback",
            "evidence quality",
        ],
        avoid_interference=[
            "unnecessary interruptions",
            "duplicate planning",
            "huge context injection",
            "constant micro-checkpoints",
        ],
        observation_level=ObservationLevel.SAMPLED.value,
        verification_level=VerificationLevel.STANDARD.value,
        checkpoint_level=CheckpointLevel.MILESTONE_ONLY.value,
        context_budget=2048,  # Avoids huge context injection while providing fast feedback
        interruption_policy=InterruptionPolicy.FATAL_ONLY.value,
        escalation_policy=EscalationPolicy.COMPENSATING_ACTION.value,
        metadata={
            "archetype": "codex",
            "motto": "Let Codex run. Make the result more trustworthy.",
            "suppress_planning_interventions": True,
        },
    )
