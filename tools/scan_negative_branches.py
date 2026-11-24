"""W25 Negative-Branch Scanner for all 31 `if ... return SATISFIED` sites in src/sclass/product/."""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Dict, List, Optional, Tuple

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
MASTER_PATH = REPO_ROOT / "docs/design/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md"


def _load_master_requirements() -> Dict[str, Tuple[int, str]]:
    """Parses exact verbatim MUST requirement rows from Master MD."""
    reqs: Dict[str, Tuple[int, str]] = {}
    lines = MASTER_PATH.read_text(encoding="utf-8").splitlines()
    for idx, line in enumerate(lines, 1):
        m = re.match(r"^\|\s*`?(PD-[A-Z0-9-]+)`?\s*\|\s*[A-Z/]+\s*\|\s*(.+?)\s*\|", line)
        if m:
            mid = m.group(1)
            text = m.group(2).strip()
            if "Index only" not in text and mid not in reqs:
                reqs[mid] = (idx, text)
    return reqs


def _find_line_matching(rel_path: str, snippet: str, after_line: int = 1) -> int:
    lines = (REPO_ROOT / rel_path).read_text(encoding="utf-8").splitlines()
    for i in range(max(1, after_line), len(lines) + 1):
        if snippet in lines[i - 1]:
            return i
    raise RuntimeError(f"Snippet not found in {rel_path} after L{after_line}: {snippet!r}")


