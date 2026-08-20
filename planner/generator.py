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

        # Collect open obligations in the executable frontier
        exec_obl_ids = set(content.executable_frontier)
        open_obls = [
            obl for obl in content.obligations
            if obl.get("status") in (ObligationStatus.OPEN.value, "OPEN")
        ]

        if not open_obls:
            return ()

        candidates: List[ExecutionStrategyArtifact] = []

        # Candidate 1: Frontier-first test-driven verification strategy
        nodes_c1: List[PlanNode] = []
        edges_c1: List[Tuple[str, str]] = []
        for idx, obl in enumerate(open_obls):
            obl_id = obl["obligation_id"]
            node_test_id = f"NODE-TEST-{obl_id}-{idx+1}"
            node_patch_id = f"NODE-PATCH-{obl_id}-{idx+1}"

            # Step A: Execute baseline test
            nodes_c1.append(
                PlanNode(
                    node_id=node_test_id,
                    obligation_id=obl_id,
                    action_type="EXECUTE_TEST",
                    target=f"tests/test_{obl_id.lower().replace('-', '_')}.py",
                    purpose=f"Baseline verification for {obl_id}",
                    execution_context=context,
                    prerequisites=(),
                    estimated_cost_usd=0.05,
                    timeout_seconds=30,
                )
            )

            # Step B: Apply patch (depends on test)
            nodes_c1.append(
                PlanNode(
                    node_id=node_patch_id,
                    obligation_id=obl_id,
                    action_type="APPLY_PATCH",
                    target="src/core.py",
                    purpose=f"Implementation patch for {obl_id}",
                    execution_context=context,
                    prerequisites=(node_test_id,),
                    estimated_cost_usd=0.10,
                    timeout_seconds=45,
                )
            )
            edges_c1.append((node_test_id, node_patch_id))

        strat_c1 = ExecutionStrategyArtifact(
            strategy_id=f"STRAT-{task_id}-C1",
            plan_id=f"PLAN-{task_id}-01",
            plan_revision=1,
            nodes=tuple(nodes_c1),
            dependency_edges=tuple(edges_c1),
        )
        strat_c1_digest = compute_execution_strategy_fingerprint(strat_c1)
        strat_c1_final = ExecutionStrategyArtifact(
            strategy_id=strat_c1.strategy_id,
            plan_id=strat_c1.plan_id,
            plan_revision=strat_c1.plan_revision,
            nodes=strat_c1.nodes,
            dependency_edges=strat_c1.dependency_edges,
            strategy_digest=strat_c1_digest,
        )
        candidates.append(strat_c1_final)

        # Candidate 2: Static-analysis and Type-check first strategy
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
                        target="src/",
                        purpose=f"Static audit for {obl_id}",
                        execution_context=context,
                        prerequisites=(),
                        estimated_cost_usd=0.02,
                        timeout_seconds=20,
                    )
                )

                nodes_c2.append(
                    PlanNode(
                        node_id=node_patch_id,
                        obligation_id=obl_id,
                        action_type="APPLY_PATCH",
                        target="src/core.py",
                        purpose=f"Conservative patch for {obl_id}",
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
            strat_c2_digest = compute_execution_strategy_fingerprint(strat_c2)
            strat_c2_final = ExecutionStrategyArtifact(
                strategy_id=strat_c2.strategy_id,
                plan_id=strat_c2.plan_id,
                plan_revision=strat_c2.plan_revision,
                nodes=strat_c2.nodes,
                dependency_edges=strat_c2.dependency_edges,
                strategy_digest=strat_c2_digest,
            )
            candidates.append(strat_c2_final)

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
