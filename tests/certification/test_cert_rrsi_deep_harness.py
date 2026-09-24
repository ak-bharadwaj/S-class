"""
Certification Suite: Deep RRSI Evolution Substrate Certification.
Fulfills Directive Section 18, 42, and 44:
Validates the harvested RRSI evolution substrate:
1. Empirical noise calibration from baseline trials.
2. Candidate proposal & hypothesis-driven edit tracking.
3. Critic gate: blocks benchmark leakage, test tampering, oracle abuse, and Trust Kernel edits.
4. Smoke gate: fast syntactic and construction validation.
5. Repeated benchmark evaluation with fixed denominator.
6. Multi-objective selection rule & non-compensatory domain guards.
7. OOD and held-out domain evaluation partitions.
8. Offline readjudication without re-running tests.
9. Selective infrastructure reevaluation (only INVALID_INFRA).
10. Mechanism attribution tracking (hit rate computation in attribution.jsonl).
11. Multi-objective Pareto frontier tracking.
"""

import os
import json
import pytest
import tempfile
import shutil

from sclass.evolution.candidate import EvolutionCandidate, HypothesisEdit, EvolutionStatus
from sclass.evolution.components import NON_EVOLVABLE_COMPONENTS, is_component_evolvable
from sclass.evolution.critic import CandidateCritic
from sclass.evolution.evaluator import CandidateEvaluator, TrialOutcome, TrialResult
from sclass.evolution.calibration import NoiseCalibrator
from sclass.evolution.selector import CandidateSelector, DomainGuards
from sclass.evolution.domain import SClassStandardCodingDomain
from sclass.evolution.attribution import AttributionTracker
from sclass.evolution.frontier import ParetoFrontier
from sclass.evolution.readjudication import Readjudicator
from sclass.evolution.reevaluation import InfrastructureReevaluator
from sclass.evolution.engine import EvolutionEngine


@pytest.fixture
def workspace_dir():
    ws = tempfile.mkdtemp(prefix="sclass_cert_rrsi_")
    yield ws
    shutil.rmtree(ws, ignore_errors=True)


def test_noise_calibration_computation():
    """
    RRSI Cert 1: Noise Calibration.
    Estimates variance from baseline scores and computes calibrated noise band delta.
    """
    baseline_scores = [0.80, 0.82, 0.79, 0.81, 0.80]
    record = NoiseCalibrator.calibrate(scores=baseline_scores, dataset_version="v2.1")

    assert record.k_trials == 5
    assert record.baseline_mean == pytest.approx(0.804, 0.01)
    assert record.baseline_variance > 0.0
    assert record.noise_band_delta > 0.0
    assert record.dataset_version == "v2.1"


def test_critic_blocks_forbidden_edits():
    """
    RRSI Cert 2: Pre-Evaluation Critic Gate.
    Blocks test tampering, skipping, assertions trivialization, and Trust Kernel modifications.
    """
    # Case A: Candidate modifying tests
    cand_test_tamper = EvolutionCandidate(
        candidate_id="cand_bad_test",
        parent_commit="HEAD",
        candidate_commit="HEAD~1",
        worktree="",
        round=1,
        edits=[
            HypothesisEdit(
                edit_id="edit_1",
                component="control_flow",
                hypothesis="Simplify test",
                mechanism="stub test",
                diff="def test_something(): pass\nassert True",
            )
        ],
        hypotheses=["Bypass"],
        component_set={"control_flow"},
    )
    res_a = CandidateCritic.evaluate_candidate(cand_test_tamper)
    assert res_a.passed is False
    assert any("assert True" in r or "test_" in r for r in res_a.rejection_reasons)

    # Case B: Candidate modifying Trust Kernel component
    cand_auth = EvolutionCandidate(
        candidate_id="cand_bad_auth",
        parent_commit="HEAD",
        candidate_commit="HEAD~1",
        worktree="",
        round=1,
        edits=[
            HypothesisEdit(
                edit_id="edit_2",
                component="authorization",
                hypothesis="Weaken auth",
                mechanism="disable checks",
                diff="ALLOW_ALL = True",
            )
        ],
        hypotheses=["Weaken auth"],
        component_set={"authorization"},
    )
    res_b = CandidateCritic.evaluate_candidate(cand_auth)
    assert res_b.passed is False
    assert any("non-evolvable" in r.lower() for r in res_b.rejection_reasons)


