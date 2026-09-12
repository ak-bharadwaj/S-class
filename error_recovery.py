import re
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from tenacity import (
    wait_exponential,
    wait_incrementing,
    wait_fixed,
    stop_after_attempt,
    RetryCallState,
    Retrying,
)

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
    def from_dict(cls, data: Any) -> 'ErrorPath':
        if not isinstance(data, dict):
            return cls(trigger_pattern=".*", root_cause_hint="", recovery_action="retry")
        return cls(
            trigger_pattern=str(data.get("trigger_pattern", ".*")),
            root_cause_hint=str(data.get("root_cause_hint", "")),
            recovery_action=str(data.get("recovery_action", "retry")),
            max_retries=int(data.get("max_retries", 3)),
            backoff_seconds=float(data.get("backoff_seconds", 1.0)),
            backoff_multiplier=float(data.get("backoff_multiplier", 2.0)),
            stop_condition=str(data.get("stop_condition", "")),
        )

class RecoveryEngine:
    def match_error(self, error_output: str, error_paths: List[ErrorPath]) -> Optional[ErrorPath]:
        for ep in error_paths:
            if re.search(ep.trigger_pattern, error_output):
                return ep
        return None

    def calculate_backoff(self, attempt: int, error_path: ErrorPath, strategy: str = "exponential") -> float:
        """Calculates backoff delay using tenacity strategy primitives."""
        state = RetryCallState(None, None, (), {})
        state.attempt_number = attempt + 1
        if strategy == "exponential":
            waiter = wait_exponential(multiplier=error_path.backoff_seconds, exp_base=error_path.backoff_multiplier)
            return float(waiter(state))
        elif strategy == "linear":
            waiter = wait_incrementing(start=error_path.backoff_seconds, increment=error_path.backoff_seconds)
            return float(waiter(state))
        elif strategy == "fixed":
            waiter = wait_fixed(error_path.backoff_seconds)
            return float(waiter(state))
        return float(error_path.backoff_seconds)

    def classify_failure_target_phase(self, error_output: str) -> str:
        """Determines exact target phase based on error categorization (Smart Multi-Tier Recovery)."""
        err_lower = error_output.lower()
        
        # 1. Requirement Ambiguity -> CLARIFICATION
        if any(kw in err_lower for kw in ["ambiguity", "specification missing", "undefined requirement"]):
            return "CLARIFICATION"
        
        # 2. Architectural / Type Mismatch -> DESIGN
        if any(kw in err_lower for kw in ["typeerror", "interface mismatch", "schemaerror", "constraintviolation"]):
            return "DESIGN"
            
        # 3. Dependency / Import Error -> INTEGRATION
        if any(kw in err_lower for kw in ["modulenotfounderror", "cannot find module", "importerror", "elifecycle"]):
            return "INTEGRATION"
            
        # 4. Syntax Error -> CODING
        return "CODING"

    def should_stop(self, attempt: int, error_path: ErrorPath) -> bool:
        """Determines retry termination using tenacity stop strategy."""
        state = RetryCallState(None, None, (), {})
        state.attempt_number = attempt
        stopper = stop_after_attempt(error_path.max_retries)
        return bool(stopper(state))

    def get_retry_controller(self, error_path: ErrorPath, strategy: str = "exponential") -> Retrying:
        """Constructs a tenacity Retrying instance configured with error_path parameters."""
        if strategy == "exponential":
            waiter = wait_exponential(multiplier=error_path.backoff_seconds, exp_base=error_path.backoff_multiplier)
        elif strategy == "linear":
            waiter = wait_incrementing(start=error_path.backoff_seconds, increment=error_path.backoff_seconds)
        else:
            waiter = wait_fixed(error_path.backoff_seconds)
        stopper = stop_after_attempt(error_path.max_retries)
        return Retrying(wait=waiter, stop=stopper, reraise=True)
