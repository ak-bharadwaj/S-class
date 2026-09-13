# Claude Adapter

## Overview
The Claude Adapter (`src/sclass/integrations/claude/adapter.py`) interfaces with Anthropic Claude Code CLI and Claude agent harnesses.

## Capabilities & Normalization
- Normalizes `Edit`, `Write`, `Bash`, `Glob`, `Grep` tool calls into standard `ActionRequest` objects.
- Hooks into Claude's bash tool invocation to route commands through S-Class `observe_command()`.
- Strips any self-reported test summaries from Claude; delegates test pass/fail determination entirely to S-Class verifiers.
