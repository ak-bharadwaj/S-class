import sys
import os
sys.path.insert(0, os.getcwd())
from token_budget import can_fast_path


def test_fast_path_cases():
    cases = [
        "Remove user from system",
        "Update pricing model",
        "Change the world entirely",
        "Fix complex caching issue",
    ]
    for c in cases:
        result = can_fast_path(c, [])
        assert isinstance(result, bool)

