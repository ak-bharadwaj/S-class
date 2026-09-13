# Generic Integration Adapter

## Overview
The Generic Adapter (`src/sclass/integrations/generic/adapter.py`) serves as a baseline integration layer for custom CLI scripts, unknown agent frameworks, or direct subprocess invocations.

## Behavior
- Translates standard POSIX/Windows CLI commands into `ActionRequest`.
- Defaults to strict boundary isolation and enforces `ExecutionMode.HOST_ARGV` when possible.
