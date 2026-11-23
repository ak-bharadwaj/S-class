"""W1 / W2 tests: comprehensive matrix over all 54 registry_adapters wrappers and 195 MUSTs."""
from __future__ import annotations

import hashlib
import pathlib
import sys
from typing import Any, Dict

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
for _p in (_REPO_ROOT / "src", _REPO_ROOT / "10-CONFORMANCE", _REPO_ROOT / "tools"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from uncovered_76_payloads import UNCOVERED_HAPPY_PAYLOADS

from sclass import canonical_c1
from sclass.product import REGISTRY_AUTHORITY, evaluate, list_musts
from sclass.product.artifacts import freeze_to_c1_compatible
from sclass.product.check_registry import get_registry
from sclass.product.claim_ledger import (
    InMemoryCanonicalDependencyResolver,
    InMemoryKernelEvidenceResolver,
    InMemoryObligationClosureResolver,
    InMemoryRepositoryIntelligenceIndex,
)
from sclass.product.gate import GateOutput, GateState
from sclass.product.oss_qualification_playbook import REQUIRED_PLAYBOOK_PHASES
from sclass.product.predicate_evaluator import (
    AcceptanceContract,
    Constraint,
    ConstraintType,
    Digest,
    InMemoryFrozenResolver,
    Requirement,
    VerificationStep,
)
from sclass.product.registry_table import REGISTRY_TABLE_ROWS
from sclass.product.traceability import InMemorySourceRefResolver
from sclass.product.trust_model import CheckRecord, InMemoryCheckRecordSource
from sclass_semantics_v6_0_1 import (
    Authority,
    CompositionMode,
    DiscoveryMethod,
    EnforcementPhase,
    EvidenceComposition,
    EvidenceKind,
    IndependenceLevel,
    IndependenceProfile,
    RequiredEvidence,
    ResourceBudget,
    Severity,
    SourceType,
    WaiverRules,
)


def _sha256_hex(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _c1_digest(obj: Any) -> str:
    return hashlib.sha256(canonical_c1(freeze_to_c1_compatible(obj))).hexdigest()


def _build_frozen_resolver() -> InMemoryFrozenResolver:
    req = Requirement(
        requirement_id="REQ-1",
        description="Functional requirement",
        authority=Authority.USER,
        source_type=SourceType.USER_INPUT,
        source_provenance=Digest("sha256:" + "a" * 64),
        discovery_method=DiscoveryMethod.USER_STATED,
        confidence_bp=10000,
        objective_revision="rev-1",
        parent_requirement=None,
        derived_obligations=(),
    )
    con = Constraint(
        constraint_id="CON-1",
        description="Safety constraint",
        constraint_type=ConstraintType.SECURITY,
        authority=Authority.POLICY,
        enforcement_phase=EnforcementPhase.EXECUTION,
        severity=Severity.BLOCKING,
        scope=(),
        version=1,
    )
    ind = IndependenceProfile(
        IndependenceLevel.NONE,
        IndependenceLevel.NONE,
        IndependenceLevel.NONE,
        IndependenceLevel.NONE,
        IndependenceLevel.NONE,
    )
    req_ev = RequiredEvidence(
        "req-key-1", EvidenceKind.BEHAVIORAL, "verifier-1", ind, (), True, 1
    )
    comp = EvidenceComposition(CompositionMode.ALL_OF, 0)
    ac = AcceptanceContract(
        "AC-1", "obl-1", 1, (req_ev,), comp, WaiverRules((), 1000, False), Authority.USER
    )
    budget = ResourceBudget(10, 10, 10, 1000, 10, 10, 10, 10, 10, 5000, 10)
    vs = VerificationStep(
        step_id="VS-1",
        evidence_kind=EvidenceKind.BEHAVIORAL,
        verifier_id="verifier-1",
        verifier_version="1.0",
        config_digest=Digest("sha256:" + "c" * 64),
        timeout_ms=5000,
        budget=budget,
    )
    return InMemoryFrozenResolver(
        {"REQ-1": req, "CON-1": con, "AC-1": ac, "VS-1": vs}
    )


_FROZEN_RESOLVER = _build_frozen_resolver()

_CH5_CACHE_ENTRY: Dict[str, Any] = {
    "phase": "P5",
    "canonical_state_binding": {"policy_version": "v1", "target": "t1"},
    "task_ref": "TASK-CH5",
    "spec_anchor_digest": _sha256_hex("ch5-spec"),
    "input_digests": [_sha256_hex("ch5-in-1")],
    "pinned_guidance": _sha256_hex("ch5-guidance-v1"),
    "policy_version": "v1",
    "evaluator_version": "eval-1.0",
    "evaluation_instant": "2026-11-22T00:00:00Z",
}

_F1_HAPPY: Dict[str, Any] = {
    "artifact": {
        "artifact_class": "data",
        "contract": {"schema": "v1"},
        "positive": {"input": 1},
        "negative": {"input": -1, "observed": "rejected"},
        "agent_result": "PASS",
    },
    "independent_verifier_result": "PASS",
}

_F2_PRED_HAPPY: Dict[str, Any] = {
    "spec": {
        "input_tokens": [
            "IDENT(x)",
            "GREATER_OR_EQUAL",
            "INTEGER(1)",
            "AND",
            "IDENT(x)",
            "LESS_THAN",
            "INTEGER(5)",
        ],
        "schema": {"x": {"type": "Int", "domain": [0, 1, 2, 3, 4, 5]}},
        "predicate": "x GREATER_OR_EQUAL 1 AND x LESS_THAN 5",
    },
    "consumer": "p3_invariant",
}

_F3_CHECK_SRC = InMemoryCheckRecordSource(
    [
        CheckRecord(
            check_id="CHK-F3-1",
            producer="evaluator",
            status="PASS",
            object_digest="obj-d1",
            target_digest="tgt-d1",
        )
    ]
)

_F3_CLAIM_HAPPY: Dict[str, Any] = {
    "candidate": {"claim_id": "CL-1", "status": "PASS"},
    "check_record_source": _F3_CHECK_SRC,
    "expected_object_digest": "obj-d1",
    "expected_target_digest": "tgt-d1",
}

_F3_FORM: Dict[str, Any] = {"requirement_id": "REQ-1", "clause": "must verify digest"}
_F3_FORM_DIGEST = _c1_digest(_F3_FORM)

_F4_HAPPY: Dict[str, Any] = {
    "requested_lane": "STANDARD",
    "profile_derived_depth": "D1",
    "policy_floor": "D1",
}

_F5_HAPPY: Dict[str, Any] = {
    "phase": "P5",
    "canonical_state_binding": {"target": "t1"},
    "pinned_guidance": {"skill": "s1"},
    "policy_version": "v1",
    "evaluator_version": "1.0",
    "evaluation_instant": "2026-11-22T00:00:00Z",
}

_F6_SPEC: Dict[str, Any] = {
    "nodes": ["REQ-1", "ACC-1", "VER-1", "TEST-1", "EV-1", "OBL-1"],
    "obligations": ["OBL-1"],
    "source_refs": ["REQ-1", "OBL-1"],
    "links": [
        {
            "link_type": "REQUIREMENT_TO_ACCEPTANCE",
            "source": "REQ-1",
            "destination": "ACC-1",
        },
        {
            "link_type": "ACCEPTANCE_TO_VERIFICATION",
            "source": "ACC-1",
            "destination": "VER-1",
        },
        {
            "link_type": "VERIFICATION_TO_TEST",
            "source": "VER-1",
            "destination": "TEST-1",
        },
        {
            "link_type": "TEST_TO_EVIDENCE",
            "source": "TEST-1",
            "destination": "EV-1",
        },
        {
            "link_type": "EVIDENCE_TO_OBLIGATION",
            "source": "EV-1",
            "destination": "OBL-1",
        },
    ],
}

_F6_HAPPY: Dict[str, Any] = {
    "spec": _F6_SPEC,
    "resolver": InMemorySourceRefResolver({"REQ-1": {"id": "REQ-1"}, "OBL-1": {"id": "OBL-1"}}),
    "freshness_predicate": lambda _nid: True,
    "mode": "realized",
}

_F7_HAPPY: Dict[str, Any] = {
    "claim": {
        "claim_id": "CL-F7-1",
        "type": "behavioral",
        "subject": "fn_x",
        "evidence_refs": ["EV-REF-1"],
        "created_by_delta": False,
    },
    "evidence_resolver": InMemoryKernelEvidenceResolver(["EV-REF-1"]),
    "repo_index": InMemoryRepositoryIntelligenceIndex(
        pre_delta_symbols=["fn_x"], post_delta_overlay=["fn_x"]
    ),
    "dependency_resolver": InMemoryCanonicalDependencyResolver({"pkg_a": "sha256:d1"}),
    "obligation_resolver": InMemoryObligationClosureResolver(["OBL-1"]),
}

_F8_STEP_PACK_ARGS: Dict[str, Any] = {
    "phase": "P5",
    "task_ref": "TASK-10",
    "canonical_state_binding": "SB-10",
    "pinned_skills": ["SK-1", "SK-2"],
    "context_budget_bytes": 4096,
}

HAPPY_EVIDENCE_BY_MUST: Dict[str, Dict[str, Any]] = {
    "PD-CH5-003": {
        "cached_entry": dict(_CH5_CACHE_ENTRY),
        "evaluation_tuple": dict(_CH5_CACHE_ENTRY),
    },
    "PD-CH5-004": {
        "claim": "p95 latency <= 50ms",
        "benchmark_corpus": "corpus-v1",
        "measurement_window": "2026-11-01/2026-11-22",
        "corpus_digest": "sha256:c1",
        "unit": "ms",
        "percentile": "p95",
        "sample_count": 100,
        "measured_result": 42.0,
    },
    "PD-CH5-005": {"numerator": 5, "denominator": 0},
    "PD-CH5-006": {"check_id": next(iter(get_registry().keys()))},
    "PD-CH5-007": {
        "cached_entry": dict(_CH5_CACHE_ENTRY),
        "evaluation_tuple": dict(_CH5_CACHE_ENTRY),
    },
    "PD-CH5-008": {
        "binding_digest": _sha256_hex("binding-10"),
        "blocker_ids": [],
        "authoritative_invalidation": True,
        "additive_evidence_digest": _sha256_hex("additive-10"),
    },
    "PD-CH5-009": {
        "declared_key_digests": [_sha256_hex("k1"), _sha256_hex("k2")],
        "lookup_digests": [_sha256_hex("k1"), _sha256_hex("k2")],
        "dependency_index_completeness": "complete",
        "cached_result_digest": _sha256_hex("res-12"),
        "evaluator_record_ref": "EVAL-CH5-009",
    },
    "PD-CH5-010": {
        "test_run_status": "PASSED",
        "retry_count": 1,
        "adapter_result_digest": _sha256_hex("run-14"),
        "flaky_disagreement": False,
        "elapsed_ms": 120,
    },
    "PD-F1-001": dict(_F1_HAPPY),
    "PD-F1-002": dict(_F1_HAPPY),
    "PD-F1-003": dict(_F1_HAPPY),
    "PD-F1-004": dict(_F1_HAPPY),
    "PD-F1-005": {
        "artifact": {
            "artifact_class": "data",
            "contract": {"schema": "v1"},
            "confirmed": {"min": 1},
            "proposed": {"min": 2},
        },
        "confirmed_artifact": {"min": 1},
        "structural_diff_procedure": lambda _c, _p: False,
    },
    "PD-F2-001": dict(_F2_PRED_HAPPY),
    "PD-F2-002": dict(_F2_PRED_HAPPY),
    "PD-F2-005": dict(_F2_PRED_HAPPY),
    "PD-F2-007": {
        "bindings": {
            "requirement_ref": "REQ-1",
            "constraint_ref": "CON-1",
            "acceptance_contract_ref": "AC-1",
            "verification_step_ref": "VS-1",
        },
        "resolver": _FROZEN_RESOLVER,
    },
    "PD-F3-001": dict(_F3_CLAIM_HAPPY),
    "PD-F3-002": dict(_F3_CLAIM_HAPPY),
    "PD-F3-003": {
        "structured_a": {"rule": "max_retries", "limit": 3},
        "structured_b": {"rule": "max_retries", "limit": 3},
        "prose": "ignored prose explanation",
    },
    "PD-F3-004": {
        "confirmation_event": {
            "event_type": "REQUIREMENT_CONFIRMED",
            "authority": "USER",
            "source_provenance": _F3_FORM_DIGEST,
        },
        "canonical_structured_form": dict(_F3_FORM),
        "canonical_structured_form_digest": _F3_FORM_DIGEST,
    },
    "PD-F3-005": {
        "artifact": dict(_F3_FORM),
        "claimed_content_digest": _F3_FORM_DIGEST,
    },
    "PD-F3-006": {
        "confirmation": {
            "confirmation_surface": "host_native",
            "principal_key_accessible_to_agent": False,
            "approval_forwarding_tool_available": False,
            "user_presence_required": True,
        }
    },
    "PD-F4-001": dict(_F4_HAPPY),
    "PD-F4-002": dict(_F4_HAPPY),
    "PD-F4-003": dict(_F4_HAPPY),
    "PD-F4-004": dict(_F4_HAPPY),
    "PD-F4-005": dict(_F4_HAPPY),
    "PD-F4-006": {"profile_depth": "D1", "policy_floor": "D2"},
    "PD-F5-001": dict(_F5_HAPPY),
    "PD-F5-002": dict(_F5_HAPPY),
    "PD-F5-003": dict(_F5_HAPPY),
    "PD-F5-004": dict(_F5_HAPPY),
    "PD-F5-005": dict(_F5_HAPPY),
    "PD-F6-001": dict(_F6_HAPPY),
    "PD-F6-002": dict(_F6_HAPPY),
    "PD-F6-003": dict(_F6_HAPPY),
    "PD-F6-004": dict(_F6_HAPPY),
    "PD-F6-005": dict(_F6_HAPPY),
    "PD-F6-006": dict(_F6_HAPPY),
    "PD-F7-001": dict(_F7_HAPPY),
    "PD-F7-002": dict(_F7_HAPPY),
    "PD-F7-003": dict(_F7_HAPPY),
    "PD-F7-004": dict(_F7_HAPPY),
    "PD-F7-005": dict(_F7_HAPPY),
    "PD-F7-006": {
        "claimed_symbols": ["sym_a", "sym_b"],
        "post_delta_symbols": ["sym_a", "sym_b", "sym_c"],
    },
    "PD-F8-001": {"step_pack_args": dict(_F8_STEP_PACK_ARGS)},
    "PD-F8-002": {
        "items": ["it1", "it2"],
        "item_bytes": {"it1": 100, "it2": 200},
        "precedence": ["it1", "it2"],
        "byte_budget": 250,
    },
    "PD-F8-003": {
        "canonical_state_binding": "SB-10",
        "anchors": ["REQ-1", "OBL-1", "VS-1"],
        "transcript_present": False,
    },
    "PD-F8-004": {
        "step_pack_args": dict(_F8_STEP_PACK_ARGS),
        "expected_digest": "D-F8-1",
    },
    "PD-F9-001": {"events": ["EV-1", "EV-2"]},
    "PD-F9-002": {
        "envelope": {
            "envelope_version": "1.0",
            "event_basis": "canonical_event_stream",
            "report": {"numerator": 8, "denominator": 10},
        }
    },
    "PD-F9-003": {
        "paired_evaluation": True,
        "false_completion_rate_old": 0.05,
        "false_completion_rate_new": 0.04,
        "false_block_rate_old": 0.05,
        "false_block_rate_new": 0.04,
    },
    "PD-F9-004": {
        "canonical_cost": 10,
        "canonical_time_seconds": 20,
        "agent_reported_cost": 1,
        "agent_reported_time_seconds": 2,
        "expected_metric_cost": 10,
        "expected_metric_time_seconds": 20,
    },
    "PD-CH10-007": {
        "cross_linked_to_master": True,
        "unknown_references_present": False,
    },
    "PD-CH6-003": {
        "scope_specific_qualification": True,
        "effective_revocation_present": False,
    },
    "PD-CH6-006": {
        "playbook_content": {
            "phases": list(REQUIRED_PLAYBOOK_PHASES),
            "unqualified_adapter_claimed_usable": False,
        }
    },
}

VIOLATING_EVIDENCE_BY_MUST: Dict[str, Dict[str, Any]] = {
    "PD-CH5-003": {
        "cached_entry": dict(_CH5_CACHE_ENTRY),
        "evaluation_tuple": {**_CH5_CACHE_ENTRY, "pinned_guidance": _sha256_hex("changed")},
    },
    "PD-CH5-004": {"claim": "fast latency", "benchmark_corpus": "absent"},
    "PD-CH5-005": {"numerator": 5, "denominator": None},
    "PD-CH5-006": {"check_id": "HAND_CREATED_INVALID_CHECK"},
    "PD-CH5-007": {
        "cached_entry": dict(_CH5_CACHE_ENTRY),
        "evaluation_tuple": {k: v for k, v in _CH5_CACHE_ENTRY.items() if k != "policy_version"},
    },
    "PD-CH5-008": {
        "binding_digest": _sha256_hex("binding-9"),
        "blocker_ids": ["BLK-1"],
        "authoritative_invalidation": False,
    },
    "PD-CH5-009": {
        "declared_key_digests": ["d1", "d2"],
        "lookup_digests": ["d1"],
        "dependency_index_completeness": "complete",
        "cached_result_digest": "r1",
        "evaluator_record_ref": "EVAL-1",
    },
    "PD-CH5-010": {
        "test_run_status": "TIMEOUT",
        "retry_count": 1,
        "adapter_result_digest": "d1",
    },
    "PD-F1-001": {"artifact": {"prose_only": "looks good"}},
    "PD-F1-002": {"artifact": {"artifact_class": "data", "agent_result": "PASS"}},
    "PD-F1-003": {"artifact": {"artifact_class": "data"}},
    "PD-F1-004": {
        "artifact": {
            "artifact_class": "data",
            "contract": {"schema": "v1"},
            "positive": {"x": 1},
            "negative": {"x": -1, "observed": "accepted"},
        }
    },
    "PD-F1-005": {
        "artifact": {
            "artifact_class": "data",
            "contract": {"schema": "v1"},
            "confirmed": {"min": 2},
            "proposed": {"min": 1},
        }
    },
    "PD-F2-001": {"predicate": "x @@ INVALID_TOKEN 5"},
    "PD-F2-002": {"predicate": "x GREATER_THAN 1"},
    "PD-F2-005": {"predicate": "ALWAYS EVENTUALLY x EQUALS 1"},
    "PD-F2-007": {"bindings": {"requirement_ref": "REQ-1"}},
    "PD-F3-001": {"candidate": {"verified": True, "status": "PASS"}},
    "PD-F3-002": {
        "candidate": {
            "check_records": [{"producer": "agent", "status": "PASS"}],
        }
    },
    "PD-F3-003": {
        "structured_a": {"limit": 3},
        "structured_b": {"limit": 5},
    },
    "PD-F3-004": {
        "confirmation_event": {
            "event_type": "REQUIREMENT_CONFIRMED",
            "authority": "USER",
            "source_provenance": "wrong_digest",
        },
        "canonical_structured_form": dict(_F3_FORM),
    },
    "PD-F3-005": {
        "artifact": dict(_F3_FORM),
        "claimed_content_digest": "0" * 64,
    },
    "PD-F3-006": {
        "confirmation": {
            "confirmation_surface": "host_native",
            "principal_key_accessible_to_agent": True,
            "approval_forwarding_tool_available": False,
            "user_presence_required": True,
        }
    },
    "PD-F4-001": {"requested_lane": "UNKNOWN_LANE"},
    "PD-F4-002": {"requested_lane": "FAST", "security_sensitive": True},
    "PD-F4-003": {
        "requested_lane": "STANDARD",
        "f1_artifact_class": "data",
        "f1_required_representation": "DDL",
        "ddl_present": False,
    },
    "PD-F4-004": {"requested_lane": "STANDARD", "budget_exhausted": True},
    "PD-F4-005": {"profile_derived_depth": "D2"},
    "PD-F4-006": {
        "profile_depth": "D1",
        "policy_floor": "D3",
        "claimed_effective_depth": "D1",
    },
    "PD-F5-001": {**_F5_HAPPY, "evaluation_instant": ""},
    "PD-F5-002": {
        **_F5_HAPPY,
        "checks": [{"check_id": "C1", "must_id": "PD-F5-002", "status": "MISSING"}],
    },
    "PD-F5-003": {**_F5_HAPPY, "budget_exhausted": True},
    "PD-F5-004": {**_F5_HAPPY, "pinned_evaluator_version": "2.0"},
    "PD-F5-005": {
        **_F5_HAPPY,
        "skill_added_checks": [{"check_id": "SK-1", "must_id": "PD-F5-005", "status": "MISSING"}],
    },
    "PD-F6-001": {"spec": _F6_SPEC},
    "PD-F6-002": {**_F6_HAPPY, "spec": {**_F6_SPEC, "orphan_nodes": ["REQ-ORPHAN"]}},
    "PD-F6-003": {"spec": {"nodes": ["REQ-1"], "links": []}},
    "PD-F6-004": {
        **_F6_HAPPY,
        "spec": {
            **_F6_SPEC,
            "agent_claimed_coverage_percent": 100,
            "missing_link": {"type": "TEST_TO_EVIDENCE"},
        },
    },
    "PD-F6-005": {
        "spec": _F6_SPEC,
        "resolver": _F6_HAPPY["resolver"],
        "freshness_predicate": lambda _nid: False,
    },
    "PD-F6-006": {
        **_F6_HAPPY,
        "spec": {
            "nodes": ["REQ-1", "ACC-1", "VER-1", "TEST-1"],
            "obligations": ["OBL-1"],
            "source_refs": ["REQ-1"],
            "links": _F6_SPEC["links"][:3],
        },
    },
    "PD-F7-001": {"claim": "prose-only claim is rejected"},
    "PD-F7-002": {
        "claim": {
            "claim_id": "CL-1",
            "type": "behavioral",
            "subject": "fn_x",
            "evidence_refs": [],
            "created_by_delta": False,
        }
    },
    "PD-F7-003": {
        "claim": {
            "claim_id": "CL-1",
            "type": "reference",
            "subject": "missing_pkg",
            "reference_kind": "package",
            "created_by_delta": False,
        }
    },
    "PD-F7-004": {
        "claim": {
            "claim_id": "CL-1",
            "type": "reference",
            "subject": "missing_sym",
            "reference_kind": "symbol",
            "created_by_delta": False,
            "target_snapshot_ref": "SNAP-1",
        },
        "repo_index": InMemoryRepositoryIntelligenceIndex(pre_delta_symbols=[]),
    },
    "PD-F7-005": {
        "claim": {
            "claim_id": "CL-1",
            "type": "INVALID_CLAIM_TYPE",
            "subject": "fn_x",
            "created_by_delta": False,
        }
    },
    "PD-F7-006": {
        "claimed_symbols": ["sym_missing"],
        "post_delta_symbols": ["sym_a"],
    },
    "PD-F8-001": {"repeat_1_digest": "D1", "repeat_2_digest": "D2"},
    "PD-F8-002": {"selected_items": ["a"], "repeat_selected_items": ["b"]},
    "PD-F8-003": {"anchors": ["REQ-1"], "recomputed_anchors": ["REQ-2"]},
    "PD-F8-004": {
        "step_pack_args": dict(_F8_STEP_PACK_ARGS),
        "expected_digest": "WRONG-DIGEST",
    },
    "PD-F9-001": {"events": []},
    "PD-F9-002": {"numerator": 5, "denominator": None},
    "PD-F9-003": {"paired_evaluation": False},
    "PD-F9-004": {
        "canonical_cost": 10,
        "canonical_time_seconds": 20,
        "agent_reported_cost": 1,
        "expected_metric_cost": 1,
    },
    "PD-CH10-007": {
        "cross_linked_to_master": False,
        "unknown_references_present": True,
    },
    "PD-CH6-003": {
        "scope_specific_qualification": False,
        "effective_revocation_present": True,
    },
    "PD-CH6-006": {
        "playbook_content": {
            "phases": ["P0", "P1"],
            "unqualified_adapter_claimed_usable": True,
        }
    },
}

for _mid, _ev in UNCOVERED_HAPPY_PAYLOADS.items():
    if _mid != "PD-CH2-053" and _mid not in HAPPY_EVIDENCE_BY_MUST:
        HAPPY_EVIDENCE_BY_MUST[_mid] = _ev


def test_pd_f3_005_fail_before_truthiness_bug_and_fix() -> None:
    """Fail-before proof for W1 (PD-F3-005): GateOutput is always truthy even when MISSING."""
    bad_ev = {
        "artifact": dict(_F3_FORM),
        "claimed_content_digest": "0" * 64,
        "adapter_qualified": True,  # TEST-ONLY QUALIFICATION
    }
    out = evaluate("PD-F3-005", bad_ev, authority=REGISTRY_AUTHORITY)
    # Fail-before demonstration: bool(out) is True even on GateState.MISSING!
    assert bool(out) is True
    # Fixed behavior: out.state is GateState.MISSING, never SATISFIED.
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-F3-005"


def test_all_195_musts_empty_and_engine_gating() -> None:
    """(a) Valid/engine-gated behavior across all 195 MUSTs; (b) empty evidence never SATISFIED."""
    rows_by_id = {r["must_id"]: r for r in REGISTRY_TABLE_ROWS}
    assert len(rows_by_id) == 195

    for entry in list_musts():
        mid = entry.must_id
        row = rows_by_id[mid]

        # (b) Empty evidence never returns SATISFIED
        empty_out = evaluate(mid, {}, authority=REGISTRY_AUTHORITY)
        assert empty_out.state != GateState.SATISFIED, f"{mid} SATISFIED on empty evidence"

        # (a) Engine-gated MUST without adapter_qualified=True must return MISSING (ENGINE_NOT_QUALIFIED)
        if row["needs_engine"]:
            base_ev = dict(HAPPY_EVIDENCE_BY_MUST.get(mid, {"probe": "unqualified"}))
            base_ev.pop("adapter_qualified", None)
            gated_out = evaluate(mid, base_ev, authority=REGISTRY_AUTHORITY)
            assert gated_out.state == GateState.MISSING, f"{mid} did not fail closed without engine qualification"
            assert gated_out.detail == "ENGINE_NOT_QUALIFIED", f"{mid} detail={gated_out.detail}"


def test_all_54_registry_adapters_and_former_survivors_happy_and_violating() -> None:
    """Every registry_adapters wrapper (+ PD-CH10-007, PD-CH6-003, PD-CH6-006) passes happy and fails violating."""
    rows_by_id = {r["must_id"]: r for r in REGISTRY_TABLE_ROWS}
    adapter_ids = {
        r["must_id"]
        for r in REGISTRY_TABLE_ROWS
        if r["module"] == "sclass.product.registry_adapters"
    }
    assert len(adapter_ids) == 54
    assert adapter_ids.issubset(set(HAPPY_EVIDENCE_BY_MUST.keys()))
    assert adapter_ids.issubset(set(VIOLATING_EVIDENCE_BY_MUST.keys()))

    for mid, happy_ev in sorted(HAPPY_EVIDENCE_BY_MUST.items()):
        row = rows_by_id[mid]
        ev = dict(happy_ev)
        if row["needs_engine"]:
            ev["adapter_qualified"] = True  # TEST-ONLY QUALIFICATION
        out_happy = evaluate(mid, ev, authority=REGISTRY_AUTHORITY)
        assert (
            out_happy.state == GateState.SATISFIED
        ), f"{mid} happy failed: {out_happy} ({out_happy.detail})"

        if mid in VIOLATING_EVIDENCE_BY_MUST:
            viol_ev = dict(VIOLATING_EVIDENCE_BY_MUST[mid])
            if row["needs_engine"]:
                viol_ev["adapter_qualified"] = True  # TEST-ONLY QUALIFICATION
            out_viol = evaluate(mid, viol_ev, authority=REGISTRY_AUTHORITY)
            assert (
                out_viol.state != GateState.SATISFIED
            ), f"{mid} violating unexpectedly SATISFIED: {out_viol}"
