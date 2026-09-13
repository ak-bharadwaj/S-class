"""
Shared fixtures for the S-Class Adversarial Test Suite.
"""

import os
import pytest
from sclass.storage.paths import WorkspacePaths
from sclass.trust.ledger import LocalLedger


@pytest.fixture
def adv_workspace(tmp_path):
    ws = tmp_path / "adversarial_workspace"
    ws.mkdir(parents=True, exist_ok=True)
    paths = WorkspacePaths(str(ws))
    paths.ensure_directories()
    # Initialize ledger genesis
    ledger = LocalLedger(str(ws))
    ledger.append("genesis", {"workspace": str(ws), "environment": "test"})
    return str(ws)
