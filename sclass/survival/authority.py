"""
S-Class Survival v0: Authority and Policy Enforcement (sclass/survival/authority.py)

Enforces:
- Path authority boundaries: AGENT_WRITABLE, USER_WRITABLE, SCLASS_ONLY (.agents protection)
- Rule-level authority (DENY vs WARN based on rule definition)
- Enforcement vs Audit modes (eliminates global warn-demotion in enforce mode)
- Sanitized secret scanning with zero secret leakage (HIGH_CONFIDENCE vs POSSIBLE_SECRET)
- Fail-closed error handling (exceptions fail closed to DENY in enforce mode)
"""

from __future__ import annotations
import os
import re
import json
import hashlib
from enum import Enum
from typing import Optional, Dict, Any, Tuple, List

from sclass.survival.models import AuthorizationRequest, AuthorizationDecision


class PathAuthority(str, Enum):
    AGENT_WRITABLE = "agent_writable"
    USER_WRITABLE = "user_writable"
    SCLASS_ONLY = "sclass_only"


PROTECTED_SCLASS_DIRS = (
    ".agents/receipts",
    ".agents/reports",
    ".agents/ledger",
    ".agents/verification",
)

PROTECTED_SCLASS_FILES = (
    "qa_report.json",
    "synthesized_spec.json",
    "design_blueprint.json",
    "event_store.jsonl",
    "event_store_snapshot.json",
    "confidence_matrix.json",
    "grill_report.json",
    "audit_ledger.jsonl",
)

AGENT_PROPOSAL_DIRS = (
    ".agents/claims",
    ".agents/proposals",
)


def get_path_authority(target_path: str, workspace_dir: str = "") -> PathAuthority:
    """Determines the authority class for a given file or directory path."""
    if not target_path:
        return PathAuthority.USER_WRITABLE

    norm = target_path.replace("\\", "/").strip()
    if workspace_dir:
        ws_norm = workspace_dir.replace("\\", "/").rstrip("/")
        if norm.lower().startswith(ws_norm.lower()):
            norm = norm[len(ws_norm):].lstrip("/")

    if norm.startswith("./"):
        norm = norm[2:]

    # Check SCLASS_ONLY directories
    for sdir in PROTECTED_SCLASS_DIRS:
        if norm.startswith(sdir) or f"/{sdir}/" in f"/{norm}/":
            return PathAuthority.SCLASS_ONLY

    # Check SCLASS_ONLY protected filenames under .agents
    basename = os.path.basename(norm)
    if ".agents" in norm and basename in PROTECTED_SCLASS_FILES:
        return PathAuthority.SCLASS_ONLY

    # Check AGENT_WRITABLE proposal directories
    for adir in AGENT_PROPOSAL_DIRS:
        if norm.startswith(adir) or f"/{adir}/" in f"/{norm}/":
            return PathAuthority.AGENT_WRITABLE

    return PathAuthority.USER_WRITABLE


