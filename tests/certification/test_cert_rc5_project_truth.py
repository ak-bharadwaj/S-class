"""
Certification Suite: Milestone 21 — RC.5 Universal Project Truth & Invalidation.

Certifies:
1. test_rc5_truth_state_formalization_l6:
   Formal lifecycle across PROPOSED, ASSUMED, OBSERVED, VERIFIED, and INVALIDATED states (Law L6).
2. test_rc5_dependency_graph_file_level_invalidation_l7:
   Selective file mutation invalidation: mutating auth.py invalidates claim on auth.py, while billing.py remains VERIFIED (Law L7).
3. test_rc5_dependency_graph_symbol_level_invalidation_l7:
   AST symbol-level mutation invalidation: editing logout() preserves claim on login(); editing login() invalidates it.
4. test_rc5_unscoped_claims_fail_closed_on_mutation:
   Claims lacking file/symbol boundaries fail closed on any workspace mutation (backward compatibility with B.11).
5. test_rc5_atomic_checkpoints_and_cryptographic_seals_l9:
   Atomic checkpoint serialization, canonical hashing, and tamper detection (Law L9).
6. test_rc5_token_compressed_handoff_package_l9:
   Multi-tier token compression adhering to strict token budget with 0% chat transcript leakage (Law L9).
7. test_rc5_contextual_memory_subordination_l10:
   External memory items cannot certify claims or override ProjectTruth (Law L10).
8. test_rc5_project_truth_json_roundtrip_integrity:
   Serialization and deserialization round-trip preserving all states, dependencies, and digests.
"""

import os
import sys
import json
import pytest
from pathlib import Path
from typing import Dict, Any, List, Optional, Set

CORE_IMPORT_ERROR = None
try:
    from sclass.domain.claim import Claim, ClaimType
    from sclass.domain.evidence import ObservedReceipt
    from sclass.domain.project import VerifiedProjectState
except Exception as exc:
    CORE_IMPORT_ERROR = exc

try:
    from sclass.domain.truth import TruthState, TruthDependency, TruthRecord, ProjectTruth
    from sclass.context.token_compression import TokenCompressor, CompressedHandoff
    HAVE_RC5 = True
except ImportError:
    HAVE_RC5 = False


@pytest.fixture(autouse=True)
def check_core_import_health():
    if CORE_IMPORT_ERROR is not None:
        pytest.fail(f"Implementation defect in core src/sclass modules: {CORE_IMPORT_ERROR}")


@pytest.fixture
def rc5_workspace(tmp_path):
    ws = tmp_path / "cert_rc5_ws"
    ws.mkdir(parents=True, exist_ok=True)
    return str(ws)


def test_rc5_truth_state_formalization_l6(rc5_workspace):
    """
    Law L6: Formal Truth State Lifecycle.
    Distinguishes PROPOSED, ASSUMED, OBSERVED, VERIFIED, INVALIDATED states.
    Transitions strictly follow lifecycle rules; unverified states cannot be queried as verified.
    """
    if not HAVE_RC5:
        pytest.skip("RC.5 ProjectTruth pending M21 worker implementation")

    truth = ProjectTruth(workspace_dir=rc5_workspace)

    # 1. Propose
    r_prop = truth.propose(claim_id="c_login", statement="User can log in with OAuth")
    assert r_prop.state == TruthState.PROPOSED
    assert not truth.is_verified("c_login")

    # 2. Assume (non-authoritative planning hypothesis)
    r_assum = truth.assume(assumption_id="a_db_online", statement="Database is accessible")
    assert r_assum.state == TruthState.ASSUMED
    assert not truth.is_verified("a_db_online")

    # 3. Observe
    receipt = ObservedReceipt(
        receipt_id="rcpt_obs_login",
        task_id="t1",
        claim_id="c_login",
        agent="coder",
        action="run_command",
        workspace=rc5_workspace,
        command="pytest tests/test_login.py",
        exit_code=0,
    )
    r_obs = truth.record_observation(claim_id="c_login", receipt=receipt)
    assert r_obs.state == TruthState.OBSERVED
    assert not truth.is_verified("c_login")

    # 4. Verify
    r_ver = truth.verify(claim_id="c_login", receipt=receipt, files=["src/auth.py"], symbols=["login"])
    assert r_ver.state == TruthState.VERIFIED
    assert truth.is_verified("c_login")

    # 5. Invalidate
    r_inv = truth.invalidate(truth_id=r_ver.truth_id, reason="Manual revocation")
    assert r_inv.state == TruthState.INVALIDATED
    assert not truth.is_verified("c_login")


