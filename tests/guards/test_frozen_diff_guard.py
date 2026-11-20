"""Unit tests for Frozen-Diff CI Guard (Roadmap B01 / R4-2).

Validates:
1. Positive case: working tree files in 00-SPEC/, 10-CONFORMANCE/, and 20-RUNTIME/
   match package hashes or authorized errata rows.
2. Negative case: unauthorized modification to a frozen file is rejected with unified diff.
3. Negative case: unauthorized file addition in a frozen directory is rejected.
4. Negative case: unauthorized drift to an errata file is rejected.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
import pytest

from tools.gates.gate_frozen_diff import (
    evaluate_frozen_diffs,
    generate_unified_diff,
    PACKAGE_ORIGINAL_HASHES,
    ROOT,
)


def test_frozen_diff_guard_positive_baseline():
    """Proves the clean working tree passes the frozen-diff guard with zero violations."""
    ok, violations = evaluate_frozen_diffs(ROOT)
    assert ok, f"Expected clean pass, got violations:\n" + "\n".join(violations)
    assert len(violations) == 0


def test_frozen_diff_guard_rejects_unauthorized_modification(tmp_path):
    """Proves guard fails when an unauthorized diff is introduced into a frozen file."""
    # Create mirror of frozen directories
    for d in ["00-SPEC", "10-CONFORMANCE", "20-RUNTIME"]:
        shutil.copytree(ROOT / d, tmp_path / d)

    # Tamper with frozen spec file
    spec_file = tmp_path / "00-SPEC" / "S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md"
    orig_content = spec_file.read_bytes()
    tampered_content = orig_content + b"\n\n<!-- UNAUTHORIZED TAMPERING -->\n"
    spec_file.write_bytes(tampered_content)

    ok, violations = evaluate_frozen_diffs(tmp_path)
    assert not ok, "Guard should have failed on unauthorized diff"
    assert any("UNAUTHORIZED DIFF in '00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md'" in v for v in violations)

    # Verify unified diff generation with full context
    diff_text = generate_unified_diff(orig_content, tampered_content, "00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md")
    assert "+<!-- UNAUTHORIZED TAMPERING -->" in diff_text
    assert "package/00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md" in diff_text


def test_frozen_diff_guard_rejects_unauthorized_new_file(tmp_path):
    """Proves guard fails when an unauthorized extra file is added to a frozen directory."""
    for d in ["00-SPEC", "10-CONFORMANCE", "20-RUNTIME"]:
        shutil.copytree(ROOT / d, tmp_path / d)

    rogue_file = tmp_path / "10-CONFORMANCE" / "rogue_extension.py"
    rogue_file.write_text("# unauthorized extension", encoding="utf-8")

    ok, violations = evaluate_frozen_diffs(tmp_path)
    assert not ok, "Guard should have failed on unauthorized file"
    assert any("UNAUTHORIZED FILE DISCOVERED: '10-CONFORMANCE/rogue_extension.py'" in v for v in violations)


def test_frozen_diff_guard_rejects_unauthorized_errata_drift(tmp_path):
    """Proves guard fails when an authorized errata file is modified with unauthorized hunks."""
    for d in ["00-SPEC", "10-CONFORMANCE", "20-RUNTIME"]:
        shutil.copytree(ROOT / d, tmp_path / d)

    # Tamper with sclass_semantics_v6_0_1.py beyond authorized E-SEM-1
    sem_file = tmp_path / "10-CONFORMANCE" / "sclass_semantics_v6_0_1.py"
    sem_content = sem_file.read_text(encoding="utf-8")
    tampered = sem_content + "\n# unauthorized extra hunk\n"
    sem_file.write_text(tampered, encoding="utf-8")

    ok, violations = evaluate_frozen_diffs(tmp_path)
    assert not ok, "Guard should have failed on unauthorized errata drift"
    assert any("UNAUTHORIZED ERRATA DRIFT in '10-CONFORMANCE/sclass_semantics_v6_0_1.py'" in v for v in violations)


def test_frozen_diff_guard_rejects_missing_errata_package_file(tmp_path):
    """Proves guard fails if a package file is missing even if present in AUTHORIZED_ERRATA table.

    CL Finding: Frozen-diff guard previously allowed missing package files whenever they had an
    AUTHORIZED_ERRATA entry. The exception must be restricted strictly to the specifically
    authorized relocation.
    """
    for d in ["00-SPEC", "10-CONFORMANCE", "20-RUNTIME"]:
        shutil.copytree(ROOT / d, tmp_path / d)

    # Delete sclass_semantics_v6_0_1.py (which has an AUTHORIZED_ERRATA entry)
    errata_pkg_file = tmp_path / "10-CONFORMANCE" / "sclass_semantics_v6_0_1.py"
    errata_pkg_file.unlink()

    ok, violations = evaluate_frozen_diffs(tmp_path)
    assert not ok, "Guard should have failed when an errata package file is missing"
    assert any("MISSING PACKAGE FILE: Required frozen package file '10-CONFORMANCE/sclass_semantics_v6_0_1.py' not found." in v for v in violations)


def test_frozen_diff_guard_rejects_missing_or_tampered_relocated_property_test(tmp_path):
    """Proves guard verifies the relocated property test exists with authorized hash when missing from 10-CONFORMANCE."""
    for d in ["00-SPEC", "10-CONFORMANCE", "20-RUNTIME"]:
        shutil.copytree(ROOT / d, tmp_path / d)

    # Simulate relocation by removing test_sclass_v6_0_1_property.py from 10-CONFORMANCE
    pkg_prop = tmp_path / "10-CONFORMANCE" / "test_sclass_v6_0_1_property.py"
    if pkg_prop.exists():
        pkg_prop.unlink()

    # Case A: If tests/conformance_ext does not exist in tmp_path, it must fail with MISSING RELOCATED FILE
    ok, violations = evaluate_frozen_diffs(tmp_path)
    assert not ok, "Guard should fail when relocated path does not exist"
    assert any("MISSING RELOCATED FILE" in v for v in violations)

    # Case B: If relocated file exists but hash is unauthorized, it must fail with UNAUTHORIZED RELOCATED FILE HASH
    relocated_dir = tmp_path / "tests" / "conformance_ext"
    relocated_dir.mkdir(parents=True, exist_ok=True)
    relocated_file = relocated_dir / "test_sclass_v6_0_1_property.py"
    relocated_file.write_text("# tampered relocated property test\n", encoding="utf-8")

    ok, violations = evaluate_frozen_diffs(tmp_path)
    assert not ok, "Guard should fail when relocated file hash is unauthorized"
    assert any("UNAUTHORIZED RELOCATED FILE HASH" in v for v in violations)

    # Case C: If relocated file has the authorized hash, it passes
    authorized_sha = "cdfabceced26e9962aad1fd09da2ff0832d3bc4a6d7469d2d1a2873663d0a5de"
    # Copy authentic property test content from ROOT (either in 10-CONFORMANCE or tests/conformance_ext)
    authentic_src = ROOT / "10-CONFORMANCE" / "test_sclass_v6_0_1_property.py"
    if not authentic_src.exists():
        authentic_src = ROOT / "tests" / "conformance_ext" / "test_sclass_v6_0_1_property.py"
    relocated_file.write_bytes(authentic_src.read_bytes())

    ok, violations = evaluate_frozen_diffs(tmp_path)
    assert ok, f"Guard should pass when relocated file has authorized hash, got: {violations}"
    assert len(violations) == 0

