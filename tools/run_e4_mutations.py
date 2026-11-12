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
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Set

REPO_ROOT = Path(__file__).resolve().parent.parent
if Path("/home/runner/venv-3.12/bin/pytest").exists():
    PYTEST_CMD = ["/home/runner/venv-3.12/bin/pytest"]
elif Path("/usr/bin/pytest").exists():
    PYTEST_CMD = ["/usr/bin/pytest"]
else:
    PYTEST_CMD = [sys.executable, "-m", "pytest"]

PYTEST_BIN = " ".join(PYTEST_CMD)


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


def normalize_node_id(node_id: str) -> str:
    """Normalize a pytest summary node ID to canonical forward-slash path format."""
    parts = node_id.strip().split("::")
    file_part = parts[0].replace("\\", "/").lstrip("./")
    return "::".join([file_part] + parts[1:])


def canonical_junit_node_id(
    tc_file: Optional[str],
    tc_class: Optional[str],
    tc_name: str,
    known_node_ids: Optional[List[str]] = None,
) -> str:
    """
    Establish canonical pytest node ID from JUnit XML attributes: file, classname, and name.
    Preserves exact parametrized test names (e.g. test_func[param1]).
    """
    tc_file = (tc_file or "").strip()
    tc_class = (tc_class or "").strip()
    tc_name = (tc_name or "").strip()

    # 1. If explicit file attribute is provided in XML
    if tc_file:
        norm_file = tc_file.replace("\\", "/").lstrip("./")
        if not norm_file.endswith(".py"):
            norm_file += ".py"
        mod_from_file = norm_file[:-3].replace("/", ".")
        if tc_class and tc_class.startswith(mod_from_file + "."):
            cls_part = tc_class[len(mod_from_file) + 1:].replace(".", "::")
            return f"{norm_file}::{cls_part}::{tc_name}"
        elif tc_class and tc_class != mod_from_file and "." not in tc_class:
            return f"{norm_file}::{tc_class}::{tc_name}"
        else:
            return f"{norm_file}::{tc_name}"

    # 2. If file attribute is omitted (standard pytest behavior), deduce canonical file from module
    if known_node_ids:
        for kn in known_node_ids:
            kn_file = kn.split("::")[0]
            kn_mod = kn_file[:-3].replace("/", ".") if kn_file.endswith(".py") else kn_file.replace("/", ".")
            if tc_class == kn_mod:
                return f"{kn_file}::{tc_name}"
            if tc_class.startswith(kn_mod + "."):
                cls_part = tc_class[len(kn_mod) + 1:].replace(".", "::")
                return f"{kn_file}::{cls_part}::{tc_name}"

    # Fallback module to path conversion when not in known_node_ids
    if tc_class:
        file_candidate = tc_class.replace(".", "/") + ".py"
        return f"{file_candidate}::{tc_name}"

    return f"::{tc_name}"


