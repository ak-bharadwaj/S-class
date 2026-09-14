"""
Performance Benchmark Matrix Suite (Handoff C).
Measures latency across the 9 core operational dimensions:
1. Authorization evaluation (PolicyEngine / ActionRequest)
2. Process observation & identity capture (ExecutionIdentity)
3. Workspace cryptographic fingerprinting (compute_workspace_fingerprint)
4. Cryptographic ledger append & commit (LocalLedger)
5. Evidence verification & acceptance gate (verify_claim)
6. Daemon health check & IPC state emission (SClassDaemon)
7. ACP protocol round-trip (ACPAdapter)
8. MCP protocol round-trip (MCPGateway)
9. Handoff package assembly (HandoffAssembler)

Calculates p50, p95, and p99 latencies and asserts strict performance SLA budgets.
"""

import os
import sys
import time
from typing import List, Dict, Callable
import pytest

from sclass.control.authorization import authorize
from sclass.domain.action import ActionRequest
from sclass.execution.identity import ExecutionIdentity
from sclass.observation.fingerprint import compute_workspace_fingerprint, compute_workspace_snapshot
from sclass.trust.ledger import LocalLedger
from sclass.state.tasks import StateRepository
from sclass.domain.project import Project, ProjectBoundary
from sclass.domain.task import Task, TaskState, TaskPriority
from sclass.domain.claim import Claim
from sclass.observation.observer import observe_command
from sclass.verification.engine import verify_claim
from sclass.cli.daemon import SClassDaemon
from sclass.integrations.acp.adapter import ACPAdapter
from sclass.integrations.mcp.gateway import MCPGateway
from sclass.context.handoff import HandoffAssembler


def calculate_percentiles(latencies_ms: List[float]) -> Dict[str, float]:
    """Calculates p50, p95, and p99 from a list of latencies in milliseconds."""
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


def measure_operation(op: Callable[[], None], iterations: int = 25) -> Dict[str, float]:
    """Runs an operation N times and records latencies in milliseconds."""
    # Warm up 2 iterations
    for _ in range(2):
        op()
    latencies: List[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        op()
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)
    return calculate_percentiles(latencies)


def test_performance_benchmark_matrix(tmp_path):
    """
    Executes full 9-dimension latency benchmark matrix and asserts SLAs.
    """
    ws = str(tmp_path / "bench_ws")
    os.makedirs(ws, exist_ok=True)
    proj_id = os.path.basename(ws)
    repo = StateRepository(ws)
    repo.save_project(Project(project_id=proj_id, name="Benchmark Proj", boundary=ProjectBoundary(ws)))
    t = Task.create(title="Benchmark Task", project_id=proj_id)
    repo.save_task(t)
    ledger = LocalLedger(ws)

    # 1. Authorization
    req = ActionRequest(
        agent="bench_agent",
        platform="acp",
        action="read_file",
        tool="read_file",
        target="src/main.py",
        parameters={"path": "src/main.py"},
        workspace=ws,
    )
    auth_perf = measure_operation(lambda: authorize(req, mode="enforce", workspace_dir=ws))

    # 2. Observation & Identity Capture
    ident_perf = measure_operation(lambda: ExecutionIdentity.capture(
        command_argv=[sys.executable, "-c", "pass"],
        cwd=ws,
    ))

    # 3. Workspace Fingerprint
    fp_perf = measure_operation(lambda: compute_workspace_fingerprint(compute_workspace_snapshot(ws)))

    # 4. Ledger Write
    counter = [0]
    def append_ledger():
        counter[0] += 1
        ledger.append("benchmark_metric", {"tick": counter[0]})
    ledger_perf = measure_operation(append_ledger)

    # 5. Verification
    test_file = tmp_path / "bench_test.py"
    test_file.write_text("def test_p(): pass\n", encoding="utf-8")
    receipt = observe_command(f'"{sys.executable}" -m pytest "{test_file}" -q', workspace_dir=ws, ledger=ledger)
    claim = Claim(claim_id="bench_claim", task_id=t.task_id, statement="Tests pass", claim_type="test_pass")
    verif_perf = measure_operation(lambda: verify_claim(claim, receipt, workspace_dir=ws, ledger=ledger))

    # 6. Daemon IPC
    daemon = SClassDaemon(ws, poll_interval_sec=0.01)
    daemon_perf = measure_operation(lambda: daemon.run_once())

    # 7. ACP Round-trip
    acp = ACPAdapter(ws)
    acp_msg = {"jsonrpc": "2.0", "id": "1", "method": "initialize", "params": {"capabilities": {}}}
    acp_perf = measure_operation(lambda: acp.process_acp_message(acp_msg))


    # 8. MCP Round-trip
    mcp_gw = MCPGateway(ws)
    mcp_perf = measure_operation(lambda: mcp_gw.handle_call_tool("list_dir", {"path": "src"}))

    # 9. Handoff Assembly
    assembler = HandoffAssembler(ws)
    handoff_perf = measure_operation(lambda: assembler.assemble_package(proj_id, next_action="Deploy"))

    matrix = {
        "1. Authorization": (auth_perf, 75.0),        # SLA: p50 < 75ms (allows CI VM jitter)
        "2. Process Identity": (ident_perf, 50.0),    # SLA: p50 < 50ms
        "3. Workspace Fingerprint": (fp_perf, 75.0),  # SLA: p50 < 75ms
        "4. Ledger Append": (ledger_perf, 75.0),      # SLA: p50 < 75ms
        "5. Verification Engine": (verif_perf, 75.0), # SLA: p50 < 75ms (allows CI VM jitter)
        "6. Daemon IPC Tick": (daemon_perf, 75.0),    # SLA: p50 < 75ms
        "7. ACP Round-trip": (acp_perf, 50.0),        # SLA: p50 < 50ms
        "8. MCP Round-trip": (mcp_perf, 50.0),        # SLA: p50 < 50ms
        "9. Handoff Assembly": (handoff_perf, 75.0),  # SLA: p50 < 75ms
    }

    # Print benchmark report
    header = f"{'Operation':<26} | {'p50 (ms)':<9} | {'p95 (ms)':<9} | {'p99 (ms)':<9} | {'SLA (p50)':<9} | {'Status'}"
    print("\n" + "=" * len(header))
    print("S-CLASS PERFORMANCE BENCHMARK MATRIX (p50 / p95 / p99)")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for name, (perf, sla) in matrix.items():
        status = "PASSED" if perf["p50"] <= sla else "EXCEEDED"
        row = f"{name:<26} | {perf['p50']:<9.3f} | {perf['p95']:<9.3f} | {perf['p99']:<9.3f} | {sla:<9.1f} | [{status}]"
        print(row)
        assert perf["p50"] <= sla, f"{name} exceeded p50 SLA: {perf['p50']}ms > {sla}ms"

    print("=" * len(header) + "\n")
