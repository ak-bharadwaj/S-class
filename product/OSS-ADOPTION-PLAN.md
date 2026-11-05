# OSS Adoption Plan — R9

**Status:** PROPOSED / BLOCKED ON SOURCE FACTS. No tool is marked qualified, accepted, implemented, or production-ready by this plan. This is a product-layer plan only; it does not edit the master lifecycle or create kernel semantics.

## Binding constraints

- The lifecycle labels used here are the frozen names: P0 Intent; P1 Discovery; P2 Requirements; P3 Domain/Data Model + Architecture; P4 Planning; P5 Testing; P6 Implementation; P7 Verification; P8 Diagnosis/Repair; P9 Review; P10 Release; P11 Continuous Engineering. Rows have phase-specific content and do not define a second state machine.
- Authority never moves. **The kernel remains the sole owner** of canonical state, reducer/replay, policy, authorization, budgets, evidence identity/freshness/independence, closure, release readiness and recovery. External tool output is **never authority**: it is untrusted input admitted only through the applicable existing F10 adapter/evidence path. External tools are never authority and are never a second durable store.
- S-Class builds glue and policy only. It does not build an agent loop, IDE, parser, indexer, MCP/ACP implementation, test runner, fuzzer, container runtime, workflow engine, telemetry platform or RAG framework.
- Adoption levels: L1 optional/content-only; L2 replaceable external adapter; L3 narrow runtime substrate; L4 embedded/foundational library. Because the required `oss_facts_pypi.jsonl` file is missing, current allowed use for every proposed tool is L1 only. L2 is a conditional target after evidence. L3/L4 are not proposed in this run. Any tool proven to be younger than the allowed threshold or pre-1.0 remains content-source/optional only, never foundational.
- Current stars, dates/releases, version tags, advisories, licenses, SHA-256 values and any numeric maturity scores are **BLOCKED** because `/mnt/data/oss_facts_pypi.jsonl` is absent. Do not substitute remembered or web-derived facts. Every fact used in a numeric comparison must map to a JSONL row with both `source_url` and `retrieved_at`; without the file, no numeric score or comparative winner is computed. The JSONL key `release_files_last_12mo`, where encountered, counts uploaded FILES, not software releases, and MUST NOT be used as release cadence.
- `M`, `E`, and `J` refer to the existing check classes. M is mechanical; E is evidence/independent evaluation; J routes judgment-dependent or unsupported cases for authorized review. J never passes by absence of findings.

## Proposed integration sequence

| Order | Entry condition | Scope | Exit rule |
|---|---|---|---|
| Gate 0 | Facts file delivered and integrity checked | Gather package/repository facts, licensing, version maturity, hashes and transitive dependencies | Missing source URL/retrieval instant/hash leaves tool L1 and its use optional |
| Gate 1 | Gate 0 source pack complete for a process source | Import intent/spec/process templates as content | Provenance, license and deterministic normalization checks pass; unresolved scope stays human-blocked |
| Gate 2 | Pinned target snapshot available | Repository-intelligence adapters and schema validators | Coverage, stale-index, reference-resolution and malformed-output negative fixtures behave fail-closed |
| Gate 3 | Existing F10 adapter contract available | Contract, type and property-test adapters | Frozen adapter tests, A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation pass |
| Gate 4 | H1b boundary proof recorded | Worker tools and filesystem mutation | No worker launch when required boundary is missing; observed writes are compared with authorized scope |
| Gate 5 | P7 evidence identity and review plan established | Review, dependency audit, SBOM and signature checks | No release if hash, source identity, license, advisory source, signature or required evidence is missing |
| Gate 6 | Release baseline exists | Continuous drift, telemetry and update proposals | Any changed identity invalidates dependent evidence; all new objective work re-enters P0 |

## R9 maturity, runtime and fact-source clarifications

- **Source blocker:** `oss_facts_pypi.jsonl` was not present in the mounted workspace. Consequently, all source-derived stars, release dates/versions, advisories, license expressions, install hashes and numeric scores remain UNVERIFIED/BLOCKED. Do not infer any from prior sweep prose or outside sources.
- **Maturity decision rule:** A row must establish age >=2 years, a version >=1.0, a permissive license and recent release, with `source_url` and `retrieved_at`, before the owner may propose L2 for a replaceable adapter or consider L3 for a narrowly justified substrate. `release_files_last_12mo` counts uploaded files, not upstream release events and must not be used for release cadence. No JSONL-backed row is available here, so no candidate is promoted on maturity evidence in R9.
- **Worker default:** Existing host IDE runtime launched through ExecutionGate; the host is not an OSS package selection and receives no prevention claim without boundary evidence. OpenHands Software Agent SDK, mini-SWE-agent, agent-client-protocol SDK, MCP Python SDK, smolagents and LangGraph are optional L1/L2 adapters only and must never be foundational. SDK age/API maturity is independent of protocol adoption. For the MCP SDK, explicitly qualify the exact 2.x API surface, wire/result schema, transport failures and compatibility; no MCP SDK becomes foundational.
- **Specific license/maintenance flags, not verified facts:** Hypothesis requires MPL-2.0 file-level obligation analysis, including unmodified-use and distribution form; Semgrep engine and rules require separate license/obligation records; detect-secrets is deprioritized in favor of Gitleaks because R9 input flags stale release history, but its release date is not verified in the missing JSONL. `pip-audit`, Tree-sitter and ast-grep license classifiers do not establish SPDX identity; SPDX remains UNVERIFIED until upstream/source feed evidence arrives.
- **Contextual memory:** magic-context/CortexKit is optional L1 only. Its memory output is a claim; it cannot be canonical state, evidence authority, or a second durable store.

## Exact selected-tool/control registry (trace to qualification records)

Each entry below has a matching `R9-NN` record in `OSS-QUALIFICATION-RECORDS.md`. The role/level is a proposal, not evidence of maturity or qualification. The facts file is absent; factual fields remain UNVERIFIED. Host controls are listed separately from installable OSS packages and do not receive an OSS adoption level unless a specific package/distribution is selected.