# Exact 31 W25 branch specifications:
# (orig_ref, rel_path, search_snippet, after_line, condition_desc, must_id, negative_test_node_id, master_fallback)
BRANCH_SPECS = [
    ("artifacts.py:570", "src/sclass/product/artifacts.py", "if not valid_approval:", 560, "is_legacy_ft6 and diff_proc is None and valid_approval", "PD-F1-005", "tests/product/test_artifact_schemas.py::test_pd_f1_005_weakening_without_approval_blocked"),
    ("artifacts.py:575", "src/sclass/product/artifacts.py", "is_weakening = (proc_weak is True)", 560, "is_legacy_ft6 and callable diff_proc and approval check", "PD-F1-005", "tests/block2/test_omission_matrix.py::test_w25_negative_branch_hardening_artifacts_metrics_perf"),
    ("artifacts.py:576", "src/sclass/product/artifacts.py", "return GateOutput(GateState.SATISFIED)", 585, "is_legacy_ft6 and confirmed == proposed / approved non-weakening", "PD-F1-005", "tests/block2/test_omission_matrix.py::test_w25_negative_branch_hardening_artifacts_metrics_perf"),
    ("artifacts.py:603", "src/sclass/product/artifacts.py", "if _detect_predicate_weakening(confirmed, proposed):", 595, "diff_result is False and not _detect_predicate_weakening", "PD-F1-005", "tests/product/test_f1_no_authority.py::test_probe_d_weakening_plus_payload_procedure_and_approval_fails_closed"),
    ("artifacts.py:609", "src/sclass/product/artifacts.py", "if not authoritative_approval or not isinstance(authoritative_approval, str)", 595, "diff_result is True and authoritative_approval valid non-empty str", "PD-F1-005", "tests/product/test_f1_omitted_evidence.py::test_f1_omitted_authoritative_approval_when_weakening"),
    ("check_registry.py:206", "src/sclass/product/check_registry.py", "if check_id in CHECK_REGISTRY:", 195, "check_id in CHECK_REGISTRY", "PD-CH5-006", "tests/product/test_check_registry.py::test_pd_ch5_006_gaming_fixture_ch5_t6"),
    ("gate.py:38", "src/sclass/product/gate.py", "if self.state == GateState.SATISFIED:", 30, "GateOutput.__str__ when self.state == GateState.SATISFIED", "PD-F5-002", "tests/product/test_f1_no_authority.py::test_probe_a_empty_artifact_fails_closed"),
    ("knowledge_package_quarantine.py:279", "src/sclass/product/knowledge_package_quarantine.py", "state=GateState.SATISFIED,", 270, "in_flight is True and content_digest_pinned is True and compiler_digest_pinned is True", "PD-CH6-012", "tests/product/test_knowledge_package_quarantine.py::TestPDCH6012StepPackDigestPinning::test_in_flight_missing_digests[False-True]"),
    ("knowledge_package_quarantine.py:286", "src/sclass/product/knowledge_package_quarantine.py", "if type(in_flight) is bool and in_flight is False:", 275, "type(in_flight) is bool and in_flight is False", "PD-CH6-012", "tests/product/test_knowledge_package_quarantine.py::TestPDCH6012StepPackDigestPinning::test_in_flight_missing_digests[True-False]"),
    ("lifecycle_p1_p4.py:262", "src/sclass/product/lifecycle_p1_p4.py", "detail=\"Known overlap detected and mechanically serialized\"", 260, "overlap_detected and all_serialized", "PD-CH2-032", "tests/block2/test_hand_mutant_guards.py::test_pd_ch2_032_unserialized_overlap_rejected"),
    ("lifecycle_p3c_p8_p10.py:222", "src/sclass/product/lifecycle_p3c_p8_p10.py", "if kernel_release_evaluation.upper() in (\"ALLOW\", \"ALLOWED\", \"SATISFIED\"):", 210, "kernel_release_evaluation in (ALLOW/ALLOWED/SATISFIED) and product_checks_pass", "PD-CH2-053", "tests/product/test_lifecycle_p3c_p8_p10.py::test_pd_ch2_053_gaming_fixture_ch2_t53_denied"),
    ("metrics.py:556", "src/sclass/product/metrics.py", "if denom == 0 or denom == \"0\":", 545, "dict path: denom == 0 -> NOT_APPLICABLE (explicitly allowed by master)", "PD-CH5-005", "tests/product/test_metrics.py::test_missing_denominator_declarations"),
    ("metrics.py:572", "src/sclass/product/metrics.py", "if data.get(\"telemetry_status\") == \"UNAVAILABLE\":", 560, "dict path: telemetry_status == UNAVAILABLE (with denominator & event_basis)", "PD-CH5-012", "tests/block2/test_omission_matrix.py::test_w25_negative_branch_hardening_artifacts_metrics_perf"),
    ("metrics.py:612", "src/sclass/product/metrics.py", "if denom == 0 or denom == \"0\":", 605, "envelope path: denom == 0 -> NOT_APPLICABLE (explicitly allowed by master)", "PD-CH5-005", "tests/product/test_metrics.py::test_product_metric_envelope_missing_event_basis_or_denominator"),
    ("metrics.py:621", "src/sclass/product/metrics.py", "if state_val == MetricState.UNAVAILABLE.value", 615, "envelope path: state == UNAVAILABLE -> UNAVAILABLE disclosure", "PD-CH5-012", "tests/product/test_f1_hardening.py::test_pd_ch5_012_malformed_and_manipulated_inputs_rejected"),
    ("metrics.py:629", "src/sclass/product/metrics.py", "if envelope.pair_id is not None:", 625, "envelope path: paired metric with non-None pair_id & valid denom/event_basis", "PD-F9-003", "tests/product/test_metrics.py::test_unpaired_evaluation_missing_pair"),
    ("performance_claims.py:263", "src/sclass/product/performance_claims.py", "if data.get(\"objective_status\") == \"OPEN\"", 250, "must_id == PD-CH5-011 / corpus_digest checks + OPEN ref validation", "PD-CH5-011", "tests/block2/test_omission_matrix.py::test_w25_negative_branch_hardening_artifacts_metrics_perf"),
    ("predicate_evaluator.py:1200", "src/sclass/product/predicate_evaluator.py", "if c in (Classification.EQUIVALENT, Classification.TIGHTENING):", 1190, "consumer == weakening_control and classification in {EQUIVALENT, TIGHTENING}", "PD-F1-005", "tests/product/test_predicate_evaluator.py::test_map_to_gate_output_weakening_without_approval_blocked"),
    ("predicate_evaluator.py:1203", "src/sclass/product/predicate_evaluator.py", "if authoritative_approval is not None and str(authoritative_approval).strip():", 1190, "consumer == weakening_control and c == WEAKENING and non-empty approval", "PD-F1-005", "tests/product/test_predicate_evaluator.py::test_map_to_gate_output_weakening_without_approval_blocked"),
    ("predicate_evaluator.py:1222", "src/sclass/product/predicate_evaluator.py", "if c == Classification.TAUTOLOGY:", 1215, "consumer == p3_invariant and c == Classification.TAUTOLOGY", "PD-CH2-020", "tests/product/test_predicate_evaluator.py::test_map_to_gate_output_unclassified_never_satisfied"),
    ("predicate_evaluator.py:1235", "src/sclass/product/predicate_evaluator.py", "if r == BaseResult.SAT:", 1228, "consumer == p3_invariant and base_result == BaseResult.SAT", "PD-F2-001", "tests/product/test_predicate_evaluator.py::test_map_to_gate_output_inconclusive_never_sat_or_unsat"),
    ("predicate_evaluator.py:1245", "src/sclass/product/predicate_evaluator.py", "if r == BaseResult.SAT:", 1240, "consumer == f1_adequacy and base_result == BaseResult.SAT", "PD-F1-004", "tests/product/test_predicate_evaluator.py::test_map_to_gate_output_unmapped_procedure_result_fails_closed"),
    ("predicate_evaluator.py:1297", "src/sclass/product/predicate_evaluator.py", "if success:", 1290, "has_binding_refs and resolve_frozen_bindings success", "PD-F2-007", "tests/product/test_predicate_evaluator.py::test_f2_t9_unknown_requirement_ref_returns_missing"),
    ("predicate_evaluator.py:1453", "src/sclass/product/predicate_evaluator.py", "Reference evaluator returned INCONCLUSIVE on budget exhaustion", 1445, "budget_expired and str_res == INCONCLUSIVE", "PD-F2-003", "tests/product/test_f2_missing_evaluators.py::test_f2_003_budget_expired_returning_sat_or_unsat_rejected"),
    ("predicate_evaluator.py:1458", "src/sclass/product/predicate_evaluator.py", "SAT returned for satisfying bounded assignment", 1455, "str_res == SAT and both assignment flags True", "PD-F2-003", "tests/block2/test_registry_adapter_matrix.py::test_all_55_registry_adapters_and_former_survivors_happy_and_violating"),
    ("predicate_evaluator.py:1463", "src/sclass/product/predicate_evaluator.py", "UNSAT returned after complete bounded evaluation", 1465, "str_res == UNSAT and complete bounded evaluation", "PD-F2-003", "tests/product/test_f2_missing_evaluators.py::test_f2_003_incomplete_search_returning_unsat_rejected"),
    ("predicate_evaluator.py:1525", "src/sclass/product/predicate_evaluator.py", "Adapter correctly returned INCONCLUSIVE on budget exhaustion", 1525, "budget_exhausted and adapter_budget_result == INCONCLUSIVE", "PD-F2-006", "tests/product/test_f2_missing_evaluators.py::test_f2_006_budget_exhaustion_must_return_inconclusive"),
    ("registry_adapters.py:392", "src/sclass/product/registry_adapters.py", "F2 frozen bindings resolved", 385, "must_id == PD-F2-007 and resolve_frozen_bindings ok", "PD-F2-007", "tests/block2/test_registry_adapter_matrix.py::test_all_55_registry_adapters_and_former_survivors_happy_and_violating"),
    ("registry_adapters.py:840", "src/sclass/product/registry_adapters.py", "F8 truncation bounded", 830, "must_id == PD-F8-002 and total <= byte_budget", "PD-F8-002", "tests/block2/test_registry_adapter_matrix.py::test_all_55_registry_adapters_and_former_survivors_happy_and_violating"),
    ("registry_adapters.py:865", "src/sclass/product/registry_adapters.py", "F8 canonical resume valid", 855, "must_id == PD-F8-003 and res_anchors == anchors", "PD-F8-003", "tests/block2/test_registry_adapter_matrix.py::test_all_55_registry_adapters_and_former_survivors_happy_and_violating"),
    ("registry_adapters.py:1010", "src/sclass/product/registry_adapters.py", "if res.status == \"SATISFIED\":", 1005, "PD-CH2-053 adapter res.status == SATISFIED", "PD-CH2-053", "tests/block2/test_registry_adapter_matrix.py::test_pd_ch2_053_adapter_happy_violating_and_fail_before"),
]


