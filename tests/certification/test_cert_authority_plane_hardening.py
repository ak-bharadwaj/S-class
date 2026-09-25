"""
Certification Suite: Authority Plane Hardening & Zero-Trust Verification.
Certifies:
1. CanonicalStateReducer.reduce() ignores caller-seeded claims/obligations and reconstructs purely from canonical records (Blocker 6a).
2. Active frontier is derived strictly from unresolved obligations/claims, not direct replay (Blocker 6b).
3. CanonicalOperationStore.list_operations() anchors to JSONL authority and reconciles derived SQLite index (Blocker 6c).
4. CompletionEvaluator.adjudicate() derives obligations and mutation boundary strictly from canonical state/ledger (Blocker 7).
5. compute_action_hash() anchors relative target paths to workspace_dir to prevent TOCTOU attacks (Blocker 8).
"""

import os
import json
import tempfile
import shutil
import pytest
from datetime import datetime, timezone

from sclass.trust.state_reducer import CanonicalStateReducer
from sclass.domain.project import VerifiedProjectState
from sclass.domain.obligations import TechnicalObligation, ObligationStatus
from sclass.domain.claim import Claim, ClaimType
from sclass.domain.action import ActionRequest
from sclass.core.completion_evaluator import CompletionEvaluator, CompletionVerdict
from sclass.execution.operations import (
    CanonicalOperationStore,
    CrossRuntimeOperation,
    OperationState,
    ReplayClass,
    compute_action_hash,
)


@pytest.fixture
def auth_workspace():
    ws = tempfile.mkdtemp(prefix="sclass_auth_harden_")
    trust_dir = os.path.join(ws, ".sclass", "trust")
    os.makedirs(trust_dir, exist_ok=True)
    yield ws
    shutil.rmtree(ws, ignore_errors=True)


def test_reducer_ignores_caller_seeded_state_and_claims(auth_workspace):
    """
    Certifies Blocker 6a: CanonicalStateReducer.reduce() reconstructs state purely
    from canonical records and does not inherit caller-seeded claims, obligations, or verifications.
    """
    # Create caller-seeded state with an unbacked verified claim
    poisoned_state = VerifiedProjectState(workspace=auth_workspace)
    poisoned_state.verified_claims.append({
        "claim_id": "forged_claim_01",
        "task_id": "task_evil",
        "statement": "Attacker fabricated claim",
        "verified": True,
    })
    poisoned_state.verified_tasks.append("task_evil")
    poisoned_state.add_obligation({
        "obligation_id": "unbacked_ob_01",
        "task_id": "task_evil",
        "mandatory": True,
    })

    # Empty or legitimate canonical records
    records = []

    # Reduce with initial_state passed
    reduced_state = CanonicalStateReducer.reduce(
        records,
        initial_state=poisoned_state,
        workspace_dir=auth_workspace,
        require_authentication=False,
    )

    # State must be pure: caller-injected claim and task MUST be purged
    assert len(reduced_state.verified_claims) == 0
    assert "task_evil" not in reduced_state.verified_tasks
    assert len(reduced_state.active_obligations) == 0


def test_frontier_is_derived_and_not_directly_replayed(auth_workspace):
    """
    Certifies Blocker 6b: Frontier is derived state.
    1. Direct frontier_update records are ignored from mutating the frontier directly.
    2. Active frontier is deterministically derived from unresolved obligations and pending claims.
    """
    records = [
        {
            "entry_id": "e_ob1",
            "entry_type": "obligation",
            "timestamp": "2026-09-25T01:00:00+00:00",
            "payload": {
                "obligation_id": "ob_req1",
                "req_id": "req_1",
                "title": "Database Schema Auth",
                "mandatory": True,
                "status": "PENDING",
            },
        },
        {
            "entry_id": "e_claim1",
            "entry_type": "claim",
            "timestamp": "2026-09-25T01:01:00+00:00",
            "payload": {
                "claim_id": "claim_p1",
                "statement": "Candidate schema satisfies ACID",
            },
        },
        {
            "entry_id": "e_frontier_fake",
            "entry_type": "frontier_update",
            "timestamp": "2026-09-25T01:02:00+00:00",
            "payload": {
                "frontier": [{"fabricated": "item", "id": "fake_frontier_01"}],
            },
        },
    ]

    reduced = CanonicalStateReducer.reduce(
        records,
        workspace_dir=auth_workspace,
        require_authentication=False,
    )

    # Fabricated frontier item from frontier_update event must NOT be present
    assert not any(f.get("id") == "fake_frontier_01" for f in reduced.frontier)

    # Derived frontier MUST contain the unresolved obligation and pending claim
    frontier_ids = {f.get("id") for f in reduced.frontier}
    assert "ob_req1" in frontier_ids
    assert "claim_p1" in frontier_ids


