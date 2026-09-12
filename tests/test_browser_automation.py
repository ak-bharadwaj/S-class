"""
Unit tests for S-Class V12 Browser Automation & Multi-Tier Visual QA
(tests/test_browser_automation.py)
"""

import pytest
from screenshot_capture import ScreenshotCaptureEngine
from app_quality_verifier import AppQualityVerifier
from accessibility_auditor import AccessibilityAuditor


def test_screenshot_capture_browser_discovery():
    # Should check PATH or known directories without throwing unhandled exceptions
    browser_exe = ScreenshotCaptureEngine.find_browser_executable()
    # If on Windows/macOS/Linux with browser, returns string; if not, None
    assert browser_exe is None or isinstance(browser_exe, str)


def test_app_quality_verifier_clean_dom():
    clean_html = """<!DOCTYPE html>
<html>
<head><title>Dashboard</title></head>
<body>
    <header><h1>ERP Control Plane</h1></header>
    <main><p>System is operational with 42 active services running smoothly.</p></main>
</body>
</html>"""
    res = AppQualityVerifier.verify_dom_html(clean_html)
    assert res["passed"] is True
    assert len(res["errors"]) == 0


def test_app_quality_verifier_blank_screen():
    blank_html = "<!DOCTYPE html><html><head></head><body></body></html>"
    res = AppQualityVerifier.verify_dom_html(blank_html)
    assert res["passed"] is False
    assert any("Blank" in e for e in res["errors"])


def test_app_quality_verifier_corruption_tokens():
    corrupted_html = """<!DOCTYPE html>
<html>
<head><title>Account</title></head>
<body>
    <div>Welcome, undefined!</div>
    <div>Balance: $NaN</div>
    <div>Details: [object Object]</div>
</body>
</html>"""
    res = AppQualityVerifier.verify_dom_html(corrupted_html)
    assert res["passed"] is False
    assert len(res["errors"]) >= 3


def test_app_quality_verifier_runtime_crash_overlay():
    crash_html = """<!DOCTYPE html>
<html>
<head><title>Error</title></head>
<body>
    <div class="nextjs-error-overlay">
        <h2>Unhandled Runtime Error</h2>
        <p>TypeError: Cannot read property 'map' of undefined</p>
    </div>
</body>
</html>"""
    res = AppQualityVerifier.verify_dom_html(crash_html)
    assert res["passed"] is False
    assert any("crash" in e.lower() or "error" in e.lower() for e in res["errors"])


def test_accessibility_auditor_compliance():
    compliant_html = """<!DOCTYPE html>
<html>
<head><title>Accessible ERP Portal</title></head>
<body>
    <img src="/logo.png" alt="Company Logo">
    <form>
        <input type="text" id="username" aria-label="Username">
        <button type="submit">Log In</button>
    </form>
</body>
</html>"""
    res = AccessibilityAuditor.audit_html(compliant_html)
    assert res["passed"] is True
    assert res["accessibility_score"] == 100.0


def test_accessibility_auditor_violations():
    inaccessible_html = """<!DOCTYPE html>
<html>
<head></head>
<body>
    <img src="/banner.jpg">
    <input>
    <button></button>
</body>
</html>"""
    res = AccessibilityAuditor.audit_html(inaccessible_html)
    assert res["passed"] is False
    assert res["violation_count"] >= 3
    assert res["accessibility_score"] < 100.0
