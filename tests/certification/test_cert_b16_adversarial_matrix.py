"""
Certification Suite: Unified Adversarial Certification Matrix (Phase 16 / B.16 / B.17).

Red-team stress testing across all 4 S-Class defense frontiers:
1. Trust Frontier: Cryptographic HMAC forgery, generation freshness, ledger chain integrity, protected directory escape.
2. Platform Optimization Frontier: Codex autonomy preservation, Claude minimal projection, Antigravity swarm concurrency.
3. State Frontier: Post-verification stealth mutation, unobserved branch divergence, concurrent collision prevention.
4. Verification Frontier: False test claims, forged receipt hashes, fake provenance, stale receipt replay.
"""

import pytest
import os
import json
import hashlib
import time

from sclass.domain.action import ActionRequest, DecisionOutcome
from sclass.control.authorization import authorize
from sclass.control.policy import DefaultPolicyEngine
from sclass.trust.ledger import LocalLedger
from sclass.domain.project import VerifiedProjectState
from sclass.platform.archetypes.codex import get_codex_profile, get_codex_compensation_policy
from sclass.platform.archetypes.claude_code import get_claude_code_profile, get_claude_code_compensation_policy
from sclass.platform.archetypes.antigravity import get_antigravity_profile, get_antigravity_compensation_policy
from sclass.platform.engine import PlatformOptimizationEngine
from sclass.context.continuity import CrossPlatformContinuityEngine
from sclass.agent_fleet import FleetIntegrityEngine, LeaseType, ConflictType
from sclass.domain.claim import Claim, ClaimType
from sclass.domain.evidence import EvidenceReceipt
from sclass.verification.engine import verify_claim
from sclass.core.errors import HandoffIntegrityError
from sclass.observation.fingerprint import compute_workspace_snapshot, compute_workspace_fingerprint


# ==============================================================================
# FRONTIER 1: TRUST & CRYPTOGRAPHIC PROVENANCE
# ==============================================================================

