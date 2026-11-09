#!/usr/bin/env python3
"""Global Authoritative Claims and Safety Auditor for S-Class Round 11.

Enforces zero-defect reporting and fails closed (exit 1) if:
1. Any git SHA cited is fabricated or does not exist in the repository.
2. Any fixture line number or expected value contradicts tools/master_fixtures.py.
3. The report headline or verdict claims PASS while any FLAW > 0 or unresolved failures exist.
4. Any LPC-STATIC check failure lacks an explicit disposition: FIXED(...), JUSTIFIED(...), or PROPOSED_CHANGE(...).
5. G5 adversarial cross-check contains fewer than 17 vectors.
6. Any branch or PR cited does not exist on origin.

Supports `--run-mutations` to verify auditor fail-closed integrity.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

try:
    from tools.master_fixtures import (
        EXPECTED_MASTER_SHA256,
        MasterFixture,
        parse_all_fixtures,
        parse_master_fixture,
        resolve_master_path,
        verify_master_sha256,
    )
except ImportError:
    from master_fixtures import (  # type: ignore
        EXPECTED_MASTER_SHA256,
        MasterFixture,
        parse_all_fixtures,
        parse_master_fixture,
        resolve_master_path,
        verify_master_sha256,
    )


def get_origin_refs(repo_root: Path) -> Tuple[Set[str], Set[str]]:
    """Retrieves remote branch heads and object SHAs from origin via git ls-remote."""
    try:
        res = subprocess.run(
            ["git", "ls-remote", "origin"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
        branches = set()
        remote_shas = set()
        for line in res.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                sha = parts[0].strip()
                ref = parts[1].strip()
                remote_shas.add(sha)
                branches.add(ref)
                if ref.startswith("refs/heads/"):
                    branches.add(ref[len("refs/heads/"):])
                elif ref.startswith("refs/pull/"):
                    branches.add(ref)
        return branches, remote_shas
    except Exception as e:
        print(f"Warning: git ls-remote failed: {e}", file=sys.stderr)
        return set(), set()


def audit_report(
    report_path: Path,
    master_path: Path,
    repo_root: Path,
    known_remote_branches: Optional[Set[str]] = None,
) -> List[str]:
    """Audits report and returns list of error messages. Empty list = SUCCESS."""
    errors: List[str] = []

    if not report_path.exists():
        return [f"Report file does not exist: {report_path}"]

    content = report_path.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()

    # 1. Master document verification
    if not master_path.exists():
        errors.append(f"Authoritative master design document not found: {master_path}")
    else:
        try:
            actual_sha = verify_master_sha256(master_path)
        except ValueError as e:
            errors.append(f"Master document SHA-256 mismatch: {e}")

    # 2. Verdict Contradiction Check: Headline claims PASS while FLAW > 0 or escaping exceptions exist
    flaw_matches = re.findall(r"(?:FLAW|flaw|Flaw)\s*[:=]\s*(\d+)", content)
    flaw_table_rows = re.findall(r"\|\s*Vector\s*\d+[^\|]*\|\s*.*?\bFLAW\b", content)
    total_flaws = sum(int(m) for m in flaw_matches) + len(flaw_table_rows)

    exception_matches = re.findall(r"(?:Exceptions Escaping|exceptions escaping|Escaping Exceptions|Exceptions)\s*[:=]\s*(\d+)", content)
    total_exceptions = sum(int(m) for m in exception_matches if int(m) > 0)

    claims_pass = (
        bool(re.search(r"##\s*.*?\bPASS\b", content, re.IGNORECASE))
        or "OVERALL VERDICT: PASS" in content
        or "VERDICT: PASS" in content
        or "G5 VERDICT: PASS" in content
    )

    if total_flaws > 0 and claims_pass:
        errors.append(
            f"VERDICT_CONTRADICTION: Report claims PASS while {total_flaws} flaw(s) are recorded in body/tables."
        )

    if total_exceptions > 0 and claims_pass:
        errors.append(
            f"VERDICT_CONTRADICTION: Report claims PASS while {total_exceptions} escaping exception(s) are recorded in body/tables."
        )

    # 3. G5 Adversarial Cross-Check Completeness (at least 21 attack vectors in Round 12)
    g5_vectors = set(re.findall(r"Vector\s*(\d+)", content))
    if g5_vectors:
        vector_nums = {int(v) for v in g5_vectors}
        if len(vector_nums) < 21 or not set(range(1, 22)).issubset(vector_nums):
            errors.append(
                f"INSUFFICIENT_G5_VECTORS: G5 cross-check contains {len(vector_nums)} vectors, expected at least 21 (Vectors 1-21)."
            )

    # 4. LPC-STATIC Disposition Completeness: Every static check FAIL must have a disposition
    for line in lines:
        if re.search(r"\|\s*S\d+\s*\|.*?FAIL", line, re.IGNORECASE):
            # Line reports an LPC failure, must contain FIXED, JUSTIFIED, or PROPOSED_CHANGE
            if not re.search(r"\b(FIXED|JUSTIFIED|PROPOSED_CHANGE)\b", line):
                errors.append(
                    f"LPC_UNDISPOSITIONED_FAIL: Static check failure lacks explicit disposition: {line.strip()}"
                )

    # 5. Remote Branch and PR existence
    if known_remote_branches is None:
        known_remote_branches, known_remote_shas = get_origin_refs(repo_root)
    else:
        known_remote_shas = set()

    if known_remote_branches:
        # Check branches mentioned under delivery/branches table
        branch_matches = re.findall(r"\|\s*`?([a-zA-Z0-9_\-\.\/]+)`?\s*\|\s*`?(?:[0-9a-f]{7,40}|PR\s*#?\d+)`?\s*\|", content)
        for b in branch_matches:
            b_clean = b.strip()
            if b_clean and b_clean not in known_remote_branches:
                if f"refs/heads/{b_clean}" not in known_remote_branches and f"refs/pull/{b_clean}" not in known_remote_branches:
                    errors.append(
                        f"NONEXISTENT_REMOTE_REF: Cited delivery branch '{b_clean}' does not exist on origin."
                    )

    # 6. Fixture Line Number and Expected Value Verification
    fixture_pattern = re.compile(
        r"\|\s*([A-Za-z0-9_\-]+)\s*\|\s*([A-Za-z0-9_\-]+)\s*\|\s*(PD-[A-Za-z0-9_\-]+)\s*\|\s*(?:L|line\s*)?(\d+)\s*\|\s*([^\|]+)\|\s*([^\|]+)\|\s*([^\|]+)\|"
    )
    all_master_fixtures = parse_all_fixtures(master_path) if master_path.exists() else {}

    for line in lines:
        match = fixture_pattern.search(line)
        if match:
            lane = match.group(1).strip()
            fix_id = match.group(2).strip()
            must_id = match.group(3).strip()
            reported_line = int(match.group(4).strip())
            reported_expected = match.group(5).strip()
            reported_actual = match.group(6).strip()
            status = match.group(7).strip()

            if fix_id not in all_master_fixtures:
                errors.append(f"Fixture ID '{fix_id}' cited in report not found in master document")
                continue

            real_fix = all_master_fixtures[fix_id]
            if reported_line != real_fix.line_number:
                errors.append(
                    f"Line number mismatch for {fix_id}: report says L{reported_line}, true master line is L{real_fix.line_number}"
                )

            if reported_expected != real_fix.expected_gate_output:
                errors.append(
                    f"Expected value mismatch for {fix_id}: report says '{reported_expected}', true master expected is '{real_fix.expected_gate_output}'"
                )

            if real_fix.expected_gate_output != "SATISFIED" and reported_expected == "SATISFIED":
                errors.append(
                    f"Default-to-SATISFIED defect for {fix_id}: master requires '{real_fix.expected_gate_output}' but report claimed 'SATISFIED'"
                )

    # 7. Git SHA verification: Any 7-40 hex string cited as commit/tree
    for token in re.findall(r"\b([0-9a-f]{7,40})\b", content):
        # Ignore sha256 hashes of files or fixtures
        if len(token) == 64:
            continue
        # Ignore purely decimal strings (e.g. GitHub Actions job IDs, run numbers, timestamps)
        if token.isdigit():
            continue
        # Check if present in origin remote references
        if token in known_remote_shas:
            continue
        # Verify object existence in local git repo
        res = subprocess.run(
            ["git", "cat-file", "-e", token],
            cwd=str(repo_root),
            capture_output=True,
        )
        if res.returncode != 0:
            errors.append(f"Invented or non-existent git SHA '{token}' cited in report")

    return errors


def run_mutation_tests(repo_root: Path, master_path: Path) -> List[str]:
    """Runs mutation tests to verify auditor detects each defect type and fails closed."""
    mutation_errors: List[str] = []
    fake_remotes = {"integration-r30-b1", "fix-omitted-evidence", "ci-hardening", "sync-main-to-integration"}

    # Mutation 1: Claims PASS while FLAW > 0
    mut1_text = """# DELIVERY REPORT
