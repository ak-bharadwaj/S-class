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


@pytest.mark.parametrize("adapter_cls", ADAPTER_CLASSES)
def test_no_passing_evidence_admitted_when_empty_output(adapter_cls, dummy_verification_context):
    """Empty stdout/stderr with exit code zero must NOT produce passed=True or PASS receipt (D8)."""
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
    mock_res.stdout = b""
    mock_res.stderr = b""

    with patch("subprocess.run", return_value=mock_res):
        record = adapter.run(tmp_path)
        assert record.passed is False
        assert record.returncode == -2
        assert b"Empty verifier output" in record.stderr

        receipt = plane.verify_step(tmp_path, step, obl, ts)
        assert receipt.payload.result_status != VerificationStatus.PASS


@pytest.mark.parametrize("adapter_cls", ADAPTER_CLASSES)
def test_no_passing_evidence_admitted_when_arbitrary_unstructured(adapter_cls, dummy_verification_context):
    """Arbitrary unstructured output with exit code zero must NOT produce passed=True or PASS receipt (D8)."""
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
    mock_res.stdout = b"Hello world 123 this is arbitrary output without structure"
    mock_res.stderr = b""

    with patch("subprocess.run", return_value=mock_res):
        record = adapter.run(tmp_path)
        assert record.passed is False
        assert record.returncode == -2
        assert b"failed" in record.stderr.lower()

        receipt = plane.verify_step(tmp_path, step, obl, ts)
        assert receipt.payload.result_status != VerificationStatus.PASS


# =============================================================================
# 6. D8 False-Success Rejection Tests (Parameterized Across All 5 Adapters)
# =============================================================================

VALID_COUNTERS = {
    "locust": {"total_requests": 150},
    "schemathesis": {"checks": 45},
    "playwright": {"tests": 12, "passed": 12},
    "testcontainers": {"containers": 2, "passed": 8},
    "cosmic-ray": {"mutation_score": 92.5, "killed": 37},
}


@pytest.mark.parametrize("adapter_cls", ADAPTER_CLASSES)
def test_adapter_rejects_passed_false(adapter_cls, dummy_verification_context):
    """1. Reject {"passed": false} both bare and in tool payload."""
    step_map, obl, ts, tmp_path = dummy_verification_context
    adapter = adapter_cls()
    ev_kind, step_id = step_map[adapter.verifier_id]
    step = VerificationStep(step_id, ev_kind, adapter.verifier_id, "1.0.0", Digest("sha256:" + "0" * 64), 5000, ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))
    plane = MultiEngineVerificationPlane()
    plane.register_engine(adapter)

    for payload in [
        b'{"passed": false}',
        f'{{"tool": "{adapter.verifier_id}", "status": "passed", "passed": false}}'.encode(),
    ]:
        mock_res = MagicMock(returncode=0, stdout=payload, stderr=b"")
        with patch("subprocess.run", return_value=mock_res):
            record = adapter.run(tmp_path)
            assert record.passed is False, f"{adapter.verifier_id} must reject passed=False"
            assert record.returncode == -2
            receipt = plane.verify_step(tmp_path, step, obl, ts)
            assert receipt.payload.result_status != VerificationStatus.PASS


@pytest.mark.parametrize("adapter_cls", ADAPTER_CLASSES)
def test_adapter_rejects_failing_item_in_json_list(adapter_cls, dummy_verification_context):
    """1. Reject any failing result inside a JSON list."""
    step_map, obl, ts, tmp_path = dummy_verification_context
    adapter = adapter_cls()
    ev_kind, step_id = step_map[adapter.verifier_id]
    step = VerificationStep(step_id, ev_kind, adapter.verifier_id, "1.0.0", Digest("sha256:" + "0" * 64), 5000, ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))
    plane = MultiEngineVerificationPlane()
    plane.register_engine(adapter)

    c_key, c_val = next(iter(VALID_COUNTERS[adapter.verifier_id].items()))
    failing_lists = [
        b'[{"passed": false}]',
        f'[{{"tool": "{adapter.verifier_id}", "status": "passed", "{c_key}": {c_val}}}, {{"passed": false}}]'.encode(),
        f'[{{"tool": "{adapter.verifier_id}", "status": "passed", "{c_key}": {c_val}}}, {{"status": "failed"}}]'.encode(),
        f'[{{"tool": "{adapter.verifier_id}", "status": "passed", "{c_key}": {c_val}}}, {{"failed": 1}}]'.encode(),
        f'[{{"tool": "{adapter.verifier_id}", "status": "passed", "{c_key}": {c_val}}}, {{"errors": 1}}]'.encode(),
    ]

    for payload in failing_lists:
        mock_res = MagicMock(returncode=0, stdout=payload, stderr=b"")
        with patch("subprocess.run", return_value=mock_res):
            record = adapter.run(tmp_path)
            assert record.passed is False, f"{adapter.verifier_id} must reject failing item in list"
            assert record.returncode == -2
            receipt = plane.verify_step(tmp_path, step, obl, ts)
            assert receipt.payload.result_status != VerificationStatus.PASS


