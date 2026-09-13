"""
S-Class Survival v0: Verification Package Core (sclass/survival/verification/__init__.py)

Implements Phase 9:
verification/
    execution.py
    claims.py
    evidence.py
"""

from __future__ import annotations
from sclass.survival.verification.claims import verify_claim
from sclass.survival.verification.evidence import check_verification_staleness
from sclass.survival.verification.execution import execute_and_record
from sclass.survival.evidence import _get_git_commit_hash, _get_git_changed_files

__all__ = [
    "verify_claim",
    "check_verification_staleness",
    "execute_and_record",
    "_get_git_commit_hash",
    "_get_git_changed_files",
]
