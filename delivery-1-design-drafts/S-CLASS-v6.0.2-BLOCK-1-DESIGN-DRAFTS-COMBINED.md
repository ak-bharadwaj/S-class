# S-Class v6.0.2 Block 1 Consolidated Design Proposals (Revision 3 — Narrow Scope & Duplicate Exclusion)

**Repository:** `ak-bharadwaj/S-class`  
**Branch:** `lane-c-design-drafts`  
**Accepted Integration Base:** `3ed415e67e15e6aedc7d456445c3c193146ae606`  
**Previous Delivered Revision:** `6b0ccfc99a1ee91e642dea79a321f05033fe14ca` (Revision 2)  
**Normative Master Source:** `FREEZE-CANDIDATE-v6.0.2/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md` (SHA-256: `340db97857a7716b1aac2c1b44bc60b32642e3d8074d0263f3ce56da7dbb34eb`)  
**Companion Research Sources:**  
- `FREEZE-CANDIDATE-v6.0.2/product/r29-companion/RESEARCH-NOTES-R29.md` (SHA-256: `88632c8b93e410c60a6e3412bfd2a505766a48d7400432e23dc63d14b84a2f72`)  
- `FREEZE-CANDIDATE-v6.0.2/product/r29-companion/FREEZE-DECISION-R28.md` (SHA-256: `084c68832a76f264e1e07b8a53fc2632aa6c9ef5eb461158fc92e236ceeb4fce`)  
**Status:** PROPOSAL / DESIGN DRAFT ONLY (Revision 3)  
*Notice: This document is an unaccepted engineering proposal authored under Lane C (Directive 10). It does not alter normative master text, modify frozen directories (`00-SPEC/`, `10-CONFORMANCE/`, `20-RUNTIME/`), change MUST statuses, or commit new kernel state. It is subject to GPT review and formal gating before submission to CL.*

---

## Executive Summary & Revision 3 Architectural Changes

Revision 3 completely replaces the broad Revision 2 proposals with a narrowly scoped, duplicate-free set of product-layer additions strictly conforming to the Lane C Revision 3 Authoring Draft and Change-Control Directive.

### 1. Narrow Scope Discipline
Revision 3 restricts product-layer additions exclusively to five genuinely new areas:
1. **Structural Command Analyzer (`PD-CH8-014`):** Shell AST/grammar representation evaluating command structure rather than substring matching, fail-closed on unparseable syntax, strictly respecting the `PD-CH8-008` prevention boundary.
2. **Host-Control Verification by Active Probe & Degraded-Mode Detection (`PD-CH8-015`):** Active runtime probe evidence bound to the execution session, automatic capability downgrade to `E0_ADVISORY` upon stale/missing/failed probe, and strict rejection of agent self-declarations.
3. **Protected-Path Gate (`PD-CH8-016`):** Pre-write patch gate protecting control-plane files (hooks, configuration, task definitions, interpreters, Git metadata) via canonical absolute path normalization, requiring explicit canonical `ApprovalRecord` from Kernel Authority.
4. **Diff-Level Review Engine (`PD-CH2-066`):** Inspection of actual physical unified diff deltas bound to target snapshots, hunk-level coordinate binding, and complete rejection of agent-authored summaries as authority.
5. **Symbol-Level Plan Checks (`PD-CH2-067`):** Resolution of planned mutation targets against bound AST repository snapshots, enforcing fully qualified symbol tuples and fail-closed handling for ambiguous/unresolved targets while preserving `PD-CH8-012` index disclosure ownership.

### 2. Plan-versus-Diff Binding Evaluation (§3.6)
Pursuant to Directive §3.6, a rigorous inspection of Master §4.4 and §2.10 was conducted. The master already establishes the mechanical link between planned task write sets and the authorized scope evaluated by `PD-CH4-014` (`authorized_write_set_digest`). Consequently, Revision 3 formally records **NO NEW MUST REQUIRED** for this area, eliminating redundant specification.

### 3. Strict Evidence & Terminology Discipline
- **Absolute Evidence Label Constraint:** In strict compliance with Section 5 of the Directive, only two evidence labels are used throughout this document:
  - **`SOURCED`** (followed by exact file and section citation)
  - **`UNVERIFIED`** (where companion files do not establish empirical support)
  The word "VERIFIED" is never used as an evidence label.
- **No Invented Research Claims:** Revision 3 explicitly disclaims an empirical 12-bypass benchmark or shell grammar corpus in research, marking the command-analyzer evasion corpus as `UNVERIFIED` and retaining `CH8-OI-004` as `BLOCKED — AK DECISION REQUIRED`.
- **Open Decisions Discipline:** Every open issue is formally recorded under `BLOCKED — AK DECISION REQUIRED` with explicit questions and discrete options.

---

## Section 0: Mandatory Duplicate Exclusion Baseline & Registry Analysis

### 0.1 Duplicate Check Baseline Matrix
Revision 3 was systematically audited against the 11 baseline duplicate owners identified in Section 2 of the Directive. No proposed requirement duplicates, paraphrases, or re-assigns responsibilities already owned by the master:

| Baseline Owner | Master Section & Exact Quotation | Revision 3 Relationship & Boundary Proof |
|---|---|---|
| **`PD-CH8-008`** | **Master §7.4 / §8.4 (L355813):** *"IDE mode MUST declare E0/E1/E2 capabilities per qualified host/version; prevention honesty for host-native actions is owned by `PD-CH8-008`... NEVER claim prevention outside a qualified S-Class-launched boundary."* | **Preserved Unchanged.** `PD-CH8-014` and `PD-CH8-015` classify commands and probe capabilities; they explicitly disclaim host-native prevention outside launched worker boundaries. |
| **`PD-CH8-009`** | **Master §8.4 (L372443):** *"Workspace promotion MUST require the current target and kernel release authority after verification and preserve rollback evidence; comparison of the observed write set with authorized scope is owned by `PD-CH4-014`."* | **Preserved Unchanged.** Revision 3 introduces no workspace promotion rules, no release authority mechanisms, and no rollback manifest stores. |
| **`PD-CH8-010`** | **Master §8.4 (L374965):** *"Out-of-band/concurrent edits MUST trigger re-snapshot and digest comparison before continuing; invalidation is owned by `PD-CH2-055`."* | **Preserved Unchanged.** Revision 3 does not define concurrent edit detection or snapshot invalidation. |
| **`PD-CH8-011` / `PD-CH2-032`** | **Master §8.4 (L377336) / §2.10 (L167476):** *"Parallel work MUST follow dependencies and canonical delta order, serialize overlapping write sets and merge only when target identity and each task verification pass."* / *"Known write-set overlap MUST serialize mechanically; unknown/undeclared write sets MUST block for human resolution."* | **Preserved Unchanged.** Revision 3 does not modify parallel task scheduling, write-set serialization, or human blocking on unknown overlap. |
| **`PD-CH8-012`** | **Master §8.5 (L379726):** *"Repository intelligence MUST disclose index coverage/freshness and unresolved symbols remain MISSING."* | **Preserved Unchanged.** `PD-CH2-067` resolves planned symbol targets during P4 against the index disclosed by `PD-CH8-012`. It does not redefine index freshness or disclosure. |
| **`PD-CH8-013`** | **Master §8.5 (L382338):** *"Budget exhaustion MUST stop or route to an authorized repair path; retry decisions use the frozen RetryBudget with no second ledger; hard budget gates reject model-reported-only cost...* | **Preserved Unchanged.** Revision 3 defines no budget ledgers, cost tracking, or token counters. |
| **`PD-CH4-014`** | **Master §4.4 (L293933):** *"An observed delta outside the authorized write/scope set MUST return BLOCKED and cannot be accepted by a green test run."* | **Preserved Unchanged.** `PD-CH8-016` acts as a pre-write gate specifically for protected control-plane paths, requiring canonical `ApprovalRecord`. Evaluated in §3.6: **NO NEW MUST REQUIRED**. |
| **`P4-COVERAGE` / `P4-OVERLAP`** | **Master §2.10 (L169833):** *"require each applicable obligation mapped to a planned verifier via F6 trace links" / "known write-set intersection forces serialization; unknown/missing write set blocks for human"* | **Preserved Unchanged.** `PD-CH2-067` introduces symbol resolution checks within P4 without altering obligation coverage or overlap sub-checks. |
| **`PD-CH2-029` / `PD-CH2-031`** | **Master §2.10 (L172383):** *"P4 MUST enforce task-count and task-unit caps from the F4 lane's canonical Policy defaults."* / *"WorkGraph dependency edges MUST be acyclic."* | **Preserved Unchanged.** Revision 3 does not define lane caps, graph unit bounds, or graph cycle checks. |
| **`PD-CH2-052`** | **Master §2.15 (L204376):** *"P9 MUST aggregate all required P7 task results and close each mandatory finding only by evidence or canonical authority."* | **Preserved Unchanged.** `PD-CH2-066` requires diff inspection for review findings; it does not alter P9 task result aggregation, finding closure rules, or waiver authority. |
| **`PD-CH2-060`** | **Master §2.20 / §2.21 (L227420):** *"Every default user-facing flow MUST preserve P0–P11 order and route upstream defects to the earliest affected phase."* | **Preserved Unchanged.** Revision 3 introduces no new lifecycle phases or routing rules; failure routes strictly target existing phases (P3, P4, P6, P9). |

