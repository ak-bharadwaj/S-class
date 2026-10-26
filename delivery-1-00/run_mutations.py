#!/usr/bin/env python3
"""Run complete mutation battery for frozen files and kernel registry guards.
Captures full command outputs, exit codes, and verification.
Guarantees byte-level isolation and restoration without invoking git checkout.
"""
from __future__ import annotations

import hashlib
import json
import os
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

EXPECTED_FROZEN_HASHES = {
    "00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md": "53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1",
    "10-CONFORMANCE/sclass_semantics_v6_0_1.py": "ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922",
    "10-CONFORMANCE/sclass_kernel_v6_0_1.py": "d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c",
    "10-CONFORMANCE/c1-vectors.v6.0.1.json": "db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8",
    "10-CONFORMANCE/state-machines.v6.0.1.json": "24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad",
}


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
    log("Restoration mechanism: Exact pre-mutation byte preservation & finally-block restore")
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
        orig_bytes = target.read_bytes()
        orig_raw_sha256 = hashlib.sha256(orig_bytes).hexdigest()
        orig_lf_sha256 = hashlib.sha256(orig_bytes.replace(b"\r\n", b"\n")).hexdigest()

        log(f"\n--- [STAGE {idx}] Mutate Frozen File: {rel_path} ---")
        log(f"Pre-mutation bytes saved: {len(orig_bytes)} bytes, raw_sha256={orig_raw_sha256}, lf_sha256={orig_lf_sha256}")

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
            # Restore exact original bytes directly without git checkout
            target.write_bytes(orig_bytes)
            restored_bytes = target.read_bytes()
            assert restored_bytes == orig_bytes, f"Byte restoration mismatch on {rel_path}!"
            restored_sha256 = hashlib.sha256(restored_bytes).hexdigest()
            assert restored_sha256 == orig_raw_sha256, f"Hash restoration mismatch on {rel_path}!"
            log(f"Restored exact pre-mutation bytes to {rel_path} (bytes={len(restored_bytes)}, raw_sha256={restored_sha256})")

        # Verify restored file passes guard check
        rc, out = run_cmd([PYTHON, "-m", "pytest", "tests/guards/test_frozen_integrity_guard.py", "-k", Path(rel_path).name, "-q"])
        assert rc == 0, f"Restoration guard run failed for {rel_path}: {out}"
        log(f"Restoration verified clean by guard test (rc=0)")

    # 3. Mutate state machine structure
    sm_path = ROOT / "10-CONFORMANCE" / "state-machines.v6.0.1.json"
    orig_sm_bytes = sm_path.read_bytes()
    orig_sm_raw_sha256 = hashlib.sha256(orig_sm_bytes).hexdigest()
    log("\n--- [STAGE 6] Mutate State Machines JSON Structure (Add Machine) ---")
    log(f"Pre-mutation bytes saved: {len(orig_sm_bytes)} bytes, raw_sha256={orig_sm_raw_sha256}")
    try:
        sm_data = json.loads(orig_sm_bytes.decode("utf-8"))
        sm_data["machines"]["MutatedMachine"] = {"STATE_A": ["STATE_B"]}
        sm_path.write_text(json.dumps(sm_data, indent=2), encoding="utf-8")

        rc, out = run_cmd([PYTHON, "-m", "pytest", "tests/guards/test_kernel_registry_guard.py::test_state_machines_json_structure_and_counts", "-v"])
        log(f"Exit code: {rc} (Expected: 1)")
        log(out.strip())
        assert rc != 0, "Kernel registry guard failed to detect mutated state machines"
        assert "State machine set drifted" in out
    finally:
        sm_path.write_bytes(orig_sm_bytes)
        restored_sm = sm_path.read_bytes()
        assert restored_sm == orig_sm_bytes, "Byte restoration mismatch on state-machines.v6.0.1.json!"
        restored_sm_sha = hashlib.sha256(restored_sm).hexdigest()
        assert restored_sm_sha == orig_sm_raw_sha256, "Hash restoration mismatch on state-machines.v6.0.1.json!"
        log(f"Restored exact pre-mutation bytes to 10-CONFORMANCE/state-machines.v6.0.1.json (bytes={len(restored_sm)}, raw_sha256={restored_sm_sha})")

    # Verify restored state machines passes test
    rc, out = run_cmd([PYTHON, "-m", "pytest", "tests/guards/test_kernel_registry_guard.py::test_state_machines_json_structure_and_counts", "-q"])
    assert rc == 0, f"Restoration verification failed for state machines: {out}"
    log("Restoration verified clean by guard test (rc=0)")

    # 4. Mutate EventType Enum in semantics
    sem_path = ROOT / "10-CONFORMANCE" / "sclass_semantics_v6_0_1.py"
    orig_sem_bytes = sem_path.read_bytes()
    orig_sem_raw_sha256 = hashlib.sha256(orig_sem_bytes).hexdigest()
    log("\n--- [STAGE 7] Mutate EventType Enum in Semantics (Inject Enum Member) ---")
    log(f"Pre-mutation bytes saved: {len(orig_sem_bytes)} bytes, raw_sha256={orig_sem_raw_sha256}")
    try:
        content = orig_sem_bytes.decode("utf-8")
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
        sem_path.write_bytes(orig_sem_bytes)
        restored_sem = sem_path.read_bytes()
        assert restored_sem == orig_sem_bytes, "Byte restoration mismatch on sclass_semantics_v6_0_1.py!"
        restored_sem_sha = hashlib.sha256(restored_sem).hexdigest()
        assert restored_sem_sha == orig_sem_raw_sha256, "Hash restoration mismatch on sclass_semantics_v6_0_1.py!"
        log(f"Restored exact pre-mutation bytes to 10-CONFORMANCE/sclass_semantics_v6_0_1.py (bytes={len(restored_sem)}, raw_sha256={restored_sem_sha})")

    # Verify restored semantics passes test
    rc, out = run_cmd([PYTHON, "-m", "pytest", "tests/guards/test_kernel_registry_guard.py::test_event_type_enum_in_semantics", "-q"])
    assert rc == 0, f"Restoration verification failed for semantics: {out}"
    log("Restoration verified clean by guard test (rc=0)")

    # 5. Final Full Guard Run
    log("\n--- [STAGE 8] Final Clean Guards Run Across All Guards ---")
    rc, out = run_cmd([PYTHON, "-m", "pytest", "tests/guards/", "-v"])
    log(f"Exit code: {rc} (Expected: 0)")
    log(out.strip())
    assert rc == 0, f"Final clean guard run failed: {out}"

    # Explicit post-mutation byte-integrity hash verification
    log("\n--- Post-Mutation Frozen Files Byte Integrity Hash Verification ---")
    for rel_path in FROZEN_FILES:
        target = ROOT / rel_path
        cur_bytes = target.read_bytes()
        cur_lf_sha = hashlib.sha256(cur_bytes.replace(b"\r\n", b"\n")).hexdigest()
        exp_lf_sha = EXPECTED_FROZEN_HASHES[rel_path]
        assert cur_lf_sha == exp_lf_sha, f"Post-mutation hash mismatch on {rel_path}: {cur_lf_sha} != {exp_lf_sha}"
        log(f"OK (byte-verified) {cur_lf_sha}  {rel_path}")

    # Verify git diff on frozen files is empty without having invoked git checkout
    rc, diff_out = run_cmd(["git", "diff", "--exit-code", "--", "00-SPEC", "10-CONFORMANCE"])
    log(f"\nGit diff on 00-SPEC and 10-CONFORMANCE exit code: {rc}")
    assert rc == 0, f"Git diff detected changes in frozen files: {diff_out}"
    log("All 5 frozen files verified completely untouched and clean.")
    log("\nALL 8 MUTATION STAGES PASSED VERIFICATION WITH EXACT BYTE RESTORATION.")

    if not os.environ.get("NO_OVERWRITE_MUTATION_LOG"):
        out_file = ROOT / "delivery-1-00" / "mutation_check.log"
        out_file.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
        log(f"Wrote full mutation log to {out_file}")


if __name__ == "__main__":
    main()
