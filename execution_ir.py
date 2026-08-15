"""
S-Class EOS V10.1 - Authoritative Execution Intermediate Representation (Execution IR)

Defines:
1. ExecutionTask (Executable task enriched with resource locks, risk metrics, and agent requirements)
2. ExecutionDependency (Typed prerequisite relationships: HARD, SOFT, DATA, STATE, MUTUAL_EXCLUSION)
3. ExecutionResource (Declarative filesystem, port, database, and terminal resource requirements)
4. ExecutionConstraint (Mutual exclusion, ordering, and execution boundary constraints)
5. AgentCapability & AgentAssignment (Formal agent capability matching model)
6. ExecutionBatch (Proven conflict-free parallel and serial execution batches)
7. ExecutionCheckpoint (Verification checkpoints with deterministic downstream invalidation scopes)
8. ExecutionPlan (Complete deterministic execution DAG with canonical cryptographic plan hash)
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Set, Any, Optional, Tuple
import hashlib
import json


class ExecutionTaskStatus(str, Enum):
    """Lifecycle status of an execution task."""
    READY = "ready"
    BLOCKED = "blocked"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INVALIDATED = "invalidated"


class DependencyType(str, Enum):
    """Type of execution dependency between tasks."""
    HARD_PREREQUISITE = "hard_prerequisite"
    SOFT_ORDERING = "soft_ordering"
    DATA_FLOW = "data_flow"
    STATE_FLOW = "state_flow"
    MUTUAL_EXCLUSION = "mutual_exclusion"


class ExecutionMode(str, Enum):
    """Execution mode of a batch or task."""
    SERIAL = "serial"
    PARALLEL = "parallel"


class TaskRiskLevel(str, Enum):
    """Assessed architectural and execution risk level."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ResourceType(str, Enum):
    """Type of execution resource."""
    FILESYSTEM_FILE = "filesystem_file"
    DIRECTORY_LOCK = "directory_lock"
    PORT_RESOURCE = "port_resource"
    DATABASE_TABLE = "database_table"
    TERMINAL_EXCLUSIVE = "terminal_exclusive"
    NETWORK_SOCKET = "network_socket"
    HUMAN_APPROVAL = "human_approval"
    MODEL_INFERENCE = "model_inference"


class ResourceAccessMode(str, Enum):
    """Access mode for an execution resource."""
    READ_SHARED = "read_shared"
    WRITE_EXCLUSIVE = "write_exclusive"


