"""
S-Class Multi-Agent Fleet: Agent Registry & Session Lifecycle (RC.9).
Manages:
- Dynamic registration and deregistration of subagents.
- Active heartbeat tracking and liveness monitoring.
- Stale agent detection and automated dead-lease cleanup.
- Subagent state transitions (ACTIVE, IDLE, QUARANTINED, COMPLETED, FAILED).
"""

from __future__ import annotations
import time
from typing import Dict, Any, List, Optional

from sclass.agent_fleet.models import AgentIdentity, AgentStatus
from sclass.core.errors import FleetIntegrityError


class AgentSessionManager:
    """Manages the registry and lifecycle of autonomous subagents in the fleet."""

    def __init__(self, heartbeat_timeout: float = 60.0):
        self.heartbeat_timeout = heartbeat_timeout
        self.agents: Dict[str, AgentIdentity] = {}
        self.heartbeats: Dict[str, float] = {}

    def register(
        self,
        agent_id: str,
        role: str = "worker",
        platform_id: str = "antigravity",
        assigned_paths: Optional[List[str]] = None,
        claimed_symbols: Optional[List[str]] = None,
        base_revision: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentIdentity:
        """Registers a new agent session or refreshes an existing one."""
        identity = AgentIdentity(
            agent_id=agent_id,
            role=role,
            platform_id=platform_id,
            status=AgentStatus.ACTIVE,
            assigned_paths=list(assigned_paths or []),
            claimed_symbols=list(claimed_symbols or []),
            base_revision=base_revision,
            registered_at=time.time(),
            metadata=dict(metadata or {}),
        )
        self.agents[agent_id] = identity
        self.heartbeats[agent_id] = time.time()
        return identity

    def deregister(self, agent_id: str) -> bool:
        """Removes an agent from the active registry upon clean termination."""
        if agent_id in self.agents:
            self.agents[agent_id].status = AgentStatus.COMPLETED
            self.heartbeats.pop(agent_id, None)
            return True
        return False

    def heartbeat(self, agent_id: str) -> float:
        """Records a keep-alive heartbeat from an active agent."""
        if agent_id not in self.agents:
            raise FleetIntegrityError(f"Cannot record heartbeat for unregistered agent '{agent_id}'.")
        now = time.time()
        self.heartbeats[agent_id] = now
        if self.agents[agent_id].status == AgentStatus.IDLE:
            self.agents[agent_id].status = AgentStatus.ACTIVE
        return now

    def is_healthy(self, agent_id: str, timeout_seconds: Optional[float] = None) -> bool:
        """Returns True if the agent is registered and has sent a heartbeat within timeout."""
        if agent_id not in self.agents:
            return False
        agent = self.agents[agent_id]
        if agent.status in (AgentStatus.QUARANTINED, AgentStatus.FAILED):
            return False
        t_limit = timeout_seconds if timeout_seconds is not None else self.heartbeat_timeout
        last_hb = self.heartbeats.get(agent_id, agent.registered_at)
        return (time.time() - last_hb) <= t_limit

    def get_stale_agents(self, timeout_seconds: Optional[float] = None) -> List[AgentIdentity]:
        """Identifies all registered agents that have missed their heartbeat deadline."""
        t_limit = timeout_seconds if timeout_seconds is not None else self.heartbeat_timeout
        now = time.time()
        stale = []
        for aid, agent in self.agents.items():
            if agent.status in (AgentStatus.COMPLETED, AgentStatus.QUARANTINED):
                continue
            last_hb = self.heartbeats.get(aid, agent.registered_at)
            if (now - last_hb) > t_limit:
                stale.append(agent)
        return stale

    def cleanup_stale_leases(self, fleet_engine: Any, timeout_seconds: Optional[float] = None) -> List[str]:
        """
        Detects dead/stale agents and revokes all held resource leases,
        preventing permanent deadlock in multi-agent swarms.
        """
        stale_agents = self.get_stale_agents(timeout_seconds=timeout_seconds)
        cleaned_leases = []
        for agent in stale_agents:
            agent.status = AgentStatus.FAILED
            # Revoke leases in fleet engine
            if hasattr(fleet_engine, "state") and hasattr(fleet_engine.state, "leases"):
                for path, lease in list(fleet_engine.state.leases.items()):
                    if lease.holder_agent_id == agent.agent_id:
                        if hasattr(fleet_engine, "release_lease"):
                            fleet_engine.release_lease(agent.agent_id, path)
                            cleaned_leases.append(path)
            # Revoke claimed symbols in fleet engine
            if hasattr(fleet_engine, "state") and hasattr(fleet_engine.state, "claimed_symbols"):
                for sym_key, holder in list(fleet_engine.state.claimed_symbols.items()):
                    if holder == agent.agent_id:
                        if hasattr(fleet_engine, "release_symbol_work"):
                            fleet_engine.release_symbol_work(agent.agent_id, sym_key)
        return cleaned_leases

    def get_agent(self, agent_id: str) -> Optional[AgentIdentity]:
        return self.agents.get(agent_id)

    def list_agents(self, status: Optional[AgentStatus] = None) -> List[AgentIdentity]:
        if status:
            return [a for a in self.agents.values() if a.status == status]
        return list(self.agents.values())

    def mark_status(self, agent_id: str, status: AgentStatus, reason: Optional[str] = None) -> AgentIdentity:
        if agent_id not in self.agents:
            raise FleetIntegrityError(f"Agent '{agent_id}' not found in registry.")
        agent = self.agents[agent_id]
        agent.status = status
        if reason:
            agent.quarantine_reason = reason
        return agent
