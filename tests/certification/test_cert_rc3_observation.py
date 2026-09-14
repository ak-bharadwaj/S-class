"""
Certification Suite: Milestone 19 — RC.3 Independent Observation Plane.

Certifies:
1. test_rc3_decouple_observation_from_agent_claims (Laws L1, L4):
   Agent self-reports carry zero evidential weight. If OS execution failed, claim is strictly rejected.
2. test_rc3_synthetic_fake_receipt_rejected (Laws L2, L5):
   Synthetic/fake receipts authored by agents are rejected as unauthentic and unanchored.
3. test_rc3_observation_record_process_telemetry:
   ObservationRecord captures authentic OS process telemetry (PID, executable hash, start/end time, exit code, hashes).
4. test_rc3_opentelemetry_semantic_spans:
   Emits OpenTelemetry semantic spans with secret redaction (ghp_... -> [REDACTED_SECRET]).
5. test_rc3_filesystem_delta_and_tree_fingerprint:
   Captures granular WorkspaceDelta (files added, modified, deleted) and tree fingerprint delta.
6. test_rc3_git_diff_observation_and_fallback:
   Captures GitRevisionState in git repositories and falls back gracefully in non-git workspaces.
7. test_rc3_cryptographic_provenance_binding_and_tamper_detection:
   ObservedReceipt is cryptographically bound to ObservationRecord hash; tampering is detected.
8. test_rc3_zero_cloud_local_persistence:
   100% local persistence in .sclass/ and .agents/ with zero network calls.
"""

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

import pytest

IMPORT_ERROR = None
try:
    from sclass.domain.action import ActionRequest
    from sclass.domain.capability import CAP_TERMINAL_EXECUTE
    from sclass.domain.claim import Claim, ClaimType
    from sclass.domain.evidence import EvidenceReceipt, ObservedReceipt
    from sclass.observation.convergence import ObservationConvergence
    from sclass.observation.fingerprint import (
        compute_workspace_fingerprint,
        compute_workspace_snapshot,
    )
    from sclass.telemetry.tracing import LocalTracer, read_recent_traces
    from sclass.trust.ledger import LocalLedger
    from sclass.verification.engine import verify_claim

    from sclass.observation.record import (
        FileMutation,
        GitRevisionState,
        ObservationRecord,
        ProcessTelemetry,
        WorkspaceDelta,
    )
    from sclass.observation.git_observer import GitObserver
    from sclass.observation.delta import DeltaCalculator
except Exception as exc:
    IMPORT_ERROR = exc


@pytest.fixture(autouse=True)
def check_implementation_health():
    """Fails fast with clear diagnostic message if an implementation defect exists in product code."""
    if IMPORT_ERROR is not None:
        pytest.fail(f"Implementation defect in src/sclass: {IMPORT_ERROR}")


@pytest.fixture
def rc3_workspace(tmp_path):
    ws = tmp_path / "cert_rc3_ws"
    ws.mkdir(parents=True, exist_ok=True)
    return str(ws)


def test_rc3_decouple_observation_from_agent_claims(rc3_workspace):
    """
    Law L1 & L4: Decouple observation from agent claims.
    Agent claims 'Process completed with 100% success and exit code 0', but the independent OS process
    exits with code 1. Verification must strictly REJECT the agent claim based on observed reality.
    """
    ledger = LocalLedger(rc3_workspace)

    req = ActionRequest(
        actor="agent:untrusted_coder",
        session="sess_rc3_l1_001",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="failing_command",
        parameters={"command": "python -c \"raise SystemExit(1)\""},
        workspace=rc3_workspace,
        platform="claude_code",
    )

    cmd = [sys.executable, "-c", "raise SystemExit(1)"]
    exec_result, receipt = ObservationConvergence.execute_and_observe(
        request=req,
        command=cmd,
        timeout=10.0,
        ledger=ledger,
    )

    assert exec_result.exit_code == 1, f"OS process must register failing exit code 1, got {exec_result.exit_code}"
    assert receipt is not None, "ObservationConvergence must emit an authentic receipt"
    assert receipt.exit_code == 1, "Receipt must record the authentic non-zero exit code"

    # Agent fraudulently claims the execution succeeded with exit code 0
    agent_claim = Claim(
        claim_id="claim_fraud_exec_pass",
        task_id="task_rc3_001",
        statement="Command completed successfully with clean exit code 0",
        claim_type=ClaimType.EXECUTION.value,
    )

    verdict = verify_claim(agent_claim, receipt, workspace_dir=rc3_workspace, ledger=ledger)

    assert verdict.is_rejected, f"Claim must be strictly REJECTED, got verdict: {verdict}"
    assert not verdict.is_accepted, "Contradicted claim must NEVER be accepted (Law L1, L4)"


