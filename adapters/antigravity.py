"""
S-Class: Google Antigravity / Gemini Hook Adapter (adapters/antigravity.py)

Generates .agents/hooks.json with true Antigravity schema:
- Top-level named hook "sclass-enforcement-guard"
- PreToolUse for interception
- Stop for completion gating
"""

from __future__ import annotations
import os
import json
from typing import Dict, Any, Optional


class AntigravityAdapter:
    """Installs and configures Google Antigravity hooks in native schema."""

    def __init__(self, workspace_dir: Optional[str] = None):
        self.workspace_dir = os.path.abspath(workspace_dir or os.getcwd())
        self.agents_dir = os.path.join(self.workspace_dir, ".agents")
        self.hooks_file = os.path.join(self.agents_dir, "hooks.json")

    def install_hooks(self, runner_path: Optional[str] = None, strict: bool = False) -> str:
        """Writes .agents/hooks.json using true Antigravity schema."""
        from adapters import resolve_runner_path
        os.makedirs(self.agents_dir, exist_ok=True)
        r_path = resolve_runner_path(self.workspace_dir, runner_path)
        norm_runner = r_path.replace("\\", "/")
        
        strict_flag = " --strict" if strict else ""

        cfg: Dict[str, Any] = {
            "sclass-enforcement-guard": {
                "PreToolUse": [
                    {
                        "matcher": "write_to_file|replace_file_content|run_command",
                        "hooks": [
                            f'python "{norm_runner}" --platform antigravity --event-type PreToolUse{strict_flag}'
                        ]
                    }
                ],
                "Stop": [
                    f'python "{norm_runner}" --platform antigravity --event-type Stop{strict_flag}'
                ]
            }
        }

        with open(self.hooks_file, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)

        return self.hooks_file
