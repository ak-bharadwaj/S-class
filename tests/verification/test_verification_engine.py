import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from sclass.verification.engine import (
    PytestVerifier,
    RuffVerifier,
    sanitize_targets,
)


def test_sanitize_targets_flag_injection_rejection():
    """Verify sanitize_targets rejects flags starting with - or --."""
    # Valid targets
    assert sanitize_targets(["src/app.py", "tests/test_app.py"]) == ("src/app.py", "tests/test_app.py")
    assert sanitize_targets(["  path/to/file.py  "]) == ("path/to/file.py",)

    # Flag injections must raise ValueError
    with pytest.raises(ValueError, match="Flag argument injection rejected"):
        sanitize_targets(["--override-ini=foo"])

    with pytest.raises(ValueError, match="Flag argument injection rejected"):
        sanitize_targets(["-o"])

    with pytest.raises(ValueError, match="Flag argument injection rejected"):
        sanitize_targets(["tests", "--confcutdir=/tmp"])


def test_verifiers_handle_timeout():
    """Verify engines catch subprocess.TimeoutExpired gracefully without crashing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        ws = Path(tmp_dir)
        verifier = PytestVerifier()

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["pytest"], timeout=1.0)):
            rec = verifier.run(ws, targets=(), timeout_ms=1000)
            assert rec.passed is False
            assert rec.returncode == -1
            assert b"timed out" in rec.stderr


def test_verifiers_handle_file_not_found():
    """Verify engines handle missing tool binary gracefully."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        ws = Path(tmp_dir)
        verifier = RuffVerifier()

        with patch("subprocess.run", side_effect=FileNotFoundError("ruff not found")):
            rec = verifier.run(ws, targets=(), timeout_ms=5000)
            assert rec.passed is False
            assert rec.returncode == 127
            assert b"not found" in rec.stderr


def test_pytest_verifier_executes_in_workspace():
    """Verify PytestVerifier executes against real workspace directory."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        ws = Path(tmp_dir)
        (ws / "test_simple.py").write_text("def test_ok(): assert 1 + 1 == 2\n")

        verifier = PytestVerifier()
        rec = verifier.run(ws, targets=("test_simple.py",), timeout_ms=10000)
        assert rec.passed is True
        assert rec.returncode == 0


def test_missing_verifier_tool_emits_explicit_tool_unavailable_observation():
    """Verify missing tool binary emits explicit TOOL_UNAVAILABLE observation, ERROR status, never silent FAIL/PASS."""
    from sclass import (
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
    from sclass.verification.engine import MultiEngineVerificationPlane

    plane = MultiEngineVerificationPlane()
    step = VerificationStep(
        "step-ruff", EvidenceKind.STATIC, "ruff", "0.1.0",
        Digest("sha256:" + "0" * 64), 5000,
        ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    )
    obl = Obligation(
        "obl-lint", "obj-1", 1, "Lint check",
        ObligationKind.NON_FUNCTIONAL, RiskTier.LOW,
        ObligationStatus.PENDING, frozenset(), "ac-1", None
    )
    ts = TargetSnapshot(
        "s", "w", Digest("sha256:" + "1" * 64), Digest("sha256:" + "2" * 64),
        None, None, Digest("sha256:" + "3" * 64), Digest("sha256:" + "4" * 64),
        Digest("sha256:" + "5" * 64), (), FrozenMap.from_items(), "p", UtcInstant(1)
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        ws = Path(tmp_dir)
        with patch("subprocess.run", side_effect=FileNotFoundError("ruff missing")):
            receipt = plane.verify_step(ws, step, obl, ts)

            # Assert explicit TOOL_UNAVAILABLE observation
            assert receipt.payload.observation_id == "TOOL_UNAVAILABLE"
            # Assert non-silent status (ERROR, not FAIL, not PASS)
            assert receipt.payload.result_status == VerificationStatus.ERROR
            assert receipt.payload.result_status is not VerificationStatus.FAIL
            assert receipt.payload.result_status is not VerificationStatus.PASS
            assert receipt.signature is not None

