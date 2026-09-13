"""
S-Class Domain: Claim Dependency Graph & Composable Acceptance Decisions.
Allows complex claims (e.g. "Authentication feature works") to decompose into
mandatory evidence requirements:
- source files changed
- unit tests pass
- integration tests pass
- no critical security regression
and authoritatively synthesizes an immutable AcceptanceDecision.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

from sclass.domain.claim import Claim, ClaimScope
from sclass.domain.verification import VerificationResult


@dataclass(frozen=True)
class EvidenceRequirement:
    """An explicit required evidence piece for claim acceptance."""
    requirement_id: str
    kind: str  # e.g., FILE_CHANGE, UNIT_TESTS, INTEGRATION_TESTS, SECURITY, BUILD
    description: str
    mandatory: bool = True
    scope: Optional[ClaimScope] = None
    expected_verifier: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "kind": self.kind,
            "description": self.description,
            "mandatory": self.mandatory,
            "scope": self.scope.to_dict() if self.scope else None,
            "expected_verifier": self.expected_verifier,
        }


@dataclass(frozen=True)
class AcceptanceDecision:
    """The aggregate acceptance decision for a composite claim or dependency graph."""
    claim_id: str
    decision: str  # ACCEPT | REJECT | INCONCLUSIVE | UNSUPPORTED
    satisfied_requirements: Tuple[str, ...]
    unsatisfied_requirements: Tuple[str, ...]
    sub_verdicts: Dict[str, Dict[str, Any]]
    reason: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def is_accepted(self) -> bool:
        return self.decision == "ACCEPT"

    @property
    def is_rejected(self) -> bool:
        return self.decision == "REJECT"

    @property
    def is_inconclusive(self) -> bool:
        return self.decision == "INCONCLUSIVE"

    @property
    def is_unsupported(self) -> bool:
        return self.decision == "UNSUPPORTED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "decision": self.decision,
            "satisfied_requirements": list(self.satisfied_requirements),
            "unsatisfied_requirements": list(self.unsatisfied_requirements),
            "sub_verdicts": self.sub_verdicts,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


@dataclass
class CompositeClaim:
    """
    A composable claim that can depend on sub-claims and multiple evidence requirements.
    """
    claim: Claim
    requirements: List[EvidenceRequirement] = field(default_factory=list)
    sub_claims: List[CompositeClaim] = field(default_factory=list)

    def add_requirement(self, requirement: EvidenceRequirement) -> None:
        self.requirements.append(requirement)

    def add_sub_claim(self, sub_claim: CompositeClaim) -> None:
        self.sub_claims.append(sub_claim)

    def evaluate(self, evidence_map: Dict[str, Any]) -> AcceptanceDecision:
        """
        Evaluates the composite claim against provided evidence keyed by requirement_id.
        """
        satisfied: List[str] = []
        unsatisfied: List[str] = []
        sub_verdicts: Dict[str, Dict[str, Any]] = {}

        for req in self.requirements:
            ev = evidence_map.get(req.requirement_id)
            if ev is None:
                unsatisfied.append(req.requirement_id)
                sub_verdicts[req.requirement_id] = {
                    "status": "REJECT" if req.mandatory else "INCONCLUSIVE",
                    "reason": f"Missing evidence for requirement: {req.description}",
                }
                continue

            # Check if evidence has exit_code
            exit_code = getattr(ev, "exit_code", None)
            if exit_code is not None and exit_code != 0:
                unsatisfied.append(req.requirement_id)
                sub_verdicts[req.requirement_id] = {
                    "status": "REJECT",
                    "reason": f"Observed execution failed with exit code {exit_code}",
                }
                continue

            # Check verifier if expected
            if req.expected_verifier:
                ev_ver = getattr(ev, "verifier", "")
                if ev_ver != req.expected_verifier:
                    unsatisfied.append(req.requirement_id)
                    sub_verdicts[req.requirement_id] = {
                        "status": "REJECT",
                        "reason": f"Verifier mismatch: expected '{req.expected_verifier}', observed '{ev_ver}'",
                    }
                    continue

            satisfied.append(req.requirement_id)
            sub_verdicts[req.requirement_id] = {
                "status": "ACCEPT",
                "reason": f"Evidence satisfied requirement: {req.description}",
            }

        # Evaluate sub-claims
        for sc in self.sub_claims:
            sc_decision = sc.evaluate(evidence_map)
            sub_verdicts[sc.claim.claim_id] = sc_decision.to_dict()
            if sc_decision.is_accepted:
                satisfied.append(sc.claim.claim_id)
            else:
                unsatisfied.append(sc.claim.claim_id)

        if not unsatisfied:
            decision = "ACCEPT"
            reason = f"All {len(satisfied)} evidence requirements satisfied."
        elif any(sub_verdicts.get(u, {}).get("status") == "REJECT" for u in unsatisfied):
            decision = "REJECT"
            reason = f"Rejected due to unmet mandatory requirements: {unsatisfied}."
        else:
            decision = "INCONCLUSIVE"
            reason = f"Inconclusive: requirements {unsatisfied} could not be authoritatively verified."

        return AcceptanceDecision(
            claim_id=self.claim.claim_id,
            decision=decision,
            satisfied_requirements=tuple(satisfied),
            unsatisfied_requirements=tuple(unsatisfied),
            sub_verdicts=sub_verdicts,
            reason=reason,
        )
