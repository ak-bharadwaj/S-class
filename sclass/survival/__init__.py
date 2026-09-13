"""
S-Class Survival v0: Package Core (sclass/survival/__init__.py)

Exposes the minimal survival interface:
- authorize()
- verify()
- record()
"""

from __future__ import annotations
from typing import Optional, Dict, Any

from sclass.survival.models import (
    AuthorizationRequest,
    AuthorizationDecision,
    EvidenceReceipt,
    ObservedReceipt,
    VerificationEvent,
    ProposedEvidence,
    ClaimedEvidence,
    Claim,
    VerificationResult,
    AdapterCapabilities,
)
from sclass.survival.authority import authorize, PathAuthority, get_path_authority
from sclass.survival.evidence import (
    _create_observed_receipt,
    create_receipt,
    create_proposed_evidence,
    load_receipt,
    save_receipt,
    observe_command,
    compute_workspace_snapshot,
    compute_workspace_fingerprint,
)
from sclass.survival.verification import verify_claim, check_verification_staleness
from sclass.survival.ledger import LocalLedger
from sclass.survival.adapters import (
    AgentAdapter,
    ClaudeCodeSurvivalAdapter,
    CursorSurvivalAdapter,
    CodexSurvivalAdapter,
    AntigravitySurvivalAdapter,
)


def verify(
    claim: Claim,
    evidence: Optional[EvidenceReceipt],
    workspace_dir: Optional[str] = None,
    ledger: Optional[LocalLedger] = None,
) -> VerificationResult:
    """Convenience entry point for verifying an agent claim against observed evidence."""
    l = ledger or LocalLedger(workspace_dir=workspace_dir)
    return verify_claim(claim, evidence, workspace_dir=workspace_dir, ledger=l)


def record(
    event_type: str,
    payload: Dict[str, Any],
    workspace_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Convenience entry point for appending an event to the local tamper-evident ledger."""
    ledger = LocalLedger(workspace_dir=workspace_dir)
    return ledger.append(event_type, payload)


__all__ = [
    "authorize",
    "verify",
    "record",
    "AuthorizationRequest",
    "AuthorizationDecision",
    "EvidenceReceipt",
    "ObservedReceipt",
    "VerificationEvent",
    "ProposedEvidence",
    "ClaimedEvidence",
    "Claim",
    "VerificationResult",
    "AdapterCapabilities",
    "PathAuthority",
    "get_path_authority",
    "create_proposed_evidence",
    "load_receipt",
    "save_receipt",
    "observe_command",
    "compute_workspace_snapshot",
    "compute_workspace_fingerprint",
    "verify_claim",
    "check_verification_staleness",
    "LocalLedger",
    "AgentAdapter",
    "ClaudeCodeSurvivalAdapter",
    "CursorSurvivalAdapter",
    "CodexSurvivalAdapter",
    "AntigravitySurvivalAdapter",
]

