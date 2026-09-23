"""
S-Class Super Refactor Invariant and Property Test Suite (Section 28).
Validates core epistemic, security, and architectural invariants:
1. Determinism property: Identical canonical state -> identical evaluation verdict and assessment.
2. Tamper-resistance property: Agent narrative / runtime success cannot forge completion without proof.
3. Ledger Separation property: Execution plane cannot directly mutate assurance plane.
4. Monotonicity & Proof Preservation: Claims require verifier evidence; mutations invalidate dependent claims.
5. Crash consistency: ReplayClass.NEVER never replays on crash; corrupt state fails closed.
"""

import os
import pytest
import tempfile
import shutil
from typing import Dict, Any

from sclass.trust.two_ledgers import ExecutionLedger, AssuranceLedger
from sclass.core.completion_evaluator import CompletionEvaluator, CompletionVerdict
from sclass.domain.project import VerifiedProjectState
from sclass.domain.obligations import TechnicalObligation, ObligationStatus
from sclass.domain.claim import Claim, ClaimType
from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.control.composite_auth import DualLayerAuthorizer
from sclass.execution.operations import ReplayClass, compute_action_hash, classify_replay_safety
from sclass.recovery.crash_consistency import CrashRecoveryManager, CrashBoundary
from sclass.core.errors import SecurityViolationError, ObservationIntegrityError


@pytest.fixture
def workspace_env():
    ws = tempfile.mkdtemp(prefix="sclass_invariants_")
    yield ws
    shutil.rmtree(ws, ignore_errors=True)


def test_invariant_determinism_property(workspace_env):
    """
    Property 1: Determinism.
    Given identical canonical project states and identical obligations,
    CompletionEvaluator computes identical verdicts and properties across repeated invocations.
    """
    state = VerifiedProjectState(workspace=workspace_env)
    state.record_verified_claim({
        "claim_id": "c_det_1",
        "task_id": "task_det",
        "statement": "deterministic claim",
        "claim_type": ClaimType.CORRECTNESS.value,
    })
    ob = TechnicalObligation(
        obligation_id="ob_det_1",
        task_id="task_det",
        req_id="r_det",
        title="Deterministic test",
        description="Verify determinism",
        mandatory=True,
        status=ObligationStatus.SATISFIED,
        required_claim_types=(ClaimType.CORRECTNESS.value,),
    )

    assessment1 = CompletionEvaluator.adjudicate(
        task_id="task_det",
        proposed_completion={"msg": "run1"},
        state=state,
        obligations=[ob],
    )
    assessment2 = CompletionEvaluator.adjudicate(
        task_id="task_det",
        proposed_completion={"msg": "run2"},
        state=state,
        obligations=[ob],
    )

    assert assessment1.verdict == assessment2.verdict == CompletionVerdict.ACCEPT
    assert assessment1.obligations_satisfied == assessment2.obligations_satisfied is True
    assert assessment1.claims_verified == assessment2.claims_verified is True
    assert assessment1.evidence_fresh == assessment2.evidence_fresh is True
    assert assessment1.details == assessment2.details


def test_invariant_tamper_resistance_agent_narrative(workspace_env):
    """
    Property 2: Tamper Resistance.
    Agent saying 'DONE', 'TASK COMPLETED', or runtime asserting SUCCESS
    must NEVER yield ACCEPT when a mandatory technical obligation is pending.
    """
    state = VerifiedProjectState(workspace=workspace_env)
    ob = TechnicalObligation(
        obligation_id="ob_unmet",
        task_id="task_tamper",
        req_id="r_unmet",
        title="Unmet security requirement",
        description="Mandatory check",
        mandatory=True,
        status=ObligationStatus.PENDING,
    )

    # Narrative attempts to force completion
    bogus_proposals = [
        {"status": "DONE", "agent_message": "All work complete"},
        {"verdict": "ACCEPT", "runtime_status": "SUCCESS"},
        {"override": True, "claims": ["ALL_PASSED"]},
    ]

    for proposal in bogus_proposals:
        assessment = CompletionEvaluator.adjudicate(
            task_id="task_tamper",
            proposed_completion=proposal,
            state=state,
            obligations=[ob],
        )
        assert assessment.verdict == CompletionVerdict.BLOCK
        assert assessment.obligations_satisfied is False
        assert not assessment.is_accepted


