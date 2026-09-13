"""
S-Class Certification Test Suite: Handoff B — Universal Action Plane.

Certifies:
1. Unified ActionRequest across ACP, MCP, Claude, Codex, Cursor, OpenCode, and CLI.
2. Multidimensional Capability Security Model.
3. Execution Backends Abstraction and Sandbox Configuration Compiler.
4. Observation Convergence (Execution -> OS Observation -> Immutable Receipt -> LocalLedger).
5. Generic Evidence Architecture (Test, Build, Lint, Security, Semantic, Filesystem, Process).
6. Verification Orchestration & Matrix (VerificationPlan & ClaimAcceptanceMatrix).
7. Semantic Impact Analyzer Boundary (Epistemic invariant: cannot certify truth).
8. Memory Provider Abstraction (Separation of CONTEXT/HYPOTHESIS from VERIFIED_FACT).
"""

import os
import pytest
from datetime import datetime, timezone

from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.domain.capability import (
    Capability,
    CAP_TERMINAL_EXECUTE,
    CAP_FILESYSTEM_READ,
    CAP_FILESYSTEM_WRITE,
    CAP_GIT_READ,
    CAP_GIT_WRITE,
    CAP_NETWORK_REQUEST,
    CAP_SECRET_READ,
    CAP_PROCESS_SPAWN,
)
from sclass.domain.claim import Claim, ClaimType
from sclass.domain.evidence import (
    Evidence,
    EvidenceKind,
    TestEvidence,
    BuildEvidence,
    LintEvidence,
    SecurityEvidence,
    SemanticEvidence,
    FilesystemEvidence,
    ProcessEvidence,
    ObservedReceipt,
    build_evidence_from_receipt,
)
from sclass.domain.verification import VerificationResult
from sclass.execution.backend import (
    ExecutionBackend,
    HostProcessBackend,
    SandboxBackend,
    SandboxConfig,
    SandboxConfigCompiler,
    get_execution_backend,
)
from sclass.observation.convergence import ObservationConvergence, converge_execution
from sclass.verification.acceptance import ClaimAcceptanceMatrix, RequiredEvidenceKind
from sclass.verification.plan import VerificationPlan
from sclass.intelligence.semantic_analyzer import SemanticImpactAnalyzer, SemanticImpactSummary
from sclass.memory.provider import MemoryItem, MemoryType, MemoryScope
from sclass.memory.local import LocalMemoryProvider
from sclass.trust.ledger import LocalLedger
from sclass.core.errors import EpistemicIntegrityError, SecurityViolationError


@pytest.fixture
def test_ws(tmp_path):
    ws = tmp_path / "cert_ws"
    ws.mkdir(parents=True, exist_ok=True)
    # create sample source and test files
    src_dir = ws / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    tests_dir = ws / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_calc.py").write_text(
        "from src.calc import add\ndef test_add():\n    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )
    return str(ws)


# ==============================================================================
# 1. UNIFIED ACTION REQUEST CERTIFICATION
# ==============================================================================

def test_unified_action_request_canonical_constructor(test_ws):
    """Certifies canonical ActionRequest constructor with actor, session, capability, etc."""
    req = ActionRequest(
        actor="agent-claude",
        session="sess_12345",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="pytest tests/",
        parameters={"timeout": 30},
        workspace=test_ws,
        context={"intent": "run unit tests"},
        provenance={"platform": "claude", "caller": "cursor-ide"},
    )

    assert req.actor == "agent-claude"
    assert req.session == "sess_12345"
    assert req.capability == CAP_TERMINAL_EXECUTE
    assert req.action == "run_command"
    assert req.target == "pytest tests/"
    assert req.parameters == {"timeout": 30}
    assert req.workspace == test_ws
    assert req.context == {"intent": "run unit tests"}
    assert req.provenance["platform"] == "claude"

    # Backward-compatible property access
    assert req.agent == "agent-claude"
    assert req.task_id == "sess_12345"
    assert req.platform == "claude"
    assert req.tool == CAP_TERMINAL_EXECUTE


