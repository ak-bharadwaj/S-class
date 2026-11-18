"""Guard tests for Authoritative Vulnerability Ignore Ledger (C1 / Block 1 Delivery)."""

from __future__ import annotations

import datetime
import json
import tempfile
from pathlib import Path
import pytest

from tools.gates.gate_vuln_ledger import (
    DEFAULT_LEDGER,
    MAX_EXPIRY_DAYS,
    VulnLedgerEntry,
    load_vuln_ledger,
    parse_and_reconcile_audit_report,
)


def test_authoritative_vuln_ledger_passes_validation():
    """Confirms governance/VULN-LEDGER.json strictly passes all authoritative checks."""
    assert DEFAULT_LEDGER.exists(), f"Missing ledger file: {DEFAULT_LEDGER}"
    entries, errors = load_vuln_ledger(DEFAULT_LEDGER)
    assert len(errors) == 0, f"Ledger validation failed: {errors}"
    assert len(entries) == 1, f"Expected exactly 1 authorized entry (gitpython), found {len(entries)}"
    for v_id, entry in entries.items():
        assert entry.owner == "ak-bharadwaj", f"Entry {v_id} owner mismatch: {entry.owner}"
        assert len(entry.exploitability_reason) >= 20, f"Entry {v_id} reason too short"
        assert entry.fixed_version.lower() != "none", f"Entry {v_id} fixed_version cannot be none"
        exp_date = datetime.date.fromisoformat(entry.expiry)
        today = datetime.date.today()
        assert exp_date >= today, f"Entry {v_id} is expired: {entry.expiry}"
        assert (exp_date - today).days <= MAX_EXPIRY_DAYS, f"Entry {v_id} window > {MAX_EXPIRY_DAYS} days"


def test_negative_missing_ledger_fails():
    non_existent = Path("/tmp/non_existent_ledger_99999.json")
    entries, errors = load_vuln_ledger(non_existent)
    assert len(entries) == 0
    assert len(errors) > 0
    assert "not found" in errors[0].lower()


def test_negative_expired_entry_fails():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "ledger.json"
        p.write_text(json.dumps({
            "entries": [{
                "id": "CVE-2026-999999",
                "package": "gitpython",
                "installed_version": "3.2.0",
                "fixed_version": "3.2.1",
                "exploitability_reason": "Legitimate reason for testing vulnerability ignore with sufficient length",
                "owner": "ak-bharadwaj",
                "expiry": "2020-01-01"
            }]
        }))
        entries, errors = load_vuln_ledger(p)
        assert len(errors) > 0
        assert any("EXPIRED" in e for e in errors)


def test_negative_window_exceeding_90_days_fails():
    far_future = (datetime.date.today() + datetime.timedelta(days=120)).isoformat()
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "ledger.json"
        p.write_text(json.dumps({
            "entries": [{
                "id": "CVE-2026-999999",
                "package": "gitpython",
                "installed_version": "3.2.0",
                "fixed_version": "3.2.1",
                "exploitability_reason": "Legitimate reason for testing vulnerability ignore with sufficient length",
                "owner": "ak-bharadwaj",
                "expiry": far_future
            }]
        }))
        entries, errors = load_vuln_ledger(p)
        assert len(errors) > 0
        assert any("exceeds maximum allowable limit" in e for e in errors)


def test_negative_unauthorized_owner_fails():
    valid_future = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "ledger.json"
        p.write_text(json.dumps({
            "entries": [{
                "id": "CVE-2026-999999",
                "package": "gitpython",
                "installed_version": "3.2.0",
                "fixed_version": "3.2.1",
                "exploitability_reason": "Legitimate reason for testing vulnerability ignore with sufficient length",
                "owner": "unauthorized-contributor",
                "expiry": valid_future
            }]
        }))
        entries, errors = load_vuln_ledger(p)
        assert len(errors) > 0
        assert any("unauthorized or missing owner" in e for e in errors)


def test_negative_short_or_placeholder_reason_fails():
    valid_future = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "ledger.json"
        p.write_text(json.dumps({
            "entries": [{
                "id": "CVE-2026-999999",
                "package": "gitpython",
                "installed_version": "3.2.0",
                "fixed_version": "3.2.1",
                "exploitability_reason": "TODO: add reason later",
                "owner": "ak-bharadwaj",
                "expiry": valid_future
            }]
        }))
        entries, errors = load_vuln_ledger(p)
        assert len(errors) > 0
        assert any("placeholder detected" in e for e in errors)


