#!/usr/bin/env python3
"""Run complete E4 mutation testing battery: 50 hand-written mutants across 10 lanes x 5 mutants.

Ensures:
1. Expected target-string replacement count validation before mutation (mismatch -> INVALID / NOT_EXECUTED).
2. Strict classifier: KILLED requires pytest returncode == 1, verified genuine test failure summary
   (both "^FAILED <path>::<test>" and final summary counter "N failed" with N > 0), and no collection/import/infra error.
   Collection errors, import errors, timeouts, subprocess exceptions, and invalid mutations evaluate to INVALID / NOT_EXECUTED.
3. Unexpected mutation or execution exceptions produce a recorded INVALID result and raw evidence.
4. Exact byte preservation & SHA-256 restoration in finally block under all paths.
5. Generates per-mutant raw logs and 50-row result matrix in delivery-evidence/ (outside product PR).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
PYTEST_BIN = "/home/runner/venv-3.12/bin/pytest"
if not Path(PYTEST_BIN).exists():
    PYTEST_BIN = sys.executable + " -m pytest"


@dataclass
class MutantDef:
    mutant_id: str
    lane: str
    target_rel_path: str
    test_rel_path: str
    name: str
    description: str
    target_str: str
    replacement_str: str
    expected_count: int = 1


# 50 Hand-Written Mutants (10 Lanes x 5 Mutants)
MUTANTS: List[MutantDef] = [
    # -------------------------------------------------------------------------
    # Lane 1: P0A (lifecycle_p0a.py)
    # -------------------------------------------------------------------------
    MutantDef(
        "P0A-M1", "p0a",
        "src/sclass/product/lifecycle_p0a.py",
        "tests/product/test_lifecycle_p0a.py",
        "bypass_p0a_authority",
        "Bypass caller authority validation in evaluate_pd_ch2_001_single_lifecycle",
        "if caller_authority != QUALIFIED_EVALUATOR_BOUNDARY:\n        return GateOutput(",
        "if False:\n        return GateOutput(",
        expected_count=6,
    ),
    MutantDef(
        "P0A-M2", "p0a",
        "src/sclass/product/lifecycle_p0a.py",
        "tests/product/test_lifecycle_p0a.py",
        "bypass_work_type_registration",
        "Bypass unregistered work type rejection in evaluate_pd_ch2_001_single_lifecycle",
        "if not work_type or work_type not in REGISTERED_WORK_TYPES:\n        return GateOutput(",
        "if False:\n        return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P0A-M3", "p0a",
        "src/sclass/product/lifecycle_p0a.py",
        "tests/product/test_lifecycle_p0a.py",
        "bypass_eleven_dimensions_check",
        "Bypass missing required dimensions check in evaluate_pd_ch2_002_eleven_dimensions",
        "missing_set = [d for d in ELEVEN_DIMENSIONS if d not in dim_set]\n        if missing_set:\n            return GateOutput(",
        "missing_set = []\n        if False:\n            return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P0A-M4", "p0a",
        "src/sclass/product/lifecycle_p0a.py",
        "tests/product/test_lifecycle_p0a.py",
        "bypass_earlier_phase_status_check",
        "Bypass earlier phase invalidity check in evaluate_pd_ch2_003_earlier_phase_validity",
        "if status in (\"INVALID\", \"FAILED\", \"MISSING\", \"BLOCKED\"):\n            return GateOutput(",
        "if False:\n            return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P0A-M5", "p0a",
        "src/sclass/product/lifecycle_p0a.py",
        "tests/product/test_lifecycle_p0a.py",
        "bypass_downstream_invalidation",
        "Bypass downstream invalidation check when digest changes in evaluate_pd_ch2_055_downstream_invalidation",
        "if authoritative_digest and bound_digest != authoritative_digest:\n        # Changed dependency digest not visible in recomputation key\n        return GateOutput(",
        "if False:\n        return GateOutput(",
        expected_count=1,
    ),

    # -------------------------------------------------------------------------
    # Lane 2: P0B (lifecycle_p0b.py)
    # -------------------------------------------------------------------------
    MutantDef(
        "P0B-M1", "p0b",
        "src/sclass/product/lifecycle_p0b.py",
        "tests/product/test_lifecycle_p0b.py",
        "bypass_p0b_authority",
        "Bypass caller authority check in evaluate_pd_ch2_007_p8_retry_budget",
        "if authority != QUALIFIED_EVALUATOR_BOUNDARY:\n        return GateOutput(",
        "if False:\n        return GateOutput(",
        expected_count=7,
    ),
    MutantDef(
        "P0B-M2", "p0b",
        "src/sclass/product/lifecycle_p0b.py",
        "tests/product/test_lifecycle_p0b.py",
        "bypass_alternate_retry_path",
        "Bypass alternate retry path prohibition in evaluate_pd_ch2_007_p8_retry_budget",
        "if alternate_retry_path_active:\n        return GateOutput(",
        "if False:\n        return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P0B-M3", "p0b",
        "src/sclass/product/lifecycle_p0b.py",
        "tests/product/test_lifecycle_p0b.py",
        "bypass_retry_budget_exceeded",
        "Bypass retry budget allocation cap in evaluate_pd_ch2_007_p8_retry_budget",
        "if retry_budget_consumed > retry_budget_allocated:\n            return GateOutput(",
        "if False:\n            return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P0B-M4", "p0b",
        "src/sclass/product/lifecycle_p0b.py",
        "tests/product/test_lifecycle_p0b.py",
        "bypass_p11_p0_reentry_requirement",
        "Allow new work trigger to re-enter at non-P0 phase in evaluate_pd_ch2_008_p11_non_terminal_reentry",
        "if target_phase != \"P0\":\n            return GateOutput(",
        "if False:\n            return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P0B-M5", "p0b",
        "src/sclass/product/lifecycle_p0b.py",
        "tests/product/test_lifecycle_p0b.py",
        "bypass_done_claim_admissible_evidence",
        "Allow model DONE claim without admissible evidence in evaluate_pd_ch2_009_done_claim_evidence_closure",
        "if not admissible_evidence_present:\n            return GateOutput(",
        "if False:\n            return GateOutput(",
        expected_count=1,
    ),

    # -------------------------------------------------------------------------
    # Lane 3: P1P4 (lifecycle_p1_p4.py)
    # -------------------------------------------------------------------------
    MutantDef(
        "P1P4-M1", "p1p4",
        "src/sclass/product/lifecycle_p1_p4.py",
        "tests/product/test_lifecycle_p1_p4.py",
        "bypass_target_snapshot_resolved",
        "Allow unresolvable target snapshot in evaluate_pd_ch2_056_discovery_completeness",
        "if not target_snapshot_resolved:\n        return GateOutput(",
        "if False:\n        return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P1P4-M2", "p1p4",
        "src/sclass/product/lifecycle_p1_p4.py",
        "tests/product/test_lifecycle_p1_p4.py",
        "bypass_index_coverage_ratio",
        "Bypass minimum index coverage ratio requirement in evaluate_pd_ch2_056_discovery_completeness",
        "if index_coverage_ratio < min_index_coverage:\n        return GateOutput(",
        "if False:\n        return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P1P4-M3", "p1p4",
        "src/sclass/product/lifecycle_p1_p4.py",
        "tests/product/test_lifecycle_p1_p4.py",
        "bypass_skill_resolution_floor",
        "Bypass skill resolution and policy depth floors in evaluate_pd_ch2_057_skill_depth_precedence",
        "if not skills_resolved or not pinned_skill_digests or not policy_floor_respected:\n        return GateOutput(",
        "if False:\n        return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P1P4-M4", "p1p4",
        "src/sclass/product/lifecycle_p1_p4.py",
        "tests/product/test_lifecycle_p1_p4.py",
        "bypass_task_units_cap",
        "Allow task units to exceed policy cap in evaluate_pd_ch2_029_task_caps",
        "if task_units > max_units:\n        return GateOutput(",
        "if False:\n        return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P1P4-M5", "p1p4",
        "src/sclass/product/lifecycle_p1_p4.py",
        "tests/product/test_lifecycle_p1_p4.py",
        "bypass_work_graph_cycle_detection",
        "Bypass cycle detection in evaluate_pd_ch2_031_work_graph_acyclic",
        "if has_cycle(node):\n                return GateOutput(",
        "if False:\n                return GateOutput(",
        expected_count=1,
    ),

    # -------------------------------------------------------------------------
    # Lane 4: P3A (lifecycle_p3a.py)
    # -------------------------------------------------------------------------
    MutantDef(
        "P3A-M1", "p3a",
        "src/sclass/product/lifecycle_p3a.py",
        "tests/product/test_lifecycle_p3a.py",
        "bypass_requirement_semantic_coverage",
        "Allow requirement without coverage or applicability in evaluate_pd_ch2_013_requirement_coverage",
        "if not (has_cov or has_app):\n            return GateOutput(",
        "if False:\n            return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P3A-M2", "p3a",
        "src/sclass/product/lifecycle_p3a.py",
        "tests/product/test_lifecycle_p3a.py",
        "bypass_domain_entity_invariants",
        "Allow domain entity without invariants in evaluate_pd_ch2_014_domain_invariants",
        "if not invs:\n            return GateOutput(",
        "if False:\n            return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P3A-M3", "p3a",
        "src/sclass/product/lifecycle_p3a.py",
        "tests/product/test_lifecycle_p3a.py",
        "bypass_architecture_provenance",
        "Allow architecture element without attributable provenance in evaluate_pd_ch2_015_architecture_provenance",
        "if not (has_req or has_dec or has_dig):\n            return GateOutput(",
        "if False:\n            return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P3A-M4", "p3a",
        "src/sclass/product/lifecycle_p3a.py",
        "tests/product/test_lifecycle_p3a.py",
        "bypass_dependency_relationships",
        "Allow unrepresented material dependency in evaluate_pd_ch2_016_dependency_relationships",
        "if not src or not dst or (src, dst) not in represented_set:\n            return GateOutput(",
        "if False:\n            return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P3A-M5", "p3a",
        "src/sclass/product/lifecycle_p3a.py",
        "tests/product/test_lifecycle_p3a.py",
        "bypass_domain_model_substance",
        "Allow domain entity with names only in evaluate_pd_ch2_017_domain_model_substance",
        "if not fields_decl and not constraints_decl:\n            return GateOutput(",
        "if False:\n            return GateOutput(",
        expected_count=1,
    ),

    # -------------------------------------------------------------------------
    # Lane 5: P3B (lifecycle_p3b.py)
    # -------------------------------------------------------------------------
    MutantDef(
        "P3B-M1", "p3b",
        "src/sclass/product/lifecycle_p3b.py",
        "tests/product/test_lifecycle_p3b.py",
        "bypass_undecidable_fragment_check",
        "Allow self-asserted PASS on undecidable fragment in evaluate_pd_ch2_020_decidable_invariants",
        "if not is_supported or frag not in DECIDABLE_FRAGMENTS:\n            if self_claimed_pass:\n                return GateOutput(",
        "if False:\n            if False:\n                return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P3B-M2", "p3b",
        "src/sclass/product/lifecycle_p3b.py",
        "tests/product/test_lifecycle_p3b.py",
        "bypass_cross_entity_cardinality",
        "Allow cross-entity constraint lacking cardinality in evaluate_pd_ch2_021_cross_entity_constraints",
        "if not rel or not card:\n            return GateOutput(",
        "if False:\n            return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P3B-M3", "p3b",
        "src/sclass/product/lifecycle_p3b.py",
        "tests/product/test_lifecycle_p3b.py",
        "bypass_change_surface_closure",
        "Allow uncovered change surface boundary in evaluate_pd_ch2_022_change_surface_boundary_closure",
        "if boundary not in covered_nodes:\n            return GateOutput(",
        "if False:\n            return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P3B-M4", "p3b",
        "src/sclass/product/lifecycle_p3b.py",
        "tests/product/test_lifecycle_p3b.py",
        "bypass_data_flow_contracts",
        "Allow data flow lacking contract or transform in evaluate_pd_ch2_023_boundary_data_flow_contracts",
        "if not (src and dst and contract and transform):\n            return GateOutput(",
        "if False:\n            return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P3B-M5", "p3b",
        "src/sclass/product/lifecycle_p3b.py",
        "tests/product/test_lifecycle_p3b.py",
        "bypass_interface_signature_agreement",
        "Allow interface signature mismatch with domain contract in evaluate_pd_ch2_024_interface_signatures_typed_contracts",
        "if not sig_type or sig_type != contract_type or sig_type != predicate_type:\n            return GateOutput(",
        "if False:\n            return GateOutput(",
        expected_count=1,
    ),

    # -------------------------------------------------------------------------
    # Lane 6: P3C (lifecycle_p3c_p8_p10.py)
    # -------------------------------------------------------------------------
    MutantDef(
        "P3C-M1", "p3c",
        "src/sclass/product/lifecycle_p3c_p8_p10.py",
        "tests/product/test_lifecycle_p3c_p8_p10.py",
        "bypass_adr_stale_or_unbound",
        "Allow stale or un-digest-bound ADR in evaluate_pd_ch2_026_adr_design_digest_binding",
        "if not dig or not lint_passed or is_stale:\n            return GateOutput(",
        "if False:\n            return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P3C-M2", "p3c",
        "src/sclass/product/lifecycle_p3c_p8_p10.py",
        "tests/product/test_lifecycle_p3c_p8_p10.py",
        "bypass_duplicate_must_ids",
        "Allow duplicate MUST ID in evaluate_pd_ch2_028_unique_must_ids",
        "if mid in seen:\n            return GateOutput(",
        "if False:\n            return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P3C-M3", "p3c",
        "src/sclass/product/lifecycle_p3c_p8_p10.py",
        "tests/product/test_lifecycle_p3c_p8_p10.py",
        "bypass_p8_retry_exhaustion_stop",
        "Allow P8 repair continuation upon budget exhaustion in evaluate_pd_ch2_051_p8_retry_budget_exhaustion",
        "if retry_budget_remaining <= 0:\n        return GateOutput(",
        "if False:\n        return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P3C-M4", "p3c",
        "src/sclass/product/lifecycle_p3c_p8_p10.py",
        "tests/product/test_lifecycle_p3c_p8_p10.py",
        "bypass_p9_open_mandatory_findings",
        "Allow P9 closure with open mandatory findings in evaluate_pd_ch2_052_p9_task_aggregation_findings_closure",
        "if open_mandatory_findings:\n        return GateOutput(",
        "if False:\n        return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P3C-M5", "p3c",
        "src/sclass/product/lifecycle_p3c_p8_p10.py",
        "tests/product/test_lifecycle_p3c_p8_p10.py",
        "override_p10_kernel_denial",
        "Allow product checks to override frozen kernel DENIED in evaluate_pd_ch2_053_p10_kernel_release_evaluation",
        "if kernel_release_evaluation.upper() in (\"DENIED\", \"DENY\"):\n        return ReleaseEvaluationOutput(",
        "if False:\n        return ReleaseEvaluationOutput(",
        expected_count=1,
    ),

    # -------------------------------------------------------------------------
    # Lane 7: P5 (lifecycle_p5.py)
    # -------------------------------------------------------------------------
    MutantDef(
        "P5-M1", "p5",
        "src/sclass/product/lifecycle_p5.py",
        "tests/product/test_lifecycle_p5.py",
        "bypass_test_delta_precedence",
        "Allow implementation delta before test delta in evaluate_pd_ch2_033_delta_sequence",
        "if impl_delta_seq <= test_delta_seq:\n        return GateOutput(",
        "if False:\n        return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P5-M2", "p5",
        "src/sclass/product/lifecycle_p5.py",
        "tests/product/test_lifecycle_p5.py",
        "bypass_failure_class_match",
        "Allow mismatched failure class in evaluate_pd_ch2_034_red_run_validity",
        "if failure_class != designed_class:\n        return GateOutput(",
        "if False:\n        return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P5-M3", "p5",
        "src/sclass/product/lifecycle_p5.py",
        "tests/product/test_lifecycle_p5.py",
        "bypass_executable_spec_prose_check",
        "Allow prose-only or unbounded spec in evaluate_pd_ch2_035_executable_spec_constraints",
        "if is_prose_only or not is_executable_f1_f2 or not finite_domain:\n        return GateOutput(",
        "if False:\n        return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P5-M4", "p5",
        "src/sclass/product/lifecycle_p5.py",
        "tests/product/test_lifecycle_p5.py",
        "bypass_adapter_qualification",
        "Allow unqualified adapter in evaluate_pd_ch2_036_adapter_qualification",
        "if not is_f10_qualified or adapter_name not in qualified_adapters:\n        return GateOutput(",
        "if False:\n        return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P5-M5", "p5",
        "src/sclass/product/lifecycle_p5.py",
        "tests/product/test_lifecycle_p5.py",
        "bypass_test_input_set_binding",
        "Allow primary test digest unbound in TestInputSet in evaluate_pd_ch2_046_test_input_set_binding",
        "if not primary_test_digest or primary_test_digest not in bound_test_input_set.values():\n        return GateOutput(",
        "if False:\n        return GateOutput(",
        expected_count=1,
    ),

    # -------------------------------------------------------------------------
    # Lane 8: P6 (lifecycle_p6.py)
    # -------------------------------------------------------------------------
    MutantDef(
        "P6-M1", "p6",
        "src/sclass/product/lifecycle_p6.py",
        "tests/product/test_lifecycle_p6.py",
        "bypass_execution_gate_authorization",
        "Allow implementation write without ExecutionGate auth in evaluate_pd_ch2_037_execution_gate_authorization",
        "if not has_execution_gate_auth:\n        return GateOutput(",
        "if False:\n        return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P6-M2", "p6",
        "src/sclass/product/lifecycle_p6.py",
        "tests/product/test_lifecycle_p6.py",
        "bypass_scope_growth_stop",
        "Allow out-of-scope write to continue in evaluate_pd_ch2_038_scope_growth_stop",
        "if is_out_of_scope:\n        return GateOutput(",
        "if False:\n        return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P6-M3", "p6",
        "src/sclass/product/lifecycle_p6.py",
        "tests/product/test_lifecycle_p6.py",
        "bypass_claimed_symbols_presence",
        "Allow absent claimed symbol in evaluate_pd_ch2_039_implementation_claims",
        "if sym not in post_delta_symbols:\n            return GateOutput(",
        "if False:\n            return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P6-M4", "p6",
        "src/sclass/product/lifecycle_p6.py",
        "tests/product/test_lifecycle_p6.py",
        "bypass_kernel_receipt_override",
        "Allow canonical delta without kernel receipt in evaluate_pd_ch2_040_canonical_delta_kernel_receipt",
        "if kernel_denied or not has_kernel_receipt or not kernel_receipt_digest:\n        return GateOutput(",
        "if False:\n        return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P6-M5", "p6",
        "src/sclass/product/lifecycle_p6.py",
        "tests/product/test_lifecycle_p6.py",
        "bypass_p6_modifies_test_input_set",
        "Allow implementation to modify frozen TestInputSet in evaluate_pd_ch2_048_test_input_set_exclusion_check",
        "if p6_modifies_test_input_set:\n        return GateOutput(",
        "if False:\n        return GateOutput(",
        expected_count=1,
    ),

    # -------------------------------------------------------------------------
    # Lane 9: P7 (lifecycle_p7.py)
    # -------------------------------------------------------------------------
    MutantDef(
        "P7-M1", "p7",
        "src/sclass/product/lifecycle_p7.py",
        "tests/product/test_lifecycle_p7.py",
        "bypass_evidence_binding",
        "Allow verification without frozen evidence binding in evaluate_pd_ch2_041_evidence_binding",
        "if not (evidence_identity_bound and current_target_bound and current_step_bound):\n        return GateOutput(",
        "if False:\n        return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P7-M2", "p7",
        "src/sclass/product/lifecycle_p7.py",
        "tests/product/test_lifecycle_p7.py",
        "bypass_p7_adapter_qualification",
        "Allow unqualified adapter in evaluate_pd_ch2_042_adapter_qualification",
        "if not is_f10_qualified or adapter_name not in qualified_adapters:\n        return GateOutput(",
        "if False:\n        return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P7-M3", "p7",
        "src/sclass/product/lifecycle_p7.py",
        "tests/product/test_lifecycle_p7.py",
        "bypass_independence_floor",
        "Allow independence below required floor in evaluate_pd_ch2_043_independence_floor",
        "if independence_level < required_floor:\n        return GateOutput(",
        "if False:\n        return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P7-M4", "p7",
        "src/sclass/product/lifecycle_p7.py",
        "tests/product/test_lifecycle_p7.py",
        "bypass_freshness_check",
        "Allow stale evidence digest in evaluate_pd_ch2_044_freshness_predicate",
        "if is_stale or evidence_digest != current_code_digest:\n        return GateOutput(",
        "if False:\n        return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P7-M5", "p7",
        "src/sclass/product/lifecycle_p7.py",
        "tests/product/test_lifecycle_p7.py",
        "bypass_deterministic_rerun_check",
        "Allow non-deterministic test rerun outcomes in evaluate_pd_ch2_050_deterministic_rerun",
        "if len(distinct) > 1:\n        return GateOutput(",
        "if False:\n        return GateOutput(",
        expected_count=1,
    ),

    # -------------------------------------------------------------------------
    # Lane 10: P11 (lifecycle_p11.py)
    # -------------------------------------------------------------------------
    MutantDef(
        "P11-M1", "p11",
        "src/sclass/product/lifecycle_p11.py",
        "tests/product/test_lifecycle_p11.py",
        "bypass_signal_source_event_ref",
        "Allow monitoring signal without source event ref in evaluate_pd_ch2_054_signal",
        "if not source_event or source_event == \"absent\":\n        return GateOutput(",
        "if False:\n        return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P11-M2", "p11",
        "src/sclass/product/lifecycle_p11.py",
        "tests/product/test_lifecycle_p11.py",
        "bypass_autonomous_mutation_rejection",
        "Allow signal to propose autonomous workspace mutation in evaluate_pd_ch2_054_signal",
        "if action == \"mutate_workspace\" or \"mutate\" in str(action).lower():\n        return GateOutput(",
        "if False:\n        return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P11-M3", "p11",
        "src/sclass/product/lifecycle_p11.py",
        "tests/product/test_lifecycle_p11.py",
        "bypass_evaluator_record_ref",
        "Allow phase skip without evaluator record in evaluate_pd_ch2_058_applicability",
        "if not eval_ref:\n        return GateOutput(",
        "if False:\n        return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P11-M4", "p11",
        "src/sclass/product/lifecycle_p11.py",
        "tests/product/test_lifecycle_p11.py",
        "bypass_flow_order_preservation",
        "Allow phase ordering inversion in evaluate_pd_ch2_060_flow_order",
        "if indices != sorted(indices):\n        return GateOutput(",
        "if False:\n        return GateOutput(",
        expected_count=1,
    ),
    MutantDef(
        "P11-M5", "p11",
        "src/sclass/product/lifecycle_p11.py",
        "tests/product/test_lifecycle_p11.py",
        "bypass_question_budget_blocker_stop",
        "Allow question budget exhaustion without keeping blockers open in evaluate_pd_ch2_063_question_budget",
        "if q_asked > q_budget and open_blockers:\n        # If treated as exhausted-complete without resolving blockers\n        if payload.get(\"treated_as_complete\", True):\n            return GateOutput(",
        "if False:\n        if False:\n            return GateOutput(",
        expected_count=1,
    ),
]


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run_one_mutant(m: MutantDef, log_dir: Optional[Path] = None) -> Tuple[str, str, str, float, str]:
    """Run one mutant under strict failure validation and occurrence pre-checks.

    Returns:
        (execution_status, result, failing_test_or_reason, elapsed_seconds, evidence)
    """
    target_path = REPO_ROOT / m.target_rel_path
    original_bytes = target_path.read_bytes()
    orig_sha = sha256_file(target_path)
    original_text = original_bytes.decode("utf-8")

    # Item 2: Validate expected occurrence count before mutation
    actual_count = original_text.count(m.target_str)
    if actual_count != m.expected_count:
        reason = f"Target occurrence mismatch: expected {m.expected_count}, got {actual_count}"
        if log_dir:
            (log_dir / f"{m.mutant_id}.log").write_text(
                f"=== MUTANT {m.mutant_id} ({m.name}) ===\n"
                f"Target: {m.target_rel_path}\n"
                f"Expected Count: {m.expected_count} | Actual Count: {actual_count}\n"
                f"Result: INVALID\nReason: {reason}\n",
                encoding="utf-8"
            )
        return "NOT_EXECUTED", "INVALID", reason, 0.0, reason

    t0 = time.time()
    exec_status = "NOT_EXECUTED"
    result = "INVALID"
    failing_test = "None"
    evidence = ""
    out = ""

    # Items 1, 2, 3: Full try/except/finally wrapping mutation and execution
    try:
        mutated_text = original_text.replace(m.target_str, m.replacement_str)
        target_path.write_text(mutated_text, encoding="utf-8")

        # Run pytest with timeout and catch all exceptions
        cmd = [PYTEST_BIN, m.test_rel_path, "-q", "--no-header"]
        res: Optional[subprocess.CompletedProcess] = None
        try:
            res = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=60)
            elapsed = time.time() - t0
            out = res.stdout + ("\n" + res.stderr if res.stderr else "")
        except subprocess.TimeoutExpired as te:
            elapsed = time.time() - t0
            out = f"TIMEOUT: pytest execution timed out after 60s\nSTDOUT:\n{te.stdout or ''}\nSTDERR:\n{te.stderr or ''}\n"
            res = None
        except Exception as sub_exc:
            elapsed = time.time() - t0
            out = f"SUBPROCESS_ERROR: {type(sub_exc).__name__}: {sub_exc}\n{traceback.format_exc()}\n"
            res = None

        if res is None:
            exec_status = "NOT_EXECUTED"
            result = "INVALID"
            failing_test = "Subprocess/Timeout Failure"
            evidence = out.strip().splitlines()[0] if out.strip() else "Subprocess execution failed"
        else:
            lower_out = out.lower()
            has_collection_or_infra_error = (
                "error collecting" in lower_out or
                "collection error" in lower_out or
                "importerror" in lower_out or
                "modulenotfounderror" in lower_out or
                "syntaxerror" in lower_out or
                "interrupted:" in lower_out or
                "internalerror" in lower_out or
                "usageerror" in lower_out or
                "pytest: error:" in lower_out or
                "errors occurred during collection" in lower_out
            )

            # Blocker 1: Genuine pytest failed-test summary verification:
            # 1. Match lines starting with "FAILED <nodeid>" in short test summary info
            failed_test_summary_lines: List[str] = []
            for line in out.splitlines():
                m_fail = re.match(r"^FAILED\s+([a-zA-Z0-9_/\.\\-]+::[a-zA-Z0-9_]+)", line.strip())
                if m_fail:
                    failed_test_summary_lines.append(m_fail.group(1))

            # 2. Match pytest final summary failure count: e.g. "5 failed, 20 passed" or "1 failed"
            summary_failed_match = re.search(r"=+\s*(?:(?:\d+\s+passed,\s*)?(\d+)\s+failed)", out)
            if not summary_failed_match:
                summary_failed_match = re.search(r"\b(\d+)\s+failed\b", out)

            has_failed_summary_count = bool(summary_failed_match and int(summary_failed_match.group(1)) > 0)
            has_genuine_test_failure = bool(failed_test_summary_lines) and has_failed_summary_count

            if res.returncode == 1 and has_genuine_test_failure and not has_collection_or_infra_error:
                exec_status = "EXECUTED"
                result = "KILLED"
                failing_test = failed_test_summary_lines[0]
                fail_count = summary_failed_match.group(1) if summary_failed_match else "1"
                evidence = f"{fail_count} failed: {failing_test}"
            elif res.returncode == 0:
                exec_status = "EXECUTED"
                result = "SURVIVED"
                failing_test = "None (Passed)"
                evidence = "Test suite passed unexpectedly (Mutant survived)"
            else:
                # Collection error, import error, missing summary failure or abnormal exit code -> INVALID
                exec_status = "NOT_EXECUTED"
                result = "INVALID"
                if has_collection_or_infra_error:
                    failing_test = "Collection/Import/Infra Error"
                    evidence = "Collection, import, or infrastructure error occurred"
                elif not has_genuine_test_failure:
                    failing_test = f"No genuine test failure summary (code {res.returncode})"
                    evidence = f"Exit code {res.returncode} without verified pytest failure summary"
                else:
                    failing_test = f"Abnormal exit code {res.returncode}"
                    evidence = f"Pytest exited with unexpected code {res.returncode}"

    except Exception as exc:
        # Blocker 3: Unexpected mutation or execution exceptions produce recorded INVALID
        elapsed = time.time() - t0
        exec_status = "NOT_EXECUTED"
        result = "INVALID"
        failing_test = f"Exception: {type(exc).__name__}"
        evidence = f"Unexpected mutation exception: {type(exc).__name__}: {exc}"
        out = f"UNEXPECTED_EXCEPTION:\n{traceback.format_exc()}\n"
    finally:
        # Blocker 3 & Item 3: Exact byte preservation & SHA-256 check under all paths
        target_path.write_bytes(original_bytes)
        restored_sha = sha256_file(target_path)
        assert restored_sha == orig_sha, f"Byte restoration mismatch on {m.target_rel_path}"

    if log_dir:
        (log_dir / f"{m.mutant_id}.log").write_text(
            f"=== MUTANT {m.mutant_id} ({m.name}) ===\n"
            f"Target: {m.target_rel_path}\n"
            f"Test: {m.test_rel_path}\n"
            f"Expected Count: {m.expected_count} | Actual Count: {actual_count}\n"
            f"Execution Status: {exec_status} | Result: {result}\n"
            f"Failing Test Summary: {failing_test}\n"
            f"Elapsed: {elapsed:.3f}s\n\n"
            f"--- PYTEST OUTPUT ---\n{out}\n",
            encoding="utf-8"
        )

    return exec_status, result, failing_test, elapsed, evidence


def main():
    print("=== S-CLASS M0 ITERATION 2: E4 MUTATION BATTERY (STRICT SUMMARY CLASSIFIER) ===")
    print(f"Total Mutants: {len(MUTANTS)} across 10 lanes (5 mutants/lane)")
    print(f"Testing environment: {PYTEST_BIN}")
    print("=" * 80)

    out_dir = REPO_ROOT / "delivery-evidence"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_logs_dir = out_dir / "raw_mutant_logs"
    raw_logs_dir.mkdir(parents=True, exist_ok=True)

    results = []
    survived_mutants = []
    invalid_mutants = []

    for i, m in enumerate(MUTANTS, 1):
        print(f"[{i:02d}/50] Lane {m.lane.upper():<5} | {m.mutant_id:<8} | {m.name:<35} ... ", end="", flush=True)
        exec_status, result, test_name, elapsed, evidence = run_one_mutant(m, log_dir=raw_logs_dir)
        print(f"{result} ({elapsed:.2f}s) - {test_name[:50]}")
        results.append({
            "mutant_id": m.mutant_id,
            "lane": m.lane,
            "name": m.name,
            "description": m.description,
            "target_file": m.target_rel_path,
            "test_file": m.test_rel_path,
            "expected_count": m.expected_count,
            "execution_status": exec_status,
            "result": result,
            "killed_by": test_name,
            "elapsed_seconds": round(elapsed, 3),
            "evidence": evidence,
        })
        if result == "SURVIVED":
            survived_mutants.append(m)
        elif result == "INVALID":
            invalid_mutants.append(m)

    executed_count = sum(1 for r in results if r["execution_status"] == "EXECUTED")
    killed_count = sum(1 for r in results if r["result"] == "KILLED")
    survived_count = len(survived_mutants)
    invalid_count = len(invalid_mutants)
    kill_rate = (killed_count / executed_count * 100.0) if executed_count > 0 else 0.0

    print("=" * 80)
    print("MUTATION BATTERY SUMMARY:")
    print(f"Total: {len(MUTANTS)} | Executed: {executed_count} | Killed: {killed_count} | Survived: {survived_count} | Invalid: {invalid_count}")
    print(f"Kill Rate (Killed / Executed): {kill_rate:.1f}%")

    if survived_mutants:
        print("\nSURVIVED MUTANTS:")
        for sm in survived_mutants:
            print(f"  - [{sm.lane.upper()}] {sm.mutant_id}: {sm.name}")

    if invalid_mutants:
        print("\nINVALID MUTANTS (NOT EXECUTED):")
        for im in invalid_mutants:
            print(f"  - [{im.lane.upper()}] {im.mutant_id}: {im.name}")

    # Save results to JSON (in delivery-evidence/)
    json_path = out_dir / "e4_mutant_matrix.json"
    json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWrote full mutant matrix to {json_path}")

    # Generate Markdown Table (50-row result table in delivery-evidence/)
    md_lines = [
        "# E4 Mutation Testing Matrix (50 Hand-Written Mutants across 10 Lanes)",
        "",
        f"- **Total Mutants:** {len(MUTANTS)}",
        f"- **Executed:** {executed_count} ({(executed_count / len(MUTANTS) * 100.0):.1f}%)",
        f"- **Killed:** {killed_count}",
        f"- **Survived:** {survived_count}",
        f"- **Invalid:** {invalid_count}",
        f"- **Kill Rate:** {kill_rate:.1f}%",
        "",
        "| Mutant ID | Lane | Expected Count | Target Evaluator File | Description | Execution Status | Result | Killed By Test | Elapsed |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        md_lines.append(
            f"| `{r['mutant_id']}` | `{r['lane'].upper()}` | {r['expected_count']} | `{Path(r['target_file']).name}` | {r['description']} | **{r['execution_status']}** | **{r['result']}** | `{r['killed_by'][:60]}` | {r['elapsed_seconds']}s |"
        )
    md_path = out_dir / "e4_mutant_matrix.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"Wrote Markdown report table to {md_path}")
    print(f"Raw per-mutant logs saved to {raw_logs_dir}/")

    return 0 if (survived_count == 0 and invalid_count == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
