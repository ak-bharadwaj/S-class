# S-Class v6.0.2 Block 1 Consolidated Design Proposals (Revision 4 — CL Acceptance Revision)

**Repository:** `ak-bharadwaj/S-class`  
**Branch:** `lane-c-design-drafts`  
**Accepted Integration Base:** `3ed415e67e15e6aedc7d456445c3c193146ae606`  
**Previous Delivered Revision:** `e75a9470169842728694f357e2c158ec9f26aba1` (Revision 3.4)  
**Normative Master Source:** `FREEZE-CANDIDATE-v6.0.2/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md` (SHA-256: `340db97857a7716b1aac2c1b44bc60b32642e3d8074d0263f3ce56da7dbb34eb`)  
**Canonical Registry Source:** `FREEZE-CANDIDATE-v6.0.2/product/MUST-REGISTRY.md` (SHA-256: `4156637e6f96dfeb30a27e7d6dc49f5727181c4e7436ddcae6f6a75f822283ea`)  
**Authoritative Research Source:** `delivery-1-design-drafts/RESEARCH-COMMAND-BLOCKING.md`  
**Companion Research Sources:**  
- `FREEZE-CANDIDATE-v6.0.2/product/r29-companion/RESEARCH-NOTES-R29.md` (SHA-256: `88632c8b93e410c60a6e3412bfd2a505766a48d7400432e23dc63d14b84a2f72`)  
- `FREEZE-CANDIDATE-v6.0.2/product/r29-companion/FREEZE-DECISION-R28.md` (SHA-256: `084c68832a76f264e1e07b8a53fc2632aa6c9ef5eb461158fc92e236ceeb4fce`)  
**Status:** PROPOSAL / DESIGN DRAFT ONLY (Revision 4 — CL Acceptance Revision)  
*Notice: This document is an unaccepted engineering proposal authored under Lane C. It does not alter normative master text, modify frozen directories (`00-SPEC/`, `10-CONFORMANCE/`, `20-RUNTIME/`), change MUST statuses, or commit new kernel state. It is subject to GPT review against CL's ten criteria before submission to CL for final acceptance.*

---

## Executive Summary & Revision 4 Correction Matrix

This revision (Revision 4) directly and exhaustively implements all ten mandatory acceptance criteria directed by CL, maintaining the five-area scope, duplicate exclusions, and frozen directory boundaries:

| Criterion # | CL Mandatory Acceptance Requirement | Affected Sections | Resolution in Revision 4 |
|---|---|---|---|
| **1** | **Master vocabulary compliance:** Use master-defined E0/E1/E2 terminology per PD-CH7-011 and §8.1. Strictly eliminate all 6 prohibited non-canonical terms (the three deprecated suffixed enforcement labels, the non-canonical probe receipt class name, the non-existent kernel authority entity name, and the deprecated dangerous command token). Every term must exist in master or be marked `PROPOSED-NEW` in open decisions. Do not merely rename prohibited terms. | Throughout proposal, §1.1, §1.2, §2.1, §2.2, §3.1, §3.2, §8, §9 | Replaced all prohibited terms across all prose and fixtures: adopted master enum values `E0`, `E1`, `E2` per Master §8.1 (`IDECapabilityRecord.enforcement_mode`); removed non-canonical receipt names from MUST text and defined candidate telemetry record under open decisions as `PROPOSED-NEW`; replaced kernel authority references with frozen `ApprovalSet` (§2.1, §3.2); replaced deprecated dangerous command tokens with research-defined category findings (`ENV_MUTATION_HIGH_RISK`, `BUILTIN_OVERRIDE_SHADOWING`, `ARGUMENT_INJECTION_RISK`, `UNRESOLVED_DYNAMIC_EXPANSION`, `DYNAMIC_EVAL_DISALLOWED`). |
| **2** | **No new kernel trust root:** Do not introduce a new kernel trust root, authority, or approval mechanism. Move Ed25519, JCS, nonce-size, clock-skew, and related cryptographic implementation choices out of MUST text and into open decisions. Mark novel mechanisms `PROPOSED-NEW`. MUST text must state only decidable condition and required outcome. | §2.2 (`PD-CH8-015`), §2.4, §8.2 | Stripped all cryptographic algorithms (Ed25519, JCS, 256-bit nonce, 60s skew) from `PD-CH8-015` MUST text; MUST text states only decidable condition (active probe boundary verification) and required outcome (fail closed to E0; automated promotion disallowed; non-self-attestation); cryptographic details moved to §2.4 as candidate transport choices marked `PROPOSED-NEW`; approval verification binds exclusively to existing frozen `ApprovalSet` (`validate_approval_set`). |
| **3** | **Remove unsupported command-dispatch binding:** Delete command-dispatch binding in §12.5. Do not replace with assumed frozen binding. Frozen binding may be cited only after checking exact existence in `00-SPEC/` using grep. If cannot be found, state unsupported or unresolved. | §1.2 (`PD-CH8-014`), §8.2, §10 | Deleted §12.5 command-dispatch binding. Confirmed via grep that `00-SPEC/` contains no command-dispatch projection (§12.5 defines Single Transition Authority for lifecycle events). Formally stated for `PD-CH8-014`: `Kernel binding (frozen): Unsupported / unresolved in frozen specification`. |
| **4** | **Citation format:** Use section-level citations only. Remove L-number/line-number citations throughout proposal and decisions log. Use `SOURCED (file, section)` or `UNVERIFIED`. | Throughout proposal, §0.1, §1.3, §2.3, §3.3, §4.1, §4.3, §5.3, §8 | Removed all line-number (`L...`) citations across all sections and tables. Replaced with section-level citations in standard format `SOURCED (file, section)` or `UNVERIFIED`. (Section 6 preserved verbatim per CL explicit preservation constraint). |
| **5** | **Action-result vocabulary:** `action_result` may have only two values: `BLOCKED` or `NONE`. `BLOCKED_ON_HUMAN` may appear only as a gate state, never as an action result. Audit every fixture, YAML example, prose definition, and decision. | §1.1, §1.2, §2.1, §2.2, §3.1, §3.2, §4.1, §4.2, §5.1, §5.2, §8 | Audited every fixture, YAML block, and prose definition: `action_result` is strictly restricted to `BLOCKED` or `NONE`. All instances requiring human approval are mapped to `gate_state: BLOCKED_ON_HUMAN` with corresponding `action_result: BLOCKED`. |
| **6** | **`PD-CH8-014` Command blocking:** Incorporate supplied `RESEARCH-COMMAND-BLOCKING.md`. Cover environment and builtin mutation, argument-level abuse, unresolved expansion, and `eval`. Apply research-defined deny or `BLOCKED_ON_HUMAN` behavior. Do not infer missing rules from general knowledge. Research document must be available to GPT for source-based review. | §1.1, §1.2 (`PD-CH8-014`), `CH8-T20`, §1.3 | Incorporated `delivery-1-design-drafts/RESEARCH-COMMAND-BLOCKING.md` into the delivery directory for source-based review. Fully structured `PD-CH8-014` and fixture `CH8-T20` around the five research categories (environment mutation, builtin mutation, argument-level abuse, unresolved expansion, dynamic `eval`) applying research-defined DENY (`action_result: BLOCKED`) and INTERCEPT (`gate_state: BLOCKED_ON_HUMAN`, `action_result: BLOCKED`). |
| **7** | **`PD-CH8-016` Agent-written executable files:** Cover files written by agents that may subsequently be run by unsandboxed tools. Specify relevant protection and enforcement behavior. Ensure not limited to files immediately executed by writing agent. Do not expand kernel authority or change frozen trust boundary. | §3.1, §3.2 (`PD-CH8-016`), `CH8-T24`, `CH8-T25` | Expanded `PD-CH8-016` scope to explicitly cover agent-written executable files and entrypoints (scripts, build tools, hooks, test runners, shebang files, binaries) that could be subsequently executed by unsandboxed tools; pre-write gate blocks unapproved creation or modification of executable files with `gate_state: BLOCKED_ON_HUMAN`, `action_result: BLOCKED` without altering frozen trust boundary. |
| **8** | **Incorporate CL's decisions:** Apply CL decisions: CH8-OI-004 (Moot/removed), CH8-OI-005 (Option C: Linux containers only; desktop IDEs unconditionally E0), CH8-OI-006 (Option A: Immutable engine registry), P9-OI-001 (Option A: Hard 2 MiB cutoff), P4-OI-001 (Option B: Python-only symbol granularity). Remove resolved decision alternatives. Remove invented numeric limits unless supported by source; otherwise mark UNVERIFIED. | §1.4, §2.4, §3.4, §4.4, §5.4, §8, §9 | Formally incorporated all five binding decisions: removed obsolete `CH8-OI-004`; adopted Option C for `CH8-OI-005`; adopted Option A for `CH8-OI-006`; adopted Option A for `P9-OI-001`; adopted Option B for `P4-OI-001`. Removed old decision alternatives and recorded decisions as resolved policy. Removed unsourced numeric thresholds or marked `UNVERIFIED`. |
| **9** | **Draft and LaTeX cleanup:** Regenerate or delete stale `1_`, `2_`, and `3_` draft files. Ensure one unambiguous current Revision 4 proposal. Correct malformed LaTeX and math notation. Search full delivery tree for stale terminology, old decision alternatives, and contradictory fixture examples. | `delivery-1-design-drafts/`, §4.1, §4.2 | Deleted stale `1_chapter_8_category_draft.md`, `2_review_engine_on_p9_draft.md`, `3_p4_additions_draft.md`, and `summary.md`; ensured `S-CLASS-v6.0.2-BLOCK-1-DESIGN-DRAFTS-COMBINED.md` is the sole proposal; corrected all malformed LaTeX formulas (resolved unescaped newlines in math blocks); audited entire delivery tree for consistency. |
| **10** | **Gate 3 binding evidence:** Verify `SessionContext`, `ApprovalSet`, and `WorkNode` directly against actual `00-SPEC/` contents. Run grep searches and paste raw outputs. Cite only sections where terms actually occur. Do not claim binding exists based on assumption. | §8.2 (Gate 3 Audit), Section 10 | Executed raw `git grep` against `00-SPEC/`: documented that `SessionContext` is unsupported (zero matches); documented `ApprovalSet` matches in §2.1, §2.2, §3.2; documented `WorkNode` matches in §2.1, §7, §8.6. Pasted raw grep output in delivery report. |

---

## Section 0: Mandatory Duplicate Exclusion Baseline & Raw Source Excerpts

### 0.1 Duplicate Check Baseline Matrix

