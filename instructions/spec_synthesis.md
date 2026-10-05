# Phase: SPECIFICATION_SYNTHESIS

Objectives:
- Enforce Rule 30: Extract explicit requirements from user goals and project files.
- Track every assumption explicitly in the assumption ledger with confidence ratings.
- Differentiate between EXPLICIT, DERIVED, and CONFLICT requirements.
- Never invent phantom tables, unrequested authorization systems, or fake third-party dependencies.
- If unresolvable contradictions exist, trigger `dispatch_event("spec_conflict_detected")` for human clarification.
- When requirements are grounded and verified, advance via `dispatch_event("spec_synthesized")`.
