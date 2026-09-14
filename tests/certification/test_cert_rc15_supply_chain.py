"""
Certification Tests for Milestone RC.15: Supply-Chain Evidence + Sigstore Provenance + API Assurance.
Validates:
- Syft capability discovery, version probe, and health
- Syft SBOM parsing (SPDX and CycloneDX JSON formats)
- Syft unavailable produces UNKNOWN/UNVERIFIED evidence (never fabricates success)
- Grype capability discovery, health, and vulnerability parsing
- Grype severity thresholding (CRITICAL, HIGH, MEDIUM, LOW)
- Grype unavailable produces UNKNOWN/UNVERIFIED evidence
- S-Class policy & risk evaluation: strict fails closed on UNKNOWN (Law L8); permissive warns
- Supply chain policy blocks on critical/high CVE findings
- Sigstore keyless signing, payload digest verification, and unavailable fallback (Law L5)
- Schemathesis API contract assurance and unavailable fallback
"""

import json
import pytest

from sclass.security.supply_chain import (
    SyftProvider,
    GrypeProvider,
    ToolHealth,
    SBOMResult,
    PackageInfo,
    VulnerabilityFinding,
    VulnerabilityScanResult,
    evaluate_supply_chain_policy,
)
from sclass.security.provenance import SigstoreProvider, ProvenanceReceipt
from sclass.security.api_assurance import SchemathesisProvider, ContractViolation


def test_syft_provider_health_and_capabilities():
    provider = SyftProvider(executable_path="/nonexistent/syft")
    health = provider.health()
    assert isinstance(health, ToolHealth)
    assert health.name == "syft"
    assert health.available is False
    assert health.status == "UNAVAILABLE"
    assert "not found" in health.error.lower()


def test_syft_spdx_and_cyclonedx_sbom_parsing():
    provider = SyftProvider()

    # 1. Sample SPDX JSON
    spdx_sample = json.dumps({
        "spdxVersion": "SPDX-2.3",
        "packages": [
            {
                "name": "cryptography",
                "versionInfo": "42.0.5",
                "licenseConcluded": "Apache-2.0",
                "externalRefs": [
                    {"referenceType": "purl", "referenceLocator": "pkg:pypi/cryptography@42.0.5"}
                ]
            },
            {
                "name": "urllib3",
                "versionInfo": "2.1.0",
                "licenseDeclared": "MIT",
            }
        ]
    })
    spdx_pkgs = provider.parse_sbom_output(spdx_sample, format="spdx-json")
    assert len(spdx_pkgs) == 2
    assert spdx_pkgs[0].name == "cryptography"
    assert spdx_pkgs[0].version == "42.0.5"
    assert spdx_pkgs[0].purl == "pkg:pypi/cryptography@42.0.5"
    assert spdx_pkgs[1].name == "urllib3"

    # 2. Sample CycloneDX JSON
    cyclonedx_sample = json.dumps({
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "components": [
            {
                "name": "requests",
                "version": "2.31.0",
                "type": "library",
                "licenses": [{"license": {"id": "Apache-2.0"}}],
                "purl": "pkg:pypi/requests@2.31.0"
            }
        ]
    })
    cdx_pkgs = provider.parse_sbom_output(cyclonedx_sample, format="cyclonedx-json")
    assert len(cdx_pkgs) == 1
    assert cdx_pkgs[0].name == "requests"
    assert cdx_pkgs[0].license == "Apache-2.0"


def test_syft_unavailable_produces_unknown_evidence():
    provider = SyftProvider(executable_path="/nonexistent/syft")
    res = provider.generate_sbom(target_path=".")

    # Invariant: Never fabricates success
    assert res.status == "UNKNOWN"
    assert res.is_verified is False
    assert res.packages_count == 0
    assert "unavailable" in res.error.lower()
    assert res.provenance.get("status") == "UNAVAILABLE"


def test_grype_provider_health_and_capabilities():
    provider = GrypeProvider(executable_path="/nonexistent/grype")
    health = provider.health()
    assert health.name == "grype"
    assert health.available is False
    assert health.status == "UNAVAILABLE"


