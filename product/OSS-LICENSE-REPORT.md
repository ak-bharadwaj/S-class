# OSS License Report — R9

**Status: legal qualification BLOCKED.** `oss_facts_pypi.jsonl` was not present. Consequently, every license expression/obligation value in the qualification records remains `UNVERIFIED`; no commercial-use, redistribution or copyleft conclusion is made here. The special items below reflect the R9 owner instructions and must be validated against the designated JSONL source and exact package/source files before any decision.

## Per-chosen-tool license status

| Chosen tool/control | License expression / obligations | Current maturity/fact status | Required owner action / risk |
|---|---|---|---|
| GitHub Spec Kit | UNVERIFIED | UNVERIFIED | Verify exact source, imported-content license and attribution/notice obligations; keep templates content-only. |
| Fission-AI OpenSpec | UNVERIFIED | UNVERIFIED | Verify source and notice terms; no executable lifecycle authority. |
| python-jsonschema | MIT (PyPI metadata; upstream text UNVERIFIED) | first 2012-01-02, latest 2026-01-07 | Reconcile PyPI row, distribution metadata, transitive lock and notices. Flags: latest upload 279 days ago (>6mo). |
| Tree-sitter core + each grammar | UNVERIFIED; license classifier alone is not an SPDX determination | BLOCKED | Exact upstream SPDX/license and each third-party grammar/license separately; no broad conclusion from classifier. |
| SCIP | UNVERIFIED | BLOCKED | Upstream/license/binary release facts and dependency closure missing. |
| ast-grep | classifier-only: MIT License (PyPI metadata; upstream text UNVERIFIED) | first 2023-12-01, latest 2026-10-09 | Need exact distribution/upstream SPDX, native component and transitive obligations. Flags: young or 0.x; 0.x version; SPDX unverified (classifier only). |
| SQLGlot | MIT (PyPI metadata; upstream text UNVERIFIED) | first 2021-03-18, latest 2026-10-09 | Exact PyPI version, license, hash and transitives from row; do not infer from a project label. |
| Semgrep engine | LGPL-2.1-or-later (PyPI metadata; upstream text UNVERIFIED) | first 2020-05-06, latest 2026-10-07 | Review exact engine distribution, LGPL obligations, linkage/modification/distribution model, source/notice duties and commercial use. Do not include this value as a source-verified score. Flags: LGPL engine; rules license UNVERIFIED. |
| Semgrep rule bundle | **UNVERIFIED — analyze separately from engine** | BLOCKED | Record each rule pack source, license, notices, version/digest and redistribution rights. Engine license never implies rules license. |
| Bandit | Apache-2.0 (PyPI metadata; upstream text UNVERIFIED) | first 2015-03-23, latest 2026-02-25 | Exact package/SPDX, transitive dependency and notices. Flags: latest upload 230 days ago (>6mo). |
| Open Policy Agent (OPA) | UNVERIFIED | BLOCKED | GitHub/binary facts absent; verify binary source, exact license/notice and provenance. Output has no policy authority. |
| pytest | MIT (PyPI metadata; upstream text UNVERIFIED) | first 2010-11-25, latest 2026-06-19 | Reconcile exact distribution/license with all plugins and transitive packages. |
| Hypothesis | MPL-2.0 (PyPI metadata; upstream text UNVERIFIED) | first 2013-03-10, latest 2026-10-11 | Inspect file-level scope even for unmodified use; identify any modified/redistributed covered files; preserve notices and satisfy source-availability/reciprocal duties as applicable. Do not assume an unmodified dependency is automatically obligation-free. Until legal review closes, bundling/redistribution of affected package is BLOCKED. Flags: MPL-2.0 file-level obligations. |
| Schemathesis | MIT (PyPI metadata; upstream text UNVERIFIED) | first 2019-08-26, latest 2026-10-12 | Verify exact PyPI license, extras and transitive closure. |
| mutmut | BSD-3-Clause (PyPI metadata; upstream text UNVERIFIED) | first 2016-12-01, latest 2026-09-12 | Verify exact package/license/notice; tool remains optional diagnostic. |
| coverage.py | Apache-2.0 (PyPI metadata; upstream text UNVERIFIED) | first 2009-05-16, latest 2026-09-27 | Verify exact PyPI license and dependency lock. |
| Host IDE runtime | Host/provider terms vary by selected environment; no OSS license asserted | UNVERIFIED / environment-specific | Keep provider/host license and data terms separate from OSS package qualification; no install or redistribution inferred. |
| OpenHands SDK | UNVERIFIED | BLOCKED | Repository/SDK/binary facts absent; review runtime/base image/optional dependency closure; optional only. |
| mini-SWE-agent | MIT License Copyright (c) 2025 Kilian A. Lieret and Carlos E (PyPI metadata; upstream text UNVERIFIED) | first 2025-07-23, latest 2026-07-23 | Exact source/distribution and dependency/license closure missing; optional only. Flags: agent/protocol SDK: fast-moving; first upload 2025-07-23 (<2y). |
| MCP Python SDK | MIT (PyPI metadata; upstream text UNVERIFIED) | first 2024-11-20, latest 2026-10-02 | Protocol adoption is not a license finding; exact SDK distribution/SPDX and transitive dependencies required. Flags: agent/protocol SDK: fast-moving; first upload 2024-11-20 (<2y). |
| Agent Client Protocol SDK | classifier-only: none (PyPI metadata; upstream text UNVERIFIED) | first 2025-09-06, latest 2026-10-12 | Exact repository/version/license and transitive obligations missing; optional only. Flags: agent/protocol SDK: fast-moving; first upload 2025-09-06 (<2y); 0.x version; SPDX unverified (classifier only). |
| smolagents | classifier-only: none (PyPI metadata; upstream text UNVERIFIED) | first 2024-12-27, latest 2026-05-29 | Exact package license and dependency closure required; optional only. Flags: agent/protocol SDK: fast-moving; first upload 2024-12-27 (<2y); SPDX unverified (classifier only). |
| LangGraph | MIT (PyPI metadata; upstream text UNVERIFIED) | first 2024-01-08, latest 2026-10-06 | Exact package/module license and dependency closure required; optional only. Flags: agent/protocol SDK: fast-moving. |
| mypy | MIT (PyPI metadata; upstream text UNVERIFIED) | first 2009-09-09, latest 2026-10-01 | Exact PyPI expression, distribution, dependencies and notices. |
| Ruff | MIT (PyPI metadata; upstream text UNVERIFIED) | first 2022-08-27, latest 2026-10-09 | Exact distribution/binary hash, license and notices. Flags: 0.x version. |
| Gitleaks | UNVERIFIED | BLOCKED | GitHub/binary facts absent; check exact release artifact, embedded notices, signature/provenance and linked/runtime components. |
| pip-audit | classifier-only: Apache Software License (PyPI metadata; upstream text UNVERIFIED) | first 2021-09-16, latest 2026-06-10 | Obtain authoritative SPDX/source license and exact package dependency closure from permitted row and package metadata. Flags: SPDX unverified (classifier only). |
| OSV-Scanner | UNVERIFIED | BLOCKED | GitHub/binary facts absent; verify artifact license, distribution, notices and source/provenance. |
| Syft | UNVERIFIED | BLOCKED | GitHub/binary facts absent; inspect release archive notices, build provenance and transitive/runtime components. |
| cyclonedx-bom | Apache-2.0 (PyPI metadata; upstream text UNVERIFIED) | first 2018-11-17, latest 2026-09-29 | Exact PyPI SPDX/license, package and transitive closure. |
| Cosign | UNVERIFIED | BLOCKED | GitHub/binary facts absent; verify archive, license/NOTICE, build provenance and trust model independently. |
| OpenTelemetry Python core | Apache-2.0 (PyPI metadata; upstream text UNVERIFIED) | first 2019-10-01, latest 2026-10-06 | Core-only result does not cover contrib, exporters, instrumentation or optional extras. |
| OpenTelemetry contrib/instrumentation/exporter packages | UNVERIFIED per package; no blanket license assumption allowed | BLOCKED — package-by-package | Enumerate every selected package/version, its own license/NOTICE, dependencies, data egress and source URL/retrieved time. Do not inherit core SDK license. |
| Renovate | UNVERIFIED | BLOCKED | Verify exact deployment/container digest, license/NOTICE and source distribution; updater has no auto-merge authority. |
| bubblewrap | UNVERIFIED | BLOCKED | GitHub/binary/source-distribution facts absent; verify package/binary, license, notices, provenance and platform-specific build. |
| AppArmor / Landlock / cgroups host facilities | Not treated as an OSS package license finding in this report; distribution/kernel source obligations UNVERIFIED | BLOCKED | Record host OS/distribution package and kernel/license provenance separately; feature/config presence is not an enforcement proof. |
| magic-context / CortexKit | R9 instruction gives MIT as expected target, but current license field remains **UNVERIFIED** | BLOCKED — optional L1 only | Verify repository commit and exact license/notice from allowed evidence; never use memory output as authority or a second durable store. |

