"""Rollback and compensating transaction contracts."""
from dataclasses import dataclass
from typing import List, Callable, Any

@dataclass(frozen=True)
class CompensatingStep:
    step_id: str
    target_resource: str
    reversal_action: str
    reversal_payload: str

@dataclass(frozen=True)
class SagaTransaction:
    transaction_id: str
    forward_action_id: str
    compensating_steps: List[CompensatingStep]
    status: str
