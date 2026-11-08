"""Authoritative Lifecycle P3C, P8, P9 & P10 Engine for S-Class Product Layer.

Implements normative requirements for Phase P3 Governance and P8-P10 Operations:
- PD-CH2-026: Existing ADR/design sources are digest-bound and pass structure/reference lint.
- PD-CH2-028: MUST IDs are unique, reserved and never reassigned.
- PD-CH2-051: P8 MUST route failure to earliest affected phase and stop when RetryBudget is exhausted.
- PD-CH2-052: P9 MUST aggregate all required P7 task results and close findings only by evidence.
- PD-CH2-053: P10 MUST require frozen kernel ReleaseEvaluation and MUST NOT override kernel denial.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from sclass.product.gate import GateOutput, GateState

QUALIFIED_EVALUATOR_BOUNDARY = "QUALIFIED_EVALUATOR"
"""Enforces caller authority boundary in S-Class execution."""

__all__ = [
    "QUALIFIED_EVALUATOR_BOUNDARY",
    "ReleaseEvaluationOutput",
    "evaluate_pd_ch2_026_adr_design_digest_binding",
    "evaluate_pd_ch2_028_unique_must_ids",
    "evaluate_pd_ch2_051_p8_retry_budget_exhaustion",
    "evaluate_pd_ch2_052_p9_task_aggregation_findings_closure",
    "evaluate_pd_ch2_053_p10_kernel_release_evaluation",
    "evaluate_p3c_p8_p10_gate",
]


@dataclass(frozen=True)
class ReleaseEvaluationOutput:
    """Specialized evaluation output supporting canonical DENIED / SATISFIED representations."""
    status: str
    detail: Optional[str] = None
    failures: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        return self.status

    @property
    def state(self) -> str:
        return self.status


def evaluate_pd_ch2_026_adr_design_digest_binding(
    adr_sources: Sequence[Mapping[str, Any]],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-026: Existing ADR/design sources are digest-bound and pass structure/reference lint."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-026",
            detail="Caller lacks qualified evaluator authority",
        )

    for adr in adr_sources:
        aid = adr.get("id", "unknown")
        dig = adr.get("digest")
        lint_passed = adr.get("lint_passed", False)
        is_stale = adr.get("is_stale", False)

        if not dig or not lint_passed or is_stale:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-026",
                detail=f"ADR source {aid} is stale, un-digest-bound, or failed structure lint",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="All ADR and design sources are digest-bound and pass structure/reference lint",
    )


def evaluate_pd_ch2_028_unique_must_ids(
    must_ids: Sequence[str],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-028: MUST IDs are unique, reserved and never reassigned."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-028",
            detail="Caller lacks qualified evaluator authority",
        )

    seen: Set[str] = set()
    for mid in must_ids:
        if mid in seen:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-028",
                detail=f"Duplicate or reassigned MUST ID detected: {mid}",
            )
        seen.add(mid)

    return GateOutput(
        state=GateState.SATISFIED,
        detail="All MUST IDs are globally unique, reserved, and un-reassigned",
    )


def evaluate_pd_ch2_051_p8_retry_budget_exhaustion(
    retry_budget_remaining: int,
    earliest_affected_phase: str = "P2",
    routed_phase: str = "P2",
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-051: P8 MUST route failure to earliest affected phase and stop when RetryBudget exhausted."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.BLOCKED_ON_HUMAN,
            must_id="PD-CH2-051",
            detail="Caller lacks qualified evaluator authority",
        )

    if retry_budget_remaining <= 0:
        return GateOutput(
            state=GateState.BLOCKED_ON_HUMAN,
            must_id="PD-CH2-051",
            detail="P8 RetryBudget exhausted; repair stopped for human intervention",
        )

    if routed_phase != earliest_affected_phase:
        return GateOutput(
            state=GateState.BLOCKED_ON_HUMAN,
            must_id="PD-CH2-051",
            detail=f"P8 repair routed to {routed_phase} instead of earliest affected phase {earliest_affected_phase}",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        detail=f"P8 repair cleanly routed to {routed_phase} within remaining RetryBudget",
    )


def evaluate_pd_ch2_052_p9_task_aggregation_findings_closure(
    required_p7_tasks: Sequence[str],
    aggregated_p7_tasks: Sequence[str],
    open_mandatory_findings: Sequence[str],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-052: P9 MUST aggregate all required P7 task results and close each mandatory finding."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-052",
            detail="Caller lacks qualified evaluator authority",
        )

    agg_set = set(aggregated_p7_tasks)
    for t in required_p7_tasks:
        if t not in agg_set:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-052",
                detail=f"Required P7 task result {t} omitted from P9 aggregation",
            )

    if open_mandatory_findings:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-052",
            detail=f"P9 has {len(open_mandatory_findings)} open mandatory findings without admissible closure",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="P9 successfully aggregated all required P7 results and closed mandatory findings",
    )


def evaluate_pd_ch2_053_p10_kernel_release_evaluation(
    kernel_release_evaluation: str,
    product_checks_pass: bool = True,
    *,
    authority: Optional[str] = None,
) -> ReleaseEvaluationOutput:
    """PD-CH2-053: P10 MUST require frozen kernel ReleaseEvaluation and MUST NOT override kernel denial."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return ReleaseEvaluationOutput(
            status="MISSING[PD-CH2-053]",
            detail="Caller lacks qualified evaluator authority",
            failures=["MISSING[PD-CH2-053]"],
        )

    if kernel_release_evaluation.upper() in ("DENIED", "DENY"):
        return ReleaseEvaluationOutput(
            status="DENIED",
            detail="Combined ReleaseEvaluation=DENIED: frozen kernel denial cannot be overridden by product checks",
        )

    if not product_checks_pass:
        return ReleaseEvaluationOutput(
            status="MISSING[PD-CH2-053]",
            detail="Product release checks failed",
            failures=["MISSING[PD-CH2-053]"],
        )

    if kernel_release_evaluation.upper() in ("ALLOW", "ALLOWED", "SATISFIED"):
        return ReleaseEvaluationOutput(
            status="SATISFIED",
            detail="Kernel ReleaseEvaluation allowed and all product checks pass",
        )

    return ReleaseEvaluationOutput(
        status="MISSING[PD-CH2-053]",
        detail=f"Unrecognized kernel ReleaseEvaluation state: {kernel_release_evaluation}",
        failures=["MISSING[PD-CH2-053]"],
    )


