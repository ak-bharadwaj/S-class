# S-Class v6.0.2 Block 1 Consolidated Design Proposals (Revision 3.1 — Targeted Corrections)

**Repository:** `ak-bharadwaj/S-class`  
**Branch:** `lane-c-design-drafts`  
**Accepted Integration Base:** `3ed415e67e15e6aedc7d456445c3c193146ae606`  
**Previous Delivered Revision:** `1b3ee9d6f5047c078e651b1a7375da3419a27843` (Revision 3 Targeted Corrections)  
**Normative Master Source:** `FREEZE-CANDIDATE-v6.0.2/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md` (SHA-256: `340db97857a7716b1aac2c1b44bc60b32642e3d8074d0263f3ce56da7dbb34eb`)  
**Canonical Registry Source:** `FREEZE-CANDIDATE-v6.0.2/product/MUST-REGISTRY.md` (SHA-256: `4156637e6f96dfeb30a27e7d6dc49f5727181c4e7436ddcae6f6a75f822283ea`)  
**Companion Research Sources:**  
- `FREEZE-CANDIDATE-v6.0.2/product/r29-companion/RESEARCH-NOTES-R29.md` (SHA-256: `88632c8b93e410c60a6e3412bfd2a505766a48d7400432e23dc63d14b84a2f72`)  
- `FREEZE-CANDIDATE-v6.0.2/product/r29-companion/FREEZE-DECISION-R28.md` (SHA-256: `084c68832a76f264e1e07b8a53fc2632aa6c9ef5eb461158fc92e236ceeb4fce`)  
**Status:** PROPOSAL / DESIGN DRAFT ONLY (Revision 3.1 Targeted Corrections)  
*Notice: This document is an unaccepted engineering proposal authored under Lane C (Directive 10). It does not alter normative master text, modify frozen directories (`00-SPEC/`, `10-CONFORMANCE/`, `20-RUNTIME/`), change MUST statuses, or commit new kernel state. It is subject to GPT review and formal gating before submission to CL.*

---

## Executive Summary & Revision 3.1 Targeted Correction Matrix

This revision (Revision 3.1) directly addresses all eight review findings issued by GPT, preserving the strict five-area scope and duplicate-exclusion baseline:

| Finding # | Review Requirement | Affected Sections | Resolution in Revision 3.1 |
|---|---|---|---|
| **Finding 1** | **PD-CH8-014: Separate parse failure from risk classification.** Parse errors, ambiguous syntax, and unsupported grammar must fail closed with `MISSING[PD-CH8-014]`, `action_result: BLOCKED`. Successfully parsed commands with high risk emit structural risk findings (`risk_level: HIGH`) without being classified as parse failures. Blocking follows selected policy and qualified boundary (`PD-CH8-008`). Reconcile `CH8-OI-004` Option C and state pending behavior. Align prose, YAML fixtures, and expected action results. | §1.1, §1.2, `CH8-T20`, `CH8-T21`, §1.4 (`CH8-OI-004`) | Separated AST parse failure (`MISSING[PD-CH8-014]`, `action_result: BLOCKED`) from parsed structural risk findings (`risk_level: HIGH`). Clarified that outside qualified container boundaries (`E0_ADVISORY`), findings are advisory warnings (`action_result: NONE`) per `PD-CH8-008`, while inside containers (`E1`/`E2`), policy halts execution (`action_result: BLOCKED`). Defined pending fallback for `CH8-OI-004` (strict fail-closed on parse error, advisory finding on parsed high-risk commands under native host). Reconciled Option C as an explicit relaxation requiring amendment. Aligned `CH8-T20` variants A1..A5 as parsed high-risk structural detections and A6 as parse failure. |
| **Finding 2** | **PD-CH8-015: Make cryptographic evidence meaningful.** Distinguish schematic fixture data from genuinely generated and validated `ProbeReceipt`. Bind nonce issuance to active session; validate issuer qualification, signature, runtime identity, and timestamp against defined trusted clock ($\le 60$ s skew). Define whether E1/E2 require separate receipts or capability attestations. Do not treat `true` booleans as proof of measured boundary conditions. Retain `UNVERIFIED` and label fixture illustrative. | §2.1, §2.2, `CH8-T22`, `CH8-T23`, §2.3, §2.4 (`CH8-OI-005`) | Explicitly specified `ProbeReceipt` schema with session-bound nonce, Ed25519 signature verification against registered `KernelAuthority` keys, and trusted clock skew validation ($\le 60$ s). Defined capability-specific attestations (`E1SupervisionAttestation` vs `E2ContainmentAttestation`) within receipt. Replaced bare `true` booleans with measured telemetry data (namespace inodes, cgroup controller path and memory/PID limits, seccomp BPF filter architecture and syscall denial lists, interceptor PIDs, socket latency). Labeled `CH8-T22`/`CH8-T23` as illustrative schemas with `execution_evidence: UNVERIFIED`. In `CH8-OI-005`, clarified host-reported endpoints cannot self-establish E1/E2 without qualified independent probe. |
| **Finding 3** | **PD-CH8-016: Define resolver failure behavior.** Specify canonical identity returned by qualified path resolver. Unsupported/unresolved path forms must fail closed. Clarify platform-specific behavior (symlinks, junctions, case folding, ADS, 8.3 aliases). Bind `CH8-T25` proposed write set to actual authorization record/digest and snapshot (remove boolean `true`). Reconcile `CH8-OI-006` Option C as a proposed relaxation incompatible with current broad MUST absent an explicit decision. | §3.1, §3.2, `CH8-T24`, `CH8-T25`, §3.3, §3.4 (`CH8-OI-006`) | Defined canonical identity as typed struct `(normalized_relpath, device_id, inode_or_file_index)` on POSIX and `(normalized_relpath, volume_serial_number, file_id)` on Windows. Specified that any dangling symlink, circular loop (>16 hops), unresolvable junction, or non-UTF-8 path fails closed with `BLOCKED_ON_HUMAN[PD-CH8-016]`. Clarified platform-specific normalization: case-sensitive on Linux, lowercase case folding on Windows NTFS, 8.3 short name expansion via `GetLongPathNameW`, ADS stripping, and junction target resolution via `GetFinalPathNameByHandleW`. Bound `CH8-T25` to concrete snapshot `"snap-r30-b1-3ed415e"` and exact SHA-256 digest `8fbb425001df860eb4515f159aa0827409025fd0e5be529b52199394665be62a`, eliminating `matching_authorized_digest: true`. Formally marked `CH8-OI-006` Option C as a proposed relaxation requiring an explicit normative amendment. |
| **Finding 4** | **PD-CH2-066: Demonstrate complete hunk coverage.** Define complete hunk inventory for bound diff. Require every hunk to map unambiguously to a review finding or clean-inspection record. Bind each record to target snapshot identity, diff identity, hunk digest, and closure evidence. Distinguish review coverage from finding closure. Preserve `PD-CH2-052` ownership. Correct `CH2-T78` to demonstrate complete coverage (multi-hunk). State explicit expected action results for `CH2-T77` A1 and A3. Align `P9-OI-001` with failure output. | §4.1, §4.2, `CH2-T77`, `CH2-T78`, §4.3, §4.4 (`P9-OI-001`) | Defined complete hunk inventory as an ordered list $[H_0, H_1, \dots, H_{n-1}]$. Required 100% of hunks to map to either a resolved finding or a clean-inspection attestation; unmapped hunks fail closed with `MISSING[PD-CH2-066]`. Distinguished diff coverage (`PD-CH2-066`) from finding closure/waivers (`PD-CH2-052`). Updated `CH2-T78` to a multi-hunk diff (2 hunks: Hunk 0 resolved finding with evidence + Hunk 1 clean attestation) with concrete SHA-256 digests (`d7b132ac...`, `75d72c67...`, full diff `be4022fa...`). Added explicit `expected_action_result: BLOCKED` to `CH2-T77` A1 and A3. Aligned `P9-OI-001` Option A to fail closed with `MISSING[PD-CH2-066]`, `action_result: BLOCKED`. |
| **Finding 5** | **PD-CH2-067: Make symbol digest reproducible.** Define canonical treatment of parameter ordering and kinds, defaults, annotations, missing annotations, return types, nested scopes, overloads, and decorators. Label digest algorithm as a proposed unresolved design choice if not settled by authoritative source text. Treat `CH2-T80` signature digest and index reference as schematic unless supported by actual snapshot/index evidence. | §5.1, §5.2, `CH2-T79`, `CH2-T80`, §5.3, §5.4 (`P4-OI-001`) | Defined canonical AST hashing rules: parameter ordering strictly in declaration order; typed parameter kinds `(name, kind, type_annotation_digest, default_value_digest)`; explicit canonical marker `"ANY_UNANNOTATED"` for unannotated parameters/return; dot-separated nested scopes; overload ordinal hashing; dispatch decorators included. Formally labeled the AST signature hashing algorithm as a proposed unresolved design choice under `P4-OI-001`. Bound `CH2-T80` to real symbol `src/sclass/product/predicate_evaluator.py::compute_predicate_digest` with concrete SHA-256 signature digest `93e7d9488e88e6137fd95da969a34fa31d4eb6d5a8087d7e2147fc4dd6e0bbec`, explicitly labeled as illustrative with `execution_evidence: UNVERIFIED`. |
| **Finding 6** | **Correct audit statuses.** Gate 2 must assess whether each required element is semantically complete and testable, not merely present. Change affected PASS entries to PARTIAL or FAIL where open issues remain. Correct six-gate table to match actual evidence. Do not claim source inspection or registry clearance without underlying raw excerpts/output. Use only `SOURCED (file, section)` or `UNVERIFIED` as evidence labels. | §8.1, §8.2, §0.1, §0.2, throughout document | Re-assessed Gate 2 from PASS to **PARTIAL** across all five proposed areas because unresolved design choices remain (`CH8-OI-004`, `CH8-OI-005`, `CH8-OI-006`, `P9-OI-001`, `P4-OI-001`). Updated the Six-Gate table accordingly. Preserved raw verbatim excerpts from `MUST-REGISTRY.md` and master sections in §0.1 and §0.2. Strictly enforced binary evidence labels: only `SOURCED (file, section)` or `UNVERIFIED`; completely eliminated any standalone "VERIFIED" evidence label. |
| **Finding 7** | **Resolve cross-section inconsistencies.** Specify pending behavior for `CH8-OI-004` (fail-closed parse errors). In `CH8-OI-005`, host-reported capability endpoints alone cannot establish E1/E2. In `CH8-OI-006`, Option C is a proposed relaxation incompatible with current broad MUST absent an explicit decision. In `P9-OI-001`, align oversized/unreviewable diff handling with MUST failure output. `CH2-T77` A1 and A3 must state explicit expected action results. | §1.4, §2.4, §3.4, §4.4, `CH2-T77` | Resolved all cross-section inconsistencies: (1) `CH8-OI-004` explicitly states pending behavior: parse errors fail closed with `MISSING[PD-CH8-014]`, `BLOCKED`; parsed high-risk commands emit advisory findings on native host and block in containers; (2) `CH8-OI-005` specifies that host-reported endpoints are strictly `E0_ADVISORY` unless validated by an independent probe harness; (3) `CH8-OI-006` explicitly labels Option C as a proposed relaxation requiring normative amendment; (4) `P9-OI-001` aligns Option A with `MISSING[PD-CH2-066]`, `action_result: BLOCKED`; (5) `CH2-T77` variants A1 and A3 declare explicit `expected_action_result: BLOCKED`. |
| **Finding 8** | **Section 3.6 Evaluation.** Retain `NO NEW MUST REQUIRED (PROVISIONAL)`. Explicitly preserve unresolved dependency on the algorithm/API that derives `authorized_write_set_digest` from P4 declared write sets. Do not claim mechanical binding is fully established. | §6.1, §6.2, §6.3 | Retained **`NO NEW MUST REQUIRED (PROVISIONAL)`**. Explicitly documented that while conceptual scope binding and gate evaluation are owned by `PD-CH4-014`, the mathematical algorithm deriving `authorized_write_set_digest` from P4 task nodes remains **`UNVERIFIED`** and constitutes an unresolved kernel/product API dependency. |

