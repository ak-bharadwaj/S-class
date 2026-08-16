"""
S-Class EOS Port Conflict Resolver Engine (port_resolver.py)

Scans local TCP ports to locate free, available ports for dev servers (Next.js, Vite, Express, FastAPI).
Prevents EADDRINUSE server crashes and passes active URLs to Chrome DevTools MCP.
"""

import socket
import logging
from typing import Optional

logger = logging.getLogger("sclass_port_resolver")


class PortConflictResolver:
    """
    Port Conflict Resolver Engine for S-Class V12.
    """

    @classmethod
    def is_port_available(cls, port: int, host: str = "127.0.0.1") -> bool:
        """Returns True if the port is free to bind."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, port))
                return True
        except OSError:
            return False

    @classmethod
    def find_available_port(cls, preferred_port: int = 3000, max_attempts: int = 50) -> int:
        """Finds the first available port starting from preferred_port. If range is exhausted, asks OS for ephemeral port."""
        for port in range(preferred_port, preferred_port + max_attempts):
            if cls.is_port_available(port):
                logger.info(f"[PortResolver] Preferred port {preferred_port} resolved to available port {port}")
                return port
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("", 0))
                assigned_port = s.getsockname()[1]
                logger.warning(f"[PortResolver] Preferred port range ({preferred_port}-{preferred_port+max_attempts}) exhausted. Assigned ephemeral port {assigned_port}")
                return assigned_port
        except Exception:
            return preferred_port
