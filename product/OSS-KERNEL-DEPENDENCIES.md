# OSS Kernel Dependencies and H1b Mapping — R9

**Status: proposed owner work; not qualified.** The authoritative definitions for H1b X1–X3 and M11 are not present in the mounted task inputs, so the mapping below is a proposed traceability crosswalk that the owner must reconcile. All tool/package facts remain UNVERIFIED because `oss_facts_pypi.jsonl` is absent. The kernel remains the sole owner of state/evidence/release.

## Kernel dependency controls now needed

| Need | Tool/control | Candidate role | H1b/M11 mapping | Evidence to obtain | Fail-closed rule |
|---|---|---|---|---|---|
| Hash-pinned Python dependencies | Exact direct+transitive locks and SHA-256 hashes; `python -m pip install --require-hashes -r locks/<tool>.requirements.txt` | Reproducible installs in disposable environments; do not inject unreviewed deps into trusted kernel environment | **H1b X1** (proposed: dependency identity and install integrity; owner must confirm definition) | Designated PyPI facts row with `source_url` + `retrieved_at`; exact versions, all hashes, lock-generator identity, SBOM correlation and raw install transcript | Missing/mismatched version/hash or facts row => do not install; BLOCKED. No latest/ranges/guessed hashes. |
| Python dependency vulnerability audit | pip-audit; optional independent OSV-Scanner when artifact/binary facts exist | Scan exact locked inventory and bind advisory-source snapshot; scanner output is evidence of that run only | **H1b X2** (proposed: dependency/security review; owner must confirm definition) | Lock/SBOM digest, scanner version/hash, database/source retrieval identity/freshness, exclusions and raw findings | Missing scanner or stale/unknown advisory DB/inventory => BLOCKED; empty output is not zero vulnerabilities. |
| Native artifact identity / provenance | Syft, OSV-Scanner, Gitleaks, Cosign and bubblewrap artifacts; hash manifests and provenance | Pin separate native artifacts; Cosign's result is not a release decision | **H1b X1/X2** (proposed joint link; owner confirms split) | Exact release URL, SHA-256, `source_url`, `retrieved_at`, trust root/signature/provenance and installed file digest. All currently UNVERIFIED. | No source digest/provenance or mismatch => refuse execution and release. |
| Linux isolation | bubblewrap plus AppArmor profile, Landlock rules and cgroups/resource limits, all behind existing ExecutionGate | Defense-in-depth for worker launch only; not a replacement for OS authorization or kernel state | **H1b X3** (proposed: host launch/isolation; owner must confirm definition) | OS/kernel/distribution and control identities; applied namespaces/mount/network/credential settings; loaded AppArmor profile; effective Landlock rules; active cgroups; escape/path/network/secret/resource negative tests | If required prevention is unsupported/unobserved, do not launch; result BLOCKED. Host-native = detect-and-contain; prevention NOT claimed. |
| Changed dependency revalidation | Renovate proposals; pip-audit/OSV-Scanner rescan; optional OpenTelemetry diagnostics | Propose dependency updates and identify affected qualification/evidence; no auto-merge | **M11** (proposed: continuing revalidation; owner must confirm definition) | Lock diff, before/after digest, impacted tools/adapters, refreshed facts rows and rerun F10 evidence | Any identity change invalidates affected evidence; no automatic acceptance/merge/release. Missing telemetry means UNKNOWN. |

## Explicit non-authority constraints

- The tools above never write canonical events/state, create enums/transitions, approve permissions, own budgets, establish evidence independence, close a MUST or approve release.
- Do not add an agent loop, IDE, parser, indexer, MCP/ACP implementation, test runner, fuzzer, container runtime, workflow engine, telemetry platform or RAG framework.
- Never add a second durable store for scan results, memory, policy decisions or telemetry. Raw outputs are external evidence artifacts referenced through the existing canonical evidence path.
- MCP protocol adoption does not establish MCP Python SDK stability. If the host requires that adapter, record its exact 2.x consumed API and run compatibility/error/transport tests; it remains replaceable and non-foundational.

## Open mapping blocker

Provide the source that defines H1b X1, X2, X3 and M11, then reconcile the proposed mapping with those normative definitions. No mapping in this table should be treated as canonical until that check passes.
