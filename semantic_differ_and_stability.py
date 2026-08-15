#!/usr/bin/env python3
"""
S-Class EOS - Semantic Output Differ, Stability Analyzer & Convergence Detector
(semantic_differ_and_stability.py)

Responsibilities:
- `EpistemicStatus`: Formal taxonomy (EXPLICIT, DERIVED_JUSTIFIED, SUPPORTED, UNKNOWN, UNSUPPORTED).
- `SemanticOutputDiffer`: Compares Legacy Heuristic Spec vs Shadow Grounded Spec to identify
  omissions, hallucinations (e.g. unrequested UI spreads), conflated invariants, and epistemic gaps.
- `RequirementStabilityAnalyzer`: Computes inter-pass churn rate, novelty addition rate, and Jaccard similarity.
- `ConvergenceDetector`: Evaluates whether iterative refinement has reached a stable equilibrium
  (CONVERGED, STABILIZING, DIVERGENT).
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set, Tuple


class EpistemicStatus(Enum):
    EXPLICIT = "EXPLICIT"
    DERIVED_JUSTIFIED = "DERIVED_JUSTIFIED"
    SUPPORTED = "SUPPORTED"
    UNKNOWN = "UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"


class ConvergenceState(Enum):
    CONVERGED = "CONVERGED"
    STABILIZING = "STABILIZING"
    DIVERGENT = "DIVERGENT"


@dataclass
class StabilityMetrics:
    pass_number: int
    candidate_count: int
    churn_rate: float
    novelty_addition_rate: float
    jaccard_similarity_to_previous: float
    must_invariant_count: int
    unknown_count: int
    unsupported_count: int
    stability_score: float
    convergence_state: ConvergenceState

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pass_number": self.pass_number,
            "candidate_count": self.candidate_count,
            "churn_rate": self.churn_rate,
            "novelty_addition_rate": self.novelty_addition_rate,
            "jaccard_similarity_to_previous": self.jaccard_similarity_to_previous,
            "must_invariant_count": self.must_invariant_count,
            "unknown_count": self.unknown_count,
            "unsupported_count": self.unsupported_count,
            "stability_score": self.stability_score,
            "convergence_state": self.convergence_state.value if hasattr(self.convergence_state, "value") else str(self.convergence_state)
        }


@dataclass
class SemanticDiffReport:
    legacy_requirement_count: int
    shadow_requirement_count: int
    legacy_page_spreads_count: int
    shadow_page_spreads_count: int
    scope_explosion_delta: int
    page_spread_hallucination_delta: int
    omitted_by_legacy: List[Dict[str, Any]] = field(default_factory=list)
    hallucinated_by_legacy: List[str] = field(default_factory=list)
    conflated_invariants_count: int = 0
    epistemic_unknowns_flagged: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "legacy_requirement_count": self.legacy_requirement_count,
            "shadow_requirement_count": self.shadow_requirement_count,
            "legacy_page_spreads_count": self.legacy_page_spreads_count,
            "shadow_page_spreads_count": self.shadow_page_spreads_count,
            "scope_explosion_delta": self.scope_explosion_delta,
            "page_spread_hallucination_delta": self.page_spread_hallucination_delta,
            "omitted_by_legacy_count": len(self.omitted_by_legacy),
            "omitted_by_legacy": self.omitted_by_legacy,
            "hallucinated_by_legacy_count": len(self.hallucinated_by_legacy),
            "hallucinated_by_legacy": self.hallucinated_by_legacy,
            "conflated_invariants_count": self.conflated_invariants_count,
            "epistemic_unknowns_flagged_count": len(self.epistemic_unknowns_flagged),
            "epistemic_unknowns_flagged": self.epistemic_unknowns_flagged
        }


class RequirementStabilityAnalyzer:
    """
    Measures stability and evolution of requirements across successive refinement passes.
    """

    @staticmethod
    def compute_jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
        if not set_a and not set_b:
            return 1.0
        intersection = len(set_a.intersection(set_b))
        union = len(set_a.union(set_b))
        return round(intersection / union, 4) if union > 0 else 1.0

    @classmethod
    def analyze_pass_transition(
        cls,
        prev_reqs: List[Dict[str, Any]],
        curr_reqs: List[Dict[str, Any]],
        pass_number: int
    ) -> StabilityMetrics:
        prev_keys = {r.get("title", "").strip().lower() for r in prev_reqs if r.get("title")}
        curr_keys = {r.get("title", "").strip().lower() for r in curr_reqs if r.get("title")}

        new_keys = curr_keys - prev_keys
        removed_keys = prev_keys - curr_keys
        maintained_keys = prev_keys.intersection(curr_keys)

        total_curr = len(curr_reqs)
        total_prev = len(prev_reqs)

        if total_prev > 0:
            churn_rate = round((len(new_keys) + len(removed_keys)) / max(1, total_curr + total_prev), 4)
            novelty_rate = round(len(new_keys) / max(1, total_curr), 4)
        else:
            churn_rate = 1.0
            novelty_rate = 1.0

        jaccard = cls.compute_jaccard_similarity(prev_keys, curr_keys)

        must_count = sum(
            1 for r in curr_reqs
            if r.get("normative_level") == "MUST" or "INVARIANT" in r.get("type", "").upper()
        )
        unknown_count = sum(
            1 for r in curr_reqs
            if r.get("epistemic_status") in ["UNKNOWN", EpistemicStatus.UNKNOWN.value]
        )
        unsupported_count = sum(
            1 for r in curr_reqs
            if r.get("epistemic_status") in ["UNSUPPORTED", EpistemicStatus.UNSUPPORTED.value]
        )

        # Stability score calculation: high jaccard, zero unsupported, bounded churn
        penalty = (unsupported_count * 0.5) + (churn_rate * 0.3)
        stability_score = max(0.0, round(1.0 - penalty, 4))

        # Convergence state classification
        if pass_number >= 3:
            if novelty_rate <= 0.25 and unsupported_count == 0 and jaccard >= 0.70:
                convergence = ConvergenceState.CONVERGED
            elif novelty_rate <= 0.50:
                convergence = ConvergenceState.STABILIZING
            else:
                convergence = ConvergenceState.DIVERGENT
        elif pass_number == 2:
            if unsupported_count == 0 and jaccard >= 0.50:
                convergence = ConvergenceState.STABILIZING
            else:
                convergence = ConvergenceState.DIVERGENT
        else:
            convergence = ConvergenceState.STABILIZING

        return StabilityMetrics(
            pass_number=pass_number,
            candidate_count=total_curr,
            churn_rate=churn_rate,
            novelty_addition_rate=novelty_rate,
            jaccard_similarity_to_previous=jaccard,
            must_invariant_count=must_count,
            unknown_count=unknown_count,
            unsupported_count=unsupported_count,
            stability_score=stability_score,
            convergence_state=convergence
        )


class ConvergenceDetector:
    """
    Evaluates whether the iterative specification synthesis sequence has converged.
    """

    @staticmethod
    def evaluate_sequence(history: List[StabilityMetrics]) -> Tuple[ConvergenceState, str]:
        if not history:
            return ConvergenceState.DIVERGENT, "No pass history available for convergence evaluation."

        final_metrics = history[-1]
        
        if len(history) >= 3:
            p2 = history[1]
            p3 = history[2]
            if p3.unsupported_count == 0 and p3.jaccard_similarity_to_previous >= 0.65:
                return (
                    ConvergenceState.CONVERGED,
                    f"Specification converged at Pass 3: Jaccard={p3.jaccard_similarity_to_previous}, "
                    f"Stability={p3.stability_score}, 0 unsupported inferences."
                )
            elif p3.unsupported_count == 0:
                return (
                    ConvergenceState.STABILIZING,
                    f"Specification stabilizing: Pass 3 Jaccard={p3.jaccard_similarity_to_previous}."
                )
            else:
                return (
                    ConvergenceState.DIVERGENT,
                    f"Specification divergent: {p3.unsupported_count} unsupported inferences detected."
                )
        elif len(history) == 2:
            return final_metrics.convergence_state, f"Intermediate state at Pass 2: Stability={final_metrics.stability_score}."
        else:
            return ConvergenceState.STABILIZING, "Initial Pass 1 baseline established."


class SemanticOutputDiffer:
    """
    Calculates differential semantics between legacy synthesized specs and shadow grounded specs.
    """

    @classmethod
    def compute_diff(
        cls,
        legacy_spec_dict: Dict[str, Any],
        shadow_spec_dict: Dict[str, Any]
    ) -> SemanticDiffReport:
        # Legacy counts
        legacy_reqs = legacy_spec_dict.get("requirements", {})
        if isinstance(legacy_reqs, dict):
            legacy_flat = [r for group in legacy_reqs.values() for r in (group if isinstance(group, list) else [])]
        elif isinstance(legacy_reqs, list):
            legacy_flat = legacy_reqs
        else:
            legacy_flat = legacy_spec_dict.get("flattened_requirements", [])

        legacy_pages_dict = legacy_spec_dict.get("page_spreads", {})
        if isinstance(legacy_pages_dict, dict):
            legacy_pages = [p for p_list in legacy_pages_dict.values() for p in (p_list if isinstance(p_list, list) else [])]
        elif isinstance(legacy_pages_dict, list):
            legacy_pages = legacy_pages_dict
        else:
            legacy_pages = []

        legacy_page_count = legacy_spec_dict.get("page_spreads_count", len(legacy_pages))
        legacy_req_count = legacy_spec_dict.get("total_requirements_count", len(legacy_flat))

        # Shadow counts
        shadow_reqs = shadow_spec_dict.get("requirements", [])
        shadow_page_count = shadow_spec_dict.get("page_spreads_count", 0)
        shadow_req_count = len(shadow_reqs)

        scope_explosion_delta = max(0, legacy_req_count - shadow_req_count)
        page_spread_hallucination_delta = max(0, legacy_page_count - shadow_page_count)

        # Detect grounded shadow requirements that legacy missed
        legacy_descs = " ".join(
            (r.get("description", "") + " " + r.get("id", "")) for r in legacy_flat
        ).lower()

        omitted_by_legacy = []
        for s_r in shadow_reqs:
            s_title = s_r.get("title", "").lower()
            s_ep = s_r.get("epistemic_status", "")
            if s_ep in ["EXPLICIT", "DERIVED_JUSTIFIED"] and s_title:
                # Check if core keywords appear in legacy
                keywords = [w for w in s_title.split() if len(w) > 4]
                if keywords and not all(k in legacy_descs for k in keywords[:2]):
                    omitted_by_legacy.append({
                        "id": s_r.get("id"),
                        "title": s_r.get("title"),
                        "type": s_r.get("type"),
                        "epistemic_status": s_ep,
                        "why_chain": s_r.get("why_chain", [])
                    })

        # Detect hallucinated legacy UI pages
        hallucinated_by_legacy = []
        if isinstance(legacy_pages_dict, dict):
            for role, pages in legacy_pages_dict.items():
                for p in pages:
                    hallucinated_by_legacy.append(f"[{role}] {p.get('route', '/')}: {p.get('page_name', 'Page')}")

        # Epistemic unknowns in shadow
        epistemic_unknowns = [
            {
                "id": s_r.get("id"),
                "title": s_r.get("title"),
                "description": s_r.get("description")
            }
            for s_r in shadow_reqs
            if s_r.get("epistemic_status") == "UNKNOWN"
        ]

        return SemanticDiffReport(
            legacy_requirement_count=legacy_req_count,
            shadow_requirement_count=shadow_req_count,
            legacy_page_spreads_count=legacy_page_count,
            shadow_page_spreads_count=shadow_page_count,
            scope_explosion_delta=scope_explosion_delta,
            page_spread_hallucination_delta=page_spread_hallucination_delta,
            omitted_by_legacy=omitted_by_legacy,
            hallucinated_by_legacy=hallucinated_by_legacy,
            conflated_invariants_count=len(omitted_by_legacy),
            epistemic_unknowns_flagged=epistemic_unknowns
        )
