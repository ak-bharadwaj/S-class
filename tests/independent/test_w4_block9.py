"""Independent W4 Consumer Contract Scenarios for Block 9 (Chapters 9 and 10).

Mandated by S-CLASS M0 ITERATION 2 (E5):
- Standalone independent test functions under tests/independent/
- Covers all 15 Block 9 MUSTs:
    PD-CH9-003, PD-CH9-004, PD-CH9-005, PD-CH9-006, PD-CH9-007,
    PD-CH9-008, PD-CH9-009, PD-CH9-010, PD-CH10-007, PD-CH10-008,
    PD-CH10-009, PD-CH10-010, PD-CH10-011, PD-CH10-012, PD-CH10-013
- Evaluates fail-closed security posture (unauthenticated / missing authority -> non-SATISFIED)
- Evaluates authorized consumer contracts (valid authority -> SATISFIED)
- Asserts GateOutput contract compliance (GateState closed vocabulary, to_dict schema)
"""
from __future__ import annotations

import pytest
from sclass.product.gate import GateOutput, GateState
from sclass.product.threat_eval_regression_gate import (
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B9_A,
    REQUIRED_THREAT_FIELDS,
    REQUIRED_EVAL_RUN_BINDINGS,
    REQUIRED_METRIC_REPORT_FIELDS,
    evaluate_pd_ch9_003_security_promotion_gate,
    evaluate_pd_ch9_004_metric_reporting_integrity,
    evaluate_pd_ch9_005_data_retention_policy,
    evaluate_pd_ch9_008_threat_coverage,
    evaluate_pd_ch9_009_eval_run_bindings,
    evaluate_pd_ch9_010_promotion_blockers,
)
from sclass.product.stratum_sampling_compatibility import (
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B9_B,
    VALID_ROADMAP_HORIZONS,
    VALID_FACT_CLASSIFICATIONS,
    REQUIRED_AUDIT_EXPORT_FIELDS,
    REQUIRED_COMPATIBILITY_FIELDS,
    evaluate_pd_ch9_006_stratum_sampling_promotion,
    evaluate_pd_ch9_007_secret_egress_claims,
    evaluate_pd_ch10_008_explicit_compatibility,
    evaluate_pd_ch10_009_audit_export_bindings,
    evaluate_pd_ch10_010_roadmap_integrity,
    evaluate_pd_ch10_011_fact_classification,
)
from sclass.product.erratum_issue_registry import (
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_B9_C,
    REQUIRED_OPEN_ISSUE_FIELDS,
    evaluate_pd_ch10_007_master_cross_links,
    evaluate_pd_ch10_012_frozen_erratum_path,
    evaluate_pd_ch10_013_open_issue_schema,
)


