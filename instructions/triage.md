# Phase: TRIAGE

Objectives:
- Inspect the user's objective and measure task complexity via multi-signal scoring.
- Select the minimal safe workflow profile (MICRO, SMALL_FIX, BUG_FIX, CORE, or FULL).
- If the request is purely informational, bypass FSM processing immediately.
- Determine whether frontend UI, database, or backend systems are affected.
- Transition forward to the next state using `dispatch_event("triage_done")`.
