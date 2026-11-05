# OSS Fast-Track Review — R16 (2026-10-18)

Scope: tools added to the earlier OSS matrix (CodeRabbit-class reviewers and new agent-harness repos), mapped to P0–P11. Facts come from repo pages read on 2026-10-18 (WebFetch, no GitHub API access in this session). Every fact is **UNVERIFIED for qualification**: no hash, advisory, last-commit date or release date was obtainable. Nothing here is qualified; the kernel keeps all state, evidence, authorization and release authority. Tool output is a claim/candidate, never evidence, until an F10-qualified adapter produces it.

"harness2": no repo by that name was found; I treated it as "new agent-harness repos" (OpenHarness, Statewright, deepagents, opencode, OpenHands). Name the repo if something else was meant.

## Facts read (source page, retrieved 2026-10-18)
| Tool | License (as shown) | Size / maturity signal | Role |
|---|---|---|---|
| CodeRabbit | proprietary SaaS; self-host only in Enterprise | free for public repos | PR review service |
| PR-Agent (qodo-ai/pr-agent) | MIT on repo page (one aggregator says Apache-2.0: conflict, resolve at qualification) | 13.4k stars; community-maintained legacy project donated by Qodo; GitHub/GitLab/Bitbucket/Azure/Gitea; any LiteLLM model | PR review/describe/improve |
| Kodus (kodustech/kodus-ai) | AGPL-3.0 + separate EE license file | 1.3k stars; self-host Docker; BYOK; daily telemetry heartbeat (opt-out env) | PR review with custom rules |
| reviewdog | MIT | 9.5k stars | posts linter output as diff-line review comments |
| HKUDS/OpenHarness | MIT | 16.0k stars; v0.1.7 (2026-04-18); self-described research project | harness: permissions, hooks, memory, MCP client, skills |
| Statewright | Apache-2.0; MCP gateway FSL-1.1-ALv2 (→Apache 2029-05-03) | 474 stars; early (0.2–0.3); 5-task SWE-bench subset only | per-state tool allow-lists via hooks/MCP gateway |
| Trellis (mindfold-ai) | AGPL-3.0 | 13.1k stars | repo-resident specs/PRDs/memory for coding agents |
| deepagents (LangChain) | MIT | 30.3k stars | planning, subagents, virtual FS, HITL |
| OpenHands | MIT (core) | 91.2k stars; docs warn default has no sandbox | agent server + SDK, per-conversation Docker |
| Aider | Apache-2.0 | 49.6k stars | repo map, lint/test loop |
| Trivy | Apache-2.0 | 38.1k stars | vuln/secret/misconfig/license/SBOM |
| Harness² (google-research/harness2) | Apache-2.0 (third_party/benchmarks keep upstream licenses) | 3.1k stars; 3 commits shown, no releases; "not an officially supported Google product"; Linux, Python 3.12 + uv | optimizer that edits a harness (prompt, guardrails, memory, tool guidance, subagents, skills, scripts, plugins) via Propose-Probe-Compose; executors OpenCode/Codex; evals JobBench/LAB/WorkBuddy-Bench |
| goose, opencode | license/stars not obtained from page (opencode fetch failed) | — | host runtimes; leave UNVERIFIED |

## Decisions by phase (fast-track order)
| Phase | Use | Level | Why / constraint |
|---|---|---|---|
| P0–P2 | Spec Kit / OpenSpec (already listed); Trellis **pattern only** | L1 content-only | Trellis is AGPL-3.0 and duplicates our ContextPackage/Requirement authority; do not link or vendor. |
| P1 | tree-sitter + SCIP (already); context7 MCP for library docs; codebase-memory-mcp/token-savior as alternates to magic-context | L1 optional | License of the MCP servers not obtained; treat output as ContextPackage candidates only. |
| P3–P4 | OPA, jsonschema (already) | as before | no new tool needed |
| P5 | pytest, Hypothesis, mutmut (already) | as before | no new tool needed |
| P6 | Host runtimes (opencode, goose, aider, Claude Code) stay **host-native = detect + revert/quarantine** via ExecutionGate. OpenHands SDK / mini-SWE-agent for **launched workers** (prevention allowed). | L2 | Statewright-style per-state tool allow-lists are the right enforcement mechanism for launched workers, but Statewright ships its own state machine, which violates "no second state machine". Adopt only as a hook/gateway that receives `allowed_tools` derived from the kernel gate result; never let it hold phase state. Early-stage (0.2–0.3): prototype behind F10, do not depend. |
| P7 | verification adapters (already) | as before | — |
| P8 | OpenHands / mini-SWE-agent / smolagents / LangGraph (already); deepagents as an equal alternate to LangGraph | L2 conditional | MIT; highest token use in third-party benchmark, so keep behind retry budget. |
| P9 | **PR-Agent** (self-hosted, BYOK) as optional review-claim generator; reviewdog to post adapter findings on diff lines; CodeRabbit allowed only as a host-side advisory service the owner already uses | L1 | Review comments are agent claims: they open findings but never close or waive one (PD-F3-001, authorized waiver only). Kodus rejected as dependency (AGPL + EE license; use only if the owner runs it as a separate service). CodeRabbit cannot be a dependency (proprietary). |
| P9–P11 | Semgrep, Bandit, Gitleaks, OSV-Scanner, pip-audit (already); Trivy as ALTERNATE to Syft+OSV (one tool for vuln/secret/misconfig/SBOM) | L1/L2 | Keep Trivy deferred until a fit comparison is run; it overlaps three listed tools. |
| P10–P11 | Syft, cyclonedx-bom, Cosign, Renovate, OpenTelemetry (already) | as before | — |
| P11 (offline, post-freeze) | **Harness²** as an experiment-only optimizer of skill packs / worker guidance | L1 content-only, no runtime dependency | It self-edits guardrails, memory and skills, and runs with unrestricted network and (for Codex) sandbox disabled. In S-Class every such edit is an agent claim: an optimized harness may only enter as a *candidate* skill-pack/guidance revision, adopted through canonical Policy/pinned-guidance revision plus F10 qualification and A1-A3 gaming fixtures. It must never write guardrails or Policy directly, and runs only in a network-restricted launched worker. 3 commits and no releases: treat as a research reference, not a dependency. |
| Reference only | OpenHarness (permission modes, PreToolUse/PostToolUse hooks, denied_commands, sensitive-path protection) | pattern, no dependency | v0.1.x research project; useful checklist for ExecutionGate hook design. |

