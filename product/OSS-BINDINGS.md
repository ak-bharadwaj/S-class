# S-Class OSS Bindings — research companion (NON-NORMATIVE; no adoption qualified)

**Status:** Draft for owner/reviewer qualification. **Authority:** subordinate to the v6.0.1 frozen package and this v6.0.2 master. This file records where external projects may provide replaceable mechanics; it does not create runtime authority or establish current implementation/production status.

## 1. Binding principles

1. Adoption level is not authority. Even an embedded/foundational library does not write canonical S-Class state.
2. External packages are selected by a versioned qualification record, not by popularity, stars, or an agent assertion. The record must include exact upstream, tag/commit, license and obligations, transitive dependency summary, security posture, test/CI evidence, installation process, OS assumptions, API surface consumed, adapter-contract version, replacement candidate, fallback, and known failure modes.
3. All tool/process outputs are untrusted input until the applicable S-Class adapter and evidence checks admit them.
4. The frozen kernel owns canonical state, reducer/replay, objective and requirements/decision semantics, obligations, authorization, policy floor, budgets, target identity, evidence identity/freshness/independence, assessment, closure, release readiness, recovery and trajectory semantics.
5. S-Class owns the lifecycle playbook, work-type/applicability model, skill resolution and pinning, phase gates, step-pack compiler, guidance protocol and developer interaction policy. This product layer is not an agent loop.

## 2. Capability bindings from the OSS map

| Capability | Candidate project | Adoption target from source map | S-Class binding and qualification boundary |
|---|---|---|---|
| Agent execution | OpenHands Software Agent SDK | L2/L3 | Replaceable worker/execution adapter only. Must not own objective, obligations, acceptance, budgets, evidence closure, replay or release. Qualify workspace, process/tool surface, isolation and cancellation. |
| Minimal worker | mini-SWE-agent | L2 | Optional low-overhead worker adapter. Its claims and outputs remain worker data; qualify exact version, sandbox and evidence capture. |
| Agent/editor protocol | Agent Client Protocol (ACP) | L2 | Interoperability transport. ACP message is not a canonical S-Class event or approval. |
| Tool protocol | MCP Python SDK | L3 | Tool/resource/prompt transport. Capability discovery does not imply authorization; consequential methods require S-Class policy, effect scope, credentials, observation and evidence. |
| Spec process source | GitHub Spec Kit | L2 (process source) | Extract templates/structures into reviewed S-Class-owned process packs. Not an alternate lifecycle or canonical state store. |
| Spec process source | Fission-AI OpenSpec | L2 (process source) | Same content-only boundary: artifacts are proposals compiled into existing Requirement/Decision/Acceptance/Work/Verification representations. |
| Skills/methodology | obra/superpowers | L1/L2 | Skills are sourced content, reviewed and normalized into S-Class manifests. Never grant authority, execute hidden code, suppress gates or fork the lifecycle. |
| Parsing | Tree-sitter | L4 | Parser mechanics only; S-Class owns semantic interpretation and freshness. Pin language grammar/runtime version and resource limits. |
| Structural search/rewrite | ast-grep | L3/L4 | Structural lookup/transformation adapter. Proposed edit must still pass scope, delta, verification and evidence gates. |
| Code intelligence protocol | SCIP | L3 | Index interchange/input. Index data is bounded, versioned evidence, not semantic authority. |
| SQL parsing/analysis | SQLGlot | L4 | SQL syntax/dialect mechanics. Database behavior requires execution or integration evidence; static parsing is not proof. |
| Unit/integration runner | pytest | L3 | Qualified test adapter; structured results, test input set, runner config and environment must be identity-bound. |
| Property testing | Hypothesis | L2/L3 | Replaceable property-test adapter; qualify runtime, strategy/input bounds, seed/replay identity and output schema. |
| API verification | Schemathesis | L2/L3 | API contract/property test adapter; bind schema, target, generated cases, runner config and environment. |
| Real dependency environments | Testcontainers Python | L2/L3 | Environment adapter; bind image/version/config, resource/time limits, output and teardown. |
| Telemetry | OpenTelemetry Python | L3 | Operational observation only. Telemetry becomes acceptance evidence only when a qualified gate explicitly binds source, scope, freshness and integrity. |

The projects, adoption levels and license entries above are copied from the companion's reviewed research map; they are **not an independently current license/security audit**. Before any promotion, verify the actual upstream tag/commit and license text. The source map specifically flags Hypothesis and selected OpenTelemetry packages for exact-license qualification.

## 3. Do-not-build boundary

