# CLAUDE.md - S-Class V12 Control Plane Directives

## Active Operational State
- **Current FSM Phase**: `TRIAGE`
- **Active Goal**: Autonomous Build Feature
- **Knowledge Graph Scale**: 3307 symbols indexed across 294 files.

## Primary Verification Commands
- **Run Pytest Regression**: `python -m pytest tests/`
- **Knowledge Graph Query**: Use FastMCP tool `graph_query` or `impact_analysis`
- **FSM State Advance**: `python -m runtime advance`

## Negative Invariants (NEVER DO THIS)
- NEVER suppress exceptions with bare `except: pass`.
- NEVER bypass visual verification gates with mock or zero-variance images.
- NEVER invent dependencies not registered in public package registries.
