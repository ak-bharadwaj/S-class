"""Authoritative Lifecycle P7 Verification Engine for S-Class Product Layer.

Implements normative requirements for Chapter 2 Phase P7 Verification & Evidence Governance:
- PD-CH2-041: Verification evidence MUST bind frozen evidence identity and current target/step.
- PD-CH2-042: Required adapter results MUST come from qualified F10 adapters.
- PD-CH2-043: Independence MUST meet F4 depth-derived floor.
- PD-CH2-044: Freshness MUST use frozen predicate at recorded evaluation instant.
- PD-CH2-045: Closure MUST be kernel-owned; per-task results use F5 schema and feed P9/P10.
- PD-CH2-050: P7 MUST reject nondeterministic test reruns; same inputs with [PASS, FAIL] -> non-SATISFIED.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from sclass.product.gate import GateOutput, GateState

QUALIFIED_EVALUATOR_BOUNDARY = "QUALIFIED_EVALUATOR"
"""Enforces caller authority boundary in S-Class execution."""

DEFAULT_QUALIFIED_ADAPTERS: Set[str] = {
    "pytest-sclass", "junit-sclass", "cargo-test-sclass", "go-test-sclass"
}

__all__ = [
    "QUALIFIED_EVALUATOR_BOUNDARY",
    "DEFAULT_QUALIFIED_ADAPTERS",
    "evaluate_pd_ch2_041_evidence_binding",
    "evaluate_pd_ch2_042_adapter_qualification",
    "evaluate_pd_ch2_043_independence_floor",
    "evaluate_pd_ch2_044_freshness_predicate",
    "evaluate_pd_ch2_045_closure_ownership",
    "evaluate_pd_ch2_050_deterministic_rerun",
    "evaluate_p7_gate",
]


def evaluate_pd_ch2_041_evidence_binding(
    evidence_identity_bound: bool,
    current_target_bound: bool,
    current_step_bound: bool,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-041: Verification evidence MUST bind frozen evidence identity and current target/step."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-041",
            detail="Caller lacks qualified evaluator authority",
        )

    if type(evidence_identity_bound) is not bool or type(current_target_bound) is not bool or type(current_step_bound) is not bool:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-041",
            detail="All arguments must be exact booleans",
        )

    if not (evidence_identity_bound and current_target_bound and current_step_bound):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-041",
            detail="Missing frozen evidence identity, current target, or current step binding",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="Verification evidence cleanly bound to frozen identity, target, and step",
    )


def evaluate_pd_ch2_042_adapter_qualification(
    adapter_name: str,
    is_f10_qualified: bool,
    *,
    qualified_adapters: Set[str] = DEFAULT_QUALIFIED_ADAPTERS,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-042: Required adapter results MUST come from qualified F10 adapters."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-042",
            detail="Caller lacks qualified evaluator authority",
        )
    try:
        if not isinstance(adapter_name, str) or type(is_f10_qualified) is not bool or not isinstance(qualified_adapters, (set, frozenset, list, tuple)) or isinstance(qualified_adapters, (str, bytes)):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-042",
                detail="Invalid adapter argument types",
            )

        if not is_f10_qualified or adapter_name not in qualified_adapters:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-042",
                detail=f"Verification adapter {adapter_name} is unqualified under F10",
            )

        return GateOutput(
            state=GateState.SATISFIED,
            detail=f"Verification adapter {adapter_name} qualified under F10",
        )
    except Exception as e:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-042",
            detail=f"Adversarial input rejected: {type(e).__name__}",
        )


def evaluate_pd_ch2_043_independence_floor(
    independence_level: int,
    required_floor: int,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-043: Independence MUST meet F4 depth-derived floor."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-043",
            detail="Caller lacks qualified evaluator authority",
        )

    if type(independence_level) is not int or type(required_floor) is not int or independence_level > 1000 or required_floor > 1000:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-043",
            detail="Arguments must be bounded exact ints",
        )

    if independence_level < required_floor:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-043",
            detail=f"Independence floor not met: level {independence_level} < required floor {required_floor}",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        detail=f"Independence level ({independence_level}) meets depth-derived floor ({required_floor})",
    )


def evaluate_pd_ch2_044_freshness_predicate(
    evidence_digest: str,
    current_code_digest: str,
    is_stale: Optional[bool] = None,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-044: Freshness MUST use frozen predicate at recorded evaluation instant."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-044",
            detail="Caller lacks qualified evaluator authority",
        )

    _is = False if is_stale is None else is_stale
    if (
        not isinstance(evidence_digest, str) or not evidence_digest
        or not isinstance(current_code_digest, str) or not current_code_digest
        or type(_is) is not bool
    ):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-044",
            detail="Arguments must be non-empty strings and exact bool",
        )

    if _is or evidence_digest != current_code_digest:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-044",
            detail="Stale evidence digest: verification evidence does not match current code digest",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="Verification evidence freshness verified at evaluation instant",
    )


def evaluate_pd_ch2_045_closure_ownership(
    kernel_closure_result: Optional[str],
    agent_asserts_closure: Optional[bool] = None,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-045: Closure MUST be kernel-owned; agent assertions without kernel closure rejected."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-045",
            detail="Caller lacks qualified evaluator authority",
        )
    try:

        _aac = False if agent_asserts_closure is None else agent_asserts_closure
        if _aac or not kernel_closure_result or kernel_closure_result.upper() != "CLOSED":
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-045",
                detail="Agent asserts closure without authoritative kernel result",
            )

        return GateOutput(
            state=GateState.SATISFIED,
            detail="Task closure verified by authoritative kernel evaluation",
        )
    except Exception as e:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-045",
            detail=f"Adversarial input rejected: {type(e).__name__}",
        )


def evaluate_pd_ch2_050_deterministic_rerun(
    rerun_results: Sequence[str],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-050: P7 MUST reject nondeterministic test reruns; [PASS, FAIL] -> non-SATISFIED."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-050",
            detail="Caller lacks qualified evaluator authority",
        )

    if not isinstance(rerun_results, (list, tuple, set)) or isinstance(rerun_results, (str, bytes)) or not rerun_results:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-050",
            detail="rerun_results must be a non-empty sequence of strings",
        )

    if len(rerun_results) > 10000:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-050",
            detail="rerun_results exceeds maximum limit (10000)",
        )

    for r in rerun_results:
        if not isinstance(r, str):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-050",
                detail="Each rerun result must be a string",
            )

    distinct = set(rerun_results)
    if len(distinct) > 1:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-050",
            detail=f"Nondeterministic rerun results across identical inputs: {list(rerun_results)}",
        )

    if any(r.upper() not in ("PASS", "SATISFIED") for r in rerun_results):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-050",
            detail=f"Test reruns did not pass: {list(rerun_results)}",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="Test execution determinism confirmed across all reruns",
    )


def evaluate_p7_gate(
    manifest: Mapping[str, Any],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """Composite gate evaluator for Lifecycle P7 verification obligations."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-041",
            detail="Caller lacks qualified evaluator authority",
            failures=[
                "MISSING[PD-CH2-041]", "MISSING[PD-CH2-042]", "MISSING[PD-CH2-043]",
                "MISSING[PD-CH2-044]", "MISSING[PD-CH2-045]", "MISSING[PD-CH2-050]",
            ],
        )

    if not isinstance(manifest, Mapping) or not manifest:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-041",
            detail="Manifest is empty or missing required fields",
        )

    required_keys = {
        "evidence_identity_bound", "current_target_bound", "current_step_bound",
        "adapter_name", "is_f10_qualified",
        "independence_level", "required_floor",
        "evidence_digest", "current_code_digest", "is_stale",
        "kernel_closure_result", "agent_asserts_closure",
        "rerun_results",
    }
    if not required_keys.issubset(manifest.keys()):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-041",
            detail=f"Missing required manifest keys: {required_keys - set(manifest.keys())}",
        )

    # 1. PD-CH2-041
    r041 = evaluate_pd_ch2_041_evidence_binding(
        evidence_identity_bound=manifest.get("evidence_identity_bound"),
        current_target_bound=manifest.get("current_target_bound"),
        current_step_bound=manifest.get("current_step_bound"),
        authority=authority,
    )
    if r041.state != GateState.SATISFIED:
        return r041

    # 2. PD-CH2-042
    r042 = evaluate_pd_ch2_042_adapter_qualification(
        adapter_name=manifest.get("adapter_name"),
        is_f10_qualified=manifest.get("is_f10_qualified"),
        authority=authority,
    )
    if r042.state != GateState.SATISFIED:
        return r042

    # 3. PD-CH2-043
    r043 = evaluate_pd_ch2_043_independence_floor(
        independence_level=manifest.get("independence_level"),
        required_floor=manifest.get("required_floor"),
        authority=authority,
    )
    if r043.state != GateState.SATISFIED:
        return r043

    # 4. PD-CH2-044
    r044 = evaluate_pd_ch2_044_freshness_predicate(
        evidence_digest=manifest.get("evidence_digest"),
        current_code_digest=manifest.get("current_code_digest"),
        is_stale=manifest.get("is_stale"),
        authority=authority,
    )
    if r044.state != GateState.SATISFIED:
        return r044

    # 5. PD-CH2-045
    r045 = evaluate_pd_ch2_045_closure_ownership(
        kernel_closure_result=manifest.get("kernel_closure_result"),
        agent_asserts_closure=manifest.get("agent_asserts_closure"),
        authority=authority,
    )
    if r045.state != GateState.SATISFIED:
        return r045

    # 6. PD-CH2-050
    r050 = evaluate_pd_ch2_050_deterministic_rerun(
        rerun_results=manifest.get("rerun_results"),
        authority=authority,
    )
    if r050.state != GateState.SATISFIED:
        return r050

    return GateOutput(
        state=GateState.SATISFIED,
        detail="All P7 verification evidence and rerun invariants satisfied",
    )
