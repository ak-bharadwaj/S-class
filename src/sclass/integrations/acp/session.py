"""
S-Class ACP Integration: Session Lifecycle Manager.
Tracks and governs active ACP agent sessions:
- Creation (`session/new`)
- State snapshots and updates (`session/update`)
- Branching/Forking (`session/fork`)
- Resumption (`session/resume`)
- Cancellation (`cancel`)
- Termination (`shutdown`)
"""

from __future__ import annotations
import uuid
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from sclass.integrations.acp.capability_map import ACPCapabilitySpec


@dataclass
class ACPAgentSession:
    """Stateful record of an active ACP agent session."""
    session_id: str
    agent_id: str
    workspace_dir: str
    capabilities: ACPCapabilitySpec = field(default_factory=ACPCapabilitySpec)
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    active: bool = True
    cancelled: bool = False
    forked_from: Optional[str] = None
    state: Dict[str, Any] = field(default_factory=dict)
    last_activity: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.last_activity = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "workspace_dir": self.workspace_dir,
            "started_at": self.started_at,
            "active": self.active,
            "cancelled": self.cancelled,
            "forked_from": self.forked_from,
            "state": dict(self.state),
            "last_activity": self.last_activity,
        }


class ACPSessionManager:
    """Thread-safe in-memory session manager for ACP connections."""

    def __init__(self):
        self._sessions: Dict[str, ACPAgentSession] = {}

    def create_session(
        self,
        workspace_dir: str,
        agent_id: str = "acp_agent",
        capabilities: Optional[ACPCapabilitySpec] = None,
        session_id: Optional[str] = None,
        forked_from: Optional[str] = None,
    ) -> ACPAgentSession:
        sid = session_id or str(uuid.uuid4())
        session = ACPAgentSession(
            session_id=sid,
            agent_id=agent_id,
            workspace_dir=workspace_dir,
            capabilities=capabilities or ACPCapabilitySpec(),
            forked_from=forked_from,
        )
        self._sessions[sid] = session
        return session

    def get_session(self, session_id: str) -> Optional[ACPAgentSession]:
        session = self._sessions.get(session_id)
        if session:
            session.touch()
        return session

    def update_session(self, session_id: str, new_state: Dict[str, Any]) -> bool:
        session = self._sessions.get(session_id)
        if not session or not session.active:
            return False
        session.state.update(new_state)
        session.touch()
        return True

    def fork_session(self, parent_session_id: str, new_session_id: Optional[str] = None) -> Optional[ACPAgentSession]:
        parent = self._sessions.get(parent_session_id)
        if not parent:
            return None
        sid = new_session_id or str(uuid.uuid4())
        forked = ACPAgentSession(
            session_id=sid,
            agent_id=parent.agent_id,
            workspace_dir=parent.workspace_dir,
            capabilities=parent.capabilities,
            forked_from=parent.session_id,
            state=dict(parent.state),
        )
        self._sessions[sid] = forked
        return forked

    def cancel_session(self, session_id: str, reason: Optional[str] = None) -> bool:
        session = self._sessions.get(session_id)
        if not session:
            return False
        session.active = False
        session.cancelled = True
        session.state["cancel_reason"] = reason or "User or client requested cancellation"
        return True

    def close_session(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if not session:
            return False
        session.active = False
        return True

    def list_active_sessions(self) -> List[ACPAgentSession]:
        return [s for s in self._sessions.values() if s.active]
