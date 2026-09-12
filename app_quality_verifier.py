"""
S-Class V12: App Quality & DOM Integrity Verifier (app_quality_verifier.py)

Evaluates rendered web application interfaces for defect patterns:
- Blank screen detection
- Leaked serialization tokens ('undefined', 'NaN', '[object Object]')
- Next.js / Vite / React crash overlays and 500 error banners
"""

import re
import urllib.request
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("sclass_app_quality_verifier")


class AppQualityVerifier:
    """
    DOM Sanity and Quality Assurance Verifier.
    """

    CORRUPTION_TOKENS = [
        "undefined",
        "NaN",
        "[object Object]",
        "Unhandled Runtime Error",
        "Next.js Server Error",
        "500 Internal Server Error",
        "React caught an error in one of your components",
        "Hydration failed because the initial UI does not match",
    ]

    @classmethod
    def verify_dom_html(cls, html_content: str) -> Dict[str, Any]:
        """Audits an HTML string for quality defects and corruption tokens."""
        errors = []
        warnings = []

        if not html_content or len(html_content.strip()) < 50:
            errors.append("Blank or severely truncated DOM detected (< 50 characters).")
            return {"passed": False, "errors": errors, "warnings": warnings}

        # Check for empty body
        body_match = re.search(r"<body[^>]*>(.*?)</body>", html_content, re.DOTALL | re.IGNORECASE)
        if body_match:
            body_inner = body_match.group(1).strip()
            # Strip tags and scripts
            clean_body = re.sub(r"<script[^>]*>.*?</script>", "", body_inner, flags=re.DOTALL | re.IGNORECASE)
            clean_body = re.sub(r"<[^>]+>", "", clean_body).strip()
            if len(clean_body) < 10:
                errors.append("Blank screen detected: HTML body contains virtually zero rendered text.")

        # Check corruption tokens
        for token in cls.CORRUPTION_TOKENS:
            found = False
            if re.match(r"^\w+$", token):
                pattern = re.compile(rf"\b{re.escape(token)}\b", re.IGNORECASE)
                found = bool(pattern.search(html_content))
            else:
                found = token.lower() in html_content.lower()

            if found:
                if any(err_kw in token.lower() for err_kw in ["error", "500", "hydration", "caught"]):
                    errors.append(f"Application crash / runtime error detected in DOM: '{token}'.")
                else:
                    errors.append(f"Corrupted serialization placeholder found in DOM: '{token}'.")

        passed = len(errors) == 0
        return {
            "passed": passed,
            "errors": errors,
            "warnings": warnings,
            "html_length": len(html_content),
        }

    @classmethod
    def verify_endpoint(cls, url: str, timeout: int = 5) -> Dict[str, Any]:
        """Fetches a live URL over HTTP and audits the rendered DOM."""
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SClassQualityVerifier/12.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = resp.status
                html_text = resp.read().decode("utf-8", errors="ignore")

            res = cls.verify_dom_html(html_text)
            res["status_code"] = status
            if status >= 400:
                res["passed"] = False
                res["errors"].append(f"HTTP response returned error status {status}.")
            return res

        except Exception as e:
            return {
                "passed": False,
                "status_code": 0,
                "errors": [f"Failed to connect to endpoint {url}: {e}"],
                "warnings": [],
            }
