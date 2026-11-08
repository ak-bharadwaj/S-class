"""Authoritative Lifecycle P5 Test-First & Red Execution Engine for S-Class Product Layer.

Implements normative requirements for Chapter 2 Phase P5 Test Construction & Red Run Governance:
- PD-CH2-033: Test canonical delta MUST precede implementation delta by canonical delta sequence.
- PD-CH2-034: Red run MUST come from qualified adapter and fail designed test for designed assertion class.
- PD-CH2-035: Executable specifications MUST satisfy F1/F2 representation and finite-domain constraints.
- PD-CH2-036: Required test adapters MUST be qualified under F10.
- PD-CH2-046: Primary test digest MUST be present in complete TestInputSet before authorizing red run.
- PD-CH2-047: Red classification MUST use adapter structured result and designed test/reason tuple, never agent assertions.
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
    "evaluate_pd_ch2_033_delta_sequence",
    "evaluate_pd_ch2_034_red_run_validity",
    "evaluate_pd_ch2_035_executable_spec_constraints",
    "evaluate_pd_ch2_036_adapter_qualification",
    "evaluate_pd_ch2_046_test_input_set_binding",
    "evaluate_pd_ch2_047_red_classification_source",
    "evaluate_p5_gate",
]


def evaluate_pd_ch2_033_delta_sequence(
    test_delta_seq: int,
    impl_delta_seq: int,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-033: Test-carrying canonical delta MUST precede implementation delta by sequence."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-033",
            detail="Caller lacks qualified evaluator authority",
        )

    if impl_delta_seq <= test_delta_seq:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-033",
            detail=f"Implementation delta seq ({impl_delta_seq}) ordered before or at test delta seq ({test_delta_seq})",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        detail=f"Test-first ordering preserved: test delta ({test_delta_seq}) strictly precedes impl delta ({impl_delta_seq})",
    )


def evaluate_pd_ch2_034_red_run_validity(
    adapter_qualified: bool,
    run_failed_designed_test: bool,
    failure_class: str,
    designed_class: str,
    harness_error: bool = False,
    skipped_or_xfail: bool = False,
    timeout: bool = False,
    unstable_flaky: bool = False,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-034: Valid red run from qualified adapter failing designed test."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-034",
            detail="Caller lacks qualified evaluator authority",
        )

    if not adapter_qualified:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-034",
            detail="Red run did not come from a qualified adapter",
        )

    if not run_failed_designed_test:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-034",
            detail="Red run did not fail the designed test",
        )

    if failure_class != designed_class:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-034",
            detail=f"Failure class mismatch ({failure_class} != {designed_class})",
        )

    if harness_error or skipped_or_xfail or timeout or unstable_flaky:
        reason = "harness_error" if harness_error else "skipped_or_xfail" if skipped_or_xfail else "timeout" if timeout else "flaky"
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-034",
            detail=f"Invalid red run due to {reason}",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="Valid red run: qualified adapter failed designed test for designed assertion class",
    )


def evaluate_pd_ch2_035_executable_spec_constraints(
    is_executable_f1_f2: bool,
    finite_domain: bool,
    is_prose_only: bool = False,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-035: Executable specifications MUST satisfy F1/F2 finite-domain constraints."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-035",
            detail="Caller lacks qualified evaluator authority",
        )

    if is_prose_only or not is_executable_f1_f2 or not finite_domain:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-035",
            detail="Specification is prose-only, non-executable, or unbounded",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="Executable specification satisfies F1/F2 finite-domain constraints",
    )


def evaluate_pd_ch2_036_adapter_qualification(
    adapter_name: str,
    *,
    qualified_adapters: Set[str] = DEFAULT_QUALIFIED_ADAPTERS,
    is_f10_qualified: bool = True,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-036: Required test adapters MUST be qualified under F10."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-036",
            detail="Caller lacks qualified evaluator authority",
        )

    if not is_f10_qualified or adapter_name not in qualified_adapters:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-036",
            detail=f"Test adapter {adapter_name} is unqualified under F10",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        detail=f"Test adapter {adapter_name} is fully qualified under F10",
    )


def evaluate_pd_ch2_046_test_input_set_binding(
    primary_test_digest: Optional[str],
    bound_test_input_set: Mapping[str, str],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-046: Primary test digest MUST be present in TestInputSet before authorizing red run."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-046",
            detail="Caller lacks qualified evaluator authority",
        )

    if not primary_test_digest or primary_test_digest not in bound_test_input_set.values():
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-046",
            detail="Red run requested before primary test digest is bound in complete TestInputSet",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="Primary test digest bound in complete TestInputSet under PD-CH4-009",
    )


def evaluate_pd_ch2_047_red_classification_source(
    adapter_structured_result: Mapping[str, Any],
    designed_test_tuple: Tuple[str, str],
    agent_assertion_used: bool = False,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-047: Red classification MUST use adapter structured result, never agent assertions."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-047",
            detail="Caller lacks qualified evaluator authority",
        )

    if agent_assertion_used:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-047",
            detail="Red classification used agent assertions instead of adapter result",
        )

    failed_test = adapter_structured_result.get("failed_test")
    failed_reason = adapter_structured_result.get("failure_reason")

    if (failed_test, failed_reason) != designed_test_tuple:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-047",
            detail=f"Adapter result ({failed_test}, {failed_reason}) targets wrong behavior; expected {designed_test_tuple}",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="Red classification validated directly against adapter structured result",
    )


def evaluate_p5_gate(
    manifest: Mapping[str, Any],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """Composite gate evaluator for Lifecycle P5 obligations."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-033",
            detail="Caller lacks qualified evaluator authority",
            failures=[
                "MISSING[PD-CH2-033]", "MISSING[PD-CH2-034]", "MISSING[PD-CH2-035]",
                "MISSING[PD-CH2-036]", "MISSING[PD-CH2-046]", "MISSING[PD-CH2-047]",
            ],
        )

    # 1. PD-CH2-033
    r033 = evaluate_pd_ch2_033_delta_sequence(
        test_delta_seq=manifest.get("test_delta_seq", 1),
        impl_delta_seq=manifest.get("impl_delta_seq", 2),
        authority=authority,
    )
    if r033.state != GateState.SATISFIED:
        return r033

    # 2. PD-CH2-034
    r034 = evaluate_pd_ch2_034_red_run_validity(
        adapter_qualified=manifest.get("adapter_qualified", True),
        run_failed_designed_test=manifest.get("run_failed_designed_test", True),
        failure_class=manifest.get("failure_class", "AssertionError"),
        designed_class=manifest.get("designed_class", "AssertionError"),
        authority=authority,
    )
    if r034.state != GateState.SATISFIED:
        return r034

    # 3. PD-CH2-035
    r035 = evaluate_pd_ch2_035_executable_spec_constraints(
        is_executable_f1_f2=manifest.get("is_executable_f1_f2", True),
        finite_domain=manifest.get("finite_domain", True),
        is_prose_only=manifest.get("is_prose_only", False),
        authority=authority,
    )
    if r035.state != GateState.SATISFIED:
        return r035

    # 4. PD-CH2-036
    r036 = evaluate_pd_ch2_036_adapter_qualification(
        adapter_name=manifest.get("adapter_name", "pytest-sclass"),
        authority=authority,
    )
    if r036.state != GateState.SATISFIED:
        return r036

    # 5. PD-CH2-046
    r046 = evaluate_pd_ch2_046_test_input_set_binding(
        primary_test_digest=manifest.get("primary_test_digest", "sha256:test1"),
        bound_test_input_set=manifest.get("bound_test_input_set", {"test.py": "sha256:test1"}),
        authority=authority,
    )
    if r046.state != GateState.SATISFIED:
        return r046

    # 6. PD-CH2-047
    r047 = evaluate_pd_ch2_047_red_classification_source(
        adapter_structured_result=manifest.get("adapter_structured_result", {"failed_test": "test_x", "failure_reason": "fail"}),
        designed_test_tuple=manifest.get("designed_test_tuple", ("test_x", "fail")),
        agent_assertion_used=manifest.get("agent_assertion_used", False),
        authority=authority,
    )
    if r047.state != GateState.SATISFIED:
        return r047

    return GateOutput(
        state=GateState.SATISFIED,
        detail="All P5 test construction and red run governance invariants satisfied",
    )
