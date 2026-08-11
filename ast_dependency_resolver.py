"""
S-Class EOS AST Dependency Resolver Engine (ast_dependency_resolver.py)

Scans generated JavaScript, TypeScript, React, and Python source code for imported modules.
Automatically updates package.json or requirements.txt to eliminate 'Cannot find module' crashes.
"""

import os
import re
import sys
import json
import logging
from typing import List, Set, Dict, Any, Optional

logger = logging.getLogger("sclass_ast_dependency_resolver")

COMMON_NPM_VERSIONS: Dict[str, str] = {
    "lucide-react": "^0.450.0",
    "framer-motion": "^11.11.0",
    "clsx": "^2.1.1",
    "tailwind-merge": "^2.5.4",
    "recharts": "^2.13.0",
    "axios": "^1.7.7",
    "express": "^4.21.1",
    "cors": "^2.8.5",
    "zod": "^3.23.8",
    "dotenv": "^16.4.5",
    "react-router-dom": "^6.27.0",
    "next": "^14.2.15",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
}

# Standard Library Modules Exclusion Set
STDLIB_PYTHON_MODULES: Set[str] = set(getattr(sys, "stdlib_module_names", {
    "abc", "argparse", "array", "ast", "asyncio", "base64", "binascii", "bisect", "builtins",
    "bz2", "calendar", "collections", "concurrent", "configparser", "contextlib", "copy",
    "csv", "ctypes", "datetime", "decimal", "difflib", "dis", "doctest", "email", "enum",
    "errno", "filecmp", "fnmatch", "functools", "gc", "getopt", "getpass", "glob", "gzip",
    "hashlib", "heapq", "hmac", "html", "http", "importlib", "inspect", "io", "itertools",
    "json", "logging", "math", "multiprocessing", "operator", "os", "pathlib", "pickle",
    "pkgutil", "platform", "pprint", "random", "re", "select", "shutil", "signal", "socket",
    "sqlite3", "ssl", "stat", "string", "struct", "subprocess", "sys", "tempfile", "textwrap",
    "threading", "time", "timeit", "tkinter", "traceback", "types", "typing", "unittest",
    "urllib", "uuid", "warnings", "weakref", "xml", "zipfile", "zlib"
}))


