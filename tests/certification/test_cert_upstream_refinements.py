"""
Certification Suite: Upstream Harvest Refinements & Hardening.
Validates the refined and hardened mechanisms from Step-Code and RRSI:
1. CandidateCritic path normalization across Windows backslash and POSIX forward slash formats.
2. EvolutionCandidate branch tracking and Git worktree isolation with directory fallback.
3. EvolutionEngine.readjudicate(round) and EvolutionEngine.reevaluate(round) lifecycle methods.
4. CandidateEvaluator exception handling, infrastructure failure classification, and missing trial policies.
5. Complete Domain protocol implementation (evolve_set, heldout_set, smoke_set, run, score, briefs, etc.).
6. Runtime plan & task system: model task updates vs canonical obligation immutability.
7. Subsystem migration registry classification and query APIs.
8. Module aliasing (sclass.evolution.controller and sclass.evolution.evaluation).
"""

import os
import pytest
import tempfile
import shutil

from sclass.evolution.candidate import EvolutionCandidate, HypothesisEdit, EvolutionStatus
from sclass.evolution.critic import CandidateCritic
from sclass.evolution.evaluator import CandidateEvaluator, TrialOutcome, TrialResult
from sclass.evolution.domain import SClassStandardCodingDomain
from sclass.evolution.engine import EvolutionEngine
from sclass.evolution.selector import CandidateSelector, DomainGuards
from sclass.evolution.gitops import GitWorktreeManager, WorktreeHandle
from sclass.runtime.plans import RuntimeTask, RuntimeTaskStatus, ExecutionPlanCandidate
from sclass.upstream.migration import MigrationRegistry, MigrationStatus
from sclass.core.errors import SecurityViolationError


@pytest.fixture
def workspace_dir():
    ws = tempfile.mkdtemp(prefix="sclass_cert_refinements_")
    yield ws
    shutil.rmtree(ws, ignore_errors=True)


def test_critic_windows_backslash_normalization():
    """
    Validates that CandidateCritic normalizes Windows-style backslashes in diffs
    and catches attempts to modify protected trust kernel paths.
    """
    # Diff targeting src\sclass\trust\state_reducer.py with Windows backslashes
    windows_diff = (
        "--- a/src\\sclass\\trust\\state_reducer.py\n"
        "+++ b/src\\sclass\\trust\\state_reducer.py\n"
        "@@ -10,3 +10,4 @@\n"
        "+# Malicious trust injection"
    )
    edit = HypothesisEdit(
        edit_id="edit_win_1",
        component="prompt",
        hypothesis="Test path normalization",
        mechanism="Windows diff",
        diff=windows_diff,
    )
    cand = EvolutionCandidate(
        candidate_id="cand_win_1",
        parent_commit="HEAD",
        candidate_commit="commit_win_1",
        worktree="",
        branch="evolution/cand_win_1",
        round=1,
        edits=[edit],
        hypotheses=["Test path normalization"],
        component_set={"prompt"},
    )

    result = CandidateCritic.evaluate_candidate(cand)
    assert result.passed is False
    assert any("src/sclass/trust/" in r for r in result.rejection_reasons)

    # Diff targeting src\sclass\assurance\authority.py
    assurance_diff = "--- a/src\\sclass\\assurance\\authority.py\n+++ b/src\\sclass\\assurance\\authority.py\n"
    edit_assur = HypothesisEdit(
        edit_id="edit_assur_1",
        component="prompt",
        hypothesis="Tamper assurance",
        mechanism="Windows diff",
        diff=assurance_diff,
    )
    cand.edits = [edit_assur]
    result_assur = CandidateCritic.evaluate_candidate(cand)
    assert result_assur.passed is False
    assert any("src/sclass/assurance/" in r for r in result_assur.rejection_reasons)


