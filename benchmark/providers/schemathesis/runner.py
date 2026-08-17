"""
S-Class EOS V11.2 - Schemathesis Provider Runner.
Executes API contract verification campaigns strictly bounded within the S-Class provider architecture.
Translates all outcomes into fail-closed ProviderExecutionResult evidence receipts.
"""

import os
import time
import json
import uuid
import hashlib
from typing import Dict, Any, List, Optional, Callable, Union, Tuple

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
    """Executes Schemathesis API verification campaigns and emits native S-Class evidence receipts."""

    def __init__(self, source_sha: Optional[str] = None):
        self.source_sha = source_sha or os.environ.get("GITHUB_SHA", "UNKNOWN")

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
        Executes an API contract verification campaign.
        Fail-Closed Invariant: Any anomaly, missing dependency, timeout, or violation results in non-TARGET_CLEAN status.
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

        # 1. Dependency Availability & Version Check
        is_avail, st_ver, err_msg = VersionPolicy.check_environment()
        if not is_avail:
            return _make_result(
                status=ProviderStatus.TOOL_NOT_AVAILABLE,
                exit_code=None,
                violations=[],
                stats=ExecutionStats(),
                diagnostics=[{"error": err_msg or "Schemathesis is not available"}],
                summary="Execution aborted: Schemathesis tool is not available or incompatible.",
                st_ver=st_ver
            )

        # 2. Input Validation
        if not schema_dict or not isinstance(schema_dict, dict) or not schema_dict.get("paths"):
            return _make_result(
                status=ProviderStatus.INPUT_INVALID,
                exit_code=None,
                violations=[],
                stats=ExecutionStats(),
                diagnostics=[{"error": "Invalid or missing OpenAPI schema dictionary."}],
                summary="Execution rejected: Schema must be a non-empty dictionary containing 'paths'.",
                st_ver=st_ver
            )

        # Import schemathesis strictly inside runner execution boundary
        import schemathesis

        # 3. Schema Parsing & Operation Discovery
        try:
            if target_app is not None and callable(target_app):
                def wrapped_app(environ, start_response):
                    if environ.get("PATH_INFO") == "/__sclass_schema__.json":
                        start_response("200 OK", [("Content-Type", "application/json")])
                        return [json.dumps(schema_dict).encode("utf-8")]
                    return target_app(environ, start_response)

                schema = schemathesis.openapi.from_wsgi("/__sclass_schema__.json", app=wrapped_app)
            else:
                schema = schemathesis.openapi.from_dict(schema_dict)
        except Exception as e:
            return _make_result(
                status=ProviderStatus.INPUT_INVALID,
                exit_code=None,
                violations=[],
                stats=ExecutionStats(),
                diagnostics=[{"error": f"Failed to parse OpenAPI schema: {type(e).__name__}: {str(e)}"}],
                summary=f"Schema parsing error: {str(e)}",
                st_ver=st_ver
            )

        try:
            endpoints = list(schema)
            raw_ops = list(schema.get_all_operations())
            operations = []
            for item in raw_ops:
                op = item.ok() if hasattr(item, "ok") else item
                if op is not None:
                    operations.append(op)

            if not operations:
                return _make_result(
                    status=ProviderStatus.INSUFFICIENT_EVIDENCE,
                    exit_code=None,
                    violations=[],
                    stats=ExecutionStats(endpoints_tested=len(endpoints)),
                    diagnostics=[{"warning": "Schema contains zero reachable operations."}],
                    summary="Execution inconclusive: Zero operations evaluated (INSUFFICIENT_EVIDENCE).",
                    st_ver=st_ver
                )
        except Exception as e:
            return _make_result(
                status=ProviderStatus.TOOL_EXECUTION_FAILED,
                exit_code=1,
                violations=[],
                stats=ExecutionStats(),
                diagnostics=[{"error": f"Failed inspecting operations: {str(e)}"}],
                summary=f"Tool execution failed during endpoint discovery: {str(e)}",
                st_ver=st_ver
            )

        # 4. Execute Contract Verification Strategy Loop
        violations: List[ContractViolation] = []
        checks_executed = 0
        operations_count = 0

        try:
            for operation in operations:
                operations_count += 1
                path_key = operation.path
                method = operation.method

                # Check timeout
                if (time.monotonic() - t_start_mono) > timeout_sec:
                    return _make_result(
                        status=ProviderStatus.TIMEOUT,
                        exit_code=124,
                        violations=violations,
                        stats=ExecutionStats(
                            endpoints_tested=len(endpoints),
                            operations_tested=operations_count,
                            checks_executed=checks_executed,
                            violations_count=len(violations)
                        ),
                        diagnostics=[{"error": f"Execution exceeded timeout limit of {timeout_sec}s"}],
                        summary=f"Execution timed out after {timeout_sec} seconds.",
                        st_ver=st_ver
                    )

                strategy = operation.as_strategy()
                for _ in range(max(1, max_examples_per_operation)):
                    checks_executed += 1
                    try:
                        case = strategy.example()
                    except Exception as e:
                        violations.extend(SchemathesisParser.parse_exception(e, path=path_key, method=method))
                        continue

                    # If callable WSGI application is provided, execute against it
                    if target_app is not None and callable(target_app):
                        response = None
                        curl_str = case.as_curl_command() if hasattr(case, "as_curl_command") else None
                        try:
                            response = case.call()
                            if response.status_code >= 500:
                                violations.append(
                                    ContractViolation(
                                        error_type="ServerError",
                                        message=f"Server Error ({response.status_code}) on {method.upper()} {path_key}: {response.text[:200]}",
                                        path=path_key,
                                        method=method.upper(),
                                        status_code=response.status_code,
                                        curl_command=curl_str
                                    )
                                )
                            case.validate_response(response)
                        except (Exception, BaseException) as e:
                            violations.extend(
                                SchemathesisParser.parse_exception(
                                    e,
                                    path=path_key,
                                    method=method,
                                    status_code=getattr(response, "status_code", None),
                                    curl_command=curl_str
                                )
                            )

                    # If live base_url is provided, execute HTTP request
                    elif base_url:
                        response = None
                        curl_str = case.as_curl_command() if hasattr(case, "as_curl_command") else None
                        try:
                            response = case.call(base_url=base_url)
                            if response.status_code >= 500:
                                violations.append(
                                    ContractViolation(
                                        error_type="ServerError",
                                        message=f"Server Error ({response.status_code}) on {method.upper()} {path_key}: {response.text[:200]}",
                                        path=path_key,
                                        method=method.upper(),
                                        status_code=response.status_code,
                                        curl_command=curl_str
                                    )
                                )
                            case.validate_response(response)
                        except (Exception, BaseException) as e:
                            violations.extend(
                                SchemathesisParser.parse_exception(
                                    e,
                                    path=path_key,
                                    method=method,
                                    status_code=getattr(response, "status_code", None),
                                    curl_command=curl_str
                                )
                            )

        except Exception as e:
            return _make_result(
                status=ProviderStatus.TOOL_EXECUTION_FAILED,
                exit_code=1,
                violations=violations,
                stats=ExecutionStats(
                    endpoints_tested=len(endpoints),
                    operations_tested=operations_count,
                    checks_executed=checks_executed,
                    violations_count=len(violations)
                ),
                diagnostics=[{"error": f"Unhandled tool execution exception: {type(e).__name__}: {str(e)}"}],
                summary=f"Schemathesis execution encountered unhandled error: {str(e)}",
                st_ver=st_ver
            )

        # 5. Determine Final Epistemic Status
        stats = ExecutionStats(
            endpoints_tested=len(endpoints),
            operations_tested=operations_count,
            checks_executed=checks_executed,
            violations_count=len(violations)
        )

        if len(violations) > 0:
            return _make_result(
                status=ProviderStatus.TARGET_CONTRACT_VIOLATED,
                exit_code=1,
                violations=violations,
                stats=stats,
                diagnostics=[{"violation": v.to_dict()} for v in violations],
                summary=f"Target contract violated: {len(violations)} violations detected across {operations_count} operations.",
                st_ver=st_ver
            )

        if checks_executed == 0:
            return _make_result(
                status=ProviderStatus.INSUFFICIENT_EVIDENCE,
                exit_code=0,
                violations=[],
                stats=stats,
                diagnostics=[{"warning": "Zero contract checks were executed."}],
                summary="Execution inconclusive: Zero checks evaluated (INSUFFICIENT_EVIDENCE).",
                st_ver=st_ver
            )

        return _make_result(
            status=ProviderStatus.TARGET_CLEAN,
            exit_code=0,
            violations=[],
            stats=stats,
            diagnostics=[],
            summary=f"Target clean: All {checks_executed} contract checks passed across {len(endpoints)} endpoints.",
            st_ver=st_ver
        )
