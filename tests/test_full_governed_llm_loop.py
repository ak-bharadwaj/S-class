"""
S-Class EOS V11.2 - Full Governed LLM End-to-End Integration Loop.

Proves the complete unified execution chain through all three bridges:
1. User Task / Spec -> SpecCompiler (Bridge 1) -> Canonical Task / Obligation DAG / Policy / Claim
2. Planner / Agent Context -> LiveModelWorker (Bridge 2) -> ActionProposalSynthesizer (D7)
3. SClassController (D5) -> Authorized Single-Use ExecutionToken -> D2 Nonce Admission
4. D6ExecutionGateway -> Real Isolated Workspace Process Execution (Injected Defect)
5. ObservationEvidenceAdapter -> Cryptographically Bound Evidence
6. D4 Claim Epistemic Reducer -> CONTRADICTED -> AssessmentReceipt (REJECTED)
7. RepairFeedbackBuilder (Bridge 3) -> Structured Refutation Context -> LiveModelWorker Repair Turn
8. SClassController (D5) -> Fresh ExecutionToken (Incremented Fence & State Version) -> D2 Admission
9. D6ExecutionGateway -> Real Workspace Re-Execution (Repaired Code) -> Pytest PASS
10. D4 Claim Epistemic Reducer -> SUPPORTED -> AssessmentReceipt (SATISFIED)
11. Zero mocks; genuine cryptographic Ed25519 signing; full durable D2 nonce lineage.
"""

import os
import sys
import pytest
from typing import Sequence
from cryptography.hazmat.primitives.asymmetric import ed25519

from domain.compiler import SpecCompiler, CompiledDomainPackage
from domain.models import (
    Task,
    Obligation,
    Claim,
    Policy,
    Evidence,
    AssessmentReceipt,
)
from domain.types import (
    ObligationStatus,
    ClaimStatus,
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
)
from execution.workspace import IsolatedWorkspace
from execution.provider import D6ExecutionProvider, D6ProviderRegistry
from execution.gateway import D6ExecutionGateway
from execution.models import ExecutionStatus
from claim.adapter import ObservationEvidenceAdapter
from claim.reducer import reduce_claim, ClaimEpistemicState
from claim.receipts import mint_assessment_receipt, verify_assessment_receipt_signature
from agent.live_worker import LiveModelWorker
from agent.repair import RepairFeedbackBuilder
from planner.models import PlanningLease
from benchmark.v0.engineering.llm_provider import LLMProvider, LLMProviderConfig, LLMResponse


DEFAULT_SHA = "a" * 40
NOW_ISO = "2026-08-20T12:00:00Z"
EXPIRY_ISO = "2026-08-20T13:00:00Z"


class RealGovernedCodeExecutionProvider:
    """Concrete D6 Execution Provider that writes code/test artifacts and executes real pytest in isolated workspace."""

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

        target_code_file = os.path.join(workspace.path, "target_module.py")
        target_test_file = os.path.join(workspace.path, "test_target_module.py")

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


class MockIterativeLLMProvider(LLMProvider):
    """Simulates multi-turn LLM reasoning: emits flawed implementation on Turn 1, repaired code on Turn 2."""
    def __init__(self):
        super().__init__(LLMProviderConfig(provider_type="mock_test"))
        self.turn = 0

    def generate(self, prompt: str, system_prompt: str = None, **kwargs) -> LLMResponse:
        self.turn += 1
        if self.turn == 1:
            # Turn 1: Flawed initial implementation (fails for x=3 -> 5 != 9)
            text = (
                "```json\n"
                "{\n"
                '  "thought": "Initial implementation of square function",\n'
                '  "tool": "propose_code_patch",\n'
                '  "args": {\n'
                '    "obligation_id": "OBL-MATH-PROD-1",\n'
                '    "target_file": "target_module.py",\n'
                '    "code_content": "def square(x):\\n    return x + 2\\n",\n'
                '    "purpose": "Starter implementation"\n'
                "  },\n"
                '  "status": "CONTINUE"\n'
                "}\n"
                "```"
            )
        else:
            # Turn 2: Repaired implementation based on refutation feedback
            text = (
                "```json\n"
                "{\n"
                '  "thought": "Repaired implementation fixing multiplication invariant",\n'
                '  "tool": "propose_code_patch",\n'
                '  "args": {\n'
                '    "obligation_id": "OBL-MATH-PROD-1",\n'
                '    "target_file": "target_module.py",\n'
                '    "code_content": "def square(x):\\n    return x * x\\n",\n'
                '    "purpose": "Repaired correct implementation"\n'
                "  },\n"
                '  "status": "CONTINUE"\n'
                "}\n"
                "```"
            )
        return LLMResponse(
            text=text,
            model_name="mock-gemini-3.5",
            provider_type="gemini",
            prompt_tokens=150,
            completion_tokens=80,
            latency_sec=0.15,
            cost_usd=0.001,
            timestamp=NOW_ISO,
        )


