"""Check registry and phase sub-check definitions for S-Class product layer.

Implements check ID calculation per Master §5.1 L652:
  check_id = digest(C1(owner_section, subcheck_name, procedure_version))
and enforces PD-CH5-006: hand-created or unregistered check IDs fail closed with
MISSING[PD-CH5-006].

Also houses authoritative Chapter 4 registry representations (PD-CH4-002, 005, 006, 007, 008)
using the UNSPECIFIED_IN_MASTER marker for unstated fields.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from sclass.product.artifacts import canonical_c1, freeze_to_c1_compatible
from sclass.product.gate import GateOutput, GateState

QUALIFIED_EVALUATOR_BOUNDARY = "sclass.product.check_registry"
"""Enforces caller authority. The real boundary is caller wiring in S-Class execution."""

UNSPECIFIED_IN_MASTER = "UNSPECIFIED_IN_MASTER"


@dataclass(frozen=True)
class CheckRecord:
    """Normative entry in phase sub-check registry per Master §5.1 L645."""

    check_id: str
    check_name: str
    check_class: str
    decision_procedure: str
    inputs: str
    failure_route: str
    cost_bound: str
    owner_section: str
    procedure_version: str
    master_line: int


def compute_check_id(
    owner_section: str,
    subcheck_name: str,
    procedure_version: str = "1.0",
) -> str:
    """Computes deterministic check_id per Master §5.1 L652:

    check_id = digest(C1(owner_section, subcheck_name, procedure_version)).
    """
    payload = (owner_section, subcheck_name, procedure_version)
    c1_bytes = canonical_c1(freeze_to_c1_compatible(payload))
    return hashlib.sha256(c1_bytes).hexdigest()


# Master-defined phase sub-check definitions across P0-P11 with line citations.
_RAW_PHASE_SUBCHECKS: List[Dict[str, Any]] = [
    # P0: §2.6 L1542
    {"section": "§2.6", "name": "Profile completeness", "class": "M", "proc": "required dimension/field presence + type/schema validation", "inputs": "EngineeringProfile", "fail": "remain P0", "cost": "linear in profile size", "ver": "1.0", "line": 1544},
    {"section": "§2.6", "name": "Work-type resolution", "class": "M", "proc": "selected option must belong to single registry and have Decision outcome", "inputs": "IntakeRecord, Decision", "fail": "QuestionBatch / human", "cost": "O(1) registry + Decision lookup", "ver": "1.0", "line": 1545},
    {"section": "§2.6", "name": "Risk floor", "class": "M", "proc": "compare effective risk tier with policy floor", "inputs": "profile + policy", "fail": "increase depth; human if policy unclear", "cost": "O(1)", "ver": "1.0", "line": 1546},
    {"section": "§2.6", "name": "Required depth", "class": "M", "proc": "derive max(policy_floor, profile-derived depth)", "inputs": "profile + policy", "fail": "deepen P0", "cost": "O(1) over fixed depth scale", "ver": "1.0", "line": 1547},
    {"section": "§2.6", "name": "Profile observations", "class": "E", "proc": "verify material repository/stack signals against admissible observations", "inputs": "TargetSnapshot/context", "fail": "P1 discovery", "cost": "bounded by low-cost observation budget", "ver": "1.0", "line": 1548},
    {"section": "§2.6", "name": "Human profile gate", "class": "J", "proc": "explicit decision required where policy/risk demands it", "inputs": "profile + policy", "fail": "BLOCKED_ON_HUMAN", "cost": "one interaction per blocking boundary", "ver": "1.0", "line": 1549},

    # P1: §2.7 L1612
    {"section": "§2.7", "name": "Target identity", "class": "M", "proc": "TargetSnapshot resolves and remains bound", "inputs": "TargetSnapshot", "fail": "remain P1", "cost": "O(1) + snapshot lookup", "ver": "1.0", "line": 1614},
    {"section": "§2.7", "name": "Declared-area coverage", "class": "M/E", "proc": "every declared/transitively affected area has attributable observation", "inputs": "ChangeSurfaceAnalysis + DiscoveryRecord", "fail": "remain P1", "cost": "bounded by discovered-area count", "ver": "1.0", "line": 1615},
    {"section": "§2.7", "name": "Context admissibility", "class": "E", "proc": "provenance + boundary + trust rules", "inputs": "ContextPackage/items", "fail": "remove item / deeper discovery", "cost": "bounded by item count", "ver": "1.0", "line": 1616},
    {"section": "§2.7", "name": "High-impact unknown closure", "class": "M/J", "proc": "every unknown answered, assumed or deferred; material ambiguity -> J", "inputs": "QuestionBatch, AssumptionRecord", "fail": "P0/P1/human", "cost": "one pass over unknowns", "ver": "1.0", "line": 1617},
    {"section": "§2.7", "name": "Change-surface completeness", "class": "M/E", "proc": "every ChangeSurface count field present and transitive impact closed", "inputs": "discovery + profile", "fail": "remain P1", "cost": "bounded by transitive impact closure", "ver": "1.0", "line": 1618},
    {"section": "§2.7", "name": "Dependency map", "class": "M", "proc": "required dependency references resolve against canonical dependency identity", "inputs": "dependency observations", "fail": "P1", "cost": "linear in affected dependency set", "ver": "1.0", "line": 1619},

    # P2: §2.8 L1736
    {"section": "§2.8", "name": "Requirement identity/uniqueness", "class": "M", "proc": "stable ID uniqueness within current objective revision", "inputs": "RequirementSet", "fail": "P2", "cost": "O(n) with indexed IDs", "ver": "1.0", "line": 1738},
    {"section": "§2.8", "name": "Binding authority", "class": "M", "proc": "read canonical Requirement.authority; producer field cannot override", "inputs": "canonical Requirements", "fail": "P2 / confirmation path", "cost": "O(requirements)", "ver": "1.0", "line": 1739},
    {"section": "§2.8", "name": "Invariant consistency", "class": "M", "proc": "typed predicates within decidable fragment; contradiction -> MISSING", "inputs": "invariant predicates", "fail": "P2 / J", "cost": "bounded predicate check", "ver": "1.0", "line": 1740},

    # P3: §2.9 L1799
    {"section": "§2.9", "name": "P3-DOMAIN-COVERAGE", "class": "M", "proc": "Link every confirmed applicable requirement by typed F6 link to a domain contract/invariant/entity", "inputs": "requirements, domain contracts", "fail": "MISSING -> P3", "cost": "default 100% applicable coverage", "ver": "1.0", "line": 1801},
    {"section": "§2.9", "name": "P3-ARCH-COVERAGE", "class": "M", "proc": "Map every required responsibility to a component, interface/signature and resolved dependency path", "inputs": "responsibilities, components", "fail": "MISSING -> P3", "cost": "default 100% coverage", "ver": "1.0", "line": 1802},

    # P4: §2.10 L1891
    {"section": "§2.10", "name": "P4-ENTRY-APPLICABILITY", "class": "M", "proc": "require current P3 product-layer applicability projection", "inputs": "P3 applicability projection, bindings", "fail": "return to P3 or MISSING", "cost": "bounded binding checks", "ver": "1.0", "line": 1893},
    {"section": "§2.10", "name": "P4-SCOPE", "class": "M", "proc": "compute task count, units/task and total units against lane policy defaults", "inputs": "lane, task graph, canonical target IDs", "fail": "split/replan P4", "cost": "O(tasks + targets)", "ver": "1.0", "line": 1894},

    # P5: §2.11 L1963
    {"section": "§2.11", "name": "P5-FIRST", "class": "M", "proc": "test-input-set delta precedes implementation delta by canonical delta sequence", "inputs": "delta refs and input manifest", "fail": "block implementation; redesign P5", "cost": "O(deltas + entries)", "ver": "1.0", "line": 1966},
    {"section": "§2.11", "name": "P5-INPUT-BINDING", "class": "M", "proc": "digest every adapter-declared test input and environment before red", "inputs": "TestInputSet, adapter discovery result", "fail": "re-design; weakening route", "cost": "O(input bytes), capped by lane", "ver": "1.0", "line": 1967},

    # P6: §2.12 L2041
    {"section": "§2.12", "name": "P6-EXECUTION-AUTH", "class": "M", "proc": "ExecutionGate binds task, target, action and exact scope", "inputs": "request, kernel gate", "fail": "deny launched-worker write", "cost": "bounded kernel checks", "ver": "1.0", "line": 2044},
    {"section": "§2.12", "name": "P6-SCOPE", "class": "M", "proc": "observed delta must be subset of authorized write set", "inputs": "target IDs and delta", "fail": "stop/replan P4", "cost": "O(delta mutations), lane cap", "ver": "1.0", "line": 2045},

    # P7: §2.13 L2111
    {"section": "§2.13", "name": "P7-EVIDENCE-IDENTITY", "class": "M", "proc": "bind receipt to obligation, target, step, tool/version, inputs, environment and raw result", "inputs": "evidence and frozen identity", "fail": "discard/rerun", "cost": "O(receipt fields), cap", "ver": "1.0", "line": 2114},
    {"section": "§2.13", "name": "P7-TEST-MATCH", "class": "E", "proc": "compare complete P5 input manifest and environment digest, and require same test green", "inputs": "P5 binding and P7 receipt", "fail": "reject; changed input returns P5/F1/F2", "cost": "O(manifest entries)", "ver": "1.0", "line": 2115},

    # P8: §2.14 L2185
    {"section": "§2.14", "name": "P8-CAUSE", "class": "E", "proc": "map failure signature to canonical failed check/evidence", "inputs": "structured result, check registry", "fail": "unknown cause -> J", "cost": "linear in failed receipt set", "ver": "1.0", "line": 2189},
    {"section": "§2.14", "name": "P8-EARLIEST", "class": "M/E", "proc": "route to earliest affected phase using dependency links", "inputs": "failed artifact, lifecycle map", "fail": "invalidate downstream; return earliest phase", "cost": "O(dependency links), capped", "ver": "1.0", "line": 2190},

    # P9: §2.15 L2251
    {"section": "§2.15", "name": "P9-COMPLETENESS", "class": "M", "proc": "aggregate every required per-task P7 result via F5", "inputs": "task results, sub-check tables", "fail": "missing task result -> MISSING", "cost": "O(tasks + findings)", "ver": "1.0", "line": 2255},
    {"section": "§2.15", "name": "P9-FRESHNESS", "class": "M", "proc": "recompute frozen freshness at recorded instant", "inputs": "target/policy/evidence digests", "fail": "invalidate and rerun P7", "cost": "O(declared dependencies)", "ver": "1.0", "line": 2256},

    # P10: §2.16 L2317
    {"section": "§2.16", "name": "P10-KERNEL-RELEASE", "class": "M/J", "proc": "require frozen ReleaseEvaluation for exact target/policy; preserve kernel DENIED", "inputs": "release evaluation and binding", "fail": "deny delivery", "cost": "bounded release record lookup", "ver": "1.0", "line": 2321},
    {"section": "§2.16", "name": "P10-CLOSURE", "class": "M", "proc": "verify every required obligation/contract is current and kernel-closed", "inputs": "obligations, AcceptanceSnapshot, RequiredEvidence", "fail": "return P7/P9", "cost": "O(required obligations + receipts)", "ver": "1.0", "line": 2322},

    # P11: §2.17 L2383
    {"section": "§2.17", "name": "P11-SIGNAL-IDENTITY", "class": "M", "proc": "bind signal to canonical events and before/after digests", "inputs": "signal record, event history", "fail": "discard ungrounded signal", "cost": "O(events in selected window)", "ver": "1.0", "line": 2387},
    {"section": "§2.17", "name": "P11-CHANGE-IMPACT", "class": "E", "proc": "resolve affected artifacts/evidence/obligations through declared dependency index", "inputs": "mutation/dependency index", "fail": "over-invalidate if uncertain; route earliest affected phase", "cost": "O(indexed dependents), cap applies", "ver": "1.0", "line": 2388},
]


def _build_registry() -> Dict[str, CheckRecord]:
    registry: Dict[str, CheckRecord] = {}
    for item in _RAW_PHASE_SUBCHECKS:
        cid = compute_check_id(item["section"], item["name"], item["ver"])
        record = CheckRecord(
            check_id=cid,
            check_name=item["name"],
            check_class=item["class"],
            decision_procedure=item["proc"],
            inputs=item["inputs"],
            failure_route=item["fail"],
            cost_bound=item["cost"],
            owner_section=item["section"],
            procedure_version=item["ver"],
            master_line=item["line"],
        )
        registry[cid] = record
        # Also index by check_name for convenience lookups
        registry[item["name"]] = record
    return registry


CHECK_REGISTRY: Dict[str, CheckRecord] = _build_registry()


def get_check_record(identifier: str) -> Optional[CheckRecord]:
    """Retrieves CheckRecord by check_id or subcheck_name."""
    return CHECK_REGISTRY.get(identifier)


def validate_check_id(
    check_id: str,
    caller_authority: Optional[str] = None,
) -> GateOutput:
    """Validates check_id origin per MUST PD-CH5-006.

    Hand-created or unregistered IDs return MISSING[PD-CH5-006].
    Enforces closed-set caller authority QUALIFIED_EVALUATOR_BOUNDARY.
    """
    if caller_authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH5-006",
            failures=["MISSING[PD-CH5-006]"],
            explain={"error": "unauthorized caller authority", "caller": caller_authority},
        )

    # Check if this check_id originates in the phase sub-check table
    if check_id in CHECK_REGISTRY:
        return GateOutput(state=GateState.SATISFIED)

    # Reject hand-inserted check ID
    return GateOutput(
        state=GateState.MISSING,
        must_id="PD-CH5-006",
        failures=["MISSING[PD-CH5-006]"],
        explain={
            "check_id": check_id,
            "error": "hand-created check ID rejected under PD-CH5-006",
        },
    )


# -----------------------------------------------------------------------------
# Chapter 4 Registry Representations
# -----------------------------------------------------------------------------

CH4_REGISTRY: Dict[str, Dict[str, Any]] = {
    "PD-CH4-002": {
        "check": "PD-CH4-002",
        "class": "UNSPECIFIED_IN_MASTER",
        "owner_block": "CH4",
        "requirement": "Claims of execution bind qualified adapter structured results and raw result identity",
        "inputs": "agent_claim, qualified_adapter_receipt",
        "failure_route": "MISSING[PD-CH4-002]",
        "fixture_ids": ["CH4-T2"],
        "depends_on_draft_sections": [],
        "procedure_ref": UNSPECIFIED_IN_MASTER,
        "decision_procedure": UNSPECIFIED_IN_MASTER,
        "cost_bound": UNSPECIFIED_IN_MASTER,
    },
    "PD-CH4-005": {
        "check": "PD-CH4-005",
        "class": "UNSPECIFIED_IN_MASTER",
        "owner_block": "CH4",
        "requirement": "Freshness and independence evaluated from bound identity; invalidation owned by PD-CH2-055",
        "inputs": "Requirement revision, evidence requirement, target, adapter, environment, input-set and raw-result digests",
        "failure_route": "MISSING[PD-CH4-005]",
        "fixture_ids": ["CH4-T5", "CH4-T28"],
        "depends_on_draft_sections": [],
        "procedure_ref": "§4.6",
        "decision_procedure": "§4.6 freshness evaluation",
        "cost_bound": UNSPECIFIED_IN_MASTER,
    },
    "PD-CH4-006": {
        "check": "PD-CH4-006",
        "class": "UNSPECIFIED_IN_MASTER",
        "owner_block": "CH4",
        "requirement": "False-completion only from canonical outcome/evidence events",
        "inputs": "Kernel obligation closure, ReleaseEvaluation, admissible evidence digests",
        "failure_route": "MISSING[PD-CH4-006]",
        "fixture_ids": ["CH4-T6", "CH4-T29"],
        "depends_on_draft_sections": [],
        "procedure_ref": "§4.7",
        "decision_procedure": "§4.7 completion verification",
        "cost_bound": UNSPECIFIED_IN_MASTER,
    },
    "PD-CH4-007": {
        "check": "PD-CH4-007",
        "class": "UNSPECIFIED_IN_MASTER",
        "owner_block": "CH4",
        "requirement": "Context resume rebuilds anchors from canonical state; transcript-only authority rejected",
        "inputs": "Canonical anchors, pinned guidance digests, step-pack digest",
        "failure_route": "MISSING[PD-CH4-007]",
        "fixture_ids": ["CH4-T7", "CH4-T30"],
        "depends_on_draft_sections": [],
        "procedure_ref": "§4.5",
        "decision_procedure": "§4.5 context resume anchor reconstruction",
        "cost_bound": UNSPECIFIED_IN_MASTER,
    },
    "PD-CH4-008": {
        "check": "PD-CH4-008",
        "class": "UNSPECIFIED_IN_MASTER",
        "owner_block": "CH4",
        "requirement": "Listed threat classes map to detection, gate, containment and fixture",
        "inputs": "Threat rows, rows with fixtures",
        "failure_route": "MISSING[PD-CH4-008]",
        "fixture_ids": ["CH4-T8"],
        "depends_on_draft_sections": ["§4.1"],
        "procedure_ref": "§4.1",
        "decision_procedure": "§4.1 threat class mapping",
        "cost_bound": UNSPECIFIED_IN_MASTER,
    },
}


def lint_ch4_registry() -> List[Dict[str, Any]]:
    """Lints CH4 registry records and reports any UNSPECIFIED_IN_MASTER fields as findings."""
    findings: List[Dict[str, Any]] = []
    for must_id, record in sorted(CH4_REGISTRY.items()):
        for field_name, value in sorted(record.items()):
            if value == UNSPECIFIED_IN_MASTER:
                findings.append({
                    "must_id": must_id,
                    "field": field_name,
                    "finding": UNSPECIFIED_IN_MASTER,
                })
    return findings
