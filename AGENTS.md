# AGENTS.md — S-Class Sovereign Agent Behavioral Standards

## 1. Epistemic Rigor & Anti-Hallucination Mandate
- Inspect before Infer: Always inspect existing schema, database models, and route definitions before proposing modifications.
- Never invent unrequested capabilities, mockup data, or phantom APIs.
- Enforce strict type validation and contractual verification on all changes.

## 2. Deterministic Execution & Safety Invariants
- Honor Layer-0 FileLock concurrency control.
- All state transitions must pass through the formal Kernel FSM.
- Release candidates require authentic cryptographic verification proofs.
