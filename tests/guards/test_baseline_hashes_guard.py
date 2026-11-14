"""Tests for baseline_hashes tool integrity and manifest tampering guard.

Guarantees:
1. tools/baseline_hashes.py --check succeeds on the clean repository tree.
2. validate_manifest_file fails closed if FROZEN-MANIFEST is missing, malformed,
   or tampered.
3. Canonical package anchors cannot be overridden by manifest tampering.
4. If BASELINE-HASHES.txt is tampered or out of date, --check fails with exit code 1.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import pytest

from tools.baseline_hashes import (
    CANONICAL_PACKAGE_HASHES,
    validate_manifest_file,
    generate_baseline_hashes_content,
)

ROOT = Path(__file__).resolve().parents[2]
BASELINE_REPORT = ROOT / "governance" / "BASELINE-HASHES.txt"
FROZEN_MANIFEST = ROOT / "governance" / "FROZEN-MANIFEST.sha256"


def test_baseline_hashes_check_passes_on_tree():
    """Verify that tools/baseline_hashes.py --check succeeds on current repo."""
    cmd = [sys.executable, str(ROOT / "tools" / "baseline_hashes.py"), "--check"]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    assert proc.returncode == 0, f"--check failed: {proc.stdout}\n{proc.stderr}"
    assert "PASS:" in proc.stdout


def test_validate_manifest_file_clean():
    """Verify validate_manifest_file passes against authoritative manifest."""
    if not FROZEN_MANIFEST.exists():
        pytest.skip("FROZEN-MANIFEST.sha256 not present in test environment")
    parsed = validate_manifest_file(FROZEN_MANIFEST)
    for path, expected_hash in CANONICAL_PACKAGE_HASHES.items():
        assert parsed.get(path) == expected_hash


def test_validate_manifest_file_missing(tmp_path: Path):
    """Missing manifest must raise FileNotFoundError."""
    missing = tmp_path / "nonexistent.sha256"
    with pytest.raises(FileNotFoundError):
        validate_manifest_file(missing)


def test_validate_manifest_file_corrupted_hash(tmp_path: Path):
    """Mutated hash in manifest must be rejected with ValueError."""
    fake_manifest = tmp_path / "FROZEN-MANIFEST.sha256"
    lines = [
        f"{h}  {p}\n" for p, h in CANONICAL_PACKAGE_HASHES.items()
    ]
    # Corrupt one hash
    lines[0] = "0" * 64 + "  " + list(CANONICAL_PACKAGE_HASHES.keys())[0] + "\n"
    fake_manifest.write_text("".join(lines), encoding="utf-8")

    with pytest.raises(ValueError, match="MANIFEST INTEGRITY TAMPER"):
        validate_manifest_file(fake_manifest)


def test_validate_manifest_file_malformed_length(tmp_path: Path):
    """Invalid hex length must be rejected with ValueError."""
    fake_manifest = tmp_path / "FROZEN-MANIFEST.sha256"
    bad_lines = ["1234abcd  00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md\n"]
    fake_manifest.write_text("".join(bad_lines), encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid SHA-256 hash"):
        validate_manifest_file(fake_manifest)


def test_validate_manifest_file_missing_monitored_entry(tmp_path: Path):
    """Omission of a canonical monitored file must be rejected with ValueError."""
    fake_manifest = tmp_path / "FROZEN-MANIFEST.sha256"
    # Omit the first monitored file
    items = list(CANONICAL_PACKAGE_HASHES.items())[1:]
    lines = [f"{h}  {p}\n" for p, h in items]
    fake_manifest.write_text("".join(lines), encoding="utf-8")

    with pytest.raises(ValueError, match="missing required canonical monitored path"):
        validate_manifest_file(fake_manifest)


def test_cannot_override_canonical_anchors(tmp_path: Path):
    """validate_manifest_file must refuse to override canonical anchors even if manifest differs."""
    fake_manifest = tmp_path / "FROZEN-MANIFEST.sha256"
    # Attempt to tamper hash in manifest
    lines = [f"{'a' * 64}  {p}\n" for p in CANONICAL_PACKAGE_HASHES]
    fake_manifest.write_text("".join(lines), encoding="utf-8")

    with pytest.raises(ValueError):
        validate_manifest_file(fake_manifest)


def test_check_fails_on_tampered_baseline_report(tmp_path: Path, monkeypatch):
    """--check must exit with code 1 if BASELINE-HASHES.txt does not match recomputed report."""
    tampered_file = tmp_path / "BASELINE-HASHES.txt"
    tampered_file.write_text("TAMPERED REPORT\n", encoding="utf-8")

    import tools.baseline_hashes as bh
    monkeypatch.setattr(bh, "BASELINE_HASHES_FILE", tampered_file)
    monkeypatch.setattr(sys, "argv", ["baseline_hashes.py", "--check"])

    ret = bh.main()
    assert ret == 1
