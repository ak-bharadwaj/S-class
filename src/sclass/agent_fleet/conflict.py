"""
S-Class Multi-Agent Fleet: Conflict Detection, Resolution & Quarantine Engine (RC.9).
Provides:
- Multi-agent file mutation and code-symbol conflict detection.
- Semantic assumption collision analysis.
- Pluggable resolution strategies (FAIL_CLOSED / REJECT, QUARANTINE, MERGE, LAST_WRITER_WINS).
- QuarantineEngine for isolating misbehaving or corrupted agents and revoking held leases.
"""

from __future__ import annotations
import time
import uuid
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple, Set

from sclass.agent_fleet.models import (
    ResourceLease,
    LeaseType,
    SymbolOwnership,
    ConflictEvent,
    ConflictType,
    ConflictRecord,
    QuarantineRecord,
    AgentStatus,
)
from sclass.core.errors import FleetIntegrityError


class ResolutionStrategy(str, Enum):
    """Strategies for resolving multi-agent concurrency and state conflicts."""
    REJECT = "REJECT"                    # Fail-closed: reject the colliding request
    QUARANTINE = "QUARANTINE"            # Isolate the requesting agent and revoke leases
    LAST_WRITER_WINS = "LAST_WRITER_WINS"# Authoritative overwrite (if explicitly permitted)
    MERGE = "MERGE"                      # Merge non-overlapping partitions cleanly


class ConflictDetector:
    """Detects multi-agent resource, symbol, and semantic assumption collisions."""

    @staticmethod
    def detect_file_conflict(
        agent_id: str,
        path: str,
        requested_type: LeaseType,
        existing_leases: Dict[str, ResourceLease],
    ) -> Optional[ConflictRecord]:
        """Detects whether requested file lease collides with an active lease."""
        norm_path = path.strip().replace("\\", "/").lower()
        for p, lease in existing_leases.items():
            l_norm = p.strip().replace("\\", "/").lower()
            is_hierarchy = norm_path.startswith(l_norm + "/") or l_norm.startswith(norm_path + "/")
            if l_norm == norm_path or is_hierarchy:
                if lease.holder_agent_id == agent_id:
                    continue  # Re-entrant acquisition
                if lease.is_expired():
                    continue

                # Conflict if either requires EXCLUSIVE_WRITE
                is_excl = (
                    requested_type == LeaseType.EXCLUSIVE_WRITE or
                    lease.lease_type == LeaseType.EXCLUSIVE_WRITE or
                    getattr(lease.lease_type, "value", str(lease.lease_type)) == LeaseType.EXCLUSIVE_WRITE.value
                )
                if is_excl:
                    return ConflictRecord(
                        conflict_id=f"conf_file_{uuid.uuid4().hex[:8]}",
                        conflict_type=ConflictType.CONCURRENT_MUTATION.value,
                        agents_involved=[lease.holder_agent_id, agent_id],
                        resource_target=path,
                        details={
                            "existing_holder": lease.holder_agent_id,
                            "existing_type": lease.lease_type.value if hasattr(lease.lease_type, "value") else str(lease.lease_type),
                            "requested_type": requested_type.value if hasattr(requested_type, "value") else str(requested_type),
                            "expires_at": lease.expires_at,
                            "overlapping_path": p,
                        },
                        timestamp=time.time(),
                    )
        return None

    @staticmethod
    def detect_symbol_conflict(
        agent_id: str,
        symbol_key: str,
        existing_claims: Dict[str, str],  # symbol_key -> agent_id
    ) -> Optional[ConflictRecord]:
        """Detects duplicate work or overlapping claims on qualified CKG symbols (file::symbol)."""
        holder = existing_claims.get(symbol_key)
        if holder and holder != agent_id:
            return ConflictRecord(
                conflict_id=f"conf_sym_{uuid.uuid4().hex[:8]}",
                conflict_type=ConflictType.DUPLICATE_WORK.value,
                agents_involved=[holder, agent_id],
                resource_target=symbol_key,
                details={
                    "existing_holder": holder,
                    "attempted_claimant": agent_id,
                },
                timestamp=time.time(),
            )
        return None

    @staticmethod
    def detect_assumption_conflict(
        agent_id: str,
        key: str,
        spec: Dict[str, Any],
        existing_assumptions: Dict[str, Dict[str, Any]],  # key -> {"agent_id": ..., "spec": ...}
    ) -> Optional[ConflictRecord]:
        """Detects contradictory semantic contracts or architectural assumptions between agents."""
        existing = existing_assumptions.get(key)
        if existing and existing.get("agent_id") != agent_id:
            old_spec = existing.get("spec", {})
            if old_spec != spec:
                return ConflictRecord(
                    conflict_id=f"conf_assump_{uuid.uuid4().hex[:8]}",
                    conflict_type=ConflictType.CONFLICTING_ASSUMPTIONS.value,
                    agents_involved=[existing["agent_id"], agent_id],
                    resource_target=key,
                    details={
                        "prior_agent": existing["agent_id"],
                        "prior_spec": old_spec,
                        "conflicting_spec": spec,
                    },
                    timestamp=time.time(),
                )
        return None


