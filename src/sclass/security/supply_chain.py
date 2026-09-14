"""
S-Class Security: External Supply-Chain Evidence Engine (RC.15).
Integrates Syft (SBOM) and Grype (Vulnerability Scanner) as external executable providers.
Never vendors or embeds executables.
Unavailable tools produce UNKNOWN/UNVERIFIED evidence and never fabricate success.
Whether UNKNOWN blocks is determined by S-Class policy/risk, not hard-coded globally.
"""

from __future__ import annotations
import os
import json
import time
import shutil
import hashlib
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple, Union


@dataclass(frozen=True)
class ToolHealth:
    """Operational status and capability discovery for an external security tool."""
    name: str
    available: bool
    version: str
    executable_path: Optional[str] = None
    status: str = "HEALTHY"  # HEALTHY | UNAVAILABLE | DEGRADED
    capabilities: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "available": self.available,
            "version": self.version,
            "executable_path": self.executable_path,
            "status": self.status,
            "capabilities": list(self.capabilities),
            "error": self.error,
        }


@dataclass(frozen=True)
class PackageInfo:
    """Normalized package / dependency metadata from SBOM."""
    name: str
    version: str
    type: str = "generic"
    license: str = "UNKNOWN"
    purl: str = ""
    cpe: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "type": self.type,
            "license": self.license,
            "purl": self.purl,
            "cpe": self.cpe,
        }


@dataclass(frozen=True)
class SBOMResult:
    """Normalized SBOM generation evidence."""
    status: str  # SUCCESS | UNKNOWN | ERROR
    is_verified: bool = False
    format: str = "spdx-json"
    packages_count: int = 0
    packages: List[PackageInfo] = field(default_factory=list)
    evidence_state: str = "OBSERVED"  # OBSERVED | VERIFIED | UNKNOWN | ERROR
    tool_version: str = "unknown"
    execution_duration: float = 0.0
    error: Optional[str] = None
    raw_json: Optional[Dict[str, Any]] = None
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "is_verified": self.is_verified,
            "evidence_state": self.evidence_state,
            "format": self.format,
            "packages_count": self.packages_count,
            "packages": [p.to_dict() for p in self.packages],
            "tool_version": self.tool_version,
            "execution_duration": self.execution_duration,
            "error": self.error,
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class VulnerabilityFinding:
    """Normalized vulnerability vulnerability finding."""
    id: str
    package: str
    version: str
    severity: str  # CRITICAL | HIGH | MEDIUM | LOW | NEGLIGIBLE | UNKNOWN
    fix_versions: List[str] = field(default_factory=list)
    cvss: Optional[float] = None
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "package": self.package,
            "version": self.version,
            "severity": self.severity,
            "fix_versions": list(self.fix_versions),
            "cvss": self.cvss,
            "description": self.description,
        }


@dataclass(frozen=True)
class VulnerabilityScanResult:
    """Normalized vulnerability scan evidence."""
    status: str  # SUCCESS | UNKNOWN | ERROR
    is_verified: bool = False
    findings_count: int = 0
    findings: List[VulnerabilityFinding] = field(default_factory=list)
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    evidence_state: str = "OBSERVED"  # OBSERVED | VERIFIED | UNKNOWN | ERROR
    tool_version: str = "unknown"
    execution_duration: float = 0.0
    error: Optional[str] = None
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "is_verified": self.is_verified,
            "evidence_state": self.evidence_state,
            "findings_count": self.findings_count,
            "findings": [f.to_dict() for f in self.findings],
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "low_count": self.low_count,
            "tool_version": self.tool_version,
            "execution_duration": self.execution_duration,
            "error": self.error,
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class SupplyChainPolicyDecision:
    """S-Class policy verdict evaluating supply-chain evidence."""
    outcome: str  # ALLOW | DENY | WARN
    is_allowed: bool
    policy_mode: str
    reason: str
    blocked_on_unknown: bool = False
    blocking_findings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outcome": self.outcome,
            "is_allowed": self.is_allowed,
            "policy_mode": self.policy_mode,
            "reason": self.reason,
            "blocked_on_unknown": self.blocked_on_unknown,
            "blocking_findings": list(self.blocking_findings),
        }


