"""
S-Class V13: IDE Hook Adapters Package (adapters/__init__.py)

Exposes platform adapters and the unified PlatformInfo detection engine.
Detects:
- Claude Code (.claude/)
- Cursor (.cursor/)
- OpenAI Codex CLI (.codex/)
- Google Antigravity (.agents/ or .gemini/)
- GitHub Copilot (.github/)
- Windsurf / Cascade (.windsurf/)

Strictly decouples static platform capability (blocking_hooks_supported: bool)
from dynamic local runtime verification state (verified: bool | None, verification_status: str).
"""

from __future__ import annotations
import os
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional, Any, List

PLATFORM_CONFIDENCE = {
    "claude_code": "High",
    "codex": "High",
    "cursor": "Medium-high",
    "antigravity": "Medium",
    "copilot": "High",
    "windsurf": "Medium-high",
}


def resolve_runner_path(workspace_dir: str, runner_path: Optional[str] = None) -> str:
    """
    Resolves the authoritative path to hook_runner.py.
    Prefers explicit runner_path, then workspace-local hook_runner.py,
    falling back to the installed S-Class package's hook_runner.py.
    """
    if runner_path and os.path.exists(runner_path):
        return runner_path

    ws_runner = os.path.join(workspace_dir, "hook_runner.py")
    if os.path.exists(ws_runner):
        return ws_runner

    pkg_runner = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hook_runner.py")
    if os.path.exists(pkg_runner):
        return os.path.abspath(pkg_runner)

    return ws_runner



@dataclass
class PlatformInfo:
    name: str
    config_dir: str
    blocking_hooks_supported: bool = True  # Static capability: all 6 platforms support blocking hooks
    confidence: str = "Medium"            # Static landscape confidence
    verified: bool = False                # True iff authentic tool execution has landed in last_verified
    verification_status: str = "UNVERIFIED"  # "PASS" | "UNVERIFIED" | "WARN"
    last_verified_at: Optional[str] = None
    installed_at: Optional[str] = None
    enforcement_mode: str = "warn"        # "warn" | "block" | "off"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "config_dir": self.config_dir,
            "blocking_hooks_supported": self.blocking_hooks_supported,
            "confidence": self.confidence,
            "verified": self.verified,
            "verification_status": self.verification_status,
            "last_verified_at": self.last_verified_at,
            "installed_at": self.installed_at,
            "enforcement_mode": self.enforcement_mode,
        }


def detect_platforms(workspace_dir: Optional[str] = None) -> Dict[str, PlatformInfo]:
    """
    Detects which AI coding agent platforms are present in workspace.
    Enriches with authoritative telemetry from .agents/sclass_hooks.json.
    """
    target = os.path.abspath(workspace_dir or os.getcwd())
    detections: Dict[str, PlatformInfo] = {}

    checks = {
        "claude_code": (".claude",),
        "cursor": (".cursor",),
        "codex": (".codex",),
        "antigravity": (".agents", ".gemini"),
        "copilot": (".github",),
        "windsurf": (".windsurf",),
    }

    for platform, markers in checks.items():
        for marker in markers:
            if os.path.isdir(os.path.join(target, marker)):
                detections[platform] = PlatformInfo(
                    name=platform,
                    config_dir=marker,
                    blocking_hooks_supported=True,
                    confidence=PLATFORM_CONFIDENCE.get(platform, "Medium"),
                )
                break

    _enrich_with_verification_state(target, detections)
    return detections


def _enrich_with_verification_state(workspace_dir: str, detections: Dict[str, PlatformInfo]) -> None:
    """Computes deterministic verification status from sclass_hooks.json."""
    hooks_cfg_path = os.path.join(workspace_dir, ".agents", "sclass_hooks.json")
    if not os.path.exists(hooks_cfg_path):
        return

    try:
        with open(hooks_cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        installed_at_str = cfg.get("installed_at")
        installed_at = datetime.fromisoformat(installed_at_str) if installed_at_str else datetime.now(timezone.utc)
        last_verified_map = cfg.get("last_verified", {})
        enforcement_map = cfg.get("enforcement_mode", {})
        now = datetime.now(timezone.utc)
        elapsed_hours = (now - installed_at).total_seconds() / 3600.0

        for platform, info in detections.items():
            info.installed_at = installed_at_str
            info.enforcement_mode = enforcement_map.get(platform, "warn")
            receipt_ts = last_verified_map.get(platform)

            if receipt_ts:
                info.verified = True
                info.verification_status = "PASS"
                info.last_verified_at = receipt_ts
            elif elapsed_hours < 48.0:
                info.verified = False
                info.verification_status = "UNVERIFIED"
            else:
                info.verified = False
                info.verification_status = "WARN"
    except Exception:
        pass
