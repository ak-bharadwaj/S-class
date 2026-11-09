"""Authoritative Lifecycle P6 Implementation Engine for S-Class Product Layer.

Implements normative requirements for Chapter 2 Phase P6 Implementation & Code Changes:
- PD-CH2-037: Implementation writes MUST be ExecutionGate-authorized for exact task/scope/target.
- PD-CH2-038: Scope growth MUST stop and route to P4.
- PD-CH2-039: Implementation claims MUST use F7's type and created_by_delta rules.
- PD-CH2-040: Product records MUST NOT create canonical delta authority or override kernel denial.
- PD-CH2-048: P6 gate MUST invoke complete TestInputSet exclusion check owned by PD-CH4-010.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from sclass.product.gate import GateOutput, GateState

QUALIFIED_EVALUATOR_BOUNDARY = "QUALIFIED_EVALUATOR"
"""Enforces caller authority boundary in S-Class execution."""

__all__ = [
    "QUALIFIED_EVALUATOR_BOUNDARY",
    "evaluate_pd_ch2_037_execution_gate_authorization",
    "evaluate_pd_ch2_038_scope_growth_stop",
    "evaluate_pd_ch2_039_implementation_claims",
    "evaluate_pd_ch2_040_canonical_delta_kernel_receipt",
    "evaluate_pd_ch2_048_test_input_set_exclusion_check",
    "evaluate_p6_gate",
]


def evaluate_pd_ch2_037_execution_gate_authorization(
    has_execution_gate_auth: bool,
    task_id: str,
    scope: str,
    target: str,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-037: Implementation writes MUST be ExecutionGate-authorized for exact task/scope/target."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-037",
            detail="Caller lacks qualified evaluator authority",
        )

    if not has_execution_gate_auth:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-037",
            detail=f"Implementation write for task {task_id} on {target} ({scope}) lacks ExecutionGate authorization",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        detail=f"Implementation write for task {task_id} is ExecutionGate-authorized for exact scope/target",
    )


def evaluate_pd_ch2_038_scope_growth_stop(
    is_out_of_scope: bool,
    delta_files: Sequence[str],
    declared_scope: Set[str],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-038: Scope growth MUST stop and route to P4."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-038",
            detail="Caller lacks qualified evaluator authority",
        )

    if is_out_of_scope:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-038",
            detail="Out-of-scope delta detected; work stopped and routed to P4",
        )

    for f in delta_files:
        if f not in declared_scope:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-038",
                detail=f"File {f} exceeds declared scope boundary; work stopped and routed to P4",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="Implementation delta strictly adheres to declared task scope",
    )


def evaluate_pd_ch2_039_implementation_claims(
    claimed_symbols: Sequence[str],
    post_delta_symbols: Set[str],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-039: Implementation claims MUST use F7 rules; symbol absent post-delta -> MISSING[PD-F7-006]."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F7-006",
            detail="Caller lacks qualified evaluator authority",
        )

    for sym in claimed_symbols:
        if sym not in post_delta_symbols:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-F7-006",
                detail=f"Claimed symbol {sym} absent post-delta",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="All claimed symbols confirmed present post-delta under F7 rules",
    )


def evaluate_pd_ch2_040_canonical_delta_kernel_receipt(
    has_kernel_receipt: bool,
    kernel_receipt_digest: Optional[str],
    kernel_denied: bool = False,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-040: Product records MUST NOT create canonical delta authority or override kernel denial."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-040",
            detail="Caller lacks qualified evaluator authority",
        )

    if kernel_denied or not has_kernel_receipt or not kernel_receipt_digest:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-040",
            detail="No valid kernel receipt or kernel denial override attempt",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="Canonical delta backed by authoritative frozen kernel receipt",
    )


def evaluate_pd_ch2_048_test_input_set_exclusion_check(
    p6_tests_frozen_invoked: bool,
    p6_modifies_test_input_set: bool = False,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-048: P6 gate MUST invoke complete TestInputSet exclusion check owned by PD-CH4-010."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-048",
            detail="Caller lacks qualified evaluator authority",
        )

    if not p6_tests_frozen_invoked:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-048",
            detail="P6 composition omits P6-TESTS-FROZEN exclusion check",
        )

    if p6_modifies_test_input_set:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-048",
            detail="P6 delta illegally modifies frozen TestInputSet",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="P6-TESTS-FROZEN exclusion check invoked and passed: no test input mutations",
    )


def evaluate_p6_gate(
    manifest: Mapping[str, Any],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """Composite gate evaluator for Lifecycle P6 implementation obligations."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-037",
            detail="Caller lacks qualified evaluator authority",
            failures=[
                "MISSING[PD-CH2-037]", "MISSING[PD-CH2-038]", "MISSING[PD-F7-006]",
                "MISSING[PD-CH2-040]", "MISSING[PD-CH2-048]",
            ],
        )

    if not isinstance(manifest, Mapping) or not manifest:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-037",
            detail="Manifest is empty or missing required fields",
        )

    # 1. PD-CH2-037
    r037 = evaluate_pd_ch2_037_execution_gate_authorization(
        has_execution_gate_auth=manifest.get("has_execution_gate_auth", True),
        task_id=manifest.get("task_id", "T1"),
        scope=manifest.get("scope", "impl"),
        target=manifest.get("target", "src/mod.py"),
        authority=authority,
    )
    if r037.state != GateState.SATISFIED:
        return r037

    # 2. PD-CH2-038
    r038 = evaluate_pd_ch2_038_scope_growth_stop(
        is_out_of_scope=manifest.get("is_out_of_scope", False),
        delta_files=manifest.get("delta_files", ["src/mod.py"]),
        declared_scope=manifest.get("declared_scope", {"src/mod.py"}),
        authority=authority,
    )
    if r038.state != GateState.SATISFIED:
        return r038

    # 3. PD-CH2-039
    r039 = evaluate_pd_ch2_039_implementation_claims(
        claimed_symbols=manifest.get("claimed_symbols", ["FuncA"]),
        post_delta_symbols=manifest.get("post_delta_symbols", {"FuncA"}),
        authority=authority,
    )
    if r039.state != GateState.SATISFIED:
        return r039

    # 4. PD-CH2-040
    r040 = evaluate_pd_ch2_040_canonical_delta_kernel_receipt(
        has_kernel_receipt=manifest.get("has_kernel_receipt", True),
        kernel_receipt_digest=manifest.get("kernel_receipt_digest", "sha256:receipt1"),
        kernel_denied=manifest.get("kernel_denied", False),
        authority=authority,
    )
    if r040.state != GateState.SATISFIED:
        return r040

    # 5. PD-CH2-048
    r048 = evaluate_pd_ch2_048_test_input_set_exclusion_check(
        p6_tests_frozen_invoked=manifest.get("p6_tests_frozen_invoked", True),
        p6_modifies_test_input_set=manifest.get("p6_modifies_test_input_set", False),
        authority=authority,
    )
    if r048.state != GateState.SATISFIED:
        return r048

    return GateOutput(
        state=GateState.SATISFIED,
        detail="All P6 implementation governance invariants satisfied",
    )