## Fast-track build order (owner action)
1. Kernel H0–H7 first; no OSS tool is needed to start.
2. Adapter shells for pytest/ruff/mypy/Semgrep/Gitleaks/OSV (P5–P9) — all mature, all already in the matrix.
3. Launched-worker runtime: OpenHands SDK in per-conversation Docker, with ExecutionGate allow-lists (Statewright pattern optional, prototype only).
4. P9 reviewer: self-hosted PR-Agent adapter emitting claims; reviewdog for tool findings.
5. Defer: Trivy swap, Kodus, Trellis, goose/opencode qualification (host-native, no adapter needed).

## Harness² verdict (added after owner pointer)
Useful idea (measure harness edits by behavioral contrast on the same task) but opposite trust direction to S-Class: it lets the agent rewrite its own guardrails. Adopt the evaluation idea only, as an owner-run P11 experiment; do not integrate before kernel H7. Fits no frozen MUST; no design change.

## New open items
- OSS-F1: resolve PR-Agent license conflict (MIT vs Apache-2.0) from LICENSE file.
- OSS-F2: fetch license/version/last-commit/advisories for every row above from GitHub/PyPI/npm (owner-side; GitHub API not available here).
- OSS-F3: decide whether a Statewright-style allow-list hook is worth F10 qualification (needs a kernel-derived `allowed_tools` spec; no design change before freeze).

## R19 addendum — governance, authorization and provenance batch (retrieved 2026-10-18; pages only, no API; all UNVERIFIED for qualification)
| Project | Facts read | Decision |
|---|---|---|
| Microsoft Agent Governance Toolkit (microsoft/agent-governance-toolkit) | MIT; 6.1k stars; labelled **Public Preview, may have breaking changes before GA**; Python/TS/.NET/Rust/Go; policy engine accepts YAML, OPA Rego, Cedar; intercepts tool calls before execution **at the application-middleware layer in the agent's process boundary** (README recommends one container per agent for OS-level isolation); own identity (Ed25519 DIDs), behavioural trust scores 0-1000, saga/kill-switch runtime, compliance grading. Counts conflict between sources (blog: 9,500+ tests; repo: 992 conformance tests + 7 fuzz targets); the 0.1 ms p99 figure has no stated method | **Reference + optional pre-action hook only.** Run its policy engine in the parent/orchestrator process, never inside the worker it governs (in-process enforcement is bypassable by a hostile agent). Feed it kernel-derived allow-lists as policy input. Do **not** adopt Mesh trust scores, Runtime sagas, SRE budgets or Compliance grading: they are a second authority/state machine and self-computed trust. Read its threat-model and LIMITATIONS docs before qualification. Same role and same caveats as Statewright; pick one hook mechanism for the prototype. |
| OpenHands | MIT core, 91.2k stars (earlier row); enterprise control-plane features (access policy, audit, cost controls) not confirmed to be in the OSS edition | Already the launched-worker runtime. Treat its event log and cost figures as claims; S-Class cost gates need authoritative or host-attested metrics (PD-CH8-013). |
| Open Policy Agent | Apache-2.0; CNCF graduated; 12.2k stars; Go SDK/REST/Wasm folders present; decision-log, bundle-signing and partial-evaluation features **not confirmed from the page** | Keep as optional evaluator for a bounded rule subset. Determinism rule: pass `evaluation_instant` as explicit input and forbid time/network/random builtins; kernel gate semantics stay canonical. in-toto-rego exists but unread. |
| Sigstore / Cosign | Apache-2.0; 6.3k stars; offline verification needs the bundle plus `trusted_root.json` (air-gapped section marked out of date on the page); keyless verification requires pinned certificate identity and issuer; DSSE in-toto attestations | Use for P10 artifact signature verification with pinned identity/issuer and a locally managed trusted root. A valid signature proves who signed which digest, never that the artifact is correct. Offline trusted-root refresh is an open task (OSS-F4). |
| in-toto | 1.1k stars; license **not stated on the page** (verify from LICENSE); verifier needs layout, link files and owner public keys; CLI-documented, Python API not confirmed | Use only for artifact/build provenance at P10-P11. Its layout model overlaps our lifecycle gates; do not let a layout define phase order. |
| OpenSSF Scorecard | not fetched | Candidate automated input to dependency qualification (OSS-F2); a score is a signal, not a verdict. Owner-side fetch. |
| GUAC | not fetched | Reject for now: a queryable graph of SBOM/provenance data would become a second evidence store. |
| SPIFFE/SPIRE | not fetched | Defer: local-first single-host workers do not need workload identity; revisit for multi-host. |
| gVisor | not fetched | Candidate isolation for launched workers on Linux; compare against bubblewrap/Landlock in the P6 qualification, adopt at most one. |
| OpenTelemetry | already listed | Telemetry stays diagnostic, never evidence. |
| Kyverno | not fetched | Out of scope unless S-Class governs Kubernetes deployments. |

