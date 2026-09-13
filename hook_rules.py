"""
S-Class V13: Built-In Hook Rules (hook_rules.py)

Implements the standard six governance rules evaluated by HookCore:
- SCLASS-SEC-001: Hardcoded Secrets Gate (DENY in strict mode)
- SCLASS-SEC-002: Dangerous Execution Functions (eval, exec, pickle) (WARN)
- SCLASS-FSM-001: Phase Integrity (code edit during spec synthesis) (WARN)
- SCLASS-FSM-002: Release Governance (altering release artifacts outside RELEASE) (DENY)
- SCLASS-BLAST-001: Caller Blast Radius Discipline (>10 downstream callers) (WARN)
- SCLASS-EVID-001: Evidence Integrity (tampering with .agents evidence) (DENY)

Strict Lazy Loading: No heavy dependencies (fastembed, tree-sitter, ast, sqlite3)
are imported at module import time, preserving <100ms cold-start budget.
"""

from __future__ import annotations
import os
import re
import json
import hashlib
from typing import Optional, Dict, Any

from hook_core import HookRule, HookEvent, HookVerdict, HookDecision, HookEventType


class SecretScannerRule(HookRule):
    """SCLASS-SEC-001: Detects hardcoded secrets, private keys, or API tokens."""

    rule_id = "SCLASS-SEC-001"
    category = "SECURITY"

    HIGH_CONFIDENCE_PATTERNS = [
        (re.compile(r"""(?:api[_-]?key|secret|token|password|auth[_-]?token)\s*[:=]\s*['"][A-Za-z0-9_\-\.]{16,}['"]""", re.IGNORECASE), "High-entropy secret assignment detected"),
        (re.compile(r"""-----BEGIN (?:RSA|OPENSSH|EC|PGP|PRIVATE) KEY-----""", re.IGNORECASE), "Private cryptographic key block detected"),
        (re.compile(r"""ghp_[A-Za-z0-9]{36}""", re.IGNORECASE), "GitHub Personal Access Token detected"),
        (re.compile(r"""sk-[A-Za-z0-9]{32,}""", re.IGNORECASE), "OpenAI/Anthropic API Key detected"),
    ]

    POSSIBLE_SECRET_PATTERNS = [
        (re.compile(r"""(?:token|secret|credential)\s*[:=]\s*['"][A-Za-z0-9_\-\.]{8,15}['"]""", re.IGNORECASE), "Potential secret assignment detected"),
    ]

    def evaluate(self, event: HookEvent) -> Optional[HookVerdict]:
        if event.event_type not in (
            HookEventType.PRE_TOOL_USE,
            HookEventType.PRE_FILE_EDIT,
            HookEventType.POST_FILE_EDIT,
            HookEventType.PRE_SHELL,
            HookEventType.PRE_READ,
        ):
            return None

        # Check content in tool_args or inspect file if present
        text_to_scan = ""
        if "content" in event.tool_args:
            text_to_scan = str(event.tool_args["content"])
        elif "file_text" in event.tool_args:
            text_to_scan = str(event.tool_args["file_text"])
        elif "new_str" in event.tool_args:
            text_to_scan = str(event.tool_args["new_str"])
        elif "command" in event.tool_args:
            text_to_scan = str(event.tool_args["command"])
        elif event.file_path and os.path.exists(event.file_path):
            try:
                # Limit scan window to first 128KB for latency
                with open(event.file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text_to_scan = f.read(131072)
            except Exception:
                pass

        if not text_to_scan:
            return None

        # Check high-confidence secrets (DENY)
        for pattern, desc in self.HIGH_CONFIDENCE_PATTERNS:
            match = pattern.search(text_to_scan)
            if match:
                raw_secret = match.group(0)
                fingerprint = hashlib.sha256(raw_secret.encode("utf-8")).hexdigest()[:12]
                line_no = text_to_scan[:match.start()].count("\n") + 1
                loc = f"{event.file_path or 'inline'}:{line_no}"
                return HookVerdict(
                    decision=HookDecision.DENY,
                    reason=(
                        f"Hardcoded secret detected: Credential detected\n"
                        f"Type: {desc}\n"
                        f"Location: {loc}\n"
                        f"Value: [REDACTED]\n"
                        f"Fingerprint: {fingerprint}"
                    ),
                    fix_hint="Extract secrets to environment variables or gitignored .env file",
                    rule_id=self.rule_id,
                    enforcement_level="blocking",
                    diagnostics=(desc, f"file: {event.file_path or 'inline'}", f"fingerprint: {fingerprint}"),
                )

        # Check possible secrets (WARN)
        for pattern, desc in self.POSSIBLE_SECRET_PATTERNS:
            match = pattern.search(text_to_scan)
            if match:
                raw_secret = match.group(0)
                fingerprint = hashlib.sha256(raw_secret.encode("utf-8")).hexdigest()[:12]
                line_no = text_to_scan[:match.start()].count("\n") + 1
                loc = f"{event.file_path or 'inline'}:{line_no}"
                return HookVerdict(
                    decision=HookDecision.WARN,
                    reason=(
                        f"Potential secret detected: Credential detected\n"
                        f"Type: {desc}\n"
                        f"Location: {loc}\n"
                        f"Value: [REDACTED]\n"
                        f"Fingerprint: {fingerprint}"
                    ),
                    fix_hint="Verify whether this value contains credentials and extract to environment variable if so",
                    rule_id=f"{self.rule_id}-WARN",
                    enforcement_level="advisory",
                    diagnostics=(desc, f"file: {event.file_path or 'inline'}", f"fingerprint: {fingerprint}"),
                )

        return None


class DangerousCodeRule(HookRule):
    """SCLASS-SEC-002: Detects dangerous execution primitives (eval, exec, pickle.loads)."""

    rule_id = "SCLASS-SEC-002"
    category = "SECURITY"

    DANGEROUS_PATTERNS = [
        (re.compile(r"\b(?:eval|exec)\s*\(", re.IGNORECASE), "Dynamic code execution via eval/exec"),
        (re.compile(r"\bpickle\.loads\s*\(", re.IGNORECASE), "Insecure deserialization via pickle.loads"),
        (re.compile(r"\b(?:subprocess\.call|os\.system)\s*\([^)]*shell\s*=\s*True", re.IGNORECASE), "Arbitrary shell injection pattern shell=True"),
    ]

    def evaluate(self, event: HookEvent) -> Optional[HookVerdict]:
        if event.event_type not in (
            HookEventType.PRE_TOOL_USE,
            HookEventType.PRE_FILE_EDIT,
            HookEventType.POST_FILE_EDIT,
            HookEventType.PRE_SHELL,
            HookEventType.PRE_READ,
        ):
            return None

        text = ""
        if "content" in event.tool_args:
            text = str(event.tool_args["content"])
        elif "file_text" in event.tool_args:
            text = str(event.tool_args["file_text"])
        elif "new_str" in event.tool_args:
            text = str(event.tool_args["new_str"])
        elif "command" in event.tool_args:
            text = str(event.tool_args["command"])
        elif event.file_path and os.path.exists(event.file_path):
            try:
                with open(event.file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read(65536)
            except Exception:
                pass

        if not text:
            return None

        for pattern, desc in self.DANGEROUS_PATTERNS:
            if pattern.search(text):
                return HookVerdict(
                    decision=HookDecision.WARN,
                    reason=f"Potentially dangerous execution construct: {desc}",
                    fix_hint="Use ast.literal_eval or structured subprocess argument arrays instead",
                    rule_id=self.rule_id,
                    enforcement_level="advisory",
                    diagnostics=(desc, f"target: {event.file_path or 'buffer'}"),
                )

        return None


class PhaseIntegrityRule(HookRule):
    """SCLASS-FSM-001: Prevents source code modifications during specification synthesis."""

    rule_id = "SCLASS-FSM-001"
    category = "FSM_INTEGRITY"

    def evaluate(self, event: HookEvent) -> Optional[HookVerdict]:
        if event.event_type not in (HookEventType.PRE_TOOL_USE, HookEventType.PRE_FILE_EDIT):
            return None

        # Check target file extension
        target = event.file_path or event.tool_args.get("path") or ""
        if not target.endswith((".py", ".ts", ".js", ".go", ".rs", ".java", ".c", ".cpp")):
            return None

        # Inspect current FSM phase (O(1) cached JSON read)
        state_path = os.path.join(event.workspace_dir, ".agents", "orchestration_state.json")
        if not os.path.exists(state_path):
            return None

        try:
            with open(state_path, "r", encoding="utf-8") as f:
                sdata = json.load(f)
            current_phase = sdata.get("currentPhase", "")
            if current_phase in ("SPECIFICATION_SYNTHESIS", "DESIGN"):
                return HookVerdict(
                    decision=HookDecision.WARN,
                    reason=f"Code modification attempted while FSM is in {current_phase} phase",
                    fix_hint="Wait for architecture and specification approval before modifying source code",
                    rule_id=self.rule_id,
                    enforcement_level="advisory",
                    diagnostics=(f"Phase: {current_phase}", f"Target: {target}"),
                )
        except Exception:
            pass

        return None


class ReleaseGovernanceRule(HookRule):
    """SCLASS-FSM-002: Blocks unauthorized modifications to release manifests."""

    rule_id = "SCLASS-FSM-002"
    category = "RELEASE"

    def evaluate(self, event: HookEvent) -> Optional[HookVerdict]:
        target = (event.file_path or event.tool_args.get("path") or "").replace("\\", "/")
        if not any(target.endswith(p) for p in ("release_manifest.json", "version.lock", ".release-marker")):
            return None

        state_path = os.path.join(event.workspace_dir, ".agents", "orchestration_state.json")
        if os.path.exists(state_path):
            try:
                with open(state_path, "r", encoding="utf-8") as f:
                    phase = json.load(f).get("currentPhase", "")
                if phase != "RELEASE":
                    return HookVerdict(
                        decision=HookDecision.DENY,
                        reason=f"Direct edit to release manifest '{os.path.basename(target)}' forbidden in phase {phase}",
                        fix_hint="Advance FSM to RELEASE phase before creating or modifying release artifacts",
                        rule_id=self.rule_id,
                        enforcement_level="blocking",
                    )
            except Exception:
                pass

        return None


class BlastRadiusRule(HookRule):
    """SCLASS-BLAST-001: Warns if a modified symbol has high caller blast radius."""

    rule_id = "SCLASS-BLAST-001"
    category = "ARCHITECTURE"
    CALLER_THRESHOLD = 10

    def evaluate(self, event: HookEvent) -> Optional[HookVerdict]:
        if event.event_type not in (HookEventType.PRE_TOOL_USE, HookEventType.PRE_FILE_EDIT):
            return None

        # Only invoke DB query if graph DB file exists
        db_path = os.path.join(event.workspace_dir, ".agents", "codebase_graph.db")
        if not os.path.exists(db_path):
            return None

        # Lazy import CodebaseGraphDB
        try:
            import sqlite3
            target_file = event.file_path or event.tool_args.get("path") or ""
            target_abs = os.path.join(event.workspace_dir, target_file) if not os.path.isabs(target_file) else target_file
            norm_target = os.path.relpath(target_abs, event.workspace_dir).replace("\\", "/")
            
            # Count downstream callers for symbols defined in this file
            query = """
                SELECT COUNT(DISTINCT src_node_id) as callers 
                FROM codebase_edges 
                WHERE edge_type = 'CALLS' AND dest_node_id LIKE ?
            """
            with sqlite3.connect(db_path) as conn:
                rows = conn.cursor().execute(query, (f"{norm_target}%",)).fetchone()
            callers = rows[0] if rows else 0
            if callers > self.CALLER_THRESHOLD:
                impact = "HIGH" if callers > 20 else "MEDIUM"
                return HookVerdict(
                    decision=HookDecision.WARN,
                    reason=f"Estimated impact:\n{impact}\n\nEstimated dependent references:\n{callers}\n\nRecommendation:\nRun targeted impact tests.",
                    fix_hint="Run impact_analysis tool or verify callers via targeted test suite before committing",
                    rule_id=self.rule_id,
                    enforcement_level="advisory",
                    diagnostics=(f"EstimatedReferences: {callers}", f"Target: {norm_target}"),
                )
        except Exception:
            pass

        return None


class EvidenceIntegrityRule(HookRule):
    """SCLASS-EVID-001: Prevents tampering with or deletion of .agents evidence artifacts."""

    rule_id = "SCLASS-EVID-001"
    category = "EVIDENCE_INTEGRITY"

    PROTECTED_ARTIFACTS = (
        "qa_report.json",
        "synthesized_spec.json",
        "design_blueprint.json",
        "event_store.jsonl",
        "event_store_snapshot.json",
        "confidence_matrix.json",
        "grill_report.json",
        "audit_ledger.jsonl",
    )

    PROTECTED_DIRS = (
        ".agents/receipts",
        ".agents/reports",
        ".agents/ledger",
        ".agents/verification",
    )

    def evaluate(self, event: HookEvent) -> Optional[HookVerdict]:
        raw_target = (event.file_path or event.tool_args.get("path") or event.tool_args.get("file_path") or "").replace("\\", "/")
        if not raw_target:
            return None

        norm_target = os.path.normpath(raw_target).replace("\\", "/")
        norm_name = os.path.basename(norm_target)
        parts = [p for p in norm_target.split("/") if p and p != "."]

        is_in_agents = ".agents" in parts or any(p in norm_target for p in self.PROTECTED_DIRS)
        is_protected_file = norm_name in self.PROTECTED_ARTIFACTS
        is_claim_proposal = False

        if is_in_agents:
            if ".agents" in parts:
                idx = parts.index(".agents")
                subparts = parts[idx + 1:]
                if subparts and subparts[0] in ("claims", "proposals"):
                    is_claim_proposal = True

        is_sclass_only = (is_in_agents and not is_claim_proposal) or is_protected_file

        if is_sclass_only:
            tool = (event.tool_name or "").lower()
            is_write_or_delete = (
                tool in ("delete", "remove", "rm", "unlink", "write_to_file", "replace_file_content", "edit", "edit_file")
                or event.tool_args.get("delete")
                or any(k in event.tool_args for k in ("content", "file_text", "new_str"))
                or event.event_type in (HookEventType.PRE_TOOL_USE, HookEventType.PRE_FILE_EDIT, HookEventType.POST_FILE_EDIT)
            )

            if is_write_or_delete:
                return HookVerdict(
                    decision=HookDecision.DENY,
                    reason=f"Tampering with evidence artifact '{norm_name}' is prohibited",
                    fix_hint="Evidence artifacts and .agents governance records may only be updated by the S-Class kernel verification engine",
                    rule_id=self.rule_id,
                    enforcement_level="blocking",
                    diagnostics=(f"ProtectedTarget: {norm_target}", f"Rule: {self.rule_id}"),
                )

        return None


def get_default_rules() -> list[HookRule]:
    """Returns standard suite of six S-Class rules in evaluation order."""
    return [
        EvidenceIntegrityRule(),
        ReleaseGovernanceRule(),
        SecretScannerRule(),
        DangerousCodeRule(),
        PhaseIntegrityRule(),
        BlastRadiusRule(),
    ]