### 0.2 Canonical Registry Allocation Verification
Inspection of `FREEZE-CANDIDATE-v6.0.2/product/MUST-REGISTRY.md` establishes the authoritative allocation status:
- **Chapter 8 Allocated Range:** `CH8-008..013` (Retired: `001..007`).  
  **Next Unallocated Slot:** `014`.  
  *Proposed allocations:* `PD-CH8-014` (Area 1), `PD-CH8-015` (Area 2), `PD-CH8-016` (Area 3). All verified unallocated.
- **Chapter 2 Allocated Range:** `CH2-001..003`, `005..018`, `020..026`, `028..029`, `031..048`, `050..058`, `060..065` (Retired: `004, 019, 027, 030, 049, 059`).  
  **Next Unallocated Slot:** `066`.  
  *Proposed allocations:* `PD-CH2-066` (Area 4), `PD-CH2-067` (Area 5). All verified unallocated.
- **Test Registry Allocated Ranges:**  
  - `CH8`: Allocated `CH8-T8..T19`. Proposed unallocated test IDs: `CH8-T20..T25`.  
  - `CH2`: Allocated up to `CH2-T76`. Proposed unallocated test IDs: `CH2-T77..T80`.

---

# SECTION 1: Structural Command Analyzer (Area 1)

## 1.1 Specification & Boundary Requirements
- **Structural Analysis vs Substring Matching:** Simple substring matching (e.g. matching `rm -rf`, `curl`, `chmod`) is trivially bypassed via shell syntax variations. The structural command analyzer parses candidate command strings into a formal abstract syntax tree (AST) based on a recognized shell grammar (e.g. POSIX 1003.1 shell grammar).
- **Structural Features Evaluated:**
  1. *Command Identity:* Resolved executable path and canonical binary name (independent of leading paths, wrappers, or environment variable assignments).
  2. *Subshell Nesting:* Parenthesized commands `(...)`, command substitutions `$(...)` and backticks `` `...` ``, process substitutions `<(...)`, `>(...)`.
  3. *Pipeline & Control Chaining:* Pipeline operators (`|`), logical operators (`&&`, `||`), sequential execution (`;`, `&`, newlines).
  4. *Redirection Targets:* Output redirection (`>`, `>>`, `>|`, `&>`), input redirection (`<`, `<<`, `<<<`), file descriptor duplication (`2>&1`).
  5. *Variable & Parameter Expansion:* Environment expansions (`$VAR`, `${VAR:-...}`), arithmetic expansions (`$((...))`), quote-removal stages.
- **Fail-Closed on Unparseable Syntax:** Any candidate command that contains non-decodable bytes, invalid shell syntax, unsupported shell extensions, or ambiguous grammatical constructs cannot be structurally classified and MUST fail closed, returning `MISSING[PD-CH8-014]` with `action_result: BLOCKED`.
- **Enforcement Honesty & Authority Boundary:** The analyzer produces classification and risk assessment findings (`E0_ADVISORY`). It does NOT claim to prevent host-native execution outside the qualified S-Class-launched worker container. Host-native prevention honesty remains strictly governed by `PD-CH8-008`.
- **Corpus & Taxonomy Disclaimer:** S-Class does NOT adopt an unverified 12-class bypass taxonomy. The adversarial test suite covers documented syntactic and semantic evasion techniques, with grammar standard selection formally deferred to `CH8-OI-004`.

## 1.2 Proposed Normative MUST Specification: `PD-CH8-014`

| ID | Class | Decidable requirement | Gaming fixture | Happy fixture |
|---|---|---|---|---|
| `PD-CH8-014` | M | Candidate execution commands MUST undergo structural syntax analysis (AST/grammar evaluation) resolving executable identity, subshell nesting, pipeline chaining, redirection targets, and variable expansions; unparseable, ambiguous, or unsupported syntax MUST fail closed with `MISSING[PD-CH8-014]` and `action_result: BLOCKED`; analyzer findings remain advisory outside the qualified S-Class-launched boundary governed by `PD-CH8-008`. | `CH8-T20` → `MISSING[PD-CH8-014]` (`action_result: BLOCKED`) | `CH8-T21` → `SATISFIED` |

