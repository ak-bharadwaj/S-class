import re
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

@dataclass
class ErrorPath:
    trigger_pattern: str        # Regex pattern matching error output
    root_cause_hint: str        # Human-readable explanation for the agent
    recovery_action: str        # retry | skip | escalate | abort
    max_retries: int = 3
    backoff_seconds: float = 1.0
    backoff_multiplier: float = 2.0  # For exponential backoff
    stop_condition: str = ""    # When to stop retrying entirely

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trigger_pattern": self.trigger_pattern,
            "root_cause_hint": self.root_cause_hint,
            "recovery_action": self.recovery_action,
            "max_retries": self.max_retries,
            "backoff_seconds": self.backoff_seconds,
            "backoff_multiplier": self.backoff_multiplier,
            "stop_condition": self.stop_condition,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ErrorPath':
        return cls(
            trigger_pattern=data["trigger_pattern"],
            root_cause_hint=data["root_cause_hint"],
            recovery_action=data["recovery_action"],
            max_retries=data.get("max_retries", 3),
            backoff_seconds=data.get("backoff_seconds", 1.0),
            backoff_multiplier=data.get("backoff_multiplier", 2.0),
            stop_condition=data.get("stop_condition", ""),
        )

class RecoveryEngine:
    def match_error(self, error_output: str, error_paths: List[ErrorPath]) -> Optional[ErrorPath]:
        for ep in error_paths:
            if re.search(ep.trigger_pattern, error_output):
                return ep
        return None

    def calculate_backoff(self, attempt: int, error_path: ErrorPath, strategy: str = "exponential") -> float:
        if strategy == "exponential":
            return error_path.backoff_seconds * (error_path.backoff_multiplier ** attempt)
        elif strategy == "linear":
            return error_path.backoff_seconds * (attempt + 1)
        elif strategy == "fixed":
            return error_path.backoff_seconds
        return error_path.backoff_seconds

    def should_stop(self, attempt: int, error_path: ErrorPath) -> bool:
        return attempt >= error_path.max_retries
