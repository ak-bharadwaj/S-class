"""
S-Class EOS V11.2 - Process-Isolated Schemathesis Provider Runner.
Executes Schemathesis inside an isolated subprocess with hard process termination on timeout.
Zero external tool or Hypothesis objects cross the process boundary into S-Class memory.
"""

import os
import sys
import time
import json
import uuid
import hashlib
import subprocess
from typing import Dict, Any, List, Optional, Callable, Union

from .models import (
    ProviderStatus,
    ContractViolation,
    ExecutionStats,
    ProviderExecutionResult
)
from .version_policy import VersionPolicy
from .parser import SchemathesisParser

PROVIDER_VERSION = "1.0.0"


class SchemathesisRunner:
    """Process-isolated coordinator executing Schemathesis in a separate child process."""

    def __init__(self, source_sha: Optional[str] = None, strict_provenance: bool = False):
        if source_sha is None:
            self.source_sha = os.environ.get("GITHUB_SHA", "UNKNOWN")
        else:
            self.source_sha = source_sha
        self.strict_provenance = strict_provenance

    def execute(
        self,
        schema_dict: Optional[Dict[str, Any]],
        target_app: Optional[Any] = None,
        base_url: Optional[str] = None,
        target_identifier: str = "openapi_target",
        max_examples_per_operation: int = 5,
        checks: Optional[List[str]] = None,
        timeout_sec: float = 30.0
    ) -> ProviderExecutionResult:
        """
        Executes API contract verification inside an isolated child subprocess.
        Hard timeout terminates the worker process.
        Fail-Closed Invariant: Any anomaly, crash, timeout, or missing provenance fails closed.
        """
        execution_id = f"EXEC-SCHEMATHESIS-{uuid.uuid4().hex[:12].upper()}"
        t_start_mono = time.monotonic()
        start_time_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # Config hash
        config_payload = {
            "max_examples_per_operation": max_examples_per_operation,
            "checks": checks or ["not_a_server_error", "status_code_conformance", "content_type_conformance"],
            "timeout_sec": timeout_sec
        }
        config_hash = hashlib.sha256(json.dumps(config_payload, sort_keys=True).encode("utf-8")).hexdigest()

        # Schema & target hashes
        if schema_dict and isinstance(schema_dict, dict):
            raw_schema = json.dumps(schema_dict, sort_keys=True, default=str)
            schema_hash = hashlib.sha256(raw_schema.encode("utf-8")).hexdigest()
        else:
            schema_hash = "NONE"

        target_hash = hashlib.sha256(str(target_app or base_url or target_identifier).encode("utf-8")).hexdigest()

        def _make_result(
            status: ProviderStatus,
            exit_code: Optional[int],
            violations: List[ContractViolation],
            stats: ExecutionStats,
            diagnostics: List[Dict[str, Any]],
            summary: str,
            st_ver: Optional[str]
        ) -> ProviderExecutionResult:
            stop_mono = time.monotonic()
            stop_time_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            duration = round(stop_mono - t_start_mono, 4)
            stats.duration_sec = duration

            return ProviderExecutionResult(
                execution_id=execution_id,
                provider_version=PROVIDER_VERSION,
                schemathesis_version=st_ver,
                source_sha=self.source_sha,
                schema_hash=schema_hash,
                target_identifier=target_identifier,
                target_hash=target_hash,
                config_hash=config_hash,
                status=status,
                exit_code=exit_code,
                start_time_iso=start_time_iso,
                stop_time_iso=stop_time_iso,
                duration_sec=duration,
                violations=violations,
                stats=stats,
                diagnostics=diagnostics,
                raw_output_summary=summary
            )

        # 1. Strict Provenance Check
        if self.strict_provenance and (not self.source_sha or self.source_sha == "UNKNOWN"):
            return _make_result(
                status=ProviderStatus.INPUT_INVALID,
                exit_code=None,
                violations=[],
                stats=ExecutionStats(),
                diagnostics=[{"error": "Strict provenance requirement failed: source_sha is missing or UNKNOWN"}],
                summary="Execution rejected: Missing authoritative source SHA under strict certification mode.",
                st_ver=None
            )

        # 2. Dependency Availability & Version Audit
        is_avail, st_ver, err_msg = VersionPolicy.check_environment()
        if not is_avail:
            return _make_result(
                status=ProviderStatus.TOOL_NOT_AVAILABLE,
                exit_code=None,
                violations=[],
                stats=ExecutionStats(),
                diagnostics=[{"error": err_msg or "Schemathesis tool is not available"}],
                summary="Execution aborted: Schemathesis is not installed or incompatible with pinned version spec.",
                st_ver=st_ver
            )

        # 3. Input Validation
        if not schema_dict or not isinstance(schema_dict, dict) or not schema_dict.get("paths"):
            return _make_result(
                status=ProviderStatus.INPUT_INVALID,
                exit_code=None,
                violations=[],
                stats=ExecutionStats(),
                diagnostics=[{"error": "Invalid or missing OpenAPI schema dictionary."}],
                summary="Execution rejected: Schema must be a dictionary containing 'paths'.",
                st_ver=st_ver
            )

        # 4. Prepare Subprocess Payload
        app_module = None
        app_callable = None
        if target_app is not None and callable(target_app):
            app_module = getattr(target_app, "__module__", None)
            app_callable = getattr(target_app, "__name__", None)

        worker_payload = {
            "schema_dict": schema_dict,
            "base_url": base_url,
            "app_module": app_module,
            "app_callable": app_callable,
            "max_examples": max_examples_per_operation
        }
        payload_str = json.dumps(worker_payload)

        # 5. Spawn Process-Isolated Worker with Hard Timeout
        cmd = [sys.executable, "-m", "benchmark.providers.schemathesis.worker"]
        env = dict(os.environ)
        # Ensure project root is in PYTHONPATH
        cwd = os.getcwd()
        env["PYTHONPATH"] = cwd + os.pathsep + env.get("PYTHONPATH", "")

        proc = None
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=cwd,
                env=env
            )
            stdout_data, stderr_data = proc.communicate(input=payload_str, timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            # Real hard timeout: forcibly kill the child process
            if proc:
                try:
                    proc.kill()
                    stdout_data, stderr_data = proc.communicate()
                except Exception:
                    pass
            return _make_result(
                status=ProviderStatus.TIMEOUT,
                exit_code=124,
                violations=[],
                stats=ExecutionStats(),
                diagnostics=[{"error": f"Worker process exceeded hard timeout limit of {timeout_sec}s and was terminated."}],
                summary=f"Execution timed out: Worker process killed after {timeout_sec}s.",
                st_ver=st_ver
            )
        except Exception as spawn_err:
            return _make_result(
                status=ProviderStatus.TOOL_EXECUTION_FAILED,
                exit_code=1,
                violations=[],
                stats=ExecutionStats(),
                diagnostics=[{"error": f"Failed to spawn isolated worker process: {type(spawn_err).__name__}: {str(spawn_err)}"}],
                summary=f"Worker spawn failure: {str(spawn_err)}",
                st_ver=st_ver
            )

        # 6. Parse and Validate Worker Output
        raw_out = stdout_data.strip()
        if not raw_out:
            return _make_result(
                status=ProviderStatus.TOOL_EXECUTION_FAILED,
                exit_code=proc.returncode if proc else 1,
                violations=[],
                stats=ExecutionStats(),
                diagnostics=[{
                    "error": "Worker process produced empty stdout.",
                    "stderr": stderr_data[:500] if stderr_data else ""
                }],
                summary=f"Worker crashed with exit code {proc.returncode if proc else 1}.",
                st_ver=st_ver
            )

        try:
            parsed_out = json.loads(raw_out)
        except json.JSONDecodeError as json_err:
            return _make_result(
                status=ProviderStatus.OUTPUT_INVALID,
                exit_code=proc.returncode,
                violations=[],
                stats=ExecutionStats(),
                diagnostics=[{
                    "error": f"Worker stdout is not valid JSON: {str(json_err)}",
                    "raw_stdout_sample": raw_out[:300],
                    "stderr": stderr_data[:300] if stderr_data else ""
                }],
                summary="Worker output validation failed: Non-JSON stdout received.",
                st_ver=st_ver
            )

        # Validate structure of JSON report
        if not isinstance(parsed_out, dict) or "status" not in parsed_out:
            return _make_result(
                status=ProviderStatus.OUTPUT_INVALID,
                exit_code=proc.returncode,
                violations=[],
                stats=ExecutionStats(),
                diagnostics=[{"error": "Worker JSON output missing required 'status' attribute."}],
                summary="Worker output validation failed: Incomplete JSON report.",
                st_ver=st_ver
            )

        # Extract normalized fields
        status_str = parsed_out.get("status", "TOOL_OUTPUT_INVALID")
        try:
            status_enum = ProviderStatus(status_str)
        except ValueError:
            status_enum = ProviderStatus.OUTPUT_INVALID

        exit_code = parsed_out.get("exit_code", proc.returncode)

        raw_violations = parsed_out.get("violations", [])
        violations = [SchemathesisParser.parse_raw_failure_entry(v) for v in raw_violations]

        raw_stats = parsed_out.get("stats", {})
        stats = ExecutionStats(
            endpoints_tested=raw_stats.get("endpoints_tested", 0),
            operations_tested=raw_stats.get("operations_tested", 0),
            checks_executed=raw_stats.get("checks_executed", 0),
            violations_count=len(violations),
            duration_sec=raw_stats.get("duration_sec", 0.0)
        )

        diagnostics = parsed_out.get("diagnostics", [])
        if stderr_data.strip():
            diagnostics.append({"worker_stderr_sample": stderr_data[:500]})

        summary = parsed_out.get("summary", f"Worker execution finished with status {status_enum.value}")

        return _make_result(
            status=status_enum,
            exit_code=exit_code,
            violations=violations,
            stats=stats,
            diagnostics=diagnostics,
            summary=summary,
            st_ver=st_ver
        )
