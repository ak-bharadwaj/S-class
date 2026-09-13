"""
S-Class Product: Compatibility Checker.
Evaluates platform compatibility and detected agent tooling.
"""

from __future__ import annotations
import shutil
import platform
from typing import Dict, Any


def check_compatibility(workspace_dir: str = ".") -> Dict[str, Any]:
    """Inspects OS capabilities and agent availability."""
    os_name = platform.system()
    supported_os = os_name in ("Windows", "Linux", "Darwin")

    agents = {
        "claude": shutil.which("claude") is not None,
        "codex": shutil.which("codex") is not None,
        "cursor": shutil.which("cursor") is not None,
        "opencode": shutil.which("opencode") is not None,
        "git": shutil.which("git") is not None,
        "pytest": shutil.which("pytest") is not None,
        "node": shutil.which("node") is not None,
        "cargo": shutil.which("cargo") is not None,
        "go": shutil.which("go") is not None,
    }

    return {
        "os": os_name,
        "os_supported": supported_os,
        "agents_detected": agents,
        "process_isolation": "native",
    }