def test_unified_action_request_backward_compatibility(test_ws):
    """Certifies that legacy callers using agent, platform, tool, task_id produce valid ActionRequest."""
    req = ActionRequest(
        agent="codex-cli",
        platform="codex",
        action="read_file",
        tool=CAP_FILESYSTEM_READ,
        target="src/calc.py",
        parameters={"offset": 0},
        workspace=test_ws,
        task_id="task_999",
    )

    assert req.actor == "codex-cli"
    assert req.session == "task_999"
    assert req.capability == CAP_FILESYSTEM_READ
    assert req.agent == "codex-cli"
    assert req.platform == "codex"
    assert req.task_id == "task_999"

    # Serialization round-trip
    d = req.to_dict()
    assert d["actor"] == "codex-cli"
    assert d["agent"] == "codex-cli"
    assert d["session"] == "task_999"
    assert d["task_id"] == "task_999"

    restored = ActionRequest.from_dict(d)
    assert restored.actor == req.actor
    assert restored.session == req.session
    assert restored.capability == req.capability


# ==============================================================================
# 2. CAPABILITY SECURITY MODEL CERTIFICATION
# ==============================================================================

def test_capability_security_model(test_ws):
    """Certifies multidimensional Capability model matching and evaluation."""
    cap_exec = Capability(
        actor="agent-*",
        operation=CAP_TERMINAL_EXECUTE,
        resource="*",
        scope="workspace",
        workspace=test_ws,
        network=False,
        filesystem="read_write",
        risk="medium",
        approval=False,
    )

    req_valid = ActionRequest(
        actor="agent-opencode",
        session="s1",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="python -m pytest",
        workspace=test_ws,
    )
    assert cap_exec.allows_request(req_valid, test_ws) is True

    # Denied: different actor
    req_wrong_actor = ActionRequest(
        actor="untrusted-external",
        session="s2",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="python -m pytest",
        workspace=test_ws,
    )
    assert cap_exec.allows_request(req_wrong_actor, test_ws) is False

    # Denied: operation mismatch
    req_wrong_op = ActionRequest(
        actor="agent-opencode",
        session="s3",
        capability=CAP_NETWORK_REQUEST,
        action="fetch",
        target="https://evil.com",
        workspace=test_ws,
    )
    assert cap_exec.allows_request(req_wrong_op, test_ws) is False


# ==============================================================================
# 3. EXECUTION BACKENDS & SANDBOX COMPILER CERTIFICATION
# ==============================================================================

def test_sandbox_config_compiler(test_ws):
    """Certifies compiler generating configurations anticipating Bubblewrap, gVisor, and Containers."""
    cap = Capability(
        actor="agent-codex",
        operation=CAP_TERMINAL_EXECUTE,
        network=False,
        filesystem="read",
        workspace=test_ws,
    )
    req = ActionRequest(
        actor="agent-codex",
        session="s1",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="pytest",
        workspace=test_ws,
    )

    config = SandboxConfigCompiler.compile(request=req, capability=cap, workspace_dir=test_ws)
    assert config.network_mode == "none"
    assert test_ws in config.read_only_binds  # filesystem="read" forces read-only workspace
    assert test_ws not in config.writable_binds

    # Compile bwrap args
    bwrap_cmd = SandboxConfigCompiler.compile_bubblewrap_args(config, ["pytest"], test_ws)
    assert "bwrap" in bwrap_cmd
    assert "--chdir" in bwrap_cmd

    # Compile gVisor args
    gvisor_cmd = SandboxConfigCompiler.compile_gvisor_args(config, ["pytest"], test_ws)
    assert "runsc" in gvisor_cmd
    assert "--network=none" in gvisor_cmd

    # Compile container args
    container_cmd = SandboxConfigCompiler.compile_container_args(config, ["pytest"], test_ws)
    assert any("docker" in c or "podman" in c for c in container_cmd)
    assert "--network" in container_cmd


