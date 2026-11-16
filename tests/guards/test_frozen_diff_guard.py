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
