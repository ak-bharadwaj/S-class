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


class PackageVerifier:
    """
    Verifies existence and legitimacy of Python (PyPI) and Node.js (npm) packages.
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
    def verify_pypi_package(cls, package_name: str, timeout: float = 3.0) -> Dict[str, Any]:
        """Queries the official PyPI JSON API."""
        clean_name = package_name.lower().strip()
        cache_key = f"pypi::{clean_name}"
        if cache_key in cls._CACHE:
            return {"valid": cls._CACHE[cache_key], "package": clean_name, "ecosystem": "pypi", "cached": True}

        if clean_name in cls.KNOWN_PYPI_PACKAGES:
            cls._CACHE[cache_key] = True
            return {"valid": True, "package": clean_name, "ecosystem": "pypi", "cached": True}

        url = f"https://pypi.org/pypi/{clean_name}/json"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SClassPackageVerifier/12.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                exists = resp.status == 200
                cls._CACHE[cache_key] = exists
                return {"valid": exists, "package": clean_name, "ecosystem": "pypi", "cached": False}
        except urllib.error.HTTPError as e:
            if e.code == 404:
                cls._CACHE[cache_key] = False
                return {"valid": False, "package": clean_name, "ecosystem": "pypi", "error": "Package not found on PyPI (404)"}
            return {"valid": False, "package": clean_name, "ecosystem": "pypi", "error": f"HTTP {e.code}"}
        except Exception as e:
            # Fallback if network unreachable
            return {"valid": True, "package": clean_name, "ecosystem": "pypi", "warning": f"Network check skipped: {e}"}

    @classmethod
    def verify_npm_package(cls, package_name: str, timeout: float = 3.0) -> Dict[str, Any]:
        """Queries the official npm registry."""
        clean_name = package_name.strip()
        cache_key = f"npm::{clean_name}"
        if cache_key in cls._CACHE:
            return {"valid": cls._CACHE[cache_key], "package": clean_name, "ecosystem": "npm", "cached": True}

        if clean_name in cls.KNOWN_NPM_PACKAGES:
            cls._CACHE[cache_key] = True
            return {"valid": True, "package": clean_name, "ecosystem": "npm", "cached": True}

        # Handle scoped packages (e.g. @prisma/client -> @prisma%2fclient)
        quoted_name = clean_name.replace("/", "%2f")
        url = f"https://registry.npmjs.org/{quoted_name}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SClassPackageVerifier/12.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                exists = resp.status == 200
                cls._CACHE[cache_key] = exists
                return {"valid": exists, "package": clean_name, "ecosystem": "npm", "cached": False}
        except urllib.error.HTTPError as e:
            if e.code == 404:
                cls._CACHE[cache_key] = False
                return {"valid": False, "package": clean_name, "ecosystem": "npm", "error": "Package not found on npm (404)"}
            return {"valid": False, "package": clean_name, "ecosystem": "npm", "error": f"HTTP {e.code}"}
        except Exception as e:
            return {"valid": True, "package": clean_name, "ecosystem": "npm", "warning": f"Network check skipped: {e}"}
