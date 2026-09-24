"""
S-Class Evolution: Multi-Objective Pareto Frontier Tracking.
Tracks the non-dominated set of evolution candidates optimizing for
higher quality score (delta_S) and lower resource cost (delta_C).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List
from sclass.evolution.candidate import EvolutionCandidate


@dataclass(frozen=True)
class FrontierPoint:
    candidate_id: str
    round: int
    delta_S: float
    delta_C: float
    component_set: List[str]


class ParetoFrontier:
    """
    Maintains non-dominated candidates where higher delta_S is better and lower delta_C is better.
    """

    def __init__(self):
        self._points: List[FrontierPoint] = []

    def update(self, candidate: EvolutionCandidate) -> bool:
        """
        Adds candidate to frontier if it is not dominated by any existing point.
        Removes any existing points dominated by the new candidate.
        Returns True if candidate was added to the frontier.
        """
        cand_s = candidate.score_delta_s
        cand_c = candidate.cost_delta_c

        # Check if dominated by existing point
        # Point P dominates candidate if:
        # P.delta_S >= cand_s AND P.delta_C <= cand_c AND (at least one is strictly better)
        for p in self._points:
            if (p.delta_S >= cand_s and p.delta_C <= cand_c) and (p.delta_S > cand_s or p.delta_C < cand_c):
                return False  # Candidate is dominated

        new_point = FrontierPoint(
            candidate_id=candidate.candidate_id,
            round=candidate.round,
            delta_S=cand_s,
            delta_C=cand_c,
            component_set=sorted(list(candidate.component_set)),
        )

        # Remove points dominated by new point
        surviving: List[FrontierPoint] = []
        for p in self._points:
            # New point dominates P if: cand_s >= p.delta_S and cand_c <= p.delta_C and strictly better
            is_dominated = (cand_s >= p.delta_S and cand_c <= p.delta_C) and (cand_s > p.delta_S or cand_c < p.delta_C)
            if not is_dominated:
                surviving.append(p)

        surviving.append(new_point)
        self._points = surviving
        return True

    def get_points(self) -> List[FrontierPoint]:
        return list(self._points)