@pytest.mark.parametrize("adapter_cls", ADAPTER_CLASSES)
def test_adapter_rejects_wrong_tool_identity(adapter_cls, dummy_verification_context):
    """2. Reject wrong-tool identity."""
    step_map, obl, ts, tmp_path = dummy_verification_context
    adapter = adapter_cls()
    ev_kind, step_id = step_map[adapter.verifier_id]
    step = VerificationStep(step_id, ev_kind, adapter.verifier_id, "1.0.0", Digest("sha256:" + "0" * 64), 5000, ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))
    plane = MultiEngineVerificationPlane()
    plane.register_engine(adapter)

    for payload in [
        b'{"tool": "wrong_tool_identity", "status": "passed", "total": 10}',
        b'[{"tool": "wrong_tool_identity", "status": "passed", "total": 10}]',
    ]:
        mock_res = MagicMock(returncode=0, stdout=payload, stderr=b"")
        with patch("subprocess.run", return_value=mock_res):
            record = adapter.run(tmp_path)
            assert record.passed is False
            assert record.returncode == -2
            receipt = plane.verify_step(tmp_path, step, obl, ts)
            assert receipt.payload.result_status != VerificationStatus.PASS


@pytest.mark.parametrize("adapter_cls", ADAPTER_CLASSES)
def test_adapter_rejects_tool_only_json(adapter_cls, dummy_verification_context):
    """2. Reject tool-only JSON."""
    step_map, obl, ts, tmp_path = dummy_verification_context
    adapter = adapter_cls()
    ev_kind, step_id = step_map[adapter.verifier_id]
    step = VerificationStep(step_id, ev_kind, adapter.verifier_id, "1.0.0", Digest("sha256:" + "0" * 64), 5000, ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))
    plane = MultiEngineVerificationPlane()
    plane.register_engine(adapter)

    for payload in [
        f'{{"tool": "{adapter.verifier_id}"}}'.encode(),
        f'[{{"tool": "{adapter.verifier_id}"}}]'.encode(),
    ]:
        mock_res = MagicMock(returncode=0, stdout=payload, stderr=b"")
        with patch("subprocess.run", return_value=mock_res):
            record = adapter.run(tmp_path)
            assert record.passed is False
            assert record.returncode == -2
            receipt = plane.verify_step(tmp_path, step, obl, ts)
            assert receipt.payload.result_status != VerificationStatus.PASS


@pytest.mark.parametrize("adapter_cls", ADAPTER_CLASSES)
def test_adapter_rejects_missing_explicit_success_status(adapter_cls, dummy_verification_context):
    """3. Require explicit successful status."""
    step_map, obl, ts, tmp_path = dummy_verification_context
    adapter = adapter_cls()
    ev_kind, step_id = step_map[adapter.verifier_id]
    step = VerificationStep(step_id, ev_kind, adapter.verifier_id, "1.0.0", Digest("sha256:" + "0" * 64), 5000, ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))
    plane = MultiEngineVerificationPlane()
    plane.register_engine(adapter)

    c_key, c_val = next(iter(VALID_COUNTERS[adapter.verifier_id].items()))
    for payload in [
        f'{{"tool": "{adapter.verifier_id}", "{c_key}": {c_val}}}'.encode(),
        f'{{"tool": "{adapter.verifier_id}", "status": "running", "{c_key}": {c_val}}}'.encode(),
    ]:
        mock_res = MagicMock(returncode=0, stdout=payload, stderr=b"")
        with patch("subprocess.run", return_value=mock_res):
            record = adapter.run(tmp_path)
            assert record.passed is False
            assert record.returncode == -2
            receipt = plane.verify_step(tmp_path, step, obl, ts)
            assert receipt.payload.result_status != VerificationStatus.PASS