Unless a measured unmet requirement justifies a new qualified adapter, do not build replacements for an agent loop, IDE, language parser, generic code indexer, generic MCP implementation, generic ACP implementation, test runner, property-testing engine, API fuzzer, browser automation engine, container runtime, telemetry platform, distributed workflow engine or generic RAG framework. The choice to use an external mechanic never transfers semantic authority.

## 4. Required qualification record

Every candidate promoted beyond research status requires: `upstream_repository`, immutable `version_tag_or_commit`, `license_expression_and_obligations`, `transitive_dependency_summary`, `security_review_ref`, `test_ci_evidence_ref`, `install_procedure_digest`, `os_runtime_assumptions`, `consumed_api_surface`, `adapter_contract_version`, `replacement_candidate`, `fallback`, `known_failure_modes`, `qualification_status`, `reviewer_ref`, and `record_digest`. Until qualification succeeds, status is `UNVERIFIED`; relevant phases must remain blocked or use an explicit qualified fallback.

## 5. Skill and process-source binding

External process systems and skill collections are **content sources only**. S-Class must normalize each sourced procedure into the common phase contract, assign check classes (M/E/J), declare inputs/failure routes/cost bounds, validate manifests and provenance, bind license/attribution and content digests, pin versions, and run pack qualification. A source may not lower policy floors, change P0–P11 topology, add canonical events, or self-certify a gate.

Skill resolution and the playbook occupy the canonical tier of context precedence. Stack/project knowledge can specialize implementation and test mechanics but cannot override confirmed requirements, frozen authority, required checks, evidence identity, lane floors or human-authority requirements.

## 6. Primary source files

- `02-OSS/S-CLASS-OSS-ADOPTION-AND-CAPABILITY-MAP.md`, §2 core candidate map, §6 do-not-build list and §7 must-remain-S-Class list.
- `product/OSS-DELTAS.md`, the explicit proposed-delta table used for this R5 reshape. It is non-normative input and does not establish qualification.
- `product/OSS-ADDENDUM-v6.0.2.md` is absent from the mounted input set. No contents are inferred. OI-015 is explicitly **BLOCKED** until the owner supplies that exact source or formally removes the inherited reference; the available `product/OSS-DELTAS.md` is treated only as the supplied non-normative delta input, not as an automatic substitute.

## 7. Reshape alignment (all non-normative)

- S0–S6 remain implementation-order stages. Execution-plan inventory uses R0–R5 to avoid label collisions; this changes names only and adds no phase/state.
- The approved master lifecycle is the sole lifecycle authority. Engineering-intelligence tools propose; S-Class validates phases/gates; a floor compiler renders deterministic packs.
- Skill-source precedence, skill selection, depth-to-existing-phase mapping, deterministic step-pack compilation and canonical playbook precedence are S-Class-owned. Skill sources are reviewed content only. Guidance protocol is not an agent loop.
- IDE-hosted operation must declare E0/E1/E2 capabilities per host/version. E1 prevention is limited to a qualified S-Class-launched boundary; host-native actions are detect-and-contain only. MCP is a tool surface; ACP remains an adapter.
- Verification companions map phase traceability/scope/schema checks and M/E/J; skill-verifier adapters and the Agent-driven adversarial suite / skill-pack evaluation produce evidence, not authority. Corpus, adapter/version, environment and thresholds must be identity-bound.
- A Knowledge Plane is a non-canonical architecture zone for packs, source provenance, index manifests and revocation metadata.
- README/start-here/manifest status labels must distinguish `DESIGNED`, `SCAFFOLDED`, `IMPLEMENTED_UNVERIFIED`. Planned S5 work must not be called implemented.
- Companion splits occur only after approved master freeze and require a manifest, canonical links, digest/version, owner and change-control/supersession record.
- Frozen Decision scope, obligation categories and PROCESS digest representation questions require source inspection and a formal erratum if insufficient. Frozen source files are never edited ad hoc.

## 8. Per-adoption qualification records

Eleven proposed reshaping adoptions have records in `product/OSS-QUALIFICATION-RECORDS.md`. Each of the 16 required fields is `UNVERIFIED`; these stubs are not evidence of current version, license, security, compatibility, integration or release readiness. `qualification_status`, `reviewer_ref` and `record_digest` remain `UNVERIFIED` as well.

## 9. Open qualification boundaries

No candidate is represented here as integrated, implemented, production-ready, or verified. Exact current upstream versions/licenses, adapter qualification, host/OS enforcement claims, and measured performance remain separate implementation/evaluation tasks. See `product/OPEN-ISSUES.md` and the Chapter 10 reality map. OSS text here is non-normative and remains subordinate to the master and frozen v6.0.1 package.
