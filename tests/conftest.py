import os
import sys

# Ensure root directory is added to sys.path for pytest across all CI runners and OS platforms
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
