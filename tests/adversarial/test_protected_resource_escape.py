"""
Adversarial Test: Attacks I & J - Protected Resource Escape Defense.
Proves that attempts to target or modify .sclass/trust, .sclass/evidence, or .sclass/state
via Python code, shell commands, or tool requests are denied.
"""

import pytest
from sclass.execution.modes import check_protected_resource_targeting
from sclass.control.authorization import authorize
from sclass.domain.action import ActionRequest
from sclass.observation.observer import observe_command
from sclass.core.errors import SecurityViolationError


def test_attack_i_modify_trust_through_python_denied():
    """
    Attack I:
    Agent attempts to write to .sclass/trust using python code payload:
    python -c "open('.sclass/trust/ledger/audit_ledger.jsonl', 'w').write('bad')"
    Result: Targeted protected resource detected and blocked.
    """
    cmd = "python -c \"open('.sclass/trust/ledger/audit_ledger.jsonl', 'w').write('bad')\""
    is_targeted, reason = check_protected_resource_targeting(cmd)
    assert is_targeted
    assert "protected S-Class resource" in reason


def test_attack_j_mcp_or_action_writing_protected_resource_denied(adv_workspace):
    """
    Attack J:
    An action attempts to write directly to .sclass/trust/audit_ledger.jsonl.
    Result: Authorization DENY.
    """
    req = ActionRequest(
        agent="claude",
        platform="acp",
        action="write_file",
        tool="file_writer",
        target=".sclass/trust/audit_ledger.jsonl",
        parameters={"content": "malicious ledger overwrite"},
        workspace=adv_workspace,
    )
    decision = authorize(req, workspace_dir=adv_workspace)
    assert decision.is_denied
    assert "protected under boundary" in decision.reason or "SCLASS_ONLY" in decision.reason