## Required special review: Hypothesis MPL-2.0 file-level obligations

Before bundling, modifying, or redistributing Hypothesis-covered files, record the exact version/package hash, license-file path, file-level coverage, whether S-Class modifies covered files, whether the dependency is redistributed or merely consumed, notices, applicable source-availability obligations, transitive licenses, and legal-owner decision. The explicit R9 input says unmodified-use obligations still require review. Until the source row and exact files are reviewed, the record stays UNVERIFIED and the affected distribution decision stays BLOCKED.

## Required special review: Semgrep engine versus rules

Treat the engine and each rules collection as separate components. The R9 instruction flags the engine license as LGPL-2.1-or-later but provides no JSONL row; therefore the license-expression field must remain UNVERIFIED in the qualification record. Separately obtain the rule pack's exact source, version/digest, license, notices, modifications and redistribution rights. Do not use the engine license to infer the rules license.

## Required special review: OpenTelemetry contrib packages

OpenTelemetry Python core and every selected contrib/instrumentation/exporter package must have a separate record of exact identity, license/NOTICE, source URL and retrieval time, dependency closure, optional extras, data egress, exporter destinations and retention. A core SDK license record does not qualify any contrib package. Missing package row or missing data-egress review means BLOCKED.

## Staleness and classifier-only findings

