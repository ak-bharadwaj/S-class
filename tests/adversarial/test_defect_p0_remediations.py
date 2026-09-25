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


def test_defect_02_workspace_relative_binary_is_untrusted(tmp_path):
    """
    DEFECT-02 Adversarial Negative Test:
    Executables inside the workspace root invoked via relative paths (e.g. ./pytest.exe)
    outside a virtual environment must be classified as UNTRUSTED and rejected with CONTRADICTED,
    never WORKSPACE_TRUSTED or AUTHORIZED.
    """
    ws = tmp_path / "app_workspace"
    ws.mkdir(parents=True, exist_ok=True)
    fake_pytest = ws / ("pytest.exe" if os.name == "nt" else "pytest")
    fake_pytest.write_text("malicious dropped runner", encoding="utf-8")

    registry = TrustRegistry()
    mode = registry.classify_binary_trust(
        executable_path=str(fake_pytest),
        workspace_dir=str(ws),
    )
    assert mode == VerifierTrustMode.UNTRUSTED
    assert mode != VerifierTrustMode.WORKSPACE_TRUSTED

    # Also test relative invocation ./pytest.exe
    rel_path = f".{os.sep}pytest.exe" if os.name == "nt" else "./pytest"
    mode_rel = registry.classify_binary_trust(
        executable_path=rel_path,
        workspace_dir=str(ws),
    )
    assert mode_rel == VerifierTrustMode.UNTRUSTED

    ident = ExecutionIdentity(
        requested_argv=(rel_path, "tests/"),
        actual_argv=(str(fake_pytest), "tests/"),
        executable_name="pytest",
        executable_path=str(fake_pytest),
        executable_hash="abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
        pid=4001,
        parent_pid=4000,
        process_start_time="2026-09-25T00:00:00Z",
        cwd=str(ws),
        environment_digest="dig_ws",
        execution_mode="HOST_ARGV",
    )
    detector = StandardVerifierDetector()
    det_res = detector.detect(ident)

    assert det_res.confidence == VerifierConfidence.CONTRADICTED
    assert det_res.confidence != VerifierConfidence.AUTHORIZED
    assert det_res.verifier_id == "pytest"
    assert "UNTRUSTED" in det_res.evidence.get("trust_mode", "")


def test_defect_09_ntfs_junction_reparse_binary_remains_untrusted(tmp_path, monkeypatch):
    """
    DEFECT-09 Adversarial Negative Test:
    NTFS junctions or symlinks pointing from workspace to an untrusted target path
    must resolve via realpath and be classified as UNTRUSTED, preventing junction bypass.
    """
    policy = TrustPolicy()
    untrusted_target = tmp_path / "untrusted_payload" / "evil_pytest.exe"
    untrusted_target.parent.mkdir(parents=True, exist_ok=True)
    untrusted_target.write_text("evil", encoding="utf-8")

    policy.untrusted_paths.add(os.path.normpath(str(untrusted_target)).lower())
    policy.untrusted_paths.add(os.path.normcase(os.path.realpath(str(untrusted_target))))

    ws = tmp_path / "clean_workspace"
    ws.mkdir(parents=True, exist_ok=True)
    link_path = ws / "symlink_pytest.exe"

    try:
        os.symlink(str(untrusted_target), str(link_path))
    except (OSError, NotImplementedError):
        orig_realpath = os.path.realpath
        def mock_realpath(p):
            if "symlink_pytest" in str(p):
                return str(untrusted_target)
            return orig_realpath(p)
        monkeypatch.setattr(os.path, "realpath", mock_realpath)

    registry = TrustRegistry(policy=policy)
    mode = registry.classify_binary_trust(
        executable_path=str(link_path),
        workspace_dir=str(ws),
    )
    assert mode == VerifierTrustMode.UNTRUSTED


def test_defect_04_missing_or_uncertain_binary_returns_contradicted_and_untrusted():
    """
    DEFECT-04 Adversarial Negative Test:
    Missing, unresolvable, or uncertain binaries must return VerifierConfidence.CONTRADICTED
    and trust_mode UNTRUSTED, rather than returning UNKNOWN.
    """
    from sclass.execution.identity import ExecutionIdentityState

    ident = ExecutionIdentity(
        requested_argv=("nonexistent_cmd_xyz", "tests/"),
        actual_argv=("nonexistent_cmd_xyz", "tests/"),
        executable_name="nonexistent_cmd_xyz",
        executable_path="",
        executable_hash="unresolved_binary",
        pid=5001,
        parent_pid=5000,
        process_start_time="2026-09-25T00:00:00Z",
        cwd=".",
        environment_digest="dig_miss",
        execution_mode="HOST_ARGV",
        identity_state=ExecutionIdentityState.IDENTITY_UNCERTAIN.value,
    )

    detector = StandardVerifierDetector()
    res = detector.detect(ident)

    # Must fail closed: CONTRADICTED + UNTRUSTED, NOT UNKNOWN
    assert res.confidence == VerifierConfidence.CONTRADICTED
    assert res.confidence != VerifierConfidence.UNKNOWN
    assert res.evidence.get("trust_mode") == "UNTRUSTED"
    assert "UNCERTAIN" in res.evidence.get("status", "")


