"""
S-Class Context: Token Compression & Minimal Handoff Packaging (RC.5).
Generates ultra-dense, token-budgeted handoff packages carrying verified project truth
with 0% chat transcript leakage.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, List, Dict


@dataclass
class CompressedHandoff:
    text: str
    estimated_tokens: int
    compression_tier: int  # 0, 1, 2, 3


class TokenCompressor:
    """Progressive token compression engine for inter-agent handoff packages."""

    def __init__(self, chars_per_token: int = 4):
        self.chars_per_token = chars_per_token

    def _estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // self.chars_per_token)

    def compress(self, truth: Any, budget_tokens: int = 500) -> CompressedHandoff:
        records = getattr(truth, "records", {})
        verified_items = [
            (cid, rec) for cid, rec in records.items()
            if getattr(rec, "state", None) == "VERIFIED" or str(getattr(rec, "state", "")) == "TruthState.VERIFIED"
        ]

        # Tier 0: Full detailed verified claims with statement & file dependencies
        lines_t0 = ["# S-Class Verified Truth Package (Tier 0)"]
        for cid, r in verified_items:
            files = getattr(r.dependencies, "files", ())
            lines_t0.append(f"- [{cid}] {r.statement} (files: {list(files)})")
        text_t0 = "\n".join(lines_t0)
        tokens_t0 = self._estimate_tokens(text_t0)
        if tokens_t0 <= budget_tokens:
            return CompressedHandoff(text=text_t0, estimated_tokens=tokens_t0, compression_tier=0)

        # Tier 1: Compact list of IDs and primary target files
        lines_t1 = ["# S-Class Verified Truth (Tier 1)"]
        for cid, r in verified_items:
            files = list(getattr(r.dependencies, "files", ()))
            f_summary = files[0] if files else "all"
            lines_t1.append(f"- {cid}: {f_summary}")
        text_t1 = "\n".join(lines_t1)
        tokens_t1 = self._estimate_tokens(text_t1)
        if tokens_t1 <= budget_tokens:
            return CompressedHandoff(text=text_t1, estimated_tokens=tokens_t1, compression_tier=1)

        # Tier 2: Categorized summary counts and top claims
        top_ids = [cid for cid, _ in verified_items[:5]]
        lines_t2 = [
            "# S-Class Verified Truth (Tier 2)",
            f"Verified Claims: {len(verified_items)}",
            f"Active IDs: {', '.join(top_ids)}",
        ]
        text_t2 = "\n".join(lines_t2)
        tokens_t2 = self._estimate_tokens(text_t2)
        if tokens_t2 <= budget_tokens:
            return CompressedHandoff(text=text_t2, estimated_tokens=tokens_t2, compression_tier=2)

        # Tier 3: Ultra-compact digest
        text_t3 = f"# Truth Digest (Tier 3): {len(verified_items)} verified claims."
        tokens_t3 = self._estimate_tokens(text_t3)
        return CompressedHandoff(text=text_t3, estimated_tokens=tokens_t3, compression_tier=3)
