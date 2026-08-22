"""
S-Class Bounded Context Construction Engine.

Assembles compact, token-efficient, and security-isolated turn prompts
from the active decision frontier, target AST symbols, and sanitized failure diagnostics.
"""

from typing import Sequence, Optional, Dict, Any
from orchestrator.models import (
    RoutingDecision,
    OrchestrationStateSnapshot,
)
from domain.models import Obligation, Claim
from agent.models import AgentSessionContext


class BoundedContextBuilder:
    """Constructs bounded prompts from active decision frontier without full-repo bloat."""

    @classmethod
    def build_agent_context(
        cls,
        state: OrchestrationStateSnapshot,
        decision: RoutingDecision,
        session_id: str,
        repository_id: str,
        symbol_context: Optional[str] = None,
        failure_diagnostics: Optional[Sequence[str]] = None,
        prior_turn_summaries: Optional[Sequence[str]] = None,
    ) -> AgentSessionContext:
        """Constructs an AgentSessionContext bounded to the active decision slice."""

        # 1. Slice obligations to only the active frontier
        frontier_obls = [
            o for o in state.obligations if o.obligation_id in decision.active_frontier_ids
        ]
        frontier_details = tuple(
            {
                "obligation_id": o.obligation_id,
                "title": o.title,
                "category": o.category.value,
                "criticality": o.criticality.value,
            }
            for o in frontier_obls
        )

        # 2. Extract verification feedback if in failure mode
        verif_feedback = tuple(failure_diagnostics) if (failure_diagnostics and decision.context_slice_spec.include_diagnostics) else ()

        # 3. Assemble bounded objective prompt
        prompt_sections = []
        prompt_sections.append(f"## Reasoning Mode: {decision.mode.value}")
        prompt_sections.append(f"**Objective**: {decision.reasoning_objective}")
        prompt_sections.append(f"**Expected Output Artifact**: {decision.expected_artifact_type.value}")
        prompt_sections.append(f"**Verification Gate**: {decision.verification_requirement}")

        if decision.selected_skills:
            prompt_sections.append("### Active Engineering Skill Playbooks:")
            for skill in decision.selected_skills:
                prompt_sections.append(f"#### [{skill.category.value}] {skill.name}")
                prompt_sections.append(f"*{skill.purpose}*")
                prompt_sections.append("Guidelines:")
                for g in skill.guidelines:
                    prompt_sections.append(f"- {g}")

        if frontier_details:
            prompt_sections.append("### Active Obligation Frontier:")
            for fd in frontier_details:
                prompt_sections.append(f"- [{fd['obligation_id']}] {fd['title']} (Category: {fd['category']})")

        if symbol_context:
            prompt_sections.append("### Relevant Target Code Context:")
            prompt_sections.append(f"```python\n{symbol_context.strip()}\n```")

        if verif_feedback:
            prompt_sections.append("### Refutation & Failure Diagnostics:")
            max_lines = decision.context_slice_spec.max_diagnostic_lines
            for diag in verif_feedback[:max_lines]:
                prompt_sections.append(f"> {diag.strip()}")

        if prior_turn_summaries and decision.context_slice_spec.include_turn_history:
            prompt_sections.append("### Prior Turn Trajectory:")
            max_hist = decision.context_slice_spec.max_turn_history_count
            for s in prior_turn_summaries[-max_hist:]:
                prompt_sections.append(f"- {s.strip()}")

        objective_text = "\n\n".join(prompt_sections)

        return AgentSessionContext(
            session_id=session_id,
            repository_id=repository_id,
            source_sha=state.source_sha,
            task_id=state.task_id,
            objective=objective_text,
            frontier_obligation_ids=decision.active_frontier_ids,
            frontier_details=frontier_details,
            policy_constraints=(),
            verification_feedback=verif_feedback,
            available_tools=(),
            granted_capabilities=decision.required_capabilities,
            has_workspace_authority=False,
            turn_index=state.turn_index,
            max_turns=state.max_turns,
            remaining_budget_units=state.remaining_budget_units,
        )