def classify_pytest_output(
    returncode: Optional[int],
    out: str,
    junit_xml: Optional[str] = None,
    require_junit: bool = False,
) -> Tuple[str, str, str, str]:
    """
    Strictly classify pytest execution results to ensure only genuine pytest assertion
    failures (AssertionError) with exact one-to-one testcase identity produce KILLED.

    Returns:
        (exec_status, result, failing_test, evidence)
        where exec_status is "EXECUTED" or "NOT_EXECUTED"
        and result is "KILLED", "SURVIVED", or "INVALID"
    """
    if returncode is None:
        first_line = out.strip().splitlines()[0] if out.strip() else "Execution failed"
        return "NOT_EXECUTED", "INVALID", "Subprocess/Timeout Failure", first_line

    if returncode == 0:
        return "EXECUTED", "SURVIVED", "None (Passed)", "Test suite passed unexpectedly (Mutant survived)"

    if returncode != 1:
        return "NOT_EXECUTED", "INVALID", f"Abnormal exit code {returncode}", f"Pytest exited with abnormal exit code {returncode}"

    lower_out = out.lower()
    infra_markers = [
        "collection error",
        "error collecting",
        "errors occurred during collection",
        "importerror",
        "modulenotfounderror",
        "syntaxerror",
        "interrupted:",
        "internalerror",
        "pytest: error:",
        "usageerror",
        "errors were found during",
        "during collection",
    ]
    for marker in infra_markers:
        if marker in lower_out:
            return "NOT_EXECUTED", "INVALID", f"Infrastructure Error: {marker}", f"Output contains infrastructure error marker '{marker}'"

    stripped_out = out.rstrip()
    if not stripped_out:
        return "NOT_EXECUTED", "INVALID", "Empty output", "Pytest produced empty output"

    lines = [line.strip() for line in stripped_out.splitlines() if line.strip()]
    if not lines:
        return "NOT_EXECUTED", "INVALID", "Empty lines", "Pytest output contains no non-empty lines"

    # Anchored final pytest summary footer pattern matching the final footer line
    final_summary_footer_re = re.compile(
        r"^(?:=+\s*)?(\d+)\s+failed(?:,\s*\d+\s+passed)?(?:,\s*\d+\s+skipped)?(?:,\s*\d+\s+deselected)?(?:,\s*\d+\s+warnings?)?(?:\s+in\s+[\d\.]+s)?(?:\s*=+)?$"
    )
    m_footer = final_summary_footer_re.match(lines[-1])
    if not m_footer:
        return "NOT_EXECUTED", "INVALID", "Missing final summary footer", f"Final output line '{lines[-1]}' does not match pytest summary footer"

    # Reject if final footer mentions any errors (e.g. setup/teardown/collection errors)
    if "error" in lines[-1].lower():
        return "NOT_EXECUTED", "INVALID", "Summary contains errors", f"Final summary footer indicates errors: {lines[-1]}"

    fail_count = int(m_footer.group(1))
    if fail_count <= 0:
        return "NOT_EXECUTED", "INVALID", "Zero failure count", f"Pytest final summary reported {fail_count} failures"

    # Locate the LAST short test summary info section header
    header_matches = list(re.finditer(r"=+\s*short test summary info\s*=+", stripped_out))
    if not header_matches:
        return "NOT_EXECUTED", "INVALID", "Missing short test summary", "No short test summary info section found"

    last_header = header_matches[-1]

    # Security check: Check if a fake summary was appended after genuine output
    pre_header_text = stripped_out[:last_header.start()]
    if re.search(r"^\s*(?:=+\s*)?\d+\s+passed(?:\s+in\s+[\d\.]+s|\s*=+)", pre_header_text, re.MULTILINE):
        return "NOT_EXECUTED", "INVALID", "Appended fake summary", "Forged pytest summary detected appended after passing run"

    # The text between the last header and the final line
    summary_tail = stripped_out[last_header.end():].rstrip()
    summary_lines = [l.strip() for l in summary_tail.splitlines() if l.strip()]

    # The last line of summary_lines must be identical to lines[-1] (the final summary footer)
    if not summary_lines or summary_lines[-1] != lines[-1]:
        return "NOT_EXECUTED", "INVALID", "Corrupted summary tail", "Summary section is not immediately adjacent to final summary footer"

    # Entries in short test summary info are lines between the header and the footer line
    entry_lines = summary_lines[:-1]
    if not entry_lines:
        return "NOT_EXECUTED", "INVALID", "Empty summary section", "Short test summary info section contains no entries"

    failed_node_ids: List[str] = []
    seen_summary_nodes: Set[str] = set()
    for entry in entry_lines:
        if entry.startswith("ERROR ") or entry.startswith("ERROR:"):
            return "NOT_EXECUTED", "INVALID", "Setup/Teardown Error in summary", f"Summary section contains error: {entry}"

        m_node = re.match(r"^FAILED\s+([a-zA-Z0-9_/\.\\-]+::[a-zA-Z0-9_\[\]\-\.]+)", entry)
        if m_node:
            raw_node_id = m_node.group(1)
            norm_node_id = normalize_node_id(raw_node_id)
            if norm_node_id in seen_summary_nodes:
                return "NOT_EXECUTED", "INVALID", "Duplicate summary node", f"Summary declares duplicate failure for '{norm_node_id}'"
            seen_summary_nodes.add(norm_node_id)

            # Whitelist verification in short summary line if exception is present
            m_summary_exc = re.search(r"\s+-\s+([a-zA-Z0-9_\.]+)(?::|\s|$)", entry)
            if m_summary_exc:
                exc_type = m_summary_exc.group(1)
                is_assert_like = (
                    exc_type == "AssertionError"
                    or exc_type.startswith("assert")
                    or exc_type.startswith("A.")
                    or exc_type.startswith("As")
                )
                if not is_assert_like:
                    return "NOT_EXECUTED", "INVALID", f"Non-assertion failure in summary: {exc_type}", f"Summary entry declares non-assertion failure {exc_type}: {entry}"

            failed_node_ids.append(norm_node_id)
        elif any(entry.startswith(prefix) for prefix in ["PASSED ", "SKIPPED ", "XFAIL ", "XPASS "]):
            continue
        else:
            return "NOT_EXECUTED", "INVALID", "Unrecognized entry in summary", f"Summary section contains non-summary line: {entry}"

    if not failed_node_ids:
        return "NOT_EXECUTED", "INVALID", "No genuine FAILED node IDs", "No valid FAILED test entries in final short test summary info"

    if len(failed_node_ids) != fail_count:
        return "NOT_EXECUTED", "INVALID", "Failure count mismatch", f"Found {len(failed_node_ids)} FAILED entries in summary, but footer declared {fail_count}"

    # Verify structured JUnit XML if provided or required
    if require_junit and junit_xml is None:
        return "NOT_EXECUTED", "INVALID", "Missing JUnit XML", "Mutant execution did not produce required JUnit XML report"

    if junit_xml is not None:
        if not junit_xml.strip():
            return "NOT_EXECUTED", "INVALID", "Empty JUnit XML", "JUnit XML content is empty"
        try:
            root = ET.fromstring(junit_xml)
        except Exception as xml_err:
            return "NOT_EXECUTED", "INVALID", f"Malformed JUnit XML: {xml_err}", f"Failed to parse JUnit XML: {xml_err}"

        # Check for errors in XML
        xml_errors = root.findall(".//error")
        if xml_errors:
            return "NOT_EXECUTED", "INVALID", "JUnit XML contains errors", f"JUnit XML records {len(xml_errors)} error(s)"

        for ts in root.findall(".//testsuite"):
            if int(ts.get("errors", 0)) > 0:
                return "NOT_EXECUTED", "INVALID", "JUnit XML testsuite errors", f"Testsuite declares errors={ts.get('errors')}"

        xml_failures = root.findall(".//failure")
        if not xml_failures:
            return "NOT_EXECUTED", "INVALID", "No JUnit XML failures", "Pytest exited 1 but JUnit XML records 0 failures"

        if len(xml_failures) != fail_count:
            return "NOT_EXECUTED", "INVALID", "Inconsistent failure count", f"JUnit XML has {len(xml_failures)} failure(s) but summary declared {fail_count}"

        # Check for duplicate testcases and extract failed testcases
        all_testcases = root.findall(".//testcase")
        seen_all_xml_cases: Set[str] = set()
        xml_failed_nodes: List[str] = []

        for tc in all_testcases:
            tc_name = (tc.get("name") or "").strip()
            tc_class = (tc.get("classname") or "").strip()
            tc_file = (tc.get("file") or "").strip()

            tc_canonical_id = canonical_junit_node_id(tc_file, tc_class, tc_name, known_node_ids=failed_node_ids)

            # Check for duplicate testcase elements in XML
            if tc_canonical_id in seen_all_xml_cases:
                return "NOT_EXECUTED", "INVALID", "Duplicate XML testcase records", f"JUnit XML contains duplicate testcase element for '{tc_canonical_id}'"
            seen_all_xml_cases.add(tc_canonical_id)

            tc_fails = tc.findall("failure")
            if not tc_fails:
                continue

            # Check for duplicate failure tags within the same testcase
            if len(tc_fails) > 1:
                return "NOT_EXECUTED", "INVALID", "Duplicate failure records", f"Testcase '{tc_canonical_id}' contains {len(tc_fails)} failure elements"

            f = tc_fails[0]
            fail_type = (f.get("type") or "").strip()
            fail_msg = (f.get("message") or "").strip()
            fail_text = (f.text or "").strip()

            # Extract exception type if not declared as XML attribute
            if not fail_type and fail_msg:
                if fail_msg.startswith("assert ") or fail_msg.startswith("assert\n") or fail_msg.startswith("AssertionError"):
                    fail_type = "AssertionError"
                else:
                    m_msg = re.match(r"^([a-zA-Z0-9_\.]+)", fail_msg)
                    if m_msg:
                        fail_type = m_msg.group(1).rstrip(":")
            if not fail_type and fail_text:
                m_txt = re.search(r"^[ \t]*E[ \t]+([A-Z][a-zA-Z0-9_]*(?:Error|Exception|Violation))\b", fail_text, re.MULTILINE)
                if m_txt:
                    fail_type = m_txt.group(1).rstrip(":")

            # Whitelist: failure type MUST strictly be AssertionError
            if fail_type != "AssertionError":
                return "NOT_EXECUTED", "INVALID", f"Non-assertion JUnit failure: {fail_type}", f"Test {tc_name} failed with non-assertion type '{fail_type}'"

            if fail_msg and not fail_msg.startswith("AssertionError") and not fail_msg.startswith("assert ") and not fail_msg.startswith("assert\n"):
                m_msg_exc = re.match(r"^([a-zA-Z0-9_\.]+(?:Error|Exception|Violation)):", fail_msg)
                if m_msg_exc and m_msg_exc.group(1) != "AssertionError":
                    return "NOT_EXECUTED", "INVALID", f"Non-assertion JUnit failure: {m_msg_exc.group(1)}", f"Test {tc_name} failure message indicates {m_msg_exc.group(1)}"

            # Also verify that failure traceback does not contain non-assertion exceptions
            if fail_text:
                txt_excs = re.findall(r"^[ \t]*E[ \t]+([A-Z][a-zA-Z0-9_]*(?:Error|Exception|Violation))\b", fail_text, re.MULTILINE)
                for te in txt_excs:
                    if te != "AssertionError":
                        return "NOT_EXECUTED", "INVALID", f"Non-assertion exception in JUnit traceback: {te}", f"Test {tc_name} traceback contains {te}"

            xml_failed_nodes.append(tc_canonical_id)

        # Enforce exact one-to-one correspondence (bijection) between summary failures and XML failures
        if len(xml_failed_nodes) != len(failed_node_ids):
            return "NOT_EXECUTED", "INVALID", "Failure count mismatch", f"XML has {len(xml_failed_nodes)} failed testcase(s), but summary declared {len(failed_node_ids)}"

        # Forward match: every failed summary node must correspond to exactly one failed XML testcase
        for s_node in failed_node_ids:
            matching_xml = [x for x in xml_failed_nodes if x == s_node]
            if len(matching_xml) == 0:
                return "NOT_EXECUTED", "INVALID", "Unmatched summary node", f"Summary node '{s_node}' has no exact matching JUnit XML testcase"
            if len(matching_xml) > 1:
                return "NOT_EXECUTED", "INVALID", "Ambiguous testcase match", f"Summary node '{s_node}' matches {len(matching_xml)} XML testcases"

        # Reverse match: every failed XML testcase must correspond to exactly one failed summary node
        for x_node in xml_failed_nodes:
            matching_sum = [s for s in failed_node_ids if s == x_node]
            if len(matching_sum) == 0:
                return "NOT_EXECUTED", "INVALID", "Unmatched XML testcase", f"JUnit XML testcase '{x_node}' has no exact matching summary node"
            if len(matching_sum) > 1:
                return "NOT_EXECUTED", "INVALID", "Ambiguous testcase match", f"JUnit XML testcase '{x_node}' matches {len(matching_sum)} summary nodes"

        return "EXECUTED", "KILLED", failed_node_ids[0], f"{fail_count} failed in final summary (exact 1:1 JUnit XML verified AssertionError): {failed_node_ids[0]}"

    # Fallback: Node-bound terminal traceback verification when junit_xml is None
    failures_match = re.search(r"=+\s*FAILURES\s*=+", stripped_out)
    if not failures_match:
        all_summary_assert = True
        for entry in entry_lines:
            m_node = re.match(r"^FAILED\s+([a-zA-Z0-9_/\.\\-]+::[a-zA-Z0-9_\[\]\-\.]+)", entry)
            if m_node:
                if not ("- AssertionError" in entry or "- assert" in entry):
                    all_summary_assert = False
                    break
        if not all_summary_assert:
            return "NOT_EXECUTED", "INVALID", "Missing AssertionError evidence", "No FAILURES block and summary lacks verified AssertionError"
        return "EXECUTED", "KILLED", failed_node_ids[0], f"{fail_count} failed in final summary (summary verified AssertionError): {failed_node_ids[0]}"

    failures_text = stripped_out[failures_match.end():last_header.start()]

    section_split_re = re.compile(r"^\s*_{2,}\s+(.+?)\s+_{2,}$", re.MULTILINE)
    sec_headers = list(section_split_re.finditer(failures_text))
    if not sec_headers:
        return "NOT_EXECUTED", "INVALID", "Corrupted FAILURES block", "No test failure sections found in FAILURES block"

    for idx, sh in enumerate(sec_headers):
        sec_name = sh.group(1).strip()
        sec_start = sh.end()
        sec_end = sec_headers[idx + 1].start() if idx + 1 < len(sec_headers) else len(failures_text)
        sec_body = failures_text[sec_start:sec_end]

        sec_body_clean = re.sub(r"-{5,}\s*Captured (?:stdout|stderr)[^\n]*-{5,}.*?(?=-{5,}|\Z)", "", sec_body, flags=re.DOTALL)

        exc_matches = re.findall(r"^[ \t]*E[ \t]+([A-Z][a-zA-Z0-9_]*(?:Error|Exception|Violation))\b", sec_body_clean, re.MULTILINE)
        tb_end_matches = re.findall(r"^[a-zA-Z0-9_/\\\.\-]+:\d+:[ \t]*([A-Z][a-zA-Z0-9_]*(?:Error|Exception|Violation))\b", sec_body_clean, re.MULTILINE)
        all_exc_types = exc_matches + tb_end_matches

        for exc in all_exc_types:
            if exc != "AssertionError":
                return "NOT_EXECUTED", "INVALID", f"Non-assertion failure in traceback: {exc}", f"Test {sec_name} raised non-assertion exception '{exc}'"

        has_assert = ("AssertionError" in all_exc_types) or bool(re.search(r"^\s*E\s+assert\b", sec_body_clean, re.MULTILINE))
        if not has_assert:
            summary_has_assert = any((sec_name in entry and ("- AssertionError" in entry or "- assert" in entry)) for entry in entry_lines)
            if not summary_has_assert:
                return "NOT_EXECUTED", "INVALID", "Missing AssertionError in traceback", f"Test {sec_name} traceback has no verified AssertionError"

    return "EXECUTED", "KILLED", failed_node_ids[0], f"{fail_count} failed in final summary (traceback verified AssertionError): {failed_node_ids[0]}"