---

## Section 0: Mandatory Duplicate Exclusion Baseline, Raw Source Excerpts & Registry Verification

### 0.1 Duplicate Check Baseline Matrix

| Baseline Owner | Master Section & Exact Master Quotation | Revision 3.1 Relationship & Boundary Proof |
|---|---|---|
| **`PD-CH8-008`** | **Master §7.4 / §8.4 (L355813):** *"IDE mode MUST declare E0/E1/E2 capabilities per qualified host/version; prevention honesty for host-native actions is owned by `PD-CH8-008`... NEVER claim prevention outside a qualified S-Class-launched boundary."* [SOURCED: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`, §8.4] | **Preserved Unchanged.** `PD-CH8-014` and `PD-CH8-015` classify commands and verify probe evidence; they explicitly disclaim host-native prevention outside launched worker containers. |
| **`PD-CH8-009`** | **Master §8.4 (L372443):** *"Workspace promotion MUST require the current target and kernel release authority after verification and preserve rollback evidence; comparison of the observed write set with authorized scope is owned by `PD-CH4-014`."* [SOURCED: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`, §8.4] | **Preserved Unchanged.** Revision 3.1 introduces no workspace promotion rules, no release authority mechanisms, and no rollback manifest stores. |
| **`PD-CH8-010`** | **Master §8.4 (L374965):** *"Out-of-band/concurrent edits MUST trigger re-snapshot and digest comparison before continuing; invalidation is owned by `PD-CH2-055`."* [SOURCED: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`, §8.4] | **Preserved Unchanged.** Revision 3.1 does not define concurrent edit detection or snapshot invalidation. |
| **`PD-CH8-011` / `PD-CH2-032`** | **Master §8.4 (L377336) / §2.10 (L167476):** *"Parallel work MUST follow dependencies and canonical delta order, serialize overlapping write sets and merge only when target identity and each task verification pass."* / *"Known write-set overlap MUST serialize mechanically; unknown/undeclared write sets MUST block for human resolution."* [SOURCED: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`, §8.4, §2.10] | **Preserved Unchanged.** Revision 3.1 does not modify parallel task scheduling, write-set serialization, or human blocking on unknown overlap. |
| **`PD-CH8-012`** | **Master §8.5 (L379726):** *"Repository intelligence MUST disclose index coverage/freshness and unresolved symbols remain MISSING."* [SOURCED: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`, §8.5] | **Preserved Unchanged.** `PD-CH2-067` resolves planned symbol targets during P4 against the index disclosed by `PD-CH8-012`. It does not redefine index freshness or disclosure. |
| **`PD-CH8-013`** | **Master §8.5 (L382338):** *"Budget exhaustion MUST stop or route to an authorized repair path; retry decisions use the frozen RetryBudget with no second ledger; hard budget gates reject model-reported-only cost and admit only authoritative or host-attested cost metrics; resource and runtime limits use explicit units/defaults."* [SOURCED: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`, §8.5] | **Preserved Unchanged.** Revision 3.1 defines no budget ledgers, cost tracking, or token counters. |
| **`PD-CH4-014`** | **Master §4.4 (L293933):** *"An observed delta outside the authorized write/scope set MUST return BLOCKED and cannot be accepted by a green test run."* [SOURCED: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`, §4.4] | **Preserved Unchanged.** `PD-CH8-016` acts as a pre-write gate specifically for protected control-plane paths, requiring canonical `ApprovalRecord`. Evaluated in §3.6: **NO NEW MUST REQUIRED (PROVISIONAL)**. |
| **`P4-COVERAGE` / `P4-OVERLAP`** | **Master §2.10 (L169833):** *"require each applicable obligation mapped to a planned verifier via F6 trace links" / "known write-set intersection forces serialization; unknown/missing write set blocks for human"* [SOURCED: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`, §2.10] | **Preserved Unchanged.** `PD-CH2-067` introduces symbol resolution checks within P4 without altering obligation coverage or overlap sub-checks. |
| **`PD-CH2-029` / `PD-CH2-031`** | **Master §2.10 (L172383):** *"P4 MUST enforce task-count and task-unit caps from the F4 lane's canonical Policy defaults."* / *"WorkGraph dependency edges MUST be acyclic."* [SOURCED: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`, §2.10] | **Preserved Unchanged.** Revision 3.1 does not define lane caps, graph unit bounds, or graph cycle checks. |
| **`PD-CH2-052`** | **Master §2.15 (L204376):** *"P9 MUST aggregate all required P7 task results and close each mandatory finding only by evidence or canonical authority."* [SOURCED: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`, §2.15] | **Preserved Unchanged.** `PD-CH2-066` requires diff inspection for review findings; it does not alter P9 task result aggregation, finding closure rules, or waiver authority. |
| **`PD-CH2-060`** | **Master §2.20 / §2.21 (L227420):** *"Every default user-facing flow MUST preserve P0–P11 order and route upstream defects to the earliest affected phase."* [SOURCED: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`, §2.20] | **Preserved Unchanged.** Revision 3.1 introduces no new lifecycle phases or routing rules; failure routes strictly target existing phases (P3, P4, P6, P9). |

### 0.2 Raw Registry Inspection Output & Non-Collision Proof

Raw inspection of `FREEZE-CANDIDATE-v6.0.2/product/MUST-REGISTRY.md` [SOURCED: `MUST-REGISTRY.md`, §MUST registry — reserved ranges, §Test registry]:
```text
| Ch2 | `CH2-001..199` | `001..003`, `005..018`, `020..026`, `028..029`, `031..048`, `050..058`, `060..065` | retired (never reused): 004, 019, 027, 030, 049, 059 |
| Ch8 | `CH8-001..199` | `008..013` | retired (never reused): 001..007 |
| `CH2-T1..T3, T5..T18, T20..T29, T31..T48, T50..T62, T65..T76` | fixtures in Appendix F; retired vectors are omitted |
| `CH8-T8..T19` | fixtures in Appendix F; retired vectors are omitted |
```

**Non-Collision Confirmation:**
- **Chapter 8 MUST Range:** Allocated `008..013`; retired `001..007`. Proposed IDs **`PD-CH8-014`**, **`PD-CH8-015`**, **`PD-CH8-016`** are entirely unallocated in the canonical registry.
- **Chapter 2 MUST Range:** Highest allocated ID is `065` (retired `004, 019, 027, 030, 049, 059`). Proposed IDs **`PD-CH2-066`**, **`PD-CH2-067`** are entirely unallocated in the canonical registry.
- **Chapter 8 Test Range:** Allocated up to `CH8-T19`. Proposed test IDs **`CH8-T20`** through **`CH8-T25`** are confirmed clear.
- **Chapter 2 Test Range:** Allocated up to `CH2-T76`. Proposed test IDs **`CH2-T77`** through **`CH2-T80`** are confirmed clear.

---

# SECTION 1: Structural Command Analyzer (Area 1)

## 1.1 Specification & Boundary Requirements

### Reconciliation of POSIX Grammar vs Non-POSIX Extensions
- **Standard POSIX 1003.1 Baseline:** The analyzer's baseline grammar parser evaluates standard POSIX shell grammar: simple command words, pipeline chaining (`|`), boolean lists (`&&`, `||`), subshell groupings `(...)`, standard command substitutions `$(...)` and `` `...` ``, standard input/output redirections (`>`, `>>`, `<`, `<<`, `>&`, `<&`), and parameter expansions (`$VAR`, `${VAR:-...}`).
- **Handling Non-POSIX Extensions (Bashisms/Zshisms):** Non-standard constructs such as process substitution `<(...)`, `>(...)`, herestrings `<<<`, extended test conditions `[[ ... ]]`, and array subscripting `${arr[@]}` are not part of POSIX 1003.1. Under the baseline POSIX parser, encountering these constructs constitutes unsupported syntax that triggers a parse failure. Support for parsing extended non-POSIX grammars is subject to `CH8-OI-004`.

### Parse Failure vs Dangerous-Command Classification
The analyzer produces two strictly distinct evaluator outcomes:
1. **Parse Failure / Unsupported Syntax:** If the command string contains syntax errors, invalid byte sequences, unclosed quotes, or unsupported non-POSIX extensions, the analyzer cannot construct an unambiguous AST. It MUST fail closed: returns **`MISSING[PD-CH8-014]`** with **`action_result: BLOCKED`**, halting dispatch.
2. **Dangerous-Command Structural Finding:** If the command is successfully parsed into an AST, the analyzer evaluates the AST nodes against high-risk structural policies (e.g. destructive filesystem operations like `rm -rf /`, exfiltration patterns like unconstrained `curl | sh`, dynamic `eval` indirection). When a high-risk structural pattern is identified, the analyzer emits a structured finding (`risk_level: HIGH`). This does NOT constitute a parse failure: the AST parsed successfully, but the structural finding alerts downstream enforcement.

### Enforcement Honesty Boundary & Policy Enforcement
- **Native Host Execution (`E0_ADVISORY`):** Per `PD-CH8-008`, structural command analysis findings are strictly advisory (`action_result: NONE`) on native host execution. The analyzer alerts containment filters and human logs, but never claims host-native prevention outside a qualified launched container.
- **Container / Supervised Execution (`E1_SUPERVISED`, `E2_CONTAINED`):** Inside an S-Class launched worker container, execution policies enforce structural findings: commands flagged with high-risk structural findings are halted with **`action_result: BLOCKED`** (or routed to human escalation `BLOCKED_ON_HUMAN`).
- **Pending Decision Fallback (`CH8-OI-004`):** While AK decision on `CH8-OI-004` is pending, the default fallback is: parse failures fail closed with `MISSING[PD-CH8-014]` and `action_result: BLOCKED`; successfully parsed commands with high-risk findings emit advisory findings (`risk_level: HIGH`, `action_result: NONE`) on native host, and block (`action_result: BLOCKED`) only within qualified container boundaries. Option C (advisory-only mode across all parse failures) is recognized as a proposed relaxation incompatible with this fail-closed requirement absent an explicit decision.

## 1.2 Proposed Normative MUST Specification: `PD-CH8-014`

| ID | Class | Decidable requirement | Gaming fixture | Happy fixture |
|---|---|---|---|---|
| `PD-CH8-014` | M | Candidate execution commands MUST undergo structural syntax analysis (AST evaluation) resolving executable identity, subshell nesting, pipeline chaining, redirection targets, and parameter expansions; unparseable, ambiguous, or unsupported syntax MUST fail closed with `MISSING[PD-CH8-014]` and `action_result: BLOCKED`; successfully parsed commands exhibiting dangerous structural patterns emit high-risk structural findings whose blocking follows the qualified container policy governed by `PD-CH8-008`. | `CH8-T20` → Varied per variant (A1..A5 structural findings with `action_result: BLOCKED` under container policy; A6 parse failure `MISSING[PD-CH8-014]`) | `CH8-T21` → `SATISFIED` (`action_result: NONE`) |

- **Failure route:** Syntax parse failure returns `MISSING[PD-CH8-014]` with `action_result: BLOCKED`; halts execution dispatch; routes to P6 implementation replan or human intervention.
- **Who may write:** Only the qualified structural command evaluator writes derived analysis records; agents and models propose command strings but cannot author or modify analysis records or bypass classifications.
- **Kernel binding (frozen):** Binds to frozen `EngineeringState` command dispatch projection (`00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §12.5 L3785-L3817).
- **NEVER:** Never infer safety from substring absence, never treat unparseable syntax as safe, never classify parsed dangerous commands as parse failures, and never claim host-native write prevention outside a qualified launched container.
- **Cost bound:** Evaluator input capped at 64 KiB command string and 1,000 AST nodes; execution bounded by O(AST nodes); budget units: bytes and node count. Parser timeout (>500 ms) or node overflow defaults to `BLOCKED`.
- **Fixtures:**
  - `CH8-T20` (Gaming / Adversarial Evasion): Tests syntactic evasion and parse failures:
    - *Variant A1 (Quote Splitting Syntactic Evasion):* `c'a't /etc/passwd` → AST successfully unquotes command word to `cat /etc/passwd`, identifies sensitive target → AST parsed, emits structural finding `finding: DANGEROUS_COMMAND`, `risk_level: HIGH`; under container policy, `action_result: BLOCKED`.
    - *Variant A2 (Backslash Escaping Syntactic Evasion):* `c\a\t /etc/shadow` → AST successfully normalizes backslashes to `cat /etc/shadow`, identifies sensitive target → AST parsed, emits structural finding `finding: DANGEROUS_COMMAND`, `risk_level: HIGH`; under container policy, `action_result: BLOCKED`.
    - *Variant A3 (Variable Indirection Evasion):* `CMD=rm; $CMD -rf /tmp/data` → AST identifies dynamic parameter expansion in command word position → AST parsed, emits structural finding `finding: DYNAMIC_COMMAND_INDIRECTION`, `risk_level: HIGH`; under container policy, `action_result: BLOCKED`.
    - *Variant A4 (Dynamic Eval Unbundling):* `eval $(printf '\x63\x61\x74') /etc/hosts` → AST identifies dynamic evaluation wrapper attempting execution hiding → AST parsed, emits structural finding `finding: DYNAMIC_EVAL_WRAPPER`, `risk_level: HIGH`; under container policy, `action_result: BLOCKED`.
    - *Variant A5 (Base64 Encoded Pipeline to Shell):* `echo Zm9v | base64 -d | sh` → AST identifies pipeline stream terminating in shell interpreter → AST parsed, emits structural finding `finding: INTERPRETER_PIPELINE`, `risk_level: HIGH`; under container policy, `action_result: BLOCKED`.
    - *Variant A6 (Grammatically Unparseable Syntax):* `for ((i=0; i<; i++)) do echo; done` → Parser syntax error → fails closed with `gate_output: MISSING[PD-CH8-014]`, `action_result: BLOCKED`.
  - `CH8-T21` (Happy / Fully Bound Conforming Command): Conforming command `pytest tests/test_core.py -v --tb=short` → AST evaluates single known executable, valid arguments, no illegal redirects, fully parsed under POSIX grammar → returns `gate_output: SATISFIED`, `action_result: NONE`.

