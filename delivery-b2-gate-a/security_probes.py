"""Standalone Security Probes for Lane B2-GATE-A (F5 Gate Evaluator).

Verifies pure deterministic gate evaluation, caller-injected authority,
fail-closed error handling, precedence rules, and kernel composition.
"""

from __future__ import annotations

import sys
from typing import List, Tuple

from sclass.product.gate import GateOutput, GateState
from sclass.product.gate_evaluator import evaluate_f5_gate


def run_probes() -> int:
    print("=" * 80)
    print("S-CLASS SECURITY PROBES: LANE B2-GATE-A (F5 GATE EVALUATOR)")
    print("=" * 80)

    probes: List[Tuple[str, bool, str]] = []

    # Probe 1: Absent evaluation_instant returns MISSING[PD-F5-001]
    res1 = evaluate_f5_gate(
        phase="P2",
        canonical_state_binding="SB-1",
        pinned_guidance="G-1",
        policy_version="P-7",
        evaluator_version="EV-3",
        evaluation_instant=None,
    )
    p1_pass = res1.state == GateState.MISSING and res1.gate_output.must_id == "PD-F5-001"
    probes.append(("[F5 PROBE 1] Absent evaluation_instant", p1_pass, str(res1.gate_output)))

    # Probe 2: MISSING over BLOCKED precedence returns MISSING[PD-F5-002]
    res2 = evaluate_f5_gate(
        phase="P2",
        canonical_state_binding="SB-2",
        pinned_guidance="G-2",
        policy_version="P-7",
        evaluator_version="EV-3",
        evaluation_instant="2026-01-01T00:00:00Z",
        checks=[
            {"check_id": "C-09", "status": "BLOCKED_ON_HUMAN", "inputs_digest": "D9"},
            {"check_id": "C-01", "status": "MISSING", "must_id": "PD-F5-002", "inputs_digest": "D1"},
        ],
    )
    p2_pass = (
        res2.state == GateState.MISSING
        and res2.gate_output.must_id == "PD-F5-002"
        and res2.explain.get("blocked") == ["C-09"]
    )
    probes.append(("[F5 PROBE 2] Precedence: MISSING over BLOCKED", p2_pass, str(res2.gate_output)))

    # Probe 3: Evaluator version mismatch returns MISSING[PD-F5-003]
    res3 = evaluate_f5_gate(
        phase="P3",
        canonical_state_binding="SB-3",
        pinned_guidance="G-3",
        policy_version="P-7",
        evaluator_version="v6",
        pinned_evaluator_version="v7",
        evaluation_instant="2026-01-01T00:00:00Z",
    )
    p3_pass = res3.state == GateState.MISSING and res3.gate_output.must_id == "PD-F5-003"
    probes.append(("[F5 PROBE 3] Version mismatch", p3_pass, str(res3.gate_output)))

    # Probe 4: Timeout returns MISSING[PD-F5-003]
    res4 = evaluate_f5_gate(
        phase="P3",
        canonical_state_binding="SB-3",
        pinned_guidance="G-3",
        policy_version="P-7",
        evaluator_version="v7",
        pinned_evaluator_version="v7",
        evaluation_instant="2026-01-01T00:00:00Z",
        timeout_ms=100,
        elapsed_ms=101,
    )
    p4_pass = res4.state == GateState.MISSING and res4.gate_output.must_id == "PD-F5-003"
    probes.append(("[F5 PROBE 4] Evaluator timeout", p4_pass, str(res4.gate_output)))

    # Probe 5: Budget exhaustion returns MISSING[PD-F5-003]
    res5 = evaluate_f5_gate(
        phase="P2",
        canonical_state_binding="SB",
        pinned_guidance="G",
        policy_version="P",
        evaluator_version="EV",
        evaluation_instant="2026-01-01T00:00:00Z",
        budget_exhausted=True,
    )
    p5_pass = res5.state == GateState.MISSING and res5.gate_output.must_id == "PD-F5-003"
    probes.append(("[F5 PROBE 5] Budget exhaustion", p5_pass, str(res5.gate_output)))

    # Probe 6: Malformed check input returns MISSING[PD-F5-003]
    res6 = evaluate_f5_gate(
        phase="P2",
        canonical_state_binding="SB",
        pinned_guidance="G",
        policy_version="P",
        evaluator_version="EV",
        evaluation_instant="2026-01-01T00:00:00Z",
        checks=["not_a_valid_dict"],  # type: ignore
    )
    p6_pass = res6.state == GateState.MISSING and res6.gate_output.must_id == "PD-F5-003"
    probes.append(("[F5 PROBE 6] Malformed check input", p6_pass, str(res6.gate_output)))

    # Probe 7: Kernel ExecutionGate=DENIED wins (Conflict F-1 check)
    res7 = evaluate_f5_gate(
        phase="P5",
        canonical_state_binding="SB-5",
        pinned_guidance="G-5",
        policy_version="P-7",
        evaluator_version="EV-3",
        evaluation_instant="2026-01-01T00:00:00Z",
        kernel_execution_gate="DENIED",
    )
    p7_pass = (
        res7.combined_result == "DENIED"
        and res7.state == GateState.MISSING
        and res7.gate_output.must_id == "PD-F5-005"
    )
    probes.append(("[F5 PROBE 7] Kernel DENIED composition (Conflict F-1)", p7_pass, f"combined={res7.combined_result}, gate={res7.gate_output}"))

    # Probe 8: Skill-added check cannot clear BLOCKED_ON_HUMAN
    res8 = evaluate_f5_gate(
        phase="P6",
        canonical_state_binding="SB-6",
        pinned_guidance="G-6",
        policy_version="P-7",
        evaluator_version="EV-3",
        evaluation_instant="2026-01-01T00:00:00Z",
        checks=[{"check_id": "H1", "status": "BLOCKED_ON_HUMAN", "must_id": "PD-F5-005"}],
        skill_added_checks=[{"check_id": "S1", "status": "SATISFIED", "must_id": "PD-F5-005"}],
        kernel_execution_gate="ALLOWED",
    )
    p8_pass = res8.state == GateState.BLOCKED_ON_HUMAN and res8.combined_result == "BLOCKED_ON_HUMAN[PD-F5-005]"
    probes.append(("[F5 PROBE 8] Skill cannot clear blocks", p8_pass, str(res8.gate_output)))

    # Probe 9: No-injected-authority negative test
    res9 = evaluate_f5_gate(
        phase="P0",
        canonical_state_binding=None,
        pinned_guidance=None,
        policy_version="P-0",
        evaluator_version="EV-0",
        evaluation_instant=None,
    )
    p9_pass = res9.state == GateState.MISSING
    probes.append(("[F5 PROBE 9] No-injected-authority negative test", p9_pass, str(res9.gate_output)))

    # Probe 10: Positive control (Valid tuple returns SATISFIED)
    res10 = evaluate_f5_gate(
        phase="P2",
        canonical_state_binding="SB-1",
        pinned_guidance="G-1",
        policy_version="P-7",
        evaluator_version="EV-3",
        evaluation_instant="2026-01-01T00:00:00Z",
        relevant_input_digests=["R-1", "AC-1"],
    )
    p10_pass = res10.state == GateState.SATISFIED and bool(res10.cache_key)
    probes.append(("[F5 POSITIVE CONTROL] Valid tuple returns SATISFIED", p10_pass, str(res10.gate_output)))

    all_pass = True
    for name, ok, detail in probes:
        status_str = "PASS" if ok else "FAIL"
        print(f"{name:<55}: {status_str} -> {detail}")
        if not ok:
            all_pass = False

    print("=" * 80)
    print(f"SECURITY PROBES RESULT: {'ALL PASS (10/10)' if all_pass else 'FAIL'}")
    print("=" * 80)
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(run_probes())
