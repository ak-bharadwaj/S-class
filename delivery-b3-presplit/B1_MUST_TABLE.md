# B1: Block 3 MUST Table (69 MUSTs)

Total Block 3 MUSTs: `69`

| # | MUST ID | Level | Line | Phase | Requirement Text (first 200 chars) | Fixture IDs (role:line) |
|---|---|---|---|---|---|---|
| 1 | `PD-F4-001` | M | L583 | `F4` | Lane selection MUST be a deterministic function of canonical depth dimensions, derived change flags, critical policy and Micro eligibility conditions. | F4-T1 (happy:L9410), F4-T2 (happy:L9430) |
| 2 | `PD-F4-002` | M | L584 | `F4` | `CRITICAL` MUST apply at D4/D5 or on a critical flag; `MICRO` MUST require every dimension <= D1 plus every Micro condition; a lower requested lane MUST fail. | F4-T3 (gaming:L9439) |
| 3 | `PD-F4-003` | M | L585 | `F4` | Lane selection MUST NEVER reduce the required depth floor or an applicable F1 representation obligation. | F4-T4 (happy:L9453), F4-T3 (happy:L9439) |
| 4 | `PD-F4-004` | M/E | L586 | `F4` | Every depth level MUST use its declared assignment budget, adapter resource class and interruption default; budget exhaustion MUST yield `INCONCLUSIVE`. | F4-T7 (gaming:L9497) |
| 5 | `PD-F4-005` | M | L587 | `F4` | A lane escalation MUST be stored as a canonical profile revision or authorized Decision so replay can reproduce the escalation. | F4-T6 (gaming:L9484) |
| 6 | `PD-F4-006` | E | L588 | `F4` | F4 MUST account for the frozen adaptive-depth and cost-model inputs without creating a second depth state, and its independence floor MUST align with `PD-F1-002`. | F4-T5 (gaming:L9475) |
| 7 | `PD-F8-001` | M | L855 | `F8` | Step-pack identity MUST be a pure function of phase, task_ref, canonical state binding, pinned skills and canonical-UTF-8-byte context budget under a pinned compiler version. | F8-T1 (gaming:L9772) |
| 8 | `PD-F8-002` | M | L856 | `F8` | Ordering and truncation MUST follow frozen context precedence deterministically. | F8-T2 (gaming:L9783) |
| 9 | `PD-F8-003` | M | L857 | `F8` | Resume MUST use canonical state and re-injected anchors, never transcript state. | F8-T3 (gaming:L9794) |
| 10 | `PD-F8-004` | E | L858 | `F8` | Step-pack golden files MUST reproduce exact canonical bytes and digest. | F8-T4 (gaming:L9803) |
| 11 | `PD-CH2-001` | M | L1314 | `P0` | Every work type MUST execute as a projection of the same P0–P11 lifecycle. | CH2-T1 (gaming:L9968) |
| 12 | `PD-CH2-003` | M | L1323 | `P0` | A later phase MUST NOT make an invalid earlier phase valid. | CH2-T3 (gaming:L9984) |
| 13 | `PD-CH2-005` | M | L1324 | `P0` | Every skipped phase MUST have an explicit evaluator-checkable applicability result. | CH2-T5 (gaming:L9991) |
| 14 | `PD-CH2-006` | M/E | L1325 | `P0` | A discovered defect MUST route to the earliest affected phase. | CH2-T6 (gaming:L9998) |
| 15 | `PD-CH2-007` | M | L1326 | `P0` | P8 repair MUST consume the frozen RetryBudget and MUST NOT create an alternate retry path. | CH2-T7 (gaming:L10006) |
| 16 | `PD-CH2-008` | M | L1327 | `P0` | P11 MUST be non-terminal; new work MUST re-enter at P0. | CH2-T8 (gaming:L10013) |
| 17 | `PD-CH2-009` | M/E | L1328 | `P0` | A model `DONE` claim MUST NOT close work without admissible evidence and kernel-evaluated closure. | CH2-T9 (gaming:L10020) |
| 18 | `PD-CH2-010` | E | L1329 | `P0` | A green external run MUST be treated only as run evidence bound to its inputs, not as completion by itself. | CH2-T10 (gaming:L10028) |
| 19 | `PD-CH2-011` | M | L1330 | `P0` | Stack/skill changes MUST NOT create a lifecycle fork or remove core phases. | CH2-T11 (gaming:L10035) |
| 20 | `PD-CH2-012` | M/E | L1331 | `P0` | Human judgment MUST NOT waive mandatory mechanical/evidence floors except through existing authorized waiver/break-glass paths. | CH2-T12 (gaming:L10042) |
| 21 | `PD-CH2-055` | M | L1353 | `P0` | The lifecycle gate MUST invalidate every downstream projection whose authoritative dependency digest changes, and the changed binding MUST be visible in the recomputation key. | CH2-T56 (happy:L10800) |
| 22 | `PD-CH2-002` | M | L1407 | `P0` | Every P-phase MUST define all eleven dimensions. | CH2-T2 (gaming:L9976) |
| 23 | `PD-CH2-056` | M | L1668 | `P1` | P1 MUST classify an unresolvable target snapshot, incomplete index coverage, or missing high-impact unknown outcome as MISSING rather than infer completeness. | CH2-T57 (gaming:L10812), CH2-T58 (happy:L10843) |
| 24 | `PD-CH2-057` | M | L1687 | `P1` | P1 MUST resolve required skills and depth against policy/profile precedence and pin their digests into the context/step-pack binding before a downstream phase can pass. | CH2-T59 (gaming:L10855), CH2-T60 (happy:L10885) |
| 25 | `PD-CH2-013` | M | L1820 | `P3` | Every applicable requirement has semantic coverage or explicit applicability. | CH2-T13 (gaming:L10049) |
| 26 | `PD-CH2-014` | M | L1821 | `P3` | Required domain/data invariants are represented. | CH2-T14 (gaming:L10057) |
| 27 | `PD-CH2-015` | M | L1822 | `P3` | Every required architecture element has attributable requirement, Decision or source-digest provenance. | CH2-T15 (gaming:L10064) |
| 28 | `PD-CH2-016` | M | L1823 | `P3` | Materially affected dependency relationships are represented. | CH2-T16 (gaming:L10071) |
| 29 | `PD-CH2-017` | M | L1824 | `P3` | `DomainModel` satisfies the measurable substance predicate. | CH2-T17 (gaming:L10078) |
| 30 | `PD-CH2-018` | M | L1825 | `P3` | `ArchitectureRecord` satisfies the measurable substance predicate. | CH2-T18 (gaming:L10088) |
| 31 | `PD-CH2-020` | M/E | L1826 | `P3` | Invariants use F2's decidable fragment; unsupported/undecidable cases route J and cannot PASS. | F2-T4 (gaming:L9134), F2-T13 (gaming:L9293), CH2-T20 (happy:L10094) |
| 32 | `PD-CH2-021` | M | L1827 | `P3` | Cross-entity constraints include explicit relationships and cardinalities. | CH2-T21 (gaming:L10101) |
| 33 | `PD-CH2-022` | M | L1828 | `P3` | Architecture dependency edges cover `ChangeSurfaceAnalysis` boundary closure. | CH2-T22 (gaming:L10109) |
| 34 | `PD-CH2-023` | M/E | L1829 | `P3` | Each boundary-crossing data flow binds source, destination, contract and transformation. | CH2-T23 (gaming:L10116) |
| 35 | `PD-CH2-024` | M | L1830 | `P3` | Interface signatures agree with typed domain contracts and requirement predicates. | CH2-T24 (gaming:L10122) |
| 36 | `PD-CH2-025` | M/J | L1831 | `P3` | Every unknown/undecidable contradiction returns `MISSING`; human review cannot waive absent analysis. | CH2-T25 (happy:L10129) |
| 37 | `PD-CH2-026` | M | L1832 | `P3` | Existing ADR/design sources are digest-bound and pass structure/reference lint. | CH2-T26 (gaming:L10140) |
| 38 | `PD-CH2-028` | M | L1833 | `P3` | MUST IDs are unique, reserved and never reassigned. | CH2-T28 (gaming:L10154) |
| 39 | `PD-CH2-029` | M | L1921 | `P4` | P4 MUST enforce task-count and task-unit caps from the F4 lane's canonical Policy defaults. | CH2-T29 (gaming:L10161) |
| 40 | `PD-CH2-031` | M | L1922 | `P4` | WorkGraph dependency edges MUST be acyclic. | CH2-T31 (gaming:L10172) |
| 41 | `PD-CH2-032` | M/E/J | L1923 | `P4` | Known write-set overlap MUST serialize mechanically; unknown/undeclared write sets MUST block for human resolution. | CH2-T32b (gaming:L10187) |
| 42 | `PD-CH2-033` | M | L1994 | `P5` | The test-carrying canonical delta MUST precede the implementation delta by canonical delta sequence, not clock time. | CH2-T33 (happy:L10195) |
| 43 | `PD-CH2-034` | E | L1995 | `P5` | A red run MUST come from the qualified adapter and fail the designed test for the designed assertion class/targets; harness errors, skip/xfail, timeout, and unstable reruns do not count. | CH2-T47 (gaming:L10309) |
| 44 | `PD-CH2-035` | M/E | L1996 | `P5` | Executable specifications MUST satisfy F1/F2 representation and finite-domain constraints. | CH2-T35 (gaming:L10212) |
| 45 | `PD-CH2-036` | E | L1997 | `P5` | Required test adapters MUST be qualified under F10. | CH2-T36 (gaming:L10219) |
| 46 | `PD-CH2-046` | M/E | L1998 | `P5` | P5 MUST NOT authorize a red run until the primary test digest is present in the complete TestInputSet bound under `PD-CH4-009`. | CH2-T46 (gaming:L10299) |
| 47 | `PD-CH2-047` | E | L1999 | `P5` | Red classification MUST use adapter structured result and designed test/reason tuple, never agent assertions. | CH2-T47 (gaming:L10309) |
| 48 | `PD-CH2-037` | M | L2072 | `P6` | Implementation writes MUST be ExecutionGate-authorized for exact task/scope/target. | CH2-T37 (gaming:L10226) |
| 49 | `PD-CH2-038` | M | L2073 | `P6` | Scope growth MUST stop and route to P4. | CH2-T38 (gaming:L10233) |
| 50 | `PD-CH2-039` | E | L2074 | `P6` | Implementation claims MUST use F7's `type` and `created_by_delta` rules. | CH2-T39 (gaming:L10241) |
| 51 | `PD-CH2-040` | M | L2075 | `P6` | Product records MUST NOT create canonical delta authority or override kernel denial. | CH2-T40 (gaming:L10251) |
| 52 | `PD-CH2-048` | M | L2076 | `P6` | P6 gate MUST invoke the complete TestInputSet exclusion check owned by `PD-CH4-010`; this MUST does not redefine TestInputSet membership. | CH2-T48 (gaming:L10317) |
| 53 | `PD-CH2-041` | M | L2144 | `P7` | Verification evidence MUST bind frozen evidence identity and current target/step. | CH2-T41 (gaming:L10258) |
| 54 | `PD-CH2-042` | E | L2145 | `P7` | Required adapter results MUST come from qualified F10 adapters. | CH2-T42 (gaming:L10266) |
| 55 | `PD-CH2-043` | M/E | L2146 | `P7` | Independence MUST meet F4 depth-derived floor. | CH2-T43 (gaming:L10274) |
| 56 | `PD-CH2-044` | M | L2147 | `P7` | Freshness MUST use frozen predicate at recorded evaluation instant. | CH2-T44 (gaming:L10282) |
| 57 | `PD-CH2-045` | M/E/J | L2148 | `P7` | Closure MUST be kernel-owned; per-task results MUST use F5 schema and feed P9/P10. | CH2-T45 (gaming:L10290) |
| 58 | `PD-CH2-050` | M/E | L2149 | `P7` | P7 MUST reject nondeterministic test reruns; complete input/manifest/environment identity is exclusively checked by `PD-CH4-010`. | CH2-T50 (gaming:L10326) |
| 59 | `PD-CH2-051` | M/E | L2215 | `P8` | P8 MUST route failure to the earliest affected phase and stop when the existing RetryBudget is exhausted. | CH2-T51 (gaming:L10334) |
| 60 | `PD-CH2-052` | M/E/J | L2281 | `P9` | P9 MUST aggregate all required P7 task results and close each mandatory finding only by evidence or canonical authority. | CH2-T52 (gaming:L10342) |
| 61 | `PD-CH2-053` | M/J | L2347 | `P10` | P10 MUST require frozen kernel ReleaseEvaluation for exact target/policy and MUST NOT override kernel denial. | CH2-T53 (happy:L10350) |
| 62 | `PD-CH2-054` | M/E/J | L2413 | `P11` | P11 MUST ground signals in canonical facts and route new objective work through P0 without autonomous canonical mutation. | CH2-T54 (gaming:L10358) |
| 63 | `PD-CH2-058` | M | L2473 | `P11` | A work type MUST resolve to exactly one declared applicability record for each P0–P11 phase, including an explicit skip reason; the matrix covers every registered work type and phase pair without impl | CH2-T61 (gaming:L10897), CH2-T62 (happy:L10925) |
| 64 | `PD-CH2-060` | M | L2568 | `P11` | Every default user-facing flow MUST preserve P0–P11 order and route upstream defects to the earliest affected phase. | CH2-T65 (gaming:L10937), CH2-T66 (happy:L10965) |
| 65 | `PD-CH2-061` | M | L2630 | `P11` | Every operations/delivery flow MUST bind its entry predicate, required gate outputs and rollback/stop condition. | CH2-T67 (gaming:L10977), CH2-T68 (happy:L11005) |
| 66 | `PD-CH2-062` | M | L2694 | `P11` | Project-class qualification MUST require explicit fit evidence and must not infer qualification from repository language or size alone. | CH2-T69 (gaming:L11017), CH2-T70 (happy:L11045) |
| 67 | `PD-CH2-063` | M | L2761 | `P11` | The question budget MUST be enforced as an integer count with a declared per-batch default and unresolved blockers MUST remain open when exhausted. | CH2-T71 (gaming:L11057), CH2-T72 (happy:L11086) |
| 68 | `PD-CH2-064` | M | L2808 | `REPLAY` | Invalidation is owned by `PD-CH2-055`; this MUST adds only that replay restarts from the earliest affected phase and stale downstream results cannot remain usable. | CH2-T73 (gaming:L11098), CH2-T74 (happy:L11126) |
| 69 | `PD-CH2-065` | M | L2866 | `REPLAY` | Each lifecycle proof example MUST state preconditions, bound inputs, expected gate output and the specific failure route; prose-only examples are not proof. | CH2-T75 (gaming:L11138), CH2-T76 (happy:L11170) |
