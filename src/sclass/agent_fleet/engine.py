"""
S-Class Multi-Agent Fleet Integrity Engine (Phase 15 / B.15).

Implements the governance and integrity layer for parallel multi-agent swarms:
- Concurrent file mutation race condition prevention with granular leases.
- Duplicate work detection via CKG symbol claim tracking.
- Cross-agent semantic assumption & contract reconciliation.
- Stale branch detection and cascading evidence invalidation upon workspace mutation.
- Subagent isolation / quarantine under EscalationPolicy.QUARANTINE_SUBAGENT.
- Epistemic global verification & multi-agent evidence merging into VerifiedProjectState.
"""

from __future__ import annotations
import os
import time
import json
import uuid
from typing import Dict, Any, List, Optional, Tuple, Set

from sclass.agent_fleet.models import (
    AgentIdentity,
    AgentStatus,
    ResourceLease,
    LeaseType,
    ConflictEvent,
    ConflictType,
    FleetState,
    FleetMergeResult,
)
from sclass.domain.project import VerifiedProjectState
from sclass.telemetry.tracing import get_local_tracer, SPAN_SESSION_TURN


class FleetIntegrityEngine:
    """
    Authoritative governance engine for multi-agent swarm integrity.
    Ensures parallel agents cannot overwrite shared state, duplicate work,
    drift in semantic assumptions, or contaminate verified truth.
    """

    def __init__(self, workspace_root: str, state_path: Optional[str] = None) -> None:
        self.workspace_root = os.path.abspath(workspace_root)
        self.state_path = state_path or os.path.join(self.workspace_root, ".sclass", "fleet", "fleet_state.json")
        self.state = FleetState()
        self._load_state()

    def _load_state(self) -> None:
        """Load persisted fleet state if available."""
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.state = FleetState.from_dict(data)
            except Exception:
                pass

    def _save_state(self) -> None:
        """Persist fleet state to disk atomically."""
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            temp_path = f"{self.state_path}.tmp.{os.getpid()}"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self.state.to_dict(), f, indent=2)
            os.replace(temp_path, self.state_path)
        except Exception:
            pass

    def _normalize_path(self, path: str) -> str:
        """Normalize a target path relative to the workspace root."""
        clean = path.replace("\\", "/").strip()
        if os.path.isabs(clean):
            try:
                rel = os.path.relpath(clean, self.workspace_root)
                return rel.replace("\\", "/")
            except Exception:
                return clean
        return clean.lstrip("./")

    def register_agent(
        self,
        agent_id: str,
        role: str = "worker",
        platform_id: str = "antigravity",
        base_revision: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentIdentity:
        """Register a subagent in the fleet."""
        tracer = get_local_tracer(self.workspace_root)
        with tracer.span("sclass.fleet.register_agent", attributes={"agent.id": agent_id, "agent.role": role}):
            if agent_id in self.state.agents:
                agent = self.state.agents[agent_id]
                agent.role = role
                agent.platform_id = platform_id
                if base_revision:
                    agent.base_revision = base_revision
                if metadata:
                    agent.metadata.update(metadata)
            else:
                agent = AgentIdentity(
                    agent_id=agent_id,
                    role=role,
                    platform_id=platform_id,
                    base_revision=base_revision,
                    metadata=metadata or {},
                )
                self.state.agents[agent_id] = agent
            self._save_state()
            return agent

    def is_quarantined(self, agent_id: str) -> bool:
        """Return True if agent exists and is in QUARANTINED status."""
        agent = self.state.agents.get(agent_id)
        return agent is not None and agent.status == AgentStatus.QUARANTINED

    def quarantine_agent(self, agent_id: str, reason: str) -> AgentIdentity:
        """
        Isolate a defective or rogue subagent.
        Revokes active leases and rejects subsequent claims without disrupting healthy swarm workers.
        """
        tracer = get_local_tracer(self.workspace_root)
        with tracer.span("sclass.fleet.quarantine", attributes={"agent.id": agent_id, "quarantine.reason": reason}):
            agent = self.state.agents.get(agent_id)
            if not agent:
                agent = self.register_agent(agent_id=agent_id, role="quarantined_worker")

            agent.status = AgentStatus.QUARANTINED
            agent.quarantine_reason = reason

            # Release all active leases held by this agent so they do not starve other workers
            expired_paths = [
                path for path, lease in self.state.leases.items()
                if lease.holder_agent_id == agent_id
            ]
            for p in expired_paths:
                del self.state.leases[p]

            # Record quarantine conflict event
            event = ConflictEvent(
                conflict_id=str(uuid.uuid4())[:8],
                conflict_type=ConflictType.QUARANTINE_VIOLATION,
                agents_involved=[agent_id],
                resource_target=f"agent:{agent_id}",
                details={"reason": reason, "revoked_leases": expired_paths},
            )
            self.state.conflicts.append(event)
            self._save_state()
            return agent

    def acquire_lease(
        self,
        agent_id: str,
        path: str,
        lease_type: LeaseType = LeaseType.EXCLUSIVE_WRITE,
        timeout_seconds: float = 300.0,
    ) -> Tuple[bool, Optional[ConflictEvent]]:
        """
        Acquire a resource lease on a workspace path.
        Prevents concurrent mutations and race conditions between parallel agents.
        """
        tracer = get_local_tracer(self.workspace_root)
        with tracer.span("sclass.fleet.lease_acquire", attributes={"agent.id": agent_id, "resource.path": path}):
            # 1. Check if agent is quarantined
            if self.is_quarantined(agent_id):
                conflict = ConflictEvent(
                    conflict_id=str(uuid.uuid4())[:8],
                    conflict_type=ConflictType.QUARANTINE_VIOLATION,
                    agents_involved=[agent_id],
                    resource_target=path,
                    details={"message": f"Quarantined agent {agent_id} cannot acquire lease."},
                )
                self.state.conflicts.append(conflict)
                self._save_state()
                return False, conflict

            norm_path = self._normalize_path(path)
            now = time.time()

            # Clean expired leases
            expired = [p for p, l in self.state.leases.items() if l.is_expired(now)]
            for exp in expired:
                del self.state.leases[exp]

            # Check existing lease on exact path
            existing = self.state.leases.get(norm_path)
            if existing:
                if existing.holder_agent_id == agent_id:
                    # Renew lease
                    existing.expires_at = now + timeout_seconds
                    existing.lease_type = lease_type
                    self._save_state()
                    return True, None
                
                # Check for conflict: either party requesting EXCLUSIVE_WRITE triggers collision
                if lease_type == LeaseType.EXCLUSIVE_WRITE or existing.lease_type == LeaseType.EXCLUSIVE_WRITE:
                    conflict = ConflictEvent(
                        conflict_id=str(uuid.uuid4())[:8],
                        conflict_type=ConflictType.CONCURRENT_MUTATION,
                        agents_involved=[existing.holder_agent_id, agent_id],
                        resource_target=norm_path,
                        details={
                            "existing_holder": existing.holder_agent_id,
                            "attempted_by": agent_id,
                            "existing_mode": existing.lease_type.value,
                            "attempted_mode": lease_type.value,
                            "expires_at": existing.expires_at,
                        },
                    )
                    self.state.conflicts.append(conflict)
                    self._save_state()
                    return False, conflict

            # Check directory hierarchy conflicts (e.g. exclusive lease on parent or child)
            for l_path, l in self.state.leases.items():
                if l.holder_agent_id != agent_id and (
                    lease_type == LeaseType.EXCLUSIVE_WRITE or l.lease_type == LeaseType.EXCLUSIVE_WRITE
                ):
                    if norm_path.startswith(l_path + "/") or l_path.startswith(norm_path + "/"):
                        conflict = ConflictEvent(
                            conflict_id=str(uuid.uuid4())[:8],
                            conflict_type=ConflictType.CONCURRENT_MUTATION,
                            agents_involved=[l.holder_agent_id, agent_id],
                            resource_target=norm_path,
                            details={
                                "overlapping_path": l_path,
                                "holder": l.holder_agent_id,
                                "reason": "Directory hierarchy containment conflict",
                            },
                        )
                        self.state.conflicts.append(conflict)
                        self._save_state()
                        return False, conflict

            # Grant lease
            new_lease = ResourceLease(
                lease_id=str(uuid.uuid4())[:8],
                path=norm_path,
                holder_agent_id=agent_id,
                lease_type=lease_type,
                acquired_at=now,
                expires_at=now + timeout_seconds,
            )
            self.state.leases[norm_path] = new_lease

            # Track in agent identity
            agent = self.state.agents.get(agent_id)
            if agent and norm_path not in agent.assigned_paths:
                agent.assigned_paths.append(norm_path)

            self._save_state()
            return True, None

    def release_lease(self, agent_id: str, path: str) -> bool:
        """Release an acquired lease."""
        norm_path = self._normalize_path(path)
        lease = self.state.leases.get(norm_path)
        if lease and lease.holder_agent_id == agent_id:
            del self.state.leases[norm_path]
            agent = self.state.agents.get(agent_id)
            if agent and norm_path in agent.assigned_paths:
                agent.assigned_paths.remove(norm_path)
            self._save_state()
            return True
        return False

    def claim_symbol_work(self, agent_id: str, symbol_name: str, file_path: str = "") -> Tuple[bool, Optional[ConflictEvent]]:
        """
        Claim ownership of a CKG symbol (function, class, component) for implementation.
        Detects and rejects duplicate work across parallel agents.
        """
        if self.is_quarantined(agent_id):
            conflict = ConflictEvent(
                conflict_id=str(uuid.uuid4())[:8],
                conflict_type=ConflictType.QUARANTINE_VIOLATION,
                agents_involved=[agent_id],
                resource_target=f"symbol:{symbol_name}",
                details={"message": f"Quarantined agent {agent_id} cannot claim symbol work."},
            )
            self.state.conflicts.append(conflict)
            return False, conflict

        existing_holder = self.state.claimed_symbols.get(symbol_name)
        if existing_holder and existing_holder != agent_id:
            conflict = ConflictEvent(
                conflict_id=str(uuid.uuid4())[:8],
                conflict_type=ConflictType.DUPLICATE_WORK,
                agents_involved=[existing_holder, agent_id],
                resource_target=f"symbol:{symbol_name}",
                details={
                    "claimed_by": existing_holder,
                    "attempted_by": agent_id,
                    "file_path": file_path,
                    "message": f"Symbol '{symbol_name}' already claimed by {existing_holder}. Duplicate work prevented.",
                },
            )
            self.state.conflicts.append(conflict)
            self._save_state()
            return False, conflict

        self.state.claimed_symbols[symbol_name] = agent_id
        agent = self.state.agents.get(agent_id)
        if agent and symbol_name not in agent.claimed_symbols:
            agent.claimed_symbols.append(symbol_name)

        self._save_state()
        return True, None

    def record_agent_assumption(
        self,
        agent_id: str,
        key: str,
        assumption_spec: Dict[str, Any],
    ) -> Tuple[bool, Optional[ConflictEvent]]:
        """
        Record a semantic assumption (e.g. API parameter types, schema formats).
        Detects conflicting assumptions across parallel subagents before merging.
        """
        if self.is_quarantined(agent_id):
            conflict = ConflictEvent(
                conflict_id=str(uuid.uuid4())[:8],
                conflict_type=ConflictType.QUARANTINE_VIOLATION,
                agents_involved=[agent_id],
                resource_target=f"assumption:{key}",
                details={"message": f"Quarantined agent {agent_id} cannot record assumptions."},
            )
            self.state.conflicts.append(conflict)
            return False, conflict

        existing = self.state.assumptions.get(key)
        if existing and existing["agent_id"] != agent_id:
            old_spec = existing["spec"]
            # Check for fundamental divergence in signature, return type, or schema version
            if old_spec != assumption_spec:
                conflict = ConflictEvent(
                    conflict_id=str(uuid.uuid4())[:8],
                    conflict_type=ConflictType.CONFLICTING_ASSUMPTIONS,
                    agents_involved=[existing["agent_id"], agent_id],
                    resource_target=f"assumption:{key}",
                    details={
                        "prior_assumption": old_spec,
                        "new_assumption": assumption_spec,
                        "prior_agent": existing["agent_id"],
                        "new_agent": agent_id,
                        "divergent_keys": [
                            k for k in set(old_spec.keys()) | set(assumption_spec.keys())
                            if old_spec.get(k) != assumption_spec.get(k)
                        ],
                    },
                )
                self.state.conflicts.append(conflict)
                self._save_state()
                return False, conflict

        self.state.assumptions[key] = {
            "agent_id": agent_id,
            "spec": assumption_spec,
            "timestamp": time.time(),
        }
        self._save_state()
        return True, None

    def detect_stale_branch(self, agent_id: str, current_workspace_revision: str) -> bool:
        """
        Detect if an agent's base working tree revision has diverged from current workspace truth.
        """
        agent = self.state.agents.get(agent_id)
        if not agent or not agent.base_revision:
            return False

        if agent.base_revision != current_workspace_revision:
            conflict = ConflictEvent(
                conflict_id=str(uuid.uuid4())[:8],
                conflict_type=ConflictType.STALE_BRANCH_MUTATION,
                agents_involved=[agent_id],
                resource_target=f"revision:{agent.base_revision}",
                details={
                    "base_revision": agent.base_revision,
                    "current_revision": current_workspace_revision,
                    "message": f"Agent {agent_id} working tree is stale ({agent.base_revision} != {current_workspace_revision}).",
                },
            )
            self.state.conflicts.append(conflict)
            self._save_state()
            return True

        return False

    def merge_fleet_evidence(
        self,
        verified_state: VerifiedProjectState,
        fleet_receipts: List[Dict[str, Any]],
        current_revision: str,
    ) -> FleetMergeResult:
        """
        Epistemic Global Verification & Multi-Agent Evidence Merging.
        Reconciles evidence receipts across parallel subagents into VerifiedProjectState.
        Rejects receipts from quarantined agents or stale revisions.
        """
        tracer = get_local_tracer(self.workspace_root)
        with tracer.span("sclass.fleet.merge_evidence", attributes={"receipt.count": len(fleet_receipts)}):
            result = FleetMergeResult()

            for receipt_dict in fleet_receipts:
                agent_id = receipt_dict.get("agent", "unknown")
                claim_id = receipt_dict.get("claim_id", str(uuid.uuid4())[:8])
                claim_text = receipt_dict.get("claim_text", receipt_dict.get("action", "unspecified claim"))
                receipt_revision = receipt_dict.get("base_commit", "")

                # 1. Check if agent is quarantined
                if self.is_quarantined(agent_id):
                    result.quarantined_agents.append(agent_id)
                    verified_state.record_invalidated_claim(
                        claim_or_id=claim_id,
                        reason=f"Evidence rejected: Agent '{agent_id}' is quarantined for safety/policy violation.",
                    )
                    result.invalidated_claims.append({
                        "claim_id": claim_id,
                        "agent": agent_id,
                        "reason": "agent_quarantined",
                    })
                    continue

                # 2. Check for stale branch divergence
                if receipt_revision and current_revision and receipt_revision != current_revision:
                    # Check if receipt's changed files were modified upstream
                    files_changed = receipt_dict.get("files_changed", [])
                    conflict = ConflictEvent(
                        conflict_id=str(uuid.uuid4())[:8],
                        conflict_type=ConflictType.STALE_BRANCH_MUTATION,
                        agents_involved=[agent_id],
                        resource_target=claim_id,
                        details={
                            "receipt_revision": receipt_revision,
                            "current_revision": current_revision,
                            "files_changed": files_changed,
                        },
                    )
                    result.conflicts.append(conflict)
                    self.state.conflicts.append(conflict)
                    verified_state.record_invalidated_claim(
                        claim_or_id=claim_id,
                        reason=f"Evidence rejected: Collected on stale revision '{receipt_revision}', current revision is '{current_revision}'.",
                    )
                    result.invalidated_claims.append({
                        "claim_id": claim_id,
                        "agent": agent_id,
                        "reason": "stale_revision_conflict",
                    })
                    continue

                # 3. Clean evidence contribution -> merge into VerifiedProjectState
                verified_state.record_verified_claim(
                    claim={"claim_id": claim_id, "text": claim_text, "agent": agent_id},
                    receipt=receipt_dict,
                )
                result.merged_claims.append({
                    "claim_id": claim_id,
                    "agent": agent_id,
                    "receipt_id": receipt_dict.get("receipt_id"),
                })

            self._save_state()
            return result