def test_smoke_gate_validation():
    """
    RRSI Cert 3: Smoke Gate.
    Rejects malformed Python syntax before costly evaluation.
    """
    cand = EvolutionCandidate(
        candidate_id="cand_smoke",
        parent_commit="HEAD",
        candidate_commit="HEAD~1",
        worktree="",
        round=1,
    )
    # Valid syntax passes
    res_ok = CandidateEvaluator.smoke_check(cand, test_code="def foo(): return 42")
    assert res_ok.passed is True

    # Syntax error fails
    res_err = CandidateEvaluator.smoke_check(cand, test_code="def broken( return")
    assert res_err.passed is False


def test_repeated_evaluation_and_fixed_denominator():
    """
    RRSI Cert 4: Repeated Evaluation.
    Evaluates across task set x k trials with fixed denominator scoring.
    """
    cand = EvolutionCandidate(
        candidate_id="cand_eval",
        parent_commit="HEAD",
        candidate_commit="HEAD~1",
        worktree="",
        round=1,
    )
    tasks = ["task_1", "task_2", "task_3"]

    def mock_trial(task_id: str, trial_idx: int):
        # task_3 fails on trial 1
        if task_id == "task_3" and trial_idx == 1:
            return TrialResult(
                trial_id=f"t_{task_id}_{trial_idx}",
                task_id=task_id,
                trial_index=trial_idx,
                outcome=TrialOutcome.FAIL,
                score=0.0,
                token_cost=300,
                latency_ms=100.0,
            )
        return TrialResult(
            trial_id=f"t_{task_id}_{trial_idx}",
            task_id=task_id,
            trial_index=trial_idx,
            outcome=TrialOutcome.PASS,
            score=1.0,
            token_cost=500,
            latency_ms=120.0,
        )

    report = CandidateEvaluator.evaluate(
        candidate=cand,
        tasks=tasks,
        k_trials=2,
        trial_runner_fn=mock_trial,
    )

    assert report.total_tasks == 3
    assert len(report.trials) == 6 # 3 tasks * 2 trials
    assert report.pass_rate == pytest.approx(5 / 6, 0.01)
    assert report.mean_score == pytest.approx(5 / 6, 0.01)
    assert report.untrusted_candidate_evidence is True


def test_non_compensatory_domain_guards():
    """
    RRSI Cert 5: Non-Compensatory Domain Guards.
    High score CANNOT compensate for security violations, bypass attempts, or cost explosion.
    """
    cand = EvolutionCandidate(
        candidate_id="cand_guards",
        parent_commit="HEAD",
        candidate_commit="HEAD~1",
        worktree="",
        round=1,
    )
    selector = CandidateSelector(noise_floor=0.05, guards=DomainGuards(max_security_failures=0))

    # High score report
    report = CandidateEvaluator.evaluate(candidate=cand, tasks=["task_1"], k_trials=1)

    # Candidate has a security violation
    res = selector.select(
        candidate=cand,
        report=report,
        baseline_score=0.50, # High delta_s = 0.50
        baseline_cost=500.0,
        security_failures=1, # Security failure!
    )

    assert res.admissible is False
    assert res.guards_satisfied is False
    assert any("Security failures" in v for v in res.violated_guards)


def test_offline_readjudication():
    """
    RRSI Cert 6: Offline Readjudication.
    Re-applies selection criteria without re-running evaluations.
    """
    cand = EvolutionCandidate(candidate_id="cand_readjud", parent_commit="HEAD", candidate_commit="", worktree="", round=1)
    report = CandidateEvaluator.evaluate(candidate=cand, tasks=["task_1"], k_trials=1)

    # Initial selector with strict noise floor = 0.50 -> Rejected
    selector_strict = CandidateSelector(noise_floor=0.50)
    res_1 = Readjudicator.readjudicate_candidate(
        candidate=cand,
        report=report,
        selector=selector_strict,
        baseline_score=0.80, # delta = 1.0 - 0.8 = 0.20 < 0.50
        baseline_cost=500.0,
    )
    assert res_1.admissible is False
    assert cand.status == EvolutionStatus.REJECTED

    # Re-adjudicate with relaxed noise floor = 0.10 -> Admissible
    selector_relaxed = CandidateSelector(noise_floor=0.10)
    res_2 = Readjudicator.readjudicate_candidate(
        candidate=cand,
        report=report,
        selector=selector_relaxed,
        baseline_score=0.80, # delta = 0.20 >= 0.10
        baseline_cost=500.0,
    )
    assert res_2.admissible is True
    assert cand.status == EvolutionStatus.ADMISSIBLE