| R9 record | Exact selected tool/control name | Phase/use and proposed level | F10 category | Gate on missing evidence |
|---|---|---|---|---|
| `R9-01` | GitHub Spec Kit | P0/P4 process-source, L1 | process-source | UNVERIFIED / BLOCKED; never authority |
| `R9-02` | Fission-AI OpenSpec | P2 process-source, L1 | process-source | UNVERIFIED / BLOCKED; never authority |
| `R9-03` | python-jsonschema | P0/P2/P3/P7 schema validator, L1 (conditional L2) | schema validator | UNVERIFIED / BLOCKED; never authority |
| `R9-04` | Tree-sitter core | P1/P3/P6/P7 repo-intelligence, L1 (conditional L2) | repo-intelligence | UNVERIFIED / BLOCKED; never authority |
| `R9-05` | SCIP | P1/P3/P7 repo-intelligence, L1 (conditional L2) | repo-intelligence | UNVERIFIED / BLOCKED; never authority |
| `R9-06` | ast-grep | P1/P3/P6/P8 repo-intelligence, L1 (conditional L2) | repo-intelligence | UNVERIFIED / BLOCKED; never authority |
| `R9-07` | SQLGlot | P3 schema/SQL AST, L1 (conditional L2) | schema validator | UNVERIFIED / BLOCKED; never authority |
| `R9-08` | Semgrep engine | P3/P6/P7/P9/P10 repo-intelligence, L1 | repo-intelligence | UNVERIFIED / BLOCKED; never authority |
| `R9-09` | Semgrep rules bundle | P3/P6/P7/P9/P10 repo-intelligence, L1 | repo-intelligence | UNVERIFIED / BLOCKED; never authority |
| `R9-10` | Bandit | P3/P5/P6/P7/P8/P9/P10 repo-intelligence, L1 (conditional L2) | repo-intelligence | UNVERIFIED / BLOCKED; never authority |
| `R9-11` | Open Policy Agent (OPA) | P3/P4/P9 policy fixture only, L1 | schema validator (envelope only; no direct policy authority) | UNVERIFIED / BLOCKED; never authority |
| `R9-12` | pytest | P5/P7/P8/P9 contract tester, L1 (conditional L2) | contract tester | UNVERIFIED / BLOCKED; never authority |
| `R9-13` | Hypothesis | P5/P7/P8 property-test, L1 (conditional L2) | property-test | UNVERIFIED / BLOCKED; never authority |
| `R9-14` | Schemathesis | P5/P7/P9 API property-test, L1 (conditional L2) | property-test | UNVERIFIED / BLOCKED; never authority |
| `R9-15` | mutmut | P5/P7/P8 mutation diagnostic, L1 optional | mutation | UNVERIFIED / BLOCKED; never authority |
| `R9-16` | coverage.py | P5/P7/P9 coverage sidecar, L1 (conditional L2) | contract tester (coverage sidecar only) | UNVERIFIED / BLOCKED; never authority |
| `R9-17` | Host IDE runtime via ExecutionGate | P6/P8 default worker runtime; existing host-provided runtime, not an OSS package | repo-intelligence (only for target/diff observations; worker is not a verifier) | UNVERIFIED / BLOCKED; never authority |
| `R9-18` | OpenHands Software Agent SDK | P6/P8 optional adapter, L1/L2 conditional only | repo-intelligence (diff/target observation; agent itself not a verifier) | UNVERIFIED / BLOCKED; never authority |
| `R9-19` | mini-SWE-agent | P6/P8 optional adapter, L1/L2 conditional only | repo-intelligence (diff/target observation; agent itself not a verifier) | UNVERIFIED / BLOCKED; never authority |
| `R9-20` | MCP Python SDK | P1/P4/P6 optional protocol adapter, L1/L2 conditional only | schema validator (message/result envelope only) | UNVERIFIED / BLOCKED; never authority |
| `R9-21` | Agent Client Protocol SDK | P4/P6 optional protocol adapter, L1/L2 conditional only | schema validator (message/result envelope only) | UNVERIFIED / BLOCKED; never authority |
| `R9-22` | smolagents | P6/P8 optional candidate only, L1/L2 max after test | repo-intelligence (diff/target observation; agent is not verifier) | UNVERIFIED / BLOCKED; never authority |
| `R9-23` | LangGraph | P6/P8 optional candidate only, L1/L2 max after test | repo-intelligence (diff/target observation; agent is not verifier) | UNVERIFIED / BLOCKED; never authority |
| `R9-24` | mypy | P3/P5/P7/P8/P9 type checker, L1 (conditional L2) | type checker | UNVERIFIED / BLOCKED; never authority |
| `R9-25` | Ruff | P5/P7/P9 repo-intelligence/lint, L1 (conditional L2) | repo-intelligence | UNVERIFIED / BLOCKED; never authority |
| `R9-26` | Gitleaks | P6/P7/P9/P10 secret scanner, L1 (conditional L2) | repo-intelligence | UNVERIFIED / BLOCKED; never authority |
| `R9-27` | pip-audit | P7/P9/P10/P11 Python dependency audit, L1 (conditional L2) | repo-intelligence | UNVERIFIED / BLOCKED; never authority |
| `R9-28` | OSV-Scanner | P9/P10/P11 advisory scan companion, L1 | repo-intelligence | UNVERIFIED / BLOCKED; never authority |
| `R9-29` | Syft | P10 SBOM/artifact inventory, L1 (conditional L2) | repo-intelligence | UNVERIFIED / BLOCKED; never authority |
| `R9-30` | cyclonedx-bom | P10 Python dependency SBOM companion, L1 (conditional L2) | schema validator (SBOM envelope only) plus repo-intelligence input | UNVERIFIED / BLOCKED; never authority |
| `R9-31` | Cosign | P10 release signature/attestation check, L1 | schema validator (attestation envelope only; crypto/trust output is untrusted evidence) | UNVERIFIED / BLOCKED; never authority |
| `R9-32` | OpenTelemetry Python core | P11 optional diagnostics, L1 | repo-intelligence (telemetry only, non-authoritative) | UNVERIFIED / BLOCKED; never authority |
| `R9-33` | Renovate | P11 dependency-update proposal only, L1 | process-source | UNVERIFIED / BLOCKED; never authority |
| `R9-34` | bubblewrap | P6 Linux worker launch boundary candidate, L1 | repo-intelligence for scope/observations only; isolation is an execution control | UNVERIFIED / BLOCKED; never authority |
| `R9-35` | AppArmor profile / host LSM control | P6 Linux defense-in-depth control, not standalone OSS package choice | repo-intelligence for observed enforcement state only | UNVERIFIED / BLOCKED; never authority |
| `R9-36` | Landlock host control | P6 Linux defense-in-depth control, not standalone package choice | repo-intelligence for observed enforcement state only | UNVERIFIED / BLOCKED; never authority |
| `R9-37` | cgroups resource controls | P6 Linux resource boundary facility, not standalone OSS package choice | repo-intelligence for observed enforcement state only | UNVERIFIED / BLOCKED; never authority |
| `R9-38` | magic-context / CortexKit | P1 optional L1 content/memory context only | process-source | UNVERIFIED / BLOCKED; never authority |

