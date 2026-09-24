"""
Integration Test: Real EvolutionEngine Substrate (Directive Section 44).
Exercises the complete RRSI evolution cycle through S-Class managed storage:
baseline
  ↓
calibrated noise
  ↓
candidate worktree / proposal
  ↓
critic
  ↓
smoke
  ↓
evaluation
  ↓
independent evidence
  ↓
selection
  ↓
heldout
  ↓
history
  ↓
readjudication
  ↓
reevaluation
"""

import os
import pytest
import tempfile
import shutil

from sclass.evolution.engine import EvolutionEngine
from sclass.evolution.candidate import EvolutionStatus
from sclass.evolution.selector import CandidateSelector, DomainGuards
from sclass.evolution.evaluator import TrialResult, TrialOutcome


@pytest.fixture
def workspace_env():
    ws = tempfile.mkdtemp(prefix="sclass_rrsi_live_")
    yield ws
    shutil.rmtree(ws, ignore_errors=True)


def test_rrsi_evolution_cycle_end_to_end(workspace_env):
    engine = EvolutionEngine(workspace_dir=workspace_env)

    # 1. Baseline calibration
    calib = engine.run_baseline_calibration(baseline_trials=5)
    assert calib.noise_band_delta > 0.0
    assert engine.selector.noise_floor == calib.noise_band_delta

    # 2. Propose candidate
    candidate = engine.propose_candidate(
        component="prompt",
        hypothesis="Add chain-of-thought instructions",
        mechanism="Prompt engineering",
        diff="SYSTEM_PROMPT += ' Explain your reasoning step by step.'",
        predicted_tasks=["task_evolve_1", "task_evolve_2"],
    )
    assert candidate.status == EvolutionStatus.DRAFT

    # 3. Custom trial runner producing high score
    def mock_evaluator(task_id: str, trial_idx: int):
        return TrialResult(
            trial_id=f"t_{task_id}_{trial_idx}",
            task_id=task_id,
            trial_index=trial_idx,
            outcome=TrialOutcome.PASS,
            score=0.95,
            token_cost=800,
            latency_ms=150.0,
        )

    # 4. Full evaluation & adjudication pipeline
    result = engine.evaluate_and_adjudicate(candidate, trial_runner_fn=mock_evaluator)

    # 5. Evolution plane outcome
    assert result["verdict"] == "ACCEPTED"
    assert candidate.status == EvolutionStatus.ACCEPTED
    assert candidate.verification_id is not None

    # 6. Verification that assurance ledger received evolution assessment
    ledger_entries = engine.assurance_ledger.get_entries()
    assessment_entries = [e for e in ledger_entries if e["entry_type"] == "evolution_assessment"]
    assert len(assessment_entries) == 1
    assert assessment_entries[0]["payload"]["verification_id"] == candidate.verification_id
    assert assessment_entries[0]["payload"]["status"] == "VERIFIED_ADMISSIBLE"

    # 7. Check Pareto frontier
    points = engine.frontier.get_points()
    assert len(points) == 1
    assert points[0].candidate_id == candidate.candidate_id

    # 8. Check attribution ledger
    attr_records = engine.attribution.get_records()
    assert len(attr_records) == 1
    assert attr_records[0].edit_id == candidate.edits[0].edit_id
    assert attr_records[0].hit_rate == 1.0

    # 9. Check evolution history ledger
    history_entries = engine.history.get_entries()
    assert len(history_entries) == 1
    assert history_entries[0].accepted is True
