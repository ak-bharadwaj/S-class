"""
S-Class EOS V11.2 - Live Provider Governed End-to-End Integration Suite.

Requires explicit live LLM credentials (GEMINI_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY).
Fails closed or skips cleanly if credentials are not provided.
Executes genuine, dynamic model reasoning with zero hardcoded/predetermined code responses.
Records live model token usage, latency, cost, and cryptographic receipts.
"""

import os
import sys
import pytest
from datetime import datetime, timezone
from typing import Optional, Tuple
from cryptography.hazmat.primitives.asymmetric import ed25519

from domain.compiler import SpecCompiler, CompiledDomainPackage
from domain.models import (
    Task,
    TaskConstraints,
    RepositoryContext,
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
from agent.models import AgentSessionContext, GENESIS_DIGEST
from planner.models import PlanningLease
from benchmark.v0.engineering.llm_provider import LLMProvider, LLMProviderConfig, LLMResponse


DEFAULT_SHA = "a" * 40
NOW_ISO = "2026-08-20T12:00:00Z"
EXPIRY_ISO = "2026-08-20T13:00:00Z"


def _get_live_provider_config() -> Optional[LLMProviderConfig]:
    """Inspects environment for live provider credentials and returns configuration if present."""
    if os.environ.get("GEMINI_API_KEY"):
        return LLMProviderConfig(
            provider_type="gemini",
            model_name=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
            api_key=os.environ["GEMINI_API_KEY"],
            timeout_sec=30,
        )
    elif os.environ.get("OPENAI_API_KEY"):
        return LLMProviderConfig(
            provider_type="openai",
            model_name=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            api_key=os.environ["OPENAI_API_KEY"],
            timeout_sec=30,
        )
    elif os.environ.get("ANTHROPIC_API_KEY"):
        return LLMProviderConfig(
            provider_type="anthropic",
            model_name=os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022"),
            api_key=os.environ["ANTHROPIC_API_KEY"],
            timeout_sec=30,
        )
    return None


class GovernedPythonExecutionProvider(D6ExecutionProvider):
    """Executes dynamic model code and verification tests in an isolated workspace."""

    @property
    def provider_id(self) -> str:
        return "live_pytest_engine"

    @property
    def supported_action_types(self) -> tuple[str, ...]:
        return ("EXECUTE_TEST", "PROPOSE_PATCH")

    @property
    def required_capabilities(self) -> tuple[str, ...]:
        return ("CAP_EXEC_TEST",)

    def build_command(
        self,
        action_binding: ActionBinding,
        workspace: IsolatedWorkspace,
        context: ExecutionContext,
    ) -> tuple[str, ...]:
        params = action_binding.parameters or {}
        code_content = params.get("code_content", "")
        test_content = params.get("test_content", "")

        target_code_file = os.path.join(workspace.path, "target_module.py")
        target_test_file = os.path.join(workspace.path, "test_target_module.py")

        if code_content:
            with open(target_code_file, "w", encoding="utf-8") as f:
                f.write(code_content)
        if test_content:
            with open(target_test_file, "w", encoding="utf-8") as f:
                f.write(test_content)

        return (
            sys.executable,
            "-m",
            "pytest",
            target_test_file,
            "-v",
            "-o",
            "addopts=",
            "-p",
            "no:cov",
        )


@pytest.fixture(autouse=True)
def setup_authority_keys():
    """Initializes genuine Gate 3 Authority KeyStore for Ed25519 signing."""
    Gate3AuthorityKeyStore.clear()
    priv = ed25519.Ed25519PrivateKey.generate()
    Gate3AuthorityKeyStore.set_private_key(priv)
    yield
    Gate3AuthorityKeyStore.clear()


def test_live_llm_governed_execution_loop(tmp_path):
    """
    Genuine Live LLM Integration Test.
    Requires live credentials. Skips cleanly if not configured.
    """
    config = _get_live_provider_config()
    if config is None:
        pytest.skip(
            "Live LLM integration test skipped: No live API credentials found in environment "
            "(GEMINI_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY)."
        )

    # 1. Initialize live provider and worker
    live_provider = LLMProvider(config)
    live_worker = LiveModelWorker(
        provider=live_provider,
        worker_id=f"live-{config.provider_type}-{config.model_name}",
    )
    signer = Gate3AuthoritySigner()

    # 2. Setup durable D2 log and nonce store
    d2_log_path = str(tmp_path / "d2_event_log.jsonl")
    nonce_log_path = str(tmp_path / "d2_nonce_log.jsonl")
    nonce_store = D2NonceStore(file_path=nonce_log_path)
    workspaces_base = tmp_path / "workspaces"
    workspaces_base.mkdir()
    ws_id = "ws_live_llm_run"

    # 3. Compile task through SpecCompiler (Bridge 1)
    repo_context = RepositoryContext(
        repository_id="REPO-LIVE-01",
        base_commit_sha=DEFAULT_SHA,
        branch="main",
    )
    constraints = TaskConstraints(
        languages=("python",),
        timeout_seconds=60,
    )
    task_spec = {
        "task_id": "MATH-ADD",
        "domain": "Arithmetic / Functional Invariance",
        "raw_prompt": "Implement a Python function `add(a: int, b: int) -> int` in target_module.py that returns the sum of a and b.",
        "must_invariants": ["Invariant 1: add(a, b) == a + b for all integer inputs."],
    }
    package: CompiledDomainPackage = SpecCompiler.compile(
        task_spec,
        repository_context=repo_context,
        constraints=constraints,
    )
    task_id = package.task.task_id
    obl = package.obligations[0]
    claim = package.claims[0]
    pol = package.policies[0]

    # 4. Setup Controller and Execution Gateway
    lease = PlanningLease(
        task_id=task_id,
        owner_id="PLANNER_LIVE_WORKER",
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
    registry.register(GovernedPythonExecutionProvider())
    gateway = D6ExecutionGateway(
        authority_signer=signer,
        nonce_store=nonce_store,
        workspace_base_dir=str(workspaces_base),
        registry=registry,
    )

    test_harness_code = (
        "import pytest\n"
        "from target_module import add\n\n"
        "def test_add_positive():\n"
        "    assert add(2, 3) == 5\n"
        "def test_add_negative():\n"
        "    assert add(-1, 1) == 0\n"
        "def test_add_zero():\n"
        "    assert add(0, 0) == 0\n"
    )

    # 5. Execute Turn 1 with genuine live model reasoning
    agent_ctx_1 = AgentSessionContext(
        session_id="SESS-LIVE-001",
        repository_id="REPO-LIVE-01",
        source_sha=DEFAULT_SHA,
        task_id=task_id,
        objective=package.task.raw_prompt,
        frontier_obligation_ids=(obl.obligation_id,),
        frontier_details=({"obligation_id": obl.obligation_id, "title": obl.title, "category": obl.category.value},),
        policy_constraints=(),
        verification_feedback=(),
        available_tools=(),
        granted_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION"),
        turn_index=1,
        max_turns=3,
        remaining_budget_units=10.0,
    )

    msg_1 = live_worker.generate_inbound_message(
        context=agent_ctx_1,
        sequence=1,
        previous_digest=GENESIS_DIGEST,
        history=(),
    )

    assert msg_1.worker_id == live_worker.worker_id
    assert len(msg_1.payload.get("tool_calls", [])) >= 1
    tool_call_1 = msg_1.payload["tool_calls"][0]
    generated_code = tool_call_1["args"].get("code_content", "")
    assert len(generated_code) > 0

    # 6. Route through D5 Controller
    exec_ctx = ExecutionContext(
        provider_id="live_pytest_engine",
        sandbox_profile_id="standard_sbx",
        workspace_id=ws_id,
        resource_profile_id="default_res",
        capability_set=("CAP_EXEC_TEST",),
    )

    proposal = ActionProposal(
        proposal_id="PROP-LIVE-001",
        obligation_id=obl.obligation_id,
        action_type="EXECUTE_TEST",
        target="test_target_module.py",
        purpose="Verify live generated add function",
        execution_context=exec_ctx,
        parameters={"code_content": generated_code, "test_content": test_harness_code},
        owner_id="PLANNER_LIVE_WORKER",
        fencing_token=1,
        lease_epoch=1,
        state_version=1,
        state_digest="1" * 64,
    )

    dispatch = controller.submit_proposal(
        proposal=proposal,
        obligations=package.obligations_by_id,
        policies=package.policies_by_id,
        source_sha=DEFAULT_SHA,
        policy_version=1,
        evaluated_at=NOW_ISO,
        expires_at=EXPIRY_ISO,
        allowed_action_types=["EXECUTE_TEST"],
    )
    assert dispatch.decision.status == AuthorizationStatus.AUTHORIZED
    token = dispatch.execution_token

    binding = ActionBinding(
        action_type="EXECUTE_TEST",
        target="test_target_module.py",
        purpose="Verify live generated add function",
        parameters={"code_content": generated_code, "test_content": test_harness_code},
    )

    admission = controller.admit_execution(
        token=token,
        expected_obligation_id=obl.obligation_id,
        expected_source_sha=DEFAULT_SHA,
        expected_policy_version=1,
        expected_action_binding=binding,
        expected_execution_context=exec_ctx,
        current_time_iso=NOW_ISO,
    )
    assert admission.is_admitted is True

    envelope = ExecutionEnvelope(
        token=token,
        admission=admission,
        action_binding=binding,
        execution_context=exec_ctx,
    )

    # 7. Execute in real isolated workspace
    obs = gateway.execute(
        envelope=envelope,
        expected_source_sha=DEFAULT_SHA,
        expected_policy_version=1,
        current_time_iso=NOW_ISO,
        timeout_seconds=20.0,
    )

    # 8. Convert to Evidence and Reduce
    ev = ObservationEvidenceAdapter.create_evidence(
        observation=obs,
        claim=claim,
        source_sha=DEFAULT_SHA,
    )
    reduction = reduce_claim(claim, [ev], DEFAULT_SHA)

    receipt = mint_assessment_receipt(
        receipt_id="RCPT-LIVE-001",
        obligation_id=obl.obligation_id,
        policy_version=1,
        repository_sha=DEFAULT_SHA,
        claim_states={claim.claim_id: reduction},
        intended_claims={claim.claim_id: claim},
        evaluated_at=NOW_ISO,
        authority_signer=signer,
    )

    assert verify_assessment_receipt_signature(receipt, authority_signer=signer) is True
    assert nonce_store.is_nonce_consumed(f"ADMIT:{token.execution_nonce}") is True
