"""
S-Class Platform Profile (B.3.1)

Defines generic PlatformProfile describing an AI coding platform's architecture,
capabilities, execution styles, and native strengths.

Architectural Invariant:
Permanent assumptions (e.g. 'Codex is always best at long horizon',
'Claude is always best at reasoning') are NOT encoded in the core schema.
Those are current working hypotheses instantiated in archetypes, not immutable facts.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, List, Optional, Set, Union


class ExecutionStyle(str, Enum):
    """Execution modality of the host platform."""
    AUTONOMOUS_LONG_HORIZON = "autonomous_long_horizon"
    DEEP_REASONING_STEP = "deep_reasoning_step"
    PARALLEL_SWARM = "parallel_swarm"
    INTERACTIVE_REPL = "interactive_repl"
    SYNCHRONOUS_SINGLE_TURN = "synchronous_single_turn"
    CUSTOM = "custom"


class ContextStyle(str, Enum):
    """Context window management style."""
    PERSISTENT_SESSION = "persistent_session"
    STATELESS_WINDOW = "stateless_window"
    HIERARCHICAL_SUMMARY = "hierarchical_summary"
    ROLLING_COMPACTION = "rolling_compaction"
    DELEGATED_CONTEXT = "delegated_context"
    CUSTOM = "custom"


class ConcurrencyModel(str, Enum):
    """Concurrency architecture of the agent harness."""
    PARALLEL_AGENTS = "parallel_agents"
    SEQUENTIAL_SINGLE_THREAD = "sequential_single_thread"
    COOPERATIVE_SUBAGENTS = "cooperative_subagents"
    ISOLATED_WORKERS = "isolated_workers"
    HYBRID_SWARM = "hybrid_swarm"
    CUSTOM = "custom"


class LongHorizonModel(str, Enum):
    """How the platform handles multi-hour or multi-step horizon work."""
    AUTONOMOUS_SESSION = "autonomous_session"
    CHECKPOINTED_EPISODES = "checkpointed_episodes"
    SUBAGENT_TREE = "subagent_tree"
    STATELESS_RESTARTS = "stateless_restarts"
    RECURSIVE_DECOMPOSITION = "recursive_decomposition"
    CUSTOM = "custom"


class CheckpointModel(str, Enum):
    """Checkpointing and state restoration strategy."""
    HARNESS_NATIVE = "harness_native"
    GIT_COMMIT_TREE = "git_commit_tree"
    EXTERNAL_STATE_STORE = "external_state_store"
    MICRO_CHECKPOINTS = "micro_checkpoints"
    NONE = "none"
    CUSTOM = "custom"


class ToolModel(str, Enum):
    """Tool invocation and dispatch paradigm."""
    AGENTS_API_TOOLS = "agents_api_tools"
    MCP_CLIENT_TOOLS = "mcp_client_tools"
    ACP_PERMISSIONED_TOOLS = "acp_permissioned_tools"
    NATIVE_SHELL = "native_shell"
    HYBRID = "hybrid"
    CUSTOM = "custom"


@dataclass(frozen=True)
class PlatformProfile:
    """
    Generic platform architectural profile.
    
    Captures platform capabilities, execution paradigms, and native strengths
    without hardcoding immutable assumptions about platform superiority.
    """
    platform_id: str
    version: str = "1.0.0"
    capabilities: List[str] = field(default_factory=list)
    execution_style: str = ExecutionStyle.AUTONOMOUS_LONG_HORIZON.value
    context_style: str = ContextStyle.PERSISTENT_SESSION.value
    concurrency_model: str = ConcurrencyModel.SEQUENTIAL_SINGLE_THREAD.value
    long_horizon_model: str = LongHorizonModel.AUTONOMOUS_SESSION.value
    checkpoint_model: str = CheckpointModel.HARNESS_NATIVE.value
    tool_model: str = ToolModel.NATIVE_SHELL.value
    native_strengths: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.platform_id or not str(self.platform_id).strip():
            raise ValueError("platform_id must be a non-empty string")
        if not self.version or not str(self.version).strip():
            raise ValueError("version must be a non-empty string")

    def has_capability(self, capability: str) -> bool:
        """Check if platform declares a specific capability."""
        if not capability or not str(capability).strip():
            return False
        cap_clean = capability.strip().lower()
        return any(c.strip().lower() == cap_clean for c in self.capabilities)

    def has_strength(self, strength: str) -> bool:
        """Check if platform has a specific declared native strength."""
        if not strength or not str(strength).strip():
            return False
        str_clean = strength.strip().lower()
        return any(s.strip().lower() == str_clean for s in self.native_strengths)

    def clone_with(self, **overrides) -> PlatformProfile:
        """Create a modified copy of this profile."""
        data = self.to_dict()
        data.update(overrides)
        return PlatformProfile.from_dict(data)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize profile to dictionary."""
        return {
            "platform_id": self.platform_id,
            "version": self.version,
            "capabilities": list(self.capabilities),
            "execution_style": str(self.execution_style),
            "context_style": str(self.context_style),
            "concurrency_model": str(self.concurrency_model),
            "long_horizon_model": str(self.long_horizon_model),
            "checkpoint_model": str(self.checkpoint_model),
            "tool_model": str(self.tool_model),
            "native_strengths": list(self.native_strengths),
            "metadata": dict(self.metadata),
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize profile to JSON formatted string."""
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> PlatformProfile:
        """Construct PlatformProfile from dictionary."""
        return cls(
            platform_id=str(d.get("platform_id", "generic")),
            version=str(d.get("version", "1.0.0")),
            capabilities=list(d.get("capabilities", [])),
            execution_style=str(d.get("execution_style", ExecutionStyle.AUTONOMOUS_LONG_HORIZON.value)),
            context_style=str(d.get("context_style", ContextStyle.PERSISTENT_SESSION.value)),
            concurrency_model=str(d.get("concurrency_model", ConcurrencyModel.SEQUENTIAL_SINGLE_THREAD.value)),
            long_horizon_model=str(d.get("long_horizon_model", LongHorizonModel.AUTONOMOUS_SESSION.value)),
            checkpoint_model=str(d.get("checkpoint_model", CheckpointModel.HARNESS_NATIVE.value)),
            tool_model=str(d.get("tool_model", ToolModel.NATIVE_SHELL.value)),
            native_strengths=list(d.get("native_strengths", [])),
            metadata=dict(d.get("metadata", {})),
        )

    @classmethod
    def from_json(cls, s: str) -> PlatformProfile:
        """Construct PlatformProfile from JSON string."""
        return cls.from_dict(json.loads(s))
