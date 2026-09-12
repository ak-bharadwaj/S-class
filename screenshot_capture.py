"""
S-Class V12: Zero-Dependency System Browser Screenshot Engine (screenshot_capture.py)

Discovers installed system browser binaries (Edge, Chrome, Chromium) and captures
high-fidelity, non-zero entropy UI screenshots via native headless CLI flags.
Verifies captured bytes against anti-cheating entropy and dimension invariants.
"""

import os
import sys
import shutil
import subprocess
import logging
from typing import Optional, Dict, Any
from verifier import audit_image_bytes

logger = logging.getLogger("sclass_screenshot_capture")


class ScreenshotCaptureEngine:
    """
    Zero-infrastructure headless browser screenshot engine using system Chrome/Edge.
    """

    KNOWN_BROWSER_PATHS = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"/usr/bin/google-chrome",
        r"/usr/bin/chromium",
        r"/usr/bin/chromium-browser",
        r"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        r"/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ]

    @classmethod
    def find_browser_executable(cls) -> Optional[str]:
        """Discovers an available Chrome or Edge browser executable on the system."""
        # Check PATH first
        for name in ["msedge", "chrome", "google-chrome", "chromium", "brave"]:
            path = shutil.which(name)
            if path and os.path.exists(path):
                return path

        # Check known installation paths
        for path in cls.KNOWN_BROWSER_PATHS:
            if os.path.exists(path):
                return path

        return None

    @classmethod
    def capture_screenshot(
        cls,
        url: str,
        output_path: str,
        width: int = 1920,
        height: int = 1080,
        timeout: int = 15,
    ) -> Dict[str, Any]:
        """
        Captures a live headless screenshot of the specified URL and verifies its authenticity.
        """
        browser_exe = cls.find_browser_executable()
        if not browser_exe:
            return {
                "success": False,
                "error": "No installed system browser (Edge/Chrome) found on the host machine.",
            }

        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        cmd = [
            browser_exe,
            "--headless=new",
            f"--screenshot={output_path}",
            f"--window-size={width},{height}",
            "--hide-scrollbars",
            "--disable-gpu",
            "--no-sandbox",
            url,
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, timeout=timeout)
            if not os.path.exists(output_path):
                return {
                    "success": False,
                    "error": f"Browser executed but output file '{output_path}' was not generated. Return code: {res.returncode}",
                }

            with open(output_path, "rb") as f:
                data = f.read()

            is_valid, w, h, std_dev, distinct_bytes = audit_image_bytes(data)

            if not is_valid or w is None or h is None or w < 320 or h < 320 or std_dev < 15.0 or distinct_bytes < 15:
                return {
                    "success": False,
                    "file_path": output_path,
                    "size_bytes": len(data),
                    "error": f"Captured screenshot failed anti-cheating audit: dimensions ({w}x{h}), std_dev {std_dev:.2f}, distinct bytes {distinct_bytes}.",
                }

            return {
                "success": True,
                "file_path": output_path,
                "width": w,
                "height": h,
                "std_dev": std_dev,
                "distinct_bytes": distinct_bytes,
                "size_bytes": len(data),
            }

        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Browser timed out after {timeout}s while capturing {url}."}
        except Exception as e:
            return {"success": False, "error": str(e)}