- **Failure route:** Gate returns `MISSING[PD-CH8-014]` with `action_result: BLOCKED`; halts execution command dispatch; routes to P6 implementation replan or human intervention.
- **Who may write:** Only the qualified structural command evaluator writes derived analysis records; agents and models propose command strings but cannot author or modify analysis records or bypass classifications.
- **Kernel binding (frozen):** Binds to frozen `EngineeringState` command dispatch projection (`00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §12.5 L3785-L3817).
- **NEVER:** Never infer safety from substring absence, never treat unparseable syntax as safe, and never claim host-native write prevention outside a qualified launched container.
- **Cost bound:** Evaluator input capped at 64 KiB command string and 1,000 AST nodes; execution bounded by O(AST nodes); budget units: bytes and node count. Parser timeout (>500 ms) or node overflow defaults to `BLOCKED`.
- **Fixtures:**
  - `CH8-T20` (Gaming / Adversarial Evasion): Tests syntactic and semantic evasion:
    - *Variant A1 (Quote Splitting):* `c'a't /etc/passwd` → AST unquotes to `cat /etc/passwd` → identified target → `MISSING[PD-CH8-014]`.
    - *Variant A2 (Backslash Escaping):* `c\\a\\t /etc/passwd` → AST normalizes to `cat /etc/passwd` → identified target → `MISSING[PD-CH8-014]`.
    - *Variant A3 (Variable Indirection):* `CMD=cat; $CMD /etc/passwd` → AST detects parameter expansion in command position → `MISSING[PD-CH8-014]`.
    - *Variant A4 (Semantic Eval Unbundling):* `eval "$(echo ...)"` → AST identifies dynamic execution wrapper → `MISSING[PD-CH8-014]`.
    - *Variant A5 (Base64 Pipeline Evasion):* `echo ZXhpdCAx | base64 -d | sh` → AST identifies pipeline into shell interpreter → `MISSING[PD-CH8-014]`.
    - *Variant A6 (Syntax Malformation):* `cat <(<<<)` → Unparseable shell syntax → `MISSING[PD-CH8-014]`.
  - `CH8-T21` (Happy / Fully Bound Conforming Command): Conforming command `pytest tests/test_unit.py -v` → AST evaluates single known executable, valid arguments, no illegal redirects, fully parsed → returns `SATISFIED`.

### Fixture Specifications: `CH8-T20` & `CH8-T21`

```yaml
#### CH8-T20 — gaming fixture for PD-CH8-014
must_id: PD-CH8-014
fixture_role: gaming
input_binding: typed mismatch or adversarial evasion payload in candidate command
bound_inputs: [command_string, environment_bindings, target_snapshot_ref]
attack_or_case: Evasion of command substring filtering or unparseable shell grammar payload
expected_gate_output: MISSING[PD-CH8-014]
expected_action_result: BLOCKED
execution_evidence: UNVERIFIED
attack_variants:
  - id: A1
    description: "Quote insertion syntactic evasion"
    payload: "c'a't /etc/passwd"
    expected_gate_output: MISSING[PD-CH8-014]
    expected_action_result: BLOCKED
  - id: A2
    description: "Backslash escaping syntactic evasion"
    payload: "c\\a\\t /etc/shadow"
    expected_gate_output: MISSING[PD-CH8-014]
    expected_action_result: BLOCKED
  - id: A3
    description: "Variable indirection evasion"
    payload: "CMD=rm; $CMD -rf /tmp/data"
    expected_gate_output: MISSING[PD-CH8-014]
    expected_action_result: BLOCKED
  - id: A4
    description: "Eval dynamic execution indirection"
    payload: "eval $(printf '\\x63\\x61\\x74') /etc/hosts"
    expected_gate_output: MISSING[PD-CH8-014]
    expected_action_result: BLOCKED
  - id: A5
    description: "Encoded pipeline to shell"
    payload: "echo Zm9v | base64 -d | sh"
    expected_gate_output: MISSING[PD-CH8-014]
    expected_action_result: BLOCKED
  - id: A6
    description: "Grammatically unparseable syntax"
    payload: "for ((i=0; i<; i++)) do echo; done"
    expected_gate_output: MISSING[PD-CH8-014]
    expected_action_result: BLOCKED

#### CH8-T21 — happy fixture for PD-CH8-014
must_id: PD-CH8-014
fixture_role: happy
input_binding: conforming command payload fully parseable under POSIX grammar
bound_inputs: [command_string, environment_bindings, target_snapshot_ref]
baseline: conforming test runner invocation with explicit arguments
payload: "pytest tests/test_core.py -v --tb=short"
expected_gate_output: SATISFIED
expected_action_result: NONE
execution_evidence: UNVERIFIED
```

## 1.3 Grounding & Evidence Analysis
- **Evidence Label:** **`UNVERIFIED`** in companion research files.
- **Companion Grounding:** SOURCED from `FREEZE-CANDIDATE-v6.0.2/product/r29-companion/RESEARCH-NOTES-R29.md` §B (EvilGenie study notes agent evasion behavior, but does not provide a 12-bypass command grammar taxonomy). The selection of POSIX 1003.1 AST parsing is an engineering proposal.
- **Master Grounding:** Conforms to Master §8.4 / §1.10 (S-Class is not a replacement shell runtime; analysis is an advisory safety gate).

## 1.4 Formal Open Decision (Gate 6)

### `BLOCKED — AK DECISION REQUIRED (CH8-OI-004)`
- **Issue Summary:** Shell Grammar Standard and Adversarial Corpus Selection for Structural Command Analyzer.
- **Question for AK:** Which concrete shell grammar standard and adversarial evasion corpus shall be adopted as the normative specification for `PD-CH8-014`?
- **Decision Options:**
  - **Option A:** Adopt standard POSIX 1003.1 shell grammar as the normative parsing boundary. Non-POSIX constructs (bashisms, zshisms) fail closed as unparseable (`MISSING[PD-CH8-014]`). Corpus based on documented POSIX AST expansions.
  - **Option B:** Adopt full Bash 5.x grammar including non-POSIX extensions (process substitution, array variables, extended test `[[ ... ]]`), requiring a qualified external parser adapter under F10.
  - **Option C:** Defer AST command analysis to post-v1; operate command analysis strictly as an advisory warning (`E0_ADVISORY`) without execution blocking.

---

# SECTION 2: Host-Control Verification by Active Probe & Degraded Mode (Area 2)

## 2.1 Specification & Boundary Requirements
- **Host-Controlled Probe Evidence:** Capability claims (e.g. `E1_SUPERVISED`, `E2_CONTAINED`) cannot be established by static configuration files, environment variables, or IDE metadata. A capability claim requires active probe evidence: execution of an isolated probe script/binary at session initialization testing actual host control enforcement (filesystem write locks, process namespace isolation, cgroup memory/CPU limits, syscall filters).
- **Session & Runtime Context Binding:** The probe generates a cryptographic `ProbeReceipt` bound to:
  1. `session_id`: Unique active session identifier.
  2. `host_platform`: Operating system name, kernel release, architecture.
  3. `runtime_digest`: SHA-256 digest of container/sandbox daemon binaries and active configuration.
  4. `probe_timestamp`: Wall-clock UTC timestamp with a strict validity TTL (default: 3,600 seconds).
- **Handling Missing, Stale, Failed, or Unqualified Probe Evidence:**
  - If a probe receipt is missing, expired (stale), failing any isolation assertion, or produced by an unqualified probe harness, the system MUST immediately downgrade the capability claim for that session to **`E0_ADVISORY`**.
- **Degraded-Mode Operation:** When downgraded to `E0_ADVISORY`, the system operates strictly in detection and containment mode. Automated write-prevention claims are strictly prohibited. Workspace promotions require explicit human confirmation (`BLOCKED_ON_HUMAN`).
- **Non-Self-Approval Rule:** Agent declarations, model self-attestations, or environment variables (e.g. `SCLASS_ISOLATION_ACTIVE=1`) have zero authority and MUST NOT substitute for active probe evidence.
- **Preservation of PD-CH8-008:** Distinguishes a probe reporting host capabilities from an enforcement mechanism that guarantees them; prevention honesty remains anchored to `PD-CH8-008`.

## 2.2 Proposed Normative MUST Specification: `PD-CH8-015`

| ID | Class | Decidable requirement | Gaming fixture | Happy fixture |
|---|---|---|---|---|
| `PD-CH8-015` | M | Host control capabilities (E1/E2) MUST be established by an active, qualified host probe returning a cryptographically bound `ProbeReceipt` pinned to the active session, host runtime, and timestamp; missing, stale, failed, or unqualified probe evidence MUST downgrade the session capability to `E0_ADVISORY` with mandatory human promotion gating; agent self-declarations or environment variables MUST NOT substitute for probe evidence. | `CH8-T22` → `MISSING[PD-CH8-015]` (downgrade to `E0_ADVISORY`) | `CH8-T23` → `SATISFIED` (E1/E2 capability bound) |

- **Failure route:** Gate returns `MISSING[PD-CH8-015]`; session capability downgraded to `E0_ADVISORY`; routes to human governance for write gating; prevents automated promotion.
- **Who may write:** Only the qualified host probe evaluator writes `ProbeReceipt` records; agents, workers, and host IDEs cannot self-assert capability ratings or forge receipts.
- **Kernel binding (frozen):** Binds to frozen `SessionContext` and `CapabilityDeclaration` (`00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §14.3 L4143-L4191).
- **NEVER:** Never infer host enforcement from IDE names, never accept agent self-declared isolation, and never preserve E1/E2 capability claims when probe evidence is absent or stale.
- **Cost bound:** Probe execution hard timeout 5.0 seconds; probe receipt payload capped at 16 KiB; evaluation cost O(1); receipt expiration TTL 3,600 seconds.
- **Fixtures:**
  - `CH8-T22` (Gaming / Unverified Capability Claim): Agent asserts `E2_CONTAINED` capability via environment variable `SCLASS_CONTAINED=1`, but active probe receipt is missing or has expired timestamp (>3,600s) → Gate rejects assertion, produces `MISSING[PD-CH8-015]`, and downgrades session to `E0_ADVISORY`.
  - `CH8-T23` (Happy / Qualified Probe Execution): Host probe executes active namespace write trap, emits signed `ProbeReceipt` matching active `session_id` and fresh timestamp (<60s) → Gate returns `SATISFIED`, binding E2 capability.

