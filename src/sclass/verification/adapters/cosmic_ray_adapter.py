"""Cosmic Ray Mutation Testing Verification Adapter.

Translates mutation testing runs into S-Class VerifierExecutionRecord and SignedEvidencePayload.
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
from sclass.verification.engine import (
    VerifierEngine,
    VerifierExecutionRecord,
    compute_sha256,
    sanitize_targets,
)


class CosmicRayAdapter(VerifierEngine):
    """Adapter for running Cosmic Ray mutation testing."""

    @property
    def verifier_id(self) -> str:
        return "cosmic-ray"

    @property
    def evidence_kind(self) -> EvidenceKind:
        return EvidenceKind.METAMORPHIC

    def get_version(self) -> str:
        try:
            import cosmic_ray

            return getattr(cosmic_ray, "__version__", "8.3.5")
        except (ImportError, AttributeError):
            return "8.3.5"

    def validate_structured_output(self, stdout: bytes, stderr: bytes) -> tuple[bool, str]:
        """Validates verifier output against the Cosmic Ray structured-result contract (D8)."""
        if not stdout or not stdout.strip():
            return False, "Empty verifier output with exit code zero (missing evidence)"

        if b"Traceback (most recent call last)" in stderr:
            return False, "Traceback detected in verifier stderr"
        if b"INTERNALERROR" in stdout:
            return False, "INTERNALERROR detected in verifier stdout"
        if b"MALFORMED:" in stdout.upper() or b"CORRUPTED:" in stdout.upper():
            return False, "Malformed or corrupted marker in verifier stream"

        text = stdout.decode("utf-8", errors="replace").strip()
        if text.startswith("{") or text.startswith("["):
            try:
                data = json.loads(text)
                if isinstance(data, dict):
                    if (
                        data.get("tool") == "cosmic-ray"
                        or "mutation_score" in data
                        or "survival_rate" in data
                        or "passed" in data
                        or data.get("status") in ("passed", "ok", "success")
                    ):
                        return True, ""
                elif isinstance(data, list) and data:
                    return True, ""
            except json.JSONDecodeError:
                pass

        cosmic_patterns = (
            r"(mutation\s+score|killed:\s*\d+|survival\s+rate|"
            r"\[cosmic-ray\]\s+summary|cosmic-ray verification passed)"
        )
        if re.search(cosmic_patterns, text, re.IGNORECASE):
            return True, ""

        return False, "Output failed cosmic-ray structured contract validation (unstructured or missing required mutation summary fields)"

    def run(
        self,
        workspace_root: Path,
        targets: Sequence[str] = (),
        timeout_ms: int = 120000,
    ) -> VerifierExecutionRecord:
        clean_targets = sanitize_targets(targets)
        start_ns = time.time_ns()
        start_instant = UtcInstant(start_ns // 1000)

        cmd = [sys.executable, "tools/run_cr.py"]
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
            else:
                passed = False
                returncode = res.returncode
                if res.returncode < 0:
                    stderr_bytes = stderr_bytes + f"\nBLOCKED: Cosmic Ray process terminated by signal {-res.returncode}".encode()
        except subprocess.TimeoutExpired as exc:
            passed = False
            returncode = -1
            stdout_bytes = exc.stdout or b""
            stderr_bytes = (exc.stderr or b"") + b"\nBLOCKED: Cosmic Ray mutation testing timed out"
        except (FileNotFoundError, OSError) as exc:
            passed = False
            returncode = 127
            stdout_bytes = b""
            stderr_bytes = f"UNAVAILABLE: Cosmic Ray tool binary not found: {exc}".encode()

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
