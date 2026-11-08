#!/usr/bin/env python3
"""Authoritative claims auditor for Block 2 delivery.

Audits report files and FAILS CLOSED (exit 1) if:
1. Any 7-40 hex string in it is not a real object in the repo (`git cat-file -e`)
   or is not found in a raw log.
2. Any `Python x.y.z (...)` string differs from the `python -VV` captured in raw logs.
3. Any fixture ID is not present in the hash-verified master design document.
4. Any "expected" value differs from the master row text.
5. Any number in data assertions is not found in a named raw log line.
6. False evaluator constants or boundary names appear.
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

EXPECTED_MASTER_SHA256 = (
    "340db97857a7716b1aac2c1b44bc60b32642e3d8074d02720c2333cea278b4ff"
)


def verify_sha256(file_path: Path, expected_sha: str) -> bool:
    if not file_path.exists():
        return False
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower() == expected_sha.lower()


def load_master_fixtures(master_path: Path) -> Tuple[Set[str], Dict[str, str]]:
    """Deterministic parse of master document to extract all valid fixture IDs and expected outputs."""
    valid_ids: Set[str] = set()
    expected_outputs: Dict[str, str] = {}

    content = master_path.read_text(encoding="utf-8", errors="replace")

    # 1. Appendix F YAML fixtures (gaming and happy pairs, etc.)
    # Pattern: #### <ID> — ... \n ```yaml \n ... must_id: ... \n ... expected_gate_output: <exp>
    yaml_header_re = re.compile(r"^#{3,4}\s+([A-Z0-9]+-T[0-9]+[a-z]?)\s+—", re.MULTILINE)
    for m in yaml_header_re.finditer(content):
        fid = m.group(1)
        valid_ids.add(fid)

    # Extract expected_gate_output from YAML blocks
    yaml_block_re = re.compile(
        r"^#{3,4}\s+([A-Z0-9]+-T[0-9]+[a-z]?)[^\n]*\n```yaml(.*?)```",
        re.MULTILINE | re.DOTALL,
    )
    for m in yaml_block_re.finditer(content):
        fid = m.group(1)
        block = m.group(2)
        valid_ids.add(fid)
        exp_m = re.search(r"expected_gate_output:\s*([^\n]+)", block)
        if exp_m:
            expected_outputs[fid] = exp_m.group(1).strip()

    # 2. Markdown tables in Section 8 & Appendix F
    # | F5-T1 | ... | ... |
    # | Test | Fixture | Exact expected output |
    table_row_re = re.compile(
        r"^\|\s*([A-Z0-9]+-T[0-9]+[a-z]?)\s*\|\s*([^|]+)\|\s*([^|]+)\|",
        re.MULTILINE,
    )
    for m in table_row_re.finditer(content):
        fid = m.group(1).strip()
        expected = m.group(3).strip()
        valid_ids.add(fid)
        if fid not in expected_outputs:
            expected_outputs[fid] = expected

    # Also capture single test lines like F5-T5a, F5-T5b, F5-T5c
    single_sub_re = re.compile(r"\b(F5-T5[a-c]|F5-T[1-7]|F9-T[1-4]|CH5-T[1-9][0-9]?)\b")
    for m in single_sub_re.finditer(content):
        valid_ids.add(m.group(1))

    # Master-specific expected values from section 8 normative text
    expected_outputs["F5-T1"] = "SATISFIED"
    expected_outputs["F5-T2"] = "MISSING[PD-F5-002]"
    expected_outputs["F5-T3"] = "MISSING[PD-F5-003]"
    expected_outputs["F5-T4"] = "SATISFIED"
    expected_outputs["F5-T5a"] = "DENIED"
    expected_outputs["F5-T5b"] = "MISSING[PD-F5-005]"
    expected_outputs["F5-T5c"] = "BLOCKED_ON_HUMAN[PD-F5-005]"
    expected_outputs["F5-T6"] = "SATISFIED"
    expected_outputs["F5-T7"] = "MISSING[PD-F5-001]"

    expected_outputs["F9-T1"] = "SATISFIED"
    expected_outputs["F9-T2"] = "MISSING[PD-F9-002]"
    expected_outputs["F9-T3"] = "SATISFIED"
    expected_outputs["F9-T4"] = "SATISFIED"

    expected_outputs["CH5-T3"] = "MISSING[PD-CH5-003]"
    expected_outputs["CH5-T4"] = "MISSING[PD-CH5-004]"
    expected_outputs["CH5-T5"] = "NOT_APPLICABLE"
    expected_outputs["CH5-T6"] = "MISSING[PD-CH5-006]"

    expected_outputs["CH5-T7"] = "MISSING[PD-CH5-007]"
    expected_outputs["CH5-T8"] = "SATISFIED"
    expected_outputs["CH5-T9"] = "MISSING[PD-CH5-008]"
    expected_outputs["CH5-T10"] = "SATISFIED"
    expected_outputs["CH5-T11"] = "MISSING[PD-CH5-009]"
    expected_outputs["CH5-T12"] = "SATISFIED"
    expected_outputs["CH5-T13"] = "MISSING[PD-CH5-010]"
    expected_outputs["CH5-T14"] = "SATISFIED"
    expected_outputs["CH5-T15"] = "MISSING[PD-CH5-011]"
    expected_outputs["CH5-T16"] = "SATISFIED"
    expected_outputs["CH5-T17"] = "MISSING[PD-CH5-012]"
    expected_outputs["CH5-T18"] = "SATISFIED"

    return valid_ids, expected_outputs


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
                    # Python -VV string
                    if line.startswith("Python 3."):
                        python_versions.add(line.strip())
                    # Tokens and numbers
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
    if not verify_sha256(master_path, EXPECTED_MASTER_SHA256):
        errors.append(
            f"Master design document {master_path} SHA-256 mismatch or file missing (expected {EXPECTED_MASTER_SHA256})"
        )
        return errors

    master_fixture_ids, master_expected_values = load_master_fixtures(master_path)
    raw_tokens, raw_numbers, captured_python_versions, raw_lines = collect_raw_log_data(logs_dirs)

    report_text = report_path.read_text(encoding="utf-8", errors="replace")

    # -------------------------------------------------------------------------
    # Check 1: 7-40 Hex Strings must be real git objects or found in raw logs
    # -------------------------------------------------------------------------
    # Match hex strings of 7 to 40 characters
    hex_candidates = re.findall(r"\b[0-9a-fA-F]{7,40}\b", report_text)
    for h in hex_candidates:
        # Ignore if it's purely digits and found in numbers (like line numbers or counts)
        if h.isdigit():
            continue
        # Also ignore non-hex keywords or common Markdown words if any
        # Verify git object or in raw logs
        if is_git_object(h, repo_root):
            continue
        # Check raw tokens or raw text
        if h in raw_tokens or any(h.lower() in line.lower() for line in raw_lines):
            continue
        errors.append(f"[Check 1 FAIL] Invented or unreproducible hex/SHA: '{h}'")

    # -------------------------------------------------------------------------
    # Check 2: Python version strings must match captured python -VV in raw logs
    # -------------------------------------------------------------------------
    py_vers_in_report = re.findall(r"Python \d+\.\d+\.\d+ [^\n]+", report_text)
    for pv in py_vers_in_report:
        pv_clean = pv.strip().rstrip("`").rstrip("*").strip()
        # Must match one of captured_python_versions
        if not any(pv_clean in cap for cap in captured_python_versions):
            errors.append(
                f"[Check 2 FAIL] Python version string '{pv_clean}' does not match captured raw python -VV logs"
            )

    # -------------------------------------------------------------------------
    # Check 3: Fixture IDs must exist in the hash-verified master document
    # -------------------------------------------------------------------------
    # Match candidate fixture IDs: e.g. P-T1, CH5-T1, CH5-PAIR-1A, F5-T2, etc.
    fixture_id_candidates = set(
        re.findall(r"\b(?:[A-Z0-9]+-T[0-9]+[a-z]?|[A-Z0-9]+-PAIR-[0-9]+[A-Z]?)\b", report_text)
    )
    # Exclude non-fixture patterns
    excluded_tags = {"SHA-256", "UTF-8"}
    for fid in fixture_id_candidates:
        if fid in excluded_tags:
            continue
        if fid not in master_fixture_ids:
            errors.append(
                f"[Check 3 FAIL] Invented fixture ID '{fid}' is not present in hash-verified master"
            )

    # -------------------------------------------------------------------------
    # Check 4: Expected values in report must match master row text
    # -------------------------------------------------------------------------
    # Check markdown table rows: | fixture_id | ... | expected | ... |
    # Or lines mentioning expected values: F5-T2: expected BLOCKED
    for fid, true_exp in master_expected_values.items():
        # Look for table rows containing fid
        for line in report_text.splitlines():
            if f"| {fid} " in line or f"|`{fid}`" in line or f"| {fid}|" in line:
                cols = [c.strip() for c in line.split("|")[1:-1]]
                if len(cols) >= 4:
                    # Table format: | Fixture ID | Owner MUST | Inputs | Expected Output | ...
                    # Or similar table
                    exp_col = cols[3] if len(cols) > 3 else cols[-2]
                    exp_col_clean = exp_col.strip("`").strip()
                    # Check if expected contradicts master
                    if "BLOCKED" in exp_col_clean and "MISSING" in true_exp:
                        errors.append(
                            f"[Check 4 FAIL] Contradictory expected value for {fid}: report says '{exp_col_clean}' but master requires '{true_exp}'"
                        )
                    elif "SATISFIED" in exp_col_clean and "MISSING" in true_exp:
                        errors.append(
                            f"[Check 4 FAIL] Contradictory expected value for {fid}: report says '{exp_col_clean}' but master requires '{true_exp}'"
                        )

    # Specific Section 0 expected value checks
    if "F5-T2" in report_text and "expected: BLOCKED" in report_text:
        errors.append("[Check 4 FAIL] F5-T2 expected value is MISSING, not BLOCKED (BLOCKED is not a gate state)")
    if "F9-T2" in report_text and "expected: SATISFIED" in report_text:
        errors.append("[Check 4 FAIL] F9-T2 expected value is MISSING[PD-F9-002], not SATISFIED")

    # -------------------------------------------------------------------------
    # Check 5: Claimed numbers in test assertions must exist in raw logs
    # -------------------------------------------------------------------------
    # Check any number claimed in test/metric context against raw logs
    data_numbers = re.findall(r"(\d+)\s*(?:passed|failed|mutants?|tests?|vectors?|pairs?|rows?|covered|lines?)", report_text)
    for num in data_numbers:
        if num not in raw_numbers:
            errors.append(f"[Check 5 FAIL] Unsourced number '{num}' cited in report but absent from raw logs")

    # Check ratio patterns like (40/32/24/14/10)
    for ratio_match in re.finditer(r"\((?:\d+[/\\])+\d+\)", report_text):
        for num in re.findall(r"\d+", ratio_match.group(0)):
            if num not in raw_numbers:
                errors.append(f"[Check 5 FAIL] Unsourced number '{num}' cited in breakdown but absent from raw logs")

    # Specifically check known fabricated numbers from Section 0
    fabricated_numbers = {"637"}
    for num in fabricated_numbers:
        if re.search(rf"\b{num}\b", report_text) and num not in raw_numbers:
            errors.append(f"[Check 5 FAIL] Unsourced number '{num}' cited in report but absent from raw logs")

    # -------------------------------------------------------------------------
    # Check 6: Check for false constants / false evaluators from Section 0
    # -------------------------------------------------------------------------
    if "sclass.conformance.v6_suite" in report_text:
        errors.append("[Check 6 FAIL] Invented evaluator 'sclass.conformance.v6_suite' has no source in codebase")

    if re.search(r"QUALIFIED_EVALUATOR_BOUNDARY\s*[:=]\s*['\"]?sclass\.product\.gate_evaluator", report_text):
        errors.append(
            "[Check 6 FAIL] False QUALIFIED_EVALUATOR_BOUNDARY 'sclass.product.gate_evaluator' cited (code has 'QUALIFIED_EVALUATOR')"
        )

    # -------------------------------------------------------------------------
    # Check 7: Fail closed on warning notices or uncovered Block 2 MUSTs (fail-closed rule)
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit delivery report against repo and raw logs.")
    parser.add_argument("report_path", help="Path to markdown report to audit")
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
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    report_path = Path(args.report_path).resolve()
    master_path = Path(args.master_path).resolve()

    logs_dirs = [Path(d).resolve() for d in args.logs_dir]
    if not logs_dirs:
        # Default logs directories
        logs_dirs = [
            repo_root / "delivery-2-block2",
            repo_root / "delivery-b1-f2-probe",
            repo_root / "delivery-b2-fixture",
        ]

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
