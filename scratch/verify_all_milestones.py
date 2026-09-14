"""
S-Class Master Milestone Auditor (scratch/verify_all_milestones.py).
Executes and audits all 18 architectural, product, and reality milestones in sequence:
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
"""

import sys
import os
import time
import subprocess
from typing import List, Dict, Any, Tuple


MILESTONES: List[Tuple[str, str, str]] = [
    ("M01_TRUST_KERNEL", "Phase 1 Trust Kernel", "tests/certification/test_cert_trust.py"),
    ("M02_EXECUTION_SECURITY", "Execution Security & Modes", "tests/certification/test_cert_execution.py"),
    ("M03_SESSION_HANDOFF", "Session Handoff & Continuity", "tests/certification/test_cert_handoff.py"),
    ("M04_MCP_TRANSPORT", "MCP Protocol & Transport", "tests/certification/test_cert_mcp.py"),
    ("M05_OPA_PROVIDER", "B.2 OPA Policy Provider", "tests/certification/test_cert_b2_opa_provider.py"),
    ("M06_PLATFORM_OPTIMIZATION", "B.3 Platform Optimization Core", "tests/certification/test_cert_b3_platform_optimization.py"),
    ("M07_PLATFORM_PROFILING", "B.4 Platform Profiling Framework", "tests/certification/test_cert_b4_platform_profiling.py"),
    ("M08_MCP_OFFICIAL", "B.5 Official MCP Integration", "tests/certification/test_cert_b5_mcp_official.py"),
    ("M09_ACP_PROTOCOL", "B.6 ACP Platform Integration", "tests/certification/test_cert_acp.py"),
    ("M10_VERIFICATION_PROVIDERS", "B.7 Verification Providers", "tests/certification/test_cert_b7_verification_providers.py"),
    ("M11_ADAPTIVE_VERIFICATION", "B.8 Adaptive Verification Policies", "tests/certification/test_cert_b8_adaptive_verification.py"),
    ("M12_INDEPENDENT_OBSERVATION", "B.9 Independent Observation & OTel", "tests/certification/test_cert_b9_independent_observation.py"),
    ("M13_EMPIRICAL_LEARNING", "B.10 Empirical Outcome Learning", "tests/certification/test_cert_b10_empirical_learning.py"),
    ("M14_UNIVERSAL_TRUTH", "B.11 Universal Truth Layer & Project State", "tests/certification/test_cert_b11_verified_project_state.py"),
    ("M15_CROSS_PLATFORM_CONTINUITY", "B.12 Cross-Platform Continuity", "tests/certification/test_cert_b12_cross_platform_continuity.py"),
    ("M16_FLEET_INTEGRITY", "B.15 Multi-Agent Fleet Integrity", "tests/certification/test_cert_b15_agent_fleet_integrity.py"),
    ("M17_CODEX_BENCHMARK", "RC.1 External Codex Subprocess & Benchmark", "tests/certification/test_cert_rc1_codex_benchmark.py"),
    ("M18_EXECUTION_PROVIDERS", "RC.2 Execution Provider Closure & Sandboxing", "tests/certification/test_cert_rc2_execution_providers.py"),
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
    print("\n" + "=" * 78)
    print("  S-CLASS: 18/18 MASTER MILESTONE AUDITOR & REALITY CERTIFICATION")
    print("=" * 78)

    results: List[Dict[str, Any]] = []
    total_start = time.perf_counter()

    for i, (code, title, path) in enumerate(MILESTONES, start=1):
        status_label = f"[{i:02d}/18] Auditing {title}..."
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
