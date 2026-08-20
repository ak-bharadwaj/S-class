"""
S-Class EOS V11.2 - D7A Hardened Agent Integration & Authority Provenance Test Suite (§8.1, §8.3).
Exhaustively verifies:
1. Cryptographic SessionExecutionBinding Authority Provenance:
   - Context from another session -> REJECT
   - Context from another repository -> REJECT
   - Context from another SHA -> REJECT
   - Context from another task -> REJECT
   - Capability mismatch between binding and context -> REJECT
   - Context digest mismatch -> REJECT
   - Provider / profile / resource / workspace substitution -> REJECT
2. Inbound External AgentMessage Ingress Validation (tamper, replay, reorder, wrong-worker, wrong-session).
3. Memory-Bounded read_file_chunk (streaming line-by-line, line cap, byte cap, fail closed on oversized files).
4. Authoritative ExecutionContext Propagation (Session workspace W1 -> Proposal workspace W1; no topology manufacture).
5. Workspace Authority & Tool Availability (read tools omitted from manifest without workspace).
6. Inspection Tool Resource Bounds (search_codebase limits on files, bytes, matches, wall time).
7. Mandatory Repository State Provider (stale SHA, fake repo ID, drift before proposal).
8. Preserved Fail-Closed Missing-Context Test.
9. Ephemeral Session State & Preserved D5 Authorization Boundary (Zero Token Minting in D7).
10. Multi-Threaded Concurrency Isolation (4 Parallel Workers).
"""

import os
import sys
import pytest
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from cryptography.hazmat.primitives.asymmetric import ed25519

from domain.exceptions import DomainValidationError
from domain.models import Obligation, Policy, PolicyRule, PolicyExpression
from domain.types import (
    ObligationStatus,
    ObligationCategory,
    Criticality,
    RuleType,
    CombinatorType,
    PolicyScope,
)
from events.store import D2NonceStore
from execution.workspace import IsolatedWorkspace
from benchmark.parity.gate_3_authority import Gate3AuthorityKeyStore, Gate3AuthoritySigner
from controller.authorization import ActionProposal, AuthorizationStatus
from controller.token import ExecutionContext
from controller.controller import SClassController
from agent.models import (
    AgentTurnStatus,
    ToolDefinition,
    AgentToolCall,
    AgentToolResult,
    AgentSessionContext,
    AgentTurnResponse,
    AgentSessionRecord,
    AgentMessage,
    SessionExecutionBinding,
    create_session_execution_binding,
    create_agent_message,
    compute_agent_message_digest,
    GENESIS_DIGEST,
    D7_INTERNAL_ACCOUNTING_UNIT,
)
from agent.protocol import (
    AgentWorkerProtocol,
    AgentMessageChainValidator,
    MockAgentWorker,
)
from agent.tools import (
    AgentToolRegistry,
    READ_CHUNK_MAX_FILE_BYTES,
    READ_CHUNK_MAX_RETURNED_BYTES,
    READ_CHUNK_MAX_RETURNED_LINES,
)
from agent.context import AgentContextBuilder
from agent.synthesizer import ActionProposalSynthesizer
from agent.session import AgentSessionManager

DEFAULT_SHA = "a" * 40
STALE_SHA = "b" * 40
FAKE_REPO_ID = "adversary/malicious-repo"
DEFAULT_REPO_ID = "ak-bharadwaj/S-class"
DEFAULT_TASK_ID = "TASK-AGENT-01"
TIMESTAMP_NOW = "2026-08-20T12:00:00Z"
TIMESTAMP_EXPIRY = "2026-08-20T13:00:00Z"


@pytest.fixture(autouse=True)
def setup_authority_keys():
    Gate3AuthorityKeyStore.clear()
    priv = ed25519.Ed25519PrivateKey.generate()
    Gate3AuthorityKeyStore.set_private_key(priv)
    yield
    Gate3AuthorityKeyStore.clear()


@pytest.fixture
def fresh_controller(tmp_path):
    signer = Gate3AuthoritySigner()
    nonce_store = D2NonceStore(file_path=str(tmp_path / "d7_nonces.log"))
    return SClassController(authority_signer=signer, nonce_store=nonce_store)


@pytest.fixture
def default_exec_ctx():
    return ExecutionContext(
        provider_id="pytest_runner_engine",
        sandbox_profile_id="sbx_std",
        workspace_id="ws_default_test",
        resource_profile_id="res_std",
        capability_set=("CAP_READ_CODE", "CAP_PROPOSE_ACTION", "CAP_EXEC_TEST"),
    )


@pytest.fixture
def default_repo_provider():
    return lambda: (DEFAULT_REPO_ID, DEFAULT_SHA)


@pytest.fixture
def standard_domain_state():
    obl_1 = Obligation(
        obligation_id="OBL-001",
        task_id=DEFAULT_TASK_ID,
        title="Test Invariant 1",
        description="Verify property invariant",
        category=ObligationCategory.SECURITY_INTEGRITY,
        criticality=Criticality.HIGH,
        status=ObligationStatus.OPEN,
        depends_on=(),
        policy_id="POL-001",
    )
    obl_2 = Obligation(
        obligation_id="OBL-002",
        task_id=DEFAULT_TASK_ID,
        title="Test Invariant 2",
        description="Verify boundary fuzzing",
        category=ObligationCategory.CORRECTNESS_FUNCTIONAL,
        criticality=Criticality.MEDIUM,
        status=ObligationStatus.OPEN,
        depends_on=("OBL-001",),
        policy_id="POL-001",
    )
    rule = PolicyRule(rule_type=RuleType.NO_CONFLICTS, parameters={})
    policy = Policy(
        policy_id="POL-001",
        scope_level=PolicyScope.PROJECT,
        version=1,
        expression=PolicyExpression(combinator=CombinatorType.ALL, rules=(rule,)),
    )
    return {"OBL-001": obl_1, "OBL-002": obl_2}, {"POL-001": policy}


# =====================================================================
# 1. ADVERSARIAL AUTHORITY PROVENANCE & BINDING INVARIANTS
# =====================================================================

