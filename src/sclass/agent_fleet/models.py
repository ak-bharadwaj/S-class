"""
S-Class Multi-Agent Fleet Integrity Models (Phase 15 / B.15).

Defines typed representations for:
- Subagent identity, role, and lifecycle status.
- Granular workspace resource leases (read/write).
- Multi-agent conflict classifications (concurrency, duplicate work, conflicting assumptions).
- Fleet state snapshots and evidence merge results.
"""

from __future__ import annotations
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Set


class AgentStatus(str, Enum):
    """Lifecycle status of a subagent within the fleet."""
    ACTIVE = "ACTIVE"
    IDLE = "IDLE"
    QUARANTINED = "QUARANTINED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class LeaseType(str, Enum):
    """Granular access mode for workspace resource leases."""
    EXCLUSIVE_WRITE = "EXCLUSIVE_WRITE"
    SHARED_READ = "SHARED_READ"


class ConflictType(str, Enum):
    """Classification of multi-agent concurrency and integrity conflicts."""
    CONCURRENT_MUTATION = "CONCURRENT_MUTATION"
    STALE_BRANCH_MUTATION = "STALE_BRANCH_MUTATION"
    CONFLICTING_ASSUMPTIONS = "CONFLICTING_ASSUMPTIONS"
    DUPLICATE_WORK = "DUPLICATE_WORK"
    QUARANTINE_VIOLATION = "QUARANTINE_VIOLATION"


@dataclass
class AgentIdentity:
    """Represents a member subagent within the parallel fleet."""
    agent_id: str
    role: str
    platform_id: str = "antigravity"
    status: AgentStatus = AgentStatus.ACTIVE
    assigned_paths: List[str] = field(default_factory=list)
    claimed_symbols: List[str] = field(default_factory=list)
    base_revision: str = ""
    quarantine_reason: Optional[str] = None
    registered_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "platform_id": self.platform_id,
            "status": self.status.value if isinstance(self.status, AgentStatus) else str(self.status),
            "assigned_paths": list(self.assigned_paths),
            "claimed_symbols": list(self.claimed_symbols),
            "base_revision": self.base_revision,
            "quarantine_reason": self.quarantine_reason,
            "registered_at": self.registered_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentIdentity:
        status_val = data.get("status", AgentStatus.ACTIVE.value)
        status = AgentStatus(status_val) if status_val in AgentStatus._value2member_map_ else AgentStatus.ACTIVE
        return cls(
            agent_id=data.get("agent_id", ""),
            role=data.get("role", "worker"),
            platform_id=data.get("platform_id", "antigravity"),
            status=status,
            assigned_paths=list(data.get("assigned_paths", [])),
            claimed_symbols=list(data.get("claimed_symbols", [])),
            base_revision=data.get("base_revision", ""),
            quarantine_reason=data.get("quarantine_reason"),
            registered_at=float(data.get("registered_at", time.time())),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ResourceLease:
    """Active lease on a workspace path to prevent race conditions."""
    lease_id: str
    path: str
    holder_agent_id: str
    lease_type: LeaseType = LeaseType.EXCLUSIVE_WRITE
    acquired_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 300.0)

    def is_expired(self, current_time: Optional[float] = None) -> bool:
        now = current_time if current_time is not None else time.time()
        return now > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lease_id": self.lease_id,
            "path": self.path,
            "holder_agent_id": self.holder_agent_id,
            "lease_type": self.lease_type.value if isinstance(self.lease_type, LeaseType) else str(self.lease_type),
            "acquired_at": self.acquired_at,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ResourceLease:
        lt_val = data.get("lease_type", LeaseType.EXCLUSIVE_WRITE.value)
        lease_type = LeaseType(lt_val) if lt_val in LeaseType._value2member_map_ else LeaseType.EXCLUSIVE_WRITE
        return cls(
            lease_id=data.get("lease_id", str(uuid.uuid4())[:8]),
            path=data.get("path", ""),
            holder_agent_id=data.get("holder_agent_id", ""),
            lease_type=lease_type,
            acquired_at=float(data.get("acquired_at", time.time())),
            expires_at=float(data.get("expires_at", time.time() + 300.0)),
        )


@dataclass
class ConflictEvent:
    """Detailed record of an integrity conflict between fleet subagents."""
    conflict_id: str
    conflict_type: ConflictType
    agents_involved: List[str]
    resource_target: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    resolved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "conflict_type": self.conflict_type.value if isinstance(self.conflict_type, ConflictType) else str(self.conflict_type),
            "agents_involved": list(self.agents_involved),
            "resource_target": self.resource_target,
            "details": dict(self.details),
            "timestamp": self.timestamp,
            "resolved": self.resolved,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ConflictEvent:
        ct_val = data.get("conflict_type", ConflictType.CONCURRENT_MUTATION.value)
        conflict_type = ConflictType(ct_val) if ct_val in ConflictType._value2member_map_ else ConflictType.CONCURRENT_MUTATION
        return cls(
            conflict_id=data.get("conflict_id", str(uuid.uuid4())[:8]),
            conflict_type=conflict_type,
            agents_involved=list(data.get("agents_involved", [])),
            resource_target=data.get("resource_target", ""),
            details=dict(data.get("details", {})),
            timestamp=float(data.get("timestamp", time.time())),
            resolved=bool(data.get("resolved", False)),
        )


@dataclass
class FleetState:
    """Comprehensive snapshot of fleet state."""
    agents: Dict[str, AgentIdentity] = field(default_factory=dict)
    leases: Dict[str, ResourceLease] = field(default_factory=dict)
    claimed_symbols: Dict[str, str] = field(default_factory=dict)
    assumptions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    conflicts: List[ConflictEvent] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agents": {k: v.to_dict() for k, v in self.agents.items()},
            "leases": {k: v.to_dict() for k, v in self.leases.items()},
            "claimed_symbols": dict(self.claimed_symbols),
            "assumptions": dict(self.assumptions),
            "conflicts": [c.to_dict() for c in self.conflicts],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FleetState:
        agents = {k: AgentIdentity.from_dict(v) for k, v in data.get("agents", {}).items()}
        leases = {k: ResourceLease.from_dict(v) for k, v in data.get("leases", {}).items()}
        conflicts = [ConflictEvent.from_dict(c) for c in data.get("conflicts", [])]
        return cls(
            agents=agents,
            leases=leases,
            claimed_symbols=dict(data.get("claimed_symbols", {})),
            assumptions=dict(data.get("assumptions", {})),
            conflicts=conflicts,
        )


@dataclass
class FleetMergeResult:
    """Outcome of merging multi-agent receipts into verified project state."""
    merged_claims: List[Dict[str, Any]] = field(default_factory=list)
    invalidated_claims: List[Dict[str, Any]] = field(default_factory=list)
    conflicts: List[ConflictEvent] = field(default_factory=list)
    quarantined_agents: List[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        """True if merge completed without conflicts or invalidations."""
        return len(self.conflicts) == 0 and len(self.invalidated_claims) == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "merged_claims": list(self.merged_claims),
            "invalidated_claims": list(self.invalidated_claims),
            "conflicts": [c.to_dict() for c in self.conflicts],
            "quarantined_agents": list(self.quarantined_agents),
            "is_clean": self.is_clean,
        }
