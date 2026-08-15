"""
S-Class EOS V10.4 - Authoritative Execution Plan Compiler

Compiles governed TaskRecords into a verified, cryptographically bound ExecutionPlan.
Enforces:
1. Proven Parallelism Safety (Zero parallel collisions on dependencies, files, state, or locks)
2. Exact Agent Capability Matching
3. Deterministic Checkpoint & Failure Invalidation Scopes
4. Immutable Plan Hashing & Atomic Persistence
"""

import os
import json
import hashlib
from typing import Dict, List, Set, Any, Optional, Tuple

from execution_ir import (
    ExecutionTask,
    ExecutionTaskStatus,
    ExecutionDependency,
    DependencyType,
    ExecutionMode,
    TaskRiskLevel,
    ResourceType,
    ResourceAccessMode,
    ExecutionResource,
    AgentCapability,
    AgentAssignment,
    ExecutionBatch,
    ExecutionCheckpoint,
    ExecutionPlan
)
from execution_dependency_resolver import ExecutionDependencyResolver, CyclicDependencyError
from task_compiler import TaskRecord, TaskCategory
from lld_compiler import LLDComponent, LLDComponentType
from requirement_ir import RequirementGraph, RequirementNode
from behavior_graph import BehaviorGraph, BehaviorNodeType, EpistemicStatus, ProvenanceKind
from hld_compiler import HLDDesign, HLDModule
from runtime import write_json_atomic, load_json


DEFAULT_AGENT_CAPABILITIES: Dict[str, AgentCapability] = {
    "cap_backend_engineer": AgentCapability(
        id="cap_backend_engineer",
        agent_role="backend_engineer",
        supported_task_categories=["api_endpoint", "state_transition", "audit_log"],
        supported_operation_classes=["command_mutation", "read_query", "state_transition", "event_processing"],
        supported_component_types=["controller", "service", "cli_dispatcher"],
        requires_exclusive_lock=False
    ),
    "cap_frontend_engineer": AgentCapability(
        id="cap_frontend_engineer",
        agent_role="frontend_engineer",
        supported_task_categories=["ui_component"],
        supported_operation_classes=["read_query", "command_mutation"],
        supported_component_types=["ui_surface"],
        requires_exclusive_lock=False
    ),
    "cap_security_auditor": AgentCapability(
        id="cap_security_auditor",
        agent_role="security_auditor",
        supported_task_categories=["authorization_guard", "audit_log"],
        supported_operation_classes=["command_mutation", "read_query"],
        supported_component_types=["controller", "service", "gateway"],
        requires_exclusive_lock=False
    ),
    "cap_qa_engineer": AgentCapability(
        id="cap_qa_engineer",
        agent_role="qa_engineer",
        supported_task_categories=["integration_test", "api_endpoint", "ui_component"],
        supported_operation_classes=["read_query"],
        supported_component_types=["controller", "service", "ui_surface", "cli_dispatcher"],
        requires_exclusive_lock=False
    )
}


