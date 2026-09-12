"""
S-Class V12 CLI Entry Point (__main__.py)
Allows running: python -m sclass-v5 [command] or python . [command]
"""

import sys
from sclass_cli import run_cli

if __name__ == "__main__":
    sys.exit(run_cli())
