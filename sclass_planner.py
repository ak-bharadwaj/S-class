"""
S-Class EOS Planning Engine (sclass_planner.py)

Untrusted Planning Service responsible for:
- Domain Classification & Domain Interaction Graph
- Capability Plugin Lookup
- Adaptive Sequential Tiered Debate Squad Assembly
- Strategy & Intent Contract Inference
- Task DAG Compilation & Dependency Confidence Graph
"""

import os
import sys
import json
import logging
from typing import List, Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from strategy import StrategyEngine, ExecutionStrategy, RiskLevel, ReviewDepth, DOMAIN_INTERACTION_GRAPH
from planner import MetaPlanner, WorkflowProfile, WorkflowPlan

logger = logging.getLogger("sclass_planner")


class PlanningEngine:
    """Standalone Planning & Strategy Service that proposes Execution Plans to the Kernel."""

    @staticmethod
    def create_execution_plan(goal: str, codebase_meta: Optional[Dict[str, Any]] = None) -> ExecutionStrategy:
        """Analyzes goal and generates a comprehensive ExecutionStrategy plan."""
        logger.info(f"[PlanningEngine] Creating execution plan for goal: '{goal}'")
        return StrategyEngine.infer_strategy(goal, codebase_meta=codebase_meta)

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
