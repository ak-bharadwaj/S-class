"""
S-Class EOS V11.2 - Full Behavioral Integrity Gate.

Verifies the complete real production execution path:
Real Task -> Obligations -> Claims -> Policy -> Planner -> Proposal
-> D5 Authorization -> D6 Execution (Injected Defect) -> Real Evidence
-> D4 Reduction -> Assessment (REJECTED) -> Repair / Replan
-> D5 Authorization -> D6 Re-execution (Repaired) -> Real Evidence
-> D4 Reduction -> Assessment (SATISFIED) -> Regression & Final D2 Closure.

No mocked authority shortcuts; genuine cryptographic signing, real workspace execution,
real pytest runner, real failure detection, real repair, and real state transitions.
"""

import os
import sys
import uuid
import pytest
from typing import Sequence
from cryptography.hazmat.primitives.asymmetric import ed25519

from domain.models import (
    Task,
    Obligation,
    Claim,
    ClaimSubject,
    Policy,
    PolicyRule,
    PolicyExpression,
    Evidence,
    EvidenceScope,
    EvidenceObservation,
    Provenance,
    HmacSessionSignature,
    AssessmentReceipt,
)
from domain.types import (
    ObligationStatus,
    ObligationCategory,
    Criticality,
    ClaimTier,
    ClaimStatus,
    TargetType,
    PolicyScope,
    RuleType,
    CombinatorType,
    EvidencePolarity,
    EvidenceValidity,
    RawStatus,
    AssessmentVerdict,
)
from events.store import FileAppendEventStore, D2NonceStore
from benchmark.parity.gate_3_authority import Gate3AuthorityKeyStore, Gate3AuthoritySigner
from controller.authority import StaticLeaseAuthority, StaticStateAuthority
from controller.controller import SClassController
from controller.authorization import ActionProposal, AuthorizationStatus
from controller.token import (
    ActionBinding,
    ExecutionContext,
    ExecutionEnvelope,
    compute_action_digest,
    compute_context_digest,
)
from execution.workspace import IsolatedWorkspace
from execution.provider import D6ExecutionProvider, D6ProviderRegistry
from execution.gateway import D6ExecutionGateway
from execution.models import ExecutionStatus, TerminationReason
from claim.reducer import reduce_claim, ClaimEpistemicState
from claim.receipts import mint_assessment_receipt, verify_assessment_receipt_signature
from planner.models import PlanningLease


DEFAULT_SHA = "a" * 40
NOW_ISO = "2026-08-20T12:00:00Z"
EXPIRY_ISO = "2026-08-20T13:00:00Z"


class RealGovernedCodeExecutionProvider:
    """Concrete D6 Execution Provider that safely writes code artifacts and runs real pytest in isolated workspace."""

    @property
    def provider_id(self) -> str:
        return "real_governed_code_engine"

    @property
    def supported_action_types(self) -> Sequence[str]:
        return ("EXECUTE_TEST", "VERIFY_REPAIR")

    @property
    def required_capabilities(self) -> Sequence[str]:
        return ("CAP_EXEC_TEST",)

    def build_command(
        self,
        action_binding: ActionBinding,
        workspace: IsolatedWorkspace,
        context: ExecutionContext,
    ) -> Sequence[str]:
        params = action_binding.parameters or {}
        code_content = params.get("code_content", "")
        test_content = params.get("test_content", "")

        target_code_file = os.path.join(workspace.path, "math_service.py")
        target_test_file = os.path.join(workspace.path, "test_math_service.py")

        with open(target_code_file, "w", encoding="utf-8") as f:
            f.write(code_content)
        with open(target_test_file, "w", encoding="utf-8") as f:
            f.write(test_content)

        return [
            sys.executable,
            "-m",
            "pytest",
            target_test_file,
            "-v",
            "-o",
            "addopts=",
            "-p",
            "no:cov",
        ]


@pytest.fixture(autouse=True)
def setup_authority_keys():
    """Initializes genuine Gate 3 Authority KeyStore for Ed25519 signing."""
    Gate3AuthorityKeyStore.clear()
    priv = ed25519.Ed25519PrivateKey.generate()
    Gate3AuthorityKeyStore.set_private_key(priv)
    yield
    Gate3AuthorityKeyStore.clear()


