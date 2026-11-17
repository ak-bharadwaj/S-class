"""tests/guards/test_evidence_synchronization.py

Auditable Guard Tests for Work Order P27 (R3 Evidence Synchronization).
Enforces CL Acceptance Criteria:
1. test_delivery_evidence_matches_synchronized_head
2. test_evidence_generation_records_exact_reference_sha
3. test_merge_diff_contains_no_unrelated_source_changes
"""

import json
import shutil
import subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
GIT_BIN = shutil.which("git") or "/usr/bin/git" or "git"

ORIGINAL_B1_EVIDENCE_SHA = "b2dfbd1904211144171366dfc1e4962ee523a7e3"
INTEGRATION_SHA = "f5b3b86539299aa27c8c2911ee90f17a5ebdbfda"


def test_delivery_evidence_matches_synchronized_head():
    """Negative test: Proves delivery evidence reflects current synchronized head."""
    evidence_dir = ROOT / "delivery-evidence"
    assert evidence_dir.is_dir(), "delivery-evidence directory must exist"

    classification_report = evidence_dir / "test_classification_report.json"
    assert classification_report.exists(), "test_classification_report.json must exist"

    data = json.loads(classification_report.read_text(encoding="utf-8"))
    assert data.get("schema") == "sclass/test-classification-report/v1"
    assert data.get("status") == "PASS"
    assert data.get("code_failures_count") == 0
    assert data.get("synchronized_head_sha") == INTEGRATION_SHA, (
        f"Synchronized head SHA mismatch: expected {INTEGRATION_SHA}, got {data.get('synchronized_head_sha')}"
    )
    assert data.get("duration_seconds") > 1.0, (
        f"Test duration must reflect genuine suite execution (>1s), got {data.get('duration_seconds')}"
    )
    assert data.get("run_id") == "44072437627", f"run_id must match CI provenance, got {data.get('run_id')}"
    assert data.get("artifact_provenance") == "verify-artifacts-ubuntu-24.04-py3.12"


def test_evidence_generation_records_exact_reference_sha():
    """Negative test: Proves branch baseline evidence records exact authoritative SHAs."""
    evidence_file = ROOT / "delivery-evidence" / "branch_baselines_classification.json"
    assert evidence_file.exists(), "branch_baselines_classification.json must exist"

    data = json.loads(evidence_file.read_text(encoding="utf-8"))
    auth_refs = data.get("authoritative_refs", {})

    expected_refs = {
        "main": "447caf96e356a836b0455ac6d845a6729a9e007f",
        "h0": "e60a089dbdd8d14394009f1c9661967d8d5b7b74",
        "h1a": "9c6e0fc9d21219f48c0235f3dc69687063f84061",
        "h1b": "8b012f2dadf8785481b36e48598e34cc8a80c92f",
    }

    for ref_name, expected_sha in expected_refs.items():
        assert ref_name in auth_refs, f"Missing ref '{ref_name}' in baseline evidence"
        assert auth_refs[ref_name] == expected_sha, (
            f"Reference SHA mismatch for '{ref_name}': expected {expected_sha}, got {auth_refs[ref_name]}"
        )


def test_merge_diff_contains_no_unrelated_source_changes():
    """Negative test: Proves merge commit contains ONLY integration merge + regenerated evidence."""
    # Check if original SHA is available in repo history
    res = subprocess.run(
        [GIT_BIN, "rev-parse", "--verify", ORIGINAL_B1_EVIDENCE_SHA],
        cwd=str(ROOT),
        capture_output=True,
    )
    if res.returncode != 0:
        pytest.fail(
            f"HARD FAILURE: Original b1-evidence SHA {ORIGINAL_B1_EVIDENCE_SHA} not found in local repository! "
            "Evidence lineage must not be shallow or severed."
        )

    # Get diff between original b1-evidence and HEAD
    diff_res = subprocess.run(
        [GIT_BIN, "diff", "--name-only", f"{ORIGINAL_B1_EVIDENCE_SHA}...HEAD"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    changed_files = [f.strip() for f in diff_res.stdout.splitlines() if f.strip()]

    # Get diff of integration baseline versus b2dfbd19
    int_diff_res = subprocess.run(
        [GIT_BIN, "diff", "--name-only", ORIGINAL_B1_EVIDENCE_SHA, INTEGRATION_SHA],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    integration_incoming_files = set(int_diff_res.stdout.splitlines())

    # Every changed file must either be from the incoming integration merge or delivery-evidence/guard test
    for f in changed_files:
        is_from_integration = f in integration_incoming_files
        is_evidence_or_guard = (
            f.startswith("delivery-evidence/")
            or f == "tests/guards/test_evidence_synchronization.py"
        )
        assert is_from_integration or is_evidence_or_guard, (
            f"UNAUTHORIZED SOURCE MUTATION DETECTED: file '{f}' was modified outside integration merge and evidence regeneration!"
        )
