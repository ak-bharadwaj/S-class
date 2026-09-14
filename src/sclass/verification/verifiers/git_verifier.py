"""
S-Class Verification: GitVerifier (Tier V2).
"""
from __future__ import annotations
from typing import Any, Dict, Optional
from sclass.domain.verification import VerificationResult


class GitVerifier:
    def __init__(self, expected_branch: Optional[str] = None, require_clean: bool = False):
        self.expected_branch = expected_branch
        self.require_clean = require_clean

    def verify_git_state(self, git_state: Dict[str, Any]) -> VerificationResult:
        branch = git_state.get("branch")
        dirty = git_state.get("dirty_files", [])

        if self.expected_branch and branch != self.expected_branch:
            return VerificationResult(
                status="REJECT",
                reason=f"Git branch '{branch}' does not match expected branch '{self.expected_branch}'",
                metadata={"branch": branch, "expected": self.expected_branch}
            )

        if self.require_clean and dirty:
            return VerificationResult(
                status="REJECT",
                reason=f"Git working tree is dirty ({len(dirty)} files modified)",
                metadata={"dirty_files": dirty}
            )

        return VerificationResult(
            status="ACCEPT",
            reason="Git repository state satisfies branch and cleanliness constraints",
            metadata=git_state
        )
