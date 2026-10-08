#!/usr/bin/env python3
"""
S-Class v6: Unified Lightweight Subprocess Hook Runner (hook_runner.py)

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
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

# Only import hook_core and hook_rules; no heavy external libraries
from hook_core import HookCore, HookEvent, HookEventType, HookDecision, HookVerdict
from hook_rules import get_default_rules

logger = logging.getLogger("sclass_hook_runner")


def _read_stdin_safe() -> str:
    """Safely reads stdin without hanging on empty redirects."""
    if sys.stdin is None or sys.stdin.isatty():
        return ""
    try:
        return sys.stdin.read()
    except Exception:
        return ""


def _record_last_verified(workspace_dir: str, platform: str) -> None:
    """Records ISO-8601 timestamp in .agents/sclass_hooks.json under last_verified[platform]."""
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

        # Also update platforms[platform] if present for test / telemetry consumers
        if "platforms" in cfg and isinstance(cfg["platforms"], dict):
            if platform in cfg["platforms"] and isinstance(cfg["platforms"][platform], dict):
                cfg["platforms"][platform]["verified"] = True
                cfg["platforms"][platform]["last_verified"] = now_iso

        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        # Non-fatal: runner must never crash on telemetry write
        logger.debug(f"[HookRunner] Failed to write verification telemetry: {e}")


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


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="S-Class Cross-Platform Hook Runner")
    parser.add_argument("--platform", required=True, help="Target platform (claude_code, cursor, codex, antigravity, copilot, windsurf)")
    parser.add_argument("--event-type", default="pre_tool_use", help="Hook event type")
    parser.add_argument("--workspace", default=None, help="Target workspace root")
    parser.add_argument("--repo-root", default=None, dest="repo_root", help="Alias for workspace root")
    parser.add_argument("--strict", action="store_true", default=True, help="Force block mode")
    parser.add_argument("--event", default=None, help="Inline JSON event payload")
    parser.add_argument("--file", default=None, help="Target file path if applicable")
    parser.add_argument("--tool", default=None, help="Tool name being invoked")

    args, _unknown = parser.parse_known_args(argv)

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
        except Exception as e:
            logger.debug(f"[HookRunner] Error parsing args.event payload: {e}")
    else:
        stdin_str = _read_stdin_safe()
        if stdin_str:
            try:
                raw_payload = json.loads(stdin_str)
            except Exception as e:
                logger.debug(f"[HookRunner] Error parsing stdin payload: {e}")

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
    enforcement_override = "block" if args.strict else None
    core = HookCore(workspace_dir=workspace_dir, enforcement_mode=enforcement_override)
    for rule in get_default_rules():
        core.register_rule(rule)

    # Evaluate event
    verdict = core.evaluate_event(hook_event)

    # Record verified timestamp in sclass_hooks.json
    _record_last_verified(workspace_dir, args.platform)

    # Format platform-specific outputs and exit codes
    platform = args.platform.lower()

    if platform == "cursor":
        # Cursor consumes stdout JSON and exit 0
        resp = _serialize_cursor_response(args.event_type, verdict)
        sys.stdout.write(resp)
        sys.stdout.flush()
        return 0

    elif platform == "antigravity":
        if "stop" in event_str:
            state_file = os.path.join(workspace_dir, ".agents", "orchestration_state.json")
            decision = "stop"
            reason = "Task verified."
            if not os.path.exists(state_file):
                decision = "continue"
                reason = "S-Class Completion Gate Rejected: Missing orchestration state. Cannot certify completion without state record."
            else:
                try:
                    with open(state_file, "r", encoding="utf-8") as f:
                        state = json.load(f)
                    phase = state.get("currentPhase", "")
                    profile = str(state.get("workflowProfile", "")).lower()
                    uncompleted = state.get("uncompleted_tasks", 0)
                    evidence = state.get("test_evidence_receipts", False)
                    is_question = (phase == "QUESTION" or profile == "question")
                    evidence_ok = True if is_question else bool(evidence)
                    if uncompleted or not evidence_ok or (phase and phase not in ("DONE", "RELEASE", "QUESTION")):
                        decision = "continue"
                        reason = "S-Class Completion Gate Rejected: Uncompleted tasks or unverified test evidence detected. Run tests before completing."
                except Exception as e:
                    # Fail-closed on corrupted state file
                    decision = "continue"
                    reason = f"S-Class Completion Gate Error: Corrupted orchestration state ({str(e)}). Cannot certify completion."
            if decision == "continue":
                sys.stdout.write(json.dumps({
                    "decision": "continue",
                    "reason": reason
                }))
            else:
                sys.stdout.write(json.dumps({"decision": "stop"}))
            sys.stdout.flush()
            return 0
        else: # PreToolUse
            if verdict.decision == HookDecision.DENY:
                sys.stdout.write(json.dumps({
                    "decision": "deny",
                    "reason": f"[{verdict.rule_id}] {verdict.reason}. Fix: {verdict.fix_hint}"
                }))
            else:
                sys.stdout.write(json.dumps({"decision": "allow"}))
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
        # Standard POSIX protocol (Claude Code, Codex CLI, GitHub Copilot)
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

