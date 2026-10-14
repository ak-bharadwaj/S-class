from __future__ import annotations
import logging
logger = logging.getLogger("sclass.mcp_installer")
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
    Creates a backup copy <filepath>.bak before modifying (only if .bak does not already exist).
    Returns None if file exists and cannot be parsed, refusing to overwrite.
    """
    if not os.path.exists(filepath):
        return {}

    # Backup existing configuration file only when no .bak exists, preserving the pristine original
    bak_path = filepath + ".bak"
    if not os.path.exists(bak_path):
        try:
            shutil.copy2(filepath, bak_path)
        except Exception as e:
            logger.debug(f"[mcp_installer] Non-critical exception creating backup: {e}")

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            raw = f.read()
        cleaned = _strip_comments(raw).strip()
        if not cleaned:
            return {}
        return json.loads(cleaned)
    except Exception as e:
        # Refuse to overwrite unparseable configuration file and warn the user naming the file
        msg = f"WARNING: [mcp_installer] Failed to parse existing MCP configuration at '{filepath}': {e}. Skipping file to prevent corruption."
        logger.warning(msg)
        print(msg, file=sys.stderr)
        return None


def _read_json_safe(filepath: str) -> Dict[str, Any]:
    """Fallback reader maintaining backwards compatibility."""
    res = _read_and_backup_json(filepath)
    return res if res is not None else {}


def _register_mcp_server_in_file(
    filepath: str,
    platform_key: str,
    python_cmd: str,
    norm_mcp_script: str,
    workspace_dir: str,
    results: Dict[str, str],
) -> None:
    """Helper to safely read, backup, and register S-Class MCP server in a target config file."""
    cfg = _read_and_backup_json(filepath)
    if cfg is None:
        msg = f"WARNING: [mcp_installer] Skipped updating {platform_key} MCP config at '{filepath}' because the existing file contains invalid JSON."
        logger.warning(msg)
        print(msg, file=sys.stderr)
        return

    servers = cfg.setdefault("mcpServers", {})
    servers["sclass"] = {
        "command": python_cmd,
        "args": [norm_mcp_script],
        "env": {
            "SCLASS_WORKSPACE": workspace_dir,
            "SCLASS_MCP_ROLE": "agent"
        }
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    results[platform_key] = filepath


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
        _register_mcp_server_in_file(cursor_mcp_file, "cursor", python_cmd, norm_mcp_script, workspace_dir, results)

    # 2. Antigravity / Gemini: .agents/mcp.json and .gemini/mcp_config.json
    if any(p in targets for p in ("antigravity", "gemini", "all")):
        agents_dir = os.path.join(workspace_dir, ".agents")
        os.makedirs(agents_dir, exist_ok=True)
        agents_mcp_file = os.path.join(agents_dir, "mcp.json")
        _register_mcp_server_in_file(agents_mcp_file, "antigravity", python_cmd, norm_mcp_script, workspace_dir, results)

        # Also support .gemini/mcp_config.json if .gemini directory exists
        gemini_dir = os.path.join(workspace_dir, ".gemini")
        if os.path.exists(gemini_dir):
            gemini_mcp_file = os.path.join(gemini_dir, "mcp_config.json")
            _register_mcp_server_in_file(gemini_mcp_file, "gemini", python_cmd, norm_mcp_script, workspace_dir, results)

    # 3. Claude Code: .claude/mcp.json
    if any(p in targets for p in ("claude_code", "claude", "all")):
        claude_dir = os.path.join(workspace_dir, ".claude")
        os.makedirs(claude_dir, exist_ok=True)
        claude_mcp_file = os.path.join(claude_dir, "mcp.json")
        _register_mcp_server_in_file(claude_mcp_file, "claude_code", python_cmd, norm_mcp_script, workspace_dir, results)

    # 4. OpenAI Codex CLI: .codex/mcp.json
    if any(p in targets for p in ("codex", "codex_cli", "all")):
        codex_dir = os.path.join(workspace_dir, ".codex")
        os.makedirs(codex_dir, exist_ok=True)
        codex_mcp_file = os.path.join(codex_dir, "mcp.json")
        _register_mcp_server_in_file(codex_mcp_file, "codex", python_cmd, norm_mcp_script, workspace_dir, results)

    if results:
        logger.info(
            f"[mcp_installer] Configured {len(results)} IDE MCP endpoints. "
            "Note: Configurations embed absolute interpreter paths; re-run 'sclass install' if the repository or virtualenv is moved."
        )

    return results
