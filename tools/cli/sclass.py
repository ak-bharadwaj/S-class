import sys
from pathlib import Path

# Remove script directory from sys.path if it shadows the sclass package
if sys.path and Path(sys.path[0]).resolve() == Path(__file__).resolve().parent:
    sys.path.pop(0)

from sclass.cli import main

if __name__ == "__main__":
    main()
