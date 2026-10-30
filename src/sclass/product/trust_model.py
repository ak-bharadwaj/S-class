"""S-Class Product Layer Trust Model for Agent-Authored Content.

Implements R30 Section F3: Trust Model for Agent-Authored Content:
- PD-F3-001 (Class M): Agent-authored content is candidate claim/provenance,
  not proof, and must not self-authenticate.
- PD-F3-002 (Class M): Gate authority must come from evaluator-produced check
  records bound to the canonical object and target.
- PD-F3-003 (Class M): Conflicting structured representations must be detected
  without using explanatory prose as a mechanical comparison operand.
- PD-F3-004 (Class E): Requirement confirmation must be a REQUIREMENT_CONFIRMED
  USER/POLICY event whose Requirement.source_provenance equals the digest of
  the canonical structured form; design confirmations must be Decision outcomes;
  ApprovalRecord/ConfirmationScope must be reserved for governance approvals.
- PD-F3-005 (Class E): The evaluator must recompute content_digest; a claimed
  digest that differs from the recomputed digest is invalid.
- PD-F3-006 (Class M): Human confirmation is admissible only from an
  S-Class-controlled or host-native rendering surface; agent-relayed text is
  inadmissible; signing principal key must be unreachable from the agent;
  no agent-callable tool may create or forward an approval; key custody
  requires user presence.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import enum
import hashlib
from typing import Any, Dict, List, Optional, Union

from sclass import (
    ApprovalRecord,
    Authority,
    EventType,
    canonical_c1,
)
from sclass.product.artifacts import (
    ArtifactType,
    c1_canonical_encode,
    compute_content_digest,
    freeze_to_c1_compatible,
)


# -----------------------------------------------------------------------------
# 1. Authoritative F5 Gate State Vocabulary & Gate Output
# -----------------------------------------------------------------------------

class GateState(str, enum.Enum):
    """Authoritative F5 Gate State Vocabulary."""
    SATISFIED = "SATISFIED"
    MISSING = "MISSING"
    BLOCKED_ON_HUMAN = "BLOCKED_ON_HUMAN"


@dataclass(frozen=True)
class GateOutput:
    """F5 Gate Output structure compliant with gate_output.json schema."""
    state: GateState
    must_id: Optional[str] = None
    detail: Optional[str] = None
    failures: List[str] = field(default_factory=list)
    explain: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        if self.state == GateState.SATISFIED:
            return "SATISFIED"
        if self.must_id:
            return f"{self.state.value}[{self.must_id}]"
        return self.state.value

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str):
            return str(self) == other
        if isinstance(other, GateOutput):
            return self.state == other.state and self.must_id == other.must_id
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Serializes to dictionary conforming to gate_output.json schema."""
        fails = list(self.failures)
        if not fails and self.must_id:
            fails.append(str(self))
        exp = dict(self.explain)
        if self.detail and "detail" not in exp:
            exp["detail"] = self.detail
        return {
            "state": self.state.value,
            "failures": fails,
            "explain": exp,
        }


# -----------------------------------------------------------------------------
# 2. Check Records and Confirmation Scope
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class CheckRecord:
    """Evaluator-produced check record conferring gate authority."""
    check_id: str
    producer: str
    status: str = "PASS"
    object_digest: Optional[str] = None
    target_digest: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "check_id": self.check_id,
            "producer": self.producer,
            "status": self.status,
        }
        if self.object_digest is not None:
            d["object_digest"] = self.object_digest
        if self.target_digest is not None:
            d["target_digest"] = self.target_digest
        if self.details is not None:
            d["details"] = self.details
        return d


@dataclass(frozen=True)
class ConfirmationScope:
    """Product-layer ConfirmationScope object for governance approvals.

    Stored in ApprovalRecord.scope_digest via sha256(canonical_c1(scope)).
    Reserved strictly for governance approvals (WAIVER, WEAKENING, ADAPTER_CHANGE);
    never used for requirement confirmation.
    """
    objective_revision: str
    artifact_type: Union[str, ArtifactType]
    obligation_ref: Optional[str] = None
    decision_ref: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        type_str = self.artifact_type.value if hasattr(self.artifact_type, "value") else str(self.artifact_type)
        d: Dict[str, Any] = {
            "artifact_type": type_str,
            "objective_revision": self.objective_revision,
        }
        if self.obligation_ref is not None:
            d["obligation_ref"] = self.obligation_ref
        if self.decision_ref is not None:
            d["decision_ref"] = self.decision_ref
        return d

    def canonical_bytes(self) -> bytes:
        return c1_canonical_encode(self.to_dict())

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


# -----------------------------------------------------------------------------
# 3. Core F3 Evaluation Gates
# -----------------------------------------------------------------------------

