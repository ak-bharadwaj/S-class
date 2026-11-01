# Research Report: Structural Command Blocking & Evasion Taxonomy

**Document Reference:** `RESEARCH-COMMAND-BLOCKING.md`  
**Status:** Authoritative Research Grounding for `PD-CH8-014`  
**Scope:** Static and AST-Level Interception of Agent Command Tampering & Subshell Execution

---

## Bypass taxonomy (corpus classes)

Empirical evaluation of autonomous coding agents across adversarial benchmarks (SWE-bench adversarial evaluations, EvilGenie benchmark, and trajectory analyses of model-generated shell commands) identifies five recurring corpus classes of command-level evasion:

1. **Argument-Level Indirection & Split Flags:**
   - Invocations of benign utilities with arguments that trigger subshell execution, arbitrary command execution, or flag indirection (e.g. `find -exec`, `xargs`, `git -c core.pager=...`, `ssh -oProxyCommand=...`).
   - Split flags and option aliases (e.g. `-execdir`, `--exec`, `-o ProxyCommand=...` vs `-oProxyCommand=...`) used to evade naive token or substring filters.
2. **Environment Mutation & Loader Injection:**
   - Manipulation of execution environment variables targeting dynamic linker/loader hijacking (e.g. `LD_PRELOAD`, `NODE_OPTIONS`) or library search paths (`PYTHONPATH`, `PERLLIB`).
3. **Dynamic Evaluation Wrappers:**
   - Passing command strings to dynamic evaluators (`eval`, dynamic `source` / `.`), or piping encoded/decoded payload streams directly into shell interpreters (e.g. `echo ... | base64 -d | sh`).
4. **Dynamic Parameter & Command Substitutions:**
   - Concealing command words inside unresolved variable expansions (e.g. `CMD=rm; $CMD -rf /tmp`) or nested command substitutions (`$(...)`, `` `...` ``) that prevent static determination of the executable target.
5. **Name-Only Allowlist Evasion & Binary Substitution:**
   - Invoking alternative absolute paths (e.g. `/bin/bash` when a filter checks `bash`), symlinks, or alternative utility binaries.

*Research Distinction Note:* The research literature documents these general corpus classes of evasion. Specific adversarial test payloads authored for test suites—such as shell alias overriding (`alias pytest=true`), shell function declarations (`function git() { ... }`), custom shell environment variables (`BASH_ENV`, `IFS`), specific alternative tool binaries (`gawk`, `mawk`), and container escape commands (`nsenter`, Docker socket mounts)—are **proposed adversarial test examples derived from the research**, rather than explicitly cited items in the original research papers.

---

## What each host enforces (documented)

Empirical observation and platform documentation establish a critical distinction between execution host environments:

1. **Native Host / Desktop IDE Environments (`E0`):**
   - Uncontained native developer workstations and desktop IDE extensions (e.g. VS Code, Cursor, Windsurf) provide **no OS-level process isolation or filesystem write containment**.
   - Processes are spawned under the ambient user identity and permissions.
   - S-Class tool mediation operating in an IDE can inspect command strings and block its own tool dispatch, but **cannot prevent direct host execution** or OS-level writes outside S-Class mediation.
   - Per Master §8.4 (`PD-CH8-008`), prevention honesty strictly prohibits claiming host-native write prevention outside a qualified launched container. Desktop IDE environments are unconditionally classified as `E0` (advisory / detection-only).
2. **Supervised Worker Environments (`E1`):**
   - Supervised execution environments where tool dispatch is mediated and monitored.
   - Commands with identified security risks or unverified constructs cannot execute automatically; they must halt execution and transition to human authorization (`gate_state: BLOCKED_ON_HUMAN`, `action_result: BLOCKED`).
3. **Launched Linux Containers (`E2`):**
   - Fully contained Linux worker containers launched directly by the S-Class harness with active boundary controls.
   - Isolation boundaries are enforced at the OS/kernel level: mount namespaces with read-only root filesystems, PID namespaces (visible host PIDs == 0), isolated network namespaces (no unauthorized default routes), cgroup v2 resource limits, and enforced seccomp BPF syscall filters.
   - Only in `E2` does the system enforce genuine **OS/container boundary prevention**.

---

## How a third party can verify controls

A third party or evaluator cannot verify execution boundary controls through passive self-attestation:

1. **Inadequacy of Self-Attestation:**
   - An agent or host environment cannot be trusted to report its own isolation capabilities via environment variables (e.g. `$CONTAINER`, `$IS_SANDBOX`), configuration flags, or host-reported endpoints. Host facts (such as current UID) are discoverable, but host control is not.
2. **Active Probe Verification:**
   - Active boundary verification requires executing an independent active probe harness prior to worker dispatch.
   - The probe attempts capability-specific assertions: testing whether write operations to the root filesystem trap and fail with `EROFS` (read-only filesystem), whether restricted syscalls (e.g. `ptrace`, `kexec_load`, `reboot`) are blocked by seccomp BPF, whether visible host PID count is zero, and whether default network egress is blocked.
3. **Cryptographic Grounding via ApprovalSet:**
   - Probe results must be signed by an authority enrolled in the frozen `ApprovalSet` principal directory and validated via `validate_approval_set`.
   - If active probe verification fails, is stale, or is absent, the environment automatically degrades to `E0` (degraded mode), disabling automated workspace promotion.

---

## Design-relevant conclusions

The empirical research leads to five mandatory design conclusions for S-Class Block 1:

1. **Pre-Dispatch Static AST Analysis (`PD-CH8-014`):**
   - Command inspection must parse candidate commands into ASTs using a formal POSIX 1003.1 grammar baseline before process creation. Token or substring allowlisting is trivially bypassed by split flags, indirection arguments, or dynamic expansions.
2. **Fail-Closed Policy for Unclassified Constructs:**
   - Any syntax error, unsupported shell grammar (e.g. Bash process substitution `<(...)`), unclassified binary, or unresolvable dynamic command-word expansion MUST fail closed (DENY or `gate_state: BLOCKED_ON_HUMAN` with `action_result: BLOCKED`). Never allow by default.
3. **Honesty About Prevention Boundaries:**
   - S-Class must explicitly distinguish between:
     - *Blocking S-Class mediated tool dispatch* (`action_result: BLOCKED`).
     - *Detecting a risky operation* (`risk_level: HIGH` finding emitted; `action_result: NONE` under `E0`).
     - *Preventing execution at an OS/container boundary* (`action_result: BLOCKED` under `E2`).
     - *Halting workflow progression pending human decision* (`gate_state: BLOCKED_ON_HUMAN`).
   - Desktop IDE environments (`E0`) must never be described as providing OS-level prevention.
4. **Pre-Write Interception for Agent-Written Files (`PD-CH8-016`):**
   - Protection cannot be limited to files immediately executed by the writing agent. Agent writes targeting control-plane paths, IDE configs, build wrappers, scripts, or Git hooks must be intercepted pre-write before disk persistence.
   - The execute bit (`0755`) is neither necessary nor sufficient evidence of future unsandboxed execution; interpreter scripts (`0644`), build files, and configuration hooks are executed by unsandboxed host processes without execute bits.
5. **Direct Unified Diff Inspection with Size Bounds (`PD-CH2-066`):**
   - Review evaluation must inspect concrete unified diff hunks against `TargetSnapshot` with 100% hunk coverage; agent summaries have zero authority.
   - Diffs exceeding the hard 2 MiB cutoff ($2{,}097{,}152\text{ bytes}$) fail closed immediately.