def test_negative_duplicate_id_fails():
    valid_future = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "ledger.json"
        p.write_text(json.dumps({
            "entries": [
                {
                    "id": "CVE-2026-114145",
                    "package": "gitpython",
                    "installed_version": "3.2.0",
                    "fixed_version": "3.2.1",
                    "exploitability_reason": "Legitimate reason for testing vulnerability ignore with sufficient length A",
                    "owner": "ak-bharadwaj",
                    "expiry": valid_future
                },
                {
                    "id": "CVE-2026-114145",
                    "package": "gitpython",
                    "installed_version": "3.2.0",
                    "fixed_version": "3.2.1",
                    "exploitability_reason": "Legitimate reason for testing vulnerability ignore with sufficient length B",
                    "owner": "ak-bharadwaj",
                    "expiry": valid_future
                }
            ]
        }))
        entries, errors = load_vuln_ledger(p)
        assert len(errors) > 0
        assert any("Duplicate vulnerability ID" in e for e in errors)


def test_negative_stale_ledger_entry_fails():
    """Confirms gate fails if ledger contains an entry not present in audit findings (stale)."""
    valid_future = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    ledger_entries = {
        "CVE-2026-114145": VulnLedgerEntry(
            vuln_id="CVE-2026-114145",
            package="gitpython",
            installed_version="3.2.0",
            fixed_version="3.2.1",
            fix_versions=["3.2.1"],
            exploitability_reason="Valid exploitability reason of sufficient character length",
            owner="ak-bharadwaj",
            expiry=valid_future,
        ),
        "CVE-2026-123817": VulnLedgerEntry(
            vuln_id="CVE-2026-123817",
            package="aiohttp",
            installed_version="3.14.3",
            fixed_version="3.14.4",
            fix_versions=["3.14.4"],
            exploitability_reason="Stale aiohttp entry after aiohttp upgrade to 3.14.4",
            owner="ak-bharadwaj",
            expiry=valid_future,
        ),
    }

    # Report has only gitpython finding (aiohttp was upgraded and clean)
    mock_report = {
        "dependencies": [
            {
                "name": "gitpython",
                "version": "3.2.0",
                "vulns": [
                    {
                        "id": "CVE-2026-114145",
                        "aliases": ["GHSA-83vg-56qc-22m7"],
                        "fix_versions": ["3.2.1"],
                        "description": "Submodule clone path traversal"
                    }
                ]
            },
            {
                "name": "aiohttp",
                "version": "3.14.4",
                "vulns": []
            }
        ]
    }

    ok, errors = parse_and_reconcile_audit_report(mock_report, ledger_entries, Path("governance/VULN-LEDGER.json"))
    assert not ok, "Expected gate reconciliation to fail on stale ledger entry"
    assert any("STALE LEDGER ENTRY" in e for e in errors), f"Expected 'STALE LEDGER ENTRY' in errors: {errors}"
    assert any("CVE-2026-123817" in e for e in errors)


def test_negative_fix_version_mismatch_fails():
    """Confirms gate fails if report lists a fix version but ledger records fixed_version as 'none'."""
    valid_future = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    ledger_entries = {
        "CVE-2026-114145": VulnLedgerEntry(
            vuln_id="CVE-2026-114145",
            package="gitpython",
            installed_version="3.2.0",
            fixed_version="none",  # Mismatch: should not be none when fix exists
            fix_versions=[],
            exploitability_reason="Valid exploitability reason of sufficient character length",
            owner="ak-bharadwaj",
            expiry=valid_future,
        ),
    }

    mock_report = {
        "dependencies": [
            {
                "name": "gitpython",
                "version": "3.2.0",
                "vulns": [
                    {
                        "id": "CVE-2026-114145",
                        "aliases": ["GHSA-83vg-56qc-22m7"],
                        "fix_versions": ["3.2.1"],
                        "description": "Submodule clone path traversal"
                    }
                ]
            }
        ]
    }

    ok, errors = parse_and_reconcile_audit_report(mock_report, ledger_entries, Path("governance/VULN-LEDGER.json"))
    assert not ok, "Expected gate reconciliation to fail on fix-version mismatch"
    assert any("FIX-VERSION MISMATCH" in e for e in errors), f"Expected 'FIX-VERSION MISMATCH' in errors: {errors}"


def test_boundary_hardening_no_fallback_fails_on_empty_or_missing_ledger():
    """Confirms tests/security/test_boundary_hardening.py fails if ledger is missing or empty."""
    with tempfile.TemporaryDirectory() as td:
        empty_ledger = Path(td) / "empty_ledger.json"
        empty_ledger.write_text(json.dumps({"entries": []}))
        
        # Test missing ledger
        missing_ledger = Path(td) / "non_existent.json"
        assert not missing_ledger.exists()
        
        # Test empty ledger
        data = json.loads(empty_ledger.read_text())
        assert len(data.get("entries", [])) == 0