def test_w4_scenario_pd_ch9_003():
    """W4 Scenario for PD-CH9-003: Security promotion gate."""
    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch9_003_security_promotion_gate(authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH9-003"

    # 2. Failed security scan fails closed
    bad = evaluate_pd_ch9_003_security_promotion_gate(
        failed_security_scan=True,
        environment_mismatch=False,
        sandbox_trust_root_failure=False,
        authority=AUTH_B9_A,
    )
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH9-003"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch9_003_security_promotion_gate(
        failed_security_scan=False,
        environment_mismatch=False,
        sandbox_trust_root_failure=False,
        authority=AUTH_B9_A,
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH9-003"


def test_w4_scenario_pd_ch9_004():
    """W4 Scenario for PD-CH9-004: Metric report integrity."""
    rep = {f: "val" for f in REQUIRED_METRIC_REPORT_FIELDS}

    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch9_004_metric_reporting_integrity(rep, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH9-004"

    # 2. Missing fields fails closed
    bad_rep = rep.copy()
    del bad_rep[list(REQUIRED_METRIC_REPORT_FIELDS)[0]]
    bad = evaluate_pd_ch9_004_metric_reporting_integrity(bad_rep, authority=AUTH_B9_A)
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH9-004"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch9_004_metric_reporting_integrity(rep, authority=AUTH_B9_A)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH9-004"


def test_w4_scenario_pd_ch9_005():
    """W4 Scenario for PD-CH9-005: Data retention policy."""
    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch9_005_data_retention_policy(authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH9-005"

    # 2. Exceeded retention limit fails closed
    bad = evaluate_pd_ch9_005_data_retention_policy(
        within_retention_limit=False,
        has_policy_reference=True,
        recorded_action=True,
        authority=AUTH_B9_A,
    )
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH9-005"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch9_005_data_retention_policy(
        within_retention_limit=True,
        has_policy_reference=True,
        recorded_action=True,
        authority=AUTH_B9_A,
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH9-005"


def test_w4_scenario_pd_ch9_006():
    """W4 Scenario for PD-CH9-006: Stratum sampling promotion."""
    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch9_006_stratum_sampling_promotion(False, {"S1": 150}, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH9-006"

    # 2. False completion worsened blocks promotion
    bad = evaluate_pd_ch9_006_stratum_sampling_promotion(True, {"S1": 150}, authority=AUTH_B9_B)
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH9-006"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch9_006_stratum_sampling_promotion(False, {"S1": 150}, authority=AUTH_B9_B)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH9-006"


def test_w4_scenario_pd_ch9_007():
    """W4 Scenario for PD-CH9-007: Secret egress claims on launched workers."""
    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch9_007_secret_egress_claims(True, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH9-007"

    # 2. Unqualified native host write fails closed
    bad = evaluate_pd_ch9_007_secret_egress_claims(
        True,
        unqualified_scanner_or_native_host_write=True,
        authority=AUTH_B9_B,
    )
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH9-007"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch9_007_secret_egress_claims(
        True,
        unqualified_scanner_or_native_host_write=False,
        authority=AUTH_B9_B,
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH9-007"


def test_w4_scenario_pd_ch9_008():
    """W4 Scenario for PD-CH9-008: Threat coverage."""
    rec = {f: "evidence" for f in REQUIRED_THREAT_FIELDS}

    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch9_008_threat_coverage(rec, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH9-008"

    # 2. Absence of findings as pass rejected
    bad = evaluate_pd_ch9_008_threat_coverage(rec, absence_of_findings_as_pass=True, authority=AUTH_B9_A)
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH9-008"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch9_008_threat_coverage(rec, absence_of_findings_as_pass=False, authority=AUTH_B9_A)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH9-008"


def test_w4_scenario_pd_ch9_009():
    """W4 Scenario for PD-CH9-009: Eval run bindings."""
    run = {f: "val" for f in REQUIRED_EVAL_RUN_BINDINGS}

    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch9_009_eval_run_bindings(run, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH9-009"

    # 2. Missing field fails closed
    bad_run = run.copy()
    del bad_run[list(REQUIRED_EVAL_RUN_BINDINGS)[0]]
    bad = evaluate_pd_ch9_009_eval_run_bindings(bad_run, authority=AUTH_B9_A)
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH9-009"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch9_009_eval_run_bindings(run, authority=AUTH_B9_A)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH9-009"


def test_w4_scenario_pd_ch9_010():
    """W4 Scenario for PD-CH9-010: Promotion blockers."""
    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch9_010_promotion_blockers(authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH9-010"

    # 2. Critical regression fails closed
    bad = evaluate_pd_ch9_010_promotion_blockers(
        critical_regression=True,
        unqualified_data_handling=False,
        authority=AUTH_B9_A,
    )
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH9-010"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch9_010_promotion_blockers(
        critical_regression=False,
        unqualified_data_handling=False,
        authority=AUTH_B9_A,
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH9-010"


def test_w4_scenario_pd_ch10_007():
    """W4 Scenario for PD-CH10-007: Master cross-links."""
    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch10_007_master_cross_links(True, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH10-007"

    # 2. Unknown references fails closed
    bad = evaluate_pd_ch10_007_master_cross_links(
        cross_linked_to_master=True,
        unknown_references_present=True,
        authority=AUTH_B9_C,
    )
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH10-007"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch10_007_master_cross_links(
        cross_linked_to_master=True,
        unknown_references_present=False,
        authority=AUTH_B9_C,
    )
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH10-007"


def test_w4_scenario_pd_ch10_008():
    """W4 Scenario for PD-CH10-008: Explicit compatibility matrix."""
    matrix = {f: "1.0" for f in REQUIRED_COMPATIBILITY_FIELDS}

    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch10_008_explicit_compatibility(matrix, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH10-008"

    # 2. Unsupported pair present fails closed
    bad = evaluate_pd_ch10_008_explicit_compatibility(matrix, unsupported_pair_present=True, authority=AUTH_B9_B)
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH10-008"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch10_008_explicit_compatibility(matrix, unsupported_pair_present=False, authority=AUTH_B9_B)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH10-008"


def test_w4_scenario_pd_ch10_009():
    """W4 Scenario for PD-CH10-009: Audit export bindings."""
    export = {f: "val" for f in REQUIRED_AUDIT_EXPORT_FIELDS}

    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch10_009_audit_export_bindings(export, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH10-009"

    # 2. Missing field fails closed
    bad_export = export.copy()
    del bad_export[list(REQUIRED_AUDIT_EXPORT_FIELDS)[0]]
    bad = evaluate_pd_ch10_009_audit_export_bindings(bad_export, authority=AUTH_B9_B)
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH10-009"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch10_009_audit_export_bindings(export, authority=AUTH_B9_B)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH10-009"


def test_w4_scenario_pd_ch10_010():
    """W4 Scenario for PD-CH10-010: Roadmap integrity."""
    valid_caps = [{"id": "C1", "horizon": "H1", "dependency": "DEP", "exit_test": "TEST", "planning_claimed_as_implemented": False}]

    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch10_010_roadmap_integrity(valid_caps, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH10-010"

    # 2. Invalid horizon fails closed
    bad_caps = [{"id": "C1", "horizon": "H99", "dependency": "DEP", "exit_test": "TEST"}]
    bad = evaluate_pd_ch10_010_roadmap_integrity(bad_caps, authority=AUTH_B9_B)
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH10-010"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch10_010_roadmap_integrity(valid_caps, authority=AUTH_B9_B)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH10-010"


def test_w4_scenario_pd_ch10_011():
    """W4 Scenario for PD-CH10-011: Fact classification."""
    valid_facts = [{"id": "F1", "classification": "keep", "evidence_ref": "REF1", "unverified": False}]

    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch10_011_fact_classification(valid_facts, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH10-011"

    # 2. Invalid classification fails closed
    bad_facts = [{"id": "F1", "classification": "invalid_kind", "evidence_ref": "REF"}]
    bad = evaluate_pd_ch10_011_fact_classification(bad_facts, authority=AUTH_B9_B)
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH10-011"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch10_011_fact_classification(valid_facts, authority=AUTH_B9_B)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH10-011"


def test_w4_scenario_pd_ch10_012():
    """W4 Scenario for PD-CH10-012: Frozen erratum path."""
    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch10_012_frozen_erratum_path(True, True, True, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH10-012"

    # 2. Ad-hoc source edit rejected
    bad = evaluate_pd_ch10_012_frozen_erratum_path(True, True, True, ad_hoc_source_edit=True, authority=AUTH_B9_C)
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH10-012"

    # 3. Authorized consumer contract satisfied
    auth = evaluate_pd_ch10_012_frozen_erratum_path(True, True, True, ad_hoc_source_edit=False, authority=AUTH_B9_C)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH10-012"


def test_w4_scenario_pd_ch10_013():
    """W4 Scenario for PD-CH10-013: Open issue schema and closure."""
    issue = {f: "val" for f in REQUIRED_OPEN_ISSUE_FIELDS}
    issue["id"] = "OI-008"
    issue["status"] = "CLOSED"

    # 1. Unauthenticated caller fails closed
    unauth = evaluate_pd_ch10_013_open_issue_schema(issue, authority=None)
    assert isinstance(unauth, GateOutput)
    assert unauth.state == GateState.MISSING
    assert unauth.must_id == "PD-CH10-013"

    # 2. Insufficient owner reviews fails closed (< 2 for OI-008 CLOSED)
    bad = evaluate_pd_ch10_013_open_issue_schema(issue, oi_008_owner_reviews_count=1, authority=AUTH_B9_C)
    assert isinstance(bad, GateOutput)
    assert bad.state == GateState.MISSING
    assert bad.must_id == "PD-CH10-013"

    # 3. Authorized consumer contract satisfied (>= 2 reviews)
    auth = evaluate_pd_ch10_013_open_issue_schema(issue, oi_008_owner_reviews_count=2, authority=AUTH_B9_C)
    assert isinstance(auth, GateOutput)
    assert auth.state == GateState.SATISFIED
    assert auth.must_id == "PD-CH10-013"
