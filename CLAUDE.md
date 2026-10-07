# CLAUDE.md - S-Class v6 Control Plane Directives

## Active Operational State
- **Control Plane Version**: S-Class v6.0.0
- **Supported Profiles**: QUESTION, MICRO, SMALL_FIX, BUG_FIX, CORE, HOTFIX, FAST, REFACTOR, FULL
- **Enforcement Mode**: Deterministic zero-trust hooks (Antigravity, Cursor, Copilot, CLI)

## Primary Verification Commands
- **Run Pytest Regression**: `python -m pytest tests/`
- **Run S-Class CLI**: `python sclass_cli.py classify "goal"` or `sclass classify "goal"`
- **Install Zero-Bypass Hooks**: `python sclass_cli.py install --platform all --strict --git-hook`

## Negative Invariants (NEVER DO THIS)
- NEVER suppress exceptions with bare `except: pass`.
- NEVER bypass visual verification gates with mock or zero-variance images.
- NEVER invent dependencies not registered in public package registries.
