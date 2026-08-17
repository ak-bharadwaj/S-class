"""
Tests for Synthetic Efficacy Pilot & External Developer Validation Protocol.
"""

import os
import time
import pytest
from benchmark.pilot.synthetic_efficacy_pilot import (
    create_synthetic_scenarios,
    run_synthetic_efficacy_campaign
)
from benchmark.pilot.external_validation_protocol import (
    ExternalValidationProtocol,
    ParticipantSessionPlan,
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


def test_external_validation_latin_square_counterbalancing():
    protocol = ExternalValidationProtocol()

    # Generate 6 session plans covering full Latin block
    plans = [protocol.generate_participant_session_plan(f"dev_{i}", i) for i in range(6)]

    # 1. Verify all 6 plans have unique task permutations or alternating condition schedules
    hashes = set(p.session_plan_hash for p in plans)
    assert len(hashes) == 6

    # 2. Check balanced distribution across the block
    task_ids = [t["task_id"] for t in protocol.get_standard_task_catalog()]
    for t_id in task_ids:
        positions = [p.ordered_task_ids.index(t_id) + 1 for p in plans]
        conditions = [p.condition_schedule[t_id] for p in plans]

        # Each task appears in positions 1, 2, and 3
        assert set(positions) == {1, 2, 3}
        # Each task appears in both BASELINE and SCLASS_TREATMENT
        assert "BASELINE" in conditions
        assert "SCLASS_TREATMENT" in conditions


def test_external_validation_protocol_smoke_execution(tmp_path):
    out_file = str(tmp_path / "external_protocol_receipt.json")
    summary = run_external_validation_smoke(output_path=out_file, tested_sha="test_commit_sha_12345")

    assert os.path.exists(out_file)
    assert summary["protocol_readiness"] == "READY_FOR_EXTERNAL_PARTICIPANTS"
    assert summary["external_evidence_status"] == "AWAITING_REAL_PARTICIPANTS"
    assert summary["provenance"]["protocol_smoke_trials_count"] == 18  # 6 devs x 3 tasks
    assert summary["provenance"]["real_participant_trials_count"] == 0
    assert len(summary["session_plans"]) == 6

    # Ensure no synthetic fake trust/usefulness scores leaked into real metrics
    assert summary["real_participant_metrics"]["sclass_treatment"]["mean_trust_score"] is None
    assert summary["real_participant_metrics"]["sclass_treatment"]["mean_usefulness_score"] is None


def test_external_validation_real_participant_trial_with_human_timing_and_outcomes():
    protocol = ExternalValidationProtocol()
    plan = protocol.generate_participant_session_plan("real_dev_01", 0)
    protocol.register_plan(plan)

    def dummy_generator(spec):
        return lambda tokens: tokens >= 0

    t_now = time.time()
    t_start = t_now - 120.0  # 120 seconds ago
    t_stop = t_now

    task_1 = plan.ordered_task_ids[0]
    cond_1 = plan.condition_schedule[task_1]

    trial = protocol.execute_participant_trial(
        participant_id="real_dev_01",
        task_id=task_1,
        task_order_index=1,
        assignment=cond_1,
        code_generator=dummy_generator,
        human_start_epoch=t_start,
        human_stop_epoch=t_stop,
        rework_iterations=1,
        developer_interventions=0,
        task_outcome="SUCCESS",
        trust_score=4.5,
        usefulness_score=4.8
    )

    assert trial.is_real_participant is True
    assert trial.task_completion_time_sec == pytest.approx(120.0, rel=1e-2)
    assert trial.measurement_sources["task_completion_time_sec"] == MeasurementProvenance.INSTRUMENTED_HUMAN_TASK_TIME
    assert trial.measurement_sources["task_outcome"] == MeasurementProvenance.OBSERVER_VERIFIED
    assert trial.measurement_sources["developer_trust_score"] == MeasurementProvenance.PARTICIPANT_REPORTED

    summary = protocol.generate_validation_summary(tested_sha="test_sha_real")
    assert summary["provenance"]["real_participant_trials_count"] == 1
    assert summary["provenance"]["real_participants_enrolled"] == 1
    assert summary["real_participant_metrics"]["baseline" if cond_1 == "BASELINE" else "sclass_treatment"]["mean_human_completion_time_sec"] == pytest.approx(120.0, rel=1e-2)
