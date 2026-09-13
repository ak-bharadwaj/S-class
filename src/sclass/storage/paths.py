"""
S-Class Storage: Canonical Path Containment and Workspace Directory Structure.
"""

from __future__ import annotations
import os
from typing import Optional


class WorkspacePaths:
    """Manages canonical paths and containment within a project workspace."""

    def __init__(self, workspace_dir: str):
        self.root = os.path.abspath(workspace_dir)
        self.sclass_dir = os.path.join(self.root, ".sclass")
        self.state_dir = os.path.join(self.sclass_dir, "state")
        self.events_dir = os.path.join(self.sclass_dir, "events")
        self.evidence_dir = os.path.join(self.sclass_dir, "evidence")
        self.receipts_dir = os.path.join(self.evidence_dir, "receipts")
        self.trust_dir = os.path.join(self.sclass_dir, "trust")
        self.ledger_dir = os.path.join(self.trust_dir, "ledger")
        self.locks_dir = os.path.join(self.sclass_dir, "locks")
        self.agent_dir = os.path.join(self.sclass_dir, "agent")

        # Compatibility paths (.agents/)
        self.legacy_agents_dir = os.path.join(self.root, ".agents")
        self.legacy_receipts_dir = os.path.join(self.legacy_agents_dir, "receipts")
        self.legacy_ledger_dir = os.path.join(self.legacy_agents_dir, "ledger")

    def ensure_directories(self) -> None:
        """Initializes all authoritative S-Class workspace directories."""
        for d in (
            self.sclass_dir,
            self.state_dir,
            self.events_dir,
            self.evidence_dir,
            self.receipts_dir,
            self.trust_dir,
            self.ledger_dir,
            self.locks_dir,
            self.agent_dir,
            self.legacy_receipts_dir,
            self.legacy_ledger_dir,
        ):
            os.makedirs(d, exist_ok=True)

    def is_contained(self, target_path: str, base_dir: Optional[str] = None) -> bool:
        """Returns True if target_path is strictly within base_dir (defaulting to project root)."""
        base = os.path.abspath(base_dir or self.root)
        try:
            target = os.path.abspath(target_path)
            return os.path.commonpath([base, target]) == base
        except (ValueError, OSError):
            return False

    def is_sclass_protected(self, target_path: str) -> bool:
        """Determines if a target path is under S-Class-only authoritative control."""
        abs_target = os.path.abspath(target_path)
        # .sclass/agent/ is agent-writable; all other .sclass/ subdirectories are S-Class-only
        if self.is_contained(abs_target, self.sclass_dir):
            return not self.is_contained(abs_target, self.agent_dir)
        # Legacy .agents/ protected areas (ledger, receipts, reports, verification)
        if self.is_contained(abs_target, self.legacy_agents_dir):
            rel = os.path.relpath(abs_target, self.legacy_agents_dir)
            first_part = rel.split(os.sep)[0]
            if first_part in ("ledger", "receipts", "reports", "verification"):
                return True
        return False
