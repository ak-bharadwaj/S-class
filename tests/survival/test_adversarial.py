"""
S-Class Survival v0: Adversarial Test Suite (tests/survival/test_adversarial.py)

Phase 15: Rigorous adversarial defense against 10 explicit attack vectors:
- Attack 1: Agent claims tests passed, actual exit code = 1 -> REJECT
- Attack 2: Agent fabricates qa_report.json -> REJECT & DENY
- Attack 3: Agent deletes evidence -> DENY
- Attack 4: Agent writes API key -> DENY and secret never appears in logs
- Attack 5: Agent modifies release artifact -> DENY
- Attack 6: Agent modifies high-impact file -> WARN
- Attack 7: Hook crashes -> Expected in enforcement mode: DENY
- Attack 8: Evidence is stale -> REJECT
- Attack 9: Agent changes repository after verification -> previous verification invalidated
- Attack 10: Agent says "done" but produces no evidence -> REJECT
"""

import os
import json
import uuid
import pytest
from datetime import datetime, timezone, timedelta

from sclass.survival.models import (
    AuthorizationRequest,
    AuthorizationDecision,
    EvidenceReceipt,
    ObservedReceipt,
    ProposedEvidence,
    ClaimedEvidence,
    Claim,
    VerificationResult,
    LIFECYCLE_OBSERVED,
    LIFECYCLE_INTEGRITY_VERIFIED,
    LIFECYCLE_CLAIM_VERIFIED,
)
from sclass.survival.authority import authorize, get_path_authority, PathAuthority
from sclass.survival.verification import verify_claim, check_verification_staleness
from sclass.survival.evidence import create_receipt, save_receipt, load_receipt, create_proposed_evidence, observe_command
from sclass.survival.ledger import LocalLedger
from hook_core import HookCore, HookEvent, HookEventType, HookDecision, HookRule
from hook_rules import (
    SecretScannerRule,
    EvidenceIntegrityRule,
    ReleaseGovernanceRule,
    BlastRadiusRule,
    get_default_rules,
)


@pytest.fixture
def test_workspace(tmp_path):
    ws = tmp_path / "survival_workspace"
    ws.mkdir()
    agents_dir = ws / ".agents"
    agents_dir.mkdir()
    (agents_dir / "receipts").mkdir()
    (agents_dir / "ledger").mkdir()
    (agents_dir / "claims").mkdir()
    return str(ws)


def test_attack_1_agent_claims_tests_pass_but_exit_code_is_1(test_workspace):
    """
    Attack 1:
    Agent claims "All tests pass", but the independently observed test execution
    exited with exit code 1.
    Expected: REJECT
    """
    claim = Claim(
        claim_id="claim_001",
        task_id="task_001",
        statement="All tests pass successfully.",
        claim_type="test_pass",
    )

    evidence = create_receipt(
        task_id="task_001",
        claim_id="claim_001",
        agent="claude",
        action="run_pytest",
        workspace=test_workspace,
        command="pytest",
        exit_code=1,  # Failure
        started_at=datetime.now(timezone.utc).isoformat(),
        finished_at=datetime.now(timezone.utc).isoformat(),
        stdout_content="================ 2 failed, 10 passed ================",
        stderr_content="AssertionError: Expected 200, got 500",
        evidence=[{"failed_tests": 2, "passed_tests": 10}],
    )

    ledger = LocalLedger(workspace_dir=test_workspace)
    verdict = verify_claim(claim, evidence, workspace_dir=test_workspace, ledger=ledger)

    assert verdict.status == "REJECT"
    assert verdict.is_rejected is True
    assert "failed" in verdict.reason.lower() or "exit code 1" in verdict.reason.lower()
    assert verdict.observed_exit_code == 1

    # Verify ledger recorded rejection
    entries = ledger.read_all_entries()
    assert len(entries) >= 1
    assert entries[-1]["event"] == "rejection"


