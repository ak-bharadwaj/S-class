"""
S-Class Platform Archetype: Cursor IDE
Principles:
- Preserve fast, fluid inline completions, composer edits, and editor responsiveness.
- Compensate for unverified multi-file diffs, hallucinated imports, and syntax regressions.
- Avoid synchronous blocking during typing flow or intrusive micro-prompts in the IDE.
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


def get_cursor_profile() -> PlatformProfile:
    """Generate canonical Cursor platform profile based on IDE integration characteristics."""
    return PlatformProfile(
        platform_id="cursor",
        version="0.45.0",
        capabilities=[
            "inline_completion",
            "composer_multi_file",
            "terminal_execution",
            "quick_diff",
            "chat_context",
            "filesystem_manipulation",
        ],
        execution_style=ExecutionStyle.INTERACTIVE_REPL.value,
        context_style=ContextStyle.ROLLING_COMPACTION.value,
        concurrency_model=ConcurrencyModel.SEQUENTIAL_SINGLE_THREAD.value,
        long_horizon_model=LongHorizonModel.CHECKPOINTED_EPISODES.value,
        checkpoint_model=CheckpointModel.GIT_COMMIT_TREE.value,
        tool_model=ToolModel.HYBRID.value,
        native_strengths=[
            "fast inline code generation",
            "fluid editor responsiveness",
            "composer multi-file editing",
            "interactive diff preview",
        ],
        metadata={
            "vendor": "Anysphere",
            "ide_base": "VSCode",
            "composer_enabled": True,
        },
    )


def get_cursor_compensation_policy() -> CompensationPolicy:
    """
    Generate Cursor compensation policy.
    
    Preserves fluid typing and composer velocity; compensates multi-file diff verification
    and import validity; avoids blocking interactive editor keystrokes.
    """
    return CompensationPolicy(
        preserve=[
            "fast inline code generation",
            "fluid editor responsiveness",
            "interactive diff preview",
            "inline typing flow",
        ],
        compensate=[
            "unverified multi-file diffs",
            "hallucinated imports",
            "syntax regressions",
            "file boundary checks",
            "evidence verification",
        ],
        avoid_interference=[
            "slow synchronous barriers during typing",
            "blocking cursor navigation",
            "unnecessary micro-prompts",
            "huge context injection",
        ],
        observation_level=ObservationLevel.PASSIVE.value,
        verification_level=VerificationLevel.STANDARD.value,
        checkpoint_level=CheckpointLevel.ACTION_BOUNDARY.value,
        context_budget=1536,
        interruption_policy=InterruptionPolicy.FATAL_ONLY.value,
        escalation_policy=EscalationPolicy.WARN_AND_AUDIT.value,
        metadata={
            "archetype": "cursor",
            "motto": "Preserve fluid IDE speed; verify multi-file diffs silently.",
        },
    )
