"""
S-Class Verification: FileVerifier (Tier V2).
"""
from __future__ import annotations
import fnmatch
from typing import Any, List, Dict, Optional
from sclass.domain.verification import VerificationResult


class FileVerifier:
    def __init__(self, allowed_patterns: Optional[List[str]] = None, forbidden_patterns: Optional[List[str]] = None):
        self.allowed_patterns = allowed_patterns or []
        self.forbidden_patterns = forbidden_patterns or []

    def _matches(self, path: str, pattern: str) -> bool:
        norm_path = path.replace("\\", "/").lstrip("/")
        norm_pat = pattern.replace("\\", "/").lstrip("/")
        if fnmatch.fnmatch(norm_path, norm_pat):
            return True
        if norm_pat.endswith("/**"):
            prefix = norm_pat[:-3]
            if norm_path == prefix or norm_path.startswith(prefix + "/"):
                return True
        return False

    def verify_delta(self, delta: Dict[str, Any]) -> VerificationResult:
        touched = set(delta.get("files_modified", []) + delta.get("files_added", []) + delta.get("files_deleted", []))

        # Check forbidden patterns first
        for f in touched:
            for pat in self.forbidden_patterns:
                if self._matches(f, pat):
                    return VerificationResult(
                        status="REJECT",
                        reason=f"Mutation touches forbidden path '{f}' matching rule '{pat}'",
                        metadata={"forbidden_file": f, "pattern": pat}
                    )

        # Check allowed patterns if declared
        if self.allowed_patterns:
            for f in touched:
                if not any(self._matches(f, pat) for pat in self.allowed_patterns):
                    return VerificationResult(
                        status="REJECT",
                        reason=f"Mutation touches unapproved path '{f}' outside allowed boundaries",
                        metadata={"unapproved_file": f}
                    )

        return VerificationResult(
            status="ACCEPT",
            reason=f"All {len(touched)} touched file(s) satisfy boundary constraints",
            metadata={"touched_files": list(touched)}
        )
