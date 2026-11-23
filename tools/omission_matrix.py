"""W14 Omission Matrix: Generic Fail-Open Detector across all active MUSTs."""
from __future__ import annotations

import copy
import os
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("src"))
sys.path.insert(0, os.path.abspath("tools"))
sys.path.insert(0, os.path.abspath("tests/block2"))

from sclass.product.registry import evaluate, REGISTRY_AUTHORITY
from sclass.product.registry_table import REGISTRY_TABLE_ROWS
from sclass.product.gate import GateState
from test_registry_adapter_matrix import HAPPY_EVIDENCE_BY_MUST
from pair_evidence_inputs import PAIR_EVIDENCE_INPUTS
from fixture_runner import parse_master_fixtures, DEFAULT_MASTER_SHA256
from generated_optional_keys import GENERATED_OPTIONAL_KEYS

# Explicit OPTIONAL_KEYS table with Master design citation and engineering rationale.
# Any SATISFIED under key deletion or setting to None is a fail-open defect unless listed here.
OPTIONAL_KEYS: Dict[Tuple[str, str], Dict[str, str]] = {
    # --- Negative indicator flags: False is conforming; absence/omission means non-presence of forbidden condition ---
    ("PD-CH1-001", "owns_ide_semantics"): {
        "reason": "Negative indicator: absence of IDE ownership claim conforms to control plane thesis",
        "master_line": "master:L1097,L8898",
    },
    ("PD-CH1-001", "owns_model_semantics"): {
        "reason": "Negative indicator: absence of model ownership claim conforms to control plane thesis",
        "master_line": "master:L1097,L8898",
    },
    ("PD-CH1-001", "owns_worker_semantics"): {
        "reason": "Negative indicator: absence of worker ownership claim conforms to control plane thesis",
        "master_line": "master:L1097,L8898",
    },
    ("PD-CH2-007", "alternate_retry_path_active"): {
        "reason": "Negative indicator: absence of alternate retry path is conforming (defaults False)",
        "master_line": "master:L1326",
    },
    ("PD-CH2-031", "unserialized_concurrent_modifications"): {
        "reason": "Negative indicator: absence of concurrent modifications is conforming",
        "master_line": "master:L2690",
    },
    ("PD-CH2-038", "is_out_of_scope"): {
        "reason": "Negative indicator: absence of out-of-scope delta is conforming (defaults False)",
        "master_line": "master:L2718",
    },
    ("PD-CH2-040", "kernel_denied"): {
        "reason": "Negative indicator: absence of kernel denial is conforming (defaults False)",
        "master_line": "master:L2730",
    },
    ("PD-CH2-044", "is_stale"): {
        "reason": "Negative indicator: absence of evidence staleness is conforming (defaults False)",
        "master_line": "master:L2740",
    },
    ("PD-CH2-045", "agent_asserts_closure"): {
        "reason": "Negative indicator: agent not asserting closure independently is conforming (defaults False)",
        "master_line": "master:L2748",
    },
    ("PD-CH2-047", "agent_assertion_used"): {
        "reason": "Negative indicator: red classification without agent assertion is conforming (defaults False)",
        "master_line": "master:L2750",
    },
    ("PD-CH2-048", "p6_modifies_test_input_set"): {
        "reason": "Negative indicator: absence of test input set modification during P6 is conforming (defaults False)",
        "master_line": "master:L2752",
    },
    # --- Master Specification-exempted optional fields ---
    ("PD-F8-003", "transcript_present"): {
        "reason": "Resume uses canonical state binding and re-injected anchors, ignoring deleted transcript",
        "master_line": "master:L857,L9794",
    },
    ("PD-CH2-063", "treated_as_complete"): {
        "reason": "Optional flag when clarification questions asked is within budget cap",
        "master_line": "master:L2761",
    },
    ("PD-CH5-012", "event_refs"): {
        "reason": "Contextual sample metadata optional in outcome disclosure",
        "master_line": "master:L2685,L9350",
    },
    ("PD-CH5-012", "numerator"): {
        "reason": "Contextual sample metadata optional in outcome disclosure",
        "master_line": "master:L2685,L9350",
    },
    # --- Alternative representations: one of multiple conforming representation forms ---
    ("PD-CH1-001", "component_role"): {
        "reason": "Alternative representation: architecture role can be supplied via responsibilities list",
        "master_line": "master:L1097",
    },
    ("PD-CH1-001", "responsibilities"): {
        "reason": "Alternative representation: responsibilities can be supplied via component_role",
        "master_line": "master:L1097",
    },
    ("PD-CH4-012", "path_reference"): {
        "reason": "Alternative reference: symbol_reference is sufficient reference target",
        "master_line": "master:L3460",
    },
    ("PD-CH4-012", "symbol_reference"): {
        "reason": "Alternative reference: path_reference is sufficient reference target",
        "master_line": "master:L3460",
    },
    ("PD-CH9-005", "has_policy_reference"): {
        "reason": "Alternative query key: within_retention_limit triggers evaluation",
        "master_line": "master:L4400",
    },
    ("PD-CH9-005", "within_retention_limit"): {
        "reason": "Alternative query key: has_policy_reference triggers evaluation",
        "master_line": "master:L4400",
    },
    ("PD-CH3-012", "human_decision_required"): {
        "reason": "Gate selector: when False, no human decision is required so interruption budget is unexercised",
        "master_line": "master:L3187",
    },
    ("PD-CH7-009", "conflict_detected"): {
        "reason": "Gate selector: when False, no protocol version conflict exists to return typed error",
        "master_line": "master:L3933",
    },
}
OPTIONAL_KEYS.update(GENERATED_OPTIONAL_KEYS)