## R9 maturity, runtime and fact-source clarifications

- **Source blocker:** `oss_facts_pypi.jsonl` was not present in the mounted workspace. Consequently, all source-derived stars, release dates/versions, advisories, license expressions, install hashes and numeric scores remain UNVERIFIED/BLOCKED. Do not infer any from prior sweep prose or outside sources.
- **Maturity decision rule:** A row must establish age >=2 years, a version >=1.0, a permissive license and recent release, with `source_url` and `retrieved_at`, before the owner may propose L2 for a replaceable adapter or consider L3 for a narrowly justified substrate. `release_files_last_12mo` counts uploaded files, not upstream release events and must not be used for release cadence. No JSONL-backed row is available here, so no candidate is promoted on maturity evidence in R9.
- **Worker default:** Existing host IDE runtime launched through ExecutionGate; the host is not an OSS package selection and receives no prevention claim without boundary evidence. OpenHands SDK, mini-SWE-agent, ACP SDK, MCP SDK, smolagents and LangGraph are optional adapters only. SDK age/API maturity is independent of protocol adoption. For the MCP SDK, explicitly qualify the exact 2.x API surface, wire/result schema, transport failures and compatibility; no MCP SDK becomes foundational.
- **Specific license/maintenance flags, not verified facts:** Hypothesis requires MPL-2.0 file-level obligation analysis, including unmodified-use and distribution form; Semgrep engine and rules require separate license/obligation records; detect-secrets is deprioritized in favor of Gitleaks because R9 input flags stale release history, but its release date is not verified in the missing JSONL. `pip-audit`, Tree-sitter and ast-grep license classifiers do not establish SPDX identity; SPDX remains UNVERIFIED until upstream/source feed evidence arrives.
- **Contextual memory:** magic-context/CortexKit is optional L1 only. Its memory output is a claim; it cannot be canonical state, evidence authority, or a second durable store.

## Exact selected-tool/control registry (trace to qualification records)

Each entry below has a matching `R9-NN` record in `OSS-QUALIFICATION-RECORDS.md`. The role/level is a proposal, not evidence of maturity or qualification. The facts file is absent; factual fields remain UNVERIFIED. Host controls are listed separately from installable OSS packages and do not receive an OSS adoption level unless a specific package/distribution is selected.

