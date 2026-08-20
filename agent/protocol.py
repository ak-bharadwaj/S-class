"""
S-Class EOS V11.2 - D7 Agent Worker Protocol & Mock Worker (§8.1, §8.3).
Defines the abstract interface seam for all external cognitive workers (LLMs, heuristics, mocks)
and provides a deterministic MockAgentWorker for cleanroom verification.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, Sequence, List
from agent.models import (
    AgentSessionContext,
    AgentTurnResponse,
    AgentToolCall,
    AgentTurnStatus,
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
