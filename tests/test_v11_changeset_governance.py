"""
S-Class EOS V11.1/V11.2 — Adversarial ChangeSet & Reconciliation Governance Test Suite (test_v11_changeset_governance.py)

Comprehensive red-team and invariant validation testing:
1. Planning Snapshot Anchor Immutability & Tampering Detection
2. Unauthorized File Modification Rejection (UNAUTHORIZED_FILE_MODIFICATION)
3. Unauthorized File Creation Rejection (UNAUTHORIZED_FILE_CREATION)
4. Unauthorized File Deletion Rejection (UNAUTHORIZED_FILE_DELETION)
5. Stale Baseline / Anchor Mismatch Rejection (STALE_CHANGESET_SOURCE_ANCHOR)
6. Legitimate Authorized ChangeSet Reconciliation & Promotion to Trusted Baseline
7. Post-Verification Mutation & Drift Detection (Live Drift Blocks Transition)
8. Missing Refinement Pipeline Artifact Fails Closed (CHANGESET_LINEAGE_SOURCE_MISSING)
9. Missing Workspace Context Fails Closed (CHANGESET_WORKSPACE_CONTEXT_MISSING)
10. Empty Governed Tasks with Non-Empty ChangeSet Fails Closed (CHANGESET_TASK_SET_MISMATCH)
11. Tampered ExecutionPlan in Pipeline Fails Closed (UPSTREAM_PLAN_INTEGRITY_FAILED)
12. Tampered TaskRecord in Pipeline Fails Closed (GOVERNED_TASK_INTEGRITY_FAILED)
13. Signer Capability Comprehensive Adversarial Boundary Matrix
"""

import os
import shutil
import tempfile
import unittest
import json
import hashlib

from repository_snapshot import (
    RepositorySnapshot,
    RepositorySnapshotEngine,
    FileClassification,
    FileEntry
)
from changeset_ir import (
    AuthorizedChangeSet,
    AuthorizedFileChange,
    FileMutationOp
)
from artifact_governor import (
    ArtifactGovernor,
    GovernanceGateResult,
    FSMTransitionTarget,
    ValidationStatus
)
from behavior_graph import BehaviorGraph, BehaviorNode, BehaviorNodeType, EpistemicStatus
from requirement_ir import RequirementGraph, RequirementNode, RequirementKind
from hld_compiler import HLDDesign, HLDModule
from lld_compiler import (
    LLDComponent,
    LLDComponentType,
    LLDParentRef,
    ComponentExecutionCapability,
    CapabilityBinding,
    OperationClass
)
from task_compiler import TaskRecord, TaskCategory
from execution_ir import ExecutionPlan
from execution_plan_compiler import ExecutionPlanCompiler
from world_model import (
    SovereignCryptoAuthority,
    SovereignSigningCapability
)