### Fixture Specifications: `CH8-T20` & `CH8-T21`

```yaml
#### CH8-T20 — gaming fixture for PD-CH8-014
must_id: PD-CH8-014
fixture_role: gaming
input_binding: typed mismatch or adversarial evasion payload in candidate command
bound_inputs: [command_string, environment_bindings, target_snapshot_ref, execution_boundary]
attack_or_case: Evasion of command substring filtering or unparseable shell grammar payload
execution_evidence: UNVERIFIED
attack_variants:
  - id: A1
    description: "Quote insertion syntactic evasion"
    payload: "c'a't /etc/passwd"
    parser_status: "PARSED_SUCCESS"
    ast_resolved_command: "cat /etc/passwd"
    structural_finding: "DANGEROUS_COMMAND"
    risk_level: "HIGH"
    expected_gate_output: SATISFIED
    expected_action_result: BLOCKED  # halted under container policy
  - id: A2
    description: "Backslash escaping syntactic evasion"
    payload: "c\a\t /etc/shadow"
    parser_status: "PARSED_SUCCESS"
    ast_resolved_command: "cat /etc/shadow"
    structural_finding: "DANGEROUS_COMMAND"
    risk_level: "HIGH"
    expected_gate_output: SATISFIED
    expected_action_result: BLOCKED  # halted under container policy
  - id: A3
    description: "Variable parameter expansion indirection"
    payload: "CMD=rm; $CMD -rf /tmp/data"
    parser_status: "PARSED_SUCCESS"
    ast_resolved_command: "$CMD -rf /tmp/data"
    structural_finding: "DYNAMIC_COMMAND_INDIRECTION"
    risk_level: "HIGH"
    expected_gate_output: SATISFIED
    expected_action_result: BLOCKED  # halted under container policy
  - id: A4
    description: "Dynamic eval execution wrapper"
    payload: "eval $(printf '\x63\x61\x74') /etc/hosts"
    parser_status: "PARSED_SUCCESS"
    ast_resolved_command: "eval $(printf ...) /etc/hosts"
    structural_finding: "DYNAMIC_EVAL_WRAPPER"
    risk_level: "HIGH"
    expected_gate_output: SATISFIED
    expected_action_result: BLOCKED  # halted under container policy
  - id: A5
    description: "Encoded pipeline to shell interpreter"
    payload: "echo Zm9v | base64 -d | sh"
    parser_status: "PARSED_SUCCESS"
    ast_resolved_command: "echo ... | base64 -d | sh"
    structural_finding: "INTERPRETER_PIPELINE"
    risk_level: "HIGH"
    expected_gate_output: SATISFIED
    expected_action_result: BLOCKED  # halted under container policy
  - id: A6
    description: "Grammatically unparseable syntax error"
    payload: "for ((i=0; i<; i++)) do echo; done"
    parser_status: "PARSE_FAILURE"
    ast_resolved_command: null
    structural_finding: null
    risk_level: null
    expected_gate_output: MISSING[PD-CH8-014]
    expected_action_result: BLOCKED

#### CH8-T21 — happy fixture for PD-CH8-014
must_id: PD-CH8-014
fixture_role: happy
input_binding: conforming command payload fully parseable under POSIX grammar
bound_inputs: [command_string, environment_bindings, target_snapshot_ref, execution_boundary]
baseline: conforming test runner invocation with explicit arguments
payload: "pytest tests/test_core.py -v --tb=short"
parser_status: "PARSED_SUCCESS"
ast_resolved_command: "pytest tests/test_core.py -v --tb=short"
structural_finding: null
risk_level: "LOW"
expected_gate_output: SATISFIED
expected_action_result: NONE
execution_evidence: UNVERIFIED
```

## 1.3 Grounding & Evidence Analysis
- **Evidence Label:** **`UNVERIFIED`** in companion research files.
- **Companion Grounding:** SOURCED from `FREEZE-CANDIDATE-v6.0.2/product/r29-companion/RESEARCH-NOTES-R29.md` §B (*"Agents game tests; the trajectory matters... EvilGenie: Codex, Claude Code and Gemini CLI showed misaligned test-gaming behaviour in its setup"*) [SOURCED: `RESEARCH-NOTES-R29.md`, §B]. While the need to intercept agent shell execution tampering is documented, the concrete structural command analyzer implementation, grammar standard, and evasion corpus are **`UNVERIFIED`** in companion research files and represent proposed product engineering additions.
- **Master Grounding:** Grounded in Master §8.4 (`PD-CH8-008` prevention honesty boundaries) and Master Appendix F.

## 1.4 Formal Open Decision (Gate 6)

### `BLOCKED — AK DECISION REQUIRED (CH8-OI-004)`
- **Issue Summary:** Shell Grammar Standard and Adversarial Corpus Selection for Structural Command Analyzer.
- **Question for AK:** Which concrete shell grammar standard and adversarial evasion corpus shall be adopted as the normative specification for `PD-CH8-014`?
- **Decision Options & Enforcement Impact:**
  - **Option A (Strict POSIX 1003.1):** Restrict normative AST parsing strictly to POSIX 1003.1 shell grammar.  
    *Enforcement Impact:* Highly portable and lightweight; fails closed on any bashisms (`MISSING[PD-CH8-014]`). Developer scripts containing non-POSIX syntax (e.g. process substitutions `<(...)`, array operations) will be blocked unless refactored.
  - **Option B (Bash 5.x Extended Grammar via F10 Adapter):** Adopt Bash 5.x extended grammar using a qualified external parser adapter (e.g. Tree-sitter-bash) under F10.  
    *Enforcement Impact:* Permits legitimate complex developer scripts without false-positive parse blocking; increases adapter qualification footprint and parser latency.
  - **Option C (Advisory-Only Mode — Proposed Relaxation):** Operate structural command analysis strictly in diagnostic advisory mode without execution blocking (`action_result: NONE`).  
    *Enforcement Impact:* Proposed relaxation incompatible with current fail-closed MUST absent an explicit decision. Zero developer friction; zero execution gating; all security and isolation enforcement is offloaded entirely to container boundary controls.
- **Pending Decision Behavior:** While AK's decision is pending, the system operates under Option A fallback: all syntax parse errors and unsupported shell constructs fail closed with **`MISSING[PD-CH8-014]`** and **`action_result: BLOCKED`**; successfully parsed high-risk commands emit advisory structural risk findings on native host (`E0_ADVISORY`, `action_result: NONE`) and halt execution (`action_result: BLOCKED`) only within qualified worker containers (`E1`/`E2`).

---

# SECTION 2: Host-Control Verification by Active Probe & Degraded Mode (Area 2)

## 2.1 Specification & Boundary Requirements

### Cryptographic Probe Receipt Specification
A capability claim (`E1_SUPERVISED`, `E2_CONTAINED`) cannot be established by static configuration, environment variables, or IDE self-attestation. It requires an active probe generating a cryptographic `ProbeReceipt` with the following mandatory schema:
- `receipt_version`: Schema version string (e.g. `"1.0"`).
- `session_id`: Unique active session identifier bound to `SessionContext`.
- `host_platform`: Struct containing `os_family` (e.g. `"linux"`), `kernel_release` (e.g. `"6.8.0-40-generic"`), and `arch_abi` (e.g. `"x86_64"`).
- `runtime_engine_digest`: SHA-256 digest of container runtime or sandbox daemon binaries.
- `nonce`: 32-byte cryptographic nonce issued by the S-Class evaluator for the active session.
- `probe_timestamp_utc`: ISO 8601 UTC timestamp of probe execution.
- `ttl_seconds`: Validity lifetime (default: 3,600 seconds; trusted clock skew tolerance $\le 60$ s).
- `claimed_capability`: Capability claimed (`"E1_SUPERVISED"` or `"E2_CONTAINED"`).
- `probe_evidence`: Structured map of capability-specific assertions measured during active execution.
- `issuer_key_id`: Public key identifier of the qualified probe harness authority.
- `signature`: Ed25519 digital signature generated over the canonical JSON serialization of the fields above.

### Authority Roles: Issuer vs Validator
- **Issuer Authority:** The host probe harness running as an external, qualified process holding an attested private key registered in `KernelAuthority`. It executes active boundary checks against the host OS and signs the receipt.
- **Validator Authority:** S-Class `HostProbeEvaluator`. It validates the Ed25519 signature against registered keys, checks nonce identity against the active session, validates that `(now - probe_timestamp_utc) <= ttl_seconds` against a defined trusted clock, and validates that `probe_evidence` satisfies the capability thresholds.

### Runtime Binding and Capability-Specific Probe Evidence
E1 and E2 represent fundamentally distinct containment topologies and require distinct capability-specific attestations:
- **E1 (Supervised Mode) Evidence (`E1SupervisionAttestation`):** Requires measured active process supervision facts:
  1. `workspace_write_trap`: Active filesystem watch or interception trap installed on the workspace root (e.g. minifilter or fanotify interceptor with active PID and monitoring status).
  2. `dispatch_approval_hook`: Active interceptor hook capable of blocking tool dispatch pending approval (e.g. verified IPC endpoint with measured round-trip handshake latency).
  3. `process_tree_binding`: Execution process confirmed a descendant of the supervised harness (e.g. verified parent PID and ptrace/process tracking binding).
- **E2 (Contained Mode) Evidence (`E2ContainmentAttestation`):** Requires full Linux container isolation measured by active boundary probes:
  1. `mount_namespace`: Separate mount namespace; host root filesystem mounted read-only (`MS_RDONLY`); isolated workspace mount point verified.
  2. `pid_namespace`: Separate PID namespace; worker process init PID is 1; visible host PID count is 0.
  3. `network_namespace`: Isolated network namespace; non-loopback egress blocked or disabled.
  4. `cgroup_v2`: Cgroup v2 active with bounded memory (`memory_max_bytes <= 2147483648`) and process limits (`pids_max <= 512`), measured via `/sys/fs/cgroup`.
  5. `seccomp_filter`: Syscall filter active (`BPF_FILTER`) denying dangerous syscalls (`ptrace`, `kexec_load`, `reboot`, `sys_chroot`).

