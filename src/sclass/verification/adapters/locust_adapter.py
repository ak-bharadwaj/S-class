"""Locust Performance and Load Verification Adapter.

Translates performance benchmarks and SLA verification into S-Class VerifierExecutionRecord.
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

    def validate_structured_output(self, stdout: bytes, stderr: bytes) -> tuple[bool, str]:
        """Validates verifier output against the Locust structured-result contract (D8)."""
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
                        data.get("tool") == "locust"
                        or "total_requests" in data
                        or "requests" in data
                        or "num_requests" in data
                        or data.get("status") in ("passed", "ok", "success")
                    ):
                        return True, ""
                elif isinstance(data, list) and data:
                    return True, ""
            except json.JSONDecodeError:
                pass

        locust_patterns = (
            r"(Aggregated|Type\s+Name\s+#\s*reqs|Total\s+Requests:\s*\d+|"
            r"\[locust\]\s+summary|locust verification passed)"
        )
        if re.search(locust_patterns, text, re.IGNORECASE):
            return True, ""

        return False, "Output failed locust structured contract validation (unstructured or missing required summary fields)"

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
                    stderr_bytes = stderr_bytes + f"\nBLOCKED: Locust process terminated by signal {-res.returncode}".encode()
        except subprocess.TimeoutExpired as exc:
            passed = False
            returncode = -1
            stdout_bytes = exc.stdout or b""
            stderr_bytes = (exc.stderr or b"") + b"\nBLOCKED: Locust load verification timed out"
        except (FileNotFoundError, OSError) as exc:
            passed = False
            returncode = 127
            stdout_bytes = b""
            stderr_bytes = f"UNAVAILABLE: Locust tool binary not found: {exc}".encode()

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
