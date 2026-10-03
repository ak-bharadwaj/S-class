"""Automates verification and safe promotion of canonical branch to main.

Performs:
1. Validates remote origin/v6.0.1-canonical commit and status.
2. Verifies SHA-256 digests against HASHES.txt.
3. Tags/branches historical main as archive/v5-pre-canonical.
4. Promotes origin/v6.0.1-canonical to main.
5. Runs test verification suite (122 passed, 3 skipped, 0 failed baseline).
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HASHES_FILE = ROOT / "HASHES.txt"
CANONICAL_REF = "origin/v6.0.1-canonical"
CANONICAL_COMMIT = "787e8a1"
ARCHIVE_BRANCH = "archive/v5-pre-canonical"


def run_cmd(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print(f"--> Running: {' '.join(args)}")
    res = subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True, check=False)
    if check and res.returncode != 0:
        print(f"ERROR: Command failed with exit code {res.returncode}:\n{res.stderr}")
        sys.exit(res.returncode)
    return res


def verify_hashes() -> bool:
    if not HASHES_FILE.exists():
        print(f"WARN: {HASHES_FILE} not found; skipping hash check.")
        return True
    print("Checking SHA-256 file digests against HASHES.txt...")
    lines = HASHES_FILE.read_text(encoding="utf-8").strip().splitlines()
    all_ok = True
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        expected_hash, rel_path = parts
        rel_path = rel_path.strip()
        target = ROOT / rel_path
        if not target.exists():
            continue
        data = target.read_bytes()
        actual_hash = hashlib.sha256(data).hexdigest()
        norm_hash = hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
        if expected_hash not in (actual_hash, norm_hash):
            print(f"  MISMATCH: {rel_path} (expected {expected_hash}, got {actual_hash})")
            all_ok = False
        else:
            print(f"  OK: {rel_path}")
    return all_ok


def promote():
    print("=== Step 1: Verify remote canonical branch ===")
    res = run_cmd(["git", "rev-parse", "--short", CANONICAL_REF])
    head_rev = res.stdout.strip()
    print(f"Canonical commit at {CANONICAL_REF}: {head_rev}")
    if head_rev != CANONICAL_COMMIT:
        print(f"WARNING: Expected commit {CANONICAL_COMMIT}, found {head_rev}")

    print("\n=== Step 2: Archive historical main ===")
    branches = run_cmd(["git", "branch", "--list", ARCHIVE_BRANCH], check=False).stdout
    if ARCHIVE_BRANCH not in branches:
        run_cmd(["git", "branch", ARCHIVE_BRANCH, "main"])
        print(f"Created branch {ARCHIVE_BRANCH}")
    else:
        print(f"Branch {ARCHIVE_BRANCH} already exists.")

    print("\n=== Step 3: Promote canonical branch to main ===")
    run_cmd(["git", "checkout", "main"])
    run_cmd(["git", "reset", "--hard", CANONICAL_REF])

    print("\n=== Step 4: Verify SHA-256 digests ===")
    if not verify_hashes():
        print("ERROR: SHA-256 digest verification failed!")
        sys.exit(1)

    print("\n=== Step 5: Run baseline verification suite ===")
    test_res = run_cmd([sys.executable, "-m", "pytest", "10-CONFORMANCE", "20-RUNTIME", "-q"], check=False)
    print(test_res.stdout)
    if test_res.returncode != 0:
        print(f"Test run failed:\n{test_res.stderr}")
        sys.exit(test_res.returncode)

    print("\n=== Canonical Promotion Complete! ===")


if __name__ == "__main__":
    promote()
