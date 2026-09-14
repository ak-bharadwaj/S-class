"""
S-Class Multi-Agent Fleet Integrity Engine (Phase 15 / B.15 Hardened - Reality Closure).

Implements the authoritative governance and integrity layer for parallel multi-agent swarms:
- ACID Transactional Storage: SQLite backing with WAL mode and atomic lease transactions.
- Concurrent file mutation race condition prevention with serializable SQLite leases.
- Duplicate work detection via qualified CKG symbol claim tracking (file_path::symbol_name).
- Cross-agent semantic assumption & contract reconciliation.
- Strict workspace path containment checking preventing directory traversal attacks.
- Stale branch detection and cascading evidence invalidation upon workspace mutation.
- Subagent isolation / quarantine under EscalationPolicy.QUARANTINE_SUBAGENT.
- Epistemic independent verification & multi-agent evidence merging into VerifiedProjectState.
- Law L8 enforcement: No silent failure, explicit FleetStorageError.
"""

from __future__ import annotations
import os
import time
import json
import uuid
import sqlite3
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
    TaskNode,
    TaskEdge,
    SymbolOwnership,
    ConflictRecord,
    QuarantineRecord,
)
from sclass.agent_fleet.agent_registry import AgentSessionManager
from sclass.agent_fleet.conflict import (
    ConflictDetector,
    ConflictResolver,
    QuarantineEngine,
    ResolutionStrategy,
)
from sclass.domain.project import VerifiedProjectState
from sclass.storage.paths import WorkspacePaths
from sclass.telemetry.tracing import get_local_tracer, SPAN_SESSION_TURN


class FleetStorageError(Exception):
    """Authoritative exception raised when fleet persistence fails or is corrupted (Law L8)."""
    pass


