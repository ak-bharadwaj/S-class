"""
Certification Suite: Multi-Agent Fleet Integrity Engine (Phase 15 / B.15).

Certifies the governance and integrity layer for parallel multi-agent swarms:
- Concurrent file mutation race condition prevention via granular leases.
- Duplicate work detection via CKG symbol claim tracking.
- Conflicting semantic assumption detection across parallel subagents.
- Stale branch detection & cascading evidence invalidation.
- Targeted subagent quarantine preserving healthy swarm momentum.
- Epistemic global verification & cross-agent evidence merging into VerifiedProjectState.
"""

import pytest
import os
import time
from sclass.agent_fleet import (
    AgentIdentity,
    AgentStatus,
    ResourceLease,
    LeaseType,
    ConflictEvent,
    ConflictType,
    FleetState,
    FleetMergeResult,
    FleetIntegrityEngine,
)
from sclass.domain.project import VerifiedProjectState


@pytest.fixture
def fleet_env(tmp_path):
    """Fixture providing an isolated fleet integrity environment."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    state_file = ws / ".sclass" / "fleet" / "fleet_state.json"
    engine = FleetIntegrityEngine(workspace_root=str(ws), state_path=str(state_file))
    return engine, str(ws)


def test_b15_concurrent_mutation_race_condition_prevented(fleet_env):
    """
    Certifies that two parallel agents cannot simultaneously acquire exclusive write leases
    on the same file or overlapping directory hierarchies.
    """
    engine, ws = fleet_env
    agent_fe = engine.register_agent(agent_id="agent_frontend", role="frontend_dev")
    agent_be = engine.register_agent(agent_id="agent_backend", role="backend_dev")

    target_file = "src/auth.py"

    # 1. Frontend acquires exclusive write lease
    granted, conflict = engine.acquire_lease("agent_frontend", target_file, LeaseType.EXCLUSIVE_WRITE)
    assert granted is True
    assert conflict is None

    # 2. Backend attempts to acquire exclusive write lease on the same file -> rejected
    granted_be, conflict_be = engine.acquire_lease("agent_backend", target_file, LeaseType.EXCLUSIVE_WRITE)
    assert granted_be is False
    assert conflict_be is not None
    assert conflict_be.conflict_type == ConflictType.CONCURRENT_MUTATION
    assert "agent_frontend" in conflict_be.agents_involved
    assert "agent_backend" in conflict_be.agents_involved

    # 3. Directory containment conflict: backend attempts exclusive lease on parent directory "src"
    granted_parent, conflict_parent = engine.acquire_lease("agent_backend", "src", LeaseType.EXCLUSIVE_WRITE)
    assert granted_parent is False
    assert conflict_parent is not None
    assert conflict_parent.conflict_type == ConflictType.CONCURRENT_MUTATION

    # 4. Frontend releases lease -> now backend can acquire lease
    released = engine.release_lease("agent_frontend", target_file)
    assert released is True

    granted_be_after, conflict_be_after = engine.acquire_lease("agent_backend", target_file, LeaseType.EXCLUSIVE_WRITE)
    assert granted_be_after is True
    assert conflict_be_after is None


def test_b15_duplicate_work_detection(fleet_env):
    """
    Certifies that CKG symbol claim tracking detects and prevents two parallel subagents
    from independently duplicating work on the same function or component.
    """
    engine, ws = fleet_env
    engine.register_agent(agent_id="agent_1", role="crypto_dev")
    engine.register_agent(agent_id="agent_2", role="security_dev")

    symbol = "hash_password"

    # Agent 1 claims the symbol
    claimed_1, conflict_1 = engine.claim_symbol_work("agent_1", symbol, file_path="src/crypto.py")
    assert claimed_1 is True
    assert conflict_1 is None

    # Agent 2 attempts to claim the same symbol
    claimed_2, conflict_2 = engine.claim_symbol_work("agent_2", symbol, file_path="src/security.py")
    assert claimed_2 is False
    assert conflict_2 is not None
    assert conflict_2.conflict_type == ConflictType.DUPLICATE_WORK
    assert conflict_2.details["claimed_by"] == "agent_1"
    assert conflict_2.details["attempted_by"] == "agent_2"


def test_b15_conflicting_semantic_assumptions_detected(fleet_env):
    """
    Certifies that divergent semantic contracts/assumptions between parallel agents
    are detected prior to destructive merge.
    """
    engine, ws = fleet_env
    engine.register_agent(agent_id="agent_api", role="api_designer")
    engine.register_agent(agent_id="agent_client", role="client_dev")

    contract_key = "user_service.authenticate"

    # Agent API records contract
    spec_api = {
        "params": ["username", "password"],
        "return_type": "AuthToken",
        "version": 2,
    }
    ok_1, conflict_1 = engine.record_agent_assumption("agent_api", contract_key, spec_api)
    assert ok_1 is True
    assert conflict_1 is None

    # Agent Client records contradictory contract
    spec_client = {
        "params": ["email", "password", "totp_code"],
        "return_type": "SessionCookie",
        "version": 1,
    }
    ok_2, conflict_2 = engine.record_agent_assumption("agent_client", contract_key, spec_client)
    assert ok_2 is False
    assert conflict_2 is not None
    assert conflict_2.conflict_type == ConflictType.CONFLICTING_ASSUMPTIONS
    assert "divergent_keys" in conflict_2.details
    assert set(conflict_2.details["divergent_keys"]) >= {"params", "return_type", "version"}


def test_b15_stale_branch_detection_and_invalidation(fleet_env):
    """
    Certifies that an agent working against a superseded revision is flagged as stale.
    """
    engine, ws = fleet_env
    engine.register_agent(agent_id="agent_slow", role="worker", base_revision="commit-alpha")

    # Current revision in workspace has advanced to commit-beta
    is_stale = engine.detect_stale_branch("agent_slow", current_workspace_revision="commit-beta")
    assert is_stale is True

    # Check that a STALE_BRANCH_MUTATION conflict was recorded
    assert any(c.conflict_type == ConflictType.STALE_BRANCH_MUTATION for c in engine.state.conflicts)


def test_b15_subagent_quarantine_isolation(fleet_env):
    """
    Certifies EscalationPolicy.QUARANTINE_SUBAGENT: a defective subagent is quarantined,
    revoking its leases and rejecting its claims, while healthy swarm members proceed uninterrupted.
    """
    engine, ws = fleet_env
    engine.register_agent(agent_id="worker_good_1", role="backend")
    engine.register_agent(agent_id="worker_good_2", role="frontend")
    engine.register_agent(agent_id="worker_rogue", role="qa")

    # Rogue worker acquires a lease
    engine.acquire_lease("worker_rogue", "temp/test.py", LeaseType.EXCLUSIVE_WRITE)
    assert "temp/test.py" in engine.state.leases

    # Quarantine the rogue worker for secret leakage
    quarantined = engine.quarantine_agent("worker_rogue", reason="Detected plaintext AWS secret key")
    assert quarantined.status == AgentStatus.QUARANTINED
    assert engine.is_quarantined("worker_rogue") is True

    # Leases previously held by the rogue worker are immediately revoked
    assert "temp/test.py" not in engine.state.leases

    # Rogue worker cannot acquire new leases
    g, c = engine.acquire_lease("worker_rogue", "src/main.py")
    assert g is False
    assert c.conflict_type == ConflictType.QUARANTINE_VIOLATION

    # Healthy workers can acquire leases and proceed normally
    g_good, c_good = engine.acquire_lease("worker_good_1", "src/main.py")
    assert g_good is True
    assert c_good is None


def test_b15_epistemic_evidence_merging_into_verified_project_state(fleet_env):
    """
    Certifies epistemic multi-agent evidence merging into VerifiedProjectState:
    - Clean receipts from healthy agents are merged.
    - Receipts from quarantined agents are rejected and recorded as invalidated claims.
    - Receipts collected on stale revisions are rejected with conflict records.
    """
    engine, ws = fleet_env
    engine.register_agent(agent_id="agent_a", role="backend", base_revision="rev-current")
    engine.register_agent(agent_id="agent_b", role="refactor", base_revision="rev-stale")
    engine.register_agent(agent_id="agent_c", role="rogue", base_revision="rev-current")
    engine.quarantine_agent("agent_c", reason="Unauthorized privileged execution attempt")

    verified_state = VerifiedProjectState(
        repository="test-repo",
        workspace=ws,
        current_revision="rev-current",
    )

    fleet_receipts = [
        {
            "receipt_id": "rcpt-001",
            "claim_id": "claim-clean",
            "claim_text": "Implemented JWT validation",
            "agent": "agent_a",
            "base_commit": "rev-current",
            "exit_code": 0,
            "files_changed": ["src/jwt.py"],
        },
        {
            "receipt_id": "rcpt-002",
            "claim_id": "claim-stale",
            "claim_text": "Refactored user database queries",
            "agent": "agent_b",
            "base_commit": "rev-stale",
            "exit_code": 0,
            "files_changed": ["src/db.py"],
        },
        {
            "receipt_id": "rcpt-003",
            "claim_id": "claim-quarantined",
            "claim_text": "Bypassed credential gate",
            "agent": "agent_c",
            "base_commit": "rev-current",
            "exit_code": 0,
            "files_changed": ["src/gate.py"],
        },
    ]

    result = engine.merge_fleet_evidence(
        verified_state=verified_state,
        fleet_receipts=fleet_receipts,
        current_revision="rev-current",
    )

    # 1. Clean claim is merged into VerifiedProjectState
    assert len(result.merged_claims) == 1
    assert result.merged_claims[0]["claim_id"] == "claim-clean"
    assert any(c["claim_id"] == "claim-clean" for c in verified_state.verified_claims)

    # 2. Stale claim is rejected and placed in invalidated_claims
    assert any(inv["claim_id"] == "claim-stale" for inv in result.invalidated_claims)
    assert any(inv["claim_id"] == "claim-stale" for inv in verified_state.invalidated_claims)

    # 3. Quarantined claim is rejected
    assert "agent_c" in result.quarantined_agents
    assert any(inv["claim_id"] == "claim-quarantined" for inv in result.invalidated_claims)
    assert any(inv["claim_id"] == "claim-quarantined" for inv in verified_state.invalidated_claims)
