"""Tests for the frozen files SHA-256 byte-integrity guard."""

from __future__ import annotations

import hashlib
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]

PACKAGE_SEMANTICS_HASH = "66387014aba28ce307ce630b58dcd3799da8251ca9955583a33a32a5f7b17a76"
ACCEPTED_ERRATA_SEMANTICS_HASH = "7ecc935246b057a3414faa3cfce36daa4f1be2a198c8265cb224990052064592"

PACKAGE_SPEC_INTEGRITY_HASH = "86056215757b8b66b4f9e405be08c82d26375ee1870a311b1957da8732a4bda5"
ACCEPTED_ERRATA_SPEC_INTEGRITY_HASH = "c3c68772e2b4ae2a945d88c9cb71e2609d5626541f7bfacbc1294e628a384932"

ACCEPTED_ERRATA_RUNTIME_HASH = "629eae9d7c52be865dbc66a72f9359b5732bddfc90055464fa2ccfadabe6526a"
ACCEPTED_ERRATA_RUNTIME_TEST_HASH = "5f839cda9c2d3f34b3fd82701758f0994a7a6a0b7b4221c0448ce635a3148bf3"

FROZEN_PACKAGE_HASHES = {
    "00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md": "53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1",
    "10-CONFORMANCE/sclass_kernel_v6_0_1.py": "d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c",
    "10-CONFORMANCE/c1-vectors.v6.0.1.json": "db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8",
    "10-CONFORMANCE/state-machines.v6.0.1.json": "24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad",
    "10-CONFORMANCE/test_sclass_v6_0_1_conformance.py": "ca4dafd9ab75096e9d92a3b15fbbac8693d03c172da444847657d42fd3b79158",
}

E_SEM_1_HUNK = """\n
    def __init__(
        self,
        proposal_id: str,
        node_id: str,
        request_content_digest: Digest,
        state_binding: StateBinding,
        context_digest: Digest,
        requested_effect: RequestedEffect,
    ) -> None:
        if not isinstance(proposal_id, str):
            raise TypeError(f"proposal_id must be str, got {type(proposal_id).__name__}")
        if not isinstance(node_id, str):
            raise TypeError(f"node_id must be str, got {type(node_id).__name__}")
        if not isinstance(request_content_digest, str):
            raise TypeError(f"request_content_digest must be Digest, got {type(request_content_digest).__name__}")
        if not isinstance(state_binding, StateBinding):
            raise TypeError(f"state_binding must be StateBinding, got {type(state_binding).__name__}")
        if not isinstance(context_digest, str):
            raise TypeError(f"context_digest must be Digest, got {type(context_digest).__name__}")
        if not isinstance(requested_effect, RequestedEffect):
            raise TypeError(f"requested_effect must be RequestedEffect, got {type(requested_effect).__name__}")
        self.proposal_id = proposal_id
        self.node_id = node_id
        self.request_content_digest = request_content_digest
        self.state_binding = state_binding
        self.context_digest = context_digest
        self.requested_effect = requested_effect"""


