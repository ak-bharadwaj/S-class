"""
S-Class Core: Independent Completion Evaluator (Section 21).
Authoritatively adjudicates proposed task or goal completion from agents or runtimes:
Agent says "DONE" / Runtime says "GOAL COMPLETE" -> Evaluated independently by S-Class.

Evaluation Criteria:
1. Obligations satisfied: All mandatory technical obligations are in SATISFIED state.
2. Required claims verified: All required technical claims are verified (test pass alone is insufficient).
3. Evidence freshness: All required evidence receipts are fresh and not invalidated by subsequent mutations.
4. Clean frontier: No unresolved or failed items remaining in the verification frontier.
5. Regression checks: No active regression failures exist.
6. Workspace consistency: State workspace identity strictly matches authoritative workspace.

Verdicts: ACCEPT | BLOCK | RECOVER
"""

from __future__ import annotations
import os
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set, Union

from sclass.domain.project import VerifiedProjectState
from sclass.domain.obligations import TechnicalObligation, ObligationStatus


class CompletionVerdict(str, Enum):
    ACCEPT = "ACCEPT"
    BLOCK = "BLOCK"
    RECOVER = "RECOVER"


@dataclass(frozen=True)
class CompletionAssessment:
    """Authoritative result of an independent completion evaluation."""
    task_id: str
    verdict: CompletionVerdict
    obligations_satisfied: bool
    claims_verified: bool
    evidence_fresh: bool
    frontier_resolved: bool
    regressions_satisfied: bool
    workspace_consistent: bool
    reasons: List[str]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_accepted(self) -> bool:
        return self.verdict == CompletionVerdict.ACCEPT

    @property
    def is_blocked(self) -> bool:
        return self.verdict == CompletionVerdict.BLOCK

    @property
    def requires_recovery(self) -> bool:
        return self.verdict == CompletionVerdict.RECOVER

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "verdict": self.verdict.value,
            "obligations_satisfied": self.obligations_satisfied,
            "claims_verified": self.claims_verified,
            "evidence_fresh": self.evidence_fresh,
            "frontier_resolved": self.frontier_resolved,
            "regressions_satisfied": self.regressions_satisfied,
            "workspace_consistent": self.workspace_consistent,
            "reasons": list(self.reasons),
            "timestamp": self.timestamp,
            "details": dict(self.details),
        }


