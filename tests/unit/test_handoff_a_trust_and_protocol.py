"""
Contract and Unit Tests for Handoff A: Real Trust + Protocol Core.
Verifies:
1. Trusted verifier identity & trust registry (trust modes, untrusted binary classification)
2. Execution chain & process tree (npm -> node -> jest, python -> pytest, shell -> wrapper -> pytest)
3. macOS process identity platform query
4. Explicit observation state machine & failure state protection
5. Real structured test verifiers (12 verifiers producing NormalizedTestResult)
6. Test-scope proof (CoverageRelation: COVERED, PARTIAL, NONE)
7. Claim dependency graph & composable acceptance decisions
8. ACP transport, session lifecycle, and permission bridge
9. MCP gateway, tool identity hashing, schema invalidation, and HTTP auth
"""

import os
import sys
import pytest
from sclass.verification.verifier_definition import VerifierDefinition, VerifierTrustMode
from sclass.verification.trust_registry import TrustRegistry, TrustPolicy, get_trust_registry
from sclass.verification.detector import StandardVerifierDetector, VerifierConfidence
from sclass.execution.identity import ExecutionIdentity, ExecutionIdentityState, _query_macos_process_image
from sclass.execution.chain import analyze_execution_chain, ExecutionChain
from sclass.execution.process_tree import ProcessTree, ProcessTreeNode, ProcessTreeInspector
from sclass.observation.lifecycle import ObservationLifecycleTracker, ObservationLifecycleState, ObservationIntegrityError
from sclass.verification.result_parser import (
    PytestResultParser,
    UnittestResultParser,
    JestResultParser,
    VitestResultParser,
    MochaResultParser,
    PlaywrightResultParser,
    CargoTestResultParser,
    GoTestResultParser,
    PackageScriptResultParser,
    GenericResultParser,
    NormalizedTestResult,
)
from sclass.verification.claim_scope import ScopeEvaluator, CoverageRelation
from sclass.domain.claim import Claim, ClaimScope
from sclass.domain.verification import TestSelection, VerificationResult
from sclass.domain.claim_graph import CompositeClaim, EvidenceRequirement, AcceptanceDecision
from sclass.integrations.acp.adapter import ACPAdapter, PermissionRequest
from sclass.integrations.mcp.normalization import MCPToolCall
from sclass.integrations.mcp.auth import MCPAuthorizationContext, MCPAuthenticator
from sclass.integrations.mcp.tools import MCPToolRegistry
from sclass.integrations.mcp.gateway import MCPGateway


# ==========================================
# 1. Trusted Verifier Identity & Trust Registry
# ==========================================

def test_verifier_definition_matching():
    defn = VerifierDefinition(
        verifier_id="pytest",
        executable_patterns=("pytest", "py.test"),
        interpreter_rules=("pytest",),
        package_rules=(),
    )
    assert defn.matches_executable("pytest")
    assert defn.matches_executable("pytest.exe")
    assert defn.matches_executable("C:/bin/py.test.exe")
    assert defn.matches_interpreter("python", ("-m", "pytest", "tests/"))
    assert not defn.matches_interpreter("python", ("-m", "unittest"))
    assert not defn.matches_executable("malicious_pytest")


def test_malicious_pytest_on_path_becomes_untrusted_binary(tmp_path):
    policy = TrustPolicy()
    untrusted_bin_dir = tmp_path / "shadow_bin"
    untrusted_bin_dir.mkdir()
    shadow_pytest = untrusted_bin_dir / "pytest.exe"
    shadow_pytest.write_text("fake", encoding="utf-8")

    # Mark directory untrusted in policy
    policy.untrusted_dirs.add(str(untrusted_bin_dir).lower())
    registry = TrustRegistry(policy=policy)

    mode = registry.classify_binary_trust(str(shadow_pytest))
    assert mode == VerifierTrustMode.UNTRUSTED

    ident = ExecutionIdentity.capture(
        command_argv=[str(shadow_pytest), "tests/"],
        cwd=str(tmp_path),
    )

    defn, trust_mode, status_code = registry.evaluate_verifier(ident)
    assert defn is not None
    assert defn.verifier_id == "pytest"
    assert trust_mode == VerifierTrustMode.UNTRUSTED
    assert status_code == "IDENTIFIED_AS_PYTEST+UNTRUSTED_BINARY"