def test_attack_2_agent_fabricates_qa_report(test_workspace):
    """
    Attack 2:
    Agent attempts to fabricate or modify .agents/qa_report.json directly.
    Expected:
    1. Pre-action authorization DENIES direct write to protected qa_report.json
    2. Verification REJECTS fabricated evidence lacking valid cryptographic receipt.
    """
    # 1. Authorization Gate defends against agent write
    req = AuthorizationRequest(
        agent="claude",
        platform="claude_code",
        action="file_edit",
        tool="Edit",
        target=os.path.join(test_workspace, ".agents", "qa_report.json"),
        parameters={"content": '{"all_passed": true, "coverage": 100}'},
        workspace=test_workspace,
    )
    auth_decision = authorize(req, mode="enforce")
    assert auth_decision.outcome == "deny"
    assert auth_decision.is_denied is True
    assert "Tampering with protected S-Class authority artifact" in auth_decision.reason

    # 2. HookCore rule defends against write/overwrite
    core = HookCore(workspace_dir=test_workspace, enforcement_mode="enforce")
    core.register_rule(EvidenceIntegrityRule())
    event = HookEvent(
        event_type=HookEventType.PRE_FILE_EDIT,
        workspace_dir=test_workspace,
        platform="claude_code",
        file_path=".agents/qa_report.json",
        tool_args={"content": '{"spoofed": true}'},
    )
    hook_verdict = core.evaluate_event(event)
    assert hook_verdict.decision == HookDecision.DENY

    # 3. Verification engine rejects forged receipt with tampered hash
    claim = Claim(
        claim_id="claim_forge",
        task_id="task_forge",
        statement="QA passed",
        claim_type="test_pass",
    )
    forged_receipt = EvidenceReceipt(
        receipt_id="rcpt_forged",
        task_id="task_forge",
        claim_id="claim_forge",
        agent="attacker",
        action="fake",
        workspace=test_workspace,
        base_commit="abc",
        result_commit="def",
        command="fake",
        exit_code=0,
        started_at="2026-09-13T00:00:00Z",
        finished_at="2026-09-13T00:01:00Z",
        stdout_hash="fake_hash",
        stderr_hash="fake_hash",
        metadata={"receipt_hash": "corrupted_or_forged_hash"},
    )
    verdict = verify_claim(claim, forged_receipt, workspace_dir=test_workspace)
    assert verdict.status == "REJECT"
    assert "tampering detected" in verdict.reason.lower() or "mismatch" in verdict.reason.lower()


def test_attack_3_agent_deletes_evidence(test_workspace):
    """
    Attack 3:
    Agent invokes 'rm' or delete on an evidence artifact or ledger record.
    Expected: DENY
    """
    # Test via canonical authorize()
    req = AuthorizationRequest(
        agent="cursor",
        platform="cursor",
        action="file_edit",
        tool="rm",
        target=os.path.join(test_workspace, ".agents", "ledger", "audit_ledger.jsonl"),
        parameters={"delete": True},
        workspace=test_workspace,
    )
    decision = authorize(req, mode="enforce")
    assert decision.outcome == "deny"
    assert decision.is_denied is True
    assert "Tampering" in decision.reason

    # Test via HookCore EvidenceIntegrityRule
    core = HookCore(workspace_dir=test_workspace, enforcement_mode="enforce")
    core.register_rule(EvidenceIntegrityRule())
    event = HookEvent(
        event_type=HookEventType.PRE_TOOL_USE,
        workspace_dir=test_workspace,
        platform="claude_code",
        tool_name="rm",
        file_path=os.path.join(test_workspace, ".agents", "qa_report.json"),
    )
    verdict = core.evaluate_event(event)
    assert verdict.decision == HookDecision.DENY
    assert "Tampering with evidence artifact" in verdict.reason


def test_attack_4_agent_writes_api_key_and_secret_never_appears_in_logs(test_workspace):
    """
    Attack 4:
    Agent attempts to write an OpenAI / GitHub API key into source code.
    Expected:
    1. DENY
    2. The raw secret string NEVER appears in verdict, reason, diagnostics, or logs.
    """
    raw_secret = "sk-live-0123456789abcdef0123456789abcdef"
    req = AuthorizationRequest(
        agent="claude",
        platform="claude_code",
        action="file_edit",
        target="src/config.py",
        parameters={"content": f'OPENAI_API_KEY = "{raw_secret}"'},
        workspace=test_workspace,
    )
    decision = authorize(req, mode="enforce")
    assert decision.outcome == "deny"
    assert decision.is_denied is True

    # Critical security assertion: secret must NEVER appear in outputs
    assert raw_secret not in decision.reason
    assert raw_secret not in decision.remediation
    assert not any(raw_secret in diag for diag in decision.diagnostics)
    assert "[REDACTED]" in decision.reason

    # Test through HookCore SecretScannerRule
    core = HookCore(workspace_dir=test_workspace, enforcement_mode="enforce")
    core.register_rule(SecretScannerRule())
    event = HookEvent(
        event_type=HookEventType.PRE_TOOL_USE,
        workspace_dir=test_workspace,
        platform="claude_code",
        tool_args={"content": f'ghp_abcdefghijklmnopqrstuvwxyz0123456789'},
    )
    verdict = core.evaluate_event(event)
    assert verdict.decision == HookDecision.DENY
    assert "ghp_abcdefghijklmnopqrstuvwxyz0123456789" not in verdict.reason
    assert "[REDACTED]" in verdict.reason


