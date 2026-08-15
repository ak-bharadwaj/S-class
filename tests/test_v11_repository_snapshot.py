"""
S-Class EOS V11.1 Test Suite — Repository Snapshot & Classification Engine
Validates:
1. Deterministic Merkle tree hashing and canonical snapshot integrity.
2. Evidence-backed file classification (SOURCE, TEST, CONFIG, DOC, GENERATED, THIRD_PARTY, LOCKED, BINARY).
3. Header pragma autogen detection.
4. Governed strict deserialization with tamper protection.
5. Live disk drift detection (file additions, modifications, deletions).
6. Hard invariant: Planned snapshot must match live snapshot.
7. Adversarial tampering attacks.
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
    # V11.1: Canonical Tree Hashing & Reproducibility
    # -------------------------------------------------------------------------
    def test_v11_1_repository_snapshot_canonical_hashing_and_reproducibility(self):
        """V11.1: Identical file trees produce bit-for-bit identical tree hashes."""
        self._create_file("src/main.py", "def main(): pass")
        self._create_file("src/utils.py", "def add(a, b): return a + b")
        self._create_file("package.json", '{"name": "test"}')

        snap1 = RepositorySnapshotEngine.capture_snapshot(self.test_dir, snapshot_id="SNP-1", snapshot_timestamp="2026-08-15T00:00:00Z")
        snap2 = RepositorySnapshotEngine.capture_snapshot(self.test_dir, snapshot_id="SNP-1", snapshot_timestamp="2026-08-15T00:00:00Z")

        self.assertEqual(snap1.tree_hash, snap2.tree_hash)
        self.assertEqual(snap1.canonical_hash, snap2.canonical_hash)
        self.assertEqual(len(snap1.file_manifest), 3)

    # -------------------------------------------------------------------------
    # V11.2: Evidence-Backed Classification
    # -------------------------------------------------------------------------
    def test_v11_2_file_classification_source_test_config_doc_binary(self):
        """V11.2: Correct classification of source, test, config, documentation, and binary files."""
        self._create_file("src/service.py", "class UserService: pass")
        self._create_file("tests/test_service.py", "def test_user(): pass")
        self._create_file("config/workflow.json", '{"state": "READY"}')
        self._create_file("docs/architecture.md", "# Architecture")
        self._create_file("assets/logo.png", "\x89PNG\r\n\x1a\n")

        snap = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        # SOURCE
        entry_src = snap.file_manifest["src/service.py"]
        self.assertEqual(entry_src.classification, FileClassification.SOURCE)
        self.assertEqual(entry_src.language, LanguageKind.PYTHON)
        self.assertIn("1st-party source code", entry_src.classification_reason)

        # TEST
        entry_test = snap.file_manifest["tests/test_service.py"]
        self.assertEqual(entry_test.classification, FileClassification.TEST)
        self.assertEqual(entry_test.language, LanguageKind.PYTHON)
        self.assertIn("test", entry_test.classification_reason.lower())

        # CONFIG
        entry_cfg = snap.file_manifest["config/workflow.json"]
        self.assertEqual(entry_cfg.classification, FileClassification.CONFIG)
        self.assertEqual(entry_cfg.language, LanguageKind.JSON)

        # DOC
        entry_doc = snap.file_manifest["docs/architecture.md"]
        self.assertEqual(entry_doc.classification, FileClassification.DOCUMENTATION)
        self.assertEqual(entry_doc.language, LanguageKind.MARKDOWN)

        # BINARY
        entry_bin = snap.file_manifest["assets/logo.png"]
        self.assertEqual(entry_bin.classification, FileClassification.BINARY_MEDIA)
        self.assertEqual(entry_bin.language, LanguageKind.BINARY)

    # -------------------------------------------------------------------------
    # V11.3: Generated File & Pragma Detection
    # -------------------------------------------------------------------------
    def test_v11_3_generated_file_content_pragma_detection(self):
        """V11.3: Detects @generated and DO NOT EDIT header pragmas in files."""
        # 1. Path-based generated
        self._create_file("dist/bundle.min.js", "console.log(1);")
        # 2. Content pragma generated
        self._create_file(
            "src/client.py",
            "# @generated by proto-compiler v1.2\n# DO NOT EDIT\nclass Client: pass"
        )

        snap = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        entry_bundle = snap.file_manifest["dist/bundle.min.js"]
        self.assertEqual(entry_bundle.classification, FileClassification.GENERATED)
        self.assertTrue(entry_bundle.is_generated)

        entry_client = snap.file_manifest["src/client.py"]
        self.assertEqual(entry_client.classification, FileClassification.GENERATED)
        self.assertTrue(entry_client.is_generated)
        self.assertIn("autogeneration pragma", entry_client.classification_reason)
        self.assertIn("src/client.py", snap.boundary_manifest.generated_paths)

    # -------------------------------------------------------------------------
    # V11.4: Locked Files and Third-Party Boundaries
    # -------------------------------------------------------------------------
    def test_v11_4_locked_files_and_third_party_boundaries(self):
        """V11.4: Lockfiles and third-party vendor dirs are strictly segregated into boundaries."""
        self._create_file("package-lock.json", '{"lockfileVersion": 2}')
        self._create_file("poetry.lock", '[[package]]\nname = "pytest"')
        self._create_file("node_modules/lodash/index.js", "module.exports = {};")
        self._create_file("vendor/lib/plugin.py", "def ext(): pass")

        snap = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        # Locked
        entry_npm = snap.file_manifest["package-lock.json"]
        self.assertEqual(entry_npm.classification, FileClassification.LOCKED)
        self.assertTrue(entry_npm.is_locked)
        self.assertIn("package-lock.json", snap.boundary_manifest.locked_paths)

        entry_poetry = snap.file_manifest["poetry.lock"]
        self.assertEqual(entry_poetry.classification, FileClassification.LOCKED)
        self.assertTrue(entry_poetry.is_locked)
        self.assertIn("poetry.lock", snap.boundary_manifest.locked_paths)

        # Third Party
        entry_node = snap.file_manifest["node_modules/lodash/index.js"]
        self.assertEqual(entry_node.classification, FileClassification.THIRD_PARTY)
        self.assertTrue(entry_node.is_third_party)
        self.assertIn("node_modules/lodash/index.js", snap.boundary_manifest.third_party_paths)

        entry_vendor = snap.file_manifest["vendor/lib/plugin.py"]
        self.assertEqual(entry_vendor.classification, FileClassification.THIRD_PARTY)
        self.assertTrue(entry_vendor.is_third_party)

    # -------------------------------------------------------------------------
    # V11.5: Strict Deserialization & Governed Ingestion
    # -------------------------------------------------------------------------
    def test_v11_5_strict_deserialization_and_governed_ingestion(self):
        """V11.5: Strict rehydration enforces tree hash and canonical hash validity."""
        self._create_file("src/app.py", "app = True")
        snap = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        # Valid rehydration
        snap_dict = snap.to_dict()
        rehydrated = RepositorySnapshot.from_governed_dict(snap_dict)
        self.assertEqual(rehydrated.canonical_hash, snap.canonical_hash)
        self.assertEqual(rehydrated.tree_hash, snap.tree_hash)

        # Tampered tree_hash fails
        tampered_tree = snap.to_dict()
        tampered_tree["tree_hash"] = "0" * 64
        with self.assertRaises(ValueError):
            RepositorySnapshot.from_governed_dict(tampered_tree)

        # Tampered canonical_hash fails
        tampered_canon = snap.to_dict()
        tampered_canon["canonical_hash"] = "f" * 64
        with self.assertRaises(ValueError):
            RepositorySnapshot.from_governed_dict(tampered_canon)

    # -------------------------------------------------------------------------
    # V11.6: Live Disk Drift Detection
    # -------------------------------------------------------------------------
    def test_v11_6_live_disk_verification_and_drift_detection(self):
        """V11.6: Verification engine detects live file modifications, additions, and deletions."""
        f1 = self._create_file("src/service.py", "v1")
        f2 = self._create_file("src/models.py", "User")
        snap = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        # 1. Exact match initially
        is_synced, errors = RepositorySnapshotEngine.verify_snapshot_integrity(snap, self.test_dir)
        self.assertTrue(is_synced)
        self.assertEqual(len(errors), 0)

        # 2. File modification detected
        with open(f1, "w", encoding="utf-8") as fp:
            fp.write("v2_modified")
        is_synced, errors = RepositorySnapshotEngine.verify_snapshot_integrity(snap, self.test_dir)
        self.assertFalse(is_synced)
        self.assertTrue(any("content modified" in e for e in errors))

        # 3. File addition detected
        self._create_file("src/secret.py", "secret_key = 123")
        is_synced, errors = RepositorySnapshotEngine.verify_snapshot_integrity(snap, self.test_dir)
        self.assertFalse(is_synced)
        self.assertTrue(any("untracked added files" in e for e in errors))

        # 4. File deletion detected
        os.remove(f2)
        is_synced, errors = RepositorySnapshotEngine.verify_snapshot_integrity(snap, self.test_dir)
        self.assertFalse(is_synced)
        self.assertTrue(any("missing files" in e for e in errors))

    # -------------------------------------------------------------------------
    # V11.7: Hard Invariant: Snapshot Match Reconciliation
    # -------------------------------------------------------------------------
    def test_v11_7_snapshot_match_reconciliation_hard_invariant(self):
        """Hard Invariant: ChangeSet cannot apply unless planned snapshot matches live snapshot."""
        self._create_file("src/core.py", "x = 1")
        snap_planned = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        # Same live disk -> Match
        snap_live = RepositorySnapshotEngine.capture_snapshot(self.test_dir)
        is_match, errors = RepositorySnapshotEngine.reconcile_snapshot_match(snap_planned, snap_live)
        self.assertTrue(is_match)

        # Live disk modifies code -> Mismatch!
        self._create_file("src/core.py", "x = 2")
        snap_live_drifted = RepositorySnapshotEngine.capture_snapshot(self.test_dir)
        is_match, errors = RepositorySnapshotEngine.reconcile_snapshot_match(snap_planned, snap_live_drifted)
        self.assertFalse(is_match, "Drifted repository snapshot MUST FAIL reconciliation!")
        self.assertTrue(any("tree_hash mismatch" in e for e in errors))

    # -------------------------------------------------------------------------
    # V11.8: Governor Gate & Adversarial Tampering
    # -------------------------------------------------------------------------
    def test_v11_adversarial_tampered_file_hash_fails_closed(self):
        """Adversarial: Tampering a single file_hash inside manifest fails Governor audit."""
        self._create_file("src/auth.py", "def login(): pass")
        snap = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        # Valid baseline
        gov_pass = ArtifactGovernor.audit_repository_snapshot_governance(snap, self.test_dir)
        self.assertFalse(gov_pass.is_blocked)

        # ATTACK: Modify file hash in manifest but recompute canonical hash
        snap.file_manifest["src/auth.py"].file_hash = "0" * 64
        snap.canonical_hash = snap.compute_canonical_hash()

        # Governor blocks because tree_hash doesn't match computed tree hash
        gov_block = ArtifactGovernor.audit_repository_snapshot_governance(snap, self.test_dir)
        self.assertTrue(gov_block.is_blocked)
        self.assertTrue(any("tree_hash mismatch" in r for r in gov_block.blocking_reasons))

    def test_v11_adversarial_unauthorized_source_reclassification_of_locked_file_blocked(self):
        """Adversarial: Claiming a locked package-lock.json as 'source' is caught by boundary check."""
        self._create_file("package-lock.json", '{"lock": 1}')
        snap = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        # ATTACK: Force package-lock.json into source_paths and remove is_locked
        snap.boundary_manifest.source_paths.append("package-lock.json")
        snap.canonical_hash = snap.compute_canonical_hash()

        gov_res = ArtifactGovernor.audit_repository_snapshot_governance(snap, self.test_dir)
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("Boundary violation: locked file 'package-lock.json' present in source_paths" in r for r in gov_res.blocking_reasons))

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

    def test_v11_adversarial_tampered_tree_hash_fails_governor(self):
        """Adversarial: Forged tree_hash fails Governor verification."""
        self._create_file("app.py", "pass")
        snap = RepositorySnapshotEngine.capture_snapshot(self.test_dir)
        snap.tree_hash = "f" * 64

        gov_res = ArtifactGovernor.audit_repository_snapshot_governance(snap, self.test_dir)
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("tree_hash mismatch" in r for r in gov_res.blocking_reasons))

    def test_v11_adversarial_tampered_canonical_hash_fails_governor(self):
        """Adversarial: Forged canonical_hash fails Governor verification."""
        self._create_file("app.py", "pass")
        snap = RepositorySnapshotEngine.capture_snapshot(self.test_dir)
        snap.canonical_hash = "e" * 64

        gov_res = ArtifactGovernor.audit_repository_snapshot_governance(snap, self.test_dir)
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("canonical_hash mismatch" in r for r in gov_res.blocking_reasons))

    def test_v11_adversarial_missing_classification_reason_fails_closed(self):
        """Adversarial: Missing classification reason on any entry fails Governor verification."""
        self._create_file("app.py", "pass")
        snap = RepositorySnapshotEngine.capture_snapshot(self.test_dir)
        snap.file_manifest["app.py"].classification_reason = ""
        snap.canonical_hash = snap.compute_canonical_hash()

        gov_res = ArtifactGovernor.audit_repository_snapshot_governance(snap, self.test_dir)
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("missing mandatory evidence-backed classification_reason" in r for r in gov_res.blocking_reasons))

    def test_v11_multi_language_extension_and_boundary_indexing(self):
        """V11.1: Indexing across multiple languages (TS, Py, Rust, Go, SQL, HTML)."""
        self._create_file("src/app.ts", "const x: number = 1;")
        self._create_file("src/main.rs", "fn main() {}")
        self._create_file("src/server.go", "package main")
        self._create_file("db/schema.sql", "CREATE TABLE users (id INT);")
        self._create_file("public/index.html", "<html></html>")
        self._create_file("styles/theme.css", "body { color: red; }")
        self._create_file("scripts/deploy.sh", "#!/bin/bash\necho 1")

        snap = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        self.assertIn("typescript", snap.language_map)
        self.assertIn("rust", snap.language_map)
        self.assertIn("go", snap.language_map)
        self.assertIn("sql", snap.language_map)
        self.assertIn("html", snap.language_map)
        self.assertIn("css", snap.language_map)
        self.assertIn("shell", snap.language_map)

        self.assertIn("src/app.ts", snap.boundary_manifest.source_paths)
        self.assertIn("src/main.rs", snap.boundary_manifest.source_paths)
        self.assertIn("src/server.go", snap.boundary_manifest.source_paths)
        self.assertIn("db/schema.sql", snap.boundary_manifest.source_paths)


if __name__ == "__main__":
    unittest.main()