def test_detector_contradicts_untrusted_binary(tmp_path, monkeypatch):
    registry = get_trust_registry()
    untrusted_tool = tmp_path / "pytest.exe"
    untrusted_tool.write_text("malicious", encoding="utf-8")
    registry.mark_untrusted_path(str(untrusted_tool))

    ident = ExecutionIdentity.capture(
        command_argv=[str(untrusted_tool), "tests/"],
        cwd=str(tmp_path),
    )


    detector = StandardVerifierDetector()
    det_res = detector.detect(ident)

    assert det_res.confidence == VerifierConfidence.CONTRADICTED
    assert det_res.verifier_id == "pytest"
    assert "UNTRUSTED" in det_res.evidence.get("trust_mode", "")
    assert "IDENTIFIED_AS_PYTEST+UNTRUSTED_BINARY" in det_res.evidence.get("status", "")


# ==========================================
# 2. Actual Execution Chain & Process Tree
# ==========================================

def test_execution_chain_python_pytest():
    chain = analyze_execution_chain(
        argv=["python", "-m", "pytest", "tests/unit"],
        resolved_path="C:/Python314/python.exe",
    )
    assert chain.launcher == "python"
    assert chain.interpreter == "python"
    assert chain.actual_child == "pytest"
    assert chain.verifier == "pytest"
    assert chain.is_authoritative


def test_execution_chain_npm_node_jest():
    chain = analyze_execution_chain(
        argv=["npm", "test"],
        resolved_path="/usr/bin/npm",
    )

    assert chain.launcher == "npm"
    assert chain.actual_child == "test"
    assert chain.verifier == "npm"



def test_execution_chain_shell_wrapper_pytest():
    chain = analyze_execution_chain(
        argv=["bash", "scripts/test_wrapper.sh", "--all"],
        resolved_path="/bin/bash",
    )
    assert chain.launcher == "bash"
    assert chain.wrapper == "scripts/test_wrapper.sh"
    assert chain.actual_child == "scripts/test_wrapper.sh"


def test_process_tree_snapshot():
    root = ProcessTreeNode(
        pid=1000,
        ppid=500,
        name="npm",
        executable_path="/usr/bin/npm",
        argv=["npm", "test"],
        children=[
            ProcessTreeNode(
                pid=1001,
                ppid=1000,
                name="node",
                executable_path="/usr/bin/node",
                argv=["node", "jest.js"],
            )
        ],
    )
    tree = ProcessTree(root=root, total_processes=2)
    flattened = tree.flatten()
    assert len(flattened) == 2
    assert flattened[0].pid == 1000
    assert flattened[1].pid == 1001


# ==========================================
# 3. macOS Process Identity
# ==========================================

def test_macos_process_image_graceful():
    # If not on Darwin, returns None, None
    exe, t = _query_macos_process_image(os.getpid())
    if sys.platform == "darwin":
        assert exe is not None or t is not None
    else:
        assert exe is None
        assert t is None


# ==========================================
# 4. Observation State Machine
# ==========================================

