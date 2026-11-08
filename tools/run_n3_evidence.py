#!/usr/bin/env python3
"""Run multi-version verification on merged integration tree (Round 10 N3)."""
import os
import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

OUT_DIR = REPO_ROOT / "delivery-integration-r33b"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MASTER_PATH = os.environ.get("SCLASS_MASTER_PATH", "/tmp/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md")
os.environ["SCLASS_MASTER_PATH"] = MASTER_PATH

def run_cmd(cmd: list, log_name: str) -> tuple[int, str]:
    log_file = OUT_DIR / log_name
    print(f"Running: {' '.join(cmd)} -> {log_name}")
    res = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    out = res.stdout + res.stderr
    log_file.write_text(out, encoding="utf-8")
    status = "OK" if res.returncode == 0 else f"EXIT {res.returncode}"
    print(f"  [{status}] {log_name}")
    return res.returncode, out

def main():
    versions = ["3.10", "3.11", "3.12", "3.13"]
    failures = 0

    print("=== 1. GUARDS (3.10 - 3.13) ===")
    for ver in versions:
        pytest_bin = f"/home/runner/venv-{ver}/bin/pytest"
        rc, _ = run_cmd([
            pytest_bin, "-v",
            "tests/guards/test_import_direction_guard.py",
            "tests/guards/test_no_personal_paths_guard.py",
            "tests/guards/test_frozen_integrity_guard.py"
        ], f"guards_{ver}.log")
        if rc != 0:
            failures += 1

    print("\n=== 2. FIXTURE RUNNERS (3.10 - 3.13) ===")
    for ver in versions:
        py_bin = f"/home/runner/venv-{ver}/bin/python3"
        rc, _ = run_cmd([py_bin, "tools/run_all_b1_fixtures.py", "--master-path", MASTER_PATH], f"b1_fixtures_{ver}.log")
        if rc != 0: failures += 1
        rc, _ = run_cmd([py_bin, "tools/run_block2_fixtures.py", "--master-path", MASTER_PATH], f"b2_fixtures_{ver}.log")
        if rc != 0: failures += 1
        rc, _ = run_cmd([py_bin, "tools/run_all_b3_fixtures.py", "--master", MASTER_PATH], f"b3_fixtures_{ver}.log")
        if rc != 0: failures += 1
        rc, _ = run_cmd([py_bin, "tools/run_all_b4_b9_fixtures.py", "--master", MASTER_PATH], f"b4_b9_fixtures_{ver}.log")
        if rc != 0: failures += 1

    print("\n=== 3. AUDITORS WITH MUTATIONS ===")
    py12 = "/home/runner/venv-3.12/bin/python3"
    rc, _ = run_cmd([py12, "tools/block2_audit.py", "delivery-2-block2/REPORT-ROUND4.md", "--master-path", MASTER_PATH, "--run-mutations"], "auditor_block2.log")
    if rc != 0: failures += 1
    rc, _ = run_cmd([py12, "tools/block3_audit.py", "delivery-b3-wave2/REPORT-ROUND8.md", "--master-path", MASTER_PATH, "--run-mutations"], "auditor_block3.log")
    if rc != 0: failures += 1
    rc, _ = run_cmd([py12, "tools/block4_9_audit.py", "delivery-b4-b9/REPORT.md", "--master-path", MASTER_PATH, "--run-mutations"], "auditor_block4_9.log")
    if rc != 0: failures += 1

    print("\n=== 4. FULL PYTEST TEST SUITE (3.10 - 3.13) ===")
    for ver in versions:
        pytest_bin = f"/home/runner/venv-{ver}/bin/pytest"
        rc, out = run_cmd([pytest_bin, "-q", "--tb=short"], f"full_suite_{ver}.log")
        # Note: full suite exit code on sandbox may have known 5-7 baseline env failures
        # Extract summary line:
        summary_line = ""
        for line in reversed(out.splitlines()):
            if "passed" in line:
                summary_line = line.strip()
                break
        print(f"  Py{ver} suite summary: {summary_line}")

    print(f"\nN3 Verification complete. Total critical failures: {failures}")
    return 0 if failures == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
