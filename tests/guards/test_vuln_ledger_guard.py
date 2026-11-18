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
    validate_ledger,
    main,
)


def test_authoritative_vuln_ledger_passes_validation():
    """Confirms governance/VULN-LEDGER.json strictly passes all authoritative checks."""
    assert DEFAULT_LEDGER.exists(), f"Missing ledger file: {DEFAULT_LEDGER}"
    ok, entries, errors = validate_ledger(DEFAULT_LEDGER)
    assert ok, f"Ledger validation failed: {errors}"
    assert len(entries) == 19, f"Expected exactly 19 authorized entries, found {len(entries)}"
    for v_id, entry in entries.items():
        assert entry.owner == "ak-bharadwaj", f"Entry {v_id} owner mismatch: {entry.owner}"
        assert len(entry.exploitability_reason) >= 20, f"Entry {v_id} reason too short"
        exp_date = datetime.date.fromisoformat(entry.expiry)
        today = datetime.date.today()
        assert exp_date >= today, f"Entry {v_id} is expired: {entry.expiry}"
        assert (exp_date - today).days <= MAX_EXPIRY_DAYS, f"Entry {v_id} window > {MAX_EXPIRY_DAYS} days"


def test_negative_missing_ledger_fails():
    non_existent = Path("/tmp/non_existent_ledger_99999.json")
    ok, entries, errors = validate_ledger(non_existent)
    assert not ok
    assert len(errors) > 0
    assert "not found" in errors[0].lower()


def test_negative_expired_entry_fails():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "ledger.json"
        p.write_text(json.dumps({
            "entries": [{
                "id": "CVE-2026-999999",
                "package": "aiohttp",
                "installed_version": "3.14.3",
                "fixed_version": "none",
                "exploitability_reason": "Legitimate reason for testing vulnerability ignore with sufficient length",
                "owner": "ak-bharadwaj",
                "expiry": "2020-01-01"
            }]
        }))
        ok, entries, errors = validate_ledger(p)
        assert not ok
        assert any("EXPIRED" in e for e in errors)


def test_negative_window_exceeding_90_days_fails():
    far_future = (datetime.date.today() + datetime.timedelta(days=120)).isoformat()
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "ledger.json"
        p.write_text(json.dumps({
            "entries": [{
                "id": "CVE-2026-999999",
                "package": "aiohttp",
                "installed_version": "3.14.3",
                "fixed_version": "none",
                "exploitability_reason": "Legitimate reason for testing vulnerability ignore with sufficient length",
                "owner": "ak-bharadwaj",
                "expiry": far_future
            }]
        }))
        ok, entries, errors = validate_ledger(p)
        assert not ok
        assert any("exceeds maximum allowable limit" in e for e in errors)


def test_negative_unauthorized_owner_fails():
    valid_future = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "ledger.json"
        p.write_text(json.dumps({
            "entries": [{
                "id": "CVE-2026-999999",
                "package": "aiohttp",
                "installed_version": "3.14.3",
                "fixed_version": "none",
                "exploitability_reason": "Legitimate reason for testing vulnerability ignore with sufficient length",
                "owner": "unauthorized-contributor",
                "expiry": valid_future
            }]
        }))
        ok, entries, errors = validate_ledger(p)
        assert not ok
        assert any("unauthorized or missing owner" in e for e in errors)


def test_negative_short_or_placeholder_reason_fails():
    valid_future = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "ledger.json"
        p.write_text(json.dumps({
            "entries": [{
                "id": "CVE-2026-999999",
                "package": "aiohttp",
                "installed_version": "3.14.3",
                "fixed_version": "none",
                "exploitability_reason": "TODO: add reason later",
                "owner": "ak-bharadwaj",
                "expiry": valid_future
            }]
        }))
        ok, entries, errors = validate_ledger(p)
        assert not ok
        assert any("placeholder detected" in e for e in errors)


def test_negative_duplicate_id_fails():
    valid_future = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "ledger.json"
        p.write_text(json.dumps({
            "entries": [
                {
                    "id": "CVE-2026-111063",
                    "package": "aiohttp",
                    "installed_version": "3.14.3",
                    "fixed_version": "none",
                    "exploitability_reason": "Legitimate reason for testing vulnerability ignore with sufficient length A",
                    "owner": "ak-bharadwaj",
                    "expiry": valid_future
                },
                {
                    "id": "CVE-2026-111063",
                    "package": "aiohttp",
                    "installed_version": "3.14.3",
                    "fixed_version": "none",
                    "exploitability_reason": "Legitimate reason for testing vulnerability ignore with sufficient length B",
                    "owner": "ak-bharadwaj",
                    "expiry": valid_future
                }
            ]
        }))
        ok, entries, errors = validate_ledger(p)
        assert not ok
        assert any("Duplicate vulnerability ID" in e for e in errors)


def test_gate_cli_check_mode():
    res = main(["--check"])
    assert res == 0
