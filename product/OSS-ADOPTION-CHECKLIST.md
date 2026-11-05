# OSS Adoption and Qualification Checklist — R9

**Rule:** This procedure records evidence and gates; it does not authorize a tool by self-report. Current status for every candidate is UNVERIFIED. Missing evidence yields BLOCKED. Do not mark any section or external tool ACCEPTED as part of this work.

## Ordered owner procedure

### Source and identity

- [ ] Locate the approved `oss_facts_pypi.jsonl` file and verify it is complete. A missing file blocks fact-based selection; do not supplement stars, dates, releases, advisories, licenses or hashes from memory or other web sources.
- [ ] For each fact used, preserve the exact JSONL object and require its `source_url` and `retrieved_at`. Pass criterion: every factual cell in the matrix traces to those values; otherwise it remains BLOCKED.
- [ ] Bind the upstream repository, exact tag/commit, package/distribution name, artifact URL and applicable native/Python/OS scope. Pass criterion: identity resolves to exactly one immutable candidate; branch names and floating package specs do not pass.
- [ ] Evaluate maturity using sourced release/tag dates and release version. If the candidate is younger than the allowed threshold, pre-1.0, or its age/release stability cannot be established, restrict to L1 optional/content-only. Never make such a tool foundational.

### License and supply chain

- [ ] Inspect the exact license expression/file at the chosen immutable revision plus package metadata, bundled notices, third-party components, extras, optional dependencies and transitive dependency closure. Pass criterion: no unknown license/package edge and explicit obligation disposition; otherwise BLOCKED.
- [ ] For Hypothesis, complete the explicit MPL-2.0 file-level investigation: identify covered files and modifications, notice/source-availability obligations, distribution form and legal owner disposition. Do not treat its license label as verified until source-backed evidence exists.
- [ ] For OpenTelemetry, enumerate core and every selected contrib/instrumentation/exporter package separately. Pass criterion: each package has its own source-backed identity/license/obligation record and data-egress review.
- [ ] Produce a hash-complete lock for every direct and transitive package, or a reviewed SHA-256 manifest for each native binary/archive. Pass criterion: no wildcard/latest/range and all hashes verify before install. Missing hash blocks.
- [ ] Execute the reviewed install command in a disposable environment: Python `python -m pip install --require-hashes -r locks/<tool-id>.requirements.txt`; native artifacts only after `sha256sum --check locks/<tool-id>.sha256` and trust/provenance check. Save raw output and environment identity. No R9 command installs anything today because the facts feed and lock/hash artifacts are absent.
- [ ] Run the source-bound advisory/security check against the exact lock/SBOM. Pass criterion: scanner version, data source/retrieval instant, inventory digest, exclusions, and raw findings are retained; stale or missing feed is BLOCKED.

### F10 adapter and platform proof

- [ ] Declare one F10 adapter category: schema validator, contract tester, type checker, property-test, mutation, or repo-intelligence. Process-source tools must remain content-only and do not run as executable-spec verifiers.
- [ ] Bind immutable tool identity, version/digest, input schema, output schema, adapter configuration, target snapshot, environment and qualification record under the existing adapter contract.
- [ ] Run all frozen F10 adapter tests, A1 reference-fixture conformance, A2 differential-result detection and A3 stale-evidence invalidation. Pass criterion: exact expected outputs on positive and negative cases, no accept-all behavior, no malformed-output acceptance and no stale-result reuse.
- [ ] Verify ExecutionGate launch, lease, budget, fence, cancellation, timeout, write-scope, target-digest and failure semantics. Pass criterion: forbidden effect attempts are blocked at the launched boundary and raw result evidence is identity-bound; otherwise do not launch.
- [ ] Run host-specific negative tests for Linux, macOS, Windows and IDE-hosted modes. Pass criterion: prevention is claimed only for the exact qualified boundary; host-native actions are detect-and-contain, and any unavailable required boundary returns BLOCKED.
- [ ] Confirm output category. Worker, process-source, updater, memory and telemetry results are claims/observations; test/scanner results are run evidence about a particular input and are not acceptance/release authority.

### Evidence, fallback and review