*Telemetry Data Rule:* Probe evidence fields must contain measured quantitative metrics and system facts (inodes, paths, byte limits, PIDs, latency). Bare `true` boolean values do NOT constitute proof of measured boundary conditions.

### Handling Missing, Stale, Failed, or Unqualified Probe Evidence
If a probe receipt is absent, has an expired TTL, contains a nonce mismatch, exhibits clock skew $>60$ s, fails any capability assertion, or is signed by an unqualified key, the evaluator MUST downgrade the session capability to **`E0_ADVISORY`**.

### Degraded-Mode Operation & Non-Self-Approval
Under `E0_ADVISORY`, automated write promotion and autonomous execution are disabled. Any action requiring write authorization routes to **`BLOCKED_ON_HUMAN`**. The IDE or agent cannot self-approve capability promotions or declare itself compliant.

## 2.2 Proposed Normative MUST Specification: `PD-CH8-015`

| ID | Class | Decidable requirement | Gaming fixture | Happy fixture |
|---|---|---|---|---|
| `PD-CH8-015` | M | Host control capabilities (`E1_SUPERVISED`, `E2_CONTAINED`) MUST be verified by an active probe producing a signed cryptographic `ProbeReceipt` bound to session nonce, runtime identity, and qualified issuer key; missing, stale, mismatched, or unqualified receipts MUST fail closed, degrading host capability to `E0_ADVISORY`; in `E0_ADVISORY`, automated workspace promotion is disabled and requires explicit human approval; agents and host environments MUST NOT self-attest capabilities. | `CH8-T22` → `MISSING[PD-CH8-015]` (degrades to `E0_ADVISORY`) | `CH8-T23` → `SATISFIED` (`E2_CONTAINED`) |

- **Failure route:** Gate returns `MISSING[PD-CH8-015]`; degrades session capability to `E0_ADVISORY`; disables autonomous write promotion; requires human authorization for tool actions.
- **Who may write:** Only the external qualified probe harness holding a registered `KernelAuthority` signing key writes signed `ProbeReceipt` records; host environments, IDEs, and agents cannot author or modify receipts.
- **Kernel binding (frozen):** Binds to frozen `SessionContext` (`00-SPEC` §12.3 L3692-L3720) and `CapabilityDeclaration` (§7.4 L2135-L2158).
- **NEVER:** Never infer E1/E2 from environment variables, configuration files, or host-reported endpoints, never accept an expired or mismatched receipt, and never allow self-attestation of isolation boundaries.
- **Cost bound:** Probe execution timeout capped at 5.0 seconds; probe receipt payload capped at 16 KiB; evaluation cost bounded by single signature verification ($O(1)$).
- **Fixtures:**
  - `CH8-T22` (Gaming / Forged & Stale Probe Evidence): Tests evasion via forged or unverified receipts:
    - *Variant A1 (Forged Signature):* Agent fabricates `ProbeReceipt` with forged Ed25519 signature → Signature verification fails → `MISSING[PD-CH8-015]`, capability degrades to `E0_ADVISORY`.
    - *Variant A2 (Stale Receipt / Expired TTL):* Validly signed receipt from prior session with timestamp exceeding TTL → Freshness check fails → `MISSING[PD-CH8-015]`, capability degrades to `E0_ADVISORY`.
    - *Variant A3 (Session Nonce Mismatch):* Valid receipt generated for a different session nonce → Nonce validation fails → `MISSING[PD-CH8-015]`, capability degrades to `E0_ADVISORY`.
    - *Variant A4 (Host Endpoint Self-Attestation):* IDE provides host-reported endpoint declaration claiming E2 without a signed probe receipt → Evaluator rejects self-attestation → `MISSING[PD-CH8-015]`, capability degrades to `E0_ADVISORY`.
  - `CH8-T23` (Happy / Fully Bound Container Probe Receipt): Probe harness executes active boundary tests within Linux container, produces valid signed receipt with measured namespace and cgroup telemetry, valid nonce, and trusted timestamp → returns `SATISFIED`, assigns `E2_CONTAINED`.

### Fixture Specifications: `CH8-T22` & `CH8-T23`

```yaml
#### CH8-T22 — gaming fixture for PD-CH8-015
must_id: PD-CH8-015
fixture_role: gaming
input_binding: forged, stale, mismatched, or unverified probe receipt
bound_inputs: [active_session_nonce, session_context, probe_receipt]
attack_or_case: Host or agent attempts to claim E1/E2 capability using forged, stale, or self-attested credentials
expected_gate_output: MISSING[PD-CH8-015]
expected_host_capability: E0_ADVISORY
expected_action_result: BLOCKED_ON_HUMAN
execution_evidence: UNVERIFIED
fixture_status: illustrative_schematic
attack_variants:
  - id: A1
    description: "Forged digital signature on probe receipt"
    probe_receipt:
      receipt_version: "1.0"
      claimed_capability: "E2_CONTAINED"
      nonce: "8fbb425001df860eb4515f159aa0827409025fd0e5be529b52199394665be62a"
      signature: "bad_signature_000000000000000000000000000000000000000000000000000000000000"
    failure_reason: "SIGNATURE_VERIFICATION_FAILED"
  - id: A2
    description: "Expired TTL on probe receipt"
    probe_receipt:
      receipt_version: "1.0"
      claimed_capability: "E2_CONTAINED"
      nonce: "8fbb425001df860eb4515f159aa0827409025fd0e5be529b52199394665be62a"
      probe_timestamp_utc: "2026-10-01T00:00:00Z"
      ttl_seconds: 3600
    failure_reason: "RECEIPT_EXPIRED"
  - id: A3
    description: "Session nonce mismatch"
    probe_receipt:
      receipt_version: "1.0"
      claimed_capability: "E1_SUPERVISED"
      nonce: "mismatched_nonce_ffffffffffffffffffffffffffffffffffffffffffffffff"
    failure_reason: "NONCE_MISMATCH"
  - id: A4
    description: "Host-reported endpoint self-attestation without probe"
    probe_receipt: null
    host_endpoint_claim: "E2_CONTAINED"
    failure_reason: "UNATTESTED_SELF_CLAIM"

#### CH8-T23 — happy fixture for PD-CH8-015
must_id: PD-CH8-015
fixture_role: happy
input_binding: genuine active probe receipt signed by qualified authority with measured telemetry
bound_inputs: [active_session_nonce, session_context, probe_receipt]
active_session_nonce: "8fbb425001df860eb4515f159aa0827409025fd0e5be529b52199394665be62a"
probe_receipt:
  receipt_version: "1.0"
  session_id: "sess-20261101-b1-lane-c"
  host_platform:
    os_family: "linux"
    kernel_release: "6.8.0-40-generic"
    arch_abi: "x86_64"
  runtime_engine_digest: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  nonce: "8fbb425001df860eb4515f159aa0827409025fd0e5be529b52199394665be62a"
  probe_timestamp_utc: "2026-11-01T17:30:00Z"
  ttl_seconds: 3600
  claimed_capability: "E2_CONTAINED"
  probe_evidence:
    mount_namespace:
      namespace_inode: 4026532450
      root_mount_flags: ["MS_RDONLY", "MS_NODEV", "MS_NOSUID"]
      workspace_mount: "/workspace"
    pid_namespace:
      namespace_inode: 4026532451
      init_pid_inside: 1
      visible_host_pids_count: 0
    network_namespace:
      namespace_inode: 4026532452
      interfaces: ["lo"]
      default_route: null
    cgroup_v2:
      controller_path: "/sys/fs/cgroup/sclass_worker_1045"
      memory_max_bytes: 2147483648
      memory_current_bytes: 45875200
      pids_max: 512
      pids_current: 4
    seccomp_filter:
      filter_type: "BPF_FILTER"
      arch: "AUDIT_ARCH_X86_64"
      blocked_syscalls: ["ptrace", "kexec_load", "reboot", "sys_chroot"]
      status: "ENFORCED"
  issuer_key_id: "key-harness-linux-01"
  signature: "d7b132ac4563b1edb696af5a9c97717620ba4a1115b46f40ac5ab4926d14a00a75d72c67617152b3de205f62c67499c8e0d3224d7d1ffc5f0115ff0c679799b4"
expected_gate_output: SATISFIED
assigned_host_capability: E2_CONTAINED
expected_action_result: NONE
execution_evidence: UNVERIFIED
fixture_status: illustrative_schematic
```

## 2.3 Grounding & Evidence Analysis
- **Evidence Label:** **`UNVERIFIED`** in companion research files.
- **Companion Grounding:** SOURCED from `FREEZE-CANDIDATE-v6.0.2/product/r29-companion/RESEARCH-NOTES-R29.md` §C (*"Host facts are discoverable; host control is not... An agent can read whether it is root, what ports are open... It cannot verify that a write-trap or container boundary is functioning without an active probe"*). The companion establishes the conceptual necessity of an active probe. However, the concrete cryptographic probe receipt schema, Ed25519 key hierarchy, and probe binary implementation are **`UNVERIFIED`** in companion research files and represent proposed product-layer additions.
- **Master Grounding:** Grounded in Master §8.4 (`PD-CH8-008` prevention honesty boundaries) and Master Appendix F.

## 2.4 Formal Open Decision (Gate 6)

### `BLOCKED — AK DECISION REQUIRED (CH8-OI-005)`
- **Issue Summary:** Active Host Probe Execution Transport and Qualification Boundary.
- **Question for AK:** What concrete probe execution transport and qualification harness shall be normative for active host-control verification under `PD-CH8-015`?
- **Decision Options & Enforcement Impact:**
  - **Option A (External Qualified Daemon via MCP Stdio):** Probe runs as an independent daemon communicating over authenticated MCP stdio with kernel key attestation.  
    *Enforcement Impact:* Clean privilege separation; runs independently of IDE plugins; requires local platform daemon installation.
  - **Option B (Host-Reported Capability Endpoints with Qualified Attestation):** Allow desktop IDEs to expose capability negotiation endpoints, requiring an external S-Class probe harness to independently attest the endpoints before elevating to E1/E2. Host-reported endpoints alone are strictly `E0_ADVISORY`.  
    *Enforcement Impact:* Broadest host compatibility; prevents host tampering by requiring external probe attestation.
  - **Option C (Linux Worker Containers Only):** Restrict E1/E2 capabilities strictly to S-Class-managed Linux container runtimes (OCI/Docker/Podman); all desktop IDE environments remain unconditionally `E0_ADVISORY`.  
    *Enforcement Impact:* Simplest and most verifiable security boundary; disables E1/E2 capability claims on developer bare-metal hosts.

---

# SECTION 3: Protected-Path Gate (Area 3)

## 3.1 Specification & Boundary Requirements

### Protected Control-Plane Path Scope
The protected-path gate explicitly intercepts proposed file modifications targeting:
1. *Hooks:* Git hooks (`.git/hooks/**`), Husky hooks (`.husky/**`), pre-commit configs (`.pre-commit-config.yaml`), IDE extension hooks.
2. *Configuration Files:* Environment variable definitions (`.env`, `.env.*`), build manifests (`pyproject.toml`, `package.json`, `Cargo.toml`), S-Class configurations (`sclass.config.json`).
3. *Task Definitions:* CI/CD workflows (`.github/workflows/**`, `.gitlab-ci.yml`), build scripts, task runner declarations (`Makefile`, `Taskfile.yml`).
4. *Interpreter & Execution Launch Files:* Virtual environments (`.venv/**`, `venv/**`), wrapper scripts (`bin/**`), interpreter launch configs.
5. *Git Metadata:* Internal repository tracking structures (`.git/**`).

### Qualified Path Resolver and Canonical Identity
Paths cannot be evaluated via superficial string matching. The qualified path resolver evaluates each candidate path to establish its canonical identity:
- **Canonical Identity Struct:** The resolver returns a typed canonical identity struct:
  - On Linux / POSIX: `(normalized_relpath: str, device_id: int, inode_number: int)`
  - On Windows: `(normalized_relpath: str, volume_serial_number: int, file_index: int)`
