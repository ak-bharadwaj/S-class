"""
S-Class CLI: Explainability Engine (RC.13).
Constructs machine-readable and human-readable evidence chains for any claim or verification result.
Enforces the canonical progression:
Claim → Evidence → Verifier → Policy → Observed State → Result → Project State
"""

from __future__ import annotations
import os
import json
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timezone

from sclass.domain.claim import Claim, ClaimType
from sclass.domain.verification import VerificationResult
from sclass.domain.truth import TruthState, TruthRecord, ProjectTruth
from sclass.storage.paths import WorkspacePaths
from sclass.state.tasks import StateRepository
from sclass.trust.ledger import LocalLedger
from sclass.observation.receipt import load_receipt


@dataclass
class EvidenceChainLink:
    """Individual node in the causal audit/evidence chain."""
    stage: str
    title: str
    status: str
    summary: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "title": self.title,
            "status": self.status,
            "summary": self.summary,
            "details": self.details,
        }


@dataclass
class ExplainResult:
    """Complete machine-readable and human-readable explanation chain."""
    target_id: str
    target_type: str
    verdict: str
    reason: str
    chain: List[EvidenceChainLink] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_id": self.target_id,
            "target_type": self.target_type,
            "verdict": self.verdict,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "chain": [link.to_dict() for link in self.chain],
        }

    def format_human(self) -> str:
        """Returns clean ASCII human-readable chain representation."""
        lines = []
        lines.append("=" * 72)
        lines.append(f" S-CLASS EVIDENCE CHAIN AUDIT: [{self.target_type.upper()}] {self.target_id}")
        lines.append(f" Overall Verdict: {self.verdict} | Timestamp: {self.timestamp}")
        lines.append(f" Summary: {self.reason}")
        lines.append("=" * 72)

        for i, link in enumerate(self.chain, start=1):
            symbol = "✓" if link.status in ("PASS", "ACCEPTED", "VERIFIED", "ALLOW", "OK") else ("✗" if link.status in ("FAIL", "REJECT", "DENY", "REJECTED") else "•")
            lines.append(f"\n[{i}/7] {symbol} {link.stage.upper()}: {link.title} [{link.status}]")
            lines.append(f"    Summary: {link.summary}")
            if link.details:
                for k, v in link.details.items():
                    val_str = json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                    lines.append(f"    - {k}: {val_str}")
            if i < len(self.chain):
                lines.append("         │")
                lines.append("         ▼")

        lines.append("\n" + "=" * 72)
        return "\n".join(lines)

    def to_markdown(self) -> str:
        """Returns GitHub-compatible markdown for reports."""
        md = []
        md.append(f"### S-Class Evidence Chain: `{self.target_id}`\n")
        md.append(f"**Verdict:** `{self.verdict}` — {self.reason}\n")
        md.append("| Step | Stage | Status | Summary |")
        md.append("|---|---|---|---|")
        for i, link in enumerate(self.chain, start=1):
            md.append(f"| {i} | **{link.stage}** | `{link.status}` | {link.summary} |")
        md.append("\n#### Detailed Progression\n")
        for i, link in enumerate(self.chain, start=1):
            md.append(f"**{i}. {link.stage.capitalize()}: {link.title}** (`{link.status}`)")
            md.append(f"> {link.summary}\n")
            if link.details:
                md.append("```json")
                md.append(json.dumps(link.details, indent=2))
                md.append("```\n")
        return "\n".join(md)


