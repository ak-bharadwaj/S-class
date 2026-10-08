"""
S-Class: IDE State Synchronization & Heartbeat Engine (adapters/state_sync.py)

Prevents state desynchronization between IDE plugins and the S-Class kernel.
Detects when IDE plugin state drifts from authoritative kernel state (e.g., after an abrupt crash or disconnect).
"""

from __future__ import annotations
import os
import json
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("sclass_state_sync")


class StateSyncManager:
    """Monitors and synchronizes IDE plugin local state with authoritative kernel state."""

    @staticmethod
    def get_authoritative_state(workspace_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Reads authoritative FSM state from .agents/orchestration_state.json."""
        cwd = workspace_dir or os.getcwd()
        state_path = os.path.join(cwd, ".agents", "orchestration_state.json")
        if not os.path.exists(state_path):
            return None
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.debug(f"[StateSync] Failed reading authoritative state: {e}")
            return None

    @staticmethod
    def get_authoritative_phase(workspace_dir: Optional[str] = None) -> str:
        """Returns the authoritative current FSM phase string, or 'UNINITIALIZED'."""
        state = StateSyncManager.get_authoritative_state(workspace_dir)
        if not state:
            return "UNINITIALIZED"
        return state.get("currentPhase", "TRIAGE")

    @classmethod
    def check_desync(
        cls,
        local_phase: str,
        workspace_dir: Optional[str] = None,
        local_task_id: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Compares local IDE plugin phase with authoritative kernel state.
        Returns (is_desynced, diagnostic_message).
        """
        auth_state = cls.get_authoritative_state(workspace_dir)
        if not auth_state:
            return False, "Kernel state is not yet initialized."

        auth_phase = auth_state.get("currentPhase", "TRIAGE")
        auth_task = auth_state.get("taskId")

        if local_task_id and auth_task and local_task_id != auth_task:
            msg = f"Task ID mismatch: IDE has task '{local_task_id}', but kernel has active task '{auth_task}'."
            logger.warning(f"[StateSync] DESYNC DETECTED: {msg}")
            return True, msg

        if local_phase.upper() != auth_phase.upper():
            msg = f"Phase desynchronization: IDE displays '{local_phase}', but authoritative kernel is in '{auth_phase}'."
            logger.warning(f"[StateSync] DESYNC DETECTED: {msg}")
            return True, msg

        return False, "States are synchronized."

    @classmethod
    def reconcile(cls, workspace_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Forces alignment of IDE plugin state with the kernel's authoritative record.
        Returns reconciled state dictionary.
        """
        auth_state = cls.get_authoritative_state(workspace_dir)
        if not auth_state:
            return {"status": "uninitialized", "phase": "UNINITIALIZED"}

        return {
            "status": "reconciled",
            "phase": auth_state.get("currentPhase", "TRIAGE"),
            "taskId": auth_state.get("taskId"),
            "workflowProfile": auth_state.get("workflowProfile", "full"),
            "activeEvent": auth_state.get("activeEvent"),
        }
