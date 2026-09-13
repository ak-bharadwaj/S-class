"""
S-Class V13: Cross-Platform Hook Core Engine (hook_core.py)

Extends controller.hooks.LifecyclePipeline to provide a unified, deterministic
interception and decision engine for external AI coding agent IDE hooks:
- Claude Code (.claude/settings.local.json)
- Cursor (.cursor/hooks.json)
- OpenAI Codex CLI (.codex/hooks.json)
- Google Antigravity (.agents/hooks.json)
- GitHub Copilot (.github/hooks/sclass.json)
- Windsurf / Cascade (.windsurf/hooks.json)

Enforces CORE-25: Fail-closed evaluation with single audit trail parity.
"""

from __future__ import annotations
import os
import sys
import json
import uuid
import hashlib
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple, Sequence

# Integration with existing D5 microkernel LifecyclePipeline
try:
    from controller.hooks import (
        LifecyclePipeline,
        LifecycleStage,
        HookContext,
        HookResult,
        LifecycleHook,
    )
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from controller.hooks import (
        LifecyclePipeline,
        LifecycleStage,
        HookContext,
        HookResult,
        LifecycleHook,
    )


class HookEventType(str, Enum):
    SESSION_START = "session_start"
    USER_PROMPT = "user_prompt"
    PRE_TOOL_USE = "pre_tool_use"
    PRE_FILE_EDIT = "pre_file_edit"
    PRE_SHELL = "pre_shell"
    PRE_READ = "pre_read"
    POST_TOOL_USE = "post_tool_use"
    POST_FILE_EDIT = "post_file_edit"


class HookDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    WARN = "warn"


@dataclass(frozen=True)
class HookEvent:
    """Platform-agnostic hook event passed into the unified decision core."""
    event_type: HookEventType
    workspace_dir: str
    platform: str  # "claude_code", "cursor", "codex", "antigravity", "copilot", "windsurf"
    tool_name: Optional[str] = None
    tool_args: Dict[str, Any] = field(default_factory=dict)
    file_path: Optional[str] = None
    prompt_text: Optional[str] = None
    timestamp: Optional[str] = None


@dataclass(frozen=True)
class HookVerdict:
    """Authoritative decision returned by S-Class evaluation."""
    decision: HookDecision
    reason: str
    fix_hint: str
    rule_id: str
    enforcement_level: str = "warn"  # "blocking" | "advisory"
    diagnostics: Tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.value,
            "reason": self.reason,
            "fix_hint": self.fix_hint,
            "rule_id": self.rule_id,
            "enforcement_level": self.enforcement_level,
            "diagnostics": list(self.diagnostics),
        }


class HookRule(LifecycleHook):
    """Protocol-compliant interceptor evaluated in the LifecyclePipeline."""

    rule_id: str = "SCLASS-GENERIC"
    category: str = "GENERIC"

    def evaluate(self, event: HookEvent) -> Optional[HookVerdict]:
        """Subclasses implement specific rule logic here. Return None to abstain."""
        raise NotImplementedError

    def execute_hook(self, context: HookContext) -> HookResult:
        """Bridges LifecyclePipeline HookContext to HookRule evaluation."""
        event: Optional[HookEvent] = context.metadata.get("hook_event")
        if not event:
            return HookResult(proceed=True)

        verdict = self.evaluate(event)
        if not verdict:
            return HookResult(proceed=True)

        if verdict.decision == HookDecision.DENY:
            return HookResult(
                proceed=False,
                error_message=f"[{verdict.rule_id}] {verdict.reason} | Fix: {verdict.fix_hint}",
                diagnostics=verdict.diagnostics or (f"Rule: {verdict.rule_id}",),
            )
        return HookResult(proceed=True, diagnostics=verdict.diagnostics)


