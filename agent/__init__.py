"""
S-Class EOS V11.2 - D7 Coding Agent Integration Layer (§8.1, §8.3).
Provides cognitive worker protocols, session management, capability-scoped tool registries,
RFC 8785 AgentMessage envelopes, and normalized action proposal synthesis for the D5 Controller.
"""

from agent.models import (
    AgentTurnStatus,
    ToolDefinition,
    AgentToolCall,
    AgentToolResult,
    AgentSessionContext,
    AgentTurnResponse,
    AgentSessionRecord,
    AgentMessage,
    create_agent_message,
    compute_agent_message_preimage,
    compute_agent_message_digest,
    GENESIS_DIGEST,
)
from agent.protocol import AgentWorkerProtocol, MockAgentWorker
from agent.tools import AgentToolRegistry
from agent.context import AgentContextBuilder
from agent.synthesizer import ActionProposalSynthesizer
from agent.session import AgentSessionManager

__all__ = [
    "AgentTurnStatus",
    "ToolDefinition",
    "AgentToolCall",
    "AgentToolResult",
    "AgentSessionContext",
    "AgentTurnResponse",
    "AgentSessionRecord",
    "AgentMessage",
    "create_agent_message",
    "compute_agent_message_preimage",
    "compute_agent_message_digest",
    "GENESIS_DIGEST",
    "AgentWorkerProtocol",
    "MockAgentWorker",
    "AgentToolRegistry",
    "AgentContextBuilder",
    "ActionProposalSynthesizer",
    "AgentSessionManager",
]