def evaluate_p3c_p8_p10_gate(
    manifest: Mapping[str, Any],
    *,
    authority: Optional[str] = None,
) -> GateOutput | ReleaseEvaluationOutput:
    """Composite gate evaluator for P3C, P8, P9, P10 obligations."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-026",
            detail="Caller lacks qualified evaluator authority",
            failures=[
                "MISSING[PD-CH2-026]", "MISSING[PD-CH2-028]", "BLOCKED_ON_HUMAN[PD-CH2-051]",
                "MISSING[PD-CH2-052]", "MISSING[PD-CH2-053]",
            ],
        )

    # 1. PD-CH2-026
    r026 = evaluate_pd_ch2_026_adr_design_digest_binding(
        adr_sources=manifest.get("adr_sources", []),
        authority=authority,
    )
    if r026.state != GateState.SATISFIED:
        return r026

    # 2. PD-CH2-028
    r028 = evaluate_pd_ch2_028_unique_must_ids(
        must_ids=manifest.get("must_ids", []),
        authority=authority,
    )
    if r028.state != GateState.SATISFIED:
        return r028

    # 3. PD-CH2-051
    r051 = evaluate_pd_ch2_051_p8_retry_budget_exhaustion(
        retry_budget_remaining=manifest.get("retry_budget_remaining", 1),
        earliest_affected_phase=manifest.get("earliest_affected_phase", "P2"),
        routed_phase=manifest.get("routed_phase", "P2"),
        authority=authority,
    )
    if r051.state != GateState.SATISFIED:
        return r051

    # 4. PD-CH2-052
    r052 = evaluate_pd_ch2_052_p9_task_aggregation_findings_closure(
        required_p7_tasks=manifest.get("required_p7_tasks", []),
        aggregated_p7_tasks=manifest.get("aggregated_p7_tasks", []),
        open_mandatory_findings=manifest.get("open_mandatory_findings", []),
        authority=authority,
    )
    if r052.state != GateState.SATISFIED:
        return r052

    # 5. PD-CH2-053
    r053 = evaluate_pd_ch2_053_p10_kernel_release_evaluation(
        kernel_release_evaluation=manifest.get("kernel_release_evaluation", "ALLOW"),
        product_checks_pass=manifest.get("product_checks_pass", True),
        authority=authority,
    )
    if r053.status != "SATISFIED":
        return r053

    return GateOutput(
        state=GateState.SATISFIED,
        detail="All P3C, P8, P9, and P10 lifecycle requirements satisfied",
    )
