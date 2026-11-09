"""Unit and regression tests for Chapter 9 Threat Evaluation & Promotion Gate (Block 9, Lane B9-A).

Covers:
- PD-CH9-008: Threat coverage (attack, boundary, prevention, containment, fixture)
- PD-CH9-009: Eval run bindings (revision, target, policy, runtime, audit label)
- PD-CH9-010: Promotion blockers (critical regression, data handling)
- PD-CH9-003: Security scan, environment mismatch, sandbox trust-root failure
- PD-CH9-004: Metric report integrity (denominator, window, stratum, uncertainty)
- PD-CH9-005: Data retention policy and explicit units
"""
import pytest
from sclass.product.gate import GateOutput, GateState
from sclass.product.threat_eval_regression_gate import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    REQUIRED_THREAT_FIELDS,
    REQUIRED_EVAL_RUN_BINDINGS,
    REQUIRED_METRIC_REPORT_FIELDS,
    evaluate_pd_ch9_008_threat_coverage,
    evaluate_pd_ch9_009_eval_run_bindings,
    evaluate_pd_ch9_010_promotion_blockers,
    evaluate_pd_ch9_003_security_promotion_gate,
    evaluate_pd_ch9_004_metric_reporting_integrity,
    evaluate_pd_ch9_005_data_retention_policy,
    evaluate_b9_a_gate,
)

AUTH = QUALIFIED_EVALUATOR_BOUNDARY


