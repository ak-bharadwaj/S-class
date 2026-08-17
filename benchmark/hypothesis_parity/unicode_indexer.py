"""
S-Class EOS V11.2 - Exact Unicode Category Interval Indexer.
Indexes the Unicode character database (UCD) bundled with the executing Python runtime.
Supported Python Versions: 3.10-3.13.

Complexity Analysis:
- Cold Index Construction: One-time linear pass over 0..0x10FFFF (O(N), N = 1,114,112 codepoints, ~0.5s cold-start).
- Query & Intersection: O(K), where K is the number of category intervals.
- Uniform Codepoint Sampling: O(M), where M is the number of resulting disjoint intervals (weighted prefix scan).
"""

import sys
import time
import hashlib
import json
import bisect
import random
import unicodedata
from typing import Dict, List, Tuple, Optional, Any

# Global state for lazy initialization and provenance
_UNICODE_CATEGORY_INTERVALS: Optional[Dict[str, List[Tuple[int, int]]]] = None
_UNICODE_PROVENANCE_METADATA: Optional[Dict[str, Any]] = None


def _init_unicode_intervals() -> Dict[str, List[Tuple[int, int]]]:
    """
    Builds exact compact interval sets for all Unicode categories across 0..0x10FFFF
    from the executing Python runtime's bundled Unicode Character Database (unicodedata.unidata_version).
    """
    global _UNICODE_CATEGORY_INTERVALS, _UNICODE_PROVENANCE_METADATA
    if _UNICODE_CATEGORY_INTERVALS is not None:
        return _UNICODE_CATEGORY_INTERVALS

    t0 = time.perf_counter_ns()
    intervals: Dict[str, List[Tuple[int, int]]] = {}
    for cp in range(0, 0x110000):
        try:
            char = chr(cp)
            cat = unicodedata.category(char)
            if cat not in intervals:
                intervals[cat] = []
            if intervals[cat] and intervals[cat][-1][1] == cp - 1:
                intervals[cat][-1] = (intervals[cat][-1][0], cp)
            else:
                intervals[cat].append((cp, cp))
        except Exception:
            continue

    elapsed_ms = (time.perf_counter_ns() - t0) / 1_000_000.0

    # Compute deterministic index checksum for provenance audit
    canonical_repr = json.dumps({k: intervals[k] for k in sorted(intervals.keys())}).encode("utf-8")
    index_checksum = hashlib.sha256(canonical_repr).hexdigest()

    total_intervals_count = sum(len(iv_list) for iv_list in intervals.values())

    _UNICODE_CATEGORY_INTERVALS = intervals
    _UNICODE_PROVENANCE_METADATA = {
        "python_runtime_version": sys.version,
        "python_version_info": list(sys.version_info[:3]),
        "unicode_database_version": unicodedata.unidata_version,
        "index_sha256_checksum": index_checksum,
        "cold_init_duration_ms": round(elapsed_ms, 3),
        "total_categories_indexed": len(intervals),
        "total_disjoint_intervals": total_intervals_count
    }
    return _UNICODE_CATEGORY_INTERVALS


def get_unicode_provenance() -> Dict[str, Any]:
    """Returns the immutable provenance and audit metadata for the indexed Unicode database."""
    _init_unicode_intervals()
    assert _UNICODE_PROVENANCE_METADATA is not None
    return dict(_UNICODE_PROVENANCE_METADATA)


def get_category_intervals(category: str) -> List[Tuple[int, int]]:
    """Returns the sorted list of disjoint codepoint intervals (start_cp, end_cp) for a category."""
    table = _init_unicode_intervals()
    return table.get(category, [])


def intersect_intervals(intervals: List[Tuple[int, int]], min_cp: int, max_cp: int) -> List[Tuple[int, int]]:
    """Intersects a sorted list of disjoint intervals with [min_cp, max_cp]. Complexity: O(K)."""
    if min_cp > max_cp or not intervals:
        return []

    result: List[Tuple[int, int]] = []
    for start, end in intervals:
        if end < min_cp:
            continue
        if start > max_cp:
            break
        i_start = max(start, min_cp)
        i_end = min(end, max_cp)
        if i_start <= i_end:
            result.append((i_start, i_end))
    return result


def find_valid_codepoint_intervals(
    whitelist: Optional[List[str]],
    blacklist: Optional[List[str]],
    min_cp: int,
    max_cp: int
) -> List[Tuple[int, int]]:
    """
    Computes exact codepoint intervals satisfying whitelist categories, blacklist categories,
    and [min_cp, max_cp] bounds with mathematical precision over the executing runtime's UCD.
    """
    if min_cp > max_cp:
        return []

    table = _init_unicode_intervals()

    # 1. Compute whitelist union (or all categories if whitelist is None)
    if whitelist:
        all_whitelisted: List[Tuple[int, int]] = []
        for cat in whitelist:
            if cat in table:
                all_whitelisted.extend(intersect_intervals(table[cat], min_cp, max_cp))
        all_whitelisted.sort()
        # Merge overlapping intervals
        merged: List[Tuple[int, int]] = []
        for start, end in all_whitelisted:
            if merged and merged[-1][1] >= start - 1:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        base_intervals = merged
    else:
        base_intervals = [(min_cp, max_cp)]

    if not base_intervals:
        return []

    # 2. Subtract blacklist categories if present
    if not blacklist:
        return base_intervals

    blacklisted_raw: List[Tuple[int, int]] = []
    for cat in blacklist:
        if cat in table:
            blacklisted_raw.extend(intersect_intervals(table[cat], min_cp, max_cp))
    blacklisted_raw.sort()

    if not blacklisted_raw:
        return base_intervals

    # Interval subtraction
    final_intervals: List[Tuple[int, int]] = []
    for b_start, b_end in base_intervals:
        curr_start = b_start
        for blk_start, blk_end in blacklisted_raw:
            if blk_end < curr_start:
                continue
            if blk_start > b_end:
                break
            if blk_start > curr_start:
                final_intervals.append((curr_start, min(b_end, blk_start - 1)))
            curr_start = max(curr_start, blk_end + 1)
            if curr_start > b_end:
                break
        if curr_start <= b_end:
            final_intervals.append((curr_start, b_end))

    return [iv for iv in final_intervals if iv[0] <= iv[1]]


def sample_codepoint(
    whitelist: Optional[List[str]],
    blacklist: Optional[List[str]],
    min_cp: int,
    max_cp: int,
    rng: random.Random
) -> Optional[int]:
    """
    Samples a single valid codepoint uniformly across all exact satisfying intervals.
    Sampling complexity: O(M) where M is the count of resulting disjoint intervals (weighted prefix scan).
    Returns None if no codepoint exists (satisfiability proven impossible).
    """
    valid_intervals = find_valid_codepoint_intervals(whitelist, blacklist, min_cp, max_cp)
    if not valid_intervals:
        return None

    total_weights = [end - start + 1 for start, end in valid_intervals]
    total_count = sum(total_weights)
    if total_count <= 0:
        return None

    choice = rng.randint(0, total_count - 1)
    cum = 0
    for idx, (start, end) in enumerate(valid_intervals):
        w = total_weights[idx]
        if cum <= choice < cum + w:
            offset = choice - cum
            return start + offset
        cum += w

    return valid_intervals[0][0]
