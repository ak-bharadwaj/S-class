"""
S-Class EOS V11.2 - D5 Lifecycle Hooks & Integrity Boundary (§8.3, CORE-25).
Deterministic 5-stage lifecycle hook pipeline:
PRE_VALIDATE -> PRE_AUTHORIZE -> (IMMUTABLE DECISION) -> PRE_EXECUTE -> (EXECUTION) -> POST_EXECUTE -> POST_OBSERVE.
CORE-25 Invariant: Hooks execute fail-closed. No hook can bypass authorization or forge execution tokens.
Later hooks (POST_EXECUTE / POST_OBSERVE) cannot grant authorization retroactively.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional, Sequence, Tuple, Any, Protocol


class LifecycleStage(str, Enum):
    """Discrete stages in Controller proposal and execution lifecycle."""
    PRE_VALIDATE = "PRE_VALIDATE"
    PRE_AUTHORIZE = "PRE_AUTHORIZE"
    PRE_EXECUTE = "PRE_EXECUTE"
    POST_EXECUTE = "POST_EXECUTE"
    POST_OBSERVE = "POST_OBSERVE"


@dataclass(frozen=True)
class HookResult:
    """Outcome of lifecycle hook execution."""
    proceed: bool
    error_message: Optional[str] = None
    diagnostics: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class HookContext:
    """Immutable execution context provided to lifecycle hooks."""
    stage: LifecycleStage
    proposal_id: str
    obligation_id: str
    action_type: str
    target: str
    source_sha: str
    authorization_decision: Optional[Any] = None
    execution_token: Optional[Any] = None
    execution_result: Optional[Any] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


class LifecycleHook(Protocol):
    """Protocol for lifecycle hook interceptors."""
    def execute_hook(self, context: HookContext) -> HookResult:
        ...


class LifecyclePipeline:
    """Deterministic, fail-closed lifecycle hook pipeline."""

    def __init__(self, hooks_by_stage: Optional[Mapping[LifecycleStage, Sequence[LifecycleHook]]] = None):
        self._hooks: dict[LifecycleStage, list[LifecycleHook]] = {
            stage: list(hooks_by_stage.get(stage, [])) if hooks_by_stage else []
            for stage in LifecycleStage
        }

    def register_hook(self, stage: LifecycleStage, hook: LifecycleHook) -> None:
        if not isinstance(stage, LifecycleStage):
            raise TypeError(f"Invalid lifecycle stage: {stage}")
        self._hooks[stage].append(hook)

    def run_stage(self, stage: LifecycleStage, context: HookContext) -> HookResult:
        """Executes all hooks registered for the given stage in deterministic order.
        
        Enforces CORE-25: Any hook returning proceed=False or throwing an exception halts the pipeline.
        """
        if context.stage != stage:
            return HookResult(proceed=False, error_message=f"Context stage mismatch: {context.stage} != {stage}")

        for hook in self._hooks.get(stage, []):
            try:
                res = hook.execute_hook(context)
                if not res or not res.proceed:
                    return HookResult(
                        proceed=False,
                        error_message=res.error_message if res else "Hook returned empty result",
                        diagnostics=res.diagnostics if res else (),
                    )
            except Exception as exc:
                return HookResult(
                    proceed=False,
                    error_message=f"Lifecycle hook exception in {stage}: {str(exc)}",
                    diagnostics=(repr(exc),),
                )

        return HookResult(proceed=True)