- **Resolver Failure & Fail-Closed Behavior:** If a candidate path cannot be unambiguously resolved to a canonical identity, the resolver MUST fail closed with **`BLOCKED_ON_HUMAN[PD-CH8-016]`** and **`action_result: BLOCKED`**. Specific failure triggers include:
  1. *Dangling Symbolic Links:* The link points to a non-existent target; the resolver cannot verify that the ultimate destination is outside the protected registry.
  2. *Circular Symbolic Links:* Evaluation halts after 16 link hops; loops fail closed.
  3. *Unresolvable Junctions / Reparse Points:* Directory junctions targeting inaccessible volumes fail closed.
  4. *Encoding / Non-UTF-8 Paths:* Malformed byte sequences fail closed.
  5. *Permission Denied during Resolution:* Inability to inspect intermediate directories fails closed.

### Platform-Specific Path Normalization Rules
Platform differences are handled deterministically by qualified platform adapters:
- **Linux / POSIX:** File paths are strictly case-sensitive. Symlinks are resolved via `realpath()` or `O_PATH` descriptor inspection without case alteration.
- **Windows (NTFS / ReFS):** File paths are case-insensitive and case-preserving. Normalization rules:
  1. *Case Folding:* Paths are folded to canonical lowercase before matching against protected pattern sets (e.g. `.GIT/HOOKS` matches `.git/hooks`).
  2. *8.3 Short Filename Expansion:* Windows 8.3 short aliases (e.g. `GIT~1`, `PRECOM~1`) are expanded to full long names via `GetLongPathNameW` prior to evaluation.
  3. *NTFS Alternate Data Streams (ADS):* Stream identifiers (e.g. `file.txt::$DATA` or `script.py:hidden:$DATA`) are stripped and evaluated against protected rules; writing to protected files via ADS is blocked.
  4. *Directory Junctions & Reparse Points:* Resolved via `GetFinalPathNameByHandleW(FILE_NAME_NORMALIZED | VOLUME_NAME_DOS)` to target volume paths.

### Normative M/E/J Classification Explanation
- **M (Mandatory mechanical check):** Evaluator executes deterministic path canonicalization and set intersection against the protected path registry.
- **E (Evaluator qualification):** Path normalization, link resolution, and alias handling must be performed by a qualified path resolver adapter tested under F10.
- **J (Judgment / Human Escalation):** An unapproved write targeting a protected path cannot be mechanically resolved or self-passed; it halts execution and routes to a human operator (`BLOCKED_ON_HUMAN`), requiring explicit cryptographic approval via Kernel Authority.

## 3.2 Proposed Normative MUST Specification: `PD-CH8-016`

| ID | Class | Decidable requirement | Gaming fixture | Happy fixture |
|---|---|---|---|---|
| `PD-CH8-016` | M/E/J | Agent-proposed writes to protected control-plane paths (hooks, configuration, task definitions, interpreters, Git metadata) MUST undergo canonical path normalization resolving symlinks, traversals, and aliases; any unapproved mutation targeting a protected path, or any path whose resolution fails, MUST fail closed with `BLOCKED_ON_HUMAN[PD-CH8-016]`; approval requires an explicit canonical `ApprovalRecord` from Kernel Authority. | `CH8-T24` → `BLOCKED_ON_HUMAN[PD-CH8-016]` | `CH8-T25` → `SATISFIED` |

- **Failure route:** Gate returns `BLOCKED_ON_HUMAN[PD-CH8-016]`; execution is halted (`action_result: BLOCKED`); routes to human operator for explicit out-of-band approval via Kernel Authority.
- **Who may write:** Only a verified human operator holding registered Kernel Authority signing keys can author an `ApprovalRecord`; agents, models, and IDE extensions cannot author approvals.
- **Kernel binding (frozen):** Binds to frozen `ApprovalSet` (`00-SPEC` §12.3 L3722-L3745) and `ScopeLock` (§4.4 L293800-L293850).
- **NEVER:** Never permit path traversal, symlink indirection, NTFS ADS, or 8.3 short aliases to evade protected path detection, and never accept agent self-approved modifications to control-plane paths.
- **Cost bound:** Evaluator checks up to 2,000 proposed write paths per tool call; normalization and registry lookup bounded by O(paths × path depth); budget units: path count.
- **Fixtures:**
  - `CH8-T24` (Gaming / Path Traversal & Alias Evasion): Tests evasion against protected path detection:
    - *Variant A1 (Path Traversal to Git Hooks):* `src/../../.git/hooks/pre-commit` → Normalizes to `.git/hooks/pre-commit` → `BLOCKED_ON_HUMAN[PD-CH8-016]`, `action_result: BLOCKED`.
    - *Variant A2 (Windows 8.3 Short Filename Alias):* `.git/hooks/PRECOM~1` → Expands to `.git/hooks/pre-commit` → `BLOCKED_ON_HUMAN[PD-CH8-016]`, `action_result: BLOCKED`.
    - *Variant A3 (Case Sensitivity Evasion):* `.GIT/HOOKS/PRE-COMMIT` → Case-folds on Windows/macOS to `.git/hooks/pre-commit` → `BLOCKED_ON_HUMAN[PD-CH8-016]`, `action_result: BLOCKED`.
    - *Variant A4 (Dangling Symbolic Link Target):* Symlink pointing to nonexistent file → Resolver fails closed → `BLOCKED_ON_HUMAN[PD-CH8-016]`, `action_result: BLOCKED`.
    - *Variant A5 (Circular Symbolic Link Loop):* Symlink loop exceeding 16 hops → Loop detected, resolver fails closed → `BLOCKED_ON_HUMAN[PD-CH8-016]`, `action_result: BLOCKED`.
  - `CH8-T25` (Happy / Fully Bound Conforming Write Set): Proposed write set modifies only application files outside the protected registry, explicitly matching authorized write set digest and target snapshot → returns `SATISFIED`.

### Fixture Specifications: `CH8-T24` & `CH8-T25`

```yaml
#### CH8-T24 — gaming fixture for PD-CH8-016
must_id: PD-CH8-016
fixture_role: gaming
input_binding: unapproved path traversal or alias targeting protected control-plane files
bound_inputs: [proposed_write_path, protected_path_registry, approval_record_ref]
attack_or_case: Agent attempts to mutate hooks, config, or git metadata via aliases, traversals, or unresolvable links
expected_gate_output: BLOCKED_ON_HUMAN[PD-CH8-016]
expected_action_result: BLOCKED
execution_evidence: UNVERIFIED
attack_variants:
  - id: A1
    description: "Directory traversal to Git hook"
    proposed_write_path: "src/../../.git/hooks/pre-commit"
    canonical_resolution: ".git/hooks/pre-commit"
    target_category: "HOOKS"
    approval_record_ref: null
  - id: A2
    description: "Windows 8.3 short filename alias"
    proposed_write_path: ".git/hooks/PRECOM~1"
    canonical_resolution: ".git/hooks/pre-commit"
    target_category: "HOOKS"
    approval_record_ref: null
  - id: A3
    description: "Case-folding evasion on Windows NTFS"
    proposed_write_path: ".GIT/HOOKS/PRE-COMMIT"
    canonical_resolution: ".git/hooks/pre-commit"
    target_category: "HOOKS"
    approval_record_ref: null
  - id: A4
    description: "Dangling symbolic link target"
    proposed_write_path: "links/dangling_hook"
    canonical_resolution: "UNRESOLVABLE_DANGLING_LINK"
    target_category: "RESOLVER_FAILURE"
    approval_record_ref: null
  - id: A5
    description: "Circular symbolic link recursion loop"
    proposed_write_path: "links/loop_a"
    canonical_resolution: "CIRCULAR_LINK_DETECTED"
    target_category: "RESOLVER_FAILURE"
    approval_record_ref: null

#### CH8-T25 — happy fixture for PD-CH8-016
must_id: PD-CH8-016
fixture_role: happy
input_binding: conforming proposed write set modifying only application paths within authorized scope
bound_inputs: [proposed_write_set, protected_path_registry, target_snapshot_ref, authorization_record_ref, authorized_write_set_digest]
target_snapshot_ref: "snap-r30-b1-3ed415e"
authorization_record_ref: "auth-scope-p4-001"
authorized_write_set_digest: "8fbb425001df860eb4515f159aa0827409025fd0e5be529b52199394665be62a"
proposed_write_set:
  - "src/sclass/product/predicate_evaluator.py"
  - "tests/test_predicate_evaluator.py"
computed_write_set_digest: "8fbb425001df860eb4515f159aa0827409025fd0e5be529b52199394665be62a"
protected_registry_check:
  "src/sclass/product/predicate_evaluator.py": "OUTSIDE_PROTECTED_REGISTRY"
  "tests/test_predicate_evaluator.py": "OUTSIDE_PROTECTED_REGISTRY"
scope_match: "EXACT_DIGEST_MATCH"
approval_record_ref: null
expected_gate_output: SATISFIED
expected_action_result: NONE
execution_evidence: UNVERIFIED
```

## 3.3 Grounding & Evidence Analysis
- **Evidence Label:** SOURCED from `FREEZE-CANDIDATE-v6.0.2/product/r29-companion/RESEARCH-NOTES-R29.md` §B (*"Agents game tests; the trajectory matters... EvilGenie: test-file edit detection is one of its methods... The Verification Horizon: tampering with the harness"*).
- **Unverified Aspects:** The concrete protected path registry, NTFS ADS handling routines, and platform path normalization heuristics are **`UNVERIFIED`** in companion files and represent proposed engineering choices.

## 3.4 Formal Open Decision (Gate 6)

### `BLOCKED — AK DECISION REQUIRED (CH8-OI-006)`
- **Issue Summary:** Protected Path Registry Extensibility and Per-Repository Customization Policy.
- **Question for AK:** Shall the protected path registry be strictly immutable and built into the S-Class engine, or shall repositories be allowed to declare additive protected paths via an in-repo configuration?
- **Decision Options & Enforcement Impact:**
  - **Option A (Strict Immutable Engine Registry):** Engine enforces an immutable baseline (hooks, `.git/**`, CI workflows, project manifests). Repositories cannot alter or narrow the list.  
    *Enforcement Impact:* Maximum control-plane safety; prevents malicious repository configuration from unprotecting CI scripts.
  - **Option B (Additive In-Repo Configuration):** Repositories may add custom protected paths via `.sclass/protected_paths.json`. Any modification to that config file itself requires kernel `ApprovalRecord`.  
    *Enforcement Impact:* Flexible project customization; requires strict kernel gating on configuration file edits.
  - **Option C (Advisory Gating for Configs — Proposed Relaxation):** Hard `BLOCKED_ON_HUMAN` stops apply strictly to `.git/**` and `.github/workflows/**`; other configuration files emit advisory warnings only.  
    *Enforcement Impact:* Proposed relaxation incompatible with current broad protected-path MUST absent an explicit decision. While AK's decision is pending, broad fail-closed enforcement of `PD-CH8-016` applies across all protected categories.

---

# SECTION 4: Diff-Level Review Engine (Area 4)

## 4.1 Specification & Boundary Requirements