def test_operation_store_list_operations_reconciles_against_canonical_jsonl(auth_workspace):
    """
    Certifies Blocker 6c: CanonicalOperationStore.list_operations() anchors to JSONL authority
    and reconciles derived SQLite index.
    """
    store = CanonicalOperationStore(auth_workspace)
    op = CrossRuntimeOperation(
        operation_id="op_canonical_01",
        runtime_name="step-code",
        action_id="act_01",
        action_hash="hash_can_01",
        state=OperationState.SETTLED,
    )
    store.save_operation(op)

    # Operations listed must match the canonical record
    ops = store.list_operations()
    assert len(ops) == 1
    assert ops[0].operation_id == "op_canonical_01"
    assert ops[0].state == OperationState.SETTLED

    # Poison SQLite directly
    db_path = os.path.join(store.paths.state_dir, "project.db")
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE cross_runtime_operations SET state = 'FAILED' WHERE operation_id = 'op_canonical_01'")

    # list_operations must detect the poisoned SQLite index, rebuild it, and return the true canonical state
    reconciled_ops = store.list_operations()
    assert len(reconciled_ops) == 1
    assert reconciled_ops[0].state == OperationState.SETTLED


def test_completion_evaluator_derives_obligations_and_boundary_from_canonical_ledger(auth_workspace):
    """
    Certifies Blocker 7: CompletionEvaluator derives obligations and mutation boundary
    strictly from canonical state/ledger rather than trusting caller-supplied values.
    """
    ledger_path = os.path.join(auth_workspace, ".sclass", "trust", "assurance_ledger.jsonl")
    mutation_ts = "2026-09-25T02:00:00+00:00"
    with open(ledger_path, "w", encoding="utf-8") as f:
        # Write canonical obligation into ledger
        f.write(json.dumps({
            "entry_id": "rec_ob_01",
            "entry_type": "obligation",
            "timestamp": "2026-09-25T01:00:00+00:00",
            "payload": {
                "obligation_id": "ob_mandatory_canonical",
                "task_id": "task_auth_01",
                "req_id": "req_auth_01",
                "title": "Mandatory Canonical Requirement",
                "mandatory": True,
                "status": "PENDING",
            }
        }) + "\n")
        # Write canonical mutation record
        f.write(json.dumps({
            "entry_id": "rec_mut_01",
            "entry_type": "mutation",
            "timestamp": mutation_ts,
            "payload": {
                "action": "write_file",
                "updated_at": mutation_ts,
            }
        }) + "\n")

    # Caller passes an empty obligation set attempting to close the task without satisfying canonical obligations
    assessment = CompletionEvaluator.adjudicate(
        task_id="task_auth_01",
        proposed_completion={"status": "ok"},
        obligations=[],  # Caller tries to omit obligations
        expected_workspace=auth_workspace,
        mutation_boundary_timestamp="2026-09-20T00:00:00+00:00",  # Caller tries to pass stale boundary
        require_canonical_persistence=False,
    )

    # Must fail closed: canonical obligation is detected and blocks completion
    assert assessment.verdict == CompletionVerdict.BLOCK
    assert assessment.is_accepted is False
    assert any("ob_mandatory_canonical" in r for r in assessment.reasons)
    # Stale caller boundary contradicting ledger boundary is flagged
    assert any("contradicts authoritative ledger boundary" in r for r in assessment.reasons)


def test_compute_action_hash_anchors_relative_targets_to_workspace(auth_workspace, tmp_path):
    """
    Certifies Blocker 8: CF-19 workspace-relative TOCTOU prevention.
    Verifies that relative targets are hashed against files in workspace_dir,
    not against ambient files in process CWD.
    """
    # Create target file in workspace
    ws_file = os.path.join(auth_workspace, "target_config.json")
    with open(ws_file, "w", encoding="utf-8") as f:
        f.write('{"auth": "authorized_content"}\n')

    # Hash computed with workspace_dir
    ws_hash = compute_action_hash(
        capability="filesystem.read",
        action="read_file",
        target="target_config.json",
        parameters={},
        workspace_dir=auth_workspace,
    )

    # Modify file in workspace
    with open(ws_file, "w", encoding="utf-8") as f:
        f.write('{"auth": "TAMPERED_CONTENT"}\n')

    tampered_hash = compute_action_hash(
        capability="filesystem.read",
        action="read_file",
        target="target_config.json",
        parameters={},
        workspace_dir=auth_workspace,
    )

    # Content change in workspace MUST alter the action hash
    assert ws_hash != tampered_hash
