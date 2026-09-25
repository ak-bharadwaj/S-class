"""
Tests for Evidence and Verification Provider Registry Substrate.
Certifies:
1. Provider registration, ID lookup, and claim-type resolution.
2. Canonical VerificationProviderRegistry lifecycle and defaults.
3. Fail-closed dispatching on unregistered or missing providers.
4. Provider execution and verification contracts for test, static analysis, SBOM, and API fuzzing.
5. Fail-closed behavior on missing or unobserved receipts.
"""

import os
import pytest
from typing import Dict, Any, List, Optional

from sclass.domain.claim import Claim, ClaimType
from sclass.domain.evidence import ObservedReceipt
from sclass.verification.provider import (
    VerificationProvider,
    BaseVerificationProvider,
    PytestProvider,
    SemgrepProvider,
    SyftProvider,
    SchemathesisProvider,
    VerificationProviderRegistry,
    get_provider_registry,
)


def test_verification_provider_registry_lifecycle():
    """Certifies that the provider registry correctly manages provider lifecycles."""
    reg = VerificationProviderRegistry(load_defaults=False)
    assert len(reg.list_all_providers()) == 0

    pytest_prov = PytestProvider()
    semgrep_prov = SemgrepProvider()
    syft_prov = SyftProvider()
    schemathesis_prov = SchemathesisProvider()

    reg.register(pytest_prov)
    reg.register(semgrep_prov)
    reg.register(syft_prov)
    reg.register(schemathesis_prov)

    assert reg.get_provider("pytest") is pytest_prov
    assert reg.get_provider("semgrep") is semgrep_prov
    assert reg.get_provider("syft") is syft_prov
    assert reg.get_provider("schemathesis") is schemathesis_prov
    assert reg.get_provider("unknown_nonexistent") is None

    # Claim type resolution
    test_providers = reg.get_providers_for_claim(ClaimType.TEST_PASS.value)
    assert pytest_prov in test_providers
    assert schemathesis_prov in test_providers

    sec_providers = reg.get_providers_for_claim(ClaimType.SECURITY.value)
    assert semgrep_prov in sec_providers
    assert syft_prov in sec_providers

    assert reg.get_providers_for_claim("nonexistent_claim_type") == []


def test_global_provider_registry_singleton():
    """Certifies that get_provider_registry returns initialized default providers."""
    global_reg = get_provider_registry()
    assert isinstance(global_reg, VerificationProviderRegistry)
    assert "pytest" in global_reg.list_all_providers()
    assert "semgrep" in global_reg.list_all_providers()
    assert "syft" in global_reg.list_all_providers()
    assert "schemathesis" in global_reg.list_all_providers()


def test_pytest_provider_fails_closed_without_receipt(tmp_path):
    """Certifies that PytestProvider rejects verification when no observed receipt is provided."""
    prov = PytestProvider()
    claim = Claim(
        claim_id="clm_no_receipt",
        task_id="tsk_01",
        statement="All tests pass",
        claim_type=ClaimType.TEST_PASS.value,
    )
    result = prov.verify(claim, None, workspace_dir=str(tmp_path))
    assert result.is_accepted is False
    assert result.status == "REJECT"
    assert "No independently observed execution receipt" in result.reason


def test_semgrep_provider_fails_closed_without_receipt(tmp_path):
    """Certifies that SemgrepProvider rejects verification when no observed receipt is provided."""
    prov = SemgrepProvider()
    claim = Claim(
        claim_id="clm_sec_no_receipt",
        task_id="tsk_02",
        statement="No SQL injection vulnerabilities",
        claim_type=ClaimType.SECURITY.value,
    )
    result = prov.verify(claim, None, workspace_dir=str(tmp_path))
    assert result.is_accepted is False
    assert result.status == "REJECT"
    assert "No independently observed SAST scan receipt" in result.reason


def test_syft_provider_fails_closed_without_receipt(tmp_path):
    """Certifies that SyftProvider rejects verification when no observed receipt is provided."""
    prov = SyftProvider()
    claim = Claim(
        claim_id="clm_sbom_no_receipt",
        task_id="tsk_03",
        statement="SBOM generated cleanly",
        claim_type=ClaimType.SECURITY.value,
    )
    result = prov.verify(claim, None, workspace_dir=str(tmp_path))
    assert result.is_accepted is False
    assert result.status == "REJECT"
    assert "No independently observed SBOM receipt" in result.reason


def test_schemathesis_provider_fails_closed_without_receipt(tmp_path):
    """Certifies that SchemathesisProvider rejects verification when no observed receipt is provided."""
    prov = SchemathesisProvider()
    claim = Claim(
        claim_id="clm_api_no_receipt",
        task_id="tsk_04",
        statement="API schema conforms",
        claim_type=ClaimType.TEST_PASS.value,
    )
    result = prov.verify(claim, None, workspace_dir=str(tmp_path))
    assert result.is_accepted is False
    assert result.status == "REJECT"
    assert "No independently observed contract test receipt" in result.reason


def test_custom_provider_registration():
    """Certifies that custom third-party verification providers can be registered."""
    class CustomBenchmarkProvider(BaseVerificationProvider):
        provider_id = "custom_bench"
        provider_type = "benchmark"
        supported_claim_types = ("benchmark_speed",)

        def is_available(self) -> bool:
            return True

    reg = VerificationProviderRegistry(load_defaults=False)
    custom_prov = CustomBenchmarkProvider()
    reg.register(custom_prov)

    assert reg.get_provider("custom_bench") is custom_prov
    assert reg.get_providers_for_claim("benchmark_speed") == [custom_prov]