class CompletionEvaluator:
    """
    Independent completion adjudicator.
    Neither agent narrative ("DONE") nor runtime state ("GOAL COMPLETE") can close a task.
    """

    @classmethod
    def adjudicate(
        cls,
        task_id: str,
        proposed_completion: Any,
        state: VerifiedProjectState,
        obligations: Optional[List[TechnicalObligation]] = None,
        expected_workspace: str = "",
        mutation_boundary_timestamp: Optional[str] = None,
    ) -> CompletionAssessment:
        reasons: List[str] = []
        needs_recovery = False

        # 1. Technical Obligations Check
        task_obligations = [o for o in (obligations or []) if o.task_id == task_id or not o.task_id]
        obs_satisfied = True
        if task_obligations:
            for ob in task_obligations:
                if ob.mandatory and ob.status != ObligationStatus.SATISFIED:
                    obs_satisfied = False
                    reasons.append(f"Mandatory obligation '{ob.obligation_id}' ({ob.title}) is {ob.status.value}")
                    if ob.status in (ObligationStatus.FAILED, ObligationStatus.REPAIR_REQUIRED):
                        needs_recovery = True
        else:
            task_verified_claims = [
                c for c in state.verified_claims
                if (c.get("task_id") == task_id or not c.get("task_id"))
            ]
            if not task_verified_claims and task_id not in state.verified_tasks:
                obs_satisfied = False
                reasons.append(f"No technical obligations or verified claims exist for task '{task_id}'")

        # 2. Required Claims Verified Check
        verified_cids = {
            c.get("claim_id") or c.get("id")
            for c in state.verified_claims
            if (c.get("task_id") == task_id or not c.get("task_id"))
        }
        invalidated_cids = {
            c.get("claim_id") or c.get("id")
            for c in state.invalidated_claims
            if (c.get("task_id") == task_id or not c.get("task_id"))
        }

        claims_verified = True
        # Check if any verified claim is also recorded as invalidated/stale
        compromised_claims = verified_cids.intersection(invalidated_cids)
        if compromised_claims:
            claims_verified = False
            reasons.append(f"Verified claims were invalidated prior to completion: {list(compromised_claims)}")
            needs_recovery = True

        # If any claims for this task are invalidated / rejected and not verified
        unresolved_invalidated = invalidated_cids - verified_cids
        if unresolved_invalidated:
            claims_verified = False
            reasons.append(f"Task '{task_id}' has invalidated claims that have not been re-verified: {list(unresolved_invalidated)}")
            needs_recovery = True

        # Check if all required claim types from obligations are actually verified
        task_verified_claims = [
            c for c in state.verified_claims
            if (c.get("task_id") == task_id or not c.get("task_id"))
        ]
        if task_obligations:
            for ob in task_obligations:
                if ob.mandatory:
                    ob_claim_types = set(ob.required_claim_types)
                    # Find verified claims fulfilling this obligation strictly for this task
                    fulfilled = False
                    for c in task_verified_claims:
                        ctype = str(c.get("claim_type", "")).upper()
                        target_types = {str(t).upper() for t in ob_claim_types}
                        if ctype in target_types or not ob_claim_types:
                            fulfilled = True
                            break
                    if not fulfilled:
                        claims_verified = False
                        formatted_types = [str(ct).upper() for ct in ob_claim_types]
                        reasons.append(f"Obligation '{ob.obligation_id}' requires {formatted_types} claim, none verified for task '{task_id}'")

        # 3. Evidence Freshness Check (scoped to task obligations and verified claims)
        evidence_fresh = True
        if mutation_boundary_timestamp and state.evidence:
            task_receipt_ids = set()
            for c in task_verified_claims:
                rid = c.get("evidence_receipt_id") or c.get("receipt_id")
                if rid:
                    task_receipt_ids.add(rid)
                for r in c.get("evidence_receipt_ids", []):
                    task_receipt_ids.add(r)
            for ob in task_obligations:
                if ob.satisfied_receipt_id:
                    task_receipt_ids.add(ob.satisfied_receipt_id)

            target_evidence = [
                ev for ev in state.evidence
                if (ev.get("receipt_id") in task_receipt_ids or ev.get("id") in task_receipt_ids
                    or ev.get("task_id") == task_id or not task_receipt_ids)
            ]
            for ev in target_evidence:
                ev_ts = ev.get("timestamp") or ev.get("created_at")
                if ev_ts and ev_ts < mutation_boundary_timestamp:
                    evidence_fresh = False
                    reasons.append(f"Evidence '{ev.get('receipt_id')}' timestamp {ev_ts} is older than mutation boundary {mutation_boundary_timestamp}")
                    needs_recovery = True
                    break

        # 4. Clean Frontier Check
        frontier_resolved = True
        if state.frontier:
            unresolved_frontier = [
                f for f in state.frontier
                if f.get("status") not in ("VERIFIED", "SATISFIED", "RESOLVED")
            ]
            if unresolved_frontier:
                frontier_resolved = False
                reasons.append(f"Verification frontier contains {len(unresolved_frontier)} unresolved items")

        # 5. Regression Checks
        regressions_satisfied = True
        if state.active_regressions:
            unresolved_regressions = [
                r for r in state.active_regressions
                if not r.get("resolved", False)
            ]
            if unresolved_regressions:
                regressions_satisfied = False
                reasons.append(f"Active regressions detected: {len(unresolved_regressions)} unresolved")
                needs_recovery = True

        # 6. Workspace Consistency Check
        workspace_consistent = True
        if expected_workspace:
            exp_norm = os.path.normpath(expected_workspace).lower()
            state_ws = state.workspace or state.workspace_identity or ""
            if state_ws:
                state_norm = os.path.normpath(state_ws).lower()
                if exp_norm != state_norm:
                    workspace_consistent = False
                    reasons.append(f"Workspace identity mismatch: expected '{expected_workspace}', found '{state_ws}'")

        # Determine Verdict
        all_passed = (
            obs_satisfied
            and claims_verified
            and evidence_fresh
            and frontier_resolved
            and regressions_satisfied
            and workspace_consistent
        )

        if all_passed:
            verdict = CompletionVerdict.ACCEPT
            reasons = ["All canonical technical obligations, evidence, claims, and regressions satisfied."]
        elif needs_recovery:
            verdict = CompletionVerdict.RECOVER
        else:
            verdict = CompletionVerdict.BLOCK

        return CompletionAssessment(
            task_id=task_id,
            verdict=verdict,
            obligations_satisfied=obs_satisfied,
            claims_verified=claims_verified,
            evidence_fresh=evidence_fresh,
            frontier_resolved=frontier_resolved,
            regressions_satisfied=regressions_satisfied,
            workspace_consistent=workspace_consistent,
            reasons=reasons,
            details={
                "task_id": task_id,
                "obligations_count": len(task_obligations),
                "verified_claims_count": len(verified_cids),
                "invalidated_claims_count": len(invalidated_cids),
            },
        )
