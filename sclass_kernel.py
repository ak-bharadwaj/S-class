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
    pass


class EventStore:
    """Append-only canonical event log with Snapshot Checkpointing for O(delta) replay performance."""

    @staticmethod
    def get_store_file(workspace_dir: Optional[str] = None) -> str:
        cwd = workspace_dir if workspace_dir else os.getcwd()
        return os.path.join(cwd, ".agents", "event_store.jsonl")

    @staticmethod
    def get_snapshot_file(workspace_dir: Optional[str] = None) -> str:
        cwd = workspace_dir if workspace_dir else os.getcwd()
        return os.path.join(cwd, ".agents", "event_store_snapshot.json")

    @staticmethod
    def append_event(event_record: Dict[str, Any], workspace_dir: Optional[str] = None) -> None:
        store_file = EventStore.get_store_file(workspace_dir)
        os.makedirs(os.path.dirname(store_file), exist_ok=True)
        with open(store_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event_record) + "\n")

    @staticmethod
    def create_checkpoint(state: Dict[str, Any], event_offset: int, workspace_dir: Optional[str] = None) -> None:
        snapshot_file = EventStore.get_snapshot_file(workspace_dir)
        os.makedirs(os.path.dirname(snapshot_file), exist_ok=True)
        snapshot = {
            "snapshot_at": datetime.now(timezone.utc).isoformat() if 'datetime' in globals() else "",
            "event_offset": event_offset,
            "state_snapshot": state
        }
        with open(snapshot_file, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)

    @staticmethod
    def read_all_events(workspace_dir: Optional[str] = None) -> List[Dict[str, Any]]:
        store_file = EventStore.get_store_file(workspace_dir)
        snapshot_file = EventStore.get_snapshot_file(workspace_dir)
        events = []
        offset = 0

        if os.path.exists(snapshot_file):
            try:
                with open(snapshot_file, "r", encoding="utf-8") as sf:
                    snap_data = json.load(sf)
                    offset = snap_data.get("event_offset", 0)
            except Exception:
                offset = 0

        if not os.path.exists(store_file):
            return events

        with open(store_file, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                if idx >= offset and line.strip():
                    events.append(json.loads(line))
        return events


class MinimalDeterministicKernel:
    """
    S-Class EOS Microkernel Engine
    Exclusive State Mutator exposing a formal, policy-driven Kernel API.
    """

    def __init__(self):
        pass

    # === Formal Kernel API Methods ===

    def request_transition(self, from_state: str, event_name: str, workspace_dir: Optional[str] = None, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Formal Kernel API method for requesting state transition."""
        return self._execute_kernel_pipeline(event_name, workspace_dir=workspace_dir, payload=payload)

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

        for record in events:
            event_type = record.get("eventType")
            payload = record.get("payload", {})
            meta = record.get("metadata", {})

            if event_type == "STATE_INITIALIZED":
                workflow_profile = payload.get("workflowProfile", "full")
                plan_rationale = payload.get("planRationale", "")
                current_phase = "TRIAGE"
            elif event_type in ["PHASE_MUTATED", "MUTATION_RECORDED"]:
                current_phase = payload.get("toPhase", payload.get("toState", current_phase))
                active_event = payload.get("eventName", payload.get("eventFired", active_event))
                if "specVersion" in payload:
                    spec_version = payload["specVersion"]
                if "debateVersion" in payload:
                    debate_version = payload["debateVersion"]
                if "taskVersion" in payload:
                    task_version = payload["taskVersion"]

            # Aggregate decision and history logs if present
            if "decision" in payload and isinstance(payload["decision"], dict):
                decision_log.append(payload["decision"])
            if "transitionRecord" in payload and isinstance(payload["transitionRecord"], dict):
                transition_history.append(payload["transitionRecord"])

        state = runtime.State(
            taskId=events[0].get("taskId", "reconstructed-task"),
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

    def _execute_kernel_pipeline(self, event_name: str, workspace_dir: Optional[str] = None, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        cwd = workspace_dir if workspace_dir else os.getcwd()
        state_dir, state_file, lock_file, config_file = runtime._resolve_paths(cwd)
        payload = payload or {}

        # 1. OS FileLock Hardware Mutual Exclusion
        with runtime.FileLock(lock_file):
            state = runtime.get_state(cwd)
            current_phase = state.currentPhase

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

            # 5. Event Sourcing Store Append
            ts_now = runtime.datetime.now(runtime.timezone.utc).isoformat() + "Z"
            event_record = {
                "event_id": len(state.transitionHistory) + 1,
                "event_name": event_name,
                "from_state": current_phase,
                "to_state": next_phase,
                "workflow_profile": state.workflowProfile,
                "payload": payload,
                "timestamp": ts_now
            }
            EventStore.append_event(event_record, workspace_dir=cwd)

            # 6. Replay Log Entry
            dec_entry = runtime.Decision(
                decision=f"Kernel Approved Transition to {next_phase}",
                reason=f"Executed Kernel API request '{event_name}' from state '{current_phase}'",
                alternatives=list(valid_transitions.keys()),
                confidence=1.0,
                timestamp=ts_now,
                agent="minimal_kernel"
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
                agent="minimal_kernel"
            )
            state.transitionHistory.append(t_rec.to_dict())

            # 7. Threshold & Phase-Boundary Context Compression
            if ContextCompressor.should_compress(runtime.asdict(state), event_name=event_name):
                comp_memory = ContextCompressor.compress_context(runtime.asdict(state))
                logger.info(f"[Kernel] Threshold/Phase-boundary compression executed (Ratio: {comp_memory.compression_ratio})")

            # 8. EXCLUSIVE State Mutation Write
            runtime.save_state(state, cwd)

            # 9. Asynchronous Event Graph Broadcast
            topic = EventTopic.TASK_COMPLETED if event_name in ["code_written", "task_merged"] else EventTopic.TASK_STARTED
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
