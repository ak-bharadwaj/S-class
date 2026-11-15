"""Tests for the frozen files SHA-256 byte-integrity guard."""

from __future__ import annotations

import hashlib
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]

PACKAGE_SEMANTICS_HASH = "66387014aba28ce307ce630b58dcd3799da8251ca9955583a33a32a5f7b17a76"
ACCEPTED_ERRATA_SEMANTICS_HASH = "7ecc935246b057a3414faa3cfce36daa4f1be2a198c8265cb224990052064592"

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
