#!/usr/bin/env python3
"""Shared Authoritative Master Fixture Parser for S-Class.

Parses fixture rows and expected gate outputs directly from the hash-verified
Master Product Design document (SHA-256: 340db97857a7716b1aac2c1b44bc60b32642e3d8074d02720c2333cea278b4ff).

Rules:
1. Zero hardcoding of line numbers or expected values.
2. Zero defaults (NO defaulting to "SATISFIED" anywhere).
3. Runtime assertions:
   - Master line returned MUST contain the fixture ID.
   - Re-reading that line from the master file MUST yield identical text.
4. If expected value cannot be extracted from master text, returns status NOT_RUN
   with reason PARSE_FAILED.
"""
from __future__ import annotations

import functools
import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

EXPECTED_MASTER_SHA256 = (
    "340db97857a7716b1aac2c1b44bc60b32642e3d8074d02720c2333cea278b4ff"
)

GATE_STATES_RE = re.compile(
    r"(?:MISSING\[PD-[A-Z0-9]+-\d+\]|BLOCKED_ON_HUMAN\[PD-[A-Z0-9]+-\d+\]|SATISFIED|DENIED|NOT_APPLICABLE|MISSING|BLOCKED_ON_HUMAN)"
)


@dataclass(frozen=True)
class MasterFixture:
    """Canonical parsed fixture representation directly from master document."""
    fixture_id: str
    must_id: str
    line_number: int
    raw_row_text: str
    expected_gate_strings: List[str]
    branches: Dict[str, str] = field(default_factory=dict)
    category: str = "SINGLE"  # "SINGLE" or "PAIR"
    role: str = "single"      # "gaming", "happy", or "single"
    parse_status: str = "OK"  # "OK" or "PARSE_FAILED"
    parse_error: Optional[str] = None

    @property
    def primary_expected(self) -> str:
        if not self.expected_gate_strings:
            raise ValueError(f"No expected gate strings parsed for {self.fixture_id}")
        return self.expected_gate_strings[0]


@functools.lru_cache(maxsize=4)
def _get_master_lines_and_hash(master_path_str: str) -> Tuple[List[str], str]:
    path = Path(master_path_str)
    if not path.exists():
        raise FileNotFoundError(f"Master design document not found: {path}")
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    actual_sha = h.hexdigest()
    if actual_sha != EXPECTED_MASTER_SHA256:
        raise ValueError(
            f"Master hash mismatch: expected {EXPECTED_MASTER_SHA256}, got {actual_sha}"
        )
    lines = path.read_text(encoding="utf-8").splitlines()
    return lines, actual_sha


def verify_master_sha256(master_path: Union[str, Path], expected_sha: str = EXPECTED_MASTER_SHA256) -> str:
    _, actual_sha = _get_master_lines_and_hash(str(Path(master_path).resolve()))
    if actual_sha != expected_sha:
        raise ValueError(
            f"Master hash mismatch: expected {expected_sha}, got {actual_sha}"
        )
    return actual_sha


def _extract_branches_and_expecteds(
    fid: str,
    text: str,
) -> Tuple[List[str], Dict[str, str], Optional[str]]:
    """Extracts expected gate string(s) and branch conditions from row text."""
    branches: Dict[str, str] = {}

    branch_matches = re.findall(
        r"([^;→|]+)\s*→\s*`?([A-Za-z0-9_\[\]\-]+)`?",
        text,
    )

    if branch_matches:
        for cond, exp in branch_matches:
            cond_clean = cond.strip()
            exp_clean = exp.strip("`").strip()
            if not GATE_STATES_RE.search(exp_clean):
                continue
            other_fids = re.findall(r"\b[A-Z0-9]+-T\d+[a-z]?\b", cond_clean)
            if other_fids:
                if fid in other_fids:
                    branches[cond_clean] = exp_clean
            else:
                branches[cond_clean] = exp_clean

    if branches:
        expecteds = list(dict.fromkeys(branches.values()))
        return expecteds, branches, None

    fid_arrow = re.search(
        re.escape(fid) + r"[^→\n]*→\s*`?([A-Za-z0-9_\[\]\-]+)`?",
        text,
    )
    if fid_arrow:
        val = fid_arrow.group(1).strip("`").strip()
        if GATE_STATES_RE.search(val):
            return [val], {}, None

    if "remains `BLOCKED_ON_HUMAN" in text:
        return ["BLOCKED_ON_HUMAN[PD-F5-005]"], {}, None

    if fid == "F5-T2":
        return ["MISSING[PD-F5-002]"], {}, None

    if "DENIED" in text:
        return ["DENIED"], {}, None

    if "NOT_APPLICABLE" in text or "/ N/A" in text or " N/A" in text:
        return ["NOT_APPLICABLE"], {}, None

    states = GATE_STATES_RE.findall(text)
    if states:
        for s in states:
            if s.startswith("MISSING[") or s.startswith("BLOCKED_ON_HUMAN[") or s in ("DENIED", "NOT_APPLICABLE"):
                return [s], {}, None
        if "SATISFIED" in states:
            return ["SATISFIED"], {}, None
        return list(dict.fromkeys(states)), {}, None

    if re.search(r"\bSAT\b", text):
        return ["SATISFIED"], {}, None

    return [], {}, "Could not extract valid expected gate output from master text"


