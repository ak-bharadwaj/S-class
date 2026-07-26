"""
S-Class EOS Deterministic Microkernel (sclass_kernel.py)

Architectural Philosophy:
LLMs, Builders, QA Agents, and Subagents are UNTRUSTED PROPOSERS.
They CANNOT edit orchestration_state.json directly.

The Deterministic Microkernel is the EXCLUSIVE AUTHORITATIVE MUTATOR
of state, enforcing FSM transition graphs, schema validation, evidence verification,
OS file locks, and immutable replay audit logs.
"""

import os
import sys
import json
import logging
from dataclasses import asdict
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runtime
import verifier
import replay
import doctor
import config_gc
import error_recovery
from strategy import StrategyEngine
from planner import MetaPlanner

logger = logging.getLogger("sclass_kernel")


class KernelPermissionError(PermissionError):
    """Raised when an untrusted component attempts direct state mutation."""
    pass


class KernelEventBus:
    """Central event dispatcher separating event producers from state mutation."""
    
    def __init__(self, kernel: "DeterministicKernel"):
        self.kernel = kernel
        self.event_subscribers: Dict[str, List[Any]] = {}

    def emit(self, event_name: str, workspace_dir: Optional[str] = None, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Emits an event into the Kernel pipeline for validation and state transition."""
        logger.info(f"[Kernel EventBus] Event Emitted: '{event_name}' with payload={payload}")
        return self.kernel.process_event(event_name, workspace_dir=workspace_dir, payload=payload)


class DeterministicKernel:
    """
    S-Class EOS Microkernel Subsystems:
    ├── Transition Manager (workflow.json FSM graph validation)
    ├── Verification Engine (verifier.py hard evidence audit)
    ├── Lock Manager (OS FileLock mutual exclusion)
    ├── Schema Validator (state_schema.json structural enforcement)
    ├── Replay Engine (replay.py deterministic audit logging)
    ├── Scheduler (ResourceAwareScheduler & ContextBudgetOptimizer)
    ├── Resource Monitor (Host CPU & RAM checks)
    ├── Recovery Dispatcher (Smart Multi-Tier Error Recovery)
    └── State Manager (EXCLUSIVE Authoritative State Mutator)
    """

    def __init__(self):
        self.event_bus = KernelEventBus(self)

    def process_event(self, event_name: str, workspace_dir: Optional[str] = None, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        The Exclusive State Mutation Pipeline:
        Producer (LLM/Agent) ➔ emit(Event) ➔ FSM Check ➔ Schema Check ➔ Evidence Check ➔ Lock Manager ➔ State Mutation ➔ Replay Trail
        """
        cwd = workspace_dir if workspace_dir else os.getcwd()
        state_dir, state_file, lock_file, config_file = runtime._resolve_paths(cwd)

        # 1. OS FileLock Acquisition
        with runtime.FileLock(lock_file):
            state = runtime.get_state(cwd)
            current_phase = state.currentPhase

            # 2. Transition Manager: Validate FSM state graph
            workflow = runtime.load_json(runtime.WORKFLOW_FILE)
            events = runtime.load_json(runtime.EVENTS_FILE)
            workflow_state = workflow["states"].get(current_phase, {})
            valid_transitions = workflow_state.get("transitions", {})

            if event_name not in valid_transitions:
                raise ValueError(
                    f"[Kernel TransitionManager] Invalid transition '{event_name}' from state '{current_phase}' under profile '{state.workflowProfile}'"
                )

            next_phase = valid_transitions[event_name]

            # 3. Verification Engine: Hard Evidence Check
            enforce_ev = payload.get("enforce_evidence", False) if payload else False
            v_res = verifier.EvidenceVerifier.verify_phase(current_phase, workspace_dir=cwd, allow_soft=not enforce_ev)
            if not v_res.passed:
                raise verifier.VerificationError(f"[Kernel VerificationEngine] Evidence check failed for '{current_phase}': {v_res.errors}")

            # 4. Schema Validator: Pre-flight state validation
            event_meta = next((e for e in events if e["event"] == event_name), {})
            state.currentPhase = next_phase
            state.activeEvent = event_name

            # Side effects
            side_effects = event_meta.get("sideEffects", [])
            runtime._execute_side_effects(state, side_effects)

            state_dict = runtime.asdict(state)
            runtime.validate_state_types(state_dict)

            # 5. Replay Engine: Record Immutable Audit Log
            ts_now = runtime.datetime.now(runtime.timezone.utc).isoformat() + "Z"
            dec_entry = runtime.Decision(
                decision=f"Kernel Transition State to {next_phase}",
                reason=f"Approved event '{event_name}' emitted from state '{current_phase}'",
                alternatives=list(valid_transitions.keys()),
                confidence=1.0,
                timestamp=ts_now,
                agent="sclass_kernel"
            )
            state.decisionLog.append(dec_entry)

            t_rec = replay.TransitionRecord(
                stepIndex=len(state.transitionHistory) + 1,
                fromState=current_phase,
                toState=next_phase,
                eventFired=event_name,
                workflowProfile=state.workflowProfile,
                evidenceVerified=[asdict(art) for art in v_res.artifacts],
                decision=asdict(dec_entry),
                timestamp=ts_now,
                agent="sclass_kernel"
            )
            state.transitionHistory.append(t_rec.to_dict())

            # 6. EXCLUSIVE State Mutation Write
            runtime.save_state(state, cwd)

            logger.info(f"[Kernel StateManager] State Mutation Approved: '{current_phase}' ➔ '{next_phase}' (Event: '{event_name}')")

            return {
                "status": "APPROVED",
                "previousPhase": current_phase,
                "currentPhase": next_phase,
                "eventFired": event_name,
                "stepIndex": len(state.transitionHistory),
                "timestamp": ts_now
            }

    def reset_workflow(self, workspace_dir: Optional[str] = None, new_goal: Optional[str] = None) -> Dict[str, Any]:
        """Resets the workflow safely via the Kernel API."""
        runtime.reset_to_triage(workspace_dir, new_goal=new_goal)
        state = runtime.get_state(workspace_dir)
        return {
            "status": "RESET_APPROVED",
            "currentPhase": state.currentPhase,
            "workflowProfile": state.workflowProfile,
            "goal": state.planRationale
        }


# Global Kernel Singleton Instance
kernel_instance = DeterministicKernel()
