import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from strategy import (
    StrategyEngine, RiskLevel, Urgency, ProjectScale, TierEnforcement,
    classify_defect_tier, get_enforcement_level, check_accumulation_threshold,
    ImpactDrivenPolicyEngine, ImpactAnalysis, EvidenceSource, ImpactVectorEvaluation,
    RiskReport, RiskEngine, PolicyEngine, SafetyCase
)
from verifier import EvidenceVerifier, VerificationError, UxDebtTracker
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


def test_impact_driven_policy_engine():
    # 1. Principle 1: Hard Invariant Check (Short-Circuit Gate)
    v_inv = ImpactDrivenPolicyEngine.evaluate_defect(
        defect_description="JWT authentication bypass on backend endpoint",
        defect_domain="auth",
        is_auth_security=True,
        is_pure_cosmetic=True  # Cosmetic flag MUST NOT override security invariant!
    )
    assert v_inv.invariant_triggered is True
    assert v_inv.risk_score == 10.0
    assert v_inv.policy_enforcement == "HARD_BLOCK"
    assert v_inv.decision == "REJECT_RELEASE"
    assert "CRITICAL: Security/Auth Bypass Invariant" in v_inv.top_contributors[0]

    # 2. Principle 2 & 3: Multiplicative Risk Interaction & Conditional Cosmetic Discount
    # When functional vectors are active, cosmetic discount is strictly 0.0, and multipliers amplify.
    # Uses PLAYWRIGHT_VISUAL source (0.98 conf) with workflow_blocking=0.5 (eff=0.49) & data_loss_risk=0.5 (eff=0.49) to trigger 1.4x multiplier.
    v_mult = ImpactDrivenPolicyEngine.evaluate_defect(
        defect_description="Checkout form workflow blocked and form state unsaved",
        defect_domain="input_output_form_flow",
        evidence_source=EvidenceSource.PLAYWRIGHT_VISUAL,
        impact_override=ImpactAnalysis(workflow_blocking=0.5, data_loss_risk=0.5)
    )
    # base = (0.49*3.5 + 0.49*4.0) = 3.67; multiplier = 1.4x -> 5.14
    assert v_mult.risk_score == 5.14
    assert "Multiplicative Interaction: Workflow x Data Loss (1.4x)" in v_mult.top_contributors

    # 3. Principle 3: Pure Cosmetic Discount (Applies ONLY when functional vectors = 0)
    v_cosmetic = ImpactDrivenPolicyEngine.evaluate_defect(
        defect_description="Slight margin misalignment on avatar card",
        defect_domain="margin_alignment",
        is_pure_cosmetic=True
    )
    assert v_cosmetic.risk_score == 0.0
    assert v_cosmetic.policy_enforcement == "SOFT_PASS"
    assert v_cosmetic.decision == "ALLOW_RELEASE"

    # 4. Principle 4: Time & Frequency Dimension Scaling (Likelihood)
    # Evaluates frequency scaling on moderate risk vectors (data_loss_risk=0.5 * 0.98 conf = 0.49 * 4.0 = 1.96 * x0.10 = 0.20)
    v_rare = ImpactDrivenPolicyEngine.evaluate_defect(
        defect_description="Rare edge case data sync mismatch on slow retry",
        defect_domain="input_output_form_flow",
        evidence_source=EvidenceSource.PLAYWRIGHT_VISUAL,
        impact_override=ImpactAnalysis(data_loss_risk=0.5, frequency_likelihood=0.10)
    )
    # base = (0.49 * 4.0) = 1.96; scale = x0.10 -> final_risk = 0.20 -> SOFT_PASS
    assert v_rare.risk_score == 0.20
    assert v_rare.policy_enforcement == "SOFT_PASS"

    # 5. Principle 5 & 6: Confidence Metrics & Explainability (Top Contributors)
    v_explain = ImpactDrivenPolicyEngine.evaluate_defect(
        defect_description="Missing error message toast on failed registration",
        defect_domain="input_output_form_flow",
        evidence_source=EvidenceSource.PLAYWRIGHT_VISUAL,
        evidence_list=["playwright_visual_receipt", "console_log"]
    )
    assert v_explain.confidence == 0.98
    assert len(v_explain.top_contributors) > 0

    # 6. Principle 7: Configurable Environment Risk Thresholds (Medical = 3.5 vs Prototype = 9.0)
    v_med = ImpactDrivenPolicyEngine.evaluate_defect(
        defect_description="Form submission delay",
        defect_domain="input_output_form_flow",
        evidence_source=EvidenceSource.PLAYWRIGHT_VISUAL,
        impact_override=ImpactAnalysis(data_loss_risk=0.90), # eff = 0.90*0.98 = 0.882 * 4.0 = 3.53
        threshold_hard_block=3.5  # Strict Medical Profile
    )
    assert v_med.policy_enforcement == "HARD_BLOCK"  # 3.53 >= 3.5


