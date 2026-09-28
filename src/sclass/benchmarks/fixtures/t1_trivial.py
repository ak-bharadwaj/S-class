"""
T1 Benchmark Fixture: Measures baseline overhead for trivial single-file edits.
"""
import time
from typing import Dict, Any

class T1TrivialBenchmark:
    def __init__(self, target_content: str):
        self.original_content = target_content

    def apply_edit(self, old_val: str, new_val: str) -> Dict[str, Any]:
        start = time.perf_counter()
        modified = self.original_content.replace(old_val, new_val, 1)
        elapsed_us = (time.perf_counter() - start) * 1_000_000
        
        return {
            "tier": "T1",
            "modified_length": len(modified),
            "elapsed_us": elapsed_us,
            "success": modified != self.original_content
        }