class TestPDCH9008ThreatCoverage:
    def test_authority_enforced(self):
        res = evaluate_pd_ch9_008_threat_coverage({}, authority=None)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH9-008"

    def test_missing_threat_record(self):
        res = evaluate_pd_ch9_008_threat_coverage(None, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH9-008"

    def test_absence_of_findings_as_pass_rejected(self):
        rec = {f: f"val_{f}" for f in REQUIRED_THREAT_FIELDS}
        res = evaluate_pd_ch9_008_threat_coverage(rec, absence_of_findings_as_pass=True, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH9-008"

    @pytest.mark.parametrize("missing_field", list(REQUIRED_THREAT_FIELDS))
    def test_missing_field(self, missing_field):
        rec = {f: f"val_{f}" for f in REQUIRED_THREAT_FIELDS}
        del rec[missing_field]
        res = evaluate_pd_ch9_008_threat_coverage(rec, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH9-008"

    def test_threat_coverage_satisfied(self):
        rec = {f: f"val_{f}" for f in REQUIRED_THREAT_FIELDS}
        res = evaluate_pd_ch9_008_threat_coverage(rec, authority=AUTH)
        assert res.state == GateState.SATISFIED


class TestPDCH9009EvalRunBindings:
    def test_authority_enforced(self):
        res = evaluate_pd_ch9_009_eval_run_bindings({}, authority=None)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH9-009"

    def test_missing_eval_run(self):
        res = evaluate_pd_ch9_009_eval_run_bindings(None, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH9-009"

    @pytest.mark.parametrize("missing_binding", list(REQUIRED_EVAL_RUN_BINDINGS))
    def test_missing_binding(self, missing_binding):
        run = {f: f"val_{f}" for f in REQUIRED_EVAL_RUN_BINDINGS}
        del run[missing_binding]
        res = evaluate_pd_ch9_009_eval_run_bindings(run, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH9-009"

    def test_eval_run_satisfied(self):
        run = {f: f"val_{f}" for f in REQUIRED_EVAL_RUN_BINDINGS}
        res = evaluate_pd_ch9_009_eval_run_bindings(run, authority=AUTH)
        assert res.state == GateState.SATISFIED


class TestPDCH9010PromotionBlockers:
    def test_authority_enforced(self):
        res = evaluate_pd_ch9_010_promotion_blockers(False, False, authority=None)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH9-010"

    def test_critical_regression_blocks(self):
        res = evaluate_pd_ch9_010_promotion_blockers(True, False, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH9-010"

    def test_unqualified_data_handling_blocks(self):
        res = evaluate_pd_ch9_010_promotion_blockers(False, True, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH9-010"

    def test_promotion_satisfied(self):
        res = evaluate_pd_ch9_010_promotion_blockers(False, False, authority=AUTH)
        assert res.state == GateState.SATISFIED


class TestPDCH9003SecurityPromotionGate:
    def test_authority_enforced(self):
        res = evaluate_pd_ch9_003_security_promotion_gate(authority=None)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH9-003"

    def test_omitted_evidence_fails_closed(self):
        """Mandatory fail-closed test: calling with valid authority but omitted evidence MUST return MISSING."""
        res = evaluate_pd_ch9_003_security_promotion_gate(authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH9-003"

    @pytest.mark.parametrize("bad_val", [None, "False", 0, 1])
    def test_invalid_types_fail_closed(self, bad_val):
        """Non-exact bool or None evidence MUST fail closed to MISSING."""
        res = evaluate_pd_ch9_003_security_promotion_gate(
            failed_security_scan=bad_val,
            environment_mismatch=False,
            sandbox_trust_root_failure=False,
            authority=AUTH,
        )
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH9-003"

    def test_exploding_object_fails_closed(self):
        class ExplodingDependency:
            def __getattr__(self, name): raise RuntimeError("Exploded")
            def __bool__(self): raise RuntimeError("Exploded")

        res = evaluate_pd_ch9_003_security_promotion_gate(
            failed_security_scan=ExplodingDependency(),
            environment_mismatch=False,
            sandbox_trust_root_failure=False,
            authority=AUTH,
        )
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH9-003"

    def test_failed_security_scan(self):
        res = evaluate_pd_ch9_003_security_promotion_gate(failed_security_scan=True, authority=AUTH)
        assert res.state == GateState.MISSING
        assert "BLOCKED" in res.detail

    def test_environment_mismatch(self):
        res = evaluate_pd_ch9_003_security_promotion_gate(environment_mismatch=True, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH9-003"

    def test_sandbox_trust_root_failure(self):
        res = evaluate_pd_ch9_003_security_promotion_gate(sandbox_trust_root_failure=True, authority=AUTH)
        assert res.state == GateState.MISSING
        assert "BLOCKED" in res.detail

    def test_mutation_restore_default_false_is_killed(self):
        """Mutation test: if an implementation restored 'failed_security_scan: bool = False',
        calling with omitted arguments would incorrectly yield SATISFIED instead of MISSING."""
        def mutated_evaluator(
            failed_security_scan: bool = False,
            environment_mismatch: bool = False,
            sandbox_trust_root_failure: bool = False,
            *,
            authority: str = AUTH,
        ):
            if authority != AUTH: return GateOutput(GateState.MISSING)
            if failed_security_scan or environment_mismatch or sandbox_trust_root_failure:
                return GateOutput(GateState.MISSING)
            return GateOutput(GateState.SATISFIED)

        # Mutated evaluator returns SATISFIED when evidence omitted (FAIL-OPEN flaw)
        mutated_result = mutated_evaluator(authority=AUTH)
        assert mutated_result.state == GateState.SATISFIED

        # Real fixed evaluator MUST kill this mutation by returning MISSING
        real_result = evaluate_pd_ch9_003_security_promotion_gate(authority=AUTH)
        assert real_result.state == GateState.MISSING
        assert real_result.state != mutated_result.state


class TestPDCH9004MetricReportingIntegrity:
    def test_authority_enforced(self):
        res = evaluate_pd_ch9_004_metric_reporting_integrity({}, authority=None)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH9-004"

    def test_missing_report(self):
        res = evaluate_pd_ch9_004_metric_reporting_integrity(None, authority=AUTH)
        assert res.state == GateState.MISSING

    def test_zero_denominator_rejected(self):
        rep = {f: f"val_{f}" for f in REQUIRED_METRIC_REPORT_FIELDS}
        rep["denominator"] = 0
        res = evaluate_pd_ch9_004_metric_reporting_integrity(rep, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH9-004"

    @pytest.mark.parametrize("missing_field", list(REQUIRED_METRIC_REPORT_FIELDS))
    def test_missing_metric_field(self, missing_field):
        rep = {f: f"val_{f}" for f in REQUIRED_METRIC_REPORT_FIELDS}
        rep["denominator"] = 100
        del rep[missing_field]
        res = evaluate_pd_ch9_004_metric_reporting_integrity(rep, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH9-004"

    def test_metric_report_satisfied(self):
        rep = {f: f"val_{f}" for f in REQUIRED_METRIC_REPORT_FIELDS}
        rep["denominator"] = 500
        res = evaluate_pd_ch9_004_metric_reporting_integrity(rep, authority=AUTH)
        assert res.state == GateState.SATISFIED


class TestPDCH9005DataRetentionPolicy:
    def test_authority_enforced(self):
        res = evaluate_pd_ch9_005_data_retention_policy(True, True, authority=None)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH9-005"

    def test_beyond_retention_limit(self):
        res = evaluate_pd_ch9_005_data_retention_policy(False, True, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH9-005"

    def test_missing_policy_reference(self):
        res = evaluate_pd_ch9_005_data_retention_policy(True, False, authority=AUTH)
        assert res.state == GateState.MISSING
        assert res.must_id == "PD-CH9-005"

    def test_data_retention_satisfied(self):
        res = evaluate_pd_ch9_005_data_retention_policy(True, True, recorded_action=True, authority=AUTH)
        assert res.state == GateState.SATISFIED


class TestAggregateB9AGate:
    def test_aggregate_satisfied(self):
        payload = {
            "threat_record": {f: f"val_{f}" for f in REQUIRED_THREAT_FIELDS},
            "absence_of_findings_as_pass": False,
            "eval_run": {f: f"val_{f}" for f in REQUIRED_EVAL_RUN_BINDINGS},
            "critical_regression": False,
            "unqualified_data_handling": False,
            "failed_security_scan": False,
            "environment_mismatch": False,
            "sandbox_trust_root_failure": False,
            "metric_report": dict({f: f"val_{f}" for f in REQUIRED_METRIC_REPORT_FIELDS}, denominator=100),
            "within_retention_limit": True,
            "has_policy_reference": True,
            "recorded_action": True,
        }
        res = evaluate_b9_a_gate(payload, authority=AUTH)
        assert len(res) == 6
        assert all(out.state == GateState.SATISFIED for out in res.values())

    def test_aggregate_no_authority(self):
        res = evaluate_b9_a_gate({}, authority=None)
        assert len(res) == 6
        assert all(out.state == GateState.MISSING for out in res.values())