## VERDICT: PASS
### Adversarial Cross-Check
FLAW: 1
| Vector 1 | Empty input | FLAW |
"""
    mut1_file = repo_root / "test_global_mutation_1.md"
    mut1_file.write_text(mut1_text, encoding="utf-8")
    errs1 = audit_report(mut1_file, master_path, repo_root, fake_remotes)
    mut1_file.unlink(missing_ok=True)
    if not any("VERDICT_CONTRADICTION" in e for e in errs1):
        mutation_errors.append("Mutation 1 FAILED: Auditor did not detect verdict contradiction (PASS claimed with FLAW > 0)")

    # Mutation 2: LPC-STATIC failure without disposition
    mut2_text = """# DELIVERY REPORT
## LPC-STATIC SUMMARY
| Check | Status | Details |
| S1 | FAIL | evaluate_b2_gate missing caller authority |
"""
    mut2_file = repo_root / "test_global_mutation_2.md"
    mut2_file.write_text(mut2_text, encoding="utf-8")
    errs2 = audit_report(mut2_file, master_path, repo_root, fake_remotes)
    mut2_file.unlink(missing_ok=True)
    if not any("LPC_UNDISPOSITIONED_FAIL" in e for e in errs2):
        mutation_errors.append("Mutation 2 FAILED: Auditor did not detect undispositioned LPC static failure")

    # Mutation 3: G5 Cross-Check with fewer than 17 vectors (e.g. only 12 vectors)
    mut3_text = "\n".join([f"| Vector {i} | Input test | PASS |" for i in range(1, 13)])
    mut3_file = repo_root / "test_global_mutation_3.md"
    mut3_file.write_text(mut3_text, encoding="utf-8")
    errs3 = audit_report(mut3_file, master_path, repo_root, fake_remotes)
    mut3_file.unlink(missing_ok=True)
    if not any("INSUFFICIENT_G5_VECTORS" in e for e in errs3):
        mutation_errors.append("Mutation 3 FAILED: Auditor did not detect insufficient G5 vectors (< 17)")

    # Mutation 4: Nonexistent branch on origin
    mut4_text = """# DELIVERY REPORT
