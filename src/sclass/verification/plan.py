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
        """
        ws = os.path.abspath(workspace_dir or os.getcwd())
        results: Dict[str, VerificationResult] = {}

        for claim in self.target_claims:
            verdict = ClaimAcceptanceMatrix.evaluate_multi_evidence(
                claim=claim,
                evidence_items=evidence_items,
                workspace_dir=ws,
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
