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
from typing import Any, Dict, List, Optional, Protocol, Union, runtime_checkable

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

from sclass.product.gate import GateOutput, GateState


# -----------------------------------------------------------------------------
# 2. Check Records and Confirmation Scope
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class CheckRecord:
    """Check record conferring gate authority when retrieved from an authoritative CheckRecordSource."""
    check_id: str
    producer: Optional[str] = None
    status: Optional[str] = None
    object_digest: Optional[str] = None
    target_digest: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "check_id": self.check_id,
        }
        if self.producer is not None:
            d["producer"] = self.producer
        if self.status is not None:
            d["status"] = self.status
        if self.object_digest is not None:
            d["object_digest"] = self.object_digest
        if self.target_digest is not None:
            d["target_digest"] = self.target_digest
        if self.details is not None:
            d["details"] = self.details
        return d


@runtime_checkable
class CheckRecordSource(Protocol):
    """Explicit dependency protocol for retrieving evaluator check records.

    Follows the injected-dependency pattern approved for F2's FrozenBindingResolver.
    Evaluator authority comes exclusively from the caller-injected lookup boundary,
    never from untrusted specification payloads, candidate fields, or self-attested
    record data.
    """

    def get_check_records(self, object_digest: str, target_digest: str) -> Sequence[Any]:
        """Retrieve evaluator check records bound to the given object and target digests."""
        ...


class InMemoryCheckRecordSource:
    """In-memory check record source holding evaluator check records.

    Keyed by (object_digest, target_digest). Does not create or mutate records.
    """

    def __init__(
        self,
        records: Sequence[Any] | Mapping[tuple[str, str], Sequence[Any]] | None = None,
    ) -> None:
        self._records: dict[tuple[str, str], list[Any]] = {}
        if records is not None:
            if isinstance(records, Mapping):
                for k, v in records.items():
                    if isinstance(k, tuple) and len(k) == 2:
                        self._records[(str(k[0]), str(k[1]))] = list(v)
            elif isinstance(records, Sequence):
                for r in records:
                    obj_d = r.get("object_digest") if isinstance(r, Mapping) else getattr(r, "object_digest", None)
                    tgt_d = r.get("target_digest") if isinstance(r, Mapping) else getattr(r, "target_digest", None)
                    if obj_d and tgt_d:
                        key = (str(obj_d), str(tgt_d))
                        self._records.setdefault(key, []).append(r)

    def get_check_records(self, object_digest: str, target_digest: str) -> Sequence[Any]:
        return list(self._records.get((str(object_digest), str(target_digest)), []))


