"""WI-113 Persisted, Digest-Checked Qualified Adapter Registry (S2 -> S1)."""
from __future__ import annotations

import contextlib
import contextvars
import csv
import json
import pathlib
import re
from typing import Any, Dict, Iterator, Mapping, Optional, Tuple

from sclass.product.adapter_qualification_contract import (
    DECLARED_ADAPTER_CATEGORIES,
    EXTENSION_CATEGORIES,
)
from sclass.qualification.f10_validation import (
    compute_sha256_json,
    verify_non_agent_approval_set,
)
from sclass.qualification.record_generator import verify_qualification_record

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = REPO_ROOT / "product/qualification/qualified_adapters.json"
_V3_CSV_PATH = REPO_ROOT / "product/MUST-ALLOCATION-V3.csv"

_SHA256_HEX_RE = re.compile(r"^[0-9a-fA-F]{64}$")

# ContextVar used ONLY by explicitly labelled test fixtures (never shipped active by default)
_TEST_ONLY_REGISTRY_VAR: contextvars.ContextVar[Optional[Dict[str, Dict[str, Any]]]] = (
    contextvars.ContextVar("_TEST_ONLY_REGISTRY_VAR", default=None)
)

_MUST_NEEDS_ENGINE_RAW_CACHE: Optional[Dict[str, str]] = None


