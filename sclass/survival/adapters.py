"""
S-Class Survival v0: Agent Platform Adapters (sclass/survival/adapters.py)

Implements Phase 11, 12:
Adapter Contract: Every adapter normalizes events into AuthorizationRequest,
emits platform-specific decisions, and declares AdapterCapabilities.

Integrations:
1. Claude Code (Reference implementation)
2. Cursor (Second implementation)
3. OpenAI Codex CLI
4. Google Antigravity
"""

from __future__ import annotations
from abc import ABC, abstractmethod
import json
from typing import Any, Dict, Optional

from sclass.survival.models import AuthorizationRequest, AuthorizationDecision, AdapterCapabilities


class AgentAdapter(ABC):
    """Abstract base contract for host AI coding agent platform adapters."""

    platform: str

    @abstractmethod
    def normalize_event(self, raw_event: Dict[str, Any], workspace_dir: str = "") -> AuthorizationRequest:
        """Translates platform-specific event payload into canonical AuthorizationRequest."""
        raise NotImplementedError

    @abstractmethod
    def emit_decision(self, decision: AuthorizationDecision) -> Any:
        """Formats canonical decision into platform-specific response payload / exit code."""
        raise NotImplementedError

    @abstractmethod
    def capabilities(self) -> AdapterCapabilities:
        """Declares host platform capabilities accurately. Never overstates enforcement."""
        raise NotImplementedError


class ClaudeCodeSurvivalAdapter(AgentAdapter):
    """Reference adapter for Claude Code CLI (.claude/settings.local.json)."""

    platform = "claude_code"

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            pre_action_enforcement=True,
            post_action_observation=True,
            approval=False,
            verification=True,
        )

    def normalize_event(self, raw_event: Dict[str, Any], workspace_dir: str = "") -> AuthorizationRequest:
        event_type = raw_event.get("event_type", "pre_tool_use")
        tool_name = raw_event.get("tool_name") or raw_event.get("tool")
        tool_input = raw_event.get("tool_input") or raw_event.get("tool_args") or {}
        file_path = raw_event.get("file_path") or tool_input.get("path") or tool_input.get("file_path")

        return AuthorizationRequest(
            agent="claude",
            platform=self.platform,
            action=event_type,
            tool=tool_name,
            target=file_path or tool_input.get("command"),
            parameters=tool_input if isinstance(tool_input, dict) else {},
            workspace=workspace_dir,
            task_id=raw_event.get("task_id"),
        )

    def emit_decision(self, decision: AuthorizationDecision) -> Dict[str, Any]:
        if decision.is_denied:
            return {
                "exit_code": 1,
                "stderr": f"[{decision.policy_id}] BLOCKED: {decision.reason}\nFix: {decision.remediation}\n",
                "stdout": "",
            }
        elif decision.is_warn:
            return {
                "exit_code": 0,
                "stderr": f"[{decision.policy_id}] WARNING: {decision.reason}\n",
                "stdout": json.dumps({"systemMessage": f"[{decision.policy_id}] {decision.reason}"}),
            }
        return {
            "exit_code": 0,
            "stderr": "",
            "stdout": "",
        }


class CursorSurvivalAdapter(AgentAdapter):
    """Second adapter for Cursor 1.7+ (.cursor/hooks.json)."""

    platform = "cursor"

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            pre_action_enforcement=True,
            post_action_observation=True,
            approval=True,
            verification=True,
        )

    def normalize_event(self, raw_event: Dict[str, Any], workspace_dir: str = "") -> AuthorizationRequest:
        event_type = raw_event.get("event_type", "preToolUse")
        file_path = raw_event.get("filePath") or raw_event.get("file_path") or raw_event.get("path")
        tool_name = raw_event.get("tool_name") or raw_event.get("tool")
        tool_input = raw_event.get("tool_input") or raw_event.get("tool_args") or raw_event

        return AuthorizationRequest(
            agent="cursor",
            platform=self.platform,
            action=event_type,
            tool=tool_name,
            target=file_path or tool_input.get("command"),
            parameters=tool_input if isinstance(tool_input, dict) else {},
            workspace=workspace_dir,
            task_id=raw_event.get("task_id"),
        )

    def emit_decision(self, decision: AuthorizationDecision) -> Dict[str, Any]:
        if decision.is_denied:
            payload = {
                "permission": "deny",
                "allowed": False,
                "userMessage": f"[{decision.policy_id}] Action blocked: {decision.reason}",
                "agentMessage": f"[{decision.policy_id}] S-Class denied action: {decision.reason}. Fix: {decision.remediation}",
            }
            return {"exit_code": 0, "stdout": json.dumps(payload), "stderr": ""}
        return {
            "exit_code": 0,
            "stdout": json.dumps({"permission": "allow", "allowed": True}),
            "stderr": "",
        }


class CodexSurvivalAdapter(AgentAdapter):
    """Adapter for OpenAI Codex CLI (.codex/hooks.json)."""

    platform = "codex"

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            pre_action_enforcement=True,
            post_action_observation=False,
            approval=True,
            verification=False,
        )

    def normalize_event(self, raw_event: Dict[str, Any], workspace_dir: str = "") -> AuthorizationRequest:
        event_type = raw_event.get("event_type", "pre_tool_use")
        return AuthorizationRequest(
            agent="codex",
            platform=self.platform,
            action=event_type,
            tool=raw_event.get("tool_name"),
            target=raw_event.get("file_path") or raw_event.get("command"),
            parameters=raw_event.get("tool_input", {}),
            workspace=workspace_dir,
        )

    def emit_decision(self, decision: AuthorizationDecision) -> Dict[str, Any]:
        if decision.is_denied:
            return {
                "exit_code": 1,
                "stderr": f"[{decision.policy_id}] BLOCKED: {decision.reason}\n",
                "stdout": "",
            }
        return {"exit_code": 0, "stderr": "", "stdout": ""}


class AntigravitySurvivalAdapter(AgentAdapter):
    """
    Adapter for Google Antigravity (.agents/hooks.json).
    Note: Antigravity native Gemini hooks support pre/post observation and verification.
    """

    platform = "antigravity"

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            pre_action_enforcement=False,       # Native dialect is primarily advisory / observational
            post_action_observation=True,
            approval=False,
            verification=True,
        )

    def normalize_event(self, raw_event: Dict[str, Any], workspace_dir: str = "") -> AuthorizationRequest:
        event_type = raw_event.get("event_type", "BeforeTool")
        return AuthorizationRequest(
            agent="antigravity",
            platform=self.platform,
            action=event_type,
            tool=raw_event.get("tool_name"),
            target=raw_event.get("file_path"),
            parameters=raw_event.get("tool_args", {}),
            workspace=workspace_dir,
        )

    def emit_decision(self, decision: AuthorizationDecision) -> Dict[str, Any]:
        if decision.is_denied:
            return {
                "exit_code": 1,
                "stderr": f"[{decision.policy_id}] BLOCKED: {decision.reason}\n",
                "stdout": "",
            }
        return {"exit_code": 0, "stderr": "", "stdout": ""}

