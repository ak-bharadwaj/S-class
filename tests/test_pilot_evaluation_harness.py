"""
Tests for Synthetic Efficacy Pilot & External Developer Validation Protocol.
"""

import os
import pytest
from benchmark.pilot.synthetic_efficacy_pilot import (
    create_synthetic_scenarios,
    run_synthetic_efficacy_campaign
)
from benchmark.pilot.external_validation_protocol import (
    ExternalValidationProtocol,
    run_external_validation_smoke,
    MeasurementProvenance
)


def test_synthetic_scenarios_construction():
    scenarios = create_synthetic_scenarios()
    assert len(scenarios) == 5
    has_pre = any(s.has_inherent_pre_gen_flaw for s in scenarios)
    has_post = any(s.has_inherent_post_gen_bug for s in scenarios)
    has_clean = any(not s.has_inherent_pre_gen_flaw and not s.has_inherent_post_gen_bug for s in scenarios)

    assert has_pre is True
    assert has_post is True
    assert has_clean is True


def test_synthetic_efficacy_campaign_execution(tmp_path):
    out_file = str(tmp_path / "synthetic_receipt.json")
    receipt = run_synthetic_efficacy_campaign(output_path=out_file, tested_sha="test_commit_sha_12345")

    assert os.path.exists(out_file)
    assert "THESIS-GATE-1" in receipt["milestone"]
    assert receipt["observable_comparative_metrics"]["baseline_defects_escaped"] > 0
    assert receipt["observable_comparative_metrics"]["treatment_defects_escaped"] == 0
    assert receipt["observable_comparative_metrics"]["pre_gen_defects_caught_by_grounding"] > 0
    assert receipt["observable_comparative_metrics"]["post_gen_defects_caught_by_evidence"] > 0
    assert receipt["observable_comparative_metrics"]["rework_cycles_avoided"] > 0
    assert receipt["observable_comparative_metrics"]["false_positive_rate"] <= 0.050
    assert receipt["pilot_verdict"] == "PASS"


def test_external_validation_protocol_smoke_execution(tmp_path):
    out_file = str(tmp_path / "external_protocol_receipt.json")
    summary = run_external_validation_smoke(output_path=out_file, tested_sha="test_commit_sha_12345")

    assert os.path.exists(out_file)
    assert summary["protocol_readiness"] == "READY_FOR_EXTERNAL_PARTICIPANTS"
    assert summary["external_evidence_status"] == "AWAITING_REAL_PARTICIPANTS"
    assert summary["provenance"]["protocol_smoke_trials_count"] == 6
    assert summary["provenance"]["real_participant_trials_count"] == 0

    # Ensure no synthetic fake trust/usefulness scores leaked into real metrics
    assert summary["real_participant_metrics"]["sclass_treatment"]["mean_trust_score"] is None
    assert summary["real_participant_metrics"]["sclass_treatment"]["mean_usefulness_score"] is None


def test_external_validation_within_participant_counterbalancing():
    protocol = ExternalValidationProtocol()

    # Verify that conditions alternate across tasks for the same participant
    cond_1 = protocol.assign_treatment_counterbalanced("dev_alpha", 1, seed=42)
    cond_2 = protocol.assign_treatment_counterbalanced("dev_alpha", 2, seed=42)
    cond_3 = protocol.assign_treatment_counterbalanced("dev_alpha", 3, seed=42)

    assert cond_1 in ["BASELINE", "SCLASS_TREATMENT"]
    assert cond_2 in ["BASELINE", "SCLASS_TREATMENT"]
    assert cond_1 != cond_2
    assert cond_1 == cond_3


def test_external_validation_real_participant_trial_with_outcomes():
    protocol = ExternalValidationProtocol()

    def dummy_generator(spec):
        return lambda tokens: tokens >= 0

    # Real participant completes 3 counterbalanced tasks with recorded outcomes
    trial_1 = protocol.execute_participant_trial(
        participant_id="real_dev_101",
        task_id="TASK-01-TOKEN-RATE-LIMITER",
        task_order_index=1,
        code_generator=dummy_generator,
        rework_iterations=0,
        developer_interventions=0,
        task_outcome="SUCCESS",
        trust_score=4.5,
        usefulness_score=4.8,
        seed=101
    )

    trial_2 = protocol.execute_participant_trial(
        participant_id="real_dev_101",
        task_id="TASK-02-CONFIG-SCHEMA-PARSER",
        task_order_index=2,
        code_generator=dummy_generator,
        rework_iterations=1,
        developer_interventions=1,
        task_outcome="SUCCESS",
        trust_score=4.0,
        usefulness_score=4.2,
        seed=101
    )

    trial_3 = protocol.execute_participant_trial(
        participant_id="real_dev_101",
        task_id="TASK-03-IDEMPOTENT-CACHE",
        task_order_index=3,
        code_generator=dummy_generator,
        rework_iterations=2,
        developer_interventions=2,
        task_outcome="ABANDONED",
        trust_score=2.0,
        usefulness_score=2.5,
        seed=101
    )

    assert trial_1.task_outcome == "SUCCESS"
    assert trial_3.task_outcome == "ABANDONED"
    assert trial_1.assignment != trial_2.assignment

    summary = protocol.generate_validation_summary(tested_sha="test_commit_real_trial")
    assert summary["provenance"]["real_participant_trials_count"] == 3
    assert summary["provenance"]["real_participants_enrolled"] == 1
    # Check that outcomes are recorded in metrics
    total_outcomes = (
        summary["real_participant_metrics"]["baseline"]["outcomes"]["success"] +
        summary["real_participant_metrics"]["baseline"]["outcomes"]["failure"] +
        summary["real_participant_metrics"]["baseline"]["outcomes"]["abandoned"] +
        summary["real_participant_metrics"]["sclass_treatment"]["outcomes"]["success"] +
        summary["real_participant_metrics"]["sclass_treatment"]["outcomes"]["failure"] +
        summary["real_participant_metrics"]["sclass_treatment"]["outcomes"]["abandoned"]
    )
    assert total_outcomes == 3