class TestV11ChangeSetGovernance(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sclass_v11_changeset_test_")
        self.agents_dir = os.path.join(self.test_dir, ".agents")
        os.makedirs(self.agents_dir, exist_ok=True)
        os.environ["SCLASS_EXECUTION_MODE"] = "TEST"
        SovereignCryptoAuthority.reset_authority()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            try:
                shutil.rmtree(self.test_dir)
            except Exception:
                pass

    def _create_file(self, rel_path: str, content: str) -> str:
        full_path = os.path.join(self.test_dir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return full_path

    def _create_governed_task(self, task_id: str = "TASK-001", file_path: str = "src/app.py", target_files: list = None, lld_hash: str = "", binding_hashes: list = None) -> TaskRecord:
        t = TaskRecord(
            id=task_id,
            title=f"Task {task_id}",
            description=f"Description for {task_id}",
            category=TaskCategory.API_ENDPOINT,
            parent_lld="LLD-001",
            parent_hld="HLD-001",
            parent_reqs=["REQ-001"],
            parent_behaviors=["BEH-001"],
            target_files=target_files if target_files is not None else ([file_path] if file_path else []),
            verification_criteria=["Test verification criteria"],
            source_lld_hash=lld_hash or "lld_hash_123",
            source_binding_hashes=binding_hashes or ["binding_hash_123"]
        )
        return t

    def _create_governed_plan(self, tasks: list) -> ExecutionPlan:
        return ExecutionPlanCompiler.compile_execution_plan(tasks)

    def _write_mock_pipeline(self, anchor_snap, changeset, tasks=None, plan=None):
        if tasks is None:
            tasks = [self._create_governed_task(tid) for tid in changeset.source_task_hashes.keys()]

        # Construct valid BehaviorGraph
        b_graph = BehaviorGraph(version=1)
        beh_node = BehaviorNode(
            id="BEH-001",
            name="ProcessData",
            behavior_type=BehaviorNodeType.COMMAND,
            actor_id="User",
            target_entity_id="Data",
            epistemic_status=EpistemicStatus.OBSERVED
        )
        b_graph.add_node(beh_node)
        beh_hash = beh_node.compute_canonical_hash()

        # Construct valid RequirementGraph
        r_graph = RequirementGraph(version=1)
        req_node = RequirementNode(
            id="REQ-001",
            kind=RequirementKind.FUNCTIONAL,
            statement="System shall process data",
            actor="User",
            capability="ProcessData",
            target="System",
            source_behaviors=["BEH-001"]
        )
        r_graph.add_requirement(req_node)

        req_payload = {
            "behavior_id": beh_node.id,
            "requirement_hashes": [req_node.canonical_hash()]
        }
        req_hash = hashlib.sha256(json.dumps(req_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

        # Construct valid HLDDesign
        hld_mod = HLDModule(
            id="HLD-001",
            name="AuthModule",
            system_boundary="Core",
            owned_entities=["Data"],
            owned_capabilities=["ProcessData"]
        )
        hld_hash = hld_mod.compute_canonical_hash()
        hld = HLDDesign(
            system_name="S",
            architecture_style="Modular Monolith",
            modules=[hld_mod],
            adrs=[],
            version=1
        )

        # Construct valid CapabilityBinding
        binding = CapabilityBinding(
            behavior_id="BEH-001",
            requirement_ids=["REQ-001"],
            operation_class=OperationClass.COMMAND_MUTATION,
            target_entity="Data",
            hld_capability="ProcessData",
            lld_component_id="LLD-001",
            allowed_component_types=[LLDComponentType.SERVICE],
            source_behavior_hash=beh_hash,
            source_requirement_hash=req_hash,
            source_hld_hash=hld_hash,
            source_behavior_graph_version=str(b_graph.version),
            source_requirement_graph_version=str(r_graph.version),
            source_hld_module_id="HLD-001",
            source_hld_version=1
        )
        binding.binding_hash = binding.compute_hash()

        # Construct valid LLDComponent
        lld_comp = LLDComponent(
            id="LLD-001",
            name="AuthComponent",
            component_type=LLDComponentType.SERVICE,
            parent=LLDParentRef(
                hld_id="HLD-001",
                req_ids=["REQ-001"],
                behavior_ids=["BEH-001"]
            ),
            role="backend_service",
            execution_capability=ComponentExecutionCapability.MUTATE,
            capability_bindings=[binding]
        )
        lld_comp.component_hash = lld_comp.compute_canonical_hash()
        lld_hash = lld_comp.component_hash

        for t in tasks:
            t.source_lld_hash = lld_hash
            t.source_binding_hashes = [binding.binding_hash]
            t.task_hash = t.compute_canonical_hash()

        if plan is None:
            plan = self._create_governed_plan(tasks)
        changeset.source_execution_plan_hash = plan.plan_hash
        changeset.source_task_hashes = {t.id: t.task_hash for t in tasks}

        pipe_path = os.path.join(self.agents_dir, "v7_refinement_pipeline.json")
        with open(pipe_path, "w", encoding="utf-8") as f:
            json.dump({
                "version": 1,
                "hld_design": hld.to_dict(),
                "behavior_graph": b_graph.to_dict(),
                "requirement_graph": r_graph.to_dict(),
                "lld_components": [lld_comp.to_dict()],
                "tasks": [t.to_dict() for t in tasks],
                "execution_plan": plan.to_dict(),
                "planning_snapshot": anchor_snap.to_dict(),
                "authorized_changeset": changeset.to_dict(),
                "repository_snapshot": anchor_snap.to_dict(),
                "blocked": False,
                "hld_governance": {"is_blocked": False}
            }, f)

        epoch_lock = ArtifactGovernor.lock_pipeline_epoch(self.test_dir)
        changeset.source_pipeline_state_hash = epoch_lock["pipeline_canonical_hash"]
        changeset.pipeline_epoch_id = epoch_lock["epoch_id"]
        changeset.changeset_hash = changeset.compute_canonical_hash()

        RepositorySnapshotEngine.save_snapshot(anchor_snap, os.path.join(self.agents_dir, "planning_snapshot.json"))
        with open(os.path.join(self.agents_dir, "authorized_changeset.json"), "w", encoding="utf-8") as cf:
            json.dump(changeset.to_dict(), cf)

        return epoch_lock

    # -------------------------------------------------------------------------
    # Test 1: Planning Snapshot Anchor Immutability & Tampering Detection
    # -------------------------------------------------------------------------
    def test_v11_planning_snapshot_anchor_immutability_and_tamper_detection(self):
        """Invariant: Tampering with planning snapshot anchor state hash fails closed."""
        self._create_file("src/app.py", "def app(): pass")
        anchor = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        task = self._create_governed_task("TASK-001")
        plan = self._create_governed_plan([task])

        changeset = AuthorizedChangeSet(
            changeset_id="CS-001",
            source_repository_state_hash=anchor.repository_state_hash,
            source_execution_plan_hash=plan.plan_hash,
            source_pipeline_state_hash="pending_epoch_hash",
            source_task_hashes={task.id: task.task_hash}
        )
        changeset.add_change(AuthorizedFileChange(
            file_path="src/app.py",
            operation=FileMutationOp.MODIFY,
            authorized_by_tasks=["TASK-001"]
        ))

        self._write_mock_pipeline(anchor, changeset, tasks=[task], plan=plan)

        # Perform valid change on disk
        self._create_file("src/app.py", "def app(): return True")
        result = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        # TAMPERING ATTACK: Attacker tampers anchor state hash
        anchor_tampered = RepositorySnapshot.from_dict(anchor.to_dict())
        anchor_tampered.repository_state_hash = "tampered_fake_hash_9999"

        gov_res = ArtifactGovernor.audit_changeset_reconciliation_governance(
            anchor_tampered, result, changeset, self.test_dir
        )
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("ANCHOR_SNAPSHOT_INTEGRITY_FAILED" in r or "STALE_CHANGESET_SOURCE_ANCHOR" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 2: Unauthorized File Modification Attack (UNAUTHORIZED_FILE_MODIFICATION)
    # -------------------------------------------------------------------------
    def test_v11_unauthorized_file_modification_attack_is_rejected(self):
        """Invariant: Modifying an unauthorized file (e.g. security.py) is strictly blocked."""
        self._create_file("src/app.py", "def app(): pass")
        self._create_file("src/security.py", "ALLOW_ALL = False")
        anchor = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        task = self._create_governed_task("TASK-001")
        plan = self._create_governed_plan([task])

        changeset = AuthorizedChangeSet(
            changeset_id="CS-002",
            source_repository_state_hash=anchor.repository_state_hash,
            source_execution_plan_hash=plan.plan_hash,
            source_pipeline_state_hash="pending_epoch_hash",
            source_task_hashes={task.id: task.task_hash}
        )
        changeset.add_change(AuthorizedFileChange(
            file_path="src/app.py",
            operation=FileMutationOp.MODIFY,
            authorized_by_tasks=["TASK-001"]
        ))

        self._write_mock_pipeline(anchor, changeset, tasks=[task], plan=plan)

        # EXECUTION ATTACK: Agent edits src/app.py AND mutates src/security.py
        self._create_file("src/app.py", "def app(): return True")
        self._create_file("src/security.py", "ALLOW_ALL = True  # ATTACK")

        gov_res = ArtifactGovernor.enforce_fsm_transition(
            current_phase="INTEGRATION",
            proposed_event="integration_passed",
            target_phase="QA",
            workspace_dir=self.test_dir
        )
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("UNAUTHORIZED_FILE_MODIFICATION: File 'src/security.py'" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 3: Unauthorized File Creation Attack (UNAUTHORIZED_FILE_CREATION)
    # -------------------------------------------------------------------------
    def test_v11_unauthorized_file_creation_attack_is_rejected(self):
        """Invariant: Creating an untracked/unauthorized file on disk is strictly blocked."""
        self._create_file("src/app.py", "def app(): pass")
        anchor = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        task = self._create_governed_task("TASK-001")
        plan = self._create_governed_plan([task])

        changeset = AuthorizedChangeSet(
            changeset_id="CS-003",
            source_repository_state_hash=anchor.repository_state_hash,
            source_execution_plan_hash=plan.plan_hash,
            source_pipeline_state_hash="pending_epoch_hash",
            source_task_hashes={task.id: task.task_hash}
        )
        changeset.add_change(AuthorizedFileChange(
            file_path="src/button.py",
            operation=FileMutationOp.CREATE,
            authorized_by_tasks=["TASK-001"]
        ))

        self._write_mock_pipeline(anchor, changeset, tasks=[task], plan=plan)

        # EXECUTION ATTACK: Agent creates src/button.py AND untracked backdoor src/backdoor.py
        self._create_file("src/button.py", "def button(): pass")
        self._create_file("src/backdoor.py", "def backdoor(): pass")

        gov_res = ArtifactGovernor.enforce_fsm_transition(
            current_phase="INTEGRATION",
            proposed_event="integration_passed",
            target_phase="QA",
            workspace_dir=self.test_dir
        )
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("UNAUTHORIZED_FILE_CREATION: File 'src/backdoor.py'" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 4: Unauthorized File Deletion Attack (UNAUTHORIZED_FILE_DELETION)
    # -------------------------------------------------------------------------
    def test_v11_unauthorized_file_deletion_attack_is_rejected(self):
        """Invariant: Deleting a file without ChangeSet authorization is strictly blocked."""
        self._create_file("src/app.py", "def app(): pass")
        self._create_file("src/critical_config.py", "CONFIG = 1")
        anchor = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        task = self._create_governed_task("TASK-001")
        plan = self._create_governed_plan([task])

        changeset = AuthorizedChangeSet(
            changeset_id="CS-004",
            source_repository_state_hash=anchor.repository_state_hash,
            source_execution_plan_hash=plan.plan_hash,
            source_pipeline_state_hash="pending_epoch_hash",
            source_task_hashes={task.id: task.task_hash}
        )
        changeset.add_change(AuthorizedFileChange(
            file_path="src/app.py",
            operation=FileMutationOp.MODIFY,
            authorized_by_tasks=["TASK-001"]
        ))

        self._write_mock_pipeline(anchor, changeset, tasks=[task], plan=plan)

        # EXECUTION ATTACK: Agent deletes src/critical_config.py
        os.remove(os.path.join(self.test_dir, "src/critical_config.py"))

        gov_res = ArtifactGovernor.enforce_fsm_transition(
            current_phase="INTEGRATION",
            proposed_event="integration_passed",
            target_phase="QA",
            workspace_dir=self.test_dir
        )
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("UNAUTHORIZED_FILE_DELETION: File 'src/critical_config.py'" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 5: Stale Baseline / Anchor Mismatch Rejection (STALE_CHANGESET_SOURCE_ANCHOR)
    # -------------------------------------------------------------------------
    def test_v11_stale_baseline_anchor_mismatch_fails_closed(self):
        """Invariant: Applying a ChangeSet anchored to Snapshot A against Snapshot B fails closed."""
        self._create_file("src/app.py", "pass")
        anchor_A = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        task = self._create_governed_task("TASK-001")
        plan = self._create_governed_plan([task])

        changeset = AuthorizedChangeSet(
            changeset_id="CS-005",
            source_repository_state_hash=anchor_A.repository_state_hash,
            source_execution_plan_hash=plan.plan_hash,
            source_pipeline_state_hash="pending_epoch_hash",
            source_task_hashes={task.id: task.task_hash}
        )
        changeset.add_change(AuthorizedFileChange(
            file_path="src/app.py",
            operation=FileMutationOp.MODIFY,
            authorized_by_tasks=["TASK-001"]
        ))

        # Planning Anchor is updated to Snapshot B
        self._create_file("src/other.py", "other = 1")
        anchor_B = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        self._write_mock_pipeline(anchor_B, changeset, tasks=[task], plan=plan)

        gov_res = ArtifactGovernor.enforce_fsm_transition(
            current_phase="INTEGRATION",
            proposed_event="integration_passed",
            target_phase="QA",
            workspace_dir=self.test_dir
        )
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("STALE_CHANGESET_SOURCE_ANCHOR" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 6: Legitimate Authorized ChangeSet Reconciliation & Promotion
    # -------------------------------------------------------------------------
    def test_v11_legitimate_authorized_changeset_promotes_to_next_trusted_state(self):
        """Invariant: Legitimate authorized modifications and creations reconcile and promote result snapshot."""
        self._create_file("src/app.py", "def app(): pass")
        anchor = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        t1 = self._create_governed_task("TASK-001", target_files=["src/app.py"])
        t2 = self._create_governed_task("TASK-002", target_files=["src/helper.py"])
        plan = self._create_governed_plan([t1, t2])

        changeset = AuthorizedChangeSet(
            changeset_id="CS-006",
            source_repository_state_hash=anchor.repository_state_hash,
            source_execution_plan_hash=plan.plan_hash,
            source_pipeline_state_hash="pending_epoch_hash",
            source_task_hashes={t1.id: t1.task_hash, t2.id: t2.task_hash}
        )
        changeset.add_change(AuthorizedFileChange(
            file_path="src/app.py",
            operation=FileMutationOp.MODIFY,
            authorized_by_tasks=["TASK-001"]
        ))
        changeset.add_change(AuthorizedFileChange(
            file_path="src/helper.py",
            operation=FileMutationOp.CREATE,
            authorized_by_tasks=["TASK-002"]
        ))

        self._write_mock_pipeline(anchor, changeset, tasks=[t1, t2], plan=plan)

        # Legitimate Execution
        self._create_file("src/app.py", "def app(): return 'authorized'")
        self._create_file("src/helper.py", "def helper(): return 42")

        # Save planning snapshot and changeset in .agents/
        RepositorySnapshotEngine.save_snapshot(anchor, os.path.join(self.agents_dir, "planning_snapshot.json"))
        with open(os.path.join(self.agents_dir, "authorized_changeset.json"), "w", encoding="utf-8") as cf:
            json.dump(changeset.to_dict(), cf)

        gov_res = ArtifactGovernor.enforce_fsm_transition(
            current_phase="INTEGRATION",
            proposed_event="integration_passed",
            target_phase="QA",
            workspace_dir=self.test_dir
        )
        self.assertFalse(gov_res.is_blocked, msg=f"Reconciliation failed: {gov_res.blocking_reasons}")

        # Verify result snapshot was promoted to repo_snapshot.json
        promoted_snap = RepositorySnapshotEngine.load_snapshot(os.path.join(self.agents_dir, "repo_snapshot.json"))
        self.assertIn("src/helper.py", promoted_snap.file_manifest)
        self.assertEqual(promoted_snap.file_manifest["src/app.py"].file_hash, promoted_snap.file_manifest["src/app.py"].file_hash)

    # -------------------------------------------------------------------------
    # Test 7: Post-Verification Mutation & Drift Detection
    # -------------------------------------------------------------------------
    def test_v11_post_verification_mutation_drift_blocks_fsm(self):
        """Invariant: Mutating disk after ChangeSet reconciliation fails closed on drift check."""
        self._create_file("src/app.py", "def app(): pass")
        anchor = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        task = self._create_governed_task("TASK-001")
        plan = self._create_governed_plan([task])

        changeset = AuthorizedChangeSet(
            changeset_id="CS-007",
            source_repository_state_hash=anchor.repository_state_hash,
            source_execution_plan_hash=plan.plan_hash,
            source_pipeline_state_hash="pending_epoch_hash",
            source_task_hashes={task.id: task.task_hash}
        )
        changeset.add_change(AuthorizedFileChange(
            file_path="src/app.py",
            operation=FileMutationOp.MODIFY,
            authorized_by_tasks=["TASK-001"]
        ))

        self._write_mock_pipeline(anchor, changeset, tasks=[task], plan=plan)

        # Legitimate execution
        self._create_file("src/app.py", "def app(): return 'authorized'")

        # Capture result snapshot and reconcile
        result = RepositorySnapshotEngine.capture_snapshot(self.test_dir)
        recon_res = RepositorySnapshotEngine.reconcile_changeset(anchor, result, changeset)
        self.assertTrue(recon_res.is_reconciled)

        # ATTACK: Post-verification silent disk drift before transition
        self._create_file("src/app.py", "def app(): return 'tampered_after_reconciliation'")

        # Re-auditing governance against the old result snapshot detects live drift
        gov_res = ArtifactGovernor.audit_repository_snapshot_governance(result, repo_root=self.test_dir)
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("drift detected" in r or "file_hash drift" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 8: Missing Refinement Pipeline Artifact Fails Closed
    # -------------------------------------------------------------------------
    def test_v11_missing_pipeline_file_fails_closed(self):
        """Invariant: If v7_refinement_pipeline.json is missing, ChangeSet reconciliation fails closed."""
        self._create_file("src/app.py", "def app(): pass")
        anchor = RepositorySnapshotEngine.capture_snapshot(self.test_dir)
        self._create_file("src/app.py", "def app(): return True")
        result = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        task = self._create_governed_task("TASK-001")
        plan = self._create_governed_plan([task])

        changeset = AuthorizedChangeSet(
            changeset_id="CS-008",
            source_repository_state_hash=anchor.repository_state_hash,
            source_execution_plan_hash=plan.plan_hash,
            source_pipeline_state_hash="pending_epoch_hash",
            source_task_hashes={task.id: task.task_hash}
        )
        changeset.add_change(AuthorizedFileChange(
            file_path="src/app.py",
            operation=FileMutationOp.MODIFY,
            authorized_by_tasks=["TASK-001"]
        ))

        # Ensure pipeline artifact is ABSENT from .agents/
        pipe_path = os.path.join(self.agents_dir, "v7_refinement_pipeline.json")
        if os.path.exists(pipe_path):
            os.remove(pipe_path)

        gov_res = ArtifactGovernor.audit_changeset_reconciliation_governance(
            anchor, result, changeset, workspace_dir=self.test_dir
        )
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("CHANGESET_LINEAGE_SOURCE_MISSING" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 9: Missing Workspace Context Fails Closed
    # -------------------------------------------------------------------------
    def test_v11_missing_workspace_dir_fails_closed(self):
        """Invariant: Attempting ChangeSet reconciliation without workspace context fails closed."""
        self._create_file("src/app.py", "def app(): pass")
        anchor = RepositorySnapshotEngine.capture_snapshot(self.test_dir)
        self._create_file("src/app.py", "def app(): return True")
        result = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        task = self._create_governed_task("TASK-001")
        plan = self._create_governed_plan([task])

        changeset = AuthorizedChangeSet(
            changeset_id="CS-009",
            source_repository_state_hash=anchor.repository_state_hash,
            source_execution_plan_hash=plan.plan_hash,
            source_pipeline_state_hash="pending_epoch_hash",
            source_task_hashes={task.id: task.task_hash}
        )
        changeset.add_change(AuthorizedFileChange(
            file_path="src/app.py",
            operation=FileMutationOp.MODIFY,
            authorized_by_tasks=["TASK-001"]
        ))

        gov_res = ArtifactGovernor.audit_changeset_reconciliation_governance(
            anchor, result, changeset, workspace_dir=None
        )
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("CHANGESET_WORKSPACE_CONTEXT_MISSING" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 10: Empty Governed Tasks in Pipeline with Non-Empty ChangeSet Fails Closed
    # -------------------------------------------------------------------------
    def test_v11_empty_governed_tasks_in_pipeline_fails_closed(self):
        """Invariant: Storing tasks=[] in pipeline while ChangeSet has tasks fails closed."""
        self._create_file("src/app.py", "def app(): pass")
        anchor = RepositorySnapshotEngine.capture_snapshot(self.test_dir)
        self._create_file("src/app.py", "def app(): return True")
        result = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        task = self._create_governed_task("TASK-001")
        plan = self._create_governed_plan([task])

        changeset = AuthorizedChangeSet(
            changeset_id="CS-010",
            source_repository_state_hash=anchor.repository_state_hash,
            source_execution_plan_hash=plan.plan_hash,
            source_pipeline_state_hash="pending_epoch_hash",
            source_task_hashes={task.id: task.task_hash}
        )
        changeset.add_change(AuthorizedFileChange(
            file_path="src/app.py",
            operation=FileMutationOp.MODIFY,
            authorized_by_tasks=["TASK-001"]
        ))

        # Pipeline contains empty tasks list
        pipe_path = os.path.join(self.agents_dir, "v7_refinement_pipeline.json")
        with open(pipe_path, "w", encoding="utf-8") as f:
            json.dump({
                "version": 1,
                "execution_plan": plan.to_dict(),
                "tasks": []  # Empty!
            }, f)
        epoch_lock = ArtifactGovernor.lock_pipeline_epoch(self.test_dir)
        changeset.source_pipeline_state_hash = epoch_lock["pipeline_canonical_hash"]
        changeset.changeset_hash = changeset.compute_canonical_hash()

        gov_res = ArtifactGovernor.audit_changeset_reconciliation_governance(
            anchor, result, changeset, workspace_dir=self.test_dir
        )
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("CHANGESET_TASK_SET_MISMATCH" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 11: Tampered ExecutionPlan in Pipeline Fails Closed
    # -------------------------------------------------------------------------
    def test_v11_tampered_execution_plan_in_pipeline_fails_closed(self):
        """Invariant: Tampering ExecutionPlan payload in pipeline fails strict governed deserialization."""
        self._create_file("src/app.py", "def app(): pass")
        anchor = RepositorySnapshotEngine.capture_snapshot(self.test_dir)
        self._create_file("src/app.py", "def app(): return True")
        result = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        task = self._create_governed_task("TASK-001")
        plan = self._create_governed_plan([task])

        changeset = AuthorizedChangeSet(
            changeset_id="CS-011",
            source_repository_state_hash=anchor.repository_state_hash,
            source_execution_plan_hash=plan.plan_hash,
            source_pipeline_state_hash="pending_epoch_hash",
            source_task_hashes={task.id: task.task_hash}
        )
        changeset.add_change(AuthorizedFileChange(
            file_path="src/app.py",
            operation=FileMutationOp.MODIFY,
            authorized_by_tasks=["TASK-001"]
        ))

        # Mutate plan structure without valid hash
        tampered_plan_dict = plan.to_dict()
        tampered_plan_dict["version"] = 999  # Invalidates hash

        pipe_path = os.path.join(self.agents_dir, "v7_refinement_pipeline.json")
        with open(pipe_path, "w", encoding="utf-8") as f:
            json.dump({
                "version": 1,
                "execution_plan": tampered_plan_dict,
                "tasks": [task.to_dict()]
            }, f)
        epoch_lock = ArtifactGovernor.lock_pipeline_epoch(self.test_dir)
        changeset.source_pipeline_state_hash = epoch_lock["pipeline_canonical_hash"]
        changeset.changeset_hash = changeset.compute_canonical_hash()

        gov_res = ArtifactGovernor.audit_changeset_reconciliation_governance(
            anchor, result, changeset, workspace_dir=self.test_dir
        )
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("UPSTREAM_PLAN_INTEGRITY_FAILED" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 12: Tampered TaskRecord in Pipeline Fails Closed
    # -------------------------------------------------------------------------
    def test_v11_tampered_task_record_in_pipeline_fails_closed(self):
        """Invariant: Tampering TaskRecord payload in pipeline fails strict governed deserialization."""
        self._create_file("src/app.py", "def app(): pass")
        anchor = RepositorySnapshotEngine.capture_snapshot(self.test_dir)
        self._create_file("src/app.py", "def app(): return True")
        result = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        task = self._create_governed_task("TASK-001")
        plan = self._create_governed_plan([task])

        changeset = AuthorizedChangeSet(
            changeset_id="CS-012",
            source_repository_state_hash=anchor.repository_state_hash,
            source_execution_plan_hash=plan.plan_hash,
            source_pipeline_state_hash="pending_epoch_hash",
            source_task_hashes={task.id: task.task_hash}
        )
        changeset.add_change(AuthorizedFileChange(
            file_path="src/app.py",
            operation=FileMutationOp.MODIFY,
            authorized_by_tasks=["TASK-001"]
        ))

        # Mutate task description without valid hash
        tampered_task_dict = task.to_dict()
        tampered_task_dict["description"] = "Tampered description injected"

        pipe_path = os.path.join(self.agents_dir, "v7_refinement_pipeline.json")
        with open(pipe_path, "w", encoding="utf-8") as f:
            json.dump({
                "version": 1,
                "execution_plan": plan.to_dict(),
                "tasks": [tampered_task_dict]
            }, f)
        epoch_lock = ArtifactGovernor.lock_pipeline_epoch(self.test_dir)
        changeset.source_pipeline_state_hash = epoch_lock["pipeline_canonical_hash"]
        changeset.changeset_hash = changeset.compute_canonical_hash()

        gov_res = ArtifactGovernor.audit_changeset_reconciliation_governance(
            anchor, result, changeset, workspace_dir=self.test_dir
        )
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("GOVERNED_TASK_INTEGRITY_FAILED" in r or "CHANGESET_TASK_SET_MISMATCH" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 13: Signer Capability Comprehensive Adversarial Boundary Matrix
    # -------------------------------------------------------------------------
    def test_v11_signer_capability_adversarial_matrix(self):
        """Invariant: All adversarial capability issuance, forgery, revocation, and pairing attacks are rejected."""
        # 1. Rogue subsystem requesting capability
        with self.assertRaises(PermissionError) as ctx1:
            SovereignCryptoAuthority.issue_signing_capability("UNTRUSTED_AGENT_OR_TOOL")
        self.assertIn("UNAUTHORIZED_SUBSYSTEM", str(ctx1.exception))

        # 2. Forged capability object (wrong secret / fake class)
        class RogueFakeCapability:
            def validate(self, secret, subsystem):
                return True

        with self.assertRaises(PermissionError) as ctx2:
            SovereignCryptoAuthority.sign(
                capability=RogueFakeCapability(),
                artifact_type="IMPLEMENTATION_EVIDENCE",
                issuer_id="SCLASS_PROMOTION_ENGINE",
                evidence_id="EV-FAKE",
                evidence_hash="abcdef" * 10
            )
        self.assertIn("UNAUTHORIZED_SIGNING_ATTEMPT", str(ctx2.exception))

        # 3. Forged SovereignSigningCapability with bad secret
        forged_cap = SovereignSigningCapability(b"bad_forged_secret_00000000000000", "SCLASS_PROMOTION_ENGINE")
        with self.assertRaises(PermissionError) as ctx3:
            SovereignCryptoAuthority.sign(
                capability=forged_cap,
                artifact_type="IMPLEMENTATION_EVIDENCE",
                issuer_id="SCLASS_PROMOTION_ENGINE",
                evidence_id="EV-FORGED",
                evidence_hash="abcdef" * 10
            )
        self.assertIn("UNAUTHORIZED_SIGNING_ATTEMPT", str(ctx3.exception))

        # 4. Revoked capability
        valid_cap = SovereignCryptoAuthority.issue_signing_capability("SCLASS_PROMOTION_ENGINE")
        valid_cap.revoke()
        with self.assertRaises(PermissionError) as ctx4:
            SovereignCryptoAuthority.sign(
                capability=valid_cap,
                artifact_type="IMPLEMENTATION_EVIDENCE",
                issuer_id="SCLASS_PROMOTION_ENGINE",
                evidence_id="EV-REVOKED",
                evidence_hash="abcdef" * 10
            )
        self.assertIn("UNAUTHORIZED_SIGNING_ATTEMPT", str(ctx4.exception))

        # 5. Wrong issuer / capability pairing (TestRunner capability used for PromotionEngine)
        test_runner_cap = SovereignCryptoAuthority.issue_signing_capability("SCLASS_TEST_RUNNER")
        with self.assertRaises(PermissionError) as ctx5:
            SovereignCryptoAuthority.sign(
                capability=test_runner_cap,
                artifact_type="IMPLEMENTATION_EVIDENCE",
                issuer_id="SCLASS_PROMOTION_ENGINE",
                evidence_id="EV-PAIRING-ATTACK",
                evidence_hash="abcdef" * 10
            )
        self.assertIn("UNAUTHORIZED_SIGNING_ATTEMPT", str(ctx5.exception))

    # -------------------------------------------------------------------------
    # Test 14: TOCTOU Pipeline Epoch Lock Tampering Fails Closed
    # -------------------------------------------------------------------------
    def test_v11_pipeline_toctou_tamper_after_validation_fails_closed(self):
        """Invariant: Modifying refinement pipeline after locking execution epoch fails closed on TOCTOU check."""
        self._create_file("src/app.py", "def app(): pass")
        anchor = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        task = self._create_governed_task("TASK-001", target_files=["src/app.py"])
        plan = self._create_governed_plan([task])

        changeset = AuthorizedChangeSet(
            changeset_id="CS-TOCTOU",
            source_repository_state_hash=anchor.repository_state_hash,
            source_execution_plan_hash=plan.plan_hash,
            source_pipeline_state_hash="pending_epoch_hash",
            source_task_hashes={task.id: task.task_hash}
        )
        changeset.add_change(AuthorizedFileChange(
            file_path="src/app.py",
            operation=FileMutationOp.MODIFY,
            authorized_by_tasks=["TASK-001"]
        ))

        self._write_mock_pipeline(anchor, changeset, tasks=[task], plan=plan)

        # 1. Pipeline epoch is locked
        epoch_lock = ArtifactGovernor.lock_pipeline_epoch(self.test_dir)
        self.assertTrue(epoch_lock.get("is_locked"))

        # 2. TOCTOU Attack: Attacker mutates pipeline on disk after epoch lock
        pipe_path = os.path.join(self.agents_dir, "v7_refinement_pipeline.json")
        with open(pipe_path, "r", encoding="utf-8") as pf:
            pdata = json.load(pf)
        pdata["tampered_field"] = "malicious_injection"
        with open(pipe_path, "w", encoding="utf-8") as pf:
            json.dump(pdata, pf)

        # 3. Legitimate execution mutation on disk
        self._create_file("src/app.py", "def app(): return 'executed'")
        result = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        gov_res = ArtifactGovernor.audit_changeset_reconciliation_governance(
            anchor_snapshot=anchor,
            result_snapshot=result,
            changeset=changeset,
            workspace_dir=self.test_dir
        )
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("PIPELINE_EPOCH_TAMPER_DETECTED" in r or "CHANGESET_PIPELINE_STATE_MISMATCH" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 15: Duplicate Authoritative Task IDs in Pipeline Fails Closed
    # -------------------------------------------------------------------------
    def test_v11_duplicate_task_id_in_pipeline_fails_closed(self):
        """Invariant: Persisted pipeline with duplicate task IDs fails closed without collapsing."""
        self._create_file("src/app.py", "def app(): pass")
        anchor = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        t1 = self._create_governed_task("TASK-001", target_files=["src/app.py"])
        t1_dup = self._create_governed_task("TASK-001", target_files=["src/app.py"])
        t2 = self._create_governed_task("TASK-002", target_files=["src/app.py"])
        plan = self._create_governed_plan([t1, t2])

        changeset = AuthorizedChangeSet(
            changeset_id="CS-DUP",
            source_repository_state_hash=anchor.repository_state_hash,
            source_execution_plan_hash=plan.plan_hash,
            source_pipeline_state_hash="pending_epoch_hash",
            source_task_hashes={t1.id: t1.task_hash, t2.id: t2.task_hash}
        )
        changeset.add_change(AuthorizedFileChange(
            file_path="src/app.py",
            operation=FileMutationOp.MODIFY,
            authorized_by_tasks=["TASK-001"]
        ))

        # Write pipeline containing duplicated TASK-001
        self._write_mock_pipeline(anchor, changeset, tasks=[t1, t2], plan=plan)
        pipe_path = os.path.join(self.agents_dir, "v7_refinement_pipeline.json")
        with open(pipe_path, "r", encoding="utf-8") as pf:
            pdata = json.load(pf)
        pdata["tasks"] = [t1.to_dict(), t1_dup.to_dict(), t2.to_dict()]  # Duplicate TASK-001!
        with open(pipe_path, "w", encoding="utf-8") as pf:
            json.dump(pdata, pf)
        epoch_lock = ArtifactGovernor.lock_pipeline_epoch(self.test_dir)
        changeset.source_pipeline_state_hash = epoch_lock["pipeline_canonical_hash"]
        changeset.changeset_hash = changeset.compute_canonical_hash()

        self._create_file("src/app.py", "def app(): return 'executed'")
        result = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        gov_res = ArtifactGovernor.audit_changeset_reconciliation_governance(
            anchor_snapshot=anchor,
            result_snapshot=result,
            changeset=changeset,
            workspace_dir=self.test_dir
        )
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("DUPLICATE_TASK_ID_DETECTED" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 16: Mutation Outside Authorized Task Target Scope Fails Closed
    # -------------------------------------------------------------------------
    def test_v11_mutation_outside_authorized_task_scope_fails_closed(self):
        """Invariant: ChangeSet mutating files outside authorizing task's target_files scope fails closed."""
        self._create_file("src/app.py", "def app(): pass")
        self._create_file("src/secrets.py", "API_KEY = 'secret'")
        anchor = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        # TASK-001 only authorizes src/app.py
        task = self._create_governed_task("TASK-001", target_files=["src/app.py"])
        plan = self._create_governed_plan([task])

        # Attacker crafts ChangeSet claiming TASK-001 authorizes modifying src/secrets.py
        changeset = AuthorizedChangeSet(
            changeset_id="CS-SCOPE-ATTACK",
            source_repository_state_hash=anchor.repository_state_hash,
            source_execution_plan_hash=plan.plan_hash,
            source_pipeline_state_hash="pending_epoch_hash",
            source_task_hashes={task.id: task.task_hash}
        )
        changeset.add_change(AuthorizedFileChange(
            file_path="src/secrets.py",
            operation=FileMutationOp.MODIFY,
            authorized_by_tasks=["TASK-001"]
        ))

        self._write_mock_pipeline(anchor, changeset, tasks=[task], plan=plan)

        self._create_file("src/secrets.py", "API_KEY = 'exfiltrated'")
        result = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        gov_res = ArtifactGovernor.audit_changeset_reconciliation_governance(
            anchor_snapshot=anchor,
            result_snapshot=result,
            changeset=changeset,
            workspace_dir=self.test_dir
        )
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("MUTATION_OUTSIDE_AUTHORIZED_TASK_SCOPE" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 17: Task Semantic Spec Hash Invariance Under Scheduler Mutation
    # -------------------------------------------------------------------------
    def test_v11_task_semantic_spec_hash_invariance_under_scheduler_mutation(self):
        """Invariant: Scheduler operational transformations (execution_mode, batching) preserve task_spec_hash."""
        task = self._create_governed_task("TASK-001", target_files=["src/app.py"])
        original_spec_hash = task.compute_spec_hash()

        # Compile execution plan with parallel execution
        t2 = self._create_governed_task("TASK-002", target_files=["src/helper.py"])
        plan = ExecutionPlanCompiler.compile_execution_plan([task, t2])

        # Verify plan contains execution tasks with preserved task_spec_hash
        exec_task = plan.tasks[f"E{task.id}"]
        self.assertEqual(exec_task.compute_spec_hash(), original_spec_hash)
        self.assertEqual(exec_task.task_spec_hash, original_spec_hash)
        self.assertNotEqual(exec_task.task_hash, "")

    # -------------------------------------------------------------------------
    # Test 18: Full Runtime Signer Capability Boundary Proof
    # -------------------------------------------------------------------------
    def test_v11_full_runtime_signer_capability_boundary_proof(self):
        """Invariant: Real runtime boundary strictly prevents unsigned, forged, or unauthenticated evidence."""
        # 1. Unauthenticated agent tool execution cannot sign evidence
        with self.assertRaises(PermissionError):
            SovereignCryptoAuthority.issue_signing_capability("AGENT_CODING_TOOL")

        # 2. Legitimate PromotionEngine and TestRunner capabilities sign and verify successfully
        promo_cap = SovereignCryptoAuthority.issue_signing_capability("SCLASS_PROMOTION_ENGINE")
        test_cap = SovereignCryptoAuthority.issue_signing_capability("SCLASS_TEST_RUNNER")

        promo_sig = SovereignCryptoAuthority.sign(
            capability=promo_cap,
            artifact_type="IMPLEMENTATION_EVIDENCE",
            issuer_id="SCLASS_PROMOTION_ENGINE",
            evidence_id="EV-REAL-01",
            evidence_hash="11223344556677889900aabbccddeeff" * 2
        )
        self.assertTrue(SovereignCryptoAuthority.verify(
            artifact_type="IMPLEMENTATION_EVIDENCE",
            issuer_id="SCLASS_PROMOTION_ENGINE",
            evidence_id="EV-REAL-01",
            evidence_hash="11223344556677889900aabbccddeeff" * 2,
            signature=promo_sig
        ))

        test_sig = SovereignCryptoAuthority.sign(
            capability=test_cap,
            artifact_type="TEST_EVIDENCE",
            issuer_id="SCLASS_TEST_RUNNER",
            evidence_id="EV-TEST-01",
            evidence_hash="aabbccddeeff11223344556677889900" * 2
        )
        self.assertTrue(SovereignCryptoAuthority.verify(
            artifact_type="TEST_EVIDENCE",
            issuer_id="SCLASS_TEST_RUNNER",
            evidence_id="EV-TEST-01",
            evidence_hash="aabbccddeeff11223344556677889900" * 2,
            signature=test_sig
        ))

    # -------------------------------------------------------------------------
    # Test 19: Missing Execution Epoch Lock Fails Closed (🔴 Blocker 1)
    # -------------------------------------------------------------------------
    def test_v11_missing_epoch_lock_fails_closed(self):
        """Invariant: Execution epoch lock is mandatory; missing lock file strictly blocks execution."""
        self._create_file("src/app.py", "def app(): pass")
        anchor = RepositorySnapshotEngine.capture_snapshot(self.test_dir)
        self._create_file("src/app.py", "def app(): return True")
        result = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        task = self._create_governed_task("TASK-001", target_files=["src/app.py"])
        plan = self._create_governed_plan([task])

        changeset = AuthorizedChangeSet(
            changeset_id="CS-NOLOCK",
            source_repository_state_hash=anchor.repository_state_hash,
            source_execution_plan_hash=plan.plan_hash,
            source_pipeline_state_hash="dummy_pipeline_hash",
            source_task_hashes={task.id: task.task_hash}
        )
        changeset.add_change(AuthorizedFileChange(
            file_path="src/app.py",
            operation=FileMutationOp.MODIFY,
            authorized_by_tasks=["TASK-001"]
        ))

        self._write_mock_pipeline(anchor, changeset, tasks=[task], plan=plan)

        # ATTACK: Delete the epoch lock file
        lock_path = os.path.join(self.agents_dir, "pipeline_epoch_lock.json")
        if os.path.exists(lock_path):
            os.remove(lock_path)

        gov_res = ArtifactGovernor.audit_changeset_reconciliation_governance(
            anchor, result, changeset, workspace_dir=self.test_dir
        )
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("PIPELINE_EPOCH_LOCK_MISSING" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 20: Forged or Modified Epoch Lock Signature Fails Closed (🔴 Blocker 3)
    # -------------------------------------------------------------------------
    def test_v11_forged_epoch_lock_signature_fails_closed(self):
        """Invariant: Tampering with or forging epoch lock signature is strictly rejected by cryptographic verification."""
        self._create_file("src/app.py", "def app(): pass")
        anchor = RepositorySnapshotEngine.capture_snapshot(self.test_dir)
        self._create_file("src/app.py", "def app(): return True")
        result = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        task = self._create_governed_task("TASK-001", target_files=["src/app.py"])
        plan = self._create_governed_plan([task])

        changeset = AuthorizedChangeSet(
            changeset_id="CS-FORGED-LOCK",
            source_repository_state_hash=anchor.repository_state_hash,
            source_execution_plan_hash=plan.plan_hash,
            source_pipeline_state_hash="pending_hash",
            source_task_hashes={task.id: task.task_hash}
        )
        changeset.add_change(AuthorizedFileChange(
            file_path="src/app.py",
            operation=FileMutationOp.MODIFY,
            authorized_by_tasks=["TASK-001"]
        ))

        self._write_mock_pipeline(anchor, changeset, tasks=[task], plan=plan)

        # ATTACK: Tamper epoch lock signature
        lock_path = os.path.join(self.agents_dir, "pipeline_epoch_lock.json")
        with open(lock_path, "r", encoding="utf-8") as f:
            lock_data = json.load(f)
        lock_data["epoch_signature"] = "forged_epoch_hmac_signature_0000000000000000"
        with open(lock_path, "w", encoding="utf-8") as f:
            json.dump(lock_data, f)

        gov_res = ArtifactGovernor.audit_changeset_reconciliation_governance(
            anchor, result, changeset, workspace_dir=self.test_dir
        )
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("PIPELINE_EPOCH_LOCK_SIGNATURE_INVALID" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 21: Stale Epoch Lock Plan Mismatch Fails Closed
    # -------------------------------------------------------------------------
    def test_v11_stale_epoch_lock_plan_mismatch_fails_closed(self):
        """Invariant: ChangeSet execution plan differing from locked execution epoch plan is blocked."""
        self._create_file("src/app.py", "def app(): pass")
        anchor = RepositorySnapshotEngine.capture_snapshot(self.test_dir)
        self._create_file("src/app.py", "def app(): return True")
        result = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        task = self._create_governed_task("TASK-001", target_files=["src/app.py"])
        plan = self._create_governed_plan([task])

        changeset = AuthorizedChangeSet(
            changeset_id="CS-STALE-PLAN",
            source_repository_state_hash=anchor.repository_state_hash,
            source_execution_plan_hash=plan.plan_hash,
            source_pipeline_state_hash="pending_hash",
            source_task_hashes={task.id: task.task_hash}
        )
        changeset.add_change(AuthorizedFileChange(
            file_path="src/app.py",
            operation=FileMutationOp.MODIFY,
            authorized_by_tasks=["TASK-001"]
        ))

        self._write_mock_pipeline(anchor, changeset, tasks=[task], plan=plan)

        # ATTACK: ChangeSet execution plan hash changed
        changeset.source_execution_plan_hash = "other_stale_plan_hash_000000"
        changeset.changeset_hash = changeset.compute_canonical_hash()

        gov_res = ArtifactGovernor.audit_changeset_reconciliation_governance(
            anchor, result, changeset, workspace_dir=self.test_dir
        )
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("PIPELINE_EPOCH_PLAN_MISMATCH" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 22: Unscoped Task Code Mutation Attempt Fails Closed (🔴 Blocker 4)
    # -------------------------------------------------------------------------
    def test_v11_unscoped_task_mutation_attempt_fails_closed(self):
        """Invariant: A task with empty target_files (UNRESOLVED scope) cannot authorize code mutations."""
        self._create_file("src/app.py", "def app(): pass")
        anchor = RepositorySnapshotEngine.capture_snapshot(self.test_dir)
        self._create_file("src/app.py", "def app(): return True")
        result = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        # Task with EMPTY target_files
        unscoped_task = self._create_governed_task("TASK-UNSCOPED", target_files=[])
        plan = self._create_governed_plan([unscoped_task])

        changeset = AuthorizedChangeSet(
            changeset_id="CS-UNSCOPED-MUTATION",
            source_repository_state_hash=anchor.repository_state_hash,
            source_execution_plan_hash=plan.plan_hash,
            source_pipeline_state_hash="pending_hash",
            source_task_hashes={unscoped_task.id: unscoped_task.task_hash}
        )
        changeset.add_change(AuthorizedFileChange(
            file_path="src/app.py",
            operation=FileMutationOp.MODIFY,
            authorized_by_tasks=[unscoped_task.id]
        ))

        self._write_mock_pipeline(anchor, changeset, tasks=[unscoped_task], plan=plan)

        gov_res = ArtifactGovernor.audit_changeset_reconciliation_governance(
            anchor, result, changeset, workspace_dir=self.test_dir
        )
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("TASK_TARGET_SCOPE_UNRESOLVED" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 23: ChangeSet Pipeline State Hash Mismatch Fails Closed (🔴 Blocker 2)
    # -------------------------------------------------------------------------
    def test_v11_changeset_pipeline_state_hash_mismatch_fails_closed(self):
        """Invariant: ChangeSet carrying mismatched source_pipeline_state_hash is blocked."""
        self._create_file("src/app.py", "def app(): pass")
        anchor = RepositorySnapshotEngine.capture_snapshot(self.test_dir)
        self._create_file("src/app.py", "def app(): return True")
        result = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        task = self._create_governed_task("TASK-001", target_files=["src/app.py"])
        plan = self._create_governed_plan([task])

        changeset = AuthorizedChangeSet(
            changeset_id="CS-PIPE-MISMATCH",
            source_repository_state_hash=anchor.repository_state_hash,
            source_execution_plan_hash=plan.plan_hash,
            source_pipeline_state_hash="pending_hash",
            source_task_hashes={task.id: task.task_hash}
        )
        changeset.add_change(AuthorizedFileChange(
            file_path="src/app.py",
            operation=FileMutationOp.MODIFY,
            authorized_by_tasks=["TASK-001"]
        ))

        self._write_mock_pipeline(anchor, changeset, tasks=[task], plan=plan)

        # ATTACK: Tamper source_pipeline_state_hash in ChangeSet
        changeset.source_pipeline_state_hash = "forged_pipeline_canonical_hash_FAKE"
        changeset.changeset_hash = changeset.compute_canonical_hash()

        gov_res = ArtifactGovernor.audit_changeset_reconciliation_governance(
            anchor, result, changeset, workspace_dir=self.test_dir
        )
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("CHANGESET_PIPELINE_EPOCH_MISMATCH" in r or "CHANGESET_PIPELINE_STATE_MISMATCH" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 24: Task Identity Confusion Attack Fails Closed (🟠 Blocker 5)
    # -------------------------------------------------------------------------
    def test_v11_task_identity_confusion_fails_closed(self):
        """Invariant: ChangeSet claiming an invalid or altered task_spec_hash is blocked."""
        self._create_file("src/app.py", "def app(): pass")
        anchor = RepositorySnapshotEngine.capture_snapshot(self.test_dir)
        self._create_file("src/app.py", "def app(): return True")
        result = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        task = self._create_governed_task("TASK-001", target_files=["src/app.py"])
        plan = self._create_governed_plan([task])

        changeset = AuthorizedChangeSet(
            changeset_id="CS-IDENTITY-CONFUSION",
            source_repository_state_hash=anchor.repository_state_hash,
            source_execution_plan_hash=plan.plan_hash,
            source_pipeline_state_hash="pending_hash",
            source_task_hashes={task.id: task.task_hash}
        )
        changeset.add_change(AuthorizedFileChange(
            file_path="src/app.py",
            operation=FileMutationOp.MODIFY,
            authorized_by_tasks=["TASK-001"]
        ))

        self._write_mock_pipeline(anchor, changeset, tasks=[task], plan=plan)

        # ATTACK: ChangeSet provides confused/fake task hash
        changeset.source_task_hashes = {task.id: "confused_fake_task_hash_999999"}
        changeset.changeset_hash = changeset.compute_canonical_hash()

        gov_res = ArtifactGovernor.audit_changeset_reconciliation_governance(
            anchor, result, changeset, workspace_dir=self.test_dir
        )
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("CHANGESET_TASK_HASH_LINEAGE_MISMATCH" in r for r in gov_res.blocking_reasons))


if __name__ == "__main__":
    unittest.main()
