"""
S-Class Evolution: Evolution Analyst, Stall Detector & Budget Annealing.
Implements Directive Sections 20, 21, and 23:
- Edit-budget annealing:
    Early rounds -> higher edit bundle sizes for exploration.
    Later rounds -> annealed single-edit bundles for precise causal attribution.
- Explore / Stall / Prune:
    Tracks tried vs untried components.
    Detects search stalls (plateau in delta_S over consecutive rounds).
    Reserves proposal slots for novel untried structural components during stalls.
    Prunes low-yield repeatedly failing mechanisms to prevent cycling.
"""

from __future__ import annotations
from typing import Dict, Any, List, Set, Optional
from sclass.evolution.components import EVOLVABLE_COMPONENTS
from sclass.evolution.history import HistoryEntry


class EvolutionAnalyst:
    """
    Analyzes historical evolution trajectories to guide candidate generation,
    budget annealing, and novelty exploration.
    """

    def __init__(
        self,
        base_bundle_size: int = 3,
        anneal_rate: float = 0.5,
        stall_threshold_rounds: int = 3,
    ):
        self.base_bundle_size = base_bundle_size
        self.anneal_rate = anneal_rate
        self.stall_threshold_rounds = stall_threshold_rounds

    def compute_annealed_budget(self, current_round: int) -> int:
        """
        Computes maximum allowable edits per candidate bundle for the given round.
        As rounds advance, bundles anneal toward 1 for precise mechanism attribution.
        """
        reduction = int(current_round * self.anneal_rate)
        return max(1, self.base_bundle_size - reduction)

    def analyze_yield(self, history: List[HistoryEntry]) -> Dict[str, Any]:
        """
        Computes component yield statistics, tried/untried components, and stall state.
        """
        tried_components: Set[str] = set()
        component_successes: Dict[str, int] = {}
        component_attempts: Dict[str, int] = {}

        for entry in history:
            c = entry.component
            tried_components.add(c)
            component_attempts[c] = component_attempts.get(c, 0) + 1
            if entry.accepted:
                component_successes[c] = component_successes.get(c, 0) + 1

        untried_components = EVOLVABLE_COMPONENTS - tried_components

        # Compute yield rates
        yield_by_component: Dict[str, float] = {}
        for c, attempts in component_attempts.items():
            succ = component_successes.get(c, 0)
            yield_by_component[c] = succ / attempts if attempts > 0 else 0.0

        # Stall detection: inspect last N entries or rounds
        rounds_seen = sorted(list({e.round for e in history}))
        is_stalled = False
        if len(rounds_seen) >= self.stall_threshold_rounds:
            recent_rounds = rounds_seen[-self.stall_threshold_rounds:]
            recent_entries = [e for e in history if e.round in recent_rounds]
            recent_accepts = sum(1 for e in recent_entries if e.accepted)
            if recent_accepts == 0:
                is_stalled = True

        # Identify prune candidates: attempted >= 3 times with 0% success
        prune_candidates: List[str] = [
            c for c, attempts in component_attempts.items()
            if attempts >= 3 and component_successes.get(c, 0) == 0
        ]

        return {
            "tried_components": sorted(list(tried_components)),
            "untried_components": sorted(list(untried_components)),
            "yield_by_component": yield_by_component,
            "is_stalled": is_stalled,
            "prune_candidates": prune_candidates,
            "recommended_focus": (
                sorted(list(untried_components)) if is_stalled and untried_components
                else [k for k, v in yield_by_component.items() if v > 0.0]
            ),
        }