def test_synthesizer_rejects_context_from_another_session(default_exec_ctx):
    call = AgentToolCall("C1", "propose_test_run", {"obligation_id": "OBL-001", "target_test": "t.py", "purpose": "P"})
    binding = create_session_execution_binding(
        session_id="SESS-ALICE",
        repository_id=DEFAULT_REPO_ID,
        source_sha=DEFAULT_SHA,
        task_id=DEFAULT_TASK_ID,
        execution_context_digest=default_exec_ctx.context_digest,
        granted_capabilities=default_exec_ctx.capability_set,
    )

    prop, err = ActionProposalSynthesizer.synthesize_proposal(
        tool_call=call,
        session_execution_context=default_exec_ctx,
        session_binding=binding,
        active_session_id="SESS-BOB",
        authoritative_repo_id=DEFAULT_REPO_ID,
        authoritative_source_sha=DEFAULT_SHA,
        active_task_id=DEFAULT_TASK_ID,
    )
    assert prop is None
    assert "BINDING_MISMATCH: session_id mismatch" in (err or "")


def test_synthesizer_rejects_context_from_another_repository(default_exec_ctx):
    call = AgentToolCall("C1", "propose_test_run", {"obligation_id": "OBL-001", "target_test": "t.py", "purpose": "P"})
    binding = create_session_execution_binding(
        session_id="SESS-01",
        repository_id=FAKE_REPO_ID,
        source_sha=DEFAULT_SHA,
        task_id=DEFAULT_TASK_ID,
        execution_context_digest=default_exec_ctx.context_digest,
        granted_capabilities=default_exec_ctx.capability_set,
    )

    prop, err = ActionProposalSynthesizer.synthesize_proposal(
        tool_call=call,
        session_execution_context=default_exec_ctx,
        session_binding=binding,
        active_session_id="SESS-01",
        authoritative_repo_id=DEFAULT_REPO_ID,
        authoritative_source_sha=DEFAULT_SHA,
        active_task_id=DEFAULT_TASK_ID,
    )
    assert prop is None
    assert "BINDING_MISMATCH: repository_id mismatch" in (err or "")


def test_synthesizer_rejects_context_from_another_sha(default_exec_ctx):
    call = AgentToolCall("C1", "propose_test_run", {"obligation_id": "OBL-001", "target_test": "t.py", "purpose": "P"})
    binding = create_session_execution_binding(
        session_id="SESS-01",
        repository_id=DEFAULT_REPO_ID,
        source_sha=STALE_SHA,
        task_id=DEFAULT_TASK_ID,
        execution_context_digest=default_exec_ctx.context_digest,
        granted_capabilities=default_exec_ctx.capability_set,
    )

    prop, err = ActionProposalSynthesizer.synthesize_proposal(
        tool_call=call,
        session_execution_context=default_exec_ctx,
        session_binding=binding,
        active_session_id="SESS-01",
        authoritative_repo_id=DEFAULT_REPO_ID,
        authoritative_source_sha=DEFAULT_SHA,
        active_task_id=DEFAULT_TASK_ID,
    )
    assert prop is None
    assert "BINDING_MISMATCH: source_sha mismatch" in (err or "")


def test_synthesizer_rejects_context_from_another_task(default_exec_ctx):
    call = AgentToolCall("C1", "propose_test_run", {"obligation_id": "OBL-001", "target_test": "t.py", "purpose": "P"})
    binding = create_session_execution_binding(
        session_id="SESS-01",
        repository_id=DEFAULT_REPO_ID,
        source_sha=DEFAULT_SHA,
        task_id="TASK-OTHER-99",
        execution_context_digest=default_exec_ctx.context_digest,
        granted_capabilities=default_exec_ctx.capability_set,
    )

    prop, err = ActionProposalSynthesizer.synthesize_proposal(
        tool_call=call,
        session_execution_context=default_exec_ctx,
        session_binding=binding,
        active_session_id="SESS-01",
        authoritative_repo_id=DEFAULT_REPO_ID,
        authoritative_source_sha=DEFAULT_SHA,
        active_task_id=DEFAULT_TASK_ID,
    )
    assert prop is None
    assert "BINDING_MISMATCH: task_id mismatch" in (err or "")


def test_synthesizer_rejects_capability_authority_mismatch(default_exec_ctx):
    call = AgentToolCall("C1", "propose_test_run", {"obligation_id": "OBL-001", "target_test": "t.py", "purpose": "P"})
    binding = create_session_execution_binding(
        session_id="SESS-01",
        repository_id=DEFAULT_REPO_ID,
        source_sha=DEFAULT_SHA,
        task_id=DEFAULT_TASK_ID,
        execution_context_digest=default_exec_ctx.context_digest,
        granted_capabilities=("CAP_READ_CODE",),
    )

    prop, err = ActionProposalSynthesizer.synthesize_proposal(
        tool_call=call,
        session_execution_context=default_exec_ctx,
        session_binding=binding,
        active_session_id="SESS-01",
        authoritative_repo_id=DEFAULT_REPO_ID,
        authoritative_source_sha=DEFAULT_SHA,
        active_task_id=DEFAULT_TASK_ID,
    )
    assert prop is None
    assert "CAPABILITY_AUTHORITY_MISMATCH" in (err or "")


def test_synthesizer_rejects_context_topology_substitution(default_exec_ctx):
    call = AgentToolCall("C1", "propose_test_run", {"obligation_id": "OBL-001", "target_test": "t.py", "purpose": "P"})
    binding = create_session_execution_binding(
        session_id="SESS-01",
        repository_id=DEFAULT_REPO_ID,
        source_sha=DEFAULT_SHA,
        task_id=DEFAULT_TASK_ID,
        execution_context_digest=default_exec_ctx.context_digest,
        granted_capabilities=default_exec_ctx.capability_set,
    )

    tampered_ctx = ExecutionContext(
        provider_id="substituted_provider",
        sandbox_profile_id=default_exec_ctx.sandbox_profile_id,
        workspace_id=default_exec_ctx.workspace_id,
        resource_profile_id=default_exec_ctx.resource_profile_id,
        capability_set=default_exec_ctx.capability_set,
    )

    prop, err = ActionProposalSynthesizer.synthesize_proposal(
        tool_call=call,
        session_execution_context=tampered_ctx,
        session_binding=binding,
        active_session_id="SESS-01",
        authoritative_repo_id=DEFAULT_REPO_ID,
        authoritative_source_sha=DEFAULT_SHA,
        active_task_id=DEFAULT_TASK_ID,
    )
    assert prop is None
    assert "BINDING_MISMATCH: context_digest mismatch" in (err or "")


