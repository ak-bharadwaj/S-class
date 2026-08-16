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


@dataclass
class APIEvidenceReceipt:
    obligation_id: str
    target_api: str
    target_url: str
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

    def compute_provenance_hash(self) -> str:
        payload = {
            "obligation_id": self.obligation_id,
            "target_api": self.target_api,
            "target_url": self.target_url,
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
        if not self.provenance_hash:
            self.compute_provenance_hash()
        return asdict(self)


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

        passed = True
        failures: List[str] = []
        failure_cases: List[Dict[str, Any]] = []
        tests_count = 0

        try:
            schema = schemathesis.openapi.from_dict(openapi_spec)
            for res in schema.get_all_operations():
                op = res.ok() if hasattr(res, "ok") else res
                if op is None:
                    passed = False
                    failures.append(f"Failed to load operation: {res}")
                    continue

                last_failing_case = None

                @settings(max_examples=max_cases_per_operation, phases=[Phase.generate, Phase.shrink], deadline=None)
                @given(case=op.as_strategy())
                def test_single_op(case):
                    nonlocal tests_count, last_failing_case
                    tests_count += 1

                    # Dispatch live HTTP request to target API
                    response = case.call(base_url=base_url)

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
                        "response_status": response.status_code,
                        "response_body": response.text[:500] if response.text else ""
                    }

                    # Check 1: 5xx server error detection
                    if response.status_code >= 500:
                        last_failing_case = case_metadata
                        assert False, f"Server Error ({response.status_code}) on {case.method} {case.formatted_path}: {response.text[:200]}"

                    # Check 2: Schema validation according to OpenAPI specification
                    try:
                        case.validate_response(response)
                    except (Exception, BaseException) as schema_err:
                        last_failing_case = case_metadata
                        assert False, f"Schema Violation on {case.method} {case.formatted_path} (status {response.status_code}): {schema_err}"

                try:
                    test_single_op()
                except (AssertionError, Exception) as op_err:
                    passed = False
                    failures.append(str(op_err))
                    if last_failing_case and last_failing_case not in failure_cases:
                        failure_cases.append(last_failing_case)

            if tests_count == 0:
                passed = False
                failures.append("No executable API operations discovered in specification")

        except Exception as e:
            passed = False
            failures.append(f"Schemathesis execution campaign error: {e}")

        receipt = APIEvidenceReceipt(
            obligation_id=obligation_id,
            target_api=target_title,
            target_url=base_url,
            passed=passed,
            endpoints_tested=endpoints_count,
            tests_executed=tests_count,
            failures_detected=len(failures),
            failure_details=failures,
            reproducible_failure_cases=failure_cases,
            reproducibility={
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
        endpoints_count = len(paths)

        passed = True
        failures = []

        if not openapi_spec.get("openapi") and not openapi_spec.get("swagger"):
            passed = False
            failures.append("Missing 'openapi' version declaration")

        if "paths" not in openapi_spec or not isinstance(openapi_spec["paths"], dict):
            passed = False
            failures.append("Specification contains no valid 'paths' definition")

        receipt = APIEvidenceReceipt(
            obligation_id=obligation_id,
            target_api=target_title,
            target_url="spec://openapi.json",
            passed=passed,
            endpoints_tested=endpoints_count,
            tests_executed=1,
            failures_detected=len(failures),
            failure_details=failures,
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
