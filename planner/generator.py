"""D8 Autonomous Planning Substrate - Candidate Generator (§3.6, §8.1).

Synthesizes candidate execution strategies using deterministic decomposition
rules and model-assisted generation with full provenance tracking.
"""

from __future__ import annotations
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, List, Mapping, Optional, Protocol, Sequence, Tuple

from controller.token import ExecutionContext
from domain.types import ObligationStatus
from planner.fingerprint import compute_execution_strategy_fingerprint
from planner.models import (
    ExecutionStrategyArtifact,
    GenerationProvenance,
    PlanNode,
    PlannerStateView,
)


class GeneratorProtocol(Protocol):
    """Protocol for candidate strategy generators."""
    def generate_candidates(
        self,
        state_view: PlannerStateView,
        context: ExecutionContext,
        max_candidates: int = 3,
    ) -> Sequence[ExecutionStrategyArtifact]:
        ...


class DeterministicRuleGenerator:
    """Rule-based deterministic candidate generator."""

    def __init__(self, generator_id: str = "GEN-RULE-DETERMINISTIC"):
        self.generator_id = generator_id

    def generate_candidates(
        self,
        state_view: PlannerStateView,
        context: ExecutionContext,
        max_candidates: int = 3,
    ) -> Sequence[ExecutionStrategyArtifact]:
        """Generates structured DAG strategies from open obligations and executable frontier."""
        content = state_view.content
        task_id = content.task_id

        # Collect open obligations strictly belonging to the executable frontier
        exec_obl_ids = set(content.executable_frontier)
        open_obls = [
            obl for obl in content.obligations
            if obl.get("status") in (ObligationStatus.OPEN.value, "OPEN")
            and obl.get("obligation_id") in exec_obl_ids
        ]

        if not open_obls:
            return ()

        # Extract analytical targets, hypotheses, and appropriate verification action types
        analytical_targets: List[str] = []
        requires_hypothesis_verification = False
        evidence_claim_refs: List[str] = []
        verification_action_type = "EXECUTE_TEST"

        for artifact in getattr(content, "analysis_artifacts", ()):
            for obs in getattr(artifact, "observations", ()):
                if getattr(obs, "target_path", None):
                    analytical_targets.append(obs.target_path)
                cat_lower = str(getattr(obs, "category", "")).lower()
                if cat_lower in ("type_signature", "types"):
                    verification_action_type = "TYPE_CHECK"
                elif cat_lower in ("static_ast", "ast", "lint"):
                    verification_action_type = "STATIC_ANALYSIS"
                elif cat_lower in ("contract", "fuzz"):
                    verification_action_type = "FUZZ_CONTRACT"
                elif cat_lower in ("file_entry", "read"):
                    if verification_action_type == "EXECUTE_TEST":
                        verification_action_type = "READ_FILE"

            for hyp in getattr(artifact, "hypotheses", ()):
                if getattr(hyp, "requires_verification", False):
                    requires_hypothesis_verification = True
                desc_lower = str(getattr(hyp, "description", "")).lower()
                if "type" in desc_lower or "signature" in desc_lower:
                    verification_action_type = "TYPE_CHECK"
                elif "static" in desc_lower or "ast" in desc_lower or "syntax" in desc_lower or "lint" in desc_lower:
                    verification_action_type = "STATIC_ANALYSIS"
                elif "contract" in desc_lower or "invariant" in desc_lower or "fuzz" in desc_lower:
                    verification_action_type = "FUZZ_CONTRACT"
                elif "read" in desc_lower or "inspect" in desc_lower:
                    verification_action_type = "READ_FILE"

            for cid in getattr(artifact, "referenced_claim_ids", ()):
                evidence_claim_refs.append(cid)

        # Grounded primary target: do NOT invent a target if none was observed in analysis
        primary_target = analytical_targets[0] if analytical_targets else None

        candidates: List[ExecutionStrategyArtifact] = []

        # Candidate 1: Frontier-first verification-driven strategy
        nodes_c1: List[PlanNode] = []
        edges_c1: List[Tuple[str, str]] = []
        for idx, obl in enumerate(open_obls):
            obl_id = obl["obligation_id"]
            node_verif_id = f"NODE-VERIF-{obl_id}-{idx+1}"
            node_patch_id = f"NODE-PATCH-{obl_id}-{idx+1}"

            if verification_action_type in ("STATIC_ANALYSIS", "TYPE_CHECK", "READ_FILE"):
                verif_target = primary_target or f"tests/test_{obl_id.lower().replace('-', '_')}.py"
            elif verification_action_type == "FUZZ_CONTRACT":
                verif_target = f"tests/fuzz_{obl_id.lower().replace('-', '_')}.py"
            else:
                verif_target = f"tests/test_{obl_id.lower().replace('-', '_')}.py"

            # Step A: Execute appropriate verification action
            nodes_c1.append(
                PlanNode(
                    node_id=node_verif_id,
                    obligation_id=obl_id,
                    action_type=verification_action_type,
                    target=verif_target,
                    purpose=f"Baseline {verification_action_type} verification for {obl_id}" + (" (Hypothesis-Gated)" if requires_hypothesis_verification else ""),
                    execution_context=context,
                    prerequisites=(),
                    estimated_cost_usd=0.05,
                    timeout_seconds=30,
                )
            )

            # Step B: Apply patch ONLY if a grounded target exists!
            if primary_target:
                nodes_c1.append(
                    PlanNode(
                        node_id=node_patch_id,
                        obligation_id=obl_id,
                        action_type="APPLY_PATCH",
                        target=primary_target,
                        purpose=f"Implementation patch for {obl_id} on {primary_target}",
                        execution_context=context,
                        prerequisites=(node_verif_id,),
                        estimated_cost_usd=0.10,
                        timeout_seconds=45,
                    )
                )
                edges_c1.append((node_verif_id, node_patch_id))

        strat_c1 = ExecutionStrategyArtifact(
            strategy_id=f"STRAT-{task_id}-C1",
            plan_id=f"PLAN-{task_id}-01",
            plan_revision=1,
            nodes=tuple(nodes_c1),
            dependency_edges=tuple(edges_c1),
        )
        candidates.append(strat_c1)

        # Candidate 2: Static-analysis and audit-first strategy
        if max_candidates > 1:
            nodes_c2: List[PlanNode] = []
            edges_c2: List[Tuple[str, str]] = []
            for idx, obl in enumerate(open_obls):
                obl_id = obl["obligation_id"]
                node_sa_id = f"NODE-SA-{obl_id}-{idx+1}"
                node_patch_id = f"NODE-PATCH-ALT-{obl_id}-{idx+1}"

                nodes_c2.append(
                    PlanNode(
                        node_id=node_sa_id,
                        obligation_id=obl_id,
                        action_type="STATIC_ANALYSIS",
                        target=primary_target or "src/",
                        purpose=f"Static audit for {obl_id}",
                        execution_context=context,
                        prerequisites=(),
                        estimated_cost_usd=0.02,
                        timeout_seconds=20,
                    )
                )

                if primary_target:
                    nodes_c2.append(
                        PlanNode(
                            node_id=node_patch_id,
                            obligation_id=obl_id,
                            action_type="APPLY_PATCH",
                            target=primary_target,
                            purpose=f"Conservative patch for {obl_id} on {primary_target}",
                            execution_context=context,
                            prerequisites=(node_sa_id,),
                            estimated_cost_usd=0.08,
                            timeout_seconds=40,
                        )
                    )
                    edges_c2.append((node_sa_id, node_patch_id))

            strat_c2 = ExecutionStrategyArtifact(
                strategy_id=f"STRAT-{task_id}-C2",
                plan_id=f"PLAN-{task_id}-01",
                plan_revision=1,
                nodes=tuple(nodes_c2),
                dependency_edges=tuple(edges_c2),
            )
            candidates.append(strat_c2)

        return tuple(candidates[:max_candidates])


