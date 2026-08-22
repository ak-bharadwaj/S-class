"""
S-Class Full Orchestration Lifecycle Integration Test.

Executes a complete 2-turn dynamic orchestration session:
Turn 1: Model generates buggy code -> D6 execution fails -> D4 reduces to CONTRADICTED ->
        AssessmentReceipt(REJECTED) -> Optimizer routes to REPAIR with skill-systematic-debug.
Turn 2: Model generates repaired code -> D6 execution passes -> D4 reduces to SUPPORTED ->
        AssessmentReceipt(SATISFIED) -> Optimizer routes to CLOSE.
"""

import os
import sys
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from domain.compiler import SpecCompiler, CompiledDomainPackage
from domain.models import RepositoryContext, TaskConstraints
from domain.types import AssessmentVerdict
from events.store import D2NonceStore
from benchmark.parity.gate_3_authority import Gate3AuthorityKeyStore, Gate3AuthoritySigner
from controller.authority import StaticLeaseAuthority, StaticStateAuthority
from controller.controller import SClassController
from controller.token import ActionBinding, ExecutionContext
from execution.workspace import IsolatedWorkspace
from execution.provider import D6ExecutionProvider, D6ProviderRegistry
from execution.gateway import D6ExecutionGateway
from agent.live_worker import LiveModelWorker
from benchmark.v0.engineering.llm_provider import LLMProvider, LLMProviderConfig, LLMResponse
from orchestrator.session import GovernedOrchestrationSession
from orchestrator.models import ReasoningMode
from planner.models import PlanningLease


DEFAULT_SHA = "a" * 40
NOW_ISO = "2026-08-20T12:00:00Z"
EXPIRY_ISO = "2026-08-20T13:00:00Z"


class MultiTurnMockProvider(LLMProvider):
    """Returns buggy code on turn 1, repaired code on turn 2."""
    def __init__(self):
        super().__init__(LLMProviderConfig(provider_type="mock_orchestrator"))
        self._turn = 1

    def generate(self, prompt: str, system_prompt: str = None, **kwargs) -> LLMResponse:
        if self._turn == 1:
            self._turn += 1
            # Buggy code: returns x + 1 instead of x * x
            text = (
                "```json\n"
                "{\n"
                '  "thought": "Initial implementation with deliberate addition bug",\n'
                '  "tool": "propose_code_patch",\n'
                '  "args": {\n'
                '    "obligation_id": "OBL-MATH-1",\n'
                '    "target_file": "target_module.py",\n'
                '    "code_content": "def square(x):\\n    return x + 1\\n",\n'
                '    "purpose": "Initial buggy implementation"\n'
                "  },\n"
                '  "status": "CONTINUE"\n'
                "}\n"
                "```"
            )
        else:
            # Repaired code: returns x * x
            text = (
                "```json\n"
                "{\n"
                '  "thought": "Repaired implementation fixing multiplication invariant based on failure diagnostic",\n'
                '  "tool": "propose_code_patch",\n'
                '  "args": {\n'
                '    "obligation_id": "OBL-MATH-1",\n'
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
            model_name="mock-gemini-orchestrator",
            provider_type="gemini",
            prompt_tokens=150,
            completion_tokens=80,
            latency_sec=0.1,
            cost_usd=0.001,
            timestamp=NOW_ISO,
        )


class OrchestrationTestExecutionProvider(D6ExecutionProvider):
    """Executes target module pytest harness."""
    @property
    def provider_id(self) -> str:
        return "orch_pytest_runner"

    @property
    def supported_action_types(self) -> tuple[str, ...]:
        return ("EXECUTE_TEST",)

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

        with open(target_code_file, "w", encoding="utf-8") as f:
            f.write(code_content)
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


