# S-Class product definition (workflow + features), derived from R28 master; nothing here changes the frozen design
Source anchors: master §1.1 (product definition), §1.9 (v1 slice), §1.10 (non-goals), Chapter 2 (P0-P11), Chapters 4-8. Where this file adds product wording, it is marked PRODUCT-BRIEF and needs owner approval; it never overrides a MUST.

## 1. One-sentence product
S-Class is the engineering control plane under a developer's IDE: the IDE and its agent write code; S-Class decides, from authoritative state and admissible evidence, whether a step may proceed and whether work is actually complete. Thesis (§1.1): proof, not the agent's self-report.

## 2. Who uses it and why they would switch (PRODUCT-BRIEF, owner to confirm)
- Developer using an AI coding agent in VS Code / Cursor / Codex / Antigravity who is tired of "done" claims that are false (tests not run, scope exceeded, requirements skipped).
- Tech lead who needs an auditable trail: what was asked, what changed, what evidence says it works.
Value in one line each: (a) the agent cannot declare completion without evidence; (b) every change stays inside an authorised scope; (c) work resumes correctly after interruption; (d) there is a replayable audit trail.

## 3. End-to-end workflow (what a developer experiences)
The lifecycle is the same for every project (P0-P11); tech stacks plug in as packs (Ch.6).
| Moment | What the developer sees | Phase / mechanism |
|---|---|---|
| Open task | `session_open`: S-Class binds task, repo snapshot, policy, pinned packs | P0 intake, Engineering Profile, work type (FEATURE, BUG_FIX in v1 slice) |
| Understand repo | agent receives only admissible context; unknowns listed, not guessed | P1 discovery; incomplete index = MISSING, never assumed complete |
| Agree what "done" means | requirements and acceptance criteria written, developer approves/rejects | P2, human gate |
| Design if needed | architecture/domain decision recorded as a claim, checked mechanically | P3 |
| Plan | decomposition with obligation-to-verifier coverage | P4 |
| Tests first | test design and a valid red run | P5 |
| Implement | `next_step` tells the agent the next justified action; `patch_validate` checks the patch against authorised scope; out-of-scope write = block | P6, ExecutionGate inside a launched boundary |
| Verify | fresh, independent, admissible evidence; green test run alone is not enough | P7 |
| Repair | bounded retries on one budget, then escalate | P8 |
| Review | findings resolved or explicitly waived by the developer | P9 |
| Release | readiness and rollback evidence; kernel ReleaseEvaluation | P10 |
| Afterwards | regressions/incidents re-enter at P0 | P11 |
At any block the developer sees: what is missing (gate id), why, the next legal action, and can approve / reject / waive / escalate (§1.9 governance).

## 4. Feature list (grouped; each is owned by MUSTs in the master)
1. Lifecycle guidance: session_open, next_step, patch_validate, status (Ch.2, Ch.7).
2. Engineering gates with exactly three results SATISFIED | MISSING[ids] | BLOCKED_ON_HUMAN[ids] (F5, Ch.5).
3. Evidence and independence: admissible, fresh, non-self-reviewed (Ch.4).
4. Scope authorisation and write-boundary: prevention only for workers S-Class launches; host-native edits are detected, never claimed prevented (PD-CH8-008).
5. Knowledge plane: versioned packs per stack, resolution precedence, signature/licence/provenance checks, revocation, pinning (Ch.6).
6. Workspace operations: worktrees, concurrent/out-of-band edit detection, re-snapshot, promotion with rollback evidence (Ch.8).
7. Developer governance: approve, reject, waive, escalate; notifications derived from gate projections only (Ch.7).
8. Audit and replay: canonical event history, export with sequence range and digests (§10.2).
9. Evaluation: sloppy-agent suite and false-completion rate (Ch.9) — see EVALUATION-PLAN.md.
10. Compatibility/versioning across kernel, protocol, schema, adapter, pack (§10.1).

## 5. Scope conflict that needs an owner decision (found while reading the master; erratum text in ERRATA-PROPOSAL-1.9.md, OI-046)
Master §1.9 fixes the v1 slice to: work types FEATURE and BUG_FIX; backend; Python; E1 enforcement; ONE MCP-capable IDE. Owner direction (2026-10-21) is v1 = VS Code, Cursor, Codex, Antigravity x Java, Python, JavaScript, TypeScript. That is a different scope from a frozen normative table. PD-CH1-007 allows v1 to be limited but forbids lowering floors; it does not authorise widening §1.9 silently. Options:
 A. Keep §1.9 as the "v1.0 proof slice" (first release gate) and ship the 16-cell matrix as the v1 release train; no master change, wording only in the release notes.
 B. Erratum / R29 revision amending §1.9 to the 4x4 matrix (change control: new revision, diff, rerun, owner signs).
Recommendation: A for the proof, B before any public "v1 supports N IDEs" claim.

## 6. Out of scope for this file (separate PRODUCT-BRIEF, owner decision): pricing, branding, marketing, onboarding docs, support. §1.10 lists non-goals (not an IDE, not a model, not an agent loop, not a CI platform, not a workflow engine, ...).
