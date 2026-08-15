"""
S-Class EOS V11.1 Test Suite — Repository Snapshot & Classification Engine (Hardened)
Validates:
1. Deterministic repository_state_hash independent of capture timestamp and snapshot ID.
2. Content Merkle tree hashing.
3. Strict boundary partition completeness (exact partition: disjoint and union == manifest keys).
4. Epistemic classification discipline (SOURCE, TEST, CONFIG, DATA, DOC, GENERATED, THIRD_PARTY, LOCKED, BINARY, UNKNOWN).
5. Manifest dictionary key == FileEntry.rel_path identity enforcement.
6. Summary and language map recomputation in Governor.
7. Internal and external symlink security policy.
8. Live disk drift detection (file additions, modifications, deletions).
9. Hard invariant: Planned snapshot must match live snapshot.
10. Adversarial tampering attacks.
"""

import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone

from repository_snapshot import (
    FileClassification,
    LanguageKind,
    FileEntry,
    BoundaryManifest,
    RepositorySnapshot,
    RepositoryClassifier,
    RepositorySnapshotEngine
)
from artifact_governor import ArtifactGovernor


class TestV11RepositorySnapshot(unittest.TestCase):
    """Test suite for V11.1 Repository Snapshot and Classification Engine."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sclass_v11_snap_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_file(self, rel_path: str, content: str = "print('hello')") -> str:
        full_path = os.path.join(self.test_dir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as fp:
            fp.write(content)
        return full_path

    # -------------------------------------------------------------------------
    # V11.1: Deterministic Repository State Hash vs Temporal Envelope
    # -------------------------------------------------------------------------
    def test_v11_1_deterministic_repository_state_hash_independent_of_timestamp(self):
        """V11.1: repository_state_hash is 100% deterministic and independent of capture timestamp."""
        self._create_file("src/main.py", "def main(): pass")
        self._create_file("src/utils.py", "def add(a, b): return a + b")
        self._create_file("package.json", '{"name": "test"}')

        # Captured at different timestamps with different snapshot IDs
        snap1 = RepositorySnapshotEngine.capture_snapshot(
            self.test_dir, snapshot_id="SNP-A", snapshot_timestamp="2026-08-15T10:00:00Z"
        )
        snap2 = RepositorySnapshotEngine.capture_snapshot(
            self.test_dir, snapshot_id="SNP-B", snapshot_timestamp="2026-08-15T18:30:00Z"
        )

        # Content and state hashes MUST be identical
        self.assertEqual(snap1.tree_hash, snap2.tree_hash)
        self.assertEqual(snap1.repository_state_hash, snap2.repository_state_hash)

        # Envelope canonical hash reflects artifact metadata
        self.assertNotEqual(snap1.canonical_hash, snap2.canonical_hash)

        # Snapshot match reconciliation PASSES based on state identity
        is_match, errors = RepositorySnapshotEngine.reconcile_snapshot_match(snap1, snap2)
        self.assertTrue(is_match)
        self.assertEqual(len(errors), 0)

    # -------------------------------------------------------------------------
    # V11.2: Evidence-Backed Classification with DATA and UNKNOWN
    # -------------------------------------------------------------------------
    def test_v11_2_file_classification_evidence_discipline(self):
        """V11.2: Disciplinary classification of source, test, config, data, doc, binary, and unknown."""
        self._create_file("src/service.py", "class UserService: pass")
        self._create_file("tests/test_service.py", "def test_user(): pass")
        self._create_file("config/workflow.json", '{"state": "READY"}')
        self._create_file("data/fixtures/sample_users.json", '[{"id": 1}]')
        self._create_file("docs/architecture.md", "# Architecture")
        self._create_file("assets/logo.png", "\x89PNG\r\n\x1a\n")
        self._create_file("random_blob.xyz123", "unknown binary or format")

        snap = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        # SOURCE
        entry_src = snap.file_manifest["src/service.py"]
        self.assertEqual(entry_src.classification, FileClassification.SOURCE)
        self.assertEqual(entry_src.language, LanguageKind.PYTHON)

        # TEST
        entry_test = snap.file_manifest["tests/test_service.py"]
        self.assertEqual(entry_test.classification, FileClassification.TEST)
        self.assertEqual(entry_test.language, LanguageKind.PYTHON)

        # CONFIG
        entry_cfg = snap.file_manifest["config/workflow.json"]
        self.assertEqual(entry_cfg.classification, FileClassification.CONFIG)
        self.assertEqual(entry_cfg.language, LanguageKind.JSON)

        # DATA (fixtures directory json is DATA, not CONFIG!)
        entry_data = snap.file_manifest["data/fixtures/sample_users.json"]
        self.assertEqual(entry_data.classification, FileClassification.DATA)
        self.assertEqual(entry_data.language, LanguageKind.JSON)

        # DOC
        entry_doc = snap.file_manifest["docs/architecture.md"]
        self.assertEqual(entry_doc.classification, FileClassification.DOCUMENTATION)
        self.assertEqual(entry_doc.language, LanguageKind.MARKDOWN)

        # BINARY
        entry_bin = snap.file_manifest["assets/logo.png"]
        self.assertEqual(entry_bin.classification, FileClassification.BINARY_MEDIA)
        self.assertEqual(entry_bin.language, LanguageKind.BINARY)

        # UNKNOWN (never defaulted to SOURCE!)
        entry_unk = snap.file_manifest["random_blob.xyz123"]
        self.assertEqual(entry_unk.classification, FileClassification.UNKNOWN)
        self.assertEqual(entry_unk.language, LanguageKind.UNKNOWN)

    # -------------------------------------------------------------------------
    # V11.3: Boundary Manifest Exact Partition Invariant
    # -------------------------------------------------------------------------
    def test_v11_3_boundary_manifest_exact_partition_completeness(self):
        """V11.3: Every file in manifest belongs to exactly one boundary list."""
        self._create_file("src/app.py", "pass")
        self._create_file("tests/test_app.py", "pass")
        self._create_file("package-lock.json", "{}")
        self._create_file("node_modules/dep/index.js", "pass")
        self._create_file("dist/out.min.js", "pass")
        self._create_file("data/seeds.json", "{}")
        self._create_file("README.md", "# Readme")
        self._create_file("icon.png", "img")
        self._create_file("custom.blob", "raw")

        snap = RepositorySnapshotEngine.capture_snapshot(self.test_dir)
        manifest_keys = set(snap.file_manifest.keys())

        is_valid, errors = snap.boundary_manifest.validate_exact_partition(manifest_keys)
        self.assertTrue(is_valid, f"Partition errors: {errors}")
        self.assertEqual(len(errors), 0)

    # -------------------------------------------------------------------------
    # V11.4: Symlink Security Policy (Internal vs External)
    # -------------------------------------------------------------------------
    def test_v11_4_symlink_internal_and_external_security_policy(self):
        """V11.4: Internal symlinks are tracked; external symlinks are locked to prevent boundary escape."""
        self._create_file("src/target.py", "x = 10")
        src_target = os.path.join(self.test_dir, "src", "target.py")

        # Internal symlink
        internal_link = os.path.join(self.test_dir, "src", "link_internal.py")
        try:
            os.symlink(src_target, internal_link)
        except OSError:
            # On Windows without developer mode/privileges, skip symlink creation
            return

        # External file & symlink
        ext_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".py")
        ext_temp.write(b"external = True")
        ext_temp.close()

        external_link = os.path.join(self.test_dir, "src", "link_external.py")
        try:
            os.symlink(ext_temp.name, external_link)
        except OSError:
            os.unlink(ext_temp.name)
            return

        try:
            snap = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

            entry_int = snap.file_manifest.get("src/link_internal.py")
            if entry_int:
                self.assertTrue(entry_int.is_symlink)
                self.assertFalse(entry_int.is_external_symlink)

            entry_ext = snap.file_manifest.get("src/link_external.py")
            if entry_ext:
                self.assertTrue(entry_ext.is_symlink)
                self.assertTrue(entry_ext.is_external_symlink)
                self.assertEqual(entry_ext.classification, FileClassification.LOCKED)
                self.assertTrue(entry_ext.is_locked)
        finally:
            os.unlink(ext_temp.name)

    # -------------------------------------------------------------------------
    # V11.5: Reconcile Snapshot Match Detects Classification Shift
    # -------------------------------------------------------------------------
    def test_v11_5_reconcile_snapshot_match_detects_classification_shift(self):
        """V11.5: Changing classification (e.g. source -> generated) changes repository_state_hash and fails match."""
        f = self._create_file("src/client.py", "class Client: pass")
        snap_planned = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        # Same file bytes, but now header pragma marks it @generated
        with open(f, "w", encoding="utf-8") as fp:
            fp.write("# @generated by tool\nclass Client: pass")

        snap_live = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        # Tree hash changed because of bytes, but critically repository_state_hash also changes
        self.assertNotEqual(snap_planned.repository_state_hash, snap_live.repository_state_hash)
        is_match, errors = RepositorySnapshotEngine.reconcile_snapshot_match(snap_planned, snap_live)
        self.assertFalse(is_match)
        self.assertTrue(any("repository_state_hash mismatch" in e for e in errors))

    # -------------------------------------------------------------------------
    # V11.6: Manifest Dictionary Key == FileEntry.rel_path Identity Enforcement
    # -------------------------------------------------------------------------
    def test_v11_adversarial_manifest_key_mismatch_fails_closed(self):
        """Blocker 4: Manifest key mismatching FileEntry.rel_path fails strict ingestion and Governor."""
        self._create_file("src/app.py", "pass")
        snap = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        # ATTACK: Desynchronize key and entry.rel_path
        snap_dict = snap.to_dict()
        snap_dict["file_manifest"]["src/forged_key.py"] = snap_dict["file_manifest"].pop("src/app.py")

        # 1. from_governed_dict fails
        with self.assertRaises(ValueError):
            RepositorySnapshot.from_governed_dict(snap_dict)

        # 2. Governor blocks
        snap.file_manifest["src/forged_key.py"] = snap.file_manifest.pop("src/app.py")
        gov_res = ArtifactGovernor.audit_repository_snapshot_governance(snap, self.test_dir)
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("Manifest identity inconsistency" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # V11.7: Boundary Partition Overlap or Missing File Fails Closed
    # -------------------------------------------------------------------------
    def test_v11_adversarial_boundary_overlap_or_missing_fails_closed(self):
        """Blocker 5: Duplicate boundary entry or missing boundary assignment fails Governor."""
        self._create_file("src/app.py", "pass")
        self._create_file("src/util.py", "pass")
        snap = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        # ATTACK: Put src/app.py into both source_paths and generated_paths
        snap.boundary_manifest.generated_paths.append("src/app.py")
        gov_res = ArtifactGovernor.audit_repository_snapshot_governance(snap, self.test_dir)
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("Boundary partition violation" in r for r in gov_res.blocking_reasons))

        # ATTACK: Remove src/util.py from all boundaries
        snap.boundary_manifest.generated_paths.remove("src/app.py")
        snap.boundary_manifest.source_paths.remove("src/util.py")
        gov_res2 = ArtifactGovernor.audit_repository_snapshot_governance(snap, self.test_dir)
        self.assertTrue(gov_res2.is_blocked)
        self.assertTrue(any("Boundary partition incomplete" in r for r in gov_res2.blocking_reasons))

    # -------------------------------------------------------------------------
    # V11.8: Summary & Language Map Recomputation Fails Forged Manifests
    # -------------------------------------------------------------------------
    def test_v11_adversarial_forged_summary_or_language_map_fails_governor(self):
        """Item 6: Forged classification_summary or language_map is caught by Governor recomputation."""
        self._create_file("src/main.py", "pass")
        snap = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        # Baseline passes
        gov_pass = ArtifactGovernor.audit_repository_snapshot_governance(snap, self.test_dir)
        self.assertFalse(gov_pass.is_blocked)

        # ATTACK: Forge classification summary (e.g. claim 99 source files)
        snap.classification_summary["source"] = 99
        snap.canonical_hash = snap.compute_canonical_hash()

        gov_res = ArtifactGovernor.audit_repository_snapshot_governance(snap, self.test_dir)
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("classification_summary mismatch" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # V11.9: Hash Tampering Fails Governor
    # -------------------------------------------------------------------------
    def test_v11_adversarial_tampered_hashes_fail_governor(self):
        """Adversarial: Tampering repository_state_hash, tree_hash, or canonical_hash fails Governor."""
        self._create_file("app.py", "pass")
        snap = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        # Tampered state hash
        snap_state = RepositorySnapshot.from_dict(snap.to_dict())
        snap_state.repository_state_hash = "0" * 64
        gov_res1 = ArtifactGovernor.audit_repository_snapshot_governance(snap_state, self.test_dir)
        self.assertTrue(gov_res1.is_blocked)
        self.assertTrue(any("repository_state_hash mismatch" in r for r in gov_res1.blocking_reasons))

        # Tampered tree hash
        snap_tree = RepositorySnapshot.from_dict(snap.to_dict())
        snap_tree.tree_hash = "1" * 64
        gov_res2 = ArtifactGovernor.audit_repository_snapshot_governance(snap_tree, self.test_dir)
        self.assertTrue(gov_res2.is_blocked)
        self.assertTrue(any("tree_hash mismatch" in r for r in gov_res2.blocking_reasons))

        # Tampered canonical hash
        snap_canon = RepositorySnapshot.from_dict(snap.to_dict())
        snap_canon.canonical_hash = "2" * 64
        gov_res3 = ArtifactGovernor.audit_repository_snapshot_governance(snap_canon, self.test_dir)
        self.assertTrue(gov_res3.is_blocked)
        self.assertTrue(any("canonical_hash mismatch" in r for r in gov_res3.blocking_reasons))

    def test_v11_atomic_persistence_and_rehydration(self):
        """V11.1: Snapshot saves atomically to disk and loads with strict validation."""
        self._create_file("main.py", "print('S-Class')")
        snap = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        save_path = os.path.join(self.test_dir, ".agents", "repo_snapshot.json")
        RepositorySnapshotEngine.save_snapshot(snap, save_path)
        self.assertTrue(os.path.exists(save_path))

        loaded = RepositorySnapshotEngine.load_snapshot(save_path, strict=True)
        self.assertEqual(loaded.canonical_hash, snap.canonical_hash)
        self.assertEqual(loaded.tree_hash, snap.tree_hash)
        self.assertEqual(loaded.repository_state_hash, snap.repository_state_hash)


if __name__ == "__main__":
    unittest.main()
