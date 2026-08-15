"""
S-Class EOS V11.1 — Adversarial ChangeSet & Reconciliation Governance Test Suite (test_v11_changeset_governance.py)

Comprehensive red-team and invariant validation testing:
1. Planning Snapshot Anchor Immutability & Tampering Detection
2. Unauthorized File Modification Rejection (UNAUTHORIZED_FILE_MODIFICATION)
3. Unauthorized File Creation Rejection (UNAUTHORIZED_FILE_CREATION)
4. Unauthorized File Deletion Rejection (UNAUTHORIZED_FILE_DELETION)
5. Stale Baseline / Anchor Mismatch Rejection (STALE_CHANGESET_SOURCE_ANCHOR)
6. Legitimate Authorized ChangeSet Reconciliation & Promotion to Trusted Baseline
7. Post-Verification Mutation & Drift Detection (Live Drift Blocks Transition)
"""

import os
import shutil
import tempfile
import unittest
import json

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
from behavior_graph import BehaviorGraph
from requirement_ir import RequirementGraph


class TestV11ChangeSetGovernance(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sclass_v11_changeset_test_")
        self.agents_dir = os.path.join(self.test_dir, ".agents")
        os.makedirs(self.agents_dir, exist_ok=True)
        os.environ["SCLASS_EXECUTION_MODE"] = "TEST"

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

    def _write_mock_pipeline(self, anchor_snap, changeset):
        pipe_path = os.path.join(self.agents_dir, "v7_refinement_pipeline.json")
        with open(pipe_path, "w", encoding="utf-8") as f:
            json.dump({
                "version": 1,
                "hld_design": {"system_name": "S", "architecture_style": "Modular Monolith", "modules": [], "adrs": [], "version": 1},
                "behavior_graph": BehaviorGraph(version=1).to_dict(),
                "requirement_graph": RequirementGraph(version=1).to_dict(),
                "lld_components": [],
                "tasks": [],
                "planning_snapshot": anchor_snap.to_dict(),
                "authorized_changeset": changeset.to_dict(),
                "repository_snapshot": anchor_snap.to_dict(),
                "blocked": False,
                "hld_governance": {"is_blocked": False}
            }, f)

    # -------------------------------------------------------------------------
    # Test 1: Planning Snapshot Anchor Immutability & Tampering Detection
    # -------------------------------------------------------------------------
    def test_v11_planning_snapshot_anchor_immutability_and_tamper_detection(self):
        """Invariant: Tampering with planning snapshot anchor state hash fails closed."""
        self._create_file("src/app.py", "def app(): pass")
        anchor = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        changeset = AuthorizedChangeSet(
            changeset_id="CS-001",
            source_repository_state_hash=anchor.repository_state_hash
        )
        changeset.add_change(AuthorizedFileChange(
            file_path="src/app.py",
            operation=FileMutationOp.MODIFY,
            authorized_by_tasks=["TASK-001"]
        ))

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

        # ChangeSet ONLY authorizes editing src/app.py
        changeset = AuthorizedChangeSet(
            changeset_id="CS-002",
            source_repository_state_hash=anchor.repository_state_hash
        )
        changeset.add_change(AuthorizedFileChange(
            file_path="src/app.py",
            operation=FileMutationOp.MODIFY,
            authorized_by_tasks=["TASK-001"]
        ))

        self._write_mock_pipeline(anchor, changeset)

        # EXECUTION ATTACK: Agent edits src/app.py AND mutates src/security.py
        self._create_file("src/app.py", "def app(): return True")
        self._create_file("src/security.py", "ALLOW_ALL = True  # ATTACK")

        # Governor FSM transition to QA must catch unauthorized modification and BLOCK
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

        # ChangeSet ONLY authorizes creating src/button.py
        changeset = AuthorizedChangeSet(
            changeset_id="CS-003",
            source_repository_state_hash=anchor.repository_state_hash
        )
        changeset.add_change(AuthorizedFileChange(
            file_path="src/button.py",
            operation=FileMutationOp.CREATE,
            authorized_by_tasks=["TASK-001"]
        ))

        self._write_mock_pipeline(anchor, changeset)

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

        changeset = AuthorizedChangeSet(
            changeset_id="CS-004",
            source_repository_state_hash=anchor.repository_state_hash
        )
        changeset.add_change(AuthorizedFileChange(
            file_path="src/app.py",
            operation=FileMutationOp.MODIFY,
            authorized_by_tasks=["TASK-001"]
        ))

        self._write_mock_pipeline(anchor, changeset)

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

        # ChangeSet compiled against Snapshot A
        changeset = AuthorizedChangeSet(
            changeset_id="CS-005",
            source_repository_state_hash=anchor_A.repository_state_hash
        )
        changeset.add_change(AuthorizedFileChange(
            file_path="src/app.py",
            operation=FileMutationOp.MODIFY,
            authorized_by_tasks=["TASK-001"]
        ))

        # Planning Anchor is updated to Snapshot B
        self._create_file("src/other.py", "other = 1")
        anchor_B = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        self._write_mock_pipeline(anchor_B, changeset)

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

        # Authorize modifying app.py and creating helper.py
        changeset = AuthorizedChangeSet(
            changeset_id="CS-006",
            source_repository_state_hash=anchor.repository_state_hash
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

        self._write_mock_pipeline(anchor, changeset)

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

        changeset = AuthorizedChangeSet(
            changeset_id="CS-007",
            source_repository_state_hash=anchor.repository_state_hash
        )
        changeset.add_change(AuthorizedFileChange(
            file_path="src/app.py",
            operation=FileMutationOp.MODIFY,
            authorized_by_tasks=["TASK-001"]
        ))

        self._write_mock_pipeline(anchor, changeset)

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


if __name__ == "__main__":
    unittest.main()
