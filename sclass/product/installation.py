"""
S-Class Product: Installation and Environment Verification.
Verifies runtime environment, Python versions, and PATH accessibility.
"""

from __future__ import annotations
import sys
import shutil
import platform
from typing import Dict, Any


def verify_installation() -> Dict[str, Any]:
    """Verifies that S-Class CLI and runtime dependencies are correctly installed."""
    py_version = sys.version_info
    py_supported = (py_version.major == 3 and py_version.minor >= 10)
    sclass_on_path = shutil.which("sclass") is not None

    return {
        "python_version": f"{py_version.major}.{py_version.minor}.{py_version.micro}",
        "python_supported": py_supported,
        "platform": platform.system(),
        "arch": platform.machine(),
        "sclass_executable": shutil.which("sclass"),
        "installed_on_path": sclass_on_path,
        "ready": py_supported,
    }
