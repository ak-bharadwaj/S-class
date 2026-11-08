# Block 4 MUST Table (32 MUSTs)

Total Block 4 MUSTs: `32`
Authoritative Master Document: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md` (SHA-256 `340db97857a7716b1aac2c1b44bc60b32642e3d8074d02720c2333cea278b4ff`)

| # | MUST ID | Level | Master Line | Phase/Chapter | Requirement Text (first 200 chars) | Fixture IDs (role:line) |
|---|---|---|---|---|---|---|
| 1 | `PD-F10-001` | M | L1020 | `F10` | Executable-spec tooling MUST be invoked only through a declared F10 adapter contract and category. | F10-T1 (gaming:L9851) |
| 2 | `PD-F10-002` | M/E | L1021 | `F10` | A usable adapter MUST bind immutable identity/version/digest, schemas, qualification and the frozen evidence-binding fields. | F10-T2 (gaming:L9858) |
| 3 | `PD-F10-003` | M | L1022 | `F10` | Only authorized non-agent authority may register/change adapters; canonical adapter identity and qualification MUST be pinned through the frozen attestation/dependency/approval mechanisms; changed ide | F10-T3 (gaming:L9869), F10-T4 (gaming:L9878) |
| 4 | `PD-F10-004` | E | L1023 | `F10` | Adapter execution MUST pass through ExecutionGate with the applicable lease, budget and fence, and MUST honor declared isolation and failure semantics. | F10-T5 (gaming:L9889) |
| 5 | `PD-F10-005` | M/E | L1024 | `F10` | Qualification MUST pass all 14 frozen adapter tests, A1 reference-fixture conformance, A2 differential-result detection and A3 stale-evidence invalidation. | F10-T6 (gaming:L9899) |
| 6 | `PD-F10-006` | E/J | L1025 | `F10` | CRITICAL-lane independent verification MUST use a qualified independent verifier; absent verifier availability yields `BLOCKED_ON_HUMAN`, while a contradiction yields `MISSING`. | F10-T7 (gaming:L9929) |
| 7 | `PD-F10-007` | E | L1026 | `F10` | Differential detection MUST compare canonicalized semantics and evidence bindings and surface any disagreement. | F10-T8 (gaming:L9943) |
| 8 | `PD-CH3-015` | M | L2916 | `CH_CH3` | Every product artifact MUST bind objective revision, source digest, artifact type and owning authority; product documents cannot shadow canonical objects. | CH3-T15 (gaming:L11182), CH3-T16 (happy:L11211) |
| 9 | `PD-CH3-016` | M | L2966 | `CH_CH3` | Every normative requirement MUST resolve to an exact spec path, symbol/heading and line range; unresolved means MISSING, and a changed anchor digest invalidates all dependent artifacts. | CH3-T17 (gaming:L11223), CH3-T18 (happy:L11251) |
| 10 | `PD-CH3-017` | M | L3024 | `CH_CH3` | Mechanical spec-quality predicates MUST use explicit measurable thresholds bound to the policy digest (an unbound or edited threshold is MISSING; weakening goes through `PD-F1-005`) and unsupported/un | CH3-T19 (gaming:L11263), CH3-T20 (happy:L11293) |
| 11 | `PD-CH3-018` | M | L3074 | `CH_CH3` | A blocking clarification MUST have an authorized outcome or remain MISSING/BLOCKED_ON_HUMAN; silence and model inference are not confirmation. | CH3-T21 (gaming:L11305), CH3-T22 (happy:L11333) |
| 12 | `PD-CH3-020` | M | L3117 | `CH_CH3` | Invalidation is owned by `PD-CH2-055`; this MUST adds only that a spec change identifies the earliest replay point for affected work/evidence. | CH3-T25 (gaming:L11345), CH3-T26 (happy:L11373) |
| 13 | `PD-CH3-001` | M | L3179 | `CH_CH3` | Every phase artifact MUST bind the objective revision and canonical SpecAnchor digests; invalidation of dependents is owned by `PD-CH2-055`. | CH3-T1 (gaming:L10367) |
| 14 | `PD-CH3-002` | M/E | L3180 | `CH_CH3` | Normative requirements MUST have testable acceptance links, explicit non-goals, and no unresolved normative placeholders. | CH3-T2 (gaming:L10375) |
| 15 | `PD-CH3-003` | E/J | L3181 | `CH_CH3` | Clarification answers changing scope MUST enter canonical Decision/Requirement mechanisms; absent human confirmation blocks. | CH3-T3 (gaming:L10383) |
| 16 | `PD-CH3-006` | E | L3182 | `CH_CH3` | External process tools MUST remain untrusted candidates until adapter/content qualification is recorded. | CH3-T6 (gaming:L10391) |
| 17 | `PD-CH3-007` | M | L3183 | `CH_CH3` | Work type MUST be projected from an existing canonical Decision scope/outcome without a product-owned state machine; invalidation is owned by `PD-CH2-055`. | CH3-T7 (gaming:L10399) |
| 18 | `PD-CH3-009` | E | L3184 | `CH_CH3` | Each default user-facing flow MUST preserve its required gates/evidence and compute lane from canonical profile/policy. | CH3-T9 (gaming:L10406) |
| 19 | `PD-CH3-010` | E | L3185 | `CH_CH3` | Upgrade, migration, performance, CI, and PR-review flows MUST bind relevant baselines and rollback/verification inputs before closure. | CH3-T10 (gaming:L10415) |
| 20 | `PD-CH3-011` | E | L3186 | `CH_CH3` | Project-class adaptation MUST preserve common gates and mark each unqualified adapter/pack as an open qualification, not as supported. | CH3-T11 (gaming:L10423) |
| 21 | `PD-CH3-012` | M/E | L3187 | `CH_CH3` | UX adaptation MUST preserve mandatory gates/anchors; interruption budgets MUST NOT suppress an authority-required human decision. | CH3-T12 (gaming:L10432) |
| 22 | `PD-CH3-014` | E | L3188 | `CH_CH3` | Canonical lifecycle examples MUST exercise real gate outputs and at least one adversarial claim and test-integrity failure. | CH3-T14 (gaming:L10441) |
| 23 | `PD-CH4-012` | M | L3257 | `CH_CH4` | Every path/symbol/line reference MUST resolve exactly against the pinned target snapshot and indexed source; any unresolved or ambiguous reference is MISSING, never fuzzy-match PASS. | CH4-T15 (gaming:L11385), CH4-T16 (happy:L11413) |
| 24 | `PD-CH4-009` | M | L3288 | `CH_CH4` | P5 MUST bind a qualified adapter-declared complete TestInputSet before red, including tests, conftest, fixtures, test data, runner configuration, markers, plugins, collection/discovery inputs and envi | CH4-T9 (happy:L10504), CH4-T27 (gaming:L11545) |
| 25 | `PD-CH4-010` | M/E | L3289 | `CH_CH4` | P6 MUST exclude every path in the bound TestInputSet from implementation writes; P7 evidence MUST use the same manifest, per-entry content digests, environment digest and designed test ID, and the sam | CH4-T12 (gaming:L10540) |
| 26 | `PD-CH4-014` | M | L1072 | `CH_CH4` | CH4-T20 | CH4-T19 (gaming:L11425), CH4-T20 (happy:L11457) |
| 27 | `PD-CH4-016` | E | L1074 | `CH_CH4` | CH4-T24 | CH4-T23 (gaming:L11469), CH4-T24 (happy:L11497) |
| 28 | `PD-CH4-002` | M/E | L3464 | `CH_CH4` | Claims of execution MUST bind qualified adapter structured results and raw result identity. | CH4-T2 (gaming:L10449) |
| 29 | `PD-CH4-005` | M/E | L1073 | `CH_CH4` | CH4-T28 | CH4-T5 (gaming:L10456), CH4-T28 (happy:L11509) |
| 30 | `PD-CH4-006` | E | L1075 | `CH_CH4` | CH4-T29 | CH4-T6 (gaming:L10470), CH4-T29 (happy:L11521) |
| 31 | `PD-CH4-007` | M/E | L3467 | `CH_CH4` | Context resume MUST rebuild anchors from canonical state and reject transcript-only authority (owner §4.5). | CH4-T7 (gaming:L10483), CH4-T30 (happy:L11533) |
| 32 | `PD-CH4-008` | M | L3468 | `CH_CH4` | All listed threat classes MUST map to a detection, gate, containment, and fixture. | CH4-T8 (gaming:L10497) |
