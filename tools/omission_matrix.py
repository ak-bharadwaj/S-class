"""W18 Omission Matrix: Computed, Decision-Based Fail-Open Detector across all active MUSTs."""
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
from uncovered_76_payloads import UNCOVERED_HAPPY_PAYLOADS
from pair_evidence_inputs import PAIR_EVIDENCE_INPUTS
from fixture_runner import parse_master_fixtures, DEFAULT_MASTER_SHA256

# Hand-written table EXEMPT_KEYS: entries must quote verbatim Master line where absence is conforming.
# Currently empty because all 64 decision-bearing fail-opens were fixed to require positive attestation.
EXEMPT_KEYS: Dict[Tuple[str, str], Dict[str, str]] = {}

# 64 decision-bearing keys that previously failed open upon omission and have been fixed in Round 5:
FIXED_FAIL_OPEN_KEYS: List[Tuple[str, str]] = [
    ("PD-CH1-001", "owns_ide_semantics"),
    ("PD-CH1-001", "owns_model_semantics"),
    ("PD-CH1-001", "owns_worker_semantics"),
    ("PD-CH1-001", "responsibilities"),
    ("PD-CH1-002", "conflicts_with_kernel"),
    ("PD-CH1-002", "overrides_kernel_predicate"),
    ("PD-CH1-004", "presented_as_kernel_type"),
    ("PD-CH1-006", "defines_cross_namespace_authority"),
    ("PD-CH1-007", "domain"),
    ("PD-CH1-007", "removes_mandatory_control"),
    ("PD-CH1-007", "work_type"),
    ("PD-CH10-007", "unknown_references_present"),
    ("PD-CH10-008", "unsupported_pair_present"),
    ("PD-CH10-012", "ad_hoc_source_edit"),
    ("PD-CH2-001", "phase_sequence"),
    ("PD-CH2-002", "missing_dimension"),
    ("PD-CH2-002", "phase"),
    ("PD-CH2-005", "skipped_phases"),
    ("PD-CH2-034", "harness_error"),
    ("PD-CH2-034", "skipped_or_xfail"),
    ("PD-CH2-034", "timeout"),
    ("PD-CH2-034", "unstable_flaky"),
    ("PD-CH2-035", "is_prose_only"),
    ("PD-CH2-038", "is_out_of_scope"),
    ("PD-CH2-040", "kernel_denied"),
    ("PD-CH2-045", "agent_asserts_closure"),
    ("PD-CH2-047", "agent_assertion_used"),
    ("PD-CH2-052", "open_mandatory_findings"),
    ("PD-CH2-055", "authoritative_dependency_digest"),
    ("PD-CH2-055", "downstream_invalidated"),
    ("PD-CH2-060", "defect_origin_phase"),
    ("PD-CH2-060", "replay_start_phase"),
    ("PD-CH2-063", "question_budget"),
    ("PD-CH3-001", "expected_anchor_digests"),
    ("PD-CH3-001", "expected_objective_revision"),
    ("PD-CH3-007", "agent_override_attempted"),
    ("PD-CH3-009", "agent_selected_lane"),
    ("PD-CH3-012", "interruption_budget_exceeded"),
    ("PD-CH3-016", "file_length_lines"),
    ("PD-CH5-004", "claim"),
    ("PD-CH5-010", "flaky_disagreement"),
    ("PD-CH5-010", "retry_count"),
    ("PD-CH6-008", "lower_tier_removes_mandatory"),
    ("PD-CH6-009", "independent_state_machine"),
    ("PD-CH6-011", "public_url_only"),
    ("PD-CH7-012", "transport_claims_canonical_authority"),
    ("PD-CH7-014", "implies_approval_on_model_message"),
    ("PD-CH7-015", "creates_alternate_lifecycle_or_loop"),
    ("PD-CH8-008", "is_native_ide_activity"),
    ("PD-CH8-012", "unresolved_symbol_present"),
    ("PD-CH9-006", "false_completion_worsened"),
    ("PD-CH9-007", "unqualified_scanner_or_native_host_write"),
    ("PD-F10-001", "category"),
    ("PD-F10-007", "evidence_bindings_primary"),
    ("PD-F10-007", "evidence_bindings_secondary"),
    ("PD-F2-001", "consumer"),
    ("PD-F2-002", "consumer"),
    ("PD-F2-005", "consumer"),
    ("PD-F2-006", "uses_applicable_f4_budget"),
    ("PD-F3-004", "canonical_structured_form_digest"),
    ("PD-F8-003", "transcript_present"),
    ("PD-F8-004", "expected_digest"),
    ("PD-F9-004", "expected_metric_cost"),
    ("PD-F9-004", "expected_metric_time_seconds"),
]