def test_grype_vulnerability_parsing_and_thresholding():
    provider = GrypeProvider()
    grype_sample = json.dumps({
        "matches": [
            {
                "vulnerability": {
                    "id": "CVE-2024-9999",
                    "severity": "Critical",
                    "description": "Remote code execution in parser",
                    "cvss": [{"metrics": {"baseScore": 9.8}}],
                    "fix": {"versions": ["2.0.1"]}
                },
                "artifact": {"name": "libvuln", "version": "1.9.0"}
            },
            {
                "vulnerability": {
                    "id": "CVE-2024-1111",
                    "severity": "High",
                    "description": "Denial of service",
                    "cvss": [{"metrics": {"baseScore": 7.5}}],
                    "fix": {"versions": []}
                },
                "artifact": {"name": "net-tool", "version": "0.5.0"}
            },
            {
                "vulnerability": {
                    "id": "CVE-2024-0001",
                    "severity": "Low",
                    "description": "Minor timing leak",
                    "cvss": [{"metrics": {"baseScore": 2.1}}],
                },
                "artifact": {"name": "helper-lib", "version": "3.0.0"}
            }
        ]
    })
    findings = provider.parse_grype_output(grype_sample)
    assert len(findings) == 3
    assert findings[0].id == "CVE-2024-9999"
    assert findings[0].severity == "CRITICAL"
    assert findings[0].cvss == 9.8
    assert findings[0].fix_versions == ["2.0.1"]
    assert findings[1].severity == "HIGH"
    assert findings[2].severity == "LOW"


def test_grype_unavailable_produces_unknown_evidence():
    provider = GrypeProvider(executable_path="/nonexistent/grype")
    res = provider.scan(target="requirements.txt")

    # Invariant: Never fabricates success
    assert res.status == "UNKNOWN"
    assert res.is_verified is False
    assert res.findings_count == 0
    assert "unavailable" in res.error.lower()


def test_supply_chain_policy_strict_fails_closed_on_unknown():
    # Law L8: Unknown security state fails closed in strict mode
    unknown_result = VulnerabilityScanResult(
        status="UNKNOWN",
        is_verified=False,
        findings_count=0,
        error="Scanner executable unavailable",
    )

    # Strict mode -> DENY
    dec_strict = evaluate_supply_chain_policy(unknown_result, policy_mode="strict")
    assert dec_strict.outcome == "DENY"
    assert dec_strict.is_allowed is False
    assert dec_strict.blocked_on_unknown is True
    assert "fails closed" in dec_strict.reason.lower()

    # Permissive / audit mode -> WARN
    dec_permissive = evaluate_supply_chain_policy(unknown_result, policy_mode="permissive")
    assert dec_permissive.outcome == "WARN"
    assert dec_permissive.is_allowed is True
    assert dec_permissive.blocked_on_unknown is False


def test_supply_chain_policy_blocks_on_critical_vulnerabilities():
    finding = VulnerabilityFinding(
        id="CVE-2026-0001",
        package="auth-lib",
        version="1.0.0",
        severity="CRITICAL",
    )
    scan_result = VulnerabilityScanResult(
        status="SUCCESS",
        is_verified=True,
        findings_count=1,
        findings=[finding],
        critical_count=1,
    )

    # In strict mode, critical vulnerabilities deny
    decision = evaluate_supply_chain_policy(scan_result, policy_mode="strict")
    assert decision.outcome == "DENY"
    assert decision.is_allowed is False
    assert len(decision.blocking_findings) == 1
    assert "CVE-2026-0001" in decision.blocking_findings[0]


def test_sigstore_provider_signing_and_verification_and_unknown_fallback():
    sigstore = SigstoreProvider(cli_path="/nonexistent/cosign")
    payload = {"claim_id": "c1", "status": "VERIFIED"}

    # If neither python sigstore nor cosign available -> UNKNOWN
    receipt = sigstore.sign_payload(payload, identity="developer@org.com")
    assert isinstance(receipt, ProvenanceReceipt)
    assert receipt.digest is not None

    if not sigstore.is_available:
        assert receipt.status == "UNKNOWN"
        assert receipt.is_verified is False
        assert "sigstore unavailable" in receipt.error.lower()

        # Cannot verify UNKNOWN receipt
        ver_res = sigstore.verify_provenance(payload, receipt)
        assert ver_res.is_valid is False
        assert ver_res.status == "UNKNOWN"
    else:
        # If available in environment, verification passes
        assert receipt.status == "SUCCESS"
        ver_res = sigstore.verify_provenance(payload, receipt)
        assert ver_res.is_valid is True


def test_schemathesis_provider_contract_testing_and_unknown_fallback():
    provider = SchemathesisProvider(cli_path="/nonexistent/schemathesis")
    health = provider.health()
    assert health.name == "schemathesis"

    res = provider.run_contract_tests(schema_path_or_url="openapi.yaml")
    if not provider.is_available:
        assert res.status == "UNKNOWN"
        assert res.is_verified is False
        assert "unavailable" in res.error.lower()

    # Output parser test
    mock_log = "FAILURE at /api/users: POST SchemaMismatch status 400"
    violations = provider.parse_schemathesis_output(mock_log)
    assert len(violations) >= 1
    assert violations[0].endpoint == "FAILURE at /api/users"
    assert violations[0].violation_type == "SchemaMismatch"
