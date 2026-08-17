"""
S-Class EOS V11.2 - Schemathesis Provider Adapter.
Implements the S-Class provider boundary adapter for API behavioral contract verification.
Translates provider requests into SchemathesisRunner executions and emits native ProviderExecutionResult evidence.
"""

import os
from typing import Dict, Any, Optional, Callable
from .models import (
    ProviderStatus,
    ProviderExecutionResult,
    ContractViolation,
    ExecutionStats
)
from .runner import SchemathesisRunner
from .version_policy import VersionPolicy


class SchemathesisProviderAdapter:
    """Adapter establishing the S-Class provider boundary around the external Schemathesis tool."""

    def __init__(self, source_sha: Optional[str] = None, strict_provenance: bool = False):
        if source_sha is None:
            self.source_sha = os.environ.get("GITHUB_SHA", "UNKNOWN")
        else:
            self.source_sha = source_sha
        self.strict_provenance = strict_provenance
        self.runner = SchemathesisRunner(source_sha=self.source_sha, strict_provenance=self.strict_provenance)

    def verify_api_contract(
        self,
        schema_dict: Optional[Dict[str, Any]],
        target_app: Optional[Callable] = None,
        base_url: Optional[str] = None,
        obligation_id: str = "OB-API-CONTRACT",
        max_examples_per_operation: int = 5,
        timeout_sec: float = 30.0
    ) -> ProviderExecutionResult:
        """Executes API contract verification and returns an immutable native S-Class evidence result."""
        return self.runner.execute(
            schema_dict=schema_dict,
            target_app=target_app,
            base_url=base_url,
            target_identifier=obligation_id,
            max_examples_per_operation=max_examples_per_operation,
            timeout_sec=timeout_sec
        )

    def collect_evidence(
        self,
        target: Any,
        obligation: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ProviderExecutionResult:
        """
        Standard entry point for integration into S-Class EvidenceProvider registry.
        Extracts schema_dict and target app from target and obligation payloads.
        """
        obligation_id = obligation.get("obligation_id", "OB-API-CONTRACT")
        schema_dict = obligation.get("schema_dict")
        target_app = None

        if callable(target):
            target_app = target
        elif isinstance(target, dict) and not schema_dict:
            schema_dict = target

        max_examples = obligation.get("max_examples", 5)
        timeout_sec = obligation.get("timeout_sec", 30.0)

        return self.verify_api_contract(
            schema_dict=schema_dict,
            target_app=target_app,
            base_url=obligation.get("base_url"),
            obligation_id=obligation_id,
            max_examples_per_operation=max_examples,
            timeout_sec=timeout_sec
        )