# High confidence credential patterns: strictly DENY
HIGH_CONFIDENCE_SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN (?:RSA|OPENSSH|EC|PGP|DSA|PRIVATE) KEY-----"), "Cryptographic Private Key Block"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS Access Key ID"),
    (re.compile(r"\bghp_[A-Za-z0-9]{36}\b"), "GitHub Personal Access Token"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{82}\b"), "GitHub Fine-Grained Token"),
    (re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"), "OpenAI API Secret Key"),
    (re.compile(r"\bsk-ant-[A-Za-z0-9_-]{32,}\b"), "Anthropic API Key"),
    (re.compile(r"""(?:api[_-]?key|secret[_-]?key|auth[_-]?token|password)\s*[:=]\s*['"][A-Za-z0-9_.-]{20,}['"]""", re.IGNORECASE), "High-Entropy Credential Assignment"),
]

# Possible secret patterns: WARN only to prevent false-alarm friction
POSSIBLE_SECRET_PATTERNS = [
    (re.compile(r"""(?:token|secret|credential)\s*[:=]\s*['"][A-Za-z0-9_.-]{10,19}['"]""", re.IGNORECASE), "Short Potential Secret Assignment"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"), "Potential JWT Token"),
]

DANGEROUS_CODE_PATTERNS = [
    (re.compile(r"\b(?:eval|exec)\s*\("), "Dynamic code execution via eval/exec"),
    (re.compile(r"\bpickle\.loads\s*\("), "Insecure deserialization via pickle.loads"),
    (re.compile(r"\b(?:subprocess\.call|os\.system)\s*\([^)]*shell\s*=\s*True"), "Arbitrary shell execution with shell=True"),
]


def _scan_for_secrets(text: str, file_target: str = "") -> Optional[Tuple[str, str, str, str]]:
    """
    Scans text for secrets. Returns (confidence, desc, location, fingerprint) or None.
    NEVER returns the raw secret!
    confidence: 'HIGH_CONFIDENCE' | 'POSSIBLE_SECRET'
    """
    if not text:
        return None

    # Check high confidence first
    for pattern, desc in HIGH_CONFIDENCE_SECRET_PATTERNS:
        match = pattern.search(text)
        if match:
            raw_match = match.group(0)
            fingerprint = hashlib.sha256(raw_match.encode("utf-8")).hexdigest()[:12]
            line_no = text[:match.start()].count("\n") + 1
            loc = f"{file_target or 'inline'}:{line_no}"
            return ("HIGH_CONFIDENCE", desc, loc, fingerprint)

    # Check possible secrets
    for pattern, desc in POSSIBLE_SECRET_PATTERNS:
        match = pattern.search(text)
        if match:
            raw_match = match.group(0)
            fingerprint = hashlib.sha256(raw_match.encode("utf-8")).hexdigest()[:12]
            line_no = text[:match.start()].count("\n") + 1
            loc = f"{file_target or 'inline'}:{line_no}"
            return ("POSSIBLE_SECRET", desc, loc, fingerprint)

    return None


def authorize(
    request: AuthorizationRequest,
    mode: str = "enforce",
    workspace_dir: Optional[str] = None,
    rules_override: Optional[Dict[str, str]] = None,
) -> AuthorizationDecision:
    """
    Authorizes an agent action proposal against S-Class canonical governance policies.
    
    Modes:
    - 'enforce': Policy decision has full authority (DENY blocks execution).
    - 'audit': Evaluates and reports, but does not block.
    - 'warn': Legacy backward-compatibility mode.
    """
    ws = os.path.abspath(workspace_dir or request.workspace or os.getcwd())
    target = request.target or request.parameters.get("path") or request.parameters.get("file_path") or ""

    try:
        # Rule 1: SCLASS-AUTH-001 / SCLASS-EVID-001 — Path Authority Boundary Protection
        if target:
            auth_class = get_path_authority(target, ws)
            is_write_or_delete = request.action in ("file_edit", "delete", "write", "pre_file_edit") or any(
                k in request.parameters for k in ("content", "file_text", "new_str", "delete")
            ) or (request.tool or "").lower() in ("delete", "remove", "rm", "unlink", "write_to_file", "replace_file_content")

            if auth_class == PathAuthority.SCLASS_ONLY and is_write_or_delete:
                decision = AuthorizationDecision(
                    outcome="deny" if mode != "audit" else "warn",
                    policy_id="SCLASS-EVID-001",
                    risk_level="critical",
                    reason=f"Tampering with protected S-Class authority artifact '{os.path.basename(target)}' is prohibited",
                    remediation="Protected .agents artifacts and ledger records may only be updated by the S-Class kernel verification engine",
                    diagnostics=(f"PathAuthority: {auth_class.value}", f"Target: {target}"),
                )
                return decision

        # Rule 2: SCLASS-FSM-002 — Release Artifact Governance
        if target and any(target.replace("\\", "/").endswith(p) for p in ("release_manifest.json", "version.lock", ".release-marker")):
            state_path = os.path.join(ws, ".agents", "orchestration_state.json")
            phase = "UNKNOWN"
            if os.path.exists(state_path):
                try:
                    with open(state_path, "r", encoding="utf-8") as f:
                        phase = json.load(f).get("currentPhase", "")
                except Exception:
                    pass
            if phase != "RELEASE":
                return AuthorizationDecision(
                    outcome="deny" if mode != "audit" else "warn",
                    policy_id="SCLASS-FSM-002",
                    risk_level="high",
                    reason=f"Direct edit to release manifest '{os.path.basename(target)}' forbidden in phase {phase}",
                    remediation="Advance FSM to RELEASE phase before creating or modifying release artifacts",
                    diagnostics=(f"Phase: {phase}", f"Target: {target}"),
                )

        # Extract text content for scanning
        text_to_scan = ""
        for key in ("content", "file_text", "new_str", "command", "prompt"):
            if key in request.parameters:
                text_to_scan = str(request.parameters[key])
                break

        if not text_to_scan and target and os.path.isabs(target) and os.path.exists(target):
            try:
                with open(target, "r", encoding="utf-8", errors="ignore") as f:
                    text_to_scan = f.read(131072)
            except Exception:
                pass

        # Rule 3: SCLASS-SEC-001 — Secret Scanner Gate (Sanitized, No Leakage)
        if text_to_scan:
            secret_hit = _scan_for_secrets(text_to_scan, target)
            if secret_hit:
                confidence, desc, loc, fingerprint = secret_hit
                is_high = confidence == "HIGH_CONFIDENCE"
                sanitized_reason = (
                    f"Hardcoded secret detected: Credential detected\n"
                    f"Type: {desc}\n"
                    f"Location: {loc}\n"
                    f"Value: [REDACTED]\n"
                    f"Fingerprint: {fingerprint}"
                )
                if is_high:
                    return AuthorizationDecision(
                        outcome="deny" if mode != "audit" else "warn",
                        policy_id="SCLASS-SEC-001",
                        risk_level="critical",
                        reason=sanitized_reason,
                        remediation="Extract secrets to environment variables or gitignored .env file. Never commit raw credentials.",
                        diagnostics=(f"Type: {desc}", f"Location: {loc}", f"Fingerprint: {fingerprint}"),
                    )
                else:
                    return AuthorizationDecision(
                        outcome="warn",
                        policy_id="SCLASS-SEC-001-WARN",
                        risk_level="medium",
                        reason=sanitized_reason,
                        remediation="Verify whether this token-like string is an actual credential. If so, move it to an environment variable.",
                        diagnostics=(f"Type: {desc}", f"Location: {loc}", f"Fingerprint: {fingerprint}"),
                    )

        # Rule 4: SCLASS-SEC-002 — Dangerous Code Primitives (Always WARN)
        if text_to_scan:
            for pattern, desc in DANGEROUS_CODE_PATTERNS:
                if pattern.search(text_to_scan):
                    return AuthorizationDecision(
                        outcome="warn",
                        policy_id="SCLASS-SEC-002",
                        risk_level="medium",
                        reason=f"Potentially dangerous execution construct: {desc}",
                        remediation="Use ast.literal_eval or structured subprocess argument arrays instead",
                        diagnostics=(desc, f"Target: {target or 'inline'}"),
                    )

        # Rule 5: SCLASS-BLAST-001 — Blast Radius Discipline
        if target:
            db_path = os.path.join(ws, ".agents", "codebase_graph.db")
            if os.path.exists(db_path):
                try:
                    import sqlite3
                    target_abs = os.path.join(ws, target) if not os.path.isabs(target) else target
                    norm_target = os.path.relpath(target_abs, ws).replace("\\", "/")
                    query = """
                        SELECT COUNT(DISTINCT src_node_id) as callers 
                        FROM codebase_edges 
                        WHERE edge_type = 'CALLS' AND dest_node_id LIKE ?
                    """
                    with sqlite3.connect(db_path) as conn:
                        rows = conn.cursor().execute(query, (f"{norm_target}%",)).fetchone()
                    callers = rows[0] if rows else 0
                    if callers > 10:
                        impact = "HIGH" if callers > 20 else "MEDIUM"
                        return AuthorizationDecision(
                            outcome="warn",
                            policy_id="SCLASS-BLAST-001",
                            risk_level="high" if impact == "HIGH" else "medium",
                            reason=f"Estimated impact: {impact}\nEstimated dependent references: {callers}\nRecommendation: Run targeted impact tests.",
                            remediation="Run impact analysis or verify affected callers via targeted test suite before committing",
                            diagnostics=(f"EstimatedReferences: {callers}", f"Target: {norm_target}"),
                        )
                except Exception:
                    pass

        # Rule 6: SCLASS-FSM-001 — Phase Integrity (Code edit during spec synthesis)
        if target and target.endswith((".py", ".ts", ".js", ".go", ".rs", ".java", ".c", ".cpp")):
            state_path = os.path.join(ws, ".agents", "orchestration_state.json")
            if os.path.exists(state_path):
                try:
                    with open(state_path, "r", encoding="utf-8") as f:
                        phase = json.load(f).get("currentPhase", "")
                    if phase in ("SPECIFICATION_SYNTHESIS", "DESIGN"):
                        return AuthorizationDecision(
                            outcome="warn",
                            policy_id="SCLASS-FSM-001",
                            risk_level="medium",
                            reason=f"Code modification attempted while FSM is in {phase} phase",
                            remediation="Wait for architecture and specification approval before modifying source code",
                            diagnostics=(f"Phase: {phase}", f"Target: {target}"),
                        )
                except Exception:
                    pass

        # Default outcome: ALLOW
        return AuthorizationDecision(
            outcome="allow",
            policy_id="SCLASS-PASS",
            risk_level="low",
            reason="All S-Class governance gates cleared",
            remediation="Proceed with proposed operation",
        )

    except Exception as e:
        # Fail-closed safety for policy exceptions
        if mode in ("enforce", "block"):
            return AuthorizationDecision(
                outcome="deny",
                policy_id="SCLASS-SYS-ERR",
                risk_level="critical",
                reason=f"Policy evaluation exception: {str(e)}",
                remediation="Audit policy engine or inspect event payload",
                diagnostics=(f"Exception: {str(e)}",),
            )
        return AuthorizationDecision(
            outcome="warn",
            policy_id="SCLASS-SYS-ERR-AUDIT",
            risk_level="medium",
            reason=f"Policy evaluation exception in audit mode: {str(e)}",
            remediation="Inspect event payload and error logs",
            diagnostics=(f"Exception: {str(e)}",),
        )

