# Phase: DEBATE

Objectives:
- Subject proposed design specifications to multi-agent adversarial red-teaming (`sclass_grill.py`).
- Evaluate across 5 threat dimensions: edge cases, data integrity, security bounds, latency, and UX fidelity.
- Challenge ungrounded assumptions with concrete failure modes.
- If revisions are required, trigger `dispatch_event("revisions_required")`.
- When consensus score >= 80%, advance via `dispatch_event("spec_approved")` or `dispatch_event("no_changes_required")`.