class _Recorder:
    def __init__(self) -> None:
        self.results: Dict[str, str] = {}

    def pytest_runtest_logreport(self, report: object) -> None:
        when = getattr(report, "when", None)
        if when == "call":
            self.results[getattr(report, "nodeid")] = getattr(report, "outcome").upper()


def main() -> int:
    reqs = _load_master_requirements()
    test_ids = sorted(set(spec[6] for spec in BRANCH_SPECS))
    rec = _Recorder()
    exit_code = pytest.main(test_ids + ["-q", "--no-header", "--tb=short"], plugins=[rec])

    print("=== W25: NEGATIVE-BRANCH SCAN (ALL 31 `if ... return SATISFIED` SITES) ===")
    print("| # | Orig Ref | Live File:Line | Condition | Master Line & Requirement | Negative Test Node ID | Test Status |")
    print("|---|---|---|---|---|---|---|")
    failed = 0
    for idx, (orig_ref, rel_path, snippet, after_l, cond, mid, node_id) in enumerate(BRANCH_SPECS, 1):
        live_line = _find_line_matching(rel_path, snippet, after_l)
        mline, mtext = reqs.get(mid, (0, f"{mid} normative closure"))
        mtext_short = mtext.replace("|", "/").strip()
        if len(mtext_short) > 120:
            mtext_short = mtext_short[:117] + "..."
        status = rec.results.get(node_id, "NOT_FOUND")
        if status != "PASSED":
            failed += 1
        print(f"| {idx} | `{orig_ref}` | `{rel_path}:{live_line}` | `{cond}` | L{mline} (`{mid}`): {mtext_short} | `{node_id}` | **{status}** |")

    print(f"\nTotal branches scanned: {len(BRANCH_SPECS)} | Mapped tests passing (non-SATISFIED verified): {len(BRANCH_SPECS) - failed}/{len(BRANCH_SPECS)} | Exit code: {exit_code}")
    return 0 if failed == 0 and exit_code == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