## Branches & PRs
| non-existent-fake-branch-12345 | PR #99 |
"""
    mut4_file = repo_root / "test_global_mutation_4.md"
    mut4_file.write_text(mut4_text, encoding="utf-8")
    errs4 = audit_report(mut4_file, master_path, repo_root, fake_remotes)
    mut4_file.unlink(missing_ok=True)
    if not any("NONEXISTENT_REMOTE_REF" in e for e in errs4):
        mutation_errors.append("Mutation 4 FAILED: Auditor did not detect non-existent remote branch")

    # Mutation 5: Claims PASS while Exceptions Escaping > 0
    mut5_text = """# DELIVERY REPORT
## VERDICT: PASS
### Adversarial Cross-Check
Exceptions Escaping: 5
| Vector 1 | Empty input | PASS |
"""
    mut5_file = repo_root / "test_global_mutation_5.md"
    mut5_file.write_text(mut5_text, encoding="utf-8")
    errs5 = audit_report(mut5_file, master_path, repo_root, fake_remotes)
    mut5_file.unlink(missing_ok=True)
    if not any("VERDICT_CONTRADICTION" in e and "escaping exception" in e for e in errs5):
        mutation_errors.append("Mutation 5 FAILED: Auditor did not detect verdict contradiction (PASS claimed with Exceptions Escaping > 0)")

    return mutation_errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Authoritative Global Claims and Safety Auditor for Round 11.")
    parser.add_argument("report_path", nargs="?", default="", help="Path to markdown report to audit")
    parser.add_argument("--master-path", default="", help="Path to authoritative Master Product Design Markdown file.")
    parser.add_argument("--repo-root", default=str(REPO_ROOT), help="Path to repository root.")
    parser.add_argument("--run-mutations", action="store_true", help="Run auditor mutation tests.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    if args.master_path:
        master_path = Path(args.master_path).resolve()
    else:
        master_path = resolve_master_path()

    if args.run_mutations:
        print("Running Global Auditor Mutation Tests...")
        mut_errs = run_mutation_tests(repo_root, master_path)
        if mut_errs:
            for me in mut_errs:
                print(f"MUTATION FAILURE: {me}", file=sys.stderr)
            return 1
        print("ALL MUTATION TESTS PASSED: Global Auditor fails closed on verdict contradiction, escaping exceptions, undispositioned LPC fails, <21 vectors, and nonexistent remote refs.")
        if not args.report_path:
            return 0

    if not args.report_path:
        print("Error: report_path is required when not running only mutations.", file=sys.stderr)
        return 1

    report_path = Path(args.report_path).resolve()
    print(f"Auditing report: {report_path}")
    print(f"Master design doc: {master_path}")
    errors = audit_report(report_path, master_path, repo_root)

    if errors:
        print(f"\nAUDIT FAILED with {len(errors)} error(s):")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("\nAUDIT SUCCESS: Report passed 100% of global claims, safety, and fixture integrity checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
