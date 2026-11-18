#!/usr/bin/env python3
"""Authoritative Vulnerability Ignore Ledger Gate for S-Class Supply Chain Audit.

Enforces CL Block 1 Step 1 Rules:
1. Validates governance/VULN-LEDGER.json schema, ownership, and expiry (<= 90 days).
2. Runs pip-audit UNIGNORED against hash-locked requirements.
3. Performs exact bidirectional reconciliation between report findings and ledger:
   - FAIL if any finding in the audit report is not in the ledger.
   - FAIL if any ledger entry is not found in active dependencies (stale).
   - FAIL if a finding has a fix version in the report but is recorded as 'none' in the ledger.
   - FAIL on missing report, zero dependencies, or abnormal exit.
"""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Dict, List, Optional, Set, Tuple

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
        fix_versions: List[str],
        exploitability_reason: str,
        owner: str,
        expiry: str,
        aliases: Optional[List[str]] = None,
    ):
        self.vuln_id = vuln_id.strip()
        self.package = package.strip()
        self.installed_version = installed_version.strip()
        self.fixed_version = fixed_version.strip()
        self.fix_versions = [v.strip() for v in fix_versions if v and v.strip()]
        self.exploitability_reason = exploitability_reason.strip()
        self.owner = owner.strip()
        self.expiry = expiry.strip()
        self.aliases = set(a.strip() for a in (aliases or []) if a and a.strip())

    def validate(self, today: Optional[datetime.date] = None) -> List[str]:
        errors = []
        if not self.vuln_id or not (
            self.vuln_id.startswith("CVE-")
            or self.vuln_id.startswith("GHSA-")
            or self.vuln_id.startswith("PYSEC-")
        ):
            errors.append(f"Invalid or missing vulnerability ID: '{self.vuln_id}'")
        if not self.package:
            errors.append(f"Vulnerability {self.vuln_id}: missing package name")
        if not self.installed_version:
            errors.append(f"Vulnerability {self.vuln_id}: missing installed_version")
        if not self.fixed_version:
            errors.append(f"Vulnerability {self.vuln_id}: missing fixed_version")
        if not self.exploitability_reason or len(self.exploitability_reason) < 20:
            errors.append(
                f"Vulnerability {self.vuln_id}: reason too short or missing (<20 chars): '{self.exploitability_reason}'"
            )
        if any(bad in self.exploitability_reason.lower() for bad in ["todo", "placeholder", "tbd"]):
            errors.append(f"Vulnerability {self.vuln_id}: placeholder detected in reason: '{self.exploitability_reason}'")
        if self.owner not in AUTHORIZED_OWNERS:
            errors.append(
                f"Vulnerability {self.vuln_id}: unauthorized or missing owner '{self.owner}' (authorized: {sorted(AUTHORIZED_OWNERS)})"
            )

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
                    errors.append(
                        f"Vulnerability {self.vuln_id}: expiry window ({days_ahead} days) exceeds maximum allowable limit of {MAX_EXPIRY_DAYS} days"
                    )
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
        return {}, ["Vulnerability ledger contains 0 entries (empty ledger)"]

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

        raw_fix_versions = item.get("fix_versions")
        if isinstance(raw_fix_versions, list):
            fix_versions = [str(x) for x in raw_fix_versions]
        elif item.get("fixed_version") and str(item.get("fixed_version")).lower() != "none":
            fix_versions = [s.strip() for s in str(item.get("fixed_version")).split(",")]
        else:
            fix_versions = []

        entry = VulnLedgerEntry(
            vuln_id=str(v_id),
            package=str(item.get("package", "")),
            installed_version=str(item.get("installed_version", "")),
            fixed_version=str(item.get("fixed_version", "")),
            fix_versions=fix_versions,
            exploitability_reason=str(item.get("exploitability_reason", "")),
            owner=str(item.get("owner", "")),
            expiry=str(item.get("expiry", "")),
            aliases=item.get("aliases"),
        )
        validation_errs = entry.validate()
        if validation_errs:
            errors.extend(validation_errs)
        entries[entry.vuln_id] = entry

    return entries, errors