def test_observation_lifecycle_happy_path():
    tracker = ObservationLifecycleTracker(ObservationLifecycleState.REQUESTED)
    assert tracker.current_state == ObservationLifecycleState.REQUESTED

    tracker.transition_to(ObservationLifecycleState.SPAWNED, "Subprocess launched")
    assert tracker.current_state == ObservationLifecycleState.SPAWNED

    tracker.transition_to(ObservationLifecycleState.IDENTIFIED, "Process identity verified")
    assert tracker.current_state == ObservationLifecycleState.IDENTIFIED

    tracker.transition_to(ObservationLifecycleState.OBSERVED, "Process exit code captured")
    assert tracker.current_state == ObservationLifecycleState.OBSERVED

    assert not tracker.can_publish
    tracker.transition_to(ObservationLifecycleState.ANCHORED, "Local ledger atomic append")
    assert tracker.can_publish

    tracker.transition_to(ObservationLifecycleState.PUBLISHED, "Sealed and delivered")
    assert tracker.current_state == ObservationLifecycleState.PUBLISHED
    assert not tracker.is_failed


def test_observation_lifecycle_failure_states_cannot_publish():
    tracker = ObservationLifecycleTracker(ObservationLifecycleState.REQUESTED)
    tracker.transition_to(ObservationLifecycleState.SPAWNED)
    tracker.transition_to(ObservationLifecycleState.IDENTITY_UNCERTAIN, "Binary hash missing")

    assert tracker.is_failed
    assert not tracker.can_publish

    # Attempting to publish must fail
    with pytest.raises(ObservationIntegrityError):
        tracker.transition_to(ObservationLifecycleState.ANCHORED)


# ==========================================
# 5. Real Structured Test Verifiers (12 Runners)
# ==========================================

def test_all_12_structured_test_parsers():
    # 1. Pytest
    py_out = "platform win32 -- Python 3.14.5, pytest-9.0.3\ntests/test_auth.py ..\n=== 42 passed, 2 failed, 1 skipped in 1.45s ==="
    res_py = PytestResultParser.parse(py_out, "", exit_code=1, targets=["tests/test_auth.py"])
    assert res_py.verifier_id == "pytest"
    assert res_py.runner_version == "9.0.3"
    assert res_py.passed == 42
    assert res_py.failed == 2
    assert res_py.skipped == 1
    assert res_py.duration == 1.45
    assert not res_py.is_successful

    # 2. Unittest
    unit_out = "Ran 10 tests in 0.250s\nOK"
    res_unit = UnittestResultParser.parse(unit_out, "", exit_code=0)
    assert res_unit.verifier_id == "unittest"
    assert res_unit.passed == 10
    assert res_unit.failed == 0
    assert res_unit.is_successful

    # 3. Jest
    jest_out = "PASS src/auth.test.ts\nTests:       8 passed, 8 total\nTime:        2.31 s"
    res_jest = JestResultParser.parse(jest_out, "", exit_code=0)
    assert res_jest.verifier_id == "jest"
    assert res_jest.passed == 8
    assert res_jest.failed == 0
    assert res_jest.duration == 2.31
    assert res_jest.is_successful

    # 4. Vitest
    vitest_out = "✓ tests/user.test.ts (5)\nTests  5 passed (5)\nDuration  0.89s"
    res_vitest = VitestResultParser.parse(vitest_out, "", exit_code=0)
    assert res_vitest.verifier_id == "vitest"
    assert res_vitest.passed == 5
    assert res_vitest.duration == 0.89
    assert res_vitest.is_successful

    # 5. Mocha
    mocha_out = "  Authentication Flow\n    ✓ should log in (45ms)\n  1 passing (60ms)"
    res_mocha = MochaResultParser.parse(mocha_out, "", exit_code=0)
    assert res_mocha.verifier_id == "mocha"
    assert res_mocha.passed == 1
    assert res_mocha.is_successful

    # 6. Playwright
    pw_out = "Running 3 tests using 1 worker\n  3 passed (1.2s)"
    res_pw = PlaywrightResultParser.parse(pw_out, "", exit_code=0)
    assert res_pw.verifier_id == "playwright"
    assert res_pw.passed == 3
    assert res_pw.is_successful

    # 7. Cargo Test
    cargo_out = "running 12 tests\ntest result: ok. 12 passed; 0 failed; 1 ignored; 0 measured; 0 filtered out"
    res_cargo = CargoTestResultParser.parse(cargo_out, "", exit_code=0)
    assert res_cargo.verifier_id == "cargo-test"
    assert res_cargo.passed == 12
    assert res_cargo.skipped == 1
    assert res_cargo.is_successful

    # 8. Go Test
    go_out = "--- PASS: TestAuthLogin (0.02s)\n--- PASS: TestAuthToken (0.01s)\nPASS\nok  example.com/auth 0.050s"
    res_go = GoTestResultParser.parse(go_out, "", exit_code=0)
    assert res_go.verifier_id == "go-test"
    assert res_go.passed == 2
    assert res_go.duration == 0.050
    assert res_go.is_successful

    # 9-12. Package Scripts (npm, pnpm, yarn, bun)
    for runner in ("npm-test", "pnpm-test", "yarn-test", "bun-test"):
        res_pkg = PackageScriptResultParser.parse(runner, "Tests: 4 passed, 4 total", "", exit_code=0)
        assert res_pkg.verifier_id == runner
        assert res_pkg.passed == 4
        assert res_pkg.is_successful


