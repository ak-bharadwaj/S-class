#!/usr/bin/env python3
"""
S-Class V13: Unified Lightweight Subprocess Hook Runner (hook_runner.py)

CLI / Process entry point invoked directly by host IDE hook harnesses:
- Claude Code: PreToolUse, UserPromptSubmit, SessionStart
- Cursor: beforeReadFile, beforeShellExecution, beforeMCPExecution, preToolUse, beforeSubmitPrompt
- Codex CLI: PreToolUse, PermissionRequest, SessionStart
- Google Antigravity: BeforeTool, AfterTool, SessionStart
- GitHub Copilot: preToolUse, sessionStart
- Windsurf: pre_write_code, pre_run_command, post_write_code

Performance Target: < 100ms cold-start execution from spawn to exit.
Audit Parity: Touches last_verified[platform] in .agents/sclass_hooks.json upon success.
"""

from __future__ import annotations
import sys
import os
import json
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, Optional

# Only import hook_core and hook_rules; no heavy external libraries
from hook_core import HookCore, HookEvent, HookEventType, HookDecision, HookVerdict
from hook_rules import get_default_rules


def _read_stdin_safe() -> str:
    """Safely reads stdin without hanging on Windows pipes or empty redirects."""
    if sys.stdin is None or sys.stdin.isatty():
        return ""
    try:
        if sys.platform == "win32":
            import msvcrt
            from ctypes import windll, byref, c_ulong, c_void_p
            try:
                handle = msvcrt.get_osfhandle(sys.stdin.fileno())
                avail = c_ulong()
                res = windll.kernel32.PeekNamedPipe(c_void_p(handle), None, 0, None, byref(avail), None)
                if res != 0 and avail.value > 0:
                    return sys.stdin.read()
                elif res != 0:
                    return ""
            except Exception:
                pass
        # Fallback if PeekNamedPipe not available or non-pipe redirect
        import select
        if hasattr(select, "select"):
            r, _, _ = select.select([sys.stdin], [], [], 0.0)
            if r:
                return sys.stdin.read()
            return ""
        return ""
    except Exception:
        return ""


def _record_hook_lifecycle(
    workspace_dir: str,
    platform: str,
    verdict: Optional[HookVerdict] = None,
    is_execution: bool = False,
) -> None:
    """
    Records separate lifecycle timestamps in .agents/sclass_hooks.json:
    - last_hook_seen: runner received event
    - last_decision: policy decision recorded
    - last_execution: action execution observed
    (last_verified is only updated when evidence verification succeeds).
    """
    try:
        cfg_path = os.path.join(workspace_dir, ".agents", "sclass_hooks.json")
        if not os.path.exists(cfg_path):
            return

        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        now_iso = datetime.now(timezone.utc).isoformat()

        # Update last_hook_seen
        if "last_hook_seen" not in cfg or not isinstance(cfg["last_hook_seen"], dict):
            cfg["last_hook_seen"] = {}
        cfg["last_hook_seen"][platform] = now_iso

        # Update last_decision
        if verdict:
            if "last_decision" not in cfg or not isinstance(cfg["last_decision"], dict):
                cfg["last_decision"] = {}
            cfg["last_decision"][platform] = {
                "outcome": verdict.decision.value,
                "rule_id": verdict.rule_id,
                "timestamp": now_iso,
            }

        # Update last_execution if this is an execution/post event
        if is_execution:
            if "last_execution" not in cfg or not isinstance(cfg["last_execution"], dict):
                cfg["last_execution"] = {}
            cfg["last_execution"][platform] = now_iso

        # Backward compatibility for existing telemetry consumers / legacy tests
        if "platforms" in cfg and isinstance(cfg["platforms"], dict):
            if platform in cfg["platforms"] and isinstance(cfg["platforms"][platform], dict):
                cfg["platforms"][platform]["verified"] = True
                cfg["platforms"][platform]["last_verified"] = now_iso
                cfg["platforms"][platform]["last_hook_seen"] = now_iso
                if verdict:
                    cfg["platforms"][platform]["last_decision"] = verdict.to_dict()

        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        # Non-fatal: runner must never crash on telemetry write
        pass


