"""WI-110 Facts Ingest + Identity/Licence/Lock Verifier (S2 Qualification Factory)."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, FrozenSet, List, Mapping, Optional, Sequence, Tuple

REQUIRED_FACTS_FIELDS: FrozenSet[str] = frozenset({
    "source_url",
    "retrieved_at",
    "repo",
    "tag_or_commit",
    "license_spdx",
    "obligations",
    "publisher",
    "advisories",
    "archived",
    "first_release_date",
    "release_date",
    "version",
    "lock_hashes",
})

PERMISSIVE_SPDX_IDS: FrozenSet[str] = frozenset({
    "MIT",
    "MIT-0",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "ISC",
    "Unlicense",
    "CC0-1.0",
    "PSF-2.0",
    "Python-2.0",
    "0BSD",
    "Zlib",
    "BSL-1.0",
    "Artistic-2.0",
    "BlueOak-1.0.0",
})

WEAK_COPYLEFT_SPDX_IDS: FrozenSet[str] = frozenset({
    "MPL-2.0",
    "LGPL-2.0-only",
    "LGPL-2.0-or-later",
    "LGPL-2.1-only",
    "LGPL-2.1-or-later",
    "LGPL-3.0-only",
    "LGPL-3.0-or-later",
    "EPL-1.0",
    "EPL-2.0",
    "CDDL-1.0",
})

STRONG_COPYLEFT_SPDX_IDS: FrozenSet[str] = frozenset({
    "GPL-2.0",
    "GPL-2.0-only",
    "GPL-2.0-or-later",
    "GPL-3.0",
    "GPL-3.0-only",
    "GPL-3.0-or-later",
    "AGPL-3.0",
    "AGPL-3.0-only",
    "AGPL-3.0-or-later",
})

_SHA256_RE = re.compile(r"^(?:sha256:)?([0-9a-fA-F]{64})$")
_COMMIT_SHA40_RE = re.compile(r"(?:^|[@:/\s])([0-9a-fA-F]{40})(?:$|[^0-9a-fA-F])")
_COMMIT_SHA256_RE = re.compile(r"sha256:([0-9a-fA-F]{64})(?:$|[^0-9a-fA-F])")
_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)(?:\.(\d+))?(?:[a-zA-Z0-9._+-]*)?$")


class FactsVerdict(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class FactsVerificationResult:
    tool_id: str
    verdict: FactsVerdict
    reasons: Tuple[str, ...]
    tier_eligibility: str  # "L2" | "L1_ONLY" | "NONE"
    license_class: str  # "PERMISSIVE" | "WEAK_COPYLEFT" | "STRONG_COPYLEFT" | "UNKNOWN"
    obligations: Tuple[str, ...]
    immutable_commit: Optional[str]
    facts_digest: str


def _canonical_digest(obj: Any) -> str:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_iso_date(val: Any) -> Optional[date]:
    if type(val) is not str or not val.strip():
        return None
    s = val.strip()
    m = re.match(r"^(\d{4}-\d{2}-\d{2})(?:[T ].*)?$", s)
    if not m:
        return None
    try:
        return date.fromisoformat(m.group(1))
    except ValueError:
        return None


def _classify_spdx_atom(atom: str) -> str:
    if atom in PERMISSIVE_SPDX_IDS:
        return "PERMISSIVE"
    if atom in WEAK_COPYLEFT_SPDX_IDS:
        return "WEAK_COPYLEFT"
    if atom in STRONG_COPYLEFT_SPDX_IDS:
        return "STRONG_COPYLEFT"
    return "UNKNOWN"


def parse_spdx_expression(expr: Any) -> Tuple[str, Tuple[str, ...]]:
    """Strictly parse an SPDX licence expression into (license_class, tokens)."""
    if type(expr) is not str or not expr.strip():
        return "UNKNOWN", ()
    cleaned = expr.strip()
    # Strip balanced outer parentheses for simple expressions; tokenize operators AND / OR
    normalized = re.sub(r"[()]", " ", cleaned)
    parts = [p for p in normalized.split() if p]
    if not parts:
        return "UNKNOWN", ()

    atoms: List[str] = []
    ops: List[str] = []
    expect_atom = True
    for tok in parts:
        if expect_atom:
            if tok in ("AND", "OR", "WITH"):
                return "UNKNOWN", ()
            atoms.append(tok)
            expect_atom = False
        else:
            if tok not in ("AND", "OR"):
                return "UNKNOWN", ()
            ops.append(tok)
            expect_atom = True

    if expect_atom or not atoms:
        return "UNKNOWN", ()

    atom_classes = [_classify_spdx_atom(a) for a in atoms]
    if any(c == "UNKNOWN" for c in atom_classes):
        return "UNKNOWN", tuple(atoms)

    # Evaluate left-to-right; AND takes strongest copyleft, OR takes most permissive branch
    cur_rank = {"PERMISSIVE": 0, "WEAK_COPYLEFT": 1, "STRONG_COPYLEFT": 2}
    rank_to_cls = {0: "PERMISSIVE", 1: "WEAK_COPYLEFT", 2: "STRONG_COPYLEFT"}
    cur = cur_rank[atom_classes[0]]
    for op, next_cls in zip(ops, atom_classes[1:]):
        nr = cur_rank[next_cls]
        if op == "AND":
            cur = max(cur, nr)
        else:  # OR
            cur = min(cur, nr)
    return rank_to_cls[cur], tuple(atoms)


def _extract_immutable_commit(tag_or_commit: str) -> Optional[str]:
    m40 = _COMMIT_SHA40_RE.search(tag_or_commit)
    if m40:
        cand = m40.group(1).lower()
        if cand != "0" * 40:
            return cand
    m64 = _COMMIT_SHA256_RE.search(tag_or_commit)
    if m64:
        cand64 = m64.group(1).lower()
        if cand64 != "0" * 64:
            return f"sha256:{cand64}"
    return None


def _is_valid_sha256(val: Any) -> bool:
    if type(val) is not str:
        return False
    m = _SHA256_RE.match(val.strip())
    if not m:
        return False
    hex_part = m.group(1).lower()
    return hex_part != "0" * 64


def verify_facts_row(
    row: Mapping[str, Any],
    *,
    as_of: Optional[str] = None,
    freshness_days: int = 30,
    requirements: Optional[Sequence[str]] = None,
) -> FactsVerificationResult:
    """Verify a single OSS tool facts row under WI-110 fail-closed rules."""
    if not isinstance(row, Mapping):
        return FactsVerificationResult(
            tool_id="<invalid>",
            verdict=FactsVerdict.BLOCKED,
            reasons=("INVALID_ROW_TYPE",),
            tier_eligibility="NONE",
            license_class="UNKNOWN",
            obligations=(),
            immutable_commit=None,
            facts_digest=_canonical_digest(repr(row)),
        )

    tool_id_raw = row.get("tool_id") or row.get("repo") or "<unknown>"
    tool_id = tool_id_raw.strip() if type(tool_id_raw) is str and tool_id_raw.strip() else "<unknown>"
    facts_digest = _canonical_digest(dict(row))

    if type(freshness_days) is not int or freshness_days <= 0:
        return FactsVerificationResult(
            tool_id=tool_id,
            verdict=FactsVerdict.BLOCKED,
            reasons=("INVALID_FRESHNESS_WINDOW",),
            tier_eligibility="NONE",
            license_class="UNKNOWN",
            obligations=(),
            immutable_commit=None,
            facts_digest=facts_digest,
        )

    if as_of is None:
        as_of_date = datetime.now(timezone.utc).date()
    else:
        parsed_as_of = _parse_iso_date(as_of)
        if parsed_as_of is None:
            return FactsVerificationResult(
                tool_id=tool_id,
                verdict=FactsVerdict.BLOCKED,
                reasons=("INVALID_AS_OF_DATE",),
                tier_eligibility="NONE",
                license_class="UNKNOWN",
                obligations=(),
                immutable_commit=None,
                facts_digest=facts_digest,
            )
        as_of_date = parsed_as_of

    blocked_reasons: List[str] = []
    unverified_reasons: List[str] = []
    l1_only_reasons: List[str] = []
    obligations_out: List[str] = []

    # 1. Presence check for all required decision-bearing fields
    for field in sorted(REQUIRED_FACTS_FIELDS):
        if field not in row or row[field] is None:
            blocked_reasons.append(f"MISSING_FIELD:{field}")

    # Optional boolean control flags strict type check if supplied
    for opt_bool in ("isolated", "never_authority", "identity_mismatch", "binary_only"):
        if opt_bool in row and row[opt_bool] is not None and type(row[opt_bool]) is not bool:
            blocked_reasons.append(f"INVALID_FIELD_TYPE:{opt_bool}")

    # 2. Strict scalar string checks
    for str_field in ("source_url", "retrieved_at", "repo", "tag_or_commit", "license_spdx", "publisher", "first_release_date", "release_date", "version"):
        if str_field in row and row[str_field] is not None:
            val = row[str_field]
            if type(val) is not str or not val.strip():
                blocked_reasons.append(f"INVALID_OR_EMPTY_FIELD:{str_field}")

    # Validate source_url scheme
    source_url = row.get("source_url")
    if type(source_url) is str and source_url.strip():
        s_url = source_url.strip()
        if not (s_url.startswith("https://") or s_url.startswith("http://")):
            blocked_reasons.append("INVALID_SOURCE_URL")

    # 3. Validate archived exact bool
    archived = row.get("archived")
    if "archived" in row and row["archived"] is not None:
        if type(archived) is not bool:
            blocked_reasons.append("INVALID_FIELD_TYPE:archived")
        elif archived is True:
            blocked_reasons.append("REPO_ARCHIVED")

    # 4. Validate obligations (non-empty str or non-empty list/tuple of non-empty str)
    raw_ob = row.get("obligations")
    if "obligations" in row and raw_ob is not None:
        if type(raw_ob) is str:
            if not raw_ob.strip():
                blocked_reasons.append("INVALID_OR_EMPTY_FIELD:obligations")
            else:
                obligations_out.append(raw_ob.strip())
        elif isinstance(raw_ob, (list, tuple)) and len(raw_ob) > 0:
            if not all(type(item) is str and item.strip() for item in raw_ob):
                blocked_reasons.append("INVALID_FIELD_TYPE:obligations")
            else:
                obligations_out.extend(item.strip() for item in raw_ob)
        else:
            blocked_reasons.append("INVALID_OR_EMPTY_FIELD:obligations")

    # 5. Validate advisories mapping
    raw_adv = row.get("advisories")
    if "advisories" in row and raw_adv is not None:
        if not isinstance(raw_adv, Mapping) or not raw_adv:
            blocked_reasons.append("INVALID_OR_EMPTY_FIELD:advisories")
        else:
            count_keys = [k for k in ("count", "gh", "osv") if k in raw_adv]
            if not count_keys:
                blocked_reasons.append("INVALID_ADVISORIES_SCHEMA")
            else:
                total_adv = 0
                bad_adv = False
                for ck in count_keys:
                    cv = raw_adv[ck]
                    if type(cv) is not int or cv < 0:
                        bad_adv = True
                    else:
                        total_adv += cv
                items_val = raw_adv.get("items", [])
                if not isinstance(items_val, (list, tuple)):
                    bad_adv = True
                if bad_adv:
                    blocked_reasons.append("INVALID_ADVISORIES_SCHEMA")
                elif total_adv > 0 or len(items_val) > 0:
                    unverified_reasons.append("ADVISORIES_PRESENT")

    # 6. Validate lock_hashes mapping (every requirement must have valid sha256)
    raw_locks = row.get("lock_hashes")
    if "lock_hashes" in row and raw_locks is not None:
        if not isinstance(raw_locks, Mapping) or len(raw_locks) == 0:
            blocked_reasons.append("INCOMPLETE_LOCK_HASHES")
        else:
            for req_k, digest_v in raw_locks.items():
                if type(req_k) is not str or not req_k.strip() or not _is_valid_sha256(digest_v):
                    blocked_reasons.append("INCOMPLETE_LOCK_HASHES")
                    break
            if requirements is not None:
                for req_name in requirements:
                    if req_name not in raw_locks or not _is_valid_sha256(raw_locks.get(req_name)):
                        blocked_reasons.append("INCOMPLETE_LOCK_HASHES")
                        break

    # 7. Immutable commit pin check
    immutable_commit: Optional[str] = None
    tag_or_commit = row.get("tag_or_commit")
    if type(tag_or_commit) is str and tag_or_commit.strip():
        immutable_commit = _extract_immutable_commit(tag_or_commit.strip())
        if immutable_commit is None:
            unverified_reasons.append("UNPINNED_COMMIT")

    # 8. Strict SPDX licence check
    license_class = "UNKNOWN"
    lic_spdx = row.get("license_spdx")
    if type(lic_spdx) is str and lic_spdx.strip():
        license_class, spdx_atoms = parse_spdx_expression(lic_spdx)
        if license_class == "UNKNOWN":
            blocked_reasons.append("UNKNOWN_SPDX")
        elif license_class == "STRONG_COPYLEFT":
            isolated_flag = row.get("isolated")
            if isolated_flag is True:
                unverified_reasons.append("STRONG_COPYLEFT_ISOLATED")
                obligations_out.append(f"Isolated execution required for {', '.join(spdx_atoms)}")
            else:
                blocked_reasons.append("STRONG_COPYLEFT_UNISOLATED")
        elif license_class == "WEAK_COPYLEFT":
            unverified_reasons.append("WEAK_COPYLEFT_OBLIGATIONS")
            obligations_out.append(f"Weak-copyleft compliance review required for {', '.join(spdx_atoms)}")

    # 9. Date checks: retrieved_at freshness, first_release_date (>=2y), release_date (<=12m)
    retrieved_dt = _parse_iso_date(row.get("retrieved_at"))
    if "retrieved_at" in row and type(row.get("retrieved_at")) is str and row["retrieved_at"].strip():
        if retrieved_dt is None:
            blocked_reasons.append("INVALID_DATE:retrieved_at")
        else:
            age_days = (as_of_date - retrieved_dt).days
            if age_days < 0:
                blocked_reasons.append("FUTURE_RETRIEVED_AT")
            elif age_days > freshness_days:
                unverified_reasons.append("FACTS_STALE")

    first_rel_dt = _parse_iso_date(row.get("first_release_date"))
    if "first_release_date" in row and type(row.get("first_release_date")) is str and row["first_release_date"].strip():
        if first_rel_dt is None:
            blocked_reasons.append("INVALID_DATE:first_release_date")
        else:
            age_since_first = (as_of_date - first_rel_dt).days
            if age_since_first < 0:
                blocked_reasons.append("INVALID_DATE:first_release_date")
            elif age_since_first < 730:
                l1_only_reasons.append("AGE_BELOW_2_YEARS")

    latest_rel_dt = _parse_iso_date(row.get("release_date"))
    if "release_date" in row and type(row.get("release_date")) is str and row["release_date"].strip():
        if latest_rel_dt is None:
            blocked_reasons.append("INVALID_DATE:release_date")
        else:
            days_since_rel = (as_of_date - latest_rel_dt).days
            if days_since_rel < 0:
                blocked_reasons.append("INVALID_DATE:release_date")
            elif days_since_rel > 365:
                l1_only_reasons.append("NO_RECENT_RELEASE_12M")

    # 10. Version >= 1.0 check
    ver = row.get("version")
    if type(ver) is str and ver.strip():
        m_ver = _VERSION_RE.match(ver.strip())
        if not m_ver:
            blocked_reasons.append("INVALID_VERSION")
        else:
            major = int(m_ver.group(1))
            if major < 1:
                l1_only_reasons.append("VERSION_BELOW_1_0")

    # 11. Identity mismatch / never-authority overrides
    if row.get("identity_mismatch") is True:
        blocked_reasons.append("IDENTITY_MISMATCH")
    if row.get("never_authority") is True:
        l1_only_reasons.append("NEVER_AUTHORITY_TOOL")

    # Deduplicate reasons while preserving order
    all_reasons = tuple(dict.fromkeys(blocked_reasons + unverified_reasons + l1_only_reasons))

    if blocked_reasons:
        return FactsVerificationResult(
            tool_id=tool_id,
            verdict=FactsVerdict.BLOCKED,
            reasons=all_reasons,
            tier_eligibility="NONE",
            license_class=license_class,
            obligations=tuple(dict.fromkeys(obligations_out)),
            immutable_commit=immutable_commit,
            facts_digest=facts_digest,
        )

    if unverified_reasons or l1_only_reasons:
        tier = "L1_ONLY" if l1_only_reasons else "L2"
        return FactsVerificationResult(
            tool_id=tool_id,
            verdict=FactsVerdict.UNVERIFIED,
            reasons=all_reasons,
            tier_eligibility=tier,
            license_class=license_class,
            obligations=tuple(dict.fromkeys(obligations_out)),
            immutable_commit=immutable_commit,
            facts_digest=facts_digest,
        )

    return FactsVerificationResult(
        tool_id=tool_id,
        verdict=FactsVerdict.VERIFIED,
        reasons=(),
        tier_eligibility="L2",
        license_class=license_class,
        obligations=tuple(dict.fromkeys(obligations_out)),
        immutable_commit=immutable_commit,
        facts_digest=facts_digest,
    )


def ingest_facts_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    as_of: Optional[str] = None,
    freshness_days: int = 30,
) -> List[FactsVerificationResult]:
    """Ingest and verify a non-empty sequence of facts rows."""
    if not isinstance(rows, (list, tuple)) or len(rows) == 0:
        raise ValueError("rows must be a non-empty list or tuple of facts row mappings")
    return [
        verify_facts_row(row, as_of=as_of, freshness_days=freshness_days)
        for row in rows
    ]
