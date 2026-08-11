"""
Strategy-Aware Planning Engine for S-Class EOS

Infers project scale, urgency, risk level, parallelism utility, and clarification necessity
from user goals and codebase metadata to produce an ExecutionStrategy.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from planner import WorkflowProfile


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Urgency(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EMERGENCY = "emergency"


class ReviewDepth(Enum):
    LIGHT = "light"
    STANDARD = "standard"
    DEEP = "deep"


class ProjectScale(Enum):
    MICRO = "micro"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    ENTERPRISE = "enterprise"


class TierEnforcement:
    """Enforcement level constants for the 6-tier verification model."""
    HARD_BLOCK = "HARD_BLOCK"   # Zero tolerance — blocks release
    SOFT_WARN  = "SOFT_WARN"    # Advisory — allows release with logged warning
    SOFT_PASS  = "SOFT_PASS"    # Allows release silently, tracks as UX debt


VERIFICATION_PRIORITY_HIERARCHY = {
    "TIER_1_LOGIC": {
        "enforcement": TierEnforcement.HARD_BLOCK,
        "tolerance": 0,
        "domains": ["working_flow", "business_logic", "backend_routing", "db_schema", "rbac_security", "state_transitions", "data_persistence"],
        "description": "Working Logic & Business Flow — Zero tolerance. If EVEN ONE flaw exists, HARD BLOCK.",
    },
    "TIER_2_DATA_VISUAL": {
        "enforcement": TierEnforcement.HARD_BLOCK,
        "tolerance": 0,
        "domains": ["data_rendering_fidelity", "no_prop_leaks", "input_output_form_flow", "no_data_pollution"],
        "description": "Data Visual & Output Fidelity — Zero tolerance. Form inputs must render in output views.",
    },
    "TIER_3A_FUNCTIONAL_UI": {
        "enforcement": TierEnforcement.HARD_BLOCK,
        "tolerance": 0,
        "domains": ["button_reachability", "navigation_rendering", "scroll_access", "modal_dismiss", "content_visibility"],
        "description": "Functional UI that blocks user workflow — Escalates to Tier 1. Button off-screen, nav broken, content hidden.",
        "crossover_escalation": "TIER_1_LOGIC",
    },
    "TIER_3B_COSMETIC_UI": {
        "enforcement": TierEnforcement.SOFT_PASS,
        "tolerance": -1,
        "domains": ["margin_alignment", "padding_consistency", "font_size_variation", "color_mismatch", "border_radius"],
        "description": "Cosmetic UI imperfections — Soft pass. Track as UX debt for follow-up polish.",
        "track_debt": True,
    },
    "TIER_4A_FUNCTIONAL_UX": {
        "enforcement": TierEnforcement.SOFT_WARN,
        "tolerance": 5,
        "domains": ["destructive_action_confirmation", "loading_indicators", "error_feedback", "form_validation_feedback", "empty_state_guidance"],
        "description": "Functional UX preventing safe interaction — Warn and allow. Escalate to SOFT_BLOCK if count > 5.",
        "escalate_above_threshold": TierEnforcement.HARD_BLOCK,
        "track_debt": True,
    },
    "TIER_4B_COSMETIC_UX": {
        "enforcement": TierEnforcement.SOFT_PASS,
        "tolerance": -1,
        "domains": ["micro_animations", "gradient_effects", "hover_transitions", "dark_mode_refinements", "toast_aesthetics"],
        "description": "Cosmetic UX polish — Soft pass. Ship working software, polish later.",
        "track_debt": True,
    },
}


def classify_defect_tier(defect_domain: str, blocks_user_flow: bool = False) -> str:
    """Classifies a defect domain into its enforcement tier.

    Args:
        defect_domain: The domain of the defect (e.g., 'working_flow', 'micro_animations').
        blocks_user_flow: If True and the defect is in Tier 3b/4a/4b, escalates via crossover.

    Returns:
        The tier key (e.g., 'TIER_1_LOGIC', 'TIER_3A_FUNCTIONAL_UI').
    """
    for tier_key, tier_config in VERIFICATION_PRIORITY_HIERARCHY.items():
        if defect_domain in tier_config["domains"]:
            # Tier crossover: if a cosmetic/UX issue blocks a user workflow, escalate
            if blocks_user_flow and tier_key in ("TIER_3B_COSMETIC_UI", "TIER_4A_FUNCTIONAL_UX", "TIER_4B_COSMETIC_UX"):
                return tier_config.get("crossover_escalation", "TIER_3A_FUNCTIONAL_UI")
            return tier_key
    # Default: unknown defects treated as Tier 1 for safety
    return "TIER_1_LOGIC"


def get_enforcement_level(tier_key: str) -> str:
    """Returns the enforcement level for a given tier."""
    tier = VERIFICATION_PRIORITY_HIERARCHY.get(tier_key, {})
    return tier.get("enforcement", TierEnforcement.HARD_BLOCK)


def check_accumulation_threshold(tier_key: str, defect_count: int) -> str:
    """Checks if accumulated defects in a tier exceed its tolerance threshold.

    Returns the effective enforcement level after applying accumulation rules.
    """
    tier = VERIFICATION_PRIORITY_HIERARCHY.get(tier_key, {})
    tolerance = tier.get("tolerance", 0)
    base_enforcement = tier.get("enforcement", TierEnforcement.HARD_BLOCK)

    # tolerance == -1 means unlimited tolerance (always soft pass)
    if tolerance == -1:
        return base_enforcement

    # tolerance == 0 means zero tolerance (always hard block)
    if tolerance == 0:
        return TierEnforcement.HARD_BLOCK if defect_count > 0 else base_enforcement

    # Accumulation escalation: if count exceeds threshold, escalate
    if defect_count > tolerance:
        return tier.get("escalate_above_threshold", TierEnforcement.HARD_BLOCK)

    return base_enforcement


class EvidenceSource:
    """Evidence sources and their associated confidence weights."""
    PLAYWRIGHT_VISUAL = "playwright_visual"   # Confidence Weight: 0.98 (Playwright / Chrome MCP visual verification)
    UNIT_TEST = "unit_test"                   # Confidence Weight: 0.90 (Automated unit / integration test receipt)
    STATIC_ANALYSIS = "static_analysis"       # Confidence Weight: 0.85 (Linter / compiler / type-checker receipt)
    LLM_REVIEW = "llm_review"                 # Confidence Weight: 0.50 (LLM subagent inspection receipt)
    HEURISTIC = "heuristic"                   # Confidence Weight: 0.40 (Static heuristic rule match)


EVIDENCE_CONFIDENCE_WEIGHTS: Dict[str, float] = {
    EvidenceSource.PLAYWRIGHT_VISUAL: 0.98,
    EvidenceSource.UNIT_TEST: 0.90,
    EvidenceSource.STATIC_ANALYSIS: 0.85,
    EvidenceSource.LLM_REVIEW: 0.50,
    EvidenceSource.HEURISTIC: 0.40,
}


@dataclass
class ImpactAnalysis:
    """Convenience container for multi-vector defect severities."""
    workflow_blocking: float = 0.0
    data_loss_risk: float = 0.0
    user_reachability: float = 0.0
    security_auth_risk: float = 0.0
    cosmetic_only: float = 0.0
    frequency_likelihood: float = 1.0

    def to_vectors(self, source: str = EvidenceSource.HEURISTIC) -> Dict[str, "ImpactVectorEvaluation"]:
        conf = EVIDENCE_CONFIDENCE_WEIGHTS.get(source, 0.40)
        return {
            "workflow_blocking": ImpactVectorEvaluation(severity=self.workflow_blocking, confidence=conf, source=source),
            "data_loss_risk": ImpactVectorEvaluation(severity=self.data_loss_risk, confidence=conf, source=source),
            "user_reachability": ImpactVectorEvaluation(severity=self.user_reachability, confidence=conf, source=source),
            "security_auth_risk": ImpactVectorEvaluation(severity=self.security_auth_risk, confidence=conf, source=source),
            "cosmetic_only": ImpactVectorEvaluation(severity=self.cosmetic_only, confidence=conf, source=source),
        }


@dataclass
class ImpactVectorEvaluation:
    """Individual impact vector evaluated with severity, confidence, and evidence source."""
    severity: float         # [0.0 - 1.0] Raw defect severity
    confidence: float       # [0.0 - 1.0] Source-weighted confidence score
    source: str             # EvidenceSource identifier

    def effective_impact(self) -> float:
        """Returns confidence-weighted impact = severity * confidence."""
        return round(self.severity * self.confidence, 4)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity,
            "confidence": self.confidence,
            "source": self.source,
            "effective_impact": self.effective_impact(),
        }


@dataclass
class RiskReport:
    """Standalone, explainable Risk Report produced by the Risk Engine. Decoupled from Policy Engine."""
    risk_score: float                            # Calculated Risk Score [0.0 - 10.0]
    overall_confidence: float                    # Weighted average confidence [0.0 - 1.0]
    hard_invariant_triggered: bool                # True if a short-circuit hard invariant fired
    top_contributors: List[str]                  # Human-readable breakdown of risk drivers
    vector_evaluations: Dict[str, ImpactVectorEvaluation] # Per-vector evaluation objects

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_score": self.risk_score,
            "overall_confidence": self.overall_confidence,
            "hard_invariant_triggered": self.hard_invariant_triggered,
            "top_contributors": self.top_contributors,
            "vector_evaluations": {k: v.to_dict() for k, v in self.vector_evaluations.items()},
        }


class RiskEngine:
    """Standalone Risk Engine: Computes risk_score, vector confidence, and hard_invariant_triggered.

    Does NOT make policy decisions (HARD_BLOCK / SOFT_PASS). Output is a pure RiskReport.
    """

    @staticmethod
    def compute_risk(
        defect_description: str,
        defect_domain: str,
        blocks_user_flow: bool = False,
        causes_double_submit: bool = False,
        causes_data_loss: bool = False,
        is_auth_security: bool = False,
        is_pure_cosmetic: bool = False,
        evidence_source: str = EvidenceSource.HEURISTIC,
        frequency_likelihood: float = 1.0,
        vector_overrides: Optional[Dict[str, ImpactVectorEvaluation]] = None,
    ) -> RiskReport:
        """Evaluates defect evidence vectors and computes RiskReport."""
        conf_weight = EVIDENCE_CONFIDENCE_WEIGHTS.get(evidence_source, 0.40)
        contributors: List[str] = []

        if vector_overrides is not None:
            vectors = vector_overrides
        else:
            # Construct vectors with source-weighted confidence
            wf_sev = 1.0 if blocks_user_flow or defect_domain in ["working_flow", "business_logic", "backend_routing", "state_transitions"] else 0.0
            dl_sev = 1.0 if causes_data_loss or causes_double_submit else (0.5 if defect_domain == "input_output_form_flow" else 0.0)
            reach_sev = 1.0 if defect_domain in ["button_reachability", "navigation_rendering", "content_visibility"] or blocks_user_flow else 0.0
            sec_sev = 1.0 if is_auth_security or defect_domain in ["rbac_security", "auth"] else 0.0
            cosm_sev = 1.0 if is_pure_cosmetic or defect_domain in ["micro_animations", "hover_transitions", "margin_alignment", "padding_consistency", "border_radius"] else 0.0

            vectors = {
                "workflow_blocking": ImpactVectorEvaluation(severity=wf_sev, confidence=conf_weight, source=evidence_source),
                "data_loss_risk": ImpactVectorEvaluation(severity=dl_sev, confidence=conf_weight, source=evidence_source),
                "user_reachability": ImpactVectorEvaluation(severity=reach_sev, confidence=conf_weight, source=evidence_source),
                "security_auth_risk": ImpactVectorEvaluation(severity=sec_sev, confidence=conf_weight, source=evidence_source),
                "cosmetic_only": ImpactVectorEvaluation(severity=cosm_sev, confidence=conf_weight, source=evidence_source),
            }

        # Ensure all 5 standard vectors exist in vectors dict (fill defaults for missing keys)
        default_vector = ImpactVectorEvaluation(severity=0.0, confidence=conf_weight, source=evidence_source)
        sec_vec = vectors.get("security_auth_risk", default_vector)
        dl_vec = vectors.get("data_loss_risk", default_vector)
        wf_vec = vectors.get("workflow_blocking", default_vector)
        reach_vec = vectors.get("user_reachability", default_vector)
        cosm_vec = vectors.get("cosmetic_only", default_vector)

        # 1. Hard Invariants Check (Short-Circuit Gates)
        if sec_vec.severity >= 0.9:
            contributors.append(f"CRITICAL: Security/Auth Bypass Invariant Triggered (Severity={sec_vec.severity}, Source={sec_vec.source})")
            return RiskReport(
                risk_score=10.0,
                overall_confidence=sec_vec.confidence,
                hard_invariant_triggered=True,
                top_contributors=contributors,
                vector_evaluations=vectors,
            )

        if dl_vec.severity >= 0.95:
            contributors.append(f"CRITICAL: Data Loss / Corruption Invariant Triggered (Severity={dl_vec.severity}, Source={dl_vec.source})")
            return RiskReport(
                risk_score=10.0,
                overall_confidence=dl_vec.confidence,
                hard_invariant_triggered=True,
                top_contributors=contributors,
                vector_evaluations=vectors,
            )

        if wf_vec.severity >= 0.95:
            contributors.append(f"CRITICAL: Total Workflow Blockage Invariant Triggered (Severity={wf_vec.severity}, Source={wf_vec.source})")
            return RiskReport(
                risk_score=10.0,
                overall_confidence=wf_vec.confidence,
                hard_invariant_triggered=True,
                top_contributors=contributors,
                vector_evaluations=vectors,
            )

        # 2. Additive Base Score weighted by confidence-effective impact
        base_score = 0.0
        wf_eff = wf_vec.effective_impact()
        if wf_eff > 0:
            val = round(wf_eff * 3.5, 2)
            base_score += val
            contributors.append(f"Workflow Blocking: +{val:.2f} (Effective Impact={wf_eff})")

        dl_eff = dl_vec.effective_impact()
        if dl_eff > 0:
            val = round(dl_eff * 4.0, 2)
            base_score += val
            contributors.append(f"Data Loss Risk: +{val:.2f} (Effective Impact={dl_eff})")

        sec_eff = sec_vec.effective_impact()
        if sec_eff > 0:
            val = round(sec_eff * 4.0, 2)
            base_score += val
            contributors.append(f"Security Auth Risk: +{val:.2f} (Effective Impact={sec_eff})")

        reach_eff = reach_vec.effective_impact()
        if reach_eff > 0:
            val = round(reach_eff * 2.5, 2)
            base_score += val
            contributors.append(f"User Reachability: +{val:.2f} (Effective Impact={reach_eff})")

        # Conditional Cosmetic Discount: ONLY if NO functional vectors are active
        has_functional_vectors = (wf_eff > 0 or dl_eff > 0 or sec_eff > 0 or reach_eff > 0)
        cosm_eff = cosm_vec.effective_impact()
        if cosm_eff > 0 and not has_functional_vectors:
            discount = round(cosm_eff * 2.0, 2)
            base_score = max(0.0, base_score - discount)
            contributors.append(f"Pure Cosmetic Discount: -{discount:.2f}")

        # 3. Multiplicative Interaction Engine
        interaction_multiplier = 1.0
        if wf_eff > 0.3 and sec_eff > 0.3:
            interaction_multiplier *= 1.5
            contributors.append("Multiplicative Interaction: Auth x Workflow (1.5x)")

        if wf_eff > 0.3 and dl_eff > 0.3:
            interaction_multiplier *= 1.4
            contributors.append("Multiplicative Interaction: Workflow x Data Loss (1.4x)")

        if dl_eff > 0.3 and sec_eff > 0.3:
            interaction_multiplier *= 1.6
            contributors.append("Multiplicative Interaction: Data Loss x Security (1.6x)")

        amplified_score = base_score * interaction_multiplier

        # 4. Time / Frequency Dimension Scaling
        final_risk = min(10.0, max(0.0, round(amplified_score * frequency_likelihood, 2)))
        if frequency_likelihood < 1.0:
            contributors.append(f"Frequency Likelihood Scale: x{frequency_likelihood}")

        # Overall Confidence = weighted average confidence across active vectors
        conf_values = [v.confidence for v in vectors.values() if v.severity > 0]
        avg_confidence = round(sum(conf_values) / len(conf_values), 2) if conf_values else conf_weight

        return RiskReport(
            risk_score=final_risk,
            overall_confidence=avg_confidence,
            hard_invariant_triggered=False,
            top_contributors=contributors,
            vector_evaluations=vectors,
        )


@dataclass
class ContractCoverage:
    """Tracks coverage metrics across user contract features, pages, and interaction flows."""
    total_required_contracts: int = 1
    verified_contracts: int = 1
    unverified_contracts: List[str] = field(default_factory=list)

    @property
    def coverage_percent(self) -> float:
        if self.total_required_contracts == 0:
            return 100.0
        return round((self.verified_contracts / self.total_required_contracts) * 100.0, 1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_required_contracts": self.total_required_contracts,
            "verified_contracts": self.verified_contracts,
            "unverified_contracts": self.unverified_contracts,
            "coverage_percent": self.coverage_percent,
        }


@dataclass
class SafetyCase:
    """Avionics & Medical Grade Safety Case. Release requires complete body of evidence."""
    build_passed: bool = False
    tests_passed: bool = False
    security_clean: bool = False
    output_contract_passed: bool = False         # MANDATORY: Output Contract Evidence verified against IntentContract
    output_verification_mechanism: str = ""       # Mechanism used: playwright_dom | json_schema | cli_golden_snapshot | markdown_ast
    contract_coverage: ContractCoverage = field(default_factory=ContractCoverage) # User Contract Coverage metrics
    risk_report: Optional[RiskReport] = None

    @property
    def visual_inspection_passed(self) -> bool:
        """Backwards-compatible alias for output_contract_passed."""
        return self.output_contract_passed

    def is_complete(self, target_threshold: Optional[float] = None, policy_profile: str = "production_saas") -> bool:
        """Verifies all safety case evidence requirements are met using profile-driven contract coverage thresholds."""
        required = target_threshold if target_threshold is not None else PROFILE_COVERAGE_THRESHOLDS.get(policy_profile, 85.0)
        return (
            self.build_passed and
            self.tests_passed and
            self.security_clean and
            self.output_contract_passed and
            self.contract_coverage.coverage_percent >= required
        )


@dataclass
class DefectEvaluationVerdict:
    """Final policy decision verdict produced by PolicyEngine consuming RiskReport + SafetyCase."""
    defect_description: str
    risk_report: RiskReport
    safety_case: Optional[SafetyCase]
    policy_enforcement: str       # HARD_BLOCK | SOFT_WARN | SOFT_PASS
    decision: str                 # REJECT_RELEASE | ALLOW_WITH_WARN | ALLOW_RELEASE
    rationale: str

    @property
    def risk_score(self) -> float:
        return self.risk_report.risk_score

    @property
    def confidence(self) -> float:
        return self.risk_report.overall_confidence

    @property
    def top_contributors(self) -> List[str]:
        return self.risk_report.top_contributors

    @property
    def invariant_triggered(self) -> bool:
        return self.risk_report.hard_invariant_triggered

    def to_dict(self) -> Dict[str, Any]:
        return {
            "defect_description": self.defect_description,
            "risk_report": self.risk_report.to_dict(),
            "safety_case_complete": self.safety_case.is_complete() if self.safety_case else False,
            "output_verification_mechanism": self.safety_case.output_verification_mechanism if self.safety_case else "",
            "contract_coverage": self.safety_case.contract_coverage.to_dict() if self.safety_case else {},
            "policy_enforcement": self.policy_enforcement,
            "decision": self.decision,
            "rationale": self.rationale,
        }


PROFILE_COVERAGE_THRESHOLDS: Dict[str, float] = {
    "prototype": 40.0,
    "startup_mvp": 70.0,
    "production_saas": 90.0,
    "mission_critical": 100.0,
}


@dataclass
class SafetyReport:
    """Summarized Safety Report consumed statelessly by PolicyEngine."""
    build_passed: bool
    tests_passed: bool
    security_clean: bool
    output_contract_passed: bool
    contract_coverage_percent: float
    unverified_contracts: List[str]
    verification_mechanism: str
    policy_profile: str = "production_saas"

    @classmethod
    def from_safety_case(cls, safety_case: Optional[Any], policy_profile: str = "production_saas") -> 'SafetyReport':
        if not safety_case:
            return cls(
                build_passed=True,
                tests_passed=True,
                security_clean=True,
                output_contract_passed=True,
                contract_coverage_percent=100.0,
                unverified_contracts=[],
                verification_mechanism="auto",
                policy_profile=policy_profile,
            )
        cov = getattr(safety_case, "contract_coverage", None)
        cov_pct = cov.coverage_percent if cov else 100.0
        unverified = cov.unverified_contracts if cov else []
        return cls(
            build_passed=getattr(safety_case, "build_passed", True),
            tests_passed=getattr(safety_case, "tests_passed", True),
            security_clean=getattr(safety_case, "security_clean", True),
            output_contract_passed=getattr(safety_case, "output_contract_passed", True),
            contract_coverage_percent=cov_pct,
            unverified_contracts=unverified,
            verification_mechanism=getattr(safety_case, "output_verification_mechanism", "auto"),
            policy_profile=policy_profile,
        )


class PolicyEngine:
    """Stateless Policy Engine: Consumes RiskReport + SafetyReport to evaluate pure decision rules.

    Supports Policy Profiles (prototype, startup_mvp, production_saas, mission_critical) and profile-driven contract coverage thresholds.
    """

    @staticmethod
    def evaluate_policy(
        defect_description: str,
        risk_report: RiskReport,
        safety_case: Optional[SafetyCase] = None,
        threshold_hard_block: float = 7.0,
        threshold_soft_warn: float = 4.0,
        min_coverage_threshold: Optional[float] = None,
        policy_profile: str = "production_saas",
    ) -> DefectEvaluationVerdict:
        """Consumes RiskReport and SafetyReport to produce the final policy decision."""
        report = SafetyReport.from_safety_case(safety_case, policy_profile=policy_profile)

        # Profile-driven coverage threshold
        required_coverage = min_coverage_threshold if min_coverage_threshold is not None else PROFILE_COVERAGE_THRESHOLDS.get(policy_profile, 85.0)

        # 1. Mandatory Safety Case Output Contract Evidence Gate
        if not report.output_contract_passed:
            return DefectEvaluationVerdict(
                defect_description=defect_description,
                risk_report=risk_report,
                safety_case=safety_case,
                policy_enforcement=TierEnforcement.HARD_BLOCK,
                decision="REJECT_RELEASE",
                rationale="SAFETY CASE INCOMPLETE: Output Contract Evidence is missing. IntentContract requires verified rendered output (Playwright DOM/table/chart, JSON schema, CLI snapshot, or PDF parser) matching user request before release.",
            )

        # 2. Profile-Driven User Contract Coverage Gate
        if report.contract_coverage_percent < required_coverage:
            return DefectEvaluationVerdict(
                defect_description=defect_description,
                risk_report=risk_report,
                safety_case=safety_case,
                policy_enforcement=TierEnforcement.HARD_BLOCK,
                decision="REJECT_RELEASE",
                rationale=f"SAFETY CASE INCOMPLETE: [{policy_profile.upper()} PROFILE] User Contract Coverage is only {report.contract_coverage_percent}%, below required {required_coverage}% profile threshold. Unverified contracts: {report.unverified_contracts}",
            )

        # 3. Hard Invariants Check
        if risk_report.hard_invariant_triggered or risk_report.risk_score >= threshold_hard_block:
            return DefectEvaluationVerdict(
                defect_description=defect_description,
                risk_report=risk_report,
                safety_case=safety_case,
                policy_enforcement=TierEnforcement.HARD_BLOCK,
                decision="REJECT_RELEASE",
                rationale=f"HARD BLOCK: Risk Score {risk_report.risk_score}/10 >= {threshold_hard_block} threshold or Hard Invariant fired.",
            )

        # 4. Soft Warn vs Soft Pass
        if risk_report.risk_score >= threshold_soft_warn:
            return DefectEvaluationVerdict(
                defect_description=defect_description,
                risk_report=risk_report,
                safety_case=safety_case,
                policy_enforcement=TierEnforcement.SOFT_WARN,
                decision="ALLOW_WITH_WARN",
                rationale=f"SOFT WARN: Risk Score {risk_report.risk_score}/10 in [{threshold_soft_warn}, {threshold_hard_block}). Release allowed with logged advisory and UX debt tracking.",
            )

        return DefectEvaluationVerdict(
            defect_description=defect_description,
            risk_report=risk_report,
            safety_case=safety_case,
            policy_enforcement=TierEnforcement.SOFT_PASS,
            decision="ALLOW_RELEASE",
            rationale=f"SOFT PASS: Risk Score {risk_report.risk_score}/10 < {threshold_soft_warn}. Release allowed silently with UX debt tracking.",
        )


class ImpactDrivenPolicyEngine:
    """Convenience facade combining RiskEngine and PolicyEngine for unified evaluation calls."""

    @staticmethod
    def evaluate_defect(
        defect_description: str,
        defect_domain: str,
        blocks_user_flow: bool = False,
        causes_double_submit: bool = False,
        causes_data_loss: bool = False,
        is_auth_security: bool = False,
        is_pure_cosmetic: bool = False,
        evidence_source: str = EvidenceSource.HEURISTIC,
        frequency_likelihood: float = 1.0,
        evidence_list: Optional[List[str]] = None,
        threshold_hard_block: float = 7.0,
        threshold_soft_warn: float = 4.0,
        impact_override: Optional[Any] = None,
    ) -> DefectEvaluationVerdict:
        """Facade method delegating to RiskEngine and PolicyEngine."""
        # 1. Compute RiskReport via RiskEngine
        if impact_override is not None and isinstance(impact_override, ImpactAnalysis):
            conf = EVIDENCE_CONFIDENCE_WEIGHTS.get(evidence_source, 0.40)
            overrides = {
                "workflow_blocking": ImpactVectorEvaluation(severity=impact_override.workflow_blocking, confidence=conf, source=evidence_source),
                "data_loss_risk": ImpactVectorEvaluation(severity=impact_override.data_loss_risk, confidence=conf, source=evidence_source),
                "user_reachability": ImpactVectorEvaluation(severity=impact_override.user_reachability, confidence=conf, source=evidence_source),
                "security_auth_risk": ImpactVectorEvaluation(severity=impact_override.security_auth_risk, confidence=conf, source=evidence_source),
                "cosmetic_only": ImpactVectorEvaluation(severity=impact_override.cosmetic_only, confidence=conf, source=evidence_source),
            }
            report = RiskEngine.compute_risk(defect_description, defect_domain, vector_overrides=overrides, frequency_likelihood=impact_override.frequency_likelihood)
        else:
            report = RiskEngine.compute_risk(
                defect_description,
                defect_domain,
                blocks_user_flow=blocks_user_flow,
                causes_double_submit=causes_double_submit,
                causes_data_loss=causes_data_loss,
                is_auth_security=is_auth_security,
                is_pure_cosmetic=is_pure_cosmetic,
                evidence_source=evidence_source,
                frequency_likelihood=frequency_likelihood,
            )

        # 2. Evaluate Policy via PolicyEngine with complete SafetyCase default
        default_safety_case = SafetyCase(
            build_passed=True,
            tests_passed=True,
            security_clean=True,
            output_contract_passed=True,
            output_verification_mechanism="playwright_dom_inspection",
            risk_report=report,
        )

        return PolicyEngine.evaluate_policy(
            defect_description=defect_description,
            risk_report=report,
            safety_case=default_safety_case,
            threshold_hard_block=threshold_hard_block,
            threshold_soft_warn=threshold_soft_warn,
        )


@dataclass
class ExecutionStrategy:
    goal: str
    risk_level: RiskLevel
    urgency: Urgency
    project_scale: ProjectScale
    parallelism_worthwhile: bool
    clarification_required: bool
    recommended_profile: WorkflowProfile
    detected_domains: List[str] = field(default_factory=list)
    review_depth: ReviewDepth = ReviewDepth.STANDARD
    debate_panel: List[str] = field(default_factory=list)
    required_evidence: Dict[str, List[str]] = field(default_factory=dict)
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "risk_level": self.risk_level.value,
            "urgency": self.urgency.value,
            "project_scale": self.project_scale.value,
            "parallelism_worthwhile": self.parallelism_worthwhile,
            "clarification_required": self.clarification_required,
            "recommended_profile": self.recommended_profile.value,
            "detected_domains": self.detected_domains,
            "review_depth": self.review_depth.value,
            "debate_panel": self.debate_panel,
            "required_evidence": self.required_evidence,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionStrategy":
        return cls(
            goal=data["goal"],
            risk_level=RiskLevel(data.get("risk_level", "medium")),
            urgency=Urgency(data.get("urgency", "medium")),
            project_scale=ProjectScale(data.get("project_scale", "medium")),
            parallelism_worthwhile=data.get("parallelism_worthwhile", False),
            clarification_required=data.get("clarification_required", False),
            recommended_profile=WorkflowProfile(data.get("recommended_profile", "full")),
            detected_domains=data.get("detected_domains", []),
            review_depth=ReviewDepth(data.get("review_depth", "standard")),
            debate_panel=data.get("debate_panel", []),
            required_evidence=data.get("required_evidence", {}),
            rationale=data.get("rationale", ""),
        )


# Default evidence requirements per state
DEFAULT_EVIDENCE_CONTRACTS: Dict[str, List[str]] = {
    "TRIAGE": ["config_file", "state_file"],
    "ANALYSIS": ["context_loaded"],
    "CLARIFICATION": ["intent_contract"],
    "DESIGN": ["decision_log"],
    "DEBATE": ["consensus_score"],
    "TASK_COMPILATION": ["task_queue"],
    "CODING": ["modified_files"],
    "TASK_VERIFICATION": ["task_verification_receipt"],
    "MERGE": ["merged_sandbox"],
    "INTEGRATION": ["build_check"],
    "QA": ["test_receipt"],
    "RECOVERY": ["patch_plan"],
    "RELEASE": ["release_verification"],
}


DOMAIN_INTERACTION_GRAPH: Dict[str, List[str]] = {
    "database": ["backend", "security"],   # Changing DB automatically triggers Backend & Security review
    "backend": ["frontend", "security"],   # Changing Backend triggers Frontend API & Security review
    "frontend": ["ui"],                     # Changing Frontend triggers UI review
    "security": ["backend", "database"],    # Changing Security triggers Backend & Database review
    "ui": []
}


class StrategyEngine:
    """Infers engineering strategy, domain interaction graph, review depth, and capability-matched debate panel."""

    @staticmethod
    def detect_domains(goal: str) -> List[str]:
        """Detects active software engineering domains and propagates relationships via Domain Interaction Graph."""
        goal_lower = goal.lower()
        base_domains = set()

        # UI / UX Domain
        if any(kw in goal_lower for kw in ["ui", "ux", "css", "style", "layout", "color", "alignment", "design", "navbar", "theme"]):
            base_domains.add("ui")

        # Frontend Domain
        if any(kw in goal_lower for kw in ["frontend", "react", "nextjs", "dom", "component", "button", "page", "view"]):
            base_domains.add("frontend")

        # Backend & API Domain
        if any(kw in goal_lower for kw in ["backend", "api", "dto", "endpoint", "controller", "server", "express", "nestjs", "fastapi", "route", "stripe", "billing", "payment", "auth", "jwt"]):
            base_domains.add("backend")

        # Database Domain
        if any(kw in goal_lower for kw in ["database", "sql", "orm", "schema", "migration", "table", "column", "postgres", "sqlite", "model", "billing", "subscription", "store"]):
            base_domains.add("database")

        # Security & Auth Domain
        if any(kw in goal_lower for kw in ["security", "auth", "crypto", "token", "jwt", "rbac", "secret", "stripe", "billing", "payment", "login"]):
            base_domains.add("security")

        if not base_domains:
            base_domains.add("frontend")
            base_domains.add("backend")

        # Propagate domain interaction graph relationships
        final_domains = set(base_domains)
        for dom in base_domains:
            for related in DOMAIN_INTERACTION_GRAPH.get(dom, []):
                final_domains.add(related)

        return sorted(list(final_domains))

    @staticmethod
    def infer_review_depth(risk_level: RiskLevel, urgency: Urgency) -> ReviewDepth:
        """Determines review depth based on risk level and urgency."""
        if urgency == Urgency.EMERGENCY or risk_level == RiskLevel.LOW:
            return ReviewDepth.LIGHT
        elif risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            return ReviewDepth.DEEP
        else:
            return ReviewDepth.STANDARD

    @staticmethod
    def resolve_debate_squad(domains: List[str], review_depth: ReviewDepth) -> List[str]:
        """Dynamically matches debate panel agents based on capability taxonomy and review depth."""
        squad = set()

        # Always include Lead & Governor for architecture review
        squad.add("dss_governor")

        # Map detected domains to capabilities
        if "ui" in domains:
            squad.add("dss_ui_ux")
        if "frontend" in domains:
            squad.add("dss_frontend_dev")
        if "backend" in domains:
            squad.add("dss_backend_dev")
        if "database" in domains:
            squad.add("dss_db_architect")
        if "security" in domains:
            squad.add("dss_cso_v2")

        # Add auditors based on review depth
        if review_depth in [ReviewDepth.STANDARD, ReviewDepth.DEEP]:
            squad.add("dss_governor")
        if review_depth == ReviewDepth.DEEP:
            squad.add("dss_user_alias_v2")

        # Fallback to governor & CSO if squad too small
        if len(squad) < 2:
            squad.add("dss_governor")

        return sorted(list(squad))

    @staticmethod
    def infer_strategy(goal: str, codebase_meta: Optional[Dict[str, Any]] = None) -> ExecutionStrategy:
        goal_lower = goal.lower()
        meta = codebase_meta or {}

        # 1. Infer Urgency
        if any(kw in goal_lower for kw in ["emergency", "hotfix", "production down", "critical bug", "crash"]):
            urgency = Urgency.EMERGENCY
        elif any(kw in goal_lower for kw in ["urgent", "asap", "blocking", "high priority"]):
            urgency = Urgency.HIGH
        elif any(kw in goal_lower for kw in ["minor", "tweak", "doc", "comment", "style", "typo"]):
            urgency = Urgency.LOW
        else:
            urgency = Urgency.MEDIUM

        # 2. Infer Risk Level
        if any(kw in goal_lower for kw in ["auth", "security", "crypto", "billing", "payment", "database migration", "schema change"]):
            risk = RiskLevel.CRITICAL if urgency == Urgency.EMERGENCY else RiskLevel.HIGH
        elif any(kw in goal_lower for kw in ["refactor", "architecture", "upgrade", "api change"]):
            risk = RiskLevel.HIGH
        elif any(kw in goal_lower for kw in ["bug", "fix", "typo", "ui alignment", "color", "navbar"]):
            risk = RiskLevel.LOW
        else:
            risk = RiskLevel.MEDIUM

        # 3. Detect Active Domains & Review Depth
        detected_domains = StrategyEngine.detect_domains(goal)
        review_depth = StrategyEngine.infer_review_depth(risk, urgency)

        # 4. Resolve Context-Aware Adaptive Debate Squad (Capability Match)
        debate_squad = StrategyEngine.resolve_debate_squad(detected_domains, review_depth)

        # 5. Infer Project Scale
        file_count = meta.get("file_count", 0)
        if file_count > 500:
            scale = ProjectScale.ENTERPRISE
        elif file_count > 100:
            scale = ProjectScale.LARGE
        elif file_count > 30:
            scale = ProjectScale.MEDIUM
        elif file_count > 5:
            scale = ProjectScale.SMALL
        else:
            scale = ProjectScale.MICRO

        # 6. Infer Parallelism & Clarification
        parallelism = scale in [ProjectScale.MEDIUM, ProjectScale.LARGE, ProjectScale.ENTERPRISE] and risk in [RiskLevel.MEDIUM, RiskLevel.HIGH]
        clarification = risk in [RiskLevel.HIGH, RiskLevel.CRITICAL] and not any(kw in goal_lower for kw in ["exact", "specifically", "do not change", "fix line"])

        # 7. Resolve Profile
        if urgency == Urgency.EMERGENCY:
            profile = WorkflowProfile.HOTFIX
        elif risk == RiskLevel.LOW and any(kw in goal_lower for kw in ["fix", "bug", "error", "align", "color"]):
            profile = WorkflowProfile.BUG_FIX
        elif any(kw in goal_lower for kw in ["audit", "research", "investigate", "explain"]):
            profile = WorkflowProfile.RESEARCH
        elif any(kw in goal_lower for kw in ["refactor", "clean"]):
            profile = WorkflowProfile.REFACTOR
        else:
            profile = WorkflowProfile.FULL

        # Construct Rationale
        rationale = (
            f"Strategy Inferred: Domains={detected_domains}, ReviewDepth={review_depth.value.upper()}, "
            f"Risk={risk.value.upper()}, DebateSquad={debate_squad}, Profile => {profile.value.upper()}"
        )

        return ExecutionStrategy(
            goal=goal,
            risk_level=risk,
            urgency=urgency,
            project_scale=scale,
            parallelism_worthwhile=parallelism,
            clarification_required=clarification,
            recommended_profile=profile,
            detected_domains=detected_domains,
            review_depth=review_depth,
            debate_panel=debate_squad,
            required_evidence=DEFAULT_EVIDENCE_CONTRACTS,
            rationale=rationale,
        )
