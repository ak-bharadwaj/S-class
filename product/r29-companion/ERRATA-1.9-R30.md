# Erratum 1.9-R30: master §1.9 v1 product slice — STATUS: APPLIED in R30 (owner decision 2026-10-21, DECISIONS.md)
Process: master §10.5 / PD-CH10-012 (formal erratum path with insufficiency and replay analysis). §1.9 is a DRAFT product-layer section; the frozen v6.0.1 spec and 10-CONFORMANCE are untouched.

## Change request
Old text: v1 = Python backend, one MCP-capable IDE, enforcement E1. New text (master §1.9 in R30): hosts VS Code, Cursor, Codex, Antigravity over MCP; languages Python, Java, JavaScript, TypeScript (backend use); per-cell support level never rounded up; stack packs for Java/JavaScript/TypeScript authored and qualified under Chapter 6; evaluation includes a published comparison with a strongly prompted baseline; release mode invite-only preview withheld until the readiness bar passes. Work types (FEATURE, BUG_FIX) and domain (Backend) are unchanged; frontend frameworks are therefore outside the v1 domain unless the owner widens it later.

## Insufficiency analysis
The owner's release scope (wide matrix for reach and feedback) exceeded the R28 table; leaving the table unchanged would make the master contradict the intended product claim. A companion document cannot override a normative table, so the table is amended.

## Replay / impact analysis
- Changed: §1.9 table and one sentence below it; ledger word counts; this erratum; README/AUDIT-GUIDE/DECISIONS/OPEN-ISSUES text.
- Unchanged and checked by gates: all 195 MUST ids and wording, every fixture and gate output, the roster (NEW-CONCEPTS.txt regenerated, content equal except any counts), the frozen corpus and kernel bindings, PD-CH1-007 (floors are not lowered; "declared v1 slice" now refers to the amended table), PD-CH7-011 (per-cell E0/E1/E2 already required), PD-CH6-013 (v1 stack packs already required to reference qualified adapter families or block checks).
- Consequences accepted: Java, JavaScript and TypeScript playbook content does not yet exist in the master (only Python, Appendix B). It is authored as pack content under Chapter 6 and qualifies per cell (roadmap B13-B15). Until then those cells are unsupported or detect-only.
- Diff: gates/R30-edits.diff-u.txt.

## Not decided here
Whether frontend frameworks (e.g., React) enter the v1 domain: needs a further owner decision and likely a Domain row change. Telemetry: off in the preview (DECISIONS.md).
