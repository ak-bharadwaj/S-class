import sys, os
sys.path.insert(0, os.getcwd())
from token_budget import can_fast_path

cases = [
    "Remove user from system",
    "Update pricing model",
    "Change the world entirely",
    "Fix complex caching issue"
]
for c in cases:
    print(f"'{c}' -> {can_fast_path(c, [])}")