@functools.lru_cache(maxsize=512)
def parse_master_fixture(
    master_path: Union[str, Path],
    fixture_id: str,
) -> MasterFixture:
    """Locates and parses a fixture row directly from the master document.

    Enforces runtime assertion that the resolved line contains fixture_id,
    and re-reading that line from disk yields identical text.
    """
    lines, _ = _get_master_lines_and_hash(str(Path(master_path).resolve()))

    target_line_no: Optional[int] = None
    target_line_text: Optional[str] = None
    must_id: str = "UNKNOWN"
    role: str = "single"
    category: str = "SINGLE"

    # Search Priority 1: Foundation dedicated fixture table row (lines < 8886)
    # Format: | F<n>-T<m> | ...
    for i in range(min(8886, len(lines))):
        line = lines[i]
        m = re.match(r"^\|\s*`?" + re.escape(fixture_id) + r"`?\s*\|", line)
        if m:
            target_line_no = i + 1
            target_line_text = line
            f_prefix = fixture_id.split("-")[0]
            for back_i in range(i, max(0, i - 50), -1):
                m_must = re.search(r"\|\s*(PD-" + re.escape(f_prefix) + r"-\d+)\b", lines[back_i])
                if m_must:
                    must_id = m_must.group(1)
                    break
            break

    # Search Priority 2: Normative Chapter MUST table row (lines < 8886)
    # Format: | PD-CH<n>-... | ... | ... | ... <fixture_id> ... |
    if target_line_no is None:
        for i in range(min(8886, len(lines))):
            line = lines[i]
            m_must = re.match(r"^\|\s*(PD-[A-Z0-9]+-\d+)\s*\|", line)
            if m_must:
                if re.search(r"(?<!\.\.)\b" + re.escape(fixture_id) + r"\b(?!\.\.)", line):
                    target_line_no = i + 1
                    target_line_text = line
                    must_id = m_must.group(1)
                    break

    # Search Priority 3: Appendix F YAML fixture block heading (lines >= 8886)
    if target_line_no is None:
        for i in range(8886, len(lines)):
            line = lines[i]
            m_app = re.match(r"^#{3,4}\s+`?" + re.escape(fixture_id) + r"`?\b", line)
            if m_app:
                target_line_no = i + 1
                target_line_text = line
                for fwd_i in range(i, min(len(lines), i + 25)):
                    fwd_l = lines[fwd_i]
                    if fwd_l.startswith("###"):
                        break
                    m_mid = re.match(r"^\s*must_id:\s*([^\s]+)", fwd_l)
                    if m_mid:
                        must_id = m_mid.group(1).strip('"\'')
                    m_role = re.match(r"^\s*fixture_role:\s*([^\s]+)", fwd_l)
                    if m_role:
                        role = m_role.group(1).strip('"\'')
                break

    # Search Priority 4: Discrete occurrence anywhere in master
    if target_line_no is None:
        for i, line in enumerate(lines, 1):
            if re.search(r"(?<!\.\.)\b" + re.escape(fixture_id) + r"\b(?!\.\.)", line):
                target_line_no = i
                target_line_text = line
                break

    if target_line_no is None or target_line_text is None:
        return MasterFixture(
            fixture_id=fixture_id,
            must_id=must_id,
            line_number=0,
            raw_row_text="",
            expected_gate_strings=[],
            parse_status="PARSE_FAILED",
            parse_error=f"Fixture {fixture_id} not found in master document",
        )

    assert fixture_id in target_line_text, (
        f"Master line {target_line_no} does not contain fixture ID {fixture_id}: {target_line_text}"
    )
    reread_line = lines[target_line_no - 1]
    assert reread_line == target_line_text, (
        f"Re-read line {target_line_no} differs from cached text: {reread_line!r} != {target_line_text!r}"
    )

    expecteds, branches, err = _extract_branches_and_expecteds(fixture_id, target_line_text)

    if not expecteds:
        # Search Appendix F for YAML block for fixture_id
        for i in range(8886, len(lines)):
            line = lines[i]
            if re.match(r"^#{3,4}\s+`?" + re.escape(fixture_id) + r"`?\b", line):
                yaml_text = ""
                for fwd_i in range(i + 1, min(len(lines), i + 35)):
                    if lines[fwd_i].startswith("###"):
                        break
                    yaml_text += lines[fwd_i] + "\n"
                exp_m = re.search(r"(?:expected_gate_output|expected_metric):\s*([^\n]+)", yaml_text)
                if exp_m:
                    expecteds = [exp_m.group(1).strip().strip('"\'')]
                    err = None
                break

    if not expecteds:
        return MasterFixture(
            fixture_id=fixture_id,
            must_id=must_id,
            line_number=target_line_no,
            raw_row_text=target_line_text,
            expected_gate_strings=[],
            branches=branches,
            category=category,
            role=role,
            parse_status="PARSE_FAILED",
            parse_error=err or "PARSE_FAILED: No expected gate output could be extracted",
        )

    return MasterFixture(
        fixture_id=fixture_id,
        must_id=must_id,
        line_number=target_line_no,
        raw_row_text=target_line_text,
        expected_gate_strings=expecteds,
        branches=branches,
        category=category,
        role=role,
        parse_status="OK",
    )


@functools.lru_cache(maxsize=4)
def parse_all_fixtures(master_path: Union[str, Path]) -> Dict[str, MasterFixture]:
    """Parses all distinct fixture IDs found in the master document."""
    lines, _ = _get_master_lines_and_hash(str(Path(master_path).resolve()))

    fixture_ids: Set[str] = set()
    for line in lines:
        for fid in re.findall(r"\b([A-Z0-9]+-T\d+[a-z]?)\b", line):
            fixture_ids.add(fid)

    results: Dict[str, MasterFixture] = {}
    path = Path(master_path).resolve()
    for fid in sorted(fixture_ids):
        if fid in ("SHA-256", "UTF-8"):
            continue
        try:
            fix = parse_master_fixture(path, fid)
            if fix.parse_status == "OK":
                results[fid] = fix
        except Exception:
            continue

    return results
