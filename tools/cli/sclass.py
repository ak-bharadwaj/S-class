import sys
from pathlib import Path

# Technical Justification (ADR-1 §5):
# When invoked directly via `python tools/cli/sclass.py`, Python automatically prepends
# the script's directory (`tools/cli`) to `sys.path[0]`. Because the script is named
# `sclass.py`, Python attempts to import from itself rather than the installed package,
# causing `ModuleNotFoundError: No module named 'sclass.cli'; 'sclass' is not a package`.
# Removing `tools/cli` from sys.path[0] resolves shadowing and imports the real `sclass` package.
if sys.path and Path(sys.path[0]).resolve() == Path(__file__).resolve().parent:
    sys.path.pop(0)

from sclass.cli import main

if __name__ == "__main__":
    main()
