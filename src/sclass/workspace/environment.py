"""Minimal allowlisted execution environment for S-Class workers and verifiers.

Enforces:
- Fixed PATH (/usr/local/bin:/usr/bin:/bin plus sys.executable parent directory)
- Fixed locale (LANG=C.UTF-8, LC_ALL=C.UTF-8)
- Workspace-local isolated HOME and TMPDIR (.sclass_home and .sclass_tmp)
- Complete scrubbing of all parent environment variables and secrets (zero parent leak)
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Optional


def make_minimal_environment(
    workspace: str | Path,
    extra: Optional[Mapping[str, str]] = None,
) -> dict[str, str]:
    """Construct an allowlisted minimal environment with zero parent passthrough."""
    ws = Path(workspace).resolve()
    home = ws / ".sclass_home"
    tmp = ws / ".sclass_tmp"
    home.mkdir(parents=True, exist_ok=True)
    tmp.mkdir(parents=True, exist_ok=True)

    exe_dir = Path(sys.executable).parent
    if sys.platform == "win32":
        fixed_path = f"{exe_dir};C:\\Windows\\System32;C:\\Windows"
    else:
        fixed_path = f"{exe_dir}:/usr/local/bin:/usr/bin:/bin" if exe_dir.exists() else "/usr/local/bin:/usr/bin:/bin"

    env: dict[str, str] = {
        "PATH": fixed_path,
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "HOME": str(home),
        "TMPDIR": str(tmp),
    }

    if sys.platform == "win32":
        env["SYSTEMROOT"] = "C:\\Windows"
        env["TEMP"] = str(tmp)
        env["TMP"] = str(tmp)

    if extra:
        for k, v in extra.items():
            if k and isinstance(v, str):
                env[k] = v

    return env
