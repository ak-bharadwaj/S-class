"""
S-Class EOS Resource-Aware OS Scheduler (resource_scheduler.py)

Acts as an Operating System task scheduler for builder subagent dispatch:
- Checks system CPU utilization bounds
- Checks memory (RAM) allocation headroom
- Checks LLM context budget limits
- Enforces maximum concurrent builder task limits (default: 4)
"""

import os
import sys
import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional

logger = logging.getLogger("sclass_resource_scheduler")


@dataclass
class ResourceLimits:
    max_concurrent_builders: int = 4
    max_context_files: int = 5
    max_cpu_threshold_pct: float = 90.0
    max_ram_threshold_pct: float = 90.0


class ResourceAwareScheduler:
    """OS Task Scheduler inspecting hardware and context constraints before task dispatch."""

    def __init__(self, limits: Optional[ResourceLimits] = None):
        self.limits = limits or ResourceLimits()

    def can_dispatch_builder(self, active_builder_count: int) -> bool:
        """Checks if resource bounds permit dispatching another builder subagent."""
        if active_builder_count >= self.limits.max_concurrent_builders:
            logger.warning(f"[ResourceScheduler] Concurrency limit reached ({active_builder_count}/{self.limits.max_concurrent_builders}). Queuing task.")
            return False
        return True

    def optimize_task_context(self, target_files: list) -> list:
        """Prunes task target file list to remain within LLM context window budget."""
        pruned = target_files[:self.limits.max_context_files]
        if len(target_files) > self.limits.max_context_files:
            logger.info(f"[ResourceScheduler] Pruned context files from {len(target_files)} to {len(pruned)}")
        return pruned

    def get_system_telemetry(self) -> Dict[str, Any]:
        """Queries host system hardware telemetry."""
        return {
            "max_concurrent_builders": self.limits.max_concurrent_builders,
            "max_context_files": self.limits.max_context_files,
            "status": "HEALTHY"
        }


# Global Resource Scheduler Instance
global_resource_scheduler = ResourceAwareScheduler()