Reviewer's point accepted: the largest OSS risk is missing a mature implementation of governance, authorization or provenance, so this batch was added. The consequence is narrow: no frozen MUST changes; OPA, Cosign and in-toto stay verification inputs, and the two hook candidates (Statewright, Agent Governance Toolkit) are prototype-only behind F10 qualification.

New open items: OSS-F4 (offline Sigstore trusted-root management), OSS-F5 (fetch license/version/last-commit/advisories for in-toto, Scorecard, gVisor, SPIFFE), OSS-F6 (choose one pre-action hook mechanism after a bypass test with the hook outside the worker process).


## R23 correction of the R22 addendum (2026-10-19; primary repository pages read via WebFetch on this date, no version pinned, nothing qualified; no MUST, gate, schema or fixture changes)
Superseded R22 claims are retained in the R22 package; the table below is authoritative. Every row stays UNVERIFIED for qualification until the LICENSE bytes, release/tag, provenance and advisories are recorded at a pinned commit.
| Tool | Primary-source finding (repo page, 2026-10-19) | Effect on this design |
|---|---|---|
| PR-Agent (P9) | Repository The-PR-Agent/pr-agent: licence shown MIT; described as community-owned and "in the process of being donated to an open-source foundation"; releases list not shown in my capture (a note cites v0.36.1; a reviewer reports v0.48.0 as latest, unverified here). The R22 claim that the licence "returns to Apache-2.0" came from one secondary article flagged AI-generated and is NOT adopted. | OSS-F1 stays open: record LICENSE bytes/hash at the chosen tag. P9 stays optional; pin org + tag + commit; record foundation-donation and maintainer-count risk. |
| Microsoft Agent Governance Toolkit | Releases page: latest v4.1.0 (June); v3.6.0/v3.7.0 notes say packages are "Microsoft-signed public preview releases" and "may have breaking changes before GA"; v4.0.0 lists a breaking change (45 Python packages consolidated into 5); v4.x notes carry no preview banner and do not state package signing. Licence not shown on that page (v2.1.0 notes said MIT). The earlier v2.1.0 statement that packages were not Microsoft-signed is historical only. | Stays prototype-only (preview stability and overlap with F5/F9 authority). Select an exact version and inspect that release's signatures, provenance and licence before any decision. Its policy results stay claims. |
| OpenHands | software-agent-sdk repo MIT; local workspace or ephemeral Docker/Kubernetes workspaces through Agent Server. "Default is not sandboxed" is version/configuration-dependent and is not relied on. | Rule: never rely on the SDK for containment; S-Class enforces and qualifies the launched-worker boundary itself; host-native stays detect/revert/quarantine. |
| Harness² | Repo: Apache-2.0, v0.1.0, "not an officially supported Google product", executor network access unrestricted, Codex sandbox disabled (secondary write-up, consistent with repo statements I could read). The "run downloaded a benchmark rubric uninstructed" observation is owner/secondary-reported and UNVERIFIED. | Experiment-only (P11). If that observation is ever used as evidence, bundle commit, config, command, egress logs and artifact digests first. |
| OPA | Repo: Apache-2.0, CNCF graduated; MAINTAINERS.md and GOVERNANCE.md exist (contents not read). The "Apple acquired the Styra team" statement is an unverified secondary report and is not recorded as a fact. | Optional evaluator unchanged. Assess maintainer concentration from the pinned MAINTAINERS.md/governance rules, not from press. |
| Cosign / in-toto (P10) | Not rechecked against primary pages. | Pin exact version, identity and trusted root at qualification. |
Not rechecked (need primary files): CodeRabbit terms, Kodus/Trellis licences, Statewright, Scorecard, GUAC, SPIFFE/SPIRE, gVisor, OTel, Kyverno.