def parse_and_reconcile_audit_report(
    report_data: dict,
    ledger_entries: Dict[str, VulnLedgerEntry],
    ledger_path: Path,
) -> Tuple[bool, List[str]]:
    """Bidirectionally reconcile unignored audit report against ledger."""
    errors: List[str] = []

    dependencies = report_data.get("dependencies")
    if not isinstance(dependencies, list):
        return False, ["Malformed pip-audit report JSON: missing 'dependencies' array"]

    if len(dependencies) == 0:
        return False, ["Zero dependencies reported in pip-audit report (empty scan)"]

    # Extract all unignored findings
    # Map finding identifiers (id + aliases) to the finding object
    all_findings: Dict[str, dict] = {}
    finding_identifiers: Set[str] = set()

    for dep in dependencies:
        pkg_name = dep.get("name", "")
        pkg_version = dep.get("version", "")
        for vuln in dep.get("vulns", []):
            vuln_id = vuln.get("id", "")
            aliases = set(vuln.get("aliases", []))
            finding_obj = {
                "id": vuln_id,
                "package": pkg_name,
                "version": pkg_version,
                "fix_versions": vuln.get("fix_versions", []),
                "aliases": aliases,
                "description": vuln.get("description", ""),
            }
            all_findings[vuln_id] = finding_obj
            finding_identifiers.add(vuln_id)
            finding_identifiers.update(aliases)

    # 1. FAIL if any finding in the report is not in the ledger
    for vuln_id, finding in all_findings.items():
        matched = False
        # Check by ID
        if vuln_id in ledger_entries:
            matched = True
        else:
            # Check by aliases
            for alias in finding["aliases"]:
                if alias in ledger_entries:
                    matched = True
                    break
        if not matched:
            errors.append(
                f"UNAUTHORIZED VULNERABILITY: Finding {vuln_id} (package: {finding['package']} {finding['version']}, "
                f"aliases: {list(finding['aliases'])}) is not recorded in authoritative ledger {ledger_path}"
            )

    # 2. FAIL if any ledger entry is not in the findings (stale entry)
    for ledger_id, entry in ledger_entries.items():
        matched = False
        if ledger_id in finding_identifiers:
            matched = True
        else:
            for alias in entry.aliases:
                if alias in finding_identifiers:
                    matched = True
                    break
        if not matched:
            errors.append(
                f"STALE LEDGER ENTRY: Vulnerability '{ledger_id}' in {ledger_path} is NOT present in "
                f"current unignored audit findings for {entry.package} {entry.installed_version}. "
                f"Stale entries must be deleted from the ledger."
            )

    # 3. FAIL if a finding has a fix version in the report but is ledgered as 'none'
    for vuln_id, finding in all_findings.items():
        # Find matching ledger entry
        entry = ledger_entries.get(vuln_id)
        if not entry:
            for alias in finding["aliases"]:
                if alias in ledger_entries:
                    entry = ledger_entries[alias]
                    break
        if entry:
            report_fixes = [f.strip() for f in finding.get("fix_versions", []) if f and f.strip()]
            if report_fixes:
                if entry.fixed_version.lower() == "none" or (not entry.fix_versions and entry.fixed_version.lower() == "none"):
                    errors.append(
                        f"FIX-VERSION MISMATCH: Finding {vuln_id} has known fix version(s) {report_fixes} "
                        f"in audit report, but ledger records fixed_version as 'none'. "
                        f"A finding with a fix version can never be ledgered as 'none'."
                    )

    return len(errors) == 0, errors


def run_unignored_audit_and_reconcile(
    ledger_path: Path,
    req_path: Path,
    output_path: Path,
    audit_executable: Optional[str] = None,
) -> int:
    """Execute pip-audit unignored and reconcile with ledger."""
    print(f"[*] Validating ledger schema and authorization: {ledger_path}")
    ledger_entries, schema_errors = load_vuln_ledger(ledger_path)
    if schema_errors:
        for err in schema_errors:
            print(f"[-] LEDGER SCHEMA ERROR: {err}", file=sys.stderr)
        return 1

    # Locate pip-audit binary
    audit_bin = audit_executable or shutil.which("pip-audit")
    if not audit_bin:
        print("[-] FATAL: pip-audit executable not found on PATH or via python module", file=sys.stderr)
        return 1

    cmd = [audit_bin, "-r", str(req_path), "-f", "json", "-o", str(output_path)]
    # Use direct hash inspection flags where supported
    cmd.extend(["--disable-pip", "--no-deps", "--require-hashes"])

    print(f"[*] Executing unignored pip-audit: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)

    # Note: pip-audit returns 1 if vulnerabilities are found, 0 if none found.
    # Any other return code indicates an abnormal execution failure.
    if res.returncode not in (0, 1):
        print(f"[-] FATAL: pip-audit abnormal execution exit code {res.returncode}", file=sys.stderr)
        if res.stderr:
            print(res.stderr, file=sys.stderr)
        return 1

    if not output_path.exists():
        print(f"[-] FATAL: pip-audit output report JSON not generated: {output_path}", file=sys.stderr)
        return 1

    try:
        report_data = json.loads(output_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[-] FATAL: Failed to parse pip-audit report JSON: {e}", file=sys.stderr)
        return 1

    success, recon_errors = parse_and_reconcile_audit_report(report_data, ledger_entries, ledger_path)
    if not success:
        print("[-] AUDIT RECONCILIATION FAILED:", file=sys.stderr)
        for err in recon_errors:
            print(f"    - {err}", file=sys.stderr)
        return 1

    deps = report_data.get("dependencies", [])
    print(
        f"[+] PASS: Unignored supply chain audit reconciled successfully "
        f"({len(ledger_entries)} authorized findings matched in {len(deps)} dependencies; 0 unledgered, 0 stale, 0 expired)."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce S-Class Authoritative Vulnerability Ledger Gate")
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER, help="Path to VULN-LEDGER.json")
    parser.add_argument("--requirements", type=Path, default=DEFAULT_REQ, help="Path to requirements file")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Path to pip-audit JSON report output")
    parser.add_argument("--run-audit", action="store_true", help="Execute unignored pip-audit and reconcile with ledger")
    parser.add_argument("--check", action="store_true", help="Validate ledger schema and validity only")

    args = parser.parse_args()

    if args.run_audit:
        return run_unignored_audit_and_reconcile(args.ledger, args.requirements, args.output)

    # Default to schema check
    entries, errors = load_vuln_ledger(args.ledger)
    if errors:
        for err in errors:
            print(f"[-] LEDGER VALIDATION ERROR: {err}", file=sys.stderr)
        return 1

    print(
        f"[+] PASS: Validated {len(entries)} authoritative vulnerability ignore entries in {args.ledger.name} "
        f"(all valid, unexpired, and strictly <= {MAX_EXPIRY_DAYS} days window)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
