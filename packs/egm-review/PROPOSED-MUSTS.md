# Proposed Spec-Quality MUST Checks (Advisory Errata Proposal)

> **Status**: PROPOSAL ONLY — NOT A MUST CHANGE.
> This document outlines two candidate spec-quality checks for consideration in the master errata process. It does not introduce, modify, or enforce any normative MUST requirement in current specifications, runtime gates, or conformance suites.

---

## Candidate Check (a): Paraphrase Check (Zero-Context Comprehension)

### Proposed Intent
Ensure every normative section of a specification or design document is fully intelligible on its own merits without reliance on unspoken conversational context or unstated assumptions.

### Mechanism
1. A zero-context reader agent (instantiated in a fresh session with independent model/provider per design F4 independence) is provided only the specification section under review.
2. The reader agent paraphrases the section's core requirements, invariants, and failure boundaries.
3. If any section cannot be paraphrased unambiguously, or if the reader must guess author intent:
   - The finding is marked as a **Blocker**.
   - The section is classified as unparaphrasable, halting progression through P2/P3 until the authoring agent rewrites the section with complete clarity.

---

## Candidate Check (b): Implementation-Readiness Check (Deterministic Plan)

### Proposed Intent
Eliminate implementation ambiguity by verifying that architectural plans provide exhaustive, concrete technical specifications before code modification begins in P4/P5.

### Mechanism
1. Prior to exiting task planning (P4), the implementation plan is evaluated against deterministic readiness criteria:
   - **File Paths**: The plan must name exact file paths for all files created, modified, or deleted.
   - **Data Structures**: The plan must define concrete data structures, schema fields, and state transitions.
   - **Signatures**: The plan must specify complete class, function, and method signatures (including argument types, return types, and error semantics).
   - **Zero Implementer Choice**: The plan must leave no design choice or architectural decision to the implementer agent.
2. If any path, data model, signature, or architectural decision is deferred to the implementer or left open-ended:
   - The finding is marked as a **Blocker**.
   - Progression to implementation is halted until the plan specifies all technical details deterministically.
