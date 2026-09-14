"""
S-Class Platform Archetype: Anthropic Claude Code

Claude Code is built around deep autonomous work with checkpoints, subagents,
hooks and background tasks. Anthropic also provides an Agent SDK exposing core
tools, context management and permissions.

S-Class Principle:
"Let Claude spend intelligence on reasoning; S-Class handles the control bookkeeping around it."
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


def get_claude_code_profile() -> PlatformProfile:
    """Generate canonical Claude Code platform profile based on SDK and architectural features."""
    return PlatformProfile(
        platform_id="claude_code",
        version="2026.1",
        capabilities=[
            "deep_reasoning",
            "context_synthesis",
            "architecture_analysis",
            "careful_implementation",
            "deliberate_review",
            "agent_sdk",
            "checkpoints",
            "subagents",
            "hooks",
            "background_tasks",
            "mcp_support",
        ],
        execution_style=ExecutionStyle.DEEP_REASONING_STEP.value,
        context_style=ContextStyle.ROLLING_COMPACTION.value,
        concurrency_model=ConcurrencyModel.COOPERATIVE_SUBAGENTS.value,
        long_horizon_model=LongHorizonModel.CHECKPOINTED_EPISODES.value,
        checkpoint_model=CheckpointModel.GIT_COMMIT_TREE.value,
        tool_model=ToolModel.MCP_CLIENT_TOOLS.value,
        native_strengths=[
            "deep reasoning",
            "context synthesis",
            "architecture analysis",
            "careful implementation",
            "deliberate review",
        ],
        metadata={
            "vendor": "Anthropic",
            "sdk": "Anthropic Agent SDK",
            "architecture_focus": "deep reasoning with native hooks",
        },
    )


def get_claude_code_compensation_policy() -> CompensationPolicy:
    """
    Generate Claude Code compensation policy.
    
    Principle: Let Claude spend intelligence on reasoning; S-Class handles control bookkeeping around it.
    Suppresses redundant history injection and state re-derivation.
    """
    return CompensationPolicy(
        preserve=[
            "deep reasoning",
            "context synthesis",
            "architecture analysis",
            "careful implementation",
            "deliberate review",
        ],
        compensate=[
            "execution bookkeeping",
            "context duplication",
            "token waste",
            "slow/overbroad validation",
            "state tracking",
        ],
        avoid_interference=[
            "feeding redundant history",
            "making Claude re-derive known state",
            "interrupting reasoning unnecessarily",
        ],
        observation_level=ObservationLevel.PASSIVE.value,  # S-Class handles bookkeeping silently
        verification_level=VerificationLevel.CONTINUOUS.value, # Targeted fast background validation
        checkpoint_level=CheckpointLevel.STATE_CHANGE.value,  # S-Class handles state tracking
        context_budget=1024,  # Strictly trimmed delta state, zero redundant history
        interruption_policy=InterruptionPolicy.POLICY_VIOLATION_ONLY.value,
        escalation_policy=EscalationPolicy.FAIL_CLOSED.value,
        metadata={
            "archetype": "claude_code",
            "motto": "Let Claude spend intelligence on reasoning; S-Class handles the control bookkeeping around it.",
            "deduplicate_history": True,
            "externalize_state_tracking": True,
        },
    )