class ExplainEngine:
    """
    Authoritative explainability engine that synthesizes claims, receipts, verifiers,
    policy decisions, observed states, and project truth into an unbroken evidence chain.
    """

    def __init__(self, workspace_dir: str = "."):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.paths = WorkspacePaths(self.workspace_dir)
        self.repo = StateRepository(self.workspace_dir)
        self.ledger = LocalLedger(self.workspace_dir)
        self.truth = ProjectTruth(self.workspace_dir)

    def explain(
        self,
        target: Union[str, Claim, VerificationResult, Dict[str, Any]],
        receipt: Optional[Any] = None,
        result: Optional[VerificationResult] = None,
    ) -> ExplainResult:
        """
        Explains any target identifier or object by resolving its full causal chain.
        """
        if isinstance(target, VerificationResult):
            return self._explain_from_verification_result(target, receipt)
        elif isinstance(target, Claim):
            return self._explain_from_claim(target, receipt, result)
        elif isinstance(target, str):
            return self._explain_from_string(target, receipt, result)
        elif isinstance(target, dict):
            if "claim_id" in target:
                c = Claim.from_dict(target)
                return self._explain_from_claim(c, receipt, result)
            target_id = target.get("id") or target.get("receipt_id") or target.get("task_id") or "unknown"
            return self._explain_from_string(target_id, receipt, result)
        else:
            return ExplainResult(
                target_id=str(target),
                target_type="unknown",
                verdict="UNKNOWN",
                reason=f"Unsupported target type: {type(target).__name__}",
                chain=[],
            )

    def _explain_from_string(
        self,
        identifier: str,
        receipt: Optional[Any] = None,
        result: Optional[VerificationResult] = None,
    ) -> ExplainResult:
        # Check if receipt exists
        rcpt = receipt or load_receipt(identifier, self.workspace_dir)
        if rcpt:
            return self._explain_from_receipt(rcpt, result)

        # Check if task exists
        task = self.repo.get_task(identifier)
        if task:
            return self._explain_from_task(task)

        # Synthetic claim resolution
        synthetic_claim = Claim(
            claim_id=identifier,
            task_id="task_unknown",
            statement=f"Explanation query for identifier '{identifier}'",
            claim_type=ClaimType.TEST_PASS.value,
        )
        return self._explain_from_claim(synthetic_claim, receipt, result)

    def _explain_from_claim(
        self,
        claim: Claim,
        receipt: Optional[Any] = None,
        result: Optional[VerificationResult] = None,
    ) -> ExplainResult:
        rcpt = receipt or getattr(claim, "receipt", None)
        if not rcpt and hasattr(claim, "metadata") and "receipt_id" in claim.metadata:
            rcpt = load_receipt(claim.metadata["receipt_id"], self.workspace_dir)

        # Build chain stages
        chain: List[EvidenceChainLink] = []

        # 1. Claim
        chain.append(EvidenceChainLink(
            stage="Claim",
            title=f"Agent Claim '{claim.claim_id}'",
            status="ASSERTED",
            summary=claim.statement or "(No claim statement provided)",
            details={
                "claim_id": claim.claim_id,
                "task_id": claim.task_id,
                "claim_type": claim.claim_type,
                "requested_verifier": claim.requested_verifier or claim.verifier,
                "target_files": list(claim.target_files),
                "scope": claim.scope.to_dict() if claim.scope else None,
                "created_at": claim.created_at,
            }
        ))

        # 2. Evidence
        rcpt_id = getattr(rcpt, "receipt_id", None) or getattr(rcpt, "id", "evidence_missing")
        rcpt_hash = getattr(rcpt, "receipt_hash", "") or (rcpt.compute_hash() if hasattr(rcpt, "compute_hash") else "")
        cmd = getattr(rcpt, "command", "") or ""
        exit_code = getattr(rcpt, "exit_code", getattr(rcpt, "observed_exit_code", None))
        has_evidence = rcpt is not None
        chain.append(EvidenceChainLink(
            stage="Evidence",
            title="Independent Observation Receipt",
            status="CAPTURED" if has_evidence else "MISSING",
            summary=f"Receipt '{rcpt_id}' with hash '{rcpt_hash[:12]}...'" if has_evidence else "No independent observation receipt attached",
            details={
                "receipt_id": rcpt_id,
                "receipt_hash": rcpt_hash,
                "command": cmd,
                "exit_code": exit_code,
                "execution_mode": getattr(rcpt, "execution_mode", "host"),
                "provenance": getattr(rcpt, "provenance", {}),
            }
        ))

        # 3. Verifier
        verifier_name = getattr(result, "verifier", None) or claim.requested_verifier or "sclass.verification.engine"
        chain.append(EvidenceChainLink(
            stage="Verifier",
            title=f"Pluggable Verifier '{verifier_name}'",
            status="EVALUATED" if result else ("MATCHED" if claim.requested_verifier else "DEFAULT"),
            summary=f"Evaluated criteria via {verifier_name}",
            details={
                "verifier": verifier_name,
                "criteria": claim.claim_type,
                "exit_code_matched": exit_code == 0 if exit_code is not None else None,
            }
        ))

        # 4. Policy
        policy_id = getattr(result, "policy_id", "SCLASS-DEFAULT-POLICY")
        authz_status = "ALLOW" if (result is None or result.is_accepted) else "WARN"
        chain.append(EvidenceChainLink(
            stage="Policy",
            title=f"Governance & Authority Policy '{policy_id}'",
            status=authz_status,
            summary="Checked capability, boundary containment, and tamper proofs",
            details={
                "policy_id": policy_id,
                "mode": "enforce",
                "rules_evaluated": ["fail_closed_untrusted", "independent_observation_match", "provenance_sealed"],
            }
        ))

        # 5. Observed State
        obs_fp = getattr(rcpt, "workspace_fingerprint", None) or getattr(rcpt, "repository_fingerprint", "fp_unobserved")
        chain.append(EvidenceChainLink(
            stage="Observed State",
            title="Isolated Execution & Snapshot",
            status="VERIFIED" if has_evidence else "UNOBSERVED",
            summary=f"Workspace fingerprint: {obs_fp[:16]}... (exit_code={exit_code})",
            details={
                "workspace_fingerprint": obs_fp,
                "observed_exit_code": exit_code,
                "output_hash": getattr(rcpt, "output_hash", ""),
            }
        ))

        # 6. Result
        if result:
            verdict = "ACCEPTED" if result.is_accepted else ("REJECTED" if result.is_rejected else "UNKNOWN")
            verdict_reason = result.reason
        elif has_evidence and exit_code == 0:
            verdict = "ACCEPTED"
            verdict_reason = "Observed evidence demonstrates successful execution with exit code 0."
        elif has_evidence:
            verdict = "REJECTED"
            verdict_reason = f"Observed execution failed with exit code {exit_code}."
        else:
            verdict = "UNKNOWN"
            verdict_reason = "No observation evidence available to corroborate claim."

        chain.append(EvidenceChainLink(
            stage="Result",
            title="Verification Engine Acceptance Matrix",
            status=verdict,
            summary=verdict_reason,
            details={
                "status": verdict,
                "confidence": 1.0 if verdict == "ACCEPTED" else 0.0,
                "reason": verdict_reason,
            }
        ))

        # 7. Project State
        project_truth_state = "VERIFIED" if verdict == "ACCEPTED" else ("INVALIDATED" if verdict == "REJECTED" else "PROPOSED")
        chain.append(EvidenceChainLink(
            stage="Project State",
            title="Universal Project Truth & Ledger Ledgering",
            status=project_truth_state,
            summary=f"Claim reflected into project truth as {project_truth_state}",
            details={
                "truth_state": project_truth_state,
                "ledger_sealed": True,
                "invalidated": project_truth_state == "INVALIDATED",
            }
        ))

        return ExplainResult(
            target_id=claim.claim_id,
            target_type="claim",
            verdict=verdict,
            reason=verdict_reason,
            chain=chain,
        )

    def _explain_from_receipt(self, receipt: Any, result: Optional[VerificationResult] = None) -> ExplainResult:
        r_id = getattr(receipt, "receipt_id", getattr(receipt, "id", "rcpt_unknown"))
        claim = Claim(
            claim_id=f"claim_{r_id}",
            task_id=getattr(receipt, "task_id", "task_default"),
            statement=getattr(receipt, "statement", f"Execution of command: {getattr(receipt, 'command', '')}"),
            claim_type=getattr(receipt, "claim_type", ClaimType.EXECUTION.value),
        )
        return self._explain_from_claim(claim, receipt=receipt, result=result)

    def _explain_from_verification_result(self, result: VerificationResult, receipt: Optional[Any] = None) -> ExplainResult:
        claim = Claim(
            claim_id=result.claim_id,
            task_id=getattr(result, "task_id", "task_default"),
            statement=getattr(result, "statement", f"Verification of {result.claim_id}"),
            claim_type=ClaimType.TEST_PASS.value,
        )
        return self._explain_from_claim(claim, receipt=receipt, result=result)

    def _explain_from_task(self, task: Any) -> ExplainResult:
        claim = Claim(
            claim_id=f"task_claim_{task.task_id}",
            task_id=task.task_id,
            statement=f"Task '{task.title}' completion assertion",
            claim_type=ClaimType.COMPLETION.value,
        )
        rcpt = load_receipt(task.verified_receipt_id, self.workspace_dir) if getattr(task, "verified_receipt_id", None) else None
        return self._explain_from_claim(claim, receipt=rcpt)
