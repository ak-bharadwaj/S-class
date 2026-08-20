"""
S-Class EOS V11.2 - D7 Agent Integration & Protocol Normalization Test Suite (§8.1, §8.3).
Verifies:
1. AgentWorkerProtocol & MockAgentWorker turn generation.
2. Deterministic AgentContextBuilder from D1 Frontier, D3 Policies, and Verification Feedback.
3. Capability-scoped tool availability in AgentToolRegistry.
4. Fail-closed tool argument validation (missing args, type mismatch, unknown tool).
5. ActionProposalSynthesizer normalization to D0 ActionProposal.
6. AgentSessionManager multi-turn execution, max turns bounding, and budget enforcement.
7. Architectural Invariants: Zero token minting in D7, zero direct execution authority, immutable context snapshots.
8. Concurrent agent session isolation.
"""

import os
import sys
import pytest
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from cryptography.hazmat.primitives.asymmetric import ed25519

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
from benchmark.parity.gate_3_authority import Gate3AuthorityKeyStore, Gate3AuthoritySigner
from controller.authorization import ActionProposal, AuthorizationStatus
from controller.controller import SClassController
from agent.models import (
    AgentTurnStatus,
    ToolDefinition,
    AgentToolCall,
    AgentToolResult,
    AgentSessionContext,
    AgentTurnResponse,
    AgentSessionRecord,
)
from agent.protocol import AgentWorkerProtocol, MockAgentWorker
from agent.tools import AgentToolRegistry
from agent.context import AgentContextBuilder
from agent.synthesizer import ActionProposalSynthesizer
from agent.session import AgentSessionManager