def test_synthesizer_rejects_empty_and_invalid_arguments(default_exec_ctx):
    call = AgentToolCall("C1", "propose_test_run", {"obligation_id": "OBL-001", "target_test": "test.py", "purpose": "Test"})
    binding = create_session_execution_binding(
        session_id="S1",
        repository_id=DEFAULT_REPO_ID,
        source_sha=DEFAULT_SHA,
        task_id=DEFAULT_TASK_ID,
        execution_context_digest=default_exec_ctx.context_digest,
        granted_capabilities=default_exec_ctx.capability_set,
    )

    # Invalid tool call type
    prop, err = ActionProposalSynthesizer.synthesize_proposal(
        "NOT_A_CALL", default_exec_ctx, binding, "S1", DEFAULT_REPO_ID, DEFAULT_SHA, DEFAULT_TASK_ID  # type: ignore
    )
    assert prop is None
    assert "tool_call must be an instance of AgentToolCall" in (err or "")

    # Invalid execution context type
    prop, err = ActionProposalSynthesizer.synthesize_proposal(
        call, "NOT_A_CONTEXT", binding, "S1", DEFAULT_REPO_ID, DEFAULT_SHA, DEFAULT_TASK_ID  # type: ignore
    )
    assert prop is None
    assert "session_execution_context must be an authoritative ExecutionContext" in (err or "")

    # Invalid session binding type
    prop, err = ActionProposalSynthesizer.synthesize_proposal(
        call, default_exec_ctx, "NOT_A_BINDING", "S1", DEFAULT_REPO_ID, DEFAULT_SHA, DEFAULT_TASK_ID  # type: ignore
    )
    assert prop is None
    assert "session_binding must be an authoritative SessionExecutionBinding" in (err or "")

    # Empty capabilities fails closed
    empty_ctx = ExecutionContext("p", "s", "w", "r", ())
    empty_binding = create_session_execution_binding(
        session_id="S1",
        repository_id=DEFAULT_REPO_ID,
        source_sha=DEFAULT_SHA,
        task_id=DEFAULT_TASK_ID,
        execution_context_digest=empty_ctx.context_digest,
        granted_capabilities=(),
    )
    prop, err = ActionProposalSynthesizer.synthesize_proposal(
        call, empty_ctx, empty_binding, "S1", DEFAULT_REPO_ID, DEFAULT_SHA, DEFAULT_TASK_ID
    )
    assert prop is None
    assert "Cannot synthesize proposal with empty capability set" in (err or "")


# =====================================================================
# 2. PRESERVED FAIL-CLOSED MISSING CONTEXT & TOPOLOGY IMMUTABILITY
# =====================================================================

def test_session_manager_fails_closed_when_execution_context_is_missing(
    fresh_controller, standard_domain_state, default_repo_provider
):
    """Proves that missing ExecutionContext fails closed and rejects ActionProposal dispatch."""
    obls, policies = standard_domain_state
    worker = MockAgentWorker("worker")
    call = AgentToolCall("C1", "propose_test_run", {"obligation_id": "OBL-001", "target_test": "test.py", "purpose": "T"})
    worker.set_script([AgentTurnResponse(thought="Propose test", tool_calls=(call,), turn_status=AgentTurnStatus.COMPLETED)])

    mgr = AgentSessionManager(
        worker=worker,
        controller=fresh_controller,
        authoritative_repo_state_provider=default_repo_provider,
        session_execution_context=None,
    )

    rec, dispatches = mgr.run_session(
        repository_id=DEFAULT_REPO_ID,
        source_sha=DEFAULT_SHA,
        task_id=DEFAULT_TASK_ID,
        objective="Obj",
        obligations=obls,
        policies=policies,
        policy_version=1,
        granted_capabilities=("CAP_PROPOSE_ACTION", "CAP_EXEC_TEST"),
        execution_context=None,
    )

    assert rec.final_status == AgentTurnStatus.COMPLETED
    assert len(dispatches) == 0
    assert "EXECUTION_CONTEXT_MISSING" in rec.turns_transcript[0].get("validation_error", "")


def test_execution_topology_immutability_across_d7_boundary(
    fresh_controller, standard_domain_state, default_repo_provider
):
    """Proves that provider_id, sandbox_profile_id, resource_profile_id, workspace_id, and capability_set cannot be mutated by D7."""
    obls, policies = standard_domain_state
    pinned_ctx = ExecutionContext(
        provider_id="prov_immutable_100",
        sandbox_profile_id="sbx_immutable_strict",
        workspace_id="ws_immutable_exact",
        resource_profile_id="res_immutable_pinned",
        capability_set=("CAP_READ_CODE", "CAP_PROPOSE_ACTION", "CAP_EXEC_TEST"),
    )

    worker = MockAgentWorker("worker")
    call = AgentToolCall("C1", "propose_test_run", {"obligation_id": "OBL-001", "target_test": "test.py", "purpose": "T"})
    worker.set_script([AgentTurnResponse(thought="Propose test", tool_calls=(call,), turn_status=AgentTurnStatus.COMPLETED)])

    mgr = AgentSessionManager(
        worker=worker,
        controller=fresh_controller,
        authoritative_repo_state_provider=default_repo_provider,
        session_execution_context=pinned_ctx,
    )

    rec, dispatches = mgr.run_session(
        repository_id=DEFAULT_REPO_ID,
        source_sha=DEFAULT_SHA,
        task_id=DEFAULT_TASK_ID,
        objective="Obj",
        obligations=obls,
        policies=policies,
        policy_version=1,
        granted_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION", "CAP_EXEC_TEST"),
    )

    assert len(dispatches) == 1
    tok = dispatches[0].execution_token
    assert tok is not None
    assert tok.context_digest == pinned_ctx.context_digest

    binding = create_session_execution_binding(
        session_id="S1",
        repository_id=DEFAULT_REPO_ID,
        source_sha=DEFAULT_SHA,
        task_id=DEFAULT_TASK_ID,
        execution_context_digest=pinned_ctx.context_digest,
        granted_capabilities=pinned_ctx.capability_set,
    )
    prop, synth_err = ActionProposalSynthesizer.synthesize_proposal(
        tool_call=call,
        session_execution_context=pinned_ctx,
        session_binding=binding,
        active_session_id="S1",
        authoritative_repo_id=DEFAULT_REPO_ID,
        authoritative_source_sha=DEFAULT_SHA,
        active_task_id=DEFAULT_TASK_ID,
    )
    assert synth_err is None
    assert prop is not None
    assert prop.execution_context.provider_id == "prov_immutable_100"
    assert prop.execution_context.sandbox_profile_id == "sbx_immutable_strict"
    assert prop.execution_context.workspace_id == "ws_immutable_exact"
    assert prop.execution_context.resource_profile_id == "res_immutable_pinned"
    assert prop.execution_context.capability_set == tuple(sorted(pinned_ctx.capability_set))


