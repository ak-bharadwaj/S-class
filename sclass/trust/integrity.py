"""
S-Class Trust: Integrity Auditor.
Independent validator for ledger chains, evidence hashes, and checkpoint signatures.
"""

from __future__ import annotations
import os
import json
from typing import Tuple, List, Dict, Any, Optional
from sclass.trust.ledger import LocalLedger


class LedgerIntegrityAuditor:
    """Audits local trust infrastructure and checks for tamper attempts or forked history."""

    @classmethod
    def audit_workspace(cls, workspace_dir: str) -> Dict[str, Any]:
        ledger = LocalLedger(workspace_dir)
        valid, err = ledger.verify_integrity()
        entries = ledger.read_all_entries()
        head_hash = ledger.get_last_hash()

        return {
            "valid": valid,
            "error": err,
            "entry_count": len(entries),
            "head_hash": head_hash,
            "ledger_path": ledger.ledger_file,
        }
