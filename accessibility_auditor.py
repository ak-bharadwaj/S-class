"""
S-Class v6: Accessibility Auditor Engine (accessibility_auditor.py)

Performs static and DOM-level WCAG 2.1 AA accessibility compliance audits:
- Missing image alt attributes
- Unlabelled form controls
- Empty interactive buttons
- Missing document title
"""

import re
from typing import Dict, Any, List


TITLE_PATTERN = re.compile(r"<title[^>]*>.*?</title>", re.IGNORECASE | re.DOTALL)
IMG_PATTERN = re.compile(r"<img\b([^>]*)>", re.IGNORECASE)
INPUT_PATTERN = re.compile(r"<input\b([^>]*)>", re.IGNORECASE)
BUTTON_EMPTY_PATTERN = re.compile(r"<button\b[^>]*>\s*</button>", re.IGNORECASE)


class AccessibilityAuditor:
    """
    Evaluates WCAG 2.1 AA accessibility invariants on HTML interfaces.
    """

    @classmethod
    def audit_html(cls, html_content: str) -> Dict[str, Any]:
        violations = []

        # 1. Document title check
        if not TITLE_PATTERN.search(html_content):
            violations.append("WCAG 2.4.2: Page missing mandatory <title> tag.")

        # 2. Image alt attributes
        for idx, match in enumerate(IMG_PATTERN.finditer(html_content), start=1):
            attrs = match.group(1)
            if "alt=" not in attrs.lower():
                violations.append(f"WCAG 1.1.1: Image #{idx} missing mandatory 'alt' description attribute.")

        # 3. Unlabelled inputs
        for idx, match in enumerate(INPUT_PATTERN.finditer(html_content), start=1):
            attrs = match.group(1).lower()
            if "type=\"hidden\"" in attrs or "type='hidden'" in attrs:
                continue
            has_label = ("aria-label=" in attrs or "aria-labelledby=" in attrs or "id=" in attrs or "placeholder=" in attrs)
            if not has_label:
                violations.append(f"WCAG 4.1.2: Interactive input #{idx} lacks accessible label or identifier.")

        # 4. Empty buttons
        if BUTTON_EMPTY_PATTERN.search(html_content):
            violations.append("WCAG 4.1.2: Empty <button> element without text or aria-label found.")

        score = max(0.0, 100.0 - (len(violations) * 15.0))
        return {
            "passed": len(violations) == 0,
            "violation_count": len(violations),
            "violations": violations,
            "accessibility_score": round(score, 1),
        }