- R9 input flags detect-secrets as stale and recommends preferring Gitleaks. The stated release date cannot be corroborated because the designated JSONL file is missing, so this is a staleness-risk input, not a scored release-cadence fact. Gitleaks facts are also UNVERIFIED until its permitted facts are available.
- `pip-audit`, Tree-sitter and ast-grep license classifiers are not an authoritative SPDX conclusion. Obtain exact upstream SPDX/license text; until then their license fields stay UNVERIFIED.
- No `release_files_last_12mo` uploaded-file count may be used as release cadence.

## Cross-cutting obligations

- Keep package facts, license obligations, security advisory facts, privacy/data-processing terms, host terms and model/API terms as separate review dimensions.
- Retain source/license/NOTICE texts and approval for redistribution, including transitive and optional dependencies, rulesets, grammars, exporters, plugins and native binaries.
- Generate/reconcile the SBOM against actual installed files and hash locks. A schema-valid SBOM is not completeness proof; Syft and cyclonedx-bom inventories must be reconciled for scope differences.
- Any unresolved incompatible/unknown obligation, missing required notice, uncertain copyleft scope or absent commercial-use disposition blocks bundling/release. This is an audit checklist, not a legal opinion.

## Exact chosen-tool record crosswalk

Every listed license field is UNVERIFIED because `oss_facts_pypi.jsonl` was not available. Parenthetical phrases below are risk/review instructions from this request, not source-verified license conclusions. No license, commercial-use, or redistribution approval is made here.