def test_host_and_sandbox_execution_backends(test_ws):
    """Certifies HostProcessBackend and SandboxBackend execution."""
    host_backend = HostProcessBackend()
    assert host_backend.is_available() is True

    req = ActionRequest(
        actor="test_runner",
        session="s_backend",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="python -c \"print('backend_ok')\"",
        workspace=test_ws,
    )

    result = host_backend.execute(
        command="python -c \"print('backend_ok')\"",
        cwd=test_ws,
        request=req,
    )
    assert result.exit_code == 0
    assert "backend_ok" in result.stdout

    # SandboxBackend with fallback
    sandbox_backend = SandboxBackend(backend_type="bubblewrap", fallback_to_host=True)
    res_sb = sandbox_backend.execute(
        command="python -c \"print('sandbox_fallback_ok')\"",
        cwd=test_ws,
        request=req,
    )
    assert res_sb.exit_code == 0
    assert "sandbox_fallback_ok" in res_sb.stdout


# ==============================================================================
# 4. OBSERVATION CONVERGENCE CERTIFICATION
# ==============================================================================

def test_observation_convergence_pipeline(test_ws):
    """Certifies execution converging on independent OS observation, receipt sealing, and ledger."""
    ledger = LocalLedger(workspace_dir=test_ws)
    init_count = ledger.get_entry_count()

    req = ActionRequest(
        actor="agent-cursor",
        session="sess_conv_1",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="python -c \"print('converged')\"",
        workspace=test_ws,
    )

    exec_result, receipt = ObservationConvergence.execute_and_observe(
        request=req,
        command="python -c \"print('converged')\"",
        backend=HostProcessBackend(),
        ledger=ledger,
    )

    assert exec_result.exit_code == 0
    assert isinstance(receipt, ObservedReceipt)
    assert receipt.is_observed is True
    assert getattr(receipt, "_sealed", False) is True

    # Receipt post-issuance immutability check
    with pytest.raises(AttributeError):
        receipt.exit_code = 99

    # Committed to LocalLedger
    assert ledger.get_entry_count() == init_count + 1
    assert ledger.verify_chain() is True



# ==============================================================================
# 5. GENERIC EVIDENCE ARCHITECTURE CERTIFICATION
# ==============================================================================

def test_generic_and_typed_evidence_models(test_ws):
    """Certifies all 7 typed evidence models and receipt conversion."""
    t_ev = TestEvidence(
        source="pytest_runner",
        is_observed=True,
        passed_count=10,
        failed_count=0,
        skipped_count=1,
        total_count=11,
        duration_ms=450.0,
    )
    assert t_ev.is_passing is True
    assert t_ev.evidence_kind == EvidenceKind.TEST.value

    b_ev = BuildEvidence(
        source="tsc_compiler",
        is_observed=True,
        build_tool="tsc",
        exit_code=0,
        errors_count=0,
    )
    assert b_ev.is_success is True
    assert b_ev.evidence_kind == EvidenceKind.BUILD.value

    l_ev = LintEvidence(
        source="ruff_linter",
        is_observed=True,
        linter="ruff",
        violation_count=0,
    )
    assert l_ev.is_clean is True

    s_ev = SecurityEvidence(
        source="semgrep_scanner",
        is_observed=True,
        scanner="semgrep",
        findings_count=0,
        passed=True,
    )
    assert s_ev.passed is True

    sem_ev = SemanticEvidence(
        source="scip_index",
        symbol="sclass://calc#add",
        file_path="src/calc.py",
        references_count=2,
        impacted_symbols=["test_add"],
    )
    assert sem_ev.references_count == 2

    fs_ev = FilesystemEvidence(
        source="observer",
        is_observed=True,
        path="src/calc.py",
        operation="write",
        bytes_changed=35,
    )
    assert fs_ev.operation == "write"

    p_ev = ProcessEvidence(
        source="observer",
        is_observed=True,
        pid=1234,
        argv=["python", "-m", "pytest"],
        exit_code=0,
    )
    assert p_ev.exit_code == 0

    # Serialization roundtrip via Evidence.from_dict polymorphic dispatch
    d_test = t_ev.to_dict()
    restored_test = Evidence.from_dict(d_test)
    assert isinstance(restored_test, TestEvidence)
    assert restored_test.passed_count == 10
    assert restored_test.is_passing is True


