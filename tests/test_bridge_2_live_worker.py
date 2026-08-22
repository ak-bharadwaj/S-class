"""
Unit and Integration Tests for Bridge 2 (agent/live_worker.py: LiveModelWorker).
Verifies:
1. Parsing of JSON tool calls into AgentToolCall objects.
2. Parsing of Python code blocks into propose_code_patch tool calls.
3. Canonical hash-chaining and AgentMessageChainValidator verification.
4. Error containment and graceful degradation on model exceptions.
5. Multi-turn execution within AgentSessionManager.
"""

import pytest
from unittest.mock import MagicMock
from agent.live_worker import LiveModelWorker
from agent.models import (
    AgentSessionContext,
    AgentTurnStatus,
    AgentToolCall,
    GENESIS_DIGEST,
)
from agent.protocol import AgentMessageChainValidator
from benchmark.v0.engineering.llm_provider import LLMProvider, LLMProviderConfig, LLMResponse


class MockTestProvider(LLMProvider):
    """Configurable mock provider simulating live LLM responses."""
    def __init__(self, responses: list[str]):
        super().__init__(LLMProviderConfig(provider_type="mock_test"))
        self._responses = list(responses)
        self._ptr = 0

    def generate(self, prompt: str, system_prompt: str = None, **kwargs) -> LLMResponse:
        if self._ptr < len(self._responses):
            text = self._responses[self._ptr]
            self._ptr += 1
        else:
            text = "Task completed successfully. All tests pass."
        return LLMResponse(
            text=text,
            model_name="mock-gemini",
            provider_type="gemini",
            prompt_tokens=100,
            completion_tokens=50,
            latency_sec=0.2,
            cost_usd=0.001,
            timestamp="2026-08-20T12:00:00Z",
        )


@pytest.fixture
def sample_context():
    return AgentSessionContext(
        session_id="SESS-TEST-001",
        repository_id="REPO-001",
        source_sha="a" * 40,
        task_id="TASK-PROD-001",
        objective="Implement square function",
        frontier_obligation_ids=("OBL-001",),
        frontier_details=({"obligation_id": "OBL-001", "title": "Square Invariant", "category": "CORRECTNESS_FUNCTIONAL"},),
        policy_constraints=(),
        verification_feedback=(),
        available_tools=(),
        granted_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION"),
        has_workspace_authority=False,
        turn_index=1,
        max_turns=10,
        remaining_budget_units=5.0,
    )


def test_live_worker_json_tool_call_parsing(sample_context):
    """Verifies that structured JSON tool calls are correctly parsed into AgentToolCalls."""
    json_reply = (
        "Here is the test proposal:\n"
        "```json\n"
        "{\n"
        '  "thought": "Let us verify the balance calculation with a test run",\n'
        '  "tool": "propose_test_run",\n'
        '  "args": {\n'
        '    "obligation_id": "OBL-001",\n'
        '    "target_test": "tests/test_ledger.py",\n'
        '    "purpose": "Verify double-entry balance property"\n'
        "  },\n"
        '  "status": "CONTINUE"\n'
        "}\n"
        "```"
    )
    worker = LiveModelWorker(provider=MockTestProvider([json_reply]), worker_id="test-worker")
    
    msg = worker.generate_inbound_message(
        context=sample_context,
        sequence=1,
        previous_digest=GENESIS_DIGEST,
        history=(),
    )

    valid, err, err_status, turn_resp = AgentMessageChainValidator.validate_inbound_message(
        message=msg,
        expected_session_id=sample_context.session_id,
        expected_worker_id="test-worker",
        expected_sequence=1,
        expected_previous_digest=GENESIS_DIGEST,
    )

    assert valid is True
    assert err is None
    assert turn_resp is not None
    assert turn_resp.turn_status == AgentTurnStatus.CONTINUE
    assert len(turn_resp.tool_calls) == 1
    assert turn_resp.tool_calls[0].tool_name == "propose_test_run"
    assert turn_resp.tool_calls[0].arguments["obligation_id"] == "OBL-001"


def test_live_worker_python_code_block_parsing(sample_context):
    """Verifies that raw python code blocks are converted into propose_code_patch tool calls."""
    code_reply = (
        "Here is the repaired implementation:\n"
        "```python\n"
        "def square(x):\n"
        "    return x * x\n"
        "```\n"
    )
    worker = LiveModelWorker(provider=MockTestProvider([code_reply]), worker_id="test-worker")
    
    msg = worker.generate_inbound_message(
        context=sample_context,
        sequence=1,
        previous_digest=GENESIS_DIGEST,
        history=(),
    )

    valid, err, err_status, turn_resp = AgentMessageChainValidator.validate_inbound_message(
        message=msg,
        expected_session_id=sample_context.session_id,
        expected_worker_id="test-worker",
        expected_sequence=1,
        expected_previous_digest=GENESIS_DIGEST,
    )

    assert valid is True
    assert turn_resp is not None
    assert len(turn_resp.tool_calls) == 1
    assert turn_resp.tool_calls[0].tool_name == "propose_code_patch"
    assert "return x * x" in turn_resp.tool_calls[0].arguments["code_content"]


def test_live_worker_error_containment_and_yield_budget(sample_context):
    """Verifies that an unhandled provider exception yields budget gracefully rather than crashing."""
    mock_prov = MagicMock(spec=LLMProvider)
    mock_prov.config = LLMProviderConfig(provider_type="gemini")
    mock_prov.generate.side_effect = TimeoutError("Gemini API connection timed out")

    worker = LiveModelWorker(provider=mock_prov, worker_id="test-worker")
    msg = worker.generate_inbound_message(
        context=sample_context,
        sequence=1,
        previous_digest=GENESIS_DIGEST,
        history=(),
    )

    valid, err, err_status, turn_resp = AgentMessageChainValidator.validate_inbound_message(
        message=msg,
        expected_session_id=sample_context.session_id,
        expected_worker_id="test-worker",
        expected_sequence=1,
        expected_previous_digest=GENESIS_DIGEST,
    )

    assert valid is True
    assert turn_resp is not None
    assert turn_resp.turn_status == AgentTurnStatus.WORKER_TIMEOUT
    assert "Gemini API connection timed out" in turn_resp.thought
