"""
S-Class CLI: Workspace Daemon.
Provides a local monitoring loop and health check server for the workspace control plane.
"""

from __future__ import annotations
import os
import time
import logging
from typing import Optional

from sclass.storage.paths import WorkspacePaths
from sclass.state.tasks import StateRepository
from sclass.trust.ledger import LocalLedger

logger = logging.getLogger("sclass.daemon")


class SClassDaemon:
    """Background service managing workspace health, locks, and ledger integrity."""

    def __init__(self, workspace_dir: str, poll_interval_sec: float = 5.0):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.poll_interval_sec = poll_interval_sec
        self.paths = WorkspacePaths(self.workspace_dir)
        self.repo = StateRepository(self.workspace_dir)
        self.ledger = LocalLedger(self.workspace_dir)
        self._running = False

    def check_health(self) -> dict:
        is_valid, err = self.ledger.verify_integrity()
        proj_name = os.path.basename(self.workspace_dir)
        tasks = self.repo.list_tasks(project_id=proj_name)
        return {
            "workspace": self.workspace_dir,
            "ledger_valid": is_valid,
            "ledger_error": err,
            "active_tasks_count": len(tasks),
            "status": "healthy" if is_valid else "degraded",
        }

    def run_once(self) -> None:
        """Single tick of daemon monitoring."""
        health = self.check_health()
        if not health["ledger_valid"]:
            logger.warning(f"Ledger integrity error detected: {health['ledger_error']}")

    def start(self, max_ticks: Optional[int] = None) -> None:
        """Starts the daemon loop."""
        self._running = True
        ticks = 0
        logger.info(f"S-Class daemon started on {self.workspace_dir}")
        while self._running:
            self.run_once()
            ticks += 1
            if max_ticks and ticks >= max_ticks:
                break
            time.sleep(self.poll_interval_sec)

    def stop(self) -> None:
        self._running = False