def test_attack_5_agent_modifies_release_artifact(test_workspace):
    """
    Attack 5:
    Agent modifies release_manifest.json when FSM is not in RELEASE phase.
    Expected: DENY
    """
    # Orchestration state is CODING phase
    state_file = os.path.join(test_workspace, ".agents", "orchestration_state.json")
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump({"currentPhase": "CODING"}, f)

    req = AuthorizationRequest(
        agent="codex",
        platform="codex",
        action="file_edit",
        target="release_manifest.json",
        parameters={"content": '{"version": "2.0.0"}'},
        workspace=test_workspace,
    )
    decision = authorize(req, mode="enforce")
    assert decision.outcome == "deny"
    assert decision.is_denied is True
    assert "forbidden in phase CODING" in decision.reason


def test_attack_6_agent_modifies_high_impact_file(test_workspace):
    """
    Attack 6:
    Agent modifies a file with high blast radius (downstream callers > 10).
    Expected: WARN (with estimated impact wording, not symbol-caller claim)
    """
    import sqlite3
    db_path = os.path.join(test_workspace, ".agents", "codebase_graph.db")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("CREATE TABLE codebase_edges (src_node_id TEXT, dest_node_id TEXT, edge_type TEXT)")
    # Insert 15 callers targeting src/core.py
    for i in range(15):
        cur.execute(
            "INSERT INTO codebase_edges VALUES (?, ?, ?)",
            (f"caller_{i}", "src/core.py:execute", "CALLS"),
        )
    conn.commit()
    conn.close()

    req = AuthorizationRequest(
        agent="cursor",
        platform="cursor",
        action="file_edit",
        target="src/core.py",
        parameters={"content": "def execute(): pass"},
        workspace=test_workspace,
    )
    decision = authorize(req, mode="enforce")
    assert decision.outcome == "warn"
    assert decision.is_warn is True
    assert "Estimated impact:" in decision.reason
    assert "Estimated dependent references:" in decision.reason
    assert "Recommendation:" in decision.reason


def test_attack_7_hook_crashes_fails_closed(test_workspace):
    """
    Attack 7:
    A hook rule throws an unhandled exception or crashes during evaluation.
    Expected in enforcement mode: Fail-closed to DENY (SCLASS-SYS-ERR).
    """
    class CrashingRule(HookRule):
        rule_id = "SCLASS-CRASH"
        def evaluate(self, event: HookEvent):
            raise RuntimeError("Database connection suddenly dropped!")

    core = HookCore(workspace_dir=test_workspace, enforcement_mode="enforce")
    core.register_rule(CrashingRule())

    event = HookEvent(
        event_type=HookEventType.PRE_TOOL_USE,
        workspace_dir=test_workspace,
        platform="claude_code",
        tool_args={"command": "npm install"},
    )
    verdict = core.evaluate_event(event)
    assert verdict.decision == HookDecision.DENY
    assert verdict.rule_id == "SCLASS-SYS-ERR"
    assert "Hook rule evaluation exception" in verdict.reason


