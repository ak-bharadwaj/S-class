#!/usr/bin/env python3
import hashlib
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

files = [
    "00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md",
    "10-CONFORMANCE/sclass_kernel_v6_0_1.py",
    "10-CONFORMANCE/sclass_semantics_v6_0_1.py",
    "20-RUNTIME/sclass_runtime_v6_0_1.py",
    "20-RUNTIME/test_sclass_runtime_v6_0_1.py",
]

print("=== Frozen Files Verification ===")
for rel_path in files:
    full_path = REPO_ROOT / rel_path
    curr_h = hashlib.sha256(full_path.read_bytes()).hexdigest()
    base_blob = subprocess.check_output(
        ["git", "show", f"10fd034938a910967f77bd8dc46fd65b982dc3d3:{rel_path}"],
        cwd=REPO_ROOT,
    )
    base_h = hashlib.sha256(base_blob).hexdigest()
    match = curr_h == base_h
    print(f"{rel_path}: {curr_h} == {base_h} -> Match: {match}")
    assert match, f"Mismatch on {rel_path}!"
print("All 5 frozen files verified byte-identical.")
