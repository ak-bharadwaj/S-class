# MUST allocation rows (generated from the master definitions)

This is an allocation/traceability index, not a status decision. Reviewer status remains `UNSET`; no section or MUST is marked ACCEPTED by this file.

| MUST ID | Owning section | Class | Requirement (master row excerpt) | Fixture/test reference(s) | Reviewer status |
|---|---|---|---|---|---|
| `PD-CH1-001` | `1.1` | M | S-Class MUST be specified as a control plane rather than an IDE, model, agent loop, workflow engine, replacement parser/indexer, or replacement external engineering mechanism. | UNRESOLVED | UNSET (reviewer-owned) |
| `PD-CH1-002` | `1.2` | M | Every v6.0.2 product rule MUST be subordinate to the frozen v6.0.1 package. | UNRESOLVED | UNSET (reviewer-owned) |
| `PD-CH1-004` | `1.5` | M | A product-layer concept MUST belong to exactly one declared classification and MUST NOT be presented as a kernel type. | UNRESOLVED | UNSET (reviewer-owned) |
| `PD-CH1-005` | `1.6` | M | Every new product artifact MUST declare authority_class using the product taxonomy. This is a classification field, not a self-asserted trust verdict. | UNRESOLVED | UNSET (reviewer-owned) |
| `PD-CH1-006` | `1.8` | M | No namespace is permitted to define authority over another namespace. | UNRESOLVED | UNSET (reviewer-owned) |
| `PD-CH1-007` | `1.9` | M | v1 MUST preserve the full authority floor while limiting shipped implementation to the declared v1 slice. | UNRESOLVED | UNSET (reviewer-owned) |
| `PD-CH10-007` | `10.6` | M | Version/qualification and issue/claim registries MUST be internally cross-linked to the master. | CH10-T7 | UNSET (reviewer-owned) |
| `PD-CH10-008` | `10.1` | M | Compatibility MUST be explicit across kernel, protocol, schema, adapter and pack versions; unsupported pairs block. | CH10-T8 | UNSET (reviewer-owned) |
| `PD-CH10-009` | `10.2` | M | Audit export MUST bind canonical sequence range, digests, gate inputs/outputs and explicit truncation or missing-data declarations. | CH10-T10 | UNSET (reviewer-owned) |
| `PD-CH10-010` | `10.3` | M | The roadmap MUST use only H0–H7, assign each capability a dependency and exit test, and must not represent planning as implemented capability. | CH10-T12 | UNSET (reviewer-owned) |
| `PD-CH10-011` | `10.4` | M | Every surfaced implementation fact MUST be classified as keep/replace/retire/qualify and evidence-backed or UNVERIFIED. | CH10-T14 | UNSET (reviewer-owned) |
| `PD-CH10-012` | `10.5` | M | A frozen change MUST require a formal erratum path and concrete insufficiency/replay analysis; frozen source is never edited ad hoc. | CH10-T16 | UNSET (reviewer-owned) |
| `PD-CH10-013` | `10.6` | M | Every open issue MUST name impact, owner, evidence/decision needed, blocking phase and status; OI-008 remains OPEN until two raw fresh-chat reviews are owner-supplied. | CH10-T18 | UNSET (reviewer-owned) |
| `PD-CH2-001` | `2.1` | M | Every work type MUST execute as a projection of the same P0–P11 lifecycle. | UNRESOLVED | UNSET (reviewer-owned) |
| `PD-CH2-002` | `2.4` | M | Every P-phase MUST define all eleven dimensions. | UNRESOLVED | UNSET (reviewer-owned) |
| `PD-CH2-003` | `2.2` | M | A later phase MUST NOT make an invalid earlier phase valid. | CH2-T3 | UNSET (reviewer-owned) |
| `PD-CH2-005` | `2.2` | M | Every skipped phase MUST have an explicit evaluator-checkable applicability result. | CH2-T5 | UNSET (reviewer-owned) |
| `PD-CH2-006` | `2.2` | M/E | A discovered defect MUST route to the earliest affected phase. | CH2-T6 | UNSET (reviewer-owned) |
| `PD-CH2-007` | `2.2` | M | P8 repair MUST consume the frozen RetryBudget and MUST NOT create an alternate retry path. | CH2-T7 | UNSET (reviewer-owned) |
| `PD-CH2-008` | `2.2` | M | P11 MUST be non-terminal; new work MUST re-enter at P0. | CH2-T8 | UNSET (reviewer-owned) |
| `PD-CH2-009` | `2.2` | M/E | A model DONE claim MUST NOT close work without admissible evidence and kernel-evaluated closure. | CH2-T9 | UNSET (reviewer-owned) |
| `PD-CH2-010` | `2.2` | E | A green external run MUST be treated only as run evidence bound to its inputs, not as completion by itself. | CH2-T10 | UNSET (reviewer-owned) |
| `PD-CH2-011` | `2.2` | M | Stack/skill changes MUST NOT create a lifecycle fork or remove core phases. | CH2-T11 | UNSET (reviewer-owned) |
| `PD-CH2-012` | `2.2` | M/E | Human judgment MUST NOT waive mandatory mechanical/evidence floors except through existing authorized waiver/break-glass paths. | CH2-T12 | UNSET (reviewer-owned) |
| `PD-CH2-013` | `2.9` | M | Every applicable requirement has semantic coverage or an explicit applicability outcome. | CH2-T13 | UNSET (reviewer-owned) |
| `PD-CH2-014` | `2.9` | M | Required domain/data invariants are represented. | CH2-T14 | UNSET (reviewer-owned) |
| `PD-CH2-015` | `2.9` | M | Each required architecture element has attributable requirement, Decision or source-digest provenance. | CH2-T15 | UNSET (reviewer-owned) |
| `PD-CH2-016` | `2.9` | M | Materially affected dependency relationships are represented. | CH2-T16 | UNSET (reviewer-owned) |
| `PD-CH2-017` | `2.9` | M | DomainModel meets the measurable substance predicate above. | CH2-T17 | UNSET (reviewer-owned) |
| `PD-CH2-018` | `2.9` | M | ArchitectureRecord meets the measurable substance predicate above. | CH2-T18 | UNSET (reviewer-owned) |
| `PD-CH2-020` | `2.9` | M/E | Invariants use the F2 decidable fragment; unsupported/undecidable cases route J and cannot PASS. | CH2-T20 | UNSET (reviewer-owned) |
| `PD-CH2-021` | `2.9` | M | Cross-entity constraints include explicit relationships and cardinalities. | CH2-T21 | UNSET (reviewer-owned) |
| `PD-CH2-022` | `2.9` | M | Architecture dependency edges cover the ChangeSurfaceAnalysis boundary closure. | CH2-T22 | UNSET (reviewer-owned) |
| `PD-CH2-023` | `2.9` | M/E | Boundary-crossing data-flow binds source, destination, contract and transformation. | CH2-T23 | UNSET (reviewer-owned) |
| `PD-CH2-024` | `2.9` | M | Interface signatures agree with typed domain contracts and requirement predicates. | CH2-T24 | UNSET (reviewer-owned) |
| `PD-CH2-025` | `2.9` | M/J | Every unknown or undecidable contradiction MUST return MISSING; authorized human review may diagnose the cause but cannot waive absent analysis. | CH2-T25 | UNSET (reviewer-owned) |
| `PD-CH2-026` | `2.9` | M | Existing ADR/design sources are digest-bound and pass structure/reference lint. | CH2-T26 | UNSET (reviewer-owned) |
| `PD-CH2-028` | `2.9` | M | MUST IDs are unique, reserved and never reassigned. | CH2-T28 | UNSET (reviewer-owned) |
| `PD-CH2-029` | `2.10` | M | P4 MUST enforce task-count and task-unit caps from the F4 lane's canonical Policy defaults. | CH2-T29 | UNSET (reviewer-owned) |
| `PD-CH2-031` | `2.10` | M | WorkGraph dependency edges MUST be acyclic. | CH2-T31 | UNSET (reviewer-owned) |
| `PD-CH2-032` | `2.10` | M/E/J | Known write-set overlap MUST serialize mechanically; unknown/undeclared write sets MUST block for human resolution. | CH2-T32; CH2-T32b | UNSET (reviewer-owned) |
| `PD-CH2-033` | `2.11` | M | The test-carrying canonical delta MUST precede the implementation delta by canonical delta sequence, not clock time. | CH2-T33 | UNSET (reviewer-owned) |
| `PD-CH2-034` | `2.11` | E | A red run MUST come from the qualified adapter and fail the designed test for the designed assertion class/targets; harness errors, skip/xfail, timeout, and unstable reruns do not count. | CH2-T34 | UNSET (reviewer-owned) |
| `PD-CH2-035` | `2.11` | M/E | Executable specifications MUST satisfy F1/F2 representation and finite-domain constraints. | CH2-T35 | UNSET (reviewer-owned) |
| `PD-CH2-036` | `2.11` | E | Required test adapters MUST be qualified under F10. | CH2-T36 | UNSET (reviewer-owned) |
| `PD-CH2-037` | `2.12` | M | Implementation writes MUST be ExecutionGate-authorized for exact task/scope/target. | CH2-T37 | UNSET (reviewer-owned) |
| `PD-CH2-038` | `2.12` | M | Scope growth MUST stop and route to P4. | CH2-T38 | UNSET (reviewer-owned) |
| `PD-CH2-039` | `2.12` | E | Implementation claims MUST use F7's type and created_by_delta rules. | CH2-T39 | UNSET (reviewer-owned) |
| `PD-CH2-040` | `2.12` | M | Product records MUST NOT create canonical delta authority or override kernel denial. | CH2-T40 | UNSET (reviewer-owned) |
| `PD-CH2-041` | `2.13` | M | Verification evidence MUST bind frozen evidence identity and current target/step. | CH2-T41 | UNSET (reviewer-owned) |
| `PD-CH2-042` | `2.13` | E | Required adapter results MUST come from qualified F10 adapters. | CH2-T42 | UNSET (reviewer-owned) |
| `PD-CH2-043` | `2.13` | M/E | Independence MUST meet F4 depth-derived floor. | CH2-T43 | UNSET (reviewer-owned) |
| `PD-CH2-044` | `2.13` | M | Freshness MUST use frozen predicate at recorded evaluation instant. | CH2-T44 | UNSET (reviewer-owned) |
| `PD-CH2-045` | `2.13` | M/E/J | Closure MUST be kernel-owned; per-task results MUST use F5 schema and feed P9/P10. | CH2-T45 | UNSET (reviewer-owned) |
| `PD-CH2-046` | `2.11` | M/E | P5 MUST NOT authorize a red run until the primary test digest is present in the complete TestInputSet bound under PD-CH4-009. | CH2-T46 | UNSET (reviewer-owned) |
| `PD-CH2-047` | `2.11` | E | Red classification MUST use adapter structured result and designed test/reason tuple, never agent assertions. | CH2-T47 | UNSET (reviewer-owned) |
| `PD-CH2-048` | `2.12` | M | P6 gate MUST invoke the complete TestInputSet exclusion check owned by PD-CH4-010; this MUST does not redefine TestInputSet membership. | CH2-T48 | UNSET (reviewer-owned) |
| `PD-CH2-050` | `2.13` | M/E | P7 MUST reject nondeterministic test reruns; complete input/manifest/environment identity is exclusively checked by PD-CH4-010. | CH2-T50 | UNSET (reviewer-owned) |
| `PD-CH2-051` | `2.14` | M/E | P8 MUST route failure to the earliest affected phase and stop when the existing RetryBudget is exhausted. | CH2-T51 | UNSET (reviewer-owned) |
| `PD-CH2-052` | `2.15` | M/E/J | P9 MUST aggregate all required P7 task results and close each mandatory finding only by evidence or canonical authority. | CH2-T52 | UNSET (reviewer-owned) |
| `PD-CH2-053` | `2.16` | M/J | P10 MUST require frozen kernel ReleaseEvaluation for exact target/policy and MUST NOT override kernel denial. | CH2-T53 | UNSET (reviewer-owned) |
| `PD-CH2-054` | `2.17` | M/E/J | P11 MUST ground signals in canonical facts and route new objective work through P0 without autonomous canonical mutation. | CH2-T54 | UNSET (reviewer-owned) |
| `PD-CH2-055` | `2.2` | M | The lifecycle gate MUST invalidate every downstream projection whose authoritative dependency digest changes, and the changed binding MUST be visible in the recomputation key. | CH2-T55 | UNSET (reviewer-owned) |
| `PD-CH2-056` | `2.7` | M | P1 MUST classify an unresolvable target snapshot, incomplete index coverage, or missing high-impact unknown outcome as MISSING rather than infer completeness. | CH2-T57 | UNSET (reviewer-owned) |
| `PD-CH2-057` | `2.7` | M | P1 MUST resolve required skills and depth against policy/profile precedence and pin their digests into the context/step-pack binding before a downstream phase can pass. | CH2-T59 | UNSET (reviewer-owned) |
| `PD-CH2-058` | `2.18` | M | A work type MUST resolve to exactly one declared applicability record for each P0–P11 phase, including an explicit skip reason; the matrix covers every registered work type and phase pair without implicit defaults, and a deferred rule names its re-entry phase. | CH2-T61 | UNSET (reviewer-owned) |
| `PD-CH2-060` | `2.20` | M | Every default user-facing flow MUST preserve P0–P11 order and route upstream defects to the earliest affected phase. | CH2-T65 | UNSET (reviewer-owned) |
| `PD-CH2-061` | `2.21` | M | Every operations/delivery flow MUST bind its entry predicate, required gate outputs and rollback/stop condition. | CH2-T67 | UNSET (reviewer-owned) |
| `PD-CH2-062` | `2.22` | M | Project-class qualification MUST require explicit fit evidence and must not infer qualification from repository language or size alone. | CH2-T69 | UNSET (reviewer-owned) |
| `PD-CH2-063` | `2.23` | M | The question budget MUST be enforced as an integer count with a declared per-batch default and unresolved blockers MUST remain open when exhausted. | CH2-T71 | UNSET (reviewer-owned) |
| `PD-CH2-064` | `2.24` | M | Invalidation is owned by `PD-CH2-055`; this MUST adds only that replay restarts from the earliest affected phase and stale downstream results cannot remain usable. | CH2-T73 | UNSET (reviewer-owned) |
| `PD-CH2-065` | `2.25` | M | Each lifecycle proof example MUST state preconditions, bound inputs, expected gate output and the specific failure route; prose-only examples are not proof. | CH2-T75 | UNSET (reviewer-owned) |
| `PD-CH3-001` | `3.8` | M | Every phase artifact MUST bind the objective revision and canonical SpecAnchor digests; invalidation of dependents is owned by `PD-CH2-055`. | CH3-T1 | UNSET (reviewer-owned) |
| `PD-CH3-002` | `3.8` | M/E | Normative requirements MUST have testable acceptance links, explicit non-goals, and no unresolved normative placeholders. | CH3-T2 | UNSET (reviewer-owned) |
| `PD-CH3-003` | `3.8` | E/J | Clarification answers changing scope MUST enter canonical Decision/Requirement mechanisms; absent human confirmation blocks. | CH3-T3 | UNSET (reviewer-owned) |
| `PD-CH3-006` | `3.8` | E | External process tools MUST remain untrusted candidates until adapter/content qualification is recorded. | CH3-T6 | UNSET (reviewer-owned) |
| `PD-CH3-007` | `3.8` | M | Work type MUST be projected from an existing canonical Decision scope/outcome without a product-owned state machine; invalidation is owned by `PD-CH2-055`. | CH3-T7 | UNSET (reviewer-owned) |
| `PD-CH3-009` | `3.8` | E | Each default user-facing flow MUST preserve its required gates/evidence and compute lane from canonical profile/policy. | CH3-T9 | UNSET (reviewer-owned) |
| `PD-CH3-010` | `3.8` | E | Upgrade, migration, performance, CI, and PR-review flows MUST bind relevant baselines and rollback/verification inputs before closure. | CH3-T10 | UNSET (reviewer-owned) |
| `PD-CH3-011` | `3.8` | E | Project-class adaptation MUST preserve common gates and mark each unqualified adapter/pack as an open qualification, not as supported. | CH3-T11 | UNSET (reviewer-owned) |
| `PD-CH3-012` | `3.8` | M/E | UX adaptation MUST preserve mandatory gates/anchors; interruption budgets MUST NOT suppress an authority-required human decision. | CH3-T12 | UNSET (reviewer-owned) |
| `PD-CH3-014` | `3.8` | E | Canonical lifecycle examples MUST exercise real gate outputs and at least one adversarial claim and test-integrity failure. | CH3-T14 | UNSET (reviewer-owned) |
| `PD-CH3-015` | `3.1` | M | Every product artifact MUST bind objective revision, source digest, artifact type and owning authority; product documents cannot shadow canonical objects. | CH3-T15 | UNSET (reviewer-owned) |
| `PD-CH3-016` | `3.2` | M | Every normative requirement MUST resolve to an exact spec path, symbol/heading and line range; unresolved means MISSING, and a changed anchor digest invalidates all dependent artifacts. | CH3-T17 | UNSET (reviewer-owned) |
| `PD-CH3-017` | `3.3` | M | Mechanical spec-quality predicates MUST use explicit measurable thresholds bound to the policy digest (an unbound or edited threshold is MISSING; weakening goes through `PD-F1-005`) and unsupported/undecidable predicates cannot return PASS. | CH3-T19 | UNSET (reviewer-owned) |
| `PD-CH3-018` | `3.4` | M | A blocking clarification MUST have an authorized outcome or remain MISSING/BLOCKED_ON_HUMAN; silence and model inference are not confirmation. | CH3-T21 | UNSET (reviewer-owned) |
| `PD-CH3-020` | `3.6` | M | Invalidation is owned by `PD-CH2-055`; this MUST adds only that a spec change identifies the earliest replay point for affected work/evidence. | CH3-T25 | UNSET (reviewer-owned) |
| `PD-CH4-002` | `4.8` | M/E | Claims of execution MUST bind qualified adapter structured results and raw result identity. | CH4-T2 | UNSET (reviewer-owned) |
| `PD-CH4-005` | `4.8` | M/E | Changed authoritative inputs MUST invalidate dependent claims/evidence using frozen freshness/dependency rules. | CH4-T5 | UNSET (reviewer-owned) |
| `PD-CH4-006` | `4.8` | E | False-completion MUST be recorded only from canonical outcome/evidence events; agent prose has no closure authority. | CH4-T6 | UNSET (reviewer-owned) |
| `PD-CH4-007` | `4.8` | M/E | Context resume MUST rebuild anchors from canonical state and reject transcript-only authority. | CH4-T7 | UNSET (reviewer-owned) |
| `PD-CH4-008` | `4.8` | M | All listed threat classes MUST map to a detection, gate, containment, and fixture. | CH4-T8 | UNSET (reviewer-owned) |
| `PD-CH4-009` | `4.4` | M | P5 MUST bind a qualified adapter-declared complete TestInputSet before red, including tests, conftest, fixtures, test data, runner configuration, markers, plugins, collection/discovery inputs and environment... | CH4-T27; CH4-T9 | UNSET (reviewer-owned) |
| `PD-CH4-010` | `4.4` | M/E | P6 MUST exclude every path in the bound TestInputSet from implementation writes; P7 evidence MUST use the same manifest, per-entry content digests, environment digest and designed test ID, and the same test ... | CH4-T10; CH4-T11; CH4-T12 | UNSET (reviewer-owned) |
| `PD-CH4-012` | `4.2` | M | Every path/symbol/line reference MUST resolve exactly against the pinned target snapshot and indexed source; any unresolved or ambiguous reference is MISSING, never fuzzy-match PASS. | CH4-T15 | UNSET (reviewer-owned) |
| `PD-CH4-013` | `4.3` | RETIRED | No active predicate remains; retired duplicate of PD-CH4-009/010 and identifier must never be reassigned. | CH4-T9; CH4-T10; CH4-T11; CH4-T12 (surviving owner fixtures) | UNSET (reviewer-owned) |
| `PD-CH4-014` | `4.4` | M | An observed delta outside the authorized write/scope set MUST return BLOCKED and cannot be accepted by a green test run. | CH4-T19 | UNSET (reviewer-owned) |
| `PD-CH4-016` | `4.6` | E | Independence claims MUST name distinct evidence producers/identities and cannot count a self-review or shared unqualified adapter as independent evidence. | CH4-T23 | UNSET (reviewer-owned) |
| `PD-CH5-003` | `5.6` | M | Cache reuse MUST require the full canonical input digest tuple, including pinned guidance and evaluation instant. | CH5-T3 | UNSET (reviewer-owned) |
| `PD-CH5-004` | `5.6` | E | Performance statements MUST report measured units/corpus; unmeasured target values remain open. | CH5-T4 | UNSET (reviewer-owned) |
| `PD-CH5-005` | `5.6` | M/E | Product outcome metrics MUST derive from canonical events/projections and mark zero denominators NOT_APPLICABLE. | CH5-T5 | UNSET (reviewer-owned) |
| `PD-CH5-006` | `5.6` | M | Every generated check ID MUST originate from phase sub-check tables under the F5 registry rule. | CH5-T6 | UNSET (reviewer-owned) |
| `PD-CH5-007` | `5.1` | M | The complete explicit gate input tuple (`phase`, `canonical_state_binding`, `pinned_guidance`, `policy_version`, `evaluator_version`, `evaluation_instant`) MUST be part of every gate cache key and replay record; a result missing any element is invalid. Determinism and non-mutation are owned by `PD-F5-001`. | CH5-T7 | UNSET (reviewer-owned) |
| `PD-CH5-008` | `5.2` | M | Invalidation is owned by `PD-CH2-055`; this MUST adds only that additive evidence alone cannot bypass existing blockers. | CH5-T9 | UNSET (reviewer-owned) |
| `PD-CH5-009` | `5.3` | M | Cache reuse MUST require exact equality of every declared key digest; uncertain dependency-index completeness defaults to MISSING. | CH5-T11 | UNSET (reviewer-owned) |
| `PD-CH5-010` | `5.4` | M | A test timeout, flaky disagreement or pending adapter result MUST NOT count as a green verification result. | CH5-T13 | UNSET (reviewer-owned) |
| `PD-CH5-011` | `5.5` | M | Performance claims MUST include measured corpus, sample count meeting the policy-bound minimum (default 100 for a p99 claim; unmeasured, tunable), unit and percentile; unmeasured objectives remain OPEN. | CH5-T15 | UNSET (reviewer-owned) |
| `PD-CH5-012` | `5.6` | M | Outcome metrics MUST derive from canonical records and disclose denominators, observation window and unknown telemetry as UNAVAILABLE. | CH5-T17 | UNSET (reviewer-owned) |
| `PD-CH6-003` | `6.8` | E | Activation MUST require scope-specific qualification and absence of effective revocation. | CH6-T3 | UNSET (reviewer-owned) |
| `PD-CH6-006` | `6.8` | E | v1 Python Feature/Bug Fix playbook content MUST provide phase checklists and refer to qualified adapter families. | CH6-T6 | UNSET (reviewer-owned) |
| `PD-CH6-007` | `6.1` | M | Every knowledge package MUST have a closed schema, content digest, provenance, license reference and declared capability set and a signature binding. | CH6-T7 | UNSET (reviewer-owned) |
| `PD-CH6-008` | `6.2` | M | Knowledge resolution MUST apply deterministic precedence and conflicts MUST NOT permit lower-tier content to remove mandatory checks. | CH6-T9 | UNSET (reviewer-owned) |
| `PD-CH6-009` | `6.3` | M | Pack lifecycle labels MUST be projections of qualification/revocation evidence, never an independent state machine. | CH6-T11 | UNSET (reviewer-owned) |
| `PD-CH6-010` | `6.4` | M | Unknown checks, weakened floors, invalid signatures or unsupported compatibility MUST quarantine the package or return MISSING. | CH6-T13 | UNSET (reviewer-owned) |
| `PD-CH6-011` | `6.5` | M | Unclear license/provenance MUST remain UNVERIFIED and block promotion; a public URL alone is not permission. | CH6-T15 | UNSET (reviewer-owned) |
| `PD-CH6-012` | `6.6` | M | Every in-flight StepPack MUST pin selected content/compiler digests; invalidation is owned by `PD-CH2-055`. | CH6-T17 | UNSET (reviewer-owned) |
| `PD-CH6-013` | `6.7` | M | A v1 stack pack MUST reference qualified adapter capability families or explicitly block applicable checks. | CH6-T19 | UNSET (reviewer-owned) |
| `PD-CH6-014` | `6.8` | M | An OSS qualification record MUST contain all 16 fields and each field must remain UNVERIFIED until independently supported by evidence; incomplete records cannot promote a dependency. | CH6-T21 | UNSET (reviewer-owned) |
| `PD-CH7-008` | `7.1` | M | Guidance resources MUST be versioned, bounded and subordinate to frozen policy and kernel authorization. | CH7-T8 | UNSET (reviewer-owned) |
| `PD-CH7-009` | `7.2` | M | Protocol retries MUST be idempotent under the same request identity (principal, method, key and request digest) and version conflicts MUST return a typed error. | CH7-T10 | UNSET (reviewer-owned) |
| `PD-CH7-011` | `7.4` | M | IDE mode MUST declare E0/E1/E2 capabilities per qualified host/version; prevention honesty for host-native actions is owned by `PD-CH8-008`. | CH7-T14 | UNSET (reviewer-owned) |
| `PD-CH7-012` | `7.5` | M | Session identity MUST bind task, target snapshot, canonical revision and pinned skill/pack digests; transport session metadata MUST NOT act as canonical lifecycle or approval authority. | CH7-T16 | UNSET (reviewer-owned) |
| `PD-CH7-013` | `7.6` | M | Consequential developer actions MUST pass existing authorization/scope gates and emit admissible observations before claims change. | CH7-T18 | UNSET (reviewer-owned) |
| `PD-CH7-014` | `7.7` | M | Notifications MUST be derived from gate projections and must not imply approval/closure on a model-generated message. | CH7-T20 | UNSET (reviewer-owned) |
| `PD-CH7-015` | `7.8` | M | External skill/playbook content MUST be normalized into S-Class-owned checks and cannot create an alternate lifecycle or agent loop. | CH7-T22 | UNSET (reviewer-owned) |
| `PD-CH7-016` | `7.1` | M | Every v1 wire request MUST carry a supported protocol_version and canonical task/session references; responses MUST include request_id, result, next_action, resource_refs and a structured error envelope; invalid requests cause no side effects. | CH7-T24; CH7-T25 | UNSET (reviewer-owned) |
| `PD-CH8-008` | `8.1` | M | Prevention MUST be claimed only inside a launched and qualified enforcement boundary; native IDE activity is detection/containment, not prevention. | CH8-T8 | UNSET (reviewer-owned) |
| `PD-CH8-009` | `8.2` | M | Workspace promotion MUST require the current target and kernel release authority after verification and preserve rollback evidence; comparison of the observed write set with authorized scope is owned by `PD-CH4-014`. | CH8-T10 | UNSET (reviewer-owned) |
| `PD-CH8-010` | `8.3` | M | Out-of-band/concurrent edits MUST trigger re-snapshot and digest comparison before continuing; invalidation is owned by `PD-CH2-055`. | CH8-T12 | UNSET (reviewer-owned) |
| `PD-CH8-011` | `8.4` | M | Parallel work MUST follow dependencies and canonical delta order, serialize overlapping write sets and merge only when target identity and each task verification pass. | CH8-T14 | UNSET (reviewer-owned) |
| `PD-CH8-012` | `8.5` | M | Repository intelligence MUST disclose index coverage/freshness and unresolved symbols remain MISSING. | CH8-T16 | UNSET (reviewer-owned) |
| `PD-CH8-013` | `8.6` | M | Budget exhaustion MUST stop or route to an authorized repair path; retry decisions use the frozen RetryBudget with no second ledger; hard budget gates reject model-reported-only cost and admit only authoritative or host-attested cost metrics; resource and runtime limits use explicit units/defaults. | CH8-T18 | UNSET (reviewer-owned) |
| `PD-CH9-003` | `9.3` | M/E | Security/test-integrity critical regressions MUST block pack or release promotion; a changed TestInputSet digest MUST block unless the F1/F2 human-bound weakening path authorizes it. | CH9-T3; CH9-T8 | UNSET (reviewer-owned) |
| `PD-CH9-004` | `9.3` | E | Metric reports MUST include denominator, observation window, stratum, exclusions and uncertainty. | CH9-T4 | UNSET (reviewer-owned) |
| `PD-CH9-005` | `9.3` | M | Retention and data access MUST follow policy values with explicit units and version. | CH9-T5 | UNSET (reviewer-owned) |
| `PD-CH9-006` | `9.3` | M/E/J | Pack promotion MUST not proceed if false-completion worsens or the comparison is underpowered. | CH9-T6 | UNSET (reviewer-owned) |
| `PD-CH9-007` | `9.3` | E | Secret-egress/control claims MUST use qualified evidence and must not imply native-host prevention. | CH9-T12 | UNSET (reviewer-owned) |
| `PD-CH9-008` | `9.1` | M | Every listed threat MUST have an attack, boundary, prevention/detection, containment and mapped fixture; absence of findings is not a pass. | CH9-T14 | UNSET (reviewer-owned) |
| `PD-CH9-009` | `9.2` | M | Evaluation runs MUST bind benchmark/task revision, target, policy, model/worker/runtime and ground-truth audit label. | CH9-T16 | UNSET (reviewer-owned) |
| `PD-CH9-010` | `9.3` | M | Promotion MUST block on critical regression or unqualified data handling; the sample minimum is owned by `PD-CH9-006` and retention by `PD-CH9-005`. | CH9-T18 | UNSET (reviewer-owned) |
| `PD-F1-001` | `F1` | M | Descriptive prose alone cannot satisfy a mechanical representation obligation. | F1-T11 | UNSET (reviewer-owned) |
| `PD-F1-002` | `F1` | E | Agent-authored executable claims require an independent verifier; F1 establishes the non-self-verification floor. | F1-T7 | UNSET (reviewer-owned) |
| `PD-F1-003` | `F1` | M | Applicable artifact kind MUST use the required executable representation or explicitly enter the defined J fallback. | F1-T1 | UNSET (reviewer-owned) |
| `PD-F1-004` | `F1` | M/E | Every executable spec MUST satisfy the generic positive/negative adequacy rule through its qualified adapter. | F1-T3 | UNSET (reviewer-owned) |
| `PD-F1-005` | `F1` | M/E/J | Changes to confirmed executable constraints MUST be treated as potentially weakening when no structural-diff procedure exists, and weakening MUST follow the authoritative change/approval path. | F1-T5 | UNSET (reviewer-owned) |
| `PD-F10-001` | `F10` | M | Executable-spec tooling MUST be invoked only through a declared F10 adapter contract and category. | F10-T1 | UNSET (reviewer-owned) |
| `PD-F10-002` | `F10` | M/E | A usable adapter MUST bind immutable identity/version/digest, schemas, qualification and the frozen evidence-binding fields. | F10-T2 | UNSET (reviewer-owned) |
| `PD-F10-003` | `F10` | M | Only authorized non-agent authority may register/change adapters; canonical adapter identity and qualification MUST be pinned through the frozen attestation/dependency/approval mechanisms; changed identity M... | F10-T3; F10-T4 | UNSET (reviewer-owned) |
| `PD-F10-004` | `F10` | E | Adapter execution MUST pass through ExecutionGate with the applicable lease, budget and fence, and MUST honor declared isolation and failure semantics. | F10-T5 | UNSET (reviewer-owned) |
| `PD-F10-005` | `F10` | M/E | Qualification MUST pass all 14 frozen adapter tests, A1 reference-fixture conformance, A2 differential-result detection and A3 stale-evidence invalidation. | F10-T6 | UNSET (reviewer-owned) |
| `PD-F10-006` | `F10` | E/J | CRITICAL-lane independent verification MUST use a qualified independent verifier; absent verifier availability yields BLOCKED_ON_HUMAN, while a contradiction yields MISSING. | F10-T7 | UNSET (reviewer-owned) |
| `PD-F10-007` | `F10` | E | Differential detection MUST compare canonicalized semantics and evidence bindings and surface any disagreement. | F10-T8 | UNSET (reviewer-owned) |
| `PD-F2-001` | `F2` | M | F2 predicates MUST conform to the closed grammar, finite types, precedence, associativity and canonical surface mapping. | F2-T1; F2-T2 | UNSET (reviewer-owned) |
| `PD-F2-002` | `F2` | M | Every mechanically decided scalar or collection variable MUST have an explicit finite domain; interval/set reduction MUST preserve the bounded model set, apply only to top-level conjunctive atoms, and solve ... | F2-T3; F2-T11 | UNSET (reviewer-owned) |
| `PD-F2-003` | `F2` | M/E | The reference evaluator MUST return SAT only for a satisfying bounded assignment, UNSAT only after complete bounded evaluation, and INCONCLUSIVE when the evaluation budget expires first. | F2-T4 | UNSET (reviewer-owned) |
| `PD-F2-004` | `F2` | M/E | Tautology, contradiction and old/new classification MUST use the same declared bounded model domain, with EQUIVALENT, TIGHTENING and WEAKENING defined as stated. | F2-T5; F2-T6 | UNSET (reviewer-owned) |
| `PD-F2-005` | `F2` | E/J | Temporal, unbounded or otherwise out-of-fragment predicates MUST route to a qualified property/stateful test or J. | F2-T7 | UNSET (reviewer-owned) |
| `PD-F2-006` | `F2` | M/E | Every qualified F2 adapter MUST match the reference evaluator on small conformance fixtures, MUST use the applicable F4 evaluation budget, and MUST return INCONCLUSIVE on budget exhaustion. | F2-T8 | UNSET (reviewer-owned) |
| `PD-F2-007` | `F2` | M | F2 canonical bindings MUST resolve to frozen Requirement, Constraint, AcceptanceContract and VerificationStep objects; digest-bound confirmation is governed by F3. | F2-T9; F2-T10; F3-T4. | UNSET (reviewer-owned) |
| `PD-F3-001` | `F3` | M | Agent-authored content MUST remain a claim/provenance input and MUST NOT self-authenticate. | F3-T1 | UNSET (reviewer-owned) |
| `PD-F3-002` | `F3` | M | Gate authority MUST come from evaluator-produced check records bound to the canonical object and target. | F3-T2 | UNSET (reviewer-owned) |
| `PD-F3-003` | `F3` | M | Conflicting structured representations MUST be detected without using explanatory prose as a mechanical comparison operand. | F3-T3 | UNSET (reviewer-owned) |
| `PD-F3-004` | `F3` | E | Requirement confirmation MUST be a REQUIREMENT_CONFIRMED USER/POLICY event whose Requirement.source_provenance equals the digest of the canonical structured form; design confirmations MUST be Decision outcom... | F3-T4 | UNSET (reviewer-owned) |
| `PD-F3-005` | `F3` | E | The evaluator MUST recompute content_digest; a claimed digest that differs from the recomputed digest is invalid. | F3-T5 | UNSET (reviewer-owned) |
| `PD-F3-006` | `F3` | M | Human confirmation is admissible only from an S-Class-controlled or host-native rendering surface; agent-relayed confirmation text is inadmissible; the signing principal key MUST be unreachable from the agen... | F3-T6 | UNSET (reviewer-owned) |
| `PD-F4-001` | `F4` | M | Lane selection MUST be a deterministic function of canonical depth dimensions, derived change flags, critical policy and Micro eligibility conditions. | F4-T1; F4-T2 | UNSET (reviewer-owned) |
| `PD-F4-002` | `F4` | M | CRITICAL MUST apply at D4/D5 or on a critical flag; MICRO MUST require every dimension <= D1 plus every Micro condition; a lower requested lane MUST fail. | F4-T3 | UNSET (reviewer-owned) |
| `PD-F4-003` | `F4` | M | Lane selection MUST NEVER reduce the required depth floor or an applicable F1 representation obligation. | F4-T4; F4-T3 | UNSET (reviewer-owned) |
| `PD-F4-004` | `F4` | M/E | Every depth level MUST use its declared assignment budget, adapter resource class and interruption default; budget exhaustion MUST yield INCONCLUSIVE. | F4-T7 | UNSET (reviewer-owned) |
| `PD-F4-005` | `F4` | M | A lane escalation MUST be stored as a canonical profile revision or authorized Decision so replay can reproduce the escalation. | F4-T6 | UNSET (reviewer-owned) |
| `PD-F4-006` | `F4` | E | F4 MUST account for the frozen adaptive-depth and cost-model inputs without creating a second depth state, and its independence floor MUST align with PD-F1-002. | F4-T5 | UNSET (reviewer-owned) |
| `PD-F5-001` | `F5` | M | The gate evaluator MUST be a pure deterministic function of phase, canonical state binding, pinned guidance, policy version, evaluator version and evaluation_instant, and MUST NOT write canonical authority. | F5-T1 | UNSET (reviewer-owned) |
| `PD-F5-002` | `F5` | M | When both missing and blocked checks apply, MISSING MUST have precedence and IDs MUST be canonically sorted; results MUST use the stated gate-output schema. | F5-T2 | UNSET (reviewer-owned) |
| `PD-F5-003` | `F5` | E | Evaluator crash, timeout, malformed internal result or budget exhaustion MUST fail closed, and evaluator version MUST be pinned. | F5-T3 | UNSET (reviewer-owned) |
| `PD-F5-004` | `F5` | E | Explain-why and caching MUST be derived from the same canonical input digest and replay MUST reproduce the same result. | F5-T4 | UNSET (reviewer-owned) |
| `PD-F5-005` | `F5` | M | Product phase gates MUST only add blocking conjunctions and MUST NOT override ExecutionGate or ReleaseEvaluation; skill-added checks may only add blocking checks. | F5-T5a; F5-T5c | UNSET (reviewer-owned) |
| `PD-F6-001` | `F6` | M | Trace links MUST be typed and derived only from resolved kernel objects reached through source_refs. | F6-T1 | UNSET (reviewer-owned) |
| `PD-F6-002` | `F6` | M | Coverage MUST be computed from valid links and MUST detect orphan nodes rather than accepting asserted coverage. | F6-T2 | UNSET (reviewer-owned) |
| `PD-F6-003` | `F6` | M | Link identity MUST be stable across revisions when source/destination stable IDs and link type remain unchanged. | F6-T3 | UNSET (reviewer-owned) |
| `PD-F6-004` | `F6` | E | Agent assertions about coverage MUST NOT substitute for evaluator-computed coverage. | F6-T4 | UNSET (reviewer-owned) |
| `PD-F6-005` | `F6` | E | Both endpoints of a trace link MUST be current under the frozen freshness predicate before the link contributes to coverage. | F6-T5 | UNSET (reviewer-owned) |
| `PD-F6-006` | `F6` | M | Planned coverage MUST be computed through VerificationStep without requiring realized evidence; realized coverage MUST require admissible evidence. | F6-T6 | UNSET (reviewer-owned) |
| `PD-F7-001` | `F7` | M | Every agent claim MUST be a structured record with claim_id, type, subject and optional evidence_refs; prose alone MUST NOT create a claim. | F7-T1 | UNSET (reviewer-owned) |
| `PD-F7-002` | `F7` | M | Behavioral and completion claims without resolvable evidence references MUST remain unverified and MUST NOT satisfy a gate; reference claims use evaluator-owned repository-intelligence resolution as their ev... | F7-T2 | UNSET (reviewer-owned) |
| `PD-F7-003` | `F7` | E | Proposed symbols, imports, packages and APIs MUST resolve against the TargetSnapshot and the canonical dependency identity before verification. | F7-T4 | UNSET (reviewer-owned) |
| `PD-F7-004` | `F7` | E | A pre-existing symbol/import/package/API reference (created_by_delta=false) absent from the pre-delta repository view MUST yield a missing claim result. | F7-T3 | UNSET (reviewer-owned) |
| `PD-F7-005` | `F7` | M | Claim types MUST use the closed v1 registry and each type MUST use its declared evidence rule. | F7-T5 | UNSET (reviewer-owned) |
| `PD-F7-006` | `F7` | E | When created_by_delta=true, the claimed symbol MUST resolve in the post-delta repository overlay; absence post-delta is missing regardless of pre-delta presence. | F7-T6 | UNSET (reviewer-owned) |
| `PD-F8-001` | `F8` | M | Step-pack identity MUST be a pure function of phase, task_ref, canonical state binding, pinned skills and canonical-UTF-8-byte context budget under a pinned compiler version. | F8-T1 | UNSET (reviewer-owned) |
| `PD-F8-002` | `F8` | M | Ordering and truncation MUST follow frozen context precedence deterministically. | F8-T2 | UNSET (reviewer-owned) |
| `PD-F8-003` | `F8` | M | Resume MUST use canonical state and re-injected anchors, never transcript state. | F8-T3 | UNSET (reviewer-owned) |
| `PD-F8-004` | `F8` | E | Step-pack golden files MUST reproduce exact canonical bytes and digest. | F8-T4 | UNSET (reviewer-owned) |
| `PD-F9-001` | `F9` | M | Metrics MUST be deterministic projections of canonical events/replayed state. | F9-T1 | UNSET (reviewer-owned) |
| `PD-F9-002` | `F9` | M | Every metric MUST declare numerator, denominator and canonical event basis. | F9-T2 | UNSET (reviewer-owned) |
| `PD-F9-003` | `F9` | E | Paired metrics MUST be evaluated together so optimization of one cannot hide the paired failure mode. | F9-T3 | UNSET (reviewer-owned) |
| `PD-F9-004` | `F9` | M | Agent/operator self-reported metrics MUST NOT contribute to canonical metric results. | F9-T4 | UNSET (reviewer-owned) |

**Allocation audit:** definitions=249; unique IDs=249; duplicate definitions=0; missing row tests=10.
