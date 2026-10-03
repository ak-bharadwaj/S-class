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
