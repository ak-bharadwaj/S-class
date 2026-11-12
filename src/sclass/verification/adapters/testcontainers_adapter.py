"""Testcontainers Integration Verification Adapter.

Executes integration suites relying on ephemeral containerized dependencies
and normalizes outputs into S-Class VerifierExecutionRecord.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from sclass_semantics_v6_0_1 import EvidenceKind, UtcInstant

from sclass.workspace.environment import make_minimal_environment
from sclass.verification.adapters.contract import validate_adapter_structured_output
from sclass.verification.engine import (
    VerifierEngine,
    VerifierExecutionRecord,
    compute_sha256,
    sanitize_targets,
)


class TestcontainersAdapter(VerifierEngine):
    """Adapter for running Docker-backed integration test suites via pytest-testcontainers."""

    @property
    def verifier_id(self) -> str:
        return "testcontainers"

    @property
    def evidence_kind(self) -> EvidenceKind:
        return EvidenceKind.DYNAMIC

    def get_version(self) -> str:
        try:
            import testcontainers

            return getattr(testcontainers, "__version__", "4.0.0")
        except (ImportError, AttributeError):
            return "4.0.0"

    def validate_structured_output(self, stdout: bytes, stderr: bytes) -> tuple[bool, str]:
        """Validates verifier output against the Testcontainers structured-result contract (D8)."""
        return validate_adapter_structured_output(self.verifier_id, stdout, stderr)

    def run(
        self,
        workspace_root: Path,
        targets: Sequence[str] = (),
        timeout_ms: int = 120000,
    ) -> VerifierExecutionRecord:
        clean_targets = sanitize_targets(targets)
        start_ns = time.time_ns()
        start_instant = UtcInstant(start_ns // 1000)

        cmd = [sys.executable, "-m", "pytest", "-q", "-m", "integration"]
        if clean_targets:
            cmd.extend(clean_targets)

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
            stdout_bytes = res.stdout or b""
            stderr_bytes = res.stderr or b""
            if res.returncode == 0:
                valid, err_msg = self.validate_structured_output(stdout_bytes, stderr_bytes)
                if not valid:
                    passed = False
                    returncode = -2
                    stderr_bytes = stderr_bytes + f"\nBLOCKED: Malformed output detected: {err_msg}".encode("utf-8")
                else:
                    passed = True
                    returncode = 0
            elif res.returncode == 5:
                # No tests collected: unverifiable result, never pass
                passed = False
                returncode = 5
                stderr_bytes = stderr_bytes + b"\nUNAVAILABLE: No tests collected (exit code 5)"
            else:
                passed = False
                returncode = res.returncode
                if res.returncode < 0:
                    stderr_bytes = stderr_bytes + f"\nBLOCKED: Testcontainers process terminated by signal {-res.returncode}".encode()
        except subprocess.TimeoutExpired as exc:
            passed = False
            returncode = -1
            stdout_bytes = exc.stdout or b""
            stderr_bytes = (exc.stderr or b"") + b"\nBLOCKED: Testcontainers verification timed out"
        except (FileNotFoundError, OSError) as exc:
            passed = False
            returncode = 127
            stdout_bytes = b""
            stderr_bytes = f"UNAVAILABLE: Testcontainers tool binary not found: {exc}".encode()

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
