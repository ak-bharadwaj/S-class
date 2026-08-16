"""
S-Class EOS V11.2 - Schemathesis API Contract Verification Adapter
Executes live HTTP API behavioral contract verification campaigns against running target endpoints
and generates structured S-Class evidence receipts.
"""

import os
import sys
import json
import hashlib
from datetime import datetime, timezone
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional, List, Callable
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
            "environment": self.environment,
            "timestamp": self.timestamp
        }
        raw = json.dumps(payload, sort_keys=True)
        self.provenance_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return self.provenance_hash

    def to_dict(self) -> Dict[str, Any]:
        if not self.provenance_hash:
            self.compute_provenance_hash()
        return asdict(self)


class APIContractVerificationAdapter:
    """
    Authoritative S-Class adapter executing Schemathesis API contract verification campaigns
    against running API endpoints and recording verifiable evidence receipts.
    """

    @classmethod
    def _get_env_metadata(cls) -> Dict[str, str]:
        return {
            "python_version": sys.version.split()[0],
            "platform": sys.platform,
            "schemathesis_version": getattr(schemathesis, "__version__", "4.24.3"),
            "engine": "Schemathesis API Contract Verification Adapter V11.2"
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
        Generates dynamic cases, dispatches HTTP requests, validates responses, and records failures.
        """
        target_title = openapi_spec.get("info", {}).get("title", "API Service")
        paths = openapi_spec.get("paths", {})
        endpoints_count = len(paths)

        passed = True
        failures: List[str] = []
        tests_count = 0

        try:
            schema = schemathesis.openapi.from_dict(openapi_spec)
            for res in schema.get_all_operations():
                op = res.ok() if hasattr(res, "ok") else res
                if op is None:
                    passed = False
                    failures.append(f"Failed to load operation: {res}")
                    continue

                strategy = op.as_strategy()
                for _ in range(max_cases_per_operation):
                    tests_count += 1
                    try:
                        case = strategy.example()
                        # Dispatch live HTTP request to target API
                        response = case.call(base_url=base_url)

                        # Check 1: 5xx server error detection
                        if response.status_code >= 500:
                            passed = False
                            failures.append(
                                f"Server Error ({response.status_code}) on {case.method} {case.formatted_path}: {response.text[:200]}"
                            )
                            continue

                        # Check 2: Schema validation according to OpenAPI specification
                        try:
                            op.validate_response(response)
                        except (Exception, BaseException) as schema_err:
                            passed = False
                            failures.append(
                                f"Schema Violation on {case.method} {case.formatted_path} (status {response.status_code}): {schema_err}"
                            )

                    except Exception as case_err:
                        passed = False
                        failures.append(f"Execution failure on {op.method} {op.path}: {case_err}")

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
        failures: List[str] = []
        tests_count = 0

        try:
            schema = schemathesis.openapi.from_dict(openapi_spec)
            for res in schema.get_all_operations():
                tests_count += 1
                op = res.ok() if hasattr(res, "ok") else res
                if op is None or not getattr(op, "path", None) or not getattr(op, "method", None):
                    passed = False
                    failures.append(f"Invalid operation signature: {res}")
            if tests_count == 0:
                passed = False
                failures.append("No valid API operations found in specification")
        except Exception as e:
            passed = False
            failures.append(f"Schemathesis schema parsing error: {e}")

        receipt = APIEvidenceReceipt(
            obligation_id=obligation_id,
            target_api=target_title,
            target_url="static://schema",
            passed=passed,
            endpoints_tested=endpoints_count,
            tests_executed=tests_count,
            failures_detected=len(failures),
            failure_details=failures,
            environment=cls._get_env_metadata()
        )
        receipt.compute_provenance_hash()
        return receipt

    @classmethod
    def save_evidence_receipt(cls, receipt: APIEvidenceReceipt, workspace_dir: str) -> str:
        """Persists API evidence receipt into .agents/evidence/ directory."""
        evidence_dir = os.path.join(workspace_dir, ".agents", "evidence")
        os.makedirs(evidence_dir, exist_ok=True)
        evidence_path = os.path.join(evidence_dir, f"api_{receipt.obligation_id}.json")
        with open(evidence_path, "w", encoding="utf-8") as f:
            json.dump(receipt.to_dict(), f, indent=2)
        return evidence_path
