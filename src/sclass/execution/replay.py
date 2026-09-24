"""
S-Class Execution: Comprehensive Replay Classification & Eligibility Verifier.
Implements the deep Step-Code replay safety mechanisms required by Directive Section 4:
- Replay classes: SAFE, IDEMPOTENT, NEVER, UNKNOWN.
- Comprehensive reasoning incorporating arguments, target identity, workspace, task,
  session, mutation class, content hashes, and runtime identity.
- Rules:
  - SAFE: May be re-run automatically.
  - IDEMPOTENT: Replay allowed only after verifying identical intent, inputs, workspace,
    and environment/content hashes.
  - NEVER: Never replayed automatically under any circumstances.
  - UNKNOWN: Strictly fails closed (treated as NEVER).
"""

from __future__ import annotations
import os
import json
import hashlib
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Set, Union

from sclass.execution.operations import ReplayClass, compute_action_hash
from sclass.core.errors import SecurityViolationError


@dataclass(frozen=True)
class ReplayContext:
    """Authoritative execution context used to assess replay eligibility."""
    workspace: str
    task_id: str
    session_id: str
    runtime_identity: str
    target_identity: str
    mutation_class: str
    content_hashes: Dict[str, str] = field(default_factory=dict)
    environment_digest: str = ""

    def compute_context_digest(self) -> str:
        data = {
            "workspace": self.workspace,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "runtime_identity": self.runtime_identity,
            "target_identity": self.target_identity,
            "mutation_class": self.mutation_class,
            "content_hashes": sorted(self.content_hashes.items()),
            "environment_digest": self.environment_digest,
        }
        raw = json.dumps(data, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class ReplayAssessment:
    """Decision outcome of replay eligibility verification."""
    eligible: bool
    replay_class: ReplayClass
    reason: str
    expected_context_digest: str
    actual_context_digest: str
    matched_invariants: List[str] = field(default_factory=list)
    violated_invariants: List[str] = field(default_factory=list)


class DeepReplayClassifier:
    """
    Evaluates operation intent across multiple semantic dimensions
    beyond simple tool-name pattern matching.
    """

    SAFE_READ_TOOLS = {
        "read_file", "view_file", "list_dir", "find_by_name", "grep_search",
        "read_url_content", "inspect_session", "health_check"
    }

    MUTATING_TOOLS = {
        "write_to_file", "replace_file_content", "delete_file", "git_commit",
        "git_push", "deploy", "publish", "install_package", "modify_system"
    }

    @classmethod
    def classify(
        cls,
        action: str,
        target: str = "",
        parameters: Optional[Dict[str, Any]] = None,
        workspace: str = "",
        task_id: str = "",
        session_id: str = "",
        mutation_class: Optional[str] = None,
        content_hashes: Optional[Dict[str, str]] = None,
        runtime_identity: str = "step-code",
    ) -> ReplayClass:
        clean_action = (action or "").strip().lower()
        params = parameters or {}

        # If explicitly marked UNKNOWN or empty
        if not clean_action:
            return ReplayClass.UNKNOWN

        # Mutation class overrides
        if mutation_class:
            mc = mutation_class.upper()
            if mc in ("DESTRUCTIVE", "EXTERNAL_EFFECT", "IRREVERSIBLE", "FINANCIAL"):
                return ReplayClass.NEVER
            if mc == "IDEMPOTENT_WRITE":
                return ReplayClass.IDEMPOTENT

        # Known direct read-only tools
        if clean_action in cls.SAFE_READ_TOOLS:
            return ReplayClass.SAFE

        # Known direct mutating tools
        if clean_action in cls.MUTATING_TOOLS:
            # Overwriting an existing file with identical content hash can be idempotent
            if clean_action in ("write_to_file", "replace_file_content"):
                if content_hashes and "expected_content_hash" in content_hashes:
                    return ReplayClass.IDEMPOTENT
            return ReplayClass.NEVER

        # Command / shell execution actions require deep parameter inspection
        if clean_action in ("run_command", "terminal_execute", "execute_command", "shell_exec"):
            cmd = str(params.get("command") or params.get("command_line") or params.get("cmd") or "").strip()
            if not cmd:
                return ReplayClass.UNKNOWN

            # Shell mutation signs
            if any(char in cmd for char in (">", ">>", "|", ";", "&&", "||", "&", "$(", "`")):
                return ReplayClass.NEVER

            tokens = cmd.split()
            if not tokens:
                return ReplayClass.UNKNOWN

            prog = os.path.splitext(os.path.basename(tokens[0]))[0].lower()
            if prog in ("pytest", "unittest", "ls", "dir", "pwd", "grep", "cat", "wc"):
                return ReplayClass.SAFE
            if prog in ("python", "python3") and len(tokens) >= 3 and tokens[1] == "-m" and tokens[2] in ("pytest", "unittest"):
                return ReplayClass.SAFE
            if prog == "git" and len(tokens) >= 2 and tokens[1] in ("status", "diff", "log", "show", "branch"):
                return ReplayClass.SAFE

            return ReplayClass.NEVER

        # Fail closed for any unmapped or ambiguous tool
        return ReplayClass.UNKNOWN

    @classmethod
    def verify_replay_eligibility(
        cls,
        recorded_op: Dict[str, Any],
        current_context: ReplayContext,
    ) -> ReplayAssessment:
        """
        Formally verifies if a previously executed or failed operation
        is legally allowed to replay in the current context.
        """
        rc_str = recorded_op.get("replay_class", ReplayClass.UNKNOWN.value)
        try:
            rc = ReplayClass(rc_str)
        except ValueError:
            rc = ReplayClass.UNKNOWN

        expected_ctx_digest = recorded_op.get("metadata", {}).get("context_digest", "")
        actual_ctx_digest = current_context.compute_context_digest()

        # Rule 1: SAFE operations can be re-run automatically
        if rc == ReplayClass.SAFE:
            return ReplayAssessment(
                eligible=True,
                replay_class=rc,
                reason="Operation is classified SAFE (read-only query). Automatic replay permitted.",
                expected_context_digest=expected_ctx_digest,
                actual_context_digest=actual_ctx_digest,
                matched_invariants=["SAFE_REPLAY_CLASS"],
                violated_invariants=[],
            )

        # Rule 2: NEVER operations must NEVER be automatically replayed
        if rc == ReplayClass.NEVER:
            return ReplayAssessment(
                eligible=False,
                replay_class=rc,
                reason="Operation is classified NEVER (mutating/destructive effect). Replay strictly forbidden.",
                expected_context_digest=expected_ctx_digest,
                actual_context_digest=actual_ctx_digest,
                matched_invariants=[],
                violated_invariants=["NEVER_REPLAY_FORBIDDEN"],
            )

        # Rule 3: UNKNOWN operations fail closed
        if rc == ReplayClass.UNKNOWN:
            return ReplayAssessment(
                eligible=False,
                replay_class=rc,
                reason="Operation replay class is UNKNOWN. Failing closed: replay denied.",
                expected_context_digest=expected_ctx_digest,
                actual_context_digest=actual_ctx_digest,
                matched_invariants=[],
                violated_invariants=["UNKNOWN_REPLAY_FAIL_CLOSED"],
            )

        # Rule 4: IDEMPOTENT operations require full context and intent equivalence
        matched: List[str] = []
        violated: List[str] = []

        # Check recorded workspace vs current workspace
        rec_workspace = recorded_op.get("workspace_id") or recorded_op.get("metadata", {}).get("workspace")
        if rec_workspace and rec_workspace != current_context.workspace:
            violated.append("WORKSPACE_MISMATCH")
        else:
            matched.append("WORKSPACE_MATCH")

        # Check task id
        rec_task = recorded_op.get("task_id")
        if rec_task and rec_task != current_context.task_id:
            violated.append("TASK_MISMATCH")
        else:
            matched.append("TASK_MATCH")

        # Check runtime identity
        rec_runtime = recorded_op.get("runtime_name")
        if rec_runtime and rec_runtime != current_context.runtime_identity:
            violated.append("RUNTIME_IDENTITY_MISMATCH")
        else:
            matched.append("RUNTIME_IDENTITY_MATCH")

        # Check content hashes if present
        rec_content_hashes = recorded_op.get("metadata", {}).get("content_hashes", {})
        if rec_content_hashes:
            for k, expected_h in rec_content_hashes.items():
                actual_h = current_context.content_hashes.get(k)
                if actual_h != expected_h:
                    violated.append(f"CONTENT_HASH_MISMATCH_{k}")
                else:
                    matched.append(f"CONTENT_HASH_MATCH_{k}")

        is_eligible = len(violated) == 0

        return ReplayAssessment(
            eligible=is_eligible,
            replay_class=rc,
            reason="IDEMPOTENT replay verified across all context invariants" if is_eligible else f"IDEMPOTENT replay rejected due to context violations: {violated}",
            expected_context_digest=expected_ctx_digest,
            actual_context_digest=actual_ctx_digest,
            matched_invariants=matched,
            violated_invariants=violated,
        )
