#!/usr/bin/env python3
"""Authoritative Vulnerability Ignore Ledger Gate (C1 / CL Block 1 Delivery).

Enforces strict supply chain integrity over governance/VULN-LEDGER.json:
1. Every ignored vulnerability must have an authoritative entry in the JSON ledger.
2. Required fields per entry:
   - id: vulnerability CVE/GHSA identifier.
   - package: affected package name.
   - installed_version: pinned version in requirements.
   - fixed_version: upstream fix version or "none".
   - exploitability_reason: genuine technical justification (no placeholders/TODOs).
   - owner: authorized owner ("ak-bharadwaj").
   - expiry: ISO date (YYYY-MM-DD) strictly unexpired AND within 90 days of creation/check.
3. Fails closed on any missing, invalid, or expired entry.
4. Executes pip-audit ONCE under hash-locked requirements and outputs JSON evidence.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEDGER = ROOT / "governance" / "VULN-LEDGER.json"
DEFAULT_REQ = ROOT / "requirements-linux.txt"
DEFAULT_OUTPUT = ROOT / "pip-audit-report.json"
AUTHORIZED_OWNERS = {"ak-bharadwaj"}
MAX_EXPIRY_DAYS = 90


class VulnLedgerEntry:
    def __init__(
        self,
        vuln_id: str,
        package: str,
        installed_version: str,
        fixed_version: str,
        exploitability_reason: str,
        owner: str,
        expiry: str,
    ):
        self.vuln_id = vuln_id.strip()
        self.package = package.strip().lower()
        self.installed_version = installed_version.strip()
        self.fixed_version = fixed_version.strip()
        self.exploitability_reason = exploitability_reason.strip()
        self.owner = owner.strip()
        self.expiry = expiry.strip()

    def validate(self, today: Optional[datetime.date] = None) -> List[str]:
        errors: List[str] = []
        if not self.vuln_id or not (self.vuln_id.startswith("CVE-") or self.vuln_id.startswith("GHSA-")):
            errors.append(f"Invalid or missing vulnerability ID: '{self.vuln_id}'")
        if not self.package:
            errors.append(f"Vulnerability {self.vuln_id}: missing package name")
        if not self.installed_version:
            errors.append(f"Vulnerability {self.vuln_id}: missing installed_version")
        if not self.fixed_version:
            errors.append(f"Vulnerability {self.vuln_id}: missing fixed_version")
        if not self.exploitability_reason or len(self.exploitability_reason) < 20:
            errors.append(f"Vulnerability {self.vuln_id}: reason too short or missing (<20 chars): '{self.exploitability_reason}'")
        if any(bad in self.exploitability_reason.lower() for bad in ["todo", "placeholder", "tbd"]):
            errors.append(f"Vulnerability {self.vuln_id}: placeholder detected in reason: '{self.exploitability_reason}'")
        if self.owner not in AUTHORIZED_OWNERS:
            errors.append(f"Vulnerability {self.vuln_id}: unauthorized or missing owner '{self.owner}' (authorized: {sorted(AUTHORIZED_OWNERS)})")

        if not self.expiry:
            errors.append(f"Vulnerability {self.vuln_id}: missing expiry date")
        else:
            try:
                exp_date = datetime.date.fromisoformat(self.expiry)
                cmp_date = today or datetime.date.today()
                if exp_date < cmp_date:
                    errors.append(f"Vulnerability {self.vuln_id}: EXPIRED on {self.expiry} (current date: {cmp_date})")
                days_ahead = (exp_date - cmp_date).days
                if days_ahead > MAX_EXPIRY_DAYS:
                    errors.append(f"Vulnerability {self.vuln_id}: expiry window ({days_ahead} days) exceeds maximum allowable limit of {MAX_EXPIRY_DAYS} days")
            except ValueError:
                errors.append(f"Vulnerability {self.vuln_id}: invalid expiry date format '{self.expiry}' (expected YYYY-MM-DD)")

        return errors


def load_vuln_ledger(ledger_path: Path) -> Tuple[Dict[str, VulnLedgerEntry], List[str]]:
    if not ledger_path.exists():
        return {}, [f"Vulnerability ledger file not found: {ledger_path}"]

    try:
        data = json.loads(ledger_path.read_text(encoding="utf-8"))
    except Exception as e:
        return {}, [f"Failed to parse vulnerability ledger JSON at {ledger_path}: {e}"]

    if not isinstance(data, dict):
        return {}, [f"Malformed ledger format: root must be a JSON object, got {type(data).__name__}"]

    raw_entries = data.get("entries")
    if not isinstance(raw_entries, list):
        return {}, [f"Malformed ledger format: 'entries' must be a list, got {type(raw_entries).__name__}"]

    if len(raw_entries) == 0:
        return {}, ["Vulnerability ledger contains 0 entries"]

    entries: Dict[str, VulnLedgerEntry] = {}
    errors: List[str] = []

    for idx, item in enumerate(raw_entries):
        if not isinstance(item, dict):
            errors.append(f"Entry {idx} is not a JSON object")
            continue
        v_id = item.get("id", "")
        if v_id in entries:
            errors.append(f"Duplicate vulnerability ID '{v_id}' in ledger at entry index {idx}")
            continue
        entry = VulnLedgerEntry(
            vuln_id=str(v_id),
            package=str(item.get("package", "")),
            installed_version=str(item.get("installed_version", "")),
            fixed_version=str(item.get("fixed_version", "")),
            exploitability_reason=str(item.get("exploitability_reason", "")),
            owner=str(item.get("owner", "")),
            expiry=str(item.get("expiry", "")),
        )
        entries[entry.vuln_id] = entry

    return entries, errors


def validate_ledger(ledger_path: Path, today: Optional[datetime.date] = None) -> Tuple[bool, Dict[str, VulnLedgerEntry], List[str]]:
    entries, parse_errors = load_vuln_ledger(ledger_path)
    if parse_errors:
        return False, {}, parse_errors

    validation_errors: List[str] = []
    for entry in entries.values():
        errs = entry.validate(today)
        validation_errors.extend(errs)

    return (len(validation_errors) == 0), entries, validation_errors


def run_pip_audit(
    requirements_path: Path,
    output_path: Path,
    ledger_entries: Dict[str, VulnLedgerEntry],
    audit_executable: Optional[str] = None,
) -> int:
    audit_bin = audit_executable or shutil.which("pip-audit") or sys.executable + " -m pip_audit"
    cmd: List[str] = []
    if audit_executable:
        cmd.append(audit_executable)
    elif shutil.which("pip-audit"):
        cmd.append("pip-audit")
    else:
        cmd.extend([sys.executable, "-m", "pip_audit"])

    cmd.extend([
        "-r", str(requirements_path),
        "--require-hashes",
        "--no-deps",
        "--disable-pip",
        "-f", "json",
        "-o", str(output_path),
    ])

    for v_id in sorted(ledger_entries.keys()):
        cmd.extend(["--ignore-vuln", v_id])

    print(f"[*] Executing single pip-audit run: {' '.join(cmd[:8])} ... ({len(ledger_entries)} ignore flags)")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.stdout:
        print(res.stdout)
    if res.stderr:
        print(res.stderr, file=sys.stderr)

    if res.returncode != 0:
        print(f"[-] FATAL: pip-audit exited with non-zero code {res.returncode}")
        return res.returncode

    if not output_path.exists():
        print(f"[-] FATAL: pip-audit output file not generated: {output_path}")
        return 1

    try:
        report = json.loads(output_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[-] FATAL: Failed to parse pip-audit report JSON: {e}")
        return 1

    deps = report.get("dependencies", [])
    vuln_count = sum(len(d.get("vulns", [])) for d in deps)
    if vuln_count > 0:
        print(f"[-] FATAL: pip-audit discovered {vuln_count} unignored vulnerabilities in dependencies!")
        for d in deps:
            for v in d.get("vulns", []):
                print(f"    - {d.get('name')} {d.get('version')}: {v.get('id')} ({v.get('description', '')[:80]}...)")
        return 1

    print(f"[+] PASS: pip-audit completed successfully (0 unignored vulnerabilities across {len(deps)} dependencies; {len(ledger_entries)} authorized ignores recorded).")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Authoritative Vulnerability Ignore Ledger Gate")
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER, help="Path to VULN-LEDGER.json")
    parser.add_argument("--requirements", type=Path, default=DEFAULT_REQ, help="Path to requirements-linux.txt")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Path to pip-audit JSON report output")
    parser.add_argument("--run-audit", action="store_true", help="Execute single pip-audit supply chain run using ledger")
    parser.add_argument("--check", action="store_true", help="Validate ledger integrity only")
    parser.add_argument("--dump-args", action="store_true", help="Dump --ignore-vuln CLI arguments from ledger")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    ok, entries, errors = validate_ledger(args.ledger)
    if not ok:
        print(f"[-] FAIL: Vulnerability Ledger validation failed ({len(errors)} errors):", file=sys.stderr)
        for err in errors:
            print(f"    - {err}", file=sys.stderr)
        return 1

    if args.dump_args:
        cli_args = []
        for v_id in sorted(entries.keys()):
            cli_args.extend(["--ignore-vuln", v_id])
        print(" ".join(cli_args))
        return 0

    if args.run_audit:
        return run_pip_audit(args.requirements, args.output, entries)

    print(f"[+] PASS: Validated {len(entries)} authoritative vulnerability ignore entries in {args.ledger.name} (all valid, unexpired, and strictly <= {MAX_EXPIRY_DAYS} days window).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
