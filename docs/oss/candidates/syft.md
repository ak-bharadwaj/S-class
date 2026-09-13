# OSS Candidate Evaluation: Syft & CycloneDX CLI

## 1. Candidate Overview
- **Project**: Syft (`anchore/syft`) & CycloneDX CLI (`CycloneDX/cyclonedx-cli`) — https://github.com/anchore/syft
- **Purpose**: CLI tool and Go library for generating Software Bill of Materials (SBOM) from container images and filesystems across 20+ package ecosystems. CycloneDX CLI provides schema validation, diffing, merging, and attestation signing.
- **License**: Apache License 2.0 (SPDX: `Apache-2.0`). Fully compatible.
- **Primary Language / Ecosystem**: Go core binary. Pre-compiled standalone binaries for all major architectures.

## 2. Maturity & Governance
- **Maturity**: Developed by Anchore; primary tool used in enterprise supply-chain security and US Federal Executive Order 14028 compliance.
- **Maintainer Health**: Large, dedicated security engineering team with active multi-organizational contributions.
- **Release Cadence**: Regular bi-weekly releases; rapid patches for newly discovered packaging formats and CVE catalogs.

## 3. Engineering Rigor & Trustworthiness
- **Security**: Signed binary releases using Sigstore/Cosign with transparency log entries (Rekor). Reproducible builds.
- **Testing**: Thousands of test fixtures covering complex lockfiles, nested dependencies, multi-stage containers, and malformed package manifests.
- **Production Evidence**: Default SBOM generator used by Docker CLI (`docker sbom`), GitHub Actions, and Fortune 500 security pipelines.
- **Platform Coverage**: Linux, macOS, Windows (amd64, arm64).
- **Protocol Compliance**: Strictly complies with SPDX 2.2/2.3 and CycloneDX 1.4/1.5/1.6 JSON/XML formats. Supports in-toto cryptographic attestations.
- **Performance**: High speed cataloging (<2 seconds for large monorepos with thousands of dependencies).

## 4. Architectural Fit & S-Class Boundaries
- **Integration Cost**: Low. Executed as a subprocess or integrated via JSON stream parsing.
- **Failure Modes**: Unsupported package manager format, lockfile syntax error. Handled gracefully with fallback parser.
- **What We Adopt**: SBOM generation, dependency graph extraction, package version delta detection, license discovery.
- **What We DON'T Adopt**: Syft does not adjudicate whether a dependency upgrade is safe. S-Class correlates SBOM deltas with test results, vulnerability databases, and security policies to make the verification verdict.
- **S-Class Wrapper**: `sclass.verification.providers.supply_chain_verifier.SupplyChainVerifier` implementing `VerificationProvider`. Emits `SBOMEvidence` receipts anchored in the cryptographic ledger.
- **Escape Plan**: `VerificationProvider` interface decouples SBOM generation; can swap with Trivy, cdxgen, or native pip/npm dependency parsers.

## 5. Architectural Decision
- **Decision**: `WRAP`
- **Architectural Tier**: Tier 2 (Pluggable Supply-Chain Verification Provider)
- **Rationale Summary**: Software supply-chain security requires accurate, standardized SBOM analysis. Adopting Syft and CycloneDX enables S-Class to independently prove claims like "Dependency update introduced zero license violations and zero critical CVEs."