| R9 record | Exact selected tool/control name | Phase/use and proposed level | F10 category | Gate on missing evidence |
|---|---|---|---|---|
| `R9-01` | GitHub Spec Kit | P0/P4 process-source, L1 | process-source | UNVERIFIED / BLOCKED; never authority |
| `R9-02` | Fission-AI OpenSpec | P2 process-source, L1 | process-source | UNVERIFIED / BLOCKED; never authority |
| `R9-03` | python-jsonschema | P0/P2/P3/P7 schema validator, L1 (conditional L2) | schema validator | UNVERIFIED / BLOCKED; never authority |
| `R9-04` | Tree-sitter core | P1/P3/P6/P7 repo-intelligence, L1 (conditional L2) | repo-intelligence | UNVERIFIED / BLOCKED; never authority |
| `R9-05` | SCIP | P1/P3/P7 repo-intelligence, L1 (conditional L2) | repo-intelligence | UNVERIFIED / BLOCKED; never authority |
| `R9-06` | ast-grep | P1/P3/P6/P8 repo-intelligence, L1 (conditional L2) | repo-intelligence | UNVERIFIED / BLOCKED; never authority |
| `R9-07` | SQLGlot | P3 schema/SQL AST, L1 (conditional L2) | schema validator | UNVERIFIED / BLOCKED; never authority |
| `R9-08` | Semgrep engine | P3/P6/P7/P9 repo-intelligence, L1 | repo-intelligence | UNVERIFIED / BLOCKED; never authority |
| `R9-09` | Semgrep rules bundle | P3/P6/P7/P9 repo-intelligence, L1 | repo-intelligence | UNVERIFIED / BLOCKED; never authority |
| `R9-10` | Bandit | P3/P5/P7/P9 repo-intelligence, L1 (conditional L2) | repo-intelligence | UNVERIFIED / BLOCKED; never authority |
| `R9-11` | Open Policy Agent (OPA) | P3/P4/P9 policy fixture only, L1 | schema validator (envelope only; no direct policy authority) | UNVERIFIED / BLOCKED; never authority |
| `R9-12` | pytest | P5/P7/P8/P9 contract tester, L1 (conditional L2) | contract tester | UNVERIFIED / BLOCKED; never authority |
| `R9-13` | Hypothesis | P5/P7/P8 property-test, L1 (conditional L2) | property-test | UNVERIFIED / BLOCKED; never authority |
| `R9-14` | Schemathesis | P5/P7/P9 API property-test, L1 (conditional L2) | property-test | UNVERIFIED / BLOCKED; never authority |
| `R9-15` | mutmut | P5/P7/P8 mutation diagnostic, L1 optional | mutation | UNVERIFIED / BLOCKED; never authority |
| `R9-16` | coverage.py | P5/P7/P9 coverage sidecar, L1 (conditional L2) | contract tester (coverage sidecar only) | UNVERIFIED / BLOCKED; never authority |
| `R9-17` | Host IDE runtime via ExecutionGate | P6/P8 default worker runtime; existing host-provided runtime, not an OSS package | repo-intelligence (only for target/diff observations; worker is not a verifier) | UNVERIFIED / BLOCKED; never authority |
| `R9-18` | OpenHands Software Agent SDK | P6/P8 optional adapter, L1/L2 conditional only | repo-intelligence (diff/target observation; agent itself not a verifier) | UNVERIFIED / BLOCKED; never authority |
| `R9-19` | mini-SWE-agent | P6/P8 optional adapter, L1/L2 conditional only | repo-intelligence (diff/target observation; agent itself not a verifier) | UNVERIFIED / BLOCKED; never authority |
| `R9-20` | MCP Python SDK | P1/P4/P6 optional protocol adapter, L1/L2 conditional only | schema validator (message/result envelope only) | UNVERIFIED / BLOCKED; never authority |
| `R9-21` | Agent Client Protocol SDK | P4/P6 optional protocol adapter, L1/L2 conditional only | schema validator (message/result envelope only) | UNVERIFIED / BLOCKED; never authority |
| `R9-22` | smolagents | P6/P8 optional candidate only, L1/L2 max after test | repo-intelligence (diff/target observation; agent is not verifier) | UNVERIFIED / BLOCKED; never authority |
| `R9-23` | LangGraph | P6/P8 optional candidate only, L1/L2 max after test | repo-intelligence (diff/target observation; agent is not verifier) | UNVERIFIED / BLOCKED; never authority |
| `R9-24` | mypy | P3/P5/P7/P8/P9 type checker, L1 (conditional L2) | type checker | UNVERIFIED / BLOCKED; never authority |
| `R9-25` | Ruff | P5/P7/P9 repo-intelligence/lint, L1 (conditional L2) | repo-intelligence | UNVERIFIED / BLOCKED; never authority |
| `R9-26` | Gitleaks | P6/P7/P9/P10 secret scanner, L1 (conditional L2) | repo-intelligence | UNVERIFIED / BLOCKED; never authority |
| `R9-27` | pip-audit | P7/P9/P10/P11 Python dependency audit, L1 (conditional L2) | repo-intelligence | UNVERIFIED / BLOCKED; never authority |
| `R9-28` | OSV-Scanner | P9/P10/P11 advisory scan companion, L1 | repo-intelligence | UNVERIFIED / BLOCKED; never authority |
| `R9-29` | Syft | P10 SBOM/artifact inventory, L1 (conditional L2) | repo-intelligence | UNVERIFIED / BLOCKED; never authority |
| `R9-30` | cyclonedx-bom | P10 Python dependency SBOM companion, L1 (conditional L2) | schema validator (SBOM envelope only) plus repo-intelligence input | UNVERIFIED / BLOCKED; never authority |
| `R9-31` | Cosign | P10 release signature/attestation check, L1 | schema validator (attestation envelope only; crypto/trust output is untrusted evidence) | UNVERIFIED / BLOCKED; never authority |
| `R9-32` | OpenTelemetry Python core | P11 optional diagnostics, L1 | repo-intelligence (telemetry only, non-authoritative) | UNVERIFIED / BLOCKED; never authority |
| `R9-33` | Renovate | P11 dependency-update proposal only, L1 | process-source | UNVERIFIED / BLOCKED; never authority |
| `R9-34` | bubblewrap | P6 Linux worker launch boundary candidate, L1 | repo-intelligence for scope/observations only; isolation is an execution control | UNVERIFIED / BLOCKED; never authority |
| `R9-35` | AppArmor profile / host LSM control | P6 Linux defense-in-depth control, not standalone OSS package choice | repo-intelligence for observed enforcement state only | UNVERIFIED / BLOCKED; never authority |
| `R9-36` | Landlock host control | P6 Linux defense-in-depth control, not standalone package choice | repo-intelligence for observed enforcement state only | UNVERIFIED / BLOCKED; never authority |
| `R9-37` | cgroups resource controls | P6 Linux resource boundary facility, not standalone OSS package choice | repo-intelligence for observed enforcement state only | UNVERIFIED / BLOCKED; never authority |
| `R9-38` | magic-context / CortexKit | P1 optional L1 content/memory context only | process-source | UNVERIFIED / BLOCKED; never authority |

## Phase-by-phase plan

### P0 Intent

**Capabilities needed:** Capture intent, objective boundary, non-goals, source provenance, intent ambiguity and typed input envelope.

**Chosen tool(s), role and level:** GitHub Spec Kit (content source, L1); python-jsonschema (schema-check adapter, L1 now / L2 target). Current factual status is UNVERIFIED because the facts file is absent; keep L1 and do not rank candidates. Conditional L2 is allowed only after the maturity rule and qualification tests pass.

**F10 category:** process-source for Spec Kit; schema validator for the structured input envelope.

**S-Class output path (claim vs evidence):** Spec Kit output is a claim about a proposed workflow/intent. JSON Schema conformance is evidence only that the envelope matches the declared schema. The user/authorized canonical path establishes intent; neither tool can resolve a blocking scope decision.

**MUST gates:** PD-CH2-001, PD-CH2-002; PD-CH3-001, PD-CH3-002, PD-CH3-003, PD-CH3-006; PD-F10-001, PD-F10-002, PD-F10-005.

**Check classes and fail-closed route:** M: schema/envelope and required-field checks; E: source digest and exact schema-version binding; J: unclear intent, scope, or non-goal. Missing fields → MISSING; unresolved intent requiring authority → BLOCKED_ON_HUMAN.

**Fallback:** S-Class-owned intent template and the same frozen schema. Do not silently default a missing objective or interpret prose as a confirmed Decision.

**S-Class builds:** Read and normalize candidate content, bind source digests, emit proposed typed artifacts, expose unanswered questions. Do not build an intent compiler, second requirements store or agent loop.

**Integration order / effort:** Gate 0; effort M. Freeze the input schema and provenance envelope before importing source templates.

**Risk — license, advisories and maturity:** Current license, maintenance, release/advisory and artifact-hash cells are BLOCKED. Keep both sources L1 content-only until current facts and the source pack review are supplied.

### P1 Discovery

**Capabilities needed:** Bounded repository inventory, syntax trees, symbol/reference observations, dependency metadata and explicit index coverage/freshness.

**Chosen tool(s), role and level:** Tree-sitter, SCIP and ast-grep (replaceable repository-intelligence adapters; L1 now / L2 target). CortexKit/magic-context is optional L1 only if separately assessed; memory output is a claim, never a durable store or authority. Current factual status is UNVERIFIED because the facts file is absent; keep L1 and do not rank candidates. Conditional L2 is allowed only after the maturity rule and qualification tests pass.

**F10 category:** repo-intelligence. CortexKit is not selected as a canonical index and is not an F10 verifier.