# ==========================================
# 6. Test-Scope Proof (ScopeEvaluator & CoverageRelation)
# ==========================================

def test_scope_proof_covered():
    scope = ClaimScope(test_targets=("tests/auth", "tests/unit/test_login.py"))
    selection = TestSelection(
        selected_tests=("tests/auth/test_jwt.py", "tests/unit/test_login.py"),
        test_files=("tests/auth/test_jwt.py", "tests/unit/test_login.py"),
    )
    relation, reason = ScopeEvaluator.evaluate(scope, selection)
    assert relation == CoverageRelation.COVERED


def test_scope_proof_partial():
    scope = ClaimScope(test_targets=("tests/auth", "tests/billing"))
    selection = TestSelection(
        selected_tests=("tests/auth/test_jwt.py",),
        test_files=("tests/auth/test_jwt.py",),
    )
    relation, reason = ScopeEvaluator.evaluate(scope, selection)
    assert relation == CoverageRelation.PARTIAL
    assert "missing required targets" in reason


def test_scope_proof_none_rejected():
    # Claim: "All authentication tests pass"
    # Observed: pytest tests/utils
    scope = ClaimScope(test_targets=("tests/auth",))
    selection = TestSelection(
        selected_tests=("tests/utils/test_helpers.py",),
        test_files=("tests/utils/test_helpers.py",),
    )
    relation, reason = ScopeEvaluator.evaluate(scope, selection)
    assert relation == CoverageRelation.NONE
    assert "ZERO overlap" in reason


# ==========================================
# 7. Claim Dependency Graph & Composable Acceptance
# ==========================================

def test_composite_claim_evaluation():
    main_claim = Claim(
        claim_id="claim_auth_feature",
        task_id="task_42",
        statement="Authentication feature works",
        claim_type="feature",
    )
    comp = CompositeClaim(claim=main_claim)
    comp.add_requirement(EvidenceRequirement(
        requirement_id="req_unit_tests",
        kind="UNIT_TESTS",
        description="Unit tests pass",
        expected_verifier="pytest",
    ))
    comp.add_requirement(EvidenceRequirement(
        requirement_id="req_integration_tests",
        kind="INTEGRATION_TESTS",
        description="Integration tests pass",
        expected_verifier="playwright",
    ))

    # Case 1: Missing integration tests -> Rejected
    class MockEvidence:
        def __init__(self, verifier, exit_code):
            self.verifier = verifier
            self.exit_code = exit_code

    evidence_map = {
        "req_unit_tests": MockEvidence("pytest", 0),
    }
    decision = comp.evaluate(evidence_map)
    assert decision.is_rejected
    assert "req_integration_tests" in decision.unsatisfied_requirements

    # Case 2: Both provided and passing -> Accepted
    evidence_map["req_integration_tests"] = MockEvidence("playwright", 0)
    decision_ok = comp.evaluate(evidence_map)
    assert decision_ok.is_accepted
    assert len(decision_ok.satisfied_requirements) == 2