def test_attack_8_evidence_is_stale(test_workspace):
    """
    Attack 8:
    Agent produces an evidence receipt from an older repository state,
    while repository HEAD has advanced.
    Expected: REJECT
    """
    claim = Claim(
        claim_id="claim_stale",
        task_id="task_stale",
        statement="Implemented auth endpoints",
        claim_type="feature",
    )

    old_commit = "1111111111111111111111111111111111111111"
    evidence = create_receipt(
        task_id="task_stale",
        claim_id="claim_stale",
        agent="claude",
        action="edit",
        workspace=test_workspace,
        command="git commit -m 'old work'",
        exit_code=0,
        started_at="2026-09-01T10:00:00Z",
        finished_at="2026-09-01T10:05:00Z",
        stdout_content="ok",
        stderr_content="",
        base_commit=old_commit,
        result_commit=old_commit,
        files_changed=["src/auth.py"],
    )

    # Mock git commit check to return advanced HEAD
    import sclass.survival.verification as v_mod
    orig_fn = v_mod._get_git_commit_hash
    try:
        v_mod._get_git_commit_hash = lambda ws: "2222222222222222222222222222222222222222"
        verdict = verify_claim(claim, evidence, workspace_dir=test_workspace)
        assert verdict.status == "REJECT"
        assert "stale" in verdict.reason.lower()
    finally:
        v_mod._get_git_commit_hash = orig_fn


def test_attack_9_agent_changes_repository_after_verification(test_workspace):
    """
    Attack 9:
    Evidence verification succeeded, but then uncommitted code changes or new commits
    were introduced after verification.
    Expected: check_verification_staleness flags the receipt as invalidated.
    """
    evidence = create_receipt(
        task_id="task_009",
        claim_id="claim_009",
        agent="claude",
        action="test",
        workspace=test_workspace,
        command="pytest",
        exit_code=0,
        started_at="2026-09-13T10:00:00Z",
        finished_at="2026-09-13T10:01:00Z",
        stdout_content="all passed",
        stderr_content="",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        result_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        files_changed=["src/api.py"],
        verified=True,
    )

    # Repository was subsequently changed: new file modified after verification
    import sclass.survival.verification as v_mod
    orig_files_fn = v_mod._get_git_changed_files
    try:
        v_mod._get_git_changed_files = lambda ws, commit: ["src/api.py", "src/tampered_payload.py"]
        is_fresh, invalid_reason = check_verification_staleness(evidence, test_workspace)
        assert is_fresh is False
        assert "uncommitted file changes introduced after verification" in invalid_reason
    finally:
        v_mod._get_git_changed_files = orig_files_fn


def test_attack_10_agent_says_done_but_produces_no_evidence(test_workspace):
    """
    Attack 10:
    Agent claims "done" or completion, but produces no EvidenceReceipt (evidence is None).
    Expected: REJECT
    """
    claim = Claim(
        claim_id="claim_empty",
        task_id="task_empty",
        statement="I have finished implementing everything and all tests are passing.",
        claim_type="completion",
    )
    verdict = verify_claim(claim, None, workspace_dir=test_workspace)
    assert verdict.status == "REJECT"
    assert verdict.is_rejected is True
    assert "produced no independently observed evidence receipt" in verdict.reason


# ==============================================================================
# S-Class Red-Team v1 Adversarial Test Suite
# ==============================================================================

def test_attack_family_a_missing_receipt_hash_rejected(test_workspace):
    """
    Finding #2: Missing receipt hash must be REJECT.
    An attacker attempts to bypass integrity checks by omitting receipt_hash.
    Expected: REJECT (no third state).
    """
    claim = Claim(
        claim_id="claim_missing_hash",
        task_id="task_missing_hash",
        statement="All tests pass",
        claim_type="test_pass",
    )

    receipt = EvidenceReceipt(
        receipt_id="rcpt_no_hash",
        task_id="task_missing_hash",
        claim_id="claim_missing_hash",
        agent="attacker",
        action="run_tests",
        workspace=test_workspace,
        base_commit="aaa",
        result_commit="aaa",
        command="pytest",
        exit_code=0,
        started_at="2026-09-13T10:00:00Z",
        finished_at="2026-09-13T10:01:00Z",
        stdout_hash="hash_out",
        stderr_hash="hash_err",
        files_changed=[],
        evidence=[{"passed_tests": 10}],
        metadata={},  # No receipt_hash in metadata
        receipt_hash=None,  # Explicitly missing
    )

    verdict = verify_claim(claim, receipt, workspace_dir=test_workspace)
    assert verdict.status == "REJECT"
    assert verdict.is_rejected is True
    assert "Missing evidence receipt hash" in verdict.reason

    # Also verify load_receipt rejects persisted file with missing receipt_hash
    target = os.path.join(test_workspace, ".agents", "receipts", "rcpt_no_hash.json")
    with open(target, "w", encoding="utf-8") as f:
        data = receipt.to_dict()
        data.pop("receipt_hash", None)
        json.dump(data, f)
    assert load_receipt("rcpt_no_hash", test_workspace) is None