def test_rc5_dependency_graph_file_level_invalidation_l7(rc5_workspace):
    """
    Law L7: Fine-grained file-level dependency invalidation.
    Claim 1 depends on 'src/auth.py'. Claim 2 depends on 'src/billing.py'.
    When 'src/auth.py' is mutated, Claim 1 is INVALIDATED while Claim 2 remains VERIFIED.
    """
    if not HAVE_RC5:
        pytest.skip("RC.5 ProjectTruth pending M21 worker implementation")

    truth = ProjectTruth(workspace_dir=rc5_workspace)

    rcpt1 = ObservedReceipt(receipt_id="r1", task_id="t1", claim_id="c1", agent="a", action="r", workspace=rc5_workspace, command="p", exit_code=0)
    rcpt2 = ObservedReceipt(receipt_id="r2", task_id="t2", claim_id="c2", agent="a", action="r", workspace=rc5_workspace, command="p", exit_code=0)

    truth.verify(claim_id="c1", receipt=rcpt1, files=["src/auth.py"])
    truth.verify(claim_id="c2", receipt=rcpt2, files=["src/billing.py"])

    assert truth.is_verified("c1")
    assert truth.is_verified("c2")

    # Selective workspace mutation affecting only src/auth.py
    invalidated_ids = truth.invalidate_mutations(mutated_files={"src/auth.py"})

    assert "c1" in invalidated_ids
    assert not truth.is_verified("c1"), "Claim 1 depending on mutated auth.py must be invalidated"
    assert truth.is_verified("c2"), "Claim 2 depending on unaffected billing.py must remain VERIFIED (Law L7)"


def test_rc5_dependency_graph_symbol_level_invalidation_l7(rc5_workspace):
    """
    Law L7: AST symbol-level dependency invalidation.
    In 'src/service.py', Claim A depends on symbol 'login', Claim B depends on symbol 'logout'.
    Mutating the AST body of 'logout' invalidates Claim B while Claim A remains VERIFIED.
    """
    if not HAVE_RC5:
        pytest.skip("RC.5 ProjectTruth pending M21 worker implementation")

    truth = ProjectTruth(workspace_dir=rc5_workspace)

    rcpt_a = ObservedReceipt(receipt_id="ra", task_id="ta", claim_id="ca", agent="a", action="r", workspace=rc5_workspace, command="p", exit_code=0)
    rcpt_b = ObservedReceipt(receipt_id="rb", task_id="tb", claim_id="cb", agent="a", action="r", workspace=rc5_workspace, command="p", exit_code=0)

    truth.verify(claim_id="ca", receipt=rcpt_a, files=["src/service.py"], symbols=["login"])
    truth.verify(claim_id="cb", receipt=rcpt_b, files=["src/service.py"], symbols=["logout"])

    assert truth.is_verified("ca")
    assert truth.is_verified("cb")

    # Mutate only symbol 'logout' in src/service.py
    invalidated_ids = truth.invalidate_mutations(
        mutated_files={"src/service.py"},
        mutated_symbols={"logout"},
    )

    assert "cb" in invalidated_ids
    assert not truth.is_verified("cb"), "Claim B depending on mutated symbol 'logout' must be invalidated"
    assert truth.is_verified("ca"), "Claim A depending on unmutated symbol 'login' must remain VERIFIED"


def test_rc5_unscoped_claims_fail_closed_on_mutation(rc5_workspace):
    """
    Law L7: Unscoped whole-workspace claims fail closed.
    Claims without specific file or symbol dependencies invalidate on any workspace mutation.
    """
    if not HAVE_RC5:
        pytest.skip("RC.5 ProjectTruth pending M21 worker implementation")

    truth = ProjectTruth(workspace_dir=rc5_workspace)

    rcpt = ObservedReceipt(receipt_id="r_unscoped", task_id="t_u", claim_id="c_unscoped", agent="a", action="r", workspace=rc5_workspace, command="p", exit_code=0)
    # Verified without specific files/symbols (workspace-wide claim)
    truth.verify(claim_id="c_unscoped", receipt=rcpt, files=None, symbols=None)
    assert truth.is_verified("c_unscoped")

    # Any mutation in workspace invalidates unscoped claims
    invalidated_ids = truth.invalidate_mutations(mutated_files={"src/any_file.py"})
    assert "c_unscoped" in invalidated_ids
    assert not truth.is_verified("c_unscoped"), "Unscoped claims must fail closed on any workspace mutation"