def test_build_evidence_from_receipt(test_ws):
    """Certifies extracting typed evidence from an authentic ObservedReceipt."""
    req = ActionRequest(
        actor="cert_agent",
        session="sess_ev",
        capability=CAP_TERMINAL_EXECUTE,
        action="run_command",
        target="python -m pytest tests/test_calc.py",
        workspace=test_ws,
    )
    _, receipt = ObservationConvergence.execute_and_observe(
        request=req,
        command="python -m pytest tests/test_calc.py",
        workspace_dir=test_ws,
    )

    evidence_list = build_evidence_from_receipt(receipt)
    assert len(evidence_list) >= 1
    # At least ProcessEvidence must be present
    proc_items = [e for e in evidence_list if isinstance(e, ProcessEvidence)]
    assert len(proc_items) == 1
    assert proc_items[0].exit_code == 0


# ==============================================================================
# 6. VERIFICATION ORCHESTRATION & MATRIX CERTIFICATION
# ==============================================================================

def test_claim_acceptance_matrix_multi_evidence(test_ws):
    """Certifies ClaimAcceptanceMatrix coordinating multi-source evidence to ACCEPT, REJECT, or INCONCLUSIVE."""
    claim_test = Claim(
        claim_id="claim_test_1",
        task_id="task_calc_1",
        claim_type=ClaimType.TEST_PASS.value,
        statement="All calculation unit tests pass",
    )

    # 1. Reject on failing test evidence
    bad_test_ev = TestEvidence(
        source="pytest",
        is_observed=True,
        passed_count=5,
        failed_count=2,
    )
    verdict_fail = ClaimAcceptanceMatrix.evaluate_multi_evidence(claim_test, [bad_test_ev], test_ws)
    assert verdict_fail.status == "REJECT"
    assert verdict_fail.failed_tests == 2

    # 2. Accept on passing test evidence
    good_test_ev = TestEvidence(
        source="pytest",
        is_observed=True,
        passed_count=5,
        failed_count=0,
    )
    verdict_pass = ClaimAcceptanceMatrix.evaluate_multi_evidence(claim_test, [good_test_ev], test_ws)
    assert verdict_pass.status == "ACCEPT"

    # 3. Inconclusive on semantic feature claim backed only by generic execution
    claim_feat = Claim(
        claim_id="claim_feat_1",
        task_id="task_feat_1",
        claim_type=ClaimType.FEATURE.value,
        statement="Implemented user profile deletion feature",
    )
    generic_proc_ev = ProcessEvidence(
        source="generic_cmd",
        is_observed=True,
        argv=["echo", "done"],
        exit_code=0,
    )
    verdict_inconcl = ClaimAcceptanceMatrix.evaluate_multi_evidence(claim_feat, [generic_proc_ev], test_ws)
    assert verdict_inconcl.status == "INCONCLUSIVE"


def test_verification_plan_coordination(test_ws):
    """Certifies VerificationPlan coordinating independent evidence providers across claims."""
    claim1 = Claim(
        claim_id="claim_c1",
        task_id="task_c1",
        claim_type=ClaimType.TEST_PASS.value,
        statement="Calculator tests pass",
    )
    claim2 = Claim(
        claim_id="claim_c2",
        task_id="task_c2",
        claim_type=ClaimType.BUILD.value,
        statement="Build compiles without errors",
    )

    plan = VerificationPlan(
        goal="Verify calculator release",
        target_claims=[claim1, claim2],
        required_evidence_kinds=["test", "build"],
        verifier_ids=["pytest"],
    )

    evidence_set = [
        TestEvidence(source="pytest", is_observed=True, passed_count=3, failed_count=0),
        BuildEvidence(source="builder", is_observed=True, exit_code=0, errors_count=0),
    ]

    results = plan.coordinate(evidence_set, workspace_dir=test_ws)
    assert len(results) == 2
    assert results["claim_c1"].status == "ACCEPT"
    assert results["claim_c2"].status == "ACCEPT"


