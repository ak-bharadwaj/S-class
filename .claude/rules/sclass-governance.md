# S-Class Epistemic Governance (Claude Code Target)

## Active Session Context
- **FSM Phase**: `TRIAGE`
- **Active Goal**: Under Development
- **Pending Tasks**: 0 active
- **Knowledge Graph**: 3323 nodes, 4837 edges

## Non-Negotiable Engineering Directives
1. **Zero Hallucinated APIs**: Always verify existing symbols in `.agents/codebase_graph.db` or via MCP `graph_query` before inventing method names or endpoints.
2. **Blast Radius Discipline**: Running changes must consider downstream callers. Do not alter public signatures without an accepted ADR.
3. **Strict Verification**: Never claim a task is completed without running targeted unit tests (`pytest` or `npm test`).
4. **Completion Handshake**: Terminate completed task chunks with `<promise>TASK-ID:DONE</promise>`.
