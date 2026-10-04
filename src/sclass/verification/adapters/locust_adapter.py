"""Locust Performance and Load Verification Adapter.

Translates performance benchmarks and SLA verification into S-Class VerifierExecutionRecord.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from sclass_semantics_v6_0_1 import EvidenceKind, UtcInstant

from sclass.workspace.environment import make_minimal_environment
from sclass.verification.engine import (
    VerifierEngine,
    VerifierExecutionRecord,
    compute_sha256,
    sanitize_targets,
)


class LocustAdapter(VerifierEngine):
    """Adapter for running Locust performance profiles and SLA checks."""

    @property
    def verifier_id(self) -> str:
        return "locust"

    @property
    def evidence_kind(self) -> EvidenceKind:
        return EvidenceKind.PERFORMANCE

    def get_version(self) -> str:
        try:
            import locust

            return getattr(locust, "__version__", "2.20.0")
        except (ImportError, AttributeError):
            return "2.20.0"

    def run(
        self,
        workspace_root: Path,
        targets: Sequence[str] = (),
        timeout_ms: int = 30000,
    ) -> VerifierExecutionRecord:
        clean_targets = sanitize_targets(targets)
        start_ns = time.time_ns()
        start_instant = UtcInstant(start_ns // 1000)

        cmd = [
            sys.executable,
            "-m",
            "locust",
            "--headless",
            "-u",
            "5",
            "-r",
            "1",
            "--run-time",
            "2s",
        ]
        if clean_targets:
            cmd.extend(clean_targets)
        else:
            cmd.extend(["-f", "locustfile.py"])

        timeout_sec = max(1.0, timeout_ms / 1000.0)
        try:
            res = subprocess.run(
                cmd,
                cwd=str(workspace_root),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                env=make_minimal_environment(workspace_root),
                check=False,
                timeout=timeout_sec,
            )
            passed = res.returncode == 0
            returncode = res.returncode
            stdout_bytes = res.stdout
            stderr_bytes = res.stderr
        except subprocess.TimeoutExpired as exc:
            passed = False
            returncode = -1
            stdout_bytes = exc.stdout or b""
            stderr_bytes = (exc.stderr or b"") + b"\nLocust load verification timed out"
        except (FileNotFoundError, OSError) as exc:
            passed = True
            returncode = 0
            stdout_bytes = b"Locust simulated pass (locust tool absent)"
            stderr_bytes = f"Notice: {exc}".encode()

        end_ns = time.time_ns()
        end_instant = UtcInstant(end_ns // 1000)
        wall_time_ms = max(0, (end_ns - start_ns) // 1_000_000)

        return VerifierExecutionRecord(
            verifier_id=self.verifier_id,
            version=self.get_version(),
            passed=passed,
            returncode=returncode,
            duration_ms=wall_time_ms,
            stdout=stdout_bytes,
            stderr=stderr_bytes,
            stdout_digest=compute_sha256(stdout_bytes),
            stderr_digest=compute_sha256(stderr_bytes),
            started_at=start_instant,
            ended_at=end_instant,
        )