class ExecutionPlanCompiler:
    """Compiles governed TaskRecords into verified ExecutionPlans with proven parallelism."""

    @classmethod
    def compile_execution_plan(
        cls,
        tasks: List[TaskRecord],
        lld_components: Optional[List[LLDComponent]] = None,
        r_graph: Optional[RequirementGraph] = None,
        b_graph: Optional[BehaviorGraph] = None,
        hld: Optional[HLDDesign] = None,
        plan_id: str = "EXEC-PLAN-001",
        version: int = 1,
        agent_capabilities: Optional[Dict[str, AgentCapability]] = None
    ) -> ExecutionPlan:
        """
        Main compilation pipeline:
        TaskRecord -> ExecutionTask -> Dependency Resolver -> Parallel Scheduler -> Agent Matcher -> ExecutionPlan.
        """
        agent_caps = agent_capabilities if agent_capabilities is not None else DEFAULT_AGENT_CAPABILITIES
        lld_map = {c.id: c for c in (lld_components or [])}
        validation_reasons: List[str] = []
        is_valid = True

        # 0. Ingest and Validate TaskRecords
        exec_tasks: Dict[str, ExecutionTask] = {}
        for t in tasks:
            # Epistemic Gate: Reject ungrounded PROPOSED_CANDIDATE tasks
            if "PROPOSED_CANDIDATE" in t.title or "PROPOSED_CANDIDATE" in t.description:
                is_valid = False
                validation_reasons.append(f"Task '{t.id}' is derived from ungrounded PROPOSED_CANDIDATE and cannot be executed.")
                continue

            # Check upstream behaviors
            if b_graph and t.parent_behaviors:
                beh_objs = [b_graph.get_node(bid) for bid in t.parent_behaviors if b_graph.get_node(bid)]
                if beh_objs and all(
                    getattr(b, "epistemic_status", None) == EpistemicStatus.PROPOSED or
                    getattr(b, "provenance", None) == ProvenanceKind.SPECULATIVE
                    for b in beh_objs
                ):
                    is_valid = False
                    validation_reasons.append(f"Task '{t.id}' has exclusively speculative/proposed behaviors.")
                    continue

            # Derive operation class from component capability bindings or behavior nodes
            op_class = "command_mutation"
            if parent_comp := lld_map.get(t.parent_lld):
                for b in parent_comp.capability_bindings:
                    if b.behavior_id in t.parent_behaviors and getattr(b, "operation_class", None):
                        op_class = b.operation_class.value if hasattr(b.operation_class, "value") else str(b.operation_class)
                        break
            if op_class == "command_mutation" and b_graph:
                for bid in t.parent_behaviors:
                    b_node = b_graph.get_node(bid)
                    if b_node:
                        if b_node.behavior_type == BehaviorNodeType.QUERY:
                            op_class = "read_query"
                            break
                        elif b_node.behavior_type == BehaviorNodeType.STATE_TRANSITION:
                            op_class = "state_transition"
                            break
            if t.category == TaskCategory.UI_COMPONENT.value:
                op_class = "read_query"

            # Derive resource requirements from component and task metadata
            required_resources = cls._derive_task_resources(t, lld_map.get(t.parent_lld))
            risk_level = cls._assess_task_risk(t, lld_map.get(t.parent_lld))
            req_agent_cap = "backend_engineer" if t.category != TaskCategory.UI_COMPONENT.value else "frontend_engineer"

            exec_t = ExecutionTask(
                id=f"E{t.id}",
                source_task_id=t.id,
                title=t.title,
                description=t.description,
                category=t.category.value if isinstance(t.category, TaskCategory) else str(t.category),
                operation_class=op_class,
                execution_mode=ExecutionMode.SERIAL,  # default, will be upgraded by scheduler
                risk_level=risk_level,
                status=ExecutionTaskStatus.READY,
                dependencies=[],
                required_resources=required_resources,
                required_agent_capability=req_agent_cap,
                assigned_agent=None,
                parent_lld_id=t.parent_lld,
                source_task_hash=t.task_hash,
                source_lld_hash=t.source_lld_hash,
                source_binding_hashes=list(t.source_binding_hashes),
                parent_req_ids=list(t.parent_reqs),
                parent_behavior_ids=list(t.parent_behaviors),
                verification_criteria=list(t.verification_criteria)
            )
            exec_t.task_hash = exec_t.compute_canonical_hash()
            exec_tasks[exec_t.id] = exec_t

        # 1. Dependency Resolution & Topological Graph Generation
        try:
            dep_dag, rev_dag, inv_graph = ExecutionDependencyResolver.resolve_dependencies(
                exec_tasks,
                lld_components=lld_components,
                r_graph=r_graph,
                b_graph=b_graph,
                hld=hld
            )
            topo_order = ExecutionDependencyResolver.compute_topological_order(dep_dag)
        except CyclicDependencyError as e:
            is_valid = False
            validation_reasons.append(str(e))
            dep_dag, rev_dag, inv_graph = {}, {}, {}
            topo_order = list(exec_tasks.keys())

        # 2. Agent Capability Matching (V10.5 - Category, Component Type, AND Operation Class!)
        for t_id, task in exec_tasks.items():
            matched_agent = cls._match_agent_capability(task, lld_map.get(task.parent_lld_id), agent_caps)
            if matched_agent:
                task.assigned_agent = matched_agent
                task.task_hash = task.compute_canonical_hash()
            else:
                is_valid = False
                validation_reasons.append(
                    f"Task '{t_id}' ({task.title}) has no capable agent assignment supporting category '{task.category}', component '{lld_map.get(task.parent_lld_id).component_type.value if lld_map.get(task.parent_lld_id) else 'none'}', and operation class '{task.operation_class}'."
                )

        # 3. Proven Parallel Batch Scheduling (V10.6 - Semantic Entity State & Resource Locking)
        batches = cls._schedule_parallel_batches(exec_tasks, dep_dag, topo_order, lld_map=lld_map, b_graph=b_graph)

        # 4. Checkpoint & Invalidation Scope Construction (V10.7)
        checkpoints = cls._construct_checkpoints(batches, inv_graph)

        # 5. Compute Source Tasks Hash (Canonical Deterministic SHA-256)
        source_tasks_payload = sorted([t.task_hash for t in tasks])
        source_tasks_hash = hashlib.sha256(json.dumps(source_tasks_payload, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()

        # 6. Assemble ExecutionPlan & Compute Canonical Plan Hash
        plan = ExecutionPlan(
            plan_id=plan_id,
            version=version,
            tasks=exec_tasks,
            batches=batches,
            checkpoints=checkpoints,
            dependency_dag=dep_dag,
            reverse_dag=rev_dag,
            invalidation_graph=inv_graph,
            source_tasks_hash=source_tasks_hash,
            is_valid=is_valid,
            validation_reasons=validation_reasons
        )
        plan.plan_hash = plan.compute_canonical_hash()
        return plan

    @classmethod
    def _derive_task_resources(cls, task: TaskRecord, parent_comp: Optional[LLDComponent]) -> List[ExecutionResource]:
        """Derives declarative resource access contracts from component metadata."""
        resources: List[ExecutionResource] = []
        if not parent_comp:
            return resources

        # File write exclusive resource
        route_or_file = parent_comp.route or f"src/{parent_comp.id}.py"
        clean_path = route_or_file.replace("cli://", "cmd/").replace("http://", "api/").replace("/", "_")
        resources.append(ExecutionResource(
            id=f"res_file_{clean_path}",
            resource_type=ResourceType.FILESYSTEM_FILE,
            access_mode=ResourceAccessMode.WRITE_EXCLUSIVE,
            target_identifier=f"src/{parent_comp.id}.py"
        ))

        # Port / Network resource for backend services
        if parent_comp.component_type in [LLDComponentType.CONTROLLER, LLDComponentType.SERVICE]:
            resources.append(ExecutionResource(
                id=f"res_port_{parent_comp.id}",
                resource_type=ResourceType.PORT_RESOURCE,
                access_mode=ResourceAccessMode.READ_SHARED,
                target_identifier="tcp://0.0.0.0:8000"
            ))

        # Entity state resource
        for ent in parent_comp.owned_entities:
            resources.append(ExecutionResource(
                id=f"res_table_{ent.lower()}",
                resource_type=ResourceType.DATABASE_TABLE,
                access_mode=ResourceAccessMode.WRITE_EXCLUSIVE if task.category != "ui_component" else ResourceAccessMode.READ_SHARED,
                target_identifier=f"tbl_{ent.lower()}"
            ))

        return resources

    @classmethod
    def _assess_task_risk(cls, task: TaskRecord, parent_comp: Optional[LLDComponent]) -> TaskRiskLevel:
        """Assesses risk level based on state transitions, audit requirements, and component criticality."""
        crit = " ".join(task.verification_criteria).lower()
        if "403 forbidden" in crit or "security" in crit or "authorization" in crit:
            return TaskRiskLevel.CRITICAL
        if task.category == "state_transition" or "audit log" in crit or (parent_comp and parent_comp.component_type == LLDComponentType.SERVICE):
            return TaskRiskLevel.HIGH
        if task.category == "api_endpoint":
            return TaskRiskLevel.MEDIUM
        return TaskRiskLevel.LOW

    @classmethod
    def _match_agent_capability(
        cls,
        task: ExecutionTask,
        parent_comp: Optional[LLDComponent],
        agent_caps: Dict[str, AgentCapability]
    ) -> Optional[AgentAssignment]:
        """Matches a task with a compatible agent capability specification verifying category, component type, and operation class."""
        comp_type_val = parent_comp.component_type.value if parent_comp else "controller"
        task_cat_val = task.category.lower()
        task_op_class = task.operation_class.lower()

        for cap_id, cap in agent_caps.items():
            if (task_cat_val in [tc.lower() for tc in cap.supported_task_categories] and
                comp_type_val in [ct.lower() for ct in cap.supported_component_types] and
                task_op_class in [op.lower() for op in cap.supported_operation_classes]):
                return AgentAssignment(
                    task_id=task.id,
                    agent_role=cap.agent_role,
                    agent_capability_id=cap.id,
                    assignment_rationale=f"Agent '{cap.agent_role}' supports category '{task_cat_val}', component '{comp_type_val}', and operation class '{task_op_class}'."
                )
        return None

    @classmethod
    def _schedule_parallel_batches(
        cls,
        tasks: Dict[str, ExecutionTask],
        dependency_dag: Dict[str, List[str]],
        topo_order: List[str],
        lld_map: Optional[Dict[str, LLDComponent]] = None,
        b_graph: Optional[BehaviorGraph] = None
    ) -> List[ExecutionBatch]:
        """
        Schedules tasks into proven conflict-free parallel batches.

        Invariant: Two tasks A and B are in the same parallel batch ONLY IF:
        1. A does not depend on B and B does not depend on A.
        2. A and B have NO overlapping WRITE_EXCLUSIVE resources.
        3. A and B have NO canonical entity state-transition collisions.
        """
        batches: List[ExecutionBatch] = []
        completed_tasks: Set[str] = set()
        remaining_tasks = set(tasks.keys())
        batch_counter = 1

        while remaining_tasks:
            # Find all tasks whose prerequisites are completely satisfied
            ready_tasks = [
                t_id for t_id in topo_order
                if t_id in remaining_tasks and set(dependency_dag.get(t_id, [])).issubset(completed_tasks)
            ]

            if not ready_tasks:
                break

            current_batch_tasks: List[ExecutionTask] = []
            claimed_write_resources: Set[str] = set()
            claimed_state_entities: Set[str] = set()

            for t_id in ready_tasks:
                task = tasks[t_id]
                task_write_res = {
                    r.target_identifier for r in task.required_resources
                    if r.access_mode == ResourceAccessMode.WRITE_EXCLUSIVE
                }

                # Semantic State Entity derivation (Blocker 4)
                task_state_entities: Set[str] = set()
                if b_graph:
                    for b_id in task.parent_behavior_ids:
                        b_node = b_graph.get_node(b_id)
                        if b_node and b_node.target_entity_id:
                            if b_node.from_state or b_node.to_state or task.category == "state_transition" or task.operation_class in ["state_transition", "command_mutation"]:
                                task_state_entities.add(b_node.target_entity_id.lower())
                if not task_state_entities and lld_map:
                    if parent_comp := lld_map.get(task.parent_lld_id):
                        if task.category == "state_transition" or task.operation_class in ["state_transition", "command_mutation"]:
                            for ent in parent_comp.owned_entities:
                                task_state_entities.add(ent.lower())

                # Parallel Collision Check
                has_resource_collision = bool(claimed_write_resources.intersection(task_write_res))
                has_state_collision = bool(claimed_state_entities.intersection(task_state_entities))

                if not has_resource_collision and not has_state_collision:
                    # Safe to include in parallel batch
                    current_batch_tasks.append(task)
                    claimed_write_resources.update(task_write_res)
                    claimed_state_entities.update(task_state_entities)

            # Determine batch execution mode and risk
            exec_mode = ExecutionMode.PARALLEL if len(current_batch_tasks) > 1 else ExecutionMode.SERIAL
            for t in current_batch_tasks:
                t.execution_mode = exec_mode

            max_risk = TaskRiskLevel.LOW
            for t in current_batch_tasks:
                if t.risk_level == TaskRiskLevel.CRITICAL:
                    max_risk = TaskRiskLevel.CRITICAL
                    break
                elif t.risk_level == TaskRiskLevel.HIGH and max_risk != TaskRiskLevel.CRITICAL:
                    max_risk = TaskRiskLevel.HIGH
                elif t.risk_level == TaskRiskLevel.MEDIUM and max_risk not in [TaskRiskLevel.CRITICAL, TaskRiskLevel.HIGH]:
                    max_risk = TaskRiskLevel.MEDIUM

            batch = ExecutionBatch(
                batch_id=batch_counter,
                tasks=current_batch_tasks,
                execution_mode=exec_mode,
                estimated_risk=max_risk
            )
            batch.batch_hash = batch.compute_canonical_hash()
            batches.append(batch)
            batch_counter += 1

            for t in current_batch_tasks:
                completed_tasks.add(t.id)
                remaining_tasks.remove(t.id)

        return batches

    @classmethod
    def _construct_checkpoints(
        cls,
        batches: List[ExecutionBatch],
        invalidation_graph: Dict[str, List[str]]
    ) -> List[ExecutionCheckpoint]:
        """Constructs execution verification checkpoints after each batch with deterministic invalidation scopes."""
        checkpoints: List[ExecutionCheckpoint] = []
        for batch in batches:
            # Build invalidation scope mapping for each task in the batch
            batch_inv_scope: Dict[str, List[str]] = {
                t.id: invalidation_graph.get(t.id, []) for t in batch.tasks
            }
            gates = [f"verify_batch_{batch.batch_id}_contracts"]
            if batch.estimated_risk in [TaskRiskLevel.HIGH, TaskRiskLevel.CRITICAL]:
                gates.append(f"security_and_audit_gate_batch_{batch.batch_id}")

            cp = ExecutionCheckpoint(
                checkpoint_id=f"CHK-{batch.batch_id:03d}",
                after_batch_id=batch.batch_id,
                verification_gates=gates,
                invalidation_scope=batch_inv_scope
            )
            cp.checkpoint_hash = cp.compute_canonical_hash()
            checkpoints.append(cp)
        return checkpoints

    @classmethod
    def save_execution_plan(cls, plan: ExecutionPlan, workspace_dir: str) -> str:
        """Atomically saves the execution plan to .agents/execution_plan.json."""
        agents_dir = os.path.join(workspace_dir, ".agents")
        os.makedirs(agents_dir, exist_ok=True)
        plan_path = os.path.join(agents_dir, "execution_plan.json")
        write_json_atomic(plan_path, plan.to_dict())
        return plan_path

    @classmethod
    def load_execution_plan(cls, workspace_dir: str, strict: bool = True) -> ExecutionPlan:
        """Loads and deserializes the execution plan from workspace with governed hash validation."""
        plan_path = os.path.join(workspace_dir, ".agents", "execution_plan.json")
        if not os.path.exists(plan_path):
            raise FileNotFoundError(f"Execution plan not found at '{plan_path}'.")
        data = load_json(plan_path)
        return ExecutionPlan.from_dict(data, strict=strict)
