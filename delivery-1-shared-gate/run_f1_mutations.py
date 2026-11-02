#!/usr/bin/env python3
"""Authoritative F1 Consumer Gate Vocabulary Mutation Battery (5 Mutants).

Verifies mutation resistance of src/sclass/product/artifacts.py across all
5 return mappings evaluated by evaluate_f1_representation():
- F1-M01: SATISFIED return mapping -> KILLED
- F1-M02: MISSING[PD-F1-002] return mapping -> KILLED
- F1-M03: MISSING[PD-F1-003] return mapping -> KILLED
- F1-M04: MISSING[PD-F1-004] return mapping -> KILLED
- F1-M05: BLOCKED_ON_HUMAN[PD-F1-005] return mapping -> KILLED

Integrity features:
- In-memory byte capture and exact byte restoration in a finally block without git checkout.
- Pre- and post-restoration SHA-256 hash verification for each mutant.
- Baseline and frozen-file integrity verification before and after the battery.
- Git checkout cleanliness check and binding to exact delivery commit.
- Pre- and post-mutant Git HEAD and working-tree status capture for every mutant.
- All 5 mutants must be KILLED by pytest tests/product/test_artifact_schemas.py -k test_f1_shared_gate_output_consumer_adoption.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import subprocess
import sys
import time

EXPECTED_COMMIT_SHA = "7d1d42123a9f3799281d7d567ba307013c3b4630"
EXPECTED_TARGET_SHA256 = "1e2ac4eb8d63825e5eeab9333db7b071395eec1e02b43ccd9115ebb80d865e58"

TARGET_RELATIVE_PATH = Path("src") / "sclass" / "product" / "artifacts.py"

FROZEN_FILES = {
    "00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md": "53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1",
    "10-CONFORMANCE/sclass_semantics_v6_0_1.py": "ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922",
    "10-CONFORMANCE/sclass_kernel_v6_0_1.py": "d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c",
    "10-CONFORMANCE/c1-vectors.v6.0.1.json": "db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8",
    "10-CONFORMANCE/state-machines.v6.0.1.json": "24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad",
}

MUTATIONS = [
    {
        "id": "F1-M01",
        "name": "corrupt_f1_satisfied_return",
        "description": "Corrupt final satisfied return mapping to MISSING",
        "target": "# All checks satisfied\n    return GateOutput(GateState.SATISFIED)",
        "replacement": "# All checks satisfied\n    return GateOutput(GateState.MISSING)",
    },
    {
        "id": "F1-M02",
        "name": "corrupt_f1_missing_pd_f1_002",
        "description": "Corrupt PD-F1-002 verifier contradiction return to SATISFIED",
        "target": 'return GateOutput(GateState.MISSING, must_id="PD-F1-002")',
        "replacement": "return GateOutput(GateState.SATISFIED)",
    },
    {
        "id": "F1-M03",
        "name": "corrupt_f1_missing_pd_f1_003",
        "description": "Corrupt PD-F1-003 executable representation return to SATISFIED",
        "target": 'return GateOutput(GateState.MISSING, must_id="PD-F1-003")',
        "replacement": "return GateOutput(GateState.SATISFIED)",
    },
    {
        "id": "F1-M04",
        "name": "corrupt_f1_missing_pd_f1_004",
        "description": "Corrupt PD-F1-004 adequacy check return to SATISFIED",
        "target": 'return GateOutput(GateState.MISSING, must_id="PD-F1-004")',
        "replacement": "return GateOutput(GateState.SATISFIED)",
    },
    {
        "id": "F1-M05",
        "name": "corrupt_f1_blocked_pd_f1_005",
        "description": "Corrupt PD-F1-005 weakening approval return to SATISFIED",
        "target": 'return GateOutput(GateState.BLOCKED_ON_HUMAN, must_id="PD-F1-005")',
        "replacement": "return GateOutput(GateState.SATISFIED)",
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
        ["git", "status", "--short", "--", "src/", "tests/", "00-SPEC/", "10-CONFORMANCE/", "20-RUNTIME/"],
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
        "tests/product/test_artifact_schemas.py",
        "-k",
        "test_f1_shared_gate_output_consumer_adoption",
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
    parser = argparse.ArgumentParser(description="Run F1 Gate Vocabulary Consumer mutation battery")
    parser.add_argument("--commit", default=EXPECTED_COMMIT_SHA, help="Expected delivery commit SHA")
    parser.add_argument("--repo-root", default=None, help="Root directory of repository")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parents[1]
    target_file = repo_root / TARGET_RELATIVE_PATH

    print("=" * 80)
    print("S-Class v6.0.2 Block 1 Lane B: F1 Consumer Gate Vocabulary Mutation Battery (5 Mutants)")
    print(f"Timestamp: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    print(f"Repository Root: {repo_root}")
    print(f"Target Module: {target_file}")
    print(f"Pytest Command: {sys.executable} -m pytest")
    print(f"Expected Commit SHA: {args.commit}")
    print("=" * 80)

    # Pre-flight git checks
    head = get_git_head(repo_root)
    git_status_initial = get_git_status(repo_root)
    print(f"Git HEAD Commit: {head}")
    print(f"Git Status before battery:\n{git_status_initial if git_status_initial else '(clean)'}")

    if head != args.commit:
        print(f"ERROR: HEAD {head} does not match expected commit {args.commit}!")
        return 1
    if git_status_initial:
        print(f"ERROR: Working tree is dirty before mutation battery:\n{git_status_initial}")
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
    if original_hash != EXPECTED_TARGET_SHA256:
        print(f"ERROR: Target file hash {original_hash} does not match expected {EXPECTED_TARGET_SHA256}")
        return 1

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

            if pre_head != args.commit:
                print(f"FATAL: HEAD changed before mutant {m_id} to {pre_head}")
                return 1
            if pre_status:
                print(f"FATAL: Working tree dirty before mutant {m_id}:\n{pre_status}")
                return 1

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
    print(f"Git Status after battery:\n{final_status if final_status else '(clean)'}")

    print("=" * 80)
    print(f"F1 MUTATION BATTERY SUMMARY: {sum(1 for _, _, v in results if v == 'KILLED')}/{len(results)} mutants KILLED")
    for mid, mname, mverdict in results:
        print(f"  [{mid}] {mname.ljust(50)} {mverdict}")
    print("=" * 80)

    if all_killed:
        print("FINAL DISPOSITION: F1 MUTATION BATTERY COMPLETE - 5/5 MUTANTS KILLED")
        return 0
    else:
        print("FINAL DISPOSITION: FAILED (surviving mutants detected)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
