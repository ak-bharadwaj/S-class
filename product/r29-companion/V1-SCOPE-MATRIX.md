# S-Class v1 scope matrix (owner decision 2026-10-21; claims follow qualification, master PD-CH6-013, PD-CH7-011, PD-CH8-008)
Hosts (4): VS Code, Cursor, Codex, Antigravity. Languages (4): Java, Python, JavaScript, TypeScript, each with its main frameworks as pack content.
Protocol path for every host: MCP (master Chapter 7). Host facts (extension API, MCP support, versions, OS behaviour) are UNVERIFIED until Brief 02 records them per host/version.

## Cell levels (a cell is host x language; each claim needs its own qualification record)
- QUALIFIED: version-pinned positive and negative tests passed on the named OS/version; full claim allowed (prevention only inside an S-Class-launched worker boundary).
- DETECT-ONLY (E0/E1): gate and observation work; no prevention claim for host-native edits.
- UNSUPPORTED: refused or routed to a human.
All 16 cells start as UNSUPPORTED. A cell moves up only with raw test evidence reviewed by Claude. No cell is promoted by Antigravity's say-so.

## Build order (does not change release scope)
1. Reference path: kernel + Python pack + VS Code via MCP. Defect finder, not a release.
2. Widen by shared code: Cursor and Antigravity (both expected to be VS Code-family: verify, do not assume), then Codex.
3. Languages by pack: Python -> TypeScript/JavaScript -> Java.
4. Frameworks are pack content under a language, qualified separately (default proposal: Python pytest + Django/FastAPI; JS/TS Jest/Vitest + Node/React; Java JUnit + Maven/Gradle + Spring). Owner to confirm or edit.

## Release rule
v1 ships the table with each cell's actual level. A cell below QUALIFIED is shown as such; it is never rounded up. Minimum bar to call v1 released: owner sets it (suggestion: every host QUALIFIED for at least one language, every language QUALIFIED on at least one host, the rest DETECT-ONLY with documented limits).

## Release mode (owner, 2026-10-21)
First release is an INVITE-ONLY preview, withheld until the readiness bar in DECISIONS.md passes. Telemetry is off in the preview.
