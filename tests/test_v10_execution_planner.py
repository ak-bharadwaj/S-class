"""
S-Class EOS V10 - Comprehensive Execution Planner & DAG Resolution Test Suite

Validates:
1. Execution IR structure, serialization, and canonical SHA-256 digests.
2. Architectural dependency resolution (Backend contracts before UI, State transitions, Requirement dependencies).
3. Fail-closed cycle detection (CyclicDependencyError).
4. Proven Parallelism Safety (Resource collisions & State collisions serialized into separate batches).
5. Agent capability matching and capability mismatch rejection.
6. Deterministic Checkpoints & Downstream Failure Invalidation Scopes.
7. Cryptographic plan reproducibility and strict governed deserialization.
8. Anti-hallucination & PROPOSED artifact execution barriers.
"""

import os
import json
import shutil
import tempfile
import unittest

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
from execution_plan_compiler import ExecutionPlanCompiler, DEFAULT_AGENT_CAPABILITIES
from task_compiler import TaskRecord, TaskCategory
from lld_compiler import LLDComponent, LLDComponentType, LLDParentRef, ComponentExecutionCapability, UIInteractionCapability
from requirement_ir import RequirementGraph, RequirementNode, RequirementKind, EpistemicStatus, ProvenanceKind
from behavior_graph import BehaviorGraph, BehaviorNode, BehaviorNodeType
from hld_compiler import HLDDesign, HLDModule
from artifact_governor import ArtifactGovernor