| Qualification record | License field | Required per-tool action |
|---|---|---|
| `R9-01 — GitHub Spec Kit` | UNVERIFIED | UNVERIFIED — obtain allowed source row (for PyPI) or immutable upstream/source-license evidence; retain notices and transitive inventory. |
| `R9-02 — Fission-AI OpenSpec` | UNVERIFIED | UNVERIFIED — obtain allowed source row (for PyPI) or immutable upstream/source-license evidence; retain notices and transitive inventory. |
| `R9-03 — python-jsonschema` | UNVERIFIED | UNVERIFIED — obtain allowed source row (for PyPI) or immutable upstream/source-license evidence; retain notices and transitive inventory. |
| `R9-04 — Tree-sitter core` | UNVERIFIED | UNVERIFIED — classifier is not authoritative SPDX; each grammar separately reviewed. |
| `R9-05 — SCIP` | UNVERIFIED | UNVERIFIED — obtain allowed source row (for PyPI) or immutable upstream/source-license evidence; retain notices and transitive inventory. |
| `R9-06 — ast-grep` | UNVERIFIED | UNVERIFIED — classifier is not authoritative SPDX. |
| `R9-07 — SQLGlot` | UNVERIFIED | UNVERIFIED — obtain allowed source row (for PyPI) or immutable upstream/source-license evidence; retain notices and transitive inventory. |
| `R9-08 — Semgrep engine` | UNVERIFIED | UNVERIFIED — R9 input flag requires LGPL-2.1-or-later obligations review; not a source-verified license field. |
| `R9-09 — Semgrep rules bundle` | UNVERIFIED | UNVERIFIED — rule license must be assessed separately from engine. |
| `R9-10 — Bandit` | UNVERIFIED | UNVERIFIED — obtain allowed source row (for PyPI) or immutable upstream/source-license evidence; retain notices and transitive inventory. |
| `R9-11 — Open Policy Agent (OPA)` | UNVERIFIED | UNVERIFIED — obtain allowed source row (for PyPI) or immutable upstream/source-license evidence; retain notices and transitive inventory. |
| `R9-12 — pytest` | UNVERIFIED | UNVERIFIED — obtain allowed source row (for PyPI) or immutable upstream/source-license evidence; retain notices and transitive inventory. |
| `R9-13 — Hypothesis` | UNVERIFIED | UNVERIFIED — R9 risk flag: perform MPL-2.0 file-level review, including unmodified-use/redistribution scope. |
| `R9-14 — Schemathesis` | UNVERIFIED | UNVERIFIED — obtain allowed source row (for PyPI) or immutable upstream/source-license evidence; retain notices and transitive inventory. |
| `R9-15 — mutmut` | UNVERIFIED | UNVERIFIED — obtain allowed source row (for PyPI) or immutable upstream/source-license evidence; retain notices and transitive inventory. |
| `R9-16 — coverage.py` | UNVERIFIED | UNVERIFIED — obtain allowed source row (for PyPI) or immutable upstream/source-license evidence; retain notices and transitive inventory. |
| `R9-17 — Host IDE runtime via ExecutionGate` | UNVERIFIED | UNVERIFIED — obtain allowed source row (for PyPI) or immutable upstream/source-license evidence; retain notices and transitive inventory. |
| `R9-18 — OpenHands Software Agent SDK` | UNVERIFIED | UNVERIFIED — obtain allowed source row (for PyPI) or immutable upstream/source-license evidence; retain notices and transitive inventory. |
| `R9-19 — mini-SWE-agent` | UNVERIFIED | UNVERIFIED — obtain allowed source row (for PyPI) or immutable upstream/source-license evidence; retain notices and transitive inventory. |
| `R9-20 — MCP Python SDK` | UNVERIFIED | UNVERIFIED — obtain allowed source row (for PyPI) or immutable upstream/source-license evidence; retain notices and transitive inventory. |
| `R9-21 — Agent Client Protocol SDK` | UNVERIFIED | UNVERIFIED — obtain allowed source row (for PyPI) or immutable upstream/source-license evidence; retain notices and transitive inventory. |
| `R9-22 — smolagents` | UNVERIFIED | UNVERIFIED — obtain allowed source row (for PyPI) or immutable upstream/source-license evidence; retain notices and transitive inventory. |
| `R9-23 — LangGraph` | UNVERIFIED | UNVERIFIED — obtain allowed source row (for PyPI) or immutable upstream/source-license evidence; retain notices and transitive inventory. |
| `R9-24 — mypy` | UNVERIFIED | UNVERIFIED — obtain allowed source row (for PyPI) or immutable upstream/source-license evidence; retain notices and transitive inventory. |
| `R9-25 — Ruff` | UNVERIFIED | UNVERIFIED — obtain allowed source row (for PyPI) or immutable upstream/source-license evidence; retain notices and transitive inventory. |
| `R9-26 — Gitleaks` | UNVERIFIED | UNVERIFIED — obtain allowed source row (for PyPI) or immutable upstream/source-license evidence; retain notices and transitive inventory. |
| `R9-27 — pip-audit` | UNVERIFIED | UNVERIFIED — classifier is not authoritative SPDX. |
| `R9-28 — OSV-Scanner` | UNVERIFIED | UNVERIFIED — obtain allowed source row (for PyPI) or immutable upstream/source-license evidence; retain notices and transitive inventory. |
| `R9-29 — Syft` | UNVERIFIED | UNVERIFIED — obtain allowed source row (for PyPI) or immutable upstream/source-license evidence; retain notices and transitive inventory. |
| `R9-30 — cyclonedx-bom` | UNVERIFIED | UNVERIFIED — obtain allowed source row (for PyPI) or immutable upstream/source-license evidence; retain notices and transitive inventory. |
| `R9-31 — Cosign` | UNVERIFIED | UNVERIFIED — obtain allowed source row (for PyPI) or immutable upstream/source-license evidence; retain notices and transitive inventory. |
| `R9-32 — OpenTelemetry Python core` | UNVERIFIED | UNVERIFIED — no assumption may transfer to any contrib/exporter. |
| `R9-33 — Renovate` | UNVERIFIED | UNVERIFIED — obtain allowed source row (for PyPI) or immutable upstream/source-license evidence; retain notices and transitive inventory. |
| `R9-34 — bubblewrap` | UNVERIFIED | UNVERIFIED — obtain allowed source row (for PyPI) or immutable upstream/source-license evidence; retain notices and transitive inventory. |
| `R9-35 — AppArmor profile / host LSM control` | UNVERIFIED | UNVERIFIED — obtain allowed source row (for PyPI) or immutable upstream/source-license evidence; retain notices and transitive inventory. |
| `R9-36 — Landlock host control` | UNVERIFIED | UNVERIFIED — obtain allowed source row (for PyPI) or immutable upstream/source-license evidence; retain notices and transitive inventory. |
| `R9-37 — cgroups resource controls` | UNVERIFIED | UNVERIFIED — obtain allowed source row (for PyPI) or immutable upstream/source-license evidence; retain notices and transitive inventory. |
| `R9-38 — magic-context / CortexKit` | UNVERIFIED | UNVERIFIED — MIT is an owner-provided expectation only; verify source license. |

## Mandatory component-specific review notes

- **Hypothesis:** the request flags MPL-2.0 file-level obligations. Review exact covered files even for unmodified use; distinguish merely consuming a dependency from redistribution, and assess notices/source-availability/reciprocal obligations as applicable. No legal conclusion until the row and package files are examined.
- **Semgrep:** engine and rule bundles have independent source, digest, license and redistribution scope. The input flags LGPL-2.1-or-later as an engine review item; the record remains UNVERIFIED without the allowed row. Rule license remains UNVERIFIED and cannot inherit engine metadata.
- **detect-secrets:** R9 input flags a stale-release risk. The precise release date/cadence is NOT VERIFIED because the facts file is missing; prefer Gitleaks provisionally, but Gitleaks is also UNVERIFIED until binary source/hash/provenance and its license are reviewed.
- **pip-audit, Tree-sitter and ast-grep:** any package license classifier alone does not establish an authoritative SPDX expression; leave SPDX UNVERIFIED until exact upstream/source text and artifact identity are reviewed.
- **OpenTelemetry:** review core, each instrumentation, contrib and exporter package independently for its own license/NOTICE, dependencies, source provenance, data egress and retention. A core license does not confer permissions on other packages.
