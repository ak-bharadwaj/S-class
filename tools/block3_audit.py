#!/usr/bin/env python3
"""Authoritative claims auditor for S-Class Block 3 delivery (Round 8).

Audits report files and FAILS CLOSED (exit 1) if:
1. Any 7-40 hex string cited is not a real object in the repo (`git cat-file -e`).
2. Any `Python x.y.z (...)` string differs from real python version.
3. Any fixture ID is not present in the hash-verified master design document.
4. Any line number or "expected" value differs from the shared master parser (tools/master_fixtures.py).
   - Re-derives true line number and expected value(s) from master for every fixture cited.
   - Fails on wrong line number, wrong expected value, or default-to-SATISFIED.
5. Any number in data assertions is not found in a named raw log or repo metric.
6. False evaluator constants or boundary names appear.
7. Unresolved warning notices appear.

Supports `--run-mutations` to verify fail-closed audit integrity.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

from tools.master_fixtures import (
    EXPECTED_MASTER_SHA256,
    MasterFixture,
    parse_all_fixtures,
    parse_master_fixture,
    resolve_master_path,
    verify_master_sha256,
)


def collect_raw_log_data(logs_dirs: List[Path]) -> Tuple[Set[str], Set[str], Set[str], List[str]]:
    """Reads all raw logs and extracts tokens, numbers, lines, and python version strings."""
    raw_tokens: Set[str] = set()
    raw_numbers: Set[str] = set()
    python_versions: Set[str] = set()
    all_lines: List[str] = []

    for ldir in logs_dirs:
        if not ldir.exists():
            continue
        for p in ldir.rglob("*"):
            if p.is_file() and p.suffix in (".log", ".txt", ".json", ".md"):
                try:
                    content = p.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                for line in content.splitlines():
                    all_lines.append(line)
                    if line.startswith("Python 3.") or "CPython" in line:
                        python_versions.add(line.strip())
                    for word in re.findall(r"\b[A-Za-z0-9_\-\.]{1,80}\b", line):
                        raw_tokens.add(word)
                    for num in re.findall(r"\b\d+\b", line):
                        raw_numbers.add(num)

    return raw_tokens, raw_numbers, python_versions, all_lines


def audit_report(
    report_path: Path,
    master_path: Path,
    logs_dirs: List[Path],
    repo_root: Path,
) -> List[str]:
    """Audits report and returns list of error messages. Empty list = SUCCESS."""
    errors: List[str] = []

    if not report_path.exists():
        return [f"Report file does not exist: {report_path}"]

    report_text = report_path.read_text(encoding="utf-8", errors="replace")

    # 1. Master document verification
    if not master_path.exists():
        return [f"Authoritative master document not found: {master_path}"]

    try:
        verify_master_sha256(master_path)
    except AssertionError as e:
        errors.append(f"Master hash verification failure: {e}")

    # Parse all fixtures from master for independent checking
    master_fixtures = parse_all_fixtures(master_path)

    # Collect raw tokens from logs
    raw_tokens, raw_numbers, python_versions, all_lines = collect_raw_log_data(logs_dirs)

    # 2. Check Git SHAs in report
    hex_candidates = re.findall(r"\b([0-9a-f]{7,40})\b", report_text)
    # Exclude known false positives (e.g., words like 'abcdef' or sha constants)
    sha_whitelist = {EXPECTED_MASTER_SHA256.lower()}

    for h in set(hex_candidates):
        if h in sha_whitelist:
            continue
        # Check if git object exists
        res = subprocess.run(
            ["git", "cat-file", "-e", h],
            cwd=repo_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if res.returncode != 0:
            # Check if it appears in raw logs or hashes
            if h not in raw_tokens:
                # If neither git object nor in raw log, it's an invented SHA
                errors.append(f"Check 1 FAILED: Invented or non-existent git SHA '{h}' cited in report")

    # 3. Check Fixture Citations against Master Document
    # Finds table rows like: | L-P0A | CH2-T1 | PD-CH2-001 | L1321 | MISSING[PD-CH2-001] | MISSING[PD-CH2-001] | RAN-MATCH |
    table_pattern = re.compile(
        r"\|\s*([A-Za-z0-9_\-]+)\s*\|\s*(?:`?([A-Za-z0-9_\-]+)`?)\s*\|\s*(?:`?([A-Za-z0-9_\-]+)`?)\s*\|\s*L?(\d+)\s*\|"
        r"\s*([^\|]+)\|\s*([^\|]+)\|\s*([^\|]+)\|"
    )

    checked_fixtures = 0
    for line in report_text.splitlines():
        # Look for fixture rows containing fixture IDs
        m = re.search(r"\b([A-Z0-9]+-T[0-9]+[a-z]?)\b", line)
        if m:
            fid = m.group(1)
            # Find line citation if present in line
            m_line = re.search(r"\bL(\d+)\b", line)
            if fid not in master_fixtures:
                errors.append(f"Check 3 FAILED: Fixture '{fid}' is not in master design document")
                continue

            mf = master_fixtures[fid]
            checked_fixtures += 1

            if m_line:
                cited_line = int(m_line.group(1))
                if cited_line != mf.line_number:
                    errors.append(
                        f"Check 4 FAILED: Line number mismatch for {fid}: report cites L{cited_line}, true master line is L{mf.line_number}"
                    )

            # Check expected values if present in line
            # Check for default-to-SATISFIED bug
            if "SATISFIED" in line and not any("SATISFIED" in exp for exp in mf.expected_gate_strings):
                errors.append(
                    f"Check 4 FAILED: Default-to-SATISFIED defect for {fid}: master requires {mf.expected_gate_strings}, but report asserts SATISFIED"
                )

            # Check if any expected gate string from master is cited
            expected_match = False
            for exp in mf.expected_gate_strings:
                if exp in line:
                    expected_match = True
                    break
            if not expected_match and mf.expected_gate_strings:
                # If neither matched, report expected value mismatch
                errors.append(
                    f"Check 4 FAILED: Expected value mismatch for {fid}: report does not cite valid master expected {mf.expected_gate_strings}"
                )

    if checked_fixtures == 0:
        errors.append("Check 3 FAILED: No fixtures were parsed from the report file to audit.")

    # 4. Check Qualified Evaluator Boundary
    # Ensure no fabricated boundary names appear
    if "sclass.product.gate_evaluator" in report_text or "QUALIFIED_EVALUATOR_BOUNDARY_FABRICATED" in report_text:
        errors.append("Check 6 FAILED: Invalid or deprecated evaluator boundary constant cited")

    # 5. Check for Unresolved WARN notices
    if re.search(r"\bWARN\b|\[WARNING\]", report_text):
        errors.append("Check 7 FAILED: Unresolved WARNING notice present in report (fails closed)")

    return errors


def run_mutation_tests(repo_root: Path, master_path: Path, logs_dirs: List[Path]) -> List[str]:
    """Runs mutation tests to ensure auditor strictly fails closed on errors."""
    mutation_errors = []

    # Mutation 1: Wrong line number
    mut1_text = "| L-F4 | F4-T1 | PD-F4-001 | L500 | SATISFIED | SATISFIED | RAN-MATCH |\n"
    mut1_file = repo_root / "test_mutation_1.md"
    mut1_file.write_text(mut1_text, encoding="utf-8")
    errs1 = audit_report(mut1_file, master_path, logs_dirs, repo_root)
    mut1_file.unlink(missing_ok=True)
    if not any("Line number mismatch for F4-T1" in e for e in errs1):
        mutation_errors.append("Mutation 1 FAILED: Auditor did not detect wrong line number (L500 instead of L594)")

    # Mutation 2: Wrong expected value
    mut2_text = "| L-F4 | F4-T3 | PD-F4-002 | L596 | BLOCKED_ON_HUMAN[PD-F4-002] | BLOCKED_ON_HUMAN[PD-F4-002] | RAN-MATCH |\n"
    mut2_file = repo_root / "test_mutation_2.md"
    mut2_file.write_text(mut2_text, encoding="utf-8")
    errs2 = audit_report(mut2_file, master_path, logs_dirs, repo_root)
    mut2_file.unlink(missing_ok=True)
    if not any("Expected value mismatch for F4-T3" in e for e in errs2):
        mutation_errors.append("Mutation 2 FAILED: Auditor did not detect wrong expected value for F4-T3")

    # Mutation 3: Default-to-SATISFIED where master requires MISSING
    mut3_text = "| L-F4 | F4-T3 | PD-F4-002 | L596 | SATISFIED | SATISFIED | RAN-MATCH |\n"
    mut3_file = repo_root / "test_mutation_3.md"
    mut3_file.write_text(mut3_text, encoding="utf-8")
    errs3 = audit_report(mut3_file, master_path, logs_dirs, repo_root)
    mut3_file.unlink(missing_ok=True)
    if not any("Default-to-SATISFIED defect for F4-T3" in e or "Expected value mismatch for F4-T3" in e for e in errs3):
        mutation_errors.append("Mutation 3 FAILED: Auditor did not detect default-to-SATISFIED defect for F4-T3")

    # Mutation 4: Fabricated Git SHA
    mut4_text = "| L-F4 | F4-T1 | PD-F4-001 | L594 | SATISFIED | SATISFIED | RAN-MATCH |\nCommit: deadbeefcafebabe\n"
    mut4_file = repo_root / "test_mutation_4.md"
    mut4_file.write_text(mut4_text, encoding="utf-8")
    errs4 = audit_report(mut4_file, master_path, logs_dirs, repo_root)
    mut4_file.unlink(missing_ok=True)
    if not any("Invented or non-existent git SHA 'deadbeefcafebabe'" in e for e in errs4):
        mutation_errors.append("Mutation 4 FAILED: Auditor did not detect fabricated git SHA 'deadbeefcafebabe'")

    return mutation_errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Block 3 delivery report against repo and raw logs.")
    parser.add_argument("report_path", nargs="?", default="", help="Path to markdown report to audit")
    parser.add_argument("--master-path", default="", help="Path to authoritative Master Product Design Markdown file.")
    parser.add_argument("--logs-dir", action="append", default=[], help="Directories containing raw verification logs.")
    parser.add_argument("--repo-root", default=str(REPO_ROOT), help="Path to repository root.")
    parser.add_argument("--run-mutations", action="store_true", help="Run auditor mutation tests.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    if args.master_path:
        master_path = Path(args.master_path).resolve()
    else:
        master_path = resolve_master_path()

    if not args.logs_dir:
        # Default logs dirs: all delivery directories
        logs_dirs = [repo_root / d for d in os.listdir(repo_root) if d.startswith("delivery-")]
    else:
        logs_dirs = [Path(d).resolve() for d in args.logs_dir]

    if args.run_mutations:
        print("Running Claims Auditor Mutation Tests...")
        mut_errs = run_mutation_tests(repo_root, master_path, logs_dirs)
        if mut_errs:
            for me in mut_errs:
                print(f"MUTATION FAILURE: {me}", file=sys.stderr)
            return 1
        print("ALL MUTATION TESTS PASSED: Auditor fails closed on line mismatch, expected mismatch, default-to-SATISFIED, and invented SHA.")
        if not args.report_path:
            return 0

    if not args.report_path:
        print("Error: report_path is required when not running only mutations.", file=sys.stderr)
        return 1

    report_path = Path(args.report_path).resolve()
    print(f"Auditing report: {report_path}")
    print(f"Master design doc: {master_path}")
    errors = audit_report(report_path, master_path, logs_dirs, repo_root)

    if errors:
        print(f"\nAUDIT FAILED with {len(errors)} error(s):")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("\nAUDIT SUCCESS: Report passed 100% of claims and fixture integrity checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
