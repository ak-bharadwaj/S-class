"""
Unit tests for S-Class v6 Core Engines (ast_dependency_resolver, zero_infra_db, port_resolver)
"""

import os
import json
import tempfile
import unittest
from ast_dependency_resolver import ASTDependencyResolver
from zero_infra_db import ZeroInfraDbEngine
from port_resolver import PortConflictResolver


class TestV12Engines(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def test_ast_dependency_resolver_injects_missing_packages(self):
        # Create a sample TSX file with missing imports
        src_dir = os.path.join(self.test_dir, "src")
        os.makedirs(src_dir, exist_ok=True)
        component_file = os.path.join(src_dir, "Dashboard.tsx")
        with open(component_file, "w", encoding="utf-8") as f:
            f.write("import { motion } from 'framer-motion';\nimport { Shield } from 'lucide-react';\nimport axios from 'axios';\n")

        # Create basic package.json without lucide-react or axios
        pkg_file = os.path.join(self.test_dir, "package.json")
        with open(pkg_file, "w", encoding="utf-8") as f:
            json.dump({"name": "test-app", "dependencies": {}}, f)

        # Verify read_only=True does not write to disk
        res_ro = ASTDependencyResolver.resolve_workspace_dependencies(workspace_dir=self.test_dir, read_only=True)
        self.assertTrue(res_ro["read_only"])
        self.assertIn("lucide-react", res_ro["npm_packages_injected"])
        with open(pkg_file, "r", encoding="utf-8") as f:
            pkg_initial = json.load(f)
        self.assertEqual(pkg_initial["dependencies"], {})

        res = ASTDependencyResolver.resolve_workspace_dependencies(workspace_dir=self.test_dir)
        self.assertFalse(res["read_only"])
        self.assertIn("lucide-react", res["npm_packages_injected"])
        self.assertIn("axios", res["npm_packages_injected"])

        # Read updated package.json
        with open(pkg_file, "r", encoding="utf-8") as f:
            pkg_data = json.load(f)
        self.assertIn("lucide-react", pkg_data["dependencies"])
        self.assertIn("axios", pkg_data["dependencies"])

    def test_zero_infra_db_fallback(self):
        res = ZeroInfraDbEngine.audit_and_fallback_database(workspace_dir=self.test_dir)
        self.assertEqual(res["status"], "HEALTHY")
        self.assertTrue(res["sqlite_active"])
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, ".env")))

    def test_port_conflict_resolver(self):
        port = PortConflictResolver.find_available_port(preferred_port=3000)
        self.assertGreaterEqual(port, 3000)


if __name__ == "__main__":
    unittest.main()