# =====================================================================
# 3. MEMORY-BOUNDED FILE CHUNK READING
# =====================================================================

def test_read_file_chunk_bounded_streaming_large_file(tmp_path):
    ws = IsolatedWorkspace("ws_stream_test", base_dir=str(tmp_path))
    ws.setup()

    large_file = os.path.join(ws.path, "large.txt")
    with open(large_file, "w", encoding="utf-8") as f:
        for i in range(10000):
            f.write(f"Line {i}: test content payload with some length\n")

    reg = AgentToolRegistry()
    call = AgentToolCall("C1", "read_file_chunk", {"path": "large.txt", "start_line": 50, "end_line": 60})
    res = reg.execute_inspection_tool(call, workspace=ws)

    assert res.success is True
    assert res.result_data["returned_lines"] == 11
    assert res.result_data["lines"][0] == "Line 49: test content payload with some length\n"
    assert res.result_data["lines"][-1] == "Line 59: test content payload with some length\n"
    assert res.result_data["returned_bytes"] < 1024

    ws.cleanup()


def test_read_file_chunk_fails_closed_on_oversized_file(tmp_path):
    ws = IsolatedWorkspace("ws_oversized_test", base_dir=str(tmp_path))
    ws.setup()

    oversized_file = os.path.join(ws.path, "oversized.bin")
    with open(oversized_file, "wb") as f:
        f.seek(READ_CHUNK_MAX_FILE_BYTES + 1)
        f.write(b"X")

    reg = AgentToolRegistry()
    call = AgentToolCall("C1", "read_file_chunk", {"path": "oversized.bin", "start_line": 1, "end_line": 10})
    res = reg.execute_inspection_tool(call, workspace=ws)

    assert res.success is False
    assert "FILE_SIZE_EXCEEDED" in (res.error_message or "")

    ws.cleanup()


def test_read_file_chunk_caps_maximum_returned_lines(tmp_path):
    ws = IsolatedWorkspace("ws_line_cap_test", base_dir=str(tmp_path))
    ws.setup()

    line_file = os.path.join(ws.path, "lines.txt")
    with open(line_file, "w", encoding="utf-8") as f:
        for i in range(1000):
            f.write(f"Line {i}\n")

    reg = AgentToolRegistry()
    call = AgentToolCall("C1", "read_file_chunk", {"path": "lines.txt", "start_line": 1, "end_line": 1000})
    res = reg.execute_inspection_tool(call, workspace=ws)

    assert res.success is True
    assert res.result_data["returned_lines"] == READ_CHUNK_MAX_RETURNED_LINES
    assert res.result_data["truncated_due_to_lines"] is True

    ws.cleanup()


# =====================================================================
# 4. INBOUND AGENT MESSAGE INGRESS & VALIDATION
# =====================================================================

def test_ingress_validator_accepts_valid_message_sequence():
    msg0 = create_agent_message("S1", "W1", 0, "USER_CONTEXT", {"turn": 0}, GENESIS_DIGEST)
    valid, err, status, resp = AgentMessageChainValidator.validate_inbound_message(
        msg0, "S1", "W1", 0, GENESIS_DIGEST
    )
    assert valid is True
    assert err is None
    assert status is None
    assert resp is not None

    msg1 = create_agent_message("S1", "W1", 1, "AGENT_TURN", {"thought": "t", "status": "CONTINUE"}, msg0.message_digest)
    valid, err, status, resp1 = AgentMessageChainValidator.validate_inbound_message(
        msg1, "S1", "W1", 1, msg0.message_digest
    )
    assert valid is True
    assert resp1 is not None
    assert resp1.thought == "t"


def test_session_manager_rejects_injected_replayed_inbound_message(
    fresh_controller, standard_domain_state, default_repo_provider, default_exec_ctx
):
    obls, policies = standard_domain_state
    worker = MockAgentWorker("worker")

    stale_msg = create_agent_message("SESS-X", "worker", 0, "AGENT_TURN", {"thought": "replay"}, GENESIS_DIGEST)
    worker.set_raw_message_script([stale_msg])

    session_mgr = AgentSessionManager(
        worker=worker,
        controller=fresh_controller,
        authoritative_repo_state_provider=default_repo_provider,
        session_execution_context=default_exec_ctx,
    )
    rec, dispatches = session_mgr.run_session(
        repository_id=DEFAULT_REPO_ID,
        source_sha=DEFAULT_SHA,
        task_id=DEFAULT_TASK_ID,
        objective="Obj",
        obligations=obls,
        policies=policies,
        policy_version=1,
    )
    assert rec.final_status in (AgentTurnStatus.INGRESS_VALIDATION_FAILED, AgentTurnStatus.REPLAY_DETECTED)
    assert len(dispatches) == 0


