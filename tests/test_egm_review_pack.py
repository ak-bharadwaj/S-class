"""Tests for EGM Advisory Design-Review Pack (packs/egm-review).

Validates:
- Manifest structure, source URL, pinned commit SHA, license, trust level, and unqualified status.
- Every vendored file's SHA-256 hash strictly matches MANIFEST.json.
- Upstream LICENSE and NOTICE exist with attribution and provenance.
- Vendored upstream prompt files and license match the exact upstream pinned commit blobs.
- Pack documentation adheres to one-page limit and mandatory operating rules.
- Proposed MUSTs document is clearly advisory and contains both candidate checks.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PACK_DIR = REPO_ROOT / "packs" / "egm-review"
UPSTREAM_DIR = PACK_DIR / "upstream"

PINNED_COMMIT = "0997679a1cc3cfe09206160a85f9379f47101053"
SOURCE_URL = "https://github.com/google/elephant-goldfish-model"

# Canonical SHA-256 hashes of upstream blobs at pinned commit 0997679a1cc3cfe09206160a85f9379f47101053
UPSTREAM_BLOB_HASHES = {
    "agents/comprehension.md": "974f4972f717dc7b102a9b1407b3a625749149f2ae905727241e919f43cc3fa5",
    "agents/design_critic.md": "cee6294735ce2bd4fea19245852b6eb07cbe8ede7e72a4bfc829f586e4a39d0f",
    "agents/implementation_readiness.md": "1f6aa61cfe7cb86dc94943ab3b3fd339e5baba533937198fd10edb06dfa64e8f",
    "agents/synthesizer.md": "44d1288c03ec829acafd8af0226ce1d0603f4cf04e9f8438b5b36a451be8f8b6",
    "agents/zoom_out.md": "adc9d7b7db4c304866e61d5e5e446502231abe188ce64656939305e07ae7995f",
    "LICENSE": "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
}


def sha256_file(path: Path) -> str:
    """Computes exact SHA-256 digest of file bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_manifest_metadata_and_structure():
    """MANIFEST.json must declare source URL, pinned commit, Apache-2.0, L1 advisory, and UNQUALIFIED status."""
    manifest_path = PACK_DIR / "MANIFEST.json"
    assert manifest_path.exists(), "MANIFEST.json must exist in packs/egm-review"

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data.get("source_url") == SOURCE_URL or data.get("source") == SOURCE_URL
    assert data.get("commit_sha") == PINNED_COMMIT or data.get("commit") == PINNED_COMMIT
    assert data.get("license") == "Apache-2.0"
    assert data.get("trust_level") == "L1 advisory"
    assert data.get("status") == "UNQUALIFIED"
    assert "F10" in data.get("qualification_note", "") or "F10" in data.get("qualification_status", "")


def test_vendored_files_hashes_match_manifest():
    """Every vendored file in MANIFEST.json must exist on disk and match its declared SHA-256 hash."""
    manifest_path = PACK_DIR / "MANIFEST.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    files_map = data.get("files") or data.get("per_file_sha256") or {}
    assert len(files_map) >= 7, "Manifest must map at least 5 prompts, LICENSE, and NOTICE"

    for rel_path, expected_hash in files_map.items():
        target = PACK_DIR / rel_path
        assert target.exists(), f"File declared in manifest must exist on disk: {target}"
        actual_hash = sha256_file(target)
        assert actual_hash == expected_hash, (
            f"Hash mismatch for {rel_path}: expected {expected_hash}, got {actual_hash}"
        )


def test_license_and_notice_exist():
    """Upstream LICENSE and NOTICE must exist, be non-empty, and carry full attribution."""
    license_path = UPSTREAM_DIR / "LICENSE"
    notice_path = UPSTREAM_DIR / "NOTICE"

    assert license_path.exists(), "LICENSE must exist in packs/egm-review/upstream/"
    assert notice_path.exists(), "NOTICE must exist in packs/egm-review/upstream/"

    license_text = license_path.read_text(encoding="utf-8")
    assert "Apache License" in license_text
    assert len(license_text) > 1000

    notice_text = notice_path.read_text(encoding="utf-8")
    assert "Google" in notice_text
    assert SOURCE_URL in notice_text
    assert PINNED_COMMIT in notice_text


def test_upstream_files_unmodified():
    """All 5 vendored agent prompts and the LICENSE must be 100% byte-identical to upstream pinned commit."""
    for rel_path, expected_hash in UPSTREAM_BLOB_HASHES.items():
        file_path = UPSTREAM_DIR / rel_path
        assert file_path.exists(), f"Upstream file must exist: {file_path}"
        raw_bytes = file_path.read_bytes()
        assert b"\r\n" not in raw_bytes, f"Vendored file {rel_path} must have canonical LF line endings"
        actual_hash = hashlib.sha256(raw_bytes).hexdigest()
        assert actual_hash == expected_hash, (
            f"Vendored file {rel_path} was modified! Expected {expected_hash}, got {actual_hash}"
        )


def test_readme_contents_and_constraints():
    """README.md must be at most one page and state all mandatory pack governance rules."""
    readme_path = PACK_DIR / "README.md"
    assert readme_path.exists(), "README.md must exist in packs/egm-review"

    text = readme_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert len(lines) <= 60, f"README.md must be at most one page (got {len(lines)} lines)"

    # Mandatory statements
    assert "P2" in text and "P4" in text, "Must state advisory design-review pack for phases P2-P4"
    assert "untrusted claim, never gate authority" in text, (
        "Must state reviewer output is an untrusted claim, never gate authority"
    )
    assert "fresh, context-free" in text, (
        "Must state reviewers must run in fresh, context-free sessions"
    )
    assert "F4" in text, "Must reference design F4 independence"
    assert "Blocker" in text and "Major" in text and "Nit" in text, (
        "Must declare severity scale Blocker, Major, Nit"
    )
    assert "re-audit per stage" in text, "Must declare at most one re-audit per stage"


def test_proposed_musts_contents():
    """PROPOSED-MUSTS.md must be labeled as a proposal only and document both candidate spec-quality checks."""
    prop_path = PACK_DIR / "PROPOSED-MUSTS.md"
    assert prop_path.exists(), "PROPOSED-MUSTS.md must exist in packs/egm-review"

    text = prop_path.read_text(encoding="utf-8")
    assert "PROPOSAL ONLY" in text or "proposal only" in text
    assert "NOT A MUST CHANGE" in text or "not a MUST change" in text

    # Candidate check (a): paraphrase check
    assert "paraphrase" in text.lower(), "Must specify paraphrase check"
    assert "Blocker" in text, "Unparaphrasable section must be a Blocker"

    # Candidate check (b): implementation-readiness check
    assert "implementation-readiness" in text.lower(), "Must specify implementation-readiness check"
    assert "file paths" in text.lower(), "Must require naming file paths"
    assert "data structures" in text.lower(), "Must require data structures"
    assert "signatures" in text.lower(), "Must require signatures"
    assert "no design choice" in text.lower(), "Must leave no design choice to the implementer"
