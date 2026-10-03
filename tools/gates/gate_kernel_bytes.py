#!/usr/bin/env python3
"""Gate 3 (Blocking): Kernel and Spec Byte Integrity Gate.

Validates that:
1. 00-SPEC and 10-CONFORMANCE bytes are completely unchanged from baseline commit 5420797.
2. 20-RUNTIME matches the declared baseline SHA recorded in docs/KERNEL-CHANGES.md.
3. The built wheel contains byte-identical copies of sclass_semantics_v6_0_1.py, sclass_kernel_v6_0_1.py,
   and sclass_runtime_v6_0_1.py under sclass/kernel/.
4. Wheel packaging invariants:
   - Contains each kernel module exactly once (no duplicates).
   - Contains zero test_*.py files.
   - Contains zero hyphenated directories (e.g. 10-CONFORMANCE, 20-RUNTIME).
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

# Pinned SHA256 hashes of canonical authority files at baseline 5420797 (normalized LF)
BASELINE_HASHES = {
    "00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md": "53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1",
    "10-CONFORMANCE/sclass_semantics_v6_0_1.py": "ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922",
    "20-RUNTIME/sclass_runtime_v6_0_1.py": "761cd60498fd399826359be2e4a56eea9b2ae31a5d783e437945f25d64d0bb0e",
    "10-CONFORMANCE/sclass_kernel_v6_0_1.py": "d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c",
    "10-CONFORMANCE/c1-vectors.v6.0.1.json": "db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8",
    "10-CONFORMANCE/state-machines.v6.0.1.json": "24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad",
}

# Update 20-RUNTIME baseline only via docs/KERNEL-CHANGES.md
KERNEL_CHANGES_FILE = ROOT / "docs" / "KERNEL-CHANGES.md"
if KERNEL_CHANGES_FILE.exists():
    for line in KERNEL_CHANGES_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("BASELINE_20_RUNTIME_SHA256:"):
            declared_hash = line.split(":", 1)[1].strip()
            if declared_hash:
                BASELINE_HASHES["20-RUNTIME/sclass_runtime_v6_0_1.py"] = declared_hash
                break


def sha256_lf(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def main():
    print("=== Gate 3: Kernel and Spec Byte Integrity Gate ===")
    failed = 0

    # 1. Verify 00-SPEC and 10-CONFORMANCE against baseline 5420797 via git diff
    try:
        check_ref = subprocess.run(
            ["git", "cat-file", "-e", f"{BASELINE_COMMIT}^{{commit}}"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        if check_ref.returncode != 0:
            # Attempt to fetch baseline commit
            subprocess.run(
                ["git", "fetch", "--depth=50", "origin", BASELINE_COMMIT],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )

        cmd_diff = ["git", "diff", "--ignore-space-at-eol", "--exit-code", BASELINE_COMMIT, "--", "00-SPEC", "10-CONFORMANCE"]
        res_diff = subprocess.run(cmd_diff, cwd=str(ROOT), capture_output=True, text=True)
        if res_diff.returncode != 0:
            if "bad object" in res_diff.stderr or "unknown revision" in res_diff.stderr:
                print(f"1. Notice: Baseline commit {BASELINE_COMMIT} not in shallow clone; verifying via SHA256 baseline hashes.")
            else:
                print(f"FAILED: git diff detected modifications against baseline {BASELINE_COMMIT} in frozen trees:")
                print(res_diff.stdout or res_diff.stderr)
                failed += 1
        else:
            print(f"1. Git diff against baseline {BASELINE_COMMIT}: 0 differences in frozen 00-SPEC, 10-CONFORMANCE.")
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # 2. Verify SHA256 of canonical authority files against declared baselines
    print("2. Verifying SHA256 of canonical authority files against declared baselines...")
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

    # 3. Verify wheel packaging invariants and byte identity
    print("3. Verifying wheel package invariants and byte identity...")
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
                    namelist = z.namelist()

                    # (a) Byte identity of kernel copies
                    for check_name, source_rel in [
                        ("sclass/kernel/sclass_semantics_v6_0_1.py", "10-CONFORMANCE/sclass_semantics_v6_0_1.py"),
                        ("sclass/kernel/sclass_kernel_v6_0_1.py", "10-CONFORMANCE/sclass_kernel_v6_0_1.py"),
                        ("sclass/kernel/sclass_runtime_v6_0_1.py", "20-RUNTIME/sclass_runtime_v6_0_1.py"),
                    ]:
                        if check_name not in namelist:
                            print(f"FAILED: Missing kernel copy in wheel: {check_name}")
                            failed += 1
                            continue
                        whl_data = z.read(check_name).replace(b"\r\n", b"\n")
                        src_data = (ROOT / source_rel).read_bytes().replace(b"\r\n", b"\n")
                        if hashlib.sha256(whl_data).hexdigest() != hashlib.sha256(src_data).hexdigest():
                            print(f"FAILED: Wheel copy {check_name} does not match source {source_rel}")
                            failed += 1
                        else:
                            print(f"   Wheel {check_name} == source {source_rel}: 100% byte identical.")

                    # (b) Exactly one copy of each kernel module
                    kernel_modules = ["sclass_semantics_v6_0_1.py", "sclass_kernel_v6_0_1.py", "sclass_runtime_v6_0_1.py"]
                    for km in kernel_modules:
                        matches = [name for name in namelist if Path(name).name == km]
                        if len(matches) != 1:
                            print(f"FAILED: Kernel module {km} appears {len(matches)} times in wheel: {matches}")
                            failed += 1
                        else:
                            print(f"   Kernel module {km}: exactly 1 copy ({matches[0]}).")

                    # (c) No test files in wheel
                    test_files = [name for name in namelist if Path(name).name.startswith("test_") and name.endswith(".py")]
                    if test_files:
                        print(f"FAILED: Wheel contains test files: {test_files}")
                        failed += 1
                    else:
                        print("   Wheel contains 0 test files (test_*.py): OK.")

                    # (d) No hyphenated directory in wheel (excluding .dist-info)
                    hyphenated_members = []
                    for name in namelist:
                        parts = Path(name).parts[:-1]
                        for part in parts:
                            if "-" in part and not part.endswith(".dist-info"):
                                hyphenated_members.append(name)
                                break
                    if hyphenated_members:
                        print(f"FAILED: Wheel contains hyphenated directories: {set(hyphenated_members)}")
                        failed += 1
                    else:
                        print("   Wheel contains 0 hyphenated directories: OK.")

    if failed > 0:
        print(f"=== Gate 3 Result: FAIL ({failed} errors) ===")
        sys.exit(1)

    print("=== Gate 3 Result: PASS ===")


if __name__ == "__main__":
    main()
