import os
import struct
import tempfile
import pytest
from verifier import audit_image_bytes, find_active_dev_server_port, EvidenceVerifier

def make_valid_png_bytes(width: int, height: int, variance: bool = True) -> bytes:
    """Helper to construct PNG byte payload with custom dimensions and byte variance."""
    header = b'\x89PNG\r\n\x1a\n'
    ihdr_type = b'IHDR'
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr_chunk = struct.pack('>I', len(ihdr_data)) + ihdr_type + ihdr_data + b'\x00\x00\x00\x00'
    
    if variance:
        # High-variance payload (simulating real UI screenshot with anti-aliasing & colors)
        idat_payload = bytes([(i * 37 + (i % 13) * 17) % 256 for i in range(20000)])
    else:
        # Zero-variance solid fill payload
        idat_payload = b'\xff' * 20000

    idat_chunk = struct.pack('>I', len(idat_payload)) + b'IDAT' + idat_payload + b'\x00\x00\x00\x00'
    iend_chunk = b'\x00\x00\x00\x00IEND\xaeB`\x82'
    return header + ihdr_chunk + idat_chunk + iend_chunk


def test_audit_image_bytes_valid_high_variance():
    png_data = make_valid_png_bytes(1920, 1080, variance=True)
    is_valid, w, h, std_dev, distinct_bytes = audit_image_bytes(png_data)
    assert is_valid is True
    assert w == 1920
    assert h == 1080
    assert std_dev > 8.0
    assert distinct_bytes >= 25


def test_audit_image_bytes_zero_variance_solid_fill():
    png_data = make_valid_png_bytes(1920, 1080, variance=False)
    is_valid, w, h, std_dev, distinct_bytes = audit_image_bytes(png_data)
    assert is_valid is True
    assert w == 1920
    assert h == 1080
    # Solid fill has low standard deviation (< 15.0) and few distinct bytes (< 15)
    assert std_dev < 15.0
    assert distinct_bytes < 15


def test_qa_evidence_shared_rejects_solid_fill_fake_screenshot():
    with tempfile.TemporaryDirectory() as tmpdir:
        state_dir = os.path.join(tmpdir, ".agents")
        screenshots_dir = os.path.join(state_dir, "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        state_file = os.path.join(state_dir, "orchestration_state.json")
        with open(state_file, "w", encoding="utf-8") as f:
            f.write("{}")

        # Write solid fill fake screenshot (size > 10KB, valid PNG header, but zero variance)
        fake_png = make_valid_png_bytes(1920, 1080, variance=False)
        assert len(fake_png) > 10240
        with open(os.path.join(screenshots_dir, "desktop_view.png"), "wb") as f:
            f.write(fake_png)

        errors, real_screenshots, min_req = EvidenceVerifier._verify_qa_evidence_shared(tmpdir, state_dir, state_file, allow_soft=False)
        assert len(real_screenshots) == 0
        assert any("CHEATING DETECTED" in err for err in errors)


def test_qa_evidence_shared_accepts_valid_high_variance_screenshot():
    with tempfile.TemporaryDirectory() as tmpdir:
        state_dir = os.path.join(tmpdir, ".agents")
        screenshots_dir = os.path.join(state_dir, "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        state_file = os.path.join(state_dir, "orchestration_state.json")
        with open(state_file, "w", encoding="utf-8") as f:
            f.write("{}")

        # Write valid high-variance screenshot
        valid_png = make_valid_png_bytes(1920, 1080, variance=True)
        assert len(valid_png) > 10240
        with open(os.path.join(screenshots_dir, "desktop_view.png"), "wb") as f:
            f.write(valid_png)

        errors, real_screenshots, min_req = EvidenceVerifier._verify_qa_evidence_shared(tmpdir, state_dir, state_file, allow_soft=True)
        assert len(real_screenshots) == 1
        assert "desktop_view.png" in real_screenshots
