#!/usr/bin/env python3
"""S-Class MCP Server tool facade."""
from sclass.mcp import SClassMCPServer, create_mcp_app, main

__all__ = ["SClassMCPServer", "create_mcp_app", "main"]

if __name__ == "__main__":
    main()
