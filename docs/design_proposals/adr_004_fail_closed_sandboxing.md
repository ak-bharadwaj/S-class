# ADR-004: Fail-Closed Sandboxing Policy

## Status
Accepted

## Context
When container runtimes (OCI, Bubblewrap, gVisor) fail or are absent on host machines,
fallbacks to unsandboxed host execution can cause catastrophic system compromises.

## Decision
We enforce a strict fail-closed invariant: *NO SANDBOX -> NO SANDBOXED EXECUTION.*
If a designated sandbox runtime is unavailable, the execution gate raises `SandboxUnavailableError` and halts.
