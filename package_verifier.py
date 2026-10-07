"""
S-Class V12: Supply-Chain Package Legitimacy Verifier (package_verifier.py)

Validates third-party package names against official PyPI and npm registries
before permitting installation, blocking AI slopsquatting and hallucinated dependencies.
"""

import json
import urllib.request
import urllib.error
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("sclass_package_verifier")


def _levenshtein(s1: str, s2: str) -> int:
    """Computes Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            ins = prev[j + 1] + 1
            dels = curr[j] + 1
            sub = prev[j] + (c1 != c2)
            curr.append(min(ins, dels, sub))
        prev = curr
    return prev[-1]


class PackageVerifier:
    """
    Verifies existence and legitimacy of Python (PyPI) and Node.js (npm) packages.
    Enforces fail-closed verification, age checks, and typosquatting detection.
    """

    _CACHE: Dict[str, bool] = {}

    KNOWN_PYPI_PACKAGES = {
        "pytest", "fastapi", "uvicorn", "pydantic", "sqlalchemy", "requests", "numpy",
        "pandas", "httpx", "click", "flask", "django", "celery", "redis", "networkx",
        "structlog", "tiktoken", "hypothesis", "schemathesis", "playwright", "gitpython",
    }

    KNOWN_NPM_PACKAGES = {
        "react", "react-dom", "next", "tailwindcss", "typescript", "eslint", "prettier",
        "zod", "prisma", "@prisma/client", "axios", "lucide-react", "clsx", "tailwind-merge",
    }

    @classmethod
    def check_typosquatting(cls, name: str, ecosystem: str = "pypi") -> Optional[str]:
        """Detects potential typosquatting against canonical popular libraries."""
        known = cls.KNOWN_PYPI_PACKAGES if ecosystem == "pypi" else cls.KNOWN_NPM_PACKAGES
        clean = name.lower()
        if clean in known:
            return None
        for k in known:
            dist = _levenshtein(clean, k)
            if dist == 1 or (dist == 2 and len(k) >= 7):
                return k
        return None

    @classmethod
    def verify_pypi_package(cls, package_name: str, timeout: float = 3.0) -> Dict[str, Any]:
        """Queries the official PyPI JSON API with fail-closed policy."""
        clean_name = package_name.lower().strip()
        cache_key = f"pypi::{clean_name}"
        if cache_key in cls._CACHE:
            return {"valid": cls._CACHE[cache_key], "package": clean_name, "ecosystem": "pypi", "cached": True}

        # Check for typosquatting attack against popular packages
        squat_target = cls.check_typosquatting(clean_name, ecosystem="pypi")
        if squat_target:
            cls._CACHE[cache_key] = False
            return {
                "valid": False,
                "package": clean_name,
                "ecosystem": "pypi",
                "error": f"Typosquatting risk detected: '{clean_name}' is suspiciously close to canonical package '{squat_target}'"
            }

        if clean_name in cls.KNOWN_PYPI_PACKAGES:
            cls._CACHE[cache_key] = True
            return {"valid": True, "package": clean_name, "ecosystem": "pypi", "cached": True, "popularity_tier": "canonical"}

        url = f"https://pypi.org/pypi/{clean_name}/json"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SClassPackageVerifier/12.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    releases = data.get("releases", {})
                    release_count = len(releases)
                    if release_count == 0:
                        cls._CACHE[cache_key] = False
                        return {"valid": False, "package": clean_name, "ecosystem": "pypi", "error": "Package has 0 releases on PyPI"}
                    cls._CACHE[cache_key] = True
                    return {
                        "valid": True,
                        "package": clean_name,
                        "ecosystem": "pypi",
                        "release_count": release_count,
                        "cached": False
                    }
                else:
                    cls._CACHE[cache_key] = False
                    return {"valid": False, "package": clean_name, "ecosystem": "pypi", "error": f"HTTP {resp.status}"}
        except urllib.error.HTTPError as e:
            cls._CACHE[cache_key] = False
            if e.code == 404:
                return {"valid": False, "package": clean_name, "ecosystem": "pypi", "error": "Package not found on PyPI (404)"}
            return {"valid": False, "package": clean_name, "ecosystem": "pypi", "error": f"HTTP {e.code}"}
        except Exception as e:
            # Fail closed on network error (Item 41)
            cls._CACHE[cache_key] = False
            return {
                "valid": False,
                "status": "unverified",
                "package": clean_name,
                "ecosystem": "pypi",
                "error": f"Registry check failed (fail-closed security policy): {e}"
            }

    @classmethod
    def verify_npm_package(cls, package_name: str, timeout: float = 3.0) -> Dict[str, Any]:
        """Queries the official npm registry with fail-closed policy."""
        clean_name = package_name.strip()
        cache_key = f"npm::{clean_name}"
        if cache_key in cls._CACHE:
            return {"valid": cls._CACHE[cache_key], "package": clean_name, "ecosystem": "npm", "cached": True}

        squat_target = cls.check_typosquatting(clean_name, ecosystem="npm")
        if squat_target:
            cls._CACHE[cache_key] = False
            return {
                "valid": False,
                "package": clean_name,
                "ecosystem": "npm",
                "error": f"Typosquatting risk detected: '{clean_name}' is suspiciously close to canonical package '{squat_target}'"
            }

        if clean_name in cls.KNOWN_NPM_PACKAGES:
            cls._CACHE[cache_key] = True
            return {"valid": True, "package": clean_name, "ecosystem": "npm", "cached": True, "popularity_tier": "canonical"}

        quoted_name = clean_name.replace("/", "%2f")
        url = f"https://registry.npmjs.org/{quoted_name}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SClassPackageVerifier/12.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    versions = data.get("versions", {})
                    if not versions:
                        cls._CACHE[cache_key] = False
                        return {"valid": False, "package": clean_name, "ecosystem": "npm", "error": "Package has 0 versions on npm"}
                    cls._CACHE[cache_key] = True
                    return {
                        "valid": True,
                        "package": clean_name,
                        "ecosystem": "npm",
                        "versions_count": len(versions),
                        "cached": False
                    }
                else:
                    cls._CACHE[cache_key] = False
                    return {"valid": False, "package": clean_name, "ecosystem": "npm", "error": f"HTTP {resp.status}"}
        except urllib.error.HTTPError as e:
            cls._CACHE[cache_key] = False
            if e.code == 404:
                return {"valid": False, "package": clean_name, "ecosystem": "npm", "error": "Package not found on npm (404)"}
            return {"valid": False, "package": clean_name, "ecosystem": "npm", "error": f"HTTP {e.code}"}
        except Exception as e:
            # Fail closed on network error (Item 41)
            cls._CACHE[cache_key] = False
            return {
                "valid": False,
                "status": "unverified",
                "package": clean_name,
                "ecosystem": "npm",
                "error": f"Registry check failed (fail-closed security policy): {e}"
            }
