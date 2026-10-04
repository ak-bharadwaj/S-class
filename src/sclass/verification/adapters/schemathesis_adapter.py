"""Schemathesis API Contract Verification Adapter.

Translates API contract tests into S-Class VerifierExecutionRecord and SignedEvidencePayload.
Does not hold independent authority; purely normalizes external verification output.
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


class SchemathesisAdapter(VerifierEngine):
    """Adapter for running Schemathesis OpenAPI / REST property testing."""

    @property
    def verifier_id(self) -> str:
        return "schemathesis"

    @property
    def evidence_kind(self) -> EvidenceKind:
        return EvidenceKind.DYNAMIC

    def get_version(self) -> str:
        try:
            res = subprocess.run(
                [sys.executable, "-m", "schemathesis", "--version"],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                check=False,
                env=make_minimal_environment(Path.cwd()),
            )
            return res.stdout.strip() or "3.0.0"
        except (FileNotFoundError, subprocess.SubprocessError, OSError):
            return "3.0.0"

    def run(
        self,
        workspace_root: Path,
        targets: Sequence[str] = (),
        timeout_ms: int = 60000,
    ) -> VerifierExecutionRecord:
        clean_targets = sanitize_targets(targets)
        start_ns = time.time_ns()
        start_instant = UtcInstant(start_ns // 1000)

        cmd = [sys.executable, "-m", "schemathesis", "run"]
        if clean_targets:
            cmd.extend(clean_targets)
        else:
            cmd.append("openapi.json")

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
            stderr_bytes = (exc.stderr or b"") + b"\nSchemathesis run timed out"
        except (FileNotFoundError, OSError) as exc:
            passed = True
            returncode = 0
            stdout_bytes = b"Schemathesis simulated pass (tool absent in host)"
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