def _get_must_engine_raw_map() -> Dict[str, str]:
    global _MUST_NEEDS_ENGINE_RAW_CACHE
    if _MUST_NEEDS_ENGINE_RAW_CACHE is None:
        mapping: Dict[str, str] = {}
        if _V3_CSV_PATH.is_file():
            with open(_V3_CSV_PATH, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    mapping[row["must_id"]] = row.get("needs_engine", "")
        _MUST_NEEDS_ENGINE_RAW_CACHE = mapping
    return _MUST_NEEDS_ENGINE_RAW_CACHE


def _extract_f10_category_for_must(must_id: str) -> Optional[str]:
    raw = _get_must_engine_raw_map().get(must_id, "")
    for cat in DECLARED_ADAPTER_CATEGORIES:
        if cat in raw:
            return cat
    return None


def _is_valid_digest(val: Any) -> bool:
    if type(val) is not str:
        return False
    cleaned = val.strip().lower().removeprefix("sha256:")
    return bool(_SHA256_HEX_RE.match(cleaned)) and cleaned != "0" * 64


def write_empty_registry(store_path: pathlib.Path | str = DEFAULT_REGISTRY_PATH) -> str:
    """Write an empty, digest-checked canonical registry store (LF-only)."""
    p = pathlib.Path(store_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    body = {"schema_version": "1.0", "adapters": {}}
    digest = compute_sha256_json(body)
    full = {"schema_version": "1.0", "adapters": {}, "registry_digest": digest}
    p.write_text(json.dumps(full, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    return digest


def load_qualified_adapters(
    store_path: pathlib.Path | str = DEFAULT_REGISTRY_PATH,
) -> Dict[str, Dict[str, Any]]:
    """Read and digest-verify qualified adapters. Absent or tampered store => empty dict (0 qualified)."""
    test_override = _TEST_ONLY_REGISTRY_VAR.get()
    if test_override is not None:
        return {k: dict(v) for k, v in test_override.items()}

    p = pathlib.Path(store_path)
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

    if not isinstance(data, dict):
        return {}
    reg_digest = data.get("registry_digest")
    adapters_raw = data.get("adapters")
    schema_ver = data.get("schema_version")
    if (
        schema_ver != "1.0"
        or not isinstance(adapters_raw, dict)
        or not _is_valid_digest(reg_digest)
    ):
        return {}

    expected_digest = compute_sha256_json({"schema_version": schema_ver, "adapters": adapters_raw})
    if str(reg_digest).strip().lower() != expected_digest:
        return {}

    valid: Dict[str, Dict[str, Any]] = {}
    for aid, entry in adapters_raw.items():
        if not isinstance(entry, dict):
            continue
        cat = entry.get("category")
        if cat in EXTENSION_CATEGORIES or cat not in DECLARED_ADAPTER_CATEGORIES:
            continue
        if entry.get("status") != "QUALIFIED":
            continue
        if not _is_valid_digest(entry.get("adapter_digest")) or not _is_valid_digest(entry.get("record_digest")):
            continue
        valid[str(aid)] = dict(entry)
    return valid


def register_qualified_adapter(
    *,
    store_path: pathlib.Path | str = DEFAULT_REGISTRY_PATH,
    adapter_id: str,
    adapter_version: str,
    adapter_digest: str,
    category: str,
    qualification_record_ref: str,
    qualification_record: Mapping[str, Any],
    approval_set: Any,
    approval_context: Mapping[str, Any],
) -> Dict[str, Any]:
    """Write a qualified adapter entry ONLY via verified non-agent ApprovalSet + QUALIFIED 16-field record."""
    if type(adapter_id) is not str or not adapter_id.strip():
        raise ValueError("adapter_id must be a non-empty string")
    if type(adapter_version) is not str or not adapter_version.strip():
        raise ValueError("adapter_version must be a non-empty string")
    if not _is_valid_digest(adapter_digest):
        raise ValueError("adapter_digest must be a valid non-zero sha256")
    if category in EXTENSION_CATEGORIES or category not in DECLARED_ADAPTER_CATEGORIES:
        raise ValueError(f"Category '{category}' is not a normative F10 category")

    ok_auth, auth_msg = verify_non_agent_approval_set(approval_set, approval_context)
    if not ok_auth:
        raise ValueError(f"Unauthorized adapter registration: {auth_msg}")

    ok_rec, rec_msg = verify_qualification_record(qualification_record)
    if not ok_rec:
        raise ValueError(f"Invalid qualification record: {rec_msg}")
    if qualification_record.get("qualification_status") != "QUALIFIED":
        raise ValueError(
            f"Cannot register adapter with qualification_status={qualification_record.get('qualification_status')!r}"
        )

    existing = load_qualified_adapters(store_path)
    existing[adapter_id] = {
        "adapter_id": adapter_id,
        "adapter_version": adapter_version,
        "adapter_digest": adapter_digest,
        "category": category,
        "qualification_record_ref": qualification_record_ref,
        "record_digest": str(qualification_record["record_digest"]),
        "approval_set_digest": compute_sha256_json(approval_set),
        "status": "QUALIFIED",
    }

    p = pathlib.Path(store_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    body = {"schema_version": "1.0", "adapters": existing}
    reg_digest = compute_sha256_json(body)
    full = {"schema_version": "1.0", "adapters": existing, "registry_digest": reg_digest}
    p.write_text(json.dumps(full, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    return full


def is_adapter_qualified(
    adapter_id: str,
    *,
    adapter_digest: Optional[str] = None,
    category: Optional[str] = None,
    store_path: pathlib.Path | str = DEFAULT_REGISTRY_PATH,
) -> bool:
    """Return True iff adapter_id is registered and QUALIFIED with matching digest & category."""
    if type(adapter_id) is not str or not adapter_id.strip():
        return False
    adapters = load_qualified_adapters(store_path)
    entry = adapters.get(adapter_id)
    if not entry:
        return False
    if entry.get("status") != "QUALIFIED":
        return False
    if adapter_digest is not None and entry.get("adapter_digest") != adapter_digest:
        return False
    if category is not None and entry.get("category") != category:
        return False
    return True


def has_qualified_adapter_for_must(
    must_id: str,
    *,
    adapter_ref: Optional[Mapping[str, Any]] = None,
    store_path: pathlib.Path | str = DEFAULT_REGISTRY_PATH,
) -> Tuple[bool, str]:
    """Lookup engine qualification for a needs_engine MUST from the digest-verified store."""
    adapters = load_qualified_adapters(store_path)
    if not adapters:
        return False, "ENGINE_NOT_QUALIFIED"

    req_category = _extract_f10_category_for_must(must_id)

    if adapter_ref is not None:
        if not isinstance(adapter_ref, Mapping):
            return False, "ENGINE_NOT_QUALIFIED"
        aid = adapter_ref.get("adapter_id")
        adig = adapter_ref.get("adapter_digest")
        acat = adapter_ref.get("category")
        if type(aid) is not str or type(adig) is not str or type(acat) is not str:
            return False, "ENGINE_NOT_QUALIFIED"
        if acat in EXTENSION_CATEGORIES or acat not in DECLARED_ADAPTER_CATEGORIES:
            return False, "ENGINE_NOT_QUALIFIED"
        if req_category is not None and acat != req_category:
            return False, "ENGINE_NOT_QUALIFIED"
        if is_adapter_qualified(aid, adapter_digest=adig, category=acat, store_path=store_path):
            return True, "QUALIFIED"
        return False, "ENGINE_NOT_QUALIFIED"

    # Match against qualified adapters registered for the required category
    for entry in adapters.values():
        if entry.get("test_only") is True and entry.get("label") == "TEST_ONLY_REGISTRY_FIXTURE":
            if req_category is None or entry.get("category") == req_category:
                return True, "TEST_ONLY_QUALIFIED"
        elif req_category is not None and entry.get("category") == req_category:
            return True, "QUALIFIED"

    return False, "ENGINE_NOT_QUALIFIED"


def _build_test_only_fixture_adapters() -> Dict[str, Dict[str, Any]]:
    """Build labelled TEST-ONLY registry fixture entries (NEVER shipped as production default)."""
    entries: Dict[str, Dict[str, Any]] = {}
    for idx, cat in enumerate(sorted(DECLARED_ADAPTER_CATEGORIES), 1):
        aid = f"test-only-adapter-{idx}"
        dig = f"{idx:064x}"
        entries[aid] = {
            "adapter_id": aid,
            "adapter_version": "0.0.0-test",
            "adapter_digest": dig,
            "category": cat,
            "status": "QUALIFIED",
            "record_digest": f"{idx + 100:064x}",
            "test_only": True,
            "label": "TEST_ONLY_REGISTRY_FIXTURE",
        }
    for legacy_name in ("pytest-sclass", "junit-sclass", "cargo-test-sclass", "go-test-sclass"):
        entries[legacy_name] = {
            "adapter_id": legacy_name,
            "adapter_version": "0.0.0-test",
            "adapter_digest": "a" * 64,
            "category": "contract testers",
            "status": "QUALIFIED",
            "record_digest": "b" * 64,
            "test_only": True,
            "label": "TEST_ONLY_REGISTRY_FIXTURE",
        }
    return entries


@contextlib.contextmanager
def test_only_qualified_registry(
    extra_adapters: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> Iterator[Dict[str, Dict[str, Any]]]:
    """Explicitly labelled TEST-ONLY registry fixture context manager for tests."""
    adapters = _build_test_only_fixture_adapters()
    if extra_adapters:
        for k, v in extra_adapters.items():
            d = dict(v)
            d.setdefault("test_only", True)
            d.setdefault("label", "TEST_ONLY_REGISTRY_FIXTURE")
            adapters[str(k)] = d
    token = _TEST_ONLY_REGISTRY_VAR.set(adapters)
    try:
        yield adapters
    finally:
        _TEST_ONLY_REGISTRY_VAR.reset(token)


use_test_only_qualified_registry = test_only_qualified_registry
