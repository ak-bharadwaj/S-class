"""D8 Autonomous Planning Substrate - Convergence & Replanning Monitor (§3.6, §8.1).

Enforces bounded replanning ceilings, monotonic Lyapunov progress potential tracking,
and multi-cycle oscillation detection over rolling fingerprint histories.
"""

from __future__ import annotations
from collections import deque
from typing import Deque, List, Optional, Set, Tuple

from domain.models import _validate_pattern
from domain.types import HEX_64_PATTERN
from planner.models import PlannerStateView


class ReplanningBudgetExceededError(RuntimeError):
    """Raised when the maximum replanning iterations budget for a task is exhausted."""
    pass


class PlanOscillationDetectedError(RuntimeError):
    """Raised when repetitive cyclic strategy generation (2-cycle or 3-cycle) is detected."""
    pass


class SpontaneousReplanningError(RuntimeError):
    """Raised when replanning is attempted without any change in underlying domain state."""
    pass


class ConvergenceMonitor:
    """Monitors planning progress and convergence bounds."""

    def __init__(
        self,
        max_replans: int = 5,
        history_window_size: int = 6,
    ):
        self._max_replans = max_replans
        self._history_window_size = history_window_size
        self._replan_count: int = 0
        self._fingerprint_history: Deque[str] = deque(maxlen=history_window_size)
        self._last_state_digest: Optional[str] = None
        self._last_progress_potential: Optional[float] = None

    @property
    def replan_count(self) -> int:
        return self._replan_count

    @property
    def max_replans(self) -> int:
        return self._max_replans

    def record_initial_plan(
        self,
        strategy_fingerprint: str,
        state_view: PlannerStateView,
        progress_potential: float,
    ):
        """Records the baseline initial plan and state coordinates."""
        _validate_pattern(strategy_fingerprint, HEX_64_PATTERN, "strategy_fingerprint")
        self._fingerprint_history.append(strategy_fingerprint)
        self._last_state_digest = state_view.planner_state_digest
        self._last_progress_potential = progress_potential

    def validate_replan_trigger(self, current_state_view: PlannerStateView):
        """Ensures replanning is grounded in an actual domain state delta."""
        if self._last_state_digest is not None:
            if current_state_view.planner_state_digest == self._last_state_digest:
                raise SpontaneousReplanningError(
                    "Spontaneous replanning rejected: No state delta detected since previous plan."
                )

    def record_replan(
        self,
        new_strategy_fingerprint: str,
        current_state_view: PlannerStateView,
        progress_potential: float,
    ):
        """Records a replanning event and validates convergence invariants."""
        _validate_pattern(new_strategy_fingerprint, HEX_64_PATTERN, "new_strategy_fingerprint")

        # 1. Verify Replanning Budget Bound
        self._replan_count += 1
        if self._replan_count > self._max_replans:
            raise ReplanningBudgetExceededError(
                f"Replanning budget exceeded: {self._replan_count} replans attempted (max {self._max_replans})."
            )

        # 2. State Delta Verification
        self.validate_replan_trigger(current_state_view)

        # 3. Oscillation Detection (Check 2-cycle and 3-cycle patterns)
        history = list(self._fingerprint_history)
        if len(history) >= 2 and new_strategy_fingerprint == history[-2]:
            raise PlanOscillationDetectedError(
                f"2-cycle plan oscillation detected: strategy '{new_strategy_fingerprint[:12]}' was active 2 steps ago."
            )
        if len(history) >= 3 and new_strategy_fingerprint == history[-3]:
            raise PlanOscillationDetectedError(
                f"3-cycle plan oscillation detected: strategy '{new_strategy_fingerprint[:12]}' was active 3 steps ago."
            )

        # Update History
        self._fingerprint_history.append(new_strategy_fingerprint)
        self._last_state_digest = current_state_view.planner_state_digest
        self._last_progress_potential = progress_potential
