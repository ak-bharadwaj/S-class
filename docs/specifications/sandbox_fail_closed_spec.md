# Layer D — Sandbox Fail-Closed Invariant

## 1. Core Principle
*NO SANDBOX -> NO SANDBOXED EXECUTION.*

Under no circumstances may an execution request that specifies sandbox isolation
fall back to unisolated host execution if the requested sandbox runtime is unavailable.

## 2. Supported Isolation Providers
1. **BubblewrapProvider (`bwrap`)**: Linux unprivileged user namespaces.
2. **OCIProvider (`docker` / `podman`)**: Standard container baseline.
3. **GVisorProvider (`runsc`)**: Application kernel virtualization.

## 3. Failure Demarcation
If a container binary fails health checks or does not exist on PATH,
the execution gate must throw `SandboxUnavailableError` immediately.
