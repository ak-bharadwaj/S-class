"""
S-Class V12: Action Fingerprinting & Circuit Breaker Engine (resilience.py)

Tracks host agent action fingerprints (SHA-256 via RFC 8785 canonical JSON) to detect
repetitive stagnation loops, trips circuit breakers before context/token budgets are
exhausted, and provides tenacity-backed exponential backoff, retry, and resilience strategies.
"""

import hashlib
import json
import logging
from collections import deque
from typing import Dict, Any, List, Optional, Callable

import rfc8785
from tenacity import (
    wait_exponential,
    wait_incrementing,
    wait_fixed,
    stop_after_attempt,
    RetryCallState,
    Retrying,
    retry_if_exception_type,
)
from error_recovery import ErrorPath, RecoveryEngine

logger = logging.getLogger("sclass_resilience")


class CircuitBreakerOpenException(Exception):
    """Raised when an action is attempted while the resilience circuit breaker is OPEN."""
    pass


class ActionResilienceEngine:
    """
    Action fingerprinting, loop stagnation guard, and circuit breaker engine backed by tenacity.
    """

    def __init__(self, loop_threshold: int = 3, max_history: int = 20, recovery_engine: Optional[RecoveryEngine] = None):
        self.loop_threshold = loop_threshold
        self.max_history = max_history
        self.action_history: deque = deque(maxlen=max_history)
        self.fingerprint_history: deque = deque(maxlen=max_history)
        self.circuit_state: str = "CLOSED"  # CLOSED, OPEN, HALF-OPEN
        self.trip_reason: Optional[str] = None
        self.recovery_engine: RecoveryEngine = recovery_engine or RecoveryEngine()

    @staticmethod
    def fingerprint(action_type: str, payload: Any) -> str:
        """Computes deterministic SHA-256 fingerprint for an action using RFC 8785 canonical serialization."""
        norm_payload = payload.to_dict() if hasattr(payload, "to_dict") and callable(payload.to_dict) else (
            payload.model_dump() if hasattr(payload, "model_dump") and callable(payload.model_dump) else payload
        )
        try:
            canonical_bytes = rfc8785.dumps({"type": action_type, "payload": norm_payload})
            return hashlib.sha256(canonical_bytes).hexdigest()
        except Exception:
            try:
                serialized = json.dumps({"type": action_type, "payload": norm_payload}, sort_keys=True, separators=(",", ":"), default=str)
                return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
            except Exception:
                serialized = f"{action_type}::{str(payload)}"
                return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def record_action(self, action_type: str, payload: Any) -> Dict[str, Any]:
        """
        Records an agent action, calculates fingerprint, checks for repetition, and trips
        the circuit breaker if a stagnation loop is detected.
        """
        if self.circuit_state == "OPEN":
            raise CircuitBreakerOpenException(f"Circuit Breaker is OPEN: {self.trip_reason}")

        fp = self.fingerprint(action_type, payload)
        self.action_history.append((action_type, payload))
        self.fingerprint_history.append(fp)

        # Check consecutive identical fingerprints
        consecutive_count = 0
        for prior_fp in reversed(self.fingerprint_history):
            if prior_fp == fp:
                consecutive_count += 1
            else:
                break

        loop_detected = consecutive_count >= self.loop_threshold

        if loop_detected:
            self.circuit_state = "OPEN"
            self.trip_reason = (
                f"Stagnation loop detected: action '{action_type}' repeated {consecutive_count} times identically."
            )
            logger.error(f"[Resilience] {self.trip_reason}")

        return {
            "fingerprint": fp,
            "consecutive_repetitions": consecutive_count,
            "loop_detected": loop_detected,
            "circuit_state": self.circuit_state,
            "trip_reason": self.trip_reason,
        }

    def reset(self) -> None:
        """Resets the circuit breaker to CLOSED state."""
        self.circuit_state = "CLOSED"
        self.trip_reason = None
        self.action_history.clear()
        self.fingerprint_history.clear()

    def calculate_backoff(self, attempt: int, error_path: ErrorPath, strategy: str = "exponential") -> float:
        """Preserves calculate_backoff contract using RecoveryEngine and tenacity math."""
        return self.recovery_engine.calculate_backoff(attempt, error_path, strategy=strategy)

    def match_error(self, error_output: str, error_paths: List[ErrorPath]) -> Optional[ErrorPath]:
        """Preserves match_error contract using RecoveryEngine."""
        return self.recovery_engine.match_error(error_output, error_paths)

    def execute_with_resilience(
        self,
        fn: Callable[..., Any],
        error_path: ErrorPath,
        *args: Any,
        strategy: str = "exponential",
        **kwargs: Any,
    ) -> Any:
        """Executes a callable under tenacity retry controller guarded by circuit state."""
        if self.circuit_state == "OPEN":
            raise CircuitBreakerOpenException(f"Circuit Breaker is OPEN: {self.trip_reason}")

        retrying = self.recovery_engine.get_retry_controller(error_path, strategy=strategy)
        return retrying(fn, *args, **kwargs)