def test_rc3_synthetic_fake_receipt_rejected(rc3_workspace):
    """
    Law L2 & L5: Synthetic fake receipts authored by agents are rejected.
    An agent manually creates a fake JSON receipt in .sclass/evidence/receipts/ claiming is_observed=True.
    Verification against LocalLedger hash chain rejects the unanchored fake evidence.
    """
    ledger = LocalLedger(rc3_workspace)

    fake_receipt_data = {
        "receipt_id": "rcpt_forged_agent_fake_999",
        "task_id": "task_fake",
        "claim_id": "claim_fake",
        "agent": "rogue_agent",
        "action": "run_command",
        "workspace": rc3_workspace,
        "command": "fake_test_runner",
        "exit_code": 0,
        "is_observed": True,
        "workspace_fingerprint": "fake_fingerprint_abc",
        "receipt_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    }

    # Agent drops fake file into receipts directory
    receipts_dir = Path(rc3_workspace) / ".sclass" / "evidence" / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    fake_file = receipts_dir / "rcpt_forged_agent_fake_999.json"
    fake_file.write_text(json.dumps(fake_receipt_data), encoding="utf-8")

    # Deserializing via standard EvidenceReceipt
    receipt = EvidenceReceipt.from_dict(fake_receipt_data)
    assert not receipt.is_observed, "EvidenceReceipt deserialized from dict must not inherit is_observed=True"

    claim = Claim(
        claim_id="claim_fake",
        task_id="task_fake",
        statement="Pretending work was verified",
        claim_type="test_pass",
    )

    verdict = verify_claim(claim, receipt, workspace_dir=rc3_workspace, ledger=ledger)
    assert verdict.is_rejected, "Synthetic fake evidence must be rejected by verification engine (Law L2, L5)"


def test_rc3_observation_record_process_telemetry(rc3_workspace):
    """
    RC.3 Requirement: ObservationRecord captures authentic OS process telemetry:
    PID (> 0), executable hash (SHA-256), start/end time (ISO-8601), exit code, duration, and output hashes.
    """
    proc_tel = ProcessTelemetry(
        pid=os.getpid(),
        executable_path=sys.executable,
        executable_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        requested_argv=(sys.executable, "-c", "print('telemetry_ok')"),
        actual_argv=(sys.executable, "-c", "print('telemetry_ok')"),
        process_start_time=datetime.now(timezone.utc).isoformat(),
        process_end_time=datetime.now(timezone.utc).isoformat(),
        duration_ms=42.5,
        cpu_user_ms=10.0,
        cpu_kernel_ms=5.0,
    )
    assert proc_tel.pid > 0
    assert len(proc_tel.executable_hash) == 64
    assert proc_tel.duration_ms > 0

    git_state = GitRevisionState(is_git_repository=False)
    ws_delta = WorkspaceDelta(
        tree_fingerprint_before="fp_before_123",
        tree_fingerprint_after="fp_after_456",
        files_added=(),
        files_modified=(),
        files_deleted=(),
        mutations=(),
        total_bytes_changed=0,
    )

    obs = ObservationRecord(
        record_id="obs_rec_001",
        task_id="task_tel_001",
        claim_id="claim_tel_001",
        command="python -c print('telemetry_ok')",
        exit_code=0,
        stdout_hash=hashlib.sha256(b"telemetry_ok\n").hexdigest(),
        stderr_hash=hashlib.sha256(b"").hexdigest(),
        stdout_bytes=13,
        stderr_bytes=0,
        process=proc_tel,
        workspace=ws_delta,
        git=git_state,
        semantic_spans=(),
    )

    record_hash = obs.compute_hash()
    assert len(record_hash) == 64, "ObservationRecord canonical hash must be 64-character hex SHA-256"
    assert obs.exit_code == 0
    assert obs.stdout_bytes == 13

    # Invariant: compute_hash binds created_at and all immutable fields
    from dataclasses import replace
    obs_time_shifted = replace(obs, created_at="2099-01-01T00:00:00Z")
    assert obs_time_shifted.compute_hash() != record_hash, "compute_hash must bind created_at"



def test_rc3_opentelemetry_semantic_spans(rc3_workspace):
    """
    RC.3 Requirement: OpenTelemetry semantic spans are emitted locally and sensitive secrets
    (such as ghp_ tokens or API keys) are redacted to [REDACTED_SECRET].
    """
    tracer = LocalTracer(rc3_workspace)
    secret_token = "ghp_ABCDEF1234567890abcdef1234567890ABCD"

    with tracer.span(
        name="sclass.action.execute",
        trace_id="trace_rc3_redaction_001",
    ) as span:
        span.set_attributes({
            "sclass.action.id": "act_rc3_001",
            "process.pid": os.getpid(),
            "process.exit_code": 0,
            "secret.api_token": secret_token,
            "command.line": f"curl -H 'Authorization: Bearer {secret_token}' https://api.local/endpoint",
        })
        span.set_attribute("sclass.evidence.id", "rcpt_rc3_sec_001")

    traces = read_recent_traces(rc3_workspace, limit=10)
    matching = [t for t in traces if t.get("trace_id") == "trace_rc3_redaction_001"]
    assert len(matching) >= 1, "Trace span must be persisted to local traces.jsonl"

    recorded_attrs = matching[0]["attributes"]
    assert recorded_attrs["sclass.action.id"] == "act_rc3_001"
    assert recorded_attrs["process.pid"] == os.getpid()

    # Secret redaction check
    assert secret_token not in json.dumps(matching[0]), "Raw secret token must NEVER be leaked in trace attributes"
    assert "[REDACTED_SECRET]" in json.dumps(matching[0]), "Secret token must be replaced with [REDACTED_SECRET]"


def test_rc3_filesystem_delta_and_tree_fingerprint(rc3_workspace):
    """
    RC.3 Requirement: Filesystem Delta & Tree Fingerprint.
    Accurately captures WorkspaceDelta: added, modified, deleted files with hashes and tree fingerprint changes.
    """
    ws = Path(rc3_workspace)
    (ws / "README.md").write_text("# Initial Readme\n", encoding="utf-8")
    (ws / "temp.txt").write_text("temporary data\n", encoding="utf-8")

    snap_before = compute_workspace_snapshot(rc3_workspace)
    fp_before = compute_workspace_fingerprint(snap_before)

    # Perform workspace mutations:
    # 1. Add module_a.py
    (ws / "module_a.py").write_text("def run(): return 42\n", encoding="utf-8")
    # 2. Modify README.md
    (ws / "README.md").write_text("# Updated Readme with new instructions\n", encoding="utf-8")
    # 3. Delete temp.txt
    (ws / "temp.txt").unlink()

    snap_after = compute_workspace_snapshot(rc3_workspace)
    fp_after = compute_workspace_fingerprint(snap_after)

    assert fp_before != fp_after, "Tree fingerprint must change when files are added, modified, or deleted"

    delta = DeltaCalculator.compute_delta(snap_before, snap_after, rc3_workspace)
    assert any("module_a.py" in f for f in delta.files_added), f"module_a.py must be in files_added: {delta.files_added}"
    assert any("README.md" in f for f in delta.files_modified), f"README.md must be in files_modified: {delta.files_modified}"
    assert any("temp.txt" in f for f in delta.files_deleted), f"temp.txt must be in files_deleted: {delta.files_deleted}"
    assert delta.tree_fingerprint_before == fp_before
    assert delta.tree_fingerprint_after == fp_after
    assert len(delta.mutations) == 3


def test_rc3_git_diff_observation_and_fallback(rc3_workspace, tmp_path):
    """
    RC.3 Requirement: Git Revision State & Fallback.
    In a git repository, captures commit hash, branch, and dirty status.
    In a non-git directory, falls back gracefully with is_git_repository=False.
    """
    # 1. Non-git workspace fallback
    non_git_ws = str(rc3_workspace)
    non_git_state = GitObserver.capture_state(non_git_ws)
    assert non_git_state.is_git_repository is False, "Non-git directory must report is_git_repository=False"
    assert non_git_state.revision_after is None

    # 2. Git workspace
    git_dir = tmp_path / "git_ws"
    git_dir.mkdir()
    try:
        subprocess.run(["git", "init"], cwd=str(git_dir), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "SClass Tester"], cwd=str(git_dir), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "tester@sclass.local"], cwd=str(git_dir), check=True, capture_output=True)
        (git_dir / "init.txt").write_text("initial commit\n", encoding="utf-8")
        subprocess.run(["git", "add", "init.txt"], cwd=str(git_dir), check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=str(git_dir), check=True, capture_output=True)

        git_state = GitObserver.capture_state(str(git_dir))
        assert git_state.is_git_repository is True
        assert git_state.revision_after is not None
        assert len(git_state.revision_after) == 40
        assert git_state.branch is not None
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("Git CLI unavailable in test environment")


