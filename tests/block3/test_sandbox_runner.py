"""WI-111 Sandbox Install Runner & Advisory/SBOM Check permanent hermetic tests."""
from __future__ import annotations

import base64
import hashlib
import json
import pathlib
import zipfile
from typing import Tuple

import pytest

from sclass.qualification.sandbox_runner import (
    SandboxVerdict,
    check_advisories_and_licenses,
    run_sandbox_install,
    validate_lock_file,
    verify_transcript_digest,
)


def _build_dummy_wheel(wheel_dir: pathlib.Path, name: str = "dummy_sclass_pkg", version: str = "1.2.3") -> Tuple[pathlib.Path, str]:
    """Create a minimal standards-compliant pure-Python wheel in wheel_dir and return (path, sha256)."""
    wheel_dir.mkdir(parents=True, exist_ok=True)
    dist_info = f"{name}-{version}.dist-info"
    whl_path = wheel_dir / f"{name}-{version}-py3-none-any.whl"

    init_bytes = b'VALUE = "sclass-sandbox-ok"\n'
    metadata_bytes = (
        f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\nLicense: MIT\n".encode("utf-8")
    )
    wheel_meta = b"Wheel-Version: 1.0\nGenerator: sclass-test\nRoot-Is-Purelib: true\nTag: py3-none-any\n"

    records = []
    files = {
        f"{name}/__init__.py": init_bytes,
        f"{dist_info}/METADATA": metadata_bytes,
        f"{dist_info}/WHEEL": wheel_meta,
    }
    for arcname, content in files.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=").decode("ascii")
        records.append(f"{arcname},sha256={digest},{len(content)}")
    records.append(f"{dist_info}/RECORD,,")
    record_bytes = ("\n".join(records) + "\n").encode("utf-8")

    with zipfile.ZipFile(whl_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for arcname, content in files.items():
            zf.writestr(arcname, content)
        zf.writestr(f"{dist_info}/RECORD", record_bytes)

    sha256 = hashlib.sha256(whl_path.read_bytes()).hexdigest()
    return whl_path, sha256


def test_hermetic_valid_install_and_transcript_verification(tmp_path: pathlib.Path) -> None:
    wheel_dir = tmp_path / "wheels"
    _, whl_sha = _build_dummy_wheel(wheel_dir, "dummy_sclass_pkg", "1.2.3")

    lock_path = tmp_path / "requirements.lock"
    lock_path.write_text(
        f"dummy_sclass_pkg==1.2.3 --hash=sha256:{whl_sha}\n",
        encoding="utf-8",
    )
    transcript_path = tmp_path / "transcript.log"

    res = run_sandbox_install(
        lock_path=lock_path,
        transcript_path=transcript_path,
        find_links=wheel_dir,
        no_index=True,
        use_bwrap=False,
    )
    assert res.install_succeeded is True
    assert res.isolation_mode == "UNISOLATED"
    # UNISOLATED mode can NEVER exceed UNVERIFIED
    assert res.verdict == SandboxVerdict.UNVERIFIED
    assert "UNISOLATED_NO_BWRAP" in res.reasons
    assert len(res.install_digest) == 64 and res.install_digest != "0" * 64
    assert res.installed_files_count >= 1
    assert transcript_path.exists()
    assert verify_transcript_digest(transcript_path, res.transcript_sha256) is True

    # Tampering transcript must be detected immediately
    orig = transcript_path.read_bytes()
    transcript_path.write_bytes(orig + b"\nTAMPERED_LINE\n")
    assert verify_transcript_digest(transcript_path, res.transcript_sha256) is False


def test_hash_mismatch_install_fails_closed(tmp_path: pathlib.Path) -> None:
    wheel_dir = tmp_path / "wheels"
    _, whl_sha = _build_dummy_wheel(wheel_dir, "dummy_sclass_pkg", "1.2.3")
    wrong_sha = ("f" if whl_sha[0] != "f" else "e") + whl_sha[1:]

    lock_path = tmp_path / "bad_hash.lock"
    lock_path.write_text(
        f"dummy_sclass_pkg==1.2.3 --hash=sha256:{wrong_sha}\n",
        encoding="utf-8",
    )
    transcript_path = tmp_path / "fail_transcript.log"

    res = run_sandbox_install(
        lock_path=lock_path,
        transcript_path=transcript_path,
        find_links=wheel_dir,
        no_index=True,
        use_bwrap=False,
    )
    assert res.install_succeeded is False
    assert res.verdict == SandboxVerdict.BLOCKED
    assert "PIP_INSTALL_FAILED" in res.reasons
    assert res.install_digest is None
    assert verify_transcript_digest(transcript_path, res.transcript_sha256) is True


def test_unpinned_missing_hash_and_placeholder_rejected(tmp_path: pathlib.Path) -> None:
    unpinned = tmp_path / "unpinned.lock"
    unpinned.write_text("dummy_sclass_pkg>=1.0.0 --hash=sha256:" + "a" * 64 + "\n", encoding="utf-8")
    v1 = validate_lock_file(unpinned)
    assert v1.valid is False
    assert "UNPINNED_REQUIREMENT" in v1.reasons

    missing_hash = tmp_path / "missing_hash.lock"
    missing_hash.write_text("dummy_sclass_pkg==1.2.3\n", encoding="utf-8")
    v2 = validate_lock_file(missing_hash)
    assert v2.valid is False
    assert "MISSING_REQUIREMENT_HASH" in v2.reasons

    zero_hash = tmp_path / "zero_hash.lock"
    zero_hash.write_text("dummy_sclass_pkg==1.2.3 --hash=sha256:" + "0" * 64 + "\n", encoding="utf-8")
    v3 = validate_lock_file(zero_hash)
    assert v3.valid is False
    assert "INVALID_HASH_PLACEHOLDER" in v3.reasons

    res = run_sandbox_install(
        lock_path=missing_hash,
        transcript_path=tmp_path / "blocked.log",
        use_bwrap=False,
    )
    assert res.verdict == SandboxVerdict.BLOCKED
    assert "MISSING_REQUIREMENT_HASH" in res.reasons


def test_bwrap_required_unavailable_blocks(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lock_path = tmp_path / "ok.lock"
    lock_path.write_text("dummy_sclass_pkg==1.2.3 --hash=sha256:" + "a" * 64 + "\n", encoding="utf-8")
    monkeypatch.setattr("shutil.which", lambda _name: None)
    res = run_sandbox_install(
        lock_path=lock_path,
        transcript_path=tmp_path / "bwrap_missing.log",
        use_bwrap=True,
    )
    assert res.verdict == SandboxVerdict.BLOCKED
    assert "BWRAP_UNAVAILABLE" in res.reasons


def test_advisory_and_sbom_fail_closed_and_happy() -> None:
    lock_hashes = {"jsonschema==4.23.0": "a" * 64}
    pip_audit_ok = json.dumps({
        "dependencies": [{"name": "jsonschema", "version": "4.23.0", "vulns": []}]
    })
    sbom_ok = json.dumps({
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "components": [
            {
                "name": "jsonschema",
                "version": "4.23.0",
                "licenses": [{"license": {"id": "MIT"}}],
                "hashes": [{"alg": "SHA-256", "content": "a" * 64}],
            }
        ],
    })
    ok_res = check_advisories_and_licenses(lock_hashes, pip_audit_ok, sbom_ok)
    assert ok_res.verdict == SandboxVerdict.VERIFIED
    assert ok_res.reasons == ()

    # Unparsable pip-audit -> BLOCKED
    bad_audit = check_advisories_and_licenses(lock_hashes, "{not-valid-json", sbom_ok)
    assert bad_audit.verdict == SandboxVerdict.BLOCKED
    assert "UNPARSABLE_PIP_AUDIT" in bad_audit.reasons

    # Unparsable SBOM -> BLOCKED
    bad_sbom = check_advisories_and_licenses(lock_hashes, pip_audit_ok, "{not-valid-json")
    assert bad_sbom.verdict == SandboxVerdict.BLOCKED
    assert "UNPARSABLE_SBOM" in bad_sbom.reasons

    # Hash mismatch in SBOM -> BLOCKED
    sbom_mismatch = json.dumps({
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "components": [
            {
                "name": "jsonschema",
                "version": "4.23.0",
                "licenses": [{"license": {"id": "MIT"}}],
                "hashes": [{"alg": "SHA-256", "content": "b" * 64}],
            }
        ],
    })
    res_mm = check_advisories_and_licenses(lock_hashes, pip_audit_ok, sbom_mismatch)
    assert res_mm.verdict == SandboxVerdict.BLOCKED
    assert "SBOM_HASH_MISMATCH" in res_mm.reasons

    # Vulnerability detected -> BLOCKED
    pip_audit_vuln = json.dumps({
        "dependencies": [{"name": "jsonschema", "version": "4.23.0", "vulns": [{"id": "CVE-2026-0001"}]}]
    })
    res_vuln = check_advisories_and_licenses(lock_hashes, pip_audit_vuln, sbom_ok)
    assert res_vuln.verdict == SandboxVerdict.BLOCKED
    assert "VULNERABILITIES_DETECTED" in res_vuln.reasons