def _record_last_verified(workspace_dir: str, platform: str) -> None:
    """Records ISO-8601 timestamp in .agents/sclass_hooks.json under last_verified[platform] when evidence verification succeeds."""
    try:
        cfg_path = os.path.join(workspace_dir, ".agents", "sclass_hooks.json")
        if not os.path.exists(cfg_path):
            return

        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        now_iso = datetime.now(timezone.utc).isoformat()
        if "last_verified" not in cfg or not isinstance(cfg["last_verified"], dict):
            cfg["last_verified"] = {}
        cfg["last_verified"][platform] = now_iso

        if "platforms" in cfg and isinstance(cfg["platforms"], dict):
            if platform in cfg["platforms"] and isinstance(cfg["platforms"][platform], dict):
                cfg["platforms"][platform]["verified"] = True
                cfg["platforms"][platform]["last_verified"] = now_iso

        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


record_last_verified = _record_last_verified


def _serialize_cursor_response(event_type: str, verdict: HookVerdict) -> str:
    """Serializes event-specific response payload for Cursor 1.7+."""
    is_deny = verdict.decision == HookDecision.DENY

    if event_type in ("beforeReadFile", "pre_read", "before_read_file"):
        if is_deny:
            return json.dumps({
                "permission": "deny",
                "user_message": f"[{verdict.rule_id}] Read blocked: {verdict.reason}",
                "agent_message": f"S-Class security policy denied file read: {verdict.reason}. Fix: {verdict.fix_hint}",
                "userMessage": f"[{verdict.rule_id}] Read blocked: {verdict.reason}",
                "agentMessage": f"S-Class security policy denied file read: {verdict.reason}. Fix: {verdict.fix_hint}",
            })
        return json.dumps({"permission": "allow"})

    elif event_type in ("beforeShellExecution", "pre_shell", "before_shell_execution"):
        if is_deny:
            return json.dumps({
                "permission": "deny",
                "user_message": f"[{verdict.rule_id}] Command blocked: {verdict.reason}",
                "agent_message": f"S-Class policy rejected terminal execution: {verdict.reason}. Fix: {verdict.fix_hint}",
                "userMessage": f"[{verdict.rule_id}] Command blocked: {verdict.reason}",
                "agentMessage": f"S-Class policy rejected terminal execution: {verdict.reason}. Fix: {verdict.fix_hint}",
                "block": True,
            })
        return json.dumps({"permission": "allow", "block": False})

    elif event_type in ("beforeSubmitPrompt", "user_prompt", "before_submit_prompt"):
        # Prompt submission is warn-only in S-Class
        return json.dumps({
            "block": False,
            "user_message": verdict.reason if verdict.decision == HookDecision.WARN else "",
            "userMessage": verdict.reason if verdict.decision == HookDecision.WARN else "",
        })

    else:
        # General preToolUse / beforeMCPExecution
        if is_deny:
            return json.dumps({
                "permission": "deny",
                "agent_message": f"[{verdict.rule_id}] Tool rejected: {verdict.reason}. Fix: {verdict.fix_hint}",
                "agentMessage": f"[{verdict.rule_id}] Tool rejected: {verdict.reason}. Fix: {verdict.fix_hint}",
                "userMessage": f"[{verdict.rule_id}] Action blocked: {verdict.reason}",
            })
        return json.dumps({"permission": "allow"})