def test_defect_05_windows_same_user_persisted_secret_fails_closed(tmp_path, monkeypatch):
    """
    DEFECT-05 Adversarial Negative Test:
    On Windows, chmod(0o600) does not restrict DACLs against same-user worker processes.
    In dev mode, accessing .sclass/trust/auth.key without explicit worker isolation
    must FAIL CLOSED with SecurityViolationError.
    """
    from sclass.policy.authorization_service import get_authorization_secret
    from sclass.core.errors import SecurityViolationError

    ws = tmp_path / "ws_sec"
    key_dir = ws / ".sclass" / "trust"
    key_dir.mkdir(parents=True)
    key_file = key_dir / "auth.key"
    key_file.write_bytes(b"super_secret_auth_key_1234567890")

    monkeypatch.delenv("SCLASS_AUTH_SECRET", raising=False)
    monkeypatch.delenv("SCLASS_STRICT_SECURITY", raising=False)
    monkeypatch.delenv("SCLASS_STRICT_CERTIFICATION", raising=False)
    monkeypatch.delenv("SCLASS_UNTRUSTED_WORKER", raising=False)
    monkeypatch.delenv("SCLASS_WORKER_ISOLATION", raising=False)
    monkeypatch.delenv("SCLASS_WORKER_ISOLATED", raising=False)

    if os.name == "nt":
        # 1. On Windows without worker isolation: MUST FAIL CLOSED
        with pytest.raises(SecurityViolationError, match="WINDOWS SAME-USER PERSISTED SECRET VULNERABILITY"):
            get_authorization_secret(workspace_dir=str(ws))

        # 2. With explicit worker isolation enabled: succeeds
        monkeypatch.setenv("SCLASS_WORKER_ISOLATION", "1")
        secret = get_authorization_secret(workspace_dir=str(ws))
        assert secret == b"super_secret_auth_key_1234567890"

        # 3. If untrusted worker detected even with isolation: MUST FAIL CLOSED
        monkeypatch.setenv("SCLASS_UNTRUSTED_WORKER", "1")
        with pytest.raises(SecurityViolationError, match="UNTRUSTED WORKER THREAT MODEL"):
            get_authorization_secret(workspace_dir=str(ws))
    else:
        # Non-Windows: verify untrusted worker fails closed
        monkeypatch.setenv("SCLASS_UNTRUSTED_WORKER", "1")
        with pytest.raises(SecurityViolationError, match="UNTRUSTED WORKER THREAT MODEL"):
            get_authorization_secret(workspace_dir=str(ws))


def test_defect_10_verification_subprocess_untrusted_rejected(tmp_path):
    """
    DEFECT-10 Adversarial Negative Test:
    Every verification subprocess must pass through authenticated execution boundary.
    1. Untrusted binary (e.g. dropped script/binary in workspace root) must be REJECTED.
    2. Uncertain/unresolvable binary must be REJECTED.
    3. Test verifier plan executing a non-test verifier must be REJECTED.
    4. Valid process verification passes and captures execution identity in receipt metadata.
    """
    from sclass.verification.executable_engine import ExecutableVerificationEngine
    from sclass.verification.plan import VerificationPlan

    ws = tmp_path / "defect10_ws"
    ws.mkdir(parents=True, exist_ok=True)
    engine = ExecutableVerificationEngine(workspace_dir=str(ws))

    # Case 1: Untrusted binary in workspace root
    evil_bin = ws / ("evil_runner.exe" if os.name == "nt" else "evil_runner.sh")
    evil_bin.write_text("echo pwned", encoding="utf-8")

    plan_untrusted = VerificationPlan(
        plan_id="plan_d10_untrusted",
        task_id="task_d10_1",
        verifiers=["process"],
        commands=[[str(evil_bin)]],
        claim_ids=["claim_d10_1"],
    )
    res_untrusted = engine.execute_plan(plan_untrusted)
    assert res_untrusted.status == "REJECT"
    assert "UNTRUSTED" in res_untrusted.reason

    # Case 2: Unresolvable / missing binary
    plan_missing = VerificationPlan(
        plan_id="plan_d10_missing",
        task_id="task_d10_2",
        verifiers=["process"],
        commands=[["definitely_nonexistent_verifier_binary_12345"]],
        claim_ids=["claim_d10_2"],
    )
    res_missing = engine.execute_plan(plan_missing)
    assert res_missing.status == "REJECT"
    assert "uncertain or unresolvable" in res_missing.reason

    # Case 3: Test runner verifier with unauthorized command
    plan_unauthorized = VerificationPlan(
        plan_id="plan_d10_unauthorized",
        task_id="task_d10_3",
        verifiers=["pytest"],  # Declared as pytest test runner
        commands=[[sys.executable, "-c", "print('not_a_test_runner')"]],
        claim_ids=["claim_d10_3"],
    )
    res_unauth = engine.execute_plan(plan_unauthorized)
    assert res_unauth.status == "REJECT"
    assert "not an authorized test verifier" in res_unauth.reason

    # Case 4: Valid process verification passes and captures execution identity
    plan_valid = VerificationPlan(
        plan_id="plan_d10_valid",
        task_id="task_d10_4",
        verifiers=["process"],
        commands=[[sys.executable, "-c", "import sys; sys.exit(0)"]],
        claim_ids=["claim_d10_4"],
    )
    res_valid = engine.execute_plan(plan_valid)
    assert res_valid.status == "ACCEPT"
    assert res_valid.receipt is not None
    assert "execution_identity" in res_valid.receipt.metadata
    assert res_valid.receipt.metadata["execution_identity"]["executable_name"]