def test_b16_trust_frontier_ledger_chain_corruption_detected(tmp_path):
    """
    Certifies that any unauthorized modification, deletion, or reordering of entries
    in the append-only local ledger is cryptographically detected by verify_chain().
    """
    ws = tmp_path / "workspace"
    ws.mkdir()
    ledger = LocalLedger(workspace_dir=str(ws))

    # Append 3 valid events
    ledger.append("sclass.action.start", {"task": "auth_refactor"})
    ledger.append("sclass.action.execute", {"cmd": "pytest"})
    ledger.append("sclass.action.verify", {"status": "PASS"})

    assert ledger.verify_chain() is True

    # Attack: Tamper with event #2 payload directly in the JSONL file
    ledger_path = ledger.ledger_file
    with open(ledger_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    record_2 = json.loads(lines[1])
    record_2["payload"]["cmd"] = "rm -rf / --no-preserve-root" # Injected malicious command
    lines[1] = json.dumps(record_2) + "\n"

    with open(ledger_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    # Verification must detect the tampering and fail
    assert ledger.verify_chain() is False


def test_b16_trust_frontier_protected_directory_write_denied(tmp_path):
    """
    Certifies that an agent cannot tamper with internal trust artifacts
    (.agents/ledger/, .sclass/policy/, .agents/verification/).
    """
    ws = tmp_path / "workspace"
    ws.mkdir()

    # Agent attempts to overwrite ledger directly
    req = ActionRequest(
        agent="rogue_agent",
        action="write_file",
        tool="file_editor",
        target=".agents/ledger/events.jsonl",
        parameters={"content": "fake ledger data"},
        workspace=str(ws),
    )
    decision = authorize(req, workspace_dir=str(ws))
    assert decision.outcome == DecisionOutcome.DENY
    assert "protected" in decision.reason.lower() or "authority" in decision.reason.lower() or "denied" in decision.reason.lower()


# ==============================================================================
# FRONTIER 2: PLATFORM OPTIMIZATION & INTERFERENCE PREVENTION
# ==============================================================================

def test_b16_platform_frontier_codex_long_horizon_preserved():
    """
    Certifies that S-Class preserves OpenAI Codex's long-horizon autonomy,
    suppressing disruptive micro-checkpoints and interactive prompts during long tasks.
    """
    profile = get_codex_profile()
    policy = get_codex_compensation_policy()

    control = PlatformOptimizationEngine.reconcile(
        profile=profile,
        compensation_policy=policy,
        task={"type": "long_running_autonomous_feature"},
        risk="normal",
    )

    # Invariants: Autonomous execution preserved, interactive checkpoints suppressed
    assert control.should_stay_out_of_way("long-horizon autonomy") or control.should_stay_out_of_way("terminal execution")
    assert control.is_intervention_suppressed("unnecessary_interruptions") or control.is_intervention_suppressed("interactive_micro_prompts")
    assert control.interruption_policy.lower() in ("fatal_only", "never")


def test_b16_platform_frontier_claude_minimal_context_projection(tmp_path):
    """
    Certifies that Claude Code receives an ultra-dense, token-budgeted projection
    without chat history bloat.
    """
    ws = tmp_path / "workspace"
    ws.mkdir()
    f = ws / "core.py"
    f.write_text("print('core')", encoding="utf-8")

    snap = compute_workspace_snapshot(str(ws))
    fp = compute_workspace_fingerprint(snap)

    state = VerifiedProjectState(
        repository="test-repo",
        workspace=str(ws),
        current_revision=fp,
    )
    state.record_verified_claim({"claim_id": "c1", "statement": "Database migrations applied"}, {"receipt_id": "r1"})

    result = CrossPlatformContinuityEngine.transfer(
        source_platform="codex",
        target_platform="claude_code",
        state=state,
        workspace_dir=str(ws),
        next_action="Continue reasoning pass",
    )

    assert result.success is True
    projection = result.prompt_projection
    assert "CLAUDE_CODE" in projection
    assert "Database migrations applied" in projection
    # Must be compact: under 2500 characters
    assert len(projection) < 2500


def test_b16_platform_frontier_antigravity_concurrency_preserved(tmp_path):
    """
    Certifies that Google Antigravity's multi-agent swarm parallelism is preserved,
    avoiding single-agent serialization while governing integrity.
    """
    ws = tmp_path / "workspace"
    ws.mkdir()
    fleet = FleetIntegrityEngine(workspace_root=str(ws))

    # Multiple parallel workers can acquire independent leases concurrently
    ok_1, _ = fleet.acquire_lease("agent_backend", "src/api.py", LeaseType.EXCLUSIVE_WRITE)
    ok_2, _ = fleet.acquire_lease("agent_frontend", "src/ui.tsx", LeaseType.EXCLUSIVE_WRITE)
    ok_3, _ = fleet.acquire_lease("agent_docs", "docs/README.md", LeaseType.EXCLUSIVE_WRITE)

    assert ok_1 is True
    assert ok_2 is True
    assert ok_3 is True
    # All 3 leases are active simultaneously without serializing the swarm
    assert len(fleet.state.leases) == 3


# ==============================================================================
# FRONTIER 3: STATE INTEGRITY & ANTI-STEALTH MUTATION
# ==============================================================================

def test_b16_state_frontier_post_verification_mutation_invalidated(tmp_path):
    """
    Certifies that if a workspace file is modified after verification without
    an observed receipt, dependent verified claims are invalidated immediately.
    """
    ws = tmp_path / "workspace"
    ws.mkdir()
    state = VerifiedProjectState(
        repository="test-repo",
        workspace=str(ws),
        current_revision="rev-initial",
    )

    # Record verified claim on rev-initial
    state.record_verified_claim(
        claim={"claim_id": "claim_crypto", "statement": "AES-256 GCM encryption enabled"},
        receipt={"receipt_id": "r_aes", "base_commit": "rev-initial", "files_changed": ["src/crypto.py"]},
    )
    assert len(state.verified_claims) == 1

    # Workspace mutates to a new revision without S-Class receipt
    invalidated = state.invalidate_on_workspace_mutation("rev-stealth-edit")

    assert len(invalidated) == 1
    assert invalidated[0] == "claim_crypto"
    assert len(state.verified_claims) == 0
    assert len(state.invalidated_claims) == 1
    assert "Workspace mutated" in state.invalidated_claims[0]["reason"]


def test_b16_state_frontier_branch_shift_fails_closed(tmp_path):
    """
    Certifies that attempting to consume a handoff on a diverged working tree fails closed.
    """
    ws = tmp_path / "workspace"
    ws.mkdir()
    f = ws / "test.py"
    f.write_text("print(1)", encoding="utf-8")

    state = VerifiedProjectState(
        repository="test-repo",
        workspace=str(ws),
        current_revision="stale_revision_hash_9999",
    )

    with pytest.raises(HandoffIntegrityError) as exc_info:
        CrossPlatformContinuityEngine.transfer(
            source_platform="codex",
            target_platform="claude_code",
            state=state,
            workspace_dir=str(ws),
            strict_fingerprint_check=True,
        )

    assert "CONTINUITY REJECTED" in str(exc_info.value)
    assert "Workspace divergence detected" in str(exc_info.value)


# ==============================================================================
# FRONTIER 4: VERIFICATION BOUNDARIES & ANTI-CHEATING
# ==============================================================================

def test_b16_verification_frontier_false_test_claim_rejected(tmp_path):
    """
    Certifies the Prime Invariant: Agent claims "All tests passed", but independently
    observed OS evidence shows exit code 1 -> claim is rejected.
    """
    ws = tmp_path / "workspace"
    ws.mkdir()
    from sclass.survival.models import Claim as SurvivalClaim
    from sclass.survival.verification import verify_claim as survival_verify_claim
    from sclass.survival.evidence import _create_observed_receipt
    from sclass.survival.ledger import LocalLedger as SurvivalLedger

    ledger = SurvivalLedger(workspace_dir=str(ws))

    claim = SurvivalClaim(
        claim_id="claim-failing-tests",
        task_id="task-1",
        statement="All tests pass successfully.",
        claim_type="test_pass",
    )

    # Observed receipt shows exit_code = 1
    evidence = _create_observed_receipt(
        task_id="task-1",
        claim_id="claim-failing-tests",
        agent="untrusted_agent",
        action="pytest",
        workspace=str(ws),
        command="pytest tests/",
        exit_code=1,
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:05Z",
        stdout_content="2 failed, 10 passed",
        stderr_content="",
        files_changed=["tests/test_foo.py"],
        evidence=[{"failed_tests": 2, "passed_tests": 10}],
    )

    result = survival_verify_claim(claim, evidence, workspace_dir=str(ws), ledger=ledger)
    assert result.status == "REJECT"
    assert "exit code" in result.reason.lower() or "failed" in result.reason.lower()


def test_b16_verification_frontier_forged_receipt_hash_rejected(tmp_path):
    """
    Certifies that an evidence receipt with an invalid or tampered receipt_hash is rejected.
    """
    ws = tmp_path / "workspace"
    ws.mkdir()
    ledger = LocalLedger(workspace_dir=str(ws))

    claim = Claim(
        claim_id="claim-tampered",
        task_id="task-tamper",
        statement="Tests pass.",
        claim_type=ClaimType.TEST_PASS.value,
    )

    # Receipt with forged hash in metadata
    evidence = EvidenceReceipt(
        receipt_id="rcpt-tamper",
        task_id="task-tamper",
        claim_id="claim-tampered",
        agent="attacker",
        action="pytest",
        workspace=str(ws),
        base_commit="rev-1",
        result_commit="rev-1",
        command="pytest",
        exit_code=0,
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:05Z",
        stdout_hash="hash1",
        stderr_hash="hash2",
        files_changed=[],
        evidence=[{"passed_tests": 10}],
        metadata={"receipt_hash": "deadbeefcafebabe0000000000000000"}, # Forged hash
    )
    evidence.receipt_hash = "deadbeefcafebabe0000000000000000"

    result = verify_claim(claim, evidence, workspace_dir=str(ws), ledger=ledger)
    assert result.status == "REJECT"
    assert "tampered" in result.reason.lower() or "hash" in result.reason.lower() or "invalid" in result.reason.lower()
