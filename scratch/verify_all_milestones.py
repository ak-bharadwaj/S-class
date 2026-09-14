"""
S-Class Master Milestone Auditor (scratch/verify_all_milestones.py).
Executes and audits all 32 architectural, product, and reality milestones in sequence:

 1. Milestone 01: Phase 1 Trust Kernel (tests/certification/test_cert_trust.py)
 2. Milestone 02: Execution Security & Modes (tests/certification/test_cert_execution.py)
 3. Milestone 03: Session Handoff & Continuity (tests/certification/test_cert_handoff.py)
 4. Milestone 04: MCP Protocol & Transport (tests/certification/test_cert_mcp.py)
 5. Milestone 05: Milestone B.2 OPA Policy Provider (tests/certification/test_cert_b2_opa_provider.py)
 6. Milestone 06: Milestone B.3 Platform Optimization Core (tests/certification/test_cert_b3_platform_optimization.py)
 7. Milestone 07: Milestone B.4 Platform Profiling Framework (tests/certification/test_cert_b4_platform_profiling.py)
 8. Milestone 08: Milestone B.5 Official MCP Integration (tests/certification/test_cert_b5_mcp_official.py)
 9. Milestone 09: Milestone B.6 ACP Platform Standard (tests/certification/test_cert_acp.py)
10. Milestone 10: Milestone B.7 Verification Providers (tests/certification/test_cert_b7_verification_providers.py)
11. Milestone 11: Milestone B.8 Adaptive Verification Policies (tests/certification/test_cert_b8_adaptive_verification.py)
12. Milestone 12: Milestone B.9 Independent Observation & OTel (tests/certification/test_cert_b9_independent_observation.py)
13. Milestone 13: Milestone B.10 Empirical Outcome Learning (tests/certification/test_cert_b10_empirical_learning.py)
14. Milestone 14: Milestone B.11 Universal Truth Layer & State (tests/certification/test_cert_b11_verified_project_state.py)
15. Milestone 15: Milestone B.12 Cross-Platform Continuity (tests/certification/test_cert_b12_cross_platform_continuity.py)
16. Milestone 16: Milestone B.15 Multi-Agent Fleet Integrity (tests/certification/test_cert_b15_agent_fleet_integrity.py)
 17. Milestone 17: Milestone RC.1 External Codex & Benchmark (tests/certification/test_cert_rc1_codex_benchmark.py)
 18. Milestone 18: Milestone RC.2 Execution Provider Closure & Sandboxing (tests/certification/test_cert_rc2_execution_providers.py)
 19. Milestone 19: Milestone RC.3 Independent Observation Plane (tests/certification/test_cert_rc3_observation.py)
 20. Milestone 20: Milestone RC.4 Executable Verification Engine (tests/certification/test_cert_rc4_verification_engine.py)
 21. Milestone 21: Milestone RC.5 Universal Project Truth & Invalidation (tests/certification/test_cert_rc5_project_truth.py)
 22. Milestone 22: Milestone RC.6 Tree-sitter Code Intelligence & SCIP (tests/certification/test_cert_rc6_code_intelligence.py)
 23. Milestone 23: Milestone RC.7 ACP Proxy & MCP Protocol Gateway (tests/certification/test_cert_rc7_protocol_gateway.py)
 24. Milestone 24: Milestone RC.8 Handoff & Continuity Engine (tests/certification/test_cert_rc8_handoff_continuity.py)
 25. Milestone 25: Milestone RC.9 Fleet Task Graph & Production Engine (tests/certification/test_cert_rc9_fleet_production.py)
 26. Milestone 26: Milestone RC.10 Memory Provider Abstraction & Mem0 (tests/certification/test_cert_rc10_memory.py)
 27. Milestone 27: Milestone RC.11 Platform Profile Engine & Compensation Budget (tests/certification/test_cert_rc11_platform_engine.py)
 28. Milestone 28: Milestone RC.12 Silent Governance Mode & Universal Adapters (tests/certification/test_cert_rc12_silent_governance.py)
 29. Milestone 29: Milestone RC.13 CLI Completion & Explain/Audit UX (tests/certification/test_cert_rc13_cli_ux.py)
 30. Milestone 30: Milestone RC.14 OPA/Cedar Policy Product & Bundles (tests/certification/test_cert_rc14_policy_product.py)
 31. Milestone 31: Milestone RC.15 Supply-Chain Evidence & Provenance (tests/certification/test_cert_rc15_supply_chain.py)
 32. Milestone 32: Milestone RC.16 Packaging, Unified Config & Installer (tests/certification/test_cert_rc16_packaging.py)
"""

import sys
import os
import time
import subprocess
from typing import List, Dict, Any, Tuple


_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from sclass.metadata import MILESTONE_DEFINITIONS

MILESTONES: List[Tuple[str, str, str]] = [
    (m["code"], m["title"], m["path"]) for m in MILESTONE_DEFINITIONS
]



def run_milestone(idx: int, code: str, title: str, path: str) -> Dict[str, Any]:
    t0 = time.perf_counter()
    cmd = [sys.executable, "-m", "pytest", path, "-q"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    dt = time.perf_counter() - t0

    success = (proc.returncode == 0)
    output_lines = [l.strip() for l in proc.stdout.strip().splitlines() if l.strip()]
    summary = output_lines[-1] if output_lines else (proc.stderr.strip() or "No output")

    return {
        "index": idx,
        "code": code,
        "title": title,
        "path": path,
        "success": success,
        "exit_code": proc.returncode,
        "duration_s": dt,
        "summary": summary,
    }


def main():
    total_count = len(MILESTONES)
    print("\n" + "=" * 78)
    print(f"  S-CLASS: {total_count}/{total_count} MASTER MILESTONE AUDITOR & REALITY CERTIFICATION")
    print("=" * 78)

    results: List[Dict[str, Any]] = []
    total_start = time.perf_counter()

    for i, (code, title, path) in enumerate(MILESTONES, start=1):
        status_label = f"[{i:02d}/{total_count}] Auditing {title}..."
        print(f"\n{status_label:<60}", end="", flush=True)
        res = run_milestone(i, code, title, path)
        results.append(res)

        if res["success"]:
            print(f" [PASS] ({res['duration_s']:.2f}s)")
            print(f"       Summary: {res['summary']}")
        else:
            print(f" [FAIL] ({res['duration_s']:.2f}s)")
            print(f"       Error: {res['summary']}")

    total_duration = time.perf_counter() - total_start
    passed_count = sum(1 for r in results if r["success"])
    total_count = len(results)

    print("\n" + "=" * 78)
    print(f"  AUDIT SUMMARY: {passed_count}/{total_count} MILESTONES PASSED ({total_duration:.2f}s total)")
    print("=" * 78)

    for r in results:
        mark = "[PASS]" if r["success"] else "[FAIL]"
        print(f"  {mark} [{r['code']}] {r['title']:<48} ({r['duration_s']:.2f}s) - {r['summary']}")

    print("=" * 78)
    if passed_count == total_count:
        print(f"#  ALL {total_count}/{total_count} MILESTONES CERTIFIED 100% GREEN (ZERO DEFECTS)")
        print("=" * 78 + "\n")
        sys.exit(0)
    else:
        print(f"#  AUDIT FAILED: {total_count - passed_count} MILESTONES FAILED")
        print("=" * 78 + "\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
