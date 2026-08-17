"""
S-Class EOS V11.2 - Schemathesis API Contract Verification Adapter (Legacy Bridge)
Delegates to the S-Class Schemathesis Provider Package (benchmark.providers.schemathesis)
and translates results to APIEvidenceReceipt.
"""

import os
import sys
import json
import hashlib
from datetime import datetime, timezone
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional, List, Callable
import hypothesis

from evidence_ir import EpistemicStatus, UnifiedEvidenceReceipt
from benchmark.providers.schemathesis.adapter import SchemathesisProviderAdapter
from benchmark.providers.schemathesis.models import ProviderStatus
from benchmark.providers.schemathesis.version_policy import VersionPolicy


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
            engine_name="SchemathesisProviderAdapter",
            engine_version=VersionPolicy.get_installed_version(),
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
    """Legacy bridge delegating to the authoritative SchemathesisProviderAdapter."""

    @classmethod
    def _get_env_metadata(cls) -> Dict[str, str]:
        return {
            "python_version": sys.version.split()[0],
            "platform": sys.platform,
            "hypothesis_version": hypothesis.__version__,
            "schemathesis_version": VersionPolicy.get_installed_version() or "UNKNOWN",
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
        """Executes API verification campaign via the Schemathesis provider boundary."""
        target_title = openapi_spec.get("info", {}).get("title", "API Service")
        spec_hash = hashlib.sha256(json.dumps(openapi_spec, sort_keys=True).encode("utf-8")).hexdigest()

        adapter = SchemathesisProviderAdapter()
        res = adapter.verify_api_contract(
            schema_dict=openapi_spec,
            base_url=base_url,
            obligation_id=obligation_id,
            max_examples_per_operation=max_cases_per_operation
        )

        status_map = {
            ProviderStatus.TARGET_CLEAN: EpistemicStatus.TARGET_CLEAN,
            ProviderStatus.TARGET_CONTRACT_VIOLATED: EpistemicStatus.TARGET_CONTRACT_VIOLATED,
            ProviderStatus.TOOL_NOT_AVAILABLE: EpistemicStatus.TOOL_NOT_AVAILABLE,
            ProviderStatus.TOOL_EXECUTION_FAILED: EpistemicStatus.TOOL_EXECUTION_FAILED,
            ProviderStatus.INPUT_INVALID: EpistemicStatus.TOOL_OUTPUT_INVALID,
            ProviderStatus.TIMEOUT: EpistemicStatus.TOOL_EXECUTION_FAILED,
            ProviderStatus.OUTPUT_INVALID: EpistemicStatus.TOOL_OUTPUT_INVALID,
            ProviderStatus.INSUFFICIENT_EVIDENCE: EpistemicStatus.TARGET_CONTRACT_VIOLATED,
        }
        ep_status = status_map.get(res.status, EpistemicStatus.TOOL_OUTPUT_INVALID)

        fcases = []
        for v in res.violations:
            d = v.to_dict()
            d["curl"] = v.curl_command or f"curl -X {v.method} '{base_url}{v.path}'"
            d["response_status"] = v.status_code
            fcases.append(d)

        return APIEvidenceReceipt(
            obligation_id=obligation_id,
            target_api=target_title,
            target_url=base_url,
            status=ep_status,
            passed=res.passed,
            endpoints_tested=res.stats.endpoints_tested,
            tests_executed=res.stats.checks_executed,
            failures_detected=len(res.violations),
            failure_details=[v.message for v in res.violations],
            reproducible_failure_cases=fcases,
            reproducibility={
                "openapi_spec_hash": spec_hash,
                "max_cases_per_operation": max_cases_per_operation,
                "config_hash": res.config_hash
            },
            environment=cls._get_env_metadata(),
            timestamp=res.start_time_iso
        )

    @classmethod
    def run_openapi_contract_check(
        cls,
        openapi_spec: Dict[str, Any],
        obligation_id: str = "OBL-API-STATIC-001"
    ) -> APIEvidenceReceipt:
        """Verifies structural validity and endpoint paths of OpenAPI specification."""
        target_title = openapi_spec.get("info", {}).get("title", "API Service")
        spec_hash = hashlib.sha256(json.dumps(openapi_spec, sort_keys=True).encode("utf-8")).hexdigest()

        adapter = SchemathesisProviderAdapter()
        res = adapter.verify_api_contract(
            schema_dict=openapi_spec,
            obligation_id=obligation_id,
            max_examples_per_operation=1
        )

        return APIEvidenceReceipt(
            obligation_id=obligation_id,
            target_api=target_title,
            target_url="in_memory_schema",
            status=EpistemicStatus.TARGET_CLEAN if res.passed else EpistemicStatus.TARGET_CONTRACT_VIOLATED,
            passed=res.passed,
            endpoints_tested=res.stats.endpoints_tested,
            tests_executed=res.stats.checks_executed,
            failures_detected=len(res.violations),
            failure_details=[v.message for v in res.violations],
            reproducible_failure_cases=[v.to_dict() for v in res.violations],
            reproducibility={
                "openapi_spec_hash": spec_hash,
                "config_hash": res.config_hash
            },
            environment=cls._get_env_metadata(),
            timestamp=res.start_time_iso
        )

    @classmethod
    def verify_openapi_spec_contract(
        cls,
        openapi_spec: Dict[str, Any],
        obligation_id: str = "OBL-API-STATIC-001"
    ) -> APIEvidenceReceipt:
        """Alias for run_openapi_contract_check."""
        return cls.run_openapi_contract_check(openapi_spec, obligation_id)

    @staticmethod
    def save_evidence_receipt(receipt: APIEvidenceReceipt, output_dir: str) -> str:
        """Persists an APIEvidenceReceipt to JSON disk storage."""
        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, f"api_evidence_{receipt.obligation_id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(receipt.to_dict(), f, indent=2)
        return file_path
