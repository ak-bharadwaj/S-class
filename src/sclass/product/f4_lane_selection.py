"""Authoritative Lane Selection Engine (F4) for S-Class Product Layer.

Implements normative requirements for Phase F4:
- PD-F4-001: Deterministic lane selection from canonical depth dimensions, change flags, critical policy, and Micro eligibility.
- PD-F4-002: Critical lane application at D4/D5 or critical flag; Micro eligibility checks; lower requested lane fails closed (MISSING[PD-F4-002]).
- PD-F4-003: Non-reduction of depth floor and preservation of applicable F1 representation obligations (consumes evaluate_f1_representation).
- PD-F4-004: Assignment budget, adapter resource class, and interruption default by depth level.
- PD-F4-005: Canonical profile revision and authorized Decision escalation storage for replayable escalation.
- PD-F4-006: Adaptive-depth precedence (policy floor override) and depth-to-independence alignment with PD-F1-002.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from sclass.product.artifacts import (
    QUALIFIED_EVALUATOR_BOUNDARY as ARTIFACTS_BOUNDARY,
    evaluate_f1_representation,
)
from sclass.product.gate import GateOutput, GateState

QUALIFIED_EVALUATOR_BOUNDARY = "QUALIFIED_EVALUATOR"
"""Enforces caller authority. The real boundary is caller wiring in S-Class execution."""

__all__ = [
    "QUALIFIED_EVALUATOR_BOUNDARY",
    "Lane",
    "DepthLevel",
    "BudgetTriple",
    "EscalationRecord",
    "BUDGET_TABLE",
    "INDEPENDENCE_FLOOR_TABLE",
    "compute_lane",
    "resolve_effective_depth",
    "get_depth_budget",
    "record_lane_escalation",
    "replay_lane",
    "evaluate_f4_lane_selection",
]


class Lane(str, enum.Enum):
    """Execution lanes ordered by ceremony and rigor."""
    MICRO = "MICRO"
    STANDARD = "STANDARD"
    CRITICAL = "CRITICAL"

    @property
    def rank(self) -> int:
        ranks = {Lane.MICRO: 0, Lane.STANDARD: 1, Lane.CRITICAL: 2}
        return ranks[self]

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Lane):
            return self.rank < other.rank
        if isinstance(other, str):
            return self.rank < Lane(other.upper()).rank
        return NotImplemented

    def __le__(self, other: Any) -> bool:
        if isinstance(other, Lane):
            return self.rank <= other.rank
        if isinstance(other, str):
            return self.rank <= Lane(other.upper()).rank
        return NotImplemented

    def __gt__(self, other: Any) -> bool:
        if isinstance(other, Lane):
            return self.rank > other.rank
        if isinstance(other, str):
            return self.rank > Lane(other.upper()).rank
        return NotImplemented

    def __ge__(self, other: Any) -> bool:
        if isinstance(other, Lane):
            return self.rank >= other.rank
        if isinstance(other, str):
            return self.rank >= Lane(other.upper()).rank
        return NotImplemented


class DepthLevel(str, enum.Enum):
    """Depth levels D0 through D5."""
    D0 = "D0"
    D1 = "D1"
    D2 = "D2"
    D3 = "D3"
    D4 = "D4"
    D5 = "D5"

    @property
    def level(self) -> int:
        levels = {"D0": 0, "D1": 1, "D2": 2, "D3": 3, "D4": 4, "D5": 5}
        return levels[self.value]


@dataclass(frozen=True)
class BudgetTriple:
    """Declared budget triple per depth level (PD-F4-004)."""
    depth: str
    max_assignments: int
    adapter_resource_limits_class: str
    interruption_budget: int


@dataclass(frozen=True)
class EscalationRecord:
    """Canonical escalation record for replayability (PD-F4-005)."""
    canonical_profile_revision: int
    prior_lane: str
    escalated_lane: str
    reason: str
    authorized_decision: Optional[str] = None


BUDGET_TABLE: Dict[str, BudgetTriple] = {
    "D0": BudgetTriple("D0", 32, "EVAL-TINY", 0),
    "D1": BudgetTriple("D1", 128, "EVAL-SMALL", 0),
    "D2": BudgetTriple("D2", 1024, "EVAL-MEDIUM", 1),
    "D3": BudgetTriple("D3", 8192, "EVAL-LARGE", 2),
    "D4": BudgetTriple("D4", 65536, "EVAL-CRITICAL", 3),
    "D5": BudgetTriple("D5", 262144, "EVAL-CRITICAL-PLUS", 4),
}

INDEPENDENCE_FLOOR_TABLE: Dict[str, str] = {
    "D0": "Record applicable common-cause dimensions; no additional independent verifier floor unless policy requires it.",
    "D1": "Track model/provider/version and context lineage.",
    "D2": "Require separation across model/provider/version and prompt/context/toolchain.",
    "D3": "Require D2 plus execution-environment separation.",
    "D4": "Require D3 plus common-test-generation separation and a qualified independent verifier where required by the obligation.",
    "D5": "Require all D4 dimensions plus human/policy control at the critical gate when applicable.",
}


def _parse_depth_value(val: Any) -> int:
    if isinstance(val, int):
        return val
    s = str(val).strip().upper()
    if s.startswith("D") and s[1:].isdigit():
        return int(s[1:])
    try:
        return int(s)
    except ValueError:
        return 0


def resolve_effective_depth(
    profile_derived_depth: Union[str, DepthLevel],
    policy_floor: Union[str, DepthLevel],
) -> Tuple[str, str]:
    """Resolves effective depth honoring policy floor precedence (PD-F4-006)."""
    p_val = _parse_depth_value(profile_derived_depth)
    f_val = _parse_depth_value(policy_floor)
    eff_val = max(p_val, f_val)
    eff_str = f"D{eff_val}"
    ind_floor = INDEPENDENCE_FLOOR_TABLE.get(eff_str, INDEPENDENCE_FLOOR_TABLE["D0"])
    return eff_str, ind_floor


def get_depth_budget(depth: Union[str, DepthLevel]) -> BudgetTriple:
    """Looks up declared assignment budget triple by depth level (PD-F4-004)."""
    s = str(depth).strip().upper()
    if s in BUDGET_TABLE:
        return BUDGET_TABLE[s]
    n = _parse_depth_value(s)
    key = f"D{min(5, max(0, n))}"
    return BUDGET_TABLE[key]


def compute_lane(
    payload: Mapping[str, Any],
    policy_floor: Optional[str] = None,
) -> Lane:
    """Computes deterministic lane from canonical inputs (PD-F4-001, PD-F4-002, PD-F4-006)."""
    depth_dims = payload.get("depth_dimensions", {})
    if not isinstance(depth_dims, dict):
        depth_dims = {}

    max_dim_val = 0
    for dim_name, dim_val in depth_dims.items():
        val = _parse_depth_value(dim_val)
        if val > max_dim_val:
            max_dim_val = val

    if "profile_derived_depth" in payload:
        p_val = _parse_depth_value(payload["profile_derived_depth"])
        if p_val > max_dim_val:
            max_dim_val = p_val
    if policy_floor:
        f_val = _parse_depth_value(policy_floor)
        if f_val > max_dim_val:
            max_dim_val = f_val
    elif "policy_floor" in payload:
        f_val = _parse_depth_value(payload["policy_floor"])
        if f_val > max_dim_val:
            max_dim_val = f_val

    critical_flag = bool(payload.get("critical_flag", False))
    security_change = bool(payload.get("security_change", False))
    policy_critical_predicate = bool(payload.get("policy_critical_predicate", False))

    if max_dim_val >= 4 or critical_flag or security_change or policy_critical_predicate:
        return Lane.CRITICAL

    if max_dim_val <= 1:
        is_micro_eligible = True

        risk_tier = str(payload.get("risk_tier", "LOW")).upper()
        if risk_tier != "LOW":
            is_micro_eligible = False

        failure_impact = str(payload.get("failure_impact", "LOW")).upper()
        if failure_impact != "LOW":
            is_micro_eligible = False

        reg_sens = str(payload.get("regulatory_sensitivity", "NONE")).upper()
        if reg_sens != "NONE":
            is_micro_eligible = False

        req_ind = str(payload.get("required_independence", "NONE")).upper()
        if req_ind != "NONE":
            is_micro_eligible = False

        if payload.get("irreversibility", False):
            is_micro_eligible = False

        if not payload.get("rollback_capability", True):
            is_micro_eligible = False

        if payload.get("estimated_files", 0) > 2:
            is_micro_eligible = False

        if payload.get("modules", 0) > 1:
            is_micro_eligible = False

        sec_sens = str(payload.get("security_sensitivity", "NONE")).upper()
        if sec_sens != "NONE":
            is_micro_eligible = False

        cs = payload.get("change_surface", {})
        if isinstance(cs, dict):
            if any(cs.get(k, 0) > 0 for k in ("apis", "databases", "schemas", "external_integrations", "deployment_surfaces")):
                is_micro_eligible = False

        if payload.get("api_change", False) or payload.get("data_model_change", False):
            is_micro_eligible = False

        ee = payload.get("external_effects", {})
        if isinstance(ee, dict):
            if ee.get("external_systems", 0) > 0 or ee.get("user_visible_effects", False) or ee.get("financial_effects", False) or ee.get("security_effects", False):
                is_micro_eligible = False

        if is_micro_eligible:
            return Lane.MICRO

    return Lane.STANDARD


def record_lane_escalation(
    canonical_profile_revision: int,
    prior_lane: str,
    escalated_lane: str,
    reason: str,
    authorized_decision: Optional[str] = None,
) -> EscalationRecord:
    """Stores lane escalation as a canonical profile revision (PD-F4-005)."""
    return EscalationRecord(
        canonical_profile_revision=canonical_profile_revision,
        prior_lane=prior_lane,
        escalated_lane=escalated_lane,
        reason=reason,
        authorized_decision=authorized_decision,
    )


def replay_lane(
    replayed_profile_revision: int,
    escalations: Sequence[EscalationRecord],
    default_lane: Lane = Lane.STANDARD,
) -> Lane:
    """Reproduces escalated lane deterministically on replay (PD-F4-005)."""
    for esc in escalations:
        if esc.canonical_profile_revision == replayed_profile_revision:
            return Lane(esc.escalated_lane)
    return default_lane


def evaluate_f4_lane_selection(
    payload: Mapping[str, Any],
    caller_authority: Optional[str] = None,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """Evaluates lane selection gate conformance (PD-F4-001..PD-F4-006)."""
    effective_authority = authority if authority is not None else caller_authority
    if effective_authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F4-001",
            detail="Unauthorized lane evaluation: caller_authority must be QUALIFIED_EVALUATOR",
            failures=["MISSING[PD-F4-001]"],
        )

    if not isinstance(payload, Mapping) or not payload:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F4-001",
            detail="Invalid or empty payload mapping",
            failures=["MISSING[PD-F4-001]"],
        )

    # 1. Escalation replay: canonical EngineeringProfile revision replay (PD-F4-005)
    if "replayed_profile_revision" in payload:
        rec_rev = payload.get("canonical_profile_revision")
        rep_rev = payload.get("replayed_profile_revision")
        if rec_rev and rec_rev == rep_rev and "recorded_lane" in payload:
            computed = Lane(payload["recorded_lane"])
        else:
            computed = compute_lane(payload)
    else:
        computed = compute_lane(payload)

    # 2. Check requested lane vs computed lane (PD-F4-002)
    requested_str = payload.get("requested_lane")
    if not requested_str:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F4-002",
            detail="requested_lane is missing from payload",
            failures=["MISSING[PD-F4-002]"],
        )

    try:
        requested = Lane(str(requested_str).upper())
    except ValueError:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F4-002",
            detail=f"Unknown requested lane: {requested_str}",
            failures=["MISSING[PD-F4-002]"],
        )

    if requested < computed:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F4-002",
            detail=f"Requested lane {requested.value} is lower than computed lane {computed.value}",
            failures=["MISSING[PD-F4-002]"],
        )

    # 3. Check F1 representation obligation retention (PD-F4-003)
    if payload.get("f1_artifact_class") or payload.get("f1_required_representation"):
        art_class = payload.get("f1_artifact_class")
        req_rep = payload.get("f1_required_representation")

        if req_rep == "DDL" and not payload.get("ddl_present", True):
            f1_res = evaluate_f1_representation(
                {"artifact_class": art_class},
                caller_authority=ARTIFACTS_BOUNDARY,
            )
            return f1_res

    # 4. Check budget exhaustion and budget triple conformance (PD-F4-004)
    if payload.get("budget_exhausted", False):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F4-004",
            detail="Budget exhausted during lane evaluation: INCONCLUSIVE",
            failures=["MISSING[PD-F4-004]"],
        )

    # Resolve effective depth and budget triple (PD-F4-004, PD-F4-006)
    eff_depth, ind_floor = resolve_effective_depth(
        payload.get("profile_derived_depth", payload.get("depth", "D0")),
        payload.get("policy_floor", "D0"),
    )
    raw_depth = payload.get("depth", eff_depth if eff_depth != "D0" else "D1")
    budget = get_depth_budget(raw_depth)

    explain: Dict[str, Any] = {
        "computed_lane": computed.value,
        "requested_lane": requested.value,
        "effective_depth": eff_depth,
        "independence_floor": ind_floor,
        "budget_triple": {
            "depth": budget.depth,
            "max_assignments": budget.max_assignments,
            "adapter_resource_limits_class": budget.adapter_resource_limits_class,
            "interruption_budget": budget.interruption_budget,
        },
    }
    if "canonical_profile_revision" in payload:
        explain["canonical_profile_revision"] = payload["canonical_profile_revision"]
    if "replayed_profile_revision" in payload:
        explain["replayed_profile_revision"] = payload["replayed_profile_revision"]

    return GateOutput(
        state=GateState.SATISFIED,
        explain=explain,
    )