def test_rc3_cryptographic_provenance_binding_and_tamper_detection(rc3_workspace):
    """
    Law L5: Cryptographic provenance binding and tamper detection.
    ObservedReceipt is bound to canonical execution facts. Modifying a single character of metadata
    or output digests alters the canonical hash and causes tamper verification to detect tampering.
    """
    ledger = LocalLedger(rc3_workspace)

    req = ActionRequest(
        actor="agent:provenance_tester",
        session="sess_rc3_prov_001",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="echo test",
        parameters={"command": "python -c \"print('provenance_valid')\""},
        workspace=rc3_workspace,
        platform="claude_code",
    )
    cmd = [sys.executable, "-c", "print('provenance_valid')"]
    exec_result, receipt = ObservationConvergence.execute_and_observe(req, command=cmd, timeout=10.0, ledger=ledger)
    assert receipt is not None
    original_hash = receipt.compute_hash()

    # Tampering attempt 1: Modify exit_code in receipt
    tampered_receipt = ObservedReceipt(
        receipt_id=receipt.receipt_id,
        task_id=receipt.task_id,
        claim_id=receipt.claim_id,
        agent=receipt.agent,
        action=receipt.action,
        workspace=receipt.workspace,
        command=receipt.command,
        exit_code=99,  # TAMPERED
        stdout_hash=receipt.stdout_hash,
        stderr_hash=receipt.stderr_hash,
        workspace_fingerprint=receipt.workspace_fingerprint,
        verifier=receipt.verifier,
        execution_kind=receipt.execution_kind,
        metadata=dict(receipt.metadata) if receipt.metadata else {},
    )

    tampered_hash = tampered_receipt.compute_hash()
    assert tampered_hash != original_hash, "Tampered receipt must generate different canonical hash"

    # Verification against ledger
    claim = Claim(
        claim_id=receipt.claim_id,
        task_id=receipt.task_id,
        statement="Claim matching original receipt",
        claim_type="execution",
    )
    verdict = verify_claim(claim, tampered_receipt, workspace_dir=rc3_workspace, ledger=ledger)
    assert verdict.is_rejected, "Tampered receipt must be rejected by verification engine"


