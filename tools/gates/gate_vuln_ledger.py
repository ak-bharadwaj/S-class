#!/usr/bin/env python3
"""Vulnerability Ignore Ledger Gate (F5 / CL Block 1 Delivery).

Enforces strict integrity over governance/VULN-IGNORE-LEDGER.md:
1. Every ignored vulnerability must have an entry in the ledger.
2. Required columns: id | package | reason | owner | expiry.
3. Owner cannot be empty or placeholder.
4. Expiry must be a valid ISO date >= current date (unexpired).
5. Reason must provide real technical justification (no placeholders/TODOs).
6. Package name must match the affected package.
7. Unknown IDs fail closed.
"""

from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEDGER = ROOT / "governance" / "VULN-IGNORE-LEDGER.md"

RE_TABLE_ROW = re.compile(r"^\|\s*`?([A-Za-z0-9_\-]+)`?\s*\|\s*`?([A-Za-z0-9_\-]+)`?\s*\|\s*([^|]+)\|\s*`?([A-Za-z0-9_\-]+)`?\s*\|\s*`?([0-9]{4}-[0-9]{2}-[0-9]{2})`?\s*\|$")


class LedgerEntry:
    def __init__(self, vuln_id: str, package: str, reason: str, owner: str, expiry: str):
        self.vuln_id = vuln_id.strip("` ")
        self.package = package.strip("` ").lower()
        self.reason = reason.strip()
        self.owner = owner.strip("` ")
        self.expiry = expiry.strip("` ")

    def validate(self, today: Optional[datetime.date] = None) -> List[str]:
        errors = []
        if not self.vuln_id:
            errors.append("Vulnerability ID is empty")
        if not self.package:
            errors.append(f"Vulnerability {self.vuln_id}: missing package")
        if not self.owner or self.owner.lower() in {"todo", "unknown", "none"}:
            errors.append(f"Vulnerability {self.vuln_id}: missing or invalid owner '{self.owner}'")
        if not self.reason or len(self.reason) < 10 or self.reason.lower() in {"todo", "ignore", "test"}:
            errors.append(f"Vulnerability {self.vuln_id}: missing or unjustified reason '{self.reason}'")

        if not self.expiry:
            errors.append(f"Vulnerability {self.vuln_id}: missing expiry date")
        else:
            try:
                exp_date = datetime.date.fromisoformat(self.expiry)
                cmp_date = today or datetime.date.today()
                if exp_date < cmp_date:
                    errors.append(f"Vulnerability {self.vuln_id}: expired on {self.expiry} (today is {cmp_date})")
            except ValueError:
                errors.append(f"Vulnerability {self.vuln_id}: invalid expiry date format '{self.expiry}' (expected YYYY-MM-DD)")

        return errors


def parse_vuln_ledger(ledger_path: Path) -> Dict[str, LedgerEntry]:
    if not ledger_path.exists():
        raise FileNotFoundError(f"Vulnerability ignore ledger '{ledger_path}' not found.")

    text = ledger_path.read_text(encoding="utf-8")
    entries: Dict[str, LedgerEntry] = {}

    for line_no, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line.startswith("|") or "---" in line or line.lower().startswith("| id"):
            continue
        parts = [p.strip() for p in line.split("|")[1:-1]]
        if len(parts) != 5:
            raise ValueError(f"Malformed row at {ledger_path}:{line_no}: expected 5 columns, found {len(parts)} in '{line}'")
        v_id, pkg, reason, owner, expiry = parts
        entry = LedgerEntry(v_id, pkg, reason, owner, expiry)
        if entry.vuln_id in entries:
            raise ValueError(f"Duplicate entry for '{entry.vuln_id}' at {ledger_path}:{line_no}")
        entries[entry.vuln_id] = entry

    return entries


def extract_ci_ignored_vulns(ci_workflow_path: Path) -> List[str]:
    if not ci_workflow_path.exists():
        raise FileNotFoundError(f"CI workflow '{ci_workflow_path}' not found.")
    content = ci_workflow_path.read_text(encoding="utf-8")
    matches = re.findall(r"--ignore-vuln\s+([A-Za-z0-9_\-]+)", content)
    seen = set()
    result = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            result.append(m)
    return result


def validate_vuln_ledger(ledger_path: Path, today: Optional[datetime.date] = None) -> Tuple[bool, List[str]]:
    try:
        entries = parse_vuln_ledger(ledger_path)
    except Exception as e:
        return False, [f"Failed to parse ledger: {e}"]

    if not entries:
        return False, ["Vulnerability ledger contains no entries."]

    all_errors = []
    for entry in entries.values():
        errs = entry.validate(today)
        all_errors.extend(errs)

    return (len(all_errors) == 0), all_errors


def verify_ignored_vulns(
    ignored_vulns: List[Tuple[str, Optional[str]]],
    ledger_entries: Dict[str, LedgerEntry],
    today: Optional[datetime.date] = None,
) -> Tuple[bool, List[str]]:
    """Verifies that every ignored vulnerability is authorized by the ledger.

    Each item in ignored_vulns is (vuln_id, expected_package).
    """
    errors = []
    for v_id, exp_pkg in ignored_vulns:
        if v_id not in ledger_entries:
            errors.append(f"UNKNOWN VULNERABILITY IGNORE: '{v_id}' is ignored in CI but not in VULN-IGNORE-LEDGER.md")
            continue
        entry = ledger_entries[v_id]
        entry_errs = entry.validate(today)
        if entry_errs:
            errors.extend(entry_errs)
        if exp_pkg and entry.package != exp_pkg.strip().lower():
            errors.append(f"PACKAGE MISMATCH: '{v_id}' expected package '{exp_pkg}', but ledger specifies '{entry.package}'")

    return (len(errors) == 0), errors


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate vulnerability ignore ledger")
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER, help="Path to VULN-IGNORE-LEDGER.md")
    parser.add_argument("--ci-workflow", type=Path, default=ROOT / ".github" / "workflows" / "ci.yml", help="Path to ci.yml")
    parser.add_argument("--dump-pip-audit-args", action="store_true", help="Output --ignore-vuln CLI arguments for pip-audit")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    ok, errors = validate_vuln_ledger(args.ledger)
    if not ok:
        print("FAIL: Vulnerability Ignore Ledger validation errors:")
        for err in errors:
            print(f"  - {err}")
        return 1

    entries = parse_vuln_ledger(args.ledger)
    if args.dump_pip_audit_args:
        cli_args = []
        for v_id in sorted(entries.keys()):
            cli_args.extend(["--ignore-vuln", v_id])
        print(" ".join(cli_args))
        return 0

    # Enforce CI ignored inventory against ledger
    ci_ignored = extract_ci_ignored_vulns(args.ci_workflow)
    if not ci_ignored:
        print(f"FAIL: No ignored vulnerabilities extracted from {args.ci_workflow}")
        return 1

    ignored_tuples = [(v_id, None) for v_id in ci_ignored]
    ci_ok, ci_errors = verify_ignored_vulns(ignored_tuples, entries)
    if not ci_ok:
        print("FAIL: CI ignored vulnerability inventory check failed:")
        for err in ci_errors:
            print(f"  - {err}")
        return 1

    # Check for unjustified ledger entries (in ledger but not ignored in CI)
    unjustified = set(entries.keys()) - set(ci_ignored)
    if unjustified:
        print(f"FAIL: Unjustified entries in ledger (not ignored in CI): {sorted(unjustified)}")
        return 1

    print(f"PASS: Verified {len(entries)} vulnerability ignore entries in {args.ledger} strictly matching CI ignored inventory ({len(ci_ignored)} IDs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