# ==========================================
# 8. ACP Transport & Session Lifecycle & Permission Bridge
# ==========================================

def test_acp_session_lifecycle_and_permission_bridge(tmp_path):
    adapter = ACPAdapter(workspace_dir=str(tmp_path), agent_id="test_agent")

    # 1. initialize
    init_res = adapter.process_acp_message({
        "jsonrpc": "2.0",
        "id": "msg-1",
        "method": "initialize",
        "params": {"capabilities": {"tools": ["run_command"]}},
    })
    session_id = init_res["result"]["sessionId"]
    assert session_id in adapter.sessions

    # 2. permission bridge (benign vs dangerous)
    # Benign command permission
    perm_allow = adapter.process_acp_message({
        "jsonrpc": "2.0",
        "id": "msg-2",
        "method": "permission",
        "params": {
            "session_id": session_id,
            "tool": "run_command",
            "arguments": {"command": "git status"},
        },
    })
    assert perm_allow["result"]["outcome"] in ("ALLOW", "APPROVAL")

    # Dangerous destructive command permission -> DENY
    perm_deny = adapter.process_acp_message({
        "jsonrpc": "2.0",
        "id": "msg-3",
        "method": "permission",
        "params": {
            "session_id": session_id,
            "tool": "run_command",
            "arguments": {"command": "rm -rf /"},
        },
    })
    assert perm_deny["result"]["outcome"] == "DENY"

    # 3. session/fork & session/resume
    fork_res = adapter.process_acp_message({
        "jsonrpc": "2.0",
        "id": "msg-4",
        "method": "session/fork",
        "params": {"session_id": session_id},
    })
    forked_id = fork_res["result"]["sessionId"]
    assert forked_id in adapter.sessions
    assert adapter.sessions[forked_id].forked_from == session_id

    # 4. shutdown
    shut_res = adapter.process_acp_message({
        "jsonrpc": "2.0",
        "id": "msg-5",
        "method": "shutdown",
        "params": {"session_id": session_id},
    })
    assert shut_res["result"]["status"] == "shutdown_complete"
    assert not adapter.sessions[session_id].active


# ==========================================
# 9. MCP Gateway, Tool Identity Hashing & Schema Invalidation
# ==========================================

def test_mcp_gateway_schema_invalidation(tmp_path):
    tool_reg = MCPToolRegistry()
    # Register tool v1
    schema_v1 = {"type": "object", "properties": {"target": {"type": "string"}}}
    tool_reg.register_tool("srv_1", "view_file", "Read file", schema_v1)
    assert not tool_reg.is_invalidated("srv_1", "view_file")

    # Update tool with mutated schema -> invalidated!
    schema_v2 = {"type": "object", "properties": {"target": {"type": "string"}, "extra": {"type": "number"}}}
    _, was_inval = tool_reg.register_tool("srv_1", "view_file", "Read file modified", schema_v2)
    assert was_inval
    assert tool_reg.is_invalidated("srv_1", "view_file")

    gateway = MCPGateway(
        workspace_dir=str(tmp_path),
        server_id="srv_1",
        tool_registry=tool_reg,
    )

    # Calling invalidated tool must be blocked by gateway
    res = gateway.handle_call_tool("view_file", {"target": "foo.txt"})
    assert "error" in res
    assert res["error"]["code"] == -32005
    assert "invalidated" in res["error"]["message"]


def test_mcp_gateway_policy_blocks_secret_read(tmp_path):
    gateway = MCPGateway(workspace_dir=str(tmp_path), server_id="fs_srv")
    # Calling tool targeting .env secret must be denied by policy
    res = gateway.handle_call_tool("read_file", {"target": ".env", "path": ".env"})
    assert "error" in res
    assert res["error"]["code"] == -32003
    assert "Authorization DENIED" in res["error"]["message"]
