"""WI-111 Sandbox Install Runner & Lock-Bound Advisory/Licence Checker.

NOTE: Host cgroup and bubblewrap (`bwrap`) host qualification is deferred to
Block 4. In Block 3, `bwrap` is used when available on PATH; otherwise the
runner executes in an explicitly labelled `UNISOLATED` mode whose verdict
NEVER exceeds `UNVERIFIED`.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import tempfile
import venv
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from sclass.qualification.facts import parse_spdx_expression

_PINNED_REQ_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*==\s*([A-Za-z0-9.+!_-]+)$")
_HASH_OPT_RE = re.compile(r"^--hash=sha256:([0-9a-fA-F]{64})$")
_VALID_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class SandboxVerdict(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class LockValidationResult:
    valid: bool
    reasons: Tuple[str, ...]
    requirements: Tuple[Tuple[str, str, Tuple[str, ...]], ...]  # (pkg, version, hashes)


@dataclass(frozen=True)
class SandboxInstallResult:
    verdict: SandboxVerdict
    install_succeeded: bool
    isolation_mode: str  # "BUBBLEWRAP" | "UNISOLATED"
    reasons: Tuple[str, ...]
    transcript_path: str
    transcript_sha256: str
    install_digest: Optional[str]
    installed_files_count: int
    returncode: int


@dataclass(frozen=True)
class AdvisoryLicenseResult:
    verdict: SandboxVerdict
    reasons: Tuple[str, ...]
    vulnerabilities: Tuple[str, ...]
    license_classes: Mapping[str, str]


def _normalize_pkg(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _parse_logical_lock_lines(text: str) -> List[str]:
    logical: List[str] = []
    buf = ""
    for raw in text.splitlines():
        stripped = raw.strip()
        if not buf and (not stripped or stripped.startswith("#")):
            continue
        if stripped.endswith("\\"):
            buf += stripped[:-1].strip() + " "
            continue
        line = (buf + stripped).strip()
        buf = ""
        if line and not line.startswith("#"):
            logical.append(line)
    if buf.strip():
        logical.append(buf.strip())
    return logical


def validate_lock_file(lock_path: pathlib.Path | str) -> LockValidationResult:
    """Strictly validate a pip hash-pinned requirements lock file."""
    p = pathlib.Path(lock_path)
    if not p.is_file():
        return LockValidationResult(valid=False, reasons=("LOCK_FILE_NOT_FOUND",), requirements=())
    try:
        raw_text = p.read_text(encoding="utf-8")
    except Exception:
        return LockValidationResult(valid=False, reasons=("LOCK_FILE_UNREADABLE",), requirements=())

    lines = _parse_logical_lock_lines(raw_text)
    if not lines:
        return LockValidationResult(valid=False, reasons=("EMPTY_LOCK_FILE",), requirements=())

    reasons: List[str] = []
    parsed_reqs: List[Tuple[str, str, Tuple[str, ...]]] = []

    for line in lines:
        # Reject inline comments after requirements safely only if preceded by space+#
        line_no_comment = line.split(" #", 1)[0].strip()
        tokens = line_no_comment.split()
        if not tokens:
            continue
        req_tok = tokens[0]
        opt_tokens = tokens[1:]

        if req_tok.startswith("-") or "://" in req_tok or " @" in line_no_comment:
            reasons.append("UNPINNED_REQUIREMENT")
            continue

        m_req = _PINNED_REQ_RE.match(req_tok)
        if not m_req:
            reasons.append("UNPINNED_REQUIREMENT")
            continue

        pkg, ver = m_req.group(1), m_req.group(2)
        hashes: List[str] = []
        bad_opt = False
        for opt in opt_tokens:
            mh = _HASH_OPT_RE.match(opt)
            if not mh:
                reasons.append("DISALLOWED_LOCK_OPTION")
                bad_opt = True
                break
            hex_digest = mh.group(1).lower()
            if hex_digest == "0" * 64:
                reasons.append("INVALID_HASH_PLACEHOLDER")
                bad_opt = True
                break
            hashes.append(hex_digest)

        if bad_opt:
            continue
        if not hashes:
            reasons.append("MISSING_REQUIREMENT_HASH")
            continue
        parsed_reqs.append((pkg, ver, tuple(hashes)))

    if not parsed_reqs and not reasons:
        reasons.append("EMPTY_LOCK_FILE")

    dedup = tuple(dict.fromkeys(reasons))
    return LockValidationResult(
        valid=(len(dedup) == 0 and len(parsed_reqs) > 0),
        reasons=dedup,
        requirements=tuple(parsed_reqs),
    )


def verify_transcript_digest(transcript_path: pathlib.Path | str, expected_sha256: str) -> bool:
    """Recompute transcript sha256 and detect tampering or missing files."""
    if type(expected_sha256) is not str or not _VALID_SHA256_RE.match(expected_sha256):
        return False
    if expected_sha256.lower() == "0" * 64:
        return False
    p = pathlib.Path(transcript_path)
    if not p.is_file():
        return False
    actual = hashlib.sha256(p.read_bytes()).hexdigest()
    return actual == expected_sha256.lower()


def _find_site_packages(venv_dir: pathlib.Path) -> List[pathlib.Path]:
    candidates: List[pathlib.Path] = []
    win_sp = venv_dir / "Lib/site-packages"
    if win_sp.is_dir():
        candidates.append(win_sp)
    for posix_sp in venv_dir.glob("lib/python*/site-packages"):
        if posix_sp.is_dir():
            candidates.append(posix_sp)
    return candidates


def _compute_install_digest(site_packages_dirs: Sequence[pathlib.Path]) -> Tuple[Optional[str], int]:
    entries: List[Tuple[str, str]] = []
    for sp in site_packages_dirs:
        for file_path in sorted(sp.rglob("*")):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(sp).as_posix()
            if "__pycache__" in rel.split("/") or rel.endswith(".pyc"):
                continue
            fhash = hashlib.sha256(file_path.read_bytes()).hexdigest()
            entries.append((rel, fhash))
    if not entries:
        return None, 0
    entries.sort(key=lambda x: x[0])
    canonical = json.dumps(entries, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest(), len(entries)


def _find_venv_python(venv_dir: pathlib.Path) -> Optional[pathlib.Path]:
    for cand in (venv_dir / "Scripts/python.exe", venv_dir / "bin/python", venv_dir / "bin/python3"):
        if cand.is_file():
            return cand
    return None


def _write_transcript(transcript_path: pathlib.Path, content: bytes) -> str:
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def run_sandbox_install(
    lock_path: pathlib.Path | str,
    transcript_path: pathlib.Path | str,
    *,
    find_links: Optional[pathlib.Path | str] = None,
    no_index: bool = True,
    use_bwrap: Optional[bool] = None,
    timeout_s: int = 120,
) -> SandboxInstallResult:
    """Install hash-locked requirements into a throwaway venv, saving transcript and install digest."""
    t_path = pathlib.Path(transcript_path)
    l_path = pathlib.Path(lock_path)

    lock_val = validate_lock_file(l_path)
    if not lock_val.valid:
        msg = f"LOCK_VALIDATION_FAILED: {', '.join(lock_val.reasons)}\n".encode("utf-8")
        t_sha = _write_transcript(t_path, msg)
        return SandboxInstallResult(
            verdict=SandboxVerdict.BLOCKED,
            install_succeeded=False,
            isolation_mode="UNISOLATED",
            reasons=lock_val.reasons,
            transcript_path=str(t_path),
            transcript_sha256=t_sha,
            install_digest=None,
            installed_files_count=0,
            returncode=2,
        )

    bwrap_bin = shutil.which("bwrap")
    if use_bwrap is True and not bwrap_bin:
        msg = b"BWRAP_UNAVAILABLE: bwrap requested explicitly but not found on PATH\n"
        t_sha = _write_transcript(t_path, msg)
        return SandboxInstallResult(
            verdict=SandboxVerdict.BLOCKED,
            install_succeeded=False,
            isolation_mode="UNISOLATED",
            reasons=("BWRAP_UNAVAILABLE",),
            transcript_path=str(t_path),
            transcript_sha256=t_sha,
            install_digest=None,
            installed_files_count=0,
            returncode=2,
        )

    isolation_mode = "BUBBLEWRAP" if (bwrap_bin and use_bwrap is not False) else "UNISOLATED"

    with tempfile.TemporaryDirectory(prefix="sclass_s2_venv_") as tmp_dir_str:
        tmp_dir = pathlib.Path(tmp_dir_str)
        venv_dir = tmp_dir / "venv"
        venv.create(venv_dir, with_pip=True, clear=True)
        venv_py = _find_venv_python(venv_dir)
        if venv_py is None:
            msg = b"VENV_CREATION_FAILED: python executable not found inside throwaway venv\n"
            t_sha = _write_transcript(t_path, msg)
            return SandboxInstallResult(
                verdict=SandboxVerdict.BLOCKED,
                install_succeeded=False,
                isolation_mode=isolation_mode,
                reasons=("VENV_CREATION_FAILED",),
                transcript_path=str(t_path),
                transcript_sha256=t_sha,
                install_digest=None,
                installed_files_count=0,
                returncode=2,
            )

        # Snapshot baseline site-packages before install so install_digest measures target packages
        pre_sp = _find_site_packages(venv_dir)
        pre_files = set()
        for sp in pre_sp:
            for fp in sp.rglob("*"):
                if fp.is_file():
                    pre_files.add(fp.resolve())

        pip_cmd: List[str] = [
            str(venv_py),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-input",
            "--require-hashes",
            "--no-deps",
        ]
        if no_index:
            pip_cmd.append("--no-index")
        if find_links is not None:
            pip_cmd.extend(["--find-links", str(pathlib.Path(find_links).resolve())])
        pip_cmd.extend(["-r", str(l_path.resolve())])

        if isolation_mode == "BUBBLEWRAP":
            assert bwrap_bin is not None
            bwrap_cmd: List[str] = [
                bwrap_bin,
                "--ro-bind", "/", "/",
                "--dev", "/dev",
                "--proc", "/proc",
                "--bind", str(tmp_dir), str(tmp_dir),
                "--unshare-pid",
                "--die-with-parent",
            ]
            if no_index:
                bwrap_cmd.append("--unshare-net")
            exec_cmd = bwrap_cmd + ["--"] + pip_cmd
        else:
            exec_cmd = pip_cmd

        header = (
            f"[sclass-sandbox] isolation_mode={isolation_mode}\n"
            f"[sclass-sandbox] cmd={' '.join(exec_cmd)}\n"
        ).encode("utf-8")

        try:
            proc = subprocess.run(
                exec_cmd,
                capture_output=True,
                timeout=timeout_s,
                check=False,
            )
            raw_transcript = header + (proc.stdout or b"") + (proc.stderr or b"")
            rc = proc.returncode
        except subprocess.TimeoutExpired as exc:
            raw_transcript = header + (exc.stdout or b"") + (exc.stderr or b"") + b"\n[sclass-sandbox] TIMEOUT\n"
            t_sha = _write_transcript(t_path, raw_transcript)
            return SandboxInstallResult(
                verdict=SandboxVerdict.BLOCKED,
                install_succeeded=False,
                isolation_mode=isolation_mode,
                reasons=("INSTALL_TIMEOUT",),
                transcript_path=str(t_path),
                transcript_sha256=t_sha,
                install_digest=None,
                installed_files_count=0,
                returncode=124,
            )

        t_sha = _write_transcript(t_path, raw_transcript)
        if rc != 0:
            return SandboxInstallResult(
                verdict=SandboxVerdict.BLOCKED,
                install_succeeded=False,
                isolation_mode=isolation_mode,
                reasons=("PIP_INSTALL_FAILED",),
                transcript_path=str(t_path),
                transcript_sha256=t_sha,
                install_digest=None,
                installed_files_count=0,
                returncode=rc,
            )

        # Compute install digest over newly installed files in site-packages
        post_sp = _find_site_packages(venv_dir)
        new_entries: List[Tuple[str, str]] = []
        for sp in post_sp:
            for fp in sorted(sp.rglob("*")):
                if not fp.is_file() or fp.resolve() in pre_files:
                    continue
                rel = fp.relative_to(sp).as_posix()
                if "__pycache__" in rel.split("/") or rel.endswith(".pyc"):
                    continue
                new_entries.append((rel, hashlib.sha256(fp.read_bytes()).hexdigest()))

        if not new_entries:
            # Fallback to full site-packages tree if pre-existing matched (e.g. reinstall)
            install_digest, file_count = _compute_install_digest(post_sp)
        else:
            new_entries.sort(key=lambda x: x[0])
            install_digest = hashlib.sha256(
                json.dumps(new_entries, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            file_count = len(new_entries)

        if isolation_mode == "UNISOLATED":
            return SandboxInstallResult(
                verdict=SandboxVerdict.UNVERIFIED,
                install_succeeded=True,
                isolation_mode=isolation_mode,
                reasons=("UNISOLATED_NO_BWRAP",),
                transcript_path=str(t_path),
                transcript_sha256=t_sha,
                install_digest=install_digest,
                installed_files_count=file_count,
                returncode=rc,
            )

        return SandboxInstallResult(
            verdict=SandboxVerdict.VERIFIED,
            install_succeeded=True,
            isolation_mode=isolation_mode,
            reasons=(),
            transcript_path=str(t_path),
            transcript_sha256=t_sha,
            install_digest=install_digest,
            installed_files_count=file_count,
            returncode=rc,
        )


def _parse_json_payload(payload: Any, err_code: str) -> Tuple[Optional[Any], Optional[str]]:
    if isinstance(payload, (dict, list)):
        return payload, None
    if type(payload) is str and payload.strip():
        try:
            return json.loads(payload), None
        except Exception:
            return None, err_code
    return None, err_code


def check_advisories_and_licenses(
    lock_hashes: Mapping[str, str],
    pip_audit_payload: Any,
    sbom_payload: Any,
    *,
    isolated: bool = False,
) -> AdvisoryLicenseResult:
    """Strictly parse pip-audit and CycloneDX SBOM payloads bound to lock_hashes."""
    if not isinstance(lock_hashes, Mapping) or not lock_hashes:
        return AdvisoryLicenseResult(
            verdict=SandboxVerdict.BLOCKED,
            reasons=("EMPTY_LOCK_HASHES",),
            vulnerabilities=(),
            license_classes={},
        )

    parsed_locks: Dict[str, str] = {}
    for req_key, sha_val in lock_hashes.items():
        if type(req_key) is not str or not req_key.strip() or type(sha_val) is not str:
            return AdvisoryLicenseResult(
                verdict=SandboxVerdict.BLOCKED,
                reasons=("INVALID_LOCK_HASHES",),
                vulnerabilities=(),
                license_classes={},
            )
        pkg_name = req_key.split("==", 1)[0].strip()
        hex_sha = sha_val.replace("sha256:", "").strip().lower()
        if not _VALID_SHA256_RE.match(hex_sha) or hex_sha == "0" * 64:
            return AdvisoryLicenseResult(
                verdict=SandboxVerdict.BLOCKED,
                reasons=("INVALID_LOCK_HASHES",),
                vulnerabilities=(),
                license_classes={},
            )
        parsed_locks[_normalize_pkg(pkg_name)] = hex_sha

    audit_obj, audit_err = _parse_json_payload(pip_audit_payload, "UNPARSABLE_PIP_AUDIT")
    if audit_err is not None:
        return AdvisoryLicenseResult(
            verdict=SandboxVerdict.BLOCKED,
            reasons=(audit_err,),
            vulnerabilities=(),
            license_classes={},
        )

    if isinstance(audit_obj, dict):
        deps = audit_obj.get("dependencies")
    elif isinstance(audit_obj, list):
        deps = audit_obj
    else:
        deps = None

    if not isinstance(deps, list):
        return AdvisoryLicenseResult(
            verdict=SandboxVerdict.BLOCKED,
            reasons=("UNPARSABLE_PIP_AUDIT",),
            vulnerabilities=(),
            license_classes={},
        )

    sbom_obj, sbom_err = _parse_json_payload(sbom_payload, "UNPARSABLE_SBOM")
    if sbom_err is not None or not isinstance(sbom_obj, dict):
        return AdvisoryLicenseResult(
            verdict=SandboxVerdict.BLOCKED,
            reasons=("UNPARSABLE_SBOM",),
            vulnerabilities=(),
            license_classes={},
        )

    if sbom_obj.get("bomFormat") != "CycloneDX" or not isinstance(sbom_obj.get("components"), list):
        return AdvisoryLicenseResult(
            verdict=SandboxVerdict.BLOCKED,
            reasons=("UNPARSABLE_SBOM",),
            vulnerabilities=(),
            license_classes={},
        )

    blocked_reasons: List[str] = []
    unverified_reasons: List[str] = []
    vulns_found: List[str] = []

    audit_seen: set[str] = set()
    for dep in deps:
        if not isinstance(dep, dict) or type(dep.get("name")) is not str or not isinstance(dep.get("vulns"), list):
            return AdvisoryLicenseResult(
                verdict=SandboxVerdict.BLOCKED,
                reasons=("UNPARSABLE_PIP_AUDIT",),
                vulnerabilities=(),
                license_classes={},
            )
        norm_name = _normalize_pkg(dep["name"])
        audit_seen.add(norm_name)
        for v in dep["vulns"]:
            if not isinstance(v, dict) or type(v.get("id")) is not str:
                return AdvisoryLicenseResult(
                    verdict=SandboxVerdict.BLOCKED,
                    reasons=("UNPARSABLE_PIP_AUDIT",),
                    vulnerabilities=(),
                    license_classes={},
                )
            vulns_found.append(f"{norm_name}:{v['id']}")

    if vulns_found:
        blocked_reasons.append("VULNERABILITIES_DETECTED")

    for req_pkg in parsed_locks:
        if req_pkg not in audit_seen:
            blocked_reasons.append("PIP_AUDIT_LOCK_MISMATCH")
            break

    sbom_seen: set[str] = set()
    license_classes: Dict[str, str] = {}
    for comp in sbom_obj["components"]:
        if not isinstance(comp, dict) or type(comp.get("name")) is not str:
            return AdvisoryLicenseResult(
                verdict=SandboxVerdict.BLOCKED,
                reasons=("UNPARSABLE_SBOM",),
                vulnerabilities=tuple(vulns_found),
                license_classes={},
            )
        norm_name = _normalize_pkg(comp["name"])
        sbom_seen.add(norm_name)

        # Verify SHA-256 hash matches lock_hashes if component is in lock_hashes
        hashes_list = comp.get("hashes", [])
        if not isinstance(hashes_list, list):
            return AdvisoryLicenseResult(
                verdict=SandboxVerdict.BLOCKED,
                reasons=("UNPARSABLE_SBOM",),
                vulnerabilities=tuple(vulns_found),
                license_classes=license_classes,
            )
        comp_sha256: Optional[str] = None
        for h_entry in hashes_list:
            if isinstance(h_entry, dict) and str(h_entry.get("alg", "")).upper() in ("SHA-256", "SHA256"):
                val = h_entry.get("content")
                if type(val) is str and _VALID_SHA256_RE.match(val.strip()):
                    comp_sha256 = val.strip().lower()
        if norm_name in parsed_locks:
            if comp_sha256 is None or comp_sha256 != parsed_locks[norm_name]:
                blocked_reasons.append("SBOM_HASH_MISMATCH")

        # Strict licence check
        lic_entries = comp.get("licenses", [])
        if not isinstance(lic_entries, list) or not lic_entries:
            blocked_reasons.append("UNKNOWN_SPDX")
            license_classes[norm_name] = "UNKNOWN"
            continue
        exprs: List[str] = []
        for le in lic_entries:
            if isinstance(le, dict):
                if isinstance(le.get("license"), dict) and type(le["license"].get("id")) is str:
                    exprs.append(le["license"]["id"])
                elif type(le.get("expression")) is str:
                    exprs.append(le["expression"])
        if not exprs:
            blocked_reasons.append("UNKNOWN_SPDX")
            license_classes[norm_name] = "UNKNOWN"
            continue
        combined_expr = " AND ".join(exprs)
        lic_cls, _ = parse_spdx_expression(combined_expr)
        license_classes[norm_name] = lic_cls
        if lic_cls == "UNKNOWN":
            blocked_reasons.append("UNKNOWN_SPDX")
        elif lic_cls == "STRONG_COPYLEFT" and not isolated:
            blocked_reasons.append("STRONG_COPYLEFT_UNISOLATED")
        elif lic_cls in ("STRONG_COPYLEFT", "WEAK_COPYLEFT"):
            unverified_reasons.append("COPYLEFT_OBLIGATIONS")

    for req_pkg in parsed_locks:
        if req_pkg not in sbom_seen:
            blocked_reasons.append("SBOM_LOCK_MISMATCH")
            break

    all_reasons = tuple(dict.fromkeys(blocked_reasons + unverified_reasons))
    if blocked_reasons:
        return AdvisoryLicenseResult(
            verdict=SandboxVerdict.BLOCKED,
            reasons=all_reasons,
            vulnerabilities=tuple(vulns_found),
            license_classes=license_classes,
        )
    if unverified_reasons:
        return AdvisoryLicenseResult(
            verdict=SandboxVerdict.UNVERIFIED,
            reasons=all_reasons,
            vulnerabilities=tuple(vulns_found),
            license_classes=license_classes,
        )
    return AdvisoryLicenseResult(
        verdict=SandboxVerdict.VERIFIED,
        reasons=(),
        vulnerabilities=(),
        license_classes=license_classes,
    )
