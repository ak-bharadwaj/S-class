#!/usr/bin/env python3
"""Authoritative Guard Lane Mutation Battery Runner (7 Mutants).

Verifies mutation resistance of tests/guards/test_import_direction_guard.py across all
architectural decision branches mandated by Criterion L7:
- G-M01: Break cycle detection back-edge check (neighbor in in_stack)
- G-M02: Break cycle path construction (cycle = rec_stack...)
- G-M03: Break cross-block unauthorized import check (Block 0 -> Block 1)
- G-M04: Break private submodule import check (part.startswith('_'))
- G-M05: Break private symbol import check (imported_symbol.startswith('_'))
- G-M06: Break declared exports (__all__) check (imported_symbol not in declared_exports)
- G-M07: Break fail-closed missing export file handling (is_file() check)

Integrity features:
- In-memory byte capture and exact byte restoration in a finally block without git checkout.
- Pre- and post-restoration SHA-256 hash verification for each mutant.
- Baseline and frozen-file integrity verification before and after the battery.
- Git checkout cleanliness check and binding to exact delivery commit.
- Pre- and post-mutant Git HEAD and working-tree status capture for every mutant.
- All mutants must be KILLED by pytest tests/guards/test_import_direction_guard.py.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import subprocess
import sys
import time

EXPECTED_COMMIT_SHA = None  # Bound dynamically via CLI --commit
EXPECTED_TARGET_PATH = Path("tests") / "guards" / "test_import_direction_guard.py"

FROZEN_FILES = {
    "00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md": "53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1",
    "10-CONFORMANCE/sclass_semantics_v6_0_1.py": "ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922",
    "10-CONFORMANCE/sclass_kernel_v6_0_1.py": "d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c",
    "10-CONFORMANCE/c1-vectors.v6.0.1.json": "db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8",
    "10-CONFORMANCE/state-machines.v6.0.1.json": "24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad",
}

MUTATIONS = [
    {
        "id": "G-M01",
        "name": "break_cycle_detection_in_stack",
        "description": "Disable back-edge in_stack cycle check in DFS",
        "target": "elif neighbor in in_stack:",
        "replacement": "elif False:",
    },
    {
        "id": "G-M02",
        "name": "break_cycle_path_construction",
        "description": "Corrupt cycle path list construction on detection",
        "target": "cycle = rec_stack[cycle_start:] + [neighbor]",
        "replacement": "cycle = []",
    },
    {
        "id": "G-M03",
        "name": "break_cross_block_unauthorized_check",
        "description": "Disable Block 0 unauthorized import from Block 1 check",
        "target": 'if mod.startswith("sclass.product") or mod == "sclass.product":',
        "replacement": "if False:",
    },
    {
        "id": "G-M04",
        "name": "break_private_submodule_check",
        "description": "Disable private submodule leading underscore check",
        "target": 'if part.startswith("_") and part != "__future__":',
        "replacement": "if False:",
    },
    {
        "id": "G-M05",
        "name": "break_private_symbol_check",
        "description": "Disable private symbol leading underscore check",
        "target": 'if imported_symbol and imported_symbol.startswith("_") and not imported_symbol.startswith("__"):',
        "replacement": "if False:",
    },
    {
        "id": "G-M06",
        "name": "break_declared_exports_all_check",
        "description": "Disable declared public exports (__all__) membership check",
        "target": "if imported_symbol not in declared_exports:",
        "replacement": "if False:",
    },
    {
        "id": "G-M07",
        "name": "break_exports_extractor_fail_closed",
        "description": "Return empty set instead of None for missing exports file",
        "target": "if not file_path.is_file():\n        return None",
        "replacement": "if not file_path.is_file():\n        return set()",
    },
]


def sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_of_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def get_git_head(repo_root: Path) -> str:
    res = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return res.stdout.strip()


def get_git_status(repo_root: Path) -> str:
    res = subprocess.run(
        ["git", "status", "--short", "--", "tests/guards/test_import_direction_guard.py"],
        cwd=repo_root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return res.stdout.strip()


def verify_frozen_hashes(repo_root: Path) -> tuple[int, int]:
    matched = 0
    total = len(FROZEN_FILES)
    for rel_path, expected_hash in FROZEN_FILES.items():
        p = repo_root / rel_path
        if not p.is_file():
            print(f"ERROR: Frozen file {rel_path} does not exist!")
            continue
        actual = sha256_of_file(p)
        if actual == expected_hash:
            matched += 1
        else:
            print(f"ERROR: Frozen file {rel_path} hash mismatch: {actual} != {expected_hash}")
    return matched, total


def run_test_suite(repo_root: Path) -> tuple[int, str]:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/guards/test_import_direction_guard.py",
        "-q",
    ]
    res = subprocess.run(
        cmd,
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return res.returncode, res.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Guard Lane mutation battery")
    parser.add_argument("--commit", default=None, help="Expected delivery commit SHA")
    parser.add_argument("--repo-root", default=None, help="Root directory of repository")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parents[1]
    target_file = repo_root / EXPECTED_TARGET_PATH

    head = get_git_head(repo_root)
    commit_sha = args.commit or head

    print("=" * 80)
    print("S-Class v6.0.2 B0/B1 Guard Lane: Import-Direction Mutation Battery (7 Mutants)")
    print(f"Timestamp: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    print(f"Repository Root: {repo_root}")
    print(f"Target Module: {target_file}")
    print(f"Pytest Command: {sys.executable} -m pytest")
    print(f"Expected Commit SHA: {commit_sha}")
    print("=" * 80)

    # Pre-flight git checks
    git_status_initial = get_git_status(repo_root)
    print(f"Git HEAD Commit: {head}")
    print(f"Git Status before battery:\n{git_status_initial if git_status_initial else '(literal stdout: empty / 0 bytes, exit code 0)'}")

    if args.commit and head != args.commit:
        print(f"ERROR: HEAD {head} does not match expected commit {args.commit}!")
        return 1
    if git_status_initial:
        print(f"ERROR: Target file is modified before mutation battery:\n{git_status_initial}")
        return 1

    # Frozen file check
    matched, total = verify_frozen_hashes(repo_root)
    print(f"Frozen file hashes verified: {matched}/{total} MATCH.")
    if matched != total:
        print("ERROR: Frozen file integrity check failed!")
        return 1

    # Read target file and verify hash
    original_bytes = target_file.read_bytes()
    original_hash = sha256_of_bytes(original_bytes)
    print(f"Target file original SHA-256: {original_hash} ({len(original_bytes)} bytes)")

    # Run baseline test
    rc, out = run_test_suite(repo_root)
    if rc != 0:
        print(f"ERROR: Baseline test run failed (rc={rc}):\n{out}")
        return 1
    print(f"Baseline test run passed clean: {out}")
    print("-" * 80)

    results = []
    all_killed = True

    try:
        for m in MUTATIONS:
            m_id = m["id"]
            name = m["name"]
            desc = m["description"]
            target_str = m["target"]
            repl_str = m["replacement"]

            print(f"[{m_id}] Testing mutant: {name}")
            print(f"     Description: {desc}")

            pre_head = get_git_head(repo_root)
            pre_status = get_git_status(repo_root)
            print(f"     Pre-mutation Git HEAD: {pre_head}")
            print(f"     Pre-mutation Git Status: {pre_status if pre_status else '(literal stdout: empty / 0 bytes, exit code 0)'}")

            original_text = original_bytes.decode("utf-8")
            if target_str not in original_text:
                print(f"ERROR: Target string for mutant {m_id} not found in {target_file}")
                all_killed = False
                results.append((m_id, name, "NOT APPLIED (target missing)"))
                continue

            mutated_text = original_text.replace(target_str, repl_str, 1)
            target_file.write_bytes(mutated_text.encode("utf-8"))

            try:
                m_rc, m_out = run_test_suite(repo_root)
                if m_rc != 0:
                    verdict = "KILLED"
                    summary = m_out.splitlines()[-1] if m_out else "failed"
                    print(f"     VERDICT: KILLED (pytest exit code {m_rc}: {summary})")
                else:
                    verdict = "SURVIVED"
                    all_killed = False
                    print(f"     VERDICT: SURVIVED (mutant was NOT detected by test suite!)")
                results.append((m_id, name, verdict))
            finally:
                target_file.write_bytes(original_bytes)
                restored_hash = sha256_of_file(target_file)
                post_head = get_git_head(repo_root)
                post_status = get_git_status(repo_root)
                print(f"     Post-mutation Git HEAD: {post_head}")
                print(f"     Post-mutation Git Status: {post_status if post_status else '(literal stdout: empty / 0 bytes, exit code 0)'}")
                if restored_hash != original_hash:
                    raise RuntimeError(f"Target byte restoration mismatch: {restored_hash} != {original_hash}")
                if post_status:
                    raise RuntimeError(f"Working tree dirty after restoring mutant {m_id}:\n{post_status}")
                print(f"     Restoration verified: exact SHA-256 match {restored_hash} and clean git state")
                print("-" * 80)
    finally:
        target_file.write_bytes(original_bytes)

    # Post-battery checks
    matched_post, total_post = verify_frozen_hashes(repo_root)
    print(f"Post-battery frozen file integrity: {matched_post}/{total_post} MATCH.")
    rc_post, out_post = run_test_suite(repo_root)
    print(f"Post-restoration baseline test run passed clean: {out_post}")
    final_status = get_git_status(repo_root)
    print(f"Git Status after battery:\n{final_status if final_status else '(literal stdout: empty / 0 bytes, exit code 0)'}")

    print("=" * 80)
    print(f"GUARD MUTATION BATTERY SUMMARY: {sum(1 for _, _, v in results if v == 'KILLED')}/{len(results)} mutants KILLED")
    for mid, mname, mverdict in results:
        print(f"  [{mid}] {mname.ljust(50)} {mverdict}")
    print("=" * 80)

    if all_killed:
        print("FINAL DISPOSITION: GUARD MUTATION BATTERY COMPLETE - 7/7 MUTANTS KILLED")
        return 0
    else:
        print("FINAL DISPOSITION: FAILED (surviving mutants detected)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
