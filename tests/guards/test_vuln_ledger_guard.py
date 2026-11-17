"""Tests for Vulnerability Ignore Ledger Integrity (F5 / CL Block 1 Delivery).

Required tests:
1. test_unknown_vulnerability_ignore_id_fails
2. test_expired_vulnerability_ignore_fails
3. test_missing_vulnerability_owner_fails
4. test_missing_vulnerability_expiry_fails
5. test_package_mismatch_fails
6. test_unjustified_ignore_is_rejected
"""

from __future__ import annotations

import datetime
from pathlib import Path
import pytest

from tools.gates.gate_vuln_ledger import (
    DEFAULT_LEDGER,
    LedgerEntry,
    parse_vuln_ledger,
    validate_vuln_ledger,
    verify_ignored_vulns,
)


@pytest.fixture
def authoritative_ledger():
    assert DEFAULT_LEDGER.exists(), "governance/VULN-IGNORE-LEDGER.md must exist"
    return parse_vuln_ledger(DEFAULT_LEDGER)


def test_vuln_ledger_baseline_passes():
    """Proves the committed vulnerability ignore ledger is 100% valid."""
    ok, errors = validate_vuln_ledger(DEFAULT_LEDGER)
    assert ok, f"Committed ledger failed validation: {errors}"
    assert len(errors) == 0


def test_unknown_vulnerability_ignore_id_fails(authoritative_ledger):
    """Proves that ignoring an unknown vulnerability ID without a ledger entry fails closed."""
    ignored = [
        ("CVE-2026-999999", "aiohttp"),  # Unknown ID
    ]
    ok, errors = verify_ignored_vulns(ignored, authoritative_ledger)
    assert not ok
    assert any("UNKNOWN VULNERABILITY IGNORE: 'CVE-2026-999999'" in e for e in errors)


def test_expired_vulnerability_ignore_fails():
    """Proves that an expired ledger entry causes validation to fail."""
    entry = LedgerEntry(
        vuln_id="CVE-2026-111063",
        package="aiohttp",
        reason="Technical reason with sufficient length explaining the vulnerability",
        owner="ak-bharadwaj",
        expiry="2025-01-01",  # Past date
    )
    errors = entry.validate(today=datetime.date(2026, 11, 17))
    assert any("expired on 2025-01-01" in e for e in errors)


def test_missing_vulnerability_owner_fails():
    """Proves that missing or placeholder owner causes validation to fail."""
    for bad_owner in ["", "TODO", "unknown", "None"]:
        entry = LedgerEntry(
            vuln_id="CVE-2026-111063",
            package="aiohttp",
            reason="Technical reason with sufficient length explaining the vulnerability",
            owner=bad_owner,
            expiry="2027-12-31",
        )
        errors = entry.validate()
        assert any("missing or invalid owner" in e for e in errors)


def test_missing_vulnerability_expiry_fails():
    """Proves that missing or malformed expiry causes validation to fail."""
    for bad_expiry in ["", "invalid-date", "2027/12/31"]:
        entry = LedgerEntry(
            vuln_id="CVE-2026-111063",
            package="aiohttp",
            reason="Technical reason with sufficient length explaining the vulnerability",
            owner="ak-bharadwaj",
            expiry=bad_expiry,
        )
        errors = entry.validate()
        assert any("expiry" in e.lower() for e in errors)


def test_package_mismatch_fails(authoritative_ledger):
    """Proves that an ignore associated with the wrong package fails closed."""
    ignored = [
        ("CVE-2026-114145", "aiohttp"),  # CVE-2026-114145 is gitpython, NOT aiohttp!
    ]
    ok, errors = verify_ignored_vulns(ignored, authoritative_ledger)
    assert not ok
    assert any("PACKAGE MISMATCH" in e and "expected package 'aiohttp'" in e for e in errors)


def test_unjustified_ignore_is_rejected():
    """Proves that missing, empty, or placeholder reasons are rejected."""
    for bad_reason in ["", "TODO", "test", "ignore", "short"]:
        entry = LedgerEntry(
            vuln_id="CVE-2026-111063",
            package="aiohttp",
            reason=bad_reason,
            owner="ak-bharadwaj",
            expiry="2027-12-31",
        )
        errors = entry.validate()
        assert any("missing or unjustified reason" in e for e in errors)
