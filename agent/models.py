"""
S-Class EOS V11.2 - D7 Agent Integration Models & Data Structures (§8.1, §8.3).
Defines immutable data classes for agent session context, turn responses, tool definitions,
canonical AgentMessage ingress envelopes with RFC 8785 digest chaining, and session audit records.
"""

from __future__ import annotations
import enum
import hashlib
from dataclasses import dataclass, field
from typing import Mapping, Optional, Sequence, Any, Tuple
from domain.models import _validate_pattern, _validate_iso8601, _freeze_nested
from domain.types import HEX_40_PATTERN, HEX_64_PATTERN
from events.serializer import canonicalize_json

GENESIS_DIGEST = "0" * 64
D7_INTERNAL_ACCOUNTING_UNIT = 0.05  # Non-authoritative internal accounting unit per proposal action


class AgentTurnStatus(str, enum.Enum):
    """Lifecycle status of a single agent session turn or terminal state."""
    CONTINUE = "CONTINUE"
    PROPOSE_ACTION = "PROPOSE_ACTION"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    MAX_TURNS_REACHED = "MAX_TURNS_REACHED"
    WORKER_TIMEOUT = "WORKER_TIMEOUT"
    WORKER_DISCONNECT = "WORKER_DISCONNECT"
    STALE_CONTEXT = "STALE_CONTEXT"
    REPOSITORY_MISMATCH = "REPOSITORY_MISMATCH"
    CAPABILITY_VIOLATION = "CAPABILITY_VIOLATION"
    INGRESS_VALIDATION_FAILED = "INGRESS_VALIDATION_FAILED"
    TAMPER_DETECTED = "TAMPER_DETECTED"
    REPLAY_DETECTED = "REPLAY_DETECTED"
    REORDER_DETECTED = "REORDER_DETECTED"
    WORKER_IDENTITY_MISMATCH = "WORKER_IDENTITY_MISMATCH"


def compute_agent_message_preimage(
    session_id: str,
    worker_id: str,
    sequence: int,
    message_type: str,
    payload: Mapping[str, Any],
    previous_digest: str,
) -> bytes:
    """Produces the exact RFC 8785 canonical preimage bytes for an AgentMessage envelope."""
    msg_dict = {
        "session_id": session_id,
        "worker_id": worker_id,
        "sequence": sequence,
        "message_type": message_type,
        "payload": payload,
        "previous_digest": previous_digest,
    }
    return canonicalize_json(msg_dict)


def compute_agent_message_digest(
    session_id: str,
    worker_id: str,
    sequence: int,
    message_type: str,
    payload: Mapping[str, Any],
    previous_digest: str,
) -> str:
    """Computes SHA-256 digest hex string from canonical RFC 8785 AgentMessage preimage."""
    preimage = compute_agent_message_preimage(
        session_id=session_id,
        worker_id=worker_id,
        sequence=sequence,
        message_type=message_type,
        payload=payload,
        previous_digest=previous_digest,
    )
    return hashlib.sha256(preimage).hexdigest()


@dataclass(frozen=True)
class AgentMessage:
    """
    Canonical, cryptographically chained message envelope for ingress and egress turn traffic.
    Provides transcript integrity and hash-chain sequencing (note: does not provide asymmetric identity signatures).
    """
    session_id: str
    worker_id: str
    sequence: int
    message_type: str
    payload: Mapping[str, Any]
    previous_digest: str
    message_digest: str

    def __post_init__(self):
        if not self.session_id or not isinstance(self.session_id, str):
            raise ValueError("session_id must be a non-empty string.")
        if not self.worker_id or not isinstance(self.worker_id, str):
            raise ValueError("worker_id must be a non-empty string.")
        if self.sequence < 0:
            raise ValueError("sequence cannot be negative.")
        if not self.message_type or not isinstance(self.message_type, str):
            raise ValueError("message_type must be a non-empty string.")
        _validate_pattern(self.previous_digest, HEX_64_PATTERN, "previous_digest")
        _validate_pattern(self.message_digest, HEX_64_PATTERN, "message_digest")
        object.__setattr__(self, "payload", _freeze_nested(self.payload))

        # Verify integrity against canonical RFC 8785 preimage
        expected_digest = compute_agent_message_digest(
            session_id=self.session_id,
            worker_id=self.worker_id,
            sequence=self.sequence,
            message_type=self.message_type,
            payload=self.payload,
            previous_digest=self.previous_digest,
        )
        if self.message_digest != expected_digest:
            raise ValueError(
                f"message_digest '{self.message_digest}' does not match computed digest '{expected_digest}'."
            )


