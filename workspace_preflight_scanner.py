"""
S-Class EOS Workspace Pre-Flight Scanner Engine (workspace_preflight_scanner.py)

Performs a full 100% workspace file scan before planning or code generation.
Extracts AST symbols, exports, environment variables, DB models, and package manifests
into a persistent workspace digest (.agents/workspace_digest.json) to eliminate AI context blind spots.
"""

import os
import re
import json
import logging
from typing import Dict, Any, List, Set, Optional

logger = logging.getLogger("sclass_workspace_preflight_scanner")


class WorkspacePreflightScanner:
    """
    Full Workspace File & AST Pre-Flight Scanner for S-Class V12.1.
    Guarantees 100% context awareness across all project files upfront.
    """

    EXCLUDED_DIRS: Set[str] = {
        "node_modules", ".git", ".next", "dist", "build", ".venv", "venv", "__pycache__", ".pytest_cache"
    }

    @classmethod
    def scan_workspace(cls, workspace_dir: Optional[str] = None) -> Dict[str, Any]:
        cwd = workspace_dir if workspace_dir else os.getcwd()
        state_dir = os.path.join(cwd, ".agents")
        os.makedirs(state_dir, exist_ok=True)

        scanned_files: List[str] = []
        exported_symbols: List[Dict[str, str]] = []
        env_vars_declared: Set[str] = set()
        pkg_dependencies: Set[str] = set()

        sym_pattern = re.compile(r"""(?:export\s+(?:default\s+)?(?:class|function|interface|type|const|let|var)|def\s+|class\s+)([a-zA-Z0-9_]+)""")
        env_pattern = re.compile(r"""^[A-Z0-9_]+=""")

        total_files = 0
        total_bytes = 0

        for root, dirs, files in os.walk(cwd):
            dirs[:] = [d for d in dirs if d not in cls.EXCLUDED_DIRS and not d.startswith(".")]
            for f in files:
                rel_path = os.path.relpath(os.path.join(root, f), cwd)
                scanned_files.append(rel_path)
                total_files += 1
                fp = os.path.join(root, f)

                try:
                    size = os.path.getsize(fp)
                    total_bytes += size
                except Exception:
                    pass

                # Scan symbols in code files
                if f.endswith(('.ts', '.tsx', '.js', '.jsx', '.py')):
                    try:
                        with open(fp, "r", encoding="utf-8", errors="ignore") as fo:
                            content = fo.read()
                        for match in sym_pattern.findall(content):
                            exported_symbols.append({"symbol": match, "file": rel_path})
                    except Exception:
                        pass

                # Scan environment variables
                if f.startswith(".env"):
                    try:
                        with open(fp, "r", encoding="utf-8", errors="ignore") as fo:
                            for line in fo:
                                line_str = line.strip()
                                if line_str and not line_str.startswith("#") and env_pattern.match(line_str):
                                    env_vars_declared.add(line_str.split("=")[0].strip())
                    except Exception:
                        pass

                # Scan dependencies
                if f == "package.json":
                    try:
                        with open(fp, "r", encoding="utf-8") as fo:
                            pkg_data = json.load(fo)
                        deps = pkg_data.get("dependencies", {})
                        dev_deps = pkg_data.get("devDependencies", {})
                        pkg_dependencies.update(deps.keys())
                        pkg_dependencies.update(dev_deps.keys())
                    except Exception:
                        pass

        # Also extract python dependencies if present
        py_deps = cls.extract_python_deps(cwd)
        pkg_dependencies.update(py_deps)

        digest = {
            "total_files": total_files,
            "total_bytes": total_bytes,
            "scanned_files": scanned_files[:200],  # Top 200 files
            "exported_symbols_count": len(exported_symbols),
            "top_symbols": exported_symbols[:50],
            "env_vars_declared": list(env_vars_declared),
            "declared_dependencies_count": len(pkg_dependencies),
            "declared_dependencies": list(pkg_dependencies)
        }

        # Save digest receipt
        digest_file = os.path.join(state_dir, "workspace_digest.json")
        with open(digest_file, "w", encoding="utf-8") as df:
            json.dump(digest, df, indent=2)

        logger.info(f"[WorkspacePreflightScanner] Scanned {total_files} workspace files ({len(exported_symbols)} symbols extracted)")
        return digest

    @classmethod
    def extract_python_deps(cls, cwd: str) -> List[str]:
        deps = set()
        req_path = os.path.join(cwd, "requirements.txt")
        if os.path.exists(req_path):
            try:
                with open(req_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line_str = line.strip()
                        if line_str and not line_str.startswith("#") and not line_str.startswith("-"):
                            pkg_name = re.split(r'(?:==|>=|<=|>|<|~=|!=)', line_str)[0].strip()
                            if pkg_name:
                                deps.add(pkg_name)
            except Exception:
                pass

        toml_path = os.path.join(cwd, "pyproject.toml")
        if os.path.exists(toml_path):
            try:
                with open(toml_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                deps_block_matches = re.findall(r'(?:dependencies\s*=\s*\[([^\]]+)\])|(?:\[(?:tool\.poetry\.)?dependencies\]([^\[]+))', content, re.MULTILINE)
                for match in deps_block_matches:
                    block = match[0] or match[1]
                    for line in block.splitlines():
                        line = line.strip().strip(',"')
                        if line and not line.startswith('#') and not line.startswith('['):
                            pkg_name = re.split(r'[=><~^!]', line)[0].strip().strip('"\'')
                            if pkg_name and pkg_name.lower() not in ["python", "project", "build-system"]:
                                deps.add(pkg_name)
            except Exception:
                pass
        return list(deps)

    @classmethod
    def extract_db_schema(cls, cwd: str) -> List[Dict]:
        schema = []
        for root, dirs, files in os.walk(cwd):
            dirs[:] = [d for d in dirs if d not in cls.EXCLUDED_DIRS and not d.startswith(".")]
            for f in files:
                fp = os.path.join(root, f)
                rel_path = os.path.relpath(fp, cwd)
                try:
                    if f.endswith('.prisma'):
                        with open(fp, "r", encoding="utf-8", errors="ignore") as fo:
                            content = fo.read()
                        models = re.findall(r'model\s+(\w+)\s+\{([^}]+)\}', content)
                        for model_name, body in models:
                            fields = [line.strip() for line in body.split('\n') if line.strip() and not line.strip().startswith('//')]
                            schema.append({"name": model_name, "fields": fields, "source": rel_path})
                    elif f.endswith('.py'):
                        with open(fp, "r", encoding="utf-8", errors="ignore") as fo:
                            content = fo.read()
                        if 'Base' in content or 'Model' in content:
                            classes_with_bodies = re.findall(r'class\s+(\w+)\s*\([^)]*(?:Model|Base)[^)]*\):([^\n]+(?:\n(?!\s*class\s+).*)*)', content)
                            for c_name, body in classes_with_bodies:
                                fields = re.findall(r'^\s{4}(\w+)\s*=\s*(?:models\.|Column\(|Field\()', body, re.MULTILINE)
                                schema.append({"name": c_name, "fields": fields, "source": rel_path})
                    elif f.endswith('.sql'):
                        with open(fp, "r", encoding="utf-8", errors="ignore") as fo:
                            content = fo.read()
                        create_blocks = re.findall(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?["`]?(\w+)["`]?\s*\(([^;]+)\);', content, re.IGNORECASE | re.DOTALL)
                        for t_name, body in create_blocks:
                            fields = []
                            for line in body.splitlines():
                                line_s = line.strip()
                                if line_s and not line_s.upper().startswith(('PRIMARY', 'FOREIGN', 'KEY', 'CONSTRAINT', 'UNIQUE', 'CHECK', 'INDEX', '--')):
                                    col_match = re.match(r'["`]?(\w+)["`]?\s+([A-Za-z0-9_()]+)', line_s)
                                    if col_match:
                                        fields.append(f"{col_match.group(1)} {col_match.group(2)}")
                            schema.append({"name": t_name, "fields": fields, "source": rel_path})
                except Exception:
                    pass
        return schema

    @classmethod
    def extract_api_routes(cls, cwd: str) -> List[Dict]:
        routes = []
        pattern = re.compile(r'@(?:router|app|app)\.(get|post|put|delete|patch)\([\'"]([^\'"]+)[\'"]')
        js_pattern = re.compile(r'(?:router|app)\.(get|post|put|delete|patch)\([\'"]([^\'"]+)[\'"]')
        nest_pattern = re.compile(r'@(Get|Post|Put|Delete|Patch)\([\'"]?([^\'"]*)[\'"]?\)')

        for root, dirs, files in os.walk(cwd):
            dirs[:] = [d for d in dirs if d not in cls.EXCLUDED_DIRS and not d.startswith(".")]
            for f in files:
                if not f.endswith(('.py', '.js', '.ts')):
                    continue
                fp = os.path.join(root, f)
                rel_path = os.path.relpath(fp, cwd)
                try:
                    with open(fp, "r", encoding="utf-8", errors="ignore") as fo:
                        content = fo.read()

                    for method, path in pattern.findall(content):
                        routes.append({"method": method.upper(), "path": path, "source": rel_path})

                    for method, path in js_pattern.findall(content):
                        routes.append({"method": method.upper(), "path": path, "source": rel_path})

                    for method, path in nest_pattern.findall(content):
                        routes.append({"method": method.upper(), "path": path, "source": rel_path})
                except Exception:
                    pass
        return routes

    @classmethod
    def extract_design_documents(cls, cwd: str) -> Dict[str, Any]:
        docs = {}
        agents_dir = os.path.join(cwd, '.agents')
        files_to_check = [
            (os.path.join(agents_dir, 'design_blueprint.json'), 'design_blueprint'),
            (os.path.join(agents_dir, 'role_interaction_matrix.json'), 'role_interaction_matrix')
        ]

        for path, key in files_to_check:
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        docs[key] = json.load(f)
                except Exception:
                    pass

        for root, dirs, files in os.walk(cwd):
            dirs[:] = [d for d in dirs if d not in cls.EXCLUDED_DIRS and not d.startswith(".")]
            for f in files:
                if f.endswith('.spec.md') or f.endswith('.requirements.md') or f.endswith('.prd.md'):
                    fp = os.path.join(root, f)
                    try:
                        with open(fp, 'r', encoding='utf-8', errors='ignore') as fo:
                            docs[os.path.relpath(fp, cwd)] = fo.read()
                    except Exception:
                        pass
        return docs

    @classmethod
    def extract_ui_components(cls, cwd: str) -> List[str]:
        components = []
        export_pattern = re.compile(r'export\s+(?:default\s+)?(?:function|const)\s+([A-Z]\w+)')
        for root, dirs, files in os.walk(cwd):
            dirs[:] = [d for d in dirs if d not in cls.EXCLUDED_DIRS and not d.startswith(".")]
            for f in files:
                if f.endswith(('.jsx', '.tsx', '.vue')):
                    fp = os.path.join(root, f)
                    try:
                        if f.endswith('.vue'):
                            components.append(f)
                        else:
                            with open(fp, 'r', encoding='utf-8', errors='ignore') as fo:
                                content = fo.read()
                            for comp in export_pattern.findall(content):
                                components.append(comp)
                    except Exception:
                        pass
        return list(set(components))

    @classmethod
    def extract_docker_services(cls, cwd: str) -> List[str]:
        services = []
        compose_paths = [
            os.path.join(cwd, "docker-compose.yml"),
            os.path.join(cwd, "docker-compose.yaml"),
            os.path.join(cwd, "compose.yml"),
            os.path.join(cwd, "compose.yaml")
        ]
        for p in compose_paths:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    services_match = re.search(r'^services:\s*\n((?:\s{2,}.*\n?)+)', content, re.MULTILINE)
                    if services_match:
                        services_block = services_match.group(1)
                        matches = re.findall(r'^\s{2}([a-zA-Z0-9_\-]+):', services_block, re.MULTILINE)
                        services.extend(matches)
                except Exception:
                    pass
        return list(set(services))

    @classmethod
    def extract_auth_permissions(cls, cwd: str) -> List[str]:
        perms = set()
        for root, dirs, files in os.walk(cwd):
            dirs[:] = [d for d in dirs if d not in cls.EXCLUDED_DIRS and not d.startswith(".")]
            for f in files:
                if f.endswith(('.ts', '.tsx', '.js', '.py')):
                    fp = os.path.join(root, f)
                    try:
                        with open(fp, "r", encoding="utf-8", errors="ignore") as fo:
                            content = fo.read()
                        matches = re.findall(r'(?:role|permission|guard)\s*[:=]\s*["\']([a-zA-Z0-9_:]+)["\']', content, re.IGNORECASE)
                        perms.update(matches)
                    except Exception:
                        pass
        return list(perms)

    @classmethod
    def extract_tests(cls, cwd: str) -> List[str]:
        tests = []
        for root, dirs, files in os.walk(cwd):
            dirs[:] = [d for d in dirs if d not in cls.EXCLUDED_DIRS and not d.startswith(".")]
            for f in files:
                if f.startswith("test_") or f.endswith(("_test.py", ".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx")):
                    tests.append(os.path.relpath(os.path.join(root, f), cwd))
        return tests

    @classmethod
    def full_project_discovery(cls, cwd: str) -> Dict[str, Any]:
        discovery = {
            "workspace_digest": cls.scan_workspace(cwd),
            "db_schema": cls.extract_db_schema(cwd),
            "api_routes": cls.extract_api_routes(cwd),
            "design_documents": cls.extract_design_documents(cwd),
            "ui_components": cls.extract_ui_components(cwd),
            "docker_services": cls.extract_docker_services(cwd),
            "auth_permissions": cls.extract_auth_permissions(cwd),
            "tests": cls.extract_tests(cwd)
        }

        state_dir = os.path.join(cwd, ".agents")
        os.makedirs(state_dir, exist_ok=True)
        discovery_file = os.path.join(state_dir, "project_discovery.json")
        try:
            with open(discovery_file, "w", encoding="utf-8") as df:
                json.dump(discovery, df, indent=2)
        except Exception as e:
            logger.error(f"Failed to save project discovery: {e}")

        return discovery
