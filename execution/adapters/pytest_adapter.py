"""
S-Class EOS V11.2 - D6 Pytest Execution Provider Adapter.
Executes pytest test runs inside isolated workspaces with strict workspace containment.
"""

from __future__ import annotations
import sys
from typing import Sequence
from controller.token import ActionBinding, ExecutionContext
from execution.workspace import IsolatedWorkspace
from execution.provider import D6ExecutionProvider


class PytestExecutionProvider(D6ExecutionProvider):
    """Concrete D6 Provider executing pytest against target tests."""

    @property
    def provider_id(self) -> str:
        return "pytest_runner_engine"

    @property
    def supported_action_types(self) -> Sequence[str]:
        return ("EXECUTE_TEST", "RUN_TEST", "PYTEST_VERIFY")

    @property
    def required_capabilities(self) -> Sequence[str]:
        return ("CAP_EXEC_TEST",)

    def build_command(
        self,
        action_binding: ActionBinding,
        workspace: IsolatedWorkspace,
        context: ExecutionContext,
    ) -> Sequence[str]:
        target = action_binding.target
        # Enforce workspace containment at provider boundary
        safe_target = workspace.resolve_safe_path(target)
        params = action_binding.parameters or {}

        # Construct argv array: [sys.executable, "-m", "pytest", "-o", "addopts=", "-p", "no:cov", ...]
        cmd = [sys.executable, "-m", "pytest", "-o", "addopts=", "-p", "no:cov", "-v"]

        # Add optional pytest parameters safely as argv elements
        if "maxfail" in params:
            cmd.extend(["--maxfail", str(int(params["maxfail"]))])
        if "quiet" in params and params["quiet"]:
            cmd.append("-q")

        cmd.append(safe_target)
        return cmd
