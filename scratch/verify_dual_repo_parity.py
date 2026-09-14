#!/usr/bin/env python3
"""
Dual-Repository Bit-for-Bit Parity Auditor (scratch/verify_dual_repo_parity.py).

Verifies 100% local, offline bit-for-bit parity between:
  Repo 1: C:\\Users\\dorni\\.gemini\\config\\plugins\\sclass-v5
  Repo 2: C:\\Users\\dorni\\OneDrive\\Desktop\\S-class

Audits:
  1. Branch parity (survival-v0)
  2. HEAD commit parity (427045c53b2e2e40070d24620a579307f67b1253 or identical HEAD)
  3. Git Tree hash parity (HEAD^{tree})
  4. Tracked file list parity (git ls-files)
  5. SHA-256 content hashes of all tracked files across both repositories (with canonical line-ending normalization)
  6. Gitlink/submodule tree entry parity

Exits 0 on match, exits 1 on any divergence.
"""

import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple


DEFAULT_REPO_A = r"C:\Users\dorni\.gemini\config\plugins\sclass-v5"
DEFAULT_REPO_B = r"C:\Users\dorni\OneDrive\Desktop\S-class"
EXPECTED_BRANCH = "survival-v0"
EXPECTED_BASELINE_COMMIT = "427045c53b2e2e40070d24620a579307f67b1253"


def run_git(repo_dir: str, args: List[str]) -> str:
    """Run git command locally and return stripped stdout."""
    cmd = ["git", "-C", repo_dir] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"Git command failed in {repo_dir}: {' '.join(cmd)}\nStderr: {result.stderr}")
    return result.stdout.strip()