def test_governed_orchestration_multi_turn_repair_lifecycle(tmp_path):
    """Executes complete multi-turn orchestrated repair lifecycle to task closure."""
    signer = Gate3AuthoritySigner()

    # 1. Setup durable D2 log and workspace
    nonce_log_path = str(tmp_path / "d2_nonce_log.jsonl")
    nonce_store = D2NonceStore(file_path=nonce_log_path)
    workspaces_base = tmp_path / "workspaces"
    workspaces_base.mkdir()
    ws_id = "ws_orch_lifecycle"

    # 2. Compile task via Bridge 1
    repo_context = RepositoryContext(
        repository_id="REPO-ORCH-01",
        base_commit_sha=DEFAULT_SHA,
        branch="main",
    )
    constraints = TaskConstraints(
        languages=("python",),
        timeout_seconds=60,
    )
    task_spec = {
        "task_id": "MATH-SQUARE",
        "domain": "Arithmetic / Functional Invariance",
        "raw_prompt": "Implement square(x: int) -> int in target_module.py such that square(x) == x * x.",
        "must_invariants": ["Invariant 1: square(x) == x * x for all integers."],
    }
    package: CompiledDomainPackage = SpecCompiler.compile(
        task_spec,
        repository_context=repo_context,
        constraints=constraints,
    )
    task_id = package.task.task_id
    obl = package.obligations[0]

    # 3. Setup Controller and Execution Gateway
    lease = PlanningLease(
        task_id=task_id,
        owner_id="PLANNER_ORCHESTRATOR",
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
    registry.register(OrchestrationTestExecutionProvider())
    gateway = D6ExecutionGateway(
        authority_signer=signer,
        nonce_store=nonce_store,
        workspace_base_dir=str(workspaces_base),
        registry=registry,
    )

    test_harness_code = (
        "import pytest\n"
        "from target_module import square\n\n"
        "def test_square_positive():\n"
        "    assert square(3) == 9\n"
        "def test_square_zero():\n"
        "    assert square(0) == 0\n"
    )

    worker = LiveModelWorker(
        provider=MultiTurnMockProvider(),
        worker_id="test-orch-worker",
    )

    # 4. Initialize Orchestration Session
    session = GovernedOrchestrationSession(
        package=package,
        session_id="SESS-ORCH-TEST-001",
        max_turns=5,
        initial_budget_units=10.0,
    )

    # TURN 1: Initial Implementation (Buggy)
    decision_1, receipt_1, is_terminal_1 = session.execute_turn(
        worker=worker,
        controller=controller,
        gateway=gateway,
        authority_signer=signer,
        workspace_id=ws_id,
        test_harness_template=test_harness_code,
    )

    assert decision_1.mode == ReasoningMode.IMPLEMENT
    assert is_terminal_1 is False
    assert receipt_1 is not None
    assert receipt_1.verdict == AssessmentVerdict.REJECTED
    assert session.repair_attempts[obl.obligation_id] == 1
    assert len(session.latest_failure_diagnostics) > 0

    # TURN 2: Repaired Implementation (Correct)
    decision_2, receipt_2, is_terminal_2 = session.execute_turn(
        worker=worker,
        controller=controller,
        gateway=gateway,
        authority_signer=signer,
        workspace_id=ws_id,
        test_harness_template=test_harness_code,
    )

    assert decision_2.mode in (ReasoningMode.DIAGNOSE, ReasoningMode.REPAIR)
    assert is_terminal_2 is False
    assert receipt_2 is not None
    assert receipt_2.verdict == AssessmentVerdict.SATISFIED
    assert obl.obligation_id in session.satisfied_obligation_ids

    # TURN 3: Verification of Task Closure
    decision_3, receipt_3, is_terminal_3 = session.execute_turn(
        worker=worker,
        controller=controller,
        gateway=gateway,
        authority_signer=signer,
        workspace_id=ws_id,
        test_harness_template=test_harness_code,
    )

    assert decision_3.mode == ReasoningMode.CLOSE
    assert is_terminal_3 is True