class TestV10ExecutionPlanner(unittest.TestCase):
    """Test suite for V10 Execution Planner & DAG Resolution Engine."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sclass_v10_test_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # V10.1: Execution IR & Canonical Hash Verification
    # -------------------------------------------------------------------------
    def test_v10_1_execution_ir_canonical_hashing_and_strict_validation(self):
        """V10.1: ExecutionTask, ExecutionBatch, and ExecutionPlan have deterministic canonical hashes."""
        res = ExecutionResource("res_1", ResourceType.FILESYSTEM_FILE, ResourceAccessMode.WRITE_EXCLUSIVE, "src/main.py")
        dep = ExecutionDependency("ETSK-001", "ETSK-002", DependencyType.HARD_PREREQUISITE, "Prerequisite backend contract")
        agent = AgentAssignment("ETSK-002", "backend_engineer", "cap_backend_engineer", "Matches API endpoint")

        task = ExecutionTask(
            id="ETSK-002",
            source_task_id="TASK-002",
            title="Implement Core Controller",
            description="Build core controller",
            category="api_endpoint",
            execution_mode=ExecutionMode.SERIAL,
            risk_level=TaskRiskLevel.MEDIUM,
            status=ExecutionTaskStatus.READY,
            dependencies=[dep],
            required_resources=[res],
            required_agent_capability="backend_engineer",
            assigned_agent=agent,
            parent_lld_id="ctrl_core",
            source_task_hash="task_hash_123",
            source_lld_hash="lld_hash_123",
            source_binding_hashes=["binding_hash_1"],
            parent_req_ids=["REQ-001"],
            parent_behavior_ids=["cmd_core"],
            verification_criteria=["Given core exists", "When action runs", "Then commits"]
        )
        task.task_hash = task.compute_canonical_hash()

        # 1. Deterministic task hash
        task_dict = task.to_dict()
        rehydrated_task = ExecutionTask.from_governed_dict(task_dict)
        self.assertEqual(rehydrated_task.task_hash, task.task_hash)

        # 2. Tampered task hash fails closed in strict mode
        bad_task_dict = dict(task_dict)
        bad_task_dict["task_hash"] = "tampered_hash_9999"
        with self.assertRaises(ValueError):
            ExecutionTask.from_governed_dict(bad_task_dict)

        # 3. Missing mandatory fields in strict mode fail closed
        incomplete_task_dict = dict(task_dict)
        incomplete_task_dict.pop("source_lld_hash")
        with self.assertRaises(ValueError):
            ExecutionTask.from_governed_dict(incomplete_task_dict)

    # -------------------------------------------------------------------------
    # V10.2: Dependency Derivation Correctness
    # -------------------------------------------------------------------------
    def test_v10_2_dependency_derivation_backend_before_frontend_and_requirements(self):
        """V10.2: Resolver derives backend contract precedence before UI and requirement dependencies."""
        b_node_auth = BehaviorNode("cmd_auth", "User Login", BehaviorNodeType.COMMAND, "user", "auth", EpistemicStatus.EXPLICIT, ProvenanceKind.EXPLICIT, 1.0)
        b_node_dash = BehaviorNode("query_dash", "View Dashboard", BehaviorNodeType.QUERY, "user", "dash", EpistemicStatus.EXPLICIT, ProvenanceKind.EXPLICIT, 1.0)
        b_graph = BehaviorGraph(version=1)
        b_graph.add_node(b_node_auth)
        b_graph.add_node(b_node_dash)

        r_node_auth = RequirementNode("REQ-AUTH", RequirementKind.FUNCTIONAL, "Login requirement", "user", "cmd_auth", "auth", source_behaviors=["cmd_auth"])
        r_node_dash = RequirementNode("REQ-DASH", RequirementKind.FUNCTIONAL, "Dashboard requirement", "user", "query_dash", "dash", source_behaviors=["query_dash"], dependencies=["REQ-AUTH"])
        r_graph = RequirementGraph(version=1)
        r_graph.add_requirement(r_node_auth)
        r_graph.add_requirement(r_node_dash)

        mod_core = HLDModule(id="mod_core", name="Core Module", system_boundary="internal", owned_entities=["auth", "dash"], owned_capabilities=["cmd_auth", "query_dash"])
        hld = HLDDesign("HLD-001", "Modular Monolith", [mod_core], [], version=1)

        comp_backend = LLDComponent(
            id="ctrl_auth", name="Auth Controller", component_type=LLDComponentType.CONTROLLER,
            parent=LLDParentRef(hld_id="mod_core", req_ids=["REQ-AUTH"], behavior_ids=["cmd_auth"]),
            role="backend_controller", execution_capability=ComponentExecutionCapability.MUTATE,
            api_endpoints=["POST /api/auth/login"]
        )
        comp_backend.component_hash = comp_backend.compute_canonical_hash()

        comp_ui = LLDComponent(
            id="ui_dashboard", name="Dashboard View", component_type=LLDComponentType.UI_SURFACE,
            parent=LLDParentRef(hld_id="mod_core", req_ids=["REQ-DASH"], behavior_ids=["query_dash"]),
            role="frontend_interface", interaction_capability=UIInteractionCapability.DISPLAYS_DATA,
            route="/dashboard"
        )
        comp_ui.component_hash = comp_ui.compute_canonical_hash()

        task_backend = TaskRecord("TSK-001", "Implement Auth API", "desc", TaskCategory.API_ENDPOINT, comp_backend.id, "mod_core", ["REQ-AUTH"], ["cmd_auth"], source_lld_hash=comp_backend.component_hash)
        task_backend.task_hash = task_backend.compute_canonical_hash()

        task_ui = TaskRecord("TSK-002", "Construct Dashboard UI", "desc", TaskCategory.UI_COMPONENT, comp_ui.id, "mod_core", ["REQ-DASH"], ["query_dash"], source_lld_hash=comp_ui.component_hash)
        task_ui.task_hash = task_ui.compute_canonical_hash()

        plan = ExecutionPlanCompiler.compile_execution_plan(
            tasks=[task_backend, task_ui],
            lld_components=[comp_backend, comp_ui],
            r_graph=r_graph,
            b_graph=b_graph,
            hld=hld
        )

        self.assertTrue(plan.is_valid)
        self.assertIn("ETSK-001", plan.dependency_dag["ETSK-002"], "UI Task ETSK-002 MUST depend on Backend Task ETSK-001!")
        self.assertEqual(plan.batches[0].tasks[0].id, "ETSK-001", "Batch 1 MUST contain Backend Task ETSK-001")
        self.assertEqual(plan.batches[1].tasks[0].id, "ETSK-002", "Batch 2 MUST contain UI Task ETSK-002")

    # -------------------------------------------------------------------------
    # V10.3: Cycle Rejection
    # -------------------------------------------------------------------------
    def test_v10_3_cyclic_dependency_rejection(self):
        """V10.3: Cyclic dependencies between tasks are detected and rejected fail-closed."""
        task1 = ExecutionTask(
            id="ETSK-A", source_task_id="TSK-A", title="Task A", description="A", category="api_endpoint",
            execution_mode=ExecutionMode.SERIAL, risk_level=TaskRiskLevel.LOW, status=ExecutionTaskStatus.READY,
            dependencies=[ExecutionDependency("ETSK-B", "ETSK-A", DependencyType.HARD_PREREQUISITE, "A depends on B")]
        )
        task2 = ExecutionTask(
            id="ETSK-B", source_task_id="TSK-B", title="Task B", description="B", category="api_endpoint",
            execution_mode=ExecutionMode.SERIAL, risk_level=TaskRiskLevel.LOW, status=ExecutionTaskStatus.READY,
            dependencies=[ExecutionDependency("ETSK-A", "ETSK-B", DependencyType.HARD_PREREQUISITE, "B depends on A")]
        )

        with self.assertRaises(CyclicDependencyError):
            ExecutionDependencyResolver.resolve_dependencies({"ETSK-A": task1, "ETSK-B": task2})

    # -------------------------------------------------------------------------
    # V10.4 & V10.6: Proven Parallelism Safety
    # -------------------------------------------------------------------------
    def test_v10_4_parallel_safety_and_resource_collision_serialization(self):
        """V10.4: Independent non-conflicting tasks run PARALLEL; shared write file conflicts serialize."""
        # 1. Two completely independent tasks with different files -> PARALLEL
        comp1 = LLDComponent("ctrl_inv", "Inventory", LLDComponentType.CONTROLLER, LLDParentRef("mod_inv", ["REQ-1"], ["cmd_inv"]), "backend_controller", ComponentExecutionCapability.MUTATE, api_endpoints=["POST /api/inv"])
        comp1.component_hash = comp1.compute_canonical_hash()
        comp2 = LLDComponent("ctrl_ord", "Orders", LLDComponentType.CONTROLLER, LLDParentRef("mod_ord", ["REQ-2"], ["cmd_ord"]), "backend_controller", ComponentExecutionCapability.MUTATE, api_endpoints=["POST /api/ord"])
        comp2.component_hash = comp2.compute_canonical_hash()

        t1 = TaskRecord("TSK-101", "Implement Inventory", "desc", TaskCategory.API_ENDPOINT, comp1.id, "mod_inv", ["REQ-1"], ["cmd_inv"], source_lld_hash=comp1.component_hash)
        t1.task_hash = t1.compute_canonical_hash()
        t2 = TaskRecord("TSK-102", "Implement Orders", "desc", TaskCategory.API_ENDPOINT, comp2.id, "mod_ord", ["REQ-2"], ["cmd_ord"], source_lld_hash=comp2.component_hash)
        t2.task_hash = t2.compute_canonical_hash()

        plan_parallel = ExecutionPlanCompiler.compile_execution_plan([t1, t2], [comp1, comp2])
        self.assertTrue(plan_parallel.is_valid)
        self.assertEqual(len(plan_parallel.batches), 1, "Independent tasks must be grouped in a single parallel batch")
        self.assertEqual(plan_parallel.batches[0].execution_mode, ExecutionMode.PARALLEL)
        self.assertEqual(len(plan_parallel.batches[0].tasks), 2)

        # 2. Two tasks modifying the SAME component/file -> SERIAL
        t1_same = TaskRecord("TSK-201", "Implement Endpoint 1", "desc", TaskCategory.API_ENDPOINT, comp1.id, "mod_inv", ["REQ-1"], ["cmd_inv"], source_lld_hash=comp1.component_hash)
        t1_same.task_hash = t1_same.compute_canonical_hash()
        t2_same = TaskRecord("TSK-202", "Implement Endpoint 2", "desc", TaskCategory.API_ENDPOINT, comp1.id, "mod_inv", ["REQ-1"], ["cmd_inv"], source_lld_hash=comp1.component_hash)
        t2_same.task_hash = t2_same.compute_canonical_hash()

        plan_serial = ExecutionPlanCompiler.compile_execution_plan([t1_same, t2_same], [comp1])
        self.assertTrue(plan_serial.is_valid)
        self.assertEqual(len(plan_serial.batches), 2, "Tasks with shared write resource MUST be serialized into separate batches")
        self.assertEqual(plan_serial.batches[0].tasks[0].id, "ETSK-201")
        self.assertEqual(plan_serial.batches[1].tasks[0].id, "ETSK-202")

    # -------------------------------------------------------------------------
    # V10.5: Agent Capability Matching
    # -------------------------------------------------------------------------
    def test_v10_5_agent_capability_matching_and_rejection(self):
        """V10.5: Matching agent roles assigned to tasks; unsupported tasks flagged invalid."""
        comp = LLDComponent("ctrl_test", "Test Controller", LLDComponentType.CONTROLLER, LLDParentRef("mod_t", ["REQ-1"], ["cmd_t"]), "backend_controller", ComponentExecutionCapability.MUTATE, api_endpoints=["POST /api/t"])
        comp.component_hash = comp.compute_canonical_hash()
        task = TaskRecord("TSK-301", "Backend Task", "desc", TaskCategory.API_ENDPOINT, comp.id, "mod_t", ["REQ-1"], ["cmd_t"], source_lld_hash=comp.component_hash)
        task.task_hash = task.compute_canonical_hash()

        # Valid matching
        plan = ExecutionPlanCompiler.compile_execution_plan([task], [comp])
        self.assertTrue(plan.is_valid)
        assigned = plan.tasks["ETSK-301"].assigned_agent
        self.assertIsNotNone(assigned)
        self.assertEqual(assigned.agent_role, "backend_engineer")

        # Unsupported agent capabilities -> Plan marked invalid
        empty_agent_caps = {}
        plan_no_agents = ExecutionPlanCompiler.compile_execution_plan([task], [comp], agent_capabilities=empty_agent_caps)
        self.assertFalse(plan_no_agents.is_valid)
        self.assertTrue(any("has no capable agent assignment" in r for r in plan_no_agents.validation_reasons))

    # -------------------------------------------------------------------------
    # V10.7: Checkpoints & Failure Invalidation Cascades
    # -------------------------------------------------------------------------
    def test_v10_7_checkpoints_and_failure_invalidation_scopes(self):
        """V10.7: Downstream invalidation scopes correctly compute transitive cascade of failed tasks."""
        comp_a = LLDComponent("ctrl_a", "A", LLDComponentType.CONTROLLER, LLDParentRef("mod_a", ["REQ-A"], ["cmd_a"]), "backend_controller", ComponentExecutionCapability.MUTATE, api_endpoints=["POST /a"])
        comp_a.component_hash = comp_a.compute_canonical_hash()
        comp_b = LLDComponent("ctrl_b", "B", LLDComponentType.CONTROLLER, LLDParentRef("mod_b", ["REQ-B"], ["cmd_b"]), "backend_controller", ComponentExecutionCapability.MUTATE, api_endpoints=["POST /b"])
        comp_b.component_hash = comp_b.compute_canonical_hash()
        comp_c = LLDComponent("ctrl_c", "C", LLDComponentType.CONTROLLER, LLDParentRef("mod_c", ["REQ-C"], ["cmd_c"]), "backend_controller", ComponentExecutionCapability.MUTATE, api_endpoints=["POST /c"])
        comp_c.component_hash = comp_c.compute_canonical_hash()

        r_graph = RequirementGraph(version=1)
        r_graph.add_requirement(RequirementNode("REQ-A", RequirementKind.FUNCTIONAL, "Req A", "u", "cmd_a", "a", source_behaviors=["cmd_a"]))
        r_graph.add_requirement(RequirementNode("REQ-B", RequirementKind.FUNCTIONAL, "Req B", "u", "cmd_b", "b", source_behaviors=["cmd_b"], dependencies=["REQ-A"])) # B depends on A
        r_graph.add_requirement(RequirementNode("REQ-C", RequirementKind.FUNCTIONAL, "Req C", "u", "cmd_c", "c", source_behaviors=["cmd_c"], dependencies=["REQ-B"])) # C depends on B

        ta = TaskRecord("TSK-A", "Task A", "desc", TaskCategory.API_ENDPOINT, comp_a.id, "mod_a", ["REQ-A"], ["cmd_a"], source_lld_hash=comp_a.component_hash)
        ta.task_hash = ta.compute_canonical_hash()
        tb = TaskRecord("TSK-B", "Task B", "desc", TaskCategory.API_ENDPOINT, comp_b.id, "mod_b", ["REQ-B"], ["cmd_b"], source_lld_hash=comp_b.component_hash)
        tb.task_hash = tb.compute_canonical_hash()
        tc = TaskRecord("TSK-C", "Task C", "desc", TaskCategory.API_ENDPOINT, comp_c.id, "mod_c", ["REQ-C"], ["cmd_c"], source_lld_hash=comp_c.component_hash)
        tc.task_hash = tc.compute_canonical_hash()

        plan = ExecutionPlanCompiler.compile_execution_plan([ta, tb, tc], [comp_a, comp_b, comp_c], r_graph=r_graph)
        self.assertTrue(plan.is_valid)

        # Transitive invalidation graph:
        # Failure of ETSK-A invalidates [ETSK-B, ETSK-C]
        self.assertEqual(sorted(plan.invalidation_graph["ETSK-A"]), ["ETSK-B", "ETSK-C"])
        # Failure of ETSK-B invalidates [ETSK-C]
        self.assertEqual(plan.invalidation_graph["ETSK-B"], ["ETSK-C"])
        # Failure of ETSK-C invalidates []
        self.assertEqual(plan.invalidation_graph["ETSK-C"], [])

        # Checkpoint invalidation scopes
        cp1 = plan.checkpoints[0]
        self.assertIn("ETSK-A", cp1.invalidation_scope)
        self.assertEqual(sorted(cp1.invalidation_scope["ETSK-A"]), ["ETSK-B", "ETSK-C"])

    # -------------------------------------------------------------------------
    # V10.8: Cryptographic Plan Persistence & Rehydration
    # -------------------------------------------------------------------------
    def test_v10_8_cryptographic_plan_persistence_and_governed_loading(self):
        """V10.8: ExecutionPlan saves atomically to .agents/execution_plan.json and strictly rehydrates."""
        comp = LLDComponent("ctrl_core", "Core", LLDComponentType.CONTROLLER, LLDParentRef("mod_core", ["REQ-1"], ["cmd_1"]), "backend_controller", ComponentExecutionCapability.MUTATE, api_endpoints=["POST /core"])
        comp.component_hash = comp.compute_canonical_hash()
        task = TaskRecord("TSK-401", "Core Task", "desc", TaskCategory.API_ENDPOINT, comp.id, "mod_core", ["REQ-1"], ["cmd_1"], source_lld_hash=comp.component_hash)
        task.task_hash = task.compute_canonical_hash()

        plan = ExecutionPlanCompiler.compile_execution_plan([task], [comp])
        saved_path = ExecutionPlanCompiler.save_execution_plan(plan, self.test_dir)
        self.assertTrue(os.path.exists(saved_path))

        # Strict governed reload succeeds
        loaded_plan = ExecutionPlanCompiler.load_execution_plan(self.test_dir, strict=True)
        self.assertEqual(loaded_plan.plan_hash, plan.plan_hash)
        self.assertEqual(loaded_plan.version, plan.version)
        self.assertEqual(len(loaded_plan.tasks), len(plan.tasks))

        # Tampering plan on disk fails closed in strict loading
        plan_file = os.path.join(self.test_dir, ".agents", "execution_plan.json")
        with open(plan_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["plan_hash"] = "tampered_plan_digest_0000"
        with open(plan_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        with self.assertRaises(ValueError):
            ExecutionPlanCompiler.load_execution_plan(self.test_dir, strict=True)

    # -------------------------------------------------------------------------
    # V10.9: Anti-Hallucination & Epistemic Execution Barriers
    # -------------------------------------------------------------------------
    def test_v10_9_proposed_candidate_and_speculative_rejection(self):
        """V10.9: ExecutionPlanCompiler blocks tasks derived from PROPOSED_CANDIDATE or purely speculative behaviors."""
        comp = LLDComponent("ctrl_test", "Test", LLDComponentType.CONTROLLER, LLDParentRef("mod_t", ["REQ-1"], ["cmd_1"]), "backend_controller", ComponentExecutionCapability.MUTATE)
        comp.component_hash = comp.compute_canonical_hash()

        # Task claiming PROPOSED_CANDIDATE
        task_prop = TaskRecord("TSK-P", "Implement Component Contract: PROPOSED_CANDIDATE: NO_ENDPOINT_EVIDENCE", "desc", TaskCategory.API_ENDPOINT, comp.id, "mod_t", ["REQ-1"], ["cmd_1"], source_lld_hash=comp.component_hash)
        task_prop.task_hash = task_prop.compute_canonical_hash()

        plan_prop = ExecutionPlanCompiler.compile_execution_plan([task_prop], [comp])
        self.assertFalse(plan_prop.is_valid)
        self.assertTrue(any("derived from ungrounded PROPOSED_CANDIDATE" in r for r in plan_prop.validation_reasons))

        # Task with purely speculative behaviors
        b_node_spec = BehaviorNode("cmd_spec", "Speculative", BehaviorNodeType.COMMAND, "user", "ent", EpistemicStatus.PROPOSED, ProvenanceKind.SPECULATIVE, 0.35)
        b_graph_spec = BehaviorGraph(version=1)
        b_graph_spec.add_node(b_node_spec)
        task_spec = TaskRecord("TSK-S", "Speculative Task", "desc", TaskCategory.API_ENDPOINT, comp.id, "mod_t", ["REQ-1"], ["cmd_spec"], source_lld_hash=comp.component_hash)
        task_spec.task_hash = task_spec.compute_canonical_hash()

        plan_spec = ExecutionPlanCompiler.compile_execution_plan([task_spec], [comp], b_graph=b_graph_spec)
        self.assertFalse(plan_spec.is_valid)
        self.assertTrue(any("has exclusively speculative/proposed behaviors" in r for r in plan_spec.validation_reasons))

    # -------------------------------------------------------------------------
    # V10.10: State-Flow Precondition Ordering
    # -------------------------------------------------------------------------
    def test_v10_10_state_flow_precondition_dependency_ordering(self):
        """V10.10: Resolver orders state transition producer tasks before state transition consumer tasks."""
        # Create Vehicle: DRAFT -> SUBMITTED
        b_create = BehaviorNode("cmd_create_veh", "Create Vehicle", BehaviorNodeType.COMMAND, "agent", "vehicle", EpistemicStatus.EXPLICIT, ProvenanceKind.EXPLICIT, 1.0, from_state="DRAFT", to_state="SUBMITTED")
        # Dispatch Vehicle: SUBMITTED -> DISPATCHED
        b_dispatch = BehaviorNode("cmd_dispatch_veh", "Dispatch Vehicle", BehaviorNodeType.COMMAND, "agent", "vehicle", EpistemicStatus.EXPLICIT, ProvenanceKind.EXPLICIT, 1.0, from_state="SUBMITTED", to_state="DISPATCHED")

        b_graph = BehaviorGraph(version=1)
        b_graph.add_node(b_create)
        b_graph.add_node(b_dispatch)

        comp = LLDComponent("ctrl_veh", "Vehicle Controller", LLDComponentType.CONTROLLER, LLDParentRef("mod_veh", ["REQ-1"], ["cmd_create_veh", "cmd_dispatch_veh"]), "backend_controller", ComponentExecutionCapability.MUTATE)
        comp.component_hash = comp.compute_canonical_hash()

        t_create = TaskRecord("TSK-CREATE", "Create Vehicle", "desc", TaskCategory.STATE_TRANSITION, comp.id, "mod_veh", ["REQ-1"], ["cmd_create_veh"], source_lld_hash=comp.component_hash)
        t_create.task_hash = t_create.compute_canonical_hash()

        t_dispatch = TaskRecord("TSK-DISPATCH", "Dispatch Vehicle", "desc", TaskCategory.STATE_TRANSITION, comp.id, "mod_veh", ["REQ-1"], ["cmd_dispatch_veh"], source_lld_hash=comp.component_hash)
        t_dispatch.task_hash = t_dispatch.compute_canonical_hash()

        plan = ExecutionPlanCompiler.compile_execution_plan([t_create, t_dispatch], [comp], b_graph=b_graph)
        self.assertTrue(plan.is_valid)
        self.assertIn("ETSK-CREATE", plan.dependency_dag["ETSK-DISPATCH"], "Dispatch task MUST depend on Create task via state-flow precondition!")
        self.assertEqual(plan.batches[0].tasks[0].id, "ETSK-CREATE")
        self.assertEqual(plan.batches[1].tasks[0].id, "ETSK-DISPATCH")

    # -------------------------------------------------------------------------
    # V10.11: Deterministic Plan Reproducibility & Plan Hash Invariance
    # -------------------------------------------------------------------------
    def test_v10_11_deterministic_plan_hashing_and_reproducibility(self):
        """V10.11: Multiple compilations of the exact same inputs produce identical plan hashes."""
        comp = LLDComponent("ctrl_test", "Test Controller", LLDComponentType.CONTROLLER, LLDParentRef("mod_t", ["REQ-1"], ["cmd_1"]), "backend_controller", ComponentExecutionCapability.MUTATE, api_endpoints=["POST /api/test"])
        comp.component_hash = comp.compute_canonical_hash()
        task = TaskRecord("TSK-501", "Test Task", "desc", TaskCategory.API_ENDPOINT, comp.id, "mod_t", ["REQ-1"], ["cmd_1"], source_lld_hash=comp.component_hash)
        task.task_hash = task.compute_canonical_hash()

        plan1 = ExecutionPlanCompiler.compile_execution_plan([task], [comp])
        plan2 = ExecutionPlanCompiler.compile_execution_plan([task], [comp])
        self.assertEqual(plan1.plan_hash, plan2.plan_hash, "Identical inputs MUST produce 100% deterministic identical plan_hash digests!")
        self.assertEqual(plan1.batches[0].batch_hash, plan2.batches[0].batch_hash)

    # -------------------------------------------------------------------------
    # V10 Blocker Audits (Zero-Neglect Hardening)
    # -------------------------------------------------------------------------
    def test_v10_blocker_1_agent_capability_operation_class_matching_and_rejection(self):
        """Blocker 1: Agent matching must validate operation class (e.g. read_only agent cannot do command_mutation)."""
        comp = LLDComponent("ctrl_order", "Order Controller", LLDComponentType.CONTROLLER, LLDParentRef("mod_o", ["REQ-1"], ["cmd_order"]), "backend_controller", ComponentExecutionCapability.MUTATE, api_endpoints=["POST /api/order"])
        comp.component_hash = comp.compute_canonical_hash()

        # Task has operation_class = command_mutation
        task = TaskRecord("TSK-601", "Create Order API", "desc", TaskCategory.API_ENDPOINT, comp.id, "mod_o", ["REQ-1"], ["cmd_order"], source_lld_hash=comp.component_hash)
        task.task_hash = task.compute_canonical_hash()

        # Custom agent capability supporting ONLY read_query
        read_only_agent = AgentCapability(
            id="cap_readonly",
            agent_role="readonly_engineer",
            supported_task_categories=["api_endpoint"],
            supported_operation_classes=["read_query"],
            supported_component_types=["controller"],
            requires_exclusive_lock=False
        )

        plan = ExecutionPlanCompiler.compile_execution_plan(
            [task], [comp], agent_capabilities={"cap_readonly": read_only_agent}
        )
        self.assertFalse(plan.is_valid, "Plan MUST be marked invalid when agent lacks supported operation class!")
        self.assertTrue(any("has no capable agent assignment supporting" in r for r in plan.validation_reasons))

        # Governor audit fails closed
        gov_res = ArtifactGovernor.audit_execution_plan_governance(plan, [task], [comp])
        self.assertTrue(gov_res.is_blocked)

    def test_v10_blocker_2_execution_task_source_task_hash_reconciliation_tamper(self):
        """Blocker 2: ExecutionTask source task hash/lld hash/binding hashes mismatch fails closed in Governor."""
        comp = LLDComponent("ctrl_user", "User Controller", LLDComponentType.CONTROLLER, LLDParentRef("mod_u", ["REQ-1"], ["cmd_user"]), "backend_controller", ComponentExecutionCapability.MUTATE, api_endpoints=["POST /api/user"])
        comp.component_hash = comp.compute_canonical_hash()
        task = TaskRecord("TSK-701", "Create User", "desc", TaskCategory.API_ENDPOINT, comp.id, "mod_u", ["REQ-1"], ["cmd_user"], source_lld_hash=comp.component_hash)
        task.task_hash = task.compute_canonical_hash()

        plan = ExecutionPlanCompiler.compile_execution_plan([task], [comp])
        gov_valid = ArtifactGovernor.audit_execution_plan_governance(plan, [task], [comp])
        self.assertFalse(gov_valid.is_blocked)

        # 1. Tamper source_task_hash on ExecutionTask
        exec_t = plan.tasks["ETSK-701"]
        exec_t.source_task_hash = "forged_task_hash_8888"
        exec_t.task_hash = exec_t.compute_canonical_hash()
        plan.plan_hash = plan.compute_canonical_hash()

        gov_tampered = ArtifactGovernor.audit_execution_plan_governance(plan, [task], [comp])
        self.assertTrue(gov_tampered.is_blocked, "Governor MUST block ExecutionTask with tampered source_task_hash!")
        self.assertTrue(any("source_task_hash mismatch" in r for r in gov_tampered.blocking_reasons))

    def test_v10_blocker_3_execution_plan_source_tasks_hash_reconciliation(self):
        """Blocker 3: ExecutionPlan.source_tasks_hash is cryptographically verified against canonical tasks."""
        comp = LLDComponent("ctrl_inv", "Inventory Controller", LLDComponentType.CONTROLLER, LLDParentRef("mod_i", ["REQ-1"], ["cmd_inv"]), "backend_controller", ComponentExecutionCapability.MUTATE, api_endpoints=["POST /api/inv"])
        comp.component_hash = comp.compute_canonical_hash()
        task = TaskRecord("TSK-801", "Inventory API", "desc", TaskCategory.API_ENDPOINT, comp.id, "mod_i", ["REQ-1"], ["cmd_inv"], source_lld_hash=comp.component_hash)
        task.task_hash = task.compute_canonical_hash()

        plan = ExecutionPlanCompiler.compile_execution_plan([task], [comp])

        # Tamper source_tasks_hash while keeping plan_hash consistent
        plan.source_tasks_hash = "forged_source_tasks_hash_9999"
        plan.plan_hash = plan.compute_canonical_hash()

        gov_res = ArtifactGovernor.audit_execution_plan_governance(plan, [task], [comp])
        self.assertTrue(gov_res.is_blocked, "Governor MUST block ExecutionPlan with forged source_tasks_hash!")
        self.assertTrue(any("source_tasks_hash mismatch" in r for r in gov_res.blocking_reasons))

    def test_v10_blocker_4_parallel_state_conflict_semantic_entity_rejection(self):
        """Blocker 4: Tasks mutating the same entity state machine are serialized into separate batches."""
        b_approve = BehaviorNode("cmd_approve_invoice", "Approve Invoice", BehaviorNodeType.COMMAND, "mgr", "invoice", EpistemicStatus.EXPLICIT, ProvenanceKind.EXPLICIT, 1.0, from_state="PENDING", to_state="APPROVED")
        b_pay = BehaviorNode("cmd_pay_invoice", "Pay Invoice", BehaviorNodeType.COMMAND, "acct", "invoice", EpistemicStatus.EXPLICIT, ProvenanceKind.EXPLICIT, 1.0, from_state="APPROVED", to_state="PAID")

        b_graph = BehaviorGraph(version=1)
        b_graph.add_node(b_approve)
        b_graph.add_node(b_pay)

        comp = LLDComponent("ctrl_inv", "Invoice Controller", LLDComponentType.CONTROLLER, LLDParentRef("mod_inv", ["REQ-1"], ["cmd_approve_invoice", "cmd_pay_invoice"]), "backend_controller", ComponentExecutionCapability.MUTATE)
        comp.component_hash = comp.compute_canonical_hash()

        t1 = TaskRecord("TSK-INV-1", "Approve Invoice", "desc", TaskCategory.STATE_TRANSITION, comp.id, "mod_inv", ["REQ-1"], ["cmd_approve_invoice"], source_lld_hash=comp.component_hash)
        t1.task_hash = t1.compute_canonical_hash()
        t2 = TaskRecord("TSK-INV-2", "Pay Invoice", "desc", TaskCategory.STATE_TRANSITION, comp.id, "mod_inv", ["REQ-1"], ["cmd_pay_invoice"], source_lld_hash=comp.component_hash)
        t2.task_hash = t2.compute_canonical_hash()

        plan = ExecutionPlanCompiler.compile_execution_plan([t1, t2], [comp], b_graph=b_graph)
        self.assertTrue(plan.is_valid)
        self.assertEqual(len(plan.batches), 2, "Tasks mutating the same entity state machine MUST be serialized into separate batches!")
        self.assertEqual(plan.batches[0].tasks[0].id, "ETSK-INV-1")
        self.assertEqual(plan.batches[1].tasks[0].id, "ETSK-INV-2")

    def test_v10_blocker_5_unknown_dependency_fails_closed(self):
        """Blocker 5: Declared dependency to unknown task ID fails closed immediately."""
        task = ExecutionTask(
            id="ETSK-901", source_task_id="TSK-901", title="Task with Ghost Dependency", description="desc",
            category="api_endpoint", execution_mode=ExecutionMode.SERIAL, risk_level=TaskRiskLevel.LOW,
            status=ExecutionTaskStatus.READY,
            dependencies=[ExecutionDependency("TSK-GHOST-999", "ETSK-901", DependencyType.HARD_PREREQUISITE, "Depends on ghost task")]
        )

        with self.assertRaises(CyclicDependencyError):
            ExecutionDependencyResolver.resolve_dependencies({"ETSK-901": task})

    def test_v10_blocker_6_architectural_layer_dependency_precision(self):
        """Blocker 6: UI surfaces depend precisely on matching backend services, not all backend tasks across module."""
        comp_profile = LLDComponent("ctrl_profile", "Profile", LLDComponentType.CONTROLLER, LLDParentRef("mod_core", ["REQ-P"], ["cmd_profile"]), "backend_controller", ComponentExecutionCapability.MUTATE, owned_entities=["Profile"])
        comp_profile.component_hash = comp_profile.compute_canonical_hash()

        comp_payment = LLDComponent("ctrl_payment", "Payment", LLDComponentType.CONTROLLER, LLDParentRef("mod_core", ["REQ-M"], ["cmd_payment"]), "backend_controller", ComponentExecutionCapability.MUTATE, owned_entities=["Payment"])
        comp_payment.component_hash = comp_payment.compute_canonical_hash()

        comp_telemetry_be = LLDComponent("ctrl_telemetry", "Telemetry Service", LLDComponentType.CONTROLLER, LLDParentRef("mod_core", ["REQ-T"], ["query_telemetry"]), "backend_controller", ComponentExecutionCapability.READ, owned_entities=["Telemetry"])
        comp_telemetry_be.component_hash = comp_telemetry_be.compute_canonical_hash()

        comp_telemetry_ui = LLDComponent("ui_telemetry", "Telemetry Dashboard", LLDComponentType.UI_SURFACE, LLDParentRef("mod_core", ["REQ-T"], ["query_telemetry"]), "frontend_interface", interaction_capability=UIInteractionCapability.DISPLAYS_DATA, owned_entities=["Telemetry"])
        comp_telemetry_ui.component_hash = comp_telemetry_ui.compute_canonical_hash()

        t_prof = TaskRecord("TSK-PROF", "Profile API", "desc", TaskCategory.API_ENDPOINT, comp_profile.id, "mod_core", ["REQ-P"], ["cmd_profile"], source_lld_hash=comp_profile.component_hash)
        t_prof.task_hash = t_prof.compute_canonical_hash()

        t_pay = TaskRecord("TSK-PAY", "Payment API", "desc", TaskCategory.API_ENDPOINT, comp_payment.id, "mod_core", ["REQ-M"], ["cmd_payment"], source_lld_hash=comp_payment.component_hash)
        t_pay.task_hash = t_pay.compute_canonical_hash()

        t_telem_be = TaskRecord("TSK-TELEM-BE", "Telemetry API", "desc", TaskCategory.API_ENDPOINT, comp_telemetry_be.id, "mod_core", ["REQ-T"], ["query_telemetry"], source_lld_hash=comp_telemetry_be.component_hash)
        t_telem_be.task_hash = t_telem_be.compute_canonical_hash()

        t_telem_ui = TaskRecord("TSK-TELEM-UI", "Telemetry UI", "desc", TaskCategory.UI_COMPONENT, comp_telemetry_ui.id, "mod_core", ["REQ-T"], ["query_telemetry"], source_lld_hash=comp_telemetry_ui.component_hash)
        t_telem_ui.task_hash = t_telem_ui.compute_canonical_hash()

        plan = ExecutionPlanCompiler.compile_execution_plan(
            [t_prof, t_pay, t_telem_be, t_telem_ui],
            [comp_profile, comp_payment, comp_telemetry_be, comp_telemetry_ui]
        )
        self.assertTrue(plan.is_valid)

        # Telemetry UI must depend ONLY on Telemetry BE, NOT on Profile or Payment!
        ui_deps = plan.dependency_dag["ETSK-TELEM-UI"]
        self.assertIn("ETSK-TELEM-BE", ui_deps)
        self.assertNotIn("ETSK-PROF", ui_deps, "Telemetry UI MUST NOT depend on unrelated Profile API!")
        self.assertNotIn("ETSK-PAY", ui_deps, "Telemetry UI MUST NOT depend on unrelated Payment API!")

    def test_v10_blocker_7_checkpoint_strict_hash_verification(self):
        """Blocker 7: ExecutionCheckpoint strict deserialization verifies checkpoint_hash."""
        cp = ExecutionCheckpoint("CHK-001", 1, ["gate_1"], {"ETSK-1": ["ETSK-2"]})
        cp.checkpoint_hash = cp.compute_canonical_hash()

        # Valid rehydration
        rehydrated = ExecutionCheckpoint.from_dict(cp.to_dict(), strict=True)
        self.assertEqual(rehydrated.checkpoint_hash, cp.checkpoint_hash)

        # Tampered checkpoint fails closed
        tampered_dict = cp.to_dict()
        tampered_dict["checkpoint_hash"] = "forged_checkpoint_hash_7777"
        with self.assertRaises(ValueError):
            ExecutionCheckpoint.from_dict(tampered_dict, strict=True)


if __name__ == "__main__":
    unittest.main()
