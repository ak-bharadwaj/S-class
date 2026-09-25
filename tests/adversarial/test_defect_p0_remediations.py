"""
P0 Defect Remediation Adversarial Test Suite.
Verifies fixes for DEFECT-01 through DEFECT-10.
"""

import os
import sys
import tempfile
import pytest

from sclass.execution.identity import ExecutionIdentity
from sclass.verification.detector import StandardVerifierDetector, VerifierConfidence
from sclass.verification.trust_registry import TrustRegistry, TrustPolicy, get_trust_registry
from sclass.verification.verifier_definition import VerifierTrustMode


def test_defect_01_unknown_verifier_trust_never_authorizes(tmp_path):
    """
    DEFECT-01 Adversarial Negative Test:
    A foreign binary named 'pytest.exe' located outside workspace, temp, or system directories
    evaluates to VerifierTrustMode.UNKNOWN.
    StandardVerifierDetector MUST fail closed with VerifierConfidence.CONTRADICTED,
    and must NEVER return AUTHORIZED via permissive basename matching fallback.
    """
    foreign_pytest = "C:\\opt\\foreign_install\\pytest.exe" if os.name == "nt" else "/opt/foreign_install/pytest"
    ws_dir = str(tmp_path / "workspace")

    ident = ExecutionIdentity(
        requested_argv=(foreign_pytest, "tests/"),
        actual_argv=(foreign_pytest, "tests/"),
        executable_name="pytest",
        executable_path=foreign_pytest,
        executable_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        pid=2001,
        parent_pid=2000,
        process_start_time="2026-09-25T00:00:00Z",
        cwd=ws_dir,
        environment_digest="dig_unknown",
        execution_mode="HOST_ARGV",
    )

    registry = TrustRegistry()
    defn, mode, status = registry.evaluate_verifier(ident, workspace_dir=ws_dir)
    assert mode == VerifierTrustMode.UNKNOWN
    assert status == "IDENTIFIED_AS_PYTEST+UNKNOWN_BINARY"

    detector = StandardVerifierDetector()
    res = detector.detect(ident)

    # Must fail closed: CONTRADICTED, NEVER AUTHORIZED
    assert res.confidence == VerifierConfidence.CONTRADICTED
    assert res.confidence != VerifierConfidence.AUTHORIZED
    assert res.verifier_id == "pytest"
    assert res.evidence["trust_mode"] == "UNKNOWN"
    assert "IDENTIFIED_AS_PYTEST+UNKNOWN_BINARY" in res.evidence["status"]


def test_defect_01_foreign_jest_unknown_trust_contradicted(tmp_path):
    """Foreign jest binary outside trusted dirs must be CONTRADICTED."""
    foreign_jest = "C:\\opt\\foreign_node\\jest.cmd" if os.name == "nt" else "/opt/foreign_node/jest"
    ws_dir = str(tmp_path / "workspace")

    ident = ExecutionIdentity(
        requested_argv=(foreign_jest, "--runInBand"),
        actual_argv=(foreign_jest, "--runInBand"),
        executable_name="jest",
        executable_path=foreign_jest,
        executable_hash="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        pid=2002,
        parent_pid=2000,
        process_start_time="2026-09-25T00:00:00Z",
        cwd=ws_dir,
        environment_digest="dig_jest",
        execution_mode="HOST_ARGV",
    )

    detector = StandardVerifierDetector()
    res = detector.detect(ident)

    assert res.confidence == VerifierConfidence.CONTRADICTED
    assert res.confidence != VerifierConfidence.AUTHORIZED
    assert res.verifier_id == "jest"
    assert res.evidence["trust_mode"] == "UNKNOWN"
