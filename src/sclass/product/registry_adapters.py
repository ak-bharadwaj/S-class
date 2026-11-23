"""Thin fail-closed evaluators for the 54 core-module MUSTs without standalone evaluate_pd_* functions.

Each function enforces caller authority (QUALIFIED_EVALUATOR_BOUNDARY), validates
evidence is a non-empty Mapping, and delegates to the authoritative core product
module (F1-F9, Ch.5). Never returns SATISFIED by default.
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, Mapping, Optional, Sequence

from sclass.product.artifacts import (
    QUALIFIED_EVALUATOR_BOUNDARY as ARTIFACTS_AUTH,
    evaluate_f1_representation,
)
from sclass.product.check_registry import (
    QUALIFIED_EVALUATOR_BOUNDARY as CHECK_REG_AUTH,
    validate_check_id,
)
from sclass.product.claim_ledger import ClaimRecord, evaluate_f7_claim
from sclass.product.f4_lane_selection import (
    QUALIFIED_EVALUATOR_BOUNDARY as F4_AUTH,
    DepthLevel,
    evaluate_f4_lane_selection,
    resolve_effective_depth,
)
from sclass.product.f8_step_pack import (
    QUALIFIED_EVALUATOR_BOUNDARY as F8_AUTH,
    compile_step_pack,
    evaluate_f8_step_pack,
    resume_step_pack,
    truncate_context_items,
)
from sclass.product.gate import GateOutput, GateState
from sclass.product.gate_cache import (
    QUALIFIED_EVALUATOR_BOUNDARY as GATE_CACHE_AUTH,
    GateCache,
    compute_gate_cache_key,
)
from sclass.product.gate_evaluator import (
    QUALIFIED_EVALUATOR_BOUNDARY as F5_AUTH,
    evaluate_f5_gate,
)
from sclass.product.lifecycle_p6 import (
    QUALIFIED_EVALUATOR_BOUNDARY as P6_AUTH,
    evaluate_pd_ch2_039_implementation_claims,
)
from sclass.product.metrics import (
    QUALIFIED_EVALUATOR_BOUNDARY as METRICS_AUTH,
    ProductMetricEnvelope,
    evaluate_f9_metric,
)
from sclass.product.performance_claims import (
    QUALIFIED_EVALUATOR_BOUNDARY as PERF_AUTH,
    evaluate_performance_claim,
)
from sclass.product.predicate_evaluator import (
    evaluate_predicate_input,
    resolve_frozen_bindings,
)
from sclass.product.traceability import evaluate_f6_traceability
from sclass.product.trust_model import (
    check_structured_conflict,
    evaluate_claim,
    evaluate_confirmation_admissibility,
    evaluate_requirement_confirmation,
    verify_content_digest,
)

QUALIFIED_EVALUATOR_BOUNDARY = "sclass.product.registry_adapters"

_GATE_CACHE_TUPLE_FIELDS = (
    "phase",
    "canonical_state_binding",
    "task_ref",
    "spec_anchor_digest",
    "input_digests",
    "pinned_guidance",
    "policy_version",
    "evaluator_version",
    "evaluation_instant",
)


def _missing_gate(must_id: str, detail: str) -> GateOutput:
    return GateOutput(
        state=GateState.MISSING,
        must_id=must_id,
        detail=detail,
        failures=[f"MISSING[{must_id}]"],
    )


def _auth_fail(must_id: str, authority: Optional[str]) -> Optional[GateOutput]:
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return _missing_gate(must_id, "Caller lacks qualified evaluator authority")
    return None


def _require_mapping(must_id: str, evidence: Any) -> Optional[GateOutput]:
    if not isinstance(evidence, Mapping) or not evidence:
        return _missing_gate(must_id, "Evidence must be a non-empty Mapping")
    return None


def _guidance_sha256(pinned_guidance: Any) -> str:
    return hashlib.sha256(repr(pinned_guidance).encode("utf-8")).hexdigest()


def _try_cache_key(entry: Mapping[str, Any]) -> Optional[str]:
    try:
        pinned = entry.get("pinned_guidance")
        return compute_gate_cache_key(
            phase=entry.get("phase"),
            canonical_state_binding=entry.get("canonical_state_binding"),
            task_ref=entry.get("task_ref"),
            spec_anchor_digest=entry.get("spec_anchor_digest"),
            input_digests=entry.get("input_digests") or (),
            pinned_guidance_digest=(
                str(pinned) if isinstance(pinned, str) else repr(pinned)
            ),
            policy_version=entry.get("policy_version"),
            evaluator_version=entry.get("evaluator_version"),
            evaluation_instant=entry.get("evaluation_instant"),
        )
    except Exception:
        return None


def _with_explain_detail(out: GateOutput) -> GateOutput:
    if out.detail or not isinstance(out.explain, Mapping):
        return out
    err = out.explain.get("error") or out.explain.get("reason")
    if isinstance(err, str) and err:
        return GateOutput(
            state=out.state,
            must_id=out.must_id,
            detail=err,
            failures=out.failures,
            explain=out.explain,
        )
    return out


def _eval_cache_lookup_must(
    must_id: str, evidence: Mapping[str, Any], authority: Optional[str]
) -> GateOutput:
    if err := (_auth_fail(must_id, authority) or _require_mapping(must_id, evidence)):
        return err

    eval_tuple = (
        dict(evidence["evaluation_tuple"])
        if isinstance(evidence.get("evaluation_tuple"), Mapping)
        else {k: evidence[k] for k in _GATE_CACHE_TUPLE_FIELDS if k in evidence}
    )

    cache = GateCache()
    cached_entry = evidence.get("cached_entry")
    cached_guidance_digest = evidence.get("cached_guidance_digest")
    current_guidance_digest = evidence.get("current_guidance_digest")

    if isinstance(cached_entry, Mapping):
        cached_key = _try_cache_key(cached_entry)
        if cached_key is not None:
            cache.put(
                cached_key,
                GateOutput(state=GateState.SATISFIED, detail=f"{must_id} cache hit"),
                cached_entry,
                caller_authority=GATE_CACHE_AUTH,
            )
            if cached_guidance_digest is None and "pinned_guidance" in cached_entry:
                cached_guidance_digest = _guidance_sha256(
                    cached_entry["pinned_guidance"]
                )

    if current_guidance_digest is None and "pinned_guidance" in eval_tuple:
        current_guidance_digest = _guidance_sha256(eval_tuple["pinned_guidance"])

    lookup_key = evidence.get("cache_key")
    if lookup_key is None and "cache_key" not in evidence:
        lookup_key = _try_cache_key(eval_tuple)

    return _with_explain_detail(
        cache.evaluate_cache_lookup(
            lookup_key,
            eval_tuple,
            cached_guidance_digest=cached_guidance_digest,
            current_guidance_digest=current_guidance_digest,
            caller_authority=GATE_CACHE_AUTH,
        )
    )


def evaluate_pd_ch5_003(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_cache_lookup_must("PD-CH5-003", evidence, authority)


def evaluate_pd_ch5_004(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    if err := (_auth_fail("PD-CH5-004", authority) or _require_mapping("PD-CH5-004", evidence)):
        return err
    claim = evidence.get("claim")
    if not isinstance(claim, str) or not claim.strip():
        return _missing_gate("PD-CH5-004", "claim must be a non-empty string")
    return evaluate_performance_claim(dict(evidence), caller_authority=PERF_AUTH)


def evaluate_pd_ch5_005(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f9_must("PD-CH5-005", evidence, authority)


def evaluate_pd_ch5_006(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    if err := (_auth_fail("PD-CH5-006", authority) or _require_mapping("PD-CH5-006", evidence)):
        return err
    cid = evidence.get("check_id")
    if not isinstance(cid, str) or not cid:
        return _missing_gate("PD-CH5-006", "check_id required")
    return validate_check_id(cid, caller_authority=CHECK_REG_AUTH)


def evaluate_pd_ch5_007(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_cache_lookup_must("PD-CH5-007", evidence, authority)


def evaluate_pd_ch5_008(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    if err := (_auth_fail("PD-CH5-008", authority) or _require_mapping("PD-CH5-008", evidence)):
        return err
    binding_digest = evidence.get("binding_digest")
    blocker_ids = evidence.get("blocker_ids")
    if (
        not isinstance(binding_digest, str)
        or not binding_digest.strip()
        or not isinstance(blocker_ids, Sequence)
        or isinstance(blocker_ids, (str, bytes))
    ):
        return _missing_gate("PD-CH5-008", "binding_digest and blocker_ids list required")
    auth_inv = evidence.get("authoritative_invalidation", False)
    if type(auth_inv) is not bool:
        return _missing_gate("PD-CH5-008", "authoritative_invalidation must be exact bool")
    return _with_explain_detail(
        GateCache().evaluate_blocker_invalidation(
            binding_digest,
            list(blocker_ids),
            additive_evidence_digest=evidence.get("additive_evidence_digest"),
            authoritative_invalidation=auth_inv,
            caller_authority=GATE_CACHE_AUTH,
        )
    )


def evaluate_pd_ch5_009(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    if err := (_auth_fail("PD-CH5-009", authority) or _require_mapping("PD-CH5-009", evidence)):
        return err
    declared = evidence.get("declared_key_digests")
    lookup = evidence.get("lookup_digests")
    comp = evidence.get("dependency_index_completeness")
    if (
        not isinstance(declared, Sequence)
        or isinstance(declared, (str, bytes))
        or not isinstance(lookup, Sequence)
        or isinstance(lookup, (str, bytes))
        or not isinstance(comp, str)
        or not comp.strip()
    ):
        return _missing_gate(
            "PD-CH5-009",
            "declared_key_digests, lookup_digests, and dependency_index_completeness required",
        )
    return _with_explain_detail(
        GateCache().evaluate_key_digests_and_dependency(
            list(declared),
            list(lookup),
            comp,
            cached_result_digest=evidence.get("cached_result_digest"),
            evaluator_record_ref=evidence.get("evaluator_record_ref"),
            caller_authority=GATE_CACHE_AUTH,
        )
    )


def evaluate_pd_ch5_010(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    if err := (_auth_fail("PD-CH5-010", authority) or _require_mapping("PD-CH5-010", evidence)):
        return err
    status = evidence.get("test_run_status")
    if not isinstance(status, str) or not status.strip():
        return _missing_gate("PD-CH5-010", "test_run_status required")
    if "retry_count" not in evidence or type(evidence.get("retry_count")) is not int:
        return _missing_gate("PD-CH5-010", "retry_count int required")
    if "flaky_disagreement" not in evidence or evidence.get("flaky_disagreement") is not False:
        return _missing_gate("PD-CH5-010", "flaky_disagreement must be explicitly False")
    retry_count = evidence["retry_count"]
    flaky = evidence["flaky_disagreement"]
    return _with_explain_detail(
        GateCache().evaluate_adapter_outcome(
            status,
            retry_count=retry_count,
            adapter_result_digest=evidence.get("adapter_result_digest"),
            flaky_disagreement=flaky,
            elapsed_ms=evidence.get("elapsed_ms"),
            caller_authority=GATE_CACHE_AUTH,
        )
    )


def _eval_f1_must(
    must_id: str, evidence: Mapping[str, Any], authority: Optional[str]
) -> GateOutput:
    if err := (_auth_fail(must_id, authority) or _require_mapping(must_id, evidence)):
        return err
    if "artifact" in evidence:
        raw_art = evidence["artifact"]
        if not isinstance(raw_art, Mapping):
            return _missing_gate(must_id, "artifact must be a Mapping")
        art: Dict[str, Any] = dict(raw_art)
        if isinstance(art.get("artifact"), Mapping):
            art["artifact"] = dict(art["artifact"])
        conf_art = evidence.get("confirmed_artifact")
        return evaluate_f1_representation(
            art,
            independent_verifier_result=evidence.get("independent_verifier_result"),
            confirmed_artifact=dict(conf_art) if isinstance(conf_art, Mapping) else conf_art,
            structural_diff_procedure=evidence.get("structural_diff_procedure"),
            authoritative_approval=evidence.get("authoritative_approval"),
            caller_authority=ARTIFACTS_AUTH,
        )
    art = dict(evidence)
    return evaluate_f1_representation(art, caller_authority=ARTIFACTS_AUTH)


def evaluate_pd_f1_001(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f1_must("PD-F1-001", evidence, authority)


def evaluate_pd_f1_002(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f1_must("PD-F1-002", evidence, authority)


def evaluate_pd_f1_003(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f1_must("PD-F1-003", evidence, authority)


def evaluate_pd_f1_004(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f1_must("PD-F1-004", evidence, authority)


def evaluate_pd_f1_005(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f1_must("PD-F1-005", evidence, authority)


def _eval_f2_must(
    must_id: str, evidence: Mapping[str, Any], authority: Optional[str]
) -> GateOutput:
    if err := (_auth_fail(must_id, authority) or _require_mapping(must_id, evidence)):
        return err
    if must_id == "PD-F2-007":
        if "bindings" in evidence:
            bindings = evidence["bindings"]
            resolver = evidence.get("resolver")
        else:
            bindings = evidence
            resolver = None
        if not isinstance(bindings, Mapping) or not bindings:
            return _missing_gate(must_id, "bindings Mapping required")
        ok, _, err_msg = resolve_frozen_bindings(bindings, resolver)
        if not ok:
            return _missing_gate(must_id, err_msg or "frozen binding resolution failed")
        return GateOutput(state=GateState.SATISFIED, detail="F2 frozen bindings resolved")

    if "spec" in evidence:
        spec = evidence["spec"]
        if not isinstance(spec, Mapping):
            return _missing_gate(must_id, "spec must be a Mapping")
        consumer = evidence.get("consumer")
        if not consumer or not isinstance(consumer, str):
            return _missing_gate(must_id, "consumer must be provided")
        res = evaluate_predicate_input(
            dict(spec),
            consumer=consumer,
            resolver=evidence.get("resolver"),
        )
    else:
        res = evaluate_predicate_input(dict(evidence))
    return res.gate_output


def evaluate_pd_f2_001(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f2_must("PD-F2-001", evidence, authority)


def evaluate_pd_f2_002(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f2_must("PD-F2-002", evidence, authority)


def evaluate_pd_f2_005(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f2_must("PD-F2-005", evidence, authority)


def evaluate_pd_f2_007(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f2_must("PD-F2-007", evidence, authority)


def _eval_f3_claim_must(
    must_id: str, evidence: Mapping[str, Any], authority: Optional[str]
) -> GateOutput:
    if err := (_auth_fail(must_id, authority) or _require_mapping(must_id, evidence)):
        return err
    if "candidate" in evidence:
        raw_cand = evidence["candidate"]
        if not isinstance(raw_cand, Mapping):
            return _missing_gate(must_id, "candidate must be a Mapping")
        return evaluate_claim(
            dict(raw_cand),
            check_record_source=evidence.get("check_record_source"),
            expected_object_digest=evidence.get("expected_object_digest"),
            expected_target_digest=evidence.get("expected_target_digest"),
        )
    return evaluate_claim(dict(evidence))


def evaluate_pd_f3_001(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f3_claim_must("PD-F3-001", evidence, authority)


def evaluate_pd_f3_002(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f3_claim_must("PD-F3-002", evidence, authority)


def evaluate_pd_f3_003(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    if err := (_auth_fail("PD-F3-003", authority) or _require_mapping("PD-F3-003", evidence)):
        return err
    if "structured_a" in evidence or "structured_b" in evidence:
        rep_a = evidence.get("structured_a")
        rep_b = evidence.get("structured_b")
    else:
        reps = evidence.get("representations")
        if not isinstance(reps, Sequence) or isinstance(reps, (str, bytes)) or len(reps) != 2:
            return _missing_gate(
                "PD-F3-003", "structured_a/structured_b or two representations required"
            )
        rep_a, rep_b = reps[0], reps[1]
    return check_structured_conflict(
        rep_a,
        rep_b,
        prose=evidence.get("prose"),
    )


def evaluate_pd_f3_004(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    if err := (_auth_fail("PD-F3-004", authority) or _require_mapping("PD-F3-004", evidence)):
        return err
    canon_digest = evidence.get("canonical_structured_form_digest")
    if not canon_digest or not isinstance(canon_digest, str):
        return _missing_gate("PD-F3-004", "canonical_structured_form_digest required")
    if "confirmation_event" in evidence or "requirement_confirmation" in evidence:
        req = evidence.get("confirmation_event") or evidence.get("requirement_confirmation")
    else:
        req = evidence
    return evaluate_requirement_confirmation(
        req,
        canonical_structured_form=evidence.get("canonical_structured_form"),
        canonical_structured_form_digest=canon_digest,
    )


def evaluate_pd_f3_005(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    if err := (_auth_fail("PD-F3-005", authority) or _require_mapping("PD-F3-005", evidence)):
        return err
    has_ccd = "claimed_content_digest" in evidence
    has_exp = "expected_digest" in evidence
    if has_ccd and has_exp and evidence.get("claimed_content_digest") != evidence.get("expected_digest"):
        return _missing_gate("PD-F3-005", "conflicting claimed digest keys supplied")
    digest = evidence.get("claimed_content_digest") if has_ccd else evidence.get("expected_digest")
    artifact = evidence.get("artifact") if "artifact" in evidence else evidence.get("content")
    if isinstance(artifact, Mapping):
        artifact = dict(artifact)
    return verify_content_digest(digest, artifact)


def evaluate_pd_f3_006(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    if err := (_auth_fail("PD-F3-006", authority) or _require_mapping("PD-F3-006", evidence)):
        return err
    rec = evidence.get("confirmation")
    if rec is None:
        rec = evidence
    if not isinstance(rec, Mapping):
        return _missing_gate("PD-F3-006", "confirmation must be a Mapping")
    return evaluate_confirmation_admissibility(
        confirmation_surface=rec.get("confirmation_surface"),
        principal_key_accessible_to_agent=rec.get("principal_key_accessible_to_agent"),
        approval_forwarding_tool_available=rec.get("approval_forwarding_tool_available"),
        user_presence_required=rec.get("user_presence_required"),
    )


def _eval_f4_must(
    must_id: str, evidence: Mapping[str, Any], authority: Optional[str]
) -> GateOutput:
    if err := (_auth_fail(must_id, authority) or _require_mapping(must_id, evidence)):
        return err
    return evaluate_f4_lane_selection(dict(evidence), authority=F4_AUTH)


def evaluate_pd_f4_001(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f4_must("PD-F4-001", evidence, authority)


def evaluate_pd_f4_002(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f4_must("PD-F4-002", evidence, authority)


def evaluate_pd_f4_003(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f4_must("PD-F4-003", evidence, authority)


def evaluate_pd_f4_004(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f4_must("PD-F4-004", evidence, authority)


def evaluate_pd_f4_005(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f4_must("PD-F4-005", evidence, authority)


def evaluate_pd_f4_006(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    if err := (_auth_fail("PD-F4-006", authority) or _require_mapping("PD-F4-006", evidence)):
        return err
    p_floor = evidence.get("policy_floor")
    prof_depth = evidence.get("profile_depth", evidence.get("profile_derived_depth"))
    valid_types = (str, DepthLevel)
    if not isinstance(p_floor, valid_types) or not isinstance(prof_depth, valid_types):
        return _missing_gate(
            "PD-F4-006", "policy_floor and profile_depth strings/DepthLevel required"
        )
    try:
        eff_depth, ind_floor = resolve_effective_depth(prof_depth, p_floor)
    except Exception as exc:
        return _missing_gate("PD-F4-006", f"invalid depth: {exc}")
    claimed = evidence.get("claimed_effective_depth")
    if claimed is not None:
        try:
            claimed_val = DepthLevel(claimed).value if not isinstance(claimed, DepthLevel) else claimed.value
        except Exception:
            claimed_val = str(claimed)
        if claimed_val != eff_depth:
            return _missing_gate(
                "PD-F4-006",
                f"claimed effective depth {claimed_val} != resolved {eff_depth}",
            )
    return GateOutput(
        state=GateState.SATISFIED,
        detail="Effective depth resolved",
        explain={"effective_depth": eff_depth, "independence_floor": ind_floor},
    )


_F5_REQUIRED_KEYS = (
    "phase",
    "canonical_state_binding",
    "pinned_guidance",
    "policy_version",
    "evaluator_version",
)


def _eval_f5_must(
    must_id: str, evidence: Mapping[str, Any], authority: Optional[str]
) -> GateOutput:
    if err := (_auth_fail(must_id, authority) or _require_mapping(must_id, evidence)):
        return err
    if any(k not in evidence for k in _F5_REQUIRED_KEYS):
        missing = [k for k in _F5_REQUIRED_KEYS if k not in evidence]
        return _missing_gate(must_id, f"missing F5 tuple fields: {missing}")
    res = evaluate_f5_gate(
        phase=evidence["phase"],
        canonical_state_binding=evidence["canonical_state_binding"],
        pinned_guidance=evidence["pinned_guidance"],
        policy_version=evidence["policy_version"],
        evaluator_version=evidence["evaluator_version"],
        evaluation_instant=evidence.get("evaluation_instant"),
        checks=evidence.get("checks"),
        relevant_input_digests=evidence.get("relevant_input_digests"),
        pinned_evaluator_version=evidence.get("pinned_evaluator_version"),
        timeout_ms=evidence.get("timeout_ms"),
        elapsed_ms=evidence.get("elapsed_ms"),
        budget_exhausted=bool(evidence.get("budget_exhausted", False)),
        kernel_decision=evidence.get("kernel_decision"),
        kernel_execution_gate=evidence.get("kernel_execution_gate"),
        skill_added_checks=evidence.get("skill_added_checks"),
        caller_authority=F5_AUTH,
    )
    return res.product_gate


def evaluate_pd_f5_001(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f5_must("PD-F5-001", evidence, authority)


def evaluate_pd_f5_002(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f5_must("PD-F5-002", evidence, authority)


def evaluate_pd_f5_003(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f5_must("PD-F5-003", evidence, authority)


def evaluate_pd_f5_004(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f5_must("PD-F5-004", evidence, authority)


def evaluate_pd_f5_005(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f5_must("PD-F5-005", evidence, authority)


def _eval_f6_must(
    must_id: str, evidence: Mapping[str, Any], authority: Optional[str]
) -> GateOutput:
    if err := (_auth_fail(must_id, authority) or _require_mapping(must_id, evidence)):
        return err
    if "spec" in evidence:
        raw_spec = evidence["spec"]
        if not isinstance(raw_spec, Mapping):
            return _missing_gate(must_id, "spec must be a Mapping")
        return evaluate_f6_traceability(
            dict(raw_spec),
            resolver=evidence.get("resolver"),
            freshness_predicate=evidence.get("freshness_predicate"),
            mode=str(evidence.get("mode", "realized")),
        )
    return evaluate_f6_traceability(dict(evidence))


def evaluate_pd_f6_001(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f6_must("PD-F6-001", evidence, authority)


def evaluate_pd_f6_002(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f6_must("PD-F6-002", evidence, authority)


def evaluate_pd_f6_003(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f6_must("PD-F6-003", evidence, authority)


def evaluate_pd_f6_004(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f6_must("PD-F6-004", evidence, authority)


def evaluate_pd_f6_005(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f6_must("PD-F6-005", evidence, authority)


def evaluate_pd_f6_006(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f6_must("PD-F6-006", evidence, authority)


def _eval_f7_must(
    must_id: str, evidence: Mapping[str, Any], authority: Optional[str]
) -> GateOutput:
    if err := (_auth_fail(must_id, authority) or _require_mapping(must_id, evidence)):
        return err
    if "claim" in evidence:
        raw_claim = evidence["claim"]
        claim_arg: Any = dict(raw_claim) if isinstance(raw_claim, Mapping) else raw_claim
        if not isinstance(claim_arg, (ClaimRecord, Mapping, str)):
            return _missing_gate(must_id, "claim must be ClaimRecord, Mapping, or str")
        return evaluate_f7_claim(
            claim_arg,
            repo_index=evidence.get("repo_index"),
            dependency_resolver=evidence.get("dependency_resolver"),
            evidence_resolver=evidence.get("evidence_resolver"),
            obligation_resolver=evidence.get("obligation_resolver"),
        )
    return evaluate_f7_claim(dict(evidence))


def evaluate_pd_f7_001(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f7_must("PD-F7-001", evidence, authority)


def evaluate_pd_f7_002(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f7_must("PD-F7-002", evidence, authority)


def evaluate_pd_f7_003(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f7_must("PD-F7-003", evidence, authority)


def evaluate_pd_f7_004(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f7_must("PD-F7-004", evidence, authority)


def evaluate_pd_f7_005(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f7_must("PD-F7-005", evidence, authority)


def evaluate_pd_f7_006(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    if err := (_auth_fail("PD-F7-006", authority) or _require_mapping("PD-F7-006", evidence)):
        return err
    claimed = evidence.get("claimed_symbols")
    post_delta = evidence.get("post_delta_symbols")
    if (
        not isinstance(claimed, Sequence)
        or isinstance(claimed, (str, bytes))
        or not claimed
        or not isinstance(post_delta, (set, frozenset, list, tuple))
    ):
        return _missing_gate(
            "PD-F7-006", "non-empty claimed_symbols sequence and post_delta_symbols set required"
        )
    return evaluate_pd_ch2_039_implementation_claims(
        list(claimed), set(post_delta), authority=P6_AUTH
    )


def _eval_f8_must(
    must_id: str, evidence: Mapping[str, Any], authority: Optional[str]
) -> GateOutput:
    if err := (_auth_fail(must_id, authority) or _require_mapping(must_id, evidence)):
        return err

    if (
        ("repeat_1_digest" in evidence and "repeat_2_digest" in evidence)
        or ("selected_items" in evidence and "repeat_selected_items" in evidence)
        or ("anchors" in evidence and "recomputed_anchors" in evidence)
        or ("golden_digest" in evidence and "computed_digest" in evidence)
    ):
        return evaluate_f8_step_pack(dict(evidence), caller_authority=F8_AUTH)

    if must_id == "PD-F8-002":
        items = evidence.get("items")
        item_bytes = evidence.get("item_bytes")
        precedence = evidence.get("precedence")
        budget = evidence.get("byte_budget")
        if (
            not isinstance(items, Sequence)
            or isinstance(items, (str, bytes))
            or not isinstance(item_bytes, Mapping)
            or not isinstance(precedence, Sequence)
            or isinstance(precedence, (str, bytes))
            or type(budget) is not int
            or budget < 0
        ):
            return _missing_gate(
                must_id, "items, item_bytes, precedence, and int byte_budget required"
            )
        selected = truncate_context_items(items, item_bytes, precedence, budget)
        total = sum(int(item_bytes[it]) for it in selected if it in item_bytes)
        if total > budget:
            return _missing_gate(must_id, "truncated items exceeded byte budget")
        return GateOutput(
            state=GateState.SATISFIED,
            detail="F8 truncation bounded",
            explain={"selected_items": list(selected), "total_bytes": total},
        )

    if must_id == "PD-F8-003":
        binding = evidence.get("canonical_state_binding")
        anchors = evidence.get("anchors")
        if (
            not isinstance(binding, str)
            or not binding.strip()
            or not isinstance(anchors, Sequence)
            or isinstance(anchors, (str, bytes))
            or not anchors
        ):
            return _missing_gate(must_id, "canonical_state_binding and anchors required")
        if "transcript_present" not in evidence or type(evidence.get("transcript_present")) is not bool:
            return _missing_gate(must_id, "transcript_present boolean required")
        transcript_present = evidence["transcript_present"]
        res_anchors, digest = resume_step_pack(
            binding, list(anchors), transcript_present=transcript_present
        )
        if list(res_anchors) != list(anchors):
            return _missing_gate(must_id, "resumed anchors differ from canonical anchors")
        return GateOutput(
            state=GateState.SATISFIED,
            detail="F8 canonical resume valid",
            explain={"step_pack_digest": digest},
        )

    pack_args = evidence.get("step_pack_args")
    if not isinstance(pack_args, Mapping) or not pack_args:
        return _missing_gate(must_id, "step_pack_args Mapping required")
    try:
        pack = compile_step_pack(**dict(pack_args))
    except Exception as exc:
        return _missing_gate(must_id, f"compile_step_pack failed: {exc}")
    exp_digest = evidence.get("expected_digest")
    if must_id == "PD-F8-004":
        if exp_digest is None or not isinstance(exp_digest, str):
            return _missing_gate(must_id, "expected_digest required")
        if pack.step_pack_digest != exp_digest:
            return _missing_gate(
                must_id,
                f"compiled digest {pack.step_pack_digest} != expected {exp_digest}",
            )
    elif exp_digest is not None and pack.step_pack_digest != exp_digest:
        return _missing_gate(
            must_id,
            f"compiled digest {pack.step_pack_digest} != expected {exp_digest}",
        )
    return GateOutput(
        state=GateState.SATISFIED,
        detail="F8 step pack compiled",
        explain={"step_pack_digest": pack.step_pack_digest},
    )


def evaluate_pd_f8_001(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f8_must("PD-F8-001", evidence, authority)


def evaluate_pd_f8_002(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f8_must("PD-F8-002", evidence, authority)


def evaluate_pd_f8_003(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f8_must("PD-F8-003", evidence, authority)


def evaluate_pd_f8_004(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f8_must("PD-F8-004", evidence, authority)


def _eval_f9_must(
    must_id: str, evidence: Mapping[str, Any], authority: Optional[str]
) -> GateOutput:
    if err := (_auth_fail(must_id, authority) or _require_mapping(must_id, evidence)):
        return err
    arg: Any
    if "envelope" in evidence:
        raw_env = evidence["envelope"]
        if isinstance(raw_env, ProductMetricEnvelope):
            arg = raw_env
        elif isinstance(raw_env, Mapping):
            try:
                arg = ProductMetricEnvelope(
                    envelope_version=raw_env.get("envelope_version", "1.0"),
                    report=dict(raw_env["report"]) if isinstance(raw_env.get("report"), Mapping) else raw_env.get("report"),  # type: ignore[arg-type]
                    event_basis=raw_env.get("event_basis", ""),
                    pair_id=raw_env.get("pair_id"),
                )
            except Exception as exc:
                return _missing_gate(must_id, f"invalid ProductMetricEnvelope: {exc}")
        else:
            return _missing_gate(must_id, "envelope must be ProductMetricEnvelope or Mapping")
    else:
        arg = dict(evidence)
    out = evaluate_f9_metric(arg, caller_authority=METRICS_AUTH)
    if out.state != GateState.SATISFIED and out.must_id is None:
        return _missing_gate(must_id, out.detail or "F9 evaluation failed")
    return out


def evaluate_pd_f9_001(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f9_must("PD-F9-001", evidence, authority)


def evaluate_pd_f9_002(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f9_must("PD-F9-002", evidence, authority)


def evaluate_pd_f9_003(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f9_must("PD-F9-003", evidence, authority)


def evaluate_pd_f9_004(
    evidence: Mapping[str, Any], *, authority: Optional[str] = None
) -> GateOutput:
    return _eval_f9_must("PD-F9-004", evidence, authority)


def evaluate_pd_ch2_053(
    evidence: Mapping[str, Any],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-053 adapter: maps ReleaseEvaluationOutput from lifecycle_p3c_p8_p10 to GateOutput."""
    auth_out = _auth_fail("PD-CH2-053", authority)
    if auth_out is not None:
        return auth_out
    req_out = _require_mapping("PD-CH2-053", evidence)
    if req_out is not None:
        return req_out

    kernel_eval = evidence.get("kernel_release_evaluation")
    if not isinstance(kernel_eval, str) or not kernel_eval.strip():
        return _missing_gate("PD-CH2-053", "kernel_release_evaluation must be a non-empty string")

    product_checks_pass = evidence.get("product_checks_pass")
    if product_checks_pass is None:
        return _missing_gate("PD-CH2-053", "product_checks_pass is required and cannot be omitted")
    if type(product_checks_pass) is not bool:
        return _missing_gate("PD-CH2-053", "product_checks_pass must be an exact boolean")

    from sclass.product.lifecycle_p3c_p8_p10 import (
        QUALIFIED_EVALUATOR_BOUNDARY as P10_AUTH,
        evaluate_pd_ch2_053_p10_kernel_release_evaluation,
    )
    res = evaluate_pd_ch2_053_p10_kernel_release_evaluation(
        kernel_release_evaluation=kernel_eval,
        product_checks_pass=product_checks_pass,
        authority=P10_AUTH,
    )
    if res.status == "SATISFIED":
        return GateOutput(
            state=GateState.SATISFIED,
            must_id="PD-CH2-053",
            detail=res.detail,
        )
    return GateOutput(
        state=GateState.MISSING,
        must_id="PD-CH2-053",
        detail=res.detail,
        failures=list(res.failures) if res.failures else [f"MISSING[PD-CH2-053]"],
    )

