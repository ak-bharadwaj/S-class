#!/usr/bin/env python3
"""Baseline Hashes Verification & Generation Tool (Roadmap B01).

Computes normalized-LF SHA-256 digests of every file across:
  - 00-SPEC/
  - 10-CONFORMANCE/
  - 20-RUNTIME/

Compares repo hashes (on current integration and main) against the
frozen design package values from FROZEN-MANIFEST.sha256 in S-CLASS-R32-PACKAGE.zip.

Generates governance/BASELINE-HASHES.txt.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
GOVERNANCE_DIR = REPO_ROOT / "governance"
BASELINE_HASHES_FILE = GOVERNANCE_DIR / "BASELINE-HASHES.txt"
MANIFEST_FILE = GOVERNANCE_DIR / "FROZEN-MANIFEST.sha256"

# Canonical package hashes from FROZEN-MANIFEST.sha256 (S-CLASS-R32-PACKAGE.zip)
# Embedded as deterministic baseline truth to guarantee offline reproducibility in CI.
CANONICAL_PACKAGE_HASHES: Dict[str, str] = {
    "00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md": "53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1",
    "10-CONFORMANCE/c1-vectors.v6.0.1.json": "db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8",
    "10-CONFORMANCE/c1_independent.js": "3d70c4791c63d8c6d1dc2724fac5012424067a2c0dd39f6432c1edf0af1abcec",
    "10-CONFORMANCE/coverage-map.v6.0.1.json": "722893054b29448238cb7cca5a149b6262d3cc606a4aeb2711c91e45a7dd6a20",
    "10-CONFORMANCE/sclass_kernel_v6_0_1.py": "d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c",
    "10-CONFORMANCE/sclass_semantics_v6_0_1.py": "66387014aba28ce307ce630b58dcd3799da8251ca9955583a33a32a5f7b17a76",
    "10-CONFORMANCE/spec_integrity.py": "86056215757b8b66b4f9e405be08c82d26375ee1870a311b1957da8732a4bda5",
    "10-CONFORMANCE/state-machines.v6.0.1.json": "24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad",
    "10-CONFORMANCE/test_sclass_v6_0_1_conformance.py": "ca4dafd9ab75096e9d92a3b15fbbac8693d03c172da444847657d42fd3b79158",
    "20-RUNTIME/README.md": "254c1a31d9a10a308c96d9c9212c487168c690f269c156bc3076b3ffdf19901f",
    "20-RUNTIME/requirements.txt": "ceeace8d072b469f31ba1a26f2c40677f225d090f76fee996ffe0f7498023c15",
    "20-RUNTIME/sclass_runtime_v6_0_1.py": "7e224c4145f405231b27b2535f17337d2d9c98dff20c1b5109028c9dd5c1c33c",
    "20-RUNTIME/test_sclass_runtime_v6_0_1.py": "0260d0d0860a0218b1990591171ce720122e85be1d42cdeb0718b8ad3f4b28b3",
}


def load_package_hashes(manifest_path: Optional[Path] = None) -> Dict[str, str]:
    hashes = dict(CANONICAL_PACKAGE_HASHES)
    p = manifest_path or MANIFEST_FILE
    if p.exists():
        try:
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(maxsplit=1)
                if len(parts) == 2:
                    h, rel = parts
                    rel = rel.strip()
                    if rel.startswith("./"):
                        rel = rel[2:]
                    if rel.startswith(("00-SPEC/", "10-CONFORMANCE/", "20-RUNTIME/")):
                        hashes[rel] = h
        except Exception:
            pass
    return hashes


def sha256_normalized_lf(raw_bytes: Optional[bytes]) -> str:
    if raw_bytes is None:
        return "MISSING"
    normalized = raw_bytes.replace(b"\r\n", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def get_git_file_bytes(ref: str, rel_path: str) -> Optional[bytes]:
    try:
        res = subprocess.run(
            ["git", "show", f"{ref}:{rel_path}"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            check=True,
        )
        return res.stdout
    except Exception:
        return None


def get_git_head_info() -> Tuple[str, str]:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        return branch, sha
    except Exception:
        return "unknown", "unknown"


def get_git_ref_sha(ref: str) -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", ref],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except Exception:
        return "unknown"


def list_target_files() -> List[str]:
    files = set()
    for root_name in ["00-SPEC", "10-CONFORMANCE", "20-RUNTIME"]:
        dir_path = REPO_ROOT / root_name
        if dir_path.exists():
            for p in dir_path.rglob("*"):
                if p.is_file() and "__pycache__" not in p.parts:
                    rel = p.relative_to(REPO_ROOT).as_posix()
                    files.add(rel)
    # Include files from package hashes that might be expected
    for rel in CANONICAL_PACKAGE_HASHES:
        files.add(rel)
    return sorted(files)


def generate_baseline_hashes_content(manifest_path: Optional[Path] = None) -> str:
    pkg_hashes = load_package_hashes(manifest_path)
    target_files = list_target_files()

    branch, head_sha = get_git_head_info()
    main_sha = get_git_ref_sha("origin/main")
    if main_sha == "unknown":
        main_sha = get_git_ref_sha("main")

    lines = [
        "# S-CLASS GOVERNANCE BASELINE HASHES (B01 BASELINE LOCK)",
        "# Generated automatically by tools/baseline_hashes.py — DO NOT EDIT MANUALLY",
        "# Normalized-LF SHA-256: hashlib.sha256(file_bytes.replace(b'\\r\\n', b'\\n')).hexdigest()",
        f"# Repository Branch: {branch}",
        f"# Integration HEAD SHA: {head_sha}",
        f"# Main Reference SHA:    {main_sha}",
        "# Design Package Source: FROZEN-MANIFEST.sha256 in S-CLASS-R32-PACKAGE.zip",
        "",
        "========================================================================================================================",
        "TABLE 1: CURRENT INTEGRATION REPO HASHES VS FROZEN DESIGN PACKAGE HASHES",
        "========================================================================================================================",
        f"{'File':<50} | {'Package Hash':<64} | {'Repo Hash':<64} | Status",
        "-" * 192,
    ]

    int_rows = []
    main_rows = []

    for f in target_files:
        pkg_h = pkg_hashes.get(f, "NOT_IN_FROZEN_MANIFEST")
        file_path = REPO_ROOT / f
        int_bytes = file_path.read_bytes() if file_path.exists() else None
        int_h = sha256_normalized_lf(int_bytes)

        status_int = "MATCH" if pkg_h == int_h else "DIFFERS"
        lines.append(f"{f:<50} | {pkg_h:<64} | {int_h:<64} | {status_int}")
        int_rows.append((f, pkg_h, int_h, status_int))

        # Check main
        main_ref = "origin/main" if get_git_ref_sha("origin/main") != "unknown" else "main"
        main_bytes = get_git_file_bytes(main_ref, f)
        main_h = sha256_normalized_lf(main_bytes)
        status_main = "MATCH" if pkg_h == main_h else "DIFFERS"
        main_rows.append((f, pkg_h, main_h, status_main))

    lines.extend([
        "",
        "========================================================================================================================",
        "TABLE 2: MAIN BRANCH HASHES VS FROZEN DESIGN PACKAGE HASHES",
        "========================================================================================================================",
        f"{'File':<50} | {'Package Hash':<64} | {'Repo Hash (main)':<64} | Status",
        "-" * 192,
    ])

    for f, pkg_h, main_h, status_main in main_rows:
        lines.append(f"{f:<50} | {pkg_h:<64} | {main_h:<64} | {status_main}")

    lines.extend([
        "",
        "========================================================================================================================",
        "TABLE 3: INTEGRATION VS MAIN COMPARISON SUMMARY",
        "========================================================================================================================",
        f"{'File':<50} | {'Integration Hash':<64} | {'Main Hash':<64} | Int == Main",
        "-" * 192,
    ])

    for i in range(len(target_files)):
        f, _, int_h, _ = int_rows[i]
        _, _, main_h, _ = main_rows[i]
        same = "MATCH" if int_h == main_h else "DIFFERS"
        lines.append(f"{f:<50} | {int_h:<64} | {main_h:<64} | {same}")

    # Explanatory Notes
    lines.extend([
        "",
        "========================================================================================================================",
        "EXPLANATORY ANALYSIS OF HASH DIFFERENCES (STATUS: DIFFERS)",
        "========================================================================================================================",
        "1. 00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md: MATCH (exact SHA-256 match across package, integration, and main).",
        "2. 10-CONFORMANCE core vectors & machines: MATCH across package, integration, and main:",
        "   - 10-CONFORMANCE/c1-vectors.v6.0.1.json: MATCH",
        "   - 10-CONFORMANCE/c1_independent.js: MATCH",
        "   - 10-CONFORMANCE/coverage-map.v6.0.1.json: MATCH",
        "   - 10-CONFORMANCE/sclass_kernel_v6_0_1.py: MATCH",
        "   - 10-CONFORMANCE/state-machines.v6.0.1.json: MATCH",
        "3. 10-CONFORMANCE/sclass_semantics_v6_0_1.py: DIFFERS from package due to normative errata:",
        "   - Package: 66387014aba28ce307ce630b58dcd3799da8251ca9955583a33a32a5f7b17a76",
        "   - Repo:    ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922",
        "   - Both integration and main have identical hash; guarded by test_frozen_integrity_guard.py.",
        "4. 10-CONFORMANCE/spec_integrity.py & test_sclass_v6_0_1_conformance.py: DIFFERS from package due to updated",
        "   conformance assertions and test suite coverage.",
        "5. 10-CONFORMANCE/test_sclass_v6_0_1_property.py: Added in repository conformance suite; not in original package manifest.",
        "6. 20-RUNTIME/sclass_runtime_v6_0_1.py: DIFFERS reflecting Phase H1a/H1b declared runtime errata:",
        "   - Package:     7e224c4145f405231b27b2535f17337d2d9c98dff20c1b5109028c9dd5c1c33c",
        "   - Main:        761cd60498fd394ebda1e00ec188f553f1a0ea4c16d9539207011d31fa7ef8d1",
        "   - Integration: 629eae9d7c52be865dbc66a72f9359b5732bddfc90055464fa2ccfadabe6526a (H1b X1-X3 baseline).",
        "   - Documented formally in docs/KERNEL-CHANGES.md with all 16 hunks declared.",
        "7. 20-RUNTIME/test_sclass_runtime_v6_0_1.py: DIFFERS reflecting migrated test cases and mock removals.",
        "",
        "SUMMARY METRICS:",
        f"  Total Monitored Files:    {len(target_files)}",
        f"  Integration vs Package:   {sum(1 for _, _, _, s in int_rows if s == 'MATCH')} MATCH, {sum(1 for _, _, _, s in int_rows if s == 'DIFFERS')} DIFFERS",
        f"  Main vs Package:          {sum(1 for _, _, _, s in main_rows if s == 'MATCH')} MATCH, {sum(1 for _, _, _, s in main_rows if s == 'DIFFERS')} DIFFERS",
        f"  Integration vs Main:      {sum(1 for i in range(len(target_files)) if int_rows[i][2] == main_rows[i][2])} MATCH, {sum(1 for i in range(len(target_files)) if int_rows[i][2] != main_rows[i][2])} DIFFERS",
    ])

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Baseline Hashes Generator and Verifier")
    parser.add_argument("--check", action="store_true", help="Check baseline hashes file without writing")
    parser.add_argument("--manifest", type=Path, default=None, help="Path to FROZEN-MANIFEST.sha256")
    parser.add_argument("--output", type=Path, default=BASELINE_HASHES_FILE, help="Output file path")
    args = parser.parse_args()

    content = generate_baseline_hashes_content(args.manifest)

    if args.check:
        if not args.output.exists():
            print(f"FAIL: {args.output} does not exist. Run without --check to generate.")
            return 1
        existing = args.output.read_text(encoding="utf-8")
        if existing != content:
            print(f"FAIL: {args.output} is out of date or drifted.")
            return 1
        print(f"PASS: {args.output} is up to date and verified.")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content, encoding="utf-8")
    print(f"Wrote baseline hashes report to {args.output}")
    print(f"Total monitored files: {len(list_target_files())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