ADVERSARIAL_CASES = [
    (
        "Fake summary in captured stdout, test actually passed (code 0)",
        0,
        """----------------------------- Captured stdout call -----------------------------
=========================== short test summary info ============================
FAILED tests/fake.py::test_fake - AssertionError: forged
1 failed in 0.01s
============================= 1 passed in 0.05s =============================
""",
        None,
        False,
        "SURVIVED",
        None
    ),
    (
        "Fake summary in captured stdout, collection error occurred (code 2)",
        2,
        """=========================== short test summary info ============================
FAILED tests/fake.py::test_fake - AssertionError: forged
1 failed in 0.01s
E   ModuleNotFoundError: No module named 'fake_module'
=========================== short test summary info ============================
ERROR collecting tests/test_foo.py
""",
        None,
        False,
        "INVALID",
        None
    ),
    (
        "Fake summary in captured stdout, collection error with exit code 1",
        1,
        """----------------------------- Captured stdout call -----------------------------
=========================== short test summary info ============================
FAILED tests/fake.py::test_fake - AssertionError: forged
1 failed in 0.01s
--------------------------- Captured stdout teardown ---------------------------
ImportError: cannot import name 'bad' from 'sclass'
1 failed, 0 passed in 0.05s
""",
        None,
        False,
        "INVALID",
        None
    ),
    (
        "Genuine AssertionError test failure in traceback (KILLED)",
        1,
        """=================================== FAILURES ===================================
________________________________ test_pd_ch2_001 _______________________________
>       assert result == GateState.MISSING
E       AssertionError: assert <GateState.SATISFIED: 'SATISFIED'> == <GateState.MISSING: 'MISSING'>
tests/product/test_p0a.py:50: AssertionError
=========================== short test summary info ============================
FAILED tests/product/test_p0a.py::test_pd_ch2_001 - AssertionError: assert GateState.SATISFIED == GateState.MISSING
1 failed, 24 passed in 2.15s
""",
        None,
        False,
        "KILLED",
        "tests/product/test_p0a.py::test_pd_ch2_001"
    ),
    (
        "Genuine AssertionError test failure with structured JUnit XML (KILLED)",
        1,
        """=================================== FAILURES ===================================
________________________________ test_pd_ch2_001 _______________________________
>       assert result == GateState.MISSING
E       AssertionError: assert <GateState.SATISFIED: 'SATISFIED'> == <GateState.MISSING: 'MISSING'>
tests/product/test_p0a.py:50: AssertionError
=========================== short test summary info ============================
FAILED tests/product/test_p0a.py::test_pd_ch2_001 - AssertionError: assert GateState.SATISFIED == GateState.MISSING
1 failed, 24 passed in 2.15s
""",
        """<?xml version="1.0" encoding="utf-8"?>
<testsuites name="pytest tests">
  <testsuite name="pytest" errors="0" failures="1" skipped="0" tests="25" time="2.15">
    <testcase classname="tests.product.test_p0a" name="test_pd_ch2_001" file="tests/product/test_p0a.py" time="0.05">
      <failure message="AssertionError: assert GateState.SATISFIED == GateState.MISSING" type="AssertionError">def test_pd_ch2_001(): ...</failure>
    </testcase>
  </testsuite>
</testsuites>
""",
        False,
        "KILLED",
        "tests/product/test_p0a.py::test_pd_ch2_001"
    ),
    (
        "test_alpha XML versus test_alpha_extra summary (INVALID)",
        1,
        """=========================== short test summary info ============================
FAILED tests/product/test_p0a.py::test_alpha_extra - AssertionError
1 failed in 0.05s
""",
        """<testsuites><testsuite errors="0" failures="1" tests="1">
  <testcase classname="tests.product.test_p0a" name="test_alpha"><failure type="AssertionError">assert False</failure></testcase>
</testsuite></testsuites>
""",
        False,
        "INVALID",
        None
    ),
    (
        "Identical test names in different modules (INVALID)",
        1,
        """=========================== short test summary info ============================
FAILED tests/module_a.py::test_common - AssertionError
1 failed in 0.05s
""",
        """<testsuites><testsuite errors="0" failures="1" tests="1">
  <testcase classname="tests.module_b" name="test_common"><failure type="AssertionError">assert False</failure></testcase>
</testsuite></testsuites>
""",
        False,
        "INVALID",
        None
    ),
    (
        "Same test name but different XML file attribute (INVALID)",
        1,
        """=========================== short test summary info ============================
FAILED tests/mod_a.py::test_common - AssertionError
1 failed in 0.05s
""",
        """<testsuites><testsuite errors="0" failures="1" tests="1">
  <testcase file="tests/mod_b.py" classname="tests.mod_a" name="test_common"><failure type="AssertionError">assert False</failure></testcase>
</testsuite></testsuites>
""",
        False,
        "INVALID",
        None
    ),
    (
        "Two summary failures mapped to one XML testcase (INVALID)",
        1,
        """=========================== short test summary info ============================
FAILED tests/mod.py::test_1 - AssertionError
FAILED tests/mod.py::test_2 - AssertionError
2 failed in 0.10s
""",
        """<testsuites><testsuite errors="0" failures="1" tests="2">
  <testcase classname="tests.mod" name="test_1"><failure type="AssertionError">assert False</failure></testcase>
</testsuite></testsuites>
""",
        False,
        "INVALID",
        None
    ),
    (
        "Duplicate failure records in single testcase (INVALID)",
        1,
        """=========================== short test summary info ============================
FAILED tests/mod.py::test_1 - AssertionError
1 failed in 0.10s
""",
        """<testsuites><testsuite errors="0" failures="2" tests="1">
  <testcase classname="tests.mod" name="test_1">
    <failure type="AssertionError">f1</failure>
    <failure type="AssertionError">f2</failure>
  </testcase>
</testsuite></testsuites>
""",
        False,
        "INVALID",
        None
    ),
    (
        "Duplicate XML testcase records for same test node (INVALID)",
        1,
        """=========================== short test summary info ============================
FAILED tests/mod.py::test_1 - AssertionError
1 failed in 0.10s
""",
        """<testsuites><testsuite errors="0" failures="1" tests="2">
  <testcase classname="tests.mod" name="test_1"><failure type="AssertionError">f1</failure></testcase>
  <testcase classname="tests.mod" name="test_1" time="0.01"/>
</testsuite></testsuites>
""",
        False,
        "INVALID",
        None
    ),
    (
        "Genuine parametrized test identity match (KILLED)",
        1,
        """=========================== short test summary info ============================
FAILED tests/mod.py::test_param[val-1] - AssertionError
1 failed in 0.10s
""",
        """<testsuites><testsuite errors="0" failures="1" tests="1">
  <testcase classname="tests.mod" name="test_param[val-1]"><failure type="AssertionError">assert False</failure></testcase>
</testsuite></testsuites>
""",
        False,
        "KILLED",
        "tests/mod.py::test_param[val-1]"
    ),
    (
        "Parametrized test identity mismatch (val-1 vs val-2) (INVALID)",
        1,
        """=========================== short test summary info ============================
FAILED tests/mod.py::test_param[val-1] - AssertionError
1 failed in 0.10s
""",
        """<testsuites><testsuite errors="0" failures="1" tests="1">
  <testcase classname="tests.mod" name="test_param[val-2]"><failure type="AssertionError">assert False</failure></testcase>
</testsuite></testsuites>
""",
        False,
        "INVALID",
        None
    ),
    (
        "Passing test prints AssertionError, while another test fails with custom exception in XML",
        1,
        """----------------------------- Captured stdout call -----------------------------
AssertionError: fake assert passed in test_pass
=================================== FAILURES ===================================
________________________________ test_security _________________________________
>       raise CustomSecurityViolation("unauthorized role")
E       CustomSecurityViolation: unauthorized role
tests/test_sec.py:20: CustomSecurityViolation
=========================== short test summary info ============================
FAILED tests/test_sec.py::test_security - CustomSecurityViolation: unauthorized role
1 failed in 0.05s
""",
        """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite errors="0" failures="1" tests="2">
  <testcase classname="tests.test_pass" name="test_passing" time="0.01"/>
  <testcase classname="tests.test_sec" name="test_security" file="tests/test_sec.py" time="0.01">
    <failure message="CustomSecurityViolation: unauthorized role" type="CustomSecurityViolation">def test_security(): ...</failure>
  </testcase>
</testsuite></testsuites>
""",
        False,
        "INVALID",
        None
    ),
    (
        "Passing test prints AssertionError, while another test fails with custom exception in traceback (no XML)",
        1,
        """----------------------------- Captured stdout call -----------------------------
AssertionError: fake assert passed in test_pass
=================================== FAILURES ===================================
________________________________ test_security _________________________________
>       raise CustomSecurityViolation("unauthorized role")
E       CustomSecurityViolation: unauthorized role
tests/test_sec.py:20: CustomSecurityViolation
=========================== short test summary info ============================
FAILED tests/test_sec.py::test_security - CustomSecurityViolation: unauthorized role
1 failed in 0.05s
""",
        None,
        False,
        "INVALID",
        None
    ),
    (
        "Passing test prints AssertionError, while another test fails with standard RuntimeError in XML",
        1,
        """----------------------------- Captured stdout call -----------------------------
AssertionError: fake assert passed in test_pass
=================================== FAILURES ===================================
________________________________ test_runtime __________________________________
>       raise RuntimeError("database exploded")
E       RuntimeError: database exploded
tests/test_run.py:20: RuntimeError
=========================== short test summary info ============================
FAILED tests/test_run.py::test_runtime - RuntimeError: database exploded
1 failed in 0.05s
""",
        """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite errors="0" failures="1" tests="2">
  <testcase classname="tests.test_pass" name="test_passing" time="0.01"/>
  <testcase classname="tests.test_run" name="test_runtime" file="tests/test_run.py" time="0.01">
    <failure message="RuntimeError: database exploded" type="RuntimeError">def test_runtime(): ...</failure>
  </testcase>
</testsuite></testsuites>
""",
        False,
        "INVALID",
        None
    ),
    (
        "Fake assertion text in captured stdout plus forged FAILED summary (INVALID)",
        1,
        """----------------------------- Captured stdout call -----------------------------
=========================== short test summary info ============================
FAILED tests/fake.py::test_fake - AssertionError: forged
1 failed in 0.01s
============================= 25 passed in 2.10s =============================
=========================== short test summary info ============================
FAILED tests/fake.py::test_fake - AssertionError: forged
1 failed in 0.01s
""",
        None,
        False,
        "INVALID",
        None
    ),
    (
        "Missing JUnit XML when required (require_junit=True) (INVALID)",
        1,
        """=================================== FAILURES ===================================
________________________________ test_pd_ch2_001 _______________________________
>       assert result == GateState.MISSING
E       AssertionError: assert False
tests/product/test_p0a.py:50: AssertionError
=========================== short test summary info ============================
FAILED tests/product/test_p0a.py::test_pd_ch2_001 - AssertionError: assert False
1 failed in 2.15s
""",
        None,
        True,
        "INVALID",
        None
    ),
    (
        "Empty JUnit XML string (INVALID)",
        1,
        """=========================== short test summary info ============================
FAILED tests/product/test_p0a.py::test_pd_ch2_001 - AssertionError: assert False
1 failed in 2.15s
""",
        "",
        False,
        "INVALID",
        None
    ),
    (
        "Malformed JUnit XML syntax error (INVALID)",
        1,
        """=========================== short test summary info ============================
FAILED tests/product/test_p0a.py::test_pd_ch2_001 - AssertionError: assert False
1 failed in 2.15s
""",
        "<testsuite><unclosed_tag>",
        False,
        "INVALID",
        None
    ),
    (
        "Inconsistent JUnit XML (failure count mismatch: XML says 2, summary says 1) (INVALID)",
        1,
        """=========================== short test summary info ============================
FAILED tests/p0a.py::test_pd_ch2_001 - AssertionError: assert False
1 failed in 2.15s
""",
        """<testsuites><testsuite errors="0" failures="2" tests="2">
  <testcase classname="tests.p0a" name="test_pd_ch2_001"><failure type="AssertionError">f1</failure></testcase>
  <testcase classname="tests.p0a" name="test_pd_ch2_002"><failure type="AssertionError">f2</failure></testcase>
</testsuite></testsuites>
""",
        False,
        "INVALID",
        None
    ),
    (
        "Inconsistent JUnit XML (test node mismatch: XML has test_other, summary has test_pd_ch2_001) (INVALID)",
        1,
        """=========================== short test summary info ============================
FAILED tests/product/test_p0a.py::test_pd_ch2_001 - AssertionError: assert False
1 failed in 2.15s
""",
        """<testsuites><testsuite errors="0" failures="1" tests="1">
  <testcase classname="tests.other" name="test_completely_unrelated"><failure type="AssertionError">f1</failure></testcase>
</testsuite></testsuites>
""",
        False,
        "INVALID",
        None
    ),
    (
        "Multiple failures where even one is a non-assertion failure (INVALID)",
        1,
        """=================================== FAILURES ===================================
________________________________ test_first ____________________________________
>       assert False
E       AssertionError
tests/test_first.py:10: AssertionError
________________________________ test_second ___________________________________
>       raise CustomAuthFailure("bad auth")
E       CustomAuthFailure: bad auth
tests/test_second.py:20: CustomAuthFailure
=========================== short test summary info ============================
FAILED tests/test_first.py::test_first - AssertionError
FAILED tests/test_second.py::test_second - CustomAuthFailure: bad auth
2 failed in 0.20s
""",
        """<testsuites><testsuite errors="0" failures="2" tests="2">
  <testcase classname="tests.test_first" name="test_first"><failure type="AssertionError">assert False</failure></testcase>
  <testcase classname="tests.test_second" name="test_second"><failure type="CustomAuthFailure">bad auth</failure></testcase>
</testsuite></testsuites>
""",
        False,
        "INVALID",
        None
    ),
    (
        "Multiple failures where ALL are genuine AssertionError (KILLED)",
        1,
        """=================================== FAILURES ===================================
________________________________ test_first ____________________________________
>       assert False
E       AssertionError
tests/test_first.py:10: AssertionError
________________________________ test_second ___________________________________
>       assert 1 == 2
E       AssertionError: assert 1 == 2
tests/test_second.py:20: AssertionError: assert 1 == 2
=========================== short test summary info ============================
FAILED tests/test_first.py::test_first - AssertionError
FAILED tests/test_second.py::test_second - AssertionError: assert 1 == 2
2 failed in 0.20s
""",
        """<testsuites><testsuite errors="0" failures="2" tests="2">
  <testcase classname="tests.test_first" name="test_first"><failure type="AssertionError">assert False</failure></testcase>
  <testcase classname="tests.test_second" name="test_second"><failure type="AssertionError">assert 1 == 2</failure></testcase>
</testsuite></testsuites>
""",
        False,
        "KILLED",
        "tests/test_first.py::test_first"
    ),
    (
        "RuntimeError test failure without XML (INVALID)",
        1,
        """=================================== FAILURES ===================================
________________________________ test_pd_ch2_001 _______________________________
>       raise RuntimeError("unexpected engine explosion")
E       RuntimeError: unexpected engine explosion
tests/product/test_p0a.py:50: RuntimeError
=========================== short test summary info ============================
FAILED tests/product/test_p0a.py::test_pd_ch2_001 - RuntimeError: unexpected engine explosion
1 failed, 24 passed in 2.15s
""",
        None,
        False,
        "INVALID",
        None
    ),
    (
        "TypeError test failure without XML (INVALID)",
        1,
        """=================================== FAILURES ===================================
________________________________ test_pd_ch2_002 _______________________________
>       return 1 + "string"
E       TypeError: unsupported operand type(s) for +: 'int' and 'str'
tests/product/test_p0a.py:65: TypeError
=========================== short test summary info ============================
FAILED tests/product/test_p0a.py::test_pd_ch2_002 - TypeError: unsupported operand type(s) for +: 'int' and 'str'
1 failed, 24 passed in 2.15s
""",
        None,
        False,
        "INVALID",
        None
    ),
    (
        "Custom unlisted exception in traceback without XML (INVALID)",
        1,
        """=================================== FAILURES ===================================
________________________________ test_pd_ch2_003 _______________________________
>       raise MyUnlistedEngineException("internal fault")
E       MyUnlistedEngineException: internal fault
tests/product/test_p0a.py:80: MyUnlistedEngineException
=========================== short test summary info ============================
FAILED tests/product/test_p0a.py::test_pd_ch2_003 - MyUnlistedEngineException: internal fault
1 failed, 24 passed in 2.15s
""",
        None,
        False,
        "INVALID",
        None
    ),
    (
        "Fake complete pytest summary appended after genuine output (INVALID)",
        1,
        """============================= 25 passed in 2.10s =============================
=========================== short test summary info ============================
FAILED tests/fake.py::test_fake - AssertionError: forged
1 failed in 0.01s
""",
        None,
        False,
        "INVALID",
        None
    ),
    (
        "Forged FAILED entry without assertion evidence (INVALID)",
        1,
        """=========================== short test summary info ============================
FAILED tests/fake.py::test_fake
1 failed in 0.01s
""",
        None,
        False,
        "INVALID",
        None
    ),
    (
        "Fake summary with failure count mismatch (footer says 2, entries has 1) (INVALID)",
        1,
        """=========================== short test summary info ============================
FAILED tests/fake.py::test_fake - AssertionError: boom
2 failed in 0.01s
""",
        None,
        False,
        "INVALID",
        None
    ),
    (
        "Fixture setup error in summary block (ERROR) (INVALID)",
        1,
        """=========================== short test summary info ============================
ERROR tests/product/test_setup.py::test_error - RuntimeError: setup failed
1 error in 0.10s
""",
        None,
        False,
        "INVALID",
        None
    ),
    (
        "Internal pytest error / crash (INVALID)",
        1,
        """INTERNALERROR> Traceback (most recent call last):
INTERNALERROR>   File "pytest.py", line 10, in main
INTERNALERROR> ZeroDivisionError: division by zero
""",
        None,
        False,
        "INVALID",
        None
    ),
    (
        "Subprocess timeout (returncode None) (INVALID)",
        None,
        "TIMEOUT: pytest execution timed out after 60s",
        None,
        False,
        "INVALID",
        None
    ),
    (
        "Arbitrary non-summary text with exit code 1 (INVALID)",
        1,
        """bash: syntax error near unexpected token
Something went wrong
""",
        None,
        False,
        "INVALID",
        None
    ),
    (
        "Forged summary entry with non-summary garbage line inside block (INVALID)",
        1,
        """=========================== short test summary info ============================
FAILED tests/product/test_real.py::test_real_fail - AssertionError: fail
This is random injected text inside summary block
1 failed in 0.50s
""",
        None,
        False,
        "INVALID",
        None
    ),
    (
        "Abnormal exit code 137 (SIGKILL/OOM) (INVALID)",
        137,
        """Killed
""",
        None,
        False,
        "INVALID",
        None
    ),
    (
        "Fake summary header printed in test body, real failure at end (extract real node ID) (KILLED)",
        1,
        """----------------------------- Captured stdout call -----------------------------
=========================== short test summary info ============================
FAILED tests/fake.py::test_forged - AssertionError: forged
1 failed in 0.01s
=================================== FAILURES ===================================
________________________________ test_real_fail ________________________________
>       assert False
E       AssertionError
tests/product/test_real.py:10: AssertionError
=========================== short test summary info ============================
FAILED tests/product/test_real.py::test_real_fail - AssertionError
1 failed in 0.50s
""",
        None,
        False,
        "KILLED",
        "tests/product/test_real.py::test_real_fail"
    ),
]


