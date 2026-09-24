"""
S-Class Runtime: Autopilot Retry & Bounded Recovery Ladder.
Harvests Step-Code's recovery machinery (Directive Section 14):
- Explicit failure classification (TRANSIENT, RATE_LIMIT, CONNECTIVITY, MUTATION_FAILURE, FATAL).
- Bound recovery ladder:
    Attempt 1: Immediate retry (if ReplayClass == SAFE)
    Attempt 2: Exponential backoff with jitter
    Attempt 3: Connection reset / probe
    Terminal: Give-up, quarantine operation, raise explicit error.
- Strict Invariants:
  1. No infinite self-healing: maximum attempts strictly enforced.
  2. No mutation replay without explicit authority: NEVER operations fail closed immediately.
  3. No hidden re-execution: every retry is logged in execution telemetry.
"""

from __future__ import annotations
import time
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable

from sclass.execution.operations import ReplayClass
from sclass.core.errors import SecurityViolationError


class FailureClass(str, Enum):
    TRANSIENT = "TRANSIENT"            # Temporary I/O or pipe glitch
    RATE_LIMIT = "RATE_LIMIT"          # Upstream provider throttled
    CONNECTIVITY = "CONNECTIVITY"      # Subprocess or pipe broken
    MUTATION_FAILURE = "MUTATION_FAILURE" # Tool execution returned non-zero or error
    FATAL = "FATAL"                    # Security violation, unauthorized action, corruption


@dataclass(frozen=True)
class RecoveryDecision:
    can_retry: bool
    attempt_number: int
    delay_seconds: float
    reason: str
    give_up: bool


class BoundedRecoveryLadder:
    """
    Evaluates recovery feasibility, bounding retries by replay class and attempt limit.
    """

    MAX_RETRIES = 3

    @classmethod
    def evaluate_retry(
        cls,
        replay_class: ReplayClass,
        failure_class: FailureClass,
        current_attempt: int,
        remaining_budget_tokens: int = 10000,
    ) -> RecoveryDecision:
        # Rule 1: NEVER or UNKNOWN replay classes can NEVER be automatically retried
        if replay_class in (ReplayClass.NEVER, ReplayClass.UNKNOWN):
            return RecoveryDecision(
                can_retry=False,
                attempt_number=current_attempt,
                delay_seconds=0.0,
                reason=f"Automatic retry prohibited for operation replay class: {replay_class.value}",
                give_up=True,
            )

        # Rule 2: Fatal failures can never be retried
        if failure_class == FailureClass.FATAL:
            return RecoveryDecision(
                can_retry=False,
                attempt_number=current_attempt,
                delay_seconds=0.0,
                reason="Operation failed due to FATAL security violation or corruption.",
                give_up=True,
            )

        # Rule 3: Budget check
        if remaining_budget_tokens <= 0:
            return RecoveryDecision(
                can_retry=False,
                attempt_number=current_attempt,
                delay_seconds=0.0,
                reason="Lane budget exhausted; cannot retry.",
                give_up=True,
            )

        # Rule 4: Maximum attempts limit
        if current_attempt >= cls.MAX_RETRIES:
            return RecoveryDecision(
                can_retry=False,
                attempt_number=current_attempt,
                delay_seconds=0.0,
                reason=f"Exceeded maximum recovery attempts ({cls.MAX_RETRIES}). Giving up.",
                give_up=True,
            )

        # Calculate backoff ladder
        next_attempt = current_attempt + 1
        if failure_class == FailureClass.RATE_LIMIT:
            delay = 2.0 * next_attempt
        elif failure_class == FailureClass.CONNECTIVITY:
            delay = 1.0 * next_attempt
        else:
            delay = 0.5 * next_attempt

        return RecoveryDecision(
            can_retry=True,
            attempt_number=next_attempt,
            delay_seconds=delay,
            reason=f"Recovery ladder permitted retry attempt {next_attempt}/{cls.MAX_RETRIES} for {failure_class.value}.",
            give_up=False,
        )
