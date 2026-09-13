"""
Unit tests for S-Class V13 Cross-Platform Hook Core Engine (hook_core.py)
and Built-in Rules (hook_rules.py).
"""

import os
import json
import pytest
from hook_core import (
    HookCore,
    HookEvent,
    HookEventType,
    HookDecision,
    HookVerdict,
)
from hook_rules import (
    SecretScannerRule,
    DangerousCodeRule,
    PhaseIntegrityRule,
    ReleaseGovernanceRule,
    BlastRadiusRule,
    EvidenceIntegrityRule,
    get_default_rules,
)


@pytest.fixture
def temp_workspace(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    agents_dir = ws / ".agents"
    agents_dir.mkdir()
    return str(ws)


def test_secret_scanner_rule_blocks_hardcoded_key(temp_workspace):
    rule = SecretScannerRule()
    event = HookEvent(
        event_type=HookEventType.PRE_TOOL_USE,
        workspace_dir=temp_workspace,
        platform="claude_code",
        tool_name="Edit",
        tool_args={"content": "api_key = 'sk-1234567890abcdef1234567890abcdef'"},
    )
    verdict = rule.evaluate(event)
    assert verdict is not None
    assert verdict.decision == HookDecision.DENY
    assert "Hardcoded secret detected" in verdict.reason
    assert verdict.rule_id == "SCLASS-SEC-001"


def test_secret_scanner_abstains_on_clean_code(temp_workspace):
    rule = SecretScannerRule()
    event = HookEvent(
        event_type=HookEventType.PRE_TOOL_USE,
        workspace_dir=temp_workspace,
        platform="claude_code",
        tool_name="Edit",
        tool_args={"content": "def calculate_area(r): return 3.14159 * r * r"},
    )
    verdict = rule.evaluate(event)
    assert verdict is None


def test_dangerous_code_rule_warns_on_eval(temp_workspace):
    rule = DangerousCodeRule()
    event = HookEvent(
        event_type=HookEventType.PRE_TOOL_USE,
        workspace_dir=temp_workspace,
        platform="cursor",
        tool_name="edit_file",
        tool_args={"new_str": "result = eval(user_input)"},
    )
    verdict = rule.evaluate(event)
    assert verdict is not None
    assert verdict.decision == HookDecision.WARN
    assert verdict.rule_id == "SCLASS-SEC-002"


def test_phase_integrity_rule_warns_during_synthesis(temp_workspace):
    # Set FSM phase to SPECIFICATION_SYNTHESIS
    state_file = os.path.join(temp_workspace, ".agents", "orchestration_state.json")
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump({"currentPhase": "SPECIFICATION_SYNTHESIS"}, f)

    rule = PhaseIntegrityRule()
    event = HookEvent(
        event_type=HookEventType.PRE_FILE_EDIT,
        workspace_dir=temp_workspace,
        platform="claude_code",
        file_path="src/main.py",
    )
    verdict = rule.evaluate(event)
    assert verdict is not None
    assert verdict.decision == HookDecision.WARN
    assert verdict.rule_id == "SCLASS-FSM-001"


def test_release_governance_rule_denies_outside_release_phase(temp_workspace):
    state_file = os.path.join(temp_workspace, ".agents", "orchestration_state.json")
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump({"currentPhase": "CODING"}, f)

    rule = ReleaseGovernanceRule()
    event = HookEvent(
        event_type=HookEventType.PRE_FILE_EDIT,
        workspace_dir=temp_workspace,
        platform="codex",
        file_path="release_manifest.json",
    )
    verdict = rule.evaluate(event)
    assert verdict is not None
    assert verdict.decision == HookDecision.DENY
    assert verdict.rule_id == "SCLASS-FSM-002"


def test_evidence_integrity_rule_blocks_qa_report_deletion(temp_workspace):
    rule = EvidenceIntegrityRule()
    event = HookEvent(
        event_type=HookEventType.PRE_TOOL_USE,
        workspace_dir=temp_workspace,
        platform="windsurf",
        tool_name="rm",
        file_path=".agents/qa_report.json",
    )
    verdict = rule.evaluate(event)
    assert verdict is not None
    assert verdict.decision == HookDecision.DENY
    assert verdict.rule_id == "SCLASS-EVID-001"


def test_hook_core_demotes_deny_in_warn_mode(temp_workspace):
    core = HookCore(workspace_dir=temp_workspace, enforcement_mode="warn")
    core.register_rule(SecretScannerRule())

    event = HookEvent(
        event_type=HookEventType.PRE_TOOL_USE,
        workspace_dir=temp_workspace,
        platform="claude_code",
        tool_args={"content": "token = 'ghp_123456789012345678901234567890123456'"},
    )
    verdict = core.evaluate_event(event)
    assert verdict.decision == HookDecision.WARN
    assert "[WARN-MODE DEMOTION]" in verdict.reason


def test_hook_core_enforces_deny_in_block_mode(temp_workspace):
    core = HookCore(workspace_dir=temp_workspace, enforcement_mode="block")
    core.register_rule(SecretScannerRule())

    event = HookEvent(
        event_type=HookEventType.PRE_TOOL_USE,
        workspace_dir=temp_workspace,
        platform="claude_code",
        tool_args={"content": "token = 'ghp_123456789012345678901234567890123456'"},
    )
    verdict = core.evaluate_event(event)
    assert verdict.decision == HookDecision.DENY
    assert verdict.enforcement_level == "blocking"
