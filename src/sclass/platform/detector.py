"""
S-Class Platform Optimization: Dynamic Platform Detector (B.4).

Detects the active AI coding agent/platform runtime (OpenAI Codex, Anthropic Claude Code,
Google Antigravity, Cursor, or Generic) by inspecting:
1. Client metadata (MCP/ACP clientInfo: name, version)
2. Explicit caller identity/actor token
3. Environment variables (CODEX_SESSION, CLAUDE_PROJECT_DIR, ANTIGRAVITY_WORKSPACE, etc.)
4. Workspace root markers (.codex, .claude, .agents/skills, .cursor, AGENTS.md, CLAUDE.md)

Binds the detected runtime to an authoritative PlatformProfile and CompensationPolicy
without permanent superiority assumptions.
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple

from sclass.platform.profile import PlatformProfile
from sclass.platform.policy import CompensationPolicy
from sclass.platform.archetypes import get_archetype, list_archetypes


@dataclass(frozen=True)
class DetectedPlatform:
    """Authoritative detection outcome with evidence trail and assigned profile/policy."""
    platform_id: str
    confidence: float
    version: str
    evidence: List[str]
    profile: PlatformProfile
    policy: CompensationPolicy

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform_id": self.platform_id,
            "confidence": round(self.confidence, 2),
            "version": self.version,
            "evidence": list(self.evidence),
            "profile": self.profile.to_dict(),
            "policy": self.policy.to_dict(),
        }


class PlatformDetector:
    """Detects active agent platforms from multi-modal environmental signals."""

    @classmethod
    def detect(
        cls,
        workspace_dir: str = "",
        env: Optional[Dict[str, str]] = None,
        client_info: Optional[Dict[str, Any]] = None,
        requested_actor: Optional[str] = None,
    ) -> DetectedPlatform:
        """
        Detects platform identity and returns DetectedPlatform.
        Evaluates signals in priority order:
        1. Explicit MCP/ACP clientInfo
        2. Explicit actor/agent token
        3. Environment variables
        4. Workspace structural markers
        5. Generic baseline fallback
        """
        environ = env if env is not None else os.environ
        ws = os.path.abspath(workspace_dir) if workspace_dir else os.getcwd()

        evidence: List[str] = []
        scores: Dict[str, float] = {
            "codex": 0.0,
            "claude_code": 0.0,
            "antigravity": 0.0,
            "cursor": 0.0,
        }
        detected_versions: Dict[str, str] = {}

        # 1. Inspect Client Info (Highest fidelity)
        if client_info and isinstance(client_info, dict):
            c_name = str(client_info.get("name", "")).strip().lower()
            c_ver = str(client_info.get("version", "1.0.0")).strip()

            if "codex" in c_name:
                scores["codex"] += 0.9
                detected_versions["codex"] = c_ver
                evidence.append(f"client_info.name:{c_name} (version={c_ver})")
            elif "claude" in c_name:
                scores["claude_code"] += 0.9
                detected_versions["claude_code"] = c_ver
                evidence.append(f"client_info.name:{c_name} (version={c_ver})")
            elif "antigravity" in c_name or "gemini" in c_name:
                scores["antigravity"] += 0.9
                detected_versions["antigravity"] = c_ver
                evidence.append(f"client_info.name:{c_name} (version={c_ver})")
            elif "cursor" in c_name:
                scores["cursor"] += 0.9
                detected_versions["cursor"] = c_ver
                evidence.append(f"client_info.name:{c_name} (version={c_ver})")

        # 2. Inspect Actor/Agent Token
        if requested_actor:
            a_norm = requested_actor.strip().lower()
            if "codex" in a_norm:
                scores["codex"] += 0.8
                evidence.append(f"actor:{requested_actor}")
            elif "claude" in a_norm:
                scores["claude_code"] += 0.8
                evidence.append(f"actor:{requested_actor}")
            elif "antigravity" in a_norm or "gemini" in a_norm:
                scores["antigravity"] += 0.8
                evidence.append(f"actor:{requested_actor}")
            elif "cursor" in a_norm:
                scores["cursor"] += 0.8
                evidence.append(f"actor:{requested_actor}")

        # 3. Inspect Environment Variables
        if environ.get("CODEX_SESSION") or environ.get("OPENAI_AGENTS_API") or environ.get("CODEX_CLI"):
            scores["codex"] += 0.75
            evidence.append("env:CODEX_SESSION_OR_API")
        if environ.get("CLAUDE_PROJECT_DIR") or environ.get("CLAUDE_CODE_ENTRYPOINT") or environ.get("ANTHROPIC_AGENT_SDK"):
            scores["claude_code"] += 0.75
            evidence.append("env:CLAUDE_CODE_ENV")
        if environ.get("ANTIGRAVITY_WORKSPACE") or environ.get("GEMINI_WORKSPACE") or environ.get("ANTIGRAVITY_SUBAGENT_ID"):
            scores["antigravity"] += 0.75
            evidence.append("env:ANTIGRAVITY_WORKSPACE_OR_SUBAGENT")
        if environ.get("CURSOR_AGENT") or environ.get("CURSOR_SESSION"):
            scores["cursor"] += 0.75
            evidence.append("env:CURSOR_AGENT_ENV")

        # 4. Inspect Workspace Structural Markers
        if os.path.exists(os.path.join(ws, ".codex")) or os.path.exists(os.path.join(ws, "AGENTS.md")):
            scores["codex"] += 0.4
            evidence.append("workspace_marker:.codex_or_AGENTS.md")
        if os.path.exists(os.path.join(ws, ".claude")) or os.path.exists(os.path.join(ws, "CLAUDE.md")):
            scores["claude_code"] += 0.4
            evidence.append("workspace_marker:.claude_or_CLAUDE.md")
        if (
            os.path.exists(os.path.join(ws, ".agents", "skills"))
            or os.path.exists(os.path.join(ws, ".gemini"))
            or os.path.exists(os.path.join(ws, "GEMINI.md"))
        ):
            scores["antigravity"] += 0.4
            evidence.append("workspace_marker:.agents_or_gemini")
        if os.path.exists(os.path.join(ws, ".cursor")) or os.path.exists(os.path.join(ws, ".cursorrules")):
            scores["cursor"] += 0.4
            evidence.append("workspace_marker:.cursor_rules")

        # Select highest scoring platform
        best_platform = max(scores, key=lambda k: scores[k])
        best_score = scores[best_platform]

        if best_score >= 0.3:
            matched_id = best_platform
            confidence = min(1.0, best_score)
            version = detected_versions.get(matched_id, "latest")
            profile, policy = get_archetype(matched_id)
        else:
            matched_id = "generic"
            confidence = 0.1
            version = "1.0.0"
            evidence.append("fallback:generic_baseline")
            profile, policy = get_archetype("generic")

        return DetectedPlatform(
            platform_id=matched_id,
            confidence=confidence,
            version=version,
            evidence=evidence,
            profile=profile,
            policy=policy,
        )


def detect_platform(
    workspace_dir: str = "",
    env: Optional[Dict[str, str]] = None,
    client_info: Optional[Dict[str, Any]] = None,
    requested_actor: Optional[str] = None,
) -> DetectedPlatform:
    """Functional convenience entrypoint for platform detection."""
    return PlatformDetector.detect(
        workspace_dir=workspace_dir,
        env=env,
        client_info=client_info,
        requested_actor=requested_actor,
    )
