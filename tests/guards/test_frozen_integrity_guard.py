"""Tests for the frozen files SHA-256 byte-integrity guard."""

from __future__ import annotations

import hashlib
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]

FROZEN_HASHES = {
    "00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md": "53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1",
    "10-CONFORMANCE/sclass_semantics_v6_0_1.py": "ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922",
    "10-CONFORMANCE/sclass_kernel_v6_0_1.py": "d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c",
    "10-CONFORMANCE/c1-vectors.v6.0.1.json": "db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8",
    "10-CONFORMANCE/state-machines.v6.0.1.json": "24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad",
}


def sha256_lf(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


@pytest.mark.parametrize("rel_path, expected_hash", list(FROZEN_HASHES.items()))
def test_frozen_file_sha256_exact(rel_path: str, expected_hash: str):
    file_path = ROOT / rel_path
    assert file_path.exists(), f"Protected frozen file is missing: {rel_path}"
    actual_hash = sha256_lf(file_path)
    assert actual_hash == expected_hash, (
        f"INTEGRITY VIOLATION: SHA-256 mismatch for frozen file {rel_path}.\n"
        f"Expected: {expected_hash}\n"
        f"Actual:   {actual_hash}"
    )