**S-Class output path (claim vs evidence):** Parsed syntax, index entries, matches and memory summaries are untrusted claims until target snapshot, tool/indexer identity, coverage, omissions and digests are bound. No match never proves absence when index coverage is incomplete.

**MUST gates:** PD-F6-002, PD-CH3-016; PD-CH4-012; PD-CH8-012, PD-CH8-012; PD-F10-001, PD-F10-002, PD-F10-007.

**Check classes and fail-closed route:** M: snapshot digest, index coverage and symbol/path resolution; E: differential reference scan on required symbols; J: unknown language, conflicting indexes or incomplete corpus. Truncation/unresolved symbols → MISSING; unknown coverage → BLOCKED.

**Fallback:** Bounded filesystem/Git inventory plus an independently specified parser/resolver. State uncovered languages and search limits; do not invent a home-built full indexer.

**S-Class builds:** Manage tool invocation, target snapshot binding, freshness/coverage receipts and normalized references. S-Class owns semantic conclusions and freshness invalidation.

**Integration order / effort:** Gate 1 after target identity; effort L due language/grammar/index coverage.

**Risk — license, advisories and maturity:** Current maintenance/advisory/license/hash comparisons are BLOCKED. All candidates remain optional; cortexkit/magic-context stays L1 and its memory output can never be authority or a second state store.

### P2 Requirements

**Capabilities needed:** Turn authorized intent into testable requirements, acceptance links, non-goals, clarification outcomes and traceability.

**Chosen tool(s), role and level:** Fission-AI OpenSpec (content-only proposals, L1); GitHub Spec Kit is the alternate process source; python-jsonschema validates artifacts. Current factual status is UNVERIFIED because the facts file is absent; keep L1 and do not rank candidates. Conditional L2 is allowed only after the maturity rule and qualification tests pass.

**F10 category:** process-source plus schema validator for requirement/acceptance artifact envelopes.

**S-Class output path (claim vs evidence):** Proposal/spec/design/task content is a claim. Schema validation is structural evidence, not requirement confirmation. A blocking clarification must use the existing user/Decision path; sourced template text cannot define canonical requirements.

**MUST gates:** PD-CH2-013, PD-CH2-025; PD-CH3-002, PD-CH3-003, PD-F6-002, PD-CH3-020; PD-F10-001, PD-F10-002, PD-F10-005.

**Check classes and fail-closed route:** M: required fields, typed trace links and acceptance coverage; E: independent orphan/orphan-backlink and schema checks; J: ambiguous intent, competing scope or non-mechanical acceptance. Missing links → MISSING; unconfirmed normative scope → BLOCKED_ON_HUMAN.

**Fallback:** S-Class-owned requirements template and explicit clarification ledger. If source packs conflict, do not choose by tool default or recency.

**S-Class builds:** Map content into existing Requirement/Decision/Acceptance representations, bind provenance and route questions. Do not add a process state machine or persist source-tool phase state.

**Integration order / effort:** Gate 2 after discovery anchors; effort M. Keep source tools out of the runtime path.

**Risk — license, advisories and maturity:** License/version/advisory/hash and maturity facts are BLOCKED. OpenSpec is content-only, not a canonical store or workflow authority.

### P3 Domain/Data Model + Architecture

**Capabilities needed:** Domain entities, invariants, cardinality/cross-entity rules, typed interfaces, SQL schema parsing, architecture elements, dependencies, data-flow edges and static-security checks against the pinned diff/snapshot.

**Chosen tool(s), role and level:** python-jsonschema checks schema envelopes; SQLGlot analyzes SQL syntax/dialect ASTs; Tree-sitter, SCIP and ast-grep provide bounded syntax/reference observations. Semgrep and Bandit are supplemental static-security tools (Semgrep language/rules scope and rules license are separate from the engine; Bandit is Python-scoped). mypy is a Python type-check proposal; OPA may evaluate non-authoritative architecture/policy fixtures only. All remain L1 now because the facts feed and qualification evidence are absent; conditional L2 is a replaceable adapter target only after evidence.

**F10 category:** schema validator (JSON Schema/SBOM-like envelopes); repo-intelligence (Tree-sitter, SCIP, ast-grep, Semgrep, Bandit); type checker (mypy). OPA has no direct policy-authority category in F10: if used for fixture evaluation, normalize its input/output envelope through the existing schema-validator path and treat its decision as a claim. SQLGlot parsing cannot prove database runtime behavior.

**S-Class output path (claim vs evidence):** AST/schema/query results are claims/evidence about syntax and declared structures only. Kernel/F2 invariant semantics, architecture provenance, acceptance and contradiction decisions remain S-Class-owned. Unsupported or undecidable invariants route J and cannot pass.

**MUST gates:** PD-CH2-014 through PD-CH2-026 (as applicable); PD-CH2-028; PD-CH3-016, PD-CH3-017; PD-F10-001, PD-F10-002, PD-F10-005, PD-F10-007.

**Check classes and fail-closed route:** M: typed entity/schema/invariant references, edge/cardinality closure and architecture provenance; E: independent schema/static cross-checks; J: semantic contradiction or unsupported predicate. Unknown/undecidable → MISSING; human review diagnoses but cannot waive absent analysis.

**Fallback:** Hand-authored typed model reviewed against the frozen schema plus a real database/integration test for runtime behavior. Explicitly mark unsupported dialect or language coverage.

**S-Class builds:** Normalize parsed outputs, bind input artifacts and digests, construct proposed links, compare required edges and route gaps. Do not build a parser, indexer or semantic solver.

**Integration order / effort:** Gate 3; effort L because coverage, cross-boundary data-flow and schema binding need qualification fixtures.

**Risk — license, advisories and maturity:** All current license, versions, advisories and hashes are BLOCKED. Keep adapters replaceable and non-foundational until dated maturity evidence clears the L1 restriction.

### P4 Planning

**Capabilities needed:** Decompose approved requirements into bounded tasks, dependency DAG, write sets, verifier coverage, lane/policy limits and rollback/stop conditions.

**Chosen tool(s), role and level:** GitHub Spec Kit and OpenSpec remain L1 process sources. OPA is an optional policy-fixture evaluator only, never the canonical policy or decision authority; its SDK/binary facts are UNVERIFIED. MCP Python SDK and Agent Client Protocol (ACP) SDK are optional, replaceable protocol adapters only when the selected host IDE requires that interface. MCP protocol adoption and MCP Python SDK maturity are different questions: do not infer SDK stability from protocol use; explicitly test exact 2.x API methods, result schemas, transport failure, reconnect and compatibility. The owner-provided list classifies MCP/ACP and the other named agent SDKs as young/optional, so no protocol SDK may become foundational.