def evaluate_claim(
    candidate: Mapping[str, Any],
    evaluator_check_records: Sequence[Any] | None = None,
    expected_object_digest: Optional[str] = None,
    expected_target_digest: Optional[str] = None,
) -> GateOutput:
    """Evaluates agent candidate claims against authoritative evaluator check records.

    Enforces:
    - PD-F3-001: Agent claims cannot self-authenticate.
    - PD-F3-002: Gate authority must come from evaluator-produced check records.
    """
    if evaluator_check_records is None:
        evaluator_check_records = []

    # Detect if candidate attempts to supply check records as authority
    candidate_check_records = candidate.get("check_records")
    has_agent_check_records = False
    if candidate_check_records:
        has_agent_check_records = any(
            (isinstance(r, Mapping) and r.get("producer") == "agent" and r.get("status") == "PASS")
            or (isinstance(r, CheckRecord) and r.producer == "agent" and r.status == "PASS")
            for r in candidate_check_records
        )

    # Validate evaluator check records
    valid_evaluator_records: List[Any] = []
    for r in evaluator_check_records:
        rec_producer = r.get("producer") if isinstance(r, Mapping) else getattr(r, "producer", None)
        rec_status = r.get("status") if isinstance(r, Mapping) else getattr(r, "status", None)
        rec_obj = r.get("object_digest") if isinstance(r, Mapping) else getattr(r, "object_digest", None)
        rec_tgt = r.get("target_digest") if isinstance(r, Mapping) else getattr(r, "target_digest", None)

        # Agent cannot author evaluator check records
        if rec_producer == "evaluator" and rec_status == "PASS":
            if expected_object_digest is not None and rec_obj != expected_object_digest:
                continue
            if expected_target_digest is not None and rec_tgt != expected_target_digest:
                continue
            valid_evaluator_records.append(r)

    if not valid_evaluator_records:
        if has_agent_check_records:
            return GateOutput(
                GateState.MISSING,
                must_id="PD-F3-002",
                detail="Gate authority must come from evaluator check records, not agent-authored check records",
                failures=["MISSING[PD-F3-002]"],
                explain={"reason": "agent_supplied_check_records_have_no_authority"},
            )
        return GateOutput(
            GateState.MISSING,
            must_id="PD-F3-001",
            detail="Agent candidate claim cannot self-authenticate without valid evaluator check records",
            failures=["MISSING[PD-F3-001]"],
            explain={"reason": "candidate_verified_claim_unsupported_by_evaluator"},
        )

    return GateOutput(
        GateState.SATISFIED,
        explain={"evaluator_check_records_count": len(valid_evaluator_records)},
    )


def check_structured_conflict(
    structured_a: Any,
    structured_b: Any,
    prose: Any = None,  # Strictly ignored: prose is never a mechanical comparison operand
) -> GateOutput:
    """Detects conflicting structured representations without comparing prose mechanically.

    Enforces PD-F3-003: Conflicting structured representations MUST be detected
    without using explanatory prose as a mechanical comparison operand.
    """
    # Exclude prose from comparison completely
    norm_a = freeze_to_c1_compatible(structured_a)
    norm_b = freeze_to_c1_compatible(structured_b)

    if norm_a != norm_b:
        return GateOutput(
            GateState.BLOCKED_ON_HUMAN,
            must_id="PD-F3-003",
            detail="Conflicting structured representations detected; human resolution required",
            failures=["BLOCKED_ON_HUMAN[PD-F3-003]"],
            explain={
                "reason": "structured_representation_mismatch",
                "prose_mechanically_compared": False,
            },
        )

    return GateOutput(
        GateState.SATISFIED,
        explain={"prose_mechanically_compared": False},
    )


