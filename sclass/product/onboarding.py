"""
S-Class Product: Onboarding and Workspace Scaffolding.
Sets up standard directory layout (.sclass/config, state, evidence, trust, events, cache, adapters, locks).
"""

from __future__ import annotations
import os
from typing import Dict, Any

from sclass.control.resources import SCLASS_DIR_LAYOUT
from sclass.storage.paths import WorkspacePaths
from sclass.trust.ledger import LocalLedger
from sclass.state.tasks import StateRepository
from sclass.domain.project import Project, ProjectBoundary


def initialize_workspace(workspace_dir: str = ".") -> Dict[str, Any]:
    """Initializes standard S-Class workspace layout and cryptographic roots."""
    ws = os.path.abspath(workspace_dir)
    sclass_base = os.path.join(ws, ".sclass")

    created_dirs = []
    for d in SCLASS_DIR_LAYOUT:
        target = os.path.join(sclass_base, d)
        os.makedirs(target, exist_ok=True)
        created_dirs.append(target)

    # Initialize repository state and project
    repo = StateRepository(ws)
    proj_name = os.path.basename(ws)
    project = repo.get_project(proj_name)
    if not project:
        project = Project(
            project_id=proj_name,
            name=proj_name,
            boundary=ProjectBoundary(ws),
        )
        repo.save_project(project)

    # Initialize ledger genesis
    ledger = LocalLedger(ws)
    last = ledger.get_last_entry()
    if not last:
        ledger.append("genesis", {"workspace": ws, "initialized_by": "sclass.onboarding"})

    return {
        "workspace": ws,
        "sclass_dir": sclass_base,
        "directories": created_dirs,
        "project_id": proj_name,
        "initialized": True,
    }
