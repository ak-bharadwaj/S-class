# OpenAI Codex Adapter

## Overview
The Codex Adapter (`src/sclass/integrations/codex/adapter.py`) integrates OpenAI Codex and related OpenAI tool-calling models.

## Operations
- Intercepts shell and python code execution calls.
- Enforces boundary policies against modifying protected trust roots or attempting shell escape.
- Binds task-level claims to independently observed execution receipts.
