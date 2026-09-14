"""
S-Class Security Subsystem: Supply chain assurance, Sigstore provenance, and API assurance (RC.15).
"""

from sclass.security.supply_chain import (
    SyftProvider,
    GrypeProvider,
    ToolHealth,
    SBOMResult,
    PackageInfo,
    VulnerabilityFinding,
    VulnerabilityScanResult,
    SupplyChainPolicyDecision,
    evaluate_supply_chain_policy,
    promote_to_verified,
)
from sclass.security.provenance import (
    SigstoreProvider,
    ProvenanceReceipt,
    ProvenanceVerificationResult,
)
from sclass.security.api_assurance import (
    SchemathesisProvider,
    SchemathesisCLIProvider,
    SchemathesisPythonProvider,
    ContractViolation,
    APIAssuranceResult,
)

__all__ = [
    "SyftProvider",
    "GrypeProvider",
    "ToolHealth",
    "SBOMResult",
    "PackageInfo",
    "VulnerabilityFinding",
    "VulnerabilityScanResult",
    "SupplyChainPolicyDecision",
    "evaluate_supply_chain_policy",
    "promote_to_verified",
    "SigstoreProvider",
    "ProvenanceReceipt",
    "ProvenanceVerificationResult",
    "SchemathesisProvider",
    "SchemathesisCLIProvider",
    "SchemathesisPythonProvider",
    "ContractViolation",
    "APIAssuranceResult",
]