def evaluate_requirement_confirmation(
    confirmation_event: Mapping[str, Any] | Any,
    canonical_structured_form: Any = None,
    canonical_structured_form_digest: Optional[str] = None,
) -> GateOutput:
    """Evaluates requirement confirmation against canonical structured form digest.

    Enforces PD-F3-004:
    - Must be a REQUIREMENT_CONFIRMED USER/POLICY event.
    - Requirement.source_provenance must equal canonical structured form digest.
    - ApprovalRecord/ConfirmationScope is strictly for governance approvals.
    """
    # If passed as an ApprovalRecord, reject as requirement confirmation
    if isinstance(confirmation_event, ApprovalRecord) or (
        isinstance(confirmation_event, Mapping) and "approval_id" in confirmation_event
    ):
        return GateOutput(
            GateState.BLOCKED_ON_HUMAN,
            must_id="PD-F3-004",
            detail="ApprovalRecord is reserved for governance approvals, not requirement confirmation",
            failures=["BLOCKED_ON_HUMAN[PD-F3-004]"],
            explain={"reason": "approval_record_used_for_requirement_confirmation"},
        )

    # Extract event attributes
    if isinstance(confirmation_event, Mapping):
        event_type = confirmation_event.get("event_type")
        authority = confirmation_event.get("authority")
        source_provenance = confirmation_event.get("source_provenance")
        ev_expected_digest = confirmation_event.get("canonical_structured_form_digest")
    else:
        event_type = getattr(confirmation_event, "event_type", None)
        authority = getattr(confirmation_event, "authority", None)
        source_provenance = getattr(confirmation_event, "source_provenance", None)
        ev_expected_digest = getattr(confirmation_event, "canonical_structured_form_digest", None)

    # Verify event type
    valid_event_types = {"REQUIREMENT_CONFIRMED", EventType.REQUIREMENT_CONFIRMED.value}
    if event_type not in valid_event_types and getattr(event_type, "value", None) not in valid_event_types:
        return GateOutput(
            GateState.BLOCKED_ON_HUMAN,
            must_id="PD-F3-004",
            detail=f"Requirement confirmation event type must be REQUIREMENT_CONFIRMED, got {event_type}",
            failures=["BLOCKED_ON_HUMAN[PD-F3-004]"],
            explain={"reason": "invalid_event_type", "event_type": str(event_type)},
        )

    # Verify authority
    valid_authorities = {"USER", "POLICY", Authority.USER.name, Authority.POLICY.name}
    auth_str = getattr(authority, "name", str(authority))
    if auth_str not in valid_authorities:
        return GateOutput(
            GateState.BLOCKED_ON_HUMAN,
            must_id="PD-F3-004",
            detail=f"Requirement confirmation authority must be USER or POLICY, got {authority}",
            failures=["BLOCKED_ON_HUMAN[PD-F3-004]"],
            explain={"reason": "invalid_authority", "authority": str(authority)},
        )

    # Compute or determine canonical structured form digest
    target_digest = canonical_structured_form_digest or ev_expected_digest
    if target_digest is None and canonical_structured_form is not None:
        if isinstance(canonical_structured_form, Mapping):
            target_digest = compute_content_digest(canonical_structured_form)
        else:
            raw = c1_canonical_encode(canonical_structured_form)
            target_digest = hashlib.sha256(raw).hexdigest()

    # Verify digest equality: changed digest requires human reconfirmation
    if target_digest is not None and source_provenance != target_digest:
        return GateOutput(
            GateState.BLOCKED_ON_HUMAN,
            must_id="PD-F3-004",
            detail=(
                f"Canonical structured form digest changed ({source_provenance} != {target_digest}); "
                "reconfirmation requires a human"
            ),
            failures=["BLOCKED_ON_HUMAN[PD-F3-004]"],
            explain={
                "reason": "canonical_digest_mismatch_requires_reconfirmation",
                "source_provenance": source_provenance,
                "canonical_structured_form_digest": target_digest,
            },
        )

    return GateOutput(
        GateState.SATISFIED,
        explain={
            "source_provenance": source_provenance,
            "canonical_structured_form_digest": target_digest,
        },
    )


def verify_content_digest(
    claimed_content_digest: str,
    recomputed_or_artifact: Any,
) -> GateOutput:
    """Verifies that claimed content digest matches recomputed content digest.

    Enforces PD-F3-005: Evaluator must recompute content_digest; a claimed
    digest differing from recomputed digest is invalid.
    """
    if isinstance(recomputed_or_artifact, str):
        recomputed_digest = recomputed_or_artifact
    elif isinstance(recomputed_or_artifact, Mapping):
        recomputed_digest = compute_content_digest(recomputed_or_artifact)
    else:
        raw = c1_canonical_encode(recomputed_or_artifact)
        recomputed_digest = hashlib.sha256(raw).hexdigest()

    if claimed_content_digest != recomputed_digest:
        return GateOutput(
            GateState.MISSING,
            must_id="PD-F3-005",
            detail=(
                f"Claimed content digest {claimed_content_digest} differs from "
                f"recomputed digest {recomputed_digest}"
            ),
            failures=["MISSING[PD-F3-005]"],
            explain={
                "reason": "content_digest_mismatch",
                "claimed_content_digest": claimed_content_digest,
                "recomputed_content_digest": recomputed_digest,
            },
        )

    return GateOutput(
        GateState.SATISFIED,
        explain={"content_digest": claimed_content_digest},
    )