def test_evolution_candidate_branch_and_worktree(workspace_dir):
    """
    Validates EvolutionCandidate branch field tracking and GitWorktreeManager
    directory copy fallback and cleanup.
    """
    cand = EvolutionCandidate(
        candidate_id="cand_branch_test",
        parent_commit="HEAD",
        candidate_commit="commit_1",
        worktree="/tmp/wt",
        round=1,
        branch="evolution/cand_branch_test",
    )
    d = cand.to_dict()
    assert d["branch"] == "evolution/cand_branch_test"

    # From dict roundtrip
    cand_rt = EvolutionCandidate.from_dict(d)
    assert cand_rt.branch == "evolution/cand_branch_test"

    # Worktree manager fallback
    wt_mgr = GitWorktreeManager(repo_root=workspace_dir)
    # Create sample file in workspace
    with open(os.path.join(workspace_dir, "sample.txt"), "w") as f:
        f.write("hello sclass")

    handle = wt_mgr.create_candidate_worktree("test_wt_1")
    assert handle.branch_name == "evolution/test_wt_1"
    assert os.path.exists(handle.worktree_path)
    # Sample file was copied via fallback or worktree
    assert os.path.exists(os.path.join(handle.worktree_path, "sample.txt"))

    # Cleanup
    wt_mgr.remove_worktree(handle)
    assert not os.path.exists(handle.worktree_path)


def test_evolution_engine_readjudicate_and_reevaluate(workspace_dir):
    """
    Validates EvolutionEngine.readjudicate(round) and EvolutionEngine.reevaluate(round)
    per Directive Sections 32 and 33.
    """
    engine = EvolutionEngine(workspace_dir=workspace_dir)
    engine.run_baseline_calibration(baseline_trials=3)

    cand = engine.propose_candidate(
        component="prompt",
        hypothesis="Improve clarity",
        mechanism="Prompt engineering",
        diff="prompt += ' Clear instructions'",
    )

    # Initial evaluation with an infrastructure failure in trial 0
    trial_count = 0
    def mock_initial_trials(task_id: str, idx: int) -> TrialResult:
        nonlocal trial_count
        trial_count += 1
        if idx == 0:
            return TrialResult(
                trial_id=f"t_infra_{trial_count}",
                task_id=task_id,
                trial_index=idx,
                outcome=TrialOutcome.INVALID_INFRA,
                score=0.0,
                token_cost=0,
                latency_ms=0.0,
                error_message="Simulated connection timeout",
            )
        return TrialResult(
            trial_id=f"t_pass_{trial_count}",
            task_id=task_id,
            trial_index=idx,
            outcome=TrialOutcome.PASS,
            score=0.95,
            token_cost=800,
            latency_ms=100.0,
        )

    res = engine.evaluate_and_adjudicate(cand, trial_runner_fn=mock_initial_trials)
    assert cand.round == 1

    # Readjudicate round 1 before remeasurement: rejected because pass_rate < 0.95 due to infra trial
    readj_before = engine.readjudicate(round_num=1)
    assert readj_before.admissible is False
    assert readj_before.selection_verdict == "REJECT_GUARD_VIOLATION"

    # Reevaluate round 1: remeasure ONLY the invalid infrastructure trial (Directive Section 33)
    def remeasure_trial(task_id: str, idx: int) -> TrialResult:
        return TrialResult(
            trial_id=f"t_remeasured_{idx}",
            task_id=task_id,
            trial_index=idx,
            outcome=TrialOutcome.PASS,
            score=0.98,
            token_cost=850,
            latency_ms=90.0,
        )

    reeval_res = engine.reevaluate(round_num=1, remeasure_trial_fn=remeasure_trial)
    assert reeval_res["report"].invalid_infra_count == 0
    assert reeval_res["report"].mean_score > 0.90
    assert reeval_res["selection"].admissible is True

    # Now readjudicate the remeasured round with a strict noise floor (should reject with REJECT_BELOW_NOISE_FLOOR)
    strict_selector = CandidateSelector(noise_floor=0.50)
    readj_strict = engine.readjudicate(round_num=1, selector=strict_selector)
    assert readj_strict.admissible is False
    assert readj_strict.selection_verdict == "REJECT_BELOW_NOISE_FLOOR"

    # Readjudicate the remeasured round with a lenient noise floor (should be ADMISSIBLE)
    lenient_selector = CandidateSelector(noise_floor=0.01)
    readj_lenient = engine.readjudicate(round_num=1, selector=lenient_selector)
    assert readj_lenient.admissible is True
    assert readj_lenient.selection_verdict == "ADMISSIBLE"


