"""
S-Class V13: Model Context Protocol (MCP) Multi-IDE Registration Module
(mcp_installer.py)

Generates and updates per-IDE MCP configuration files so that S-Class MCP servers
(`mcp_server.py` and `codebase_kg_server.py`) are natively recognized as plugins:
- Cursor: .cursor/mcp.json
- Antigravity / Gemini: .agents/mcp.json and .gemini/mcp_config.json (or ~/.gemini/config/mcp_config.json)
- Claude Code: .claude/mcp.json
- OpenAI Codex CLI: .codex/mcp.json
"""

from __future__ import annotations
import os
import sys
import json
from typing import Dict, Any, List, Optional


def install_mcp_configs(workspace_dir: str, detected_platforms: Optional[List[str]] = None) -> Dict[str, str]:
    """
    Generates or updates per-IDE MCP registration files for the target workspace.
    Returns a dict mapping platform/IDE name to the generated configuration path.
    """
    workspace_dir = os.path.abspath(workspace_dir)
    results: Dict[str, str] = {}

    # Target executable path: prefer workspace mcp_server.py, fallback to module entry
    mcp_script_path = os.path.join(workspace_dir, "mcp_server.py")
    if not os.path.exists(mcp_script_path):
        # Point to the installed S-Class plugin distribution if available
        sclass_plugin_dir = os.path.dirname(os.path.abspath(__file__))
        cand = os.path.join(sclass_plugin_dir, "mcp_server.py")
        if os.path.exists(cand):
            mcp_script_path = cand

    norm_mcp_script = mcp_script_path.replace("\\", "/")

    # Standard python interpreter
    python_cmd = sys.executable or "python"

    targets = [p.lower() for p in (detected_platforms or ["cursor", "antigravity", "gemini", "claude_code", "codex"])]

    # 1. Cursor: .cursor/mcp.json
    if any(p in targets for p in ("cursor", "all")):
        cursor_dir = os.path.join(workspace_dir, ".cursor")
        os.makedirs(cursor_dir, exist_ok=True)
        cursor_mcp_file = os.path.join(cursor_dir, "mcp.json")
        cfg = _read_json_safe(cursor_mcp_file)
        servers = cfg.setdefault("mcpServers", {})
        servers["sclass"] = {
            "command": python_cmd,
            "args": [norm_mcp_script],
            "env": {"SCLASS_WORKSPACE": workspace_dir}
        }
        with open(cursor_mcp_file, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        results["cursor"] = cursor_mcp_file

    # 2. Antigravity / Gemini: .agents/mcp.json and .gemini/mcp_config.json
    if any(p in targets for p in ("antigravity", "gemini", "all")):
        agents_dir = os.path.join(workspace_dir, ".agents")
        os.makedirs(agents_dir, exist_ok=True)
        agents_mcp_file = os.path.join(agents_dir, "mcp.json")
        cfg = _read_json_safe(agents_mcp_file)
        servers = cfg.setdefault("mcpServers", {})
        servers["sclass"] = {
            "command": python_cmd,
            "args": [norm_mcp_script],
            "env": {"SCLASS_WORKSPACE": workspace_dir}
        }
        with open(agents_mcp_file, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        results["antigravity"] = agents_mcp_file

        # Also support .gemini/mcp_config.json if .gemini directory exists
        gemini_dir = os.path.join(workspace_dir, ".gemini")
        if os.path.exists(gemini_dir):
            gemini_mcp_file = os.path.join(gemini_dir, "mcp_config.json")
            gcfg = _read_json_safe(gemini_mcp_file)
            gservers = gcfg.setdefault("mcpServers", {})
            gservers["sclass"] = {
                "command": python_cmd,
                "args": [norm_mcp_script],
                "env": {"SCLASS_WORKSPACE": workspace_dir}
            }
            with open(gemini_mcp_file, "w", encoding="utf-8") as f:
                json.dump(gcfg, f, indent=2)
            results["gemini"] = gemini_mcp_file

    # 3. Claude Code: .claude/mcp.json
    if any(p in targets for p in ("claude_code", "claude", "all")):
        claude_dir = os.path.join(workspace_dir, ".claude")
        os.makedirs(claude_dir, exist_ok=True)
        claude_mcp_file = os.path.join(claude_dir, "mcp.json")
        cfg = _read_json_safe(claude_mcp_file)
        servers = cfg.setdefault("mcpServers", {})
        servers["sclass"] = {
            "command": python_cmd,
            "args": [norm_mcp_script],
            "env": {"SCLASS_WORKSPACE": workspace_dir}
        }
        with open(claude_mcp_file, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        results["claude_code"] = claude_mcp_file

    # 4. OpenAI Codex CLI: .codex/mcp.json
    if any(p in targets for p in ("codex", "codex_cli", "all")):
        codex_dir = os.path.join(workspace_dir, ".codex")
        os.makedirs(codex_dir, exist_ok=True)
        codex_mcp_file = os.path.join(codex_dir, "mcp.json")
        cfg = _read_json_safe(codex_mcp_file)
        servers = cfg.setdefault("mcpServers", {})
        servers["sclass"] = {
            "command": python_cmd,
            "args": [norm_mcp_script],
            "env": {"SCLASS_WORKSPACE": workspace_dir}
        }
        with open(codex_mcp_file, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        results["codex"] = codex_mcp_file

    return results


def _read_json_safe(filepath: str) -> Dict[str, Any]:
    """Reads existing JSON configuration or returns empty dictionary."""
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}