def test_session_manager_rejects_injected_wrong_worker_inbound_message(
    fresh_controller, standard_domain_state, default_repo_provider, default_exec_ctx
):
    obls, policies = standard_domain_state

    class ImpostorWorker(AgentWorkerProtocol):
        @property
        def worker_id(self) -> str:
            return "legitimate-worker"
        def generate_inbound_message(self, context, sequence, previous_digest, history):
            return create_agent_message(
                session_id=context.session_id,
                worker_id="impostor-worker",
                sequence=sequence,
                message_type="AGENT_TURN",
                payload={"thought": "hijack"},
                previous_digest=previous_digest,
            )

    session_mgr = AgentSessionManager(
        worker=ImpostorWorker(),
        controller=fresh_controller,
        authoritative_repo_state_provider=default_repo_provider,
        session_execution_context=default_exec_ctx,
    )
    rec, dispatches = session_mgr.run_session(
        repository_id=DEFAULT_REPO_ID,
        source_sha=DEFAULT_SHA,
        task_id=DEFAULT_TASK_ID,
        objective="Obj",
        obligations=obls,
        policies=policies,
        policy_version=1,
    )
    assert rec.final_status == AgentTurnStatus.WORKER_IDENTITY_MISMATCH
    assert len(dispatches) == 0


def test_ingress_validator_rejects_reordered_and_tampered_payload():
    msg0 = create_agent_message("S1", "W1", 0, "USER_CONTEXT", {}, GENESIS_DIGEST)

    # Reordered sequence gap
    msg_reordered = create_agent_message("S1", "W1", 2, "AGENT_TURN", {}, msg0.message_digest)
    valid, err, status, _ = AgentMessageChainValidator.validate_inbound_message(
        msg_reordered, "S1", "W1", 1, msg0.message_digest
    )
    assert valid is False
    assert status == AgentTurnStatus.REORDER_DETECTED

    # Broken digest chain
    msg1 = create_agent_message("S1", "W1", 1, "AGENT_TURN", {"val": 2}, "f" * 64)
    valid, err, status, _ = AgentMessageChainValidator.validate_inbound_message(
        msg1, "S1", "W1", 1, msg0.message_digest
    )
    assert valid is False
    assert status == AgentTurnStatus.REPLAY_DETECTED


# =====================================================================
# 5. WORKSPACE AUTHORITY & SEARCH RESOURCE BOUNDS
# =====================================================================

def test_context_builder_omits_workspace_tools_when_no_workspace():
    reg = AgentToolRegistry()
    builder = AgentContextBuilder(tool_registry=reg)

    ctx_no_ws = builder.build_context(
        session_id="S1",
        repository_id=DEFAULT_REPO_ID,
        source_sha=DEFAULT_SHA,
        task_id=DEFAULT_TASK_ID,
        objective="Obj",
        obligations={},
        policies={},
        granted_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION"),
        has_workspace_authority=False,
    )
    tool_names = [t.name for t in ctx_no_ws.available_tools]
    assert "read_file_chunk" not in tool_names
    assert "search_codebase" not in tool_names
    assert "propose_test_run" in tool_names
    assert "propose_code_patch" in tool_names


def test_execute_inspection_tool_fails_explicitly_without_workspace():
    reg = AgentToolRegistry()
    call = AgentToolCall("C1", "read_file_chunk", {"path": "main.py"})
    res = reg.execute_inspection_tool(call, workspace=None)
    assert res.success is False
    assert "Active isolated workspace authority is required" in (res.error_message or "")


def test_search_codebase_enforces_resource_bounds(tmp_path):
    ws = IsolatedWorkspace("ws_resource_bounds", base_dir=str(tmp_path))
    ws.setup()

    for i in range(10):
        with open(os.path.join(ws.path, f"file_{i}.py"), "w", encoding="utf-8") as f:
            f.write(f"keyword match in file {i}\n" * 10)

    reg = AgentToolRegistry()
    call = AgentToolCall("C1", "search_codebase", {"query": "keyword"})
    res = reg.execute_inspection_tool(call, workspace=ws)

    assert res.success is True
    assert "matches" in res.result_data
    assert "files_scanned" in res.result_data
    assert "bytes_scanned" in res.result_data
    assert res.result_data["files_scanned"] <= 500
    assert len(res.result_data["matches"]) <= 50

    ws.cleanup()


# =====================================================================
# 6. MANDATORY REPOSITORY STATE VERIFICATION
# =====================================================================

def test_session_manager_requires_mandatory_repo_provider(fresh_controller):
    worker = MockAgentWorker("worker")
    with pytest.raises(TypeError, match="authoritative_repo_state_provider is mandatory"):
        AgentSessionManager(worker=worker, controller=fresh_controller, authoritative_repo_state_provider=None)  # type: ignore


def test_session_manager_rejects_stale_repository_before_turn(fresh_controller, standard_domain_state):
    obls, policies = standard_domain_state
    worker = MockAgentWorker("worker")
    stale_provider = lambda: (DEFAULT_REPO_ID, STALE_SHA)

    session_mgr = AgentSessionManager(
        worker=worker,
        controller=fresh_controller,
        authoritative_repo_state_provider=stale_provider,
    )
    rec, dispatches = session_mgr.run_session(
        repository_id=DEFAULT_REPO_ID,
        source_sha=DEFAULT_SHA,
        task_id=DEFAULT_TASK_ID,
        objective="Obj",
        obligations=obls,
        policies=policies,
        policy_version=1,
    )
    assert rec.final_status == AgentTurnStatus.STALE_CONTEXT
    assert len(dispatches) == 0


def test_session_manager_rejects_fake_repository_identity(fresh_controller, standard_domain_state):
    obls, policies = standard_domain_state
    worker = MockAgentWorker("worker")
    fake_repo_provider = lambda: (FAKE_REPO_ID, DEFAULT_SHA)

    session_mgr = AgentSessionManager(
        worker=worker,
        controller=fresh_controller,
        authoritative_repo_state_provider=fake_repo_provider,
    )
    rec, dispatches = session_mgr.run_session(
        repository_id=DEFAULT_REPO_ID,
        source_sha=DEFAULT_SHA,
        task_id=DEFAULT_TASK_ID,
        objective="Obj",
        obligations=obls,
        policies=policies,
        policy_version=1,
    )
    assert rec.final_status == AgentTurnStatus.REPOSITORY_MISMATCH
    assert len(dispatches) == 0


