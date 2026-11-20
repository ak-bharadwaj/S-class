"""Tests for the frozen files SHA-256 byte-integrity guard."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import pytest

from tools.baseline_hashes import (
    CANONICAL_PACKAGE_HASHES,
    CLASSIFICATION_EVIDENCE_FILE,
    RAW_EVIDENCE_DIR,
    validate_manifest_file,
    load_and_validate_branch_classification_evidence,
    generate_baseline_hashes_content,
)

ROOT = Path(__file__).resolve().parents[2]
BASELINE_REPORT = ROOT / "governance" / "BASELINE-HASHES.txt"
FROZEN_MANIFEST = ROOT / "governance" / "FROZEN-MANIFEST.sha256"

PACKAGE_SEMANTICS_HASH = "66387014aba28ce307ce630b58dcd3799da8251ca9955583a33a32a5f7b17a76"
ACCEPTED_ERRATA_SEMANTICS_HASH = "7ecc935246b057a3414faa3cfce36daa4f1be2a198c8265cb224990052064592"

PACKAGE_SPEC_INTEGRITY_HASH = "86056215757b8b66b4f9e405be08c82d26375ee1870a311b1957da8732a4bda5"
ACCEPTED_ERRATA_SPEC_INTEGRITY_HASH = "c3c68772e2b4ae2a945d88c9cb71e2609d5626541f7bfacbc1294e628a384932"

ACCEPTED_ERRATA_RUNTIME_HASH = "c43845feb5e7842ebc81100ed3b7f1be8d4143fa3187978673c37ce614fdefff"
ACCEPTED_ERRATA_RUNTIME_HASHES = {
    "629eae9d7c52be865dbc66a72f9359b5732bddfc90055464fa2ccfadabe6526a",  # H1b baseline
    "d3648922d381970f6d7848e8999a9556eac2c631db1c37bce7c565b2351f9697",  # Block 1 R2 hardened runtime
    "d021c973bef3cdf9f2221f6e603622f733f95e2fb52cfb6b0a74a841baf9d50d",  # R2 intermediate
    "3ce36270a5c5c6f356edc37822f067b40bf908b3d199aa2b0119ca50d5b19861",  # Block 1 R2 final hardened runtime
    "70aef358edef702ab8240f57d7d4dfd8d52f944c37f8864a236e5d6a8828eeb8",  # Block 1 R2 hardened runtime with L-1 fixes
    "ac45e7fd30130266b154661b9d91a82726d6d99f2bf08c5ae23e3ddc5d9e218e",  # Block 1 F-1/F-2 intermediate
    "1cdbe979116ab982d92f5594236614ab0c0c98e2cee3c8d55b4c2fce993b5f6e",  # Block 1 F-1/F-2 intermediate 2
    "30cecbb0827b0eaa63ffdd426929029bf709266bc4ac47d5580024ab0cfc4556",  # Block 1 F-1/F-2 intermediate 3
    "ef82635a31198eaf3b6a171d58b68bfec3066b754c5c1aa95a37b24b0efc7718",  # Block 1 F-1/F-2 fail-closed boundary and isolated assessor
    "c43845feb5e7842ebc81100ed3b7f1be8d4143fa3187978673c37ce614fdefff",  # Block 1 F-1/F-2 fail-closed cleanup and group kill
}
ACCEPTED_ERRATA_RUNTIME_TEST_HASH = "53d20129e7003c7b19b4bbf62f1f71a68001acfacd4818446063ca58f90b0455"
ACCEPTED_ERRATA_RUNTIME_TEST_HASHES = {
    "5f839cda9c2d3f34b3fd82701758f0994a7a6a0b7b4221c0448ce635a3148bf3",  # H1b test baseline
    "53d20129e7003c7b19b4bbf62f1f71a68001acfacd4818446063ca58f90b0455",  # E-RT-TEST-1
}

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

    assert sha256_lf(rt_path) in ACCEPTED_ERRATA_RUNTIME_HASHES, f"Runtime baseline hash mismatch: {sha256_lf(rt_path)}"
    assert sha256_lf(rt_test_path) in ACCEPTED_ERRATA_RUNTIME_TEST_HASHES, "Runtime test baseline hash mismatch"


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



# =============================================================================
# BLOCKER F-3: Baseline Identity & Historical Consistency Suite (7 Mandatory Tests)
# =============================================================================

def test_f3_historical_evidence_remains_verifiable():
    """F-3.1: Historical integration evidence remains verifiable against HISTORICAL_INTEGRATION_SHA."""
    import tools.baseline_hashes as bh
    assert hasattr(bh, "HISTORICAL_INTEGRATION_SHA")
    assert bh.HISTORICAL_INTEGRATION_SHA == "4af5aba9d9898bb10dd2e859cc6d8a4572fac157"
    validated = bh.load_and_validate_branch_classification_evidence()
    assert "integration" in validated
    assert validated["integration"]["ref_sha"] == bh.HISTORICAL_INTEGRATION_SHA


def test_f3_current_candidate_tied_to_exact_tested_sha():
    """F-3.2: Current integration candidate is dynamically tied to the exact tested commit SHA."""
    import tools.baseline_hashes as bh
    cand_sha = bh.get_current_candidate_sha()
    assert len(cand_sha) == 40
    assert cand_sha != "unknown"
    proc = subprocess.run([bh.GIT_BIN, "rev-parse", "HEAD"], cwd=str(ROOT), capture_output=True, text=True, check=True)
    assert cand_sha == proc.stdout.strip()


def test_f3_tampered_historical_sha_detected(tmp_path: Path):
    """F-3.3: A tampered historical integration SHA in classification evidence is detected."""
    import tools.baseline_hashes as bh
    data = json.loads(CLASSIFICATION_EVIDENCE_FILE.read_text(encoding="utf-8"))
    data["metrics_by_ref"]["integration"]["ref_sha"] = "0000000000000000000000000000000000000000"
    tampered_file = tmp_path / "tampered_class.json"
    tampered_file.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="Tampered or mismatched historical commit SHA"):
        bh.load_and_validate_branch_classification_evidence(tampered_file)


def test_f3_candidate_sha_mismatch_detected():
    """F-3.4: Candidate SHA mismatch between tested git HEAD and expected pin is detected."""
    import tools.baseline_hashes as bh
    with pytest.raises(ValueError, match="Candidate SHA mismatch"):
        bh.validate_candidate_sha("ffffffffffffffffffffffffffffffffffffffff")


def test_f3_missing_required_historical_evidence_detected(tmp_path: Path):
    """F-3.5: Missing required historical evidence for 'integration' ref is detected."""
    import tools.baseline_hashes as bh
    data = json.loads(CLASSIFICATION_EVIDENCE_FILE.read_text(encoding="utf-8"))
    del data["metrics_by_ref"]["integration"]
    tampered_file = tmp_path / "missing_int.json"
    tampered_file.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="Missing required ref 'integration'"):
        bh.load_and_validate_branch_classification_evidence(tampered_file)


def test_f3_current_candidate_identity_not_substituted_with_historical_sha():
    """F-3.6: Current candidate identity is not silently substituted with historical SHA."""
    import tools.baseline_hashes as bh
    with pytest.raises(ValueError, match="Candidate SHA cannot be substituted with immutable historical"):
        bh.validate_candidate_sha(bh.HISTORICAL_INTEGRATION_SHA)


def test_f3_generated_reports_correctly_label_historical_and_dynamic_references():
    """F-3.7: Generated reports correctly label historical baseline vs dynamic integration candidate."""
    import tools.baseline_hashes as bh
    content = bh.generate_baseline_hashes_content()
    assert f"historical baseline: {bh.HISTORICAL_INTEGRATION_SHA}" in content
    assert "dynamic at head under test" in content