def test_attack_family_a_tamper_evidence_payload_rejected(test_workspace):
    """
    Finding #1: Canonical hash must cover evidence items.
    An attacker changes passed_tests or failed_tests inside evidence while retaining receipt_hash.
    Expected: REJECT.
    """
    claim = Claim(
        claim_id="claim_tamper_ev",
        task_id="task_tamper_ev",
        statement="All tests pass",
        claim_type="test_pass",
    )

    receipt = create_receipt(
        task_id="task_tamper_ev",
        claim_id="claim_tamper_ev",
        agent="claude",
        action="test",
        workspace=test_workspace,
        command="pytest",
        exit_code=0,
        started_at="2026-09-13T10:00:00Z",
        finished_at="2026-09-13T10:01:00Z",
        stdout_content="tests ran",
        stderr_content="",
        evidence=[{"passed_tests": 5, "failed_tests": 2}],
    )

    # Attacker tampers with evidence: fabricates 100 passing tests and 0 failures
    receipt.evidence = [{"passed_tests": 100, "failed_tests": 0}]

    verdict = verify_claim(claim, receipt, workspace_dir=test_workspace)
    assert verdict.status == "REJECT"
    assert "tampering detected" in verdict.reason.lower() or "mismatch" in verdict.reason.lower()


def test_attack_family_a_tamper_metadata_rejected(test_workspace):
    """
    Finding #1: Canonical hash must cover metadata.
    An attacker alters metadata payload while retaining original receipt_hash.
    Expected: REJECT.
    """
    claim = Claim(
        claim_id="claim_tamper_meta",
        task_id="task_tamper_meta",
        statement="Tests pass",
        claim_type="test_pass",
    )

    receipt = create_receipt(
        task_id="task_tamper_meta",
        claim_id="claim_tamper_meta",
        agent="claude",
        action="test",
        workspace=test_workspace,
        command="pytest",
        exit_code=0,
        started_at="2026-09-13T10:00:00Z",
        finished_at="2026-09-13T10:01:00Z",
        stdout_content="ok",
        stderr_content="",
        metadata={"build_env": "production", "runner": "trusted_ci"},
    )

    # Attacker tampers with metadata
    receipt.metadata["runner"] = "compromised_runner"

    verdict = verify_claim(claim, receipt, workspace_dir=test_workspace)
    assert verdict.status == "REJECT"
    assert "tampering detected" in verdict.reason.lower() or "mismatch" in verdict.reason.lower()


def test_attack_family_a_tamper_security_relevant_fields_rejected(test_workspace):
    """
    Finding #1: Verify that every security-relevant field is bound to the canonical hash.
    Mutating any of command, exit_code, files_changed, timestamps, claim_id, or task_id
    triggers hash mismatch rejection.
    """
    claim = Claim(
        claim_id="claim_multi_tamper",
        task_id="task_multi_tamper",
        statement="Verification test",
        claim_type="test_pass",
    )

    receipt = create_receipt(
        task_id="task_multi_tamper",
        claim_id="claim_multi_tamper",
        agent="claude",
        action="test",
        workspace=test_workspace,
        command="pytest",
        exit_code=0,
        started_at="2026-09-13T10:00:00Z",
        finished_at="2026-09-13T10:01:00Z",
        stdout_content="ok",
        stderr_content="",
        files_changed=["src/main.py"],
    )

    # 1. Mutate command
    receipt.command = "pytest --injected"
    assert verify_claim(claim, receipt, workspace_dir=test_workspace).status == "REJECT"
    receipt.command = "pytest"

    # 2. Mutate exit code
    receipt.exit_code = 1
    assert verify_claim(claim, receipt, workspace_dir=test_workspace).status == "REJECT"
    receipt.exit_code = 0

    # 3. Mutate files_changed
    receipt.files_changed = ["src/other.py"]
    assert verify_claim(claim, receipt, workspace_dir=test_workspace).status == "REJECT"
    receipt.files_changed = ["src/main.py"]

    # 4. Mutate task_id
    receipt.task_id = "task_hijacked"
    assert verify_claim(claim, receipt, workspace_dir=test_workspace).status == "REJECT"