def test_decoupled_risk_and_policy_engine_and_safety_case():
    # 1. Test Evidence-Weighted RiskEngine (Playwright Visual = 0.98 confidence vs LLM Review = 0.50 confidence)
    # Evaluates severity=0.80 (below 0.95 invariant threshold) to test evidence confidence weighting
    report_playwright = RiskEngine.compute_risk(
        defect_description="Submit button unreachable",
        defect_domain="button_reachability",
        evidence_source=EvidenceSource.PLAYWRIGHT_VISUAL,
        vector_overrides={"workflow_blocking": ImpactVectorEvaluation(severity=0.80, confidence=0.98, source=EvidenceSource.PLAYWRIGHT_VISUAL)}
    )
    assert report_playwright.overall_confidence == 0.98

    report_llm = RiskEngine.compute_risk(
        defect_description="Submit button unreachable",
        defect_domain="button_reachability",
        evidence_source=EvidenceSource.LLM_REVIEW,
        vector_overrides={"workflow_blocking": ImpactVectorEvaluation(severity=0.80, confidence=0.50, source=EvidenceSource.LLM_REVIEW)}
    )
    assert report_llm.overall_confidence == 0.50
    # Higher confidence source yields higher effective risk impact (2.74 vs 1.40)
    assert report_playwright.risk_score > report_llm.risk_score

    # 2. Test Mandatory Safety Case Visual Gate in PolicyEngine
    incomplete_safety_case = SafetyCase(
        build_passed=True,
        tests_passed=True,
        security_clean=True,
        visual_inspection_passed=False  # Missing visual output receipt!
    )
    verdict_incomplete = PolicyEngine.evaluate_policy(
        defect_description="Minor alignment tweak",
        risk_report=RiskReport(risk_score=1.0, overall_confidence=0.98, hard_invariant_triggered=False, top_contributors=[], vector_evaluations={}),
        safety_case=incomplete_safety_case
    )
    assert verdict_incomplete.policy_enforcement == "HARD_BLOCK"
    assert verdict_incomplete.decision == "REJECT_RELEASE"
    assert "SAFETY CASE INCOMPLETE" in verdict_incomplete.rationale

    # Complete Safety Case allows release for low risk
    complete_safety_case = SafetyCase(
        build_passed=True,
        tests_passed=True,
        security_clean=True,
        visual_inspection_passed=True  # Visual output verified!
    )
    verdict_complete = PolicyEngine.evaluate_policy(
        defect_description="Minor alignment tweak",
        risk_report=RiskReport(risk_score=1.0, overall_confidence=0.98, hard_invariant_triggered=False, top_contributors=[], vector_evaluations={}),
        safety_case=complete_safety_case
    )
    assert verdict_complete.policy_enforcement == "SOFT_PASS"
    assert verdict_complete.decision == "ALLOW_RELEASE"



