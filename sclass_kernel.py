"""
S-Class EOS Minimal Deterministic Microkernel (sclass_kernel.py)

Architectural Philosophy:
A microkernel must be SMALL, DETERMINISTIC, and EXCLUSIVELY AUTHORITATIVE over state mutation.
Planners, LLMs, Builders, and QA agents propose actions through the formal Kernel API.

Core Kernel Components:
├── Formal Kernel API (submit_event, request_transition, request_merge, request_recovery, request_release)
├── Transition Manager (workflow.json FSM State Graph validation)
├── Policy-Driven Verification Engine (policies.json declarative strength audit)
├── Lock Manager (OS FileLock hardware mutual exclusion)
├── Schema Validator (state_schema.json strict type validation)
├── Event Sourcing Store (append-only event_store.jsonl for state reconstruction)
├── Replay Engine (replay.py deterministic audit logging)
└── State Manager (EXCLUSIVE Authoritative State Mutator)
"""

import os
import sys
import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runtime
import verifier
import replay
import error_recovery
from event_graph import global_event_graph, EventTopic
from context_compressor import ContextCompressor

logger = logging.getLogger("sclass_kernel")


class KernelPermissionError(PermissionError):
    """Raised when an untrusted component attempts direct state mutation without Kernel API."""
from event_store import EventStore, EventRecord


class KernelPermissionError(PermissionError):
    """Raised when an untrusted component attempts direct state mutation without Kernel API."""
    pass


