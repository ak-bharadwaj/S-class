"""
S-Class EOS Decoupled Planning Pipeline (sclass_planner.py)

Decoupled single-responsibility planning components:
1. IntentExtractor    -> Extracts goals, scope boundaries, and explicit constraints.
2. RiskAnalyzer       -> Assesses risk level, urgency, review depth, and queries Knowledge Base.
3. WorkflowSelector   -> Selects optimal workflow profile (FULL, BUG_FIX, RESEARCH, REFACTOR, HOTFIX).
4. ExecutionPlanner   -> Assembles execution plan, task DAG, and capability plugin squad.
"""

import os
import sys
import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from strategy import StrategyEngine, ExecutionStrategy, RiskLevel, ReviewDepth, DOMAIN_INTERACTION_GRAPH
from planner import MetaPlanner, WorkflowProfile, WorkflowPlan
from knowledge_base import KnowledgeBaseManager

logger = logging.getLogger("sclass_planner")


@dataclass
class ExtractedIntent:
    goal: str
    target_domains: List[str]
    explicit_constraints: List[str] = field(default_factory=list)
    extracted_features: List[str] = field(default_factory=list)


@dataclass
class RiskAssessment:
    risk_level: RiskLevel
    review_depth: ReviewDepth
    knowledge_context: Dict[str, List[Dict[str, Any]]]


class IntentExtractor:
    """Stage 1: Extracts intent, domains, scope boundaries, and structured spec features from files."""

    @staticmethod
    def extract_spec_features(workspace_dir: Optional[str] = None) -> List[str]:
        """Parses specification files (e.g. implementation-details.txt) to extract all explicit feature headings and sections."""
        cwd = workspace_dir if workspace_dir else os.getcwd()
        features = []
        spec_candidates = ["implementation-details.txt", "spec.md", "REQUIREMENTS.md", "PROJECT.md"]
        for fname in spec_candidates:
            fpath = os.path.join(cwd, fname)
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            l_strip = line.strip()
                            if not l_strip:
                                continue
                            l_lower = l_strip.lower()
                            # Match headings, features, milestones, modules, and numbered list items
                            if (l_strip.startswith("#") or
                                "feature:" in l_lower or
                                "milestone" in l_lower or
                                "module:" in l_lower or
                                any(l_lower.startswith(f"{i}.") for i in range(1, 25)) or
                                any(l_lower.startswith(f"{i}feature:") for i in range(1, 25))):
                                features.append(l_strip)
                except Exception as e:
                    logger.error(f"[IntentExtractor] Spec file parse error '{fname}': {e}")
        return features

    @staticmethod
    def extract_intent(goal_text: str, workspace_dir: Optional[str] = None) -> ExtractedIntent:
        domains = StrategyEngine.detect_domains(goal_text)
        constraints = []
        if "must" in goal_text.lower() or "never" in goal_text.lower():
            constraints.append("Enforce explicit prompt boundary constraints")
        
        features = IntentExtractor.extract_spec_features(workspace_dir)
        if features:
            logger.info(f"[IntentExtractor] Parsed {len(features)} explicit specification features from workspace")
        return ExtractedIntent(goal=goal_text, target_domains=domains, explicit_constraints=constraints, extracted_features=features)


class RiskAnalyzer:
    """Stage 2: Assesses risk level, review depth, and retrieves organizational Knowledge Base."""

    @staticmethod
    def analyze_risk(intent: ExtractedIntent, workspace_dir: Optional[str] = None) -> RiskAssessment:
        strat = StrategyEngine.infer_strategy(intent.goal)
        kb_data = KnowledgeBaseManager.query_knowledge_base(intent.goal, workspace_dir=workspace_dir)
        return RiskAssessment(
            risk_level=strat.risk_level,
            review_depth=strat.review_depth,
            knowledge_context=kb_data
        )


class WorkflowSelector:
    """Stage 3: Selects the optimal workflow profile."""

    @staticmethod
    def select_profile(intent: ExtractedIntent, risk: RiskAssessment, override_profile: Optional[str] = None) -> WorkflowPlan:
        return MetaPlanner.classify_goal(intent.goal, override_profile=override_profile)


class ExecutionPlanner:
    """Stage 4: Assembles the complete Execution Plan and capability squad."""

    @staticmethod
    def create_plan(goal: str, workspace_dir: Optional[str] = None, codebase_meta: Optional[Dict[str, Any]] = None) -> ExecutionStrategy:
        # Step 1: Intent Extraction & Spec Feature Parsing
        intent = IntentExtractor.extract_intent(goal, workspace_dir=workspace_dir)
        # Step 2: Risk & Knowledge Base Retrieval
        risk = RiskAnalyzer.analyze_risk(intent, workspace_dir=workspace_dir)
        # Step 3: Workflow Profile Selection
        plan = WorkflowSelector.select_profile(intent, risk)
        # Step 4: Assemble Execution Strategy chained with Pipeline outputs
        strategy = StrategyEngine.infer_strategy(goal, codebase_meta=codebase_meta)
        strategy.target_domains = list(dict.fromkeys(strategy.target_domains + intent.target_domains))
        strategy.risk_level = risk.risk_level
        strategy.review_depth = risk.review_depth

        logger.info(f"[ExecutionPlanner] Assembled Execution Plan (Domains={strategy.target_domains}, Risk={risk.risk_level.value}, Profile={plan.profile.value})")
        return strategy

    @staticmethod
    def discover_capability_plugins() -> Dict[str, Any]:
        """Discovers capability plugins dynamically from capability_plugins/ directory."""
        plugins_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "capability_plugins")
        capabilities = {}
        if os.path.exists(plugins_dir):
            for fname in os.listdir(plugins_dir):
                if fname.endswith(".py") and not fname.startswith("__"):
                    mod_name = fname[:-3]
                    try:
                        import importlib
                        mod = importlib.import_module(f"capability_plugins.{mod_name}")
                        if hasattr(mod, "PLUGIN_INFO"):
                            info = getattr(mod, "PLUGIN_INFO")
                            capabilities[info["name"]] = info
                    except Exception as e:
                        logger.error(f"Failed loading capability plugin '{fname}': {e}")
        return capabilities
