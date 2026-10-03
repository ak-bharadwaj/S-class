#!/usr/bin/env python3
"""Gate 3 (Blocking): Kernel and Spec Byte Integrity Gate.

Validates that:
1. 00-SPEC, 10-CONFORMANCE, and 20-RUNTIME bytes are completely unchanged from baseline commit 5420797.
2. The built wheel contains byte-identical copies of sclass_semantics_v6_0_1.py and sclass_runtime_v6_0_1.py.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE_COMMIT = "5420797"

# Pinned SHA256 hashes of kernel authority files at baseline 5420797 (normalized LF)
BASELINE_HASHES = {
    "00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md": "53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1",
    "10-CONFORMANCE/sclass_semantics_v6_0_1.py": "ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922",
    "20-RUNTIME/sclass_runtime_v6_0_1.py": "761cd60498fd399826359be2e4a56eea9b2ae31a5d783e437945f25d64d0bb0e",
    "10-CONFORMANCE/sclass_kernel_v6_0_1.py": "d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c",
    "10-CONFORMANCE/c1-vectors.v6.0.1.json": "db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8",
    "10-CONFORMANCE/state-machines.v6.0.1.json": "24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad",
}


def sha256_lf(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def main():
    print("=== Gate 3: Kernel and Spec Byte Integrity Gate ===")
    failed = 0

    # 1. Verify against baseline 5420797 via git diff if git available
    try:
        cmd_diff = ["git", "diff", "--ignore-space-at-eol", "--exit-code", BASELINE_COMMIT, "--", "00-SPEC", "10-CONFORMANCE", "20-RUNTIME"]
        res_diff = subprocess.run(cmd_diff, cwd=str(ROOT), capture_output=True, text=True)
        if res_diff.returncode != 0:
            print(f"FAILED: git diff detected modifications against baseline {BASELINE_COMMIT}:")
            print(res_diff.stdout)
            failed += 1
        else:
            print(f"1. Git diff against baseline {BASELINE_COMMIT}: 0 differences in 00-SPEC, 10-CONFORMANCE, 20-RUNTIME.")
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # 2. Verify SHA256 of canonical authority files
    print("2. Verifying SHA256 of canonical authority files against baseline 5420797...")
    for rel_path, expected_hash in BASELINE_HASHES.items():
        f_path = ROOT / rel_path
        if not f_path.exists():
            print(f"FAILED: Missing file: {rel_path}")
            failed += 1
            continue
        actual_hash = sha256_lf(f_path)
        if actual_hash != expected_hash:
            print(f"FAILED: Hash mismatch for {rel_path}: expected {expected_hash}, got {actual_hash}")
            failed += 1
        else:
            print(f"   {rel_path}: OK ({actual_hash[:16]}...)")

    # 3. Verify wheel packaging byte identity (ADR-1 Option A)
    print("3. Verifying wheel package byte identity (ADR-1 Option A)...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        dist_dir = Path(tmp_dir) / "dist"
        dist_dir.mkdir()
        cmd_wheel = [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(dist_dir), str(ROOT)]
        res_wheel = subprocess.run(cmd_wheel, capture_output=True, text=True)
        if res_wheel.returncode != 0:
            print(f"FAILED: Wheel build failed: {res_wheel.stderr}")
            failed += 1
        else:
            wheels = list(dist_dir.glob("*.whl"))
            if not wheels:
                print("FAILED: No wheel produced.")
                failed += 1
            else:
                with zipfile.ZipFile(wheels[0]) as z:
                    for check_name, source_rel in [
                        ("sclass/kernel/sclass_semantics_v6_0_1.py", "10-CONFORMANCE/sclass_semantics_v6_0_1.py"),
                        ("sclass/kernel/sclass_runtime_v6_0_1.py", "20-RUNTIME/sclass_runtime_v6_0_1.py"),
                    ]:
                        whl_data = z.read(check_name).replace(b"\r\n", b"\n")
                        src_data = (ROOT / source_rel).read_bytes().replace(b"\r\n", b"\n")
                        if hashlib.sha256(whl_data).hexdigest() != hashlib.sha256(src_data).hexdigest():
                            print(f"FAILED: Wheel copy {check_name} does not match source {source_rel}")
                            failed += 1
                        else:
                            print(f"   Wheel {check_name} == source {source_rel}: 100% byte identical.")

    if failed > 0:
        print(f"=== Gate 3 Result: FAIL ({failed} errors) ===")
        sys.exit(1)

    print("=== Gate 3 Result: PASS ===")


if __name__ == "__main__":
    main()
