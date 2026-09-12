# 🚀 CONTINUE_HERE.md — S-Class Session Continuity Guide

> **Notice**: This repository is governed by the S-Class V12 Epistemic Control Plane.
> All incoming agents (Cursor, Claude Code, Codex CLI, Antigravity) must resume from this state.

---

## 📍 Current System Status
- **FSM Phase**: `RELEASE`
- **Active Goal**: implement binary search tree
- **Active Task**: `None (Advance phase)`
- **Pending Tasks Remaining**: 0
- **Handoff Timestamp**: `2026-09-12T16:06:20.839699+00:00`

## ⚡ Next Resumption Command
```bash
python -m runtime advance
```


## 🛠️ Operating Rules for the Incoming Agent
1. **Never Assume**: Check `.agents/codebase_graph.db` using MCP `graph_query` before inventing symbols.
2. **Test Before Complete**: Verify implementation against real test fixtures.
3. **Promise Handshake**: Terminate completion with `<promise>TASK_ID:DONE</promise>`.
