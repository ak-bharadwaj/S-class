# S-Class Implementation Guide

S-Class architecture is partitioned into authoritative subsystems under src/sclass/:

1. control/: Authorization gates, capability evaluations, and security policies.
2. xecution/: Subprocess spawning, process tree analysis, and ExecutionIdentity.
3. observation/: Platform-specific process observers and ObservationLifecycleTracker.
4. 	rust/: Append-only LocalLedger and cryptographic provenance receipts.
5. erification/: Independent verifiers, claim evaluation matrix, and state machine.
6. context/: Zero-drift cross-agent handoff packaging and workspace checkpoints.
7. state/: Persistent SQLite repository for tasks, claims, and projects.
