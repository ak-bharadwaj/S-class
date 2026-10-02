"""
Tool Package Integrity Verifier: Validates SHA-256 digests of external dependencies.
"""
import hashlib
from typing import Dict

class ToolPackageVerifier:
    def __init__(self, trusted_manifest: Dict[str, str]):
        self.trusted_manifest = trusted_manifest

    def verify_package(self, package_name: str, content_bytes: bytes) -> bool:
        if package_name not in self.trusted_manifest:
            return False
        expected_digest = self.trusted_manifest[package_name]
        actual_digest = hashlib.sha256(content_bytes).hexdigest()
        return actual_digest == expected_digest
