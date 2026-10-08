"""
S-Class v6: Model Context Protocol (MCP) Multi-IDE Registration Module
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
import shutil
import re
from typing import Dict, Any, List, Optional


from adapters.common import strip_comments as _strip_comments


def _read_and_backup_json(filepath: str) -> Optional[Dict[str, Any]]:
    """
    Safely reads JSON (handling // and /* */ comments).
    Creates a backup copy <filepath>.bak before modifying.
    Returns None if file exists and cannot be parsed, refusing to overwrite.
    """
    if not os.path.exists(filepath):
        return {}

    # Backup existing configuration file first (Item 36)
    try:
        shutil.copy2(filepath, filepath + ".bak")
    except Exception:
        pass

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            raw = f.read()
        cleaned = _strip_comments(raw).strip()
        if not cleaned:
            return {}
        return json.loads(cleaned)
    except Exception:
        # Refuse to overwrite unparseable configuration file (Item 36)
        return None


def _read_json_safe(filepath: str) -> Dict[str, Any]:
    """Fallback reader maintaining backwards compatibility."""
    res = _read_and_backup_json(filepath)
    return res if res is not None else {}


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
        cfg = _read_and_backup_json(cursor_mcp_file)
        if cfg is not None:
            servers = cfg.setdefault("mcpServers", {})
            servers["sclass"] = {
                "command": python_cmd,
                "args": [norm_mcp_script],
                "env": {
                    "SCLASS_WORKSPACE": workspace_dir,
                    "SCLASS_MCP_ROLE": "agent"
                }
            }
            with open(cursor_mcp_file, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            results["cursor"] = cursor_mcp_file

    # 2. Antigravity / Gemini: .agents/mcp.json and .gemini/mcp_config.json
    if any(p in targets for p in ("antigravity", "gemini", "all")):
        agents_dir = os.path.join(workspace_dir, ".agents")
        os.makedirs(agents_dir, exist_ok=True)
        agents_mcp_file = os.path.join(agents_dir, "mcp.json")
        cfg = _read_and_backup_json(agents_mcp_file)
        if cfg is not None:
            servers = cfg.setdefault("mcpServers", {})
            servers["sclass"] = {
                "command": python_cmd,
                "args": [norm_mcp_script],
                "env": {
                    "SCLASS_WORKSPACE": workspace_dir,
                    "SCLASS_MCP_ROLE": "agent"
                }
            }
            with open(agents_mcp_file, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            results["antigravity"] = agents_mcp_file

        # Also support .gemini/mcp_config.json if .gemini directory exists
        gemini_dir = os.path.join(workspace_dir, ".gemini")
        if os.path.exists(gemini_dir):
            gemini_mcp_file = os.path.join(gemini_dir, "mcp_config.json")
            gcfg = _read_and_backup_json(gemini_mcp_file)
            if gcfg is not None:
                gservers = gcfg.setdefault("mcpServers", {})
                gservers["sclass"] = {
                    "command": python_cmd,
                    "args": [norm_mcp_script],
                    "env": {
                    "SCLASS_WORKSPACE": workspace_dir,
                    "SCLASS_MCP_ROLE": "agent"
                }
                }
                with open(gemini_mcp_file, "w", encoding="utf-8") as f:
                    json.dump(gcfg, f, indent=2)
                results["gemini"] = gemini_mcp_file

    # 3. Claude Code: .claude/mcp.json
    if any(p in targets for p in ("claude_code", "claude", "all")):
        claude_dir = os.path.join(workspace_dir, ".claude")
        os.makedirs(claude_dir, exist_ok=True)
        claude_mcp_file = os.path.join(claude_dir, "mcp.json")
        cfg = _read_and_backup_json(claude_mcp_file)
        if cfg is not None:
            servers = cfg.setdefault("mcpServers", {})
            servers["sclass"] = {
                "command": python_cmd,
                "args": [norm_mcp_script],
                "env": {
                    "SCLASS_WORKSPACE": workspace_dir,
                    "SCLASS_MCP_ROLE": "agent"
                }
            }
            with open(claude_mcp_file, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            results["claude_code"] = claude_mcp_file

    # 4. OpenAI Codex CLI: .codex/mcp.json
    if any(p in targets for p in ("codex", "codex_cli", "all")):
        codex_dir = os.path.join(workspace_dir, ".codex")
        os.makedirs(codex_dir, exist_ok=True)
        codex_mcp_file = os.path.join(codex_dir, "mcp.json")
        cfg = _read_and_backup_json(codex_mcp_file)
        if cfg is not None:
            servers = cfg.setdefault("mcpServers", {})
            servers["sclass"] = {
                "command": python_cmd,
                "args": [norm_mcp_script],
                "env": {
                    "SCLASS_WORKSPACE": workspace_dir,
                    "SCLASS_MCP_ROLE": "agent"
                }
            }
            with open(codex_mcp_file, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            results["codex"] = codex_mcp_file

    return results