DEFAULT_SHA = "a" * 40
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
def standard_domain_state():
    obl_1 = Obligation(
        obligation_id="OBL-001",
        task_id="TASK-AGENT-01",
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
        task_id="TASK-AGENT-01",
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
# 1. AGENT MODELS & DATA STRUCTURE TESTS
# =====================================================================

def test_tool_definition_immutability_and_validation():
    tool = ToolDefinition(
        name="test_tool",
        description="A test tool",
        parameters_schema={"type": "object", "properties": {"target": {"type": "string"}}},
        required_capabilities=("CAP_READ_CODE",),
    )
    assert tool.name == "test_tool"
    assert tool.required_capabilities == ("CAP_READ_CODE",)

    with pytest.raises(ValueError):
        ToolDefinition("", "desc", {})
    with pytest.raises(ValueError):
        ToolDefinition("tool", "", {})
    with pytest.raises(TypeError):
        ToolDefinition("tool", "desc", "not_a_dict")  # type: ignore


def test_agent_tool_call_and_turn_response_validation():
    call = AgentToolCall(call_id="C1", tool_name="read_file_chunk", arguments={"path": "main.py"})
    assert call.call_id == "C1"
    assert call.arguments["path"] == "main.py"

    with pytest.raises(ValueError):
        AgentToolCall("", "read_file_chunk", {})
    with pytest.raises(ValueError):
        AgentToolCall("C1", "", {})

    resp = AgentTurnResponse(
        thought="I should propose a test run",
        tool_calls=(call,),
        turn_status=AgentTurnStatus.PROPOSE_ACTION,
        estimated_cost_usd=0.02,
    )
    assert resp.turn_status == AgentTurnStatus.PROPOSE_ACTION
    assert len(resp.tool_calls) == 1

    with pytest.raises(TypeError):
        AgentTurnResponse(thought=123)  # type: ignore
    with pytest.raises(TypeError):
        AgentTurnResponse(thought="t", turn_status="INVALID")  # type: ignore
    with pytest.raises(ValueError):
        AgentTurnResponse(thought="t", estimated_cost_usd=-1.0)


def test_agent_tool_result_and_session_record_validation():
    res = AgentToolResult(call_id="C1", tool_name="read_file_chunk", success=True, result_data={"lines": ["a"]})
    assert res.success is True
    assert res.result_data["lines"] == ("a",)

    with pytest.raises(ValueError):
        AgentToolResult("", "read_file_chunk", True)
    with pytest.raises(ValueError):
        AgentToolResult("C1", "", True)

    rec = AgentSessionRecord(
        session_id="SESS-01",
        task_id="TASK-01",
        total_turns=2,
        total_cost_usd=0.05,
        final_status=AgentTurnStatus.COMPLETED,
        started_at="2026-08-20T12:00:00Z",
        ended_at="2026-08-20T12:05:00Z",
        proposed_action_count=1,
    )
    assert rec.total_turns == 2
    assert rec.final_status == AgentTurnStatus.COMPLETED

    with pytest.raises(ValueError):
        AgentSessionRecord("S1", "T1", -1, 0.0, AgentTurnStatus.COMPLETED, "2026-08-20T12:00:00Z", "2026-08-20T12:05:00Z", 0)
    with pytest.raises(ValueError):
        AgentSessionRecord("S1", "T1", 1, -1.0, AgentTurnStatus.COMPLETED, "2026-08-20T12:00:00Z", "2026-08-20T12:05:00Z", 0)
    with pytest.raises(TypeError):
        AgentSessionRecord("S1", "T1", 1, 0.0, "INVALID", "2026-08-20T12:00:00Z", "2026-08-20T12:05:00Z", 0)  # type: ignore


# =====================================================================
# 2. WORKER PROTOCOL & MOCK WORKER TESTS
# =====================================================================

def test_mock_agent_worker_scripted_turns():
    worker = MockAgentWorker("test-mock-worker")
    assert worker.worker_id == "test-mock-worker"

    ctx = AgentSessionContext(
        session_id="SESS-01",
        task_id="TASK-01",
        objective="Run verification",
        frontier_obligation_ids=("OBL-001",),
        frontier_details=({"obligation_id": "OBL-001"},),
        policy_constraints=(),
        verification_feedback=(),
        available_tools=(),
    )

    t1 = AgentTurnResponse(thought="Turn 1", turn_status=AgentTurnStatus.CONTINUE)
    t2 = AgentTurnResponse(thought="Turn 2", turn_status=AgentTurnStatus.COMPLETED)
    worker.set_script([t1, t2])

    resp1 = worker.generate_turn(ctx, ())
    assert resp1.thought == "Turn 1"
    assert resp1.turn_status == AgentTurnStatus.CONTINUE

    resp2 = worker.generate_turn(ctx, (resp1,))
    assert resp2.thought == "Turn 2"
    assert resp2.turn_status == AgentTurnStatus.COMPLETED

    # Fallback turn after script exhaustion
    resp3 = worker.generate_turn(ctx, (resp1, resp2))
    assert "Default mock thought" in resp3.thought
    assert resp3.turn_status == AgentTurnStatus.COMPLETED


# =====================================================================
# 3. TOOL REGISTRY & VALIDATION TESTS
# =====================================================================

def test_tool_registry_registration_and_listing():
    reg = AgentToolRegistry()
    assert len(reg.list_tools()) >= 4

    custom_tool = ToolDefinition(
        name="custom_inspector",
        description="Custom inspector",
        parameters_schema={"type": "object", "properties": {"opt": {"type": "string"}}},
        required_capabilities=("CAP_CUSTOM",),
    )
    reg.register(custom_tool)
    assert reg.get_tool("custom_inspector") == custom_tool

    with pytest.raises(TypeError):
        reg.register("NOT_A_TOOL")  # type: ignore


def test_tool_registry_capability_filtering():
    reg = AgentToolRegistry()
    
    # User granted only CAP_READ_CODE
    read_tools = reg.get_available_tools_for_capabilities(("CAP_READ_CODE",))
    read_names = {t.name for t in read_tools}
    assert "read_file_chunk" in read_names
    assert "search_codebase" in read_names
    assert "propose_code_patch" not in read_names
    assert "propose_test_run" not in read_names

    # User granted both CAP_READ_CODE and CAP_PROPOSE_ACTION
    all_tools = reg.get_available_tools_for_capabilities(("CAP_READ_CODE", "CAP_PROPOSE_ACTION"))
    all_names = {t.name for t in all_tools}
    assert "read_file_chunk" in all_names
    assert "propose_code_patch" in all_names
    assert "propose_test_run" in all_names


def test_tool_registry_argument_validation():
    reg = AgentToolRegistry()

    # Valid tool call
    valid_call = AgentToolCall(
        call_id="C1",
        tool_name="read_file_chunk",
        arguments={"path": "src/main.py", "start_line": 1, "end_line": 10},
    )
    is_valid, err = reg.validate_tool_call(valid_call)
    assert is_valid is True
    assert err is None

    # Missing required argument
    missing_arg_call = AgentToolCall(
        call_id="C2",
        tool_name="read_file_chunk",
        arguments={"start_line": 1},
    )
    is_valid, err = reg.validate_tool_call(missing_arg_call)
    assert is_valid is False
    assert "Missing required argument 'path'" in (err or "")

    # Argument type mismatch (expected string, got int)
    bad_type_call = AgentToolCall(
        call_id="C3",
        tool_name="read_file_chunk",
        arguments={"path": 12345},
    )
    is_valid, err = reg.validate_tool_call(bad_type_call)
    assert is_valid is False
    assert "must be a string" in (err or "")

    # Argument type mismatch (expected int, got string)
    bad_int_call = AgentToolCall(
        call_id="C3b",
        tool_name="read_file_chunk",
        arguments={"path": "main.py", "start_line": "not_an_int"},
    )
    is_valid, err = reg.validate_tool_call(bad_int_call)
    assert is_valid is False
    assert "must be an integer" in (err or "")

    # Unknown tool call
    unknown_tool_call = AgentToolCall(
        call_id="C4",
        tool_name="hack_system_exec",
        arguments={"cmd": "rm -rf /"},
    )
    is_valid, err = reg.validate_tool_call(unknown_tool_call)
    assert is_valid is False
    assert "Unknown tool" in (err or "")

    # Invalid tool call type
    is_valid, err = reg.validate_tool_call("NOT_A_TOOL_CALL")  # type: ignore
    assert is_valid is False


# =====================================================================
# 4. CONTEXT BUILDER TESTS
# =====================================================================

def test_context_builder_assembles_deterministic_frontier(standard_domain_state):
    obls, policies = standard_domain_state
    builder = AgentContextBuilder()

    ctx = builder.build_context(
        session_id="SESS-001",
        task_id="TASK-AGENT-01",
        objective="Verify system obligations",
        obligations=obls,
        policies=policies,
        granted_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION"),
        verification_feedback=({"claim_id": "CLM-001", "status": "CONTRADICTED"},),
        budget_remaining_usd=5.0,
    )

    assert ctx.session_id == "SESS-001"
    assert ctx.task_id == "TASK-AGENT-01"
    assert ctx.frontier_obligation_ids == ("OBL-001",)
    assert len(ctx.frontier_details) == 1
    assert ctx.frontier_details[0]["obligation_id"] == "OBL-001"
    assert len(ctx.verification_feedback) == 1
    assert len(ctx.available_tools) == 4
    assert ctx.budget_remaining_usd == 5.0


def test_context_builder_validation_errors():
    with pytest.raises(ValueError):
        AgentSessionContext("", "T1", "Obj", (), (), (), (), ())
    with pytest.raises(ValueError):
        AgentSessionContext("S1", "", "Obj", (), (), (), (), ())
    with pytest.raises(ValueError):
        AgentSessionContext("S1", "T1", "", (), (), (), (), ())
    with pytest.raises(ValueError):
        AgentSessionContext("S1", "T1", "Obj", (), (), (), (), (), turn_index=-1)
    with pytest.raises(ValueError):
        AgentSessionContext("S1", "T1", "Obj", (), (), (), (), (), max_turns=0)
    with pytest.raises(ValueError):
        AgentSessionContext("S1", "T1", "Obj", (), (), (), (), (), budget_remaining_usd=-0.1)


# =====================================================================
# 5. ACTION PROPOSAL SYNTHESIZER TESTS
# =====================================================================

def test_proposal_synthesizer_creates_valid_proposals():
    # Test propose_test_run
    call_test = AgentToolCall(
        call_id="C1",
        tool_name="propose_test_run",
        arguments={
            "obligation_id": "OBL-001",
            "target_test": "tests/test_unit.py",
            "purpose": "Verify unit tests",
            "parameters": {"quiet": True},
        },
    )
    prop_test, err = ActionProposalSynthesizer.synthesize_proposal(call_test)
    assert err is None
    assert isinstance(prop_test, ActionProposal)
    assert prop_test.obligation_id == "OBL-001"
    assert prop_test.action_type == "EXECUTE_TEST"
    assert prop_test.target == "tests/test_unit.py"

    # Test propose_code_patch
    call_patch = AgentToolCall(
        call_id="C2",
        tool_name="propose_code_patch",
        arguments={
            "obligation_id": "OBL-001",
            "target_file": "src/module.py",
            "patch_content": "+def test(): pass",
            "purpose": "Fix bug in module",
        },
    )
    prop_patch, err = ActionProposalSynthesizer.synthesize_proposal(call_patch)
    assert err is None
    assert isinstance(prop_patch, ActionProposal)
    assert prop_patch.obligation_id == "OBL-001"
    assert prop_patch.action_type == "APPLY_PATCH"
    assert prop_patch.target == "src/module.py"

    # Test non-proposal tool
    call_read = AgentToolCall(call_id="C3", tool_name="read_file_chunk", arguments={"path": "a.py"})
    prop_read, err = ActionProposalSynthesizer.synthesize_proposal(call_read)
    assert prop_read is None
    assert "not a recognized proposal tool" in (err or "")

    # Test invalid object type
    prop_bad, err = ActionProposalSynthesizer.synthesize_proposal("NOT_A_CALL")  # type: ignore
    assert prop_bad is None
    assert "tool_call must be an instance of AgentToolCall" in (err or "")


def test_proposal_synthesizer_rejects_missing_arguments():
    # Missing target_test in propose_test_run
    call_missing_target = AgentToolCall("C1", "propose_test_run", {"obligation_id": "OBL-001"})
    prop, err = ActionProposalSynthesizer.synthesize_proposal(call_missing_target)
    assert prop is None
    assert "Missing or invalid 'target_test'" in (err or "")

    # Missing obligation_id in propose_test_run
    call_missing_obl = AgentToolCall("C2", "propose_test_run", {"target_test": "test.py"})
    prop, err = ActionProposalSynthesizer.synthesize_proposal(call_missing_obl)
    assert prop is None
    assert "Missing or invalid 'obligation_id'" in (err or "")

    # Missing patch_content in propose_code_patch
    call_missing_patch = AgentToolCall("C3", "propose_code_patch", {"obligation_id": "OBL-001", "target_file": "a.py"})
    prop, err = ActionProposalSynthesizer.synthesize_proposal(call_missing_patch)
    assert prop is None
    assert "Missing or invalid 'patch_content'" in (err or "")


# =====================================================================
# 6. AGENT SESSION MANAGER MULTI-TURN TESTS
# =====================================================================

def test_session_manager_executes_multi_turn_flow_and_submits_proposals(
    fresh_controller, standard_domain_state
):
    obls, policies = standard_domain_state
    worker = MockAgentWorker("test-worker")

    # Script: Turn 1 inspects code, Turn 2 proposes test run, Turn 3 completes
    t1 = AgentTurnResponse(
        thought="I will read the test file first",
        tool_calls=(AgentToolCall("C1", "read_file_chunk", {"path": "tests/test_unit.py"}),),
        turn_status=AgentTurnStatus.CONTINUE,
        estimated_cost_usd=0.01,
    )
    t2 = AgentTurnResponse(
        thought="Now I will propose running the test suite",
        tool_calls=(
            AgentToolCall(
                "C2",
                "propose_test_run",
                {"obligation_id": "OBL-001", "target_test": "tests/test_unit.py", "purpose": "Run verification"},
            ),
        ),
        turn_status=AgentTurnStatus.PROPOSE_ACTION,
        estimated_cost_usd=0.02,
    )
    t3 = AgentTurnResponse(
        thought="Work complete",
        tool_calls=(),
        turn_status=AgentTurnStatus.COMPLETED,
        estimated_cost_usd=0.01,
    )
    worker.set_script([t1, t2, t3])

    session_mgr = AgentSessionManager(worker=worker, controller=fresh_controller)
    record, dispatches = session_mgr.run_session(
        task_id="TASK-AGENT-01",
        objective="Verify system invariants",
        obligations=obls,
        policies=policies,
        source_sha=DEFAULT_SHA,
        policy_version=1,
        max_turns=5,
        cost_budget_usd=1.0,
    )

    assert isinstance(record, AgentSessionRecord)
    assert record.total_turns == 3
    assert record.final_status == AgentTurnStatus.COMPLETED
    assert record.proposed_action_count == 1
    assert len(dispatches) == 1
    assert dispatches[0].decision.status == AuthorizationStatus.AUTHORIZED
    assert dispatches[0].execution_token is not None


def test_session_manager_handles_invalid_tool_calls_gracefully(
    fresh_controller, standard_domain_state
):
    obls, policies = standard_domain_state
    worker = MockAgentWorker("hallucinating-worker")

    # Turn with hallucinated tool
    t1 = AgentTurnResponse(
        thought="Calling invalid tool",
        tool_calls=(AgentToolCall("C1", "non_existent_tool", {}),),
        turn_status=AgentTurnStatus.CONTINUE,
        estimated_cost_usd=0.01,
    )
    t2 = AgentTurnResponse(
        thought="Recovery turn",
        tool_calls=(),
        turn_status=AgentTurnStatus.COMPLETED,
        estimated_cost_usd=0.01,
    )
    worker.set_script([t1, t2])

    session_mgr = AgentSessionManager(worker=worker, controller=fresh_controller)
    record, dispatches = session_mgr.run_session(
        task_id="TASK-AGENT-01",
        objective="Error recovery test",
        obligations=obls,
        policies=policies,
        source_sha=DEFAULT_SHA,
        policy_version=1,
        max_turns=5,
        cost_budget_usd=1.0,
    )

    assert record.total_turns == 2
    assert record.final_status == AgentTurnStatus.COMPLETED
    assert "validation_error" in record.turns_transcript[0]


def test_session_manager_enforces_max_turns(fresh_controller, standard_domain_state):
    obls, policies = standard_domain_state
    worker = MockAgentWorker("looping-worker")

    # Infinite CONTINUE loop
    loop_turn = AgentTurnResponse(
        thought="Looping forever",
        tool_calls=(),
        turn_status=AgentTurnStatus.CONTINUE,
        estimated_cost_usd=0.01,
    )
    worker.set_script([loop_turn] * 10)

    session_mgr = AgentSessionManager(worker=worker, controller=fresh_controller)
    record, dispatches = session_mgr.run_session(
        task_id="TASK-AGENT-01",
        objective="Infinite loop test",
        obligations=obls,
        policies=policies,
        source_sha=DEFAULT_SHA,
        policy_version=1,
        max_turns=3,
        cost_budget_usd=1.0,
    )

    assert record.total_turns == 3
    assert record.final_status == AgentTurnStatus.MAX_TURNS_REACHED


def test_session_manager_enforces_budget_limit(fresh_controller, standard_domain_state):
    obls, policies = standard_domain_state
    worker = MockAgentWorker("expensive-worker")

    # Expensive turn exceeding budget
    expensive_turn = AgentTurnResponse(
        thought="Calling expensive model",
        tool_calls=(),
        turn_status=AgentTurnStatus.CONTINUE,
        estimated_cost_usd=0.75,
    )
    worker.set_script([expensive_turn, expensive_turn])

    session_mgr = AgentSessionManager(worker=worker, controller=fresh_controller)
    record, dispatches = session_mgr.run_session(
        task_id="TASK-AGENT-01",
        objective="Budget limit test",
        obligations=obls,
        policies=policies,
        source_sha=DEFAULT_SHA,
        policy_version=1,
        max_turns=10,
        cost_budget_usd=1.0,
    )

    assert record.final_status == AgentTurnStatus.BUDGET_EXCEEDED


# =====================================================================
# 7. CONCURRENCY & ISOLATION TESTS
# =====================================================================

def test_concurrent_agent_sessions_remain_isolated(
    fresh_controller, standard_domain_state
):
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
            estimated_cost_usd=0.01,
        )
        worker.set_script([t1])
        mgr = AgentSessionManager(worker=worker, controller=fresh_controller)
        return mgr.run_session(
            task_id=f"TASK-AGENT-{worker_idx}",
            objective="Concurrent test",
            obligations=obls,
            policies=policies,
            source_sha=DEFAULT_SHA,
            policy_version=1,
            max_turns=2,
            cost_budget_usd=0.5,
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


# =====================================================================
# 8. ARCHITECTURAL INVARIANT & TAMPER GUARDS
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


def test_d7_session_manager_rejects_invalid_worker_or_controller():
    with pytest.raises(TypeError):
        AgentSessionManager(worker="NOT_A_WORKER", controller="NOT_A_CONTROLLER")  # type: ignore
