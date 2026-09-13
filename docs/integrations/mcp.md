# MCP (Model Context Protocol) Adapter

## Overview
The S-Class MCP Adapter (`src/sclass/integrations/mcp/adapter.py`) connects Model Context Protocol servers and clients to S-Class control plane.

## Protected Resource Shielding (Attack J Mitigation)
Even if an MCP tool claims to be "safe" (e.g. `read_resource` or `safe_file_write`), if its target argument touches a protected trust root (`.sclass/ledger.jsonl`, `sclass.db`, `trust_anchors.json`), the MCP adapter gates the operation and rejects it before tool invocation.

## Tool Identity
MCP tools are tracked via `MCPToolIdentity`:
- Server URI and name
- Tool name
- Parameter schema
- Declared and inferred capabilities
