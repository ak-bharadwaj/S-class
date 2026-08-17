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
    run_external_validation_demo
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
    assert receipt["milestone"] == "THESIS-GATE-1: Synthetic Efficacy Pilot (Controlled Failure Injection)"
    assert receipt["observable_comparative_metrics"]["baseline_defects_escaped"] > 0
    assert receipt["observable_comparative_metrics"]["treatment_defects_escaped"] == 0
    assert receipt["observable_comparative_metrics"]["pre_gen_defects_caught_by_grounding"] > 0
    assert receipt["observable_comparative_metrics"]["post_gen_defects_caught_by_evidence"] > 0
    assert receipt["observable_comparative_metrics"]["rework_cycles_avoided"] > 0
    assert receipt["observable_comparative_metrics"]["false_positive_rate"] <= 0.050
    assert receipt["pilot_verdict"] == "PASS"


def test_external_validation_protocol_execution(tmp_path):
    out_file = str(tmp_path / "external_receipt.json")
    summary = run_external_validation_demo(output_path=out_file, tested_sha="test_commit_sha_12345")

    assert os.path.exists(out_file)
    assert summary["protocol_status"] == "READY_FOR_EXTERNAL_PARTICIPANTS"
    assert summary["provenance"]["total_trials_recorded"] == 6
    assert summary["comparative_metrics"]["sclass_treatment"]["mean_trust_score"] >= 4.0
    assert summary["comparative_metrics"]["sclass_treatment"]["mean_usefulness_score"] >= 4.0
