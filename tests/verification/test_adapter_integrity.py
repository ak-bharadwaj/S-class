"""Comprehensive verification adapter integrity tests (F8).

Ensures that absent external tools, timeouts, process crashes, malformed outputs,
and unverifiable results never produce passed=True or admissible passing evidence.
"""
from pathlib import Path
import subprocess
from unittest.mock import MagicMock, patch
import pytest

from sclass import (
    Admissibility,
    ClosureVerdict,
    Digest,
    EvidenceKind,
    FrozenMap,
    Obligation,
    ObligationKind,
    ObligationStatus,
    ResourceBudget,
    RiskTier,
    TargetSnapshot,
    UtcInstant,
    VerificationStatus,
    VerificationStep,
)
from sclass.verification.adapters.locust_adapter import LocustAdapter
from sclass.verification.adapters.schemathesis_adapter import SchemathesisAdapter
from sclass.verification.adapters.playwright_adapter import PlaywrightAdapter
from sclass.verification.adapters.testcontainers_adapter import TestcontainersAdapter
from sclass.verification.adapters.cosmic_ray_adapter import CosmicRayAdapter
from sclass.verification.engine import (
    MultiEngineVerificationPlane,
    VerifierExecutionRecord,
)

ADAPTER_CLASSES = [
    LocustAdapter,
    SchemathesisAdapter,
    PlaywrightAdapter,
    TestcontainersAdapter,
    CosmicRayAdapter,
]


@pytest.fixture
def dummy_verification_context(tmp_path):
    """Provides minimal valid context objects for MultiEngineVerificationPlane integration."""
    step_map = {
        "locust": (EvidenceKind.PERFORMANCE, "step-locust"),
        "schemathesis": (EvidenceKind.DYNAMIC, "step-schemathesis"),
        "playwright": (EvidenceKind.BEHAVIORAL, "step-playwright"),
        "testcontainers": (EvidenceKind.BEHAVIORAL, "step-testcontainers"),
        "cosmic-ray": (EvidenceKind.METAMORPHIC, "step-cosmic-ray"),
    }
    obl = Obligation(
        "obl-f8", "obj-1", 1, "F8 integrity obligation",
        ObligationKind.FUNCTIONAL, RiskTier.HIGH,
        ObligationStatus.PENDING, frozenset(), "ac-f8", None,
    )
    ts = TargetSnapshot(
        "s", "w", Digest("sha256:" + "1" * 64), Digest("sha256:" + "2" * 64),
        None, None, Digest("sha256:" + "3" * 64), Digest("sha256:" + "4" * 64),
        Digest("sha256:" + "5" * 64), (), FrozenMap.from_items(), "p", UtcInstant(1),
    )
    return step_map, obl, ts, tmp_path


# =============================================================================
# 1. Tool Absent
# =============================================================================

@pytest.mark.parametrize("adapter_cls", ADAPTER_CLASSES)
def test_adapter_tool_absent_returns_non_passing_unavailable(adapter_cls, tmp_path):
    adapter = adapter_cls()
    with patch("subprocess.run", side_effect=FileNotFoundError(f"{adapter.verifier_id} not found")):
        record = adapter.run(tmp_path)
        assert record.passed is False, f"{adapter.verifier_id} must not pass when tool absent"
        assert record.returncode == 127
        assert b"UNAVAILABLE:" in record.stderr
        assert b"not found" in record.stderr.lower()


# =============================================================================
# 2. Timeout
# =============================================================================

@pytest.mark.parametrize("adapter_cls", ADAPTER_CLASSES)
def test_adapter_timeout_returns_non_passing_blocked(adapter_cls, tmp_path):
    adapter = adapter_cls()
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["test"], timeout=1.0)):
        record = adapter.run(tmp_path, timeout_ms=1000)
        assert record.passed is False, f"{adapter.verifier_id} must not pass on timeout"
        assert record.returncode == -1
        assert b"BLOCKED:" in record.stderr
        assert b"timed out" in record.stderr.lower()


# =============================================================================
# 3. Process Crash / Non-zero Exit
# =============================================================================

@pytest.mark.parametrize("adapter_cls", ADAPTER_CLASSES)
@pytest.mark.parametrize("exit_code", [1, 2, 5, 137, -9])
def test_adapter_nonzero_exit_returns_non_passing(adapter_cls, exit_code, tmp_path):
    adapter = adapter_cls()
    mock_res = MagicMock()
    mock_res.returncode = exit_code
    mock_res.stdout = b"Execution failed"
    mock_res.stderr = b"Fatal runtime exit"

    with patch("subprocess.run", return_value=mock_res):
        record = adapter.run(tmp_path)
        assert record.passed is False, f"{adapter.verifier_id} must not pass on exit code {exit_code}"
        assert record.returncode == exit_code


