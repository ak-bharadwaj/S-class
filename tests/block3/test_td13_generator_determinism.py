"""TD-13 determinism and self-sha256 header tests for generate_qualification_records.py."""
from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
GEN_PATH = REPO_ROOT / "product/oss-evidence/sweep/generate_qualification_records.py"
MD_PATH = REPO_ROOT / "product/oss-evidence/sweep/qualification_records_r32.md"


def _lf_sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def test_td13_generator_header_sha256_and_lf_only() -> None:
    gen_bytes = GEN_PATH.read_bytes()
    assert b"\r" not in gen_bytes, "generate_qualification_records.py contains CR/CRLF"

    md_bytes = MD_PATH.read_bytes()
    assert b"\r" not in md_bytes, "qualification_records_r32.md contains CR/CRLF"

    expected_gen_sha = _lf_sha256(GEN_PATH)
    header_lines = md_bytes.decode("utf-8").splitlines()[:10]
    assert any(line.startswith("As-of date: `2026-11-05`") for line in header_lines), (
        f"Missing As-of date header in {header_lines}"
    )
    assert f"Generator sha256: `{expected_gen_sha}`" in header_lines, (
        f"Missing or stale Generator sha256 `{expected_gen_sha}` in {header_lines}"
    )


def test_td13_regeneration_byte_identical(tmp_path: pathlib.Path) -> None:
    out_md = tmp_path / "regen_r32.md"
    subprocess.run(
        [
            sys.executable,
            str(GEN_PATH),
            "--recompute-from-md",
            str(MD_PATH),
            "--as-of",
            "2026-11-05",
            "--output-md",
            str(out_md),
            "--standalone-only",
        ],
        cwd=str(REPO_ROOT),
        check=True,
        capture_output=True,
        text=True,
    )
    regen_bytes = out_md.read_bytes()
    assert b"\r" not in regen_bytes
    assert regen_bytes == MD_PATH.read_bytes(), "Regenerated markdown differs from checked-in artifact"
