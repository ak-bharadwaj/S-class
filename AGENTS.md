# AGENTS.md - Operational Contract & Architectural Directives

## Execution Environment & Governance Limits
- **FSM Engine**: S-Class EOS v6 Adaptive Engineering Guard
- **State Database**: `.agents/codebase_graph.db` (SQLite WAL mode)

## Behavioral Constraints & Quality Laws
1. **The Cardinal Rule**: Always scan the existing codebase and inspect models, routes, and schemas before inferring or writing new code.
2. **Atomic Conventional Commits**: All modifications must use format `feat(scope): ...` or `fix(scope): ...`.
3. **Subagent Scoping**: Edits are strictly constrained to files within assigned task targets.
4. **Anti-Hallucination**: No fake APIs, unreferenced external dependencies, or unverified claims.
5. **Verified Evidence**: Never claim completion without passing unit/integration tests with real assertions.
