"""
S-Class V13: GitHub Copilot Hook Adapter (adapters/copilot.py)

Generates:
1. .github/hooks/sclass.json: Real executable preToolUse hook
2. .github/copilot-instructions.md: Advisory prompt context injection

Surface Scoping:
- Local Copilot CLI sessions execute .github/hooks/*.json immediately from workspace.
- Remote GitHub Copilot Cloud Agent requires committing .github/hooks/*.json to default branch.
"""

from __future__ import annotations
import os
import json
from typing import Dict, Any, Optional


class CopilotAdapter:
    """Installs and configures GitHub Copilot hooks and instructions."""

    def __init__(self, workspace_dir: Optional[str] = None):
        self.workspace_dir = os.path.abspath(workspace_dir or os.getcwd())
        self.github_dir = os.path.join(self.workspace_dir, ".github")
        self.hooks_dir = os.path.join(self.github_dir, "hooks")
        self.hooks_file = os.path.join(self.hooks_dir, "sclass.json")
        self.instructions_file = os.path.join(self.github_dir, "copilot-instructions.md")

    def install_hooks(self, runner_path: Optional[str] = None, strict: bool = False) -> str:
        """Writes .github/hooks/sclass.json executable hook configuration."""
        from adapters import resolve_runner_path
        os.makedirs(self.hooks_dir, exist_ok=True)
        r_path = resolve_runner_path(self.workspace_dir, runner_path)
        norm_runner = r_path.replace("\\", "/")

        cfg: Dict[str, Any] = {
            "version": 1,
            "hooks": {
                "preToolUse": [
                    {
                        "type": "command",
                        "matcher": "edit|create|apply_patch|write_to_file",
                        "bash": f'python "{norm_runner}" --platform copilot --event-type pre_tool_use',
                        "powershell": f'python "{norm_runner}" --platform copilot --event-type pre_tool_use',
                        "timeoutSec": 60,
                    }
                ],
                "sessionStart": [
                    {
                        "type": "command",
                        "bash": f'python "{norm_runner}" --platform copilot --event-type session_start',
                        "powershell": f'python "{norm_runner}" --platform copilot --event-type session_start',
                        "timeoutSec": 10,
                    }
                ],
            },
        }

        with open(self.hooks_file, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)

        return self.hooks_file

    def generate_instructions(self, project_context: str = "") -> str:
        """Writes .github/copilot-instructions.md advisory markdown."""
        os.makedirs(self.github_dir, exist_ok=True)
        content = f"""# S-Class Governance: GitHub Copilot Instructions

> [!IMPORTANT]
> This repository is governed by the S-Class authoritative execution microkernel.

## Architectural Governance
- Do not commit hardcoded secrets, API tokens, or private keys.
- Avoid insecure dynamic execution (`eval()`, `exec()`, `pickle.loads()`).
- All architectural decisions must satisfy evidence gates.

{project_context}
"""
        with open(self.instructions_file, "w", encoding="utf-8") as f:
            f.write(content)

        return self.instructions_file
