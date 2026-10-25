#!/usr/bin/env python3
"""Run complete mutation battery for frozen files and kernel registry guards.
Captures full command outputs, exit codes, and verification.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable

FROZEN_FILES = [
    "00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md",
    "10-CONFORMANCE/sclass_semantics_v6_0_1.py",
    "10-CONFORMANCE/sclass_kernel_v6_0_1.py",
    "10-CONFORMANCE/c1-vectors.v6.0.1.json",
    "10-CONFORMANCE/state-machines.v6.0.1.json",
]


def run_cmd(cmd: list[str]) -> tuple[int, str]:
    res = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    out = res.stdout + res.stderr
    return res.returncode, out


def main():
    log_lines = []
    def log(msg: str):
        print(msg)
        log_lines.append(msg)

    log("=" * 80)
    log("BLOCK 1-00b MUTATION BATTERY VERIFICATION")
    log(f"Working directory: {ROOT}")
    log(f"Python interpreter: {PYTHON}")
    log("=" * 80)

    # 1. Clean Baseline
    log("\n--- [STAGE 0] Clean Baseline Guards Run ---")
    rc, out = run_cmd([PYTHON, "-m", "pytest", "tests/guards/", "-v"])
    log(f"Exit code: {rc} (Expected: 0)")
    log(out.strip())
    assert rc == 0, f"Clean baseline failed: {out}"

    # 2. Mutate each frozen file for SHA-256 integrity guard
    for idx, rel_path in enumerate(FROZEN_FILES, start=1):
        target = ROOT / rel_path
        backup = target.with_suffix(target.suffix + ".orig")
        log(f"\n--- [STAGE {idx}] Mutate Frozen File: {rel_path} ---")
        
        # Backup
        shutil.copy2(target, backup)
        try:
            # Mutate by appending a mutation comment/byte
            with open(target, "ab") as f:
                f.write(b"\n# MUTATION_INJECTION_TEST_GUARD\n")

            rc, out = run_cmd([PYTHON, "-m", "pytest", "tests/guards/test_frozen_integrity_guard.py", "-k", Path(rel_path).name, "-v"])
            log(f"Exit code: {rc} (Expected: 1)")
            log(out.strip())
            assert rc != 0, f"Integrity guard failed to detect mutation in {rel_path}!"
            assert "INTEGRITY VIOLATION" in out or "FAILED" in out, "Expected failure message missing"
        finally:
            if backup.exists():
                backup.unlink()
            run_cmd(["git", "checkout", "--", rel_path])
            log(f"Restored: {rel_path}")

        # Quick check that restored file passes
        rc, out = run_cmd([PYTHON, "-m", "pytest", "tests/guards/test_frozen_integrity_guard.py", "-k", Path(rel_path).name, "-q"])
        assert rc == 0, f"Restoration failed for {rel_path}: {out}"
        log(f"Restoration verified clean (rc=0)")

    # 3. Mutate state machine structure
    sm_path = ROOT / "10-CONFORMANCE" / "state-machines.v6.0.1.json"
    log("\n--- [STAGE 6] Mutate State Machines JSON Structure (Add Machine) ---")
    try:
        import json
        sm_data = json.loads(sm_path.read_text(encoding="utf-8"))
        sm_data["machines"]["MutatedMachine"] = {"STATE_A": ["STATE_B"]}
        sm_path.write_text(json.dumps(sm_data, indent=2), encoding="utf-8")

        rc, out = run_cmd([PYTHON, "-m", "pytest", "tests/guards/test_kernel_registry_guard.py::test_state_machines_json_structure_and_counts", "-v"])
        log(f"Exit code: {rc} (Expected: 1)")
        log(out.strip())
        assert rc != 0, "Kernel registry guard failed to detect mutated state machines"
        assert "State machine set drifted" in out
    finally:
        run_cmd(["git", "checkout", "--", "10-CONFORMANCE/state-machines.v6.0.1.json"])
        log("Restored: 10-CONFORMANCE/state-machines.v6.0.1.json")

    # 4. Mutate EventType Enum in semantics
    sem_path = ROOT / "10-CONFORMANCE" / "sclass_semantics_v6_0_1.py"
    log("\n--- [STAGE 7] Mutate EventType Enum in Semantics (Inject Enum Member) ---")
    try:
        content = sem_path.read_text(encoding="utf-8")
        needle = "class EventType(Enum):"
        assert needle in content
        mutated_content = content.replace(needle, needle + "\n    MUTATION_INJECTED_EVENT = 99999")
        sem_path.write_text(mutated_content, encoding="utf-8")

        rc, out = run_cmd([PYTHON, "-m", "pytest", "tests/guards/test_kernel_registry_guard.py::test_event_type_enum_in_semantics", "-v"])
        log(f"Exit code: {rc} (Expected: 1)")
        log(out.strip())
        assert rc != 0, "Kernel registry guard failed to detect mutated EventType"
        assert "EventType count in semantics is 57, expected 56" in out
    finally:
        run_cmd(["git", "checkout", "--", "10-CONFORMANCE/sclass_semantics_v6_0_1.py"])
        log("Restored: 10-CONFORMANCE/sclass_semantics_v6_0_1.py")

    # 5. Final Full Guard Run
    log("\n--- [STAGE 8] Final Clean Guards Run Across All Guards ---")
    rc, out = run_cmd([PYTHON, "-m", "pytest", "tests/guards/", "-v"])
    log(f"Exit code: {rc} (Expected: 0)")
    log(out.strip())
    assert rc == 0, f"Final clean guard run failed: {out}"

    # Verify git diff on frozen files is empty
    rc, diff_out = run_cmd(["git", "diff", "--ignore-space-at-eol", "--exit-code", "--", "00-SPEC", "10-CONFORMANCE"])
    log(f"\nGit diff on 00-SPEC and 10-CONFORMANCE exit code: {rc}")
    assert rc == 0, f"Git diff detected changes in frozen files: {diff_out}"
    log("All 5 frozen files verified completely untouched and clean.")
    log("\nALL 8 MUTATION STAGES PASSED VERIFICATION.")

    out_file = ROOT / "delivery-1-00" / "mutation_check.log"
    out_file.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    log(f"Wrote full mutation log to {out_file}")


if __name__ == "__main__":
    main()
