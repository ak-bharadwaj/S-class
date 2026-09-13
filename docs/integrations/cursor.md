# Cursor IDE Adapter

## Overview
The Cursor Adapter (`src/sclass/integrations/cursor/adapter.py`) interfaces with Cursor agent hooks and composer terminal executions.

## Features
- Captures terminal execution events from Cursor IDE.
- Inspects process identities for node, python, or bash child processes.
- Ensures file edits within Cursor stay within project boundary and cannot touch `.sclass/`.
