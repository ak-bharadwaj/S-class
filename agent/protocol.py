"""
S-Class EOS V11.2 - D7 Agent Worker Protocol & Inbound Message Ingress (§8.1, §8.3).
Defines the abstract interface seam for all cognitive workers, inbound message ingress validation,
and scriptable MockAgentWorker.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, Sequence, List, Tuple
from agent.models import (
    AgentSessionContext,
    AgentTurnResponse,
    AgentToolCall,
    AgentTurnStatus,
    AgentMessage,
    compute_agent_message_digest,
)


class AgentWorkerProtocol(ABC):
    """Abstract Base Protocol for cognitive agent workers interacting with S-Class."""

    @property
    @abstractmethod
    def worker_id(self) -> str:
        """Unique identifier for this worker implementation (e.g. 'claude-3-5-sonnet', 'mock-worker')."""
        pass

    @abstractmethod
    def generate_turn(
        self,
        context: AgentSessionContext,
        history: Sequence[AgentTurnResponse],
    ) -> AgentTurnResponse:
        """Generates a single conversational or tool-calling turn given session context and prior turns."""
        pass


class AgentMessageChainValidator:
    """
    Validates inbound AgentMessage envelopes against sequence order, hash chain continuity,
    worker binding, and session identity.
    """

    @staticmethod
    def validate_inbound_message(
        message: AgentMessage,
        expected_session_id: str,
        expected_worker_id: str,
        expected_sequence: int,
        expected_previous_digest: str,
    ) -> Tuple[bool, Optional[str], Optional[AgentTurnStatus]]:
        """Validates all ingress invariants for an inbound AgentMessage."""
        if not isinstance(message, AgentMessage):
            return False, "Message is not an AgentMessage instance.", AgentTurnStatus.INGRESS_VALIDATION_FAILED

        # 1. Session Binding
        if message.session_id != expected_session_id:
            return False, f"Wrong session ID: expected '{expected_session_id}', got '{message.session_id}'.", AgentTurnStatus.INGRESS_VALIDATION_FAILED

        # 2. Worker Identity Binding
        if message.worker_id != expected_worker_id:
            return False, f"Wrong worker ID: expected '{expected_worker_id}', got '{message.worker_id}'.", AgentTurnStatus.WORKER_IDENTITY_MISMATCH

        # 3. Sequence Ordering & Duplicate Check
        if message.sequence != expected_sequence:
            if message.sequence < expected_sequence:
                return False, f"Duplicate or stale sequence: expected {expected_sequence}, got {message.sequence}.", AgentTurnStatus.REPLAY_DETECTED
            else:
                return False, f"Reordered sequence gap: expected {expected_sequence}, got {message.sequence}.", AgentTurnStatus.REORDER_DETECTED

        # 4. Previous Digest Continuity (Hash Chain)
        if message.previous_digest != expected_previous_digest:
            return False, f"Digest chain discontinuity: expected previous digest '{expected_previous_digest}', got '{message.previous_digest}'.", AgentTurnStatus.REPLAY_DETECTED

        # 5. Digest Integrity Verification
        computed = compute_agent_message_digest(
            session_id=message.session_id,
            worker_id=message.worker_id,
            sequence=message.sequence,
            message_type=message.message_type,
            payload=message.payload,
            previous_digest=message.previous_digest,
        )
        if message.message_digest != computed:
            return False, f"Tampered digest mismatch: expected '{computed}', got '{message.message_digest}'.", AgentTurnStatus.TAMPER_DETECTED

        return True, None, None


class MockAgentWorker(AgentWorkerProtocol):
    """Deterministic, scriptable mock agent worker for testing and differential verification."""

    def __init__(self, worker_id: str = "mock-agent-worker", script: Optional[List[AgentTurnResponse]] = None):
        self._worker_id = worker_id
        self._script = list(script) if script else []
        self._turn_pointer = 0

    @property
    def worker_id(self) -> str:
        return self._worker_id

    def set_script(self, script: Sequence[AgentTurnResponse]) -> None:
        """Sets the sequence of scripted responses to return on subsequent turns."""
        self._script = list(script)
        self._turn_pointer = 0

    def generate_turn(
        self,
        context: AgentSessionContext,
        history: Sequence[AgentTurnResponse],
    ) -> AgentTurnResponse:
        if self._turn_pointer < len(self._script):
            resp = self._script[self._turn_pointer]
            self._turn_pointer += 1
            return resp

        # Default fallback response if script is exhausted
        return AgentTurnResponse(
            thought=f"Default mock thought for turn {context.turn_index}",
            tool_calls=(),
            turn_status=AgentTurnStatus.COMPLETED,
            advisory_estimated_cost_usd=0.01,
        )
