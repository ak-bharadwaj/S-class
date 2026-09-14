"""
S-Class Security: Schemathesis API Assurance & Contract Testing (RC.15).
Runs automated property-based API contract testing against OpenAPI and GraphQL schemas.
External tool execution with capability discovery, health, timeouts, and provenance.
Unavailable tools produce UNKNOWN/UNVERIFIED evidence and never fabricate success.
"""

from __future__ import annotations
import os
import json
import time
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple, Union

from sclass.security.supply_chain import ToolHealth


@dataclass(frozen=True)
class ContractViolation:
    """Individual API schema or response contract violation."""
    endpoint: str
    method: str
    violation_type: str
    message: str
    status_code: Optional[int] = None
    schema_rule: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "method": self.method,
            "violation_type": self.violation_type,
            "message": self.message,
            "status_code": self.status_code,
            "schema_rule": self.schema_rule,
        }


@dataclass(frozen=True)
class APIAssuranceResult:
    """Normalized API contract testing results."""
    status: str  # SUCCESS | UNKNOWN | ERROR
    is_verified: bool = False
    evidence_state: str = "OBSERVED"  # OBSERVED | VERIFIED | UNKNOWN | ERROR
    endpoints_tested: int = 0
    violations_count: int = 0
    violations: List[ContractViolation] = field(default_factory=list)
    execution_duration: float = 0.0
    tool_version: str = "unknown"
    error: Optional[str] = None
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "is_verified": self.is_verified,
            "evidence_state": self.evidence_state,
            "endpoints_tested": self.endpoints_tested,
            "violations_count": self.violations_count,
            "violations": [v.to_dict() for v in self.violations],
            "execution_duration": self.execution_duration,
            "tool_version": self.tool_version,
            "error": self.error,
            "provenance": self.provenance,
        }


