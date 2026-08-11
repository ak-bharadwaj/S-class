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
from typing import Dict, Any, Optional, List

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

    @staticmethod
    def _measure_cpu_utilization() -> float:
        """Measures CPU load percentage across platforms using stdlib fallback."""
        try:
            import psutil
            return psutil.cpu_percent(interval=0.1)
        except ImportError:
            try:
                if hasattr(os, "getloadavg"):
                    load = os.getloadavg()[0]
                    cpu_count = os.cpu_count() or 1
                    return min(100.0, (load / cpu_count) * 100.0)
            except Exception:
                pass
        return 10.0

    @staticmethod
    def _measure_ram_utilization() -> float:
        """Measures RAM load percentage across platforms using stdlib fallback."""
        try:
            import psutil
            return psutil.virtual_memory().percent
        except ImportError:
            try:
                if sys.platform == "win32":
                    import ctypes
                    class MEMORYSTATUSEX(ctypes.Structure):
                        _fields_ = [
                            ("dwLength", ctypes.c_ulong),
                            ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                        ]
                    stat = MEMORYSTATUSEX()
                    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                    return float(stat.dwMemoryLoad)
            except Exception:
                pass
        return 20.0

    def can_dispatch_builder(self, active_builder_count: int) -> bool:
        """Checks if resource bounds (concurrency, CPU, RAM) permit dispatching another builder subagent."""
        cpu_pct = self._measure_cpu_utilization()
        ram_pct = self._measure_ram_utilization()

        if active_builder_count >= self.limits.max_concurrent_builders:
            logger.warning(f"[ResourceScheduler] Concurrency limit reached ({active_builder_count}/{self.limits.max_concurrent_builders}). Queuing task.")
            return False
        if cpu_pct >= self.limits.max_cpu_threshold_pct:
            logger.warning(f"[ResourceScheduler] CPU load threshold exceeded ({cpu_pct:.1f}% >= {self.limits.max_cpu_threshold_pct}%). Throttling builder dispatch.")
            return False
        if ram_pct >= self.limits.max_ram_threshold_pct:
            logger.warning(f"[ResourceScheduler] RAM load threshold exceeded ({ram_pct:.1f}% >= {self.limits.max_ram_threshold_pct}%). Throttling builder dispatch.")
            return False
        return True

    def optimize_task_context(self, target_files: List[str]) -> List[str]:
        """Prunes task target file list to remain within LLM context window budget."""
        pruned = target_files[:self.limits.max_context_files]
        if len(target_files) > self.limits.max_context_files:
            logger.info(f"[ResourceScheduler] Pruned context files from {len(target_files)} to {len(pruned)}")
        return pruned

    def get_system_telemetry(self) -> Dict[str, Any]:
        """Queries host system hardware telemetry."""
        cpu = self._measure_cpu_utilization()
        ram = self._measure_ram_utilization()
        is_healthy = cpu < self.limits.max_cpu_threshold_pct and ram < self.limits.max_ram_threshold_pct
        return {
            "max_concurrent_builders": self.limits.max_concurrent_builders,
            "max_context_files": self.limits.max_context_files,
            "cpu_utilization_pct": round(cpu, 1),
            "ram_utilization_pct": round(ram, 1),
            "status": "HEALTHY" if is_healthy else "THROTTLED"
        }


# Global Resource Scheduler Instance
global_resource_scheduler = ResourceAwareScheduler()