def evaluate_confirmation_admissibility(
    confirmation_surface: str,
    principal_key_accessible_to_agent: bool = False,
    approval_forwarding_tool_available: bool = False,
    user_presence_required: bool = True,
) -> GateOutput:
    """Evaluates admissibility of human confirmation surface and signing key custody.

    Enforces PD-F3-006:
    - Admissible only from S-Class controlled or host-native surface.
    - Agent-relayed text is inadmissible.
    - Signing key must be unreachable from agent.
    - No agent-callable tool may create or forward an approval.
    - Key custody requires user presence in separate OS principal or hardware store.
    """
    inadmissible_surfaces = {
        "agent_facing_tool",
        "agent_relayed",
        "agent",
        "chat_relay",
        "untrusted",
        "agent_tool",
    }

    if confirmation_surface in inadmissible_surfaces:
        return GateOutput(
            GateState.BLOCKED_ON_HUMAN,
            must_id="PD-F3-006",
            detail=f"Confirmation surface '{confirmation_surface}' is agent-facing or untrusted",
            failures=["BLOCKED_ON_HUMAN[PD-F3-006]"],
            explain={"reason": "inadmissible_confirmation_surface", "confirmation_surface": confirmation_surface},
        )

    if principal_key_accessible_to_agent:
        return GateOutput(
            GateState.BLOCKED_ON_HUMAN,
            must_id="PD-F3-006",
            detail="Principal key is accessible to agent; approval inadmissible",
            failures=["BLOCKED_ON_HUMAN[PD-F3-006]"],
            explain={"reason": "principal_key_accessible_to_agent"},
        )

    if approval_forwarding_tool_available:
        return GateOutput(
            GateState.BLOCKED_ON_HUMAN,
            must_id="PD-F3-006",
            detail="Approval creation or forwarding tool is available to agent; approval inadmissible",
            failures=["BLOCKED_ON_HUMAN[PD-F3-006]"],
            explain={"reason": "approval_forwarding_tool_available"},
        )

    if not user_presence_required:
        return GateOutput(
            GateState.BLOCKED_ON_HUMAN,
            must_id="PD-F3-006",
            detail="User presence is not required for signing key custody; approval inadmissible",
            failures=["BLOCKED_ON_HUMAN[PD-F3-006]"],
            explain={"reason": "user_presence_not_required"},
        )

    return GateOutput(
        GateState.SATISFIED,
        explain={
            "confirmation_surface": confirmation_surface,
            "key_custody_verified": True,
        },
    )


def evaluate_f3_trust(spec: Mapping[str, Any]) -> GateOutput:
    """Unified evaluator for R30 Section F3 fixtures and specifications.

    Dispatches to specific F3 gate evaluations based on input fields.
    """
    # 1. PD-F3-006: Confirmation surface and key custody
    if "confirmation_surface" in spec:
        return evaluate_confirmation_admissibility(
            confirmation_surface=spec["confirmation_surface"],
            principal_key_accessible_to_agent=spec.get("principal_key_accessible_to_agent", False),
            approval_forwarding_tool_available=spec.get("approval_forwarding_tool_available", False),
            user_presence_required=spec.get("user_presence_required", True),
        )

    # 2. PD-F3-005: Content digest verification
    if "claimed_content_digest" in spec or "claimed_digest" in spec:
        claimed = spec.get("claimed_content_digest") or spec.get("claimed_digest")
        recomputed = (
            spec.get("recomputed_content_digest")
            or spec.get("recomputed_digest")
            or spec.get("artifact")
        )
        return verify_content_digest(claimed, recomputed)

    # 3. PD-F3-004: Requirement confirmation
    if "requirement_confirmation" in spec:
        return evaluate_requirement_confirmation(
            confirmation_event=spec["requirement_confirmation"],
            canonical_structured_form=spec.get("canonical_structured_form"),
            canonical_structured_form_digest=spec.get("canonical_structured_form_digest"),
        )

    # 4. PD-F3-003: Structured conflict detection
    if "structured_a" in spec and "structured_b" in spec:
        return check_structured_conflict(
            structured_a=spec["structured_a"],
            structured_b=spec["structured_b"],
            prose=spec.get("prose"),
        )

    # 5. PD-F3-001 / PD-F3-002: Candidate claims vs evaluator check records
    if "candidate" in spec:
        return evaluate_claim(
            candidate=spec["candidate"],
            evaluator_check_records=spec.get("evaluator_check_records"),
            expected_object_digest=spec.get("expected_object_digest"),
            expected_target_digest=spec.get("expected_target_digest"),
        )

    # If must_id specified but inputs missing, fail closed with MISSING
    must_id = spec.get("must_id")
    if must_id:
        return GateOutput(GateState.MISSING, must_id=must_id, detail=f"Incomplete input specification for {must_id}")

    return GateOutput(GateState.MISSING, detail="Unrecognized F3 trust specification inputs")