class SyftProvider:
    """
    External executable provider for Syft Software Bill of Materials (SBOM) generator.
    Never vendors or embeds Syft.
    """

    def __init__(self, executable_path: Optional[str] = None):
        self.bin_path = (
            executable_path
            or os.environ.get("SYFT_BIN")
            or shutil.which("syft")
        )

    @property
    def is_available(self) -> bool:
        return self.bin_path is not None and os.path.isfile(self.bin_path)

    def health(self) -> ToolHealth:
        """Discovers capabilities, version, and execution health."""
        if not self.bin_path or not shutil.which(self.bin_path):
            return ToolHealth(
                name="syft",
                available=False,
                version="unavailable",
                status="UNAVAILABLE",
                capabilities=[],
                error="Syft executable not found in system PATH. Install syft or set SYFT_BIN.",
            )

        try:
            res = subprocess.run([self.bin_path, "version"], capture_output=True, text=True, timeout=5.0)
            ver = res.stdout.strip().splitlines()[0] if res.stdout else "syft-unknown"
            return ToolHealth(
                name="syft",
                available=True,
                version=ver,
                executable_path=self.bin_path,
                status="HEALTHY",
                capabilities=["sbom.generate", "spdx-json", "cyclonedx-json", "syft-json"],
            )
        except Exception as ex:
            return ToolHealth(
                name="syft",
                available=False,
                version="error",
                executable_path=self.bin_path,
                status="DEGRADED",
                capabilities=[],
                error=str(ex),
            )

    def generate_sbom(
        self,
        target_path: str,
        format: str = "spdx-json",
        timeout: float = 30.0,
    ) -> SBOMResult:
        """
        Executes Syft to generate an SBOM for the target.
        If Syft is unavailable, produces UNKNOWN/UNVERIFIED evidence. Never fabricates success.
        """
        health = self.health()
        if not health.available:
            return SBOMResult(
                status="UNKNOWN",
                is_verified=False,
                format=format,
                packages_count=0,
                packages=[],
                tool_version="unavailable",
                error="Syft executable unavailable. Output marked UNKNOWN/UNVERIFIED.",
                provenance={
                    "provider": "syft",
                    "status": "UNAVAILABLE",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

        t0 = time.perf_counter()
        abs_target = os.path.abspath(target_path)
        cmd = [self.bin_path, abs_target, "-o", format]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            duration = time.perf_counter() - t0

            if proc.returncode != 0:
                return SBOMResult(
                    status="ERROR",
                    is_verified=False,
                    format=format,
                    packages_count=0,
                    packages=[],
                    tool_version=health.version,
                    execution_duration=duration,
                    error=proc.stderr.strip() or f"Syft exited with non-zero code {proc.returncode}",
                    provenance={
                        "provider": "syft",
                        "status": "ERROR",
                        "exit_code": proc.returncode,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

            packages = self.parse_sbom_output(proc.stdout, format=format)
            raw = None
            try:
                raw = json.loads(proc.stdout)
            except Exception:
                pass

            out_hash = hashlib.sha256(proc.stdout.encode("utf-8")).hexdigest()
            return SBOMResult(
                status="SUCCESS",
                is_verified=False,
                evidence_state="OBSERVED",
                format=format,
                packages_count=len(packages),
                packages=packages,
                raw_json=raw,
                tool_version=health.version,
                execution_duration=duration,
                provenance={
                    "provider": "syft",
                    "executable": self.bin_path,
                    "sha256": out_hash,
                    "target": abs_target,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

        except subprocess.TimeoutExpired:
            return SBOMResult(
                status="UNKNOWN",
                is_verified=False,
                evidence_state="UNKNOWN",
                format=format,
                packages_count=0,
                tool_version=health.version,
                execution_duration=timeout,
                error=f"Syft execution timed out after {timeout}s",
                provenance={"provider": "syft", "status": "TIMEOUT"},
            )
        except Exception as ex:
            return SBOMResult(
                status="UNKNOWN",
                is_verified=False,
                evidence_state="UNKNOWN",
                format=format,
                packages_count=0,
                tool_version=health.version,
                error=str(ex),
                provenance={"provider": "syft", "status": "EXCEPTION"},
            )

    def parse_sbom_output(self, raw_output: str, format: str = "spdx-json") -> List[PackageInfo]:
        """Parses SPDX or CycloneDX JSON into normalized PackageInfo instances."""
        try:
            data = json.loads(raw_output)
        except Exception:
            return []

        packages: List[PackageInfo] = []

        # SPDX JSON format
        if "packages" in data and isinstance(data["packages"], list):
            for p in data["packages"]:
                name = p.get("name", "unknown")
                version = p.get("versionInfo", "unknown")
                lic = p.get("licenseConcluded") or p.get("licenseDeclared") or "UNKNOWN"
                purl = ""
                for ext in p.get("externalRefs", []):
                    if ext.get("referenceType") == "purl":
                        purl = ext.get("referenceLocator", "")
                packages.append(PackageInfo(
                    name=name,
                    version=version,
                    type="spdx",
                    license=str(lic),
                    purl=purl,
                ))

        # CycloneDX JSON format
        elif "components" in data and isinstance(data["components"], list):
            for c in data["components"]:
                name = c.get("name", "unknown")
                version = c.get("version", "unknown")
                ptype = c.get("type", "library")
                purl = c.get("purl", "")
                licenses = []
                for lic_item in c.get("licenses", []):
                    if "license" in lic_item and "id" in lic_item["license"]:
                        licenses.append(lic_item["license"]["id"])
                packages.append(PackageInfo(
                    name=name,
                    version=version,
                    type=ptype,
                    license=", ".join(licenses) if licenses else "UNKNOWN",
                    purl=purl,
                ))

        # Syft native JSON format
        elif "artifacts" in data and isinstance(data["artifacts"], list):
            for art in data["artifacts"]:
                packages.append(PackageInfo(
                    name=art.get("name", "unknown"),
                    version=art.get("version", "unknown"),
                    type=art.get("type", "generic"),
                    license=", ".join(art.get("licenses", [])) if art.get("licenses") else "UNKNOWN",
                    purl=art.get("purl", ""),
                ))

        return packages


class GrypeProvider:
    """
    External executable provider for Grype Vulnerability Scanner.
    Never vendors or embeds Grype.
    Unavailable tools produce UNKNOWN/UNVERIFIED evidence. Never fabricates success.
    """

    def __init__(self, executable_path: Optional[str] = None):
        self.bin_path = (
            executable_path
            or os.environ.get("GRYPE_BIN")
            or shutil.which("grype")
        )

    @property
    def is_available(self) -> bool:
        return self.bin_path is not None and os.path.isfile(self.bin_path)

    def health(self) -> ToolHealth:
        """Discovers capabilities, version, and execution health."""
        if not self.bin_path or not shutil.which(self.bin_path):
            return ToolHealth(
                name="grype",
                available=False,
                version="unavailable",
                status="UNAVAILABLE",
                capabilities=[],
                error="Grype executable not found in system PATH. Install grype or set GRYPE_BIN.",
            )

        try:
            res = subprocess.run([self.bin_path, "version"], capture_output=True, text=True, timeout=5.0)
            ver = res.stdout.strip().splitlines()[0] if res.stdout else "grype-unknown"
            return ToolHealth(
                name="grype",
                available=True,
                version=ver,
                executable_path=self.bin_path,
                status="HEALTHY",
                capabilities=["vulnerability.scan", "severity.filtering", "json.output"],
            )
        except Exception as ex:
            return ToolHealth(
                name="grype",
                available=False,
                version="error",
                executable_path=self.bin_path,
                status="DEGRADED",
                capabilities=[],
                error=str(ex),
            )

    def scan(
        self,
        target: str,
        is_sbom: bool = False,
        severity_threshold: str = "HIGH",
        timeout: float = 30.0,
    ) -> VulnerabilityScanResult:
        """
        Executes Grype vulnerability scan on directory or SBOM file.
        If Grype is unavailable, produces UNKNOWN/UNVERIFIED evidence. Never fabricates success.
        """
        health = self.health()
        if not health.available:
            return VulnerabilityScanResult(
                status="UNKNOWN",
                is_verified=False,
                findings_count=0,
                findings=[],
                tool_version="unavailable",
                error="Grype executable unavailable. Scan evidence is UNKNOWN/UNVERIFIED.",
                provenance={
                    "provider": "grype",
                    "status": "UNAVAILABLE",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

        t0 = time.perf_counter()
        target_arg = f"sbom:{os.path.abspath(target)}" if is_sbom else os.path.abspath(target)
        cmd = [self.bin_path, target_arg, "-o", "json"]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            duration = time.perf_counter() - t0

            if proc.returncode != 0 and not proc.stdout.strip():
                return VulnerabilityScanResult(
                    status="ERROR",
                    is_verified=False,
                    findings_count=0,
                    tool_version=health.version,
                    execution_duration=duration,
                    error=proc.stderr.strip() or f"Grype exited with error code {proc.returncode}",
                    provenance={"provider": "grype", "status": "ERROR"},
                )

            findings = self.parse_grype_output(proc.stdout)
            critical = sum(1 for f in findings if f.severity == "CRITICAL")
            high = sum(1 for f in findings if f.severity == "HIGH")
            medium = sum(1 for f in findings if f.severity == "MEDIUM")
            low = sum(1 for f in findings if f.severity in ("LOW", "NEGLIGIBLE"))

            out_hash = hashlib.sha256(proc.stdout.encode("utf-8")).hexdigest()
            return VulnerabilityScanResult(
                status="SUCCESS",
                is_verified=False,
                evidence_state="OBSERVED",
                findings_count=len(findings),
                findings=findings,
                critical_count=critical,
                high_count=high,
                medium_count=medium,
                low_count=low,
                tool_version=health.version,
                execution_duration=duration,
                provenance={
                    "provider": "grype",
                    "executable": self.bin_path,
                    "sha256": out_hash,
                    "target": target,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

        except subprocess.TimeoutExpired:
            return VulnerabilityScanResult(
                status="UNKNOWN",
                is_verified=False,
                evidence_state="UNKNOWN",
                findings_count=0,
                tool_version=health.version,
                execution_duration=timeout,
                error=f"Grype scan timed out after {timeout}s",
                provenance={"provider": "grype", "status": "TIMEOUT"},
            )
        except Exception as ex:
            return VulnerabilityScanResult(
                status="UNKNOWN",
                is_verified=False,
                findings_count=0,
                tool_version=health.version,
                error=str(ex),
                provenance={"provider": "grype", "status": "EXCEPTION"},
            )

    def parse_grype_output(self, raw_output: str) -> List[VulnerabilityFinding]:
        """Parses Grype JSON output into normalized VulnerabilityFinding instances."""
        try:
            data = json.loads(raw_output)
        except Exception:
            return []

        findings: List[VulnerabilityFinding] = []
        matches = data.get("matches", [])
        for m in matches:
            vuln = m.get("vulnerability", {})
            artifact = m.get("artifact", {})

            vuln_id = vuln.get("id", "UNKNOWN-CVE")
            sev = (vuln.get("severity") or "UNKNOWN").upper()
            pkg_name = artifact.get("name", "unknown")
            pkg_ver = artifact.get("version", "unknown")

            # CVSS
            cvss_val = None
            cvss_list = vuln.get("cvss", [])
            if cvss_list and isinstance(cvss_list, list):
                metrics = cvss_list[0].get("metrics", {})
                cvss_val = metrics.get("baseScore")

            # Fix versions
            fix_versions = []
            fix_info = vuln.get("fix", {})
            if "versions" in fix_info and isinstance(fix_info["versions"], list):
                fix_versions = fix_info["versions"]

            findings.append(VulnerabilityFinding(
                id=vuln_id,
                package=pkg_name,
                version=pkg_ver,
                severity=sev,
                fix_versions=fix_versions,
                cvss=cvss_val,
                description=vuln.get("description", ""),
            ))

        return findings


def promote_to_verified(result: Any) -> Any:
    """Promotes corroborated tool observation (OBSERVED) to VERIFIED S-Class evidence."""
    if isinstance(result, SBOMResult):
        return SBOMResult(
            status=result.status,
            is_verified=True,
            evidence_state="VERIFIED",
            format=result.format,
            packages_count=result.packages_count,
            packages=result.packages,
            raw_json=result.raw_json,
            tool_version=result.tool_version,
            execution_duration=result.execution_duration,
            error=result.error,
            provenance=dict(result.provenance),
        )
    elif isinstance(result, VulnerabilityScanResult):
        return VulnerabilityScanResult(
            status=result.status,
            is_verified=True,
            evidence_state="VERIFIED",
            findings_count=result.findings_count,
            findings=result.findings,
            critical_count=result.critical_count,
            high_count=result.high_count,
            medium_count=result.medium_count,
            low_count=result.low_count,
            tool_version=result.tool_version,
            execution_duration=result.execution_duration,
            error=result.error,
            provenance=dict(result.provenance),
        )
    elif type(result).__name__ == "APIAssuranceResult" or hasattr(result, "violations_count"):
        from sclass.security.api_assurance import APIAssuranceResult
        if isinstance(result, APIAssuranceResult):
            return APIAssuranceResult(
                status=result.status,
                is_verified=True,
                evidence_state="VERIFIED",
                endpoints_tested=result.endpoints_tested,
                violations_count=result.violations_count,
                violations=result.violations,
                execution_duration=result.execution_duration,
                tool_version=result.tool_version,
                error=result.error,
                provenance=dict(result.provenance),
            )
    return result



def evaluate_supply_chain_policy(
    result: Union[SBOMResult, VulnerabilityScanResult],
    policy_mode: str = "strict",
    block_on_unknown: Optional[bool] = None,
    allowed_severities: Optional[List[str]] = None,
) -> SupplyChainPolicyDecision:
    """
    Evaluates supply chain security evidence against S-Class policy and risk rules.
    Law L8: Unknown security state fails closed when configured in strict mode.
    Whether UNKNOWN blocks is determined by policy/risk, not hard-coded globally.
    """
    # 1. Handle UNKNOWN Evidence
    is_unknown = (result.status == "UNKNOWN") or (getattr(result, "evidence_state", "") == "UNKNOWN") or (not result.is_verified and getattr(result, "evidence_state", "") != "OBSERVED")
    if is_unknown:
        should_block = block_on_unknown if block_on_unknown is not None else (policy_mode.lower() in ("strict", "enforce", "high_risk"))
        if should_block:
            return SupplyChainPolicyDecision(
                outcome="DENY",
                is_allowed=False,
                policy_mode=policy_mode,
                reason="Policy DENY: Unknown security state fails closed in strict policy mode (Law L8). External tool evidence is unverified.",
                blocked_on_unknown=True,
            )
        else:
            return SupplyChainPolicyDecision(
                outcome="WARN",
                is_allowed=True,
                policy_mode=policy_mode,
                reason="Policy WARN: Tool unavailable or output unverified; allowed by permissive policy/risk setting.",
                blocked_on_unknown=False,
            )

    # 2. Handle Vulnerability Scan Results
    if isinstance(result, VulnerabilityScanResult):
        blocking_severities = allowed_severities or ["CRITICAL", "HIGH"]
        violations = [
            f"{f.id} in {f.package} ({f.severity})"
            for f in result.findings
            if f.severity.upper() in blocking_severities
        ]

        if violations and policy_mode.lower() in ("strict", "enforce"):
            return SupplyChainPolicyDecision(
                outcome="DENY",
                is_allowed=False,
                policy_mode=policy_mode,
                reason=f"Policy DENY: Found {len(violations)} vulnerabilities exceeding threshold: {', '.join(violations[:3])}",
                blocking_findings=violations,
            )
        elif violations:
            return SupplyChainPolicyDecision(
                outcome="WARN",
                is_allowed=True,
                policy_mode=policy_mode,
                reason=f"Policy WARN: Found {len(violations)} vulnerabilities exceeding threshold in audit mode.",
                blocking_findings=violations,
            )

    # 3. Clean Verified Outcome
    return SupplyChainPolicyDecision(
        outcome="ALLOW",
        is_allowed=True,
        policy_mode=policy_mode,
        reason="Supply chain verification successful: Evidence corroborated and policy compliant.",
    )
