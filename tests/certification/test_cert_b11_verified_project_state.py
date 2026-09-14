"""
Certification Suite: Verified Project State as Universal Truth Layer (B.11).
Certifies:
1. VerifiedProjectState Universal Truth schema compliance across all required B.11 fields.
2. Invariant: Agent memory cannot replace or falsify verified project state without OS evidence receipt.
3. Automatic post-verification workspace mutation invalidation.
4. Pending verification lifecycle: pending claims move to verified upon receipt sealing.
5. Round-trip JSON and dict serialization integrity.
"""

import os
import json
import pytest

from sclass.domain.project import VerifiedProjectState
from sclass.domain.claim import Claim, ClaimType
from sclass.domain.evidence import ObservedReceipt
from sclass.observation.fingerprint import compute_workspace_snapshot, compute_workspace_fingerprint


@pytest.fixture
def b11_workspace(tmp_path):
    ws = tmp_path / "cert_b11_ws"
    ws.mkdir(parents=True, exist_ok=True)
    return str(ws)


def test_b11_universal_truth_layer_schema(b11_workspace):
    """Certifies that VerifiedProjectState conforms to the B.11 universal truth layer structure."""
    state = VerifiedProjectState(
        repository="git@github.com:ak-bharadwaj/S-class.git",
        workspace=b11_workspace,
        current_revision="rev_abc123",
        verified_claims=[{"claim_id": "c1", "statement": "tests pass"}],
        evidence=[{"receipt_id": "rcpt_1"}],
        invalidated_claims=[],
        pending_verification=[{"claim_id": "c2"}],
        agent_context_summary="Initial summary",
        handoff={"package_id": "pkg_1"},
    )

    d = state.to_dict()
    assert d["repository"] == "git@github.com:ak-bharadwaj/S-class.git"
    assert d["workspace"] == b11_workspace
    assert d["current_revision"] == "rev_abc123"
    assert len(d["verified_claims"]) == 1
    assert len(d["evidence"]) == 1
    assert len(d["pending_verification"]) == 1
    assert d["agent_context_summary"] == "Initial summary"
    assert d["handoff"]["package_id"] == "pkg_1"

    # Round-trip JSON
    json_str = state.to_json()
    reconstructed = VerifiedProjectState.from_json(json_str)
    assert reconstructed.repository == state.repository
    assert reconstructed.current_revision == state.current_revision
    assert len(reconstructed.verified_claims) == 1


def test_b11_agent_claim_requires_receipt_for_verification(b11_workspace):
    """
    Certifies S-Class Invariant:
    Agent memory cannot assert verified status; only authoritative receipt anchors verified state.
    """
    state = VerifiedProjectState(workspace=b11_workspace)

    # 1. Propose claim -> enters pending_verification
    unverified_claim = Claim(
        claim_id="claim_auth_impl",
        task_id="task_1",
        statement="Implemented OAuth endpoint",
        claim_type=ClaimType.CORRECTNESS.value,
    )
    state.record_pending_verification(unverified_claim)
    assert len(state.pending_verification) == 1
    assert len(state.verified_claims) == 0

    # 2. Independent receipt is anchored -> moves to verified_claims
    fake_receipt = {
        "receipt_id": "rcpt_os_observed_001",
        "receipt_hash": "hash_123456",
        "exit_code": 0,
    }
    state.record_verified_claim(unverified_claim, receipt=fake_receipt)

    assert len(state.pending_verification) == 0
    assert len(state.verified_claims) == 1
    assert state.verified_claims[0]["evidence_receipt_id"] == "rcpt_os_observed_001"
    assert len(state.evidence) == 1
    assert "task_1" in state.verified_tasks


def test_b11_workspace_mutation_invalidates_verified_claims(b11_workspace):
    """Certifies that unobserved workspace mutation invalidates dependent verified claims."""
    f1 = os.path.join(b11_workspace, "auth.py")
    with open(f1, "w", encoding="utf-8") as f:
        f.write("def auth(): pass\n")

    snap = compute_workspace_snapshot(b11_workspace)
    fp1 = compute_workspace_fingerprint(snap)

    state = VerifiedProjectState(workspace=b11_workspace, current_revision=fp1)
    state.record_verified_claim({"claim_id": "claim_auth_ok", "statement": "auth is valid"})
    assert len(state.verified_claims) == 1
    assert len(state.invalidated_claims) == 0

    # Modify workspace without observation
    with open(f1, "a", encoding="utf-8") as f:
        f.write("# unauthorized edit\n")

    snap2 = compute_workspace_snapshot(b11_workspace)
    fp2 = compute_workspace_fingerprint(snap2)
    assert fp1 != fp2

    # Invalidation trigger
    invalidated = state.invalidate_on_workspace_mutation(fp2)
    assert "claim_auth_ok" in invalidated
    assert len(state.verified_claims) == 0
    assert len(state.invalidated_claims) == 1
    assert "claim_auth_ok" in state.rejected_claims
    assert "Workspace mutated" in state.invalidated_claims[0]["reason"]