@dataclass
class ExecutionResource:
    """A resource required by an execution task with access mode semantics."""
    id: str
    resource_type: ResourceType
    access_mode: ResourceAccessMode
    target_identifier: str

    def compute_canonical_hash(self) -> str:
        payload = {
            "id": self.id,
            "resource_type": self.resource_type.value,
            "access_mode": self.access_mode.value,
            "target_identifier": self.target_identifier
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "resource_type": self.resource_type.value,
            "access_mode": self.access_mode.value,
            "target_identifier": self.target_identifier
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutionResource':
        return cls(
            id=str(data.get("id", "")),
            resource_type=ResourceType(data.get("resource_type")),
            access_mode=ResourceAccessMode(data.get("access_mode")),
            target_identifier=str(data.get("target_identifier", ""))
        )


@dataclass
class ExecutionDependency:
    """A typed dependency edge between two execution tasks."""
    source_task_id: str  # Prerequisite task
    target_task_id: str  # Dependent task
    dep_type: DependencyType
    rationale: str
    lineage_ref: str = ""

    def compute_canonical_hash(self) -> str:
        payload = {
            "source_task_id": self.source_task_id,
            "target_task_id": self.target_task_id,
            "dep_type": self.dep_type.value,
            "rationale": self.rationale,
            "lineage_ref": self.lineage_ref
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_task_id": self.source_task_id,
            "target_task_id": self.target_task_id,
            "dep_type": self.dep_type.value,
            "rationale": self.rationale,
            "lineage_ref": self.lineage_ref
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutionDependency':
        return cls(
            source_task_id=str(data.get("source_task_id", "")),
            target_task_id=str(data.get("target_task_id", "")),
            dep_type=DependencyType(data.get("dep_type")),
            rationale=str(data.get("rationale", "")),
            lineage_ref=str(data.get("lineage_ref", ""))
        )


@dataclass
class ExecutionConstraint:
    """Execution constraint enforcing ordering, mutual exclusion, or gating."""
    id: str
    kind: str
    applies_to_tasks: List[str]
    rule: str
    fail_closed: bool = True

    def compute_canonical_hash(self) -> str:
        payload = {
            "id": self.id,
            "kind": self.kind,
            "applies_to_tasks": sorted(self.applies_to_tasks),
            "rule": self.rule,
            "fail_closed": self.fail_closed
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "applies_to_tasks": sorted(self.applies_to_tasks),
            "rule": self.rule,
            "fail_closed": self.fail_closed
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutionConstraint':
        return cls(
            id=str(data.get("id", "")),
            kind=str(data.get("kind", "")),
            applies_to_tasks=list(data.get("applies_to_tasks", [])),
            rule=str(data.get("rule", "")),
            fail_closed=bool(data.get("fail_closed", True))
        )


@dataclass
class AgentCapability:
    """Specification of an agent's architectural competencies and execution role."""
    id: str
    agent_role: str
    supported_task_categories: List[str]
    supported_operation_classes: List[str]
    supported_component_types: List[str]
    requires_exclusive_lock: bool = False

    def compute_canonical_hash(self) -> str:
        payload = {
            "id": self.id,
            "agent_role": self.agent_role,
            "supported_task_categories": sorted(self.supported_task_categories),
            "supported_operation_classes": sorted(self.supported_operation_classes),
            "supported_component_types": sorted(self.supported_component_types),
            "requires_exclusive_lock": self.requires_exclusive_lock
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "agent_role": self.agent_role,
            "supported_task_categories": sorted(self.supported_task_categories),
            "supported_operation_classes": sorted(self.supported_operation_classes),
            "supported_component_types": sorted(self.supported_component_types),
            "requires_exclusive_lock": self.requires_exclusive_lock
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentCapability':
        return cls(
            id=str(data.get("id", "")),
            agent_role=str(data.get("agent_role", "")),
            supported_task_categories=list(data.get("supported_task_categories", [])),
            supported_operation_classes=list(data.get("supported_operation_classes", [])),
            supported_component_types=list(data.get("supported_component_types", [])),
            requires_exclusive_lock=bool(data.get("requires_exclusive_lock", False))
        )


@dataclass
class AgentAssignment:
    """An authoritative assignment of an execution task to a capable agent role."""
    task_id: str
    agent_role: str
    agent_capability_id: str
    assignment_rationale: str

    def compute_canonical_hash(self) -> str:
        payload = {
            "task_id": self.task_id,
            "agent_role": self.agent_role,
            "agent_capability_id": self.agent_capability_id,
            "assignment_rationale": self.assignment_rationale
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "agent_role": self.agent_role,
            "agent_capability_id": self.agent_capability_id,
            "assignment_rationale": self.assignment_rationale
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentAssignment':
        return cls(
            task_id=str(data.get("task_id", "")),
            agent_role=str(data.get("agent_role", "")),
            agent_capability_id=str(data.get("agent_capability_id", "")),
            assignment_rationale=str(data.get("assignment_rationale", ""))
        )


@dataclass
class ExecutionTask:
    """An execution-ready task enriched with explicit dependencies, resource locks, and agent requirements."""
    id: str
    source_task_id: str
    title: str
    description: str
    category: str
    execution_mode: ExecutionMode
    risk_level: TaskRiskLevel
    status: ExecutionTaskStatus
    dependencies: List[ExecutionDependency] = field(default_factory=list)
    required_resources: List[ExecutionResource] = field(default_factory=list)
    required_agent_capability: str = "general_coding"
    assigned_agent: Optional[AgentAssignment] = None
    parent_lld_id: str = ""
    source_task_hash: str = ""
    source_lld_hash: str = ""
    source_binding_hashes: List[str] = field(default_factory=list)
    parent_req_ids: List[str] = field(default_factory=list)
    parent_behavior_ids: List[str] = field(default_factory=list)
    verification_criteria: List[str] = field(default_factory=list)
    task_hash: str = ""

    def compute_canonical_hash(self) -> str:
        """Computes deterministic SHA-256 digest over complete execution task definition."""
        payload = {
            "id": self.id,
            "source_task_id": self.source_task_id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "execution_mode": self.execution_mode.value,
            "risk_level": self.risk_level.value,
            "dependencies": sorted([d.compute_canonical_hash() for d in self.dependencies]),
            "required_resources": sorted([r.compute_canonical_hash() for r in self.required_resources]),
            "required_agent_capability": self.required_agent_capability,
            "assigned_agent": self.assigned_agent.compute_canonical_hash() if self.assigned_agent else "",
            "parent_lld_id": self.parent_lld_id,
            "source_task_hash": self.source_task_hash,
            "source_lld_hash": self.source_lld_hash,
            "source_binding_hashes": sorted(self.source_binding_hashes),
            "parent_req_ids": sorted(self.parent_req_ids),
            "parent_behavior_ids": sorted(self.parent_behavior_ids),
            "verification_criteria": sorted(self.verification_criteria)
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_task_id": self.source_task_id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "execution_mode": self.execution_mode.value,
            "risk_level": self.risk_level.value,
            "status": self.status.value,
            "dependencies": [d.to_dict() for d in self.dependencies],
            "required_resources": [r.to_dict() for r in self.required_resources],
            "required_agent_capability": self.required_agent_capability,
            "assigned_agent": self.assigned_agent.to_dict() if self.assigned_agent else None,
            "parent_lld_id": self.parent_lld_id,
            "source_task_hash": self.source_task_hash,
            "source_lld_hash": self.source_lld_hash,
            "source_binding_hashes": sorted(self.source_binding_hashes),
            "parent_req_ids": sorted(self.parent_req_ids),
            "parent_behavior_ids": sorted(self.parent_behavior_ids),
            "verification_criteria": sorted(self.verification_criteria),
            "task_hash": self.task_hash or self.compute_canonical_hash()
        }

    @classmethod
    def from_governed_dict(cls, data: Dict[str, Any]) -> 'ExecutionTask':
        return cls.from_dict(data, strict=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], strict: bool = False) -> 'ExecutionTask':
        if strict:
            mandatory_fields = [
                "id", "source_task_id", "title", "description", "category",
                "execution_mode", "risk_level", "status", "parent_lld_id",
                "source_task_hash", "source_lld_hash", "source_binding_hashes",
                "parent_req_ids", "parent_behavior_ids", "verification_criteria",
                "task_hash"
            ]
            for f in mandatory_fields:
                if f not in data or data[f] is None:
                    raise ValueError(f"Missing mandatory '{f}' in ExecutionTask governed payload (strict mode)")

        task = cls(
            id=str(data.get("id", "")),
            source_task_id=str(data.get("source_task_id", "")),
            title=str(data.get("title", "")),
            description=str(data.get("description", "")),
            category=str(data.get("category", "")),
            execution_mode=ExecutionMode(data.get("execution_mode", "serial")),
            risk_level=TaskRiskLevel(data.get("risk_level", "low")),
            status=ExecutionTaskStatus(data.get("status", "ready")),
            dependencies=[ExecutionDependency.from_dict(d) for d in data.get("dependencies", [])],
            required_resources=[ExecutionResource.from_dict(r) for r in data.get("required_resources", [])],
            required_agent_capability=str(data.get("required_agent_capability", "general_coding")),
            assigned_agent=AgentAssignment.from_dict(data["assigned_agent"]) if data.get("assigned_agent") else None,
            parent_lld_id=str(data.get("parent_lld_id", "")),
            source_task_hash=str(data.get("source_task_hash", "")),
            source_lld_hash=str(data.get("source_lld_hash", "")),
            source_binding_hashes=list(data.get("source_binding_hashes", [])),
            parent_req_ids=list(data.get("parent_req_ids", [])),
            parent_behavior_ids=list(data.get("parent_behavior_ids", [])),
            verification_criteria=list(data.get("verification_criteria", [])),
            task_hash=str(data.get("task_hash", ""))
        )

        if strict:
            computed_hash = task.compute_canonical_hash()
            if data["task_hash"] != computed_hash:
                raise ValueError(
                    f"ExecutionTask '{task.id}' task_hash mismatch (provided: {data['task_hash'][:8]}, computed: {computed_hash[:8]})"
                )
        return task


@dataclass
class ExecutionBatch:
    """A proven conflict-free set of execution tasks scheduled together."""
    batch_id: int
    tasks: List[ExecutionTask]
    execution_mode: ExecutionMode
    estimated_risk: TaskRiskLevel
    batch_hash: str = ""

    def compute_canonical_hash(self) -> str:
        payload = {
            "batch_id": self.batch_id,
            "tasks": sorted([t.compute_canonical_hash() for t in self.tasks]),
            "execution_mode": self.execution_mode.value,
            "estimated_risk": self.estimated_risk.value
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "tasks": [t.to_dict() for t in self.tasks],
            "execution_mode": self.execution_mode.value,
            "estimated_risk": self.estimated_risk.value,
            "batch_hash": self.batch_hash or self.compute_canonical_hash()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], strict: bool = False) -> 'ExecutionBatch':
        batch = cls(
            batch_id=int(data.get("batch_id", 0)),
            tasks=[ExecutionTask.from_dict(t, strict=strict) for t in data.get("tasks", [])],
            execution_mode=ExecutionMode(data.get("execution_mode", "serial")),
            estimated_risk=TaskRiskLevel(data.get("estimated_risk", "low")),
            batch_hash=str(data.get("batch_hash", ""))
        )
        if strict:
            computed = batch.compute_canonical_hash()
            if data.get("batch_hash") and data["batch_hash"] != computed:
                raise ValueError(f"ExecutionBatch '{batch.batch_id}' hash mismatch")
        return batch


@dataclass
class ExecutionCheckpoint:
    """A deterministic execution gate with explicit failure invalidation scope."""
    checkpoint_id: str
    after_batch_id: int
    verification_gates: List[str]
    invalidation_scope: Dict[str, List[str]]  # task_id -> downstream task_ids invalidated on failure
    checkpoint_hash: str = ""

    def compute_canonical_hash(self) -> str:
        payload = {
            "checkpoint_id": self.checkpoint_id,
            "after_batch_id": self.after_batch_id,
            "verification_gates": sorted(self.verification_gates),
            "invalidation_scope": {k: sorted(v) for k, v in self.invalidation_scope.items()}
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "after_batch_id": self.after_batch_id,
            "verification_gates": sorted(self.verification_gates),
            "invalidation_scope": {k: sorted(v) for k, v in self.invalidation_scope.items()},
            "checkpoint_hash": self.checkpoint_hash or self.compute_canonical_hash()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutionCheckpoint':
        return cls(
            checkpoint_id=str(data.get("checkpoint_id", "")),
            after_batch_id=int(data.get("after_batch_id", 0)),
            verification_gates=list(data.get("verification_gates", [])),
            invalidation_scope=dict(data.get("invalidation_scope", {})),
            checkpoint_hash=str(data.get("checkpoint_hash", ""))
        )


@dataclass
class ExecutionPlan:
    """The authoritative, immutable, cryptographically verifiable execution DAG and scheduling plan."""
    plan_id: str
    version: int
    tasks: Dict[str, ExecutionTask]
    batches: List[ExecutionBatch]
    checkpoints: List[ExecutionCheckpoint]
    dependency_dag: Dict[str, List[str]]  # task_id -> list of prerequisite task_ids
    reverse_dag: Dict[str, List[str]]     # task_id -> list of dependent task_ids
    invalidation_graph: Dict[str, List[str]]  # task_id -> complete downstream transitive cascade
    source_tasks_hash: str
    plan_hash: str = ""
    is_valid: bool = True
    validation_reasons: List[str] = field(default_factory=list)

    def compute_canonical_hash(self) -> str:
        """Computes deterministic SHA-256 digest over complete execution plan."""
        payload = {
            "plan_id": self.plan_id,
            "version": self.version,
            "tasks": {k: self.tasks[k].compute_canonical_hash() for k in sorted(self.tasks.keys())},
            "batches": [b.compute_canonical_hash() for b in self.batches],
            "checkpoints": [c.compute_canonical_hash() for c in self.checkpoints],
            "dependency_dag": {k: sorted(v) for k, v in sorted(self.dependency_dag.items())},
            "reverse_dag": {k: sorted(v) for k, v in sorted(self.reverse_dag.items())},
            "invalidation_graph": {k: sorted(v) for k, v in sorted(self.invalidation_graph.items())},
            "source_tasks_hash": self.source_tasks_hash,
            "is_valid": self.is_valid,
            "validation_reasons": sorted(self.validation_reasons)
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "version": self.version,
            "tasks": {k: v.to_dict() for k, v in self.tasks.items()},
            "batches": [b.to_dict() for b in self.batches],
            "checkpoints": [c.to_dict() for c in self.checkpoints],
            "dependency_dag": {k: sorted(v) for k, v in self.dependency_dag.items()},
            "reverse_dag": {k: sorted(v) for k, v in self.reverse_dag.items()},
            "invalidation_graph": {k: sorted(v) for k, v in self.invalidation_graph.items()},
            "source_tasks_hash": self.source_tasks_hash,
            "plan_hash": self.plan_hash or self.compute_canonical_hash(),
            "is_valid": self.is_valid,
            "validation_reasons": self.validation_reasons
        }

    @classmethod
    def from_governed_dict(cls, data: Dict[str, Any]) -> 'ExecutionPlan':
        return cls.from_dict(data, strict=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], strict: bool = False) -> 'ExecutionPlan':
        if strict:
            mandatory_fields = [
                "plan_id", "version", "tasks", "batches", "checkpoints",
                "dependency_dag", "reverse_dag", "invalidation_graph",
                "source_tasks_hash", "plan_hash", "is_valid"
            ]
            for f in mandatory_fields:
                if f not in data or data[f] is None:
                    raise ValueError(f"Missing mandatory '{f}' in ExecutionPlan governed payload (strict mode)")

            ver = data.get("version")
            if type(ver) is not int or ver <= 0:
                raise ValueError(f"ExecutionPlan version must be positive int, got {ver!r}")

        tasks_dict = {
            k: ExecutionTask.from_dict(v, strict=strict)
            for k, v in data.get("tasks", {}).items()
        }
        batches = [ExecutionBatch.from_dict(b, strict=strict) for b in data.get("batches", [])]
        checkpoints = [ExecutionCheckpoint.from_dict(c) for c in data.get("checkpoints", [])]

        plan = cls(
            plan_id=str(data.get("plan_id", "")),
            version=int(data.get("version", 1)),
            tasks=tasks_dict,
            batches=batches,
            checkpoints=checkpoints,
            dependency_dag={k: list(v) for k, v in data.get("dependency_dag", {}).items()},
            reverse_dag={k: list(v) for k, v in data.get("reverse_dag", {}).items()},
            invalidation_graph={k: list(v) for k, v in data.get("invalidation_graph", {}).items()},
            source_tasks_hash=str(data.get("source_tasks_hash", "")),
            plan_hash=str(data.get("plan_hash", "")),
            is_valid=bool(data.get("is_valid", True)),
            validation_reasons=list(data.get("validation_reasons", []))
        )

        if strict:
            computed_hash = plan.compute_canonical_hash()
            if data["plan_hash"] != computed_hash:
                raise ValueError(
                    f"ExecutionPlan '{plan.plan_id}' plan_hash mismatch (provided: {data['plan_hash'][:8]}, computed: {computed_hash[:8]})"
                )
        return plan