def sha256_lf(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


@pytest.mark.parametrize("rel_path, expected_hash", list(FROZEN_PACKAGE_HASHES.items()))
def test_frozen_file_sha256_exact(rel_path: str, expected_hash: str):
    file_path = ROOT / rel_path
    assert file_path.exists(), f"Protected frozen file is missing: {rel_path}"
    actual_hash = sha256_lf(file_path)
    assert actual_hash == expected_hash, (
        f"INTEGRITY VIOLATION: SHA-256 mismatch for frozen file {rel_path}.\n"
        f"Expected: {expected_hash}\n"
        f"Actual:   {actual_hash}"
    )


def test_semantics_file_errata_integrity():
    """Verify sclass_semantics_v6_0_1.py matches accepted errata hash and differs only by E-SEM-1."""
    sem_path = ROOT / "10-CONFORMANCE" / "sclass_semantics_v6_0_1.py"
    assert sem_path.exists(), "Semantics file is missing"

    # 1. Semantics file matches accepted errata hash
    actual_hash = sha256_lf(sem_path)
    assert actual_hash == ACCEPTED_ERRATA_SEMANTICS_HASH, (
        f"INTEGRITY VIOLATION: SHA-256 mismatch for sclass_semantics_v6_0_1.py.\n"
        f"Expected errata hash: {ACCEPTED_ERRATA_SEMANTICS_HASH}\n"
        f"Actual:                {actual_hash}"
    )

    # 2. Difference from original package is exactly the authorized E-SEM-1 hunk
    raw = sem_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert E_SEM_1_HUNK in raw, "Authorized E-SEM-1 hunk missing from sclass_semantics_v6_0_1.py"

    # 3. No additional semantics-file changes exist (reverting E-SEM-1 yields original package hash)
    reverted = raw.replace(E_SEM_1_HUNK, "", 1)
    reverted_hash = hashlib.sha256(reverted.encode("utf-8")).hexdigest()
    assert reverted_hash == PACKAGE_SEMANTICS_HASH, (
        f"INTEGRITY VIOLATION: Semantics file contains changes outside authorized E-SEM-1.\n"
        f"Expected package hash: {PACKAGE_SEMANTICS_HASH}\n"
        f"Actual reverted hash: {reverted_hash}"
    )


def test_spec_integrity_file_errata_integrity():
    """Verify spec_integrity.py matches accepted errata hash and differs only by E-SPEC-1."""
    spec_path = ROOT / "10-CONFORMANCE" / "spec_integrity.py"
    assert spec_path.exists(), "spec_integrity.py is missing"

    # 1. Matches accepted errata hash
    actual_hash = sha256_lf(spec_path)
    assert actual_hash == ACCEPTED_ERRATA_SPEC_INTEGRITY_HASH, (
        f"INTEGRITY VIOLATION: SHA-256 mismatch for spec_integrity.py.\n"
        f"Expected errata hash: {ACCEPTED_ERRATA_SPEC_INTEGRITY_HASH}\n"
        f"Actual:                {actual_hash}"
    )

    # 2. Contains exactly the authorized 7 E-SPEC-1 edits
    raw = spec_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    target = 'read_text(encoding="utf-8")'
    count = raw.count(target)
    assert count == 7, f"Expected exactly 7 E-SPEC-1 edits, found {count}"

    # 3. Reverting E-SPEC-1 yields original package hash
    reverted = raw.replace(target, "read_text()")
    reverted_hash = hashlib.sha256(reverted.encode("utf-8")).hexdigest()
    assert reverted_hash == PACKAGE_SPEC_INTEGRITY_HASH, (
        f"INTEGRITY VIOLATION: spec_integrity.py contains changes outside authorized E-SPEC-1.\n"
        f"Expected package hash: {PACKAGE_SPEC_INTEGRITY_HASH}\n"
        f"Actual reverted hash: {reverted_hash}"
    )


def test_runtime_baseline_errata_integrity():
    """Verify runtime baseline and test baseline hashes match accepted errata rows."""
    rt_path = ROOT / "20-RUNTIME" / "sclass_runtime_v6_0_1.py"
    rt_test_path = ROOT / "20-RUNTIME" / "test_sclass_runtime_v6_0_1.py"
    assert rt_path.exists(), "sclass_runtime_v6_0_1.py is missing"
    assert rt_test_path.exists(), "test_sclass_runtime_v6_0_1.py is missing"

    assert sha256_lf(rt_path) == ACCEPTED_ERRATA_RUNTIME_HASH, "Runtime baseline hash mismatch"
    assert sha256_lf(rt_test_path) == ACCEPTED_ERRATA_RUNTIME_TEST_HASH, "Runtime test baseline hash mismatch"


def test_frozen_directories_contain_no_untracked_files():
    """Verify 00-SPEC and 10-CONFORMANCE contain only package files and authorized errata."""
    spec_dir = ROOT / "00-SPEC"
    spec_files = {p.name for p in spec_dir.iterdir() if p.is_file()}
    assert spec_files == {"S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md"}, f"Unexpected files in 00-SPEC: {spec_files}"

    conf_dir = ROOT / "10-CONFORMANCE"
    conf_files = {p.name for p in conf_dir.iterdir() if p.is_file() and not p.name.endswith(".pyc")}
    expected_conf_files = {
        "c1-vectors.v6.0.1.json",
        "c1_independent.js",
        "coverage-map.v6.0.1.json",
        "sclass_kernel_v6_0_1.py",
        "sclass_semantics_v6_0_1.py",
        "spec_integrity.py",
        "state-machines.v6.0.1.json",
        "test_sclass_v6_0_1_conformance.py",
    }
    unexpected = conf_files - expected_conf_files
    assert not unexpected, (
        f"INTEGRITY VIOLATION: Unauthorized files found in 10-CONFORMANCE: {unexpected}. "
        f"Property and extension tests must reside in tests/conformance_ext/."
    )


def test_tampered_spec_integrity_fails_guard():
    """Attack simulation: any mutation to spec_integrity.py outside E-SPEC-1 must fail closed."""
    spec_path = ROOT / "10-CONFORMANCE" / "spec_integrity.py"
    raw = spec_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    tampered = raw + "\n# rogue comment\n"
    tampered_hash = hashlib.sha256(tampered.encode("utf-8")).hexdigest()
    assert tampered_hash != ACCEPTED_ERRATA_SPEC_INTEGRITY_HASH


def test_table1_accounts_for_all_monitored_files():
    """Verify Table 1 has zero unapproved DIFFERS entries (every file is MATCH or has an authorized errata row)."""
    table1_path = ROOT / "governance" / "BASELINE-HASHES.txt"
    assert table1_path.exists(), "BASELINE-HASHES.txt missing"
    content = table1_path.read_text(encoding="utf-8")

    in_table1 = False
    table1_rows = []
    for line in content.splitlines():
        if "TABLE 1:" in line:
            in_table1 = True
            continue
        if "TABLE 2:" in line:
            in_table1 = False
            break
        if in_table1 and "|" in line and not line.startswith("File") and not line.startswith("-"):
            table1_rows.append(line)

    unaccounted_differs = []
    for i, row in enumerate(table1_rows):
        parts = [p.strip() for p in row.split("|")]
        if len(parts) >= 4:
            f, pkg_h, repo_h, status = parts[0], parts[1], parts[2], parts[3]
            if not f.startswith("[") and status == "DIFFERS":
                # Check if next row is an accepted errata row for this file
                has_errata = False
                if i + 1 < len(table1_rows):
                    next_parts = [p.strip() for p in table1_rows[i + 1].split("|")]
                    if len(next_parts) >= 4 and next_parts[0].startswith("[Accepted") and next_parts[3] == "ACCEPTED_ERRATA":
                        has_errata = True
                if not has_errata:
                    unaccounted_differs.append(f)

    assert not unaccounted_differs, (
        f"INTEGRITY VIOLATION: Unaccounted DIFFERS rows in Table 1: {unaccounted_differs}. "
        f"Every differing file must have an authorized errata row."
    )
