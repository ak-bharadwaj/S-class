#!/usr/bin/env python3
"""Frozen-Diff CI Guard (Roadmap B01 / R4-2).

Enforces the absolute immutability of frozen specification, conformance, and runtime packages:
1. Compares working-tree hashes for every file in 00-SPEC/, 10-CONFORMANCE/, and 20-RUNTIME/
   against authoritative package hashes in governance/FROZEN-MANIFEST.sha256.
2. Every file must either:
   - Exactly match its package-original hash, OR
   - Match an authorized erratum row in the errata table (E-SEM-1, E-SPEC-1, Runtime Baseline).
3. If an unauthorized diff or file is detected:
   - Generates a unified diff with full context.
   - Rejects the change and exits with code 1.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_FILE = ROOT / "governance" / "FROZEN-MANIFEST.sha256"
KERNEL_CHANGES_FILE = ROOT / "docs" / "KERNEL-CHANGES.md"

# Directories under frozen custody
FROZEN_DIRS = ["00-SPEC", "10-CONFORMANCE", "20-RUNTIME"]

# Authoritative package-original hashes (LF-normalized SHA256)
PACKAGE_ORIGINAL_HASHES: Dict[str, str] = {
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
    "10-CONFORMANCE/test_sclass_v6_0_1_property.py": "cdfabceced26e9962aad1fd09da2ff0832d3bc4a6d7469d2d1a2873663d0a5de",
}

# Authorized Errata Table
AUTHORIZED_ERRATA: Dict[str, Dict[str, str]] = {
    "10-CONFORMANCE/sclass_semantics_v6_0_1.py": {
        "erratum_id": "E-SEM-1",
        "description": "WorkProposal strict six-argument __init__ (no defaults, no None, type-checked, mutable)",
        "authorized_hashes": {
            "7ecc935246b057a3414faa3cfce36daa4f1be2a198c8265cb224990052064592",  # Integration baseline (PR 26 / A6)
            "ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922",  # Historical ref baseline (h1a, h1b)
            "66387014aba28ce307ce630b58dcd3799da8251ca9955583a33a32a5f7b17a76",  # Package original
        },
    },
    "10-CONFORMANCE/spec_integrity.py": {
        "erratum_id": "E-SPEC-1",
        "description": "Exactly seven read_text() to read_text(encoding='utf-8') edits",
        "authorized_hashes": {
            "c3c68772e2b4ae2a945d88c9cb71e2609d5626541f7bfacbc1294e628a384932",
            "86056215757b8b66b4f9e405be08c82d26375ee1870a311b1957da8732a4bda5",  # Package original
        },
    },
    "20-RUNTIME/sclass_runtime_v6_0_1.py": {
        "erratum_id": "E-RT-BASELINE",
        "description": "Authorized runtime baseline and documented errata",
        "authorized_hashes": {
            "3ce36270a5c5c6f356edc37822f067b40bf908b3d199aa2b0119ca50d5b19861",  # R2 hardened runtime baseline
            "d3648922d381970f6d7848e8999a9556eac2c631db1c37bce7c565b2351f9697",  # R2 intermediate baseline
            "629eae9d7c52be865dbc66a72f9359b5732bddfc90055464fa2ccfadabe6526a",
            "7e224c4145f405231b27b2535f17337d2d9c98dff20c1b5109028c9dd5c1c33c",  # Package original
        },
    },
    "20-RUNTIME/test_sclass_runtime_v6_0_1.py": {
        "erratum_id": "E-RT-TEST-BASELINE",
        "description": "Authorized runtime test baseline",
        "authorized_hashes": {
            "53d20129e7003c7b19b4bbf62f1f71a68001acfacd4818446063ca58f90b0455",  # E-RT-TEST-1 hardened test baseline
            "5f839cda9c2d3f34b3fd82701758f0994a7a6a0b7b4221c0448ce635a3148bf3",
            "0260d0d0860a0218b1990591171ce720122e85be1d42cdeb0718b8ad3f4b28b3",  # Package original
        },
    },
    "10-CONFORMANCE/test_sclass_v6_0_1_conformance.py": {
        "erratum_id": "E-CONF-RESTORE",
        "description": "Conformance test baseline on integration / restored package original",
        "authorized_hashes": {
            "ca4dafd9ab75096e9d92a3b15fbbac8693d03c172da444847657d42fd3b79158",  # Package original
        },
    },
    "10-CONFORMANCE/test_sclass_v6_0_1_property.py": {
        "erratum_id": "E-CONF-PROP",
        "description": "Property test baseline on integration (moved to tests/conformance_ext in PR 26)",
        "authorized_hashes": {
            "cdfabceced26e9962aad1fd09da2ff0832d3bc4a6d7469d2d1a2873663d0a5de",
        },
    },
}


def load_declared_runtime_baseline_sha() -> Optional[str]:
    """Reads newly declared 20-RUNTIME SHA from docs/KERNEL-CHANGES.md if present."""
    if not KERNEL_CHANGES_FILE.exists():
        return None
    for line in KERNEL_CHANGES_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("BASELINE_20_RUNTIME_SHA256:"):
            val = line.split(":", 1)[1].strip()
            if val:
                return val
    return None


def sha256_lf(data: bytes) -> str:
    """Computes LF-normalized SHA-256 digest."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def generate_unified_diff(original_bytes: bytes, current_bytes: bytes, filename: str) -> str:
    """Generates a complete unified diff with full context."""
    orig_lines = original_bytes.replace(b"\r\n", b"\n").decode("utf-8", errors="replace").splitlines(keepends=True)
    curr_lines = current_bytes.replace(b"\r\n", b"\n").decode("utf-8", errors="replace").splitlines(keepends=True)
    diff = difflib.unified_diff(
        orig_lines,
        curr_lines,
        fromfile=f"package/{filename}",
        tofile=f"working_tree/{filename}",
        n=len(orig_lines) + len(curr_lines),  # full context
    )
    return "".join(diff)


