"""Authoritative Wire Protocol, Session Identity & Consequential Actions Gate Engine.

Implements normative requirements for Chapter 7 Integrations & Developer Experience (Block 7, Lane B7-A):
- PD-CH7-016 (Line 3892): Every v1 wire request MUST carry a supported protocol_version and canonical
  task/session references; every response MUST carry request_id, result, next_action, resource_refs,
  and structured error envelope.
- PD-CH7-008 (Line 3909): Guidance resources MUST be versioned, bounded, and subordinate to frozen policy
  and kernel authorization.
- PD-CH7-009 (Line 3933): Protocol retries MUST be idempotent under the same request identity (principal,
  method, key, and request digest) and version conflicts MUST return a typed error.
- PD-CH7-011 (Line 3969): IDE mode MUST declare E0/E1/E2 capabilities per qualified host/version.
- PD-CH7-012 (Line 3993): Session identity MUST bind task, target snapshot, canonical revision, and
  pinned skill/pack digests; transport session metadata MUST NOT act as canonical lifecycle or approval authority.
- PD-CH7-013 (Line 4017): Consequential developer actions MUST pass existing authorization/scope gates
  and emit admissible observations before claims change.
"""
from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple

from sclass.product.gate import GateOutput, GateState

QUALIFIED_EVALUATOR_BOUNDARY = "QUALIFIED_EVALUATOR"
"""Enforces caller authority boundary across Block 7 Lane A evaluation."""

SUPPORTED_PROTOCOL_VERSIONS: FrozenSet[str] = frozenset({"1.0", "v1", "1.0.0"})
IDE_CAPABILITY_TIERS: FrozenSet[str] = frozenset({"E0", "E1", "E2"})

REQUIRED_SESSION_BINDINGS: FrozenSet[str] = frozenset({
    "task_id",
    "target_snapshot",
    "canonical_revision",
    "pinned_skill_digests",
    "pinned_pack_digests",
})

__all__ = [
    "QUALIFIED_EVALUATOR_BOUNDARY",
    "SUPPORTED_PROTOCOL_VERSIONS",
    "IDE_CAPABILITY_TIERS",
    "REQUIRED_SESSION_BINDINGS",
    "evaluate_pd_ch7_016_wire_protocol_envelope",
    "evaluate_pd_ch7_008_guidance_resources",
    "evaluate_pd_ch7_009_protocol_idempotent_retries",
    "evaluate_pd_ch7_011_ide_mode_capabilities",
    "evaluate_pd_ch7_012_session_identity_bindings",
    "evaluate_pd_ch7_013_consequential_developer_actions",
    "evaluate_b7_a_gate",
]


def evaluate_pd_ch7_016_wire_protocol_envelope(
    request: Optional[Mapping[str, Any]],
    response: Optional[Mapping[str, Any]],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH7-016 (Line 3892): Wire protocol request/response envelope conformance."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH7-016",
            detail="Caller lacks qualified evaluator authority",
        )
    try:

        if not request or not response:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH7-016",
                detail="Missing wire request or response envelope",
            )

        proto_ver = str(request.get("protocol_version", "")).strip()
        if proto_ver not in SUPPORTED_PROTOCOL_VERSIONS:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH7-016",
                detail=f"Unsupported wire protocol version: {proto_ver}",
            )

        if not request.get("task_id") or not request.get("session_id"):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH7-016",
                detail="Wire request missing canonical task or session reference",
            )

        for field in ("request_id", "result", "next_action", "resource_refs", "error"):
            if field not in response:
                return GateOutput(
                    state=GateState.MISSING,
                    must_id="PD-CH7-016",
                    detail=f"Wire response envelope missing required field: {field}",
                )

        return GateOutput(
            state=GateState.SATISFIED,
            must_id="PD-CH7-016",
            detail="Wire request/response envelopes fully conform to protocol specification",
        )
    except Exception as e:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH7-016",
            detail=f"Adversarial input rejected: {type(e).__name__}",
        )


def evaluate_pd_ch7_008_guidance_resources(
    versioned: bool,
    bounded: bool,
    subordinate_to_policy_and_kernel: bool,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH7-008 (Line 3909): Guidance resources versioned, bounded, subordinate to policy/kernel."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH7-008",
            detail="Caller lacks qualified evaluator authority",
        )

    if type(versioned) is not bool or type(bounded) is not bool or type(subordinate_to_policy_and_kernel) is not bool:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH7-008",
            detail="Guidance resources require exact boolean inputs",
        )

    if not versioned or not bounded or not subordinate_to_policy_and_kernel:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH7-008",
            detail="Guidance resource must be versioned, bounded, and subordinate to policy and kernel authorization",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH7-008",
        detail="Guidance resources versioned, bounded, and properly subordinate",
    )


