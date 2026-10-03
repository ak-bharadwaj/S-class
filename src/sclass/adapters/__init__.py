"""S-Class IDE and Editor Hook Adapters.

Enables seamless integration with modern AI-native IDEs (VS Code, Cursor, Windsurf, Claude Code)
by configuring workspace hooks and settings to route agent proposals and mutations through
the S-Class Model Context Protocol (MCP) server and ExecutionGate.
"""

from sclass.adapters.claude_code import ClaudeCodeAdapter
from sclass.adapters.cursor import CursorAdapter
from sclass.adapters.vscode import VSCodeAdapter
from sclass.adapters.windsurf import WindsurfAdapter

__all__ = [
    "ClaudeCodeAdapter",
    "CursorAdapter",
    "VSCodeAdapter",
    "WindsurfAdapter",
]