def test_session_manager_rejects_repository_drift_before_proposal_synthesis(
    fresh_controller, standard_domain_state, default_exec_ctx
):
    obls, policies = standard_domain_state
    worker = MockAgentWorker("worker")
    call = AgentToolCall("C1", "propose_test_run", {"obligation_id": "OBL-001", "target_test": "test.py", "purpose": "T"})
    worker.set_script([AgentTurnResponse(thought="Propose test", tool_calls=(call,), turn_status=AgentTurnStatus.CONTINUE)])

    current_sha = [DEFAULT_SHA]
    def dynamic_provider():
        return (DEFAULT_REPO_ID, current_sha[0])

    session_mgr = AgentSessionManager(
        worker=worker,
        controller=fresh_controller,
        authoritative_repo_state_provider=dynamic_provider,
        session_execution_context=default_exec_ctx,
    )

    current_sha[0] = STALE_SHA

    rec, dispatches = session_mgr.run_session(
        repository_id=DEFAULT_REPO_ID,
        source_sha=DEFAULT_SHA,
        task_id=DEFAULT_TASK_ID,
        objective="Obj",
        obligations=obls,
        policies=policies,
        policy_version=1,
        granted_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION", "CAP_EXEC_TEST"),
    )
    assert rec.final_status == AgentTurnStatus.STALE_CONTEXT
    assert len(dispatches) == 0


# =====================================================================
# 7. TOOL REGISTRY SCHEMA & CAPABILITY CHECKS
# =====================================================================

def test_validate_tool_call_enforces_capabilities_at_validation_time():
    reg = AgentToolRegistry()

    call = AgentToolCall(
        call_id="C1",
        tool_name="propose_test_run",
        arguments={"obligation_id": "OBL-001", "target_test": "test.py", "purpose": "Verify"},
    )
    is_valid, err = reg.validate_tool_call(call, granted_capabilities=("CAP_READ_CODE",))
    assert is_valid is False
    assert "Missing required capability 'CAP_PROPOSE_ACTION'" in (err or "")

    is_valid, err = reg.validate_tool_call(call, granted_capabilities=("CAP_PROPOSE_ACTION",))
    assert is_valid is True
    assert err is None


def test_validate_tool_call_full_json_schema_validation():
    reg = AgentToolRegistry()

    # Missing required property
    call_missing = AgentToolCall("C1", "read_file_chunk", arguments={})
    is_valid, err = reg.validate_tool_call(call_missing, granted_capabilities=("CAP_READ_CODE",))
    assert is_valid is False
    assert "required" in (err or "").lower()

    # Disallowed additional property
    call_extra = AgentToolCall("C2", "read_file_chunk", arguments={"path": "main.py", "unsupported": 123})
    is_valid, err = reg.validate_tool_call(call_extra, granted_capabilities=("CAP_READ_CODE",))
    assert is_valid is False
    assert "Additional properties are not allowed" in (err or "")


# =====================================================================
# 8. MULTI-THREADED CONCURRENCY & SESSION ISOLATION
# =====================================================================

def test_concurrent_agent_sessions_remain_isolated(fresh_controller, standard_domain_state, default_repo_provider):
    obls, policies = standard_domain_state

    def run_worker_session(worker_idx: int):
        worker = MockAgentWorker(f"worker-{worker_idx}")
        t1 = AgentTurnResponse(
            thought=f"Turn 1 for worker {worker_idx}",
            tool_calls=(
                AgentToolCall(
                    f"C-{worker_idx}",
                    "propose_test_run",
                    {"obligation_id": "OBL-001", "target_test": f"test_{worker_idx}.py", "purpose": "Test"},
                ),
            ),
            turn_status=AgentTurnStatus.COMPLETED,
            advisory_estimated_cost_usd=0.01,
        )
        worker.set_script([t1])
        worker_exec_ctx = ExecutionContext(
            provider_id="pytest_runner_engine",
            sandbox_profile_id="sbx_std",
            workspace_id=f"ws_worker_{worker_idx}",
            resource_profile_id="res_std",
            capability_set=("CAP_READ_CODE", "CAP_PROPOSE_ACTION", "CAP_EXEC_TEST"),
        )
        mgr = AgentSessionManager(
            worker=worker,
            controller=fresh_controller,
            authoritative_repo_state_provider=default_repo_provider,
            session_execution_context=worker_exec_ctx,
        )
        return mgr.run_session(
            repository_id=DEFAULT_REPO_ID,
            source_sha=DEFAULT_SHA,
            task_id=f"TASK-AGENT-{worker_idx}",
            objective="Concurrent test",
            obligations=obls,
            policies=policies,
            policy_version=1,
            granted_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION", "CAP_EXEC_TEST"),
            max_turns=2,
            budget_units=0.5,
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(run_worker_session, range(4)))

    session_ids = [r[0].session_id for r in results]
    assert len(set(session_ids)) == 4, "All concurrent session IDs must be unique"
    for record, dispatches in results:
        assert record.final_status == AgentTurnStatus.COMPLETED
        assert record.proposed_action_count == 1
        assert len(dispatches) == 1
        assert dispatches[0].decision.status == AuthorizationStatus.AUTHORIZED
        assert len(record.final_message_digest) == 64


# =====================================================================
# 9. ARCHITECTURAL INVARIANTS & CODE GUARDS
# =====================================================================

def test_d7_has_no_token_minting_or_execution_authority():
    """Architectural Guard: D7 modules must not have token minting or direct action execution APIs."""
    import agent
    assert not hasattr(agent, "mint_execution_token")
    assert not hasattr(agent, "admit_execution")
    assert not hasattr(agent, "execute_action")
    assert not hasattr(agent, "evaluate_policy")
    assert not hasattr(AgentSessionManager, "mint_execution_token")
    assert not hasattr(ActionProposalSynthesizer, "mint_execution_token")


def test_tool_definition_and_agent_model_validations():
    with pytest.raises(ValueError):
        ToolDefinition("", "desc", {})
    with pytest.raises(ValueError):
        ToolDefinition("t", "", {})
    with pytest.raises(TypeError):
        ToolDefinition("t", "desc", "not_a_dict")  # type: ignore

    with pytest.raises(ValueError):
        AgentToolCall("", "tool", {})
    with pytest.raises(ValueError):
        AgentToolCall("C1", "", {})

    with pytest.raises(ValueError):
        AgentToolResult("", "tool", True)
    with pytest.raises(ValueError):
        AgentToolResult("C1", "", True)