def create_agent_message(
    session_id: str,
    worker_id: str,
    sequence: int,
    message_type: str,
    payload: Mapping[str, Any],
    previous_digest: str,
) -> AgentMessage:
    """Helper to construct an AgentMessage with automatically computed RFC 8785 digest."""
    digest = compute_agent_message_digest(
        session_id=session_id,
        worker_id=worker_id,
        sequence=sequence,
        message_type=message_type,
        payload=payload,
        previous_digest=previous_digest,
    )
    return AgentMessage(
        session_id=session_id,
        worker_id=worker_id,
        sequence=sequence,
        message_type=message_type,
        payload=payload,
        previous_digest=previous_digest,
        message_digest=digest,
    )


@dataclass(frozen=True)
class ToolDefinition:
    """Immutable definition of a capability-scoped tool exposed to an AI worker."""
    name: str
    description: str
    parameters_schema: Mapping[str, Any]
    required_capabilities: Tuple[str, ...] = field(default_factory=tuple)
    is_proposal_tool: bool = False

    def __post_init__(self):
        if not self.name or not isinstance(self.name, str):
            raise ValueError("Tool name must be a non-empty string.")
        if not self.description or not isinstance(self.description, str):
            raise ValueError("Tool description must be a non-empty string.")
        if not isinstance(self.parameters_schema, (dict, Mapping)):
            raise TypeError("parameters_schema must be a dictionary or Mapping.")
        object.__setattr__(self, "parameters_schema", _freeze_nested(self.parameters_schema))
        object.__setattr__(self, "required_capabilities", tuple(self.required_capabilities))


@dataclass(frozen=True)
class AgentToolCall:
    """Immutable record of a tool invocation emitted by an AI worker."""
    call_id: str
    tool_name: str
    arguments: Mapping[str, Any]

    def __post_init__(self):
        if not self.call_id or not isinstance(self.call_id, str):
            raise ValueError("call_id must be a non-empty string.")
        if not self.tool_name or not isinstance(self.tool_name, str):
            raise ValueError("tool_name must be a non-empty string.")
        object.__setattr__(self, "arguments", _freeze_nested(self.arguments))