class ASTDependencyResolver:
    """
    Automated Dependency Scanner and Package Injector for S-Class EOS V12.
    Ensures zero undeclared module import errors.
    """

    @classmethod
    def resolve_workspace_dependencies(cls, workspace_dir: Optional[str] = None) -> Dict[str, Any]:
        cwd = workspace_dir if workspace_dir else os.getcwd()
        frontend_dir = os.path.join(cwd, "frontend")
        backend_dir = os.path.join(cwd, "backend")

        missing_npm_added = []
        missing_pip_added = []

        # 1. Resolve Frontend / Node.js Dependencies (check frontend_dir, backend_dir, and cwd)
        for node_dir in [frontend_dir, backend_dir, cwd]:
            if os.path.exists(node_dir):
                pkg_file = os.path.join(node_dir, "package.json")
                if os.path.exists(pkg_file):
                    injected = cls._sync_npm_dependencies(node_dir, pkg_file)
                    missing_npm_added.extend(injected)

        # 2. Resolve Python Dependencies (check backend_dir and cwd)
        for py_dir in [backend_dir, cwd]:
            if os.path.exists(py_dir):
                req_file = os.path.join(py_dir, "requirements.txt")
                if os.path.exists(req_file):
                    injected = cls._sync_pip_dependencies(py_dir, req_file)
                    missing_pip_added.extend(injected)

        # Deduplicate results
        missing_npm_added = list(dict.fromkeys(missing_npm_added))
        missing_pip_added = list(dict.fromkeys(missing_pip_added))

        logger.info(f"[ASTDependencyResolver] Resolved missing dependencies: NPM={missing_npm_added}, PIP={missing_pip_added}")
        return {
            "npm_packages_injected": missing_npm_added,
            "pip_packages_injected": missing_pip_added
        }

    @classmethod
    def _sync_npm_dependencies(cls, search_dir: str, pkg_file: str) -> List[str]:
        imported_modules: Set[str] = set()

        import_pattern = re.compile(r"""(?:import|export)\s+(?:.*?from\s+)?['"]([^'".\///][^'"]*)['"]""")
        require_pattern = re.compile(r"""require\s*\(\s*['"]([^'".\///][^'"]*)['"]\s*\)""")

        for root, _, files in os.walk(search_dir):
            if any(ignored in root for ignored in ["node_modules", ".next", "dist", "build", ".git"]):
                continue
            for f in files:
                if f.endswith(('.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs')):
                    fp = os.path.join(root, f)
                    try:
                        with open(fp, "r", encoding="utf-8", errors="ignore") as file_obj:
                            content = file_obj.read()
                        
                        for match in import_pattern.findall(content):
                            pkg_name = cls._extract_npm_package_name(match)
                            if pkg_name:
                                imported_modules.add(pkg_name)
                                
                        for match in require_pattern.findall(content):
                            pkg_name = cls._extract_npm_package_name(match)
                            if pkg_name:
                                imported_modules.add(pkg_name)
                    except Exception:
                        pass

        # Load package.json
        try:
            with open(pkg_file, "r", encoding="utf-8") as pf:
                pkg_data = json.load(pf)
        except Exception:
            return []

        deps = pkg_data.get("dependencies", {})
        dev_deps = pkg_data.get("devDependencies", {})
        all_declared = set(deps.keys()).union(set(dev_deps.keys()))

        builtin_node = {"fs", "path", "http", "https", "os", "events", "util", "stream", "crypto", "child_process", "url"}
        
        missing = [m for m in imported_modules if m not in all_declared and m not in builtin_node]
        if not missing:
            return []

        for m in missing:
            ver = COMMON_NPM_VERSIONS.get(m, "latest")
            deps[m] = ver

        pkg_data["dependencies"] = deps

        with open(pkg_file, "w", encoding="utf-8") as pf:
            json.dump(pkg_data, pf, indent=2)

        return missing

    @classmethod
    def _extract_npm_package_name(cls, raw_path: str) -> Optional[str]:
        if not raw_path or raw_path.startswith(".") or raw_path.startswith("/"):
            return None
        parts = raw_path.split("/")
        if raw_path.startswith("@"):
            if len(parts) >= 2:
                return f"{parts[0]}/{parts[1]}"
            return None
        return parts[0]

    @classmethod
    def _sync_pip_dependencies(cls, search_dir: str, req_file: str) -> List[str]:
        imported_py: Set[str] = set()

        # Robust Python import regexes (only capture root module name from top-level import/from statements)
        from_py_pattern = re.compile(r"^\s*from\s+([a-zA-Z0-9_]+)", re.MULTILINE)
        import_py_pattern = re.compile(r"^\s*import\s+([a-zA-Z0-9_]+)", re.MULTILINE)

        # Discover all local Python module & directory names in search_dir to prevent local files from being treated as pip packages
        local_modules: Set[str] = set()
        for root, dirs, files in os.walk(search_dir):
            if any(ignored in root for ignored in ["venv", ".venv", "__pycache__", ".git"]):
                continue
            for f in files:
                if f.endswith(".py"):
                    local_modules.add(f[:-3].lower())
            for d in dirs:
                local_modules.add(d.lower())

        for root, _, files in os.walk(search_dir):
            if any(ignored in root for ignored in ["venv", ".venv", "__pycache__", ".git"]):
                continue
            for f in files:
                if f.endswith(".py"):
                    fp = os.path.join(root, f)
                    try:
                        with open(fp, "r", encoding="utf-8", errors="ignore") as file_obj:
                            content = file_obj.read()
                        
                        for match in from_py_pattern.findall(content):
                            imported_py.add(match)
                        for match in import_py_pattern.findall(content):
                            imported_py.add(match)
                    except Exception:
                        pass

        # Load requirements.txt
        try:
            with open(req_file, "r", encoding="utf-8") as rf:
                declared = set(line.strip().split("==")[0].split(">=")[0].split("<=")[0].lower() for line in rf if line.strip() and not line.startswith("#"))
        except Exception:
            return []

        pip_mapping = {
            "fastapi": "fastapi",
            "uvicorn": "uvicorn",
            "pydantic": "pydantic",
            "sqlalchemy": "sqlalchemy",
            "requests": "requests",
            "flask": "flask",
            "dotenv": "python-dotenv",
            "corsheaders": "django-cors-headers",
            "pytest": "pytest",
            "playwright": "playwright",
            "pil": "pillow",
            "cv2": "opencv-python",
            "bs4": "beautifulsoup4",
            "yaml": "pyyaml",
            "jwt": "pyjwt"
        }

        missing = []
        for mod in imported_py:
            mod_lower = mod.lower()
            # Skip if stdlib module or local workspace file/module
            if mod_lower in STDLIB_PYTHON_MODULES or mod_lower in local_modules:
                continue
            
            pip_pkg = pip_mapping.get(mod_lower, mod_lower)
            if pip_pkg not in declared and pip_pkg not in missing:
                missing.append(pip_pkg)

        if missing:
            with open(req_file, "a", encoding="utf-8") as rf:
                for pkg in missing:
                    rf.write(f"{pkg}\n")

        return missing
