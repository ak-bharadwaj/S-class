"""
Adversarial Test: Shell Escape and Execution Mode Defense.
Proves that shell metacharacters in HOST_ARGV are rejected, and HOST_SHELL requires explicit gating.
"""

import pytest
from sclass.execution.modes import ExecutionMode, ExecutionPolicy
from sclass.core.errors import SecurityViolationError
from sclass.observation.observer import observe_command


def test_shell_chaining_in_host_argv_mode_rejected(adv_workspace):
    """Verifies that shell chaining operators are rejected in HOST_ARGV mode."""
    with pytest.raises(SecurityViolationError):
        observe_command(
            command="echo hello && echo evil",
            workspace_dir=adv_workspace,
            mode=ExecutionMode.HOST_ARGV,
        )


def test_host_shell_policy_evaluation():
    """Verifies that HOST_SHELL flags high risk and requires explicit approval."""
    eval_res = ExecutionPolicy.evaluate(
        mode=ExecutionMode.HOST_SHELL,
        command="ls -la",
        cwd=".",
    )
    assert eval_res.allowed
    assert eval_res.requires_approval
    assert eval_res.risk_level == "HIGH"
