#!/usr/bin/env python3
"""Execute full verification battery for BRIEF 1-BASE-b integration and capture logs."""

import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "delivery-1-base-b"
OUT_DIR.mkdir(exist_ok=True)
PYTHON = sys.executable

FROZEN_FILES = {
    "00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md": "53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1",
    "10-CONFORMANCE/sclass_semantics_v6_0_1.py": "ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922",
    "10-CONFORMANCE/sclass_kernel_v6_0_1.py": "d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c",
    "10-CONFORMANCE/c1-vectors.v6.0.1.json": "db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8",
    "10-CONFORMANCE/state-machines.v6.0.1.json": "24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad",
}


def run_cmd(args: list[str], log_file: Path) -> int:
    print(f"\n>>> Running: {' '.join(args)}")
    t0 = time.time()
    env = os.environ.copy()
    env["VIRTUAL_ENV"] = str(Path(PYTHON).parent.parent)
    res = subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True, env=env)
    elapsed = time.time() - t0
    header = f"$ {' '.join(args)}\n[EXIT CODE: {res.returncode}] [ELAPSED: {elapsed:.2f}s]\n\n"
    output = header + res.stdout + res.stderr
    log_file.write_text(output, encoding="utf-8")
    print(f"Finished with exit code {res.returncode} in {elapsed:.2f}s -> {log_file.name}")
    return res.returncode


def check_frozen_hashes(log_file: Path) -> int:
    print("\n>>> Verifying 5 frozen file hashes...")
    lines = ["=== FROZEN FILES SHA-256 BYTE INTEGRITY CHECK ==="]
    mismatches = 0
    for rel_path, expected in FROZEN_FILES.items():
        f_path = ROOT / rel_path
        if not f_path.exists():
            line = f"FAILED (MISSING): {rel_path}"
            mismatches += 1
        else:
            raw = f_path.read_bytes().replace(b"\r\n", b"\n")
            actual = hashlib.sha256(raw).hexdigest()
            if actual == expected:
                line = f"OK     {actual}  {rel_path}"
            else:
                line = f"FAILED {actual} != {expected}  {rel_path}"
                mismatches += 1
        print("  " + line)
        lines.append(line)
    lines.append(f"\nResult: {'PASS (0 mismatches)' if mismatches == 0 else f'FAIL ({mismatches} mismatches)'}")
    log_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if mismatches == 0 else 1


def main():
    results = {}

    # 1. pip install --require-hashes
    pip_bin = str(Path(PYTHON).parent / "pip")
    pip_cmd = [pip_bin, "install", "--require-hashes", "-r", "requirements-linux.txt", "--find-links", "/home/runner/pip-cache"]
    results["1_pip_install"] = run_cmd(pip_cmd, OUT_DIR / "1_pip_install.log")

    # 2. Guard tests
    guard_cmd = [PYTHON, "-m", "pytest", "tests/guards/", "-v"]
    results["2_guard_tests"] = run_cmd(guard_cmd, OUT_DIR / "2_guard_tests.log")

    # 3. Full suite
    suite_cmd = [PYTHON, "-m", "pytest", "-v", "--junitxml=verify_junit.xml"]
    results["3_full_suite"] = run_cmd(suite_cmd, OUT_DIR / "3_full_suite.log")

    # 4. Mutation checks (frozen files battery)
    mutation_cmd = [PYTHON, "delivery-1-00/run_mutations.py"]
    results["4_mutation_checks"] = run_cmd(mutation_cmd, OUT_DIR / "4_mutation_checks.log")

    # 5. M5 tests & delegated cgroup sandbox execution
    m5_cmd = [PYTHON, "-m", "pytest", "-v", "tests/security/test_boundary_hardening.py", "-k", "test_m5"]
    results["5_m5_sandbox"] = run_cmd(m5_cmd, OUT_DIR / "5_m5_sandbox_qualification.log")

    # 6. Frozen file hashes
    results["6_frozen_hashes"] = check_frozen_hashes(OUT_DIR / "6_frozen_hashes.log")

    print("\n" + "=" * 60)
    print("VERIFICATION BATTERY SUMMARY:")
    for k, v in results.items():
        status = "PASS (rc=0)" if v == 0 else f"FAIL (rc={v})"
        print(f"  {k:25s}: {status}")
    print("=" * 60)


if __name__ == "__main__":
    main()
