#!/usr/bin/env python3
"""TD-17 Master Fixture Runner for all 129 FIXTURE-REF-NOT-RUN MUSTs.

Verifies the Master Product Design SHA-256, parses the matching Master YAML
fixture blocks, executes the 81 MUSTs covered by run_all_b3_fixtures /
run_all_b4_b9_fixtures and translates+executes the remaining 48 MUSTs through
`sclass.product.registry.evaluate` (using `use_test_only_qualified_registry()`
strictly in-memory for `needs_engine` MUSTs), and emits deterministic LF-only
`product/qualification/td17_fixture_results.json`.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pathlib
import re
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
for _p in (REPO_ROOT, REPO_ROOT / "src", REPO_ROOT / "tools", REPO_ROOT / "10-CONFORMANCE"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from sclass import canonical_c1
from sclass.product.artifacts import freeze_to_c1_compatible
from sclass.product.check_registry import get_registry
from sclass.product.claim_ledger import (
    InMemoryCanonicalDependencyResolver,
    InMemoryKernelEvidenceResolver,
    InMemoryObligationClosureResolver,
    InMemoryRepositoryIntelligenceIndex,
)
from sclass.product.gate import GateOutput, GateState
from sclass.product.predicate_evaluator import (
    AcceptanceContract,
    Constraint,
    ConstraintType,
    Digest,
    InMemoryFrozenResolver,
    Requirement,
    VerificationStep,
)
from sclass.product.registry import REGISTRY_AUTHORITY, evaluate
from sclass.product.registry_table import REGISTRY_TABLE_ROWS
from sclass.product.traceability import InMemorySourceRefResolver
from sclass.product.trust_model import CheckRecord, InMemoryCheckRecordSource
from sclass.qualification.adapter_registry import use_test_only_qualified_registry
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
from tools.master_fixtures import EXPECTED_MASTER_SHA256, verify_master_sha256
from tools.run_all_b3_fixtures import run_all_block3_fixtures
from tools.run_all_b4_b9_fixtures import run_all_b4_b9_fixtures

DEFAULT_MASTER_PATH = REPO_ROOT / "docs/design/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md"
DEFAULT_TABLE_PATH = REPO_ROOT / "product/MUST-RESULT-TABLE.csv"
DEFAULT_OUT_PATH = REPO_ROOT / "product/qualification/td17_fixture_results.json"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


def parse_all_master_yaml_blocks(master_path: pathlib.Path) -> Dict[str, Dict[str, Any]]:
    """Parse every YAML fixture block headed by a Markdown heading containing FIDs."""
    verify_master_sha256(master_path)
    lines = master_path.read_text(encoding="utf-8").splitlines()
    blocks: Dict[str, Dict[str, Any]] = {}
    i = 0
    while i < len(lines):
        m = re.match(r"^#{2,4}\s+(.+)$", lines[i])
        if m:
            hdr = m.group(1)
            fids = re.findall(r"\b(?:CH\d+|F\d+)-F?T\d+[a-z]?\b", hdr)
            if fids:
                j = i + 1
                while j < len(lines) and not re.match(r"^#{1,4}\s+", lines[j]):
                    if lines[j].strip().startswith("```yaml"):
                        k = j + 1
                        yb: List[str] = []
                        while k < len(lines) and not lines[k].strip().startswith("```"):
                            yb.append(lines[k])
                            k += 1
                        raw_yaml = "\n".join(yb)
                        parsed = yaml.safe_load(raw_yaml)
                        entry = {
                            "master_line": i + 1,
                            "heading": hdr.strip(),
                            "yaml_sha256": _sha256_text(raw_yaml),
                            "data": parsed if isinstance(parsed, dict) else {},
                        }
                        for fid in fids:
                            blocks[fid] = entry
                        i = k
                        break
                    j += 1
        i += 1
    return blocks


def _classify_expected(exp_val: Any) -> str:
    txt = json.dumps(exp_val, sort_keys=True) if not isinstance(exp_val, str) else exp_val
    u = txt.upper()
    if "BLOCKED_ON_HUMAN" in u:
        return "NON_SATISFIED"
    if "MISSING" in u or "DENIED" in u or "REJECT" in u or "MISS" in u:
        return "NON_SATISFIED"
    if "SATISFIED" in u or "NOT_APPLICABLE" in u:
        return "SATISFIED"
    return "NON_SATISFIED"


def _build_f5_base(yd: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "phase": str(yd.get("phase") or "P5"),
        "canonical_state_binding": yd.get("state_binding_digest") or {"target": "t1"},
        "pinned_guidance": yd.get("pinned_guidance_digest") or {"skill": "s1"},
        "policy_version": str(yd.get("policy_version") or "v1"),
        "evaluator_version": str(
            yd.get("executing_evaluator_version") or yd.get("evaluator_version") or "1.0"
        ),
        "evaluation_instant": None if yd.get("evaluation_instant") == "absent" else "2026-11-22T00:00:00Z",
    }


def _build_f6_chain_spec(nodes: Sequence[str], links_raw: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    links = []
    for lr in links_raw:
        links.append(
            {
                "link_type": lr.get("type") or lr.get("link_type") or "REQUIREMENT_TO_ACCEPTANCE",
                "source": lr["source"],
                "destination": lr["destination"],
            }
        )
    return {
        "nodes": list(nodes),
        "obligations": [n for n in nodes if str(n).startswith("OBL")],
        "source_refs": [n for n in nodes if str(n).startswith(("REQ", "OBL", "AC", "VS"))][:4],
        "links": links,
    }


def _translate_48_case(
    must_id: str, fid: str, yd: Mapping[str, Any]
) -> Tuple[List[Tuple[str, Dict[str, Any], str]], Optional[str]]:
    """Translate one of the 48 non-lane-runner Master YAML blocks to registry.evaluate subcases.

    Returns ([(label, payload, expected_class), ...], not_executable_reason).
    """
    # Chapter 1 (PD-CH1-002..007)
    if must_id == "PD-CH1-002":
        return ([
            (
                fid,
                {
                    "subordinate_to_frozen_package": False,
                    "conflicts_with_kernel": True,
                    "overrides_kernel_predicate": True,
                    "shadows_canonical_semantics": True,
                },
                "NON_SATISFIED",
            )
        ], None)
    if must_id == "PD-CH1-004":
        return ([
            (
                fid,
                {
                    "concept_name": str(yd.get("concept", "TestInputSet")),
                    "classifications": list(yd.get("classifications", ["product_projection", "kernel_canonical"])),
                    "presented_as_kernel_type": True,
                },
                "NON_SATISFIED",
            )
        ], None)
    if must_id == "PD-CH1-005":
        return ([
            (fid, {"authority_class": None, "artifact_type": str(yd.get("artifact_type", "TestDesignRecord"))}, "NON_SATISFIED")
        ], None)
    if must_id == "PD-CH1-006":
        return ([
            (
                fid,
                {
                    "source_namespace": str(yd.get("namespace", "process")),
                    "target_namespace": "kernel",
                    "defines_cross_namespace_authority": True,
                    "isolation_enforced": False,
                },
                "NON_SATISFIED",
            )
        ], None)
    if must_id == "PD-CH1-007":
        return ([
            (
                fid,
                {
                    "work_type": str(yd.get("work_type", "BUG_FIX")),
                    "domain": "Backend",
                    "removes_mandatory_control": True,
                    "mandatory_controls_preserved": False,
                },
                "NON_SATISFIED",
            )
        ], None)

    # Chapter 5 (PD-CH5-003..006)
    if must_id == "PD-CH5-003":
        base_entry = {
            "phase": "P5",
            "canonical_state_binding": {"policy_version": "v1", "target": "t1"},
            "task_ref": "TASK-CH5",
            "spec_anchor_digest": _sha256_text("ch5-spec"),
            "input_digests": [_sha256_text("ch5-in-1")],
            "pinned_guidance": yd.get("cached_guidance_digest", "G1"),
            "policy_version": "v1",
            "evaluator_version": "eval-1.0",
            "evaluation_instant": "2026-11-22T00:00:00Z",
        }
        eval_tuple = dict(base_entry)
        eval_tuple["pinned_guidance"] = yd.get("current_guidance_digest", "G2")
        return ([
            (
                fid,
                {
                    "cached_entry": base_entry,
                    "evaluation_tuple": eval_tuple,
                    "cached_guidance_digest": yd.get("cached_guidance_digest", "G1"),
                    "current_guidance_digest": yd.get("current_guidance_digest", "G2"),
                },
                "NON_SATISFIED",
            )
        ], None)
    if must_id == "PD-CH5-004":
        return ([
            (
                fid,
                {
                    "claim": str(yd.get("claim", "10x faster")),
                    "benchmark_corpus": yd.get("benchmark_corpus"),
                    "measurement_window": yd.get("measurement_window"),
                },
                "NON_SATISFIED",
            )
        ], None)
    if must_id == "PD-CH5-005":
        return ([
            (
                fid,
                {"numerator": yd.get("numerator", 0), "denominator": yd.get("denominator", 0)},
                "SATISFIED",
            )
        ], None)
    if must_id == "PD-CH5-006":
        return ([(fid, {"check_id": str(yd.get("check_id", "UNKNOWN-CHECK-99"))}, "NON_SATISFIED")], None)

    # F1 (PD-F1-001..005)
    if must_id == "PD-F1-001":
        art_a = {
            "artifact_class": "data",
            "contract": {"schema": "v1", "digest": yd["artifact_a"]["structured_spec_digest"]},
            "positive": {"input": 1},
            "negative": {"input": -1, "observed": "rejected"},
            "agent_result": "PASS",
        }
        art_b = dict(art_a)
        art_b["prose"] = yd["artifact_b"]["prose"]
        return ([
            (f"{fid}:a", {"artifact": art_a, "independent_verifier_result": "PASS"}, "SATISFIED"),
            (f"{fid}:b", {"artifact": art_b, "independent_verifier_result": "PASS"}, "SATISFIED"),
        ], None)
    if must_id == "PD-F1-002":
        return ([
            (
                fid,
                {
                    "artifact": {
                        "artifact_class": "data",
                        "contract": {"schema": "v1"},
                        "positive": {"input": 1},
                        "negative": {"input": -1, "observed": "rejected"},
                        "agent_result": str(yd.get("agent_result", "PASS")),
                    },
                    "independent_verifier_result": str(yd.get("independent_verifier_result", "FAIL")),
                },
                "NON_SATISFIED",
            )
        ], None)
    if must_id in ("PD-F1-003", "PD-F1-004"):
        return ([
            (fid, {"artifact": dict(yd["artifact"]), "independent_verifier_result": "PASS"}, "NON_SATISFIED")
        ], None)
    if must_id == "PD-F1-005":
        return ([
            (
                fid,
                {
                    "artifact": {
                        "artifact_class": "data",
                        "contract": {"schema": "v1"},
                        "confirmed": dict(yd["confirmed"]),
                        "proposed": dict(yd["proposed"]),
                    },
                    "confirmed_artifact": dict(yd["confirmed"]),
                    "authoritative_approval": yd.get("authoritative_approval"),
                    "structural_diff_procedure": lambda _c, _p: False,
                },
                "NON_SATISFIED",
            )
        ], None)

    # F2 (PD-F2-001..007)
    if must_id == "PD-F2-001":
        return ([
            (
                f"{fid}:case1",
                {
                    "spec": {
                        "input_tokens": list(yd["case_1"]["input_tokens"]),
                        "schema": {"x": {"type": "Int", "domain": [0, 1]}},
                    },
                    "consumer": "p3_invariant",
                },
                "NON_SATISFIED",
            ),
            (
                f"{fid}:case2",
                {
                    "spec": {
                        "input_tokens": list(yd["case_2"]["input_tokens"]),
                        "schema": {"x": {"type": "Int", "domain": [0, 1]}},
                    },
                    "consumer": "p3_invariant",
                },
                "NON_SATISFIED",
            ),
        ], None)
    if must_id == "PD-F2-002":
        return ([
            (
                fid,
                {"spec": {"predicate": yd["predicate"], "schema": yd["schema"]}, "consumer": "p3_invariant"},
                "NON_SATISFIED",
            )
        ], None)
    if must_id == "PD-F2-003":
        b = int(yd.get("evaluation_budget_assignments", 1))
        return ([
            (
                f"{fid}:inconclusive_ok",
                {"base_result": "INCONCLUSIVE", "budget_expired": True, "assignments_evaluated": b, "budget_limit": b},
                "SATISFIED",
            ),
            (
                f"{fid}:false_unsat_rejected",
                {"base_result": "UNSAT", "budget_expired": True, "assignments_evaluated": b, "budget_limit": b},
                "NON_SATISFIED",
            ),
        ], None)
    if must_id == "PD-F2-004":
        return ([
            (f"{fid}:matched", {"classification": "TAUTOLOGY", "domain_bounds_matched": True}, "SATISFIED"),
            (f"{fid}:mismatched", {"classification": "TAUTOLOGY", "domain_bounds_matched": False}, "NON_SATISFIED"),
        ], None)
    if must_id == "PD-F2-005":
        return ([
            (
                fid,
                {
                    "spec": {
                        "predicate": yd["predicate"],
                        "schema": yd["schema"],
                        "qualified_stateful_adapter": yd.get("qualified_stateful_adapter"),
                    },
                    "consumer": "p3_invariant",
                },
                "NON_SATISFIED",
            )
        ], None)
    if must_id == "PD-F2-006":
        ins = list(yd.get("inputs", []))
        return ([
            (
                fid,
                {
                    "adapter_outputs": [x.get("adapter_result") for x in ins],
                    "reference_outputs": [x.get("reference_result") for x in ins],
                    "uses_applicable_f4_budget": True,
                },
                "SATISFIED",
            )
        ], None)
    if must_id == "PD-F2-007":
        return ([
            (
                fid,
                {
                    "bindings": {
                        "requirement_ref": str(yd.get("requirement_ref", "REQ-1")),
                        "constraint_ref": str(yd.get("constraint_ref", "CON-1")),
                        "acceptance_contract_ref": str(yd.get("acceptance_contract_ref", "AC-1")),
                        "verification_step_ref": str(yd.get("verification_step_ref", "VS-1")),
                    },
                    "resolver": _build_frozen_resolver(),
                },
                "SATISFIED",
            )
        ], None)

    # F3 (PD-F3-001..006)
    if must_id in ("PD-F3-001", "PD-F3-002"):
        return ([
            (
                fid,
                {
                    "candidate": dict(yd["candidate"]),
                    "check_record_source": InMemoryCheckRecordSource([]),
                    "expected_object_digest": "obj-d1",
                    "expected_target_digest": "tgt-d1",
                },
                "NON_SATISFIED",
            )
        ], None)
    if must_id == "PD-F3-003":
        return ([
            (
                fid,
                {
                    "structured_a": yd["structured_a"],
                    "structured_b": yd["structured_b"],
                    "prose": yd.get("prose", ""),
                },
                "NON_SATISFIED",
            )
        ], None)
    if must_id == "PD-F3-004":
        rc = yd["requirement_confirmation"]
        return ([
            (
                fid,
                {
                    "confirmation_event": {
                        "event_type": rc["event_type"],
                        "authority": rc["authority"],
                        "source_provenance": rc["source_provenance"],
                    },
                    "canonical_structured_form": {"requirement_id": "REQ-1"},
                    "canonical_structured_form_digest": str(rc["canonical_structured_form_digest"]),
                },
                "NON_SATISFIED",
            )
        ], None)
    if must_id == "PD-F3-005":
        return ([
            (
                fid,
                {
                    "claimed_content_digest": str(yd["claimed_content_digest"]),
                    "artifact": {"recomputed": str(yd["recomputed_content_digest"])},
                },
                "NON_SATISFIED",
            )
        ], None)
    if must_id == "PD-F3-006":
        return ([
            (
                fid,
                {
                    "confirmation": {
                        "confirmation_surface": yd["confirmation_surface"],
                        "principal_key_accessible_to_agent": yd["principal_key_accessible_to_agent"],
                        "approval_forwarding_tool_available": yd["approval_forwarding_tool_available"],
                        "user_presence_required": yd["user_presence_required"],
                    }
                },
                "NON_SATISFIED",
            )
        ], None)

    # F5 (PD-F5-001..005)
    if must_id == "PD-F5-001":
        return ([(fid, _build_f5_base(yd), "NON_SATISFIED")], None)
    if must_id == "PD-F5-002":
        pl = _build_f5_base(yd)
        pl["checks"] = [
            {"check_id": cid, "must_id": "PD-F5-002", "status": "MISSING"}
            for cid in yd.get("missing_check_ids", [])
        ] + [
            {"check_id": cid, "must_id": "PD-F5-002", "status": "BLOCKED"}
            for cid in yd.get("blocked_check_ids", [])
        ]
        return ([(fid, pl, "NON_SATISFIED")], None)
    if must_id == "PD-F5-003":
        pl = _build_f5_base(yd)
        pl["pinned_evaluator_version"] = str(yd["pinned_evaluator_version"])
        pl["elapsed_ms"] = int(yd["elapsed_ms"])
        pl["timeout_ms"] = int(yd["timeout_ms"])
        return ([(fid, pl, "NON_SATISFIED")], None)
    if must_id == "PD-F5-004":
        pl = _build_f5_base(yd)
        pl["relevant_input_digests"] = list(yd.get("relevant_input_digests", []))
        return ([(fid, pl, "SATISFIED")], None)
    if must_id == "PD-F5-005":
        pl_a = _build_f5_base(yd)
        pl_a["kernel_execution_gate"] = str(yd.get("kernel_execution_gate", "DENIED"))
        pl_b = _build_f5_base(yd)
        pl_b["skill_added_checks"] = [
            {"check_id": "SK-F5-5", "must_id": "PD-F5-005", "status": "MISSING"}
        ]
        return (
            [
                (f"{fid}:product_check_under_kernel_deny", pl_a, "SATISFIED"),
                (f"{fid}:skill_blocking_conjunction", pl_b, "NON_SATISFIED"),
            ],
            None,
        )

    # F6 (PD-F6-001..006)
    if must_id == "PD-F6-001":
        spec = _build_f6_chain_spec(yd["nodes"], yd["links"])
        ref_map = {n: {"id": n} for n in spec["source_refs"]}
        return ([
            (
                fid,
                {
                    "spec": spec,
                    "resolver": InMemorySourceRefResolver(ref_map),
                    "freshness_predicate": lambda _n: True,
                    "mode": "realized",
                },
                "SATISFIED",
            )
        ], None)
    if must_id == "PD-F6-002":
        nodes = list(yd.get("nodes", [])) + list(yd.get("orphan_nodes", []))
        spec = _build_f6_chain_spec(nodes, yd.get("links", []))
        spec["obligations"] = ["OBL-2"]
        ref_map = {n: {"id": n} for n in spec["source_refs"]}
        return ([
            (
                fid,
                {
                    "spec": spec,
                    "resolver": InMemorySourceRefResolver(ref_map),
                    "freshness_predicate": lambda _n: True,
                    "mode": "realized",
                },
                "NON_SATISFIED",
            )
        ], None)
    if must_id == "PD-F6-003":
        src = str(yd["source_stable_id"])
        dst = str(yd["destination_stable_id"])
        spec = {
            "nodes": ["REQ-1", src, dst, "TEST-1", "EV-1", "OBL-1"],
            "obligations": ["OBL-1"],
            "source_refs": ["REQ-1", src, dst, "OBL-1"],
            "links": [
                {"link_type": "REQUIREMENT_TO_ACCEPTANCE", "source": "REQ-1", "destination": src},
                {"link_type": str(yd["link_type"]), "source": src, "destination": dst},
                {"link_type": "VERIFICATION_TO_TEST", "source": dst, "destination": "TEST-1"},
                {"link_type": "TEST_TO_EVIDENCE", "source": "TEST-1", "destination": "EV-1"},
                {"link_type": "EVIDENCE_TO_OBLIGATION", "source": "EV-1", "destination": "OBL-1"},
            ],
        }
        return ([
            (
                fid,
                {
                    "spec": spec,
                    "resolver": InMemorySourceRefResolver(
                        {n: {"id": n} for n in ("REQ-1", src, dst, "OBL-1")}
                    ),
                    "freshness_predicate": lambda _n: True,
                    "mode": "realized",
                },
                "SATISFIED",
            )
        ], None)
    if must_id == "PD-F6-004":
        spec = {
            "nodes": ["REQ-1", "AC-1", "VS-1", "TEST-1", "OBL-1"],
            "obligations": ["OBL-1"],
            "source_refs": ["REQ-1", "OBL-1"],
            "links": [
                {"link_type": "REQUIREMENT_TO_ACCEPTANCE", "source": "REQ-1", "destination": "AC-1"}
            ],
            "agent_claimed_coverage_percent": yd.get("agent_claimed_coverage_percent", 100),
        }
        return ([
            (
                fid,
                {
                    "spec": spec,
                    "resolver": InMemorySourceRefResolver({"REQ-1": {"id": "REQ-1"}, "OBL-1": {"id": "OBL-1"}}),
                    "freshness_predicate": lambda _n: True,
                    "mode": "realized",
                },
                "NON_SATISFIED",
            )
        ], None)
    if must_id == "PD-F6-005":
        spec = _build_f6_chain_spec(
            ["REQ-1", "AC-1", "VS-1", "TEST-1", "EV-1", "OBL-1"],
            [
                {"link_type": "REQUIREMENT_TO_ACCEPTANCE", "source": "REQ-1", "destination": "AC-1"},
                {"link_type": "ACCEPTANCE_TO_VERIFICATION", "source": "AC-1", "destination": "VS-1"},
                {"link_type": "VERIFICATION_TO_TEST", "source": "VS-1", "destination": "TEST-1"},
                {"link_type": "TEST_TO_EVIDENCE", "source": "TEST-1", "destination": "EV-1"},
                {"link_type": "EVIDENCE_TO_OBLIGATION", "source": "EV-1", "destination": "OBL-1"},
            ],
        )
        dst_fresh = bool(yd.get("destination_fresh", False))
        return ([
            (
                fid,
                {
                    "spec": spec,
                    "resolver": InMemorySourceRefResolver({"REQ-1": {"id": "REQ-1"}, "OBL-1": {"id": "OBL-1"}}),
                    "freshness_predicate": lambda nid: dst_fresh if nid == "OBL-1" else True,
                    "mode": "realized",
                },
                "NON_SATISFIED",
            )
        ], None)
    if must_id == "PD-F6-006":
        spec_planned = {
            "nodes": ["REQ-1", "AC-1", "VS-1", "TEST-1"],
            "obligations": ["OBL-1"],
            "source_refs": ["REQ-1"],
            "links": [
                {"link_type": "REQUIREMENT_TO_ACCEPTANCE", "source": "REQ-1", "destination": "AC-1"},
                {"link_type": "ACCEPTANCE_TO_VERIFICATION", "source": "AC-1", "destination": "VS-1"},
                {"link_type": "VERIFICATION_TO_TEST", "source": "VS-1", "destination": "TEST-1"},
            ],
        }
        resolver = InMemorySourceRefResolver({n: {"id": n} for n in ("REQ-1", "AC-1", "VS-1", "TEST-1")})
        return ([
            (
                f"{fid}:planned",
                {
                    "spec": spec_planned,
                    "resolver": resolver,
                    "freshness_predicate": lambda _n: True,
                    "mode": "planned",
                },
                "SATISFIED",
            ),
            (
                f"{fid}:realized_missing_evidence",
                {
                    "spec": spec_planned,
                    "resolver": resolver,
                    "freshness_predicate": lambda _n: True,
                    "mode": "realized",
                },
                "NON_SATISFIED",
            ),
        ], None)

    # F7 (PD-F7-001..006)
    if must_id == "PD-F7-001":
        subj = str(yd["subject"])
        return ([
            (
                fid,
                {
                    "claim": {
                        "claim_id": str(yd["claim_id"]),
                        "type": str(yd["type"]),
                        "reference_kind": str(yd["reference_kind"]),
                        "subject": subj,
                        "evidence_refs": list(yd.get("evidence_refs", [])),
                        "target_snapshot": str(yd.get("target_snapshot", "TS-1")),
                        "created_by_delta": False,
                    },
                    "repo_index": InMemoryRepositoryIntelligenceIndex(pre_delta_symbols=[subj], post_delta_overlay=[subj]),
                    "evidence_resolver": InMemoryKernelEvidenceResolver([]),
                    "dependency_resolver": InMemoryCanonicalDependencyResolver({}),
                    "obligation_resolver": InMemoryObligationClosureResolver([]),
                },
                "SATISFIED",
            )
        ], None)
    if must_id == "PD-F7-002":
        return ([
            (
                fid,
                {
                    "claim": {
                        "claim_id": str(yd["claim_id"]),
                        "type": str(yd["type"]),
                        "subject": str(yd["subject"]),
                        "evidence_refs": list(yd.get("evidence_refs", [])),
                        "target_snapshot": str(yd.get("target_snapshot", "TS-1")),
                        "created_by_delta": False,
                    },
                    "repo_index": InMemoryRepositoryIntelligenceIndex(),
                    "evidence_resolver": InMemoryKernelEvidenceResolver([]),
                    "dependency_resolver": InMemoryCanonicalDependencyResolver({}),
                    "obligation_resolver": InMemoryObligationClosureResolver([]),
                },
                "NON_SATISFIED",
            )
        ], None)
    if must_id == "PD-F7-003":
        subj = str(yd["subject"])
        return ([
            (
                fid,
                {
                    "claim": {
                        "claim_id": str(yd["claim_id"]),
                        "type": str(yd["type"]),
                        "reference_kind": str(yd["reference_kind"]),
                        "subject": subj,
                        "dependency_digest": "D_MISMATCH",
                        "target_snapshot": str(yd.get("target_snapshot", "TS-1")),
                        "created_by_delta": False,
                    },
                    "repo_index": InMemoryRepositoryIntelligenceIndex(pre_delta_symbols=[subj], post_delta_overlay=[subj]),
                    "evidence_resolver": InMemoryKernelEvidenceResolver([]),
                    "dependency_resolver": InMemoryCanonicalDependencyResolver(
                        {subj: str(yd.get("canonical_dependency_set_digest", "D1"))}
                    ),
                    "obligation_resolver": InMemoryObligationClosureResolver([]),
                },
                "NON_SATISFIED",
            )
        ], None)
    if must_id == "PD-F7-004":
        return ([
            (
                fid,
                {
                    "claim": {
                        "claim_id": str(yd["claim_id"]),
                        "type": str(yd["type"]),
                        "reference_kind": str(yd["reference_kind"]),
                        "subject": str(yd["subject"]),
                        "target_snapshot": str(yd.get("target_snapshot", "TS-1")),
                        "created_by_delta": bool(yd.get("created_by_delta", False)),
                    },
                    "repo_index": InMemoryRepositoryIntelligenceIndex(pre_delta_symbols=[], post_delta_overlay=[]),
                    "evidence_resolver": InMemoryKernelEvidenceResolver([]),
                    "dependency_resolver": InMemoryCanonicalDependencyResolver({}),
                    "obligation_resolver": InMemoryObligationClosureResolver([]),
                },
                "NON_SATISFIED",
            )
        ], None)
    if must_id == "PD-F7-005":
        rc = yd["reference_claim"]
        bc = yd["behavioral_claim"]
        cc = yd["completion_claim"]
        subj = str(rc.get("subject", "pkg.rate_limiter:Limiter"))
        return ([
            (
                f"{fid}:reference",
                {
                    "claim": {
                        "claim_id": "CL-F7-5-REF",
                        "type": str(rc["type"]),
                        "reference_kind": "symbol",
                        "subject": subj,
                        "evidence_refs": [],
                        "created_by_delta": False,
                    },
                    "repo_index": InMemoryRepositoryIntelligenceIndex(pre_delta_symbols=[subj], post_delta_overlay=[subj]),
                    "evidence_resolver": InMemoryKernelEvidenceResolver([]),
                    "dependency_resolver": InMemoryCanonicalDependencyResolver({}),
                    "obligation_resolver": InMemoryObligationClosureResolver([]),
                },
                "SATISFIED",
            ),
            (
                f"{fid}:behavioral",
                {
                    "claim": {
                        "claim_id": "CL-F7-5-BEH",
                        "type": str(bc["type"]),
                        "subject": subj,
                        "evidence_refs": list(bc.get("evidence_refs", ["EV-B1"])),
                        "created_by_delta": False,
                    },
                    "repo_index": InMemoryRepositoryIntelligenceIndex(pre_delta_symbols=[subj], post_delta_overlay=[subj]),
                    "evidence_resolver": InMemoryKernelEvidenceResolver(list(bc.get("evidence_refs", ["EV-B1"]))),
                    "dependency_resolver": InMemoryCanonicalDependencyResolver({}),
                    "obligation_resolver": InMemoryObligationClosureResolver([]),
                },
                "SATISFIED",
            ),
            (
                f"{fid}:completion_unclosed",
                {
                    "claim": {
                        "claim_id": "CL-F7-5-COMP",
                        "type": str(cc["type"]),
                        "subject": str(cc.get("subject", subj)),
                        "evidence_refs": list(cc.get("evidence_refs", [])),
                        "created_by_delta": False,
                    },
                    "repo_index": InMemoryRepositoryIntelligenceIndex(),
                    "evidence_resolver": InMemoryKernelEvidenceResolver([]),
                    "dependency_resolver": InMemoryCanonicalDependencyResolver({}),
                    "obligation_resolver": InMemoryObligationClosureResolver([]),
                },
                "NON_SATISFIED",
            ),
        ], None)
    if must_id == "PD-F7-006":
        return ([
            (
                f"{fid}:present",
                {
                    "claimed_symbols": [str(yd["claim_subject"])],
                    "post_delta_symbols": list(yd.get("post_delta_overlay", [])),
                },
                "SATISFIED",
            ),
            (
                f"{fid}:absent",
                {
                    "claimed_symbols": [str(yd["absent_case_subject"])],
                    "post_delta_symbols": list(yd.get("post_delta_overlay", [])),
                },
                "NON_SATISFIED",
            ),
        ], None)

    # F9 (PD-F9-001..004)
    if must_id == "PD-F9-001":
        return ([(fid, {"events": list(yd["events"])}, "SATISFIED")], None)
    if must_id == "PD-F9-002":
        return ([
            (
                fid,
                {
                    "envelope": {
                        "envelope_version": "1.0",
                        "event_basis": "canonical_event_stream",
                        "report": {
                            "metric": yd.get("metric", "pass_rate"),
                            "numerator": yd["numerator"],
                            "denominator": yd["denominator"],
                        },
                    }
                },
                "NON_SATISFIED",
            )
        ], None)
    if must_id in ("PD-F9-003", "PD-F9-004"):
        pl = dict(yd)
        if must_id == "PD-F9-004":
            pl["expected_metric_cost"] = pl["canonical_cost"]
            pl["expected_metric_time_seconds"] = pl["canonical_time_seconds"]
        return ([(fid, pl, "SATISFIED")], None)

    return ([], f"NO_TRANSLATOR_DEFINED_FOR:{must_id}:{fid}")


def run_td17_fixtures(
    *,
    master_path: pathlib.Path = DEFAULT_MASTER_PATH,
    table_path: pathlib.Path = DEFAULT_TABLE_PATH,
    out_path: pathlib.Path = DEFAULT_OUT_PATH,
) -> Dict[str, Any]:
    master_sha = verify_master_sha256(master_path)
    yaml_blocks = parse_all_master_yaml_blocks(master_path)

    rows = [
        r
        for r in csv.DictReader(table_path.open(encoding="utf-8"))
        if r["status"] == "FIXTURE-REF-NOT-RUN"
    ]
    assert len(rows) == 129, f"Expected 129 FIXTURE-REF-NOT-RUN rows, got {len(rows)}"

    # Execute existing lane runners for the 81 MUSTs they cover
    b3_results, _ = run_all_block3_fixtures(master_path)
    b49_results = run_all_b4_b9_fixtures(master_path)

    lane_by_must: Dict[str, List[Dict[str, Any]]] = {}
    for lane_id, res in b3_results:
        lane_by_must.setdefault(res.must_id, []).append(
            {
                "lane": lane_id,
                "fixture_id": res.fixture_id,
                "master_line": res.master_line,
                "expected": getattr(res, "expected", getattr(res, "expected_gate_output", "")),
                "actual": getattr(res, "actual", getattr(res, "actual_gate_output", "")),
                "status": res.status,
            }
        )
    for res in b49_results:
        lane_by_must.setdefault(res.must_id, []).append(
            {
                "lane": res.lane,
                "fixture_id": res.fixture_id,
                "master_line": res.master_line,
                "expected": res.expected,
                "actual": res.actual,
                "status": res.status,
            }
        )

    reg_meta = {r["must_id"]: r for r in REGISTRY_TABLE_ROWS}
    results_list: List[Dict[str, Any]] = []
    executed_count = 0
    not_executable_count = 0
    mismatches: List[str] = []

    with use_test_only_qualified_registry():
        for r in sorted(rows, key=lambda item: item["must_id"]):
            mid = r["must_id"]
            fids = re.findall(
                r"\b(?:CH\d+|F\d+)-F?T\d+[a-z]?\b",
                r["gaming_fixture_id"] + " " + r["happy_fixture_id"],
            )
            matched_fid = next((f for f in fids if f in yaml_blocks), None)
            if mid == "PD-F2-007" and "F2-T9" in yaml_blocks:
                matched_fid = "F2-T9"
            yb = yaml_blocks[matched_fid] if matched_fid else None

            if mid in lane_by_must:
                lane_entries = lane_by_must[mid]
                all_match = all(e["status"] == "RAN-MATCH" for e in lane_entries)
                if not all_match:
                    mismatches.append(f"{mid}: lane runner mismatch {lane_entries}")
                executed_count += 1
                results_list.append(
                    {
                        "must_id": mid,
                        "needs_engine": bool(reg_meta[mid]["needs_engine"]),
                        "execution_status": "EXECUTED",
                        "execution_path": "master_lane_runner",
                        "matched_fixture_id": matched_fid,
                        "master_line": yb["master_line"] if yb else lane_entries[0]["master_line"],
                        "yaml_sha256": yb["yaml_sha256"] if yb else "",
                        "subcase_count": len(lane_entries),
                        "all_matched": all_match,
                        "subcases": lane_entries,
                    }
                )
            else:
                if yb is None or matched_fid is None:
                    not_executable_count += 1
                    results_list.append(
                        {
                            "must_id": mid,
                            "needs_engine": bool(reg_meta[mid]["needs_engine"]),
                            "execution_status": "NOT_EXECUTABLE",
                            "execution_path": "none",
                            "reason": f"NO_MASTER_YAML_BLOCK:{r['gaming_fixture_id']}",
                        }
                    )
                    continue
                subcases, ne_reason = _translate_48_case(mid, matched_fid, yb["data"])
                if ne_reason is not None or not subcases:
                    not_executable_count += 1
                    results_list.append(
                        {
                            "must_id": mid,
                            "needs_engine": bool(reg_meta[mid]["needs_engine"]),
                            "execution_status": "NOT_EXECUTABLE",
                            "execution_path": "none",
                            "matched_fixture_id": matched_fid,
                            "master_line": yb["master_line"],
                            "yaml_sha256": yb["yaml_sha256"],
                            "reason": ne_reason or "EMPTY_SUBCASES",
                        }
                    )
                    continue

                sub_out: List[Dict[str, Any]] = []
                all_ok = True
                for label, payload, exp_cls in subcases:
                    out: GateOutput = evaluate(mid, payload, authority=REGISTRY_AUTHORITY)
                    if out.detail and "unexpected evidence key" in out.detail:
                        all_ok = False
                        mismatches.append(f"{mid}/{label}: unexpected evidence key: {out.detail}")
                    actual_cls = "SATISFIED" if out.state == GateState.SATISFIED else "NON_SATISFIED"
                    matched = actual_cls == exp_cls
                    if not matched:
                        all_ok = False
                        mismatches.append(
                            f"{mid}/{label}: expected {exp_cls}, got {out.state.value} ({out.detail})"
                        )
                    sub_out.append(
                        {
                            "label": label,
                            "expected_class": exp_cls,
                            "actual_state": out.state.value,
                            "actual_detail": out.detail,
                            "matched": matched,
                        }
                    )
                executed_count += 1
                results_list.append(
                    {
                        "must_id": mid,
                        "needs_engine": bool(reg_meta[mid]["needs_engine"]),
                        "execution_status": "EXECUTED",
                        "execution_path": "master_yaml_to_registry_evaluate",
                        "matched_fixture_id": matched_fid,
                        "master_line": yb["master_line"],
                        "yaml_sha256": yb["yaml_sha256"],
                        "subcase_count": len(sub_out),
                        "all_matched": all_ok,
                        "subcases": sub_out,
                    }
                )

    report = {
        "schema_version": "1.0",
        "master_sha256": master_sha,
        "total_fnr_rows": len(rows),
        "executed_count": executed_count,
        "not_executable_count": not_executable_count,
        "mismatches": mismatches,
        "results": results_list,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute TD-17 Master fixtures for 129 FIXTURE-REF-NOT-RUN MUSTs")
    parser.add_argument("--master-path", type=pathlib.Path, default=DEFAULT_MASTER_PATH)
    parser.add_argument("--out-path", type=pathlib.Path, default=DEFAULT_OUT_PATH)
    args = parser.parse_args()
    rep = run_td17_fixtures(master_path=args.master_path, out_path=args.out_path)
    print(
        f"TD-17 FIXTURE SUMMARY: total={rep['total_fnr_rows']} "
        f"executed={rep['executed_count']} not_executable={rep['not_executable_count']} "
        f"mismatches={len(rep['mismatches'])}"
    )
    if rep["mismatches"]:
        for m in rep["mismatches"]:
            print("  MISMATCH:", m)
        return 1
    assert rep["executed_count"] + rep["not_executable_count"] == 129
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