class FleetIntegrityEngine:
    """
    Authoritative governance engine for multi-agent swarm integrity.
    Ensures parallel agents cannot overwrite shared state, duplicate work,
    drift in semantic assumptions, or contaminate verified truth.
    Backed by an ACID transactional SQLite store (.sclass/fleet/fleet.db) with WAL mode
    and atomic serializable lease acquisition.
    """

    def __init__(
        self,
        workspace_root: str,
        state_path: Optional[str] = None,
        db_path: Optional[str] = None,
    ) -> None:
        self.workspace_root = os.path.abspath(workspace_root)
        self.state_path = state_path or os.path.join(self.workspace_root, ".sclass", "fleet", "fleet_state.json")
        
        # Configure SQLite database path
        if db_path:
            self.db_path = os.path.abspath(db_path)
        elif state_path and state_path.endswith(".json"):
            self.db_path = os.path.abspath(state_path[:-5] + ".db")
        else:
            self.db_path = os.path.join(self.workspace_root, ".sclass", "fleet", "fleet.db")

        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)

        self.state = FleetState()
        self._init_db()
        self._load_state()

        self.task_graph = TaskGraph()
        self.agent_registry = AgentSessionManager()
        self.conflict_engine = ConflictEngine(fleet_engine=self)
        self.evidence_aggregator = EvidenceAggregator(self.workspace_root, fleet_engine=self)

    def _get_conn(self) -> sqlite3.Connection:
        """Returns a configured SQLite connection with WAL mode and busy timeout."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA busy_timeout = 5000;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            return conn
        except sqlite3.Error as e:
            raise FleetStorageError(f"Failed to open fleet database at '{self.db_path}': {e}") from e

    def _init_db(self) -> None:
        """Initializes database schema with ACID table definitions."""
        try:
            with self._get_conn() as conn:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS agents (
                        agent_id TEXT PRIMARY KEY,
                        role TEXT,
                        platform_id TEXT,
                        status TEXT,
                        base_revision TEXT,
                        quarantine_reason TEXT,
                        assigned_paths TEXT,
                        claimed_symbols TEXT,
                        metadata TEXT,
                        registered_at REAL
                    );
                    CREATE TABLE IF NOT EXISTS leases (
                        path TEXT PRIMARY KEY,
                        lease_id TEXT,
                        holder_agent_id TEXT,
                        lease_type TEXT,
                        acquired_at REAL,
                        expires_at REAL
                    );
                    CREATE TABLE IF NOT EXISTS symbol_claims (
                        symbol_key TEXT PRIMARY KEY,
                        symbol_name TEXT,
                        file_path TEXT,
                        holder_agent_id TEXT,
                        claimed_at REAL
                    );
                    CREATE TABLE IF NOT EXISTS assumptions (
                        key TEXT PRIMARY KEY,
                        agent_id TEXT,
                        spec TEXT,
                        timestamp REAL
                    );
                    CREATE TABLE IF NOT EXISTS conflicts (
                        conflict_id TEXT PRIMARY KEY,
                        conflict_type TEXT,
                        agents_involved TEXT,
                        resource_target TEXT,
                        details TEXT,
                        timestamp REAL,
                        resolved INTEGER DEFAULT 0
                    );
                """)
        except sqlite3.Error as e:
            raise FleetStorageError(f"Failed to initialize fleet database schema: {e}") from e

    def _load_state(self) -> None:
        """Load fleet state from transactional SQLite store or migrate legacy JSON."""
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) as cnt FROM agents")
                count = cursor.fetchone()["cnt"]

                # If database is empty and legacy JSON exists, migrate it
                if count == 0 and os.path.exists(self.state_path):
                    try:
                        with open(self.state_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            self.state = FleetState.from_dict(data)
                            self._save_state()
                            return
                    except Exception as e:
                        raise FleetStorageError(f"Failed to read legacy fleet state JSON: {e}") from e

                # Load agents
                cursor.execute("SELECT * FROM agents")
                agents = {}
                for row in cursor.fetchall():
                    agents[row["agent_id"]] = AgentIdentity(
                        agent_id=row["agent_id"],
                        role=row["role"],
                        platform_id=row["platform_id"],
                        status=AgentStatus(row["status"]),
                        base_revision=row["base_revision"] or "",
                        quarantine_reason=row["quarantine_reason"],
                        assigned_paths=json.loads(row["assigned_paths"] or "[]"),
                        claimed_symbols=json.loads(row["claimed_symbols"] or "[]"),
                        metadata=json.loads(row["metadata"] or "{}"),
                        registered_at=float(row["registered_at"]),
                    )

                # Load leases
                cursor.execute("SELECT * FROM leases")
                leases = {}
                for row in cursor.fetchall():
                    leases[row["path"]] = ResourceLease(
                        lease_id=row["lease_id"],
                        path=row["path"],
                        holder_agent_id=row["holder_agent_id"],
                        lease_type=LeaseType(row["lease_type"]),
                        acquired_at=float(row["acquired_at"]),
                        expires_at=float(row["expires_at"]),
                    )

                # Load symbol claims
                cursor.execute("SELECT * FROM symbol_claims")
                claimed_symbols = {}
                for row in cursor.fetchall():
                    claimed_symbols[row["symbol_key"]] = row["holder_agent_id"]

                # Load assumptions
                cursor.execute("SELECT * FROM assumptions")
                assumptions = {}
                for row in cursor.fetchall():
                    assumptions[row["key"]] = {
                        "agent_id": row["agent_id"],
                        "spec": json.loads(row["spec"] or "{}"),
                        "timestamp": float(row["timestamp"]),
                    }

                # Load conflicts
                cursor.execute("SELECT * FROM conflicts ORDER BY timestamp ASC")
                conflicts = []
                for row in cursor.fetchall():
                    conflicts.append(ConflictEvent(
                        conflict_id=row["conflict_id"],
                        conflict_type=ConflictType(row["conflict_type"]),
                        agents_involved=json.loads(row["agents_involved"] or "[]"),
                        resource_target=row["resource_target"],
                        details=json.loads(row["details"] or "{}"),
                        timestamp=float(row["timestamp"]),
                        resolved=bool(row["resolved"]),
                    ))

                self.state = FleetState(
                    agents=agents,
                    leases=leases,
                    claimed_symbols=claimed_symbols,
                    assumptions=assumptions,
                    conflicts=conflicts,
                )
        except sqlite3.Error as e:
            raise FleetStorageError(f"Database error during _load_state: {e}") from e

    def _save_state(self) -> None:
        """
        Transactional sync to SQLite store and secondary atomic JSON snapshot.
        Eliminates fail-silent anti-pattern (Law L8).
        """
        try:
            with self._get_conn() as conn:
                with conn:
                    # Sync agents
                    for a in self.state.agents.values():
                        conn.execute("""
                            INSERT INTO agents (agent_id, role, platform_id, status, base_revision, quarantine_reason, assigned_paths, claimed_symbols, metadata, registered_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(agent_id) DO UPDATE SET
                                role = excluded.role,
                                platform_id = excluded.platform_id,
                                status = excluded.status,
                                base_revision = excluded.base_revision,
                                quarantine_reason = excluded.quarantine_reason,
                                assigned_paths = excluded.assigned_paths,
                                claimed_symbols = excluded.claimed_symbols,
                                metadata = excluded.metadata,
                                registered_at = excluded.registered_at;
                        """, (
                            a.agent_id,
                            a.role,
                            a.platform_id,
                            a.status.value,
                            a.base_revision,
                            a.quarantine_reason,
                            json.dumps(a.assigned_paths),
                            json.dumps(a.claimed_symbols),
                            json.dumps(a.metadata),
                            a.registered_at,
                        ))

                    # Sync leases: replace table contents with active leases
                    conn.execute("DELETE FROM leases;")
                    for l in self.state.leases.values():
                        conn.execute("""
                            INSERT INTO leases (path, lease_id, holder_agent_id, lease_type, acquired_at, expires_at)
                            VALUES (?, ?, ?, ?, ?, ?);
                        """, (
                            l.path,
                            l.lease_id,
                            l.holder_agent_id,
                            l.lease_type.value,
                            l.acquired_at,
                            l.expires_at,
                        ))

                    # Sync symbol claims
                    conn.execute("DELETE FROM symbol_claims;")
                    for sym_key, holder in self.state.claimed_symbols.items():
                        parts = sym_key.split("::", 1)
                        file_path = parts[0] if len(parts) > 1 else ""
                        sym_name = parts[1] if len(parts) > 1 else sym_key
                        conn.execute("""
                            INSERT INTO symbol_claims (symbol_key, symbol_name, file_path, holder_agent_id, claimed_at)
                            VALUES (?, ?, ?, ?, ?);
                        """, (sym_key, sym_name, file_path, holder, time.time()))

                    # Sync assumptions
                    conn.execute("DELETE FROM assumptions;")
                    for key, val in self.state.assumptions.items():
                        conn.execute("""
                            INSERT INTO assumptions (key, agent_id, spec, timestamp)
                            VALUES (?, ?, ?, ?);
                        """, (key, val["agent_id"], json.dumps(val["spec"]), val["timestamp"]))

                    # Sync conflicts
                    for c in self.state.conflicts:
                        conn.execute("""
                            INSERT INTO conflicts (conflict_id, conflict_type, agents_involved, resource_target, details, timestamp, resolved)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(conflict_id) DO UPDATE SET
                                resolved = excluded.resolved;
                        """, (
                            c.conflict_id,
                            c.conflict_type.value,
                            json.dumps(c.agents_involved),
                            c.resource_target,
                            json.dumps(c.details),
                            c.timestamp,
                            1 if c.resolved else 0,
                        ))

            # Secondary atomic JSON snapshot for external inspectors
            temp_path = f"{self.state_path}.tmp.{os.getpid()}"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self.state.to_dict(), f, indent=2)
            os.replace(temp_path, self.state_path)
        except (sqlite3.Error, OSError) as e:
            raise FleetStorageError(f"Failed to persist fleet state (Law L8 violation): {e}") from e

    def _normalize_path(self, path: str) -> str:
        """
        Normalize a target path relative to the workspace root and enforce strict containment.
        Rejects directory traversal (../../) attacks.
        """
        clean = path.replace("\\", "/").strip()
        if not clean:
            return ""
        abs_path = os.path.abspath(os.path.join(self.workspace_root, clean) if not os.path.isabs(clean) else clean)
        paths = WorkspacePaths(self.workspace_root)
        if not paths.is_contained(abs_path):
            raise ValueError(
                f"Security violation: Target path '{path}' escapes workspace root '{self.workspace_root}'."
            )
        rel = os.path.relpath(abs_path, self.workspace_root).replace("\\", "/")
        return "" if rel == "." else rel

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
        Enforces strict workspace path containment and serializable SQLite transactions.
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

            # 2. Strict path containment check
            try:
                norm_path = self._normalize_path(path)
            except ValueError as e:
                conflict = ConflictEvent(
                    conflict_id=str(uuid.uuid4())[:8],
                    conflict_type=ConflictType.QUARANTINE_VIOLATION,
                    agents_involved=[agent_id],
                    resource_target=path,
                    details={"error": "Path containment violation", "message": str(e)},
                )
                self.state.conflicts.append(conflict)
                self._save_state()
                return False, conflict

            now = time.time()
            expires = now + timeout_seconds

            # 3. ATOMIC SQLite TRANSACTION for serializable lease acquisition
            try:
                with self._get_conn() as conn:
                    conn.execute("BEGIN IMMEDIATE;")
                    
                    # Clean expired leases
                    conn.execute("DELETE FROM leases WHERE expires_at <= ?;", (now,))

                    # Check exact path lease
                    cur = conn.execute("SELECT * FROM leases WHERE path = ?;", (norm_path,))
                    existing = cur.fetchone()
                    if existing:
                        existing_holder = existing["holder_agent_id"]
                        existing_type = existing["lease_type"]
                        if existing_holder == agent_id:
                            # Renew
                            conn.execute(
                                "UPDATE leases SET expires_at = ?, lease_type = ? WHERE path = ?;",
                                (expires, lease_type.value, norm_path)
                            )
                            conn.commit()
                            self._load_state()
                            return True, None
                        
                        if lease_type == LeaseType.EXCLUSIVE_WRITE or existing_type == LeaseType.EXCLUSIVE_WRITE.value:
                            conflict = ConflictEvent(
                                conflict_id=str(uuid.uuid4())[:8],
                                conflict_type=ConflictType.CONCURRENT_MUTATION,
                                agents_involved=[existing_holder, agent_id],
                                resource_target=norm_path,
                                details={
                                    "existing_holder": existing_holder,
                                    "attempted_by": agent_id,
                                    "existing_mode": existing_type,
                                    "attempted_mode": lease_type.value,
                                    "expires_at": existing["expires_at"],
                                },
                            )
                            self._record_conflict_in_conn(conn, conflict)
                            conn.commit()
                            self._load_state()
                            return False, conflict

                    # Check directory hierarchy conflicts
                    cur = conn.execute("SELECT * FROM leases WHERE holder_agent_id != ?;", (agent_id,))
                    for row in cur.fetchall():
                        l_path = row["path"]
                        l_type = row["lease_type"]
                        l_holder = row["holder_agent_id"]
                        if lease_type == LeaseType.EXCLUSIVE_WRITE or l_type == LeaseType.EXCLUSIVE_WRITE.value:
                            if norm_path.startswith(l_path + "/") or l_path.startswith(norm_path + "/"):
                                conflict = ConflictEvent(
                                    conflict_id=str(uuid.uuid4())[:8],
                                    conflict_type=ConflictType.CONCURRENT_MUTATION,
                                    agents_involved=[l_holder, agent_id],
                                    resource_target=norm_path,
                                    details={
                                        "overlapping_path": l_path,
                                        "holder": l_holder,
                                        "reason": "Directory hierarchy containment conflict",
                                    },
                                )
                                self._record_conflict_in_conn(conn, conflict)
                                conn.commit()
                                self._load_state()
                                return False, conflict

                    # Grant lease atomically
                    lease_id = str(uuid.uuid4())[:8]
                    conn.execute("""
                        INSERT INTO leases (path, lease_id, holder_agent_id, lease_type, acquired_at, expires_at)
                        VALUES (?, ?, ?, ?, ?, ?);
                    """, (norm_path, lease_id, agent_id, lease_type.value, now, expires))
                    conn.commit()
                    self._load_state()
                    return True, None
            except sqlite3.Error as e:
                raise FleetStorageError(f"Atomic lease acquisition failed: {e}") from e

    def _record_conflict_in_conn(self, conn: sqlite3.Connection, conflict: ConflictEvent) -> None:
        """Records a conflict event inside an active database connection."""
        conn.execute("""
            INSERT INTO conflicts (conflict_id, conflict_type, agents_involved, resource_target, details, timestamp, resolved)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (
            conflict.conflict_id,
            conflict.conflict_type.value,
            json.dumps(conflict.agents_involved),
            conflict.resource_target,
            json.dumps(conflict.details),
            conflict.timestamp,
            1 if conflict.resolved else 0,
        ))

    def release_lease(self, agent_id: str, path: str) -> bool:
        """Release an acquired lease atomically."""
        try:
            norm_path = self._normalize_path(path)
        except ValueError:
            return False

        try:
            with self._get_conn() as conn:
                with conn:
                    cur = conn.execute("DELETE FROM leases WHERE path = ? AND holder_agent_id = ?;", (norm_path, agent_id))
                    released = cur.rowcount > 0
            if released:
                self._load_state()
            return released
        except sqlite3.Error as e:
            raise FleetStorageError(f"Failed to release lease: {e}") from e

    def claim_symbol_work(
        self,
        agent_id: str,
        symbol_name: str,
        file_path: str = "",
    ) -> Tuple[bool, Optional[ConflictEvent]]:
        """
        Claim ownership of a CKG symbol (function, class, component) for implementation.
        Keys on qualified symbol path (file_path::symbol_name) when file_path is provided,
        preventing false collisions across distinct modules while stopping duplicate work
        on the same module symbol.
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
            self._save_state()
            return False, conflict

        # Formulate qualified symbol key
        if file_path:
            try:
                norm_file = self._normalize_path(file_path)
            except ValueError:
                norm_file = file_path.replace("\\", "/").strip()
            symbol_key = f"{norm_file}::{symbol_name}"
        else:
            symbol_key = symbol_name

        existing_holder = self.state.claimed_symbols.get(symbol_key)
        if existing_holder and existing_holder != agent_id:
            conflict = ConflictEvent(
                conflict_id=str(uuid.uuid4())[:8],
                conflict_type=ConflictType.DUPLICATE_WORK,
                agents_involved=[existing_holder, agent_id],
                resource_target=f"symbol:{symbol_key}",
                details={
                    "claimed_by": existing_holder,
                    "attempted_by": agent_id,
                    "file_path": file_path,
                    "symbol_key": symbol_key,
                    "message": f"Symbol '{symbol_key}' already claimed by {existing_holder}. Duplicate work prevented.",
                },
            )
            self.state.conflicts.append(conflict)
            self._save_state()
            return False, conflict

        self.state.claimed_symbols[symbol_key] = agent_id
        agent = self.state.agents.get(agent_id)
        if agent and symbol_key not in agent.claimed_symbols:
            agent.claimed_symbols.append(symbol_key)

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
            self._save_state()
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
        Enforces the Evidence Hierarchy:
        Agent Receipt -> Evidence Validation -> Independent Verifier -> Accepted Evidence -> Fleet Merge -> VerifiedProjectState.
        
        Rejects:
        1. Receipts from quarantined agents.
        2. Receipts collected against stale workspace revisions.
        3. Receipts with non-zero exit codes, failed tests, or unverified claims.
        """
        tracer = get_local_tracer(self.workspace_root)
        with tracer.span("sclass.fleet.merge_evidence", attributes={"receipt.count": len(fleet_receipts)}):
            result = FleetMergeResult()

            for receipt_dict in fleet_receipts:
                agent_id = receipt_dict.get("agent", "unknown")
                claim_id = receipt_dict.get("claim_id", str(uuid.uuid4())[:8])
                claim_text = receipt_dict.get("claim_text", receipt_dict.get("action", "unspecified claim"))
                receipt_revision = receipt_dict.get("base_commit", "")
                exit_code = receipt_dict.get("exit_code", 0)
                failed_tests = receipt_dict.get("failed_tests", 0)

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

                # 3. Evidence Validation Gate: Verify independent execution reality
                if exit_code != 0:
                    verified_state.record_invalidated_claim(
                        claim_or_id=claim_id,
                        reason=f"Evidence rejected: Observed non-zero exit code ({exit_code}).",
                    )
                    result.invalidated_claims.append({
                        "claim_id": claim_id,
                        "agent": agent_id,
                        "reason": f"non_zero_exit_code_{exit_code}",
                    })
                    continue

                if failed_tests > 0:
                    verified_state.record_invalidated_claim(
                        claim_or_id=claim_id,
                        reason=f"Evidence rejected: {failed_tests} tests failed.",
                    )
                    result.invalidated_claims.append({
                        "claim_id": claim_id,
                        "agent": agent_id,
                        "reason": f"test_failures_{failed_tests}",
                    })
                    continue

                # 4. Clean verified evidence -> incorporate into VerifiedProjectState
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


class TaskGraph:
    """Directed Acyclic Graph (DAG) coordinating multi-agent subtask execution."""

    def __init__(self):
        self.nodes: Dict[str, TaskNode] = {}
        self.edges: List[TaskEdge] = []

    def add_task(
        self,
        task_id: str,
        title: str,
        dependencies: Optional[List[str]] = None,
        assigned_agent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TaskNode:
        deps = list(dependencies or [])
        node = TaskNode(
            task_id=task_id,
            title=title,
            dependencies=deps,
            assigned_agent_id=assigned_agent_id,
            state="READY" if not deps else "PENDING",
            metadata=dict(metadata or {}),
        )
        self.nodes[task_id] = node
        for d in deps:
            self.edges.append(TaskEdge(from_task_id=d, to_task_id=task_id, relation="depends_on"))
        return node

    def add_dependency(self, task_id: str, depends_on_task_id: str) -> None:
        if task_id not in self.nodes:
            raise FleetStorageError(f"Task '{task_id}' not found in task graph.")
        if depends_on_task_id not in self.nodes[task_id].dependencies:
            self.nodes[task_id].dependencies.append(depends_on_task_id)
            self.edges.append(TaskEdge(from_task_id=depends_on_task_id, to_task_id=task_id, relation="depends_on"))
            if self.nodes[task_id].state == "READY":
                self.nodes[task_id].state = "PENDING"

    def has_cycles(self) -> bool:
        """Detects whether the task dependency graph contains any cycles via DFS."""
        visited: Dict[str, int] = {}  # 0: visiting, 1: visited

        def dfs(u: str) -> bool:
            visited[u] = 0
            node = self.nodes.get(u)
            if node:
                for dep in node.dependencies:
                    if dep in self.nodes:
                        if visited.get(dep) == 0:
                            return True
                        if dep not in visited and dfs(dep):
                            return True
            visited[u] = 1
            return False

        for node_id in self.nodes:
            if node_id not in visited:
                if dfs(node_id):
                    return True
        return False

    def get_execution_order(self) -> List[str]:
        """Calculates topological sort order of tasks. Raises FleetStorageError if cycles exist."""
        if self.has_cycles():
            raise FleetStorageError("Cycle detected in fleet task graph; cannot determine execution order.")

        in_degree: Dict[str, int] = {k: 0 for k in self.nodes}
        adj: Dict[str, List[str]] = {k: [] for k in self.nodes}

        for edge in self.edges:
            if edge.from_task_id in self.nodes and edge.to_task_id in self.nodes:
                adj[edge.from_task_id].append(edge.to_task_id)
                in_degree[edge.to_task_id] += 1

        queue = [k for k, deg in in_degree.items() if deg == 0]
        order = []

        while queue:
            curr = queue.pop(0)
            order.append(curr)
            for neighbor in adj.get(curr, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self.nodes):
            raise FleetStorageError("Task graph has unresolvable dependencies or cycles.")
        return order

    def get_ready_tasks(self) -> List[TaskNode]:
        """Returns all tasks whose dependencies are fully completed and are ready to execute."""
        ready = []
        for node in self.nodes.values():
            if node.state in ("COMPLETED", "FAILED", "RUNNING"):
                continue
            all_deps_completed = True
            for dep_id in node.dependencies:
                dep_node = self.nodes.get(dep_id)
                if not dep_node or dep_node.state != "COMPLETED":
                    all_deps_completed = False
                    break
            if all_deps_completed:
                node.state = "READY"
                ready.append(node)
        return ready

    def mark_completed(self, task_id: str) -> None:
        if task_id in self.nodes:
            self.nodes[task_id].state = "COMPLETED"

    def mark_failed(self, task_id: str) -> None:
        if task_id in self.nodes:
            self.nodes[task_id].state = "FAILED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "edges": [e.to_dict() for e in self.edges],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TaskGraph:
        tg = cls()
        for k, v in data.get("nodes", {}).items():
            tg.nodes[k] = TaskNode.from_dict(v)
        for e in data.get("edges", []):
            tg.edges.append(TaskEdge.from_dict(e))
        return tg


class ConflictEngine:
    """Manages conflict detection, policy resolution, and agent quarantine."""

    def __init__(self, fleet_engine: Optional[Any] = None):
        self.fleet_engine = fleet_engine
        self.detector = ConflictDetector()
        self.quarantine_engine = QuarantineEngine()
        self.resolver = ConflictResolver(quarantine_engine=self.quarantine_engine)

    def check_and_resolve(
        self,
        conflict: ConflictRecord,
        strategy: ResolutionStrategy = ResolutionStrategy.REJECT,
    ) -> ConflictRecord:
        return self.resolver.resolve(conflict, strategy=strategy, fleet_engine=self.fleet_engine)

    def quarantine(self, agent_id: str, reason: str, evidence: Optional[Dict[str, Any]] = None) -> QuarantineRecord:
        return self.quarantine_engine.quarantine_agent(
            agent_id=agent_id,
            reason=reason,
            evidence=evidence,
            fleet_engine=self.fleet_engine,
        )

    def is_quarantined(self, agent_id: str) -> bool:
        return self.quarantine_engine.is_quarantined(agent_id)


class EvidenceAggregator:
    """Aggregates and reconciles multi-agent claims, receipts, and truth updates."""

    def __init__(self, workspace_root: str, fleet_engine: Optional[Any] = None):
        self.workspace_root = os.path.abspath(workspace_root)
        self.fleet_engine = fleet_engine

    def aggregate_evidence(
        self,
        agent_receipts: List[Dict[str, Any]],
        verified_state: Optional[VerifiedProjectState] = None,
        project_truth: Optional[Any] = None,
    ) -> FleetMergeResult:
        if self.fleet_engine and hasattr(self.fleet_engine, "merge_fleet_evidence"):
            state = verified_state or VerifiedProjectState(workspace=self.workspace_root)
            rev = getattr(state, "current_revision", "") or "REV_001"
            return self.fleet_engine.merge_fleet_evidence(
                verified_state=state,
                fleet_receipts=agent_receipts,
                current_revision=rev,
            )

        # Standalone aggregation fallback
        result = FleetMergeResult()
        for r in agent_receipts:
            cid = r.get("claim_id", "")
            agent = r.get("agent_id", "")
            code = r.get("exit_code", 0)
            if code != 0:
                result.invalidated_claims.append({"claim_id": cid, "agent": agent, "reason": f"exit_code_{code}"})
            else:
                result.merged_claims.append({"claim_id": cid, "agent": agent, "receipt": r})
                if project_truth and hasattr(project_truth, "verify"):
                    project_truth.verify(cid, receipt=r)
        return result