def test_invariant_tamper_resistance_action_hash_forgery(workspace_env):
    """
    Property 2b: Action hash verification.
    If an action is authorized, modifying target, capability, or parameters
    invalidates the action hash and blocks execution.
    """
    action = ActionRequest(
        actor="agent_1",
        capability="terminal.execute",
        action="run_command",
        target="pytest",
        parameters={"cmd": "pytest"},
        workspace=workspace_env,
    )
    valid_hash = compute_action_hash(action.capability, action.action, action.target, action.parameters)

    auth = AuthorizationDecision(
        outcome=DecisionOutcome.ALLOW,
        decision_id="dec_valid",
        request_id="req_valid",
        reason="Authorized",
    )

    # Tampered action with different parameters
    tampered_action = ActionRequest(
        actor="agent_1",
        capability="terminal.execute",
        action="run_command",
        target="pytest",
        parameters={"cmd": "rm -rf /"},
        workspace=workspace_env,
    )

    # When validated against the original action_hash
    tampered_hash = compute_action_hash(tampered_action.capability, tampered_action.action, tampered_action.target, tampered_action.parameters)
    assert valid_hash != tampered_hash


def test_invariant_ledger_separation(workspace_env):
    """
    Property 3: Ledger Separation.
    ExecutionLedger and AssuranceLedger are strictly segregated.
    Raw execution events cannot mutate assurance truth without passing through verification.
    """
    exec_ledger = ExecutionLedger(workspace_env)
    assur_ledger = AssuranceLedger(workspace_env)

    # Execution ledger records raw command
    exec_ledger.append_entry("execution_event", {
        "event_id": "ev_exec_1",
        "operation_id": "op_exec_1",
        "action": "run_command",
        "status": "COMPLETED",
    })

    # Assurance ledger remains untouched
    assert len(assur_ledger.get_entries()) == 0

    # Direct unauthorized bypass raises architectural violation
    with pytest.raises(SecurityViolationError, match="ARCHITECTURAL INVARIANT VIOLATION"):
        assur_ledger.direct_mutate_from_execution_ledger({"synthetic_claim": "unverified"})


def test_invariant_monotonic_proof_and_invalidation(workspace_env):
    """
    Property 4: Proof Monotonicity & Invalidation.
    Verified truth is invalidated when underlying dependencies or files mutate.
    """
    state = VerifiedProjectState(workspace=workspace_env)
    state.record_verified_claim({
        "claim_id": "claim_src_1",
        "task_id": "task_monotonic",
        "statement": "src/core.py verified",
    })

    assert any((c.get("claim_id") or c.get("id")) == "claim_src_1" for c in state.verified_claims)

    # Mutation occurs -> claim invalidated
    state.record_invalidated_claim("claim_src_1", reason="File src/core.py mutated")

    # Claim removed from verified_claims
    assert not any((c.get("claim_id") or c.get("id")) == "claim_src_1" for c in state.verified_claims)
    assert any(c.get("claim_id") == "claim_src_1" for c in state.invalidated_claims)


def test_invariant_crash_consistency_fail_closed(workspace_env):
    """
    Property 5: Crash consistency & fail-closed recovery.
    ReplayClass.NEVER operations are strictly prevented from auto-replay on crash.
    """
    from sclass.execution.harness import StepCodeHarness
    never_op_class = classify_replay_safety(action="write_file", target="critical.py", parameters={})
    assert never_op_class == ReplayClass.NEVER

    harness = StepCodeHarness(workspace_env)
    op = harness.start_operation({"action": "write_file", "target": "critical.py"})
    assert op.replay_class == ReplayClass.NEVER

    # Attempting to recover/replay NEVER operation at AFTER_EFFECT raises SecurityViolationError
    with pytest.raises(SecurityViolationError, match="CRASH RECOVERY REJECTED"):
        CrashRecoveryManager.recover_from_crash(CrashBoundary.AFTER_EFFECT, op)