**F10 category:** process-source for templates; repo-intelligence for snapshot target lookup. OPA's raw evaluation is a claim; at most, the existing schema-validator adapter validates the result envelope. MCP/ACP messages are untrusted tool outputs admitted only by the existing adapter boundary.

**S-Class output path (claim vs evidence):** Sourced task lists and worker estimates are claims. S-Class-derived task count, dependency acyclicity, target identity, verifier coverage, budgets and overlap checks determine admissibility. No tool owns a workflow or retry engine.

**MUST gates:** PD-CH2-002, PD-CH2-029, PD-F6-006, PD-CH2-031, PD-CH2-032; PD-CH2-058, PD-CH3-009; PD-F10-001, PD-F10-002.

**Check classes and fail-closed route:** M: DAG/limits/write-set and verifier-coverage checks; E: snapshot-bound target-resolution and overlap checks; J: unknown write set, contested dependency or insufficient verifier. Missing verifier or over-limit plan → MISSING/BLOCKED.

**Fallback:** S-Class deterministic WorkGraph generation/checks plus owner-specified decomposition. If process source is unavailable, same policy floor remains.

**S-Class builds:** Translate source task proposals into existing WorkGraph projections, compute inputs and render packs. Do not build a workflow engine, second graph store or alternate retry authority.

**Integration order / effort:** Gate 4 after P3 dependencies; effort M. Must precede any worker launch.

**Risk — license, advisories and maturity:** Current tool maturity/license/advisory/hash facts are BLOCKED. Both process sources are content-only, and the S-Class plan remains the only controlling plan.

### P5 Testing

**Capabilities needed:** Design tests before implementation; freeze complete TestInputSet, acceptance predicates, contract fixtures, property strategies, mutation probes, coverage measurement, type/lint configuration and runner/configuration identity.

**Chosen tool(s), role and level:** pytest runs the declared test collection; Hypothesis supplies property strategies; Schemathesis supplies API-schema-driven tests; mutmut is an optional mutation diagnostic. coverage.py provides Python coverage measurements bound to that same collection; Ruff and mypy supply lint/type diagnostics for test code and fixtures. These are replaceable L1 candidates until the facts row and F10 qualification exist; coverage or lint output alone cannot satisfy correctness.

**F10 category:** contract tester (pytest and collection-bound coverage receipt); property-test (Hypothesis/Schemathesis); mutation (mutmut); type checker (mypy); repo-intelligence (Ruff diagnostics). Declare each output schema/config and bind exact TestInputSet/target/environment identity.

**S-Class output path (claim vs evidence):** A run result is evidence only when bound to the target, TestInputSet manifest and digests, environment, config/plugins/markers, adapter identity/version and output schema. Generated tests and mutation scores are diagnostic evidence, not approval.

**MUST gates:** PD-CH4-009, PD-CH4-009, PD-CH2-010, PD-F6-006; PD-F10-001 through PD-F10-007.

**Check classes and fail-closed route:** M: exact input collection and positive/negative adequacy; E: independent/differential result checks and A1/A2/A3 adapter tests; J: ambiguous oracle or untestable acceptance. Missing/incomplete manifest or mismatch → MISSING; missing independent verifier in required lane → BLOCKED_ON_HUMAN.

**Fallback:** Declared project runner only after exact collection/config identity is known; otherwise explicit fixture-only plan plus BLOCKED for unavailable required coverage. No mutation engine fallback becomes a gate without policy approval.

**S-Class builds:** Freeze test input identity, pass bound schemas and target to adapters, collect raw outputs and normalize result receipts. Do not build a test runner, fuzzer or property engine.

**Integration order / effort:** Gate 5 before implementation; effort M. For mutation, begin only as optional diagnostic.

**Risk — license, advisories and maturity:** Current package licenses, hashes, releases and advisories are BLOCKED. Hypothesis has a specifically requested MPL-2.0 file-level obligation review; its license fact and affected files are not verified in this run.

### P6 Implementation

**Capabilities needed:** Apply authorized bounded changes in a launched workspace, enforce write scope, preserve TestInputSet, bind execution generation, capture observed diffs and support cancellation/recovery.

**Chosen tool(s), role and level:** The default worker is the host IDE's existing runtime launched through the existing ExecutionGate and OS boundary; S-Class does not embed a runtime or build an agent loop. OpenHands SDK and mini-SWE-agent are optional L1/L2 adapters only after qualification, never the primary worker substrate. smolagents and LangGraph remain optional candidates behind the same boundary; no SDK may expand the write scope or hold state. bubblewrap is a Linux isolation candidate; AppArmor, Landlock and cgroups are complementary host controls, not substitutes for ExecutionGate. Because the facts feed and boundary evidence are absent, no prevention claim or level promotion is made.

**F10 category:** repo-intelligence and type checker for target/diff diagnostics. Gitleaks and optional Semgrep/Bandit can inspect proposed changes through the repo-intelligence path; Ruff adds lint observations and mypy adds Python type-check observations, all bound to the same target/config digest. Secret/static/type/lint findings are observations, not approval. Worker tools themselves are not F10 verifiers; patches and worker statements are claims.

**S-Class output path (claim vs evidence):** Worker output enters as proposed delta/claim plus host observations. ExecutionGate, authorized write-set comparison, target snapshot and frozen kernel mechanisms govern effects. A patch, agent summary or green status cannot establish correctness.

**MUST gates:** PD-CH4-010, PD-CH4-014, PD-CH4-014; PD-CH7-013; PD-CH8-009, PD-CH8-010, PD-CH8-011; PD-F10-004.

**Check classes and fail-closed route:** M: target/write-scope and test-input exclusion checks; E: observed delta/digest and post-change snapshot checks; J: unknown side effects or unrecognized host enforcement. Scope breach → BLOCKED; inability to prove boundary → worker not launched.

**Fallback:** Use the host IDE's owner-managed runtime through the same ExecutionGate. An optional OpenHands/mini-SWE-agent/smolagents/LangGraph/ACP/MCP adapter may only run behind an equivalent proven boundary. If host-specific isolation is not demonstrated, do not launch automation: result BLOCKED and route to owner-managed edits. No alternate SDK is permitted to bypass fences, budgets or canonical state.