class CandidateGenerator:
    """High-level candidate generator coordinator with fallback and provenance tracking."""

    def __init__(
        self,
        engine: Optional[GeneratorProtocol] = None,
        generator_id: str = "GEN-SCLASS-CORE-V1",
    ):
        self._engine = engine or DeterministicRuleGenerator()
        self._generator_id = generator_id

    def generate(
        self,
        state_view: PlannerStateView,
        context: ExecutionContext,
        max_candidates: int = 3,
    ) -> Sequence[Tuple[ExecutionStrategyArtifact, GenerationProvenance]]:
        """Generates candidate execution strategies paired with their provenance."""
        now_iso = datetime.now(timezone.utc).isoformat()
        prompt_digest = hashlib.sha256(
            f"{state_view.planner_state_digest}:{now_iso}".encode("utf-8")
        ).hexdigest()

        strategies = self._engine.generate_candidates(
            state_view=state_view,
            context=context,
            max_candidates=max_candidates,
        )

        results: List[Tuple[ExecutionStrategyArtifact, GenerationProvenance]] = []
        for idx, strat in enumerate(strategies):
            prov = GenerationProvenance(
                generator_id=self._generator_id,
                model_id="deterministic-rules" if isinstance(self._engine, DeterministicRuleGenerator) else "llm-planner",
                prompt_digest=prompt_digest,
                temperature=0.0,
                generated_at=now_iso,
                candidate_index=idx,
            )
            results.append((strat, prov))

        return tuple(results)