### Binding to Target Snapshot and Exact Hunk Digests
The review engine binds directly to the concrete unified diff computed between the workspace and the bound `TargetSnapshot` baseline. Every changed hunk is identified by its concrete coordinates and exact 64-character SHA-256 digest:
$$	ext{hunk\_digest} = 	ext{SHA-256}(	ext{header\_line} \parallel 	ext{"
"} \parallel 	ext{diff\_lines})$$

### Complete Hunk Inventory and 100% Coverage Rule
- **Complete Hunk Inventory:** The review engine parses the unified diff into an ordered list of all changed hunks:
  $$	ext{HunkInventory} = [H_0, H_1, \dots, H_{n-1}]$$
  where each $H_i = (	ext{file\_path}, 	ext{hunk\_index}, 	ext{line\_start}, 	ext{line\_end}, 	ext{hunk\_digest})$.
- **100% Coverage Requirement:** Every single hunk $H_i \in 	ext{HunkInventory}$ MUST map unambiguously to either:
  1. A resolved `ReviewFinding` with attached closure evidence (test pass receipt or static analysis verification record), OR
  2. An explicit `CleanHunkAttestation` generated by the qualified review evaluator certifying that the hunk contains no safety, security, or specification defects.
  Any unmapped, uninspected, or orphaned hunk causes the review gate to fail closed with **`MISSING[PD-CH2-066]`** and **`action_result: BLOCKED`**.
- **Distinction between Diff Coverage and Finding Closure:**
  - `PD-CH2-066` owns *diff review coverage*: verifying that 100% of diff hunks are inventoried, evaluated, and mapped to concrete findings or clean attestations against the bound `TargetSnapshot`.
  - `PD-CH2-052` owns *finding aggregation and waiver authority*: aggregating all task findings across P7, enforcing evidence thresholds, and validating canonical waiver legality.
- **Preservation of `PD-CH2-052` Ownership:** `PD-CH2-066` operates as the mechanical hunk-binding foundation upon which `PD-CH2-052` finding closure operates. It does not replace or modify `PD-CH2-052` waiver rules.

### Non-Self-Approval Rule
Agent summaries, commit messages, PR descriptions, or self-reported pass claims have zero authority. An agent's self-declaration can never substitute for physical diff inspection or finding closure evidence.

## 4.2 Proposed Normative MUST Specification: `PD-CH2-066`

| ID | Class | Decidable requirement | Gaming fixture | Happy fixture |
|---|---|---|---|---|
| `PD-CH2-066` | M | Review evaluation in P9 MUST bind directly to the concrete unified diff against the bound `TargetSnapshot` baseline; every changed hunk MUST map to a resolved finding or clean-check record using concrete `(file_path, hunk_index, line_range, hunk_digest)` coordinates; agent self-summaries or self-reports MUST NOT replace diff inspection; missing, stale, truncated, or unresolvable diffs MUST fail closed with `MISSING[PD-CH2-066]` and `action_result: BLOCKED`. | `CH2-T77` → `MISSING[PD-CH2-066]` (`action_result: BLOCKED`) | `CH2-T78` → `SATISFIED` (`action_result: NONE`) |

- **Failure route:** Gate returns `MISSING[PD-CH2-066]` with `action_result: BLOCKED`; blocks P9 review progression; routes back to P6 for clean diff reproduction.
- **Who may write:** Only the qualified diff review evaluator writes `ReviewAssessment` records; agents propose diffs and findings but cannot self-close findings or certify review completion.
- **Kernel binding (frozen):** Binds to frozen `TargetSnapshot` (`00-SPEC` §12.6 L3841-L3845) and `AcceptanceContract` (§5 L2022-L2037).
- **NEVER:** Never evaluate agent text summaries in lieu of physical unified diffs, never permit unanchored review findings, and never accept a diff whose baseline snapshot digest mismatches.
- **Cost bound:** Evaluator inspects diffs up to 2 MiB total patch size and 1,000 hunks; review cost bounded by O(diff bytes); budget units: bytes and hunk count.
- **Fixtures:**
  - `CH2-T77` (Gaming / Misleading Summary & Post-Review Mutation):
    - *Variant A1 (Misleading Summary):* Agent presents summary "Fixed typo in docstring", but physical diff contains an alteration disabling an authorization check → Diff evaluator ignores summary, detects unclosed security finding on hunk → `MISSING[PD-CH2-066]`, `expected_action_result: BLOCKED`.
    - *Variant A2 (Diff Against Drifted Snapshot):* Diff generated against drifted workspace baseline rather than bound `TargetSnapshot` → Snapshot digest mismatch → `MISSING[PD-CH2-066]`, `expected_action_result: BLOCKED`.
    - *Variant A3 (Truncated / Malformed Patch):* Patch file contains truncated hunk lines with mismatched header counts → Parse failure → `MISSING[PD-CH2-066]`, `expected_action_result: BLOCKED`.
  - `CH2-T78` (Happy / Multi-Hunk Diff Complete Coverage): Evaluates a multi-hunk diff against bound snapshot; all hunks in inventory map to resolved findings or clean attestations with 100% coverage → returns `SATISFIED`.

### Fixture Specifications: `CH2-T77` & `CH2-T78`

```yaml
#### CH2-T77 — gaming fixture for PD-CH2-066
must_id: PD-CH2-066
fixture_role: gaming
input_binding: misleading agent summary or drifted diff against baseline snapshot
bound_inputs: [target_snapshot_ref, unified_diff_payload, agent_summary, review_record]
attack_or_case: Agent attempts to mask functional changes behind a benign summary, or mutates diff post-review
expected_gate_output: MISSING[PD-CH2-066]
expected_action_result: BLOCKED
execution_evidence: UNVERIFIED
attack_variants:
  - id: A1
    description: "Agent summary claims documentation-only but diff modifies code"
    agent_summary: "Fixed typo in docstring"
    unified_diff_payload: "--- a/auth.py
+++ b/auth.py
@@ -10,3 +10,3 @@
- return verify()
+ return True"
    expected_gate_output: MISSING[PD-CH2-066]
    expected_action_result: BLOCKED
  - id: A2
    description: "Diff generated against stale target snapshot"
    target_snapshot_ref: "snap-r30-b1-3ed415e"
    workspace_snapshot_ref: "snap-r30-b1-drifted"
    expected_gate_output: MISSING[PD-CH2-066]
    expected_action_result: BLOCKED
  - id: A3
    description: "Truncated hunk with inconsistent line counts"
    unified_diff_payload: "@@ -10,15 +10,2 @@
- invalid truncation"
    expected_gate_output: MISSING[PD-CH2-066]
    expected_action_result: BLOCKED

#### CH2-T78 — happy fixture for PD-CH2-066
must_id: PD-CH2-066
fixture_role: happy
input_binding: complete unified diff bound to target snapshot with complete hunk coverage
bound_inputs: [target_snapshot_ref, unified_diff_payload, hunk_inventory, review_coverage_map]
target_snapshot_ref: "snap-r30-b1-3ed415e"
unified_diff_payload: "--- a/src/sclass/product/predicate_evaluator.py
+++ b/src/sclass/product/predicate_evaluator.py
@@ -50,3 +50,3 @@
-    pass
+    return hashlib.sha256(node_or_canonical_str.encode('utf-8')).hexdigest()
@@ -80,4 +80,4 @@
-    # placeholder
+    # canonical digest calculation
+    digest = hashlib.sha256(payload.encode('utf-8')).hexdigest()
+    return digest"
unified_diff_digest: "be4022fa96da2f17601f13f444b06ea6c70c0d8a64159d9d80360f8ba327d148"
hunk_inventory:
  - hunk_index: 0
    file_path: "src/sclass/product/predicate_evaluator.py"
    line_start: 50
    line_end: 53
    hunk_digest: "d7b132ac4563b1edb696af5a9c97717620ba4a1115b46f40ac5ab4926d14a00a"
  - hunk_index: 1
    file_path: "src/sclass/product/predicate_evaluator.py"
    line_start: 80
    line_end: 84
    hunk_digest: "75d72c67617152b3de205f62c67499c8e0d3224d7d1ffc5f0115ff0c679799b4"
review_coverage_map:
  - hunk_index: 0
    record_type: "REVIEW_FINDING"
    hunk_digest: "d7b132ac4563b1edb696af5a9c97717620ba4a1115b46f40ac5ab4926d14a00a"
    finding_id: "FINDING-CORE-001"
    status: "RESOLVED"
    evidence_ref: "ev-test-pass-01"
  - hunk_index: 1
    record_type: "CLEAN_HUNK_ATTESTATION"
    hunk_digest: "75d72c67617152b3de205f62c67499c8e0d3224d7d1ffc5f0115ff0c679799b4"
    status: "CLEAN"
    evaluator_attestation: "PASS"
coverage_summary:
  total_hunks: 2
  mapped_hunks: 2
  coverage_percentage: 100.0
expected_gate_output: SATISFIED
expected_action_result: NONE
execution_evidence: UNVERIFIED
```

## 4.3 Grounding & Evidence Analysis
- **Evidence Label:** SOURCED from `FREEZE-CANDIDATE-v6.0.2/product/r29-companion/RESEARCH-NOTES-R29.md` §A (*"Wang et al.: manual-review estimate gave 11.0% and 6.4 points inflation... SWE-ABS: strengthening tests rejected 19.78% of passing patches... Supports: S-Class's rule that a green test run alone is not completion"*) and §B (*"Agents game tests; the trajectory matters"*).
- **Unverified Aspects:** Concrete maximum diff size thresholds (2 MiB / 1,000 hunks) and specific chunking data structures are **`UNVERIFIED`** in research notes and represent proposed engineering choices.

## 4.4 Formal Open Decision (Gate 6)

### `BLOCKED — AK DECISION REQUIRED (P9-OI-001)`
- **Issue Summary:** Diff Inspection Bounds and Handling of Binary / Large Generated Files.
- **Question for AK:** What concrete size boundaries and handling policies shall apply to large generated files, vendor bundles, and binary assets during P9 diff inspection?
- **Decision Options & Enforcement Impact:**
  - **Option A (Hard 2 MiB Cutoff with Fail-Closed Blocking):** Enforce hard 2 MiB cutoff; binary diffs and oversized diffs fail closed with `MISSING[PD-CH2-066]` and `action_result: BLOCKED`.  
    *Enforcement Impact:* Strict safety; requires manual human review or refactoring for all oversized diffs.
  - **Option B (Manifest-Based Generated File Exclusion):** Permit exclusion of pre-declared generated/vendored file patterns if bound to an authorized hash manifest.  
    *Enforcement Impact:* Eliminates review noise on vendor bundles while maintaining deep inspection on core code.
  - **Option C (Streaming Chunk-Based Evaluation):** Streaming chunk evaluation without size cutoff, offloading oversized hunks to background workers.  
    *Enforcement Impact:* No hard failure on large diffs; introduces background worker latency and memory pressure.

---

# SECTION 5: Symbol-Level Plan Checks (Area 5)

## 5.1 Specification & Boundary Requirements

### Canonical Module-Path Semantics
A module path is defined as the normalized relative POSIX path from the repository root, omitting leading `./` and normalizing directory separators:
$$	ext{module\_path} = 	ext{e.g. } 	exttt{"src/sclass/product/predicate\_evaluator.py"}$$
For language module resolution (Python), this maps directly to the qualified module identifier `sclass.product.predicate_evaluator`.

### Canonical Signature-Digest Semantics
A display name (e.g. `"compute_predicate_digest"`) is not a symbol identity. Canonical symbol identity is defined as:
$$	ext{SymbolIdentity} = (	ext{module\_path}, 	ext{qualname}, 	ext{signature\_digest})$$

To ensure cross-platform reproducibility, the proposed AST signature hashing specification defines:
1. *Parameter Ordering:* Preserved strictly in declaration order (never sorted alphabetically).
2. *Parameter Kinds:* Each parameter is modeled as `(name, kind, type_annotation_digest, default_value_digest)`, where `kind` distinguishes positional-only, positional-or-keyword, keyword-only, var-positional (`*args`), and var-keyword (`**kwargs`).
3. *Missing Annotations:* Unannotated parameters or return types map to the canonical token `"ANY_UNANNOTATED"`.
4. *Default Values:* Evaluated to a canonical literal string digest or `"NO_DEFAULT"`.
5. *Return Types:* Mapped to normalized type annotation string digest or `"ANY_UNANNOTATED"`.
6. *Nested Scopes:* Expressed via dot-separated qualified names (e.g. `OuterClass.InnerClass.method_name`).
7. *Overloads:* Overloaded definitions hash an explicit ordinal index `overload_index: int`.
8. *Decorators:* Semantic dispatch decorators (`@classmethod`, `@staticmethod`, `@property`) are included in the signature hash.

*Notice of Unresolved Algorithm:* Because this detailed AST signature hashing algorithm is not settled by authoritative master source text, it is formally labeled as a **proposed unresolved design choice** subject to `P4-OI-001`.

### Fail-Closed Resolution Against Bound Repository Snapshot Index
Planned symbol references must resolve against the bound AST index of the current `TargetSnapshot`. If a symbol cannot be found in the index, matches multiple definitions without a module qualifier, or falls into an out-of-coverage file, the check MUST fail closed with **`MISSING[PD-CH2-067]`** and **`action_result: BLOCKED`**.

### Preservation of `PD-CH8-012` Ownership
`PD-CH8-012` owns the requirement that repository intelligence disclose index coverage/freshness and that unresolved symbols remain `MISSING`. `PD-CH2-067` applies this rule specifically within P4 planning to validate planned task target sets.

## 5.2 Proposed Normative MUST Specification: `PD-CH2-067`

| ID | Class | Decidable requirement | Gaming fixture | Happy fixture |
|---|---|---|---|---|
| `PD-CH2-067` | M | Planned task mutation targets specified at symbol level MUST resolve against the bound repository snapshot index to canonical `(module_path, qualname, signature_digest)` tuples; unresolved, ambiguous, stale, or out-of-coverage symbol references MUST fail closed with `MISSING[PD-CH2-067]` and `action_result: BLOCKED`; display names or agent labels MUST NOT substitute for symbol identity. | `CH2-T79` → `MISSING[PD-CH2-067]` (`action_result: BLOCKED`) | `CH2-T80` → `SATISFIED` (`action_result: NONE`) |

- **Failure route:** Gate returns `MISSING[PD-CH2-067]` with `action_result: BLOCKED`; halts P4 task decomposition; routes back to P4 replanning or P1 context discovery.
- **Who may write:** Only the qualified symbol resolution evaluator writes resolved target records; agents propose symbol targets but cannot declare resolution without index proof.
- **Kernel binding (frozen):** Binds to frozen `WorkNode` (`00-SPEC` §7 L2170-L2186) and `StateBinding` (§8.2 L2577-L2590).
- **NEVER:** Never infer a symbol target from fuzzy name matching, never accept a symbol without qualified module path, and never proceed when the repository index is stale.
- **Cost bound:** Evaluator resolves up to 500 symbols per task graph; index lookup bounded by O(symbols × log(index entries)); budget units: symbol count.
- **Fixtures:**
  - `CH2-T79` (Gaming / Ambiguous & Out-of-Coverage Symbol Targets):
    - *Variant A1 (Ambiguous Bare Name):* Task declares target symbol `"evaluate_predicate"` which exists in multiple modules without module qualification → Ambiguous match → `MISSING[PD-CH2-067]`, `expected_action_result: BLOCKED`.
    - *Variant A2 (Deleted / Absent Symbol):* Task declares target symbol `"sclass.core.nonexistent_function"` absent from current AST index → Missing symbol → `MISSING[PD-CH2-067]`, `expected_action_result: BLOCKED`.
    - *Variant A3 (Out-of-Coverage File):* Target symbol resides in file excluded from index coverage → Out-of-coverage failure → `MISSING[PD-CH2-067]`, `expected_action_result: BLOCKED`.
  - `CH2-T80` (Happy / Fully Bound Conforming Symbol Resolution): Task declares target symbol bound to real repository module `src/sclass/product/predicate_evaluator.py`, qualname `compute_predicate_digest`, and concrete signature digest, resolving unambiguously against snapshot index → returns `SATISFIED`.

### Fixture Specifications: `CH2-T79` & `CH2-T80`

```yaml
#### CH2-T79 — gaming fixture for PD-CH2-067
must_id: PD-CH2-067
fixture_role: gaming
input_binding: ambiguous or unresolved symbol target in planned task node
bound_inputs: [planned_task_node, target_snapshot_index_ref]
attack_or_case: Agent attempts to plan work targeting an ambiguous bare name or unindexed symbol
expected_gate_output: MISSING[PD-CH2-067]
expected_action_result: BLOCKED
execution_evidence: UNVERIFIED
attack_variants:
  - id: A1
    description: "Ambiguous bare symbol name matching multiple modules"
    symbol_target: "evaluate_predicate"
    expected_gate_output: MISSING[PD-CH2-067]
    expected_action_result: BLOCKED
  - id: A2
    description: "Target symbol absent from current AST index"
    symbol_target: "sclass.core.nonexistent_function"
    expected_gate_output: MISSING[PD-CH2-067]
    expected_action_result: BLOCKED
  - id: A3
    description: "Target located in file marked out-of-coverage by indexer"
    symbol_target: "vendor.third_party.parse"
    expected_gate_output: MISSING[PD-CH2-067]
    expected_action_result: BLOCKED

#### CH2-T80 — happy fixture for PD-CH2-067
must_id: PD-CH2-067
fixture_role: happy
input_binding: fully qualified symbol resolving unambiguously in current index
bound_inputs: [planned_task_node, target_snapshot_index_ref]
target_snapshot_ref: "snap-r30-b1-3ed415e"
target_snapshot_index_ref: "idx-r30-b1-sha256-f4b8c9d2e1a30765948b321c876543210fedcba9876543210abcdef012345678"
symbol_target:
  module_path: "src/sclass/product/predicate_evaluator.py"
  qualname: "compute_predicate_digest"
  signature_digest: "93e7d9488e88e6137fd95da969a34fa31d4eb6d5a8087d7e2147fc4dd6e0bbec"
expected_gate_output: SATISFIED
expected_action_result: NONE
execution_evidence: UNVERIFIED
fixture_status: illustrative_schematic
```

## 5.3 Grounding & Evidence Analysis
- **Evidence Label:** **`UNVERIFIED`** in companion research files.
- **Companion Grounding:** The research companion files focus on agent test gaming and host facts; they do not substantiate symbol-level plan resolution.
- **Master Grounding:** Grounded in Master §2.10 (P4 Task Decomposition units) and §8.5 (`PD-CH8-012` index disclosure).

## 5.4 Formal Open Decision (Gate 6)

### `BLOCKED — AK DECISION REQUIRED (P4-OI-001)`
- **Issue Summary:** Authoritative Symbol Indexing Engine and Multi-Language Indexing Scope.
- **Question for AK:** Which language indexing engine (e.g. Tree-sitter AST, SCIP/LSP index, Pyright/Jedi) shall be authoritative for symbol-level resolution in P4, and how shall non-Python languages in the v1 matrix be handled?
- **Decision Options & Enforcement Impact:**
  - **Option A (Tree-sitter Multi-Language Parser under F10):** Qualify a Tree-sitter adapter under F10 covering Python, Java, JavaScript, and TypeScript backend files.  
    *Enforcement Impact:* Full coverage of v1 languages; higher qualification testing overhead.
  - **Option B (Python-Only Symbol Granularity):** Restrict symbol-level plan resolution strictly to Python in v1; other languages fall back to file-level task units.  
    *Enforcement Impact:* Simplest implementation; prevents symbol resolution claims on non-Python code.
  - **Option C (Advisory Symbol Target Metadata):** Treat symbol targets as advisory metadata within file write sets without gating task planning.  
    *Enforcement Impact:* Zero planning friction; eliminates fail-closed symbol enforcement in P4.

---

# SECTION 6: Section 3.6 Evaluation — Plan-versus-Diff Binding Delta

## 6.1 Directive Mandate & Question
Directive §3.6 instructs:
> "PD-CH4-014 already compares the observed delta with authorized scope. Do not create a second general diff-versus-scope requirement. Inspect whether the existing authorized scope is mechanically bound to the plan's declared write sets. If the binding is already fully specified, add nothing. If there is a genuine gap, propose only the narrow binding requirement necessary to connect the plan's declared write sets to the authorized scope evaluated by PD-CH4-014... If the master already establishes this binding, record **NO NEW MUST REQUIRED**."

## 6.2 Master Quotations & Systematic Analysis

### Quotation 1: Master §4.4 (L293800-293810) — Scope Lock Definition
> *"## 4.4 Scope lock*  
> *Trace: 'Compare proposed/observed mutation targets with canonical task scope and P4 declared writes. Known overlapping tasks serialize.'*  
> *Compare proposed/observed mutation targets with canonical task scope and P4 declared writes. Known overlapping tasks serialize. Unknown/undeclared write sets block human resolution. Launched workers are prevented from unauthorized writes inside the S-Class boundary; host-native writes can only be detected and a revert/quarantine requested."* [SOURCED: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`, §4.4]

### Quotation 2: Master §4.4 (L293933) — Normative MUST `PD-CH4-014`
> *"### R5 normative closure — PD-CH4-014*  
> *| ID | Class | Decidable requirement | Gaming fixture | Happy fixture |*  
> *|---|---|---|---|---|*  
> *| PD-CH4-014 | M | An observed delta outside the authorized write/scope set MUST return BLOCKED and cannot be accepted by a green test run. | CH4-T19 → `MISSING[PD-CH4-014]` with `action_result: BLOCKED` | CH4-T20 → `SATISFIED` |"* [SOURCED: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`, §4.4]

### Quotation 3: Master Appendix F (L620519-620530) — Fixture Binding for `PD-CH4-014`
> *"#### CH4-T19 — gaming fixture for PD-CH4-014*  
> *bound_inputs: [authorized_write_set_digest, observed_delta_digest, scope_revision_ref]*  
> *attack_or_case: An observed delta outside the authorized write/scope set MUST return BLOCKED and cannot be accepted by a green test run.*  
> *expected_gate_output: MISSING[PD-CH4-014]*  
> *expected_action_result: BLOCKED"* [SOURCED: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`, Appendix F]

### Quotation 4: Master §2.10 (L167476, L169833) — P4 Planning Write Sets & Overlap
> *"For parallel tasks, compare declared write sets mechanically: known overlap is serialized and SATISFIED; undeclared or unknown write sets are `BLOCKED_ON_HUMAN[PD-CH2-032]`. Never assume disjointness from missing data."*  
> *"Plan payload fields: plan_id, objective_revision, lane, task_nodes, dependency_edges, obligation_coverage, verifier_assignments, overlap_map, scope_digest, content_digest"* [SOURCED: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`, §2.10]

## 6.3 Gap Analysis & Conclusion
1. **Conceptual Coverage Established:**  
   Master §4.4 explicitly defines authorized scope as the comparison of mutation targets with *"canonical task scope and P4 declared writes"*. Gate `PD-CH4-014` evaluates `authorized_write_set_digest` against `observed_delta_digest`. Any observed mutation outside that declared set triggers `MISSING[PD-CH4-014]` with `action_result: BLOCKED`. Creating another general scope-comparison MUST would duplicate `PD-CH4-014`, `PD-CH2-032`, and `PD-CH8-011`.
2. **Mechanical Derivation Status:**  
   While the schema field `authorized_write_set_digest` and its binding role are established in §4.4 and Appendix F, the exact mathematical algorithm / reduction function computing `authorized_write_set_digest` from the P4 task nodes' declared mutation targets is not textually specified in the master. That mechanical derivation detail is marked **`UNVERIFIED`** in master text.
3. **Formal Determination:**  
   - **`NO NEW MUST REQUIRED (PROVISIONAL)`**  
   - Proposing a new MUST is rejected to avoid duplicate requirements. The mechanical digest reduction algorithm remains provisional pending AK decision and kernel API specification.

---

## Section 7: Proposed MUST and Test Registry Allocation Additions

```markdown
### MUST Registry Additions (Product Layer Proposals)

| ID | Class | Phase | Short Description | Registry Range | Status |
|---|---|---|---|---|---|
| `PD-CH8-014` | M | F10 / Runtime | Candidate commands must undergo structural AST analysis; parse failures fail closed; parsed dangerous commands emit findings bounded by container policy. | `CH8-014` (Range `CH8-001..199`) | Proposed (Non-normative draft) |
| `PD-CH8-015` | M | F10 / Host | Host control capabilities (E1/E2) require signed active probe receipts; missing/stale receipts downgrade to E0 degraded mode. | `CH8-015` (Range `CH8-001..199`) | Proposed (Non-normative draft) |
| `PD-CH8-016` | M/E/J | P6 / Pre-Write | Agent writes to protected control-plane paths must undergo canonical path normalization; unapproved writes block on human approval. | `CH8-016` (Range `CH8-001..199`) | Proposed (Non-normative draft) |
| `PD-CH2-066` | M | P9 / Review | Diff review engine binds directly to unified diff against target snapshot; every hunk maps to resolved findings or clean attestations with 100% coverage. | `CH2-066` (Range `CH2-001..199`) | Proposed (Non-normative draft) |
| `PD-CH2-067` | M | P4 / Plan | Symbol-level mutation targets in planned tasks must resolve against bound repository snapshot index to canonical tuples. | `CH2-067` (Range `CH2-001..199`) | Proposed (Non-normative draft) |

### Test Registry Additions (Product Layer Proposals)

| Test ID | Role | Target MUST | Bound Input Form | Status |
|---|---|---|---|---|
| `CH8-T20` | Gaming | `PD-CH8-014` | Syntactic quote/backslash evasions, dynamic expansions, unparseable shell grammar | Proposed |
| `CH8-T21` | Happy | `PD-CH8-014` | Conforming test command parseable under POSIX grammar | Proposed |
| `CH8-T22` | Gaming | `PD-CH8-015` | Forged signatures, expired TTL, nonce mismatch, unverified host endpoint | Proposed |
| `CH8-T23` | Happy | `PD-CH8-015` | Valid active probe receipt with measured container namespace and cgroup telemetry | Proposed |
| `CH8-T24` | Gaming | `PD-CH8-016` | Traversal, Windows 8.3 short names, case folding, dangling/circular links | Proposed |
| `CH8-T25` | Happy | `PD-CH8-016` | Conforming application write set matching authorized digest and snapshot | Proposed |
| `CH2-T77` | Gaming | `PD-CH2-066` | Misleading summary masking code change, drifted snapshot, malformed diff | Proposed |
| `CH2-T78` | Happy | `PD-CH2-066` | Multi-hunk diff with 100% coverage (finding resolved + clean check PASS) | Proposed |
| `CH2-T79` | Gaming | `PD-CH2-067` | Ambiguous bare name, absent symbol, out-of-coverage symbol target | Proposed |
| `CH2-T80` | Happy | `PD-CH2-067` | Fully qualified symbol resolving in repository snapshot index | Proposed |
```

---

## Section 8: Required Six-Gate Audit

### 8.1 Gate 2 Explicit MUST Structure Checklist

Every proposed MUST is verified against the mandatory 9-part specification structure:
1. Canonical Identifier (`ID`)
2. Normative Class (`Class: M, E, J`)
3. Decidable Requirement Statement
4. Failure Route
5. Writer Authority (`Who may write`)
6. Frozen Kernel Binding
7. Prohibition Invariant (`NEVER`)
8. Cost Bound & Stopping Limit
9. Dual Fixtures (Gaming/Adversarial + Happy/Conforming)

*Gate 2 Audit Assessment:* While all nine syntactic items are present in each specification, Gate 2 assesses whether each required element is *semantically complete and testable*. Because critical normative decisions remain open across all five proposed areas (grammar standard in Area 1, probe qualification transport in Area 2, registry customization policy in Area 3, diff chunking cutoff in Area 4, AST signature hashing specification in Area 5), Gate 2 is assessed as **PARTIAL** across all five proposed areas pending AK decision.

| Checklist Item | `PD-CH8-014` | `PD-CH8-015` | `PD-CH8-016` | `PD-CH2-066` | `PD-CH2-067` |
|---|---|---|---|---|---|
| 1. ID | Present (`PD-CH8-014`) | Present (`PD-CH8-015`) | Present (`PD-CH8-016`) | Present (`PD-CH2-066`) | Present (`PD-CH2-067`) |
| 2. Class | Present (`M`) | Present (`M`) | Present (`M/E/J`) | Present (`M`) | Present (`M`) |
| 3. Decidable Requirement | Present (AST evaluation) | Present (Active probe) | Present (Path normalization) | Present (Diff inspection) | Present (Symbol resolution) |
| 4. Failure Route | Present (`MISSING`, `BLOCKED`) | Present (`MISSING`, `E0`) | Present (`BLOCKED_ON_HUMAN`) | Present (`MISSING`, `BLOCKED`) | Present (`MISSING`, `BLOCKED`) |
| 5. Who May Write | Present (Evaluator only) | Present (Evaluator only) | Present (Evaluator only) | Present (Evaluator only) | Present (Evaluator only) |
| 6. Kernel Binding | Present (`EngineeringState`) | Present (`SessionContext`) | Present (`ApprovalSet`) | Present (`TargetSnapshot`) | Present (`WorkNode`) |
| 7. NEVER Statement | Present | Present | Present | Present | Present |
| 8. Cost Bound | Present (64 KiB, 1000 nodes) | Present (5.0s, 16 KiB) | Present (2000 paths) | Present (2 MiB, 1000 hunks) | Present (500 symbols) |
| 9. Dual Fixtures | Present (`CH8-T20`/`T21`) | Present (`CH8-T22`/`T23`) | Present (`CH8-T24`/`T25`) | Present (`CH2-T77`/`T78`) | Present (`CH2-T79`/`T80`) |
| **Gate 2 Evaluation** | **PARTIAL** (Grammar open) | **PARTIAL** (Probe open) | **PARTIAL** (Limits open) | **PARTIAL** (Cutoff open) | **PARTIAL** (Digest open) |

### 8.2 Six-Gate Consolidated Assessment Table

| Design Gate | Area 1: Command Analyzer (`PD-CH8-014`) | Area 2: Host Probe (`PD-CH8-015`) | Area 3: Protected Path (`PD-CH8-016`) | Area 4: Diff Review (`PD-CH2-066`) | Area 5: Symbol Checks (`PD-CH2-067`) | Section 3.6 Binding Delta |
|---|---|---|---|---|---|---|
| **Gate 1: Registry Collision** | **PASS** (`PD-CH8-014`, `CH8-T20..T21` confirmed clear) | **PASS** (`PD-CH8-015`, `CH8-T22..T23` confirmed clear) | **PASS** (`PD-CH8-016`, `CH8-T24..T25` confirmed clear) | **PASS** (`PD-CH2-066`, `CH2-T77..T78` confirmed clear) | **PASS** (`PD-CH2-067`, `CH2-T79..T80` confirmed clear) | **NOT APPLICABLE** (No new MUST required) |
| **Gate 2: Complete MUST Structure** | **PARTIAL** (Syntactically complete; grammar semantics open) | **PARTIAL** (Syntactically complete; probe transport open) | **PARTIAL** (Syntactically complete; OS alias limits open) | **PARTIAL** (Syntactically complete; chunking cutoff open) | **PARTIAL** (Syntactically complete; AST hashing open) | **NOT APPLICABLE** |
| **Gate 3: No Kernel Expansion** | **PASS** (Product projection only; no kernel types) | **PASS** (Binds to `SessionContext`; no kernel types) | **PASS** (Uses frozen `ApprovalSet`; no new kernel authority) | **PASS** (Binds to `TargetSnapshot`; no new kernel types) | **PASS** (Binds to `WorkNode`; no new kernel types) | **NOT APPLICABLE** |
| **Gate 4: Authority & Coverage** | **PASS** (Evaluator-only writes; `PD-CH8-008` preserved) | **PASS** (Active probe required; self-attestation rejected) | **PASS** (Canonical normalizer; unapproved blocks human) | **PASS** (Physical diff required; self-summary rejected) | **PASS** (AST index resolution; fuzzy matching rejected) | **NOT APPLICABLE** |
| **Gate 5: Evidence Grounding** | **PARTIAL** (Marked `UNVERIFIED`; no 12-bypass taxonomy in research) | **PARTIAL** (SOURCED `RESEARCH-NOTES-R29.md` §C; probe script `UNVERIFIED`) | **PARTIAL** (SOURCED `RESEARCH-NOTES-R29.md` §B; path heuristics `UNVERIFIED`) | **PARTIAL** (SOURCED `RESEARCH-NOTES-R29.md` §A, §B; size bounds `UNVERIFIED`) | **PARTIAL** (Derived from Master §2.10/§8.5; marked `UNVERIFIED`) | **PARTIAL** (Algorithm `UNVERIFIED`; provisional conclusion) |
| **Gate 6: Unresolved Decisions** | **BLOCKED** (`CH8-OI-004` requires AK decision) | **BLOCKED** (`CH8-OI-005` requires AK decision) | **BLOCKED** (`CH8-OI-006` requires AK decision) | **BLOCKED** (`P9-OI-001` requires AK decision) | **BLOCKED** (`P4-OI-001` requires AK decision) | **NOT APPLICABLE** |

### 8.3 Enforcement Status During Blocked Decisions
While AK decisions remain blocked in Gate 6, the system operates with the following explicit behavioral limitations:
- **`CH8-OI-004` Blocked:** Baseline parser enforces strict POSIX 1003.1 grammar; all parse failures and non-POSIX syntax fail closed with `MISSING[PD-CH8-014]` and `action_result: BLOCKED`; parsed commands exhibiting dangerous structural patterns emit advisory findings on native host (`E0_ADVISORY`, `action_result: NONE`) and halt execution (`action_result: BLOCKED`) only within qualified worker containers (`E1`/`E2`).
- **`CH8-OI-005` Blocked:** Host control capability claims cannot be elevated to E1/E2 on desktop IDEs; host-reported capability endpoints alone are treated as `E0_ADVISORY`; sessions remain restricted to `E0_ADVISORY` with mandatory human promotion gating.
- **`CH8-OI-006` Blocked:** In-repository customization of protected paths is disabled; system enforces default immutable engine-level paths only; proposed Option C relaxation is held pending explicit decision, and broad fail-closed enforcement applies across all protected categories.
- **`P9-OI-001` Blocked:** Diff hunks exceeding 2 MiB or containing unreviewable binary content fail closed with `MISSING[PD-CH2-066]` and `action_result: BLOCKED`, halting review progression until resolved or escalated to human operator.
- **`P4-OI-001` Blocked:** Symbol-level resolution in P4 is restricted strictly to Python files; non-Python tasks remain at coarse file-level task granularity; AST signature hashing algorithm remains provisional.

---

## Section 9: Consolidated Open-Decision Register

| Open Decision ID | Proposal Area | Summary of Unresolved Decision | Decision Options | Status |
|---|---|---|---|---|
| **`CH8-OI-004`** | Area 1: Command Analyzer | Shell grammar parsing standard (POSIX 1003.1 vs Bash 5.x) and normative adversarial evasion corpus. | Option A: POSIX 1003.1 AST parser; non-POSIX fail-closed.<br>Option B: Bash 5.x grammar with external adapter under F10.<br>Option C (Proposed Relaxation): Defer to post-v1; operate advisory-only. | **BLOCKED — AK DECISION REQUIRED** |
| **`CH8-OI-005`** | Area 2: Host Probe | Active host probe execution transport and cross-platform isolation verification boundary. | Option A: Standalone binary probe via MCP stdio.<br>Option B: Host-specific capability negotiation endpoints with external probe attestation.<br>Option C: Linux containers only; desktop IDEs unconditionally E0. | **BLOCKED — AK DECISION REQUIRED** |
| **`CH8-OI-006`** | Area 3: Protected Path | In-repository customization policy for protected control-plane paths. | Option A: Immutable engine-level registry.<br>Option B: Baseline registry + `.sclass/protected_paths.json`.<br>Option C (Proposed Relaxation): Advisory warnings for config files, hard block for `.git/**` only. | **BLOCKED — AK DECISION REQUIRED** |
| **`P9-OI-001`** | Area 4: Diff Review | Diff inspection size thresholds (2 MiB limit) and handling of binary/vendored files. | Option A: Hard 2 MiB cutoff; larger diffs fail closed with `MISSING[PD-CH2-066]`.<br>Option B: Manifest-based exclusions for generated files.<br>Option C: Streaming chunk-based evaluation without size cutoff. | **BLOCKED — AK DECISION REQUIRED** |
| **`P4-OI-001`** | Area 5: Symbol Checks | Authoritative symbol indexing engine and multi-language index qualification in v1. | Option A: Tree-sitter multi-language parser under F10.<br>Option B: Python-only symbol checks in v1.<br>Option C: Defer symbol checks to post-v1; file-level units only. | **BLOCKED — AK DECISION REQUIRED** |
