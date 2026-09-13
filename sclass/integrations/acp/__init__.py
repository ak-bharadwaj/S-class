"""
S-Class ACP Integration: Agent Client Protocol proxy and bridge (STRUCTURALLY COMPLETE protocol interceptor prototype).
"""

from sclass.integrations.acp.decision_bridge import ACPDecisionBridge
from sclass.integrations.acp.proxy import ACPProxy

__all__ = ["ACPDecisionBridge", "ACPProxy"]