@pytest.mark.parametrize("adapter_cls", ADAPTER_CLASSES)
def test_adapter_rejects_missing_counters(adapter_cls, dummy_verification_context):
    """4. Reject missing numeric result counters."""
    step_map, obl, ts, tmp_path = dummy_verification_context
    adapter = adapter_cls()
    ev_kind, step_id = step_map[adapter.verifier_id]
    step = VerificationStep(step_id, ev_kind, adapter.verifier_id, "1.0.0", Digest("sha256:" + "0" * 64), 5000, ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))
    plane = MultiEngineVerificationPlane()
    plane.register_engine(adapter)

    for payload in [
        f'{{"tool": "{adapter.verifier_id}", "status": "passed"}}'.encode(),
        f'{{"tool": "{adapter.verifier_id}", "passed": true}}'.encode(),
        f'[{{"tool": "{adapter.verifier_id}", "status": "passed"}}]'.encode(),
    ]:
        mock_res = MagicMock(returncode=0, stdout=payload, stderr=b"")
        with patch("subprocess.run", return_value=mock_res):
            record = adapter.run(tmp_path)
            assert record.passed is False
            assert record.returncode == -2
            receipt = plane.verify_step(tmp_path, step, obl, ts)
            assert receipt.payload.result_status != VerificationStatus.PASS


@pytest.mark.parametrize("adapter_cls", ADAPTER_CLASSES)
def test_adapter_rejects_nonzero_failed_or_error_counts(adapter_cls, dummy_verification_context):
    """4. Reject nonzero failed/error counts."""
    step_map, obl, ts, tmp_path = dummy_verification_context
    adapter = adapter_cls()
    ev_kind, step_id = step_map[adapter.verifier_id]
    step = VerificationStep(step_id, ev_kind, adapter.verifier_id, "1.0.0", Digest("sha256:" + "0" * 64), 5000, ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))
    plane = MultiEngineVerificationPlane()
    plane.register_engine(adapter)

    c_key, c_val = next(iter(VALID_COUNTERS[adapter.verifier_id].items()))
    for err_field in ("failed", "failures", "errors", "num_failures"):
        payload = f'{{"tool": "{adapter.verifier_id}", "status": "passed", "{c_key}": {c_val}, "{err_field}": 1}}'.encode()
        mock_res = MagicMock(returncode=0, stdout=payload, stderr=b"")
        with patch("subprocess.run", return_value=mock_res):
            record = adapter.run(tmp_path)
            assert record.passed is False, f"{adapter.verifier_id} must reject nonzero {err_field}"
            assert record.returncode == -2
            receipt = plane.verify_step(tmp_path, step, obl, ts)
            assert receipt.payload.result_status != VerificationStatus.PASS


@pytest.mark.parametrize("adapter_cls", ADAPTER_CLASSES)
@pytest.mark.parametrize("bare_text", [
    b"All 12 verifications passed cleanly",
    b"passed cleanly",
    b"success",
    b"ok",
    b"OK",
    b"pass",
    b"passed",
    b"true",
    b"Verification succeeded",
    b"Everything passed",
    b"0",
])
def test_adapter_rejects_bare_success_text(adapter_cls, bare_text, dummy_verification_context):
    """5. Reject bare success-like text without validated, tool-specific summary."""
    step_map, obl, ts, tmp_path = dummy_verification_context
    adapter = adapter_cls()
    ev_kind, step_id = step_map[adapter.verifier_id]
    step = VerificationStep(step_id, ev_kind, adapter.verifier_id, "1.0.0", Digest("sha256:" + "0" * 64), 5000, ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))
    plane = MultiEngineVerificationPlane()
    plane.register_engine(adapter)

    mock_res = MagicMock(returncode=0, stdout=bare_text, stderr=b"")
    with patch("subprocess.run", return_value=mock_res):
        record = adapter.run(tmp_path)
        assert record.passed is False, f"{adapter.verifier_id} must reject bare text: {bare_text!r}"
        assert record.returncode == -2
        receipt = plane.verify_step(tmp_path, step, obl, ts)
        assert receipt.payload.result_status != VerificationStatus.PASS


