#!/usr/bin/env python3
"""Guard test pinning the integrity of the committed Master Product Design (Decision D2)."""

import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MASTER_DESIGN_PATH = REPO_ROOT / "docs" / "design" / "S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md"

EXPECTED_SHA256 = "340db97857a7716b1aac2c1b44bc60b32642e3d8074d02720c2333cea278b4ff"
EXPECTED_SIZE_BYTES = 699827

def test_master_design_file_exists():
    assert MASTER_DESIGN_PATH.exists(), f"Master design file missing at {MASTER_DESIGN_PATH}"

def test_master_design_size_bytes():
    assert MASTER_DESIGN_PATH.exists()
    size = MASTER_DESIGN_PATH.stat().st_size
    assert size == EXPECTED_SIZE_BYTES, f"Master design size mismatch: {size} != {EXPECTED_SIZE_BYTES}"

def test_master_design_sha256_exact():
    assert MASTER_DESIGN_PATH.exists()
    data = MASTER_DESIGN_PATH.read_bytes()
    h = hashlib.sha256(data).hexdigest()
    assert h == EXPECTED_SHA256, f"Master design SHA256 mismatch: {h} != {EXPECTED_SHA256}"