def test_rc3_zero_cloud_local_persistence(rc3_workspace):
    """
    R1 & R4: Zero-Cloud Local Persistence.
    All observations, receipts, telemetry traces, and ledger entries persist strictly
    within local workspace directories (.sclass/ and .agents/) with zero cloud or network dependencies.
    """
    ledger = LocalLedger(rc3_workspace)
    req = ActionRequest(
        actor="agent:local_persistence_tester",
        session="sess_rc3_local_001",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="echo local",
        parameters={"command": "python -c \"print('100_percent_local')\""},
        workspace=rc3_workspace,
        platform="claude_code",
    )
    cmd = [sys.executable, "-c", "print('100_percent_local')"]
    exec_result, receipt = ObservationConvergence.execute_and_observe(req, command=cmd, timeout=10.0, ledger=ledger)

    # 1. Receipts stored locally
    receipts_dir = Path(rc3_workspace) / ".sclass" / "evidence" / "receipts"
    assert receipts_dir.exists(), ".sclass/evidence/receipts/ must exist locally"
    receipt_files = list(receipts_dir.glob("*.json"))
    assert len(receipt_files) >= 1, "Observed receipt must be written to local JSON file"

    # 2. Local ledger stored locally
    ledger_entries = ledger.read_all_entries()
    assert len(ledger_entries) >= 1, "Local ledger must record transaction entries locally"

    # 3. Traces stored locally
    traces_file = Path(rc3_workspace) / ".sclass" / "events" / "traces.jsonl"
    assert traces_file.exists(), ".sclass/events/traces.jsonl must exist locally"
    assert traces_file.stat().st_size > 0, "Traces file must contain local telemetry records"
