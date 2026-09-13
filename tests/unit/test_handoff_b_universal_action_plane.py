"""
Unit Tests: Handoff B — Universal Action Plane.
Exhaustive unit test coverage for edge cases, error paths, and invariants across all Handoff B components.
"""

import os
import pytest
from datetime import datetime, timezone

from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.domain.capability import (
    Capability,
    RiskTier,
    NetworkAccessLevel,
    FilesystemAccessLevel,
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
def ws(tmp_path):
    w = tmp_path / "unit_ws"
    w.mkdir(parents=True, exist_ok=True)
    src = w / "pkg"
    src.mkdir(parents=True, exist_ok=True)
    (src / "mod.py").write_text(
        "class Helper:\n    def run(self):\n        return 'ok'\n\ndef entrypoint():\n    return Helper().run()\n",
        encoding="utf-8",
    )
    tests = w / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_mod.py").write_text(
        "from pkg.mod import entrypoint\ndef test_entry():\n    assert entrypoint() == 'ok'\n",
        encoding="utf-8",
    )
    return str(w)


# ------------------------------------------------------------------------------
# 1. ActionRequest Edge Cases
# ------------------------------------------------------------------------------

def test_action_request_frozen_immutability():
    req = ActionRequest(actor="agent-1", session="s1", capability="terminal.execute", action="run")
    with pytest.raises((AttributeError, TypeError)):
        req.actor = "tampered"  # type: ignore


def test_action_request_defaults_and_roundtrip():
    req = ActionRequest()
    assert req.actor == "unknown_actor"
    assert req.session == ""
    assert req.capability == ""
    assert req.action == "unknown_action"
    assert req.parameters == {}
    assert req.provenance["platform"] == "generic"

    d = req.to_dict()
    restored = ActionRequest.from_dict(d)
    assert restored.actor == req.actor
    assert restored.platform == req.platform


# ------------------------------------------------------------------------------
# 2. Capability Edge Cases
# ------------------------------------------------------------------------------

def test_capability_wildcard_and_prefix_matching(ws):
    cap_star = Capability(operation="*")
    assert cap_star.allows_operation("terminal.execute") is True
    assert cap_star.allows_operation("custom.unknown") is True

    cap_prefix = Capability(operation="filesystem.*")
    assert cap_prefix.allows_operation("filesystem.read") is True
    assert cap_prefix.allows_operation("filesystem.write") is True
    assert cap_prefix.allows_operation("terminal.execute") is False

    cap_actor = Capability(operation="terminal.execute", actor="claude-*")
    assert cap_actor.allows_actor("claude-code") is True
    assert cap_actor.allows_actor("cursor-agent") is False


def test_capability_serialization():
    cap = Capability(
        operation=CAP_GIT_WRITE,
        actor="dev-agent",
        resource="src/*",
        risk="high",
        network="local",
        filesystem="read_write",
        approval=True,
    )
    d = cap.to_dict()
    restored = Capability.from_dict(d)
    assert restored.operation == CAP_GIT_WRITE
    assert restored.actor == "dev-agent"
    assert restored.risk == "high"
    assert restored.approval is True


# ------------------------------------------------------------------------------
# 3. Execution Backend & Sandbox Compiler Edge Cases
# ------------------------------------------------------------------------------

def test_sandbox_compiler_credential_masking(ws):
    os.environ["SECRET_TOKEN_FOR_TEST"] = "super_secret_123"
    try:
        cap_no_creds = Capability(operation="terminal.execute", credentials=[])
        cfg = SandboxConfigCompiler.compile(capability=cap_no_creds, workspace_dir=ws)
        assert "SECRET_TOKEN_FOR_TEST" not in cfg.env_whitelist

        cap_with_creds = Capability(operation="terminal.execute", credentials=["SECRET_TOKEN_FOR_TEST"])
        cfg_allowed = SandboxConfigCompiler.compile(capability=cap_with_creds, workspace_dir=ws)
        assert cfg_allowed.env_whitelist.get("SECRET_TOKEN_FOR_TEST") == "super_secret_123"
    finally:
        os.environ.pop("SECRET_TOKEN_FOR_TEST", None)


def test_get_execution_backend_factory():
    b_host = get_execution_backend("host")
    assert isinstance(b_host, HostProcessBackend)
    b_bwrap = get_execution_backend("bwrap")
    assert isinstance(b_bwrap, SandboxBackend)
    assert "bubblewrap" in b_bwrap.name
    b_docker = get_execution_backend("docker")
    assert isinstance(b_docker, SandboxBackend)
    assert "container" in b_docker.name


# ------------------------------------------------------------------------------
# 4. Observation Convergence Edge Cases
# ------------------------------------------------------------------------------

def test_convergence_on_failing_command(ws):
    ledger = LocalLedger(workspace_dir=ws)
    req = ActionRequest(actor="tester", session="s_err", capability="terminal.execute", action="run", workspace=ws)

    exec_res, receipt = ObservationConvergence.execute_and_observe(
        request=req,
        command="python -c \"import sys; sys.stderr.write('err_msg'); sys.exit(2)\"",
        ledger=ledger,
    )

    assert exec_res.exit_code == 2
    assert "err_msg" in exec_res.stderr
    assert receipt.exit_code == 2
    assert receipt.is_observed is True
    assert ledger.verify_chain() is True


