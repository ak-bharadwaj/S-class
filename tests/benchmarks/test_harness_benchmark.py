"""
S-Class Super Refactor Performance Benchmark Suite (Section 29).
Measures overhead and latency across the absorbed Step-Code harness and assurance plane:
1. Native harness submit_action latency
2. Step-Code harness submit_action latency
3. Dual-layer authorization evaluation overhead (S-Class policy + StepCodeCommandAnalyzer)
4. Independent verification registry evaluation overhead
5. CompletionEvaluator adjudication latency
6. Assurance handoff assembly latency
"""

import os
import time
import tempfile
import shutil
from typing import List, Dict, Callable
import pytest

from sclass.execution.harness import NativeHarness, StepCodeHarness
from sclass.control.composite_auth import DualLayerAuthorizer
from sclass.verification.independent_registry import IndependentEvaluator, TestVerifier
from sclass.core.completion_evaluator import CompletionEvaluator, CompletionVerdict
from sclass.context.assurance_handoff import assemble_assurance_handoff
from sclass.domain.project import VerifiedProjectState
from sclass.domain.claim import Claim, ClaimType
from sclass.domain.obligations import TechnicalObligation, ObligationStatus
from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.execution.operations import compute_action_hash


def calculate_percentiles(latencies_ms: List[float]) -> Dict[str, float]:
    s = sorted(latencies_ms)
    n = len(s)
    if n == 0:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
    p50_idx = min(int(n * 0.50), n - 1)
    p95_idx = min(int(n * 0.95), n - 1)
    p99_idx = min(int(n * 0.99), n - 1)
    return {
        "p50": round(s[p50_idx], 3),
        "p95": round(s[p95_idx], 3),
        "p99": round(s[p99_idx], 3),
    }


def measure_op(op: Callable[[], None], iterations: int = 20) -> Dict[str, float]:
    for _ in range(2):
        op()
    latencies: List[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        op()
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)
    return calculate_percentiles(latencies)


def test_harness_and_assurance_benchmarks():
    workspace = tempfile.mkdtemp(prefix="sclass_bench_")
    try:
        native_harness = NativeHarness(workspace_dir=workspace)
        stepcode_harness = StepCodeHarness(workspace_dir=workspace)
        evaluator = IndependentEvaluator()

        action = ActionRequest(
            actor="subagent_1",
            capability="terminal.execute",
            action="run_command",
            target="git status",
            parameters={"command": "git status"},
            workspace=workspace,
        )
        act_hash = compute_action_hash(action.capability, action.action, action.target, action.parameters)
        auth = AuthorizationDecision(
            outcome=DecisionOutcome.ALLOW,
            decision_id="dec_bench",
            request_id="req_bench",
            reason="Authorized for benchmark",
        )

        # 1. Native harness submit_action latency
        res_native = measure_op(lambda: native_harness.submit_action(action, auth), iterations=15)

        # 2. StepCode harness submit_action latency
        res_stepcode = measure_op(lambda: stepcode_harness.submit_action(action, auth), iterations=15)

        # 3. DualLayerAuthorizer overhead
        res_auth = measure_op(lambda: DualLayerAuthorizer.authorize_request(action), iterations=30)

        # 4. Independent verifier registry latency
        test_verifier = TestVerifier()
        claim = Claim(claim_id="cl_bench", task_id="t_bench", statement="test passes", claim_type=ClaimType.TEST_PASS)
        evidence = {"payload": {"exit_code": 0, "passed": 10, "failed": 0}}
        res_verif = measure_op(lambda: test_verifier.verify(claim, evidence), iterations=50)

        # 5. CompletionEvaluator adjudication latency
        state = VerifiedProjectState(workspace=workspace)
        state.record_verified_claim({"claim_id": "c_bench", "task_id": "t_bench", "statement": "bench verified"})
        ob = TechnicalObligation(
            obligation_id="ob_bench",
            task_id="t_bench",
            req_id="r_b",
            title="Benchmark obligation",
            description="Testing adjudication latency",
            mandatory=True,
            status=ObligationStatus.SATISFIED,
        )
        res_adjudicate = measure_op(
            lambda: CompletionEvaluator.adjudicate("t_bench", {"status": "complete"}, state, obligations=[ob]),
            iterations=50,
        )

        # 6. Assurance handoff assembly latency
        res_handoff = measure_op(
            lambda: assemble_assurance_handoff(
                task_id="t_bench",
                state=state,
                obligations=[ob],
            ),
            iterations=50,
        )

        # Performance SLA assertions (sub-50ms p50 for control/assurance operations)
        assert res_native["p50"] < 50.0, f"Native submit p50 too high: {res_native['p50']}ms"
        assert res_stepcode["p50"] < 50.0, f"StepCode submit p50 too high: {res_stepcode['p50']}ms"
        assert res_auth["p50"] < 50.0, f"Authorization p50 too high: {res_auth['p50']}ms"
        assert res_verif["p50"] < 50.0, f"Verifier dispatch p50 too high: {res_verif['p50']}ms"
        assert res_adjudicate["p50"] < 50.0, f"Completion evaluation p50 too high: {res_adjudicate['p50']}ms"
        assert res_handoff["p50"] < 50.0, f"Handoff assembly p50 too high: {res_handoff['p50']}ms"

        # Print benchmark metrics for transparency
        print(f"\n[BENCHMARK] Native submit_action: {res_native}")
        print(f"[BENCHMARK] StepCode submit_action: {res_stepcode}")
        print(f"[BENCHMARK] DualLayerAuthorizer: {res_auth}")
        print(f"[BENCHMARK] IndependentEvaluator: {res_verif}")
        print(f"[BENCHMARK] CompletionEvaluator: {res_adjudicate}")
        print(f"[BENCHMARK] AssuranceHandoff: {res_handoff}")
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