# =============================================================================
# 4. Malformed Output
# =============================================================================

@pytest.mark.parametrize("adapter_cls", ADAPTER_CLASSES)
@pytest.mark.parametrize("stdout,stderr", [
    (b"ok", b"Traceback (most recent call last):\n  File 'x.py', line 1, in <module>\nValueError"),
    (b"INTERNALERROR: cannot inspect test suite", b""),
    (b"MALFORMED: corrupted JSON record output stream", b""),
    (b"CORRUPTED: header checksum mismatch", b""),
])
def test_adapter_malformed_output_returns_non_passing(adapter_cls, stdout, stderr, tmp_path):
    adapter = adapter_cls()
    mock_res = MagicMock()
    mock_res.returncode = 0  # Even if process exited with 0
    mock_res.stdout = stdout
    mock_res.stderr = stderr

    with patch("subprocess.run", return_value=mock_res):
        record = adapter.run(tmp_path)
        assert record.passed is False, f"{adapter.verifier_id} must reject malformed output"
        assert record.returncode != 0
        assert b"BLOCKED: Malformed output detected" in record.stderr


# =============================================================================
# 5. No Passing Evidence Admitted in Any Failure Case
# =============================================================================

@pytest.mark.parametrize("adapter_cls", ADAPTER_CLASSES)
def test_no_passing_evidence_admitted_when_tool_absent(adapter_cls, dummy_verification_context):
    step_map, obl, ts, tmp_path = dummy_verification_context
    adapter = adapter_cls()
    ev_kind, step_id = step_map[adapter.verifier_id]

    step = VerificationStep(
        step_id, ev_kind, adapter.verifier_id, "1.0.0",
        Digest("sha256:" + "0" * 64), 5000,
        ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    )

    plane = MultiEngineVerificationPlane()
    plane.register_engine(adapter)

    with patch("subprocess.run", side_effect=FileNotFoundError("binary not found")):
        receipt = plane.verify_step(tmp_path, step, obl, ts)
        # 1. Receipt must NOT have PASS status
        assert receipt.payload.result_status != VerificationStatus.PASS
        assert receipt.payload.result_status == VerificationStatus.ERROR
        assert receipt.payload.observation_id == "TOOL_UNAVAILABLE"


@pytest.mark.parametrize("adapter_cls", ADAPTER_CLASSES)
def test_no_passing_evidence_admitted_when_timed_out(adapter_cls, dummy_verification_context):
    step_map, obl, ts, tmp_path = dummy_verification_context
    adapter = adapter_cls()
    ev_kind, step_id = step_map[adapter.verifier_id]

    step = VerificationStep(
        step_id, ev_kind, adapter.verifier_id, "1.0.0",
        Digest("sha256:" + "0" * 64), 5000,
        ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    )

    plane = MultiEngineVerificationPlane()
    plane.register_engine(adapter)

    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["test"], timeout=1.0)):
        receipt = plane.verify_step(tmp_path, step, obl, ts)
        assert receipt.payload.result_status != VerificationStatus.PASS
        assert receipt.payload.result_status == VerificationStatus.TIMEOUT


@pytest.mark.parametrize("adapter_cls", ADAPTER_CLASSES)
def test_no_passing_evidence_admitted_when_malformed(adapter_cls, dummy_verification_context):
    step_map, obl, ts, tmp_path = dummy_verification_context
    adapter = adapter_cls()
    ev_kind, step_id = step_map[adapter.verifier_id]

    step = VerificationStep(
        step_id, ev_kind, adapter.verifier_id, "1.0.0",
        Digest("sha256:" + "0" * 64), 5000,
        ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    )

    plane = MultiEngineVerificationPlane()
    plane.register_engine(adapter)

    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = b"MALFORMED: corrupt test results"
    mock_res.stderr = b""

    with patch("subprocess.run", return_value=mock_res):
        receipt = plane.verify_step(tmp_path, step, obl, ts)
        assert receipt.payload.result_status != VerificationStatus.PASS


# =============================================================================
# 6. Valid Passing Case
# =============================================================================

@pytest.mark.parametrize("adapter_cls", ADAPTER_CLASSES)
def test_adapter_valid_execution_passes(adapter_cls, tmp_path):
    adapter = adapter_cls()
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = b"All 12 verifications passed cleanly"
    mock_res.stderr = b""

    with patch("subprocess.run", return_value=mock_res):
        record = adapter.run(tmp_path)
        assert record.passed is True
        assert record.returncode == 0
        assert b"passed cleanly" in record.stdout
