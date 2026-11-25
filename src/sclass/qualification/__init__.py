"""S2 Qualification Factory package (WI-110..WI-113)."""
from __future__ import annotations

from sclass.qualification.conformance_runner import (
    ConformanceCheckFlags,
    ConformanceSuiteResult,
    ConformanceVerdict,
    ReferenceFixture,
    run_conformance_suite,
)
from sclass.qualification.f10_validation import (
    DEFAULT_RESOURCE_LIMITS,
    build_approval_context_payload,
    check_stale_evidence,
    detect_differential_disagreement,
    validate_resource_limits,
    verify_non_agent_approval_set,
)
from sclass.qualification.facts import (
    REQUIRED_FACTS_FIELDS,
    FactsVerdict,
    FactsVerificationResult,
    ingest_facts_rows,
    parse_spdx_expression,
    verify_facts_row,
)
from sclass.qualification.sandbox_runner import (
    AdvisoryLicenseResult,
    LockValidationResult,
    SandboxInstallResult,
    SandboxVerdict,
    check_advisories_and_licenses,
    run_sandbox_install,
    validate_lock_file,
    verify_transcript_digest,
)

__all__ = [
    "REQUIRED_FACTS_FIELDS",
    "FactsVerdict",
    "FactsVerificationResult",
    "ingest_facts_rows",
    "parse_spdx_expression",
    "verify_facts_row",
    "AdvisoryLicenseResult",
    "LockValidationResult",
    "SandboxInstallResult",
    "SandboxVerdict",
    "check_advisories_and_licenses",
    "run_sandbox_install",
    "validate_lock_file",
    "verify_transcript_digest",
    "DEFAULT_RESOURCE_LIMITS",
    "ConformanceCheckFlags",
    "ConformanceSuiteResult",
    "ConformanceVerdict",
    "ReferenceFixture",
    "build_approval_context_payload",
    "check_stale_evidence",
    "detect_differential_disagreement",
    "run_conformance_suite",
    "validate_resource_limits",
    "verify_non_agent_approval_set",
]
