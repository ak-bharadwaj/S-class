# Subsystem Evaluation: Execution & Sandboxing Backends

## 1. Subsystem Scope & Requirements
The Execution Subsystem isolates and executes commands permitted by policy, while capturing authoritative OS-level process observation.
Key requirements:
1. **Multi-Tier Isolation**: Support ranging from unconstrained local host execution to unprivileged Linux sandboxing and strong container virtualization.
2. **Independent Observation**: S-Class must independently capture PID, executable hash, start time, exit code, and stdout/stderr hashes regardless of the backend.
3. **Cross-Platform Portability**: Functional on Linux, macOS, and Windows.
4. **Policy-Driven Sandbox Compilation**: S-Class compiles declarative policy constraints (read-only directories, writable workspace, network disabled) into backend-specific arguments.

---

## 2. Candidates Evaluated

| Candidate | Architecture | Strengths | Weaknesses | S-Class Fit |
| :--- | :--- | :--- | :--- | :--- |
| **Host Process Runner (`subprocess`)** | Direct OS execution | Zero setup, universal cross-platform, native speed | No filesystem or network isolation without OS job objects | **Default Local Tier (`HostExecutionBackend`)** |
| **Bubblewrap (`bwrap`)** | Linux namespaces (user, mount, net, pid) | Unprivileged execution, zero root daemon, sub-5ms startup, standard on Linux | Linux only; requires unprivileged user namespaces | **Primary Linux Sandbox (`BubblewrapBackend`)** |
| **gVisor (`runsc`)** | User-space application kernel virtualization | Near-VM level security boundary, intercepts syscalls, immune to host kernel exploits | Higher startup overhead (~50-100ms), requires Linux kernel or Docker runtime | **High-Risk Sandbox (`gVisorBackend`)** |
| **Dagger** | Programmable container pipelines (BuildKit) | Completely hermetic, distributed caching, reproducible across CI and local | Container daemon dependency, startup latency penalty | **CI & Reproducibility Tier (`DaggerBackend`)** |

---

## 3. Sandboxing Architecture

```
                    S-Class Policy Decision
                               │
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
     Allow Direct Host                     Allow Isolated
            │                                     │
            ▼                                     ▼
   HostExecutionBackend                Sandbox Argument Compiler
            │                          (translates policy to bwrap/gvisor)
            │                                     │
            │                  ┌──────────────────┴──────────────────┐
            │                  ▼                                     ▼
            │         BubblewrapBackend                        gVisorBackend
            │                  │                                     │
            └──────────────────┼─────────────────────────────────────┘
                               ▼
                   ExecutionObservationFactory
            (PID, binary hash, start_time, exit_code, digests)
                               │
                               ▼
                   Authoritative ObservedReceipt
```

### Architectural Principle: "Policy != Isolation Primitive"
Bubblewrap and gVisor are isolation primitives, NOT security policies. S-Class policy specifies *what is allowed* (e.g. `workspace-only`, `network=false`, `env=sanitized`). S-Class compiles these constraints into isolation flags and passes them to the backend.

---

## 4. Architectural Decision
- **Host Process**: Default for trusted developer tools and cross-platform baselines.
- **Bubblewrap**: Wrap as primary Tier 2 sandboxing backend on Linux.
- **gVisor & Dagger**: Extend as pluggable backends for untrusted code execution and hermetic CI reproduction.