def test_candidate_evaluator_robustness():
    """
    Validates CandidateEvaluator handling of unexpected exceptions and missing trials per Section 26.
    """
    cand = EvolutionCandidate(
        candidate_id="cand_robust_test",
        parent_commit="HEAD",
        candidate_commit="commit_rob",
        worktree="",
        round=1,
    )

    # 1. Unhandled exception in runner function -> converted to INVALID_INFRA
    def crashing_runner(task_id: str, idx: int):
        if idx == 0:
            raise ConnectionResetError("Broken pipe")
        return {"outcome": "PASS", "score": 1.0, "token_cost": 200, "latency_ms": 50.0}

    report = CandidateEvaluator.evaluate(
        candidate=cand,
        tasks=["task_1"],
        k_trials=2,
        trial_runner_fn=crashing_runner,
    )
    assert report.invalid_infra_count == 1
    assert any(t.outcome == TrialOutcome.INVALID_INFRA for t in report.trials)

    # 2. Missing trial (returns None) -> converted to FAIL with score 0.0
    def missing_runner(task_id: str, idx: int):
        return None

    report_missing = CandidateEvaluator.evaluate(
        candidate=cand,
        tasks=["task_1"],
        k_trials=1,
        trial_runner_fn=missing_runner,
    )
    assert report_missing.trials[0].outcome == TrialOutcome.FAIL
    assert report_missing.trials[0].score == 0.0


def test_domain_full_protocol():
    """
    Validates all properties and methods required by Directive Section 17 on Domain.
    """
    domain = SClassStandardCodingDomain()
    assert len(domain.evolve_set) == 10
    assert len(domain.heldout_set) == 10
    assert len(domain.smoke_set) == 2
    assert "assert False" in domain.critic_patterns
    assert "prompt" in domain.component_signals
    assert "min_pass_rate" in domain.guards
    assert "domain_summary" in domain.briefs

    run_res = domain.run("task_evolve_1", None)
    assert run_res["status"] == "COMPLETED"
    assert domain.score("task_evolve_1", {"passed": True}) == 1.0
    assert domain.score("task_evolve_1", {"passed": False}) == 0.0
    assert domain.smoke(None) is True
    trace_str = domain.render_trace({"status": "OK"})
    assert "status" in trace_str


def test_runtime_plan_task_system_isolation():
    """
    Validates Directive Section 12:
    The model can update runtime tasks, but RuntimeTask completion cannot
    satisfy canonical obligations.
    """
    plan = ExecutionPlanCandidate(plan_id="plan_1", session_id="sess_1", goal="Implement feature")
    task1 = plan.add_task(title="Refactor auth", description="Extract helper function")

    assert task1.status == RuntimeTaskStatus.PENDING
    task1.update_status(RuntimeTaskStatus.IN_PROGRESS)
    assert task1.status == RuntimeTaskStatus.IN_PROGRESS
    task1.update_status(RuntimeTaskStatus.COMPLETED)
    assert task1.status == RuntimeTaskStatus.COMPLETED

    # Enforces invariant: RuntimeTask cannot satisfy canonical technical obligation
    with pytest.raises(SecurityViolationError, match="cannot satisfy canonical obligation"):
        task1.assert_cannot_satisfy_canonical_obligation("ob_security_1")


def test_subsystem_migration_registry():
    """
    Validates Directive Section 41: Subsystem Migration Registry.
    """
    all_records = MigrationRegistry.get_all()
    assert len(all_records) >= 8

    active_records = MigrationRegistry.get_by_status(MigrationStatus.ACTIVE)
    assert any(r.subsystem_id == "stepcode_provider" for r in active_records)
    assert any(r.subsystem_id == "evolution_engine" for r in active_records)
    assert any(r.subsystem_id == "effect_boundary" for r in active_records)

    dead_records = MigrationRegistry.get_by_status(MigrationStatus.DEAD)
    assert any(r.subsystem_id == "unverified_agent_proposals" for r in dead_records)

    stepcode_rec = MigrationRegistry.get("stepcode_provider")
    assert stepcode_rec is not None
    assert stepcode_rec.status == MigrationStatus.ACTIVE


def test_evolution_module_aliasing():
    """
    Validates Directive Section 16 & Section 40:
    sclass.evolution.controller and sclass.evolution.evaluation resolve and alias correctly.
    """
    from sclass.evolution.controller import EvolutionController, EvolutionEngine as EE
    from sclass.evolution.evaluation import CandidateEvaluator as CE, TrialOutcome as TO

    assert EvolutionController is EE
    assert CE is CandidateEvaluator
    assert TO is TrialOutcome
