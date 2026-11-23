"""Tests for T5: generated 72-entry P0-P11 check_registry from Master."""
from __future__ import annotations

import pathlib

from sclass.product import check_registry

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_check_registry_has_all_72_master_subchecks() -> None:
    reg = check_registry.get_registry()
    assert len(reg) == 72, f"Expected 72 sub-checks, got {len(reg)}"


def test_p2_line_1740_not_mistranscribed() -> None:
    reg = check_registry.get_registry()
    names = {r.check_name for r in reg.values()}
    assert "No PROPOSED requirement relied upon" in names
    assert "Invariant consistency" not in names


def test_check_registry_matches_generator_output() -> None:
    import sys

    sys.path.insert(0, str(REPO_ROOT / "tools"))
    import generate_check_registry  # type: ignore

    generated = generate_check_registry.render_check_registry(
        REPO_ROOT / "docs/design/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md"
    )
    committed = (REPO_ROOT / "src/sclass/product/check_registry.py").read_text(
        encoding="utf-8"
    )
    assert generated == committed


def test_generated_files_have_no_carriage_returns() -> None:
    """W13 guard: committed generated files must use strict LF line endings with zero \\r."""
    for rel in ("src/sclass/product/registry_table.py", "src/sclass/product/check_registry.py"):
        raw = (REPO_ROOT / rel).read_bytes()
        cr_count = raw.count(b"\r")
        assert cr_count == 0, f"Found {cr_count} carriage return (\\r) bytes in {rel}"