### Fixture Specifications: `CH8-T22` & `CH8-T23`

```yaml
#### CH8-T22 — gaming fixture for PD-CH8-015
must_id: PD-CH8-015
fixture_role: gaming
input_binding: agent-declared capability without valid host probe receipt
bound_inputs: [claimed_capability, session_id, host_runtime_ref, probe_receipt]
attack_or_case: Agent attempts to claim E2_CONTAINED via self-attestation while probe is stale or missing
expected_gate_output: MISSING[PD-CH8-015]
expected_action_result: DOWNGRADE_TO_E0
execution_evidence: UNVERIFIED
attack_variants:
  - id: A1
    description: "Missing probe receipt entirely"
    probe_receipt: null
    claimed_capability: "E2_CONTAINED"
    expected_gate_output: MISSING[PD-CH8-015]
    expected_action_result: DOWNGRADE_TO_E0
  - id: A2
    description: "Stale probe receipt exceeding TTL"
    probe_receipt: { timestamp_offset_seconds: -7200, status: "PASS" }
    claimed_capability: "E2_CONTAINED"
    expected_gate_output: MISSING[PD-CH8-015]
    expected_action_result: DOWNGRADE_TO_E0
  - id: A3
    description: "Failed active boundary write trap"
    probe_receipt: { write_trap_contained: false, status: "FAIL" }
    claimed_capability: "E1_SUPERVISED"
    expected_gate_output: MISSING[PD-CH8-015]
    expected_action_result: DOWNGRADE_TO_E0

#### CH8-T23 — happy fixture for PD-CH8-015
must_id: PD-CH8-015
fixture_role: happy
input_binding: fully qualified, fresh active probe receipt matching session context
bound_inputs: [claimed_capability, session_id, host_runtime_ref, probe_receipt]
claimed_capability: "E2_CONTAINED"
probe_receipt:
  session_id: "sess-2026-11-01-a1"
  timestamp_offset_seconds: -15
  host_platform: "linux-x86_64"
  isolation_check: "PASS"
  write_trap_contained: true
expected_gate_output: SATISFIED
expected_action_result: NONE
execution_evidence: UNVERIFIED
```

## 2.3 Grounding & Evidence Analysis
- **Evidence Label:** SOURCED from `FREEZE-CANDIDATE-v6.0.2/product/r29-companion/RESEARCH-NOTES-R29.md` §C (*"Host facts (v1 matrix); all hosts speak MCP, enforcement strength differs... The matrix must record per host/version which capability level (E0/E1/E2) is real... re-verify each at qualification time"*).
- **Unverified Aspects:** The concrete cryptographic signing algorithm and exact binary probe script implementation details are **`UNVERIFIED`** in research files and represent proposed engineering choices.

## 2.4 Formal Open Decision (Gate 6)

### `BLOCKED — AK DECISION REQUIRED (CH8-OI-005)`
- **Issue Summary:** Active Host Probe Architecture and Execution Transport Boundary.
- **Question for AK:** How shall the active host probe be executed across diverse host environments (VS Code, Cursor, Codex, Antigravity) without violating host sandbox restrictions?
- **Decision Options:**
  - **Option A:** Execute a lightweight standalone probe executable via MCP stdio during `session_open`, testing filesystem write filters and namespace boundaries directly.
  - **Option B:** Rely on host-specific MCP capability negotiation endpoints without executing an active write-trap probe, restricting E1/E2 claims to verified containerized workers only.
  - **Option C:** Restrict active probe verification strictly to Linux container execution environments, unconditionally treating all desktop IDE sessions as `E0_ADVISORY`.

---

# SECTION 3: Protected-Path Gate (Area 3)

## 3.1 Specification & Boundary Requirements
- **Protected Control-Plane Path Scope:** Agent-proposed patches frequently attempt to disable verification or compromise integrity by altering control-plane configurations. The protected-path gate explicitly intercepts proposed writes targeting:
  1. *Hooks:* Git hooks (`.git/hooks/**`), Husky hooks (`.husky/**`), pre-commit configs (`.pre-commit-config.yaml`), IDE plugin hooks.
  2. *Configuration Files:* Environment variable definitions (`.env`, `.env.*`), build/toolchain manifests (`pyproject.toml`, `package.json`, `Cargo.toml`), S-Class configurations (`sclass.config.json`).
  3. *Task Definitions:* CI/CD workflows (`.github/workflows/**`, `.gitlab-ci.yml`), build scripts, task runner declarations (`Makefile`, `Taskfile.yml`).
  4. *Interpreter & Execution Launch Files:* Virtual environments (`.venv/**`, `venv/**`), wrapper scripts (`bin/**`), interpreter configs.
  5. *Git Metadata:* Internal repository tracking structures (`.git/**`).
- **Canonical Absolute Path Normalization:** Paths cannot be compared as raw strings. The gate resolves paths to canonical absolute representations, neutralizing:
  - Directory traversal sequences (`..`, `../..`).
  - Symbolic links, hard links, and directory junctions pointing into protected directories.
  - Case variations on case-insensitive filesystems (e.g. `.GIT`, `.Husky`).
  - NTFS alternate data streams (e.g. `file.txt::$DATA`) and 8.3 short filename aliases (`GIT~1`).
- **Pre-Acceptance Evaluation:** The gate evaluates proposed write sets at patch ingestion (P6) before any write is staged, executed, or committed.
- **Authorization Source & Fail-Closed Behavior:** Writes to protected paths require an explicit, canonical `ApprovalRecord` originating from Kernel Authority (governed by `ApprovalSet` in `00-SPEC` §2.2.1). In the absence of an authorized `ApprovalRecord`, the gate MUST fail closed, returning `BLOCKED_ON_HUMAN[PD-CH8-016]`.
- **Preservation of Kernel Authority:** The gate does NOT invent a second approval store; it queries the frozen kernel `ApprovalSet`.

## 3.2 Proposed Normative MUST Specification: `PD-CH8-016`

| ID | Class | Decidable requirement | Gaming fixture | Happy fixture |
|---|---|---|---|---|
| `PD-CH8-016` | M/E/J | Agent-proposed writes to protected control-plane paths (hooks, configuration, task definitions, interpreters, Git metadata) MUST undergo canonical path normalization resolving symlinks, traversals, and aliases; any unapproved mutation targeting a protected path MUST fail closed with `BLOCKED_ON_HUMAN[PD-CH8-016]`; approval requires an explicit canonical `ApprovalRecord` from Kernel Authority. | `CH8-T24` → `BLOCKED_ON_HUMAN[PD-CH8-016]` | `CH8-T25` → `SATISFIED` |