- [ ] Verify the fallback is independently installable and has its own source, license, hash, adapter and platform evidence. Pass criterion: fallback does not bypass budgets, fences, test input binding or authorization. If no equivalent fallback exists, missing capability remains BLOCKED.
- [ ] Validate the exact phase MUST mapping and class M/E/J, including failure route. Pass criterion: every required check is owned by existing S-Class/kernel policy; no tool owns authority and no second event/state store is introduced.
- [ ] Compare license/advisory/source facts against the selection matrix; no candidate wins by unverified popularity, unsupported release-age claim or agent recommendation. Pass criterion: numeric score only exists with source_url and retrieved_at for each fact and the approved rubric.
- [ ] Independently review the raw install, scan, test, sandbox and output-binding evidence. Pass criterion: reviewer is not the sole producer of the evidence being verified, and all discrepancies remain open/blocking until resolved.
- [ ] Fill the 16 mandatory qualification fields only with evidence-backed values; otherwise leave `UNVERIFIED`. Record exact fallback and F10 output handling separately. Pass criterion: identity change revokes or invalidates dependent evidence.
- [ ] Record the promotion or rejection decision through the existing authority path. This checklist does not mark a tool qualified or a phase ACCEPTED.

## R9 owner sequence for newly named tools

- [ ] Qualify Semgrep engine separately from the rules bundle. Pass criterion: engine version/hash/license and each ruleset source/version/hash/license are separate and no excluded path is hidden.
- [ ] Run Bandit only on Python targets and retain the language/scope declaration; it does not replace cross-language analysis.
- [ ] Run Ruff and mypy with pinned configs and full target digest; lint output is not a type-check result and neither output is a pass by itself.
- [ ] Attach coverage.py output to the exact pytest/TestInputSet/environment receipt; missing coverage must remain UNKNOWN and cannot replace correctness tests.
- [ ] Use OPA only for fixed fixtures with a bound policy bundle and exact input/output; route its result as a claim through existing gates, never authority.
- [ ] Generate SBOM/inventory with Syft and use cyclonedx-bom only for its declared Python/package scope; reconcile both outputs to the artifact/files/hash lock before release.
- [ ] Run pip-audit over the exact Python lock and OSV-Scanner over its bound lock/SBOM/data snapshot where qualified; missing/stale advisory data means BLOCKED, not zero findings.
- [ ] Prefer Gitleaks provisionally over detect-secrets; prove binary/config/rules identity and bounded secret fixtures. The R9 input's stale release indication for detect-secrets is not source-verified until the designated feed arrives.
- [ ] Keep the host IDE runtime as default worker through ExecutionGate. Any OpenHands, mini-SWE-agent, MCP/ACP, smolagents or LangGraph adapter remains optional L1/L2, with exact API compatibility and host-boundary tests. MCP 2.x adapter compatibility is a separate check from protocol adoption.
- [ ] Review each OpenTelemetry contrib/exporter independently from core for license, lock, data egress, retention and source facts.

## R9 owner sequence for newly named tools

- [ ] Qualify Semgrep engine separately from the rules bundle. Pass criterion: engine version/hash/license and each ruleset source/version/hash/license are separate and no excluded path is hidden.
- [ ] Run Bandit only on Python targets and retain the language/scope declaration; it does not replace cross-language analysis.
- [ ] Run Ruff and mypy with pinned configs and full target digest; lint output is not a type-check result and neither output is a pass by itself.
- [ ] Attach coverage.py output to the exact pytest/TestInputSet/environment receipt; missing coverage must remain UNKNOWN and cannot replace correctness tests.
- [ ] Use OPA only for fixed fixtures with a bound policy bundle and exact input/output; route its result as a claim through existing gates, never authority.
- [ ] Generate SBOM/inventory with Syft and use cyclonedx-bom only for its declared Python/package scope; reconcile both outputs to the artifact/files/hash lock before release.
- [ ] Run pip-audit over the exact Python lock and OSV-Scanner over its bound lock/SBOM/data snapshot where qualified; missing/stale advisory data means BLOCKED, not zero findings.
- [ ] Prefer Gitleaks provisionally over detect-secrets; prove binary/config/rules identity and bounded secret fixtures. The R9 input's stale release indication for detect-secrets is not source-verified until the designated feed arrives.
- [ ] Keep the host IDE runtime as default worker through ExecutionGate. Any OpenHands, mini-SWE-agent, MCP/ACP, smolagents or LangGraph adapter remains optional L1/L2, with exact API compatibility and host-boundary tests. MCP 2.x adapter compatibility is a separate check from protocol adoption.
- [ ] Review each OpenTelemetry contrib/exporter independently from core for license, lock, data egress, retention and source facts.

## Required raw evidence bundle

- Original facts JSONL file and integrity digest; source URL/retrieval metadata.
- Immutable repository/tag/artifact identity and license/notice files.
- Hash lock/native artifact hash manifest and verified install transcript.
- Dependency inventory/SBOM and source-bound security/advisory scan.
- F10 tests, A1/A2/A3 fixtures, raw outputs, schemas and environment/target digests.
- OS isolation/negative-test logs and fallback results.
- Reviewer decision, open risks, known failure modes and requalification triggers.