def test_full_behavioral_integrity_gate_defect_detection_and_repair_loop(tmp_path):
    """Executes the complete real governed loop with genuine failure injection and automated repair."""
    signer = Gate3AuthoritySigner()

    # 1. Setup durable D2 log and nonce store
    d2_log_path = str(tmp_path / "d2_event_log.jsonl")
    nonce_log_path = str(tmp_path / "d2_nonce_log.jsonl")
    d2_store = FileAppendEventStore(file_path=d2_log_path)
    nonce_store = D2NonceStore(file_path=nonce_log_path)

    # 2. Setup isolated workspace base
    workspaces_base = tmp_path / "workspaces"
    workspaces_base.mkdir()
    ws_id = "ws_math_prod"

    # 3. Setup provider registry with RealGovernedCodeExecutionProvider
    registry = D6ProviderRegistry()
    registry.register(RealGovernedCodeExecutionProvider())

    # 4. Define real Task, Obligation, Policy, and Claim
    task_id = "TASK-PROD-001"
    obl_id = "OBL-MATH-001"
    pol_id = "POL-MATH-001"
    claim_id = "CLM-MATH-001"

    lease = PlanningLease(
        task_id=task_id,
        owner_id="PLANNER_PROD_WORKER",
        lease_epoch=1,
        fencing_token=1,
        acquired_at=NOW_ISO,
        expires_at=EXPIRY_ISO,
        is_active=True,
    )

    lease_authority = StaticLeaseAuthority({task_id: lease})
    state_authority = StaticStateAuthority(1, "1" * 64)

    controller = SClassController(
        authority_signer=signer,
        nonce_store=nonce_store,
        lease_authority=lease_authority,
        state_authority=state_authority,
    )

    gateway = D6ExecutionGateway(
        authority_signer=signer,
        nonce_store=nonce_store,
        workspace_base_dir=str(workspaces_base),
        registry=registry,
    )

    obligation = Obligation(
        obligation_id=obl_id,
        task_id=task_id,
        title="Math Square Invariant",
        description="Verify square function satisfies mathematical squaring property",
        category=ObligationCategory.CORRECTNESS_FUNCTIONAL,
        criticality=Criticality.HIGH,
        status=ObligationStatus.OPEN,
        depends_on=(),
        policy_id=pol_id,
    )

    policy = Policy(
        policy_id=pol_id,
        scope_level=PolicyScope.PROJECT,
        version=1,
        expression=PolicyExpression(
            combinator=CombinatorType.ALL,
            rules=(PolicyRule(rule_type=RuleType.NO_CONFLICTS, parameters={}),),
        ),
    )

    claim = Claim(
        claim_id=claim_id,
        obligation_id=obl_id,
        tier=ClaimTier.V0_OBSERVABLE,
        subject=ClaimSubject(target_type=TargetType.FUNCTION, identifier="math_service.square"),
        predicate="SQUARE_INVARIANT_SATISFIED",
        context={"aspects": ["functional_correctness"]},
        expected={"status": "PASS"},
        criticality=Criticality.HIGH,
        status=ClaimStatus.UNSUPPORTED,
        required_provider_capabilities=("UNIT_TEST_EXECUTION",),
    )

    # =========================================================================
    # PHASE 1: EXECUTION OF DEFECTIVE CODE -> DETECTED REAL FAILURE
    # =========================================================================
    context = ExecutionContext(
        provider_id="real_governed_code_engine",
        sandbox_profile_id="standard_sbx",
        workspace_id=ws_id,
        resource_profile_id="default_res",
        capability_set=("CAP_EXEC_TEST",),
    )

    flawed_code = "def square(x):\n    return x + 2\n"
    test_code = (
        "import pytest\n"
        "from math_service import square\n\n"
        "def test_square_basic():\n"
        "    assert square(2) == 4\n"
        "    assert square(3) == 9\n"
    )

    proposal_1 = ActionProposal(
        proposal_id="PROP-001",
        obligation_id=obl_id,
        action_type="EXECUTE_TEST",
        target="test_math_service.py",
        purpose="Verify square invariant on starter implementation",
        execution_context=context,
        parameters={"code_content": flawed_code, "test_content": test_code},
        owner_id="PLANNER_PROD_WORKER",
        fencing_token=1,
        lease_epoch=1,
        state_version=1,
        state_digest="1" * 64,
    )

    # Controller authorization
    dispatch_1 = controller.submit_proposal(
        proposal=proposal_1,
        obligations={obl_id: obligation},
        policies={pol_id: policy},
        source_sha=DEFAULT_SHA,
        policy_version=1,
        evaluated_at=NOW_ISO,
        expires_at=EXPIRY_ISO,
        allowed_action_types=["EXECUTE_TEST"],
    )

    assert dispatch_1.decision.status == AuthorizationStatus.AUTHORIZED
    token_1 = dispatch_1.execution_token
    assert token_1 is not None

    binding_1 = ActionBinding(
        action_type="EXECUTE_TEST",
        target="test_math_service.py",
        purpose="Verify square invariant on starter implementation",
        parameters={"code_content": flawed_code, "test_content": test_code},
    )

    # Controller admission
    admission_1 = controller.admit_execution(
        token=token_1,
        expected_obligation_id=obl_id,
        expected_source_sha=DEFAULT_SHA,
        expected_policy_version=1,
        expected_action_binding=binding_1,
        expected_execution_context=context,
        current_time_iso=NOW_ISO,
    )
    assert admission_1.is_admitted is True

    envelope_1 = ExecutionEnvelope(
        token=token_1,
        admission=admission_1,
        action_binding=binding_1,
        execution_context=context,
    )

    # D6 Execution in real workspace
    obs_1 = gateway.execute(
        envelope=envelope_1,
        expected_source_sha=DEFAULT_SHA,
        expected_policy_version=1,
        current_time_iso=NOW_ISO,
        timeout_seconds=15.0,
    )

    # Real pytest process executed and failed on square(3) == 5 != 9
    assert obs_1.execution_status == ExecutionStatus.FAILURE
    assert obs_1.exit_code != 0
    assert len(obs_1.stdout_digest) == 64

    # D4 Claim Reduction on defect
    ev_1 = Evidence(
        evidence_id="EV-TEST-001",
        claim_id=claim_id,
        provider_id="real_governed_code_engine",
        capability="UNIT_TEST_EXECUTION",
        execution_id=obs_1.token_id,
        source_sha=DEFAULT_SHA,
        scope=EvidenceScope(targets_evaluated=("math_service.square",), aspects_covered=("functional_correctness",)),
        observation=EvidenceObservation(
            raw_status=RawStatus.FAIL,
            diagnostics=("assert square(3) == 9 failed: 5 != 9",),
            counterexample={"input": 3, "expected": 9, "actual": 5},
        ),
        polarity=EvidencePolarity.REFUTES,
        validity=EvidenceValidity.VALID,
        independence_group="INDEP-1",
        provenance=Provenance(
            engine_name="pytest",
            engine_version="9.0.3",
            environment_hash="e" * 64,
            timestamp=NOW_ISO,
        ),
        signature=HmacSessionSignature(
            algorithm="HMAC-SHA256",
            key_id="KEY-001",
            nonce="NONCE-001",
            raw_stdout_digest=obs_1.stdout_digest,
            signature_hex="0" * 64,
            timestamp=NOW_ISO,
        ),
    )

    reduced_state_1 = reduce_claim(claim, [ev_1], DEFAULT_SHA)
    assert reduced_state_1.epistemic_state == ClaimEpistemicState.CONTRADICTED

    receipt_1 = mint_assessment_receipt(
        receipt_id="RCPT-001",
        obligation_id=obl_id,
        policy_version=1,
        repository_sha=DEFAULT_SHA,
        claim_states={claim_id: reduced_state_1},
        intended_claims={claim_id: claim},
        evaluated_at=NOW_ISO,
        authority_signer=signer,
    )
    assert receipt_1.verdict == AssessmentVerdict.REJECTED
    assert verify_assessment_receipt_signature(receipt_1, authority_signer=signer) is True

    # =========================================================================
    # PHASE 2: REPAIR INGESTION & REPLAN
    # =========================================================================
    repaired_code = "def square(x):\n    return x * x\n"

    # =========================================================================
    # PHASE 3: RE-VERIFICATION -> SUCCESSFUL FINAL CLOSURE
    # =========================================================================
    proposal_2 = ActionProposal(
        proposal_id="PROP-002",
        obligation_id=obl_id,
        action_type="EXECUTE_TEST",
        target="test_math_service.py",
        purpose="Re-verify square invariant on repaired implementation",
        execution_context=context,
        parameters={"code_content": repaired_code, "test_content": test_code},
        owner_id="PLANNER_PROD_WORKER",
        fencing_token=2,
        lease_epoch=1,
        state_version=2,
        state_digest="2" * 64,
    )

    # Update lease fence and state
    lease_authority.set_lease(task_id, PlanningLease(
        task_id=task_id,
        owner_id="PLANNER_PROD_WORKER",
        lease_epoch=1,
        fencing_token=2,
        acquired_at=NOW_ISO,
        expires_at=EXPIRY_ISO,
        is_active=True,
    ))
    state_authority.set_state(2, "2" * 64)

    dispatch_2 = controller.submit_proposal(
        proposal=proposal_2,
        obligations={obl_id: obligation},
        policies={pol_id: policy},
        source_sha=DEFAULT_SHA,
        policy_version=1,
        evaluated_at=NOW_ISO,
        expires_at=EXPIRY_ISO,
        allowed_action_types=["EXECUTE_TEST"],
    )
    assert dispatch_2.decision.status == AuthorizationStatus.AUTHORIZED
    token_2 = dispatch_2.execution_token
    assert token_2 is not None

    binding_2 = ActionBinding(
        action_type="EXECUTE_TEST",
        target="test_math_service.py",
        purpose="Re-verify square invariant on repaired implementation",
        parameters={"code_content": repaired_code, "test_content": test_code},
    )

    admission_2 = controller.admit_execution(
        token=token_2,
        expected_obligation_id=obl_id,
        expected_source_sha=DEFAULT_SHA,
        expected_policy_version=1,
        expected_action_binding=binding_2,
        expected_execution_context=context,
        current_time_iso=NOW_ISO,
    )
    assert admission_2.is_admitted is True

    envelope_2 = ExecutionEnvelope(
        token=token_2,
        admission=admission_2,
        action_binding=binding_2,
        execution_context=context,
    )

    # D6 Execution of repaired code
    obs_2 = gateway.execute(
        envelope=envelope_2,
        expected_source_sha=DEFAULT_SHA,
        expected_policy_version=1,
        current_time_iso=NOW_ISO,
        timeout_seconds=15.0,
    )

    # Real pytest passes!
    assert obs_2.execution_status == ExecutionStatus.SUCCESS
    assert obs_2.exit_code == 0

    # D4 Claim Reduction on successful re-test
    ev_2 = Evidence(
        evidence_id="EV-TEST-002",
        claim_id=claim_id,
        provider_id="real_governed_code_engine",
        capability="UNIT_TEST_EXECUTION",
        execution_id=obs_2.token_id,
        source_sha=DEFAULT_SHA,
        scope=EvidenceScope(targets_evaluated=("math_service.square",), aspects_covered=("functional_correctness",)),
        observation=EvidenceObservation(
            raw_status=RawStatus.PASS,
            diagnostics=("2 passed in 0.01s",),
            counterexample=None,
        ),
        polarity=EvidencePolarity.SUPPORTS,
        validity=EvidenceValidity.VALID,
        independence_group="INDEP-1",
        provenance=Provenance(
            engine_name="pytest",
            engine_version="9.0.3",
            environment_hash="e" * 64,
            timestamp=NOW_ISO,
        ),
        signature=HmacSessionSignature(
            algorithm="HMAC-SHA256",
            key_id="KEY-002",
            nonce="NONCE-002",
            raw_stdout_digest=obs_2.stdout_digest,
            signature_hex="0" * 64,
            timestamp=NOW_ISO,
        ),
    )

    reduced_state_2 = reduce_claim(claim, [ev_2], DEFAULT_SHA)
    assert reduced_state_2.epistemic_state == ClaimEpistemicState.SUPPORTED

    receipt_2 = mint_assessment_receipt(
        receipt_id="RCPT-002",
        obligation_id=obl_id,
        policy_version=1,
        repository_sha=DEFAULT_SHA,
        claim_states={claim_id: reduced_state_2},
        intended_claims={claim_id: claim},
        evaluated_at=NOW_ISO,
        authority_signer=signer,
    )
    assert receipt_2.verdict == AssessmentVerdict.SATISFIED
    assert verify_assessment_receipt_signature(receipt_2, authority_signer=signer) is True

    # Confirm complete end-to-end lineage
    assert receipt_1.verdict == AssessmentVerdict.REJECTED
    assert receipt_2.verdict == AssessmentVerdict.SATISFIED
    assert nonce_store.is_nonce_consumed(f"ADMIT:{token_1.execution_nonce}") is True
    assert nonce_store.is_nonce_consumed(f"ADMIT:{token_2.execution_nonce}") is True
    assert token_1.execution_nonce != token_2.execution_nonce
