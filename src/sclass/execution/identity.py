"""
S-Class Execution: ExecutionIdentity and Process Provenance.
Platform-aware, cryptographic process identity capturing actual executable paths,
binary hashes, child PIDs, execution chains, and identity lifecycles.
"""

from __future__ import annotations
import os
import sys
import shutil
import hashlib
import platform
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

from sclass.execution.modes import ExecutionMode
from sclass.execution.chain import ExecutionChain, analyze_execution_chain
from enum import Enum


class ExecutionIdentityState(str, Enum):
    """Lifecycle state of process execution identity."""
    REQUESTED = "REQUESTED"
    SPAWNED = "SPAWNED"
    IDENTIFIED = "IDENTIFIED"
    COMPLETED = "COMPLETED"
    IDENTITY_UNCERTAIN = "IDENTITY_UNCERTAIN"


class PlatformSupportStatus(str, Enum):
    """Authoritative platform support status for process inspection."""
    SUPPORTED = "supported"
    DEGRADED = "degraded"
    UNSUPPORTED = "unsupported"



def _query_windows_process_image(pid: int) -> Tuple[Optional[str], Optional[str]]:
    """
    Windows platform helper using kernel32 QueryFullProcessImageNameW.
    Returns (actual_executable_path, creation_time_iso) or (None, None).
    """
    if platform.system() != "Windows" or not pid:
        return None, None

    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h_proc:
            return None, None

        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            if kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size)):
                exe_path = buf.value
            else:
                exe_path = None

            # Attempt creation time
            creation_time = wintypes.FILETIME()
            exit_time = wintypes.FILETIME()
            kernel_time = wintypes.FILETIME()
            user_time = wintypes.FILETIME()
            iso_time = None
            if kernel32.GetProcessTimes(
                h_proc,
                ctypes.byref(creation_time),
                ctypes.byref(exit_time),
                ctypes.byref(kernel_time),
                ctypes.byref(user_time),
            ):
                ft_val = (creation_time.dwHighDateTime << 32) + creation_time.dwLowDateTime
                if ft_val > 0:
                    unix_sec = (ft_val - 116444736000000000) / 10000000.0
                    try:
                        iso_time = datetime.fromtimestamp(unix_sec, timezone.utc).isoformat()
                    except Exception:
                        iso_time = None

            return exe_path, iso_time
        finally:
            kernel32.CloseHandle(h_proc)
    except Exception:
        return None, None


def _query_linux_process_image(pid: int) -> Tuple[Optional[str], Optional[str]]:
    """
    Linux platform helper reading /proc/<pid>/exe, stat, and starttime.
    Returns (actual_executable_path, creation_time_iso) or (None, None).
    """
    if platform.system() != "Linux" or not pid:
        return None, None

    exe_link = f"/proc/{pid}/exe"
    exe_path = None
    if os.path.exists(exe_link):
        try:
            exe_path = os.path.realpath(exe_link)
        except Exception:
            pass

    iso_time = None
    stat_file = f"/proc/{pid}/stat"
    if os.path.exists(stat_file):
        try:
            stat_mtime = os.path.getmtime(stat_file)
            iso_time = datetime.fromtimestamp(stat_mtime, timezone.utc).isoformat()
        except Exception:
            pass

    return exe_path, iso_time


def _query_macos_process_image(pid: int) -> Tuple[Optional[str], Optional[str]]:
    """
    macOS platform helper using libproc proc_pidpath and creation time inspection.
    Returns (actual_executable_path, creation_time_iso) or (None, None).
    """
    if platform.system() != "Darwin" or not pid:
        return None, None

    exe_path = None
    iso_time = None
    try:
        import ctypes
        import ctypes.util

        libproc_path = ctypes.util.find_library("proc") or "/usr/lib/libproc.dylib"
        libproc = ctypes.CDLL(libproc_path)
        PROC_PIDPATHINFO_MAXSIZE = 4096
        buf = ctypes.create_string_buffer(PROC_PIDPATHINFO_MAXSIZE)
        ret = libproc.proc_pidpath(pid, buf, PROC_PIDPATHINFO_MAXSIZE)
        if ret > 0:
            exe_path = buf.value.decode("utf-8", errors="replace")
    except Exception:
        pass

    if not exe_path:
        try:
            import subprocess
            out = subprocess.check_output(["ps", "-p", str(pid), "-o", "comm="], text=True, timeout=2).strip()
            if out:
                exe_path = out
        except Exception:
            pass

    return exe_path, iso_time