# =============================================================================
# 7. Valid Passing Cases (Using Actual Supported Tool Output / Captured Fixtures)
# =============================================================================

VALID_STRUCTURED_SAMPLES = {
    "locust": b'{"tool": "locust", "status": "passed", "total_requests": 150, "failed": 0}',
    "schemathesis": b'{"tool": "schemathesis", "status": "passed", "checks": 45, "failed": 0, "errors": 0}',
    "playwright": b'{"tool": "playwright", "status": "passed", "tests": 12, "passed": 12, "failed": 0}',
    "testcontainers": b'{"tool": "testcontainers", "status": "passed", "containers": 2, "passed": 8, "failed": 0}',
    "cosmic-ray": b'{"tool": "cosmic-ray", "status": "passed", "total_mutations": 40, "killed": 37, "mutation_score": 92.5, "errors": 0}',
}

VALID_TEXT_SAMPLES = {
    "locust": b"""Type     Name                                                              # reqs      # fails |    Avg     Min     Max    Med |   req/s  failures/s
--------|----------------------------------------------------------------|-------|-------------|-------|-------|-------|-------|--------|-----------
GET      /api/health                                                          150           0(0.00%) |      4       1      15      3 |   50.00        0.00
--------|----------------------------------------------------------------|-------|-------------|-------|-------|-------|-------|--------|-----------
         Aggregated                                                           150           0(0.00%) |      4       1      15      3 |   50.00        0.00
""",
    "schemathesis": b"""============================== Schemathesis test session starts ==============================
Schema: /openapi.json
checks: 45 passed, 0 failed

=================================== 45 passed in 1.42s ===================================
""",
    "playwright": b"""Running 12 tests using 4 workers
============================== 12 passed in 2.34s ==============================
""",
    "testcontainers": b"""============================== 8 passed in 3.12s ==============================
[testcontainers] containers healthy (postgres:15-alpine, redis:7-alpine)
""",
    "cosmic-ray": b"""[cosmic-ray] summary: mutation score 92.5%, killed: 37, errors: 0
complete: mutation score 92.5%, killed: 37, survived: 0, errors: 0
""",
}


@pytest.mark.parametrize("adapter_cls", ADAPTER_CLASSES)
def test_adapter_valid_execution_passes(adapter_cls, tmp_path, dummy_verification_context):
    step_map, obl, ts, _ = dummy_verification_context
    adapter = adapter_cls()
    ev_kind, step_id = step_map[adapter.verifier_id]

    step = VerificationStep(
        step_id, ev_kind, adapter.verifier_id, "1.0.0",
        Digest("sha256:" + "0" * 64), 5000,
        ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    )

    plane = MultiEngineVerificationPlane()
    plane.register_engine(adapter)

    # 1. Test valid JSON structured output
    mock_json = MagicMock()
    mock_json.returncode = 0
    mock_json.stdout = VALID_STRUCTURED_SAMPLES[adapter.verifier_id]
    mock_json.stderr = b""

    with patch("subprocess.run", return_value=mock_json):
        record = adapter.run(tmp_path)
        assert record.passed is True
        assert record.returncode == 0

        receipt = plane.verify_step(tmp_path, step, obl, ts)
        assert receipt.payload.result_status == VerificationStatus.PASS

    # 2. Test valid Text structured output
    mock_text = MagicMock()
    mock_text.returncode = 0
    mock_text.stdout = VALID_TEXT_SAMPLES[adapter.verifier_id]
    mock_text.stderr = b""

    with patch("subprocess.run", return_value=mock_text):
        record = adapter.run(tmp_path)
        assert record.passed is True
        assert record.returncode == 0

        receipt = plane.verify_step(tmp_path, step, obl, ts)
        assert receipt.payload.result_status == VerificationStatus.PASS