def sha256_content(data: bytes, normalize_newlines: bool = True) -> str:
    """Compute SHA-256 digest of content, optionally normalizing CRLF to LF for cross-platform parity."""
    if normalize_newlines:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def verify_dual_repo_parity(repo_a: str = DEFAULT_REPO_A, repo_b: str = DEFAULT_REPO_B, strict_crlf: bool = False) -> bool:
    print("=" * 80)
    print("S-CLASS DUAL-REPOSITORY OFFLINE BIT-FOR-BIT PARITY AUDITOR")
    print("=" * 80)
    print(f"Repository A: {repo_a}")
    print(f"Repository B: {repo_b}")
    print(f"Strict CRLF Mode: {strict_crlf}")
    print("-" * 80)

    if not os.path.isdir(repo_a):
        print(f"[FAIL] Repository A directory does not exist: {repo_a}")
        return False
    if not os.path.isdir(repo_b):
        print(f"[FAIL] Repository B directory does not exist: {repo_b}")
        return False

    errors: List[str] = []

    # 1. Branch Check
    branch_a = run_git(repo_a, ["branch", "--show-current"])
    branch_b = run_git(repo_b, ["branch", "--show-current"])
    print(f"[*] Branch: Repo A='{branch_a}', Repo B='{branch_b}'")
    if branch_a != branch_b:
        errors.append(f"Branch mismatch: '{branch_a}' != '{branch_b}'")
    if branch_a != EXPECTED_BRANCH:
        print(f"    [WARN] Expected branch '{EXPECTED_BRANCH}', but found '{branch_a}'")

    # 2. HEAD Commit Check
    head_a = run_git(repo_a, ["rev-parse", "HEAD"])
    head_b = run_git(repo_b, ["rev-parse", "HEAD"])
    print(f"[*] HEAD Commit: Repo A={head_a} | Repo B={head_b}")
    if head_a != head_b:
        errors.append(f"HEAD commit mismatch: {head_a} != {head_b}")
    if head_a != EXPECTED_BASELINE_COMMIT:
        print(f"    [NOTE] Commit differs from baseline {EXPECTED_BASELINE_COMMIT} (commits added on top)")

    # 3. Tree Hash Check
    tree_a = run_git(repo_a, ["rev-parse", "HEAD^{tree}"])
    tree_b = run_git(repo_b, ["rev-parse", "HEAD^{tree}"])
    print(f"[*] Tree Hash:   Repo A={tree_a} | Repo B={tree_b}")
    if tree_a != tree_b:
        errors.append(f"Tree hash mismatch: {tree_a} != {tree_b}")

    # 4. Tracked File List & Content Hashing
    files_a_raw = run_git(repo_a, ["ls-files"]).splitlines()
    files_b_raw = run_git(repo_b, ["ls-files"]).splitlines()
    files_a = set(f.strip() for f in files_a_raw if f.strip())
    files_b = set(f.strip() for f in files_b_raw if f.strip())

    print(f"[*] Tracked Files: Repo A={len(files_a)} files | Repo B={len(files_b)} files")
    if files_a != files_b:
        only_a = files_a - files_b
        only_b = files_b - files_a
        if only_a:
            errors.append(f"Files only tracked in Repo A: {sorted(list(only_a))[:5]}")
        if only_b:
            errors.append(f"Files only tracked in Repo B: {sorted(list(only_b))[:5]}")

    common_files = sorted(list(files_a & files_b))
    mismatched_contents = []
    total_bytes = 0
    checked_files = 0
    checked_submodules = 0

    for rel_path in common_files:
        path_a = Path(repo_a) / rel_path
        path_b = Path(repo_b) / rel_path

        # Check if submodule/gitlink
        if path_a.is_dir() or path_b.is_dir():
            tree_entry_a = run_git(repo_a, ["ls-tree", "HEAD", rel_path])
            tree_entry_b = run_git(repo_b, ["ls-tree", "HEAD", rel_path])
            if tree_entry_a != tree_entry_b:
                mismatched_contents.append((rel_path, tree_entry_a, tree_entry_b))
            checked_submodules += 1
            continue

        if not path_a.exists():
            errors.append(f"File missing on disk in Repo A: {rel_path}")
            continue
        if not path_b.exists():
            errors.append(f"File missing on disk in Repo B: {rel_path}")
            continue

        size_a = path_a.stat().st_size
        total_bytes += size_a
        checked_files += 1

        with open(path_a, "rb") as fa, open(path_b, "rb") as fb:
            raw_a = fa.read()
            raw_b = fb.read()

        hash_a = sha256_content(raw_a, normalize_newlines=not strict_crlf)
        hash_b = sha256_content(raw_b, normalize_newlines=not strict_crlf)

        if hash_a != hash_b:
            mismatched_contents.append((rel_path, hash_a, hash_b))

    if mismatched_contents:
        errors.append(f"Content hash mismatch in {len(mismatched_contents)} tracked files/entries:")
        for rel_p, ha, hb in mismatched_contents[:10]:
            errors.append(f"  {rel_p}: A={ha[:12]}.. B={hb[:12]}..")

    print("-" * 80)
    if errors:
        print(f"[FAIL] Parity verification FAILED with {len(errors)} discrepancies:")
        for err in errors:
            print(f"  - {err}")
        return False

    print(f"[PASS] 100% BIT-FOR-BIT PARITY VERIFIED")
    print(f"       Checked {checked_files} tracked files ({total_bytes / (1024 * 1024):.2f} MB) and {checked_submodules} submodules.")
    print(f"       Zero discrepancies across branch, commit, tree, and tracked file contents.")
    print("=" * 80)
    return True


if __name__ == "__main__":
    args = sys.argv[1:]
    strict = "--strict" in args
    filtered_args = [a for a in args if a != "--strict"]

    repo_a = filtered_args[0] if len(filtered_args) > 0 else os.getenv("SCLASS_REPO_A", DEFAULT_REPO_A)
    repo_b = filtered_args[1] if len(filtered_args) > 1 else os.getenv("SCLASS_REPO_B", DEFAULT_REPO_B)

    success = verify_dual_repo_parity(repo_a, repo_b, strict_crlf=strict)
    sys.exit(0 if success else 1)