# Positive indicator keys where True is conforming and False is violating.
# If flipped to False and evaluator returns SATISFIED, it is a fail-open defect.
POSITIVE_BOOLEAN_KEYS: Set[str] = {
    "is_qualified",
    "manifest_unchanged",
    "environment_digest_match",
    "test_is_green",
    "green_test_run",
    "target_identity_match",
    "rollback_inputs_bound",
    "verification_inputs_bound",
    "is_before_red",
    "invalidated_evidence",
    "recorded_action",
    "bytes_equal",
    "rollback_capability",
    "ddl_present",
    "target_snapshot_pinned",
    "exercises_real_gate_outputs",
    "has_adversarial_claim_failure",
    "has_test_integrity_failure",
    "idempotent_under_request_identity",
    "subordinate_to_frozen_package",
    "evidence_present",
    "authority_class_declared",
    "usable_adapter_bound",
    "has_structured_results",
    "kernel_obligation_closure",
    "has_admissible_evidence",
}


def collect_all_happy_inputs() -> Dict[str, Dict[str, Any]]:
    rows_by_id = {r["must_id"]: r for r in REGISTRY_TABLE_ROWS}
    res = parse_master_fixtures("docs/design/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md", DEFAULT_MASTER_SHA256)
    happy_fixtures = [f for f in res[0] if f.role == "happy"]

    happy_inputs: Dict[str, Dict[str, Any]] = {}

    # 1. Master Appendix F happy pairs
    for f in happy_fixtures:
        ev = dict(PAIR_EVIDENCE_INPUTS.get(f.fixture_id, {}))
        if rows_by_id[f.must_id]["needs_engine"]:
            ev["adapter_qualified"] = True
        happy_inputs[f.must_id] = ev

    # 2. HAPPY_EVIDENCE_BY_MUST (including 75 newly extracted)
    for mid, ev in HAPPY_EVIDENCE_BY_MUST.items():
        ev_copy = dict(ev)
        if rows_by_id[mid]["needs_engine"]:
            ev_copy["adapter_qualified"] = True
        happy_inputs[mid] = ev_copy

    return happy_inputs


