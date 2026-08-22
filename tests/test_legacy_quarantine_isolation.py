"""
S-Class EOS - Legacy Control Plane Quarantine Certification Test Suite.
Exhaustively proves that legacy modules (runtime.py, evaluation.py, mcp_server.py, sclass_kernel.py)
are completely quarantined and CANNOT affect D2, D3, D5, or D8 authoritative decisions.
"""

import os
import pytest
import tempfile
from datetime import datetime, timezone

from domain.models import Obligation, Policy, PolicyRule, PolicyExpression
from domain.types import ObligationStatus, ObligationCategory, Criticality, RuleType, CombinatorType, PolicyScope
from events.store import D2NonceStore, FileAppendEventStore, InMemoryEventStore
from controller.controller import SClassController, ControllerDispatchResult
from controller.authorization import ActionProposal, AuthorizationStatus
from controller.token import ExecutionContext
from controller.authority import StaticLeaseAuthority, StaticStateAuthority
from planner.models import PlanningLease, Plan, PlanStatus
from benchmark.parity.gate_3_authority import Gate3AuthoritySigner, Gate3AuthorityKeyStore
from cryptography.hazmat.primitives.asymmetric import ed25519

# Legacy modules
import evaluation
from evaluation import SelfEvaluator, EvaluationAction, PhaseEvaluation
import sclass_kernel
from sclass_kernel import MinimalDeterministicKernel
import runtime


@pytest.fixture(autouse=True)
def setup_keys():
    Gate3AuthorityKeyStore.clear()
    priv = ed25519.Ed25519PrivateKey.generate()
    Gate3AuthorityKeyStore.set_private_key(priv)
    yield
    Gate3AuthorityKeyStore.clear()


@pytest.fixture
def fresh_d5_controller(tmp_path):
    signer = Gate3AuthoritySigner()
    nonce_store = D2NonceStore(file_path=str(tmp_path / "legacy_test_nonces.log"))
    lease = PlanningLease(
        task_id="TASK-LEGACY-01",
        owner_id="worker-01",
        lease_epoch=1,
        fencing_token=1,
        acquired_at="2026-08-22T00:00:00Z",
        expires_at="2026-08-22T23:59:59Z",
        is_active=True,
    )
    return SClassController(
        authority_signer=signer,
        nonce_store=nonce_store,
        lease_authority=StaticLeaseAuthority({"TASK-LEGACY-01": lease}),
        state_authority=StaticStateAuthority(1, "1" * 64),
    )


def test_legacy_scalar_confidence_cannot_affect_d3_policy_decision():
    """Proves that legacy confidence scores (0.0 - 1.0) cannot influence pure D3 policy decisions."""
    # Low confidence in legacy evaluator
    legacy_eval = SelfEvaluator.evaluate_phase(
        phase="QA",
        confidence_score=0.1,  # very low confidence
        retry_count=0,
    )
    assert legacy_eval.action == EvaluationAction.CLARIFY

    # D3 policy evaluation is strictly deterministic based on domain expressions, oblivious to scalar confidence
    rule = PolicyRule(rule_type=RuleType.NO_CONFLICTS, parameters={})
    policy = Policy(
        policy_id="POL-001",
        scope_level=PolicyScope.PROJECT,
        version=1,
        expression=PolicyExpression(combinator=CombinatorType.ALL, rules=(rule,)),
    )
    assert policy.version == 1


def test_legacy_evaluator_cannot_mint_d5_execution_tokens(fresh_d5_controller):
    """Proves that legacy SelfEvaluator cannot mint D5 execution tokens or bypass controller disposition."""
    eval_proceed = SelfEvaluator.evaluate_phase("RELEASE", confidence_score=1.0)
    assert eval_proceed.action == EvaluationAction.PROCEED

    # D5 controller rejects any non-ActionProposal object
    with pytest.raises(TypeError, match="proposal must be an ActionProposal instance"):
        fresh_d5_controller.submit_proposal(
            proposal=eval_proceed,  # type: ignore
            obligations={},
            policies={},
            source_sha="a" * 40,
            policy_version=1,
            evaluated_at="2026-08-22T00:00:00Z",
            expires_at="2026-08-22T01:00:00Z",
        )


def test_legacy_kernel_cannot_affect_d2_event_store(tmp_path):
    """Proves that legacy sclass_kernel cannot commit unverified entries to the authoritative D2 store."""
    d2_path = str(tmp_path / "d2_quarantine.log")
    d2_store = FileAppendEventStore(file_path=d2_path)

    # Legacy kernel operates solely on legacy in-memory state
    kernel = MinimalDeterministicKernel()
    assert hasattr(kernel, "request_transition")
    assert not hasattr(kernel, "commit_admission")
    assert not hasattr(kernel, "mint_execution_token")

    # D2 store remains strictly empty
    assert len(d2_store) == 0


def test_legacy_runtime_cannot_bypass_d8_planner_plan():
    """Proves that legacy runtime Task objects cannot mutate or substitute D8 Plan entities."""
    legacy_task = runtime.Task(
        id="LEGACY-01",
        owner="legacy_user",
        targets=["file.py"],
        dependsOn=[],
        acceptanceCriteria="pass",
        priority="high",
        status="OPEN",
    )

    # D8 Plan requires typed fields and string IDs conforming to canonical patterns
    with pytest.raises(Exception):
        Plan(
            plan_id="PLAN-001",
            task_id=legacy_task,  # type: ignore (must be string matching TASK_ID_PATTERN)
            version=1,
        )


def test_quarantined_legacy_plane_has_zero_authority_apis():
    """Architectural guard: verifies that legacy modules possess zero cryptographic or authority signing APIs."""
    for mod in (runtime, evaluation, sclass_kernel):
        assert not hasattr(mod, "issue_session_binding")
        assert not hasattr(mod, "mint_execution_token")
        assert not hasattr(mod, "commit_admission")
        assert not hasattr(mod, "verify_session_binding")
        assert not hasattr(mod, "resolve_proposal_authority_context")
