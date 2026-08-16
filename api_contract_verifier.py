"""
S-Class EOS V11.2 - Schemathesis API Contract Verification Adapter
Executes live HTTP API behavioral contract verification campaigns under Hypothesis property execution
against running target endpoints and generates structured S-Class evidence receipts with reproducible request/response cases.
"""

import os
import sys
import json
import hashlib
from datetime import datetime, timezone
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional, List, Callable
import hypothesis
from hypothesis import given, settings, Phase
import schemathesis

from evidence_ir import EpistemicStatus, UnifiedEvidenceReceipt


@dataclass
class APIEvidenceReceipt:
    obligation_id: str
    target_api: str
    target_url: str
    status: EpistemicStatus
    passed: bool
    endpoints_tested: int
    tests_executed: int
    failures_detected: int
    failure_details: List[str] = field(default_factory=list)
    reproducible_failure_cases: List[Dict[str, Any]] = field(default_factory=list)
    reproducibility: Dict[str, Any] = field(default_factory=dict)
    environment: Dict[str, str] = field(default_factory=dict)
    provenance_hash: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        if isinstance(self.status, str):
            try:
                self.status = EpistemicStatus(self.status)
            except ValueError:
                self.status = EpistemicStatus.TOOL_OUTPUT_INVALID
        # Authority Invariant: passed is True iff status is TARGET_CLEAN
        if self.status != EpistemicStatus.TARGET_CLEAN:
            self.passed = False
        if not self.provenance_hash:
            self.compute_provenance_hash()

    def compute_provenance_hash(self) -> str:
        payload = {
            "obligation_id": self.obligation_id,
            "target_api": self.target_api,
            "target_url": self.target_url,
            "status": self.status.value if isinstance(self.status, EpistemicStatus) else str(self.status),
            "passed": self.passed,
            "endpoints_tested": self.endpoints_tested,
            "tests_executed": self.tests_executed,
            "failures_detected": self.failures_detected,
            "failure_details": self.failure_details,
            "reproducible_failure_cases": self.reproducible_failure_cases,
            "reproducibility": self.reproducibility,
            "environment": self.environment,
            "timestamp": self.timestamp
        }
        raw = json.dumps(payload, sort_keys=True, default=str)
        self.provenance_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return self.provenance_hash

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value if isinstance(self.status, EpistemicStatus) else str(self.status)
        return data

    def to_ir(self) -> UnifiedEvidenceReceipt:
        spec_hash = self.reproducibility.get("openapi_spec_hash", "")
        return UnifiedEvidenceReceipt(
            obligation_id=self.obligation_id,
            provider_type="api_contract_verifier",
            engine_name="Schemathesis",
            engine_version=getattr(schemathesis, "__version__", None),
            status=self.status,
            passed=self.passed,
            target_name=self.target_api,
            target_identifier=self.target_url,
            target_source_hash=spec_hash,
            execution_metadata={
                "endpoints_tested": self.endpoints_tested,
                "tests_executed": self.tests_executed,
                "reproducibility": self.reproducibility,
                "environment": self.environment
            },
            diagnostics=[{"message": f} for f in self.failure_details],
            reproducible_cases=self.reproducible_failure_cases,
            provenance_hash=self.provenance_hash,
            timestamp=self.timestamp
        )


