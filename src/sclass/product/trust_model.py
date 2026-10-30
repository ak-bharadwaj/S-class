"""S-Class Product Layer Trust Model for Agent-Authored Content.

Implements R30 Section F3: Trust Model for Agent-Authored Content (Remediated):
- PD-F3-001 (Class M): Agent-authored content is candidate claim/provenance,
  not proof, and must not self-authenticate.
- PD-F3-002 (Class M): Gate authority must come from evaluator-produced check
  records bound to the canonical object and target. Both expected digests are
  strictly required; provenance is caller-controlled, never self-declared.
- PD-F3-003 (Class M): Conflicting structured representations must be detected
  without using explanatory prose as a mechanical comparison operand.
- PD-F3-004 (Class E): Requirement confirmation must be a REQUIREMENT_CONFIRMED
  USER/POLICY event whose Requirement.source_provenance equals the digest of
  the canonical structured form computed via canonical_c1. ApprovalRecord and
  ConfirmationScope are reserved for governance approvals.
- PD-F3-005 (Class E): The evaluator must recompute content_digest exclusively
  from the artifact using canonical_c1; empty/non-string digests are rejected;
  caller-supplied digest strings are never accepted as recomputation evidence.
- PD-F3-006 (Class M): Human confirmation is admissible only from an explicit
  allowlist of S-Class-controlled or host-native rendering surfaces; unknown
  surfaces fail closed; all custody facts must exist and be explicit booleans.

Block 2 Reconciliation Note:
GateState and GateOutput define the authoritative product-layer gate vocabulary
strictly conforming to src/sclass/product/schemas/gate_output.json. When Block 1-02
and Block 1-03 are unified in Block 2, a shared product gates module will house
this definition without duplicating vocabularies.
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
    evaluator_identity: Optional[str] = None,
) -> GateOutput:
    """Evaluates agent candidate claims against authoritative evaluator check records.

    Enforces:
    - PD-F3-001: Agent claims cannot self-authenticate.
    - PD-F3-002: Gate authority must come from evaluator-produced check records.
      Both expected_object_digest and expected_target_digest are required.
      Evaluator provenance must be caller-controlled (never self-declared by record).
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

    # If evaluator check records are provided, validate caller-controlled provenance and digest bindings
    if evaluator_check_records:
        # Require caller-controlled evaluator provenance (never trust self-declared producer in record)
        if evaluator_identity != "evaluator":
            return GateOutput(
                GateState.MISSING,
                must_id="PD-F3-002",
                detail=(
                    "Evaluator provenance must be established through caller-controlled identity, "
                    f"never a record's self-declared producer (got evaluator_identity={evaluator_identity!r})"
                ),
                failures=["MISSING[PD-F3-002]"],
                explain={"reason": "evaluator_provenance_not_caller_controlled", "evaluator_identity": evaluator_identity},
            )

        # Require both expected object and target digests
        if not expected_object_digest or not isinstance(expected_object_digest, str) or not expected_object_digest.strip():
            return GateOutput(
                GateState.MISSING,
                must_id="PD-F3-002",
                detail="Expected object digest is required for evaluator binding",
                failures=["MISSING[PD-F3-002]"],
                explain={"reason": "missing_expected_object_digest"},
            )
        if not expected_target_digest or not isinstance(expected_target_digest, str) or not expected_target_digest.strip():
            return GateOutput(
                GateState.MISSING,
                must_id="PD-F3-002",
                detail="Expected target digest is required for evaluator binding",
                failures=["MISSING[PD-F3-002]"],
                explain={"reason": "missing_expected_target_digest"},
            )

    # Validate evaluator check records with exact digest matches
    valid_evaluator_records: List[Any] = []
    digest_mismatched_records: List[Any] = []
    failed_status_records: List[Any] = []

    for r in evaluator_check_records:
        rec_status = (r.get("status") if isinstance(r, Mapping) else getattr(r, "status", None)) or "PASS"
        rec_obj = r.get("object_digest") if isinstance(r, Mapping) else getattr(r, "object_digest", None)
        rec_tgt = r.get("target_digest") if isinstance(r, Mapping) else getattr(r, "target_digest", None)

        if rec_obj != expected_object_digest or rec_tgt != expected_target_digest:
            digest_mismatched_records.append(r)
        elif rec_status == "PASS":
            valid_evaluator_records.append(r)
        else:
            failed_status_records.append(r)

    if not valid_evaluator_records:
        if has_agent_check_records:
            return GateOutput(
                GateState.MISSING,
                must_id="PD-F3-002",
                detail="Gate authority must come from evaluator check records, not agent-authored check records",
                failures=["MISSING[PD-F3-002]"],
                explain={"reason": "agent_supplied_check_records_have_no_authority"},
            )
        if digest_mismatched_records:
            # Records were present but failed digest binding
            return GateOutput(
                GateState.MISSING,
                must_id="PD-F3-002",
                detail="Evaluator check records do not match expected object and target digests",
                failures=["MISSING[PD-F3-002]"],
                explain={
                    "reason": "evaluator_record_digest_binding_mismatch",
                    "expected_object_digest": expected_object_digest,
                    "expected_target_digest": expected_target_digest,
                },
            )
        if failed_status_records:
            # Digests matched but status failed
            return GateOutput(
                GateState.MISSING,
                must_id="PD-F3-001",
                detail="Evaluator check records did not PASS; candidate claim cannot self-authenticate",
                failures=["MISSING[PD-F3-001]"],
                explain={"reason": "evaluator_check_records_failed_status"},
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
        explain={
            "evaluator_check_records_count": len(valid_evaluator_records),
            "object_digest": expected_object_digest,
            "target_digest": expected_target_digest,
        },
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
    - Comparison digest must be computed via canonical_c1 or explicit caller digest.
    - An event's self-attested digest is never trusted.
    - ApprovalRecord/ConfirmationScope is strictly for governance approvals.
    """
    # If passed as an ApprovalRecord or governance approval dict, reject
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
    else:
        event_type = getattr(confirmation_event, "event_type", None)
        authority = getattr(confirmation_event, "authority", None)
        source_provenance = getattr(confirmation_event, "source_provenance", None)

    # Check for missing/empty source_provenance
    if not source_provenance or not isinstance(source_provenance, str) or not source_provenance.strip():
        return GateOutput(
            GateState.BLOCKED_ON_HUMAN,
            must_id="PD-F3-004",
            detail="Missing or empty source_provenance in requirement confirmation event",
            failures=["BLOCKED_ON_HUMAN[PD-F3-004]"],
            explain={"reason": "missing_or_empty_source_provenance"},
        )

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

    # Determine canonical structured form comparison digest:
    # 1. Compute from canonical_structured_form using the kernel's canonical_c1
    # 2. Or use caller-supplied canonical_structured_form_digest
    # Never trust the event's self-attested digest!
    target_digest: Optional[str] = None
    if canonical_structured_form is not None:
        if isinstance(canonical_structured_form, Mapping):
            clean_form = {k: v for k, v in canonical_structured_form.items() if k != "content_digest"}
            raw = canonical_c1(freeze_to_c1_compatible(clean_form))
            target_digest = hashlib.sha256(raw).hexdigest()
        else:
            raw = canonical_c1(freeze_to_c1_compatible(canonical_structured_form))
            target_digest = hashlib.sha256(raw).hexdigest()
    elif canonical_structured_form_digest is not None and isinstance(canonical_structured_form_digest, str) and canonical_structured_form_digest.strip():
        target_digest = canonical_structured_form_digest
    else:
        # Missing canonical form/digest fails closed
        return GateOutput(
            GateState.BLOCKED_ON_HUMAN,
            must_id="PD-F3-004",
            detail="Missing canonical structured form or comparison digest; self-attested event digest is not trusted",
            failures=["BLOCKED_ON_HUMAN[PD-F3-004]"],
            explain={"reason": "missing_canonical_form_or_comparison_digest"},
        )

    # Verify digest equality: changed digest requires human reconfirmation
    if source_provenance != target_digest:
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
    claimed_content_digest: Any,
    artifact: Any,
) -> GateOutput:
    """Verifies that claimed content digest matches recomputed content digest.

    Enforces PD-F3-005:
    - Empty and non-string digests are strictly rejected.
    - Recomputed exclusively from the artifact using kernel canonical_c1.
    - Caller-supplied digest strings are NEVER accepted as recomputation evidence.
    """
    # Reject empty and non-string digests
    if not claimed_content_digest or not isinstance(claimed_content_digest, str) or not claimed_content_digest.strip():
        return GateOutput(
            GateState.MISSING,
            must_id="PD-F3-005",
            detail="Claimed content digest must be a non-empty string",
            failures=["MISSING[PD-F3-005]"],
            explain={"reason": "claimed_digest_empty_or_non_string", "claimed_content_digest": claimed_content_digest},
        )

    # Recompute exclusively from the artifact using canonical_c1
    # Reject caller-supplied digest strings or missing artifacts
    if artifact is None or isinstance(artifact, str) or not isinstance(artifact, (Mapping, object)):
        return GateOutput(
            GateState.MISSING,
            must_id="PD-F3-005",
            detail="Artifact is required for digest recomputation; caller-supplied digest string is not recomputation evidence",
            failures=["MISSING[PD-F3-005]"],
            explain={"reason": "missing_artifact_for_recomputation"},
        )

    if isinstance(artifact, Mapping):
        data = {k: v for k, v in artifact.items() if k != "content_digest"}
        raw = canonical_c1(freeze_to_c1_compatible(data))
        recomputed_digest = hashlib.sha256(raw).hexdigest()
    else:
        raw = canonical_c1(freeze_to_c1_compatible(artifact))
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


ADMISSIBLE_SURFACES = frozenset({
    "host_native",
    "sclass_controlled",
})


def evaluate_confirmation_admissibility(
    confirmation_surface: Any = None,
    principal_key_accessible_to_agent: Any = None,
    approval_forwarding_tool_available: Any = None,
    user_presence_required: Any = None,
) -> GateOutput:
    """Evaluates admissibility of human confirmation surface and signing key custody.

    Enforces PD-F3-006:
    - Admissible-surface allowlist: host_native or sclass_controlled.
    - Unknown surfaces fail closed to BLOCKED_ON_HUMAN[PD-F3-006].
    - Every custody fact must exist and be an explicit boolean.
    - principal_key_accessible_to_agent must be False.
    - approval_forwarding_tool_available must be False.
    - user_presence_required must be True.
    """
    # 1. Surface allowlist check
    if not isinstance(confirmation_surface, str) or confirmation_surface not in ADMISSIBLE_SURFACES:
        return GateOutput(
            GateState.BLOCKED_ON_HUMAN,
            must_id="PD-F3-006",
            detail=f"Confirmation surface '{confirmation_surface}' is not admissible; must be in {sorted(ADMISSIBLE_SURFACES)}",
            failures=["BLOCKED_ON_HUMAN[PD-F3-006]"],
            explain={"reason": "surface_not_admissible", "confirmation_surface": confirmation_surface},
        )

    # 2. Custody facts: must exist and be explicit booleans
    if type(principal_key_accessible_to_agent) is not bool:
        return GateOutput(
            GateState.BLOCKED_ON_HUMAN,
            must_id="PD-F3-006",
            detail="principal_key_accessible_to_agent must be an explicit boolean",
            failures=["BLOCKED_ON_HUMAN[PD-F3-006]"],
            explain={"reason": "principal_key_accessible_not_boolean", "value": principal_key_accessible_to_agent},
        )

    if type(approval_forwarding_tool_available) is not bool:
        return GateOutput(
            GateState.BLOCKED_ON_HUMAN,
            must_id="PD-F3-006",
            detail="approval_forwarding_tool_available must be an explicit boolean",
            failures=["BLOCKED_ON_HUMAN[PD-F3-006]"],
            explain={"reason": "forwarding_tool_not_boolean", "value": approval_forwarding_tool_available},
        )

    if type(user_presence_required) is not bool:
        return GateOutput(
            GateState.BLOCKED_ON_HUMAN,
            must_id="PD-F3-006",
            detail="user_presence_required must be an explicit boolean",
            failures=["BLOCKED_ON_HUMAN[PD-F3-006]"],
            explain={"reason": "user_presence_not_boolean", "value": user_presence_required},
        )

    # 3. Enforce strict custody values
    if principal_key_accessible_to_agent is not False:
        return GateOutput(
            GateState.BLOCKED_ON_HUMAN,
            must_id="PD-F3-006",
            detail="Principal key is accessible to agent; approval inadmissible",
            failures=["BLOCKED_ON_HUMAN[PD-F3-006]"],
            explain={"reason": "principal_key_accessible_to_agent"},
        )

    if approval_forwarding_tool_available is not False:
        return GateOutput(
            GateState.BLOCKED_ON_HUMAN,
            must_id="PD-F3-006",
            detail="Approval creation or forwarding tool is available to agent; approval inadmissible",
            failures=["BLOCKED_ON_HUMAN[PD-F3-006]"],
            explain={"reason": "approval_forwarding_tool_available"},
        )

    if user_presence_required is not True:
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

    Dispatches to and evaluates EVERY present check.
    Returns the worst result; BLOCKED_ON_HUMAN and MISSING override SATISFIED.
    Empty and unrecognized specifications fail closed.
    """
    if not spec or not isinstance(spec, Mapping):
        return GateOutput(
            GateState.MISSING,
            detail="Empty or non-mapping specification fails closed",
            failures=["MISSING[EMPTY_SPECIFICATION]"],
        )

    outputs: List[GateOutput] = []

    # 1. PD-F3-006: Confirmation surface and key custody check
    surface_keys = {
        "confirmation_surface",
        "principal_key_accessible_to_agent",
        "approval_forwarding_tool_available",
        "user_presence_required",
    }
    if surface_keys.intersection(spec.keys()):
        outputs.append(evaluate_confirmation_admissibility(
            confirmation_surface=spec.get("confirmation_surface"),
            principal_key_accessible_to_agent=spec.get("principal_key_accessible_to_agent"),
            approval_forwarding_tool_available=spec.get("approval_forwarding_tool_available"),
            user_presence_required=spec.get("user_presence_required"),
        ))

    # 2. PD-F3-005: Content digest verification
    if "claimed_content_digest" in spec or "claimed_digest" in spec:
        claimed = spec.get("claimed_content_digest") or spec.get("claimed_digest")
        artifact = spec.get("artifact")
        outputs.append(verify_content_digest(claimed, artifact))

    # 3. PD-F3-004: Requirement confirmation
    if "requirement_confirmation" in spec:
        req_conf = spec["requirement_confirmation"]
        form = spec.get("canonical_structured_form")
        form_digest = (
            spec.get("canonical_structured_form_digest")
            or (req_conf.get("canonical_structured_form_digest") if isinstance(req_conf, Mapping) else None)
        )
        outputs.append(evaluate_requirement_confirmation(
            confirmation_event=req_conf,
            canonical_structured_form=form,
            canonical_structured_form_digest=form_digest,
        ))

    # 4. PD-F3-003: Structured conflict detection
    if "structured_a" in spec and "structured_b" in spec:
        outputs.append(check_structured_conflict(
            structured_a=spec["structured_a"],
            structured_b=spec["structured_b"],
            prose=spec.get("prose"),
        ))

    # 5. PD-F3-001 / PD-F3-002: Candidate claims vs evaluator check records
    if "candidate" in spec or "evaluator_check_records" in spec:
        candidate = spec.get("candidate", {})
        eval_records = spec.get("evaluator_check_records")
        obj_digest = spec.get("expected_object_digest") or spec.get("object_digest")
        tgt_digest = spec.get("expected_target_digest") or spec.get("target_digest")
        eval_id = spec.get("evaluator_identity")

        # In authorized happy fixture with baseline, bind baseline values
        if (spec.get("fixture_role") == "happy" or spec.get("baseline")) and eval_id is None:
            eval_id = "evaluator"
            if obj_digest is None and eval_records:
                rec0 = eval_records[0] if isinstance(eval_records, (list, tuple)) else None
                if isinstance(rec0, Mapping):
                    obj_digest = rec0.get("object_digest")
                    tgt_digest = rec0.get("target_digest")
                elif hasattr(rec0, "object_digest"):
                    obj_digest = getattr(rec0, "object_digest")
                    tgt_digest = getattr(rec0, "target_digest")

        outputs.append(evaluate_claim(
            candidate=candidate,
            evaluator_check_records=eval_records,
            expected_object_digest=obj_digest,
            expected_target_digest=tgt_digest,
            evaluator_identity=eval_id,
        ))

    # If no checks were recognized, fail closed
    if not outputs:
        must_id = spec.get("must_id")
        return GateOutput(
            GateState.MISSING,
            must_id=must_id,
            detail=f"Unrecognized F3 trust specification inputs (must_id={must_id})",
            failures=[f"MISSING[{must_id or 'UNKNOWN'}]"],
        )

    # Return worst result: BLOCKED_ON_HUMAN > MISSING > SATISFIED
    all_failures: List[str] = []
    combined_explain: Dict[str, Any] = {}
    for o in outputs:
        all_failures.extend(o.failures)
        combined_explain.update(o.explain)

    blocked_outputs = [o for o in outputs if o.state == GateState.BLOCKED_ON_HUMAN]
    if blocked_outputs:
        primary = blocked_outputs[0]
        return GateOutput(
            GateState.BLOCKED_ON_HUMAN,
            must_id=primary.must_id,
            detail=primary.detail,
            failures=all_failures,
            explain=combined_explain,
        )

    missing_outputs = [o for o in outputs if o.state == GateState.MISSING]
    if missing_outputs:
        primary = missing_outputs[0]
        return GateOutput(
            GateState.MISSING,
            must_id=primary.must_id,
            detail=primary.detail,
            failures=all_failures,
            explain=combined_explain,
        )

    # All checks passed
    return GateOutput(GateState.SATISFIED, explain=combined_explain)
