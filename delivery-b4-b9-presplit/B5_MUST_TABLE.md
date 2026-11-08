# Block 5 MUST Table (6 MUSTs)

Total Block 5 MUSTs: `6`
Authoritative Master Document: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md` (SHA-256 `340db97857a7716b1aac2c1b44bc60b32642e3d8074d02720c2333cea278b4ff`)

| # | MUST ID | Level | Master Line | Phase/Chapter | Requirement Text (first 200 chars) | Fixture IDs (role:line) |
|---|---|---|---|---|---|---|
| 1 | `PD-CH8-008` | M | L4102 | `CH_CH8` | Prevention MUST be claimed only inside a launched and qualified enforcement boundary; native IDE activity is detection/containment, not prevention. | CH8-T8 (gaming:L12436), CH8-T9 (happy:L12484) |
| 2 | `PD-CH8-009` | M | L4126 | `CH_CH8` | Workspace promotion MUST require the current target and kernel release authority after verification and preserve rollback evidence; comparison of the observed write set with authorized scope is owned  | CH8-T10 (gaming:L12496), CH8-T11 (happy:L12524) |
| 3 | `PD-CH8-010` | M | L4150 | `CH_CH8` | Out-of-band/concurrent edits MUST trigger re-snapshot and digest comparison before continuing; invalidation is owned by `PD-CH2-055`. | CH8-T12 (gaming:L12536), CH8-T13 (happy:L12565) |
| 4 | `PD-CH8-011` | M | L4174 | `CH_CH8` | Parallel work MUST follow dependencies and canonical delta order, serialize overlapping write sets and merge only when target identity and each task verification pass. | CH8-T14 (gaming:L12577), CH8-T15 (happy:L12605) |
| 5 | `PD-CH8-012` | M | L4198 | `CH_CH8` | Repository intelligence MUST disclose index coverage/freshness and unresolved symbols remain MISSING. | CH8-T16 (gaming:L12617), CH8-T17 (happy:L12645) |
| 6 | `PD-CH8-013` | M | L4222 | `CH_CH8` | Budget exhaustion MUST stop or route to an authorized repair path; retry decisions use the frozen RetryBudget with no second ledger; hard budget gates reject model-reported-only cost and admit only au | CH8-T18 (gaming:L12657), CH8-T19 (happy:L12699) |
