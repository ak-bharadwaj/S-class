# EGM Advisory Design-Review Pack

This pack vendors reviewer prompts from the [Google Elephant-Goldfish Model (EGM)](https://github.com/google/elephant-goldfish-model) (pinned commit `0997679a1cc3cfe09206160a85f9379f47101053`) under Apache-2.0.

## Scope & Advisory Status

- **Advisory Design-Review**: This pack provides advisory design-review prompts for workflow phases **P2–P4** (Specification Synthesis, Design & Architecture, and Task Planning).
- **Untrusted Claims**: Reviewer output is an **untrusted claim, never gate authority**. Advisory reviewer findings inform author revisions but possess zero authority to satisfy gates, grant approvals, or alter system state.
- **Qualification Status**: **UNQUALIFIED** (this pack has not undergone or passed F10 adapter qualification).

## Operating Rules & Constraints

1. **Independent Evaluator Protocol (Design F4 Independence)**:
   - Reviewers must run in **fresh, context-free sessions** without memory or state carryover from prior turns.
   - Where possible, reviewers must use a **different model or provider** from the authoring agent to provide authentic cognitive diversity and unconstrained critique.
2. **Standardized Severity Scale**:
   - **Blocker**: Core ambiguity, unparaphrasable specification section, missing technical interface/schema, or unexecutable requirement that halts progression.
   - **Major**: Significant omission, unhandled failure mode, or architectural risk requiring explicit remediation.
   - **Nit**: Minor documentation polish, stylistic note, or non-critical clarification.
3. **Bounded Review Cycle**:
   - The review process permits **at most one re-audit per stage**. After the authoring agent addresses initial findings, a single re-audit verifies remediation to prevent open-ended review thrashing.
