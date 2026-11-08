#!/usr/bin/env python3
"""Verifies the five frozen files match their exact required SHA-256 hashes."""

import hashlib
import sys
from pathlib import Path

FROZEN_FILES = {
    "00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md": "53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1",
    "10-CONFORMANCE/sclass_kernel_v6_0_1.py": "d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c",
    "10-CONFORMANCE/sclass_semantics_v6_0_1.py": "ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922",
    "10-CONFORMANCE/c1-vectors.v6.0.1.json": "db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8",
    "10-CONFORMANCE/state-machines.v6.0.1.json": "24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad",
}

def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    all_ok = True
    print("Verifying 5 frozen hashes...")
    for rel_path, expected_hash in FROZEN_FILES.items():
        file_path = repo_root / rel_path
        if not file_path.exists():
            print(f"[FAIL] Missing file: {rel_path}")
            all_ok = False
            continue
        data = file_path.read_bytes()
        actual_hash = hashlib.sha256(data).hexdigest()
        if actual_hash == expected_hash:
            print(f"[PASS] {rel_path}: {actual_hash} ({len(data)} bytes)")
        else:
            print(f"[FAIL] {rel_path}: expected {expected_hash}, got {actual_hash}")
            all_ok = False

    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
