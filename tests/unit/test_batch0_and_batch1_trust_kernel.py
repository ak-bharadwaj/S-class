"""
Authoritative Test Suite for Batch 0 and Batch 1:
- Batch 0: Single authoritative source tree, secret/env hygiene, context shrink, invariants.
- Batch 1: Fail-closed trust fallback, ExecutionIdentity with real process chain,
           platform identity, observation lifecycle state machine, immutable evidence
           dependency graph, fail-closed handoff reads, verification state machine.
"""

import os
import sys
import tempfile
import platform
import pytest

from sclass.core.errors import StateTransitionError, ObservationIntegrityError, HandoffIntegrityError
from sclass.verification.verifier_definition import VerifierTrustMode
from sclass.verification.trust_registry import TrustRegistry, TrustPolicy
from sclass.execution.identity import ExecutionIdentity, PlatformSupportStatus
from sclass.execution.chain import analyze_execution_chain
from sclass.observation.lifecycle import ObservationLifecycleTracker, ObservationLifecycleState
from sclass.domain.evidence import EvidenceReceipt, EvidenceDependencies
from sclass.verification.state_machine import VerificationState, VerificationStateMachine
from sclass.context.handoff import HandoffAssembler


# ====================================================================
# BATCH 0 TESTS
# ====================================================================

def test_batch0_1_authoritative_package_tree():
    """Verify src/sclass is the sole source tree and root sclass/ is eliminated."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    root_sclass = os.path.join(root_dir, "sclass")
    src_sclass = os.path.join(root_dir, "src", "sclass")

    assert os.path.isdir(src_sclass), "src/sclass must exist as authoritative tree"
    assert not os.path.isdir(root_sclass), "Root sclass/ must be eliminated to prevent drift"

    import sclass.api
    import sclass.policy
    import sclass.daemon
    import sclass.control
    import sclass.verification

    assert "src" in sclass.__file__ or "src" in sys.modules["sclass"].__file__


def test_batch0_2_env_hygiene_and_gitignore():
    """Verify .env and .env.local are not tracked and .env.example contains variable names only."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    env_example = os.path.join(root_dir, ".env.example")
    gitignore = os.path.join(root_dir, ".gitignore")

    assert os.path.isfile(env_example), ".env.example must exist"
    assert os.path.isfile(gitignore), ".gitignore must exist"

    with open(env_example, "r", encoding="utf-8") as f:
        content = f.read()
    # Ensure no values are set in .env.example (variable names only)
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            assert line.endswith("="), f"Line in .env.example has a value instead of name only: {line}"

    with open(gitignore, "r", encoding="utf-8") as f:
        gi_content = f.read()
    assert ".env" in gi_content
    assert ".env.local" in gi_content
    assert ".env.*" in gi_content
    assert "!.env.example" in gi_content


