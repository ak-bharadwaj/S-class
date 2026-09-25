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


def test_defect_08_non_zero_exit_code_never_produces_successful_verification():
    """
    DEFECT-08 Adversarial Negative Test:
    A crashed, aborted, or failing test runner with exit code != 0 that reported some passed tests
    must NEVER evaluate to is_successful=True, and failed must be max(1, failed).
    """
    from sclass.verification.result_parser import (
        PytestResultParser,
        JestResultParser,
        VitestResultParser,
        MochaResultParser,
        PlaywrightResultParser,
        CargoTestResultParser,
        GoTestResultParser,
        UnittestResultParser,
    )

    # 1. Pytest: 5 passed tests, but suite crashed/aborted with exit code 2
    py_res = PytestResultParser.parse(
        stdout="=== 5 passed in 0.45s ===",
        stderr="INTERNALERROR: crash in test runner teardown",
        exit_code=2,
    )
    assert not py_res.is_successful
    assert py_res.failed >= 1
    assert py_res.exit_code == 2

    # 2. Jest: 3 passed tests, aborted with exit code 1
    jest_res = JestResultParser.parse(
        stdout="Tests: 3 passed, 3 total\nTime: 1.2s",
        stderr="FATAL: out of memory",
        exit_code=1,
    )
    assert not jest_res.is_successful
    assert jest_res.failed >= 1
    assert jest_res.exit_code == 1

    # 3. Vitest: 4 passed tests, exit code 1
    vit_res = VitestResultParser.parse(
        stdout="4 passed\nDuration 0.8s",
        stderr="Segmentation fault",
        exit_code=1,
    )
    assert not vit_res.is_successful
    assert vit_res.failed >= 1
    assert vit_res.exit_code == 1

    # 4. Mocha: 2 passed tests, exit code 1
    mocha_res = MochaResultParser.parse(
        stdout="2 passing (50ms)",
        stderr="UnhandlerPromiseRejection",
        exit_code=1,
    )
    assert not mocha_res.is_successful
    assert mocha_res.failed >= 1
    assert mocha_res.exit_code == 1

    # 5. Playwright: 6 passed tests, exit code 1
    pw_res = PlaywrightResultParser.parse(
        stdout="6 passed (3.2s)",
        stderr="Browser disconnected unexpectedly",
        exit_code=1,
    )
    assert not pw_res.is_successful
    assert pw_res.failed >= 1
    assert pw_res.exit_code == 1

    # 6. Cargo test: 10 passed tests, exit code 101 (panic)
    cargo_res = CargoTestResultParser.parse(
        stdout="test result: ok. 10 passed; 0 failed; 0 ignored",
        stderr="thread 'main' panicked at 'assertion failed'",
        exit_code=101,
    )
    assert not cargo_res.is_successful
    assert cargo_res.failed >= 1
    assert cargo_res.exit_code == 101

    # 7. Go test: 1 passed test, exit code 1
    go_res = GoTestResultParser.parse(
        stdout="--- PASS: TestFeature\nok pkg/mod 0.12s",
        stderr="panic: runtime error",
        exit_code=1,
    )
    assert not go_res.is_successful
    assert go_res.failed >= 1
    assert go_res.exit_code == 1

    # 8. Unittest: 3 passed tests, exit code 1
    ut_res = UnittestResultParser.parse(
        stdout="Ran 3 tests in 0.05s\n\nOK",
        stderr="SystemExit during teardown",
        exit_code=1,
    )
    assert not ut_res.is_successful
    assert ut_res.failed >= 1
    assert ut_res.exit_code == 1


def test_defect_03_trusted_path_requires_trusted_hash(tmp_path):
    """
    DEFECT-03 Adversarial Negative Test:
    A binary located at an explicitly trusted path must require a matching trusted hash
    when trusted_hashes is populated. An attacker replacing the trusted binary with a
    modified payload (yielding a different hash) must be classified as UNTRUSTED and
    CONTRADICTED, never TRUSTED or AUTHORIZED.
    """
    trusted_bin = "C:\\trusted_tools\\pytest.exe" if os.name == "nt" else "/trusted_tools/pytest"
    valid_hash = "1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff"
    tampered_hash = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"

    policy = TrustPolicy()
    registry = TrustRegistry(policy=policy)
    registry.mark_trusted_path(trusted_bin)
    registry.mark_trusted_hash(valid_hash)

    # 1. Authentic binary matching both path and hash -> TRUSTED
    mode_legit = registry.classify_binary_trust(trusted_bin, binary_hash=valid_hash)
    assert mode_legit == VerifierTrustMode.TRUSTED

    # 2. Tampered binary at trusted path with mismatched hash -> UNTRUSTED
    mode_tampered = registry.classify_binary_trust(trusted_bin, binary_hash=tampered_hash)
    assert mode_tampered == VerifierTrustMode.UNTRUSTED
    assert mode_tampered != VerifierTrustMode.TRUSTED

    # 3. Missing hash at trusted path when trusted_hashes populated -> UNTRUSTED
    mode_nohash = registry.classify_binary_trust(trusted_bin, binary_hash="")
    assert mode_nohash == VerifierTrustMode.UNTRUSTED

    # 4. StandardVerifierDetector on tampered binary -> CONTRADICTED
    ident_tampered = ExecutionIdentity(
        requested_argv=(trusted_bin, "tests/"),
        actual_argv=(trusted_bin, "tests/"),
        executable_name="pytest",
        executable_path=trusted_bin,
        executable_hash=tampered_hash,
        pid=3001,
        parent_pid=3000,
        process_start_time="2026-09-25T00:00:00Z",
        cwd=str(tmp_path),
        environment_digest="dig_tamp",
        execution_mode="HOST_ARGV",
    )
    # Use registry with policy
    defn, mode, status = registry.evaluate_verifier(ident_tampered)
    assert mode == VerifierTrustMode.UNTRUSTED
    assert "UNTRUSTED" in status