class MinimalDeterministicKernel:
    """
    S-Class EOS Central Deterministic Orchestration Kernel
    Exclusive State Mutator exposing a formal, policy-driven Kernel API.
    """

    def __init__(self):
        pass

    # === Formal Kernel API Methods ===

    def request_transition(
        self,
        event_name: Optional[str] = None,
        from_state: Optional[str] = None,
        workspace_dir: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Formal Kernel API method for requesting state transition.
        Contract: The kernel obtains authoritative currentPhase from persisted state.
        If caller specifies from_state (or legacy positional from_state), enforce caller_from_state == persisted.currentPhase.
        """
        # Robust parsing accommodating positional (from_state, event_name), (event_name), and kwargs
        if event_name and from_state:
            if event_name.isupper() and not from_state.isupper():
                caller_from_state = event_name
                actual_event = from_state
            else:
                caller_from_state = from_state
                actual_event = event_name
        elif event_name and not from_state:
            if args:
                if event_name.isupper():
                    caller_from_state = event_name
                    actual_event = args[0]
                else:
                    actual_event = event_name
                    caller_from_state = args[0]
            else:
                actual_event = event_name
                caller_from_state = kwargs.get("from_state")
        elif not event_name and from_state:
            actual_event = from_state
            caller_from_state = None
        else:
            caller_from_state = from_state or kwargs.get("from_state")
            actual_event = event_name or kwargs.get("event_name", "")

        if not actual_event:
            raise ValueError("[Kernel API] Missing mandatory 'event_name' for request_transition")

        return self._execute_kernel_pipeline(
            actual_event,
            workspace_dir=workspace_dir,
            payload=payload,
            expected_from_state=caller_from_state
        )

    def request_task_verification(self, task_id: str, workspace_dir: Optional[str] = None) -> Dict[str, Any]:
        """Formal Kernel API method for verifying an isolated task builder sandbox."""
        return self._execute_kernel_pipeline("task_verified", workspace_dir=workspace_dir, payload={"task_id": task_id, "enforce_evidence": True})

    def request_merge(self, task_id: str, sandbox_branch: str, workspace_dir: Optional[str] = None) -> Dict[str, Any]:
        """Formal Kernel API method for merging a verified task sandbox into primary branch."""
        return self._execute_kernel_pipeline("task_merged", workspace_dir=workspace_dir, payload={"task_id": task_id, "sandbox_branch": sandbox_branch})

    def request_recovery(self, error_log: str, workspace_dir: Optional[str] = None) -> Dict[str, Any]:
        """Formal Kernel API method for triggering smart multi-tier recovery."""
        rec_engine = error_recovery.RecoveryEngine()
        target_phase = rec_engine.classify_failure_target_phase(error_log)
        logger.warning(f"[Kernel Recovery] Smart Recovery routed error to target phase: '{target_phase}'")
        return self._execute_kernel_pipeline("patch_assigned", workspace_dir=workspace_dir, payload={"error_log": error_log, "target_phase": target_phase})

    def request_release(self, workspace_dir: Optional[str] = None) -> Dict[str, Any]:
        """Formal Kernel API method for final build release confirmation."""
        return self._execute_kernel_pipeline("release_complete", workspace_dir=workspace_dir, payload={"enforce_evidence": True})

    def reconstruct_state_from_event_store(self, workspace_dir: Optional[str] = None) -> Dict[str, Any]:
        """Event Sourcing State Projection: Reconstructs orchestration state by replaying event_store.jsonl."""
        cwd = workspace_dir if workspace_dir else os.getcwd()
        events = EventStore.read_all_events(cwd)
        logger.info(f"[Kernel EventSourcing] Reconstructing state from {len(events)} canonical event store records...")
        
        if not events:
            # No events to replay
            state = runtime.get_state(cwd)
            return {"reconstructed": False, "total_events": 0, "currentPhase": state.currentPhase, "state": runtime.asdict(state)}

        # Replay event stream to fold projected state
        current_phase = "TRIAGE"
        active_event = None
        spec_version = 1
        debate_version = 0
        task_version = 0
        retry_count = 0
        workflow_profile = "full"
        plan_rationale = ""
        decision_log = []
        transition_history = []
        tasks = []

        seen_event_ids = set()
        prev_state = None

        for idx, record in enumerate(events):
            # 1. Duplicate event ID check
            if record.event_id in seen_event_ids:
                raise ValueError(f"[Kernel Replay] Duplicate event_id '{record.event_id}' detected in event store.")
            seen_event_ids.add(record.event_id)

            # 2. Sequence continuity check (1-indexed contiguous)
            if record.event_id != idx + 1:
                raise ValueError(f"[Kernel Replay] Event sequence discontinuity: expected event_id {idx + 1}, got {record.event_id}")

            # 3. State continuity check
            if prev_state is not None and record.from_state and record.from_state != prev_state:
                raise ValueError(f"[Kernel Replay] State discontinuity at event {record.event_id}: previous state was '{prev_state}', but event started from '{record.from_state}'")

            if record.to_state:
                current_phase = record.to_state
                prev_state = record.to_state
            elif record.from_state:
                prev_state = record.from_state

            if record.event_name:
                active_event = record.event_name
            if record.workflow_profile:
                workflow_profile = record.workflow_profile

            payload = record.payload or {}
            if "specVersion" in payload:
                spec_version = payload["specVersion"]
            if "debateVersion" in payload:
                debate_version = payload["debateVersion"]
            if "taskVersion" in payload:
                task_version = payload["taskVersion"]

            # Aggregate decision and history logs
            if "decision" in payload and isinstance(payload["decision"], dict):
                decision_log.append(payload["decision"])
            if "transitionRecord" in payload and isinstance(payload["transitionRecord"], dict):
                transition_history.append(payload["transitionRecord"])
            else:
                transition_history.append({
                    "stepIndex": record.event_id,
                    "fromState": record.from_state,
                    "toState": record.to_state,
                    "eventFired": record.event_name,
                    "workflowProfile": record.workflow_profile,
                    "timestamp": record.timestamp
                })

        state = runtime.State(
            taskId="reconstructed-task",
            currentPhase=current_phase,
            activeEvent=active_event,
            currentSpecVersion=spec_version,
            currentDebateVersion=debate_version,
            currentTaskVersion=task_version,
            retryCount=retry_count,
            confidenceMatrix=runtime.ConfidenceMatrix(),
            workflowProfile=workflow_profile,
            planRationale=plan_rationale,
            tasks=tasks,
            decisionLog=decision_log,
            transitionHistory=transition_history
        )

        # Save reconstructed state to disk
        runtime.save_state(state, cwd)
        logger.info(f"[Kernel EventSourcing] State projected successfully at phase '{current_phase}'.")

        return {
            "reconstructed": True,
            "total_events": len(events),
            "currentPhase": current_phase,
            "state": runtime.asdict(state)
        }

    # === Internal Pipeline Execution Core ===

    def _execute_kernel_pipeline(
        self,
        event_name: str,
        workspace_dir: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        expected_from_state: Optional[str] = None
    ) -> Dict[str, Any]:
        cwd = workspace_dir if workspace_dir else os.getcwd()
        state_dir, state_file, lock_file, config_file = runtime._resolve_paths(cwd)
        payload = payload or {}

        # 1. OS FileLock Hardware Mutual Exclusion
        with runtime.FileLock(lock_file):
            state = runtime.get_state(cwd)
            current_phase = state.currentPhase

            # Enforce caller from_state contract if supplied
            if expected_from_state is not None and expected_from_state != current_phase:
                raise ValueError(
                    f"[Kernel API] State mismatch: caller claims from_state='{expected_from_state}', but authoritative persisted state is '{current_phase}'"
                )

            # 2. Transition Manager: Validate FSM State Graph
            workflow = runtime.load_json(runtime.WORKFLOW_FILE)
            events = runtime.load_json(runtime.EVENTS_FILE)
            workflow_state = workflow["states"].get(current_phase, {})
            valid_transitions = workflow_state.get("transitions", {})

            if event_name not in valid_transitions:
                raise ValueError(
                    f"[Kernel TransitionManager] Invalid transition '{event_name}' from state '{current_phase}' under profile '{state.workflowProfile}'"
                )

            next_phase = valid_transitions[event_name]

            # 3. Policy-Driven Verification Engine (QA & RELEASE phases strictly block soft evidence bypass)
            enforce_ev = payload.get("enforce_evidence", True)
            allow_soft = False if current_phase in ["QA", "RELEASE", "VERIFYING"] else not enforce_ev
            v_res = verifier.EvidenceVerifier.verify_phase(current_phase, workspace_dir=cwd, allow_soft=allow_soft)
            if not v_res.passed:
                raise verifier.VerificationError(f"[Kernel VerificationEngine] Evidence check failed for '{current_phase}': {'; '.join(v_res.errors)}")

            # 4. Schema Validator
            event_meta = next((e for e in events if e["event"] == event_name), {})
            state.currentPhase = next_phase
            state.activeEvent = event_name

            side_effects = event_meta.get("sideEffects", [])
            runtime._execute_side_effects(state, side_effects)

            state_dict = runtime.asdict(state)
            runtime.validate_state_types(state_dict)

            # 5. Canonical Event Sourcing Store Append
            ts_now = runtime.datetime.now(runtime.timezone.utc).isoformat() + "Z"
            event_rec = EventRecord(
                event_id=len(state.transitionHistory) + 1,
                event_name=event_name,
                from_state=current_phase,
                to_state=next_phase,
                timestamp=ts_now,
                payload=payload,
                event_type="PHASE_MUTATED",
                workflow_profile=state.workflowProfile
            )
            EventStore.append_event(event_rec, workspace_dir=cwd)

            # 6. Replay Log Entry
            dec_entry = runtime.Decision(
                decision=f"Kernel Approved Transition to {next_phase}",
                reason=f"Executed Kernel API request '{event_name}' from state '{current_phase}'",
                alternatives=list(valid_transitions.keys()),
                confidence=1.0,
                timestamp=ts_now,
                agent="central_kernel"
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
                agent="central_kernel"
            )
            state.transitionHistory.append(t_rec.to_dict())

            # 7. Threshold & Phase-Boundary Context Compression
            if ContextCompressor.should_compress(runtime.asdict(state), event_name=event_name):
                comp_memory = ContextCompressor.compress_context(runtime.asdict(state))
                logger.info(f"[Kernel] Threshold/Phase-boundary compression executed (Ratio: {comp_memory.compression_ratio})")

            # 8. EXCLUSIVE State Mutation Write
            runtime.save_state(state, cwd)

            # 9. Asynchronous Event Graph Broadcast
            if event_name in ["qa_failed", "verification_failed"]:
                topic = EventTopic.QA_FAILED
            elif event_name in ["patch_assigned", "issue_detected", "recovery_needed"]:
                topic = EventTopic.RECOVERY_REQUIRED
            elif event_name in ["release_complete", "released"]:
                topic = EventTopic.RELEASE_CREATED
            elif event_name in ["monitoring_alert", "telemetry_anomaly"]:
                topic = EventTopic.MONITORING_ALERT
            elif event_name in ["code_written", "task_merged", "spec_approved", "triage_done"]:
                topic = EventTopic.TASK_COMPLETED
            else:
                topic = EventTopic.TASK_STARTED

            global_event_graph.publish(topic, sender="sclass_kernel", payload={"event_name": event_name, "from_phase": current_phase, "to_phase": next_phase})

            logger.info(f"[Kernel StateManager] Mutation Approved: '{current_phase}' ➔ '{next_phase}' (Event: '{event_name}')")

            return {
                "status": "APPROVED",
                "previousPhase": current_phase,
                "currentPhase": next_phase,
                "eventFired": event_name,
                "stepIndex": len(state.transitionHistory),
                "timestamp": ts_now
            }


# Kernel Singleton Instance
kernel_instance = MinimalDeterministicKernel()
