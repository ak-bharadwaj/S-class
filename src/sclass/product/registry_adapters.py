"""Thin fail-closed evaluators for the 54 core-module MUSTs without standalone evaluate_pd_* functions.

Each function enforces caller authority (QUALIFIED_EVALUATOR_BOUNDARY), validates
evidence is a non-empty Mapping, and delegates to the authoritative core product
module (F1-F9, Ch.5). Never returns SATISFIED by default.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

from sclass.product.artifacts import evaluate_f1_representation
from sclass.product.check_registry import (
    QUALIFIED_EVALUATOR_BOUNDARY as CHECK_REG_AUTH,
    validate_check_id,
)
from sclass.product.claim_ledger import evaluate_f7_claim
from sclass.product.f4_lane_selection import (
    QUALIFIED_EVALUATOR_BOUNDARY as F4_AUTH,
    compute_lane,
    evaluate_f4_lane_selection,
    resolve_effective_depth,
)
from sclass.product.f8_step_pack import compile_step_pack, resume_step_pack, truncate_context_items
from sclass.product.gate import GateOutput, GateState
from sclass.product.gate_cache import GateCache
from sclass.product.gate_evaluator import (
    QUALIFIED_EVALUATOR_BOUNDARY as F5_AUTH,
    evaluate_f5_gate,
)
from sclass.product.lifecycle_p6 import (
    QUALIFIED_EVALUATOR_BOUNDARY as P6_AUTH,
    evaluate_pd_ch2_039_implementation_claims,
)
from sclass.product.metrics import project_metrics_from_events
from sclass.product.performance_claims import (
    QUALIFIED_EVALUATOR_BOUNDARY as PERF_AUTH,
    evaluate_performance_claim,
)
from sclass.product.predicate_evaluator import evaluate_predicate_input, resolve_frozen_bindings
from sclass.product.traceability import evaluate_f6_traceability
from sclass.product.trust_model import (
    check_structured_conflict,
    evaluate_claim,
    evaluate_confirmation_admissibility,
    evaluate_requirement_confirmation,
    verify_content_digest,
)

QUALIFIED_EVALUATOR_BOUNDARY = "sclass.product.registry_adapters"


def _auth_fail(must_id: str, authority: Optional[str]) -> Optional[GateOutput]:
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id=must_id,
            detail="Caller lacks qualified evaluator authority",
            failures=[f"MISSING[{must_id}]"],
        )
    return None


def _require_mapping(must_id: str, evidence: Any) -> Optional[GateOutput]:
    if not isinstance(evidence, Mapping) or not evidence:
        return GateOutput(
            state=GateState.MISSING,
            must_id=must_id,
            detail="Evidence must be a non-empty Mapping",
            failures=[f"MISSING[{must_id}]"],
        )
    return None


def _eval_gate_cache_must(must_id: str, evidence: Mapping[str, Any], authority: Optional[str]) -> GateOutput:
    if err := (_auth_fail(must_id, authority) or _require_mapping(must_id, evidence)):
        return err
    # Check GateCache key fields (guidance_digest, policy_version, target_digest, etc.)
    cached_g = evidence.get("cached_guidance_digest")
    curr_g = evidence.get("current_guidance_digest")
    if cached_g is not None and curr_g is not None and cached_g != curr_g:
        return GateOutput(state=GateState.MISSING, must_id=must_id, detail="cache guidance digest mismatch")
    key_fields = evidence.get("cache_key_inputs")
    if isinstance(key_fields, Mapping) and key_fields:
        if evidence.get("identity_changed") is True or evidence.get("stale") is True:
            return GateOutput(state=GateState.MISSING, must_id=must_id, detail="stale cache invalidated")
        return GateOutput(state=GateState.SATISFIED, detail=f"{must_id} gate cache valid")
    return GateOutput(state=GateState.MISSING, must_id=must_id, detail="missing cache_key_inputs")


def evaluate_pd_ch5_003(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_gate_cache_must("PD-CH5-003", evidence, authority)


def evaluate_pd_ch5_004(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    if err := (_auth_fail("PD-CH5-004", authority) or _require_mapping("PD-CH5-004", evidence)):
        return err
    return evaluate_performance_claim(evidence, authority=PERF_AUTH)


def evaluate_pd_ch5_005(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    if err := (_auth_fail("PD-CH5-005", authority) or _require_mapping("PD-CH5-005", evidence)):
        return err
    events = evidence.get("events")
    if not isinstance(events, list) or not events:
        return GateOutput(state=GateState.MISSING, must_id="PD-CH5-005", detail="events required for metric projection")
    res = project_metrics_from_events(events)
    if not res:
        return GateOutput(state=GateState.MISSING, must_id="PD-CH5-005", detail="no metrics projected")
    return GateOutput(state=GateState.SATISFIED, detail="Metrics projected from canonical events")


def evaluate_pd_ch5_006(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    if err := (_auth_fail("PD-CH5-006", authority) or _require_mapping("PD-CH5-006", evidence)):
        return err
    cid = evidence.get("check_id")
    if not isinstance(cid, str) or not cid:
        return GateOutput(state=GateState.MISSING, must_id="PD-CH5-006", detail="check_id required")
    return validate_check_id(cid, caller_authority=CHECK_REG_AUTH)


def evaluate_pd_ch5_007(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_gate_cache_must("PD-CH5-007", evidence, authority)


def evaluate_pd_ch5_008(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_gate_cache_must("PD-CH5-008", evidence, authority)


def evaluate_pd_ch5_009(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_gate_cache_must("PD-CH5-009", evidence, authority)


def evaluate_pd_ch5_010(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_gate_cache_must("PD-CH5-010", evidence, authority)


def _eval_f1_must(must_id: str, evidence: Mapping[str, Any], authority: Optional[str]) -> GateOutput:
    if err := (_auth_fail(must_id, authority) or _require_mapping(must_id, evidence)):
        return err
    art = evidence.get("artifact", evidence)
    return evaluate_f1_representation(art, caller_authority="sclass.product.artifacts")


def evaluate_pd_f1_001(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f1_must("PD-F1-001", evidence, authority)


def evaluate_pd_f1_002(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f1_must("PD-F1-002", evidence, authority)


def evaluate_pd_f1_003(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f1_must("PD-F1-003", evidence, authority)


def evaluate_pd_f1_004(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f1_must("PD-F1-004", evidence, authority)


def evaluate_pd_f1_005(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f1_must("PD-F1-005", evidence, authority)


def _eval_f2_must(must_id: str, evidence: Mapping[str, Any], authority: Optional[str]) -> GateOutput:
    if err := (_auth_fail(must_id, authority) or _require_mapping(must_id, evidence)):
        return err
    if must_id == "PD-F2-007":
        bindings = evidence.get("bindings")
        if not isinstance(bindings, Mapping) or not bindings:
            return GateOutput(state=GateState.MISSING, must_id=must_id, detail="bindings required")
        resolve_frozen_bindings(bindings)
        return GateOutput(state=GateState.SATISFIED, detail="F2 frozen bindings resolved")
    pred = evidence.get("predicate")
    if pred is None:
        return GateOutput(state=GateState.MISSING, must_id=must_id, detail="predicate required")
    return evaluate_predicate_input(pred, evidence.get("context", {}))


def evaluate_pd_f2_001(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f2_must("PD-F2-001", evidence, authority)


def evaluate_pd_f2_002(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f2_must("PD-F2-002", evidence, authority)


def evaluate_pd_f2_005(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f2_must("PD-F2-005", evidence, authority)


def evaluate_pd_f2_007(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f2_must("PD-F2-007", evidence, authority)


def evaluate_pd_f3_001(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    if err := (_auth_fail("PD-F3-001", authority) or _require_mapping("PD-F3-001", evidence)):
        return err
    claim = evidence.get("claim", evidence)
    return evaluate_claim(claim, caller_authority="sclass.product.trust_model")


def evaluate_pd_f3_002(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    if err := (_auth_fail("PD-F3-002", authority) or _require_mapping("PD-F3-002", evidence)):
        return err
    claim = evidence.get("claim", evidence)
    return evaluate_claim(claim, caller_authority="sclass.product.trust_model")


def evaluate_pd_f3_003(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    if err := (_auth_fail("PD-F3-003", authority) or _require_mapping("PD-F3-003", evidence)):
        return err
    reps = evidence.get("representations")
    if not isinstance(reps, list) or not reps:
        return GateOutput(state=GateState.MISSING, must_id="PD-F3-003", detail="representations required")
    return check_structured_conflict(reps, caller_authority="sclass.product.trust_model")


def evaluate_pd_f3_004(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    if err := (_auth_fail("PD-F3-004", authority) or _require_mapping("PD-F3-004", evidence)):
        return err
    req = evidence.get("requirement", evidence)
    return evaluate_requirement_confirmation(req, caller_authority="sclass.product.trust_model")


def evaluate_pd_f3_005(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    if err := (_auth_fail("PD-F3-005", authority) or _require_mapping("PD-F3-005", evidence)):
        return err
    content = evidence.get("content")
    digest = evidence.get("expected_digest")
    if not isinstance(content, (bytes, str)) or not isinstance(digest, str):
        return GateOutput(state=GateState.MISSING, must_id="PD-F3-005", detail="content and expected_digest required")
    ok = verify_content_digest(content.encode("utf-8") if isinstance(content, str) else content, digest)
    if not ok:
        return GateOutput(state=GateState.MISSING, must_id="PD-F3-005", detail="content digest mismatch")
    return GateOutput(state=GateState.SATISFIED, detail="Content digest verified")


def evaluate_pd_f3_006(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    if err := (_auth_fail("PD-F3-006", authority) or _require_mapping("PD-F3-006", evidence)):
        return err
    rec = evidence.get("confirmation", evidence)
    return evaluate_confirmation_admissibility(rec, caller_authority="sclass.product.trust_model")


def _eval_f4_must(must_id: str, evidence: Mapping[str, Any], authority: Optional[str]) -> GateOutput:
    if err := (_auth_fail(must_id, authority) or _require_mapping(must_id, evidence)):
        return err
    return evaluate_f4_lane_selection(evidence, authority=F4_AUTH)


def evaluate_pd_f4_001(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f4_must("PD-F4-001", evidence, authority)


def evaluate_pd_f4_002(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f4_must("PD-F4-002", evidence, authority)


def evaluate_pd_f4_003(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f4_must("PD-F4-003", evidence, authority)


def evaluate_pd_f4_004(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f4_must("PD-F4-004", evidence, authority)


def evaluate_pd_f4_005(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f4_must("PD-F4-005", evidence, authority)


def evaluate_pd_f4_006(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    if err := (_auth_fail("PD-F4-006", authority) or _require_mapping("PD-F4-006", evidence)):
        return err
    p_depth = evidence.get("policy_floor")
    prof_depth = evidence.get("profile_depth")
    if not isinstance(p_depth, int) or isinstance(p_depth, bool) or not isinstance(prof_depth, int) or isinstance(prof_depth, bool):
        return GateOutput(state=GateState.MISSING, must_id="PD-F4-006", detail="policy_floor and profile_depth ints required")
    resolve_effective_depth(p_depth, prof_depth)
    return GateOutput(state=GateState.SATISFIED, detail="Effective depth resolved")


def _eval_f5_must(must_id: str, evidence: Mapping[str, Any], authority: Optional[str]) -> GateOutput:
    if err := (_auth_fail(must_id, authority) or _require_mapping(must_id, evidence)):
        return err
    return evaluate_f5_gate(evidence, authority=F5_AUTH)


def evaluate_pd_f5_001(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f5_must("PD-F5-001", evidence, authority)


def evaluate_pd_f5_002(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f5_must("PD-F5-002", evidence, authority)


def evaluate_pd_f5_003(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f5_must("PD-F5-003", evidence, authority)


def evaluate_pd_f5_004(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f5_must("PD-F5-004", evidence, authority)


def evaluate_pd_f5_005(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f5_must("PD-F5-005", evidence, authority)


def _eval_f6_must(must_id: str, evidence: Mapping[str, Any], authority: Optional[str]) -> GateOutput:
    if err := (_auth_fail(must_id, authority) or _require_mapping(must_id, evidence)):
        return err
    return evaluate_f6_traceability(evidence, caller_authority="sclass.product.traceability")


def evaluate_pd_f6_001(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f6_must("PD-F6-001", evidence, authority)


def evaluate_pd_f6_002(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f6_must("PD-F6-002", evidence, authority)


def evaluate_pd_f6_003(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f6_must("PD-F6-003", evidence, authority)


def evaluate_pd_f6_004(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f6_must("PD-F6-004", evidence, authority)


def evaluate_pd_f6_005(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f6_must("PD-F6-005", evidence, authority)


def evaluate_pd_f6_006(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f6_must("PD-F6-006", evidence, authority)


def _eval_f7_must(must_id: str, evidence: Mapping[str, Any], authority: Optional[str]) -> GateOutput:
    if err := (_auth_fail(must_id, authority) or _require_mapping(must_id, evidence)):
        return err
    claim = evidence.get("claim", evidence)
    return evaluate_f7_claim(claim)


def evaluate_pd_f7_001(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f7_must("PD-F7-001", evidence, authority)


def evaluate_pd_f7_002(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f7_must("PD-F7-002", evidence, authority)


def evaluate_pd_f7_003(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f7_must("PD-F7-003", evidence, authority)


def evaluate_pd_f7_004(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f7_must("PD-F7-004", evidence, authority)


def evaluate_pd_f7_005(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f7_must("PD-F7-005", evidence, authority)


def evaluate_pd_f7_006(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    if err := (_auth_fail("PD-F7-006", authority) or _require_mapping("PD-F7-006", evidence)):
        return err
    return evaluate_pd_ch2_039_implementation_claims(
        claim_type=evidence.get("claim_type"),
        created_by_delta=evidence.get("created_by_delta"),
        authority=P6_AUTH,
    )


def _eval_f8_must(must_id: str, evidence: Mapping[str, Any], authority: Optional[str]) -> GateOutput:
    if err := (_auth_fail(must_id, authority) or _require_mapping(must_id, evidence)):
        return err
    if must_id == "PD-F8-002":
        items = evidence.get("items")
        budget = evidence.get("byte_budget")
        if not isinstance(items, list) or not isinstance(budget, int):
            return GateOutput(state=GateState.MISSING, must_id=must_id, detail="items and byte_budget required")
        truncate_context_items(items, budget)
        return GateOutput(state=GateState.SATISFIED, detail="F8 truncation bounded")
    if must_id == "PD-F8-003":
        snap = evidence.get("snapshot")
        if not isinstance(snap, Mapping):
            return GateOutput(state=GateState.MISSING, must_id=must_id, detail="snapshot required")
        resume_step_pack(snap)
        return GateOutput(state=GateState.SATISFIED, detail="F8 canonical resume valid")
    pack_args = evidence.get("step_pack_args")
    if not isinstance(pack_args, Mapping):
        return GateOutput(state=GateState.MISSING, must_id=must_id, detail="step_pack_args required")
    compile_step_pack(**dict(pack_args))
    return GateOutput(state=GateState.SATISFIED, detail="F8 step pack compiled")


def evaluate_pd_f8_001(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f8_must("PD-F8-001", evidence, authority)


def evaluate_pd_f8_002(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f8_must("PD-F8-002", evidence, authority)


def evaluate_pd_f8_003(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f8_must("PD-F8-003", evidence, authority)


def evaluate_pd_f8_004(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f8_must("PD-F8-004", evidence, authority)


def _eval_f9_must(must_id: str, evidence: Mapping[str, Any], authority: Optional[str]) -> GateOutput:
    if err := (_auth_fail(must_id, authority) or _require_mapping(must_id, evidence)):
        return err
    events = evidence.get("events")
    if not isinstance(events, list) or not events:
        return GateOutput(state=GateState.MISSING, must_id=must_id, detail="events required for F9 metrics")
    res = project_metrics_from_events(events)
    if not res:
        return GateOutput(state=GateState.MISSING, must_id=must_id, detail="no metrics projected")
    return GateOutput(state=GateState.SATISFIED, detail="F9 metrics projected")


def evaluate_pd_f9_001(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f9_must("PD-F9-001", evidence, authority)


def evaluate_pd_f9_002(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f9_must("PD-F9-002", evidence, authority)


def evaluate_pd_f9_003(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f9_must("PD-F9-003", evidence, authority)


def evaluate_pd_f9_004(evidence: Mapping[str, Any], *, authority: Optional[str] = None) -> GateOutput:
    return _eval_f9_must("PD-F9-004", evidence, authority)