def test_attack_family_b_same_file_modification_staleness(test_workspace):
    """
    Finding #3: The stale-verification defense same-file hole.
    Attacker modifies a recorded file (src/auth.py) AFTER verification,
    keeping files_changed the same.
    Content-hash fingerprint must detect this mutation and invalidate verification.
    """
    auth_file = os.path.join(test_workspace, "src", "auth.py")
    os.makedirs(os.path.dirname(auth_file), exist_ok=True)
    with open(auth_file, "w", encoding="utf-8") as f:
        f.write("def authenticate(): return True\n")

    claim = Claim(
        claim_id="claim_same_file",
        task_id="task_same_file",
        statement="Implemented authentication",
        claim_type="feature",
    )

    # Create receipt which fingerprints src/auth.py content hash
    receipt = create_receipt(
        task_id="task_same_file",
        claim_id="claim_same_file",
        agent="claude",
        action="edit",
        workspace=test_workspace,
        command="pytest",
        exit_code=0,
        started_at="2026-09-13T10:00:00Z",
        finished_at="2026-09-13T10:01:00Z",
        stdout_content="ok",
        stderr_content="",
        files_changed=["src/auth.py"],
    )

    assert "src/auth.py" in receipt.file_hashes
    original_file_hash = receipt.file_hashes["src/auth.py"]
    assert len(original_file_hash) == 64

    # Verification initially succeeds
    verdict1 = verify_claim(claim, receipt, workspace_dir=test_workspace)
    assert verdict1.status == "ACCEPT"

    # ATTACK: Attacker alters src/auth.py content after verification
    with open(auth_file, "w", encoding="utf-8") as f:
        f.write("def authenticate(): return False # Tampered backdoor\n")

    # Re-evaluating staleness must flag the same-file modification
    is_fresh, reason = check_verification_staleness(receipt, test_workspace)
    assert is_fresh is False
    assert "Recorded file content changed after verification: src/auth.py" in reason

    # Verifying claim again must REJECT due to staleness
    verdict2 = verify_claim(claim, receipt, workspace_dir=test_workspace)
    assert verdict2.status == "REJECT"
    assert "stale" in verdict2.reason.lower()


def test_attack_family_b_same_file_deletion_staleness(test_workspace):
    """
    Finding #3: Attacker deletes a recorded file after verification.
    Content-hash fingerprint must detect the missing file and flag staleness.
    """
    svc_file = os.path.join(test_workspace, "src", "service.py")
    os.makedirs(os.path.dirname(svc_file), exist_ok=True)
    with open(svc_file, "w", encoding="utf-8") as f:
        f.write("def service(): pass\n")

    receipt = create_receipt(
        task_id="task_del",
        claim_id="claim_del",
        agent="claude",
        action="edit",
        workspace=test_workspace,
        command="pytest",
        exit_code=0,
        started_at="2026-09-13T10:00:00Z",
        finished_at="2026-09-13T10:01:00Z",
        stdout_content="ok",
        stderr_content="",
        files_changed=["src/service.py"],
    )

    # Attacker deletes src/service.py
    os.remove(svc_file)

    is_fresh, reason = check_verification_staleness(receipt, test_workspace)
    assert is_fresh is False
    assert "Recorded file was deleted after verification: src/service.py" in reason


def test_attack_family_c_proposed_vs_observed_evidence_separation(test_workspace):
    """
    Finding #4: Distinguish ObservedReceipt vs ProposedEvidence/ClaimedEvidence.
    Caller-supplied proposed evidence CANNOT satisfy verification gates.
    """
    claim = Claim(
        claim_id="claim_prop",
        task_id="task_prop",
        statement="Tests pass",
        claim_type="test_pass",
    )

    # 1. ProposedEvidence instance rejected
    proposed = create_proposed_evidence(
        statement="I ran tests and all 50 passed",
        exit_code=0,
        files_changed=["src/core.py"],
        evidence=[{"passed_tests": 50}],
    )
    verdict = verify_claim(claim, proposed, workspace_dir=test_workspace)
    assert verdict.status == "REJECT"
    assert "proposed/claimed evidence" in verdict.reason.lower()

    # 2. ClaimedEvidence alias rejected
    claimed = ClaimedEvidence(statement="all good", exit_code=0)
    verdict2 = verify_claim(claim, claimed, workspace_dir=test_workspace)
    assert verdict2.status == "REJECT"
    assert "proposed/claimed evidence" in verdict2.reason.lower()

    # 3. EvidenceReceipt with is_observed=False rejected
    unobserved = EvidenceReceipt(
        receipt_id="rcpt_unobserved",
        task_id="task_prop",
        claim_id="claim_prop",
        agent="attacker",
        action="test",
        workspace=test_workspace,
        base_commit="aaa",
        result_commit="aaa",
        command="pytest",
        exit_code=0,
        started_at="2026-09-13T10:00:00Z",
        finished_at="2026-09-13T10:01:00Z",
        stdout_hash="h1",
        stderr_hash="h2",
        is_observed=False,
    )
    verdict3 = verify_claim(claim, unobserved, workspace_dir=test_workspace)
    assert verdict3.status == "REJECT"
    assert "proposed/claimed evidence" in verdict3.reason.lower()


