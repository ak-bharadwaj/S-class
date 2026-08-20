"""
S-Class EOS V11.2 - D7 Coding Agent Integration Layer (§8.1, §8.3).
Provides cognitive worker protocols, session management, capability-scoped tool registries,
RFC 8785 AgentMessage ingress validation, and normalized action proposal synthesis for D5.
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
    D7_INTERNAL_ACCOUNTING_UNIT,
)
from agent.protocol import (
    AgentWorkerProtocol,
    AgentMessageChainValidator,
    MockAgentWorker,
)
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
    "D7_INTERNAL_ACCOUNTING_UNIT",
    "AgentWorkerProtocol",
    "AgentMessageChainValidator",
    "MockAgentWorker",
    "AgentToolRegistry",
    "AgentContextBuilder",
    "ActionProposalSynthesizer",
    "AgentSessionManager",
]
