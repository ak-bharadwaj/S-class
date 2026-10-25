#!/usr/bin/env python3
"""CL Independent Acceptance Audit Script for S-Class v6.0.1 Candidate f17d3acb580f5ef57f08f46aa7c77d5913833dd6."""

import os
import sys
import shutil
import subprocess
import time
import hashlib
from pathlib import Path

TARGET_SHA = "f17d3acb580f5ef57f08f46aa7c77d5913833dd6"
REPO = Path(__file__).resolve().parents[1]
AUDIT_DIR = Path("/home/runner/cl-audit-output")
AUDIT_DIR.mkdir(exist_ok=True)
REPO_AUDIT_DIR = REPO / "delivery-1-base-b" / "cl_independent_audit"
REPO_AUDIT_DIR.mkdir(parents=True, exist_ok=True)
VENV_DIR = Path("/home/runner/cl-acceptance-venv")
PYTHON = str(VENV_DIR / "bin" / "python")
PIP = str(VENV_DIR / "bin" / "pip")

FROZEN_FILES = {
    "00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md": "53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1",
    "10-CONFORMANCE/sclass_semantics_v6_0_1.py": "ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922",
    "10-CONFORMANCE/sclass_kernel_v6_0_1.py": "d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c",
    "10-CONFORMANCE/c1-vectors.v6.0.1.json": "db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8",
    "10-CONFORMANCE/state-machines.v6.0.1.json": "24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad",
}

def run_cmd(cmd, log_name):
    cmd_str = " ".join(cmd)
    print(f"\n>>> [CL AUDIT] {cmd_str}")
    t0 = time.time()
    env = os.environ.copy()
    env["VIRTUAL_ENV"] = str(VENV_DIR)
    env["PATH"] = f"{VENV_DIR}/bin:" + env.get("PATH", "")
    res = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, env=env)
    dur = time.time() - t0
    timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    header = (
        f"=== CL INDEPENDENT ACCEPTANCE AUDIT RECORD ===\n"
        f"TARGET_COMMIT: {TARGET_SHA}\n"
        f"TIMESTAMP: {timestamp}\n"
        f"COMMAND: {cmd_str}\n"
        f"EXIT_CODE: {res.returncode}\n"
        f"ELAPSED: {dur:.2f}s\n"
        f"==============================================\n\n"
    )
    output = header + res.stdout + res.stderr
    (AUDIT_DIR / log_name).write_text(output, encoding="utf-8")
    (REPO_AUDIT_DIR / log_name).write_text(output, encoding="utf-8")
    print(f"Finished with rc={res.returncode} in {dur:.2f}s -> {log_name}")
    return res.returncode

def main():
    print("=" * 70)
    print(f"CL INDEPENDENT AUDIT EXECUTION FOR CANDIDATE {TARGET_SHA}")
    print("=" * 70)

    # 1. Environment & Commit verification
    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO), capture_output=True, text=True).stdout.strip()
    print(f"Target Git HEAD SHA: {rev}")
    assert rev == TARGET_SHA, f"Unexpected HEAD: {rev} (expected {TARGET_SHA})"

    # 2. Setup clean acceptance venv
    print("Setting up fresh acceptance venv at /home/runner/cl-acceptance-venv...")
    subprocess.run(["rm", "-rf", str(VENV_DIR)], check=True)
    subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)

    # 3. Pip install locked dependencies with --require-hashes
    rc_install = run_cmd([PIP, "install", "--require-hashes", "-r", "requirements-linux.txt", "--find-links", "/home/runner/pip-cache"], "1_locked_pip_install.log")
    assert rc_install == 0, f"Locked install failed with exit code {rc_install}"

    # 4. Pip install sclass editable
    rc_editable = run_cmd([PIP, "install", "--no-deps", "-e", "."], "2_editable_install.log")
    assert rc_editable == 0, f"Editable install failed with exit code {rc_editable}"

    # 5. Capture pip freeze
    rc_freeze = run_cmd([PIP, "freeze"], "3_pip_freeze.log")
    assert rc_freeze == 0, f"Pip freeze failed with exit code {rc_freeze}"

    # Verify editable install line in pip freeze matches candidate SHA exactly
    freeze_txt = (AUDIT_DIR / "3_pip_freeze.log").read_text()
    expected_line = f"-e git+https://github.com/ak-bharadwaj/S-class.git@{TARGET_SHA}#egg=sclass"
    assert expected_line in freeze_txt, f"Expected '{expected_line}' in pip freeze"
    print(f"Verified: pip freeze recorded exact candidate commit {TARGET_SHA}")

    # 6. Run Guard tests
    rc_guards = run_cmd([PYTHON, "-m", "pytest", "tests/guards/", "-v"], "4_guard_tests.log")
    assert rc_guards == 0, f"Guard tests failed with exit code {rc_guards}"

    # 7. Run Full suite
    rc_full = run_cmd([PYTHON, "-m", "pytest", "-v", f"--junitxml={AUDIT_DIR}/cl_junit.xml"], "5_full_suite.log")
    assert rc_full == 0, f"Full suite failed with exit code {rc_full}"
    shutil.copy(AUDIT_DIR / "cl_junit.xml", REPO_AUDIT_DIR / "cl_junit.xml")

    # 8. Run Mutation checks
    rc_mut = run_cmd([PYTHON, "delivery-1-00/run_mutations.py"], "6_mutation_checks.log")
    assert rc_mut == 0, f"Mutation checks failed with exit code {rc_mut}"

    # 9. Run M5 Sandbox Qualification tests
    rc_m5 = run_cmd([PYTHON, "-m", "pytest", "-v", "tests/security/test_boundary_hardening.py", "-k", "test_m5"], "7_m5_sandbox.log")
    assert rc_m5 == 0, f"M5 tests failed with exit code {rc_m5}"

    # 10. Spec integrity check
    rc_spec = run_cmd([PYTHON, "10-CONFORMANCE/spec_integrity.py"], "8_spec_integrity.log")
    assert rc_spec == 0, f"Spec integrity check failed with exit code {rc_spec}"

    # 11. Frozen hashes
    print("\nChecking frozen hashes...")
    timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    lines = [
        "=== CL AUDIT: FROZEN FILES SHA-256 BYTE INTEGRITY CHECK ===",
        f"TARGET_COMMIT: {TARGET_SHA}",
        f"TIMESTAMP: {timestamp}",
        ""
    ]
    mismatches = 0
    for rel, exp in FROZEN_FILES.items():
        raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
        act = hashlib.sha256(raw).hexdigest()
        if act == exp:
            line = f"OK     {act}  {rel}"
        else:
            line = f"FAILED {act} != {exp}  {rel}"
            mismatches += 1
        print("  " + line)
        lines.append(line)
    lines.append(f"\nResult: {'PASS (0 mismatches)' if mismatches == 0 else f'FAIL ({mismatches} mismatches)'}")
    (AUDIT_DIR / "9_frozen_hashes.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (REPO_AUDIT_DIR / "9_frozen_hashes.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert mismatches == 0, f"Frozen hashes mismatch: {mismatches} failures"

    print("\n" + "=" * 70)
    print("ALL CL INDEPENDENT ACCEPTANCE AUDIT STAGES PASSED SUCCESSFULLY!")
    print(f"VERIFIED CANDIDATE COMMIT: {TARGET_SHA}")
    print("=" * 70)

if __name__ == "__main__":
    main()