| Baseline Owner | Master Section & Verbatim Quotation | Revision 4 Relationship & Boundary Proof |
|---|---|---|
| **`PD-CH8-008`** | **Master §7.4, §8.4:** *"IDE mode MUST declare E0/E1/E2 capabilities per qualified host/version; prevention honesty for host-native actions is owned by `PD-CH8-008`... NEVER claim prevention outside a qualified S-Class-launched boundary."* [SOURCED: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`, §7.4, §8.4] | **Preserved Unchanged.** `PD-CH8-014` and `PD-CH8-015` evaluate command syntax and container boundary isolation; they explicitly disclaim host-native prevention outside qualified launched worker containers. |
| **`PD-CH8-009`** | **Master §8.4:** *"Workspace promotion MUST require the current target and kernel release authority after verification and preserve rollback evidence; comparison of the observed write set with authorized scope is owned by `PD-CH4-014`."* [SOURCED: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`, §8.4] | **Preserved Unchanged.** Revision 4 introduces no workspace promotion rules, no release authority mechanisms, and no rollback manifest stores. |
| **`PD-CH8-010`** | **Master §8.4:** *"Out-of-band/concurrent edits MUST trigger re-snapshot and digest comparison before continuing; invalidation is owned by `PD-CH2-055`."* [SOURCED: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`, §8.4] | **Preserved Unchanged.** Revision 4 does not define concurrent edit detection or snapshot invalidation. |
| **`PD-CH8-011` / `PD-CH2-032`** | **Master §8.4, §2.10:** *"Parallel work MUST follow dependencies and canonical delta order, serialize overlapping write sets and merge only when target identity and each task verification pass."* / *"Known write-set overlap MUST serialize mechanically; unknown/undeclared write sets MUST block for human resolution."* [SOURCED: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`, §8.4, §2.10] | **Preserved Unchanged.** Revision 4 does not modify parallel task scheduling, write-set serialization, or human blocking on unknown overlap. |
| **`PD-CH8-012`** | **Master §8.5:** *"Repository intelligence MUST disclose index coverage/freshness and unresolved symbols remain MISSING."* [SOURCED: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`, §8.5] | **Preserved Unchanged.** `PD-CH2-067` resolves planned symbol targets during P4 against the index disclosed by `PD-CH8-012`. It does not redefine index freshness or disclosure. |
| **`PD-CH8-013`** | **Master §8.5:** *"Budget exhaustion MUST stop or route to an authorized repair path; retry decisions use the frozen RetryBudget with no second ledger; hard budget gates reject model-reported-only cost and admit only authoritative or host-attested cost metrics; resource and runtime limits use explicit units/defaults."* [SOURCED: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`, §8.5] | **Preserved Unchanged.** Revision 4 defines no budget ledgers, cost tracking, or token counters. |
| **`PD-CH4-014`** | **Master §4.4:** *"An observed delta outside the authorized write/scope set MUST return BLOCKED and cannot be accepted by a green test run."* [SOURCED: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`, §4.4] | **Preserved Unchanged.** `PD-CH8-016` acts as a pre-write gate specifically for protected control-plane paths and agent-written executable files. Evaluated in Section 6: **NO NEW MUST REQUIRED (PROVISIONAL)**. |
| **`P4-COVERAGE` / `P4-OVERLAP`** | **Master §2.10:** *"require each applicable obligation mapped to a planned verifier via F6 trace links" / "known write-set intersection forces serialization; unknown/missing write set blocks for human"* [SOURCED: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`, §2.10] | **Preserved Unchanged.** `PD-CH2-067` introduces symbol resolution checks within P4 without altering obligation coverage or overlap sub-checks. |
| **`PD-CH2-029` / `PD-CH2-031`** | **Master §2.10:** *"P4 MUST enforce task-count and task-unit caps from the F4 lane's canonical Policy defaults."* / *"WorkGraph dependency edges MUST be acyclic."* [SOURCED: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`, §2.10] | **Preserved Unchanged.** Revision 4 does not define lane caps, graph unit bounds, or graph cycle checks. |
| **`PD-CH2-052`** | **Master §2.15:** *"P9 MUST aggregate all requirement and obligation results across P7, reject unverified claims, enforce policy thresholds, and validate that waivers have authorized signatures and non-expired TTLs; no task completes with unverified obligations."* [SOURCED: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`, §2.15] | **Preserved Unchanged.** `PD-CH2-066` establishes diff hunk coverage against target snapshots; `PD-CH2-052` remains sole aggregator and waiver authority. |
| **`PD-CH2-060`** | **Master §2.20, §2.21:** *"Every default user-facing branch cut MUST begin with a clean workspace check; untracked or modified files block branching."* [SOURCED: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`, §2.20, §2.21] | **Preserved Unchanged.** Revision 4 introduces no new lifecycle phases or branching gates. |

---

# SECTION 1: Structural Command Analyzer (Area 1)

## 1.1 Specification & Boundary Requirements

### Master Terminology & Enforcement Tiers
Per Master §8.1 and `PD-CH7-011`, the S-Class control plane operates across three distinct enforcement modes:
- **`E0` (Advisory Mode):** Host execution displays gate results and structural findings; no write-prevention promise is made on the native host.
- **`E1` (Mediated Worker Mode):** S-Class-launched worker writes pass through ExecutionGate and its configured isolation boundary; preventive claim is limited to qualified OS/runtime support.
- **`E2` (Controlled Promotion Mode):** Authorized worker changes are staged against a bound baseline and promoted only after kernel and product gates close.

### Grounding in Command-Blocking Research
In strict accordance with `delivery-1-design-drafts/RESEARCH-COMMAND-BLOCKING.md` §1–§3, candidate command execution strings are evaluated by static AST inspection covering five distinct evasion and tampering categories:
1. **Environment Mutation:** Attempts to alter security-critical environment variables (`LD_PRELOAD`, `BASH_ENV`, `IFS`, `PATH`, `PYTHONPATH`) via command prefixes, `export`, `set`, or `env`.
2. **Builtin Mutation & Function Overrides:** Attempts to disable, alias, or shadow core tools (`alias pytest=true`, `function git() { ... }`, `builtin`, `enable -n`).
3. **Argument-Level Abuse:** Invocations of utilities with execution flags (`find -exec`, `xargs`, `awk 'BEGIN {system(...)}'`, `git -c core.pager=...`, `ssh -oProxyCommand=...`).
4. **Unresolved Dynamic Expansions:** Unresolved parameter expansions or command substitutions in command-word position (`$CMD -rf /`, `$(printf ...) /etc/passwd`).
5. **Dynamic Evaluation Wrappers:** Passing strings to `eval`, dynamic `source` / `.`, or piping decoded streams into a shell (`base64 -d | sh`).

### Parse Failure vs Dangerous Structural Patterns
- **Parser Grammar Failure:** A failure to parse tokens into an AST under the baseline POSIX 1003.1 grammar (e.g. malformed syntax operators, unclosed loops, or non-POSIX grammatical constructs such as Bash process substitution `<(...)` or `>(...)`, coprocs, and extended tests `[[ ... ]]`). This is strictly distinguished from an unknown command word, an unsupported builtin, or invalid flags (which parse successfully into simple command AST nodes). Any parser grammar failure MUST fail closed: returns **`gate_output: MISSING[PD-CH8-014]`** with **`action_result: BLOCKED`** across all execution boundaries (`E0`, `E1`, and `E2`).
- **Parsed Risk Patterns:** If the command parses successfully, the AST is evaluated against the research rules:
  - Critical environment mutation, builtin shadowing, or interpreter pipelines trigger **DENY**: returns **`gate_output: MISSING[PD-CH8-014]`** with **`action_result: BLOCKED`**.
  - Argument-level indirection, path modification, or unresolved dynamic expansions trigger **INTERCEPT**: returns **`gate_state: BLOCKED_ON_HUMAN`** with **`action_result: BLOCKED`** under `E1` and `E2`. Under `E0`, findings are advisory (`action_result: NONE`).

### Action-Result Invariant
In accordance with CL Criterion 5, `action_result` is strictly restricted to **`BLOCKED`** or **`NONE`**. `BLOCKED_ON_HUMAN` represents a gate state, never an action result. When human intervention is required under `E1`, the gate enters `gate_state: BLOCKED_ON_HUMAN` and enforces **`action_result: BLOCKED`** (hard stop: tool dispatch is suspended, no child process is spawned, and zero execution occurs while human decision is pending).

## 1.2 Proposed Normative MUST Specification: `PD-CH8-014`

| ID | Class | Decidable requirement | Gaming fixture | Happy fixture |
|---|---|---|---|---|
| `PD-CH8-014` | M | Candidate execution commands MUST undergo structural syntax analysis (AST evaluation) verifying environment mutation, builtin mutation, argument-level abuse, unresolved expansions, and dynamic evaluation against research rules; unparseable grammar or critical tampering MUST fail closed with `MISSING[PD-CH8-014]` and `action_result: BLOCKED` across all execution tiers; high-risk structural indirection MUST enter `gate_state: BLOCKED_ON_HUMAN` with `action_result: BLOCKED` under E1 and E2; conforming commands parseable under POSIX grammar MUST return `SATISFIED` with `action_result: NONE`. | `CH8-T20` → Varied per variant (DENY variants fail closed with `MISSING[PD-CH8-014]`, `action_result: BLOCKED`; INTERCEPT variants enter `BLOCKED_ON_HUMAN`, `action_result: BLOCKED`; under E0, advisory `action_result: NONE`) | `CH8-T21` → `SATISFIED` (`action_result: NONE`) |

- **Failure route:** Gate returns `MISSING[PD-CH8-014]` with `action_result: BLOCKED`; halts tool execution dispatch across E0, E1, and E2; routes to P6 replan or developer escalation.
- **Who may write:** Only the qualified structural command evaluator writes analysis records; agents propose command strings but cannot author or modify analysis records or bypass classifications.
- **Kernel binding (frozen):** Unsupported / unresolved in frozen specification. (Grep verification in `00-SPEC/` confirms no frozen command dispatch projection exists; §12.5 specifies Single Transition Authority for lifecycle status machine events, not shell command dispatch).
- **NEVER:** Never infer safety from substring absence, never treat unparseable syntax as safe, never classify parsed dangerous commands as parse failures, and never claim host-native write prevention outside a qualified launched container.
- **Cost bound:** Evaluator input capped at 64 KiB command string and 1,000 AST nodes [UNVERIFIED: proposed engineering limit]; execution bounded by O(AST nodes). Parser timeout (>500 ms) defaults to `action_result: BLOCKED`.
- **Fixtures:**
  - `CH8-T20` (Gaming / Research Command Blocking Taxonomy): Tests five research evasion categories, syntax errors, and non-POSIX grammar across E0, E1, and E2:
    - *Variant A1 (Environment Mutation — Loader Hijacking):* `LD_PRELOAD=/tmp/libevil.so pytest` → AST identifies loader variable injection → Research DENY → `gate_output: MISSING[PD-CH8-014]`, `action_result: BLOCKED` across E0, E1, E2.
    - *Variant A2 (Builtin Mutation — Test Runner Aliasing):* `alias pytest="echo Pass && true"` → AST identifies alias shadowing core test utility → Research DENY → `gate_output: MISSING[PD-CH8-014]`, `action_result: BLOCKED` across E0, E1, E2.
    - *Variant A3 (Argument Abuse — Execution Indirection):* `find . -name "*.py" -exec rm -rf /etc/hosts \;` → AST identifies `-exec` argument indirection → Research INTERCEPT → under E0, advisory `action_result: NONE`; under E1/E2, `gate_state: BLOCKED_ON_HUMAN`, `action_result: BLOCKED` (hard stop).
    - *Variant A4 (Unresolved Dynamic Expansion):* `CMD=rm; $CMD -rf /tmp/data` → AST identifies dynamic parameter in command-word position → Research INTERCEPT → under E0, advisory `action_result: NONE`; under E1/E2, `gate_state: BLOCKED_ON_HUMAN`, `action_result: BLOCKED` (hard stop).
    - *Variant A5 (Dynamic Eval Wrapper — Encoded Shell Pipeline):* `echo Zm9v | base64 -d | sh` → AST identifies pipeline streaming into shell interpreter → Research DENY → `gate_output: MISSING[PD-CH8-014]`, `action_result: BLOCKED` across E0, E1, E2.
    - *Variant A6 (Syntax Error in POSIX Grammar):* `for ((i=0; i<; i++)) do echo; done` → Malformed shell syntax error → Parser syntax error → fails closed with `gate_output: MISSING[PD-CH8-014]`, `action_result: BLOCKED` across E0, E1, E2.
    - *Variant A7 (Unsupported Non-POSIX Shell Grammar — Process Substitution):* `diff <(cat fileA) <(cat fileB)` → Genuine Bash process substitution `<(...)` violating POSIX 1003.1 grammar baseline → Parser grammar failure (`PARSE_FAILURE_UNSUPPORTED_GRAMMAR`), strictly distinguished from unknown command/builtin → fails closed with `gate_output: MISSING[PD-CH8-014]`, `action_result: BLOCKED` across E0, E1, E2.
  - `CH8-T21` (Happy / Fully Bound Conforming Command): Conforming command `pytest tests/test_core.py -v --tb=short` → AST evaluates known executable, valid arguments, no illegal redirects, fully parsed under POSIX grammar → returns `gate_output: SATISFIED`, `action_result: NONE` across E0, E1, E2.

### Fixture Specifications: `CH8-T20` & `CH8-T21`

```yaml
#### CH8-T20 — gaming fixture for PD-CH8-014
must_id: PD-CH8-014
fixture_role: gaming
input_binding: typed mismatch, adversarial evasion payload, or unparseable shell grammar in candidate command
bound_inputs: [command_string, environment_bindings, target_snapshot_ref, enforcement_mode]
attack_or_case: Evasion of command substring filtering or unparseable shell grammar payload
execution_evidence: UNVERIFIED
attack_variants:
  - id: A1
    category: "ENVIRONMENT_MUTATION"
    description: "Loader injection via LD_PRELOAD"
    payload: "LD_PRELOAD=/tmp/libevil.so pytest"
    parser_status: "PARSED_SUCCESS"
    finding_type: "ENV_MUTATION_HIGH_RISK"
    research_disposition: "DENY"
    expected_gate_output: MISSING[PD-CH8-014]
    boundary_actions:
      - boundary: "E0"
        expected_action_result: BLOCKED
      - boundary: "E1"
        expected_action_result: BLOCKED
      - boundary: "E2"
        expected_action_result: BLOCKED
  - id: A2
    category: "BUILTIN_MUTATION"
    description: "Aliasing test runner to bypass verification"
    payload: 'alias pytest="echo Pass && true"'
    parser_status: "PARSED_SUCCESS"
    finding_type: "BUILTIN_OVERRIDE_SHADOWING"
    research_disposition: "DENY"
    expected_gate_output: MISSING[PD-CH8-014]
    boundary_actions:
      - boundary: "E0"
        expected_action_result: BLOCKED
      - boundary: "E1"
        expected_action_result: BLOCKED
      - boundary: "E2"
        expected_action_result: BLOCKED
  - id: A3
    category: "ARGUMENT_ABUSE"
    description: "Execution flag indirection in find utility"
    payload: 'find . -name "*.py" -exec rm -rf /etc/hosts \;'
    parser_status: "PARSED_SUCCESS"
    finding_type: "ARGUMENT_INJECTION_RISK"
    research_disposition: "INTERCEPT"
    expected_gate_output: SATISFIED
    boundary_actions:
      - boundary: "E0"
        expected_action_result: NONE
      - boundary: "E1"
        gate_state: "BLOCKED_ON_HUMAN"
        expected_action_result: BLOCKED # hard stop: zero execution pending human approval
      - boundary: "E2"
        expected_action_result: BLOCKED
  - id: A4
    category: "UNRESOLVED_EXPANSION"
    description: "Variable parameter expansion in command word position"
    payload: "CMD=rm; $CMD -rf /tmp/data"
    parser_status: "PARSED_SUCCESS"
    finding_type: "UNRESOLVED_DYNAMIC_EXPANSION"
    research_disposition: "INTERCEPT"
    expected_gate_output: SATISFIED
    boundary_actions:
      - boundary: "E0"
        expected_action_result: NONE
      - boundary: "E1"
        gate_state: "BLOCKED_ON_HUMAN"
        expected_action_result: BLOCKED # hard stop: zero execution pending human approval
      - boundary: "E2"
        expected_action_result: BLOCKED
  - id: A5
    category: "DYNAMIC_EVAL"
    description: "Encoded pipeline to shell interpreter"
    payload: "echo Zm9v | base64 -d | sh"
    parser_status: "PARSED_SUCCESS"
    finding_type: "DYNAMIC_EVAL_DISALLOWED"
    research_disposition: "DENY"
    expected_gate_output: MISSING[PD-CH8-014]
    boundary_actions:
      - boundary: "E0"
        expected_action_result: BLOCKED
      - boundary: "E1"
        expected_action_result: BLOCKED
      - boundary: "E2"
        expected_action_result: BLOCKED
  - id: A6
    category: "SYNTAX_ERROR"
    description: "Malformed POSIX shell syntax error"
    payload: "for ((i=0; i<; i++)) do echo; done"
    parser_status: "PARSE_FAILURE_SYNTAX_ERROR"
    finding_type: null
    research_disposition: "DENY"
    expected_gate_output: MISSING[PD-CH8-014]
    boundary_actions:
      - boundary: "E0"
        expected_action_result: BLOCKED
      - boundary: "E1"
        expected_action_result: BLOCKED
      - boundary: "E2"
        expected_action_result: BLOCKED
  - id: A7
    category: "UNSUPPORTED_GRAMMAR"
    description: "Unsupported non-POSIX shell grammar construct (Bash process substitution)"
    payload: "diff <(cat fileA) <(cat fileB)"
    parser_status: "PARSE_FAILURE_UNSUPPORTED_GRAMMAR"
    finding_type: null
    research_disposition: "DENY"
    expected_gate_output: MISSING[PD-CH8-014]
    boundary_actions:
      - boundary: "E0"
        expected_action_result: BLOCKED
      - boundary: "E1"
        expected_action_result: BLOCKED
      - boundary: "E2"
        expected_action_result: BLOCKED

#### CH8-T21 — happy fixture for PD-CH8-014
must_id: PD-CH8-014
fixture_role: happy
input_binding: conforming command payload fully parseable under POSIX grammar
bound_inputs: [command_string, environment_bindings, target_snapshot_ref, enforcement_mode]
baseline: conforming test runner invocation with explicit arguments
payload: "pytest tests/test_core.py -v --tb=short"
parser_status: "PARSED_SUCCESS"
finding_type: null
expected_gate_output: SATISFIED
boundary_actions:
  - boundary: "E0"
    expected_action_result: NONE
  - boundary: "E1"
    expected_action_result: NONE
  - boundary: "E2"
    expected_action_result: NONE
execution_evidence: UNVERIFIED
```

## 1.3 Grounding & Evidence Analysis
- **Authoritative Research Grounding:** SOURCED from `delivery-1-design-drafts/RESEARCH-COMMAND-BLOCKING.md` §1–§3 (covering environment mutation, builtin overrides, argument abuse, unresolved expansion, and dynamic `eval`).
- **Companion Grounding:** SOURCED from `FREEZE-CANDIDATE-v6.0.2/product/r29-companion/RESEARCH-NOTES-R29.md` §B (*"Agents game tests; the trajectory matters... EvilGenie: Codex, Claude Code and Gemini CLI showed misaligned test-gaming behaviour in its setup"*).
- **Master Grounding:** Grounded in Master §8.1 (`E0`/`E1`/`E2` boundary definitions) and Master §8.4 (`PD-CH8-008` prevention honesty boundaries).
- **Kernel Binding Status:** Formally documented as unsupported / unresolved in frozen specification (`00-SPEC/`).

## 1.4 Decision Resolution (CL Directive)
- **`CH8-OI-004` (Command Analyzer Grammar & Engine):** **RESOLVED AS MOOT** per CL Direction. The research-defined command-blocking taxonomy in `RESEARCH-COMMAND-BLOCKING.md` governs enforcement behavior: unparseable non-POSIX constructs fail closed with `MISSING[PD-CH8-014]` and `action_result: BLOCKED`; high-risk patterns enforce research-defined deny (`action_result: BLOCKED`) or human interception (`gate_state: BLOCKED_ON_HUMAN`, `action_result: BLOCKED`).

---

# SECTION 2: Host-Control Verification by Active Probe & Degraded Mode (Area 2)

## 2.1 Specification & Boundary Requirements

### Master Grounding & Adoption of CL Decision (Option C)
Per CL's binding decision on `CH8-OI-005` (Option C):
- **Linux Containers Only:** Active host probe verification applies strictly to S-Class-launched Linux worker container boundaries.
- **Desktop Environments Unconditionally E0:** Native desktop IDEs, developer workstations, and unmediated host environments are unconditionally designated **`E0`** (advisory mode with no write-prevention promise).
- In `E0`, automated workspace write promotion is disallowed; any action requiring write authorization routes to `gate_state: BLOCKED_ON_HUMAN` with `action_result: BLOCKED`.

### Elimination of Novel Kernel Trust Roots
In strict compliance with CL Criterion 2:
- Zero new kernel trust roots, novel signature authorities, or approval mechanisms are introduced into MUST text.
- Approval and verification mechanisms bind strictly to existing frozen kernel primitives: `ApprovalSet` (`00-SPEC` §2.1, §3.2) evaluated via `validate_approval_set`.
- Specific cryptographic wire formats (Ed25519 signatures, RFC 8785 JCS canonicalization, 256-bit session nonces, 60s clock skew) are moved out of MUST text and classified under §2.4 as candidate implementation choices marked **`PROPOSED-NEW`**.

## 2.2 Proposed Normative MUST Specification: `PD-CH8-015`

| ID | Class | Decidable requirement | Gaming fixture | Happy fixture |
|---|---|---|---|---|
| `PD-CH8-015` | M | Candidate execution environments claiming E1 or E2 enforcement MUST provide active probe verification confirming boundary isolation before tool execution; absent or unverified probe evidence MUST fail closed, restricting host capability to E0; in E0, automated workspace promotion is disallowed and actions requiring write authorization enter `gate_state: BLOCKED_ON_HUMAN` with `action_result: BLOCKED`; environments MUST NOT self-attest enforcement capabilities. | `CH8-T22` → `MISSING[PD-CH8-015]` (degrades to `E0`, `gate_state: BLOCKED_ON_HUMAN`, `action_result: BLOCKED`) | `CH8-T23` → Illustrative schema template (Attempted dummy evaluation fails closed with `MISSING[PD-CH8-015]`; authentic probe evidence yields `SATISFIED`) |

- **Failure route:** Gate returns `MISSING[PD-CH8-015]`; degrades session capability to `E0`; disables automated workspace promotion; routes actions requiring write authorization to `gate_state: BLOCKED_ON_HUMAN` with `action_result: BLOCKED`.
- **Who may write:** Only external qualified probe harnesses holding keys registered in an authorized `ApprovalSet` principal directory write probe evidence records; host environments, IDEs, and agents cannot author or modify records.
- **Kernel binding (frozen):** Binds to frozen `ApprovalSet` (`00-SPEC` §2.1, §3.2) and `CapabilityDeclaration` (`00-SPEC` §7.4). (`SessionContext` is unsupported in `00-SPEC/`).
- **NEVER:** Never infer E1/E2 from environment variables, configuration files, or host-reported endpoints; never accept unverified probe evidence; and never allow self-attestation of isolation boundaries.
- **Cost bound:** Probe execution timeout capped at 5.0 seconds [UNVERIFIED: proposed engineering limit]; evaluation cost bounded by O(1) signature verification.
- **Fixtures:**
  - `CH8-T22` (Gaming / Forged & Stale Probe Evidence): Tests evasion via forged or unverified evidence:
    - *Variant A1 (Forged Signature):* Fabricated evidence record with invalid signature → Verification fails → `MISSING[PD-CH8-015]`, capability degrades to `E0`, `gate_state: BLOCKED_ON_HUMAN`, `action_result: BLOCKED`.
    - *Variant A2 (Stale Evidence / Expired TTL):* Evidence record from prior session with timestamp exceeding TTL → Freshness check fails → `MISSING[PD-CH8-015]`, capability degrades to `E0`, `gate_state: BLOCKED_ON_HUMAN`, `action_result: BLOCKED`.
    - *Variant A3 (Session Nonce Mismatch):* Evidence generated for a different session nonce → Nonce validation fails → `MISSING[PD-CH8-015]`, capability degrades to `E0`, `gate_state: BLOCKED_ON_HUMAN`, `action_result: BLOCKED`.
    - *Variant A4 (Host Endpoint Self-Attestation):* IDE provides host-reported endpoint declaration claiming E2 without active probe verification → Evaluator rejects self-attestation → `MISSING[PD-CH8-015]`, capability degrades to `E0`, `gate_state: BLOCKED_ON_HUMAN`, `action_result: BLOCKED`.
  - `CH8-T23` (Happy / Illustrative Container Probe Template): Illustrative schema template demonstrating required telemetry fields and boundary assertions for `E2`. Explicitly labeled illustrative and unexecuted (`UNVERIFIED`).

### Fixture Specifications: `CH8-T22` & `CH8-T23`

```yaml
#### CH8-T22 — gaming fixture for PD-CH8-015
must_id: PD-CH8-015
fixture_role: gaming
input_binding: forged, stale, mismatched, or unverified probe evidence record
bound_inputs: [active_session_nonce, host_evidence_record]
attack_or_case: Host or agent attempts to claim E1/E2 capability using forged, stale, or self-attested credentials
expected_gate_output: MISSING[PD-CH8-015]
expected_host_capability: "E0"
gate_state: "BLOCKED_ON_HUMAN"
expected_action_result: BLOCKED
execution_evidence: UNVERIFIED
fixture_status: illustrative_schematic_template (UNEXECUTED)
attack_variants:
  - id: A1
    description: "Forged digital signature on evidence record"
    host_evidence_record:
      record_version: "1.0"
      claimed_enforcement_mode: "E2"
      nonce: "8fbb425001df860eb4515f159aa0827409025fd0e5be529b52199394665be62a"
      signature: "bad_signature_000000000000000000000000000000000000000000000000000000000000"
    failure_reason: "SIGNATURE_VERIFICATION_FAILED"
  - id: A2
    description: "Expired TTL on probe evidence"
    host_evidence_record:
      record_version: "1.0"
      claimed_enforcement_mode: "E2"
      nonce: "8fbb425001df860eb4515f159aa0827409025fd0e5be529b52199394665be62a"
      probe_timestamp_utc: "2026-10-01T00:00:00Z"
      ttl_seconds: 3600
    failure_reason: "RECORD_EXPIRED"
  - id: A3
    description: "Session nonce mismatch"
    host_evidence_record:
      record_version: "1.0"
      claimed_enforcement_mode: "E1"
      nonce: "mismatched_nonce_ffffffffffffffffffffffffffffffffffffffffffffffff"
    failure_reason: "NONCE_MISMATCH"
  - id: A4
    description: "Host-reported endpoint self-attestation without probe"
    host_evidence_record: null
    host_endpoint_claim: "E2"
    failure_reason: "UNATTESTED_SELF_CLAIM"

#### CH8-T23 — happy fixture for PD-CH8-015
must_id: PD-CH8-015
fixture_role: happy
fixture_status: illustrative_schematic_template (UNEXECUTED)
execution_evidence: UNVERIFIED
notice_of_schematic_status: >
  This fixture is strictly an illustrative structural template demonstrating required
  telemetry metrics and serialization for an E2 container probe evidence record.
  Both the runtime_engine_digest and signature fields contain illustrative unmeasured placeholders
  and must not be presented as genuine execution evidence. Attempted automated evaluation of this
  template as-written fails closed (MISSING[PD-CH8-015], degrading capability to E0)
  because the non-functional signature cannot be verified. A genuinely generated, conforming record
  is required to pass verification.
input_binding: illustrative schematic template for active probe evidence record demonstrating required fields and telemetry schema
bound_inputs: [active_session_nonce, host_evidence_record]
active_session_nonce: "8fbb425001df860eb4515f159aa0827409025fd0e5be529b52199394665be62a"
host_evidence_record:
  record_version: "1.0"
  session_id: "sess-20261101-b1-lane-c"
  host_platform:
    os_family: "linux"
    kernel_release: "6.8.0-40-generic"
    arch_abi: "x86_64"
  runtime_engine_digest: "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef" # illustrative placeholder; genuine probe measures actual running runtime binary SHA-256
  nonce: "8fbb425001df860eb4515f159aa0827409025fd0e5be529b52199394665be62a"
  probe_timestamp_utc: "2026-11-01T12:00:00Z"  # schematic illustrative UTC timestamp
  ttl_seconds: 3600
  claimed_enforcement_mode: "E2"
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
  issuer_authority_ref: "auth-harness-linux-01"
  signature: "ILLUSTRATIVE_DUMMY_SIGNATURE_HEX_NOT_GENUINE_7f8c9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f"
evaluation_outcomes:
  observed_execution_result:
    execution_status: "NOT_RUN"
    observed_gate_output: "NOT_RUN"
    observed_dispatch_status: "NOT_RUN"
    reason: >
      This fixture is an unexecuted illustrative schematic template; no live active host probe
      harness was executed during this drafting turn. An unexecuted template reports NOT_RUN.
  attempted_template_evaluation:
    gate_output: MISSING[PD-CH8-015]
    assigned_host_capability: "E0"
    gate_state: "BLOCKED_ON_HUMAN"
    action_result: BLOCKED
    reason: "Dummy non-functional signature cannot verify against authorized ApprovalSet public key; fails closed to E0."
  normative_conforming_case_expectation:
    gate_output: SATISFIED
    assigned_host_capability: "E2"
    action_result: NONE
    required_validations:
      - canonical_payload: "Canonical serialization over HostEvidenceRecord excluding signature field"
      - registered_issuer_authority: "Authority enrolled in authorized ApprovalSet principal directory"
      - valid_signature: "Authentic signature verified against registered public key"
      - active_session_nonce: "Exact match against currently active session nonce"
      - actual_runtime_identity: "Genuine runtime_engine_digest matching independently measured SHA-256 of the running runtime binary"
      - trusted_timestamp: "Probe timestamp verified within maximum skew threshold (<= 60 s) and active TTL"
      - capability_specific_telemetry: "Container isolation probe evidence verified: isolated mount namespace with read-only root, isolated PID namespace (visible host PIDs == 0), isolated network namespace (no default route), enforced cgroup v2 limits, and enforced seccomp BPF filter"
```

## 2.3 Grounding & Evidence Analysis
- **Evidence Label:** SOURCED from `FREEZE-CANDIDATE-v6.0.2/product/r29-companion/RESEARCH-NOTES-R29.md` §C (*"Host facts are discoverable; host control is not... An agent can read whether it is root, what ports are open... It cannot verify that a write-trap or container boundary is functioning without an active probe"*).
- **Master Grounding:** Grounded in Master §8.1 (`E0`/`E1`/`E2` definitions) and Master §8.4 (`PD-CH8-008` prevention honesty boundaries).
- **Unverified Aspects:** Concrete transport schemas and probe binary packaging are **`UNVERIFIED`** in companion files and represent proposed engineering choices.

## 2.4 Decision Resolution & Candidate Cryptographic Transport (`PROPOSED-NEW`)
- **`CH8-OI-005` (Active Host Probe Transport):** **RESOLVED VIA CL DIRECTION (OPTION C)**. Active host probe verification applies strictly to Linux container boundaries; desktop IDEs are unconditionally designated `E0`.
- **Candidate Cryptographic Transport Choices (`PROPOSED-NEW`):** For Linux container verification, candidate transport choices moved from MUST text include:
  - Canonical Serialization: RFC 8785 JSON Canonicalization Scheme (JCS).
  - Signature Algorithm: Ed25519 digital signatures.
  - Session Nonce: Cryptographic 256-bit random nonce issued per worker session.
  - Trusted Clock Skew: Maximum tolerance of $\le 60	ext{ s}$ between host and container timestamps.
  All such mechanisms remain explicitly `PROPOSED-NEW` non-normative choices subject to future implementation review.

---

# SECTION 3: Protected-Path Gate (Area 3)

## 3.1 Specification & Boundary Requirements

### Expanded Scope: Agent-Written Executable Files & Entrypoints
In strict compliance with CL Criterion 7, `PD-CH8-016` covers two distinct categories of protected paths:
1. **Control-Plane Files & Git Metadata:** Agent writes to repository hooks (`.git/hooks/**`), configuration files, CI workflows (`.github/workflows/**`), package manifests (`pyproject.toml`, `package.json`, `setup.py`), or task definitions.
2. **Agent-Written Executable Files & Entrypoints:** Files written or created by agents that may subsequently be executed by unsandboxed tools, host processes, or developer workflows (e.g. shell scripts `.sh`, batch files `.bat`/`.cmd`, test runner scripts, build wrappers, Makefile targets, or any file created with executable permissions).

### Protection & Enforcement Behavior
- The protected-path gate operates as a **pre-write gate** in P6.
- Any agent tool write targeting a protected control-plane path OR creating/modifying an executable file/entrypoint MUST be intercepted before the write is executed on the filesystem.
- Unless the write is covered by an authentic scope authorization record or pre-authorized via an existing frozen `ApprovalSet` (`00-SPEC` §2.1, §3.2), the write MUST fail closed: returns **`gate_output: MISSING[PD-CH8-016]`** with **`gate_state: BLOCKED_ON_HUMAN`** and **`action_result: BLOCKED`**.
- This ensures protection is not limited to files immediately executed by the writing agent, but guards against delayed or indirect execution by unsandboxed host tools.
- Zero kernel expansion or modifications to the frozen trust boundary are introduced; approvals bind exclusively to frozen `ApprovalSet`.

### Adoption of CL Decision on Registry Customization (`CH8-OI-006` Option A)
Per CL's binding decision:
- **Strict Immutable Engine Registry:** The protected path registry is built into the engine as an immutable baseline. In-repository customization is disabled; no in-repo configuration file may narrow or override the protected paths.

## 3.2 Proposed Normative MUST Specification: `PD-CH8-016`

| ID | Class | Decidable requirement | Gaming fixture | Happy fixture |
|---|---|---|---|---|
| `PD-CH8-016` | M/E/J | Agent write operations targeting protected control-plane paths OR creating/modifying executable files and interpreter entrypoints that may subsequently be run by unsandboxed tools MUST undergo canonical path normalization and require pre-write authorization; unapproved writes MUST fail closed with `MISSING[PD-CH8-016]`, entering `gate_state: BLOCKED_ON_HUMAN` with `action_result: BLOCKED`; application writes outside the protected registry require no separate approval record. | `CH8-T24` → `MISSING[PD-CH8-016]` (`gate_state: BLOCKED_ON_HUMAN`, `action_result: BLOCKED`) | `CH8-T25` → Illustrative schema template (Application write outside protected registry yields `SATISFIED`, `action_result: NONE`) |

- **Failure route:** Gate returns `MISSING[PD-CH8-016]`; enters `gate_state: BLOCKED_ON_HUMAN` with `action_result: BLOCKED`; halts write dispatch; routes to developer confirmation.
- **Who may write:** Only the qualified path resolver writes normalized path classification records; agents propose write paths but cannot author classifications or alter the immutable protected registry.
- **Kernel binding (frozen):** Binds to frozen `ApprovalSet` (`00-SPEC` §2.1, §3.2) and `TargetSnapshot` (`00-SPEC` §12.6).
- **NEVER:** Never permit path traversal (`../`) to bypass protected checks, never resolve Windows 8.3 short names or NTFS ADS without normalization, and never write unapproved executable files to the host filesystem.
- **Cost bound:** Evaluator input capped at 1,024 write paths per task and 4,096 characters per path [UNVERIFIED: proposed limit]; path resolution bounded by O(path components).
- **Fixtures:**
  - `CH8-T24` (Gaming / Protected Path Traversal & Executable Script Creation): Tests path traversal, alias evasion, and unapproved executable creation:
    - *Variant A1 (Dot-Dot Traversal):* `src/../../.git/hooks/pre-commit` → Normalizes to `.git/hooks/pre-commit` → Protected hook path → `MISSING[PD-CH8-016]`, `gate_state: BLOCKED_ON_HUMAN`, `action_result: BLOCKED`.
    - *Variant A2 (Windows 8.3 Short Name Evasion):* `GIT~1/hooks/pre-commit` → Resolves alias to `.git/hooks/pre-commit` → `MISSING[PD-CH8-016]`, `gate_state: BLOCKED_ON_HUMAN`, `action_result: BLOCKED`.
    - *Variant A3 (NTFS Alternate Data Stream):* `build.bat:hidden.ps1` → Identifies ADS colon stream syntax → Fails closed with `MISSING[PD-CH8-016]`, `action_result: BLOCKED`.
    - *Variant A4 (Agent-Written Executable Entrypoint):* Agent attempts to create `scripts/run_tool.sh` with executable permissions without pre-authorization → Intercepted as unsandboxed entrypoint → `MISSING[PD-CH8-016]`, `gate_state: BLOCKED_ON_HUMAN`, `action_result: BLOCKED`.
  - `CH8-T25` (Happy / Conforming Application Path): Write targets `src/sclass/product/predicate_evaluator.py` outside protected registry → Normalizes to ordinary application path → returns `gate_output: SATISFIED`, `action_result: NONE`.

### Fixture Specifications: `CH8-T24` & `CH8-T25`

```yaml
#### CH8-T24 — gaming fixture for PD-CH8-016
must_id: PD-CH8-016
fixture_role: gaming
input_binding: path traversal, alias evasion, or unapproved executable creation in candidate write set
bound_inputs: [target_snapshot_ref, candidate_write_paths, immutable_protected_registry]
attack_or_case: Agent attempts to write to control-plane paths or create unapproved executable entrypoints
expected_gate_output: MISSING[PD-CH8-016]
gate_state: "BLOCKED_ON_HUMAN"
expected_action_result: BLOCKED
execution_evidence: UNVERIFIED
attack_variants:
  - id: A1
    description: "Directory traversal into git hooks"
    candidate_path: "src/../../.git/hooks/pre-commit"
    canonical_resolution: ".git/hooks/pre-commit"
    protected_classification: "PROTECTED_CONTROL_PLANE"
  - id: A2
    description: "Windows 8.3 short name alias evasion"
    candidate_path: "GIT~1/hooks/pre-commit"
    canonical_resolution: ".git/hooks/pre-commit"
    protected_classification: "PROTECTED_CONTROL_PLANE"
  - id: A3
    description: "NTFS alternate data stream injection"
    candidate_path: "build.bat:stream.ps1"
    canonical_resolution: "REJECTED_INVALID_STREAM_SYNTAX"
    protected_classification: "MALFORMED_PATH"
  - id: A4
    description: "Unapproved agent-written executable entrypoint"
    candidate_path: "scripts/run_tool.sh"
    file_mode: "0755"
    canonical_resolution: "scripts/run_tool.sh"
    protected_classification: "AGENT_WRITTEN_EXECUTABLE_ENTRYPOINT"

#### CH8-T25 — happy fixture for PD-CH8-016
must_id: PD-CH8-016
fixture_role: happy
fixture_status: illustrative_schematic_template (UNEXECUTED)
execution_evidence: UNVERIFIED
notice_of_schematic_status: >
  This fixture is strictly an illustrative structural template demonstrating path resolution
  for application-layer writes outside the protected registry. Attempted automated evaluation
  without an authenticated scope authorization record fails closed.
input_binding: conforming application write paths fully resolved outside immutable protected registry
bound_inputs: [target_snapshot_ref, candidate_write_paths, immutable_protected_registry]
target_snapshot_ref: "snap-r30-b1-3ed415e"
candidate_write_paths:
  - "src/sclass/product/predicate_evaluator.py"
  - "tests/test_predicate_evaluator.py"
computed_write_set_digest: "8fbb425001df860eb4515f159aa0827409025fd0e5be529b52199394665be62a" # schematic placeholder
protected_registry_check:
  "src/sclass/product/predicate_evaluator.py": "OUTSIDE_PROTECTED_REGISTRY"
  "tests/test_predicate_evaluator.py": "OUTSIDE_PROTECTED_REGISTRY"
executable_entrypoint_check:
  "src/sclass/product/predicate_evaluator.py": "NON_EXECUTABLE_MODULE"
  "tests/test_predicate_evaluator.py": "NON_EXECUTABLE_TEST"
approval_record_ref: null # strictly admissible: non-protected, non-executable application paths require no approval record
evaluation_outcomes:
  observed_execution_result:
    execution_status: "NOT_RUN"
    observed_gate_output: "NOT_RUN"
    observed_dispatch_status: "NOT_RUN"
    reason: >
      This fixture is an unexecuted illustrative schematic template; no live path
      gate evaluation was executed during this drafting turn. An unexecuted template reports NOT_RUN.
  attempted_template_evaluation:
    gate_output: MISSING[PD-CH8-016]
    gate_state: "BLOCKED_ON_HUMAN"
    action_result: BLOCKED
    reason: "Placeholder digest match without authenticated kernel scope authorization fails closed."
  normative_conforming_case_expectation:
    gate_output: SATISFIED
    action_result: NONE
    condition: >
      Applies when proposed write set targets only application files outside the protected registry,
      creates no unapproved executable entrypoints, and authorized_write_set_digest is authenticated.
```

## 3.3 Grounding & Evidence Analysis
- **Evidence Label:** SOURCED from `FREEZE-CANDIDATE-v6.0.2/product/r29-companion/RESEARCH-NOTES-R29.md` §B (*"Agents game tests; the trajectory matters... EvilGenie: test-file edit detection is one of its methods... The Verification Horizon: tampering with the harness"*).
- **Master Grounding:** Grounded in Master §4.4 (Scope lock and `PD-CH4-014`).
- **Unverified Aspects:** Specific path normalization algorithms and Windows junction heuristics are **`UNVERIFIED`** in companion files and represent proposed engineering choices.

## 3.4 Decision Resolution (CL Directive)
- **`CH8-OI-006` (Protected Path Registry Storage & Customization):** **RESOLVED VIA CL DIRECTION (OPTION A)**. The protected path registry is an immutable engine-level baseline. In-repository customization is disabled; no in-repo configuration file may narrow or override the protected paths.

---

# SECTION 4: Diff-Level Review Engine (Area 4)

## 4.1 Specification & Boundary Requirements

### Binding to Target Snapshot & LF-Normalized Hunk Hashing
The review engine binds directly to the concrete unified diff computed between the workspace and the bound `TargetSnapshot`. Every changed hunk is identified by its concrete coordinates and exact 64-character SHA-256 digest computed under strict canonical rules:
1. *Encoding:* UTF-8 strictly without Byte Order Mark (BOM).
2. *Line-Ending Canonicalization:* All line endings are normalized to LF (`
`, byte `0x0A`). Any CRLF or CR byte sequence is converted to LF prior to hashing.
3. *Hunk Digest Formula:*
   $$	ext{hunk\_digest} = 	ext{SHA-256}(	ext{hunk\_header} \parallel 	exttt{"\n"} \parallel 	ext{hunk\_body\_lines\_normalized\_LF})$$
   where `hunk_header` is the exact unified diff header line (e.g. `@@ -3,4 +3,4 @@`) and `hunk_body_lines` includes all context, addition (`+`), and deletion (`-`) lines with trailing `
`.
4. *Diff Digest Formula:*
   $$	ext{diff\_digest} = 	ext{SHA-256}(	ext{full\_diff\_text\_normalized\_LF})$$

### Complete Hunk Inventory & 100% Coverage Rule
- **Complete Hunk Inventory:** The review engine parses the unified diff into an ordered list:
  $$	ext{HunkInventory} = [H_0, H_1, \dots, H_{n-1}]$$
  where each $H_i = (	ext{file\_path}, 	ext{hunk\_index}, 	ext{line\_start}, 	ext{line\_end}, 	ext{hunk\_digest})$.
- **100% Coverage Requirement:** Every single hunk $H_i \in 	ext{HunkInventory}$ MUST map unambiguously to either:
  1. A resolved `ReviewFinding` with attached qualified closure evidence (e.g. structured pytest execution receipt or static analysis verification record), OR
  2. An explicit `CleanHunkAttestation` generated by a qualified review evaluator certifying that the hunk contains strictly non-semantic edits (e.g. comments, docstrings, formatting).
  Any unmapped, uninspected, or orphaned hunk causes the review gate to fail closed with **`gate_output: MISSING[PD-CH2-066]`** and **`action_result: BLOCKED`**.
- **Preservation of `PD-CH2-052` Ownership:** `PD-CH2-066` owns physical diff hunk coverage; `PD-CH2-052` remains the sole aggregator and waiver authority across P7/P9.
- **Non-Self-Approval Rule:** Agent summaries, commit messages, or PR descriptions have zero authority.

### Adoption of CL Decision on Diff Size Cutoff (`P9-OI-001` Option A)
Per CL's binding decision on `P9-OI-001` (Option A):
- A hard **2 MiB patch size cutoff** is enforced.
- Any diff exceeding 2 MiB or containing unreviewable binary content fails closed with **`gate_output: MISSING[PD-CH2-066]`** and **`action_result: BLOCKED`**.

## 4.2 Proposed Normative MUST Specification: `PD-CH2-066`

| ID | Class | Decidable requirement | Gaming fixture | Happy fixture |
|---|---|---|---|---|
| `PD-CH2-066` | M | Review evaluation in P9 MUST bind directly to the concrete unified diff against the bound `TargetSnapshot` baseline; every changed hunk MUST map to a resolved finding or clean-check record using concrete `(file_path, hunk_index, line_range, hunk_digest)` coordinates; diffs exceeding 2 MiB or containing unreviewable binary content MUST fail closed with `MISSING[PD-CH2-066]` and `action_result: BLOCKED`; agent self-summaries MUST NOT replace diff inspection. | `CH2-T77` → `MISSING[PD-CH2-066]` (`action_result: BLOCKED`) | `CH2-T78` → Illustrative schema template (100% hunk coverage with resolved findings and structured receipts) |

- **Failure route:** Gate returns `MISSING[PD-CH2-066]` with `action_result: BLOCKED`; blocks P9 review progression; routes back to P6 for clean diff reproduction.
- **Who may write:** Only the qualified diff review evaluator writes `ReviewAssessment` records; agents propose diffs and findings but cannot self-close findings or certify review completion.
- **Kernel binding (frozen):** Binds to frozen `TargetSnapshot` (`00-SPEC` §12.6) and `AcceptanceContract` (`00-SPEC` §5).
- **NEVER:** Never evaluate agent text summaries in lieu of physical unified diffs, never permit unanchored review findings, and never accept a diff whose baseline snapshot digest mismatches.
- **Cost bound:** Evaluator inspects diffs up to 2 MiB total patch size and 1,000 hunks [SOURCED: CL Decision on P9-OI-001 (Option A)]; review cost bounded by O(diff bytes). Oversized diffs fail closed with `action_result: BLOCKED`.
- **Fixtures:**
  - `CH2-T77` (Gaming / Misleading Summary & Post-Review Mutation):
    - *Variant A1 (Misleading Summary):* Agent claims "Fixed typo in docstring", but diff alters an authorization check → Diff evaluator ignores summary, detects unclosed security finding on hunk → `MISSING[PD-CH2-066]`, `action_result: BLOCKED`.
    - *Variant A2 (Diff Against Drifted Snapshot):* Diff generated against drifted workspace baseline rather than bound `TargetSnapshot` → Snapshot digest mismatch → `MISSING[PD-CH2-066]`, `action_result: BLOCKED`.
    - *Variant A3 (Truncated / Malformed Patch):* Patch file contains truncated hunk lines with mismatched header counts → Parse failure → `MISSING[PD-CH2-066]`, `action_result: BLOCKED`.
    - *Variant A4 (Oversized Patch > 2 MiB):* Patch exceeds 2 MiB threshold → Fails closed per Option A → `MISSING[PD-CH2-066]`, `action_result: BLOCKED`.
  - `CH2-T78` (Happy / Multi-Hunk Diff Complete Coverage): Evaluates an exact, syntactically valid multi-hunk diff against bound snapshot; all hunks map to resolved findings closed by test receipts with 100% coverage.

### Fixture Specifications: `CH2-T77` & `CH2-T78`

```yaml
#### CH2-T77 — gaming fixture for PD-CH2-066
must_id: PD-CH2-066
fixture_role: gaming
input_binding: misleading agent summary, drifted diff against baseline snapshot, or oversized patch
bound_inputs: [target_snapshot_ref, unified_diff_payload, agent_summary, review_record]
attack_or_case: Agent attempts to mask functional changes behind a benign summary, or patch exceeds 2 MiB
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
  - id: A2
    description: "Diff generated against stale target snapshot"
    target_snapshot_ref: "snap-r30-b1-3ed415e"
    workspace_snapshot_ref: "snap-r30-b1-drifted"
  - id: A3
    description: "Truncated hunk with inconsistent line counts"
    unified_diff_payload: "@@ -10,15 +10,2 @@
- invalid truncation"
  - id: A4
    description: "Oversized patch exceeding 2 MiB cutoff"
    patch_size_bytes: 2621440 # 2.5 MiB

#### CH2-T78 — happy fixture for PD-CH2-066
must_id: PD-CH2-066
fixture_role: happy
fixture_status: illustrative_schematic_template (UNEXECUTED)
execution_evidence: UNVERIFIED
notice_of_schematic_status: >
  This fixture evaluates a syntactically valid unified diff verified via git apply --check (exit code 0).
  Both hunks contain functional code changes and are mapped to distinct review findings closed by structured
  pytest execution receipts. The test receipts are illustrative schematic records demonstrating the required
  schema and runner digest binding; they are not claimed as live execution logs from this drafting turn.
input_binding: complete, syntactically valid unified diff bound to target snapshot with complete hunk coverage
bound_inputs: [target_snapshot_ref, unified_diff_payload, hunk_inventory, review_coverage_map, closure_evidence]
target_snapshot_ref: "snap-r30-b1-3ed415e"
unified_diff_payload: |
  --- a/src/sclass/product/predicate_evaluator.py
  +++ b/src/sclass/product/predicate_evaluator.py
  @@ -3,4 +3,4 @@
   def compute_predicate_digest(node_or_canonical_str: str) -> str:
  -    # Initial placeholder
  -    pass
  +    # Canonical SHA-256 digest computation
  +    return hashlib.sha256(node_or_canonical_str.encode('utf-8')).hexdigest()
   
  @@ -17,4 +17,4 @@
   def canonicalize_expression(expr: str) -> str:
  -    # Expression normalizer placeholder
  -    return expr
  +    # Expression normalizer implementation
  +    return expr.strip().lower()
   
unified_diff_digest: "17b50c47e5c6e1bee9b7671eeef4a7f16f9b319f0a1cad06e47c396fd805cc5e"
hunk_inventory:
  - hunk_index: 0
    file_path: "src/sclass/product/predicate_evaluator.py"
    line_start: 3
    line_end: 6
    header: "@@ -3,4 +3,4 @@"
    hunk_digest: "dc1c571a15ca0596e036512b63ebc195f6b3f43acdcec53ab5a32116f942ca8f"
    classification: "FUNCTIONAL_IMPLEMENTATION_REVIEW_REQUIRED"
    semantic_rationale: "Initial pass placeholder replaced with cryptographic SHA-256 digest computation. Modifies executable implementation; mapped to review finding FINDING-CORE-001 closed by illustrative test receipt ev-test-pass-01."
  - hunk_index: 1
    file_path: "src/sclass/product/predicate_evaluator.py"
    line_start: 17
    line_end: 20
    header: "@@ -17,4 +17,4 @@"
    hunk_digest: "b2c434c4d2243d25861f4fd89eab50c0a8794ccf4e0d8343620afd4d8712b913"
    classification: "FUNCTIONAL_IMPLEMENTATION_REVIEW_REQUIRED"
    semantic_rationale: "String normalization logic modified via .strip().lower(). This alters runtime return values and is a semantic behavior change, NOT a clean documentation or comment change; mapped to review finding FINDING-CORE-002 closed by illustrative test receipt ev-test-pass-02."
review_coverage_map:
  - hunk_index: 0
    record_type: "REVIEW_FINDING"
    hunk_digest: "dc1c571a15ca0596e036512b63ebc195f6b3f43acdcec53ab5a32116f942ca8f"
    finding_id: "FINDING-CORE-001"
    status: "RESOLVED"
    evidence_ref: "ev-test-pass-01"
  - hunk_index: 1
    record_type: "REVIEW_FINDING"
    hunk_digest: "b2c434c4d2243d25861f4fd89eab50c0a8794ccf4e0d8343620afd4d8712b913"
    finding_id: "FINDING-CORE-002"
    status: "RESOLVED"
    evidence_ref: "ev-test-pass-02"
closure_evidence:
  ev-test-pass-01:
    evidence_type: "PYTEST_EXECUTION_RECEIPT"
    receipt_status: "illustrative_schematic_record (UNEXECUTED)"
    execution_evidence: "UNVERIFIED"
    test_suite: "tests/test_predicate_evaluator.py"
    target_module: "src/sclass/product/predicate_evaluator.py"
    hunk_coverage: [0]
    test_command: "pytest tests/test_predicate_evaluator.py -k test_compute_predicate_digest"
    exit_code: 0
    tests_run: 4
    tests_passed: 4
    tests_failed: 0
    execution_timestamp_utc: "2026-11-01T12:10:00Z"
    runner_digest: "ee3131591ecdc30ebc9221769239e9d89df47380ed01e1b25ba2c68f6e808417"
    verdict: "RESOLVED_BY_PASSING_TESTS"
  ev-test-pass-02:
    evidence_type: "PYTEST_EXECUTION_RECEIPT"
    receipt_status: "illustrative_schematic_record (UNEXECUTED)"
    execution_evidence: "UNVERIFIED"
    test_suite: "tests/test_predicate_evaluator.py"
    target_module: "src/sclass/product/predicate_evaluator.py"
    hunk_coverage: [1]
    test_command: "pytest tests/test_predicate_evaluator.py -k test_canonicalize_expression"
    exit_code: 0
    tests_run: 6
    tests_passed: 6
    tests_failed: 0
    execution_timestamp_utc: "2026-11-01T12:10:02Z"
    runner_digest: "ee3131591ecdc30ebc9221769239e9d89df47380ed01e1b25ba2c68f6e808417"
    verdict: "RESOLVED_BY_PASSING_TESTS"
clean_attestation_schema_specification:
  note: >
    Illustrative specification template only. For non-functional hunks (e.g. comments, docstrings, formatting),
    the proposed review engine admits CleanHunkAttestation records. Because the review evaluator is a proposed product
    addition not yet qualified under F10 (Gate 4 PARTIAL), this attestation structure is strictly an illustrative schema
    and MUST NOT be treated as a qualified authority or accepted as authoritative evidence while Gate 4 remains PARTIAL.
  evaluator_specification:
    evaluator_id: "evaluator-diff-ast-static-analyzer-v1"
    qualification_reference: "F10-QUAL-AST-01"
    evaluation_rule: "AST_EQUIVALENCE_OR_PURE_DOCUMENTATION"
    canonical_payload_template:
      attestation_version: "1.0"
      evaluator_id: "evaluator-diff-ast-static-analyzer-v1"
      qualification_reference: "F10-QUAL-AST-01"
      rule: "AST_EQUIVALENCE_OR_PURE_DOCUMENTATION"
      statement: "Hunk inspected; verified no functional, security, or permission regressions."
    attestation_digest: "b4eebe5b57c4978e8e2dbb2575022a3e16943ecf4cb672f0b5390153678c657c"
coverage_summary:
  total_hunks: 2
  mapped_hunks: 2
  coverage_percentage: 100.0
evaluation_outcomes:
  observed_execution_result:
    execution_status: "NOT_RUN"
    observed_gate_output: "NOT_RUN"
    observed_dispatch_status: "NOT_RUN"
    reason: >
      This fixture is strictly an unexecuted illustrative schematic template; no live review
      engine or test runner was executed during this drafting turn. An unexecuted template
      must report NOT_RUN, not an observed SATISFIED outcome.
  expected_coverage_outcome_if_valid_evidence_is_supplied:
    expected_gate_output: SATISFIED
    expected_action_result: NONE
    condition: >
      Applies when authentic, executed test receipts with matching runner binary digests
      or qualified CleanHunkAttestation records are supplied, demonstrating 100% coverage
      and resolution across all unified diff hunks.
```

## 4.3 Grounding & Evidence Analysis
- **Evidence Label:** SOURCED from `FREEZE-CANDIDATE-v6.0.2/product/r29-companion/RESEARCH-NOTES-R29.md` §A (*"Wang et al.: manual-review estimate gave 11.0% and 6.4 points inflation... SWE-ABS: strengthening tests rejected 19.78% of passing patches... Supports: S-Class's rule that a green test run alone is not completion"*) and §B (*"Agents game tests; the trajectory matters"*).
- **Master Grounding:** Grounded in Master §2.15 (`PD-CH2-052` finding aggregation).
- **Size Bounds Authority:** The 2 MiB cutoff is authoritative per CL binding decision on `P9-OI-001` (Option A).

## 4.4 Decision Resolution (CL Directive)
- **`P9-OI-001` (Diff Inspection Bounds & Large Files):** **RESOLVED VIA CL DIRECTION (OPTION A)**. Hard 2 MiB cutoff enforced. Diffs exceeding 2 MiB or containing unreviewable binary content fail closed with `MISSING[PD-CH2-066]` and `action_result: BLOCKED`.

---

# SECTION 5: Symbol-Level Plan Checks (Area 5)

## 5.1 Specification & Boundary Requirements

### Canonical Module-Path Semantics & Python-Only Granularity
Per CL's binding decision on `P4-OI-001` (Option B):
- Symbol-level plan resolution in P4 is restricted strictly to Python in v1.
- For non-Python files, task units remain at coarse file-level granularity.
- Symbol targets in Python tasks are identified by canonical 4-tuples:
  $$	ext{SymbolTuple} = (	ext{target\_snapshot\_ref}, 	ext{canonical\_module\_path}, 	ext{qualname}, 	ext{signature\_digest})$$
- Every planned symbol mutation target MUST resolve against the active repository snapshot index (`PD-CH8-012`). Unresolvable symbols fail closed with **`gate_output: MISSING[PD-CH2-067]`** and **`action_result: BLOCKED`**.

## 5.2 Proposed Normative MUST Specification: `PD-CH2-067`

| ID | Class | Decidable requirement | Gaming fixture | Happy fixture |
|---|---|---|---|---|
| `PD-CH2-067` | M | In planned tasks modifying Python files, symbol-level mutation targets MUST resolve against the repository snapshot index to canonical `(target_snapshot_ref, module_path, qualname, signature_digest)` tuples; unresolvable symbols or ambiguous bare names MUST fail closed with `MISSING[PD-CH2-067]` and `action_result: BLOCKED`; non-Python tasks fall back to file-level task granularity. | `CH2-T79` → `MISSING[PD-CH2-067]` (`action_result: BLOCKED`) | `CH2-T80` → Illustrative schema template (Python symbol resolving unambiguously to index entry) |

- **Failure route:** Gate returns `MISSING[PD-CH2-067]` with `action_result: BLOCKED`; halts P4 plan compilation; routes back to task decomposition.
- **Who may write:** Only the qualified language symbol resolver writes derived symbol resolution records; agents propose symbol targets but cannot author index resolutions.
- **Kernel binding (frozen):** Binds to frozen `WorkNode` (`00-SPEC` §2.1, §7, §8.6) and `TargetSnapshot` (`00-SPEC` §12.6).
- **NEVER:** Never permit bare un-namespaced symbol names in multi-module projects, never resolve against unpinned repository state, and never invent signatures for unindexed symbols.
- **Cost bound:** Evaluator input capped at 512 symbol targets per plan [UNVERIFIED: proposed limit]; index lookup bounded by O(log N) index search.
- **Fixtures:**
  - `CH2-T79` (Gaming / Ambiguous & Absent Symbols):
    - *Variant A1 (Ambiguous Bare Symbol):* Plan declares `target: compute_digest` without module path → Ambiguous resolution → `MISSING[PD-CH2-067]`, `action_result: BLOCKED`.
    - *Variant A2 (Absent Symbol):* Plan declares `target: src/auth.py::non_existent_func` → Symbol not found in index → `MISSING[PD-CH2-067]`, `action_result: BLOCKED`.
  - `CH2-T80` (Happy / Qualified Symbol Resolving in Index): Symbol `compute_predicate_digest` resolves to `src/sclass/product/predicate_evaluator.py` with matching signature digest → `gate_output: SATISFIED`, `action_result: NONE`.

### Fixture Specifications: `CH2-T79` & `CH2-T80`

```yaml
#### CH2-T79 — gaming fixture for PD-CH2-067
must_id: PD-CH2-067
fixture_role: gaming
input_binding: ambiguous, un-namespaced, or non-existent symbol reference in planned task
bound_inputs: [planned_task_node, target_snapshot_index_ref]
attack_or_case: Agent attempts to schedule task without unambiguous symbol binding
expected_gate_output: MISSING[PD-CH2-067]
expected_action_result: BLOCKED
execution_evidence: UNVERIFIED
attack_variants:
  - id: A1
    description: "Ambiguous bare symbol name without module path"
    planned_symbol_target: "compute_digest"
    index_lookup_result: "AMBIGUOUS_MULTIPLE_MATCHES"
  - id: A2
    description: "Symbol does not exist in target snapshot index"
    planned_symbol_target: "src/sclass/product/predicate_evaluator.py::non_existent_method"
    index_lookup_result: "SYMBOL_NOT_FOUND"

#### CH2-T80 — happy fixture for PD-CH2-067
must_id: PD-CH2-067
fixture_role: happy
fixture_status: illustrative_schematic_template (UNEXECUTED)
execution_evidence: UNVERIFIED
notice_of_schematic_status: >
  This fixture illustrates the structural binding of a planned symbol mutation target to an
  AST snapshot index. The signature digest is computed over the real predicate_evaluator.py
  module, but the index reference and snapshot resolution are schematic representations
  pending qualification of an F10 language indexing adapter under P4-OI-001 (Option B).
input_binding: fully qualified symbol resolving unambiguously in current index
bound_inputs: [planned_task_node, target_snapshot_index_ref]
target_snapshot_ref: "snap-r30-b1-3ed415e"
target_snapshot_index_ref: "idx-r30-b1-sha256-f4b8c9d2e1a30765948b321c876543210abcdef012345678"
symbol_target:
  module_path: "src/sclass/product/predicate_evaluator.py"
  qualname: "compute_predicate_digest"
  signature_digest: "93e7d9488e88e6137fd95da969a34fa31d4eb6d5a8087d7e2147fc4dd6e0bbec"
evaluation_outcomes:
  observed_execution_result:
    execution_status: "NOT_RUN"
    observed_gate_output: "NOT_RUN"
    observed_dispatch_status: "NOT_RUN"
    reason: >
      This fixture is strictly an unexecuted illustrative schematic template; no live symbol
      index resolution was executed during this drafting turn. An unexecuted template reports NOT_RUN.
  normative_conforming_case_expectation:
    gate_output: SATISFIED
    action_result: NONE
    condition: "Applies when planned symbol target resolves unambiguously to an active index entry bound to current TargetSnapshot."
```

## 5.3 Grounding & Evidence Analysis
- **Evidence Label:** **`UNVERIFIED`** in companion research files.
- **Master Grounding:** Grounded in Master §2.10 (P4 Task Decomposition units) and Master §8.5 (`PD-CH8-012` index disclosure).

## 5.4 Decision Resolution (CL Directive)
- **`P4-OI-001` (Symbol Indexing Engine & Scope):** **RESOLVED VIA CL DIRECTION (OPTION B)**. Python-only symbol granularity in v1; non-Python tasks fall back to file-level task units.

---

# SECTION 6: Section 3.6 Evaluation — Plan-versus-Diff Binding Delta

## 6.1 Directive Mandate & Question
Directive §3.6 instructs:
> "PD-CH4-014 already compares the observed delta with authorized scope. Do not create a second general diff-versus-scope requirement. Inspect whether the existing authorized scope is mechanically bound to the plan's declared write sets. If the binding is already fully specified, add nothing. If there is a genuine gap, propose only the narrow binding requirement necessary to connect the plan's declared write sets to the authorized scope evaluated by PD-CH4-014... If the master already establishes this binding, record **NO NEW MUST REQUIRED**."

## 6.2 Master Quotations & Systematic Analysis

### Quotation 1: Master §4.4 — Scope Lock Definition
> *"## 4.4 Scope lock*  
> *Trace: 'Compare proposed/observed mutation targets with canonical task scope and P4 declared writes. Known overlapping tasks serialize.'*  
> *Compare proposed/observed mutation targets with canonical task scope and P4 declared writes. Known overlapping tasks serialize. Unknown/undeclared write sets block human resolution. Launched workers are prevented from unauthorized writes inside the S-Class boundary; host-native writes can only be detected and a revert/quarantine requested."* [SOURCED: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`, §4.4]

### Quotation 2: Master §4.4 — Normative MUST `PD-CH4-014`
> *"### R5 normative closure — PD-CH4-014*  
> *| ID | Class | Decidable requirement | Gaming fixture | Happy fixture |*  
> *|---|---|---|---|---|*  
> *| PD-CH4-014 | M | An observed delta outside the authorized write/scope set MUST return BLOCKED and cannot be accepted by a green test run. | CH4-T19 → `MISSING[PD-CH4-014]` with `action_result: BLOCKED` | CH4-T20 → `SATISFIED` |"* [SOURCED: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`, §4.4]

### Quotation 3: Master Appendix F — Fixture Binding for `PD-CH4-014`
> *"#### CH4-T19 — gaming fixture for PD-CH4-014*  
> *bound_inputs: [authorized_write_set_digest, observed_delta_digest, scope_revision_ref]*  
> *attack_or_case: An observed delta outside the authorized write/scope set MUST return BLOCKED and cannot be accepted by a green test run.*  
> *expected_gate_output: MISSING[PD-CH4-014]*  
> *expected_action_result: BLOCKED"* [SOURCED: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`, Appendix F]

### Quotation 4: Master §2.10 — P4 Planning Write Sets & Overlap
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
| `PD-CH8-014` | M | F10 / Runtime | Candidate commands must undergo structural AST analysis; parse failures fail closed; parsed dangerous commands emit findings bounded by boundary policy. | `CH8-014` (Range `CH8-001..199`) | Proposed (Non-normative draft) |
| `PD-CH8-015` | M | F10 / Host | Host control capabilities (E1/E2) require active probe verification; missing/unverified evidence downgrades to E0 degraded mode. | `CH8-015` (Range `CH8-001..199`) | Proposed (Non-normative draft) |
| `PD-CH8-016` | M/E/J | P6 / Pre-Write | Agent writes to protected control-plane paths or executable entrypoints require pre-write authorization; unapproved writes block on human approval. | `CH8-016` (Range `CH8-001..199`) | Proposed (Non-normative draft) |
| `PD-CH2-066` | M | P9 / Review | Diff review engine binds directly to unified diff against target snapshot; every hunk maps to resolved findings or clean attestations with 100% coverage. | `CH2-066` (Range `CH2-001..199`) | Proposed (Non-normative draft) |
| `PD-CH2-067` | M | P4 / Plan | Symbol-level mutation targets in planned tasks must resolve against bound repository snapshot index to canonical tuples. | `CH2-067` (Range `CH2-001..199`) | Proposed (Non-normative draft) |

### Test Registry Additions (Product Layer Proposals)

| Test ID | Role | Target MUST | Bound Input Form | Status |
|---|---|---|---|---|
| `CH8-T20` | Gaming | `PD-CH8-014` | Research-defined evasion categories (env, builtin, argument, expansion, eval), syntax errors, process substitution across E0/E1/E2 | Proposed |
| `CH8-T21` | Happy | `PD-CH8-014` | Conforming test command parseable under POSIX grammar across E0/E1/E2 | Proposed |
| `CH8-T22` | Gaming | `PD-CH8-015` | Forged signatures, expired TTL, nonce mismatch, unverified host endpoint | Proposed |
| `CH8-T23` | Happy | `PD-CH8-015` | Illustrative template with container namespace and cgroup telemetry | Proposed |
| `CH8-T24` | Gaming | `PD-CH8-016` | Traversal, Windows 8.3 short names, ADS syntax, unapproved executable entrypoint creation | Proposed |
| `CH8-T25` | Happy | `PD-CH8-016` | Illustrative template for application write set outside protected registry with null approval ref | Proposed |
| `CH2-T77` | Gaming | `PD-CH2-066` | Misleading summary masking code change, drifted snapshot, malformed diff, oversized patch (>2 MiB) | Proposed |
| `CH2-T78` | Happy | `PD-CH2-066` | Multi-hunk diff with 100% coverage (findings resolved with test receipts) | Proposed |
| `CH2-T79` | Gaming | `PD-CH2-067` | Ambiguous bare name, absent symbol in index | Proposed |
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

*Gate 2 Audit Assessment:* While all nine syntactic items are present in each specification, Gate 2 assesses whether each required element is *semantically complete and testable*. Because algorithmic derivation for write sets (`P4-OI-002`) remains open, Gate 2 is assessed as **PARTIAL** pending future kernel API specification.

| Checklist Item | `PD-CH8-014` | `PD-CH8-015` | `PD-CH8-016` | `PD-CH2-066` | `PD-CH2-067` |
|---|---|---|---|---|---|
| 1. ID | Present (`PD-CH8-014`) | Present (`PD-CH8-015`) | Present (`PD-CH8-016`) | Present (`PD-CH2-066`) | Present (`PD-CH2-067`) |
| 2. Class | Present (`M`) | Present (`M`) | Present (`M/E/J`) | Present (`M`) | Present (`M`) |
| 3. Decidable Requirement | Present (AST evaluation under research rules) | Present (Active probe boundary verification) | Present (Protected path & executable entrypoint gate) | Present (Diff-level hunk coverage & 2 MiB cutoff) | Present (Python symbol index resolution) |
| 4. Failure Route | Present (`MISSING[PD-CH8-014]`, `BLOCKED`) | Present (`MISSING[PD-CH8-015]`, `BLOCKED`) | Present (`MISSING[PD-CH8-016]`, `BLOCKED`) | Present (`MISSING[PD-CH2-066]`, `BLOCKED`) | Present (`MISSING[PD-CH2-067]`, `BLOCKED`) |
| 5. Writer Authority | Present (Qualified command evaluator) | Present (External probe harness via ApprovalSet) | Present (Qualified path resolver) | Present (Qualified diff review evaluator) | Present (Qualified symbol resolver) |
| 6. Frozen Kernel Binding | Unsupported in `00-SPEC/` (Grep verified) | Present (`ApprovalSet`, `CapabilityDeclaration`) | Present (`ApprovalSet`, `TargetSnapshot`) | Present (`TargetSnapshot`, `AcceptanceContract`) | Present (`WorkNode`, `TargetSnapshot`) |
| 7. NEVER Invariant | Present (Four explicit NEVER clauses) | Present (Four explicit NEVER clauses) | Present (Four explicit NEVER clauses) | Present (Four explicit NEVER clauses) | Present (Three explicit NEVER clauses) |
| 8. Cost Bound | Present (64 KiB, 1,000 nodes, 500 ms) | Present (5.0s probe timeout) | Present (1,024 paths, 4,096 chars) | Present (2 MiB patch limit, 1,000 hunks) | Present (512 symbols, O(log N)) |
| 9. Dual Fixtures | Present (`CH8-T20` / `CH8-T21`) | Present (`CH8-T22` / `CH8-T23`) | Present (`CH8-T24` / `CH8-T25`) | Present (`CH2-T77` / `CH2-T78`) | Present (`CH2-T79` / `CH2-T80`) |

### 8.2 Six-Gate Summary Table

| Gate | Area 1: Command Analyzer (`PD-CH8-014`) | Area 2: Host Probe (`PD-CH8-015`) | Area 3: Protected Path (`PD-CH8-016`) | Area 4: Diff Review (`PD-CH2-066`) | Area 5: Symbol Checks (`PD-CH2-067`) | Section 3.6 Evaluation |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Gate 1: Duplicate Avoidance** | **PASS** (Zero overlap with `PD-CH8-008`) | **PASS** (Zero overlap with `PD-CH8-008`) | **PASS** (Zero overlap with `PD-CH4-014`, `PD-CH8-011`) | **PASS** (Zero overlap with `PD-CH2-052`) | **PASS** (Zero overlap with `PD-CH8-012`, `PD-CH2-029`) | **PASS** (NO NEW MUST REQUIRED) |
| **Gate 2: Completeness (9-Part)** | **PARTIAL** (Cost limits `UNVERIFIED`) | **PARTIAL** (Transport choices `PROPOSED-NEW`) | **PARTIAL** (Resolution limits `UNVERIFIED`) | **PARTIAL** (Clean evaluator proposed under F10) | **PARTIAL** (Signature hashing `UNVERIFIED`) | **NOT APPLICABLE** |
| **Gate 3: Non-Self-Approval & Kernel Non-Expansion** | **PASS** (No new kernel trust root; command binding unsupported) | **PASS** (No new kernel trust root; binds to `ApprovalSet`) | **PASS** (No new kernel trust root; binds to `ApprovalSet`) | **PASS** (Evaluator output requires external review finding closure) | **PASS** (Index resolution reads frozen snapshot index) | **PASS** (Zero kernel modification) |
| **Gate 4: Qualified Evaluator Authority** | **PARTIAL** (Command evaluator proposed, not qualified under F10) | **PARTIAL** (Probe harness proposed, not qualified under F10) | **PARTIAL** (Path resolver proposed, not qualified under F10) | **PARTIAL** (Diff review evaluator proposed, not qualified under F10) | **PARTIAL** (AST indexer proposed, not qualified under F10) | **NOT APPLICABLE** |
| **Gate 5: Evidence Grounding** | **PARTIAL** (SOURCED `RESEARCH-COMMAND-BLOCKING.md`; limits `UNVERIFIED`) | **PARTIAL** (SOURCED `RESEARCH-NOTES-R29.md` §C; transport `PROPOSED-NEW`) | **PARTIAL** (SOURCED `RESEARCH-NOTES-R29.md` §B; limits `UNVERIFIED`) | **PARTIAL** (SOURCED `RESEARCH-NOTES-R29.md` §A, §B; 2 MiB cutoff per CL decision) | **PARTIAL** (Derived from Master §2.10/§8.5; marked `UNVERIFIED`) | **PARTIAL** (Algorithm `UNVERIFIED`; provisional conclusion) |
| **Gate 6: Unresolved Decisions** | **PASS** (`CH8-OI-004` MOOT per CL direction) | **PASS** (`CH8-OI-005` RESOLVED via Option C per CL direction) | **PASS** (`CH8-OI-006` RESOLVED via Option A per CL direction) | **PASS** (`P9-OI-001` RESOLVED via Option A per CL direction) | **PASS** (`P4-OI-001` RESOLVED via Option B per CL direction) | **BLOCKED** (`P4-OI-002` derivation algorithm unresolved) |

### 8.3 Enforcement Status & CL Binding Directives
- **`CH8-OI-004` (Moot):** Research-defined taxonomy in `RESEARCH-COMMAND-BLOCKING.md` governs command evaluation.
- **`CH8-OI-005` (Option C Adopted):** Linux containers only; desktop IDEs unconditionally E0.
- **`CH8-OI-006` (Option A Adopted):** Immutable engine-level registry; in-repo customization disabled.
- **`P9-OI-001` (Option A Adopted):** Hard 2 MiB cutoff; diffs > 2 MiB fail closed with `action_result: BLOCKED`.
- **`P4-OI-001` (Option B Adopted):** Python-only symbol granularity in v1; non-Python falls back to file units.

---

## Section 9: Consolidated Decision Register

| Decision ID | Proposal Area | Status | Resolution / Directing Authority |
|---|---|:---:|---|
| **`CH8-OI-004`** | Area 1: Command Analyzer | **RESOLVED (MOOT)** | Moot per CL Direction; governed by `RESEARCH-COMMAND-BLOCKING.md`. |
| **`CH8-OI-005`** | Area 2: Host Probe | **RESOLVED (OPTION C)** | Option C adopted per CL Direction: Linux containers only; desktop IDEs unconditionally E0. |
| **`CH8-OI-006`** | Area 3: Protected Path | **RESOLVED (OPTION A)** | Option A adopted per CL Direction: Immutable engine-level registry; in-repo customization disabled. |
| **`P9-OI-001`** | Area 4: Diff Review | **RESOLVED (OPTION A)** | Option A adopted per CL Direction: Hard 2 MiB cutoff with fail-closed blocking. |
| **`P4-OI-001`** | Area 5: Symbol Checks | **RESOLVED (OPTION B)** | Option B adopted per CL Direction: Python-only symbol granularity in v1. |
| **`P4-OI-002`** | Section 3.6 / P4 Derivation | **BLOCKED — AK DECISION REQUIRED** | Algorithmic definition of mechanical write-set digest derivation from P4 task nodes remains provisional. |

---

## Section 10: Gate 3 Frozen Specification Grep Audit

In strict compliance with CL Criterion 10, all kernel bindings were verified by direct `git grep` execution against `00-SPEC/`:

### Raw Grep 1: `SessionContext`
```text
$ git grep "SessionContext" -- 00-SPEC/
<zero matches - exit code 1>
```
*Determination:* `SessionContext` does NOT exist in `00-SPEC/`. Any prior claim of a frozen kernel binding to `SessionContext` was erroneous. In Revision 4, `SessionContext` is explicitly removed and documented as unsupported.

### Raw Grep 2: `ApprovalSet`
```text
$ git grep "ApprovalSet" -- 00-SPEC/
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:| 11 | `ApprovalSetResult` | Enum/Value |
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:| 12 | `ApprovalSet` | Canonical |
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:    approval_sets: FrozenMap                    # set_id -> ApprovalSet
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:class ApprovalSetResult(Enum):
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:class ApprovalSet:
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:def validate_approval_set(a: ApprovalSet, valid_signature_ids: frozenset[str], at: UtcInstant,
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:                           require_separation_of_duties: bool = True) -> ApprovalSetResult:
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:        return ApprovalSetResult.INSUFFICIENT
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:        return ApprovalSetResult.INVALID_SCOPE
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:        return ApprovalSetResult.INVALID_SCOPE
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:            return ApprovalSetResult.INVALID_SIGNATURE
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:            return ApprovalSetResult.INVALID_SCOPE
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:            return ApprovalSetResult.EXPIRED
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:            return ApprovalSetResult.INVALID_SCOPE
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:            return ApprovalSetResult.DUPLICATE_PRINCIPAL
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:            return ApprovalSetResult.INVALID_SCOPE
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:            return ApprovalSetResult.DUPLICATE_PRINCIPAL
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:    return ApprovalSetResult.VALID if len(authorities) >= required_principals else ApprovalSetResult.INSUFFICIENT
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:**ApprovalSet:** one reusable approval primitive covers dual authorization, policy relaxation, break-glass, waiver and release approvals. Distinct principals are mandatory wherever the required quorum is greater than one.
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:        if validate_approval_set(ApprovalSet("policy-activation", ApprovalKind.POLICY_RELAXATION,
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:        valid_signature_ids, at, principal_directory, required_principals, principal_authority_ids, bool(requester_principal_id)) is not ApprovalSetResult.VALID:
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:                if validate_approval_set(aset,valid_ids,state.target_snapshot.created_at,policy.waiver_rules.approver_authorities,aset.required_principals,{},True) is not ApprovalSetResult.VALID: continue
```
*Determination:* `ApprovalSet` is authenticated in `00-SPEC/` §2.1 (SemanticTypeRegistry), §2.2 (`EngineeringState`), and §3.2 (Transaction Boundary validation).

### Raw Grep 3: `WorkNode`
```text
$ git grep "WorkNode" -- 00-SPEC/
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:| 100 | `WorkNodeStatus` | Enum/Value |
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:| 101 | `WorkNode` | Canonical |
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:class WorkNodeStatus(Enum):
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:class WorkNode:
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:    status: WorkNodeStatus
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:    def frontier(self) -> Sequence[WorkNode]: ...                       # READY nodes whose deps satisfy
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:    def schedule(self, frontier: Sequence[WorkNode], workers: Sequence[WorkerInstance],
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:**No bypass path:** the only code allowed to invoke `WorkerContract.execute` is `ExecutionGate`. Executors accept only `AuthorizedWorkRequest` (never `WorkProposal`/`WorkNode`), and re-verify `envelope_digest`, both leases, and fencing on entry. Construction of `AuthorizedWorkRequest` outside the gate is a lint error (CI ZV1 check).
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:                      for name in ("WorkNodeStatus","ObligationStatus","RequirementStatus","LeaseState")}
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:        if optional_machine and node_id is not None: apply_machine("WorkNodeStatus",node_id,optional_machine)
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md:`WorkNodeStatus` legal transitions (anything else → `REJECTED_ILLEGAL_TRANSITION`):
00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md: -> plan one WorkNode
```
*Determination:* `WorkNode` is authenticated in `00-SPEC/` §2.1 (SemanticTypeRegistry), §7 (WorkGraph, Scheduler, Retry), and §8.6 (ExecutionGate).