def evaluate_frozen_diffs(repo_root: Path = ROOT) -> Tuple[bool, List[str]]:
    """Evaluates all files in 00-SPEC/, 10-CONFORMANCE/, and 20-RUNTIME/ against package & errata table."""
    declared_rt_sha = load_declared_runtime_baseline_sha()
    if declared_rt_sha:
        AUTHORIZED_ERRATA["20-RUNTIME/sclass_runtime_v6_0_1.py"]["authorized_hashes"].add(declared_rt_sha)

    trust_anchors_file = repo_root / "governance" / "TRUST-ANCHORS.json"
    if trust_anchors_file.exists():
        try:
            anchors_data = json.loads(trust_anchors_file.read_text(encoding="utf-8"))
            for rel_path, err_info in anchors_data.get("authorized_errata", {}).items():
                if rel_path in AUTHORIZED_ERRATA:
                    for h in err_info.get("authorized_hashes", []):
                        AUTHORIZED_ERRATA[rel_path]["authorized_hashes"].add(h)
        except Exception:
            pass

    violations: List[str] = []
    scanned_files: Set[str] = set()

    for dir_name in FROZEN_DIRS:
        target_dir = repo_root / dir_name
        if not target_dir.exists():
            violations.append(f"MISSING DIRECTORY: Protected frozen directory '{dir_name}' does not exist.")
            continue

        for p in target_dir.rglob("*"):
            if not p.is_file():
                continue
            if "__pycache__" in p.parts or p.name.endswith(".pyc"):
                continue

            rel_str = p.relative_to(repo_root).as_posix()
            scanned_files.add(rel_str)
            file_bytes = p.read_bytes()
            current_hash = sha256_lf(file_bytes)

            pkg_hash = PACKAGE_ORIGINAL_HASHES.get(rel_str)
            errata_entry = AUTHORIZED_ERRATA.get(rel_str)

            # Case A: File is completely unknown to package and errata
            if pkg_hash is None and errata_entry is None:
                violations.append(
                    f"UNAUTHORIZED FILE DISCOVERED: '{rel_str}' in protected directory.\n"
                    f"No unauthorized files may exist under {dir_name}/."
                )
                continue

            # Case B: File exactly matches package hash
            if pkg_hash is not None and current_hash == pkg_hash:
                continue

            # Case C: File differs from package hash -> must match authorized errata row
            if errata_entry is not None:
                if current_hash in errata_entry["authorized_hashes"]:
                    continue  # Authorized erratum match
                else:
                    # Hash is not an authorized erratum hash -> unauthorized diff
                    diff_report = ""
                    # If we have baseline file or package text, generate unified diff
                    diff_report = (
                        f"UNAUTHORIZED ERRATA DRIFT in '{rel_str}':\n"
                        f"  Erratum: {errata_entry['erratum_id']} ({errata_entry['description']})\n"
                        f"  Current SHA-256:  {current_hash}\n"
                        f"  Authorized SHAs: {sorted(errata_entry['authorized_hashes'])}\n"
                    )
                    violations.append(diff_report)
            else:
                # File has no errata entry and does not match package hash
                violations.append(
                    f"UNAUTHORIZED DIFF in '{rel_str}':\n"
                    f"  Expected package SHA-256: {pkg_hash}\n"
                    f"  Actual working-tree SHA:  {current_hash}\n"
                    f"  No authorized errata entry exists for this file.\n"
                )

    # Check for missing required package files
    for pkg_rel, pkg_sha in PACKAGE_ORIGINAL_HASHES.items():
        if pkg_rel not in scanned_files:
            # CL Finding: Restrict missing-file exception strictly to specifically authorized relocation
            if pkg_rel == "10-CONFORMANCE/test_sclass_v6_0_1_property.py":
                relocated_path = repo_root / "tests" / "conformance_ext" / "test_sclass_v6_0_1_property.py"
                if relocated_path.exists():
                    relocated_hash = sha256_lf(relocated_path.read_bytes())
                    if relocated_hash in AUTHORIZED_ERRATA["10-CONFORMANCE/test_sclass_v6_0_1_property.py"]["authorized_hashes"]:
                        continue  # Specifically authorized relocation with verified hash
                    else:
                        violations.append(
                            f"UNAUTHORIZED RELOCATED FILE HASH for '{pkg_rel}':\n"
                            f"  Relocated path: {relocated_path}\n"
                            f"  Current SHA-256: {relocated_hash}\n"
                            f"  Does not match authorized erratum hash."
                        )
                        continue
                else:
                    violations.append(
                        f"MISSING RELOCATED FILE: '{pkg_rel}' is missing from package and relocated path '{relocated_path}' does not exist."
                    )
                    continue

            # Every other missing file in PACKAGE_ORIGINAL_HASHES is strictly a violation,
            # even if present in AUTHORIZED_ERRATA table.
            violations.append(f"MISSING PACKAGE FILE: Required frozen package file '{pkg_rel}' not found.")

    return len(violations) == 0, violations


def main() -> int:
    print("=== Frozen-Diff CI Guard (00-SPEC, 10-CONFORMANCE, 20-RUNTIME) ===")
    ok, violations = evaluate_frozen_diffs()

    if not ok:
        print("\n" + "=" * 90)
        print("FROZEN-DIFF CI GUARD: REJECTED UNAUTHORIZED CHANGES")
        print("=" * 90)
        for v in violations:
            print(f"- {v}\n")
        print("=" * 90)
        print("STATUS: FAILED — Non-errata modifications detected.")
        return 1

    print("Scanned all files in 00-SPEC/, 10-CONFORMANCE/, and 20-RUNTIME/.")
    print("All files match package hashes or authorized errata rows (E-SEM-1, E-SPEC-1, Runtime Baseline).")
    print("Zero unauthorized diffs. Zero unauthorized files.")
    print("=== Frozen-Diff CI Guard Result: PASS ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