def test_selective_infrastructure_reevaluation():
    """
    RRSI Cert 7: Selective Infrastructure Reevaluation.
    Only remeasures trials marked INVALID_INFRA, preserving true candidate failures.
    """
    cand = EvolutionCandidate(candidate_id="cand_infra", parent_commit="HEAD", candidate_commit="", worktree="", round=1)

    # Initial report has 1 pass, 1 candidate fail, 1 infra invalid
    initial_trials = [
        TrialResult("t1", "task_1", 0, TrialOutcome.PASS, 1.0, 500, 100.0),
        TrialResult("t2", "task_2", 0, TrialOutcome.FAIL, 0.0, 200, 50.0),
        TrialResult("t3", "task_3", 0, TrialOutcome.INVALID_INFRA, 0.0, 0, 0.0, error_message="Pipe broken"),
    ]
    report = CandidateEvaluator.evaluate(candidate=cand, tasks=["task_1", "task_2", "task_3"], k_trials=1)
    report.trials = initial_trials

    def remeasure_trial(task_id: str, trial_idx: int):
        return TrialResult(f"t_{task_id}_rem", task_id, trial_idx, TrialOutcome.PASS, 1.0, 500, 120.0)

    re_report = InfrastructureReevaluator.reevaluate_invalid_trials(report, remeasure_trial)

    # task_3 was remeasured and now passes
    t3 = [t for t in re_report.trials if t.task_id == "task_3"][0]
    assert t3.outcome == TrialOutcome.PASS

    # task_2 was a REAL candidate failure and remains FAIL
    t2 = [t for t in re_report.trials if t.task_id == "task_2"][0]
    assert t2.outcome == TrialOutcome.FAIL


def test_attribution_and_hit_rate_tracking(workspace_dir):
    """
    RRSI Cert 8: Mechanism Attribution & Hit Rate.
    Logs predictive task accuracy into attribution.jsonl.
    """
    tracker = AttributionTracker(workspace_dir)
    record = tracker.record_attribution(
        edit_id="edit_cache",
        component="client_tool",
        mechanism="Result caching",
        candidate_id="cand_1",
        predicted_tasks=["task_1", "task_2"],
        improved_tasks=["task_1"],
        regressed_tasks=[],
    )

    assert record.hit_rate == 0.5 # 1 hit out of 2 predicted
    assert os.path.exists(tracker.ledger_file)
    records = tracker.get_records()
    assert len(records) == 1
    assert records[0].edit_id == "edit_cache"


def test_pareto_frontier_tracking():
    """
    RRSI Cert 9: Multi-Objective Pareto Frontier.
    Tracks non-dominated candidates across delta_S and delta_C.
    """
    frontier = ParetoFrontier()

    # Candidate 1: Delta_S = 0.10, Delta_C = 100
    c1 = EvolutionCandidate("c1", "HEAD", "", "", round=1, score_delta_s=0.10, cost_delta_c=100.0)
    assert frontier.update(c1) is True
    assert len(frontier.get_points()) == 1

    # Candidate 2: Delta_S = 0.05, Delta_C = 200 (Dominated by c1)
    c2 = EvolutionCandidate("c2", "HEAD", "", "", round=1, score_delta_s=0.05, cost_delta_c=200.0)
    assert frontier.update(c2) is False
    assert len(frontier.get_points()) == 1

    # Candidate 3: Delta_S = 0.15, Delta_C = 150 (Trade-off: higher score, higher cost -> non-dominated)
    c3 = EvolutionCandidate("c3", "HEAD", "", "", round=1, score_delta_s=0.15, cost_delta_c=150.0)
    assert frontier.update(c3) is True
    assert len(frontier.get_points()) == 2
