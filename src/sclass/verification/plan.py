"""
S-Class Verification: Verification Plan and Multi-Provider Orchestration.
Coordinates multiple independent evidence providers to produce authoritative claim verdicts.
"""

from __future__ import annotations
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Union

from sclass.domain.claim import Claim, ClaimType
from sclass.domain.evidence import Evidence, EvidenceReceipt, build_evidence_from_receipt
from sclass.domain.verification import VerificationResult
from sclass.verification.acceptance import ClaimAcceptanceMatrix
from sclass.execution.backend import ExecutionBackend, get_execution_backend
from sclass.trust.ledger import LocalLedger


@dataclass
class VerificationPlan:
    """
    Orchestration plan coordinating multiple independent evidence providers
    (test runners, linters, security scanners, build tools) against declared claims.
    """
    plan_id: str = field(default_factory=lambda: f"vplan_{uuid.uuid4().hex[:12]}")
    goal: str = ""
    task_id: str = ""
    verifiers: List[str] = field(default_factory=list)
    commands: List[Any] = field(default_factory=list)
    claim_ids: List[str] = field(default_factory=list)
    target_claims: List[Claim] = field(default_factory=list)
    required_evidence_kinds: List[str] = field(default_factory=list)
    verifier_ids: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    execution_backend: str = "host"
    timeout_seconds: float = 120.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def coordinate(
        self,
        evidence_items: List[Any],
        workspace_dir: str = "",
    ) -> Dict[str, VerificationResult]:
        """
        Coordinates multiple independent evidence items across all target claims in this plan.
        Returns a mapping of claim_id -> VerificationResult.
        Authoritatively enforces required evidence kinds and verifier IDs declared by the plan.
        """
        ws = os.path.abspath(workspace_dir or os.getcwd())
        results: Dict[str, VerificationResult] = {}

        # 1. Determine present evidence kinds and verifier sources
        present_kinds = set()
        present_sources = set()
        has_unobserved = False
        has_unauthentic = False

        for ev in evidence_items:
            # Validate observation status
            is_obs = getattr(ev, "is_observed", True)
            if not is_obs:
                has_unobserved = True

            # Validate provenance integrity
            if isinstance(ev, dict):
                if ev.get("is_observed") and not (ev.get("receipt_id") and ev.get("receipt_hash")):
                    has_unauthentic = True
                if ev.get("is_fake") or ev.get("forged"):
                    has_unauthentic = True
            elif getattr(ev, "is_fake", False) or getattr(ev, "forged", False):
                has_unauthentic = True
            elif hasattr(ev, "compute_hash") and getattr(ev, "receipt_hash", None):
                try:
                    if ev.receipt_hash != ev.compute_hash():
                        has_unauthentic = True
                except Exception:
                    has_unauthentic = True

            kind = getattr(ev, "evidence_kind", None)
            if kind:
                present_kinds.add(str(kind).lower())
            src = getattr(ev, "source", None) or getattr(ev, "verifier", None)
            if src:
                present_sources.add(str(src).lower())

        def _match_verifier(req_id: str, sources: set) -> bool:
            """Canonical exact matching for verifier identity, preventing substring spoofing."""
            req_clean = str(req_id).lower().strip()
            for s in sources:
                s_clean = s.lower().strip()
                if req_clean == s_clean:
                    return True
                # Canonical provider/version tags: e.g. pytest@7.4, pytest==7.4, pytest:7.4
                if "@" in s_clean and s_clean.split("@")[0].strip() == req_clean:
                    return True
                if "==" in s_clean and s_clean.split("==")[0].strip() == req_clean:
                    return True
                if ":" in s_clean and s_clean.split(":")[0].strip() == req_clean:
                    return True
            return False

        missing_kinds = [k for k in self.required_evidence_kinds if str(k).lower() not in present_kinds]
        missing_verifiers = [v for v in self.verifier_ids if not _match_verifier(v, present_sources)]

        for claim in self.target_claims:
            verdict = ClaimAcceptanceMatrix.evaluate_multi_evidence(
                claim=claim,
                evidence_items=evidence_items,
                workspace_dir=ws,
            )

            # Invariant: MISSING REQUIRED EVIDENCE -> NO ACCEPTED CLAIM
            if verdict.is_accepted:
                if not evidence_items:
                    verdict = VerificationResult(
                        status="INCONCLUSIVE",
                        claim_id=claim.claim_id,
                        reason="MISSING REQUIRED EVIDENCE -> NO ACCEPTED CLAIM: No evidence items provided to plan.",
                        metadata={**verdict.metadata, "empty_evidence": True},
                    )
                elif missing_kinds:
                    verdict = VerificationResult(
                        status="INCONCLUSIVE",
                        claim_id=claim.claim_id,
                        reason=f"MISSING REQUIRED EVIDENCE -> NO ACCEPTED CLAIM: Plan requires evidence kinds {self.required_evidence_kinds}, but missing: {missing_kinds}",
                        metadata={**verdict.metadata, "missing_evidence_kinds": missing_kinds},
                    )
                elif missing_verifiers:
                    verdict = VerificationResult(
                        status="INCONCLUSIVE",
                        claim_id=claim.claim_id,
                        reason=f"MISSING REQUIRED EVIDENCE -> NO ACCEPTED CLAIM: Plan requires verifier IDs {self.verifier_ids}, but missing: {missing_verifiers}",
                        metadata={**verdict.metadata, "missing_verifiers": missing_verifiers},
                    )
                elif has_unobserved or has_unauthentic:
                    verdict = VerificationResult(
                        status="REJECT",
                        claim_id=claim.claim_id,
                        reason="UNAUTHENTIC EVIDENCE: Provided evidence contains unobserved, forged, or unauthentic receipts.",
                        metadata={**verdict.metadata, "unobserved_evidence": True, "unauthentic_evidence": has_unauthentic},
                    )

            results[claim.claim_id] = verdict

        return results


    def execute_and_verify(
        self,
        workspace_dir: str,
        commands: Optional[List[str]] = None,
        backend: Optional[ExecutionBackend] = None,
        ledger: Optional[LocalLedger] = None,
    ) -> Dict[str, VerificationResult]:
        """
        Executes plan commands via observation convergence, gathers authentic evidence,
        and coordinates adjudication across all target claims.
        """
        from sclass.observation.convergence import ObservationConvergence
        from sclass.domain.action import ActionRequest

        ws = os.path.abspath(workspace_dir)
        exec_backend = backend or get_execution_backend(self.execution_backend)
        local_ledger = ledger or LocalLedger(workspace_dir=ws)

        gathered_evidence: List[Any] = []
        cmds_to_run = commands or self.parameters.get("commands", [])

        for cmd in cmds_to_run:
            act_req = ActionRequest(
                actor="verification_orchestrator",
                session=self.plan_id,
                capability="terminal.execute",
                action="run_command",
                target=cmd,
                workspace=ws,
            )
            _, receipt = ObservationConvergence.execute_and_observe(
                request=act_req,
                command=cmd,
                backend=exec_backend,
                ledger=local_ledger,
                timeout=self.timeout_seconds,
            )
            gathered_evidence.append(receipt)
            # Also extract typed evidence models
            gathered_evidence.extend(build_evidence_from_receipt(receipt))

        return self.coordinate(gathered_evidence, workspace_dir=ws)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "goal": self.goal,
            "target_claims": [c.to_dict() if hasattr(c, "to_dict") else c for c in self.target_claims],
            "required_evidence_kinds": list(self.required_evidence_kinds),
            "verifier_ids": list(self.verifier_ids),
            "parameters": dict(self.parameters),
            "execution_backend": self.execution_backend,
            "timeout_seconds": self.timeout_seconds,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> VerificationPlan:
        claims: List[Claim] = []
        for c in data.get("target_claims", []):
            if isinstance(c, dict):
                claims.append(Claim.from_dict(c))
            elif isinstance(c, Claim):
                claims.append(c)

        return cls(
            plan_id=data.get("plan_id", f"vplan_{uuid.uuid4().hex[:12]}"),
            goal=data.get("goal", ""),
            target_claims=claims,
            required_evidence_kinds=list(data.get("required_evidence_kinds", [])),
            verifier_ids=list(data.get("verifier_ids", [])),
            parameters=dict(data.get("parameters", {})),
            execution_backend=data.get("execution_backend", "host"),
            timeout_seconds=data.get("timeout_seconds", 120.0),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
        )
