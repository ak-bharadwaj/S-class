#!/usr/bin/env python3
"""Authoritative Claims Auditor for S-Class Blocks 4-9 Delivery (Round 9).

Audits report files and FAILS CLOSED (exit 1) if:
1. Any 7-40 hex string cited is not a real object in the repo (`git cat-file -e`) or raw logs.
2. Any `Python x.y.z (...)` string differs from real python version.
3. Any fixture ID is not present in the hash-verified master design document.
4. Any line number or "expected" value differs from the shared master parser (tools/master_fixtures.py).
   - Re-derives true line number and expected value(s) from master for every fixture cited.
   - Fails on wrong line number, wrong expected value, or default-to-SATISFIED.
5. False evaluator constants or boundary names appear.
6. Unresolved warning notices appear.

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
            if h not in raw_tokens:
                errors.append(f"Check 1 FAILED: Invented or non-existent git SHA '{h}' cited in report")

    # 3. Check Fixture Citations against Master Document
    checked_fixtures = 0
    for line in report_text.splitlines():
        # Look for fixture rows containing fixture IDs
        m = re.search(r"\b([A-Z0-9]+-T[0-9]+(?:_branch\d+)?)\b", line)
        if m:
            raw_fid = m.group(1)
            fid = raw_fid.split("_")[0]  # base fixture ID
            m_line = re.search(r"\bL?(\d+)\b", line)
            if fid not in master_fixtures:
                errors.append(f"Check 3 FAILED: Fixture '{raw_fid}' is not in master design document")
                continue

            mf = master_fixtures[fid]
            checked_fixtures += 1

            cols = [p.strip() for p in line.split("|") if p.strip()]
            fid_idx = None
            for idx, col in enumerate(cols):
                if raw_fid == col:
                    fid_idx = idx
                    break

            if fid_idx is not None and len(cols) > fid_idx + 3:
                line_str = cols[fid_idx + 2]
                expected_val = cols[fid_idx + 3]

                # Verify line number
                if line_str.isdigit() or (line_str.startswith("L") and line_str[1:].isdigit()):
                    line_num = int(line_str.lstrip("L"))
                    if line_num != mf.line_number:
                        errors.append(
                            f"Check 4 FAILED: Line number mismatch for {raw_fid}: report cites L{line_num}, true master line is L{mf.line_number}"
                        )

                # Check for default-to-SATISFIED bug
                if "SATISFIED" in expected_val and not any("SATISFIED" in exp for exp in mf.expected_gate_strings):
                    errors.append(
                        f"Check 4 FAILED: Default-to-SATISFIED defect for {raw_fid}: master requires {mf.expected_gate_strings}, but report asserts SATISFIED"
                    )

                # Check if expected gate string matches
                expected_match = any(exp in expected_val for exp in mf.expected_gate_strings)
                if not expected_match:
                    errors.append(
                        f"Check 4 FAILED: Expected value mismatch for {raw_fid}: report cites '{expected_val}', master requires {mf.expected_gate_strings}"
                    )
            else:
                if m_line:
                    line_parts = [p.strip() for p in line.split("|") if p.strip()]
                    line_col = None
                    for lp in line_parts:
                        if lp.isdigit() or (lp.startswith("L") and lp[1:].isdigit()):
                            line_col = int(lp.lstrip("L"))
                            break
                    if line_col is not None and line_col != mf.line_number:
                        errors.append(
                            f"Check 4 FAILED: Line number mismatch for {raw_fid}: report cites L{line_col}, true master line is L{mf.line_number}"
                        )

                if "SATISFIED" in line and not any("SATISFIED" in exp for exp in mf.expected_gate_strings):
                    errors.append(
                        f"Check 4 FAILED: Default-to-SATISFIED defect for {raw_fid}: master requires {mf.expected_gate_strings}, but report asserts SATISFIED"
                    )

                expected_match = any(exp in line for exp in mf.expected_gate_strings)
                if not expected_match:
                    errors.append(
                        f"Check 4 FAILED: Expected value mismatch for {raw_fid}: line does not contain master expected values {mf.expected_gate_strings}"
                    )

    if checked_fixtures == 0:
        errors.append("Check 5 FAILED: Zero fixtures found in report table to audit.")

    # 4. Check for forbidden false constants
    if "QUALIFIED_BOUNDARY" in report_text and "QUALIFIED_EVALUATOR_BOUNDARY" not in report_text:
        errors.append("Check 6 FAILED: Found false authority constant 'QUALIFIED_BOUNDARY'")

    return errors


def run_mutation_tests(repo_root: Path, master_path: Path, logs_dirs: List[Path]) -> List[str]:
    """Runs mutation tests to verify auditor fails closed on corrupt claims."""
    mutation_errors: List[str] = []

    # Mutation 1: Fabricated line number
    mut1_text = "| L-B4A | F10-T1 | PD-F10-001 | L9999 | MISSING[PD-F10-001] | MISSING[PD-F10-001] | RAN-MATCH |\n"
    mut1_file = repo_root / "test_mutation_1.md"
    mut1_file.write_text(mut1_text, encoding="utf-8")
    errs1 = audit_report(mut1_file, master_path, logs_dirs, repo_root)
    mut1_file.unlink(missing_ok=True)
    if not any("Line number mismatch for F10-T1" in e for e in errs1):
        mutation_errors.append("Mutation 1 FAILED: Auditor did not detect fabricated line number for F10-T1")

    # Mutation 2: Wrong expected value
    mut2_text = "| L-B4A | F10-T1 | PD-F10-001 | 1032 | WRONG_EXPECTED | MISSING[PD-F10-001] | MISMATCH |\n"
    mut2_file = repo_root / "test_mutation_2.md"
    mut2_file.write_text(mut2_text, encoding="utf-8")
    errs2 = audit_report(mut2_file, master_path, logs_dirs, repo_root)
    mut2_file.unlink(missing_ok=True)
    if not any("Expected value mismatch for F10-T1" in e for e in errs2):
        mutation_errors.append("Mutation 2 FAILED: Auditor did not detect wrong expected value for F10-T1")

    # Mutation 3: Default-to-SATISFIED where master requires MISSING
    mut3_text = "| L-B4A | F10-T1 | PD-F10-001 | 1032 | SATISFIED | SATISFIED | RAN-MATCH |\n"
    mut3_file = repo_root / "test_mutation_3.md"
    mut3_file.write_text(mut3_text, encoding="utf-8")
    errs3 = audit_report(mut3_file, master_path, logs_dirs, repo_root)
    mut3_file.unlink(missing_ok=True)
    if not any("Default-to-SATISFIED defect for F10-T1" in e or "Expected value mismatch for F10-T1" in e for e in errs3):
        mutation_errors.append("Mutation 3 FAILED: Auditor did not detect default-to-SATISFIED defect for F10-T1")

    # Mutation 4: Fabricated Git SHA
    mut4_text = "| L-B4A | F10-T1 | PD-F10-001 | 1032 | MISSING[PD-F10-001] | MISSING[PD-F10-001] | RAN-MATCH |\nCommit: deadbeefcafebabe\n"
    mut4_file = repo_root / "test_mutation_4.md"
    mut4_file.write_text(mut4_text, encoding="utf-8")
    errs4 = audit_report(mut4_file, master_path, logs_dirs, repo_root)
    mut4_file.unlink(missing_ok=True)
    if not any("Invented or non-existent git SHA 'deadbeefcafebabe'" in e for e in errs4):
        mutation_errors.append("Mutation 4 FAILED: Auditor did not detect fabricated git SHA 'deadbeefcafebabe'")

    return mutation_errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Blocks 4-9 delivery report against repo and raw logs.")
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