@dataclass(frozen=True)
class AgentToolResult:
    """Immutable result of a tool execution fed back into agent context."""
    call_id: str
    tool_name: str
    success: bool
    result_data: Mapping[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None

    def __post_init__(self):
        if not self.call_id:
            raise ValueError("call_id cannot be empty.")
        if not self.tool_name:
            raise ValueError("tool_name cannot be empty.")
        object.__setattr__(self, "result_data", _freeze_nested(self.result_data))


@dataclass(frozen=True)
class AgentSessionContext:
    """Immutable context snapshot provided to the AI agent on each turn, bound to repository state."""
    session_id: str
    repository_id: str
    source_sha: str
    task_id: str
    objective: str
    frontier_obligation_ids: Tuple[str, ...]
    frontier_details: Tuple[Mapping[str, Any], ...]
    policy_constraints: Tuple[str, ...]
    verification_feedback: Tuple[Mapping[str, Any], ...]
    available_tools: Tuple[ToolDefinition, ...]
    granted_capabilities: Tuple[str, ...]
    turn_index: int = 0
    max_turns: int = 10
    remaining_budget_units: float = 10.0

    def __post_init__(self):
        if not self.session_id:
            raise ValueError("session_id cannot be empty.")
        if not self.repository_id:
            raise ValueError("repository_id cannot be empty.")
        _validate_pattern(self.source_sha, HEX_40_PATTERN, "source_sha")
        if not self.task_id:
            raise ValueError("task_id cannot be empty.")
        if not self.objective:
            raise ValueError("objective cannot be empty.")
        if self.turn_index < 0:
            raise ValueError("turn_index cannot be negative.")
        if self.max_turns <= 0:
            raise ValueError("max_turns must be positive.")
        if self.remaining_budget_units < 0.0:
            raise ValueError("remaining_budget_units cannot be negative.")
        object.__setattr__(self, "frontier_obligation_ids", tuple(self.frontier_obligation_ids))
        object.__setattr__(self, "frontier_details", tuple(_freeze_nested(d) for d in self.frontier_details))
        object.__setattr__(self, "policy_constraints", tuple(self.policy_constraints))
        object.__setattr__(self, "verification_feedback", tuple(_freeze_nested(f) for f in self.verification_feedback))
        object.__setattr__(self, "available_tools", tuple(self.available_tools))
        object.__setattr__(self, "granted_capabilities", tuple(self.granted_capabilities))


@dataclass(frozen=True)
class AgentTurnResponse:
    """Immutable response generated by an AI worker for a single turn."""
    thought: str
    tool_calls: Tuple[AgentToolCall, ...] = field(default_factory=tuple)
    turn_status: AgentTurnStatus = AgentTurnStatus.CONTINUE
    advisory_estimated_cost_usd: float = 0.0

    def __post_init__(self):
        if not isinstance(self.thought, str):
            raise TypeError("thought must be a string.")
        if not isinstance(self.turn_status, AgentTurnStatus):
            raise TypeError("turn_status must be an instance of AgentTurnStatus.")
        if self.advisory_estimated_cost_usd < 0.0:
            raise ValueError("advisory_estimated_cost_usd cannot be negative.")
        object.__setattr__(self, "tool_calls", tuple(self.tool_calls))


@dataclass(frozen=True)
class AgentSessionRecord:
    """
    Immutable audit record of a completed or terminated agent session.
    Note: D7A session state is ephemeral in-memory; durable persistence is governed by D2.
    """
    session_id: str
    repository_id: str
    source_sha: str
    task_id: str
    total_turns: int
    advisory_total_cost_usd: float
    internal_accounting_units: float
    final_status: AgentTurnStatus
    started_at: str
    ended_at: str
    proposed_action_count: int
    turns_transcript: Tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    final_message_digest: str = GENESIS_DIGEST

    def __post_init__(self):
        if not self.session_id:
            raise ValueError("session_id cannot be empty.")
        if not self.repository_id:
            raise ValueError("repository_id cannot be empty.")
        _validate_pattern(self.source_sha, HEX_40_PATTERN, "source_sha")
        if not self.task_id:
            raise ValueError("task_id cannot be empty.")
        if self.total_turns < 0:
            raise ValueError("total_turns cannot be negative.")
        if self.advisory_total_cost_usd < 0.0:
            raise ValueError("advisory_total_cost_usd cannot be negative.")
        if self.internal_accounting_units < 0.0:
            raise ValueError("internal_accounting_units cannot be negative.")
        _validate_iso8601(self.started_at, "started_at")
        _validate_iso8601(self.ended_at, "ended_at")
        if not isinstance(self.final_status, AgentTurnStatus):
            raise TypeError("final_status must be an instance of AgentTurnStatus.")
        _validate_pattern(self.final_message_digest, HEX_64_PATTERN, "final_message_digest")
        object.__setattr__(self, "turns_transcript", tuple(_freeze_nested(t) for t in self.turns_transcript))