def main() -> int:
    parser = argparse.ArgumentParser(description="S-Class Cross-Platform Hook Runner")
    parser.add_argument("--platform", required=True, help="Target platform (claude_code, cursor, codex, antigravity, copilot, windsurf)")
    parser.add_argument("--event-type", default="pre_tool_use", help="Hook event type")
    parser.add_argument("--workspace", default=None, help="Target workspace root")
    parser.add_argument("--repo-root", default=None, dest="repo_root", help="Alias for workspace root")
    parser.add_argument("--strict", action="store_true", default=False, help="Force block mode")
    parser.add_argument("--enforce", action="store_true", default=False, help="Force strict enforcement mode")
    parser.add_argument("--audit", action="store_true", default=False, help="Force audit mode (non-blocking)")
    parser.add_argument("--event", default=None, help="Inline JSON event payload")
    parser.add_argument("--file", default=None, help="Target file path if applicable")
    parser.add_argument("--tool", default=None, help="Tool name being invoked")

    args, unknown = parser.parse_known_args()

    workspace_dir = os.path.abspath(
        args.workspace
        or args.repo_root
        or os.environ.get("SCLASS_WORKSPACE")
        or os.environ.get("CLAUDE_PROJECT_DIR")
        or os.getcwd()
    )

    # Read payload from args or non-blocking stdin
    raw_payload: Dict[str, Any] = {}
    if args.event:
        try:
            raw_payload = json.loads(args.event)
        except Exception:
            pass
    else:
        stdin_str = _read_stdin_safe()
        if stdin_str:
            try:
                raw_payload = json.loads(stdin_str)
            except Exception:
                pass

    # Extract normalized parameters
    norm_event_type = HookEventType.PRE_TOOL_USE
    event_str = args.event_type.lower()
    if "session" in event_str:
        norm_event_type = HookEventType.SESSION_START
    elif "prompt" in event_str:
        norm_event_type = HookEventType.USER_PROMPT
    elif "shell" in event_str:
        norm_event_type = HookEventType.PRE_SHELL
    elif "read" in event_str:
        norm_event_type = HookEventType.PRE_READ
    elif "post" in event_str:
        norm_event_type = HookEventType.POST_TOOL_USE

    tool_name = args.tool or raw_payload.get("tool_name") or raw_payload.get("tool")
    file_path = args.file or raw_payload.get("file_path") or raw_payload.get("path") or raw_payload.get("target") or raw_payload.get("filePath")
    tool_args = raw_payload.get("tool_input") or raw_payload.get("tool_args") or raw_payload

    hook_event = HookEvent(
        event_type=norm_event_type,
        workspace_dir=workspace_dir,
        platform=args.platform,
        tool_name=tool_name,
        tool_args=tool_args if isinstance(tool_args, dict) else {},
        file_path=file_path,
        prompt_text=raw_payload.get("prompt"),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    # Initialize Core with default rules
    enforcement_override = None
    if args.audit:
        enforcement_override = "audit"
    elif args.strict or args.enforce:
        enforcement_override = "enforce"

    core = HookCore(workspace_dir=workspace_dir, enforcement_mode=enforcement_override)
    for rule in get_default_rules():
        core.register_rule(rule)

    # Evaluate event
    verdict = core.evaluate_event(hook_event)

    # Record lifecycle state (hook_seen, decision, execution)
    _record_hook_lifecycle(
        workspace_dir,
        args.platform,
        verdict=verdict,
        is_execution="post" in args.event_type.lower(),
    )

    # Format platform-specific outputs and exit codes
    platform = args.platform.lower()

    if platform == "cursor":
        # Cursor consumes stdout JSON and exit 0
        resp = _serialize_cursor_response(args.event_type, verdict)
        sys.stdout.write(resp)
        sys.stdout.flush()
        return 0

    elif platform == "windsurf":
        # Windsurf protocol: Exit 0 = allow, Exit 2 = deny
        if verdict.decision == HookDecision.DENY:
            sys.stderr.write(f"[{verdict.rule_id}] BLOCKED: {verdict.reason}\nFix: {verdict.fix_hint}\n")
            sys.stderr.flush()
            return 2
        elif verdict.decision == HookDecision.WARN:
            sys.stderr.write(f"[{verdict.rule_id}] WARNING: {verdict.reason}\n")
            sys.stderr.flush()
        return 0

    else:
        # Standard POSIX protocol (Claude Code, Codex CLI, Antigravity, GitHub Copilot)
        if verdict.decision == HookDecision.DENY:
            sys.stderr.write(f"[{verdict.rule_id}] BLOCKED: {verdict.reason}\nFix: {verdict.fix_hint}\n")
            sys.stderr.flush()
            return 1
        elif verdict.decision == HookDecision.WARN:
            sys.stderr.write(f"[{verdict.rule_id}] WARNING: {verdict.reason}\n")
            sys.stderr.flush()
            # If Claude Code, inject advisory into systemMessage if possible
            if platform == "claude_code":
                sys.stdout.write(json.dumps({"systemMessage": f"[{verdict.rule_id}] {verdict.reason}"}))
                sys.stdout.flush()
        return 0


if __name__ == "__main__":
    sys.exit(main())