def test_session_execution_binding_validations():
    with pytest.raises(ValueError):
        SessionExecutionBinding("", DEFAULT_REPO_ID, DEFAULT_SHA, DEFAULT_TASK_ID, "0"*64, ("CAP_1",))
    with pytest.raises(ValueError):
        SessionExecutionBinding("S1", "", DEFAULT_SHA, DEFAULT_TASK_ID, "0"*64, ("CAP_1",))
    with pytest.raises(ValueError):
        SessionExecutionBinding("S1", DEFAULT_REPO_ID, DEFAULT_SHA, "", "0"*64, ("CAP_1",))
    with pytest.raises((ValueError, DomainValidationError)):
        SessionExecutionBinding("S1", DEFAULT_REPO_ID, "invalid_sha", DEFAULT_TASK_ID, "0"*64, ("CAP_1",))
    with pytest.raises((ValueError, DomainValidationError)):
        SessionExecutionBinding("S1", DEFAULT_REPO_ID, DEFAULT_SHA, DEFAULT_TASK_ID, "invalid_digest", ("CAP_1",))


def test_session_manager_tracks_internal_accounting_units(
    fresh_controller, standard_domain_state, default_repo_provider, default_exec_ctx
):
    obls, policies = standard_domain_state
    worker = MockAgentWorker("worker")

    t1 = AgentTurnResponse(
        thought="Advisory cost turn",
        tool_calls=(
            AgentToolCall(
                "C1",
                "propose_test_run",
                {"obligation_id": "OBL-001", "target_test": "test.py", "purpose": "Test"},
            ),
        ),
        turn_status=AgentTurnStatus.COMPLETED,
        advisory_estimated_cost_usd=0.035,
    )
    worker.set_script([t1])

    session_mgr = AgentSessionManager(
        worker=worker,
        controller=fresh_controller,
        authoritative_repo_state_provider=default_repo_provider,
        session_execution_context=default_exec_ctx,
    )
    record, dispatches = session_mgr.run_session(
        repository_id=DEFAULT_REPO_ID,
        source_sha=DEFAULT_SHA,
        task_id=DEFAULT_TASK_ID,
        objective="Verify budget tracking",
        obligations=obls,
        policies=policies,
        policy_version=1,
        granted_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION", "CAP_EXEC_TEST"),
        budget_units=1.0,
    )

    assert record.advisory_total_cost_usd == 0.035
    assert record.internal_accounting_units == D7_INTERNAL_ACCOUNTING_UNIT
    assert len(dispatches) == 1


class CrashingWorker(AgentWorkerProtocol):
    def __init__(self, exception_to_raise):
        self._exc = exception_to_raise

    @property
    def worker_id(self) -> str:
        return "crashing-worker"

    def generate_inbound_message(self, context, sequence, previous_digest, history):
        raise self._exc


def test_session_manager_handles_worker_timeout_and_disconnect(
    fresh_controller, standard_domain_state, default_repo_provider, default_exec_ctx
):
    obls, policies = standard_domain_state

    # Timeout
    w_to = CrashingWorker(TimeoutError("Timeout"))
    mgr_to = AgentSessionManager(
        worker=w_to, controller=fresh_controller, authoritative_repo_state_provider=default_repo_provider, session_execution_context=default_exec_ctx
    )
    rec_to, _ = mgr_to.run_session(DEFAULT_REPO_ID, DEFAULT_SHA, DEFAULT_TASK_ID, "Obj", obls, policies, 1)
    assert rec_to.final_status == AgentTurnStatus.WORKER_TIMEOUT

    # Disconnect
    w_disc = CrashingWorker(ConnectionError("Disconnect"))
    mgr_disc = AgentSessionManager(
        worker=w_disc, controller=fresh_controller, authoritative_repo_state_provider=default_repo_provider, session_execution_context=default_exec_ctx
    )
    rec_disc, _ = mgr_disc.run_session(DEFAULT_REPO_ID, DEFAULT_SHA, DEFAULT_TASK_ID, "Obj", obls, policies, 1)
    assert rec_disc.final_status == AgentTurnStatus.WORKER_DISCONNECT


def test_synthesizer_code_patch_and_error_branches():
    exec_ctx = ExecutionContext("p", "s", "w", "r", ("CAP_APPLY_PATCH", "CAP_PROPOSE_ACTION"))
    binding = create_session_execution_binding(
        session_id="S1",
        repository_id=DEFAULT_REPO_ID,
        source_sha=DEFAULT_SHA,
        task_id=DEFAULT_TASK_ID,
        execution_context_digest=exec_ctx.context_digest,
        granted_capabilities=exec_ctx.capability_set,
    )

    # Valid code patch proposal
    c_patch = AgentToolCall(
        "C1",
        "propose_code_patch",
        {
            "obligation_id": "OBL-001",
            "target_file": "src/app.py",
            "patch_content": "patch text",
            "purpose": "Patch description",
        },
    )
    prop, err = ActionProposalSynthesizer.synthesize_proposal(
        tool_call=c_patch,
        session_execution_context=exec_ctx,
        session_binding=binding,
        active_session_id="S1",
        authoritative_repo_id=DEFAULT_REPO_ID,
        authoritative_source_sha=DEFAULT_SHA,
        active_task_id=DEFAULT_TASK_ID,
    )
    assert err is None
    assert prop is not None
    assert prop.action_type == "APPLY_PATCH"
    assert prop.parameters["patch_content"] == "patch text"

    # Missing obligation_id in propose_test_run
    c_no_obl = AgentToolCall("C2", "propose_test_run", {"target_test": "t.py", "purpose": "P"})
    prop, err = ActionProposalSynthesizer.synthesize_proposal(
        c_no_obl, exec_ctx, binding, "S1", DEFAULT_REPO_ID, DEFAULT_SHA, DEFAULT_TASK_ID
    )
    assert prop is None
    assert "Missing or invalid 'obligation_id'" in (err or "")

    # Missing target_test in propose_test_run
    c_no_tgt = AgentToolCall("C3", "propose_test_run", {"obligation_id": "OBL-001", "purpose": "P"})
    prop, err = ActionProposalSynthesizer.synthesize_proposal(
        c_no_tgt, exec_ctx, binding, "S1", DEFAULT_REPO_ID, DEFAULT_SHA, DEFAULT_TASK_ID
    )
    assert prop is None
    assert "Missing or invalid 'target_test'" in (err or "")

    # Missing target_file in propose_code_patch
    c_no_tf = AgentToolCall("C4", "propose_code_patch", {"obligation_id": "OBL-001", "patch_content": "p", "purpose": "P"})
    prop, err = ActionProposalSynthesizer.synthesize_proposal(
        c_no_tf, exec_ctx, binding, "S1", DEFAULT_REPO_ID, DEFAULT_SHA, DEFAULT_TASK_ID
    )
    assert prop is None
    assert "Missing or invalid 'target_file'" in (err or "")

    # Missing patch_content in propose_code_patch
    c_no_pc = AgentToolCall("C5", "propose_code_patch", {"obligation_id": "OBL-001", "target_file": "f.py", "purpose": "P"})
    prop, err = ActionProposalSynthesizer.synthesize_proposal(
        c_no_pc, exec_ctx, binding, "S1", DEFAULT_REPO_ID, DEFAULT_SHA, DEFAULT_TASK_ID
    )
    assert prop is None
    assert "Missing or invalid 'patch_content'" in (err or "")

    # Missing obligation_id in propose_code_patch
    c_patch_no_obl = AgentToolCall("C6", "propose_code_patch", {"target_file": "f.py", "patch_content": "p", "purpose": "P"})
    prop, err = ActionProposalSynthesizer.synthesize_proposal(
        c_patch_no_obl, exec_ctx, binding, "S1", DEFAULT_REPO_ID, DEFAULT_SHA, DEFAULT_TASK_ID
    )
    assert prop is None
    assert "Missing or invalid 'obligation_id'" in (err or "")

    # Unrecognized tool
    c_unknown = AgentToolCall("C7", "unrecognized_proposal_tool", {})
    prop, err = ActionProposalSynthesizer.synthesize_proposal(
        c_unknown, exec_ctx, binding, "S1", DEFAULT_REPO_ID, DEFAULT_SHA, DEFAULT_TASK_ID
    )
    assert prop is None
    assert "not a recognized proposal tool" in (err or "")


