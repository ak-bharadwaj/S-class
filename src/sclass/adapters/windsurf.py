"""S-Class Windsurf Adapter (adapters/windsurf.py).

Configures Windsurf / Cascade workspace rules (.windsurf/rules or .windsurfrules)
to enforce S-Class architectural governance, requirement obligations,
and mutation verification through the S-Class MCP server.
"""

from __future__ import annotations

from pathlib import Path


class WindsurfAdapter:
    """Configures Windsurf / Cascade workspace rules for S-Class governance."""

    def __init__(self, workspace_root: Path | str = "."):
        self.workspace_root = Path(workspace_root).resolve()
        self.rules_file = self.workspace_root / ".windsurfrules"

    def install_rules(self) -> Path:
        """Writes .windsurfrules instructing Cascade to delegate to S-Class."""
        rules_content = """# S-Class v6.0.1 Windsurf Architectural Rules

1. Authority Invariant:
   - All proposed code changes must be validated against S-Class obligations.
   - Use the `sclass_guide_task` MCP tool before starting any implementation task.
   - Use the `sclass_validate_patch` MCP tool to verify diffs against the 14-step ExecutionGate.

2. Zero Bypass:
   - Direct file edits outside S-Class boundary governance are non-authoritative.
   - Ensure all verification suites pass before marking tasks as complete.

3. S-Class Version: 6.0.1 (Frozen Canonical Architecture)
"""
        self.rules_file.write_text(rules_content, encoding="utf-8")
        return self.rules_file
