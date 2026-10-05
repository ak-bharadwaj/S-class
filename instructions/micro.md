# Micro & Small-Fix Execution Protocol

When executing in MICRO or SMALL_FIX profiles:
- Minimize overhead: execute directly without spawning subagents.
- Focus narrowly on the target lines and files requested.
- Run a targeted verification (linter, unit test, or syntax check).
- Transition state to DONE upon verification without demanding full visual QA or safety-case packs.
- Keep diff clean, minimal, and free of scope creep.