def run_adversarial_tests() -> List[Tuple[str, bool, str]]:
    results = []
    for name, code, output, junit_xml, req_junit, expected_result, expected_node in ADVERSARIAL_CASES:
        status, result, failing_test, ev = classify_pytest_output(code, output, junit_xml=junit_xml, require_junit=req_junit)
        passed = (result == expected_result)
        if passed and expected_node is not None:
            passed = (failing_test == expected_node)
        detail = f"result={result}, failing_test={failing_test}"
        results.append((name, passed, detail))
    return results


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
    junit_xml_content: Optional[str] = None

    junit_file = (log_dir / f"{m.mutant_id}_junit.xml") if log_dir else (REPO_ROOT / f"delivery-evidence/raw_mutant_logs/{m.mutant_id}_junit.xml")
    junit_file.parent.mkdir(parents=True, exist_ok=True)
    if junit_file.exists():
        try:
            junit_file.unlink()
        except Exception:
            pass

    # Items 1, 2, 3: Full try/except/finally wrapping mutation and execution
    try:
        mutated_text = original_text.replace(m.target_str, m.replacement_str)
        target_path.write_text(mutated_text, encoding="utf-8")

        # Run pytest with timeout and catch all exceptions
        cmd = [*PYTEST_CMD, m.test_rel_path, "-q", "--no-header", f"--junitxml={junit_file}"]
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

        if junit_file.exists():
            try:
                junit_xml_content = junit_file.read_text(encoding="utf-8")
            except Exception:
                junit_xml_content = None

        retcode = res.returncode if res is not None else None
        exec_status, result, failing_test, evidence = classify_pytest_output(
            retcode, out, junit_xml=junit_xml_content, require_junit=True
        )
    except Exception as exc:
        # Unexpected mutation or execution exceptions produce recorded INVALID
        elapsed = time.time() - t0
        exec_status = "NOT_EXECUTED"
        result = "INVALID"
        failing_test = f"Exception: {type(exc).__name__}"
        evidence = f"Unexpected mutation exception: {type(exc).__name__}: {exc}"
        out = f"UNEXPECTED_EXCEPTION:\n{traceback.format_exc()}\n"
    finally:
        # Exact byte preservation & SHA-256 check under all paths
        target_path.write_bytes(original_bytes)
        restored_sha = sha256_file(target_path)
        assert restored_sha == orig_sha, f"Byte restoration mismatch on {m.target_rel_path}"

    if log_dir:
        log_content = (
            f"=== MUTANT {m.mutant_id} ({m.name}) ===\n"
            f"Target: {m.target_rel_path}\n"
            f"Test: {m.test_rel_path}\n"
            f"Expected Count: {m.expected_count} | Actual Count: {actual_count}\n"
            f"Execution Status: {exec_status} | Result: {result}\n"
            f"Failing Test Summary: {failing_test}\n"
            f"Elapsed: {elapsed:.3f}s\n\n"
            f"--- PYTEST OUTPUT ---\n{out}\n"
        )
        if junit_xml_content:
            log_content += f"\n--- JUNIT XML ---\n{junit_xml_content}\n"
        (log_dir / f"{m.mutant_id}.log").write_text(log_content, encoding="utf-8")

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

    # Item 3: Execute focused adversarial classifier security suite
    adv_results = run_adversarial_tests()
    print(f"\n[ADVERSARIAL SECURITY SUITE] Running {len(adv_results)} focused adversarial classifier tests...")
    adv_passed = sum(1 for r in adv_results if r[1])
    print(f"[ADVERSARIAL SECURITY SUITE] Passed: {adv_passed}/{len(adv_results)}")
    for name, ok, detail in adv_results:
        status_str = "PASS" if ok else "FAIL"
        print(f"  [{status_str}] {name} ({detail})")
    assert adv_passed == len(adv_results), f"Adversarial tests failed: {adv_passed}/{len(adv_results)}"

    # Save adversarial test log in evidence directory
    adv_log_lines = ["=== E4 ADVERSARIAL CLASSIFIER TEST SUITE ===\n\n"]
    for name, ok, detail in adv_results:
        adv_log_lines.append(f"['{'PASS' if ok else 'FAIL'}'] {name}\n  Detail: {detail}\n\n")
    adv_log_lines.append(f"Total Adversarial Tests: {len(adv_results)} | Passed: {adv_passed} | Failed: {len(adv_results) - adv_passed}\n")
    (out_dir / "e4_adversarial_tests.log").write_text("".join(adv_log_lines), encoding="utf-8")

    if "--adversarial-only" in sys.argv:
        print("\nAdversarial tests completed successfully. Exiting (--adversarial-only).")
        return

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
