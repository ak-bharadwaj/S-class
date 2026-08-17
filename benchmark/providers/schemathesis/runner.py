"""
S-Class EOS V11.2 - Process-Isolated Schemathesis Provider Runner (D0 Protocol).
Executes Schemathesis inside an isolated subprocess with keyed HMAC-SHA256 challenge-response handshake,
hard process termination on timeout, source revision binding, and multi-layer verifiable hash chains.
Zero external tool or Hypothesis objects cross the process boundary into S-Class memory.
"""

import os
import sys
import time
import json
import uuid
import hmac
import secrets
import hashlib
import subprocess
from typing import Dict, Any, List, Optional, Callable, Union

from .models import (
    ProviderStatus,
    ContractViolation,
    ExecutionStats,
    ProviderExecutionResult,
    WorkerInvocationEnvelope,
    WorkerOutputEnvelope
)
from .version_policy import VersionPolicy
from .parser import SchemathesisParser

PROVIDER_VERSION = "1.0.0"


class SchemathesisRunner:
    """Process-isolated coordinator executing Schemathesis under the D0 Provider Contract."""

    def __init__(self, source_sha: Optional[str] = None, strict_provenance: bool = False):
        if source_sha is None:
            self.source_sha = os.environ.get("GITHUB_SHA", "UNKNOWN")
        else:
            self.source_sha = source_sha
        self.strict_provenance = strict_provenance

    @staticmethod
    def get_authoritative_revision() -> Optional[str]:
        """
        Retrieves the authoritative revision for the current environment:
        1. GITHUB_SHA if running in GitHub Actions CI and well-formed.
        2. Otherwise, current repository HEAD commit via `git rev-parse HEAD`.
        """
        ci_sha = os.environ.get("GITHUB_SHA")
        if ci_sha and ci_sha != "UNKNOWN" and len(ci_sha) == 40:
            try:
                int(ci_sha, 16)
                return ci_sha.lower()
            except ValueError:
                pass

        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                cwd=os.getcwd(),
                timeout=5.0
            )
            if res.returncode == 0:
                head_sha = res.stdout.strip()
                if len(head_sha) == 40:
                    int(head_sha, 16)
                    return head_sha.lower()
        except Exception:
            pass

        return None

    def _verify_source_sha_authenticity(self, sha: Optional[str]) -> bool:
        """
        Validates that a source SHA is well-formed AND strictly matches the authoritative
        revision being certified (CI GITHUB_SHA or current repository HEAD).
        Stale historical commits, uncommitted hashes, and fabricated SHAs fail closed.
        """
        if not sha or sha == "UNKNOWN" or len(sha) != 40:
            return False
        try:
            int(sha, 16)
        except ValueError:
            return False

        auth_rev = self.get_authoritative_revision()
        if not auth_rev:
            return False

        return auth_rev.lower() == sha.lower()

    def _spawn_worker_process(self, cmd: List[str], cwd: str, env: Dict[str, str]) -> subprocess.Popen:
        """Spawns the isolated child worker process."""
        return subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            env=env
        )

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
        # ...

        """
        Executes API contract verification inside an isolated child subprocess under D0 contract.
        Performs keyed HMAC-SHA256 challenge-response handshake and digest chain verification.
        Fail-Closed Invariant: Any anomaly, crash, timeout, replay, forged signature, or missing provenance fails closed.
        """
        execution_id = f"EXEC-ST-{time.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:12].upper()}"
        parent_nonce = secrets.token_hex(32)
        execution_secret = secrets.token_hex(32)
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

        app_module = None
        app_callable = None
        if target_app is not None and callable(target_app):
            app_module = getattr(target_app, "__module__", None)
            app_callable = getattr(target_app, "__name__", None)

        invocation_envelope = WorkerInvocationEnvelope(
            execution_id=execution_id,
            parent_nonce=parent_nonce,
            execution_secret=execution_secret,
            source_sha=self.source_sha,
            provider_version=PROVIDER_VERSION,
            target_identifier=target_identifier,
            target_hash=target_hash,
            config_hash=config_hash,
            schema_dict=schema_dict,
            base_url=base_url,
            app_module=app_module,
            app_callable=app_callable,
            max_examples=max_examples_per_operation
        )
        input_digest = invocation_envelope.input_digest

        def _make_result(
            status: ProviderStatus,
            exit_code: Optional[int],
            violations: List[ContractViolation],
            stats: ExecutionStats,
            diagnostics: List[Dict[str, Any]],
            summary: str,
            st_ver: Optional[str],
            worker_digest: str = "NONE_PRE_EXECUTION",
            worker_hmac: str = "NONE_PRE_EXECUTION"
        ) -> ProviderExecutionResult:
            stop_mono = time.monotonic()
            stop_time_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            duration = round(stop_mono - t_start_mono, 4)
            stats.duration_sec = duration

            return ProviderExecutionResult(
                execution_id=execution_id,
                execution_nonce=parent_nonce,
                provider_version=PROVIDER_VERSION,
                schemathesis_version=st_ver,
                source_sha=self.source_sha,
                schema_hash=schema_hash,
                target_identifier=target_identifier,
                target_hash=target_hash,
                config_hash=config_hash,
                input_digest=input_digest,
                worker_digest=worker_digest,
                worker_hmac=worker_hmac,
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
        if self.strict_provenance and not self._verify_source_sha_authenticity(self.source_sha):
            return _make_result(
                status=ProviderStatus.INPUT_INVALID,
                exit_code=None,
                violations=[],
                stats=ExecutionStats(),
                diagnostics=[{"error": f"Strict provenance requirement failed: source_sha '{self.source_sha}' is not an authoritative 40-character commit SHA."}],
                summary="Execution rejected: Missing or invalid authoritative source SHA under strict certification mode.",
                st_ver=None
            )

        # 2. Dependency Availability & Version Audit
        is_avail, st_ver, err_msg = VersionPolicy.check_environment(require_certified=self.strict_provenance)
        if not is_avail:
            return _make_result(
                status=ProviderStatus.TOOL_NOT_AVAILABLE,
                exit_code=None,
                violations=[],
                stats=ExecutionStats(),
                diagnostics=[{"error": err_msg or "Schemathesis tool is not available"}],
                summary="Execution aborted: Schemathesis is not installed or does not match exact certified version.",
                st_ver=st_ver
            )

        # 3. Input Validation
        if not schema_dict or not isinstance(schema_dict, dict) or not isinstance(schema_dict.get("paths"), dict):
            return _make_result(
                status=ProviderStatus.INPUT_INVALID,
                exit_code=None,
                violations=[],
                stats=ExecutionStats(),
                diagnostics=[{"error": "Invalid or missing OpenAPI schema dictionary: 'paths' must be a dictionary."}],
                summary="Execution rejected: Schema must be a dictionary containing 'paths' mapping.",
                st_ver=st_ver
            )

        # 4. Prepare Subprocess Payload
        payload_str = json.dumps(invocation_envelope.to_dict())

        # 5. Spawn Process-Isolated Worker with Hard Timeout
        cmd = [sys.executable, "-m", "benchmark.providers.schemathesis.worker"]
        env = dict(os.environ)
        cwd = os.getcwd()
        env["PYTHONPATH"] = cwd + os.pathsep + env.get("PYTHONPATH", "")

        proc = None
        try:
            proc = self._spawn_worker_process(cmd=cmd, cwd=cwd, env=env)
            stdout_data, stderr_data = proc.communicate(input=payload_str, timeout=timeout_sec)
        except subprocess.TimeoutExpired:
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

        # 6. Parse and Validate Worker Output Envelope
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

        # 7. Keyed Handshake Verification (Execution ID, Nonce, HMAC signature)
        if not isinstance(parsed_out, dict):
            return _make_result(
                status=ProviderStatus.OUTPUT_INVALID,
                exit_code=proc.returncode,
                violations=[],
                stats=ExecutionStats(),
                diagnostics=[{"error": "Worker output payload is not a JSON object."}],
                summary="Worker output validation failed: Root JSON must be an object.",
                st_ver=st_ver
            )

        # Nonce and Execution ID Verification (Replay / Spoofing Protection)
        resp_exec_id = parsed_out.get("execution_id")
        resp_nonce = parsed_out.get("parent_nonce")
        if resp_exec_id != execution_id:
            return _make_result(
                status=ProviderStatus.OUTPUT_INVALID,
                exit_code=proc.returncode,
                violations=[],
                stats=ExecutionStats(),
                diagnostics=[{"error": f"Execution ID handshake mismatch! Expected '{execution_id}', got '{resp_exec_id}'"}],
                summary="Worker handshake failed: Execution ID mismatch.",
                st_ver=st_ver
            )

        if resp_nonce != parent_nonce:
            return _make_result(
                status=ProviderStatus.OUTPUT_INVALID,
                exit_code=proc.returncode,
                violations=[],
                stats=ExecutionStats(),
                diagnostics=[{"error": "Parent nonce handshake mismatch (replay attack or stale worker output detected)."}],
                summary="Worker handshake failed: Nonce challenge mismatch.",
                st_ver=st_ver
            )

        # Worker Digest Verification
        claimed_worker_digest = parsed_out.get("worker_digest")
        if not claimed_worker_digest:
            return _make_result(
                status=ProviderStatus.OUTPUT_INVALID,
                exit_code=proc.returncode,
                violations=[],
                stats=ExecutionStats(),
                diagnostics=[{"error": "Worker output envelope missing required 'worker_digest' cryptographic proof."}],
                summary="Worker output validation failed: Missing worker digest.",
                st_ver=st_ver
            )

        # Canonical raw payload for verification
        digest_check_payload = {
            "execution_id": parsed_out.get("execution_id"),
            "parent_nonce": parsed_out.get("parent_nonce"),
            "worker_pid": parsed_out.get("worker_pid"),
            "status": parsed_out.get("status"),
            "exit_code": parsed_out.get("exit_code"),
            "violations": parsed_out.get("violations", []),
            "stats": parsed_out.get("stats", {}),
            "diagnostics": parsed_out.get("diagnostics", []),
            "summary": parsed_out.get("summary", "")
        }
        raw_canonical_payload = json.dumps(digest_check_payload, sort_keys=True, default=str)
        recomputed_digest = hashlib.sha256(raw_canonical_payload.encode("utf-8")).hexdigest()
        if claimed_worker_digest != recomputed_digest:
            return _make_result(
                status=ProviderStatus.OUTPUT_INVALID,
                exit_code=proc.returncode,
                violations=[],
                stats=ExecutionStats(),
                diagnostics=[{"error": f"Worker digest mismatch! Claimed: '{claimed_worker_digest}', Computed: '{recomputed_digest}'"}],
                summary="Worker output validation failed: Digest tampering detected.",
                st_ver=st_ver
            )

        # Keyed HMAC Authentication Verification (Guarantees authenticity with parent secret)
        claimed_hmac = parsed_out.get("worker_hmac")
        if not claimed_hmac:
            return _make_result(
                status=ProviderStatus.OUTPUT_INVALID,
                exit_code=proc.returncode,
                violations=[],
                stats=ExecutionStats(),
                diagnostics=[{"error": "Worker output envelope missing required 'worker_hmac' keyed signature."}],
                summary="Worker output validation failed: Missing HMAC signature.",
                st_ver=st_ver
            )

        expected_hmac = hmac.new(execution_secret.encode("utf-8"), raw_canonical_payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(claimed_hmac, expected_hmac):
            return _make_result(
                status=ProviderStatus.OUTPUT_INVALID,
                exit_code=proc.returncode,
                violations=[],
                stats=ExecutionStats(),
                diagnostics=[{"error": f"Worker HMAC cryptographic authentication failure! Claimed: '{claimed_hmac}', Expected: '{expected_hmac}'"}],
                summary="Worker output validation failed: Invalid or forged HMAC signature.",
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
        raw_stats = parsed_out.get("stats", {})
        checks_executed = raw_stats.get("checks_executed", 0)
        violations_count = raw_stats.get("violations_count", len(raw_violations))

        # 8. Independent Semantic & Mathematical Evidence Verification (Parent Authority Boundary)
        # Rule A: Mathematical consistency
        if violations_count != len(raw_violations):
            return _make_result(
                status=ProviderStatus.OUTPUT_INVALID,
                exit_code=proc.returncode,
                violations=[],
                stats=ExecutionStats(),
                diagnostics=[{"error": f"Statistical mismatch: stats.violations_count ({violations_count}) != len(violations) ({len(raw_violations)})"}],
                summary="Worker output validation failed: Mathematical inconsistency in violation count.",
                st_ver=st_ver
            )

        # Rule B: Status vs Evidence consistency
        if status_enum == ProviderStatus.TARGET_CLEAN:
            if len(raw_violations) > 0:
                return _make_result(
                    status=ProviderStatus.OUTPUT_INVALID,
                    exit_code=proc.returncode,
                    violations=[],
                    stats=ExecutionStats(),
                    diagnostics=[{"error": f"Semantic contradiction: status is TARGET_CLEAN but worker provided {len(raw_violations)} violations."}],
                    summary="Worker output validation failed: TARGET_CLEAN contradiction with non-empty violations.",
                    st_ver=st_ver
                )
            if checks_executed == 0:
                return _make_result(
                    status=ProviderStatus.OUTPUT_INVALID,
                    exit_code=proc.returncode,
                    violations=[],
                    stats=ExecutionStats(),
                    diagnostics=[{"error": "Semantic contradiction: status is TARGET_CLEAN but checks_executed is 0."}],
                    summary="Worker output validation failed: TARGET_CLEAN contradiction with 0 checks.",
                    st_ver=st_ver
                )
            if exit_code != 0:
                return _make_result(
                    status=ProviderStatus.OUTPUT_INVALID,
                    exit_code=proc.returncode,
                    violations=[],
                    stats=ExecutionStats(),
                    diagnostics=[{"error": f"Exit code contradiction: status is TARGET_CLEAN but exit code is {exit_code}."}],
                    summary="Worker output validation failed: Non-zero exit code on TARGET_CLEAN.",
                    st_ver=st_ver
                )

        elif status_enum == ProviderStatus.TARGET_CONTRACT_VIOLATED:
            if len(raw_violations) == 0:
                return _make_result(
                    status=ProviderStatus.OUTPUT_INVALID,
                    exit_code=proc.returncode,
                    violations=[],
                    stats=ExecutionStats(),
                    diagnostics=[{"error": "Semantic contradiction: status is TARGET_CONTRACT_VIOLATED but violations list is empty."}],
                    summary="Worker output validation failed: TARGET_CONTRACT_VIOLATED contradiction with empty violations.",
                    st_ver=st_ver
                )

        # Rule C: Authoritative Schema Scope & Path Conformance
        if schema_dict and isinstance(schema_dict.get("paths"), dict):
            valid_paths = set(schema_dict["paths"].keys())
            for v_entry in raw_violations:
                v_path = v_entry.get("path")
                if v_path and v_path != "unknown" and v_path not in valid_paths:
                    return _make_result(
                        status=ProviderStatus.OUTPUT_INVALID,
                        exit_code=proc.returncode,
                        violations=[],
                        stats=ExecutionStats(),
                        diagnostics=[{"error": f"Scope violation: Reported violation path '{v_path}' does not exist in authoritative schema."}],
                        summary="Worker output validation failed: Fabricated or unknown endpoint path.",
                        st_ver=st_ver
                    )

        violations = [SchemathesisParser.parse_raw_failure_entry(v) for v in raw_violations]

        stats = ExecutionStats(
            endpoints_tested=raw_stats.get("endpoints_tested", 0),
            operations_tested=raw_stats.get("operations_tested", 0),
            checks_executed=checks_executed,
            violations_count=len(violations),
            duration_sec=raw_stats.get("duration_sec", 0.0)
        )

        diagnostics = parsed_out.get("diagnostics", [])
        diagnostics.append({
            "worker_pid": parsed_out.get("worker_pid"),
            "parent_pid": os.getpid(),
            "handshake_verified": True,
            "hmac_verified": True,
            "semantic_consistency_verified": True
        })
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
            st_ver=st_ver,
            worker_digest=claimed_worker_digest,
            worker_hmac=claimed_hmac
        )
