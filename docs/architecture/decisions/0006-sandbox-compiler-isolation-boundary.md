# ADR 0006: Sandbox Compiler and Execution Isolation Boundary

## Status
Accepted

## Context
Running arbitrary agent-generated commands poses security risks to developer workstations and CI runners. Relying on host-only execution leaves developer files, credentials, and network accessible to malicious or mistaken commands. Conversely, treating sandbox tools (like Bubblewrap or Docker) as the security policy conflates isolation mechanisms with authorization logic.

## Decision
1. Explicitly separate security policy from execution isolation mechanisms.
2. Establish an `ExecutionBackend` abstraction with implementations for:
   - `HostExecutionBackend`: Native local execution for trusted host environments.
   - `BubblewrapExecutionBackend`: Low-overhead, unprivileged namespace sandbox on Linux.
   - `gVisorExecutionBackend`: High-isolation user-space virtualization for untrusted workloads.
   - `DaggerExecutionBackend`: Hermetic container pipeline execution.
3. S-Class compiles declarative policy constraints into backend-specific sandbox flags (read-only binds, unshare-net, masked env vars).
4. Regardless of the backend used, S-Class independently observes the process lifecycle via `ExecutionIdentity` and seals the resulting `ObservedReceipt`.

## Consequences
- **Positive**: Clear boundary between policy and isolation; easily swappable backends per OS and threat tier.
- **Negative**: Sandbox availability varies by host OS (Bubblewrap is Linux only; Windows relies on host job objects or containers).
- **Invariants Upheld**: Invariant I3 (Observations originate from S-Class controlled execution), Invariant I8 (Unknown security state fails closed).