def detect_execution_chain(
    argv: tuple[str, ...] | List[str],
    resolved_path: str = "",
) -> ExecutionChain:
    """Derives multi-tier execution chain (launcher, interpreter, child, verifier)."""
    return analyze_execution_chain(argv, resolved_path)


def discover_parent_chain(target_pid: int, known_parent_pid: Optional[int] = None) -> tuple[int, ...]:
    """
    Authoritatively discovers multi-tier OS process ancestry (parent PIDs).
    Walks up the parent process chain across Windows, Linux, and macOS.
    """
    chain: List[int] = []
    if not target_pid:
        return ()

    if platform.system() == "Windows":
        try:
            import ctypes
            from ctypes import wintypes
            TH32CS_SNAPPROCESS = 0x00000002

            class PROCESSENTRY32W(ctypes.Structure):
                _fields_ = [
                    ('dwSize', wintypes.DWORD),
                    ('cntUsage', wintypes.DWORD),
                    ('th32ProcessID', wintypes.DWORD),
                    ('th32DefaultHeapID', ctypes.POINTER(wintypes.ULONG)),
                    ('th32ModuleID', wintypes.DWORD),
                    ('cntThreads', wintypes.DWORD),
                    ('th32ParentProcessID', wintypes.DWORD),
                    ('pcPriClassBase', wintypes.LONG),
                    ('dwFlags', wintypes.DWORD),
                    ('szExeFile', ctypes.c_wchar * 260)
                ]

            hSnapshot = ctypes.windll.kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
            if hSnapshot and hSnapshot != -1:
                pe = PROCESSENTRY32W()
                pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
                pid_map = {}
                if ctypes.windll.kernel32.Process32FirstW(hSnapshot, ctypes.byref(pe)):
                    while True:
                        pid_map[pe.th32ProcessID] = pe.th32ParentProcessID
                        if not ctypes.windll.kernel32.Process32NextW(hSnapshot, ctypes.byref(pe)):
                            break
                ctypes.windll.kernel32.CloseHandle(hSnapshot)

                curr = target_pid
                start_p = pid_map.get(curr, known_parent_pid)
                curr = start_p
                while curr and curr in pid_map and curr not in chain and curr > 0 and len(chain) < 32:
                    chain.append(curr)
                    curr = pid_map.get(curr)
        except Exception:
            pass

    elif platform.system() == "Linux":
        curr = known_parent_pid or target_pid
        while curr and curr > 1 and len(chain) < 32:
            try:
                with open(f"/proc/{curr}/status", "r", encoding="utf-8") as f:
                    ppid = None
                    for line in f:
                        if line.startswith("PPid:"):
                            ppid = int(line.split()[1])
                            break
                    if ppid and ppid not in chain and ppid > 0:
                        chain.append(ppid)
                        curr = ppid
                    else:
                        break
            except Exception:
                break

    elif platform.system() == "Darwin":
        curr = known_parent_pid or target_pid
        while curr and curr > 1 and len(chain) < 32:
            try:
                import subprocess
                out = subprocess.check_output(["ps", "-o", "ppid=", "-p", str(curr)], text=True, timeout=1).strip()
                if out and out.isdigit():
                    ppid = int(out)
                    if ppid not in chain and ppid > 0:
                        chain.append(ppid)
                        curr = ppid
                    else:
                        break
                else:
                    break
            except Exception:
                break

    if known_parent_pid and known_parent_pid not in chain:
        chain.insert(0, known_parent_pid)
    if target_pid not in chain:
        chain.append(target_pid)

    return tuple(chain)