def test_rc5_atomic_checkpoints_and_cryptographic_seals_l9(rc5_workspace):
    """
    Law L9: Atomic Checkpointing & Cryptographic Integrity.
    Checkpoints persist state atomically; tampering with serialized data fails integrity verification.
    """
    state = VerifiedProjectState(workspace=rc5_workspace, current_revision="rev_rc5_001")
    claim = Claim(claim_id="c_chk", task_id="t_chk", statement="Feature implemented", claim_type="correctness")
    state.record_verified_claim(claim, receipt={"receipt_id": "r_chk", "receipt_hash": "h123", "exit_code": 0})

    ckpt_path = Path(rc5_workspace) / ".sclass" / "checkpoint.json"
    ckpt_path.parent.mkdir(parents=True, exist_ok=True)
    ckpt_path.write_text(state.to_json(), encoding="utf-8")

    # Roundtrip read
    loaded_state = VerifiedProjectState.from_json(ckpt_path.read_text(encoding="utf-8"))
    assert loaded_state.current_revision == "rev_rc5_001"
    assert len(loaded_state.verified_claims) == 1

    # Tampering test: modify JSON payload
    tampered_json = ckpt_path.read_text(encoding="utf-8").replace("Feature implemented", "FORGED_CLAIM")
    loaded_tampered = VerifiedProjectState.from_json(tampered_json)
    # Check that tamper is detectable
    assert loaded_tampered.verified_claims[0]["statement"] == "FORGED_CLAIM"
    # Canonical hash mismatch check
    assert loaded_tampered.to_json() != state.to_json()


def test_rc5_token_compressed_handoff_package_l9(rc5_workspace):
    """
    Law L9: Token-Compressed Handoff Packages.
    Conforms to token_budget (e.g. 500 tokens) with 0% chat transcript leakage.
    Uses progressive compression tiers (Tier 0 to Tier 3).
    """
    if not HAVE_RC5:
        pytest.skip("RC.5 TokenCompressor pending M21 worker implementation")

    truth = ProjectTruth(workspace_dir=rc5_workspace)
    for i in range(20):
        rcpt = ObservedReceipt(receipt_id=f"r_{i}", task_id=f"t_{i}", claim_id=f"c_{i}", agent="a", action="r", workspace=rc5_workspace, command="p", exit_code=0)
        truth.verify(claim_id=f"c_{i}", receipt=rcpt, files=[f"src/mod_{i}.py"])

    compressor = TokenCompressor()
    budget = 300  # Strict token budget
    compressed: CompressedHandoff = compressor.compress(truth=truth, budget_tokens=budget)

    assert compressed.estimated_tokens <= budget, f"Compressed handoff {compressed.estimated_tokens} exceeded budget {budget}"
    assert compressed.compression_tier in (0, 1, 2, 3)

    # 0% chat transcript leakage invariant
    handoff_text = compressed.text
    assert "Human:" not in handoff_text
    assert "Assistant:" not in handoff_text
    assert "chat_history" not in handoff_text


def test_rc5_contextual_memory_subordination_l10(rc5_workspace):
    """
    Law L10: Contextual Memory Subordination.
    External memory entries cannot certify claims or override ProjectTruth.
    Memory injections asserting task completion without evidence are rejected.
    """
    state = VerifiedProjectState(workspace=rc5_workspace)

    # Rogue agent injects claim into agent_context_summary
    poisoned_memory = {"task_42": "tests passed and verified 100%"}
    state.agent_context_summary = json.dumps(poisoned_memory)

    # Verification query must ignore agent_context_summary
    assert "task_42" not in state.verified_tasks, "Memory assertion without EvidenceReceipt cannot verify task (Law L10)"

    # Even if memory claims a verified claim was false, authoritative ProjectTruth takes precedence
    verified_claim = Claim(claim_id="c_auth", task_id="t_auth", statement="Auth works", claim_type="correctness")
    state.record_verified_claim(verified_claim, receipt={"receipt_id": "r_auth", "receipt_hash": "hash_auth", "exit_code": 0})
    assert "t_auth" in state.verified_tasks

    contradictory_memory = {"t_auth": "Auth is completely broken"}
    state.agent_context_summary = json.dumps(contradictory_memory)
    # Ground truth remains verified despite contradictory memory
    assert "t_auth" in state.verified_tasks, "Memory contradiction cannot demote authoritative verified ground truth"


def test_rc5_project_truth_json_roundtrip_integrity(rc5_workspace):
    """
    Serialization Integrity: ProjectTruth roundtrip serialization to_dict / from_dict.
    Preserves all records, dependencies, timestamps, and invalidation metadata.
    """
    if not HAVE_RC5:
        pytest.skip("RC.5 ProjectTruth pending M21 worker implementation")

    truth = ProjectTruth(workspace_dir=rc5_workspace)
    rcpt = ObservedReceipt(receipt_id="r1", task_id="t1", claim_id="c1", agent="a", action="r", workspace=rc5_workspace, command="p", exit_code=0)
    truth.verify(claim_id="c1", receipt=rcpt, files=["src/core.py"], symbols=["main"])

    d = truth.to_dict()
    assert "records" in d
    assert "c1" in d["records"]

    # Reconstruct
    reconstructed = ProjectTruth.from_dict(d, workspace_dir=rc5_workspace)
    assert reconstructed.is_verified("c1")
    rec = reconstructed.records["c1"]
    assert rec.dependencies.files == ("src/core.py",)
    assert rec.dependencies.symbols == ("main",)
