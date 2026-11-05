# AUDIT GUIDE — S-Class v6.0.2 design package, candidate R30
Read this first. It tells you what is normative, what is not, how to re-run every check, and what is NOT evidenced.

## 1. What this package is
- Normative design: S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md (single file; 195 MUSTs; 64 section markers: 10 ACCEPTED foundations F1-F10, 54 DRAFT; Appendix fixtures: 66 gaming/happy pairs, 189 variants). Frozen kernel spec v6.0.1 is bundled in frozen-v6.0.1/ and is never edited.
- Frozen baseline: R28 (qualified baseline, product/r29-companion/FREEZE-DECISION-R28.md; master sha256 508fc017924736ad6d1739fcca81b0a9923dcdf2061b3f81e46448bfb02a8c98). R29 added non-normative companion documents only. R30 = R29 + erratum 1.9-R30: master §1.9 amended to the host-by-language matrix; all 195 MUST ids/wording, fixtures and kernel bindings unchanged (diff: gates/R30-edits.diff-u.txt). R30 needs its own owner sign-off.
- Companion (non-normative, product/r29-companion/): PRODUCT-DEFINITION, EVALUATION-PLAN, RESEARCH-NOTES-R29, V1-SCOPE-MATRIX, ROADMAP, HANDOFF-PROTOCOL, DECISIONS, STATUS, ERRATA-PROPOSAL-1.9, briefs/.

## 2. Suggested reading order
1) README-FREEZE-CANDIDATE.md (history and stamp) 2) master §1 (product definition, hierarchy, trust model, v1 slice, non-goals) 3) master Chapter 2 (lifecycle P0-P11) 4) Chapters 4, 5, 8 (evidence, gates, enforcement) 5) F1-F10 (accepted foundations) 6) product/r29-companion/DECISIONS.md, PRODUCT-DEFINITION.md, EVALUATION-PLAN.md, RESEARCH-NOTES-R29.md, ROADMAP.md 7) product/OPEN-ISSUES.md.

## 3. Re-run everything
`bash RERUN.sh` (about 1 minute, python3 + PyYAML; fail-closed; per-gate output). Gate meaning and limits: gates/README-GATES.md. Expected: ALL GATES PASSED. gates/chk_release_ready.py (sign-off gate) is expected to FAIL on this draft (8 findings) until the independent review and owner form exist.

## 4. What passing the gates means and does not mean
Means: structure, registries, fixtures parse and bind to required inputs, gate vocabulary closed, frozen citations resolve, counts consistent, manifest intact. Does NOT mean: the design is correct, any fixture was executed against a kernel, the 189 variant dispositions are independent (review/VARIANT-DISPOSITIONS.txt is a self-review), or the product beats blind prompting.

## 5. Known limitations (stated, not hidden)
- Prose gate cannot detect a new kernel state named by a bare ordinary word with no declaration phrase; enforcement belongs to the kernel enum test (roadmap B04). 
- OI-003/OI-034: fixtures have never run on a real kernel. OI-031: 11 artifact types shape-only. OI-036: five owner-held external documents absent. OI-015: OSS addendum choice open. Owner decisions unsigned. 
- §1.9 now states the wide matrix (erratum applied in R30), but only Python has fully specified playbook content (Appendix B); Java/JavaScript/TypeScript pack content is absent (OI-053) and frontend frameworks are outside the domain (OI-054).
- Research notes cite public sources read on 2026-10-21; Antigravity MCP facts and hook support are UNVERIFIED.
- Implementation repo (github.com/ak-bharadwaj/S-class) is audited separately; the first scan was rejected for wrong citations (see briefs/ANTIGRAVITY-BRIEF-00b).

## 6. Suggested audit questions
Does each MUST have exactly one defining row, one gaming and one happy fixture? Does any section let the product layer add kernel states/events/enums or a second state machine? Does any claim of prevention exist outside a launched boundary? Is any unknown treated as PASS? Are the roadmap exit tests real and measurable? Is the evaluation plan able to falsify the thesis?
