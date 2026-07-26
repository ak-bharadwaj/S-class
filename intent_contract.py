from dataclasses import dataclass, field
from typing import List, Dict, Any
from error_recovery import ErrorPath

@dataclass
class IntentContract:
    goal: str                        # What the user wants
    scope_boundaries: List[str]      # What is explicitly OUT of scope
    acceptance_criteria: List[str]   # Measurable success conditions
    error_paths: List[ErrorPath]     # Explicit failure handling
    max_retries: int = 3
    backoff_strategy: str = "exponential"  # linear | exponential | fixed
    stop_conditions: List[str] = field(default_factory=list)  # When to give up entirely

    def validate(self) -> None:
        if not self.goal:
            raise ValueError("goal cannot be empty")
        if not self.acceptance_criteria:
            raise ValueError("acceptance_criteria cannot be empty")
        if not self.error_paths:
            raise ValueError("error_paths cannot be empty")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "scope_boundaries": self.scope_boundaries,
            "acceptance_criteria": self.acceptance_criteria,
            "error_paths": [ep.to_dict() for ep in self.error_paths],
            "max_retries": self.max_retries,
            "backoff_strategy": self.backoff_strategy,
            "stop_conditions": self.stop_conditions,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IntentContract':
        return cls(
            goal=data["goal"],
            scope_boundaries=data["scope_boundaries"],
            acceptance_criteria=data["acceptance_criteria"],
            error_paths=[ErrorPath.from_dict(ep) for ep in data["error_paths"]],
            max_retries=data.get("max_retries", 3),
            backoff_strategy=data.get("backoff_strategy", "exponential"),
            stop_conditions=data.get("stop_conditions", []),
        )