**S-Class builds:** Provide capability invocation, scope manifest, process/workspace identity, result capture, cancellation and adapter mapping. Do not build an agent loop, IDE, container runtime, durable worker ledger or second state store.

**Integration order / effort:** Gate 6 only after P5 red baseline and sandbox gate; effort L. Sandbox qualification is a hard prerequisite, not a best-effort warning.

**Risk — license, advisories and maturity:** Worker versions, advisories, licenses and artifact hashes are BLOCKED. No native IDE prevention claim; host-native action is detect-and-contain only, with result BLOCKED when required prevention is unavailable.

### P7 Verification

**Capabilities needed:** Re-run the exact designed TestInputSet, type/schema/contract checks and independent verification; produce target- and environment-bound evidence for kernel evaluation.

**Chosen tool(s), role and level:** pytest, Hypothesis, Schemathesis, python-jsonschema, mypy and Ruff; SCIP/Tree-sitter provide bounded reference resolution. Semgrep and Bandit add static-security observations; coverage.py reports Python line/branch observations bound to the exact TestInputSet; Gitleaks checks the target snapshot for secrets. All are L1 until the facts source and adapter evidence are available; potential L2 targets remain conditional. No tool result is release authority.

**F10 category:** contract tester; property-test; type checker; schema validator; repo-intelligence. Coverage.py is attached to the contract-tester receipt and is never a standalone pass/fail oracle; Semgrep/Bandit/Gitleaks findings are repo-intelligence observations.

**S-Class output path (claim vs evidence):** Structured outputs become candidate evidence receipts after identity/schema binding, raw-result retention, freshness/independence checks and kernel evaluation. External PASS/SATISFIED claims never close obligations directly.

**MUST gates:** PD-CH2-009, PD-CH2-010, PD-CH2-042, PD-CH2-045; PD-CH4-002, PD-CH4-006; PD-F10-001 through PD-F10-007.

**Check classes and fail-closed route:** M: result schema, same TestInputSet and target/environment binding; E: independent verifier/differential checks; J: unavailable independent checker or semantic oracle. Any missing/stale/mismatched evidence → MISSING; required independent verifier unavailable → BLOCKED_ON_HUMAN.

**Fallback:** Repeat with a distinct qualified verifier or preserve BLOCKED. A manual review may explain a discrepancy but cannot fabricate missing mechanical evidence.

**S-Class builds:** Bind planned checks to adapter contracts, store immutable raw-result references, normalize outputs and request kernel closure evaluation. Do not build a test runner or acceptance authority.

**Integration order / effort:** Gate 7 after implementation snapshot; effort M. Verification identity must match the P5 input plan.

**Risk — license, advisories and maturity:** All external current facts BLOCKED. A tool result is an observation about its run, not a release decision; the kernel owns evidence closure.

### P8 Diagnosis/Repair

**Capabilities needed:** Classify failure causes, resolve earliest invalid phase, prepare bounded patch alternatives, use RetryBudget, compare after-repair evidence and stop on unknown side effects.

**Chosen tool(s), role and level:** The host IDE runtime remains the default repair worker through ExecutionGate. OpenHands SDK and mini-SWE-agent are optional adapters; ast-grep, Semgrep, Bandit, mypy, Ruff, Hypothesis, pytest and coverage.py can produce bounded diagnostic observations. All worker SDKs remain optional L1/L2 only after maturity, interface and boundary proof; young/pre-1.0 adapters cannot be foundational.

**F10 category:** repo-intelligence, type checker, contract tester and property-test for diagnostic observations; worker reasoning remains claims.

**S-Class output path (claim vs evidence):** Stack traces, mutant kills, type findings and worker explanations are claims or run evidence bound to the failed target. They can propose repair; only the existing lifecycle invalidation and kernel gate route re-evaluates closure.

**MUST gates:** PD-CH2-006, PD-CH2-007, PD-CH2-064; PD-CH8-013, PD-CH8-009, PD-CH8-010, PD-CH8-013; PD-F10-004, PD-F10-007.

**Check classes and fail-closed route:** M: earliest-invalid-phase and RetryBudget gates; E: before/after evidence identity and regression checks; J: ambiguous root cause or unknown external effect. Exhausted budget → stop/escalate; unknown side effect → BLOCKED; new requirement defect re-enters its earliest owning phase.

**Fallback:** Use a deterministic reproducer and owner-authored patch or replace worker behind the same fence. Do not create a repair-only retry loop or reset canonical budget.

**S-Class builds:** Group diagnostics by bound run identity, present repair candidates, compute target invalidations and invoke existing repair/reverification path. Do not build a root-cause engine or alternate retry ledger.

**Integration order / effort:** Gate 8 only after a concrete P7 failure; effort M. Repair must not bypass the P5 input freeze.

**Risk — license, advisories and maturity:** Maturity, license and supply-chain facts are BLOCKED. Any optional young/pre-1.0 tool stays content-source/optional and cannot be a foundational repair dependency.

### P9 Review

**Capabilities needed:** Review change scope, secret exposure, static/lint/type findings, threat coverage, coverage sufficiency, SBOM/advisory identity, independent review and security/test-integrity regressions.

**Chosen tool(s), role and level:** Semgrep (engine and rule bundle separately reviewed), Bandit (Python static-security scope), Ruff (Python lint), mypy (Python type checking), Gitleaks (preferred provisional secret scanner), pytest/Schemathesis (regression checks) and coverage.py (bound coverage report). detect-secrets is deferred because the R9 input flags stale release history; this is a risk flag, not a source-backed cadence score. OPA may be run against fixed policy fixtures only; its decision is not authority. All remain L1 pending evidence.

**F10 category:** repo-intelligence (Semgrep, Bandit, Ruff and Gitleaks; detect-secrets only if later qualified); type checker (mypy); contract tester (pytest plus coverage sidecar); property-test (Schemathesis). OPA output is a claim; the existing schema-validator path may check only its envelope.

**S-Class output path (claim vs evidence):** Scanner findings are bounded observations. A clean scan only describes the tool, rules, snapshot and exclusions used. Kernel/policy determines mandatory findings, waivers, independence and promotion.

**MUST gates:** PD-CH9-008 through PD-CH9-010; PD-CH2-052; PD-CH4-008; PD-F10-005, PD-F10-006, PD-F10-007.