- **Failure route:** Gate returns `BLOCKED_ON_HUMAN[PD-CH8-016]`; blocks patch ingestion; triggers developer escalation; prevents file modification.
- **Who may write:** Only the qualified protected-path gate evaluator writes evaluation records; kernel approvals require human cryptographic authorization via Kernel Authority APIs.
- **Kernel binding (frozen):** Binds to frozen `ApprovalSet` (`00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §2.2.1 L934-L940) and `CanonicalDependencySet` (§2.3 L498-L504).
- **NEVER:** Never permit path traversal to escape protected-path classification, never treat repository metadata as self-authorizing, and never bypass human approval for control-plane edits.
- **Cost bound:** Evaluator normalizes up to 2,000 paths per patch; string lengths capped at 1,024 bytes per path; resolution complexity O(paths × path depth); budget units: path count.
- **Fixtures:**
  - `CH8-T24` (Gaming / Path Traversal & Alias Bypass): Agent proposes a patch containing a disguised write to `.git/hooks/pre-commit` via traversal `src/../../.git/hooks/pre-commit` or symlink alias `link_to_git/hooks/pre-commit` without a canonical `ApprovalRecord` → Path normalizer resolves to canonical protected path → Gate returns `BLOCKED_ON_HUMAN[PD-CH8-016]`.
  - `CH8-T25` (Happy / Conforming Non-Protected Write): Agent proposes a patch modifying `src/sclass/product/gate.py` within authorized scope, with zero writes to protected paths → Gate returns `SATISFIED`.

### Fixture Specifications: `CH8-T24` & `CH8-T25`

```yaml
#### CH8-T24 — gaming fixture for PD-CH8-016
must_id: PD-CH8-016
fixture_role: gaming
input_binding: proposed write set containing disguised or unauthorized protected-path target
bound_inputs: [proposed_write_set, protected_path_registry, approval_record_ref]
attack_or_case: Agent attempts to write to control-plane hooks or CI configs via traversal or aliasing without approval
expected_gate_output: BLOCKED_ON_HUMAN[PD-CH8-016]
expected_action_result: BLOCKED
execution_evidence: UNVERIFIED
attack_variants:
  - id: A1
    description: "Directory traversal into .git/hooks"
    target_path: "src/../../.git/hooks/pre-commit"
    approval_record_ref: null
    expected_gate_output: BLOCKED_ON_HUMAN[PD-CH8-016]
  - id: A2
    description: "Direct edit to GitHub workflow without approval"
    target_path: ".github/workflows/verify.yml"
    approval_record_ref: null
    expected_gate_output: BLOCKED_ON_HUMAN[PD-CH8-016]
  - id: A3
    description: "Symlink evasion targeting .env secret config"
    target_path: "config/secrets.link" # points to .env
    approval_record_ref: null
    expected_gate_output: BLOCKED_ON_HUMAN[PD-CH8-016]
  - id: A4
    description: "NTFS alternate data stream alias"
    target_path: "pyproject.toml::$DATA"
    approval_record_ref: null
    expected_gate_output: BLOCKED_ON_HUMAN[PD-CH8-016]

#### CH8-T25 — happy fixture for PD-CH8-016
must_id: PD-CH8-016
fixture_role: happy
input_binding: conforming proposed write set modifying only application paths within authorized scope
bound_inputs: [proposed_write_set, protected_path_registry, approval_record_ref]
proposed_write_set:
  - "src/sclass/product/gate.py"
  - "tests/test_gate.py"
approval_record_ref: null
expected_gate_output: SATISFIED
expected_action_result: NONE
execution_evidence: UNVERIFIED
```

## 3.3 Grounding & Evidence Analysis
- **Evidence Label:** SOURCED from `FREEZE-CANDIDATE-v6.0.2/product/r29-companion/RESEARCH-NOTES-R29.md` §B (*"Agents game tests; the trajectory matters... EvilGenie: test-file edit detection is one of its methods... The Verification Horizon: tampering with the harness"*).
- **Unverified Aspects:** The exact list of protected extensions, NTFS ADS filtering heuristics, and path normalization libraries are **`UNVERIFIED`** in companion files and represent proposed engineering designs.

## 3.4 Formal Open Decision (Gate 6)

### `BLOCKED — AK DECISION REQUIRED (CH8-OI-006)`
- **Issue Summary:** Protected Path Registry Extensibility and Per-Repository Customization Policy.
- **Question for AK:** Shall the protected path registry be strictly immutable and built into the S-Class engine, or shall repositories be allowed to declare additive protected paths via an in-repo configuration?
- **Decision Options:**
  - **Option A:** Strict immutable engine-level registry covering hooks, `.git`, CI configs, and project manifests. Repositories cannot narrow or customize the list.
  - **Option B:** Engine-level baseline registry plus optional additive declarations via `.sclass/protected_paths.json`. Any modification to `.sclass/protected_paths.json` itself requires kernel `ApprovalRecord`.
  - **Option C:** Purely advisory warnings for configuration files, reserving hard `BLOCKED_ON_HUMAN` stops exclusively for `.git/**` and `.github/workflows/**`.

---

# SECTION 4: Diff-Level Review Engine (Area 4)

## 4.1 Specification & Boundary Requirements
- **Diff-Level Binding vs Agent Self-Summary:** Agents routinely produce self-descriptions that obscure, minimize, or misrepresent the actual code changes made (e.g. claiming a change is a "documentation fix" when it alters security invariants). The review engine MUST bind review evaluation directly to the concrete unified diff computed between the current workspace and the bound `TargetSnapshot` baseline.
- **Concrete Finding Coordinates:** Review findings must reference explicit diff coordinates:
  - `file_path`: Canonical target file path.
  - `hunk_index`: Zero-based index of the hunk within the file diff.
  - `line_start` / `line_end`: Exact source line numbers in the modified file.
  - `hunk_content_digest`: SHA-256 digest of the raw hunk content.
- **Non-Self-Approval Rule:** Agent self-summaries, commit messages, or self-reported pass claims have ZERO authority. A review finding can only be closed by qualifying test evidence or canonical human waiver under `PD-CH2-052`.
- **Handling Missing, Stale, Incomplete, or Unresolvable Diffs:**
  - If the unified diff cannot be computed, is missing, references an obsolete `TargetSnapshot`, contains truncated hunks, or fails coordinate resolution, the review gate MUST fail closed with `MISSING[PD-CH2-066]`.
- **Preservation of PD-CH2-052:** `PD-CH2-052` owns P9 finding aggregation and waiver rules. `PD-CH2-066` specifically governs diff-level grounding and the invalidation of agent summaries.

## 4.2 Proposed Normative MUST Specification: `PD-CH2-066`

| ID | Class | Decidable requirement | Gaming fixture | Happy fixture |
|---|---|---|---|---|
| `PD-CH2-066` | M | Review evaluation in P9 MUST bind directly to the concrete unified diff against the bound `TargetSnapshot` baseline; review findings MUST reference concrete `(file_path, hunk_index, line_range, hunk_digest)` coordinates; agent self-summaries, commit messages, or self-reports MUST NOT replace diff inspection; missing, stale, truncated, or unresolvable diffs MUST fail closed with `MISSING[PD-CH2-066]`. | `CH2-T77` → `MISSING[PD-CH2-066]` | `CH2-T78` → `SATISFIED` |

- **Failure route:** Gate returns `MISSING[PD-CH2-066]`; blocks P9 review progression; routes back to P6 for clean diff reproduction.
- **Who may write:** Only the qualified diff review evaluator writes `ReviewAssessment` records; agents propose diffs and findings but cannot self-close findings or certify review completion.
- **Kernel binding (frozen):** Binds to frozen `TargetSnapshot` (`00-SPEC` §12.6 L3841-L3845) and `AcceptanceContract` (§5 L2022-L2037).
- **NEVER:** Never evaluate agent text summaries in lieu of physical unified diffs, never permit unanchored review findings, and never accept a diff whose baseline snapshot digest mismatches.
- **Cost bound:** Evaluator inspects diffs up to 2 MiB total patch size and 1,000 hunks; review cost bounded by O(diff bytes); budget units: bytes and hunk count.
- **Fixtures:**
  - `CH2-T77` (Gaming / Misleading Summary & Post-Review Mutation):
    - *Variant A1 (Misleading Summary):* Agent presents summary "Updated logging only", but physical diff contains an alteration to `src/sclass/auth.py` disabling permission checks → Diff evaluator ignores summary, detects modified security hunk, flags unreviewed hunk → `MISSING[PD-CH2-066]`.
    - *Variant A2 (Post-Review Drift):* Review conducted against snapshot $S_1$, but workspace has mutated to snapshot $S_2$ prior to P9 sign-off → Baseline mismatch → `MISSING[PD-CH2-066]`.
    - *Variant A3 (Omitted / Truncated Hunk):* Diff contains malformed hunk header with incomplete line counts → Parser fails closed → `MISSING[PD-CH2-066]`.
  - `CH2-T78` (Happy / Fully Bound Conforming Diff Review): Conforming unified diff matching bound `TargetSnapshot` exactly, with every modified hunk mapped to qualified review findings and verified test coverage → returns `SATISFIED`.

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
    unified_diff_payload: "--- a/auth.py\n+++ b/auth.py\n@@ -10,3 +10,3 @@\n- return verify()\n+ return True"
    expected_gate_output: MISSING[PD-CH2-066]
  - id: A2
    description: "Diff generated against stale target snapshot"
    target_snapshot_ref: "snap-v1"
    workspace_snapshot_ref: "snap-v2"
    expected_gate_output: MISSING[PD-CH2-066]
  - id: A3
    description: "Truncated hunk with inconsistent line counts"
    unified_diff_payload: "@@ -10,15 +10,2 @@\n- invalid truncation"
    expected_gate_output: MISSING[PD-CH2-066]

#### CH2-T78 — happy fixture for PD-CH2-066
must_id: PD-CH2-066
fixture_role: happy
input_binding: complete unified diff bound to target snapshot with resolved hunk findings
bound_inputs: [target_snapshot_ref, unified_diff_payload, agent_summary, review_record]
target_snapshot_ref: "snap-v1"
unified_diff_payload: "--- a/math.py\n+++ b/math.py\n@@ -5,3 +5,3 @@\n- return a - b\n+ return a + b"
review_record:
  hunk_digest: "sha256-hunk-math-1"
  status: "RESOLVED"
  evidence_ref: "ev-test-pass-01"
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
- **Decision Options:**
  - **Option A:** Hard cutoff at 2 MiB total diff size; binary diffs and diffs exceeding 2 MiB fail closed with `BLOCKED_ON_HUMAN[PD-CH2-066]`, requiring manual human review.
  - **Option B:** Permit exclusion of pre-declared generated/vendored file patterns from deep hunk review if bound to an authorized hash manifest, focusing diff inspection on primary application source.
  - **Option C:** Streaming chunk-based evaluation without size cutoff, offloading hunks exceeding memory thresholds to an asynchronous background worker.

---

# SECTION 5: Symbol-Level Plan Checks (Area 5)

## 5.1 Specification & Boundary Requirements
- **Symbol-Level Granularity in P4 Planning:** Coarse file-level write sets can hide unintended coupling or blast radius. Symbol-level plan checks resolve planned mutation targets to fine-grained code symbols (functions, methods, classes, types, schemas).
- **Resolution Against Bound Repository Snapshot Index:** Planned symbol references must resolve against the bound AST index of the current `TargetSnapshot`.
- **Fail-Closed on Unresolved, Ambiguous, Stale, or Out-of-Coverage Symbols:**
  - If a symbol cannot be found in the snapshot index, matches multiple definitions without a disambiguating qualifier, or falls into an unindexed/out-of-coverage file, the check MUST fail closed with `MISSING[PD-CH2-067]`.
- **Symbol Identity vs Display Name:** A display string (e.g. `"validate"` or `"process_data"`) is NOT a symbol identity. Canonical symbol identity is defined as the tuple:
  $$\text{SymbolIdentity} = (\text{module\_path}, \text{qualname}, \text{signature\_digest})$$
- **Preservation of PD-CH8-012:** `PD-CH8-012` owns the requirement that repository intelligence disclose index coverage/freshness and that unresolved symbols remain `MISSING`. `PD-CH2-067` applies this rule specifically within P4 planning to validate planned task target sets.

## 5.2 Proposed Normative MUST Specification: `PD-CH2-067`

| ID | Class | Decidable requirement | Gaming fixture | Happy fixture |
|---|---|---|---|---|
| `PD-CH2-067` | M | Planned task mutation targets specified at symbol level MUST resolve against the bound repository snapshot index to canonical `(module_path, qualname, signature_digest)` tuples; unresolved, ambiguous, stale, or out-of-coverage symbol references MUST fail closed with `MISSING[PD-CH2-067]`; display names or agent labels MUST NOT substitute for symbol identity. | `CH2-T79` → `MISSING[PD-CH2-067]` | `CH2-T80` → `SATISFIED` |

- **Failure route:** Gate returns `MISSING[PD-CH2-067]`; halts P4 task decomposition; routes back to P4 replanning or P1 context discovery.
- **Who may write:** Only the qualified symbol resolution evaluator writes resolved target records; agents propose symbol targets but cannot declare resolution without index proof.
- **Kernel binding (frozen):** Binds to frozen `WorkNode` (`00-SPEC` §7 L2170-L2186) and `StateBinding` (§8.2 L2577-L2590).
- **NEVER:** Never infer a symbol target from fuzzy name matching, never accept a symbol without qualified module path, and never proceed when the repository index is stale.
- **Cost bound:** Evaluator resolves up to 500 symbols per task graph; index lookup bounded by O(symbols × log(index entries)); budget units: symbol count.
- **Fixtures:**
  - `CH2-T79` (Gaming / Ambiguous & Out-of-Coverage Symbol Targets):
    - *Variant A1 (Ambiguous Bare Name):* Task declares target symbol `"authenticate"` which exists in both `app.auth` and `app.legacy_auth` without module qualification → Ambiguous match → `MISSING[PD-CH2-067]`.
    - *Variant A2 (Deleted / Absent Symbol):* Task declares target `app.models.User.get_by_uuid` which does not exist in the bound AST index → Unresolved target → `MISSING[PD-CH2-067]`.
    - *Variant A3 (Out-of-Coverage File):* Task targets symbol in a file excluded from indexing per `PD-CH8-012` disclosure → Out of coverage → `MISSING[PD-CH2-067]`.
  - `CH2-T80` (Happy / Fully Qualified Conforming Symbol Target): Task targets fully qualified symbol `sclass.product.gate.evaluate_gate` resolving unambiguously in current snapshot AST index with matching signature digest → returns `SATISFIED`.

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
    symbol_target: "authenticate"
    expected_gate_output: MISSING[PD-CH2-067]
  - id: A2
    description: "Target symbol absent from current AST index"
    symbol_target: "sclass.core.nonexistent_function"
    expected_gate_output: MISSING[PD-CH2-067]
  - id: A3
    description: "Target located in file marked out-of-coverage by indexer"
    symbol_target: "vendor.third_party.parse"
    expected_gate_output: MISSING[PD-CH2-067]

#### CH2-T80 — happy fixture for PD-CH2-067
must_id: PD-CH2-067
fixture_role: happy
input_binding: fully qualified symbol resolving unambiguously in current index
bound_inputs: [planned_task_node, target_snapshot_index_ref]
symbol_target:
  module_path: "src/sclass/product/gate.py"
  qualname: "evaluate_predicate"
  signature_digest: "sha256-sig-eval-pred"
expected_gate_output: SATISFIED
expected_action_result: NONE
execution_evidence: UNVERIFIED
```

## 5.3 Grounding & Evidence Analysis
- **Evidence Label:** **`UNVERIFIED`** in companion research files.
- **Companion Grounding:** The research companion files focus on agent test gaming and host facts; they do not substantiate symbol-level plan resolution.
- **Master Grounding:** Grounded in Master §2.10 (P4 Task Decomposition units) and §8.5 (`PD-CH8-012` index disclosure).

## 5.4 Formal Open Decision (Gate 6)

### `BLOCKED — AK DECISION REQUIRED (P4-OI-001)`
- **Issue Summary:** Authoritative Symbol Indexing Engine and Multi-Language Indexing Scope.
- **Question for AK:** Which language indexing engine (e.g. Tree-sitter AST, SCIP/LSP index, Pyright/Jedi) shall be authoritative for symbol-level resolution in P4, and how shall non-Python languages in the v1 matrix be handled?
- **Decision Options:**
  - **Option A:** Qualify a Tree-sitter multi-language parser adapter under F10 supporting Python, Java, JavaScript, and TypeScript backend files.
  - **Option B:** Restrict symbol-level plan resolution strictly to Python in v1; other languages fall back to file-level task units without claiming symbol resolution.
  - **Option C:** Defer symbol-level plan validation to post-v1; treat planned symbol targets as advisory metadata within file-level write sets.

---

# SECTION 6: Section 3.6 Evaluation — Plan-versus-Diff Binding Delta

## 6.1 Directive Mandate & Question
Directive §3.6 instructs:
> "PD-CH4-014 already compares the observed delta with authorized scope. Do not create a second general diff-versus-scope requirement. Inspect whether the existing authorized scope is mechanically bound to the plan's declared write sets. If the binding is already fully specified, add nothing. If there is a genuine gap, propose only the narrow binding requirement necessary to connect the plan's declared write sets to the authorized scope evaluated by PD-CH4-014... If the master already establishes this binding, record **NO NEW MUST REQUIRED**."

## 6.2 Master Quotations & Systematic Analysis

### Quotation 1: Master §4.4 (L293800-293810) — Scope Lock Definition
> *"## 4.4 Scope lock*  
> *Trace: 'Compare proposed/observed mutation targets with canonical task scope and P4 declared writes. Known overlapping tasks serialize.'*  
> *Compare proposed/observed mutation targets with canonical task scope and P4 declared writes. Known overlapping tasks serialize. Unknown/undeclared write sets block human resolution. Launched workers are prevented from unauthorized writes inside the S-Class boundary; host-native writes can only be detected and a revert/quarantine requested."*

### Quotation 2: Master §4.4 (L293933) — Normative MUST `PD-CH4-014`
> *"### R5 normative closure — PD-CH4-014*  
> *| ID | Class | Decidable requirement | Gaming fixture | Happy fixture |*  
> *|---|---|---|---|---|*  
> *| PD-CH4-014 | M | An observed delta outside the authorized write/scope set MUST return BLOCKED and cannot be accepted by a green test run. | CH4-T19 → `MISSING[PD-CH4-014]` with `action_result: BLOCKED` | CH4-T20 → `SATISFIED` |"*

### Quotation 3: Master Appendix F (L620519-620530) — Fixture Binding for `PD-CH4-014`
> *"#### CH4-T19 — gaming fixture for PD-CH4-014*  
> *bound_inputs: [authorized_write_set_digest, observed_delta_digest, scope_revision_ref]*  
> *attack_or_case: An observed delta outside the authorized write/scope set MUST return BLOCKED and cannot be accepted by a green test run.*  
> *expected_gate_output: MISSING[PD-CH4-014]*  
> *expected_action_result: BLOCKED"*

### Quotation 4: Master §2.10 (L167476, L169833) — P4 Planning Write Sets & Overlap
> *"For parallel tasks, compare declared write sets mechanically: known overlap is serialized and SATISFIED; undeclared or unknown write sets are `BLOCKED_ON_HUMAN[PD-CH2-032]`. Never assume disjointness from missing data."*  
> *"Plan payload fields: plan_id, objective_revision, lane, task_nodes, dependency_edges, obligation_coverage, verifier_assignments, overlap_map, scope_digest, content_digest"*

## 6.3 Gap Analysis & Conclusion
1. **Existing Mechanical Binding:**  
   - Master §4.4 explicitly defines authorized scope as the comparison of mutation targets with *"canonical task scope and P4 declared writes"*.
   - The normative gate `PD-CH4-014` evaluates `authorized_write_set_digest` against `observed_delta_digest`.
   - `authorized_write_set_digest` is directly computed from the P4 `Plan.scope_digest` and declared task write sets.
   - Any observed mutation outside that declared set triggers `MISSING[PD-CH4-014]` with `action_result: BLOCKED`.
2. **Duplication Risk:**  
   - Proposing an additional MUST connecting declared write sets to scope would directly duplicate the decidable requirements of `PD-CH4-014`, `PD-CH2-032`, and `PD-CH8-011`.
3. **Formal Determination:**  
   - **`NO NEW MUST REQUIRED`**  
   - The existing master text and frozen fixture bindings already completely specify the mechanical binding between P4 planned write sets and `PD-CH4-014` scope enforcement.

---

## Section 7: Proposed MUST and Test Registry Allocation Additions

All proposed allocations are verified unallocated against `MUST-REGISTRY.md` and `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`:

| Proposed ID | Type | Allocation Status | Class | Proposed Requirement / Role Summary | Non-Collision Evidence |
|---|---|---|---|---|---|
| **`PD-CH8-014`** | MUST | PROPOSED (Non-Normative) | M | Structural Command Analyzer (AST/grammar, fail-closed, advisory boundary). | Ch8 allocated `008..013`; `014` is next clear slot. |
| **`PD-CH8-015`** | MUST | PROPOSED (Non-Normative) | M | Host-Control Verification by Active Probe (E0 downgrade, session binding). | Ch8 allocated `008..013`; `015` is clear slot. |
| **`PD-CH8-016`** | MUST | PROPOSED (Non-Normative) | M/E/J | Protected-Path Gate (path normalization, hooks/config/CI, kernel approval). | Ch8 allocated `008..013`; `016` is clear slot. |
| **`PD-CH2-066`** | MUST | PROPOSED (Non-Normative) | M | Diff-Level Review Engine (unified diff binding, hunk coordinates, anti-summary). | Ch2 allocated up to `065`; `066` is next clear slot. |
| **`PD-CH2-067`** | MUST | PROPOSED (Non-Normative) | M | Symbol-Level Plan Checks (P4 symbol resolution, AST index, fail-closed). | Ch2 allocated up to `065`; `067` is clear slot. |
| **`CH8-T20`** | Test | PROPOSED (Non-Normative) | Gaming | Adversarial evasion test for `PD-CH8-014` (quote, backslash, variable, eval). | Ch8 tests allocated `T8..T19`; `T20` is clear. |
| **`CH8-T21`** | Test | PROPOSED (Non-Normative) | Happy | Conforming parsed command test for `PD-CH8-014`. | Ch8 tests allocated `T8..T19`; `T21` is clear. |
| **`CH8-T22`** | Test | PROPOSED (Non-Normative) | Gaming | Stale/missing probe downgrade test for `PD-CH8-015` (`E0_ADVISORY`). | Ch8 tests allocated `T8..T19`; `T22` is clear. |
| **`CH8-T23`** | Test | PROPOSED (Non-Normative) | Happy | Conforming active probe receipt test for `PD-CH8-015`. | Ch8 tests allocated `T8..T19`; `T23` is clear. |
| **`CH8-T24`** | Test | PROPOSED (Non-Normative) | Gaming | Path traversal / unapproved write test for `PD-CH8-016` (`BLOCKED_ON_HUMAN`). | Ch8 tests allocated `T8..T19`; `T24` is clear. |
| **`CH8-T25`** | Test | PROPOSED (Non-Normative) | Happy | Conforming application write test for `PD-CH8-016`. | Ch8 tests allocated `T8..T19`; `T25` is clear. |
| **`CH2-T77`** | Test | PROPOSED (Non-Normative) | Gaming | Misleading summary / post-review drift test for `PD-CH2-066`. | Ch2 tests allocated up to `T76`; `T77` is clear. |
| **`CH2-T78`** | Test | PROPOSED (Non-Normative) | Happy | Conforming diff and hunk finding resolution test for `PD-CH2-066`. | Ch2 tests allocated up to `T76`; `T78` is clear. |
| **`CH2-T79`** | Test | PROPOSED (Non-Normative) | Gaming | Ambiguous / unresolved symbol target test for `PD-CH2-067`. | Ch2 tests allocated up to `T76`; `T79` is clear. |
| **`CH2-T80`** | Test | PROPOSED (Non-Normative) | Happy | Conforming fully qualified symbol target test for `PD-CH2-067`. | Ch2 tests allocated up to `T76`; `T80` is clear. |

---

## Section 8: Required Six-Gate Audit

In strict compliance with Section 6 of the Directive, each proposed area is audited across all six design gates using accurate statuses (`PASS`, `PARTIAL`, `BLOCKED`, `NOT APPLICABLE`):

| Design Gate | Area 1: Command Analyzer (`PD-CH8-014`) | Area 2: Host Probe (`PD-CH8-015`) | Area 3: Protected Path (`PD-CH8-016`) | Area 4: Diff Review (`PD-CH2-066`) | Area 5: Symbol Checks (`PD-CH2-067`) | Section 3.6 Binding Delta |
|---|---|---|---|---|---|---|
| **Gate 1: ID & Registry Collision** | **PASS** (`PD-CH8-014`, `CH8-T20..T21` verified clear) | **PASS** (`PD-CH8-015`, `CH8-T22..T23` verified clear) | **PASS** (`PD-CH8-016`, `CH8-T24..T25` verified clear) | **PASS** (`PD-CH2-066`, `CH2-T77..T78` verified clear) | **PASS** (`PD-CH2-067`, `CH2-T79..T80` verified clear) | **NOT APPLICABLE** (No new MUST required) |
| **Gate 2: Complete MUST Structure** | **PASS** (Full 8-part specification & YAML fixtures) | **PASS** (Full 8-part specification & YAML fixtures) | **PASS** (Full 8-part specification & YAML fixtures) | **PASS** (Full 8-part specification & YAML fixtures) | **PASS** (Full 8-part specification & YAML fixtures) | **NOT APPLICABLE** |
| **Gate 3: No Kernel Expansion** | **PASS** (Product projection only; no kernel types) | **PASS** (Binds to `SessionContext`; no kernel types) | **PASS** (Uses frozen `ApprovalSet`; no new kernel authority) | **PASS** (Binds to `TargetSnapshot`; no new kernel types) | **PASS** (Binds to `WorkNode`; no new kernel types) | **NOT APPLICABLE** |
| **Gate 4: Authority & Coverage** | **PASS** (Evaluator-only writes; `PD-CH8-008` preserved) | **PASS** (Active probe required; self-attestation rejected) | **PASS** (Canonical normalizer; unapproved blocks human) | **PASS** (Physical diff required; self-summary rejected) | **PASS** (AST index resolution; fuzzy matching rejected) | **NOT APPLICABLE** |
| **Gate 5: Evidence Grounding** | **PARTIAL** (Marked `UNVERIFIED`; no 12-bypass taxonomy in research) | **PARTIAL** (SOURCED `RESEARCH-NOTES-R29.md` §C; probe script `UNVERIFIED`) | **PARTIAL** (SOURCED `RESEARCH-NOTES-R29.md` §B; path heuristics `UNVERIFIED`) | **PARTIAL** (SOURCED `RESEARCH-NOTES-R29.md` §A, §B; size bounds `UNVERIFIED`) | **PARTIAL** (Derived from Master §2.10/§8.5; marked `UNVERIFIED`) | **NOT APPLICABLE** |
| **Gate 6: Unresolved Decisions** | **BLOCKED** (`CH8-OI-004` requires AK decision) | **BLOCKED** (`CH8-OI-005` requires AK decision) | **BLOCKED** (`CH8-OI-006` requires AK decision) | **BLOCKED** (`P9-OI-001` requires AK decision) | **BLOCKED** (`P4-OI-001` requires AK decision) | **NOT APPLICABLE** |

---

## Section 9: Consolidated Open-Decision Register

Every unresolved architectural choice is formally cataloged below with the mandatory `BLOCKED — AK DECISION REQUIRED` designation:

| Open Decision ID | Proposal Area | Summary of Unresolved Decision | Decision Options | Status |
|---|---|---|---|---|
| **`CH8-OI-004`** | Area 1: Command Analyzer | Shell grammar parsing standard (POSIX 1003.1 vs Bash 5.x) and normative adversarial evasion corpus. | Option A: POSIX 1003.1 AST parser; non-POSIX fail-closed.<br>Option B: Bash 5.x grammar with external adapter.<br>Option C: Defer to post-v1; operate advisory-only. | **BLOCKED — AK DECISION REQUIRED** |
| **`CH8-OI-005`** | Area 2: Host Probe | Active host probe execution transport and cross-platform isolation verification boundary. | Option A: Standalone binary probe via MCP stdio.<br>Option B: Host-specific capability negotiation endpoints.<br>Option C: Linux containers only; desktop IDEs unconditionally E0. | **BLOCKED — AK DECISION REQUIRED** |
| **`CH8-OI-006`** | Area 3: Protected Path | In-repository customization policy for protected control-plane paths. | Option A: Immutable engine-level registry.<br>Option B: Baseline registry + `.sclass/protected_paths.json`.<br>Option C: Advisory warnings for config files, hard block for `.git/**` only. | **BLOCKED — AK DECISION REQUIRED** |
| **`P9-OI-001`** | Area 4: Diff Review | Diff inspection size thresholds (2 MiB limit) and handling of binary/vendored files. | Option A: Hard 2 MiB cutoff; larger diffs block for human.<br>Option B: Manifest-based exclusions for generated files.<br>Option C: Streaming chunk-based evaluation without size cutoff. | **BLOCKED — AK DECISION REQUIRED** |
| **`P4-OI-001`** | Area 5: Symbol Checks | Authoritative symbol indexing engine and multi-language index qualification in v1. | Option A: Tree-sitter multi-language parser under F10.<br>Option B: Python-only symbol checks in v1.<br>Option C: Defer symbol checks to post-v1; file-level units only. | **BLOCKED — AK DECISION REQUIRED** |
