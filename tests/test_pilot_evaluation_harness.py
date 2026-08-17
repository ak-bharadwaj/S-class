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
    ObserverVerificationRecord,
    ActiveTaskContext,
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

    plans = [protocol.generate_participant_session_plan(f"dev_{i}", i) for i in range(6)]
    hashes = set(p.session_plan_hash for p in plans)
    assert len(hashes) == 6

    task_ids = [t["task_id"] for t in protocol.get_standard_task_catalog()]
    for t_id in task_ids:
        positions = [p.ordered_task_ids.index(t_id) + 1 for p in plans]
        conditions = [p.condition_schedule[t_id] for p in plans]

        assert set(positions) == {1, 2, 3}
        assert "BASELINE" in conditions
        assert "SCLASS_TREATMENT" in conditions


def test_external_validation_block_provenance():
    protocol = ExternalValidationProtocol()
    plan_0 = protocol.generate_participant_session_plan("dev_0", 0)
    plan_5 = protocol.generate_participant_session_plan("dev_5", 5)
    plan_6 = protocol.generate_participant_session_plan("dev_6", 6)

    assert plan_0.block_id == "BLOCK-01"
    assert plan_0.participant_index_in_block == 0

    assert plan_5.block_id == "BLOCK-01"
    assert plan_5.participant_index_in_block == 5

    assert plan_6.block_id == "BLOCK-02"
    assert plan_6.participant_index_in_block == 0


def test_external_validation_protocol_smoke_execution(tmp_path):
    out_file = str(tmp_path / "external_protocol_receipt.json")
    summary = run_external_validation_smoke(output_path=out_file, tested_sha="test_commit_sha_12345")

    assert os.path.exists(out_file)
    assert summary["protocol_readiness"] == "READY_FOR_EXTERNAL_PARTICIPANTS"
    assert summary["external_evidence_status"] == "AWAITING_REAL_PARTICIPANTS"
    assert summary["provenance"]["protocol_smoke_trials_count"] == 18
    assert summary["provenance"]["real_participant_trials_count"] == 0
    assert len(summary["session_plans"]) == 6

    assert summary["real_participant_metrics"]["sclass_treatment"]["mean_trust_score"] is None
    assert summary["real_participant_metrics"]["sclass_treatment"]["mean_usefulness_score"] is None


def test_external_validation_real_participant_trial_authoritative_lifecycle():
    protocol = ExternalValidationProtocol()
    plan = protocol.generate_participant_session_plan("real_dev_01", 0)
    protocol.register_plan(plan)

    def dummy_generator(spec):
        return lambda tokens: tokens >= 0

    # Step 1: Start task 1
    active_task = protocol.start_participant_task("real_dev_01", 1)
    assert active_task.task_order_index == 1
    assert active_task.task_id == plan.ordered_task_ids[0]
    assert active_task.assignment == plan.condition_schedule[active_task.task_id]

    # Observer verification
    observer = ObserverVerificationRecord(
        observer_id="observer_dr_smith",
        verified_outcome="SUCCESS",
        verification_notes=["Observed clean implementation passing all property obligations"]
    )

    # Step 2: Finish task
    trial = protocol.finish_participant_task(
        active_task=active_task,
        code_generator=dummy_generator,
        observer_verification=observer,
        rework_iterations=1,
        developer_interventions=0,
        trust_score=4.5,
        usefulness_score=4.8
    )

    assert trial.is_real_participant is True
    assert trial.block_id == "BLOCK-01"
    assert trial.observer_id == "observer_dr_smith"
    assert trial.task_outcome == "SUCCESS"
    assert trial.task_completion_time_sec >= 0.0
    assert trial.measurement_sources["task_completion_time_sec"] == MeasurementProvenance.INSTRUMENTED_HUMAN_TASK_TIME
    assert trial.measurement_sources["task_outcome"] == MeasurementProvenance.OBSERVER_VERIFIED
    assert trial.measurement_sources["developer_trust_score"] == MeasurementProvenance.PARTICIPANT_REPORTED

    summary = protocol.generate_validation_summary(tested_sha="test_sha_real")
    assert summary["provenance"]["real_participant_trials_count"] == 1
    assert summary["provenance"]["real_participants_enrolled"] == 1


def test_tamper_attempt_to_execute_without_registered_plan_fails_closed():
    protocol = ExternalValidationProtocol()
    with pytest.raises(ValueError, match="No registered session plan found"):
        protocol.start_participant_task("unregistered_dev", 1)


def test_tamper_attempt_with_invalid_task_order_index_fails_closed():
    protocol = ExternalValidationProtocol()
    plan = protocol.generate_participant_session_plan("dev_02", 1)
    protocol.register_plan(plan)

    with pytest.raises(ValueError, match="Invalid task_order_index"):
        protocol.start_participant_task("dev_02", 4)


def test_tamper_attempt_with_corrupted_plan_hash_fails_closed():
    protocol = ExternalValidationProtocol()
    plan = protocol.generate_participant_session_plan("dev_03", 2)
    plan.session_plan_hash = "tampered_hash_value_12345"

    with pytest.raises(ValueError, match="integrity verification failed"):
        protocol.register_plan(plan)


def test_tamper_attempt_missing_observer_verification_fails_closed():
    protocol = ExternalValidationProtocol()
    plan = protocol.generate_participant_session_plan("dev_04", 3)
    protocol.register_plan(plan)

    active_task = protocol.start_participant_task("dev_04", 1)

    with pytest.raises(ValueError, match="Missing or invalid ObserverVerificationRecord"):
        protocol.finish_participant_task(
            active_task=active_task,
            code_generator=lambda s: (lambda x: x),
            observer_verification=None,  # Missing observer
            rework_iterations=0,
            developer_interventions=0,
            trust_score=4.0,
            usefulness_score=4.0
        )
