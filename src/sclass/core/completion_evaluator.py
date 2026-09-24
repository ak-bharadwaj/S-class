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
    CORRUPT = "CORRUPT"
    UNAVAILABLE = "UNAVAILABLE"


def _parse_iso_utc(ts: Union[str, datetime]) -> datetime:
    """Safely normalizes an ISO 8601 string or datetime to a timezone-aware UTC datetime."""
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)
    if not isinstance(ts, str) or not ts.strip():
        return datetime.min.replace(tzinfo=timezone.utc)
    cleaned = ts.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


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
    canonical_persistence_consistent: bool = True
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

    @property
    def is_corrupt(self) -> bool:
        return self.verdict == CompletionVerdict.CORRUPT

    @property
    def is_unavailable(self) -> bool:
        return self.verdict == CompletionVerdict.UNAVAILABLE

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
            "canonical_persistence_consistent": self.canonical_persistence_consistent,
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
        state: Optional[VerifiedProjectState] = None,
        obligations: Optional[List[TechnicalObligation]] = None,
        expected_workspace: str = "",
        mutation_boundary_timestamp: Optional[str] = None,
        require_canonical_persistence: bool = False,
    ) -> CompletionAssessment:
        reasons: List[str] = []
        needs_recovery = False
        ledger_corrupt = False

        ws_root = expected_workspace or (state.workspace if state else "") or (state.workspace_identity if state else "") or ""

        # Part I: Completion evaluator must load canonical state itself.
        # It must not trust a caller-supplied VerifiedProjectState as authoritative.
        canonical_state: Optional[VerifiedProjectState] = None
        canonical_persistence_consistent = True

        ledger_exists = False
        latest_ledger_mutation_ts: Optional[str] = None
        if ws_root and os.path.exists(ws_root):
            ledger_file = os.path.join(ws_root, ".sclass", "trust", "assurance_ledger.jsonl")
            ledger_exists = os.path.exists(ledger_file)
            if ledger_exists:
                try:
                    import json
                    entries = []
                    with open(ledger_file, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.strip():
                                e = json.loads(line.strip())
                                entries.append(e)
                                etype = e.get("entry_type", "")
                                p = e.get("payload", {})
                                if etype in ("obligation", "action", "mutation", "tool_execution"):
                                    ts = p.get("updated_at") or e.get("timestamp")
                                    if ts and (not latest_ledger_mutation_ts or ts > latest_ledger_mutation_ts):
                                        latest_ledger_mutation_ts = ts
                    from sclass.trust.state_reducer import CanonicalStateReducer
                    req_auth = require_canonical_persistence or (
                        os.environ.get("SCLASS_STRICT_SECURITY") == "1"
                        or os.environ.get("SCLASS_ENVIRONMENT") == "production"
                    )
                    CanonicalStateReducer.validate_history_consistency(entries, require_authentication=req_auth)
                    canonical_state = CanonicalStateReducer.reduce(entries, workspace_dir=ws_root, require_authentication=req_auth)
                except Exception as e:
                    canonical_persistence_consistent = False
                    ledger_corrupt = True
                    reasons.append(f"Canonical persistence consistency check failed: {e}")
            elif require_canonical_persistence or (expected_workspace and os.path.exists(os.path.join(ws_root, ".sclass", "trust"))):
                canonical_persistence_consistent = False
                reasons.append(f"Authoritative assurance ledger missing at '{ledger_file}'")
        elif require_canonical_persistence:
            canonical_persistence_consistent = False
            reasons.append(f"Workspace root '{ws_root}' does not exist or lacks canonical assurance ledger")

        # Reconcile caller state vs canonical state
        eval_state: VerifiedProjectState
        if canonical_state is not None:
            if state is not None:
                # Reconcile: caller-supplied state cannot forge claims or suppress regressions
                caller_cids = {c.get("claim_id") or c.get("id") for c in state.verified_claims}
                canonical_cids = {c.get("claim_id") or c.get("id") for c in canonical_state.verified_claims}
                unbacked_cids = caller_cids - canonical_cids
                if unbacked_cids:
                    canonical_persistence_consistent = False
                    reasons.append(
                        f"Caller-supplied state contains unbacked claims not present in canonical persistence: {sorted(list(unbacked_cids))}"
                    )
                    needs_recovery = True

                caller_reg = {r.get("regression_id") or r.get("id") for r in state.active_regressions if not r.get("resolved", False)}
                canonical_reg = {r.get("regression_id") or r.get("id") for r in canonical_state.active_regressions if not r.get("resolved", False)}
                suppressed_reg = canonical_reg - caller_reg
                if suppressed_reg:
                    canonical_persistence_consistent = False
                    reasons.append(
                        f"Caller-supplied state suppressed active regressions present in canonical persistence: {sorted(list(suppressed_reg))}"
                    )
                    needs_recovery = True

            eval_state = canonical_state
        else:
            if require_canonical_persistence:
                canonical_persistence_consistent = False
                reasons.append("Canonical persistence is required but no valid canonical state exists on disk")
            eval_state = state or VerifiedProjectState(workspace=ws_root)

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
                c for c in eval_state.verified_claims
                if (c.get("task_id") == task_id or not c.get("task_id"))
            ]
            if not task_verified_claims and task_id not in eval_state.verified_tasks:
                obs_satisfied = False
                reasons.append(f"No technical obligations or verified claims exist for task '{task_id}'")

        # 2. Required Claims Verified Check
        verified_cids = {
            c.get("claim_id") or c.get("id")
            for c in eval_state.verified_claims
            if (c.get("task_id") == task_id or not c.get("task_id"))
        }
        invalidated_cids = {
            c.get("claim_id") or c.get("id")
            for c in eval_state.invalidated_claims
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
            c for c in eval_state.verified_claims
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
        effective_boundary_ts = mutation_boundary_timestamp or latest_ledger_mutation_ts
        if effective_boundary_ts and eval_state.evidence:
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
                ev for ev in eval_state.evidence
                if (ev.get("receipt_id") in task_receipt_ids or ev.get("id") in task_receipt_ids
                    or ev.get("task_id") == task_id or not task_receipt_ids)
            ]
            boundary_dt = _parse_iso_utc(effective_boundary_ts)
            for ev in target_evidence:
                ev_ts = ev.get("timestamp") or ev.get("created_at")
                if ev_ts:
                    ev_dt = _parse_iso_utc(ev_ts)
                    if ev_dt < boundary_dt:
                        evidence_fresh = False
                        reasons.append(f"Evidence '{ev.get('receipt_id')}' timestamp {ev_ts} is older than mutation boundary {effective_boundary_ts}")
                        needs_recovery = True
                        break

        # 4. Clean Frontier Check
        frontier_resolved = True
        if eval_state.frontier:
            unresolved_frontier = [
                f for f in eval_state.frontier
                if f.get("status") not in ("VERIFIED", "SATISFIED", "RESOLVED")
            ]
            if unresolved_frontier:
                frontier_resolved = False
                reasons.append(f"Verification frontier contains {len(unresolved_frontier)} unresolved items")

        # 5. Regression Checks
        regressions_satisfied = True
        if eval_state.active_regressions:
            unresolved_regressions = [
                r for r in eval_state.active_regressions
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
            state_ws = eval_state.workspace or eval_state.workspace_identity or ""
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
            and canonical_persistence_consistent
        )

        if require_canonical_persistence and not ledger_exists:
            verdict = CompletionVerdict.UNAVAILABLE
        elif all_passed:
            verdict = CompletionVerdict.ACCEPT
            reasons = ["All canonical technical obligations, evidence, claims, regressions, and persistence satisfied."]
        elif ledger_corrupt:
            verdict = CompletionVerdict.CORRUPT
        elif needs_recovery:
            verdict = CompletionVerdict.RECOVER
        elif not canonical_persistence_consistent:
            verdict = CompletionVerdict.BLOCK
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
            canonical_persistence_consistent=canonical_persistence_consistent,
            reasons=reasons,
            details={
                "task_id": task_id,
                "obligations_count": len(task_obligations),
                "verified_claims_count": len(verified_cids),
                "invalidated_claims_count": len(invalidated_cids),
            },
        )
