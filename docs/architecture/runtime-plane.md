# Architecture: Runtime Plane vs Assurance Plane

## 1. Overview

S-Class establishes a strict dual-plane architecture that explicitly separates the **Execution Plane** from the **Assurance Plane**.

```text
                        USER / IDE
                            |
                            v
               +---------------------------+
               |      EXECUTION PLANE      |
               |                           |
               | Step-Code                 |
               | Claude Code               |
               | Codex                     |
               | Custom agent runtimes     |
               |                           |
               | sessions                  |
               | tools                     |
               | subagents                 |
               | retries                   |
               | workflows                 |
               | worktrees                 |
               | provider protocols        |
               | durable operation state   |
               +-------------+-------------+
                             |
                      runtime events
                      intents/actions
                      observations
                             |
                             v
               +---------------------------+
               |       S-CLASS CORE        |
               |     (ASSURANCE PLANE)     |
               |                           |
               | TASK                      |
               |   -> OBLIGATIONS          |
               |   -> CLAIMS               |
               |   -> POLICY               |
               |   -> AUTHORIZATION        |
               |   -> OBSERVATION          |
               |   -> EVIDENCE             |
               |   -> ASSESSMENT           |
               |   -> TRUTH STATE          |
               |   -> INVALIDATION         |
               |   -> FRONTIER             |
               |   -> RECOVERY             |
               |   -> REGRESSION           |
               |   -> COMPLETION           |
               |   -> ASSURANCE RECEIPT    |
               +-------------+-------------+
                             |
                             v
                  CANONICAL PROJECT TRUTH
```

## 2. Fundamental Boundary Invariant

> **Step-Code execution state != S-Class project truth.**

- **Execution state** records what the runtime environment and agent believe happened. It comprises tool exit codes, session trees, terminal streams, and provider responses.
- **Assurance state** represents what the project can legitimately be proven to have achieved based on independent observation, cryptographic provenance, and typed verification.

## 3. Epistemic Subordination of Execution

Under Absolute Laws L1 and L2:
- An agent stating "tests pass" or "task complete" has zero authoritative truth value.
- Runtime execution outputs are candidate evidence inputs into S-Class, never direct determinants of project truth.