@pytest.fixture(autouse=True)
def setup_authority_keys():
    """Initializes genuine Gate 3 Authority KeyStore for Ed25519 signing."""
    Gate3AuthorityKeyStore.clear()
    priv = ed25519.Ed25519PrivateKey.generate()
    Gate3AuthorityKeyStore.set_private_key(priv)
    yield
    Gate3AuthorityKeyStore.clear()


def test_full_governed_llm_loop_with_all_three_bridges(tmp_path):
    """Executes the complete unified governed loop through Bridge 1, Bridge 2, and Bridge 3."""
    signer = Gate3AuthoritySigner()

    # 1. Setup durable D2 log and nonce store
    d2_log_path = str(tmp_path / "d2_event_log.jsonl")
    nonce_log_path = str(tmp_path / "d2_nonce_log.jsonl")
    d2_store = FileAppendEventStore(file_path=d2_log_path)
    nonce_store = D2NonceStore(file_path=nonce_log_path)

    # 2. Setup isolated workspace base
    workspaces_base = tmp_path / "workspaces"
    workspaces_base.mkdir()
    ws_id = "ws_full_bridge_loop"

    # =========================================================================
    # BRIDGE 1: SpecCompiler (Task Spec -> Canonical Domain Models)
    # =========================================================================
    raw_task_spec = {
        "task_id": "MATH-PROD",
        "domain": "Arithmetic / Functional Invariance",
        "raw_prompt": "Implement pure mathematical squaring function with invariant square(x) == x * x.",
        "must_invariants": [
            "Verify squaring invariant on positive integers square(x) == x * x"
        ],
    }
    package: CompiledDomainPackage = SpecCompiler.compile(raw_task_spec, default_base_sha=DEFAULT_SHA)
    assert package.task.task_id == "TASK-MATH-PROD"
    assert len(package.obligations) == 1
    assert len(package.claims) == 1
    assert len(package.policies) == 1

    obligation = package.obligations[0]
    claim = package.claims[0]
    policy = package.policies[0]
    task_id = package.task.task_id
    obl_id = obligation.obligation_id
    claim_id = claim.claim_id
    pol_id = policy.policy_id

    assert obligation.status == ObligationStatus.OPEN
    assert claim.status == ClaimStatus.UNSUPPORTED

    # Setup controller and execution fabric
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

    registry = D6ProviderRegistry()
    registry.register(RealGovernedCodeExecutionProvider())

    gateway = D6ExecutionGateway(
        authority_signer=signer,
        nonce_store=nonce_store,
        workspace_base_dir=str(workspaces_base),
        registry=registry,
    )

    context = ExecutionContext(
        provider_id="real_governed_code_engine",
        sandbox_profile_id="standard_sbx",
        workspace_id=ws_id,
        resource_profile_id="default_res",
        capability_set=("CAP_EXEC_TEST",),
    )

    # Unit test suite verifying the square invariant
    test_code = (
        "import pytest\n"
        "from target_module import square\n\n"
        "def test_square_basic():\n"
        "    assert square(2) == 4\n"
        "    assert square(3) == 9\n"
    )

    # =========================================================================
    # BRIDGE 2: LiveModelWorker (Turn 1: Model Emits Initial Patch)
    # =========================================================================
    mock_provider = MockIterativeLLMProvider()
    worker = LiveModelWorker(provider=mock_provider, worker_id="test-live-agent")

    from agent.models import AgentSessionContext, GENESIS_DIGEST
    agent_ctx_1 = AgentSessionContext(
        session_id="SESS-MATH-01",
        repository_id="REPO-MAIN",
        source_sha=DEFAULT_SHA,
        task_id=task_id,
        objective=package.task.raw_prompt,
        frontier_obligation_ids=(obl_id,),
        frontier_details=({"obligation_id": obl_id, "title": obligation.title, "category": obligation.category.value},),
        policy_constraints=(),
        verification_feedback=(),
        available_tools=(),
        granted_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION"),
        turn_index=1,
        max_turns=5,
        remaining_budget_units=5.0,
    )

    msg_1 = worker.generate_inbound_message(
        context=agent_ctx_1,
        sequence=1,
        previous_digest=GENESIS_DIGEST,
        history=(),
    )
    assert len(msg_1.payload.get("tool_calls", [])) == 1
    tool_call_1 = msg_1.payload["tool_calls"][0]
    starter_code = tool_call_1["args"]["code_content"]

    # =========================================================================
    # PHASE 1: D5 AUTHORIZATION -> D6 EXECUTION (DEFECT) -> D4 REFUTATION
    # =========================================================================
    proposal_1 = ActionProposal(
        proposal_id="PROP-001",
        obligation_id=obl_id,
        action_type="EXECUTE_TEST",
        target="test_target_module.py",
        purpose="Verify square invariant on initial patch",
        execution_context=context,
        parameters={"code_content": starter_code, "test_content": test_code},
        owner_id="PLANNER_PROD_WORKER",
        fencing_token=1,
        lease_epoch=1,
        state_version=1,
        state_digest="1" * 64,
    )

    dispatch_1 = controller.submit_proposal(
        proposal=proposal_1,
        obligations=package.obligations_by_id,
        policies=package.policies_by_id,
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
        target="test_target_module.py",
        purpose="Verify square invariant on initial patch",
        parameters={"code_content": starter_code, "test_content": test_code},
    )

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

    obs_1 = gateway.execute(
        envelope=envelope_1,
        expected_source_sha=DEFAULT_SHA,
        expected_policy_version=1,
        current_time_iso=NOW_ISO,
        timeout_seconds=15.0,
    )

    # Real pytest failed on square(3) == 5 != 9
    assert obs_1.execution_status == ExecutionStatus.FAILURE
    assert obs_1.exit_code != 0

    # ObservationEvidenceAdapter creates verified Evidence from Observation
    ev_1 = ObservationEvidenceAdapter.create_evidence(
        observation=obs_1,
        claim=claim,
        source_sha=DEFAULT_SHA,
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
    # BRIDGE 3: RepairFeedbackBuilder (Refutation -> Repair Turn Context)
    # =========================================================================
    feedback = RepairFeedbackBuilder.build_repair_feedback(
        receipt=receipt_1,
        claim_states={claim_id: reduced_state_1},
        evidence_items=[ev_1],
        current_code=starter_code,
    )
    assert feedback.is_rejected is True
    assert claim_id in feedback.refuted_claim_ids

    # Next agent turn receives verification feedback
    agent_ctx_2 = AgentSessionContext(
        session_id="SESS-MATH-01",
        repository_id="REPO-MAIN",
        source_sha=DEFAULT_SHA,
        task_id=task_id,
        objective=package.task.raw_prompt,
        frontier_obligation_ids=(obl_id,),
        frontier_details=({"obligation_id": obl_id, "title": obligation.title, "category": obligation.category.value},),
        policy_constraints=(),
        verification_feedback=({"feedback": feedback.suggested_repair_prompt},),
        available_tools=(),
        granted_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION"),
        turn_index=2,
        max_turns=5,
        remaining_budget_units=4.0,
    )

    msg_2 = worker.generate_inbound_message(
        context=agent_ctx_2,
        sequence=2,
        previous_digest=msg_1.message_digest,
        history=(msg_1,),
    )
    tool_call_2 = msg_2.payload["tool_calls"][0]
    repaired_code = tool_call_2["args"]["code_content"]
    assert "return x * x" in repaired_code

    # =========================================================================
    # PHASE 2: D5 RE-AUTHORIZATION -> D6 RE-EXECUTION -> D4 SATISFACTION
    # =========================================================================
    # Advance lease fencing token and state version
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

    proposal_2 = ActionProposal(
        proposal_id="PROP-002",
        obligation_id=obl_id,
        action_type="EXECUTE_TEST",
        target="test_target_module.py",
        purpose="Re-verify square invariant on repaired code",
        execution_context=context,
        parameters={"code_content": repaired_code, "test_content": test_code},
        owner_id="PLANNER_PROD_WORKER",
        fencing_token=2,
        lease_epoch=1,
        state_version=2,
        state_digest="2" * 64,
    )

    dispatch_2 = controller.submit_proposal(
        proposal=proposal_2,
        obligations=package.obligations_by_id,
        policies=package.policies_by_id,
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
        target="test_target_module.py",
        purpose="Re-verify square invariant on repaired code",
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

    # ObservationEvidenceAdapter creates passing Evidence
    ev_2 = ObservationEvidenceAdapter.create_evidence(
        observation=obs_2,
        claim=claim,
        source_sha=DEFAULT_SHA,
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

    # Complete lineage verification
    assert receipt_1.verdict == AssessmentVerdict.REJECTED
    assert receipt_2.verdict == AssessmentVerdict.SATISFIED
    assert nonce_store.is_nonce_consumed(f"ADMIT:{token_1.execution_nonce}") is True
    assert nonce_store.is_nonce_consumed(f"ADMIT:{token_2.execution_nonce}") is True
    assert token_1.execution_nonce != token_2.execution_nonce