**Check classes and fail-closed route:** M: threat-to-boundary/attack/containment/test mapping; E: run identity, changed TestInputSet digest and critical regression checks; J: severity/oracle ambiguity and authorized waiver. Missing threat coverage, critical regression or unqualified data handling → MISSING/BLOCKED.

**Fallback:** A second scanner may be used only with a declared scope/ruleset; no scan or an excluded path is not a pass. Hold release if required review is unavailable.

**S-Class builds:** Map scanner findings to files/rules/digests, classify them as findings, bind review identity and route disposition to existing authority. Do not build a security scanner or telemetry platform.

**Integration order / effort:** Gate 9 after P7 and before release; effort M. Review must include independent evidence where policy requires it.

**Risk — license, advisories and maturity:** Licenses/advisories/hashes/current releases are BLOCKED. Copyleft/commercial-use exposure is unassessed; do not ship a bundled tool until package-level obligations are reviewed.

### P10 Release

**Capabilities needed:** Inventory build contents using complementary SBOM emitters, audit dependency advisories from pinned inventories, verify signatures/attestations, scan release contents for secrets, bind artifact identity and emit a release evidence packet to the kernel release gate.

**Chosen tool(s), role and level:** pip-audit checks pinned Python dependencies; OSV-Scanner provides an independent advisory-scan candidate over the locked package/SBOM identity; Syft inventories files/artifacts; cyclonedx-bom is a Python-package inventory/format companion, not a substitute for complete artifact scanning; Cosign checks signature/attestation claims; Gitleaks scans the release snapshot for secrets. Semgrep/Bandit and OPA fixture checks may run as supplemental review evidence. Gitleaks is the provisional secret-scan choice; detect-secrets is deferred because the R9 input flags staleness risk, but no release date/cadence is verified. Do not treat either scan as proof of absence. All remain L1 pending exact source facts, artifact hashes, trust-root identity and qualification.

**F10 category:** repo-intelligence for pinned dependency/advisory observations, SBOM inventories and secret/static findings; schema validator for SBOM/attestation envelopes only. Signature checks remain external observations; only kernel release policy can decide release readiness.

**S-Class output path (claim vs evidence):** SBOM, advisory scan and signature result are observations over specified bytes/configuration/source snapshot. Kernel release readiness, policy/approval, rollback and canonical ReleaseEvaluation remain authoritative. Missing SBOM or unresolved identity must not be represented as a clean scan.

**MUST gates:** PD-CH10-008, PD-CH10-009, PD-CH10-011, PD-CH10-009, PD-CH10-011, PD-CH10-013; PD-CH2-010; PD-F10-002, PD-F10-003, PD-F10-005, PD-F10-006.

**Check classes and fail-closed route:** M: artifact/digest/provenance completeness; E: scan and signature verification against the same artifact identity and declared trust roots; J: license applicability or risk acceptance. Missing hash, stale advisory data, signature mismatch, unresolved license risk or missing authority → release BLOCKED.

**Fallback:** Alternate SBOM/scanner/verifier only after its output and coverage equivalence are established; otherwise no release. Never reinterpret missing advisory data as zero advisories.

**S-Class builds:** Generate manifests of inputs/outputs, correlate artifact and tool identity, bind raw results, export audit evidence and ask the kernel for release evaluation. Do not build a release authority or package scanner.

**Integration order / effort:** Gate 10 after review; effort L. Do not promote until hash, license, advisory, trust-root and rollback evidence is complete.

**Risk — license, advisories and maturity:** No current versions, hashes, advisory records or licenses can be verified without `oss_facts_pypi.jsonl`; this gate therefore remains BLOCKED.

### P11 Continuous Engineering

**Capabilities needed:** Observe drift, refresh dependencies, detect changed upstream/tool identity, track advisories and propose requalification or new work while remaining non-terminal.

**Chosen tool(s), role and level:** OpenTelemetry Python for optional diagnostics; Renovate for dependency-update proposals; pip-audit and OSV-Scanner for scheduled advisory checks; Syft/CycloneDX for inventory drift. Outputs can only propose observations/work. Current level is L1 because the facts file is missing; promotion requires source-backed version/hash, license, advisory source and test evidence. Each OpenTelemetry contrib/instrumentation package is qualified separately from core.

**F10 category:** repo-intelligence for pinned dependency/source drift; telemetry itself is diagnostic only and cannot close an obligation.

**S-Class output path (claim vs evidence):** Telemetry spans, issue counts and updater PRs are non-authoritative observations/proposals. A changed tool digest invalidates dependent qualification/evidence under existing freshness rules. Any new objective work re-enters P0; P11 is not terminal.

**MUST gates:** PD-CH2-008, PD-CH2-054, PD-CH10-008, PD-CH10-013; PD-CH5-003, PD-CH5-005; PD-F10-002, PD-F10-003, PD-F10-007.

**Check classes and fail-closed route:** M: compare approved lock/artifact digests and re-entry condition; E: independently re-run affected gates and capture source/scan identity; J: unclassified signal or contested update risk. Missing monitoring means UNKNOWN, not healthy; changed identity invalidates stale approvals/evidence and routes P0 or the earliest affected phase.

**Fallback:** Scheduled owner-run lock scan, static inventory and open issue. No auto-merge, no auto-approval and no direct canonical mutation by updater or telemetry system.

**S-Class builds:** Correlate observations to existing evidence/identity and open review work via current policy; preserve explicit source/freshness. Do not create telemetry infrastructure, a second state store or a new event/state machine.

**Integration order / effort:** Gate 11 after release baseline, then continuous schedule; effort M. Tool additions flow through the same qualification procedure.

**Risk — license, advisories and maturity:** All current OpenTelemetry core/contrib licenses, Renovate version/advisories/hashes and audit-feed freshness are BLOCKED. Loss of telemetry cannot be interpreted as no defects.

## Adoption decision rule

The matrix’s provisional fit choices are not a claim that the “most mature proven” winner was established. The comparative winner is blocked until source-backed scores are available. Do not promote a proposed L2 target, add a direct kernel dependency, execute imported content, or ship a bundled tool solely because it appears in this plan. Until the source facts and F10/platform tests exist, treat external outputs as claims and keep any unavailable required path BLOCKED/MISSING. A successful external run is evidence about that run only; it is never authority.
