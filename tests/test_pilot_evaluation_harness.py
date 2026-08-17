"""
Tests for THESIS-GATE-1 Pilot Evaluation Harness.
"""

import os
import pytest
from benchmark.pilot.pilot_evaluation_harness import (
    create_standard_pilot_scenarios,
    run_pilot_evaluation_campaign
)


def test_standard_scenarios_construction():
    scenarios = create_standard_pilot_scenarios()
    assert len(scenarios) == 5
    # Verify scenarios cover pre-gen flaws, post-gen bugs, and clean passes
    has_pre = any(s.has_inherent_pre_gen_flaw for s in scenarios)
    has_post = any(s.has_inherent_post_gen_bug for s in scenarios)
    has_clean = any(not s.has_inherent_pre_gen_flaw and not s.has_inherent_post_gen_bug for s in scenarios)

    assert has_pre is True
    assert has_post is True
    assert has_clean is True


def test_pilot_evaluation_campaign_execution(tmp_path):
    out_file = str(tmp_path / "pilot_receipt.json")
    receipt = run_pilot_evaluation_campaign(output_path=out_file, tested_sha="test_commit_sha_12345")

    assert os.path.exists(out_file)
    assert receipt["milestone"] == "THESIS-GATE-1: Enterprise Core + External Validation Pilot"
    assert receipt["comparative_metrics"]["baseline_defects_escaped"] > 0
    assert receipt["comparative_metrics"]["treatment_defects_escaped"] == 0
    assert receipt["comparative_metrics"]["pre_gen_defects_caught_by_grounding"] > 0
    assert receipt["comparative_metrics"]["post_gen_defects_caught_by_evidence"] > 0
    assert receipt["comparative_metrics"]["rework_cycles_avoided"] > 0
    assert receipt["comparative_metrics"]["false_positive_rate"] <= 0.050
    assert receipt["final_pilot_verdict"] == "PASS"
