import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from strategy import StrategyEngine, RiskLevel, Urgency, ProjectScale
from verifier import EvidenceVerifier, VerificationError
from evaluation import SelfEvaluator, EvaluationAction
import runtime


def test_strategy_engine_hotfix():
    strat = StrategyEngine.infer_strategy("Emergency hotfix for auth crash")
    assert strat.urgency == Urgency.EMERGENCY
    assert strat.recommended_profile.value == "hotfix"
    assert strat.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]


def test_strategy_engine_bug_fix():
    strat = StrategyEngine.infer_strategy("Fix typo in error message")
    assert strat.urgency == Urgency.LOW
    assert strat.recommended_profile.value == "bug_fix"


def test_strategy_engine_research():
    strat = StrategyEngine.infer_strategy("Audit and research database schema")
    assert strat.recommended_profile.value == "research"


def test_domain_classification_and_capability_matching():
    # Prompt 1: UI Alignment -> UI + Frontend domains only
    strat_ui = StrategyEngine.infer_strategy("Fix navbar alignment and button color")
    assert "ui" in strat_ui.detected_domains
    assert "frontend" in strat_ui.detected_domains
    assert "database" not in strat_ui.detected_domains
    assert "dss_ui_ux" in strat_ui.debate_panel
    assert "dss_db_architect" not in strat_ui.debate_panel

    # Prompt 2: Database Migration -> DB + Backend domains only
    strat_db = StrategyEngine.infer_strategy("Add a new column to Users table in PostgreSQL")
    assert "database" in strat_db.detected_domains
    assert "dss_db_architect" in strat_db.debate_panel
    assert "dss_ui_ux" not in strat_db.debate_panel

    # Prompt 3: Stripe Billing -> Security + Backend + Database domains
    strat_stripe = StrategyEngine.infer_strategy("Implement Stripe subscription billing with JWT auth")
    assert "security" in strat_stripe.detected_domains
    assert "dss_cso_v2" in strat_stripe.debate_panel
    assert "dss_db_architect" in strat_stripe.debate_panel


def test_evidence_verifier_triage(tmp_path):
    workspace = str(tmp_path)
    
    # Before init -> verification fails if allow_soft is False
    res = EvidenceVerifier.verify_phase("TRIAGE", workspace_dir=workspace, allow_soft=False)
    assert res.passed is False
    assert len(res.errors) > 0
    
    # After init -> verification passes
    runtime.initialize_state(workspace_dir=workspace)
    res = EvidenceVerifier.verify_phase("TRIAGE", workspace_dir=workspace, allow_soft=False)
    assert res.passed is True


def test_self_evaluator_proceed():
    eval_res = SelfEvaluator.evaluate_phase("CODING", confidence_score=0.95)
    assert eval_res.action == EvaluationAction.PROCEED


def test_self_evaluator_low_confidence():
    eval_res = SelfEvaluator.evaluate_phase("DESIGN", confidence_score=0.3)
    assert eval_res.action == EvaluationAction.CLARIFY
    assert "clarification" in eval_res.reason.lower()


def test_self_evaluator_retry_exhausted():
    eval_res = SelfEvaluator.evaluate_phase("QA", retry_count=3, max_retries=3)
    assert eval_res.action == EvaluationAction.RECOVER


def test_self_evaluator_profile_pivot():
    eval_res = SelfEvaluator.evaluate_phase(
        "ANALYSIS",
        goal_text="Bug fix that turned into a major refactor and rewrite of auth",
        current_profile="bug_fix"
    )
    assert eval_res.action == EvaluationAction.PIVOT_PROFILE
    assert eval_res.suggested_profile == "full"
