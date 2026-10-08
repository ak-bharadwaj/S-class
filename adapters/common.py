"""
S-Class: Shared Utilities for IDE Hook Adapters (adapters/common.py)

Provides non-destructive configuration parsing, comment stripping, automated backups,
and cross-platform path resolution for all platform adapters.
"""

from __future__ import annotations
import os
import re
import sys
import json
import shutil
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger("sclass_adapter_common")

# Pre-compiled module-level regex for JSONC comment stripping (PERF-03)
JSONC_COMMENT_PATTERN = re.compile(
    r'("(?:\\.|[^"\\])*")|//.*?$|/\*.*?\*/',
    re.MULTILINE | re.DOTALL,
)


def strip_comments(text: str) -> str:
    """Strips single-line (//) and multi-line (/* */) comments from JSONC configuration text."""
    def replacer(match):
        if match.group(1):
            return match.group(1)
        return ""
    cleaned = JSONC_COMMENT_PATTERN.sub(replacer, text)
    cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned)
    return cleaned


def backup_config_file(filepath: str) -> bool:
    """
    Creates a .bak copy of filepath before modification if filepath exists.
    Returns True if backup was created or already exists.
    """
    if not os.path.exists(filepath):
        return False
    bak_path = filepath + ".bak"
    try:
        if not os.path.exists(bak_path):
            shutil.copy2(filepath, bak_path)
            return True
    except Exception as e:
        logger.debug(f"[AdapterCommon] Failed creating backup for '{filepath}': {e}")
    return False


def safe_read_json_config(filepath: str) -> Optional[Dict[str, Any]]:
    """
    Safely reads JSON or JSONC file.
    Returns parsed dictionary if successful, or None if the file cannot be parsed.
    """
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            raw = f.read()
        cleaned = strip_comments(raw).strip()
        if not cleaned:
            return {}
        data = json.loads(cleaned)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning(f"[AdapterCommon] Failed parsing config '{filepath}': {e}")
        return None


def get_python_executable() -> str:
    """Returns normalized Python executable path using forward slashes for cross-platform compatibility."""
    py_path = sys.executable or "python"
    return py_path.replace("\\", "/")


def merge_hook_list(existing_list: list, new_entry: dict, identity_marker: str) -> list:
    """
    Merges new_entry into existing_list idempotently.
    If an existing entry contains identity_marker in its command, updates it in place.
    Otherwise, prepends new_entry, ensuring user's own hooks are preserved.
    """
    result = list(existing_list)
    for idx, item in enumerate(result):
        if isinstance(item, dict):
            # Check direct command field
            cmd = str(item.get("command", ""))
            if identity_marker in cmd:
                result[idx] = new_entry
                return result
            # Check nested hooks array
            sub_hooks = item.get("hooks", [])
            if any(identity_marker in str(h.get("command", "")) for h in sub_hooks):
                result[idx] = new_entry
                return result
            # Check bash / powershell fields
            if identity_marker in str(item.get("bash", "")) or identity_marker in str(item.get("powershell", "")):
                result[idx] = new_entry
                return result
    result.insert(0, new_entry)
    return result
