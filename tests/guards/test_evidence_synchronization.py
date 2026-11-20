"""tests/guards/test_evidence_synchronization.py

Auditable Guard Tests for Work Order P27 (R3 Evidence Synchronization).
Enforces CL Acceptance Criteria:
1. test_delivery_evidence_matches_synchronized_head
2. test_evidence_generation_records_exact_reference_sha
"""

import json
import shutil
import subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
GIT_BIN = shutil.which("git") or "/usr/bin/git" or "git"


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
    assert data.get("total_collected") >= 2314
    assert data.get("passed_count") >= 2314
    assert data.get("duration_seconds") > 1.0, (
        f"Test duration must reflect genuine suite execution (>1s), got {data.get('duration_seconds')}"
    )

    report_head = data.get("synchronized_head_sha")
    assert report_head, "synchronized_head_sha must be present in classification report"

    # Validate that report_head is a valid commit in the git repository
    res = subprocess.run(
        [GIT_BIN, "cat-file", "-e", f"{report_head}^{{commit}}"],
        cwd=str(ROOT),
        capture_output=True,
    )
    assert res.returncode == 0, f"Recorded synchronized_head_sha {report_head} must be a valid commit in git history"


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
