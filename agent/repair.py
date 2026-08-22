"""
S-Class EOS V11.2 - D7/D8 Repair Feedback Builder (Bridge 3).
Transforms D4 AssessmentReceipt refutations and ClaimReductionState contradictions
into structured repair context and prompt payloads for iterative model correction.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from domain.models import AssessmentReceipt, Evidence
from domain.types import AssessmentVerdict
from claim.reducer import ClaimReductionState, ClaimEpistemicState


@dataclass(frozen=True)
class RepairFeedbackPayload:
    """Immutable structured feedback for driving iterative repair cycles."""
    obligation_id: str
    verdict: AssessmentVerdict
    is_rejected: bool
    refuted_claim_ids: Tuple[str, ...]
    contradicted_aspects: Tuple[str, ...]
    failure_diagnostics: Tuple[str, ...]
    suggested_repair_prompt: str
    fencing_token_advance: int = 1
    state_version_advance: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "obligation_id": self.obligation_id,
            "verdict": self.verdict.value,
            "is_rejected": self.is_rejected,
            "refuted_claim_ids": list(self.refuted_claim_ids),
            "contradicted_aspects": list(self.contradicted_aspects),
            "failure_diagnostics": list(self.failure_diagnostics),
            "suggested_repair_prompt": self.suggested_repair_prompt,
            "fencing_token_advance": self.fencing_token_advance,
            "state_version_advance": self.state_version_advance,
        }


class RepairFeedbackBuilder:
    """Builds structured repair feedback from D4 assessment receipts and epistemic claim states."""

    @classmethod
    def build_repair_feedback(
        cls,
        receipt: AssessmentReceipt,
        claim_states: Mapping[str, ClaimReductionState],
        evidence_items: Sequence[Evidence],
        current_code: Optional[str] = None,
        max_diag_lines: int = 20,
    ) -> RepairFeedbackPayload:
        """Extracts failure lineage from refuting evidence and constructs a bounded repair context."""
        if not isinstance(receipt, AssessmentReceipt):
            raise TypeError("receipt must be an AssessmentReceipt instance.")
        if not receipt.signature or not receipt.signature.signature_hex:
            raise ValueError("AssessmentReceipt signature is missing or unverified.")

        is_rejected = receipt.verdict == AssessmentVerdict.REJECTED
        refuted_claims: List[str] = []
        contradicted_aspects: List[str] = []
        failure_diagnostics: List[str] = []

        # Map evidence by ID, filtering for authentic, valid evidence
        from domain.types import EvidenceValidity
        ev_by_id = {
            ev.evidence_id: ev for ev in evidence_items
            if isinstance(ev, Evidence) and ev.validity == EvidenceValidity.VALID and ev.signature and ev.signature.raw_stdout_digest
        }

        for cid, state in claim_states.items():
            if state.epistemic_state in (ClaimEpistemicState.CONTRADICTED, ClaimEpistemicState.CONFLICTED):
                refuted_claims.append(cid)
                for aspect in state.missing_aspects:
                    contradicted_aspects.append(aspect)

                # Extract diagnostics from refuting evidence
                for ev_id in state.refuting_evidence_ids:
                    if ev_id in ev_by_id:
                        ev = ev_by_id[ev_id]
                        for d in ev.observation.diagnostics:
                            failure_diagnostics.append(str(d))

        # Deduplicate and bound diagnostics
        unique_diags = list(dict.fromkeys(failure_diagnostics))[:max_diag_lines]

        # Construct prompt
        lines = [
            "### S-Class Governed Verification Failure Feedback",
            f"Assessment Verdict: {receipt.verdict.value} for Obligation: {receipt.obligation_id}",
            f"Contradicted Claims: {', '.join(refuted_claims) if refuted_claims else 'None'}",
            "",
            "Execution Failure Diagnostics:",
        ]
        if unique_diags:
            for d in unique_diags:
                lines.append(f"  - {d}")
        else:
            lines.append("  - Verification tests failed or invariants contradicted.")

        if current_code:
            lines.extend([
                "",
                "Current Implementation:",
                "```python",
                current_code.strip(),
                "```",
            ])

        lines.extend([
            "",
            "Analyze the failure diagnostics, identify the broken invariant, and provide a corrected code implementation."
        ])

        return RepairFeedbackPayload(
            obligation_id=receipt.obligation_id,
            verdict=receipt.verdict,
            is_rejected=is_rejected,
            refuted_claim_ids=tuple(refuted_claims),
            contradicted_aspects=tuple(contradicted_aspects),
            failure_diagnostics=tuple(unique_diags),
            suggested_repair_prompt="\n".join(lines),
            fencing_token_advance=1,
            state_version_advance=1,
        )
