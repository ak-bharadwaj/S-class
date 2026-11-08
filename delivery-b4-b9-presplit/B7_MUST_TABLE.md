# Block 7 MUST Table (8 MUSTs)

Total Block 7 MUSTs: `8`
Authoritative Master Document: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md` (SHA-256 `340db97857a7716b1aac2c1b44bc60b32642e3d8074d02720c2333cea278b4ff`)

| # | MUST ID | Level | Master Line | Phase/Chapter | Requirement Text (first 200 chars) | Fixture IDs (role:line) |
|---|---|---|---|---|---|---|
| 1 | `PD-CH7-016` | M | L3892 | `CH_CH7` | Every v1 wire request MUST carry a supported `protocol_version` and canonical task/session references; every response MUST carry `request_id`, `result`, `next_action`, `resource_refs`, and a structure | CH7-T24 (gaming:L12387), CH7-T25 (happy:L12419) |
| 2 | `PD-CH7-008` | M | L3909 | `CH_CH7` | Guidance resources MUST be versioned, bounded and subordinate to frozen policy and kernel authorization. | CH7-T8 (gaming:L12084), CH7-T9 (happy:L12125) |
| 3 | `PD-CH7-009` | M | L3933 | `CH_CH7` | Protocol retries MUST be idempotent under the same request identity (principal, method, key and request digest) and version conflicts MUST return a typed error. | CH7-T10 (gaming:L12137), CH7-T11 (happy:L12165) |
| 4 | `PD-CH7-011` | M | L3969 | `CH_CH7` | IDE mode MUST declare E0/E1/E2 capabilities per qualified host/version; prevention honesty for host-native actions is owned by `PD-CH8-008`. | CH7-T14 (gaming:L12177), CH7-T15 (happy:L12205) |
| 5 | `PD-CH7-012` | M | L3993 | `CH_CH7` | Session identity MUST bind task, target snapshot, canonical revision and pinned skill/pack digests; transport session metadata MUST NOT act as canonical lifecycle or approval authority. | CH7-T16 (gaming:L12217), CH7-T17 (happy:L12246) |
| 6 | `PD-CH7-013` | M | L4017 | `CH_CH7` | Consequential developer actions MUST pass existing authorization/scope gates and emit admissible observations before claims change. | CH7-T18 (gaming:L12258), CH7-T19 (happy:L12286) |
| 7 | `PD-CH7-014` | M | L4041 | `CH_CH7` | Notifications MUST be derived from gate projections and must not imply approval/closure on a model-generated message. | CH7-T20 (gaming:L12298), CH7-T21 (happy:L12327) |
| 8 | `PD-CH7-015` | M | L4077 | `CH_CH7` | Index only; defined in its R5 closure table with its fixtures (External skill/playbook content MUST be normalized into S-Class-owned checks and cannot create an alternate li) | CH7-T22 (gaming:L12339), CH7-T23 (happy:L12374) |