def evaluate_pd_ch7_009_protocol_idempotent_retries(
    idempotent_under_request_identity: bool,
    version_conflict_typed_error: bool = True,
    *,
    conflict_detected: bool = False,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH7-009 (Line 3933): Protocol retries idempotent under identity; version conflicts return typed error."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH7-009",
            detail="Caller lacks qualified evaluator authority",
        )

    if type(idempotent_under_request_identity) is not bool or type(version_conflict_typed_error) is not bool or (conflict_detected is not None and type(conflict_detected) is not bool):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH7-009",
            detail="Protocol idempotent retries requires exact boolean inputs",
        )

    if not idempotent_under_request_identity:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH7-009",
            detail="Protocol retry is not idempotent under request identity (principal, method, key, digest)",
        )

    if conflict_detected and not version_conflict_typed_error:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH7-009",
            detail="Version conflict failed to return typed protocol error",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH7-009",
        detail="Protocol retries idempotent with typed version conflict handling",
    )


def evaluate_pd_ch7_011_ide_mode_capabilities(
    host_qualified: bool,
    declared_tier: Optional[str],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH7-011 (Line 3969): IDE mode declares E0/E1/E2 capabilities per qualified host/version."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH7-011",
            detail="Caller lacks qualified evaluator authority",
        )
    try:

        if not host_qualified or declared_tier not in IDE_CAPABILITY_TIERS:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH7-011",
                detail="IDE mode host not qualified or invalid capability tier (must declare E0, E1, or E2)",
            )

        return GateOutput(
            state=GateState.SATISFIED,
            must_id="PD-CH7-011",
            detail=f"IDE mode qualified with declared capability tier {declared_tier}",
        )
    except Exception as e:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH7-011",
            detail=f"Adversarial input rejected: {type(e).__name__}",
        )


def evaluate_pd_ch7_012_session_identity_bindings(
    session_bindings: Optional[Mapping[str, Any]],
    *,
    transport_claims_canonical_authority: bool = False,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH7-012 (Line 3993): Session identity binds task, snapshot, revision, and pins; no transport authority."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH7-012",
            detail="Caller lacks qualified evaluator authority",
        )
    try:

        if transport_claims_canonical_authority:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH7-012",
                detail="Transport session metadata claimed canonical lifecycle or approval authority",
            )

        if not session_bindings:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH7-012",
                detail="Session identity bindings missing entirely",
            )

        for field in REQUIRED_SESSION_BINDINGS:
            val = session_bindings.get(field)
            if val is None or (isinstance(val, (str, list, dict, set)) and len(val) == 0):
                return GateOutput(
                    state=GateState.MISSING,
                    must_id="PD-CH7-012",
                    detail=f"Session identity missing required binding: {field}",
                )

        return GateOutput(
            state=GateState.SATISFIED,
            must_id="PD-CH7-012",
            detail="Session identity successfully binds task, target snapshot, revision, and digests without transport usurpation",
        )
    except Exception as e:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH7-012",
            detail=f"Adversarial input rejected: {type(e).__name__}",
        )


def evaluate_pd_ch7_013_consequential_developer_actions(
    authorization_scope_gate_passed: bool,
    admissible_observation_emitted: bool,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH7-013 (Line 4017): Consequential developer actions pass authorization/scope gates and emit observation."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH7-013",
            detail="Caller lacks qualified evaluator authority",
        )

    if type(authorization_scope_gate_passed) is not bool or type(admissible_observation_emitted) is not bool:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH7-013",
            detail="Consequential actions require exact boolean inputs",
        )

    if not authorization_scope_gate_passed or not admissible_observation_emitted:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH7-013",
            detail="Consequential developer action failed authorization/scope gate or did not emit admissible observation",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        must_id="PD-CH7-013",
        detail="Consequential developer action authorized with admissible observation emitted",
    )


def evaluate_b7_a_gate(
    payload: Mapping[str, Any],
    *,
    authority: Optional[str] = None,
) -> Dict[str, GateOutput]:
    """Aggregate gate evaluator for Block 7 Lane A (PD-CH7-016, 008, 009, 011, 012, 013)."""
    if not isinstance(payload, Mapping):
        payload = {}
    return {
        "PD-CH7-016": evaluate_pd_ch7_016_wire_protocol_envelope(
            payload.get("request"),
            payload.get("response"),
            authority=authority,
        ),
        "PD-CH7-008": evaluate_pd_ch7_008_guidance_resources(
            payload.get("versioned", False),
            payload.get("bounded", False),
            payload.get("subordinate_to_policy_and_kernel", False),
            authority=authority,
        ),
        "PD-CH7-009": evaluate_pd_ch7_009_protocol_idempotent_retries(
            payload.get("idempotent_under_request_identity", False),
            version_conflict_typed_error=payload.get("version_conflict_typed_error", True),
            conflict_detected=payload.get("conflict_detected", False),
            authority=authority,
        ),
        "PD-CH7-011": evaluate_pd_ch7_011_ide_mode_capabilities(
            payload.get("host_qualified", False),
            payload.get("declared_tier"),
            authority=authority,
        ),
        "PD-CH7-012": evaluate_pd_ch7_012_session_identity_bindings(
            payload.get("session_bindings"),
            transport_claims_canonical_authority=payload.get("transport_claims_canonical_authority", False),
            authority=authority,
        ),
        "PD-CH7-013": evaluate_pd_ch7_013_consequential_developer_actions(
            payload.get("authorization_scope_gate_passed", False),
            payload.get("admissible_observation_emitted", False),
            authority=authority,
        ),
    }
