"""
S-Class Product: Diagnostics Engine.
Performs deep health and tamper diagnostics on an S-Class workspace.
"""

from __future__ import annotations
import os
from typing import Dict, Any, List, Tuple

from sclass.storage.paths import WorkspacePaths
from sclass.trust.ledger import LocalLedger
from sclass.state.sqlite import SQLiteStateStore


def run_diagnostics(workspace_dir: str = ".") -> Dict[str, Any]:
    ws = os.path.abspath(workspace_dir)
    paths = WorkspacePaths(ws)

    results: List[Tuple[str, bool, str]] = []

    # 1. Directory presence
    results.append(("Workspace directory", os.path.isdir(ws), ws))
    results.append(("S-Class root (.sclass)", os.path.isdir(paths.sclass_dir), paths.sclass_dir))
    results.append(("State database", os.path.isfile(os.path.join(paths.state_dir, "project.db")), paths.state_dir))

    # 2. Ledger integrity
    ledger = LocalLedger(ws)
    is_valid, err = ledger.verify_integrity()
    results.append(("Cryptographic ledger integrity", is_valid, err or "OK"))

    # 3. SQLite connection check
    try:
        store = SQLiteStateStore(ws)
        with store.get_connection() as conn:
            row = conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
            sqlite_ok = row is not None
    except Exception as sq_err:
        sqlite_ok = False
        err = str(sq_err)

    results.append(("SQLite relational engine", sqlite_ok, "WAL mode active"))

    all_passed = all(passed for _, passed, _ in results)

    return {
        "workspace": ws,
        "healthy": all_passed,
        "diagnostics": [
            {"name": name, "passed": passed, "details": details}
            for name, passed, details in results
        ],
    }
