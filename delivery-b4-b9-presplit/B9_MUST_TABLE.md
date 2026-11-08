# Block 9 MUST Table (15 MUSTs)

Total Block 9 MUSTs: `15`
Authoritative Master Document: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md` (SHA-256 `340db97857a7716b1aac2c1b44bc60b32642e3d8074d02720c2333cea278b4ff`)

| # | MUST ID | Level | Master Line | Phase/Chapter | Requirement Text (first 200 chars) | Fixture IDs (role:line) |
|---|---|---|---|---|---|---|
| 1 | `PD-CH9-008` | M | L4321 | `CH_CH9` | Every listed threat MUST have an attack, boundary, prevention/detection, containment and mapped fixture; absence of findings is not a pass. | CH9-T14 (gaming:L12711), CH9-T15 (happy:L12740) |
| 2 | `PD-CH9-009` | M | L4347 | `CH_CH9` | Evaluation runs MUST bind benchmark/task revision, target, policy, model/worker/runtime and ground-truth audit label. | CH9-T16 (gaming:L12752), CH9-T17 (happy:L12780) |
| 3 | `PD-CH9-010` | M | L4371 | `CH_CH9` | Promotion MUST block on critical regression or unqualified data handling; the sample minimum is owned by `PD-CH9-006` and retention by `PD-CH9-005`. | CH9-T18 (gaming:L12792), CH9-T19 (happy:L12821) |
| 4 | `PD-CH9-003` | M/E | L4398 | `CH_CH9` | Security critical regressions, a mismatched environment/runner identity receipt and a sandbox/trust-root failure MUST block pack or release promotion; a changed TestInputSet digest is owned by `PD-CH4 | CH9-T3 (gaming:L10595), CH9-T8 (gaming:L10664), CH9-T9 (gaming:L10707), CH9-T20 (happy:L12833) |
| 5 | `PD-CH9-004` | E | L4399 | `CH_CH9` | Metric reports MUST include denominator, observation window, stratum, exclusions and uncertainty. | CH9-T4 (gaming:L10610), CH9-T21 (happy:L12845) |
| 6 | `PD-CH9-005` | M | L4400 | `CH_CH9` | Retention and data access MUST follow policy values with explicit units and version. | CH9-T5 (gaming:L10627), CH9-T22 (happy:L12857) |
| 7 | `PD-CH9-006` | M/E/J | L4401 | `CH_CH9` | Pack promotion MUST not proceed if false-completion worsens or any registered stratum has fewer completed paired tasks than the policy-bound minimum (default 100 per stratum). | CH9-T6 (gaming:L10646), CH9-T23 (happy:L12869) |
| 8 | `PD-CH9-007` | E | L4402 | `CH_CH9` | Secret-egress/control claims MUST use qualified evidence (prevention honesty is owned by `PD-CH8-008`). | CH9-T12 (gaming:L10691), CH9-T24 (happy:L12881) |
| 9 | `PD-CH10-008` | M | L4426 | `CH_CH10` | Compatibility MUST be explicit across kernel, protocol, schema, adapter and pack versions; unsupported pairs block. | CH10-T8 (gaming:L12893), CH10-T9 (happy:L12921) |
| 10 | `PD-CH10-009` | M | L4450 | `CH_CH10` | Audit export MUST bind canonical sequence range, digests, gate inputs/outputs and explicit truncation or missing-data declarations. | CH10-T10 (gaming:L12933), CH10-T11 (happy:L12962) |
| 11 | `PD-CH10-010` | M | L4485 | `CH_CH10` | The roadmap MUST use only H0–H7, assign each capability a dependency and exit test, and must not represent planning as implemented capability. | CH10-T12 (gaming:L12974), CH10-T13 (happy:L13007) |
| 12 | `PD-CH10-011` | M | L4519 | `CH_CH10` | Every surfaced implementation fact MUST be classified as keep/replace/retire/qualify and evidence-backed or UNVERIFIED. | CH10-T14 (gaming:L13019), CH10-T15 (happy:L13052) |
| 13 | `PD-CH10-012` | M | L4543 | `CH_CH10` | A frozen change MUST require a formal erratum path and concrete insufficiency/replay analysis; frozen source is never edited ad hoc. | CH10-T16 (gaming:L13064), CH10-T17 (happy:L13097) |
| 14 | `PD-CH10-013` | M | L4567 | `CH_CH10` | Every open issue MUST name impact, owner, evidence/decision needed, blocking phase and status; OI-008 remains OPEN until two raw fresh-chat reviews are owner-supplied. | CH10-T18 (gaming:L13109), CH10-T19 (happy:L13147) |
| 15 | `PD-CH10-007` | M | L4594 | `CH_CH10` | Version/qualification and issue/claim registries MUST be internally cross-linked to the master. | CH10-T7 (gaming:L10726) |
