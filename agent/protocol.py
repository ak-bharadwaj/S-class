"""
S-Class EOS V11.2 - D7 Agent Worker Protocol & Inbound Message Ingress (§8.1, §8.3).
Defines the abstract interface seam for all cognitive workers, inbound message ingress validation,
and scriptable MockAgentWorker.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, Sequence, List, Tuple, Any, Mapping
from types import MappingProxyType
from agent.models import (
    AgentSessionContext,
    AgentTurnResponse,
    AgentToolCall,
    AgentTurnStatus,
    AgentMessage,
    create_agent_message,
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
    def generate_inbound_message(
        self,
        context: AgentSessionContext,
        sequence: int,
        previous_digest: str,
        history: Sequence[AgentMessage],
    ) -> AgentMessage:
        """
        Emits an externally constructed, canonical AgentMessage envelope to D7 ingress.
        Worker constructs its own payload, sequence, and digest.
        """
        pass


class AgentMessageChainValidator:
    """
    Validates inbound AgentMessage envelopes against sequence order, hash chain continuity,
    worker binding, session identity, and payload structure before creating an AgentTurnResponse.
    """

    @staticmethod
    def validate_inbound_message(
        message: AgentMessage,
        expected_session_id: str,
        expected_worker_id: str,
        expected_sequence: int,
        expected_previous_digest: str,
    ) -> Tuple[bool, Optional[str], Optional[AgentTurnStatus], Optional[AgentTurnResponse]]:
        """
        Validates all ingress invariants for an inbound AgentMessage and extracts validated AgentTurnResponse.
        """
        if not isinstance(message, AgentMessage):
            return False, "Message is not an AgentMessage instance.", AgentTurnStatus.INGRESS_VALIDATION_FAILED, None

        # 1. Session Binding
        if message.session_id != expected_session_id:
            return False, f"Wrong session ID: expected '{expected_session_id}', got '{message.session_id}'.", AgentTurnStatus.INGRESS_VALIDATION_FAILED, None

        # 2. Worker Identity Binding (Trusted Local Worker in D7A)
        if message.worker_id != expected_worker_id:
            return False, f"Wrong worker ID: expected '{expected_worker_id}', got '{message.worker_id}'.", AgentTurnStatus.WORKER_IDENTITY_MISMATCH, None

        # 3. Sequence Ordering & Duplicate Check
        if message.sequence != expected_sequence:
            if message.sequence < expected_sequence:
                return False, f"Duplicate or stale sequence: expected {expected_sequence}, got {message.sequence}.", AgentTurnStatus.REPLAY_DETECTED, None
            else:
                return False, f"Reordered sequence gap: expected {expected_sequence}, got {message.sequence}.", AgentTurnStatus.REORDER_DETECTED, None

        # 4. Previous Digest Continuity (Hash Chain)
        if message.previous_digest != expected_previous_digest:
            return False, f"Digest chain discontinuity: expected previous digest '{expected_previous_digest}', got '{message.previous_digest}'.", AgentTurnStatus.REPLAY_DETECTED, None

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
            return False, f"Tampered digest mismatch: expected '{computed}', got '{message.message_digest}'.", AgentTurnStatus.TAMPER_DETECTED, None

        # 6. Unpack validated payload into AgentTurnResponse
        payload = message.payload
        try:
            thought = str(payload.get("thought", ""))
            status_str = str(payload.get("status", "CONTINUE"))
            turn_status = AgentTurnStatus(status_str)
            advisory_cost = float(payload.get("advisory_cost_usd", 0.0))

            raw_tool_calls = payload.get("tool_calls", ())
            parsed_tool_calls = []
            for tc in raw_tool_calls:
                if isinstance(tc, (dict, Mapping, MappingProxyType)):
                    parsed_tool_calls.append(
                        AgentToolCall(
                            call_id=str(tc.get("call_id", "")),
                            tool_name=str(tc.get("tool", "")),
                            arguments=dict(tc.get("args", {})),
                        )
                    )
            turn_response = AgentTurnResponse(
                thought=thought,
                tool_calls=tuple(parsed_tool_calls),
                turn_status=turn_status,
                advisory_estimated_cost_usd=advisory_cost,
            )
            return True, None, None, turn_response
        except Exception as ex:
            return False, f"Malformed message payload: {ex}", AgentTurnStatus.INGRESS_VALIDATION_FAILED, None


class MockAgentWorker(AgentWorkerProtocol):
    """Deterministic, scriptable mock agent worker for testing and differential verification."""

    def __init__(self, worker_id: str = "mock-agent-worker", script: Optional[List[AgentTurnResponse]] = None):
        self._worker_id = worker_id
        self._script = list(script) if script else []
        self._raw_message_script: Optional[List[AgentMessage]] = None
        self._turn_pointer = 0

    @property
    def worker_id(self) -> str:
        return self._worker_id

    def set_script(self, script: Sequence[AgentTurnResponse]) -> None:
        """Sets the sequence of scripted responses to return on subsequent turns."""
        self._script = list(script)
        self._raw_message_script = None
        self._turn_pointer = 0

    def set_raw_message_script(self, messages: Sequence[AgentMessage]) -> None:
        """Directly injects externally constructed raw AgentMessages for adversarial testing."""
        self._raw_message_script = list(messages)
        self._turn_pointer = 0

    def generate_inbound_message(
        self,
        context: AgentSessionContext,
        sequence: int,
        previous_digest: str,
        history: Sequence[AgentMessage],
    ) -> AgentMessage:
        if self._raw_message_script is not None and self._turn_pointer < len(self._raw_message_script):
            msg = self._raw_message_script[self._turn_pointer]
            self._turn_pointer += 1
            return msg

        if self._turn_pointer < len(self._script):
            resp = self._script[self._turn_pointer]
            self._turn_pointer += 1
        else:
            resp = AgentTurnResponse(
                thought=f"Default mock thought for turn {context.turn_index}",
                tool_calls=(),
                turn_status=AgentTurnStatus.COMPLETED,
                advisory_estimated_cost_usd=0.01,
            )

        payload = {
            "thought": resp.thought,
            "status": resp.turn_status.value,
            "advisory_cost_usd": resp.advisory_estimated_cost_usd,
            "tool_calls": [
                {"call_id": tc.call_id, "tool": tc.tool_name, "args": dict(tc.arguments)}
                for tc in resp.tool_calls
            ],
        }
        return create_agent_message(
            session_id=context.session_id,
            worker_id=self._worker_id,
            sequence=sequence,
            message_type="AGENT_TURN",
            payload=payload,
            previous_digest=previous_digest,
        )
