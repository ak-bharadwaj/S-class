# S-Class Protocol Specifications

S-Class establishes native boundaries with external agent protocols:

1. **ACP (Agent Communication Protocol)**:
   - Client and agent session lifecycle.
   - Filesystem read/write interception.
   - Terminal command execution gating.
   - See [ACP Integration](../integrations/acp.md).

2. **MCP (Model Context Protocol)**:
   - Stateless tool and resource routing (2026-07-28 standard).
   - Header-level verification (MCP-Protocol-Version, Mcp-Method, Mcp-Name).
   - Tool identity and argument hashing.
   - See [MCP Integration](../integrations/mcp.md).
