"""
S-Class V12: Action Fingerprinting & Circuit Breaker Engine (resilience.py)

Tracks host agent action fingerprints (SHA-256) to detect repetitive stagnation loops
and trips circuit breakers before context and token budgets are exhausted.
"""

import hashlib
import json
import logging
from typing import Dict, Any, List, Optional
from collections import deque

logger = logging.getLogger("sclass_resilience")


class CircuitBreakerOpenException(Exception):
    pass


class ActionResilienceEngine:
    """
    Action fingerprinting and loop stagnation guard.
    """

    def __init__(self, loop_threshold: int = 3, max_history: int = 20):
        self.loop_threshold = loop_threshold
        self.action_history: deque = deque(maxlen=max_history)
        self.fingerprint_history: deque = deque(maxlen=max_history)
        self.circuit_state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN
        self.trip_reason: Optional[str] = None

    @staticmethod
    def fingerprint(action_type: str, payload: Any) -> str:
        """Computes deterministic SHA-256 fingerprint for an action."""
        try:
            serialized = json.dumps({"type": action_type, "payload": payload}, sort_keys=True)
        except Exception:
            serialized = f"{action_type}::{str(payload)}"
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def record_action(self, action_type: str, payload: Any) -> Dict[str, Any]:
        """
        Records an agent action, calculates fingerprint, and checks for repetition.
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
            self.trip_reason = f"Stagnation loop detected: action '{action_type}' repeated {consecutive_count} times identically."
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