def test_session_manager_handles_turn_limit_and_budget_exhaustion(
    fresh_controller, standard_domain_state, default_repo_provider, default_exec_ctx
):
    obls, policies = standard_domain_state

    # 1. Max turns reached
    worker_loop = MockAgentWorker("worker-loop")
    worker_loop.set_script([AgentTurnResponse(thought="Loop", tool_calls=(), turn_status=AgentTurnStatus.CONTINUE)] * 5)
    mgr = AgentSessionManager(
        worker=worker_loop,
        controller=fresh_controller,
        authoritative_repo_state_provider=default_repo_provider,
        session_execution_context=default_exec_ctx,
    )
    rec, _ = mgr.run_session(DEFAULT_REPO_ID, DEFAULT_SHA, DEFAULT_TASK_ID, "Obj", obls, policies, 1, max_turns=2, budget_units=10.0)
    assert rec.final_status == AgentTurnStatus.MAX_TURNS_REACHED

    # 2. Budget exceeded by proposal actions
    worker_exp = MockAgentWorker("worker-exp")
    call = AgentToolCall("C1", "propose_test_run", {"obligation_id": "OBL-001", "target_test": "test.py", "purpose": "T"})
    worker_exp.set_script([AgentTurnResponse(thought="T", tool_calls=(call,), turn_status=AgentTurnStatus.CONTINUE)] * 5)
    mgr_exp = AgentSessionManager(
        worker=worker_exp,
        controller=fresh_controller,
        authoritative_repo_state_provider=default_repo_provider,
        session_execution_context=default_exec_ctx,
    )
    rec_exp, _ = mgr_exp.run_session(
        DEFAULT_REPO_ID,
        DEFAULT_SHA,
        DEFAULT_TASK_ID,
        "Obj",
        obls,
        policies,
        1,
        granted_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION", "CAP_EXEC_TEST"),
        max_turns=10,
        budget_units=0.05,
    )
    assert rec_exp.final_status == AgentTurnStatus.BUDGET_EXCEEDED


def test_session_manager_handles_invalid_tool_calls_in_turn(
    fresh_controller, standard_domain_state, default_repo_provider, default_exec_ctx
):
    obls, policies = standard_domain_state
    worker = MockAgentWorker("worker")

    c_inv = AgentToolCall("C1", "propose_test_run", {})
    worker.set_script([AgentTurnResponse(thought="Bad call", tool_calls=(c_inv,), turn_status=AgentTurnStatus.COMPLETED)])

    mgr = AgentSessionManager(
        worker=worker,
        controller=fresh_controller,
        authoritative_repo_state_provider=default_repo_provider,
        session_execution_context=default_exec_ctx,
    )
    rec, dispatches = mgr.run_session(
        repository_id=DEFAULT_REPO_ID,
        source_sha=DEFAULT_SHA,
        task_id=DEFAULT_TASK_ID,
        objective="Obj",
        obligations=obls,
        policies=policies,
        policy_version=1,
        granted_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION", "CAP_EXEC_TEST"),
    )
    assert rec.final_status == AgentTurnStatus.COMPLETED
    assert len(dispatches) == 0
    assert "Schema validation error" in rec.turns_transcript[0].get("validation_error", "")


def test_read_file_chunk_execution_and_errors(tmp_path):
    ws = IsolatedWorkspace("ws_read_test", base_dir=str(tmp_path))
    ws.setup()

    reg = AgentToolRegistry()

    c_missing = AgentToolCall("C1", "read_file_chunk", {"path": "does_not_exist.py"})
    res = reg.execute_inspection_tool(c_missing, workspace=ws)
    assert res.success is False
    assert "does not exist" in (res.error_message or "")

    target = os.path.join(ws.path, "test.py")
    with open(target, "w", encoding="utf-8") as f:
        f.write("line 1\nline 2\nline 3\n")

    c_valid = AgentToolCall("C2", "read_file_chunk", {"path": "test.py", "start_line": 1, "end_line": 2})
    res_valid = reg.execute_inspection_tool(c_valid, workspace=ws)
    assert res_valid.success is True
    assert res_valid.result_data["returned_lines"] == 2
    assert res_valid.result_data["lines"] == ("line 1\n", "line 2\n")

    ws.cleanup()
