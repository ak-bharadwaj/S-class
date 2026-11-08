#!/usr/bin/env python3
"""Authoritative claims auditor for S-Class delivery.

Audits report files and FAILS CLOSED (exit 1) if:
1. Any 7-40 hex string in it is not a real object in the repo (`git cat-file -e`)
   or is not found in a raw log.
2. Any `Python x.y.z (...)` string differs from the `python -VV` captured in raw logs.
3. Any fixture ID is not present in the hash-verified master design document.
4. Any line number or "expected" value differs from the shared master parser (tools/master_fixtures.py).
   - Re-derives true line number and expected value(s) from master for every fixture cited.
   - Fails on wrong line number, wrong expected value, or default-to-SATISFIED.
5. Any number in data assertions is not found in a named raw log line.
6. False evaluator constants or boundary names appear.
7. Unresolved warning notices appear.
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
                    if line.startswith("Python 3."):
                        python_versions.add(line.strip())
                    for word in re.findall(r"\b[A-Za-z0-9_\-\.]{1,80}\b", line):
                        raw_tokens.add(word)
                        if word.isdigit():
                            raw_numbers.add(word)

    return raw_tokens, raw_numbers, python_versions, all_lines


def is_git_object(hex_str: str, repo_root: Path) -> bool:
    """Checks if a 7-40 hex string corresponds to a valid git object in repo."""
    try:
        res = subprocess.run(
            ["git", "cat-file", "-e", f"{hex_str}^{{object}}"],
            cwd=repo_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return res.returncode == 0
    except Exception:
        return False


def audit_report(
    report_path: Path,
    master_path: Path,
    logs_dirs: List[Path],
    repo_root: Path,
) -> List[str]:
    """Runs all audit checks against the report and returns list of errors."""
    errors: List[str] = []

    if not report_path.exists():
        return [f"Report file {report_path} does not exist."]

    # Pre-verify master SHA-256
    try:
        verify_master_sha256(master_path, EXPECTED_MASTER_SHA256)
    except Exception as ex:
        errors.append(f"Master design document {master_path} verification failed: {ex}")
        return errors

    master_fixtures = parse_all_fixtures(master_path)
    raw_tokens, raw_numbers, captured_python_versions, raw_lines = collect_raw_log_data(logs_dirs)

    report_text = report_path.read_text(encoding="utf-8", errors="replace")

    # -------------------------------------------------------------------------
    # Check 1: 7-40 Hex Strings must be real git objects or found in raw logs
    # -------------------------------------------------------------------------
    hex_candidates = re.findall(r"\b[0-9a-fA-F]{7,40}\b", report_text)
    for h in hex_candidates:
        if h.isdigit():
            continue
        if is_git_object(h, repo_root):
            continue
        if h in raw_tokens or any(h.lower() in line.lower() for line in raw_lines):
            continue
        errors.append(f"[Check 1 FAIL] Invented or unreproducible hex/SHA: '{h}'")

    # -------------------------------------------------------------------------
    # Check 2: Python version strings must match captured python -VV in raw logs
    # -------------------------------------------------------------------------
    py_vers_in_report = re.findall(r"Python \d+\.\d+\.\d+ [^\n]+", report_text)
    for pv in py_vers_in_report:
        pv_clean = pv.strip().rstrip("`").rstrip("*").strip()
        if not any(pv_clean in cap for cap in captured_python_versions):
            errors.append(
                f"[Check 2 FAIL] Python version string '{pv_clean}' does not match captured raw python -VV logs"
            )

    # -------------------------------------------------------------------------
    # Check 3: Fixture IDs must exist in the hash-verified master document
    # -------------------------------------------------------------------------
    fixture_id_candidates = set(
        re.findall(r"\b(?:[A-Z0-9]+-T[0-9]+[a-z]?|[A-Z0-9]+-PAIR-[0-9]+[A-Z]?)\b", report_text)
    )
    excluded_tags = {"SHA-256", "UTF-8"}
    for fid in fixture_id_candidates:
        if fid in excluded_tags:
            continue
        if fid not in master_fixtures:
            # Try parsing individually
            try:
                single_fix = parse_master_fixture(master_path, fid)
                if single_fix.parse_status != "OK":
                    errors.append(
                        f"[Check 3 FAIL] Invented fixture ID '{fid}' is not present in hash-verified master: {single_fix.parse_error}"
                    )
            except Exception as ex:
                errors.append(
                    f"[Check 3 FAIL] Invented fixture ID '{fid}' is not present in hash-verified master: {ex}"
                )

    # -------------------------------------------------------------------------
    # Check 4: Line numbers and Expected values derived from master parser (R7-1, R7-2)
    # -------------------------------------------------------------------------
    for line_idx, line in enumerate(report_text.splitlines(), 1):
        # Look for fixture citations with master lines: e.g.
        # | `F4-T1` | `PD-F4-001` | L594 | ... | SATISFIED | ...
        # or F4-T1 | PD-F4-001 | L594 | SATISFIED | ...
        fids = re.findall(r"\b([A-Z0-9]+-T\d+[a-z]?)\b", line)
        lines_cited = re.findall(r"\bL(\d+)\b", line)

        if fids and lines_cited:
            fid = fids[0]
            if fid in excluded_tags:
                continue
            rep_line = int(lines_cited[0])

            try:
                true_fix = parse_master_fixture(master_path, fid)
            except Exception as ex:
                errors.append(f"[Check 4 FAIL] Could not parse master fixture {fid}: {ex}")
                continue

            if true_fix.parse_status != "OK":
                errors.append(f"[Check 4 FAIL] Master parse failed for {fid}: {true_fix.parse_error}")
                continue

            # Verify line number truth
            if rep_line != true_fix.line_number:
                errors.append(
                    f"[Check 4 FAIL] Line number mismatch for {fid} at report line {line_idx}: "
                    f"report says L{rep_line} but master requires L{true_fix.line_number}"
                )

            # Check expected gate output in the line
            # Extract expected token(s) from table columns if table format
            cols = [c.strip().strip("`*") for c in line.split("|")[1:-1]]
            found_expected_match = False
            for exp_target in true_fix.expected_gate_strings:
                if exp_target in line:
                    found_expected_match = True
                    break

            # If no direct substring, check if contradictory values were reported
            if not found_expected_match:
                errors.append(
                    f"[Check 4 FAIL] Expected value mismatch for {fid} at report line {line_idx}: "
                    f"master requires {true_fix.expected_gate_strings} but not found in reported row: '{line.strip()}'"
                )

            # Strict default-to-SATISFIED guard:
            # If true expected is MISSING, BLOCKED, or DENIED, but line contains SATISFIED as expected
            for exp_target in true_fix.expected_gate_strings:
                if (exp_target.startswith("MISSING") or exp_target.startswith("BLOCKED") or exp_target == "DENIED") and "SATISFIED" in line:
                    # Check if SATISFIED is in the expected column
                    # e.g. cols = [fid, must, line, role, status, expected, actual]
                    if len(cols) >= 6:
                        exp_col = cols[5] if len(cols) > 6 else cols[-2]
                        if "SATISFIED" in exp_col and not exp_target.startswith("SATISFIED"):
                            errors.append(
                                f"[Check 4 FAIL] Default-to-SATISFIED defect for {fid}: "
                                f"master requires {exp_target} but report expected column has '{exp_col}'"
                            )

    # -------------------------------------------------------------------------
    # Check 5: Claimed numbers in test assertions must exist in raw logs
    # -------------------------------------------------------------------------
    data_numbers = re.findall(
        r"\b(\d+)\s*(?:passed|failed|mutants?|tests?|vectors?|pairs?|rows?|covered|lines?)\b",
        report_text,
    )
    for num in data_numbers:
        if num not in raw_numbers:
            errors.append(f"[Check 5 FAIL] Unsourced number '{num}' cited in report but absent from raw logs")

    for ratio_match in re.finditer(r"\((?:\d+[/\\])+\d+\)", report_text):
        for num in re.findall(r"\d+", ratio_match.group(0)):
            if num not in raw_numbers:
                errors.append(f"[Check 5 FAIL] Unsourced number '{num}' cited in breakdown but absent from raw logs")

    fabricated_numbers = {"637"}
    for num in fabricated_numbers:
        if re.search(rf"\b{num}\b", report_text) and num not in raw_numbers:
            errors.append(f"[Check 5 FAIL] Unsourced number '{num}' cited in report but absent from raw logs")

    # -------------------------------------------------------------------------
    # Check 6: Check for false constants / false evaluators
    # -------------------------------------------------------------------------
    if "sclass.conformance.v6_suite" in report_text:
        errors.append("[Check 6 FAIL] Invented evaluator 'sclass.conformance.v6_suite' has no source in codebase")

    if re.search(r"QUALIFIED_EVALUATOR_BOUNDARY\s*[:=]\s*['\"]?sclass\.product\.gate_evaluator", report_text):
        errors.append(
            "[Check 6 FAIL] False QUALIFIED_EVALUATOR_BOUNDARY 'sclass.product.gate_evaluator' cited (code has 'QUALIFIED_EVALUATOR')"
        )

    # -------------------------------------------------------------------------
    # Check 7: Fail closed on warning notices or uncovered Block 2 MUSTs
    # -------------------------------------------------------------------------
    if "[WARN" in report_text or "WARN/FAIL" in report_text:
        errors.append("[Check 7 FAIL] Report contains unresolved [WARN] or [WARN/FAIL] notices (fail closed)")

    block2_musts = [
        "PD-F5-001", "PD-F5-002", "PD-F5-003", "PD-F5-004", "PD-F5-005",
        "PD-F9-001", "PD-F9-002", "PD-F9-003", "PD-F9-004",
        "PD-CH5-003", "PD-CH5-004", "PD-CH5-005", "PD-CH5-006", "PD-CH5-007",
        "PD-CH5-008", "PD-CH5-009", "PD-CH5-010", "PD-CH5-011", "PD-CH5-012",
    ]
    for mid in block2_musts:
        res = subprocess.run(
            ["git", "grep", "-E", f"def test_.*{mid.replace('-', '.*')}|{mid}", "tests/"],
            cwd=repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if res.returncode != 0 or not res.stdout.strip():
            errors.append(f"[Check 7 FAIL] Block 2 MUST '{mid}' has ZERO test citations in tests/ (fail closed)")

    return errors


def run_mutation_tests(master_path: Path, logs_dirs: List[Path], repo_root: Path) -> List[str]:
    """Runs 3 mutation tests (wrong line, wrong expected, default-to-SATISFIED) to verify auditor fails closed."""
    mutation_errors: List[str] = []

    # Valid template row using real line and expected
    valid_snippet = (
        "| `F4-T1` | `PD-F4-001` | L594 | single | **RAN-MATCH** | `SATISFIED` | `SATISFIED` |\n"
        "| `F4-T3` | `PD-F4-002` | L596 | single | **RAN-MATCH** | `MISSING[PD-F4-002]` | `MISSING[PD-F4-002]` |\n"
    )

    # Mutation 1: Wrong line number (L595 instead of L594 for F4-T1)
    mut1_text = (
        "| `F4-T1` | `PD-F4-001` | L595 | single | **RAN-MATCH** | `SATISFIED` | `SATISFIED` |\n"
    )
    mut1_file = repo_root / "delivery-2-block2" / "test_mutation_1.md"
    mut1_file.write_text(mut1_text, encoding="utf-8")
    errs1 = audit_report(mut1_file, master_path, logs_dirs, repo_root)
    mut1_file.unlink(missing_ok=True)
    if not any("Line number mismatch for F4-T1" in e for e in errs1):
        mutation_errors.append("Mutation 1 FAILED: Auditor did not detect wrong line number (L595 instead of L594)")

    # Mutation 2: Wrong expected value (e.g. BLOCKED_ON_HUMAN instead of MISSING[PD-F4-002] for F4-T3)
    mut2_text = (
        "| `F4-T3` | `PD-F4-002` | L596 | single | **RAN-MATCH** | `BLOCKED_ON_HUMAN[PD-F4-002]` | `BLOCKED_ON_HUMAN[PD-F4-002]` |\n"
    )
    mut2_file = repo_root / "delivery-2-block2" / "test_mutation_2.md"
    mut2_file.write_text(mut2_text, encoding="utf-8")
    errs2 = audit_report(mut2_file, master_path, logs_dirs, repo_root)
    mut2_file.unlink(missing_ok=True)
    if not any("Expected value mismatch for F4-T3" in e for e in errs2):
        mutation_errors.append("Mutation 2 FAILED: Auditor did not detect wrong expected value for F4-T3")

    # Mutation 3: Default-to-SATISFIED where master requires MISSING
    mut3_text = (
        "| `F4-T3` | `PD-F4-002` | L596 | single | **RAN-MATCH** | `SATISFIED` | `SATISFIED` |\n"
    )
    mut3_file = repo_root / "delivery-2-block2" / "test_mutation_3.md"
    mut3_file.write_text(mut3_text, encoding="utf-8")
    errs3 = audit_report(mut3_file, master_path, logs_dirs, repo_root)
    mut3_file.unlink(missing_ok=True)
    if not any("Default-to-SATISFIED defect for F4-T3" in e or "Expected value mismatch for F4-T3" in e for e in errs3):
        mutation_errors.append("Mutation 3 FAILED: Auditor did not detect default-to-SATISFIED defect for F4-T3")

    return mutation_errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit delivery report against repo and raw logs.")
    parser.add_argument("report_path", nargs="?", default="", help="Path to markdown report to audit")
    parser.add_argument(
        "--master-path",
        default=os.environ.get("SCLASS_MASTER_PATH", ""),
        help="Path to authoritative Master Product Design Markdown file (or env SCLASS_MASTER_PATH).",
    )
    parser.add_argument(
        "--logs-dir",
        action="append",
        default=[],
        help="Directories containing raw verification logs (can specify multiple).",
    )
    default_root = Path(__file__).resolve().parent.parent
    parser.add_argument(
        "--repo-root",
        default=str(default_root),
        help="Path to repository root.",
    )
    parser.add_argument(
        "--run-mutations",
        action="store_true",
        help="Run auditor mutation tests (wrong line, wrong expected, default-to-SATISFIED).",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    master_path = Path(args.master_path).resolve() if args.master_path else (
        Path("/mnt/c/Users/dorni/Downloads/S-CLASS-R32-PACKAGE/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md")
    )

    logs_dirs = [Path(d).resolve() for d in args.logs_dir]
    if not logs_dirs:
        logs_dirs = [
            repo_root / "delivery-2-block2",
            repo_root / "delivery-b1-f2-probe",
            repo_root / "delivery-b2-fixture",
            repo_root / "delivery-b3-f4",
            repo_root / "delivery-b3-e",
            repo_root / "delivery-b3-p11",
        ]

    if args.run_mutations:
        print("Running Claims Auditor Mutation Tests (Requirement C)...")
        mut_errs = run_mutation_tests(master_path, logs_dirs, repo_root)
        if mut_errs:
            for me in mut_errs:
                print(f"MUTATION FAIL: {me}", file=sys.stderr)
            return 1
        print("ALL 3 CLAIMS AUDITOR MUTATION TESTS PASSED (Auditor fails closed on wrong line, wrong expected, default-to-SATISFIED).")
        return 0

    if not args.report_path:
        print("Error: report_path is required when not running --run-mutations", file=sys.stderr)
        return 2

    report_path = Path(args.report_path).resolve()
    errors = audit_report(report_path, master_path, logs_dirs, repo_root)

    print("=" * 60)
    print("S-CLASS CLAIMS AUDITOR (block2_audit.py)")
    print("=" * 60)
    print(f"Report:     {report_path}")
    print(f"Master Doc: {master_path}")
    print(f"Log Dirs:   {', '.join(str(d) for d in logs_dirs)}")
    print("-" * 60)

    if errors:
        print(f"AUDIT FAILED CLOSED: {len(errors)} error(s) discovered!\n", file=sys.stderr)
        for idx, err in enumerate(errors, 1):
            print(f"  {idx}. {err}", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        return 1

    print("AUDIT SUCCESS: All report claims verified against git and raw logs.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