# ==============================================================================
# 7. SEMANTIC IMPACT ANALYZER CERTIFICATION
# ==============================================================================

def test_semantic_impact_analyzer_and_epistemic_boundary(test_ws):
    """Certifies SemanticImpactAnalyzer planning verification while enforcing that semantic models cannot certify truth."""
    analyzer = SemanticImpactAnalyzer(workspace_root=test_ws)

    # 1. Analysis produces SemanticImpactSummary
    summary = analyzer.analyze(["src/calc.py"])
    assert isinstance(summary, SemanticImpactSummary)
    assert "src/calc.py" in summary.target_files
    assert any("test_calc.py" in tf for tf in summary.recommended_test_files)

    # 2. Generates VerificationPlan
    plan = analyzer.plan_verification(["src/calc.py"])
    assert isinstance(plan, VerificationPlan)
    assert "pytest" in plan.verifier_ids
    assert "test" in plan.required_evidence_kinds

    # 3. Strict Epistemic Invariant: semantic intelligence CANNOT certify truth
    assert analyzer.can_certify_truth is False
    with pytest.raises(EpistemicIntegrityError) as exc_info:
        analyzer.certify_claim(Claim(claim_id="c_fake", task_id="t_fake", claim_type="feature", statement="It is true"))
    assert "cannot directly certify truth" in str(exc_info.value)



# ==============================================================================
# 8. MEMORY PROVIDER ABSTRACTION CERTIFICATION
# ==============================================================================

def test_memory_provider_separation_of_context_and_verified_fact(test_ws):
    """Certifies LocalMemoryProvider separating CONTEXT/HYPOTHESIS from VERIFIED_FACT."""
    mem = LocalMemoryProvider(workspace_dir=test_ws)

    # 1. Candidate CONTEXT memory (no evidence pointer required)
    item_ctx = MemoryItem(
        key="convention_style",
        content="Always use snake_case for python functions",
        memory_type=MemoryType.CONTEXT,
        category="convention",
    )
    mem.remember(item_ctx)

    # 2. Candidate HYPOTHESIS memory (no evidence pointer required)
    item_hyp = MemoryItem(
        key="hyp_speed",
        content="Caching user session might reduce latency by 20ms",
        memory_type=MemoryType.HYPOTHESIS,
        category="hypothesis",
    )
    mem.remember(item_hyp)

    # 3. Attempting to store VERIFIED_FACT without evidence pointer MUST FAIL
    with pytest.raises(ValueError) as exc_info:
        MemoryItem(
            key="fact_unverified",
            content="Authentication bypass vulnerability was completely fixed",
            memory_type=MemoryType.VERIFIED_FACT,
            evidence_pointer=None,  # Missing!
        )
    assert "VERIFIED_FACT memory requires a cryptographic evidence pointer" in str(exc_info.value)

    # 4. Valid VERIFIED_FACT with cryptographic pointer
    item_fact = MemoryItem(
        key="fact_verified",
        content="Calculator add tests verified with 0 failures",
        memory_type=MemoryType.VERIFIED_FACT,
        evidence_pointer="rcpt_abc123456789_sha256",
        category="verification",
    )
    mem.remember(item_fact)

    # 5. Recall
    recalled = mem.recall("fact_verified")
    assert recalled is not None
    assert recalled.evidence_pointer == "rcpt_abc123456789_sha256"
    assert recalled.memory_type == MemoryType.VERIFIED_FACT.value

    # 6. Search with memory_type filtering
    ctx_results = mem.search("snake_case", memory_type=MemoryType.CONTEXT)
    assert len(ctx_results) == 1
    assert ctx_results[0].key == "convention_style"

    fact_results = mem.search("Calculator", memory_type=MemoryType.VERIFIED_FACT)
    assert len(fact_results) == 1
    assert fact_results[0].key == "fact_verified"

    # 7. Forget
    assert mem.forget("convention_style") is True
    assert mem.recall("convention_style") is None
