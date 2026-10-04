"""Test-only unsandboxed execution boundary.

EXPLICIT TEST COMPONENT ONLY.
Never exported or bundled in shipped code. Injected via explicit constructor parameters.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from sclass_runtime_v6_0_1 import (
    BoundaryContext,
    BoundaryIsolation,
    BoundaryRunResult,
    Digest,
    IdentityCheckResult,
    IsolationLevel,
    LocalWorkspaceSnapshotHandle,
    ProcessLineageEntry,
    ResourceBudget,
    digest,
)


class TestOnlyUnsandboxedBoundary:
    """Explicit test-only unsandboxed execution boundary.

    Injected through explicit constructor parameters in test fixtures.
    """

    __test__ = False

    def __init__(self, workspace: str | Path, require_sandbox: bool = False):
        self.workspace = Path(workspace).resolve()
        if not self.workspace.exists() or not self.workspace.is_dir():
            raise ValueError("workspace must be an existing directory")
        self._gate_capability = object()
        self._active_pids: set[int] = set()
        self.bwrap = None

    def run(self, argv: Sequence[str], **kwargs: Any) -> BoundaryRunResult:
        """Raw execution outside ExecutionGate fails closed."""
        raise PermissionError("raw OS execution is not a production API; route execution through ExecutionGate")

    def run_for_test(self, argv: Sequence[str], **kwargs: Any) -> BoundaryRunResult:
        """Explicit test entry delegating to _run_from_gate."""
        return self._run_from_gate(self._gate_capability, argv, **kwargs)

    @staticmethod
    def _executable_path(argv0: str) -> Path:
        if argv0 in ("python", "python3", "python.exe") and sys.executable:
            return Path(sys.executable).resolve()
        resolved = shutil.which(argv0) or argv0
        p = Path(resolved).resolve()
        if not p.exists() or not p.is_file():
            raise FileNotFoundError(argv0)
        return p

    @staticmethod
    def _file_digest(path: Path) -> Digest:
        import hashlib
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return Digest("sha256:" + h.hexdigest())

    @staticmethod
    def _proc_start_time_ns(pid: int) -> Optional[int]:
        try:
            stat = Path(f"/proc/{pid}/stat").read_text()
            after = stat.rsplit(") ", 1)[1].split()
            start_ticks = int(after[19])
            clk = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
            btime = None
            for line in Path("/proc/stat").read_text().splitlines():
                if line.startswith("btime "):
                    btime = int(line.split()[1])
                    break
            if btime is None or clk <= 0:
                return None
            return btime * 1_000_000_000 + (start_ticks * 1_000_000_000) // clk
        except (OSError, ValueError, IndexError, KeyError):
            return None

    def _snapshot_tree(self, root_pid: int) -> tuple[ProcessLineageEntry, ...]:
        rows = []
        proc_dir = Path("/proc")
        if not proc_dir.exists():
            return ()
        table = {}
        for p in proc_dir.iterdir():
            if not p.name.isdigit():
                continue
            try:
                stat = Path(f"/proc/{p.name}/stat").read_text()
                after = stat.rsplit(") ", 1)[1].split()
                ppid = int(after[1])
                table[int(p.name)] = (ppid,)
            except (OSError, ValueError, IndexError):
                continue
        seen = {root_pid}
        queue = [root_pid]
        while queue:
            pid = queue.pop(0)
            try:
                exe_path = Path(os.readlink(f"/proc/{pid}/exe")).resolve()
                exe_digest = self._file_digest(exe_path)
                cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\x00")[:-1]
                argv_digest = digest("sclass/argv/v1", tuple(x.decode("utf-8", "replace") for x in cmdline))
                start_ns = self._proc_start_time_ns(pid) or 0
                rows.append(ProcessLineageEntry(pid, start_ns, exe_digest, argv_digest))
            except (OSError, ValueError):
                pass
            for child, (ppid,) in table.items():
                if ppid == pid and child not in seen:
                    seen.add(child)
                    queue.append(child)
        return tuple(sorted(rows, key=lambda x: (x.pid, x.start_time_ns)))

    def _run_from_gate(
        self,
        capability: object,
        argv: Sequence[str],
        *,
        allow_write: bool = False,
        allow_network: bool = False,
        env: Optional[Mapping[str, str]] = None,
        timeout_ms: int = 30_000,
        max_output_bytes: int = 1_000_000,
        budget: Optional[ResourceBudget] = None,
        expected_executable_digest: Optional[Digest] = None,
        write_paths: Sequence[str] = (),
        filesystem_accesses: Sequence[Any] = (),
    ) -> BoundaryRunResult:
        if capability is not self._gate_capability:
            raise PermissionError("OS execution is callable only through ExecutionGate")
        if timeout_ms < 1 or max_output_bytes < 1:
            raise ValueError("invalid execution limits")

        exe = self._executable_path(argv[0])
        exe_digest = self._file_digest(exe)
        if expected_executable_digest is not None and exe_digest != expected_executable_digest:
            raise PermissionError("resolved executable digest does not match authorized execution identity")
        argv_digest = digest("sclass/argv/v1", tuple(argv))

        from sclass.workspace.environment import make_minimal_environment

        run_env = make_minimal_environment(self.workspace, extra=env)

        start = time.monotonic()
        timed = False
        proc = None
        start_ns = time.time_ns()
        out = b""
        err = b""
        observed_lineage = ()
        try:
            proc = subprocess.Popen(
                [str(exe)] + list(argv[1:]),
                cwd=str(self.workspace),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=run_env,
            )
            self._active_pids.add(proc.pid)
            start_ns = self._proc_start_time_ns(proc.pid) or start_ns
            observed_lineage = (ProcessLineageEntry(proc.pid, start_ns, exe_digest, argv_digest),)

            # Deterministic process tree monitoring while running and upon completion
            if Path("/proc").exists():
                deadline = time.monotonic() + (timeout_ms / 1000.0)
                while True:
                    tree = self._snapshot_tree(proc.pid)
                    if tree:
                        observed_lineage = tuple({(x.pid, x.start_time_ns): x for x in observed_lineage + tree}.values())
                    if expected_executable_digest is not None:
                        for entry in observed_lineage:
                            if entry.executable_digest != expected_executable_digest:
                                try:
                                    for t_entry in self._snapshot_tree(proc.pid):
                                        try: os.kill(t_entry.pid, signal.SIGKILL)
                                        except OSError: pass
                                except Exception:
                                    pass
                                proc.kill()
                                proc.wait()
                                raise PermissionError("running executable identity does not match authorized digest")
                    if proc.poll() is not None:
                        break
                    if time.monotonic() >= deadline:
                        timed = True
                        proc.kill()
                        proc.wait()
                        break
                    time.sleep(0.002)

                # Final snapshot check
                final_tree = self._snapshot_tree(proc.pid)
                if final_tree:
                    observed_lineage = tuple({(x.pid, x.start_time_ns): x for x in observed_lineage + final_tree}.values())
                if expected_executable_digest is not None:
                    for entry in observed_lineage:
                        if entry.executable_digest != expected_executable_digest:
                            proc.kill()
                            proc.wait()
                            raise PermissionError("running executable identity does not match authorized digest")

            try:
                out, err = proc.communicate(timeout=max(0.1, timeout_ms / 1000.0))
            except subprocess.TimeoutExpired:
                proc.kill()
                out, err = proc.communicate()
                timed = True
        finally:
            if proc is not None:
                self._active_pids.discard(proc.pid)

        dur = int((time.monotonic() - start) * 1000)
        return BoundaryRunResult(
            BoundaryIsolation.DENY,
            proc.returncode if proc is not None else -1,
            (out or b"")[:max_output_bytes],
            (err or b"")[:max_output_bytes],
            timed,
            dur,
            exe_digest,
            argv_digest,
            proc.pid if proc is not None else None,
            start_ns,
            len(out or b""),
            len(err or b""),
            observed_lineage,
        )

    def enter(self, request: Any, handle: LocalWorkspaceSnapshotHandle) -> BoundaryContext:
        if handle.fencing_token != request.execution_lease.fencing_token:
            raise PermissionError("workspace handle fencing token mismatch")
        if handle.workspace_id != request.execution_lease.workspace_id or handle.snapshot_id != request.execution_lease.workspace_snapshot_id:
            raise PermissionError("workspace snapshot binding mismatch")
        if handle.verify_identity() is not IdentityCheckResult.MATCH:
            raise PermissionError("workspace handle identity is not stable")
        from sclass_runtime_v6_0_1 import _stable_id
        return BoundaryContext(
            _stable_id("boundary", (request.execution_lease.lease_id, handle.handle_id)),
            IsolationLevel.PROCESS,
            handle.handle_id,
            request.execution_lease.fencing_token,
        )

    def exit(self, ctx: BoundaryContext) -> None:
        if not ctx.boundary_id:
            raise ValueError("invalid boundary context")


def create_test_quiescence_attestor(keys: Any) -> Any:
    """Explicit test-only quiescence attestor factory.

    Constructs a test attestor with _test_only=True and
    is_production_provisioned() == False, ensuring test authority
    remains strictly distinguishable from production authority.
    """
    import secrets
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from sclass_runtime_v6_0_1 import LocalQuiescenceAttestor, _BOUNDARY_TEST_TOKEN

    root = "sclass-test-boundary-root"
    key_id = f"test-boundary-{secrets.token_hex(8)}"
    priv = Ed25519PrivateKey.generate()
    from cryptography.hazmat.primitives import serialization
    keys.add_root(root)
    pub = priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    keys.register(key_id, root, pub, 0, 2**63 - 1)
    return LocalQuiescenceAttestor(
        keys,
        root,
        key_id,
        priv,
        _provisioning_token=_BOUNDARY_TEST_TOKEN,
    )