def run_omission_matrix(verbose: bool = False) -> Tuple[int, int, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Runs omission matrix across all happy inputs.
    
    Returns:
        (musts_checked_count, operations_count, unexpected_fail_opens, listed_optional_hits)
    """
    happy_inputs = collect_all_happy_inputs()
    rows_by_id = {r["must_id"]: r for r in REGISTRY_TABLE_ROWS}
    
    musts_checked = len(happy_inputs)
    operations_count = 0
    unexpected_fail_opens = []
    listed_optional_hits = []

    # Baseline verification
    for mid, base_ev in sorted(happy_inputs.items()):
        out = evaluate(mid, base_ev, authority=REGISTRY_AUTHORITY)
        assert out.state == GateState.SATISFIED, f"Baseline for {mid} not SATISFIED: {out}"

    for mid, base_ev in sorted(happy_inputs.items()):
        # 1. Top-level keys
        for k in list(base_ev.keys()):
            if k == "adapter_qualified":
                continue  # Engine qualification wrapper

            # (b) Deletion
            del_ev = {x: copy.deepcopy(y) for x, y in base_ev.items() if x != k}
            operations_count += 1
            out = evaluate(mid, del_ev, authority=REGISTRY_AUTHORITY)
            if out.state == GateState.SATISFIED:
                hit = {"must_id": mid, "key": k, "op": "DELETE", "val": base_ev[k], "detail": out.detail}
                if (mid, k) in OPTIONAL_KEYS:
                    listed_optional_hits.append(hit)
                else:
                    unexpected_fail_opens.append(hit)
            if verbose:
                verdict = "FAIL_OPEN" if (out.state == GateState.SATISFIED and (mid, k) not in OPTIONAL_KEYS) else "SAFE"
                print(f"{mid} | {k} | DELETE | {out.state.value} | {verdict}")

            # (c) Boolean flip
            if isinstance(base_ev[k], bool):
                flip_ev = {x: copy.deepcopy(y) for x, y in base_ev.items()}
                flip_ev[k] = not base_ev[k]
                operations_count += 1
                out = evaluate(mid, flip_ev, authority=REGISTRY_AUTHORITY)
                # Opposite is violating if key is a positive boolean and was True
                is_violating_opposite = (k in POSITIVE_BOOLEAN_KEYS and base_ev[k] is True)
                if out.state == GateState.SATISFIED and is_violating_opposite:
                    hit = {"must_id": mid, "key": k, "op": "FLIP_BOOL", "orig": base_ev[k], "new": flip_ev[k], "detail": out.detail}
                    unexpected_fail_opens.append(hit)
                if verbose:
                    verdict = "FAIL_OPEN" if (out.state == GateState.SATISFIED and is_violating_opposite) else "SAFE"
                    print(f"{mid} | {k} | FLIP_BOOL | {out.state.value} | {verdict}")

            # (d) Set None
            none_ev = {x: copy.deepcopy(y) for x, y in base_ev.items()}
            none_ev[k] = None
            operations_count += 1
            out = evaluate(mid, none_ev, authority=REGISTRY_AUTHORITY)
            if out.state == GateState.SATISFIED:
                hit = {"must_id": mid, "key": k, "op": "SET_NONE", "orig": base_ev[k], "detail": out.detail}
                if (mid, k) in OPTIONAL_KEYS:
                    listed_optional_hits.append(hit)
                else:
                    unexpected_fail_opens.append(hit)
            if verbose:
                verdict = "FAIL_OPEN" if (out.state == GateState.SATISFIED and (mid, k) not in OPTIONAL_KEYS) else "SAFE"
                print(f"{mid} | {k} | SET_NONE | {out.state.value} | {verdict}")

        # 2. Nested dicts one level down
        for k, v in list(base_ev.items()):
            if isinstance(v, dict):
                for sk in list(v.keys()):
                    nested_path = f"{k}.{sk}"
                    # (b) Deletion in nested dict
                    del_ev = copy.deepcopy(base_ev)
                    del del_ev[k][sk]
                    operations_count += 1
                    out = evaluate(mid, del_ev, authority=REGISTRY_AUTHORITY)
                    if out.state == GateState.SATISFIED:
                        hit = {"must_id": mid, "key": nested_path, "op": "DELETE_NESTED", "val": v[sk], "detail": out.detail}
                        if (mid, nested_path) in OPTIONAL_KEYS:
                            listed_optional_hits.append(hit)
                        else:
                            unexpected_fail_opens.append(hit)

                    # (c) Boolean flip in nested dict
                    if isinstance(v[sk], bool):
                        flip_ev = copy.deepcopy(base_ev)
                        flip_ev[k][sk] = not v[sk]
                        operations_count += 1
                        out = evaluate(mid, flip_ev, authority=REGISTRY_AUTHORITY)
                        is_violating_opposite = (sk in POSITIVE_BOOLEAN_KEYS and v[sk] is True)
                        if out.state == GateState.SATISFIED and is_violating_opposite:
                            hit = {"must_id": mid, "key": nested_path, "op": "FLIP_BOOL_NESTED", "orig": v[sk], "new": flip_ev[k][sk], "detail": out.detail}
                            unexpected_fail_opens.append(hit)

                    # (d) Set None in nested dict
                    none_ev = copy.deepcopy(base_ev)
                    none_ev[k][sk] = None
                    operations_count += 1
                    out = evaluate(mid, none_ev, authority=REGISTRY_AUTHORITY)
                    if out.state == GateState.SATISFIED:
                        hit = {"must_id": mid, "key": nested_path, "op": "SET_NONE_NESTED", "orig": v[sk], "detail": out.detail}
                        if (mid, nested_path) in OPTIONAL_KEYS:
                            listed_optional_hits.append(hit)
                        else:
                            unexpected_fail_opens.append(hit)

    return musts_checked, operations_count, unexpected_fail_opens, listed_optional_hits


if __name__ == "__main__":
    musts_checked, ops, unexpected, listed = run_omission_matrix()
    print("=== W14 OMISSION MATRIX EXECUTION REPORT ===")
    print(f"MUSTs checked: {musts_checked} / 195 (194 active with SATISFIED evidence, 1 kernel-denied PD-CH2-053)")
    print(f"Operations executed: {ops}")
    print(f"Fail-opens detected (unexpected): {len(unexpected)}")
    print(f"Listed OPTIONAL hits (expected & conformant): {len(listed)}")
    
    if unexpected:
        print("\nUNEXPECTED FAIL-OPENS DETECTED:")
        for u in unexpected:
            print(f"  {u['must_id']} | key={u['key']} | op={u['op']} | detail={u['detail']}")
    else:
        print("\nALL FAIL-OPENS RESOLVED: 0 unexpected fail-opens detected!")

    print("\nOPTIONAL_KEYS with Master Design Citations:")
    for (mid, k), info in sorted(OPTIONAL_KEYS.items()):
        print(f"  ({mid}, '{k}') -> {info['reason']} [{info['master_line']}]")