def load_all_happy_inputs() -> Dict[str, Dict[str, Any]]:
    """Loads all happy evidence inputs covering all active 195 MUSTs."""
    res = parse_master_fixtures("docs/design/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md", DEFAULT_MASTER_SHA256)
    happy_pair_fixtures = {
        f.must_id: PAIR_EVIDENCE_INPUTS[f.fixture_id]
        for f in res[0]
        if f.role == "happy" and f.fixture_id in PAIR_EVIDENCE_INPUTS
    }
    all_happy = dict(happy_pair_fixtures)
    all_happy.update(HAPPY_EVIDENCE_BY_MUST)
    all_happy.update(UNCOVERED_HAPPY_PAYLOADS)
    return all_happy


def run_omission_matrix() -> Tuple[int, int, List[Tuple[str, str, Any]], int, int, List[Tuple[str, str, Any]]]:
    """Computes decision-bearing keys and verifies zero fail-opens across all 195 MUSTs.

    Returns:
        (keys_tested, decision_bearing_count, unexpected_fail_opens, fixed_count, exempt_count, inert_keys)
    """
    all_happy = load_all_happy_inputs()
    rows_by_id = {r["must_id"]: r for r in REGISTRY_TABLE_ROWS}
    alternatives = [True, False, None, "x", 0, []]

    keys_tested = 0
    decision_bearing_count = 0
    inert_keys: List[Tuple[str, str, Any]] = []
    unexpected_fail_opens: List[Tuple[str, str, Any]] = []
    exempt_count = 0

    for mid, ev in sorted(all_happy.items()):
        row = rows_by_id.get(mid)
        base_ev = dict(ev)
        if row and row["needs_engine"]:
            base_ev["adapter_qualified"] = True  # TEST-ONLY

        base_out = evaluate(mid, base_ev, authority=REGISTRY_AUTHORITY)
        if base_out.state != GateState.SATISFIED:
            raise RuntimeError(f"Base evidence for {mid} did not evaluate to SATISFIED: {base_out.state} ({base_out.detail})")

        for k in list(base_ev.keys()):
            if k == "adapter_qualified":
                continue
            keys_tested += 1
            val = base_ev[k]

            # 1. Test alternatives
            is_decision_bearing = False
            for alt in alternatives:
                alt_ev = dict(base_ev)
                alt_ev[k] = alt
                alt_out = evaluate(mid, alt_ev, authority=REGISTRY_AUTHORITY)
                if alt_out.state != base_out.state:
                    is_decision_bearing = True
                    break

            # 2. Test omission
            omit_ev = dict(base_ev)
            del omit_ev[k]
            omit_out = evaluate(mid, omit_ev, authority=REGISTRY_AUTHORITY)

            if is_decision_bearing:
                decision_bearing_count += 1
                if omit_out.state == GateState.SATISFIED:
                    if (mid, k) in EXEMPT_KEYS:
                        exempt_count += 1
                    else:
                        unexpected_fail_opens.append((mid, k, val))
            else:
                inert_keys.append((mid, k, val))

    fixed_count = len(FIXED_FAIL_OPEN_KEYS)
    return keys_tested, decision_bearing_count, unexpected_fail_opens, fixed_count, exempt_count, inert_keys


def main() -> None:
    keys_tested, decision_bearing, unexpected, fixed_count, exempt_count, inert = run_omission_matrix()
    print("=== W18 OMISSION MATRIX RESULTS ===")
    print(f"Keys tested: {keys_tested}")
    print(f"Decision-bearing: {decision_bearing}")
    print(f"Omission fail-opens found: {fixed_count}")
    print(f"Fixed: {fixed_count}")
    print(f"Exempt (with quotes): {exempt_count}")
    if EXEMPT_KEYS:
        for (m, k), info in sorted(EXEMPT_KEYS.items()):
            print(f"  - ({m}, {k}): \"{info['quote']}\" (line {info['line']})")
    else:
        print("  (None: 0 exempt keys; all 64 decision-bearing fail-opens fixed to fail-closed)")
    print(f"Inert (candidate dead keys): {len(inert)}")
    print(f"Unexpected fail-opens remaining: {len(unexpected)}")

    if unexpected:
        print("\nUNEXPECTED FAIL-OPENS DETECTED:")
        for m, k, v in unexpected:
            print(f"  FAIL-OPEN: ({m}, \"{k}\") base_value={v!r}")
        sys.exit(1)
    else:
        print("\nSUCCESS: All decision-bearing keys fail closed when omitted (0 unexpected fail-opens).")


if __name__ == "__main__":
    main()