def query_check_record_source(
    source: Any,
    object_digest: str,
    target_digest: str,
) -> Sequence[Any]:
    """Queries an injected check record source for records bound to object and target digests."""
    if hasattr(source, "get_check_records") and callable(getattr(source, "get_check_records")):
        res = source.get_check_records(object_digest, target_digest)
        return list(res) if isinstance(res, Sequence) else []
    return []


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
    check_record_source: Optional[Any] = None,
    expected_object_digest: Optional[str] = None,
    expected_target_digest: Optional[str] = None,
    *,
    spec_evaluator_records: Optional[Sequence[Any]] = None,
    evaluator_check_records: Optional[Sequence[Any]] = None,
) -> GateOutput:
    """Evaluates agent candidate claims against authoritative evaluator check records.

    Enforces:
    - PD-F3-001: Agent claims cannot self-authenticate. Evaluator records require explicit PASS status;
      missing, empty, or invalid status fails closed.
    - PD-F3-002: Gate authority must come from evaluator check records bound to object and target.
      Authority comes exclusively from a caller-injected CheckRecordSource dependency; untrusted
      specifications, candidate payloads, or embedded records cannot confer evaluator authority.
      Sources must implement get_check_records(object_digest, target_digest); arbitrary callables are rejected.
      Both expected_object_digest and expected_target_digest are required.
      Every record returned by the source must match both expected digests.
      Authority derives from the lookup boundary; a record's producer field cannot independently
      confer authority, nor does a correctly bound record require a self-asserted producer field.
    """
    # Detect candidate-embedded check records
    candidate_check_records = candidate.get("check_records") if isinstance(candidate, Mapping) else None
    has_agent_check_records = False
    has_embedded_evaluator_records = False
    if candidate_check_records:
        for r in candidate_check_records:
            r_prod = r.get("producer") if isinstance(r, Mapping) else getattr(r, "producer", None)
            r_status = r.get("status") if isinstance(r, Mapping) else getattr(r, "status", None)
            if r_prod == "agent" and r_status == "PASS":
                has_agent_check_records = True
            if r_prod == "evaluator":
                has_embedded_evaluator_records = True

    # Check for missing check record source
    if check_record_source is None:
        if has_embedded_evaluator_records:
            return GateOutput(
                GateState.MISSING,
                must_id="PD-F3-002",
                detail="Candidate-embedded check records cannot confer evaluator authority; authority requires an injected CheckRecordSource",
                failures=["MISSING[PD-F3-002]"],
                explain={"reason": "candidate_embedded_evaluator_records_ignored"},
            )
        if has_agent_check_records:
            return GateOutput(
                GateState.MISSING,
                must_id="PD-F3-002",
                detail="Gate authority must come from evaluator check records, not agent-authored check records",
                failures=["MISSING[PD-F3-002]"],
                explain={"reason": "agent_supplied_check_records_have_no_authority"},
            )
        # If untrusted spec supplied check records without source
        if spec_evaluator_records:
            return GateOutput(
                GateState.MISSING,
                must_id="PD-F3-002",
                detail="Evaluator check records must be queried from an injected CheckRecordSource, not supplied in spec",
                failures=["MISSING[PD-F3-002]"],
                explain={"reason": "missing_check_record_source"},
            )
        if expected_object_digest is not None or expected_target_digest is not None:
            return GateOutput(
                GateState.MISSING,
                must_id="PD-F3-002",
                detail="Evaluator authority requires an explicit caller-injected CheckRecordSource dependency",
                failures=["MISSING[PD-F3-002]"],
                explain={"reason": "missing_check_record_source"},
            )
        if isinstance(candidate, Mapping) and (candidate.get("verified") is True or candidate.get("status") == "PASS"):
            return GateOutput(
                GateState.MISSING,
                must_id="PD-F3-001",
                detail="Agent candidate claim cannot self-authenticate without valid evaluator check records",
                failures=["MISSING[PD-F3-001]"],
                explain={"reason": "candidate_verified_claim_unsupported_by_evaluator"},
            )
        return GateOutput(
            GateState.MISSING,
            must_id="PD-F3-002",
            detail="Evaluator authority requires an explicit caller-injected CheckRecordSource dependency",
            failures=["MISSING[PD-F3-002]"],
            explain={"reason": "missing_check_record_source"},
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

    # Validate source protocol conformance: must implement get_check_records
    if not (hasattr(check_record_source, "get_check_records") and callable(getattr(check_record_source, "get_check_records"))):
        return GateOutput(
            GateState.MISSING,
            must_id="PD-F3-002",
            detail="Evaluator check records require a valid CheckRecordSource dependency implementing get_check_records",
            failures=["MISSING[PD-F3-002]"],
            explain={"reason": "invalid_check_record_source_protocol"},
        )

    # Retrieve evaluator check records strictly from injected source
    evaluator_records = query_check_record_source(check_record_source, expected_object_digest, expected_target_digest)

    # Validate each returned record
    valid_evaluator_records: List[Any] = []
    for r in evaluator_records:
        rec_status = r.get("status") if isinstance(r, Mapping) else getattr(r, "status", None)
        rec_obj = r.get("object_digest") if isinstance(r, Mapping) else getattr(r, "object_digest", None)
        rec_tgt = r.get("target_digest") if isinstance(r, Mapping) else getattr(r, "target_digest", None)

        # Mandatory binding check on every returned record:
        # Both object and target digests must match expected digests
        if rec_obj != expected_object_digest:
            return GateOutput(
                GateState.MISSING,
                must_id="PD-F3-002",
                detail=f"Evaluator check record object digest mismatch: {rec_obj!r} != {expected_object_digest!r}",
                failures=["MISSING[PD-F3-002]"],
                explain={
                    "reason": "evaluator_record_digest_binding_mismatch",
                    "expected_object_digest": expected_object_digest,
                    "record_object_digest": rec_obj,
                },
            )
        if rec_tgt != expected_target_digest:
            return GateOutput(
                GateState.MISSING,
                must_id="PD-F3-002",
                detail=f"Evaluator check record target digest mismatch: {rec_tgt!r} != {expected_target_digest!r}",
                failures=["MISSING[PD-F3-002]"],
                explain={
                    "reason": "evaluator_record_digest_binding_mismatch",
                    "expected_target_digest": expected_target_digest,
                    "record_target_digest": rec_tgt,
                },
            )

        # Status validation: explicit PASS required
        if rec_status is None:
            return GateOutput(
                GateState.MISSING,
                must_id="PD-F3-001",
                detail="Evaluator check record missing required status; cannot implicitly default to PASS",
                failures=["MISSING[PD-F3-001]"],
                explain={"reason": "evaluator_record_status_missing"},
            )
        if not isinstance(rec_status, str) or not rec_status.strip() or rec_status.strip() != "PASS":
            return GateOutput(
                GateState.MISSING,
                must_id="PD-F3-001",
                detail="Evaluator check record status must be 'PASS'; missing, empty, or invalid status fails closed",
                failures=["MISSING[PD-F3-001]"],
                explain={
                    "reason": "evaluator_record_status_invalid",
                    "invalid_statuses": [str(rec_status)],
                },
            )

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
        if expected_object_digest or expected_target_digest:
            return GateOutput(
                GateState.MISSING,
                must_id="PD-F3-002",
                detail="No evaluator check records found matching expected object and target digests",
                failures=["MISSING[PD-F3-002]"],
                explain={
                    "reason": "evaluator_record_digest_binding_mismatch",
                    "expected_object_digest": expected_object_digest,
                    "expected_target_digest": expected_target_digest,
                },
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
    # 1. Canonical structured form is REQUIRED; digest-only input fails closed
    # 2. Recomputed via canonical_c1
    # 3. If caller supplied comparison digest, empty values rejected and differing values fail closed
    # Never trust the event's self-attested digest!
    if canonical_structured_form is None:
        return GateOutput(
            GateState.BLOCKED_ON_HUMAN,
            must_id="PD-F3-004",
            detail="Canonical structured form is required; digest-only input fails closed",
            failures=["BLOCKED_ON_HUMAN[PD-F3-004]"],
            explain={"reason": "canonical_structured_form_required_digest_only_rejected"},
        )

    if isinstance(canonical_structured_form, Mapping):
        clean_form = {k: v for k, v in canonical_structured_form.items() if k != "content_digest"}
        raw = canonical_c1(freeze_to_c1_compatible(clean_form))
    else:
        raw = canonical_c1(freeze_to_c1_compatible(canonical_structured_form))
    computed_digest = hashlib.sha256(raw).hexdigest()

    if canonical_structured_form_digest is not None:
        if not isinstance(canonical_structured_form_digest, str) or not canonical_structured_form_digest.strip():
            return GateOutput(
                GateState.BLOCKED_ON_HUMAN,
                must_id="PD-F3-004",
                detail="Empty canonical_structured_form_digest supplied",
                failures=["BLOCKED_ON_HUMAN[PD-F3-004]"],
                explain={"reason": "empty_canonical_structured_form_digest"},
            )
        if canonical_structured_form_digest != computed_digest:
            return GateOutput(
                GateState.BLOCKED_ON_HUMAN,
                must_id="PD-F3-004",
                detail=(
                    f"Supplied comparison digest {canonical_structured_form_digest} differs from "
                    f"recomputed digest {computed_digest}"
                ),
                failures=["BLOCKED_ON_HUMAN[PD-F3-004]"],
                explain={
                    "reason": "conflicting_canonical_form_digests",
                    "supplied_digest": canonical_structured_form_digest,
                    "recomputed_digest": computed_digest,
                },
            )

    # Verify digest equality: changed digest requires human reconfirmation
    if source_provenance != computed_digest:
        return GateOutput(
            GateState.BLOCKED_ON_HUMAN,
            must_id="PD-F3-004",
            detail=(
                f"Canonical structured form digest changed ({source_provenance} != {computed_digest}); "
                "reconfirmation requires a human"
            ),
            failures=["BLOCKED_ON_HUMAN[PD-F3-004]"],
            explain={
                "reason": "canonical_digest_mismatch_requires_reconfirmation",
                "source_provenance": source_provenance,
                "canonical_structured_form_digest": computed_digest,
            },
        )

    return GateOutput(
        GateState.SATISFIED,
        explain={
            "source_provenance": source_provenance,
            "canonical_structured_form_digest": computed_digest,
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


def evaluate_f3_trust(
    spec: Mapping[str, Any],
    check_record_source: Optional[Any] = None,
    expected_object_digest: Optional[str] = None,
    expected_target_digest: Optional[str] = None,
) -> GateOutput:
    """Unified evaluator for R30 Section F3 fixtures and specifications.

    Dispatches to and evaluates EVERY present check.
    Returns the worst result; BLOCKED_ON_HUMAN and MISSING override SATISFIED.
    Empty and unrecognized specifications fail closed.

    Enforces Directive 1-03e and 1-03f:
    - Authority comes strictly from a caller-injected CheckRecordSource dependency;
      never from untrusted specifications, candidate payloads, or embedded records.
    - CheckRecordSource must implement get_check_records(object_digest, target_digest);
      arbitrary callables are rejected.
    - Evaluator authority derives strictly from the injected CheckRecordSource lookup boundary;
      no caller-asserted evaluator identity parameter exists.
    - expected_object_digest and expected_target_digest must be supplied as explicit caller arguments.
    - PD-F3-004 requires canonical structured form; digest-only input fails closed.
    - All fallback chains replaced with explicit key-presence and conflict validation.
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

    # 2. PD-F3-005: Content digest verification (explicit key presence, no fallback chain)
    has_ccd = "claimed_content_digest" in spec
    has_cd = "claimed_digest" in spec

    if has_ccd or has_cd:
        artifact = spec.get("artifact")
        if has_ccd and has_cd:
            v_ccd = spec.get("claimed_content_digest")
            v_cd = spec.get("claimed_digest")
            if not isinstance(v_ccd, str) or not v_ccd.strip():
                outputs.append(GateOutput(
                    GateState.MISSING,
                    must_id="PD-F3-005",
                    detail="Empty claimed_content_digest supplied",
                    failures=["MISSING[PD-F3-005]"],
                    explain={"reason": "empty_claimed_content_digest"},
                ))
            elif not isinstance(v_cd, str) or not v_cd.strip():
                outputs.append(GateOutput(
                    GateState.MISSING,
                    must_id="PD-F3-005",
                    detail="Empty claimed_digest supplied",
                    failures=["MISSING[PD-F3-005]"],
                    explain={"reason": "empty_claimed_digest"},
                ))
            elif v_ccd != v_cd:
                outputs.append(GateOutput(
                    GateState.MISSING,
                    must_id="PD-F3-005",
                    detail=f"Conflicting claimed digest keys supplied: claimed_content_digest={v_ccd!r} != claimed_digest={v_cd!r}",
                    failures=["MISSING[PD-F3-005]"],
                    explain={"reason": "conflicting_claimed_digest_keys", "claimed_content_digest": v_ccd, "claimed_digest": v_cd},
                ))
            else:
                outputs.append(verify_content_digest(v_ccd, artifact))
        elif has_ccd:
            v_ccd = spec.get("claimed_content_digest")
            if not isinstance(v_ccd, str) or not v_ccd.strip():
                outputs.append(GateOutput(
                    GateState.MISSING,
                    must_id="PD-F3-005",
                    detail="Empty claimed_content_digest supplied",
                    failures=["MISSING[PD-F3-005]"],
                    explain={"reason": "empty_claimed_content_digest"},
                ))
            else:
                outputs.append(verify_content_digest(v_ccd, artifact))
        else:  # has_cd
            v_cd = spec.get("claimed_digest")
            if not isinstance(v_cd, str) or not v_cd.strip():
                outputs.append(GateOutput(
                    GateState.MISSING,
                    must_id="PD-F3-005",
                    detail="Empty claimed_digest supplied",
                    failures=["MISSING[PD-F3-005]"],
                    explain={"reason": "empty_claimed_digest"},
                ))
            else:
                outputs.append(verify_content_digest(v_cd, artifact))

    # 3. PD-F3-004: Requirement confirmation (explicit key presence, canonical structured form required)
    if "requirement_confirmation" in spec:
        req_conf = spec["requirement_confirmation"]
        form = spec.get("canonical_structured_form")

        has_top_d = "canonical_structured_form_digest" in spec
        has_req_d = isinstance(req_conf, Mapping) and "canonical_structured_form_digest" in req_conf

        form_digest: Optional[str] = None
        has_digest_error = False

        if has_top_d and has_req_d:
            top_d = spec.get("canonical_structured_form_digest")
            req_d = req_conf.get("canonical_structured_form_digest")
            if not isinstance(top_d, str) or not top_d.strip() or not isinstance(req_d, str) or not req_d.strip():
                outputs.append(GateOutput(
                    GateState.BLOCKED_ON_HUMAN,
                    must_id="PD-F3-004",
                    detail="Empty canonical structured form digest supplied",
                    failures=["BLOCKED_ON_HUMAN[PD-F3-004]"],
                    explain={"reason": "empty_canonical_structured_form_digest"},
                ))
                has_digest_error = True
            elif top_d != req_d:
                outputs.append(GateOutput(
                    GateState.BLOCKED_ON_HUMAN,
                    must_id="PD-F3-004",
                    detail=f"Conflicting canonical structured form digests supplied: {top_d!r} != {req_d!r}",
                    failures=["BLOCKED_ON_HUMAN[PD-F3-004]"],
                    explain={"reason": "conflicting_canonical_form_digests", "top_digest": top_d, "req_digest": req_d},
                ))
                has_digest_error = True
            else:
                form_digest = top_d
        elif has_top_d:
            top_d = spec.get("canonical_structured_form_digest")
            if not isinstance(top_d, str) or not top_d.strip():
                outputs.append(GateOutput(
                    GateState.BLOCKED_ON_HUMAN,
                    must_id="PD-F3-004",
                    detail="Empty canonical structured form digest supplied",
                    failures=["BLOCKED_ON_HUMAN[PD-F3-004]"],
                    explain={"reason": "empty_canonical_structured_form_digest"},
                ))
                has_digest_error = True
            else:
                form_digest = top_d
        elif has_req_d:
            req_d = req_conf.get("canonical_structured_form_digest")
            if not isinstance(req_d, str) or not req_d.strip():
                outputs.append(GateOutput(
                    GateState.BLOCKED_ON_HUMAN,
                    must_id="PD-F3-004",
                    detail="Empty canonical structured form digest supplied in event",
                    failures=["BLOCKED_ON_HUMAN[PD-F3-004]"],
                    explain={"reason": "empty_canonical_structured_form_digest"},
                ))
                has_digest_error = True
            else:
                form_digest = req_d

        if not has_digest_error:
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
    # Evaluator authority requires an injected CheckRecordSource and caller arguments.
    # Never obtain the source from spec, candidate, or untrusted payload!
    if "candidate" in spec or "evaluator_check_records" in spec or check_record_source is not None:
        candidate = spec.get("candidate", {})
        spec_eval_records = spec.get("evaluator_check_records")
        outputs.append(evaluate_claim(
            candidate=candidate,
            check_record_source=check_record_source,
            expected_object_digest=expected_object_digest,
            expected_target_digest=expected_target_digest,
            spec_evaluator_records=spec_eval_records,
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