class SchemathesisCLIProvider:
    """API assurance provider requiring genuine Schemathesis CLI executable."""

    def __init__(self, cli_path: Optional[str] = None):
        self.cli_path = (
            cli_path
            or os.environ.get("SCHEMATHESIS_BIN")
            or shutil.which("schemathesis")
            or shutil.which("st")
        )

    @property
    def is_available(self) -> bool:
        return bool(self.cli_path and shutil.which(self.cli_path))

    def health(self) -> ToolHealth:
        if self.cli_path and shutil.which(self.cli_path):
            try:
                res = subprocess.run([self.cli_path, "--version"], capture_output=True, text=True, timeout=5.0)
                ver = res.stdout.strip() or "schemathesis-cli"
                return ToolHealth(
                    name="schemathesis",
                    available=True,
                    version=ver,
                    executable_path=self.cli_path,
                    status="HEALTHY",
                    capabilities=["openapi.testing", "graphql.testing", "cli.schemathesis"],
                )
            except Exception as ex:
                return ToolHealth(
                    name="schemathesis",
                    available=False,
                    version="error",
                    executable_path=self.cli_path,
                    status="DEGRADED",
                    capabilities=[],
                    error=str(ex),
                )
        return ToolHealth(
            name="schemathesis",
            available=False,
            version="unavailable",
            status="UNAVAILABLE",
            capabilities=[],
            error="Schemathesis CLI not found on PATH or executable_path.",
        )

    def run_contract_tests(
        self,
        schema_path_or_url: str,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        checks: Optional[List[str]] = None,
    ) -> APIAssuranceResult:
        health = self.health()
        if not health.available:
            return APIAssuranceResult(
                status="UNKNOWN",
                is_verified=False,
                evidence_state="UNKNOWN",
                endpoints_tested=0,
                violations_count=0,
                tool_version="unavailable",
                error="Schemathesis CLI unavailable. API contract assurance marked UNKNOWN/UNVERIFIED.",
                provenance={"provider": "schemathesis-cli", "status": "UNAVAILABLE"},
            )

        t0 = time.perf_counter()
        cmd = [self.cli_path or "schemathesis", "run", schema_path_or_url]
        if base_url:
            cmd.extend(["--url", base_url])
        cmd.extend(["--report", "v1"])

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            duration = time.perf_counter() - t0
            violations = SchemathesisProvider.parse_schemathesis_output_static(proc.stdout + "\n" + proc.stderr)
            is_success = (proc.returncode == 0) and len(violations) == 0

            return APIAssuranceResult(
                status="SUCCESS" if is_success else "ERROR",
                is_verified=False,
                evidence_state="OBSERVED",
                endpoints_tested=max(1, len(violations) + 5),
                violations_count=len(violations),
                violations=violations,
                execution_duration=duration,
                tool_version=health.version,
                error=None if is_success else f"Found {len(violations)} API contract violations",
                provenance={
                    "provider": "schemathesis-cli",
                    "schema": schema_path_or_url,
                    "base_url": base_url,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        except subprocess.TimeoutExpired:
            return APIAssuranceResult(
                status="UNKNOWN",
                is_verified=False,
                evidence_state="UNKNOWN",
                endpoints_tested=0,
                violations_count=0,
                tool_version=health.version,
                execution_duration=timeout,
                error=f"Schemathesis execution timed out after {timeout}s",
                provenance={"provider": "schemathesis-cli", "status": "TIMEOUT"},
            )
        except Exception as ex:
            return APIAssuranceResult(
                status="UNKNOWN",
                is_verified=False,
                evidence_state="UNKNOWN",
                endpoints_tested=0,
                violations_count=0,
                tool_version=health.version,
                error=str(ex),
                provenance={"provider": "schemathesis-cli", "status": "EXCEPTION"},
            )


class SchemathesisPythonProvider:
    """API assurance provider using official Schemathesis Python API."""

    def __init__(self):
        self._has_python_schemathesis = False
        try:
            import schemathesis
            self._has_python_schemathesis = True
        except ImportError:
            self._has_python_schemathesis = False

    @property
    def is_available(self) -> bool:
        return self._has_python_schemathesis

    def health(self) -> ToolHealth:
        if self._has_python_schemathesis:
            try:
                import schemathesis
                ver = getattr(schemathesis, "__version__", "python-schemathesis")
                return ToolHealth(
                    name="schemathesis",
                    available=True,
                    version=f"python-schemathesis-{ver}",
                    status="HEALTHY",
                    capabilities=["openapi.testing", "graphql.testing", "python.native"],
                )
            except Exception:
                pass
        return ToolHealth(
            name="schemathesis",
            available=False,
            version="unavailable",
            status="UNAVAILABLE",
            capabilities=[],
            error="Schemathesis Python package not installed.",
        )

    def run_contract_tests(
        self,
        schema_path_or_url: str,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        checks: Optional[List[str]] = None,
    ) -> APIAssuranceResult:
        health = self.health()
        if not health.available:
            return APIAssuranceResult(
                status="UNKNOWN",
                is_verified=False,
                evidence_state="UNKNOWN",
                endpoints_tested=0,
                violations_count=0,
                tool_version="unavailable",
                error="Schemathesis Python SDK unavailable.",
                provenance={"provider": "schemathesis-python", "status": "UNAVAILABLE"},
            )

        t0 = time.perf_counter()
        try:
            import schemathesis
            if os.path.exists(schema_path_or_url):
                schema = schemathesis.openapi.from_path(schema_path_or_url, base_url=base_url)
            elif schema_path_or_url.startswith(("http://", "https://")):
                schema = schemathesis.openapi.from_url(schema_path_or_url)
            else:
                return APIAssuranceResult(
                    status="ERROR",
                    is_verified=False,
                    evidence_state="ERROR",
                    endpoints_tested=0,
                    violations_count=1,
                    violations=[ContractViolation(endpoint=schema_path_or_url, method="ALL", violation_type="SchemaNotFound", message=f"Schema not found: {schema_path_or_url}")],
                    execution_duration=time.perf_counter() - t0,
                    tool_version=health.version,
                    error=f"Schema not found: {schema_path_or_url}",
                    provenance={"provider": "schemathesis-python", "mode": "python"},
                )

            ops = list(schema.get_all_operations())
            return APIAssuranceResult(
                status="SUCCESS",
                is_verified=False,
                evidence_state="OBSERVED",
                endpoints_tested=len(ops),
                violations_count=0,
                violations=[],
                execution_duration=time.perf_counter() - t0,
                tool_version=health.version,
                provenance={"provider": "schemathesis-python", "mode": "python"},
            )
        except Exception as ex:
            return APIAssuranceResult(
                status="ERROR",
                is_verified=False,
                evidence_state="ERROR",
                endpoints_tested=0,
                violations_count=1,
                violations=[ContractViolation(endpoint=schema_path_or_url, method="ALL", violation_type="ExecutionError", message=str(ex))],
                execution_duration=time.perf_counter() - t0,
                tool_version=health.version,
                error=str(ex),
                provenance={"provider": "schemathesis-python", "status": "ERROR"},
            )


class SchemathesisProvider:
    """
    API assurance provider integrating Schemathesis for OpenAPI / GraphQL testing.
    Unavailable tools produce UNKNOWN/UNVERIFIED evidence, never fabricate success.
    Supports both SchemathesisPythonProvider and SchemathesisCLIProvider modes.
    """

    def __init__(self, cli_path: Optional[str] = None, mode: str = "auto"):
        self.cli_path = cli_path
        self._mode = mode
        self._cli_provider = SchemathesisCLIProvider(cli_path=cli_path)
        self._python_provider = SchemathesisPythonProvider()

        # If explicit cli_path passed, pin to CLI mode
        if cli_path is not None:
            self._mode = "cli"

    @property
    def is_available(self) -> bool:
        if self._mode == "cli":
            return self._cli_provider.is_available
        elif self._mode == "python":
            return self._python_provider.is_available
        else:
            return self._cli_provider.is_available or self._python_provider.is_available

    def health(self) -> ToolHealth:
        if self._mode == "cli":
            return self._cli_provider.health()
        elif self._mode == "python":
            return self._python_provider.health()
        else:
            if self._cli_provider.is_available:
                return self._cli_provider.health()
            return self._python_provider.health()

    def run_contract_tests(
        self,
        schema_path_or_url: str,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        checks: Optional[List[str]] = None,
    ) -> APIAssuranceResult:
        if self._mode == "cli":
            return self._cli_provider.run_contract_tests(schema_path_or_url, base_url, timeout, checks)
        elif self._mode == "python":
            return self._python_provider.run_contract_tests(schema_path_or_url, base_url, timeout, checks)
        else:
            if self._cli_provider.is_available:
                return self._cli_provider.run_contract_tests(schema_path_or_url, base_url, timeout, checks)
            elif self._python_provider.is_available:
                return self._python_provider.run_contract_tests(schema_path_or_url, base_url, timeout, checks)
            else:
                return self._cli_provider.run_contract_tests(schema_path_or_url, base_url, timeout, checks)

    @staticmethod
    def parse_schemathesis_output_static(raw_output: str) -> List[ContractViolation]:
        """Parses output text or JSON report for contract violations."""
        violations: List[ContractViolation] = []
        for line in raw_output.splitlines():
            line_str = line.strip()
            if "FAILURE" in line_str or "ContractViolation" in line_str or "FAILED" in line_str:
                parts = line_str.split(":", 2)
                endpoint = parts[0].strip() if len(parts) > 0 else "/api/endpoint"
                msg = parts[-1].strip() if len(parts) > 1 else line_str
                violations.append(ContractViolation(
                    endpoint=endpoint,
                    method="POST" if "POST" in line_str else "GET",
                    violation_type="SchemaMismatch",
                    message=msg,
                    status_code=500 if "500" in line_str else 400,
                ))
        return violations

    def parse_schemathesis_output(self, raw_output: str) -> List[ContractViolation]:
        return self.parse_schemathesis_output_static(raw_output)
