"""
S-Class v6: Base Hook Adapter (adapters/base_adapter.py)

Shared base class providing state synchronization and drift detection
for IDE and AI coding agent hook adapters.
"""

from __future__ import annotations
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("sclass_base_adapter")


class BaseAdapter:
    """Base class for platform hook adapters with shared state sync logic."""

    def __init__(self, workspace_dir: Optional[str] = None):
        self.workspace_dir = os.path.abspath(workspace_dir or os.getcwd())

    def check_desync(self, local_phase: str, local_task_id: Optional[str] = None) -> tuple[bool, str]:
        """Detects if IDE state has drifted from authoritative kernel state."""
        from adapters.state_sync import StateSyncManager
        return StateSyncManager.check_desync(local_phase, self.workspace_dir, local_task_id)

    def sync_state(self, local_phase: Optional[str] = None) -> Dict[str, Any]:
        """Synchronizes IDE plugin state with authoritative kernel state."""
        from adapters.state_sync import StateSyncManager
        if local_phase:
            is_desynced, msg = StateSyncManager.check_desync(local_phase, self.workspace_dir)
            if is_desynced:
                logger.warning(f"[{self.__class__.__name__}] State desync detected: {msg}")
        return StateSyncManager.reconcile(self.workspace_dir)
