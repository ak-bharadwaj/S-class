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
import tracemalloc
from datetime import datetime, timezone
from typing import List, Dict, Callable
import pytest

from sclass.execution.harness import NativeHarness, StepCodeHarness, StepCodeRpcHarness
from sclass.control.composite_auth import DualLayerAuthorizer
from sclass.verification.independent_registry import IndependentEvaluator, TestVerifier, FileSystemObserver
from sclass.trust.state_reducer import CanonicalStateReducer
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


def test_six_tier_stepcode_assurance_benchmarks():
    """
    Part O: Six-Tier Step-Code Assurance Performance Benchmark Suite.
    Measures across 6 execution tiers:
      Tier 1: Step-Code baseline (raw external RPC)
      Tier 2: Step-Code + S-Class authorization
      Tier 3: Step-Code + S-Class event bridge
      Tier 4: Step-Code + independent observation
      Tier 5: Step-Code + verification
      Tier 6: Step-Code + full assurance
    Tracks: p50, p95, p99, total runtime overhead, CPU time, memory, event volume, persistence overhead, verification latency.
    """
    workspace = tempfile.mkdtemp(prefix="sclass_bench_6tier_")
    harness = None
    try:
        test_file = os.path.join(workspace, "target.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("benchmarking real step-code rpc runtime\n")

        harness = StepCodeRpcHarness(workspace_dir=workspace, use_test_double=True)
        health = harness.health_check()
        assert health["status"] == "HEALTHY"

        action = ActionRequest(
            actor="bench_agent",
            capability="terminal.execute",
            action="read_file",
            target="target.txt",
            parameters={},
            workspace=workspace,
        )

        observer = FileSystemObserver()
        verifier = TestVerifier()
        reducer = CanonicalStateReducer()
        claim = Claim(
            claim_id="c_bench_6tier",
            task_id="t_bench_6tier",
            statement="read verified",
            claim_type=ClaimType.TEST_PASS,
        )
        ob = TechnicalObligation(
            obligation_id="ob_bench_6tier",
            task_id="t_bench_6tier",
            req_id="r_bench_6tier",
            title="Benchmark 6tier obligation",
            description="Obligation satisfied for benchmark",
            mandatory=True,
            status=ObligationStatus.SATISFIED,
        )
        canonical_records = [{
            "entry_id": "e_bench_6tier",
            "entry_type": "obligation",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": ob.to_dict(),
        }]

        # Warm up RPC
        for _ in range(2):
            harness._send_rpc("tool_call", {"action": "read_file", "target": "target.txt", "parameters": {}})

        tier_metrics = {}
        iterations = 10

        # --- Tier 1: Step-Code baseline ---
        tracemalloc.start()
        cpu_start = time.process_time()
        t1_latencies = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            r = harness._send_rpc("tool_call", {"action": "read_file", "target": "target.txt", "parameters": {}})
            t1 = time.perf_counter()
            t1_latencies.append((t1 - t0) * 1000.0)
            assert r.get("status") in ("ok", "SETTLED")
        cpu_t1 = (time.process_time() - cpu_start) * 1000.0
        _, mem_t1 = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        tier_metrics["Tier 1 (Baseline)"] = {
            "percentiles": calculate_percentiles(t1_latencies),
            "cpu_ms": round(cpu_t1, 3),
            "mem_kb": round(mem_t1 / 1024.0, 2),
            "events": 0,
            "persistence_bytes": 0,
            "verif_latency_ms": 0.0,
        }

        # --- Tier 2: Step-Code + S-Class authorization ---
        tracemalloc.start()
        cpu_start = time.process_time()
        t2_latencies = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            auth = DualLayerAuthorizer.authorize_request(action, workspace_dir=workspace)
            r = harness._send_rpc("tool_call", {"action": "read_file", "target": "target.txt", "parameters": {}})
            t1 = time.perf_counter()
            t2_latencies.append((t1 - t0) * 1000.0)
            assert auth.is_allowed and r.get("status") in ("ok", "SETTLED")
        cpu_t2 = (time.process_time() - cpu_start) * 1000.0
        _, mem_t2 = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        tier_metrics["Tier 2 (+ Auth)"] = {
            "percentiles": calculate_percentiles(t2_latencies),
            "cpu_ms": round(cpu_t2, 3),
            "mem_kb": round(mem_t2 / 1024.0, 2),
            "events": 0,
            "persistence_bytes": 0,
            "verif_latency_ms": 0.0,
        }

        # --- Tier 3: Step-Code + S-Class event bridge ---
        events_t3 = []
        sub_id_3 = harness.subscribe_events(lambda e: events_t3.append(e))
        tracemalloc.start()
        cpu_start = time.process_time()
        t3_latencies = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            auth = DualLayerAuthorizer.authorize_request(action, workspace_dir=workspace)
            res = harness.submit_action(action, auth)
            t1 = time.perf_counter()
            t3_latencies.append((t1 - t0) * 1000.0)
            assert res["status"] == "SETTLED"
        cpu_t3 = (time.process_time() - cpu_start) * 1000.0
        _, mem_t3 = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        harness.unsubscribe_events(sub_id_3)

        store_file = os.path.join(workspace, ".sclass", "trust", "cross_runtime_operations.jsonl")
        persist_bytes_t3 = os.path.getsize(store_file) if os.path.exists(store_file) else 0

        tier_metrics["Tier 3 (+ Event Bridge)"] = {
            "percentiles": calculate_percentiles(t3_latencies),
            "cpu_ms": round(cpu_t3, 3),
            "mem_kb": round(mem_t3 / 1024.0, 2),
            "events": len(events_t3),
            "persistence_bytes": persist_bytes_t3,
            "verif_latency_ms": 0.0,
        }

        # --- Tier 4: Step-Code + independent observation ---
        events_t4 = []
        sub_id_4 = harness.subscribe_events(lambda e: events_t4.append(e))
        tracemalloc.start()
        cpu_start = time.process_time()
        t4_latencies = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            auth = DualLayerAuthorizer.authorize_request(action, workspace_dir=workspace)
            res = harness.submit_action(action, auth)
            obs = observer.observe(target="target.txt", workspace_dir=workspace)
            t1 = time.perf_counter()
            t4_latencies.append((t1 - t0) * 1000.0)
            assert obs.payload.get("exists") is True
        cpu_t4 = (time.process_time() - cpu_start) * 1000.0
        _, mem_t4 = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        harness.unsubscribe_events(sub_id_4)

        tier_metrics["Tier 4 (+ Observation)"] = {
            "percentiles": calculate_percentiles(t4_latencies),
            "cpu_ms": round(cpu_t4, 3),
            "mem_kb": round(mem_t4 / 1024.0, 2),
            "events": len(events_t4),
            "persistence_bytes": os.path.getsize(store_file) if os.path.exists(store_file) else 0,
            "verif_latency_ms": 0.0,
        }

        # --- Tier 5: Step-Code + verification ---
        events_t5 = []
        sub_id_5 = harness.subscribe_events(lambda e: events_t5.append(e))
        tracemalloc.start()
        cpu_start = time.process_time()
        t5_latencies = []
        t5_verif_latencies = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            auth = DualLayerAuthorizer.authorize_request(action, workspace_dir=workspace)
            res = harness.submit_action(action, auth)
            obs = observer.observe(target="target.txt", workspace_dir=workspace)

            vt0 = time.perf_counter()
            v_res = verifier.verify(claim, {"payload": {"exit_code": 0, "passed": 1, "failed": 0}})
            vt1 = time.perf_counter()
            t5_verif_latencies.append((vt1 - vt0) * 1000.0)

            t1 = time.perf_counter()
            t5_latencies.append((t1 - t0) * 1000.0)
            assert v_res.is_verified is True
        cpu_t5 = (time.process_time() - cpu_start) * 1000.0
        _, mem_t5 = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        harness.unsubscribe_events(sub_id_5)

        tier_metrics["Tier 5 (+ Verification)"] = {
            "percentiles": calculate_percentiles(t5_latencies),
            "cpu_ms": round(cpu_t5, 3),
            "mem_kb": round(mem_t5 / 1024.0, 2),
            "events": len(events_t5),
            "persistence_bytes": os.path.getsize(store_file) if os.path.exists(store_file) else 0,
            "verif_latency_ms": calculate_percentiles(t5_verif_latencies)["p50"],
        }

        # --- Tier 6: Step-Code + full assurance ---
        events_t6 = []
        sub_id_6 = harness.subscribe_events(lambda e: events_t6.append(e))
        tracemalloc.start()
        cpu_start = time.process_time()
        t6_latencies = []
        t6_verif_latencies = []
        for _ in range(iterations):
            state = VerifiedProjectState(workspace=workspace)
            t0 = time.perf_counter()
            auth = DualLayerAuthorizer.authorize_request(action, workspace_dir=workspace)
            res = harness.submit_action(action, auth)
            obs = observer.observe(target="target.txt", workspace_dir=workspace)

            vt0 = time.perf_counter()
            v_res = verifier.verify(claim, {"payload": {"exit_code": 0, "passed": 1, "failed": 0}})
            state.record_verified_claim({"claim_id": claim.claim_id, "task_id": claim.task_id, "statement": claim.statement})
            v_state = reducer.reduce(canonical_records, initial_state=state, workspace_dir=workspace)
            adjudication = CompletionEvaluator.adjudicate(
                "t_bench_6tier",
                res,
                v_state,
                obligations=[ob],
                expected_workspace=workspace,
            )
            vt1 = time.perf_counter()
            t6_verif_latencies.append((vt1 - vt0) * 1000.0)

            t1 = time.perf_counter()
            t6_latencies.append((t1 - t0) * 1000.0)
            assert adjudication.verdict is not None
        cpu_t6 = (time.process_time() - cpu_start) * 1000.0
        _, mem_t6 = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        harness.unsubscribe_events(sub_id_6)

        tier_metrics["Tier 6 (+ Full Assurance)"] = {
            "percentiles": calculate_percentiles(t6_latencies),
            "cpu_ms": round(cpu_t6, 3),
            "mem_kb": round(mem_t6 / 1024.0, 2),
            "events": len(events_t6),
            "persistence_bytes": os.path.getsize(store_file) if os.path.exists(store_file) else 0,
            "verif_latency_ms": calculate_percentiles(t6_verif_latencies)["p50"],
        }

        # Print structured metrics report
        print("\n" + "=" * 95)
        print("PART O: SIX-TIER STEP-CODE ASSURANCE PERFORMANCE BENCHMARK REPORT")
        print("=" * 95)
        baseline_p50 = tier_metrics["Tier 1 (Baseline)"]["percentiles"]["p50"]
        print(f"{'Tier':<25} | {'p50(ms)':<8} | {'p95(ms)':<8} | {'p99(ms)':<8} | {'Overhead':<10} | {'CPU(ms)':<8} | {'Mem(KB)':<8} | {'Events':<6} | {'Persist(B)':<10}")
        print("-" * 95)
        for name, m in tier_metrics.items():
            p50 = m["percentiles"]["p50"]
            p95 = m["percentiles"]["p95"]
            p99 = m["percentiles"]["p99"]
            overhead = f"+{round(p50 - baseline_p50, 2)}ms" if p50 >= baseline_p50 else f"-{round(baseline_p50 - p50, 2)}ms"
            print(f"{name:<25} | {p50:<8} | {p95:<8} | {p99:<8} | {overhead:<10} | {m['cpu_ms']:<8} | {m['mem_kb']:<8} | {m['events']:<6} | {m['persistence_bytes']:<10}")
        print("=" * 95)

        # Sanity & SLA Assertions
        assert len(tier_metrics) == 6
        assert tier_metrics["Tier 1 (Baseline)"]["percentiles"]["p50"] > 0.0
        assert tier_metrics["Tier 6 (+ Full Assurance)"]["percentiles"]["p50"] > 0.0
        assert tier_metrics["Tier 3 (+ Event Bridge)"]["events"] > 0
        assert tier_metrics["Tier 3 (+ Event Bridge)"]["persistence_bytes"] > 0
    finally:
        if harness:
            harness.close()
        shutil.rmtree(workspace, ignore_errors=True)