class HookCore:
    """
    Authoritative decision core coordinating platform-agnostic HookEvents
    through the deterministic LifecyclePipeline.
    """

    def __init__(
        self,
        workspace_dir: Optional[str] = None,
        enforcement_mode: Optional[str] = None,
        pipeline: Optional[LifecyclePipeline] = None,
    ):
        self.workspace_dir = os.path.abspath(workspace_dir or os.getcwd())
        self._custom_enforcement = enforcement_mode
        self.pipeline = pipeline or LifecyclePipeline()
        self._rules: List[HookRule] = []

    def register_rule(self, rule: HookRule, stage: LifecycleStage = LifecycleStage.PRE_EXECUTE) -> None:
        self._rules.append(rule)
        self.pipeline.register_hook(stage, rule)

    def _get_enforcement_mode(self, platform: str) -> str:
        """Resolves effective enforcement mode: 'warn', 'block', or 'off'."""
        if self._custom_enforcement:
            return self._custom_enforcement

        cfg_path = os.path.join(self.workspace_dir, ".agents", "sclass_hooks.json")
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                return cfg.get("enforcement_mode", {}).get(platform, "warn")
            except Exception:
                pass
        return "warn"

    def evaluate_event(self, event: HookEvent) -> HookVerdict:
        """
        Evaluates event through the LifecyclePipeline and returns a canonical HookVerdict.
        """
        mode = self._get_enforcement_mode(event.platform)
        if mode == "off":
            return HookVerdict(
                decision=HookDecision.ALLOW,
                reason="Enforcement disabled for platform",
                fix_hint="None",
                rule_id="SCLASS-SYS-OFF",
                enforcement_level="advisory",
            )

        # Build immutable HookContext for D5 Lifecycle pipeline
        context = HookContext(
            stage=LifecycleStage.PRE_EXECUTE,
            proposal_id=f"hook_{uuid.uuid4().hex[:8]}",
            obligation_id=f"ob_{event.platform}_{event.event_type.value}",
            action_type=event.event_type.value,
            target=event.file_path or event.tool_name or "unknown",
            source_sha=hashlib.sha256((event.file_path or "").encode()).hexdigest()[:16],
            metadata={"hook_event": event, "enforcement_mode": mode},
        )

        first_warn: Optional[HookVerdict] = None

        # Execute registered rules
        for rule in self._rules:
            try:
                verdict = rule.evaluate(event)
                if not verdict:
                    continue

                if verdict.decision == HookDecision.DENY:
                    if mode == "warn":
                        # In legacy warn mode, demote DENY to WARN
                        demoted = HookVerdict(
                            decision=HookDecision.WARN,
                            reason=f"[WARN-MODE DEMOTION] {verdict.reason}",
                            fix_hint=verdict.fix_hint,
                            rule_id=verdict.rule_id,
                            enforcement_level="advisory",
                            diagnostics=verdict.diagnostics,
                        )
                        if not first_warn:
                            first_warn = demoted
                    elif mode == "audit":
                        # In audit mode: evaluate and record, but do not interfere
                        audit_verdict = HookVerdict(
                            decision=HookDecision.WARN,
                            reason=f"[AUDIT] {verdict.reason}",
                            fix_hint=verdict.fix_hint,
                            rule_id=verdict.rule_id,
                            enforcement_level="advisory",
                            diagnostics=verdict.diagnostics,
                        )
                        if not first_warn:
                            first_warn = audit_verdict
                    else:
                        # Enforce / blocking mode: policy decision has full authority
                        self.pipeline.run_stage(LifecycleStage.PRE_EXECUTE, context)
                        return verdict

                elif verdict.decision == HookDecision.WARN:
                    if not first_warn:
                        first_warn = verdict

            except Exception as e:
                # Fail-closed safety for rule exceptions when in enforce or block mode
                if mode in ("block", "enforce"):
                    return HookVerdict(
                        decision=HookDecision.DENY,
                        reason=f"Hook rule evaluation exception: {str(e)}",
                        fix_hint="Audit rule implementation or switch to audit mode",
                        rule_id="SCLASS-SYS-ERR",
                        enforcement_level="blocking",
                    )

        if first_warn:
            return first_warn

        # Default: ALLOW
        return HookVerdict(
            decision=HookDecision.ALLOW,
            reason="All S-Class governance gates cleared",
            fix_hint="None",
            rule_id="SCLASS-PASS",
            enforcement_level="advisory",
        )
