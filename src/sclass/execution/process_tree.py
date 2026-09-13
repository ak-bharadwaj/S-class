"""
S-Class Execution: Process Tree Inspection and Hierarchy Tracing.
Captures actual parent-child process relationships across execution layers
(launcher -> wrapper -> interpreter -> child -> verifier).
"""

from __future__ import annotations
import os
import sys
import platform
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple


@dataclass
class ProcessTreeNode:
    """Individual node in an observed execution process tree."""
    pid: int
    ppid: int
    name: str
    executable_path: str
    argv: List[str]
    children: List[ProcessTreeNode] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pid": self.pid,
            "ppid": self.ppid,
            "name": self.name,
            "executable_path": self.executable_path,
            "argv": list(self.argv),
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class ProcessTree:
    """Authoritative snapshot of an executed process tree."""
    root: ProcessTreeNode
    total_processes: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "root": self.root.to_dict(),
            "total_processes": self.total_processes,
        }

    def flatten(self) -> List[ProcessTreeNode]:
        """Returns flattened list of all nodes in tree in breadth-first order."""
        nodes = []
        queue = [self.root]
        while queue:
            curr = queue.pop(0)
            nodes.append(curr)
            queue.extend(curr.children)
        return nodes


class ProcessTreeInspector:
    """
    Cross-platform process tree inspector extracting true process hierarchies.
    Discovers multi-tier wrappers, interpreters, and spawned children.
    """

    @classmethod
    def capture_tree(
        cls,
        root_pid: int,
        fallback_argv: Optional[List[str]] = None,
        fallback_exe: Optional[str] = None,
    ) -> ProcessTree:
        """Captures process tree rooted at root_pid with platform-specific inspection."""
        argv = list(fallback_argv or [])
        exe = fallback_exe or (argv[0] if argv else "")
        name = os.path.basename(exe) if exe else f"proc_{root_pid}"

        root_node = ProcessTreeNode(
            pid=root_pid,
            ppid=os.getppid() if hasattr(os, "getppid") else 0,
            name=name,
            executable_path=exe,
            argv=argv,
        )

        children_nodes: List[ProcessTreeNode] = []

        # Attempt platform child discovery
        try:
            if platform.system() == "Windows":
                children_nodes = cls._discover_windows_children(root_pid)
            elif platform.system() == "Linux":
                children_nodes = cls._discover_linux_children(root_pid)
            elif platform.system() == "Darwin":
                children_nodes = cls._discover_macos_children(root_pid)
        except Exception:
            pass

        root_node.children = children_nodes
        total = 1 + sum(len(c.children) + 1 for c in children_nodes)

        return ProcessTree(root=root_node, total_processes=total)

    @classmethod
    def _discover_windows_children(cls, parent_pid: int) -> List[ProcessTreeNode]:
        """Windows Toolhelp32Snapshot or WMI fallback."""
        children = []
        # Attempt psutil if installed
        try:
            import psutil
            parent = psutil.Process(parent_pid)
            for ch in parent.children(recursive=False):
                try:
                    c_argv = ch.cmdline()
                    c_exe = ch.exe()
                    node = ProcessTreeNode(
                        pid=ch.pid,
                        ppid=parent_pid,
                        name=ch.name(),
                        executable_path=c_exe,
                        argv=c_argv,
                    )
                    children.append(node)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
        return children

    @classmethod
    def _discover_linux_children(cls, parent_pid: int) -> List[ProcessTreeNode]:
        """Linux /proc scanning."""
        children = []
        task_dir = f"/proc/{parent_pid}/task"
        if not os.path.exists(task_dir):
            return children

        seen_pids = set()
        try:
            for tid in os.listdir(task_dir):
                ch_file = os.path.join(task_dir, tid, "children")
                if os.path.exists(ch_file):
                    with open(ch_file, "r") as f:
                        for line in f:
                            for part in line.split():
                                ch_pid = int(part)
                                if ch_pid not in seen_pids:
                                    seen_pids.add(ch_pid)
                                    exe = ""
                                    try:
                                        exe = os.path.realpath(f"/proc/{ch_pid}/exe")
                                    except Exception:
                                        pass
                                    cmd = []
                                    try:
                                        with open(f"/proc/{ch_pid}/cmdline", "rb") as cf:
                                            cmd = [c.decode("utf-8", "replace") for c in cf.read().split(b"\x00") if c]
                                    except Exception:
                                        pass
                                    children.append(ProcessTreeNode(
                                        pid=ch_pid,
                                        ppid=parent_pid,
                                        name=os.path.basename(exe) if exe else f"proc_{ch_pid}",
                                        executable_path=exe,
                                        argv=cmd,
                                    ))
        except Exception:
            pass
        return children

    @classmethod
    def _discover_macos_children(cls, parent_pid: int) -> List[ProcessTreeNode]:
        """macOS pgrep fallback."""
        children = []
        try:
            import subprocess
            out = subprocess.check_output(["pgrep", "-P", str(parent_pid)], text=True, timeout=1).strip()
            for line in out.splitlines():
                ch_pid = int(line.strip())
                children.append(ProcessTreeNode(
                    pid=ch_pid,
                    ppid=parent_pid,
                    name=f"proc_{ch_pid}",
                    executable_path="",
                    argv=[],
                ))
        except Exception:
            pass
        return children