def test_batch0_3_and_4_shrunk_agent_instructions_and_invariants():
    """Verify AGENTS.md and GEMINI.md are concise (<15KB) and invariants.md contains I1-I10."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    agents_md = os.path.join(root_dir, "AGENTS.md")
    gemini_md = os.path.join(root_dir, "GEMINI.md")
    invariants_md = os.path.join(root_dir, "docs", "architecture", "invariants.md")

    assert os.path.getsize(agents_md) < 15000, "AGENTS.md must not be polluted with 400KB bloat"
    assert os.path.getsize(gemini_md) < 15000, "GEMINI.md must not be polluted with 400KB bloat"
    assert os.path.isfile(invariants_md), "docs/architecture/invariants.md must exist"

    with open(invariants_md, "r", encoding="utf-8") as f:
        inv_text = f.read()
    for i in range(1, 11):
        assert f"I{i}:" in inv_text, f"Missing invariant I{i} in invariants.md"


# ====================================================================
# BATCH 1 TESTS
# ====================================================================

def test_batch1_1_fail_closed_trust_fallback(tmp_path):
    """Verify unknown absolute path returns UNKNOWN, never SYSTEM_TRUSTED."""
    registry = TrustRegistry()
    
    ws_dir = str(tmp_path / "workspace")
    os.makedirs(ws_dir, exist_ok=True)
    # An unrecognized absolute path outside system/workspace/user/temp dirs
    unknown_bin = "C:\\custom_vendor\\rogue_runner.exe" if os.name == "nt" else "/custom_vendor/rogue_runner"
    
    mode = registry.classify_binary_trust(unknown_bin, workspace_dir=ws_dir)
    assert mode == VerifierTrustMode.UNKNOWN, f"Expected UNKNOWN for rogue binary, got {mode}"

    # A binary in an untrusted directory (such as temp) outside workspace resolves to UNTRUSTED
    temp_bin = str(tmp_path / "other_dir" / "temp_runner.exe")
    assert registry.classify_binary_trust(temp_bin, workspace_dir=ws_dir) == VerifierTrustMode.UNTRUSTED

    # Explicit trusted path resolves to TRUSTED
    registry.mark_trusted_path(unknown_bin)
    mode_trusted = registry.classify_binary_trust(unknown_bin, workspace_dir=ws_dir)
    assert mode_trusted == VerifierTrustMode.TRUSTED

    # Explicit trusted hash resolves to TRUSTED
    hash_test = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    registry.mark_trusted_hash(hash_test)
    mode_hash = registry.classify_binary_trust("/some/arbitrary/path", binary_hash=hash_test)
    assert mode_hash == VerifierTrustMode.TRUSTED

    # Sibling directory prefix attack: /workspace_attacker must NEVER match /workspace
    sibling_bin = "C:\\project_attacker\\pytest.exe" if os.name == "nt" else "/project_attacker/pytest"
    assert registry.classify_binary_trust(sibling_bin, workspace_dir="C:\\project" if os.name == "nt" else "/project") == VerifierTrustMode.UNKNOWN

    # Sibling in temp directory resolves to UNTRUSTED (outside workspace in temp)
    sibling_temp = str(tmp_path / "workspace_attacker" / "pytest.exe")
    assert registry.classify_binary_trust(sibling_temp, workspace_dir=ws_dir) == VerifierTrustMode.UNTRUSTED

    # Windows NTFS Alternate Data Stream attack: file.txt:evil.exe must fail closed to UNKNOWN
    ads_bin = os.path.join(ws_dir, "clean.txt:evil.exe")
    assert registry.classify_binary_trust(ads_bin, workspace_dir=ws_dir) == VerifierTrustMode.UNKNOWN

    # Direct ExecutionIdentity consumption
    from sclass.execution.identity import ExecutionIdentity
    ident = ExecutionIdentity(
        requested_argv=("pytest",),
        actual_argv=("pytest",),
        executable_name="pytest",
        executable_path=unknown_bin,
        executable_hash=hash_test,
        pid=1234,
        parent_pid=1,
        process_start_time="2026-09-13T00:00:00Z",
        cwd=ws_dir,
        environment_digest="digest",
        execution_mode="HOST_ARGV",
    )
    # With trusted hash, execution object resolves to TRUSTED
    assert registry.classify_binary_trust(execution=ident) == VerifierTrustMode.TRUSTED


def test_batch1_2_and_3_execution_identity_and_chain(tmp_path):
    """Verify ExecutionIdentity captures all required dimensions and chain identifies modern runners."""
    identity = ExecutionIdentity.capture(
        command_argv=["uv", "run", "pytest", "tests/"],
        cwd=str(tmp_path),
        pid=os.getpid(),
    )

    assert identity.pid == os.getpid()
    assert identity.ppid is not None or hasattr(identity, "parent_pid")
    assert identity.argv == ("uv", "run", "pytest", "tests/")
    assert identity.cwd == str(tmp_path)
    assert identity.environment_fingerprint
    assert identity.platform == platform.system()
    assert identity.platform_support_status in (PlatformSupportStatus.SUPPORTED.value, PlatformSupportStatus.DEGRADED.value)

    assert len(identity.parent_chain) >= 1

    # Chain analysis for modern tools with options and flags
    chain_uv = analyze_execution_chain(["uv", "run", "pytest", "tests/"])
    assert chain_uv.launcher == "uv"
    assert chain_uv.actual_child == "pytest"
    assert chain_uv.verifier == "pytest"
    assert "uv" in chain_uv.describe_chain()

    # uv run with flags like --isolated
    chain_uv_isolated = analyze_execution_chain(["uv", "run", "--isolated", "pytest", "tests/"])
    assert chain_uv_isolated.launcher == "uv"
    assert chain_uv_isolated.verifier == "pytest"

    # uv run with python -m pytest
    chain_uv_py = analyze_execution_chain(["uv", "run", "python", "-m", "pytest", "tests/"])
    assert chain_uv_py.launcher == "uv"
    assert chain_uv_py.interpreter == "python"
    assert chain_uv_py.verifier == "pytest"

    chain_poetry = analyze_execution_chain(["poetry", "run", "pytest", "tests/unit"])
    assert chain_poetry.launcher == "poetry"
    assert chain_poetry.verifier == "pytest"

    chain_npx = analyze_execution_chain(["npx", "jest", "--coverage"])
    assert chain_npx.launcher == "npx"
    assert chain_npx.verifier == "jest"

    chain_docker = analyze_execution_chain(["docker", "run", "-v", ".:/app", "test-image", "pytest"])
    assert chain_docker.launcher == "docker"
    assert chain_docker.verifier == "pytest"

    # docker run with multiple flags and trailing arguments
    chain_docker_rm = analyze_execution_chain(["docker", "run", "--rm", "-v", ".:/app", "image:latest", "pytest", "tests/"])
    assert chain_docker_rm.launcher == "docker"
    assert chain_docker_rm.verifier == "pytest"

    # shell -c inline script unwrapping
    chain_bash_c = analyze_execution_chain(["bash", "-c", "pytest tests/"])
    assert chain_bash_c.launcher == "bash"
    assert chain_bash_c.verifier == "pytest"


def test_batch1_4_platform_identity():
    """Verify authoritative process identity explicitly records platform support status."""
    identity = ExecutionIdentity(
        requested_argv=("pytest",),
        actual_argv=("pytest",),
        executable_name="pytest",
        executable_path=sys.executable,
        executable_hash="abc123hash",
        pid=9999,
        parent_pid=1000,
        process_start_time="2026-09-13T00:00:00Z",
        cwd=os.getcwd(),
        environment_digest="digest",
        execution_mode="HOST_ARGV",
        platform="Windows",
        platform_support_status="supported",
    )

    assert identity.platform == "Windows"
    assert identity.platform_support_status == "supported"
    d = identity.to_dict()
    assert d["platform"] == "Windows"
    assert d["platform_support_status"] == "supported"


def test_batch1_5_observation_lifecycle_state_machine():
    """Verify formal lifecycle monotonic progression and rejection of illegal transitions."""
    tracker = ObservationLifecycleTracker(ObservationLifecycleState.REQUESTED)
    assert tracker.current_state == ObservationLifecycleState.REQUESTED

    # Illegal transition: REQUESTED -> VERIFIED directly
    with pytest.raises(ObservationIntegrityError):
        tracker.transition_to(ObservationLifecycleState.VERIFIED)

    # Formal legal lifecycle
    tracker.transition_to(ObservationLifecycleState.AUTHORIZED, "Policy passed")
    assert tracker.current_state == ObservationLifecycleState.AUTHORIZED

    tracker.transition_to(ObservationLifecycleState.STARTED, "Subprocess started")
    assert tracker.current_state == ObservationLifecycleState.STARTED

    tracker.transition_to(ObservationLifecycleState.RUNNING, "Process running")
    assert tracker.current_state == ObservationLifecycleState.RUNNING

    # Illegal transition: RUNNING -> VERIFIED
    with pytest.raises(ObservationIntegrityError):
        tracker.transition_to(ObservationLifecycleState.VERIFIED)

    tracker.transition_to(ObservationLifecycleState.EXITED, "Process exited with 0")
    assert tracker.current_state == ObservationLifecycleState.EXITED

    tracker.transition_to(ObservationLifecycleState.OBSERVED, "Outputs and hashes captured")
    assert tracker.current_state == ObservationLifecycleState.OBSERVED

    tracker.transition_to(ObservationLifecycleState.ANCHORED, "Anchored into LocalLedger")
    assert tracker.current_state == ObservationLifecycleState.ANCHORED

    tracker.transition_to(ObservationLifecycleState.VERIFIED, "Independently verified")
    assert tracker.current_state == ObservationLifecycleState.VERIFIED

    # Mutation invalidates verified state
    tracker.transition_to(ObservationLifecycleState.INVALIDATED, "Workspace modified after verification")
    assert tracker.current_state == ObservationLifecycleState.INVALIDATED


def test_batch1_6_immutable_evidence_dependency_graph(tmp_path):
    """Verify EvidenceDependencies are bound to receipt and mutation invalidates evidence."""
    ws = tmp_path / "dep_workspace"
    ws.mkdir()
    (ws / "app.py").write_text("print('hello')", encoding="utf-8")

    from sclass.observation.fingerprint import compute_workspace_snapshot, compute_workspace_fingerprint
    snap = compute_workspace_snapshot(str(ws))
    fp = compute_workspace_fingerprint(snap)

    deps = EvidenceDependencies(
        argv=("pytest", "tests/"),
        workspace_fingerprint=fp,
        relevant_files=("app.py",),
        verifier="pytest",
    )

    receipt = EvidenceReceipt(
        receipt_id="rcpt_dep_test",
        task_id="T1",
        claim_id="C1",
        agent="agent-1",
        action="test",
        workspace=str(ws),
        workspace_fingerprint=fp,
        dependencies=deps,
    )

    # Initial state is valid
    is_valid, reason = receipt.validate_dependencies(str(ws))
    assert is_valid
    assert reason is None

    # Mutate workspace
    (ws / "app.py").write_text("print('tampered')", encoding="utf-8")
    is_valid_mut, reason_mut = receipt.validate_dependencies(str(ws))
    assert not is_valid_mut
    assert "Workspace mutation detected" in reason_mut


def test_batch1_7_fail_closed_handoff_reads(tmp_path, monkeypatch):
    """Verify database access failure raises HandoffIntegrityError rather than pretending 0 failures."""
    ws = str(tmp_path / "broken_db_ws")
    os.makedirs(ws, exist_ok=True)
    assembler = HandoffAssembler(ws)

    # Force database failure by breaking repository store connection
    def broken_connection():
        raise RuntimeError("Database disk corrupted or unreachable")

    monkeypatch.setattr(assembler.repo.store, "get_connection", broken_connection)

    with pytest.raises(HandoffIntegrityError) as exc_info:
        assembler.assemble(project_id="PROJ-FAIL")

    assert "Database access failure" in str(exc_info.value)

    # CheckpointManager.create_checkpoint also fails closed with HandoffIntegrityError
    from sclass.context.checkpoint import CheckpointManager
    from sclass.state.tasks import StateRepository

    def broken_list_tasks(*args, **kwargs):
        raise RuntimeError("SQLite database file corrupt")

    monkeypatch.setattr(StateRepository, "list_tasks", broken_list_tasks)
    with pytest.raises(HandoffIntegrityError) as chk_exc:
        CheckpointManager.create_checkpoint(workspace_dir=ws)
    assert "Database access failure" in str(chk_exc.value)


def test_batch1_8_verification_state_machine(tmp_path):
    """Verify strict verification state machine: CLAIMED -> ... -> ACCEPTED -> INVALIDATED and engine integration."""
    sm = VerificationStateMachine(claim_id="claim_test_101")
    assert sm.current_state == VerificationState.CLAIMED

    # Hard invariant: Direct CLAIMED -> ACCEPTED is strictly rejected
    with pytest.raises(StateTransitionError) as exc:
        sm.transition_to(VerificationState.ACCEPTED)
    assert "Illegal verification state transition" in str(exc.value)

    # Monotonic legal path
    sm.transition_to(VerificationState.EVIDENCE_REQUIRED, "Awaiting evidence receipt")
    assert sm.current_state == VerificationState.EVIDENCE_REQUIRED

    # Direct EVIDENCE_REQUIRED -> ACCEPTED is also rejected
    with pytest.raises(StateTransitionError):
        sm.transition_to(VerificationState.ACCEPTED)

    sm.transition_to(VerificationState.OBSERVED, "Authoritative receipt observed")
    assert sm.current_state == VerificationState.OBSERVED

    sm.transition_to(VerificationState.VERIFICATION_RUNNING, "Running verifiers")
    assert sm.current_state == VerificationState.VERIFICATION_RUNNING

    sm.transition_to(VerificationState.ACCEPTED, "All checks passed")
    assert sm.current_state == VerificationState.ACCEPTED

    # Mutation invalidates accepted claim
    sm.transition_to(VerificationState.INVALIDATED, "Workspace mutated")
    assert sm.current_state == VerificationState.INVALIDATED

    # Verify engine integration: verify_claim attaches and transitions state_machine
    from sclass.domain.claim import Claim
    from sclass.verification.engine import verify_claim, check_staleness
    from sclass.domain.claim import ClaimType
    from sclass.trust.ledger import LocalLedger
    from sclass.observation.fingerprint import compute_workspace_snapshot, compute_workspace_fingerprint

    ws_dir = str(tmp_path / "engine_sm_ws")
    os.makedirs(ws_dir, exist_ok=True)
    ledger = LocalLedger(workspace_dir=ws_dir)

    claim = Claim(
        claim_id="claim_engine_sm",
        task_id="T_SM",
        statement="Executed command",
        claim_type=ClaimType.EXECUTION.value,
        metadata={"agent": "test_agent"},
    )

    # Unobserved evidence is rejected and state machine moves to REJECTED
    verdict_none = verify_claim(claim=claim, evidence=None, workspace_dir=ws_dir, ledger=ledger)
    assert verdict_none.status == "REJECT"
    assert verdict_none.state_machine is not None
    assert verdict_none.state_machine.current_state == VerificationState.REJECTED

    # Valid observed receipt advances state machine to ACCEPTED
    snap = compute_workspace_snapshot(ws_dir)
    fp = compute_workspace_fingerprint(snap)
    receipt = EvidenceReceipt(
        receipt_id="rcpt_sm_test",
        task_id="T_SM",
        claim_id="claim_engine_sm",
        agent="test_agent",
        action="run_command",
        workspace=ws_dir,
        workspace_fingerprint=fp,
        execution_kind="generic_command",
        verifier="generic",
        exit_code=0,
        is_observed=True,
        metadata={
            "workspace_fingerprint_before": fp,
            "workspace_fingerprint": fp,
        },
    )
    receipt.receipt_hash = receipt.compute_hash()

    # Anchor receipt into ledger
    ledger.append("OBSERVATION", {
        "receipt_id": receipt.receipt_id,
        "receipt_hash": receipt.receipt_hash,
        "fingerprint_before": fp,
        "fingerprint_after": fp,
        "action": "run_command",
        "verifier": "generic",
        "status": "COMPLETED",
    })

    verdict_accepted = verify_claim(claim=claim, evidence=receipt, workspace_dir=ws_dir, ledger=ledger)
    assert verdict_accepted.status == "ACCEPT"
    assert verdict_accepted.state_machine is not None
    assert verdict_accepted.state_machine.current_state == VerificationState.ACCEPTED

    # Subsequent workspace mutation invalidates accepted verification state machine
    with open(os.path.join(ws_dir, "mutation.txt"), "w") as f:
        f.write("modified")

    receipt.state_machine = verdict_accepted.state_machine
    is_fresh, stale_reason = check_staleness(receipt, ws_dir)
    assert not is_fresh
    assert receipt.state_machine.current_state == VerificationState.INVALIDATED