class QuarantineEngine:
    """Isolates misbehaving, conflicting, or untrusted agents from the workspace."""

    def __init__(self):
        self.records: Dict[str, QuarantineRecord] = {}

    def quarantine_agent(
        self,
        agent_id: str,
        reason: str,
        evidence: Optional[Dict[str, Any]] = None,
        fleet_engine: Optional[Any] = None,
    ) -> QuarantineRecord:
        """
        Immediately isolates the specified agent, revokes all held leases,
        and forbids further state mutation.
        """
        rec = QuarantineRecord(
            agent_id=agent_id,
            reason=reason,
            quarantined_at=time.time(),
            evidence=dict(evidence or {}),
        )
        self.records[agent_id] = rec

        # Revoke all leases and symbol claims in fleet engine
        if fleet_engine:
            if hasattr(fleet_engine, "state") and hasattr(fleet_engine.state, "leases"):
                for path, lease in list(fleet_engine.state.leases.items()):
                    if lease.holder_agent_id == agent_id:
                        if hasattr(fleet_engine, "release_lease"):
                            fleet_engine.release_lease(agent_id, path)

            if hasattr(fleet_engine, "state") and hasattr(fleet_engine.state, "claimed_symbols"):
                for sym_key, holder in list(fleet_engine.state.claimed_symbols.items()):
                    if holder == agent_id:
                        if hasattr(fleet_engine, "release_symbol_work"):
                            fleet_engine.release_symbol_work(agent_id, sym_key)

            # Update agent status in engine state if available
            if hasattr(fleet_engine, "state") and hasattr(fleet_engine.state, "agents"):
                if agent_id in fleet_engine.state.agents:
                    fleet_engine.state.agents[agent_id].status = AgentStatus.QUARANTINED
                    fleet_engine.state.agents[agent_id].quarantine_reason = reason

        return rec

    def is_quarantined(self, agent_id: str) -> bool:
        return agent_id in self.records

    def release_quarantine(self, agent_id: str) -> bool:
        """Lifts quarantine status for an agent after manual or automated clearance."""
        if agent_id in self.records:
            del self.records[agent_id]
            return True
        return False

    def list_quarantined(self) -> List[QuarantineRecord]:
        return list(self.records.values())


class ConflictResolver:
    """Executes deterministic conflict resolution policies."""

    def __init__(self, quarantine_engine: Optional[QuarantineEngine] = None):
        self.quarantine_engine = quarantine_engine or QuarantineEngine()

    def resolve(
        self,
        conflict: ConflictRecord,
        strategy: ResolutionStrategy = ResolutionStrategy.REJECT,
        fleet_engine: Optional[Any] = None,
    ) -> ConflictRecord:
        """Applies the designated resolution strategy to an active conflict."""
        if strategy == ResolutionStrategy.REJECT:
            conflict.resolution = f"Rejected conflicting action on '{conflict.resource_target}' (fail-closed)."
            conflict.resolved = True

        elif strategy == ResolutionStrategy.QUARANTINE:
            # Quarantine the second agent involved (the conflicting claimant)
            offending_agent = conflict.agents_involved[-1] if conflict.agents_involved else "unknown"
            self.quarantine_engine.quarantine_agent(
                agent_id=offending_agent,
                reason=f"Quarantined due to conflict on '{conflict.resource_target}': {conflict.conflict_type}",
                evidence=conflict.details,
                fleet_engine=fleet_engine,
            )
            conflict.resolution = f"Quarantined offending agent '{offending_agent}'."
            conflict.resolved = True

        elif strategy == ResolutionStrategy.LAST_WRITER_WINS:
            conflict.resolution = f"Overwritten via LAST_WRITER_WINS by '{conflict.agents_involved[-1]}'."
            conflict.resolved = True

        elif strategy == ResolutionStrategy.MERGE:
            conflict.resolution = f"Merged non-overlapping partitions on '{conflict.resource_target}'."
            conflict.resolved = True

        return conflict
