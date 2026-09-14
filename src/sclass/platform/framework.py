"""
S-Class Platform Optimization: Platform Profiling Framework (B.4).

Coordinates dynamic platform detection, harness capability probing,
reconciliation with PlatformOptimizationEngine, and outcome-based strength learning.
"""

from __future__ import annotations
import os
import json
from typing import Dict, Any, Optional, List, Tuple

from sclass.platform.profile import PlatformProfile
from sclass.platform.policy import CompensationPolicy
from sclass.platform.budget import PerformanceBudget
from sclass.platform.detector import PlatformDetector, DetectedPlatform, detect_platform
from sclass.platform.archetypes import get_archetype, register_archetype, list_archetypes
from sclass.platform.engine import PlatformOptimizationEngine, ControlPolicy


class PlatformProfilingFramework:
    """
    Central framework managing active platform profiling, harness probing,
    and dynamic control policy synthesis across disparate coding agents.
    """

    def __init__(
        self,
        workspace_dir: str = "",
        budget: Optional[PerformanceBudget] = None,
        override_platform_id: Optional[str] = None,
    ):
        self.workspace_dir = os.path.abspath(workspace_dir) if workspace_dir else os.getcwd()
        self.budget = budget or PerformanceBudget()
        self.override_platform_id = override_platform_id
        self.metrics_file = os.path.join(self.workspace_dir, ".sclass", "platform", "learned_metrics.json")
        self._learned_metrics: Dict[str, List[Dict[str, Any]]] = {}
        self._load_learned_metrics()

    def _load_learned_metrics(self) -> None:
        if os.path.exists(self.metrics_file):
            try:
                with open(self.metrics_file, "r", encoding="utf-8") as f:
                    self._learned_metrics = json.load(f)
            except Exception:
                self._learned_metrics = {}

    def _save_learned_metrics(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.metrics_file), exist_ok=True)
            with open(self.metrics_file, "w", encoding="utf-8") as f:
                json.dump(self._learned_metrics, f, indent=2)
        except Exception:
            pass

    def resolve_platform(
        self,
        client_info: Optional[Dict[str, Any]] = None,
        requested_actor: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> DetectedPlatform:
        """Resolves active platform through explicit override or multi-modal detection."""
        if self.override_platform_id:
            profile, policy = get_archetype(self.override_platform_id)
            return DetectedPlatform(
                platform_id=self.override_platform_id,
                confidence=1.0,
                version=profile.version,
                evidence=[f"manual_override:{self.override_platform_id}"],
                profile=profile,
                policy=policy,
            )

        return detect_platform(
            workspace_dir=self.workspace_dir,
            env=env,
            client_info=client_info,
            requested_actor=requested_actor,
        )

    def probe_capabilities(
        self,
        platform_id: str,
        client_info: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """
        Probes dynamic harness capabilities (e.g. streaming, roots, sampling, parallel subagents).
        """
        capabilities = ["terminal_execution", "filesystem_io"]
        p_norm = platform_id.lower()

        if "codex" in p_norm:
            capabilities.extend([
                "long_horizon_sessions",
                "persistent_harness",
                "parallel_subagents",
                "multi_step_iteration",
            ])
        elif "claude" in p_norm:
            capabilities.extend([
                "deep_reasoning",
                "structured_tools",
                "prompt_caching",
                "subagent_tree",
                "checkpointing",
            ])
        elif "antigravity" in p_norm or "gemini" in p_norm:
            capabilities.extend([
                "parallel_agent_teams",
                "asynchronous_tasks",
                "cross_agent_handoff",
                "shared_graph_access",
            ])

        # Inspect client capabilities if provided via protocol
        if client_info and isinstance(client_info, dict):
            caps = client_info.get("capabilities", {})
            if isinstance(caps, dict):
                if caps.get("roots"):
                    capabilities.append("mcp_roots")
                if caps.get("sampling"):
                    capabilities.append("mcp_sampling")
                if caps.get("experimental"):
                    capabilities.append("experimental_features")

        return sorted(list(set(capabilities)))

    def get_profile(self, platform_id: str) -> PlatformProfile:
        """Retrieves PlatformProfile for a given platform identifier."""
        from sclass.platform.archetypes import get_archetype_profile
        return get_archetype_profile(platform_id)

    def detect(
        self,
        actor_token: Optional[str] = None,
        client_info: Optional[Dict[str, Any]] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> DetectedPlatform:
        """Convenience alias for resolve_platform."""
        return self.resolve_platform(
            requested_actor=actor_token,
            client_info=client_info,
            env=env,
        )

    def synthesize_policy(
        self,
        task: str = "general",
        risk: str = "medium",
        actor_token: Optional[str] = None,
        state: Optional[Dict[str, Any]] = None,
        client_info: Optional[Dict[str, Any]] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> ControlPolicy:
        """Convenience alias for synthesize_control_policy."""
        return self.synthesize_control_policy(
            task=task,
            risk=risk,
            state=state,
            client_info=client_info,
            requested_actor=actor_token,
            env=env,
        )

    def synthesize_control_policy(
        self,
        task: str = "general",
        risk: str = "medium",
        state: Optional[Dict[str, Any]] = None,
        client_info: Optional[Dict[str, Any]] = None,
        requested_actor: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> ControlPolicy:
        """
        Synthesizes active ControlPolicy for the detected platform and current task context.
        """
        detected = self.resolve_platform(
            client_info=client_info,
            requested_actor=requested_actor,
            env=env,
        )

        return PlatformOptimizationEngine.reconcile(
            profile=detected.profile,
            task=task,
            risk=risk,
            state=state or {},
            budget=self.budget,
        )

    def record_run_outcome(
        self,
        platform_id: str,
        task_class: str,
        success: bool,
        duration_ms: float,
        tokens_used: int = 0,
        regressions_detected: int = 0,
    ) -> None:
        """Records empirical performance telemetry for runtime strength learning."""
        key = platform_id.lower()
        if key not in self._learned_metrics:
            self._learned_metrics[key] = []

        self._learned_metrics[key].append({
            "task_class": task_class,
            "success": success,
            "duration_ms": duration_ms,
            "tokens_used": tokens_used,
            "regressions_detected": regressions_detected,
        })
        self._save_learned_metrics()

    def get_learned_summary(self, platform_id: str) -> Dict[str, Any]:
        """Summarizes empirical outcomes recorded for a platform archetype."""
        key = platform_id.lower()
        runs = self._learned_metrics.get(key, [])
        if not runs:
            return {"runs_count": 0, "success_rate": 0.0, "avg_duration_ms": 0.0, "total_regressions": 0}

        successes = sum(1 for r in runs if r["success"])
        total_dur = sum(r["duration_ms"] for r in runs)

        return {
            "runs_count": len(runs),
            "success_rate": round(successes / len(runs), 3),
            "avg_duration_ms": round(total_dur / len(runs), 2),
            "total_regressions": sum(r["regressions_detected"] for r in runs),
        }

    def refine_archetype(self, platform_id: str) -> PlatformProfile:
        """
        Refines PlatformProfile dynamically based on empirical historical runs.
        - If success_rate >= 0.85 and 0 regressions: annotates high empirical reliability, optimizes strengths.
        - If regressions > 0 or success_rate < 0.70: annotates elevated risk, requires deep verification.
        """
        base_profile = self.get_profile(platform_id)
        summary = self.get_learned_summary(platform_id)

        if summary.get("runs_count", 0) < 1:
            return base_profile

        meta = dict(base_profile.metadata)
        meta["empirical_runs"] = summary["runs_count"]
        meta["empirical_success_rate"] = summary["success_rate"]
        meta["empirical_regressions"] = summary["total_regressions"]

        strengths = list(base_profile.native_strengths)

        if summary["total_regressions"] > 0 or summary["success_rate"] < 0.70:
            meta["verification_requirement"] = "deep"
            meta["empirical_status"] = "elevated_risk"
            if "deep_verification_required" not in strengths:
                strengths.append("deep_verification_required")
        elif summary["success_rate"] >= 0.85 and summary["total_regressions"] == 0:
            meta["verification_requirement"] = "streamlined"
            meta["empirical_status"] = "high_reliability"
            if "high_empirical_reliability" not in strengths:
                strengths.append("high_empirical_reliability")

        return base_profile.clone_with(
            native_strengths=strengths,
            metadata=meta,
        )

    def evaluate_net_utility(self, platform_id: str) -> float:
        """
        Calculates empirical Net Utility Ratio for a platform across historical runs:
        Useful reliability gained vs operational overhead consumed.
        """
        summary = self.get_learned_summary(platform_id)
        if summary.get("runs_count", 0) == 0:
            return 1.0

        runs = self._learned_metrics.get(platform_id.lower(), [])
        success_count = sum(1 for r in runs if r.get("success", False))
        regressions = sum(r.get("regressions_detected", 0) for r in runs)
        total_duration = sum(r.get("duration_ms", 0.0) for r in runs)
        total_tokens = sum(r.get("tokens_used", 0) for r in runs)

        # Reliability score: success gives 20 pts each, regressions penalized 10 pts
        rel_score = max(1.0, (success_count * 20.0) - (regressions * 10.0))
        # Overhead score: duration (0.01 per ms) + tokens (0.005 per token)
        ovh_score = max(1.0, (total_duration * 0.01) + (total_tokens * 0.005))
        return round(rel_score / ovh_score, 4)