def detect_container_sandbox() -> Optional[str]:
    """Authoritatively detects containerization or sandbox environment."""
    if os.path.exists("/.dockerenv"):
        return "docker"
    elif os.path.exists("/run/.containerenv"):
        return "podman"
    elif "CONTAINER_ID" in os.environ:
        return os.environ["CONTAINER_ID"]
    elif "KUBERNETES_SERVICE_HOST" in os.environ:
        return "kubernetes"
    elif "WSL_DISTRO_NAME" in os.environ or os.path.exists("/proc/sys/fs/binfmt_misc/WSLInterop"):
        return "wsl2"
    elif os.path.exists("/proc/1/cgroup"):
        try:
            with open("/proc/1/cgroup", "r", encoding="utf-8", errors="ignore") as f:
                cgroup = f.read()
                if "docker" in cgroup:
                    return "docker"
                elif "containerd" in cgroup:
                    return "containerd"
                elif "kubepods" in cgroup:
                    return "kubernetes"
                elif "lxc" in cgroup:
                    return "lxc"
        except Exception:
            pass
    return None




@dataclass(frozen=True)
class ExecutionIdentity:
    """
    Authoritative cryptographic and process identity of an executed process.
    Separates requested parameters from independently captured actual runtime parameters.
    """
    requested_argv: tuple[str, ...]
    actual_argv: tuple[str, ...]
    executable_name: str
    executable_path: str
    executable_hash: str
    pid: Optional[int]
    parent_pid: Optional[int]
    process_start_time: str
    cwd: str
    environment_digest: str
    execution_mode: str
    launcher_identity: Optional[str] = None
    wrapper_identity: Optional[str] = None
    identity_state: str = ExecutionIdentityState.IDENTIFIED.value
    execution_chain: Optional[Dict[str, Any]] = None
    ppid: Optional[int] = None
    uid: Optional[int] = None
    gid: Optional[int] = None
    parent_chain: tuple[int, ...] = field(default_factory=tuple)
    platform: str = field(default_factory=platform.system)
    container_sandbox_identity: Optional[str] = None
    platform_support_status: str = PlatformSupportStatus.SUPPORTED.value

    def __post_init__(self):
        if self.ppid is None and self.parent_pid is not None:
            object.__setattr__(self, "ppid", self.parent_pid)
        elif self.parent_pid is None and self.ppid is not None:
            object.__setattr__(self, "parent_pid", self.ppid)

    @property
    def executable(self) -> str:
        return self.executable_name

    @property
    def resolved_path(self) -> str:
        return self.executable_path

    @property
    def argv(self) -> tuple[str, ...]:
        return self.actual_argv

    @property
    def start_time(self) -> str:
        return self.process_start_time

    @property
    def environment_fingerprint(self) -> str:
        return self.environment_digest

    @classmethod
    def capture(
        cls,
        command_argv: List[str] | tuple[str, ...],
        cwd: str,
        env: Optional[Dict[str, str]] = None,
        pid: Optional[int] = None,
        parent_pid: Optional[int] = None,
        mode: ExecutionMode | str = ExecutionMode.HOST_ARGV,
        requested_argv: Optional[List[str] | tuple[str, ...]] = None,
        launcher_identity: Optional[str] = None,
        wrapper_identity: Optional[str] = None,
    ) -> ExecutionIdentity:
        """
        Captures authoritative execution identity using OS process inspection,
        hash verification, and execution chain analysis.
        """
        actual_tokens = tuple(command_argv)
        req_tokens = tuple(requested_argv) if requested_argv is not None else actual_tokens

        exe_name = actual_tokens[0] if actual_tokens else ""
        resolved = ""
        actual_start_time = None
        state = ExecutionIdentityState.IDENTIFIED

        # 1. Platform-aware process inspection from actual child PID
        if pid:
            if platform.system() == "Windows":
                proc_exe, proc_start = _query_windows_process_image(pid)
                if proc_exe:
                    resolved = proc_exe
                if proc_start:
                    actual_start_time = proc_start
            elif platform.system() == "Linux":
                proc_exe, proc_start = _query_linux_process_image(pid)
                if proc_exe:
                    resolved = proc_exe
                if proc_start:
                    actual_start_time = proc_start
            elif platform.system() == "Darwin":
                proc_exe, proc_start = _query_macos_process_image(pid)
                if proc_exe:
                    resolved = proc_exe
                if proc_start:
                    actual_start_time = proc_start


        # 2. Path resolution fallback if child PID inspection did not yield executable
        if not resolved and exe_name:
            # If exe_name is a python interpreter, prefer sys.executable over WindowsApps stub
            exe_clean = exe_name.lower()[:-4] if exe_name.lower().endswith(".exe") else exe_name.lower()
            if (exe_clean in ("python", "python3", "py", "pypy") or exe_clean.startswith("python3.") or exe_clean.startswith("python2.")) and not os.path.isabs(exe_name):
                resolved = sys.executable
            else:
                resolved = shutil.which(exe_name, path=cwd + os.pathsep + os.environ.get("PATH", "")) or ""
                if not resolved and os.path.exists(exe_name):
                    resolved = os.path.abspath(exe_name)

        exe_clean = exe_name.lower()[:-4] if exe_name.lower().endswith(".exe") else exe_name.lower()
        if resolved and "WindowsApps" in resolved and (exe_clean in ("python", "python3", "py", "pypy") or exe_clean.startswith("python3.")):
            resolved = sys.executable


        # 3. Cryptographic executable hashing
        exe_hash = ""
        if resolved and os.path.isfile(resolved):
            try:
                hasher = hashlib.sha256()
                with open(resolved, "rb") as f:
                    while chunk := f.read(65536):
                        hasher.update(chunk)
                exe_hash = hasher.hexdigest()
            except (OSError, PermissionError):
                exe_hash = "unreadable_binary"
                state = ExecutionIdentityState.IDENTITY_UNCERTAIN
        elif resolved and not os.path.isfile(resolved):
            exe_hash = "unreadable_binary"
            state = ExecutionIdentityState.IDENTITY_UNCERTAIN
        else:
            exe_hash = "unresolved_binary"
            state = ExecutionIdentityState.IDENTITY_UNCERTAIN

        # 4. Environment digest
        env_dict = env or os.environ
        critical_keys = sorted(["PATH", "PYTHONPATH", "VIRTUAL_ENV", "NODE_PATH"])
        env_payload = "".join(f"{k}={env_dict.get(k, '')};" for k in critical_keys)
        env_digest = hashlib.sha256(env_payload.encode("utf-8")).hexdigest()

        mode_val = mode.value if isinstance(mode, ExecutionMode) else str(mode)
        start_time_val = actual_start_time or datetime.now(timezone.utc).isoformat()

        # 5. Execution chain
        chain = detect_execution_chain(actual_tokens, resolved)

        # 6. Platform identity and support status
        plat = platform.system()
        if plat in ("Windows", "Linux", "Darwin"):
            if pid and resolved and actual_start_time:
                plat_status = PlatformSupportStatus.SUPPORTED.value
            else:
                plat_status = PlatformSupportStatus.DEGRADED.value
        else:
            plat_status = PlatformSupportStatus.UNSUPPORTED.value

        # 7. UID, GID, authoritative parent chain, and container sandbox identity
        actual_parent_pid = parent_pid or (os.getppid() if hasattr(os, "getppid") else None)
        cur_uid = os.getuid() if hasattr(os, "getuid") else None
        cur_gid = os.getgid() if hasattr(os, "getgid") else None

        target_proc_pid = pid or os.getpid()
        parent_chain_tuple = discover_parent_chain(target_proc_pid, actual_parent_pid)
        container_id = detect_container_sandbox()

        return cls(
            requested_argv=req_tokens,
            actual_argv=actual_tokens,
            executable_name=exe_name,
            executable_path=resolved,
            executable_hash=exe_hash,
            pid=pid or os.getpid(),
            parent_pid=actual_parent_pid,
            ppid=actual_parent_pid,
            uid=cur_uid,
            gid=cur_gid,
            parent_chain=parent_chain_tuple,
            platform=plat,
            container_sandbox_identity=container_id,
            platform_support_status=plat_status,
            process_start_time=start_time_val,
            cwd=os.path.abspath(cwd) if cwd else os.getcwd(),
            environment_digest=env_digest,
            execution_mode=mode_val,
            launcher_identity=launcher_identity,
            wrapper_identity=wrapper_identity,
            identity_state=state.value,
            execution_chain=chain.to_dict(),
        )

    def compute_identity_hash(self) -> str:
        """Computes canonical cryptographic digest over authoritative execution fields."""
        payload = (
            f"{self.executable_path}|{self.executable_hash}|"
            f"{' '.join(self.actual_argv)}|{' '.join(self.requested_argv)}|"
            f"{self.cwd}|{self.environment_digest}|{self.execution_mode}|{self.identity_state}|"
            f"{self.platform}|{self.platform_support_status}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requested_argv": list(self.requested_argv),
            "actual_argv": list(self.actual_argv),
            "executable": self.executable_name,
            "executable_name": self.executable_name,
            "resolved_path": self.executable_path,
            "executable_path": self.executable_path,
            "executable_hash": self.executable_hash,
            "argv": list(self.actual_argv),
            "cwd": self.cwd,
            "environment_digest": self.environment_digest,
            "environment_fingerprint": self.environment_digest,
            "parent_pid": self.parent_pid,
            "ppid": self.ppid or self.parent_pid,
            "pid": self.pid,
            "uid": self.uid,
            "gid": self.gid,
            "parent_chain": list(self.parent_chain),
            "platform": self.platform,
            "container_sandbox_identity": self.container_sandbox_identity,
            "platform_support_status": self.platform_support_status,
            "start_time": self.process_start_time,
            "process_start_time": self.process_start_time,
            "execution_mode": self.execution_mode,
            "launcher_identity": self.launcher_identity,
            "wrapper_identity": self.wrapper_identity,
            "identity_state": self.identity_state,
            "execution_chain": self.execution_chain,
            "identity_hash": self.compute_identity_hash(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExecutionIdentity:
        req_argv = tuple(data.get("requested_argv", data.get("argv", [])))
        act_argv = tuple(data.get("actual_argv", data.get("argv", [])))
        parent_p = data.get("parent_pid", data.get("ppid"))
        return cls(
            requested_argv=req_argv,
            actual_argv=act_argv,
            executable_name=data.get("executable_name", data.get("executable", "")),
            executable_path=data.get("executable_path", data.get("resolved_path", "")),
            executable_hash=data.get("executable_hash", ""),
            pid=data.get("pid"),
            parent_pid=parent_p,
            ppid=data.get("ppid", parent_p),
            uid=data.get("uid"),
            gid=data.get("gid"),
            parent_chain=tuple(data.get("parent_chain", [])),
            platform=data.get("platform", platform.system()),
            container_sandbox_identity=data.get("container_sandbox_identity"),
            platform_support_status=data.get("platform_support_status", PlatformSupportStatus.SUPPORTED.value),
            process_start_time=data.get("process_start_time", data.get("start_time", datetime.now(timezone.utc).isoformat())),
            cwd=data.get("cwd", ""),
            environment_digest=data.get("environment_digest", data.get("environment_fingerprint", "")),
            execution_mode=data.get("execution_mode", ExecutionMode.HOST_ARGV.value),
            launcher_identity=data.get("launcher_identity"),
            wrapper_identity=data.get("wrapper_identity"),
            identity_state=data.get("identity_state", ExecutionIdentityState.IDENTIFIED.value),
            execution_chain=data.get("execution_chain"),
        )
