# Handoff protocol (applies to every step; nobody skips a stage)
Authority: R28 baseline. Actors: AK (owner, decides/signs), AG (Antigravity, builds), CL (Claude, specifies/verifies/accepts), GPT (optional hostile reviewer).

## The only legal flow of one step
1. CL -> AG: BRIEF-NN (file). Contains: goal, in-scope files, out-of-scope, MUST ids touched, exact commands to run, required evidence, acceptance checklist, "stop and ask" triggers.
2. AG -> CL: DELIVERY-NN (a branch/commit sha + folder delivery-NN/ with evidence.txt, logs, summary.md). AG may not say "done/pass/verified"; it states facts with commands and output.
3. CL verifies (cheap): clones the sha, opens cited lines, re-runs ONE named test command, runs the diff guards (below). Result file: REVIEW-NN.md with verdict ACCEPT / ACCEPT-WITH-FIXES / REJECT and a numbered list of findings.
4. If not ACCEPT: CL -> AG: BRIEF-NNb (only the fixes). Repeat 2-3. Max 3 rounds, then AK is asked.
5. CL updates STATUS.md and the MUST tracker. Only CL changes a MUST's status. AK is told in 5 lines.
6. AK decisions are written into DECISIONS.md with date (never only in chat).

## Rules AG must follow in every brief
- Work only on the named branch from the named base sha. No merges, tags, force-push, history rewrite.
- Every claim = command + raw output or file:line produced by grep -n / wc -l pasted in evidence.txt. No line numbers from memory. Unknown = write UNVERIFIED.
- Do not edit 00-SPEC/ or 10-CONFORMANCE/. Do not add kernel events, states or enums, a second state machine, or agent-writable trust fields. If a change seems needed, STOP and open an ERRATA-REQUEST-NN.md (what, why, hunk, alternatives); CL and AK decide.
- Tests: report exact command, exit code, passed/failed/skipped counts, failing test names, and whether each failure is env or code.
- Scope: touching a file not listed in the brief = reject until explained.

## Diff guards CL runs on every delivery (mechanical)
G1 sha256 of 00-SPEC/* and 10-CONFORMANCE/* equals baseline sha list (B01 records it). G2 grep for new EventType members / state names versus state-machines.v6.0.1.json. G3 files changed vs brief scope list. G4 secrets scan. G5 test count never decreases, no test deleted/skipped without a reason in summary.md. G6 every cited line opens and says what is claimed (sample >= 20%, all boundary-related).

## Statuses
Step: BRIEFED -> DELIVERED -> ACCEPTED | REJECTED. MUST: NOT STARTED -> FIXTURE RAN (raw log) -> ACCEPTED (CL review). Matrix cell (host x language): UNSUPPORTED -> DETECT-ONLY -> QUALIFIED (CL + evidence; AK ratifies QUALIFIED).

## Stop-and-ask triggers (AG must stop, not guess)
Need to edit frozen files; a MUST cannot be implemented as written; a test cannot run in the environment; two docs disagree; any security-boundary design choice; anything destructive (delete, force-push, history rewrite).

## Files (all in repo under governance/, committed only by CL-approved delivery)
ROADMAP.md, STATUS.md, DECISIONS.md, briefs/BRIEF-NN.md, deliveries/delivery-NN/, reviews/REVIEW-NN.md, MUST-TRACKER.tsv, MATRIX.tsv.