# ------------------------------------------------------------------------------
# 5. Generic Evidence Edge Cases
# ------------------------------------------------------------------------------

def test_evidence_staleness_invalidation(ws):
    # Capture snapshot
    from sclass.observation.fingerprint import compute_workspace_snapshot, compute_workspace_fingerprint
    snap = compute_workspace_snapshot(ws)
    fp = compute_workspace_fingerprint(snap)

    ev = TestEvidence(
        source="pytest",
        is_observed=True,
        workspace_fingerprint=fp,
        passed_count=5,
    )
    assert ev.is_valid(ws) is True

    # Mutate workspace
    (os.path.join(ws, "pkg", "mod.py"))
    with open(os.path.join(ws, "pkg", "mod.py"), "a", encoding="utf-8") as f:
        f.write("# mutation\n")

    assert ev.is_valid(ws) is False


def test_all_typed_evidence_to_and_from_dict():
    models = [
        TestEvidence(passed_count=2, failed_count=1),
        BuildEvidence(build_tool="make", exit_code=1, errors_count=2),
        LintEvidence(linter="flake8", violation_count=4),
        SecurityEvidence(scanner="trivy", findings_count=1, passed=False),
        SemanticEvidence(symbol="test_sym", references_count=5),
        FilesystemEvidence(path="file.txt", operation="delete", bytes_changed=100),
        ProcessEvidence(pid=999, argv=["python"], exit_code=0),
    ]

    for m in models:
        d = m.to_dict()
        restored = Evidence.from_dict(d)
        assert restored.evidence_kind == m.evidence_kind
        assert restored.__class__ == m.__class__


# ------------------------------------------------------------------------------
# 6. Verification Orchestration & Matrix Edge Cases
# ------------------------------------------------------------------------------

def test_matrix_rejects_on_build_failure(ws):
    claim = Claim(claim_id="c_build", task_id="t1", statement="Build successful", claim_type=ClaimType.BUILD.value)
    bad_build = BuildEvidence(source="builder", is_observed=True, build_tool="cargo", exit_code=101, errors_count=1)
    res = ClaimAcceptanceMatrix.evaluate_multi_evidence(claim, [bad_build], ws)
    assert res.status == "REJECT"
    assert "Build failed" in res.reason


def test_matrix_rejects_on_security_findings(ws):
    claim = Claim(claim_id="c_sec", task_id="t2", statement="No vulnerabilities", claim_type=ClaimType.SECURITY.value)
    vuln_ev = SecurityEvidence(source="semgrep", is_observed=True, findings_count=3, passed=False)
    res = ClaimAcceptanceMatrix.evaluate_multi_evidence(claim, [vuln_ev], ws)
    assert res.status == "REJECT"
    assert "security finding" in res.reason


def test_matrix_empty_evidence_behavior_claim_inconclusive(ws):
    claim = Claim(claim_id="c_beh", task_id="t3", statement="Behavior verified", claim_type=ClaimType.BEHAVIOR.value)
    res = ClaimAcceptanceMatrix.evaluate_multi_evidence(claim, [], ws)
    assert res.status == "INCONCLUSIVE"


# ------------------------------------------------------------------------------
# 7. Semantic Impact Analyzer Edge Cases
# ------------------------------------------------------------------------------

def test_semantic_analyzer_symbol_resolution(ws):
    analyzer = SemanticImpactAnalyzer(workspace_root=ws)
    summary = analyzer.analyze(["pkg/mod.py"])
    assert len(summary.defined_symbols) >= 2  # class Helper and def entrypoint
    sym_names = [s.name for s in summary.defined_symbols]
    assert "Helper" in sym_names
    assert "entrypoint" in sym_names

    # Recommended tests should find tests/test_mod.py
    assert any("test_mod.py" in tf for tf in summary.recommended_test_files)


def test_semantic_analyzer_epistemic_block(ws):
    analyzer = SemanticImpactAnalyzer(workspace_root=ws)
    claim = Claim(claim_id="c_claim", task_id="t_claim", statement="Tests pass", claim_type="test_pass")
    with pytest.raises(EpistemicIntegrityError):
        analyzer.certify_claim(claim)


# ------------------------------------------------------------------------------
# 8. LocalMemoryProvider Edge Cases
# ------------------------------------------------------------------------------

def test_memory_provider_search_limit_and_filter(ws):
    mem = LocalMemoryProvider(workspace_dir=ws)

    for i in range(10):
        mem.remember(MemoryItem(
            key=f"ctx_{i}",
            content=f"Context content item number {i}",
            memory_type=MemoryType.CONTEXT,
        ))

    mem.remember(MemoryItem(
        key="fact_1",
        content="Verified fact item number 1",
        memory_type=MemoryType.VERIFIED_FACT,
        evidence_pointer="rcpt_001_hash",
    ))

    # Search with limit
    results = mem.search("content", limit=3)
    assert len(results) == 3

    # Search filtered by type
    facts = mem.search("item", memory_type=MemoryType.VERIFIED_FACT)
    assert len(facts) == 1
    assert facts[0].key == "fact_1"

    contexts = mem.search("item", memory_type=MemoryType.CONTEXT, limit=20)
    assert len(contexts) == 10