class APIContractVerificationAdapter:
    """
    Authoritative S-Class adapter executing Schemathesis API contract verification campaigns
    against running API endpoints using native Hypothesis property generation and recording verifiable evidence receipts.
    """

    @classmethod
    def _get_env_metadata(cls) -> Dict[str, str]:
        return {
            "python_version": sys.version.split()[0],
            "platform": sys.platform,
            "hypothesis_version": hypothesis.__version__,
            "schemathesis_version": getattr(schemathesis, "__version__", "4.24.3"),
            "engine": "Schemathesis Hypothesis API Verification Adapter V11.2"
        }

    @classmethod
    def run_api_execution_campaign(
        cls,
        openapi_spec: Dict[str, Any],
        base_url: str,
        obligation_id: str = "OBL-API-EXEC-001",
        max_cases_per_operation: int = 5
    ) -> APIEvidenceReceipt:
        """
        Executes a live Schemathesis testing campaign against base_url using openapi_spec.
        Uses Hypothesis property generation/shrinking per operation, dispatches HTTP requests,
        validates responses against the schema, and captures reproducible curl/response cases.
        """
        target_title = openapi_spec.get("info", {}).get("title", "API Service")
        paths = openapi_spec.get("paths", {})
        endpoints_count = len(paths)
        spec_hash = hashlib.sha256(json.dumps(openapi_spec, sort_keys=True).encode("utf-8")).hexdigest()

        failures: List[str] = []
        failure_cases: List[Dict[str, Any]] = []
        tests_count = 0
        status = EpistemicStatus.TARGET_CLEAN

        try:
            schema = schemathesis.openapi.from_dict(openapi_spec)
            for res in schema.get_all_operations():
                op = res.ok() if hasattr(res, "ok") else res
                if op is None:
                    failures.append(f"Failed to load operation: {res}")
                    continue

                last_failing_case = None
                current_case = None

                @settings(max_examples=max_cases_per_operation, phases=[Phase.generate, Phase.shrink], deadline=None)
                @given(case=op.as_strategy())
                def test_single_op(case):
                    nonlocal tests_count, last_failing_case, current_case
                    tests_count += 1

                    try:
                        curl_str = case.as_curl_command()
                    except Exception:
                        curl_str = f"curl -X {case.method} '{base_url}{case.formatted_path}'"

                    case_metadata = {
                        "operation": f"{case.method} {case.formatted_path}",
                        "method": case.method,
                        "path": case.formatted_path,
                        "query": case.query,
                        "headers": dict(case.headers) if case.headers else {},
                        "body": case.body,
                        "curl": curl_str,
                        "response_status": None,
                        "response_body": None,
                        "transport_error": None
                    }
                    current_case = case_metadata

                    response = None
                    try:
                        response = case.call(base_url=base_url)
                        case_metadata["response_status"] = response.status_code
                        case_metadata["response_body"] = response.text[:500] if response.text else ""
                    except (AssertionError, Exception, BaseException) as transport_err:
                        case_metadata["transport_error"] = str(transport_err)
                        last_failing_case = case_metadata
                        raise AssertionError(f"Transport Error on {case.method} {case.formatted_path}: {transport_err}") from transport_err

                    # Check 1: 5xx server error detection
                    if response.status_code >= 500:
                        last_failing_case = case_metadata
                        assert False, f"Server Error ({response.status_code}) on {case.method} {case.formatted_path}: {response.text[:200]}"

                    # Check 2: Schema validation according to OpenAPI specification
                    try:
                        case.validate_response(response)
                    except (AssertionError, Exception, BaseException) as schema_err:
                        last_failing_case = case_metadata
                        raise AssertionError(f"Schema Violation on {case.method} {case.formatted_path} (status {response.status_code}): {schema_err}") from schema_err

                try:
                    test_single_op()
                except (AssertionError, Exception, BaseException) as op_err:
                    failures.append(str(op_err))
                    target_case = last_failing_case or current_case
                    if target_case and target_case not in failure_cases:
                        failure_cases.append(target_case)

            if tests_count == 0:
                status = EpistemicStatus.TOOL_OUTPUT_INVALID
                failures.append("No executable API operations discovered in specification")
            elif len(failures) > 0:
                status = EpistemicStatus.TARGET_CONTRACT_VIOLATED
            else:
                status = EpistemicStatus.TARGET_CLEAN

        except Exception as e:
            status = EpistemicStatus.TOOL_EXECUTION_FAILED
            failures.append(f"Schemathesis execution campaign error: {e}")
        except BaseException as e:
            status = EpistemicStatus.TOOL_EXECUTION_FAILED
            failures.append(f"Schemathesis execution campaign error: {e}")

        passed = (status == EpistemicStatus.TARGET_CLEAN)

        receipt = APIEvidenceReceipt(
            obligation_id=obligation_id,
            target_api=target_title,
            target_url=base_url,
            status=status,
            passed=passed,
            endpoints_tested=endpoints_count,
            tests_executed=tests_count,
            failures_detected=len(failures),
            failure_details=failures,
            reproducible_failure_cases=failure_cases,
            reproducibility={
                "openapi_spec_hash": spec_hash,
                "max_cases_per_operation": max_cases_per_operation,
                "execution_model": "Hypothesis @given(case=op.as_strategy())",
                "phases": ["generate", "shrink"]
            },
            environment=cls._get_env_metadata()
        )
        receipt.compute_provenance_hash()
        return receipt

    @classmethod
    def run_openapi_contract_check(
        cls,
        openapi_spec: Dict[str, Any],
        obligation_id: str = "OBL-API-OPENAPI-001"
    ) -> APIEvidenceReceipt:
        """
        Static inspection and structural validation of OpenAPI specification.
        """
        target_title = openapi_spec.get("info", {}).get("title", "API Service")
        paths = openapi_spec.get("paths", {})
        endpoints_count = len(paths) if isinstance(paths, dict) else 0
        spec_hash = hashlib.sha256(json.dumps(openapi_spec, sort_keys=True).encode("utf-8")).hexdigest()

        failures: List[str] = []
        operations_validated = 0

        # Validate OpenAPI / Swagger version declaration
        if not openapi_spec.get("openapi") and not openapi_spec.get("swagger"):
            failures.append("Missing 'openapi' or 'swagger' version declaration")

        # Validate Info object
        info = openapi_spec.get("info")
        if not isinstance(info, dict):
            failures.append("Missing or invalid 'info' metadata object")
        else:
            if not info.get("title"):
                failures.append("Missing 'info.title' in OpenAPI specification")
            if not info.get("version"):
                failures.append("Missing 'info.version' in OpenAPI specification")

        # Validate Paths mapping
        if not isinstance(paths, dict) or not paths:
            failures.append("Specification contains no valid or non-empty 'paths' definition")
        else:
            http_methods = {"get", "post", "put", "delete", "patch", "options", "head", "trace"}
            for path_key, path_item in paths.items():
                if not isinstance(path_key, str) or not path_key.startswith("/"):
                    failures.append(f"Invalid path key '{path_key}': must start with '/'")
                if not isinstance(path_item, dict):
                    failures.append(f"Path item for '{path_key}' must be an object")
                    continue
                op_count = 0
                for method, op_def in path_item.items():
                    if method.lower() in http_methods and isinstance(op_def, dict):
                        op_count += 1
                        operations_validated += 1
                        responses = op_def.get("responses")
                        if not isinstance(responses, dict) or not responses:
                            failures.append(f"Operation {method.upper()} {path_key} missing valid 'responses' object")
                if op_count == 0:
                    failures.append(f"Path '{path_key}' defines no standard HTTP operations")

        status = EpistemicStatus.TARGET_CLEAN if not failures else EpistemicStatus.TARGET_CONTRACT_VIOLATED
        passed = (status == EpistemicStatus.TARGET_CLEAN)

        receipt = APIEvidenceReceipt(
            obligation_id=obligation_id,
            target_api=target_title,
            target_url="spec://openapi.json",
            status=status,
            passed=passed,
            endpoints_tested=endpoints_count,
            tests_executed=operations_validated if operations_validated > 0 else 1,
            failures_detected=len(failures),
            failure_details=failures,
            reproducibility={
                "openapi_spec_hash": spec_hash,
                "validation_mode": "structural_contract_inspection"
            },
            environment=cls._get_env_metadata()
        )
        receipt.compute_provenance_hash()
        return receipt

    @classmethod
    def save_evidence_receipt(cls, receipt: APIEvidenceReceipt, workspace_dir: str) -> str:
        """Persists API verification evidence receipt into .agents/evidence/ directory."""
        evidence_dir = os.path.join(workspace_dir, ".agents", "evidence")
        os.makedirs(evidence_dir, exist_ok=True)
        evidence_path = os.path.join(evidence_dir, f"api_{receipt.obligation_id}.json")
        with open(evidence_path, "w", encoding="utf-8") as f:
            json.dump(receipt.to_dict(), f, indent=2, default=str)
        return evidence_path