def test_attack_family_d_lifecycle_immutability(test_workspace):
    """
    Finding #6: Lifecycle separation (OBSERVED -> INTEGRITY VERIFIED -> CLAIM VERIFIED).
    Verified=True and lifecycle transitions must NOT mutate the observation hash.
    """
    claim = Claim(
        claim_id="claim_life",
        task_id="task_life",
        statement="Feature completed",
        claim_type="completion",
    )

    receipt = create_receipt(
        task_id="task_life",
        claim_id="claim_life",
        agent="claude",
        action="run",
        workspace=test_workspace,
        command="echo ok",
        exit_code=0,
        started_at="2026-09-13T10:00:00Z",
        finished_at="2026-09-13T10:01:00Z",
        stdout_content="ok",
        stderr_content="",
    )

    initial_hash = receipt.compute_hash()
    assert receipt.lifecycle_state == LIFECYCLE_OBSERVED
    assert receipt.verified is False

    # Execute verification
    verdict = verify_claim(claim, receipt, workspace_dir=test_workspace)
    assert verdict.status == "ACCEPT"
    assert receipt.verified is True
    assert receipt.lifecycle_state == LIFECYCLE_CLAIM_VERIFIED

    # Observation hash MUST remain identical
    post_verification_hash = receipt.compute_hash()
    assert post_verification_hash == initial_hash, "Observation hash must not change after claim verification!"

    # Receipt loaded from disk must also validate with identical hash
    loaded = load_receipt(receipt.receipt_id, test_workspace)
    assert loaded is not None
    assert loaded.compute_hash() == initial_hash
    assert loaded.verified is True


def test_attack_family_e_structured_claim_classification(test_workspace):
    """
    Finding #7: Structured claim classification.
    - "I changed the test documentation." contains 'test' but is doc change (no test pass requirement).
    - "The implementation is green." asserts green build (triggers test pass requirement).
    """
    # 1. Documentation statement does not fail because of exit_code != 0
    doc_claim = Claim(
        claim_id="claim_doc",
        task_id="task_doc",
        statement="I changed the test documentation in README.md",
        claim_type="completion",
    )
    doc_receipt = create_receipt(
        task_id="task_doc",
        claim_id="claim_doc",
        agent="claude",
        action="edit",
        workspace=test_workspace,
        command="pytest",
        exit_code=1,  # A test failure in repository
        started_at="2026-09-13T10:00:00Z",
        finished_at="2026-09-13T10:01:00Z",
        stdout_content="1 failed",
        stderr_content="",
    )
    doc_verdict = verify_claim(doc_claim, doc_receipt, workspace_dir=test_workspace)
    # Doc claim is NOT rejected due to exit_code != 0
    assert doc_verdict.status == "ACCEPT"

    # 2. "The implementation is green" asserts test status and fails if exit_code != 0
    green_claim = Claim(
        claim_id="claim_green",
        task_id="task_green",
        statement="The implementation is green and ready for review",
        claim_type="completion",
    )
    green_verdict = verify_claim(green_claim, doc_receipt, workspace_dir=test_workspace)
    assert green_verdict.status == "REJECT"
    assert "exit code 1" in green_verdict.reason.lower()


def test_attack_family_f_shell_injection_thwarted(test_workspace):
    """
    Finding #8: Execution verifier security boundary.
    Shell chaining and injection operators in verification commands are rejected.
    """
    receipt = observe_command(
        command="pytest && rm -rf .agents",
        workspace_dir=test_workspace,
    )
    assert receipt.exit_code == 126
    # Protected directory remains intact
    assert os.path.exists(os.path.join(test_workspace, ".agents"))


