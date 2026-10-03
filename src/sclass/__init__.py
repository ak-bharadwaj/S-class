"""S-Class v6.0.1: Universal Trust and Control Plane."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure singleton module identity between sclass.kernel and top-level kernel names
if "sclass_semantics_v6_0_1" in sys.modules and "sclass_runtime_v6_0_1" in sys.modules:
    _semantics = sys.modules["sclass_semantics_v6_0_1"]
    _runtime = sys.modules["sclass_runtime_v6_0_1"]
else:
    try:
        from .kernel import sclass_semantics_v6_0_1 as _semantics
        from .kernel import sclass_runtime_v6_0_1 as _runtime
    except ImportError:
        # Development checkout fallback when running directly in source repo without wheel install
        _root = Path(__file__).resolve().parents[2]
        import importlib.util

        def _load(path: Path, name: str):
            spec = importlib.util.spec_from_file_location(name, str(path))
            mod = importlib.util.module_from_spec(spec)
            sys.modules[name] = mod
            spec.loader.exec_module(mod)
            return mod

        _semantics = _load(_root / "10-CONFORMANCE" / "sclass_semantics_v6_0_1.py", "sclass_semantics_v6_0_1")
        _runtime = _load(_root / "20-RUNTIME" / "sclass_runtime_v6_0_1.py", "sclass_runtime_v6_0_1")

import types

_kernel = sys.modules.get("sclass.kernel")
if _kernel is None:
    _kernel = types.ModuleType("sclass.kernel")
    sys.modules["sclass.kernel"] = _kernel
_kernel.sclass_semantics_v6_0_1 = _semantics
_kernel.sclass_runtime_v6_0_1 = _runtime

# Canonicalize in sys.modules under both names so Enums and types share exact identity
sys.modules["sclass_semantics_v6_0_1"] = _semantics
sys.modules["sclass_runtime_v6_0_1"] = _runtime
sys.modules["sclass.kernel.sclass_semantics_v6_0_1"] = _semantics
sys.modules["sclass.kernel.sclass_runtime_v6_0_1"] = _runtime
sys.modules[__name__].kernel = _kernel

# Re-export kernel symbols
from sclass_runtime_v6_0_1 import *  # noqa: F401,F403
from sclass_semantics_v6_0_1 import *  # noqa: F401,F403

__version__ = "6.0.1"
