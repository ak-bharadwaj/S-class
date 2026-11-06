#!/usr/bin/env python3
"""
S-CLASS Block 2 — TASK OSS-SWEEP-R32: Stage A Candidate Resolver
Generates product/oss-evidence/sweep/candidates.yaml

Enforces:
1. One entry per candidate:
   id, display_name, phase_tags, canonical_repo, ecosystems, why_listed,
   is_fork, parent_repo, archived, moved_to, identity_checks{pkg_home_url_matches_repo}
2. Follow redirects and record canonical repo.
3. Record archived repos and their successors (both recorded).
4. Name collision check: compare PyPI/npm/crate home URL to canonical repo.
5. Negative controls included and flagged.
"""

import os
import json
import urllib.request
import urllib.parse
import urllib.error
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SWEEP_DIR = os.path.join(ROOT, "product", "oss-evidence", "sweep")
RAW_DIR = os.path.join(SWEEP_DIR, "raw")
CANDIDATES_YAML = os.path.join(SWEEP_DIR, "candidates.yaml")

os.makedirs(RAW_DIR, exist_ok=True)

USER_AGENT = "S-Class-OSS-Sweep-R32 (ak-bharadwaj/S-class)"

def cached_get(url, cache_prefix="reg"):
    clean_name = "".join(c if c.isalnum() else "_" for c in url)[-60:]
    cache_path = os.path.join(RAW_DIR, f"{cache_prefix}_{clean_name}.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read().decode("utf-8")
            h = dict(resp.headers)
            res = {"status": resp.status, "body": data, "headers": h}
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(res, f)
            return res
    except urllib.error.HTTPError as e:
        res = {"status": e.code, "body": e.read().decode("utf-8", errors="replace"), "headers": dict(e.headers)}
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(res, f)
        return res
    except Exception as e:
        return {"status": 0, "body": str(e), "headers": {}}

def check_identity(ecosystems, canonical_repo):
    """
    Check if registry package home URL points to canonical_repo.
    Returns: True / False / "NA"
    """
    if not canonical_repo or canonical_repo.startswith("closed/") or canonical_repo.startswith("spec/"):
        return "NA"
    
    canon_lower = canonical_repo.lower()

    # 1. PyPI
    pypi_pkgs = ecosystems.get("pypi", [])
    for pkg in pypi_pkgs:
        url = f"https://pypi.org/pypi/{pkg}/json"
        res = cached_get(url, cache_prefix=f"pypi_{pkg}")
        if res["status"] == 200:
            try:
                d = json.loads(res["body"])
                info = d.get("info", {})
                urls = []
                if info.get("home_page"):
                    urls.append(info.get("home_page"))
                if info.get("project_urls"):
                    for _, v in info.get("project_urls").items():
                        if v:
                            urls.append(v)
                matches = any(canon_lower in u.lower() for u in urls)
                return True if matches else False
            except Exception:
                pass
        elif res["status"] == 404:
            return "NA"

    # 2. npm
    npm_pkgs = ecosystems.get("npm", [])
    for pkg in npm_pkgs:
        encoded_pkg = urllib.parse.quote(pkg, safe="@")
        url = f"https://registry.npmjs.org/{encoded_pkg}"
        res = cached_get(url, cache_prefix=f"npm_{pkg.replace('/', '_')}")
        if res["status"] == 200:
            try:
                d = json.loads(res["body"])
                repo = d.get("repository", {})
                repo_url = repo.get("url") if isinstance(repo, dict) else str(repo)
                hp = d.get("homepage", "")
                urls = [str(repo_url), str(hp)]
                matches = any(canon_lower in u.lower() for u in urls if u)
                return True if matches else False
            except Exception:
                pass
        elif res["status"] == 404:
            return "NA"

    # 3. crates
    crates_pkgs = ecosystems.get("crates", [])
    for pkg in crates_pkgs:
        url = f"https://crates.io/api/v1/crates/{pkg}"
        res = cached_get(url, cache_prefix=f"crate_{pkg}")
        if res["status"] == 200:
            try:
                d = json.loads(res["body"])
                c = d.get("crate", {})
                urls = [str(c.get("repository")), str(c.get("homepage"))]
                matches = any(canon_lower in u.lower() for u in urls if u)
                return True if matches else False
            except Exception:
                pass
        elif res["status"] == 404:
            return "NA"

    return "NA"

# Candidate definitions
RAW_CANDIDATES = [
    # --- P0 Intent ---
    {
        "id": "bmad-method", "display_name": "BMAD-METHOD", "phase_tags": ["P0", "X-workflow"],
        "canonical_repo": "bmad-code-org/BMAD-METHOD", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "madr", "display_name": "MADR", "phase_tags": ["P0"],
        "canonical_repo": "adr/madr", "ecosystems": {"npm": ["madr"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "adr-tools", "display_name": "adr-tools", "phase_tags": ["P0"],
        "canonical_repo": "npryce/adr-tools", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "log4brains", "display_name": "log4brains", "phase_tags": ["P0"],
        "canonical_repo": "thomvaill/log4brains", "ecosystems": {"npm": ["log4brains"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "behave", "display_name": "behave", "phase_tags": ["P0"],
        "canonical_repo": "behave/behave", "ecosystems": {"pypi": ["behave"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "pytest-bdd", "display_name": "pytest-bdd", "phase_tags": ["P0"],
        "canonical_repo": "pytest-dev/pytest-bdd", "ecosystems": {"pypi": ["pytest-bdd"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "cucumber-gherkin", "display_name": "cucumber gherkin parser", "phase_tags": ["P0"],
        "canonical_repo": "cucumber/gherkin", "ecosystems": {"npm": ["@cucumber/gherkin"], "pypi": ["gherkin-official"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    # P0 Discovery additions
    {
        "id": "mocha", "display_name": "Mocha", "phase_tags": ["P0"],
        "canonical_repo": "mochajs/mocha", "ecosystems": {"npm": ["mocha"]},
        "why_listed": "https://api.github.com/search/repositories?q=topic:bdd+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "robotframework", "display_name": "Robot Framework", "phase_tags": ["P0"],
        "canonical_repo": "robotframework/robotframework", "ecosystems": {"pypi": ["robotframework"]},
        "why_listed": "https://api.github.com/search/repositories?q=topic:bdd+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "quick", "display_name": "Quick", "phase_tags": ["P0"],
        "canonical_repo": "Quick/Quick", "ecosystems": {"none": []},
        "why_listed": "https://api.github.com/search/repositories?q=topic:bdd+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "ginkgo", "display_name": "Ginkgo", "phase_tags": ["P0"],
        "canonical_repo": "onsi/ginkgo", "ecosystems": {"go": ["github.com/onsi/ginkgo/v2"]},
        "why_listed": "https://api.github.com/search/repositories?q=topic:bdd+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "karate", "display_name": "Karate", "phase_tags": ["P0"],
        "canonical_repo": "karatelabs/karate", "ecosystems": {"none": []},
        "why_listed": "https://api.github.com/search/repositories?q=topic:bdd+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },

    # --- P1 Discovery ---
    {
        "id": "ripgrep", "display_name": "ripgrep", "phase_tags": ["P1"],
        "canonical_repo": "BurntSushi/ripgrep", "ecosystems": {"crates": ["ripgrep"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "universal-ctags", "display_name": "universal-ctags", "phase_tags": ["P1"],
        "canonical_repo": "universal-ctags/ctags", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "zoekt", "display_name": "zoekt", "phase_tags": ["P1"],
        "canonical_repo": "sourcegraph/zoekt", "ecosystems": {"go": ["github.com/sourcegraph/zoekt"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "scip-python", "display_name": "scip-python", "phase_tags": ["P1"],
        "canonical_repo": "sourcegraph/scip-python", "ecosystems": {"npm": ["@sourcegraph/scip-python"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "scip-typescript", "display_name": "scip-typescript", "phase_tags": ["P1"],
        "canonical_repo": "sourcegraph/scip-typescript", "ecosystems": {"npm": ["@sourcegraph/scip-typescript"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "kythe", "display_name": "Kythe", "phase_tags": ["P1"],
        "canonical_repo": "kythe/kythe", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "grep-ast", "display_name": "grep-ast", "phase_tags": ["P1"],
        "canonical_repo": "paul-gauthier/grep-ast", "ecosystems": {"pypi": ["grep-ast"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "joern", "display_name": "Joern", "phase_tags": ["P1", "X-graph"],
        "canonical_repo": "joernio/joern", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "aider-repo-map", "display_name": "Aider repo-map", "phase_tags": ["P1", "P6"],
        "canonical_repo": "paul-gauthier/aider", "ecosystems": {"pypi": ["aider-chat"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    # P1 Discovery additions
    {
        "id": "graphify", "display_name": "Graphify", "phase_tags": ["P1", "X-graph"],
        "canonical_repo": "Graphify-Labs/graphify", "ecosystems": {"none": []},
        "why_listed": "https://api.github.com/search/repositories?q=topic:code-search+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "xerj", "display_name": "xerj", "phase_tags": ["P1"],
        "canonical_repo": "xerj-org/xerj", "ecosystems": {"none": []},
        "why_listed": "https://api.github.com/search/repositories?q=topic:code-search+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "claude-context", "display_name": "claude-context", "phase_tags": ["P1"],
        "canonical_repo": "zilliztech/claude-context", "ecosystems": {"npm": ["claude-context"]},
        "why_listed": "https://api.github.com/search/repositories?q=topic:code-search+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "semble", "display_name": "semble", "phase_tags": ["P1"],
        "canonical_repo": "MinishLab/semble", "ecosystems": {"none": []},
        "why_listed": "https://api.github.com/search/repositories?q=topic:code-search+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "exa-mcp-server", "display_name": "exa-mcp-server", "phase_tags": ["P1"],
        "canonical_repo": "exa-labs/exa-mcp-server", "ecosystems": {"npm": ["exa-mcp-server"]},
        "why_listed": "https://api.github.com/search/repositories?q=topic:code-search+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },

    # --- P2 Requirements ---
    {
        "id": "strictdoc", "display_name": "StrictDoc", "phase_tags": ["P2"],
        "canonical_repo": "strictdoc-project/strictdoc", "ecosystems": {"pypi": ["strictdoc"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "sphinx-needs", "display_name": "Sphinx-needs", "phase_tags": ["P2"],
        "canonical_repo": "useblocks/sphinx-needs", "ecosystems": {"pypi": ["sphinx-needs"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "doorstop", "display_name": "Doorstop", "phase_tags": ["P2"],
        "canonical_repo": "doorstop-dev/doorstop", "ecosystems": {"pypi": ["doorstop"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "openfasttrace", "display_name": "OpenFastTrace", "phase_tags": ["P2"],
        "canonical_repo": "itsallcode/openfasttrace", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "spectral", "display_name": "Spectral", "phase_tags": ["P2"],
        "canonical_repo": "stoplightio/spectral", "ecosystems": {"npm": ["@stoplight/spectral-cli"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "openapi-spec-validator", "display_name": "openapi-spec-validator", "phase_tags": ["P2"],
        "canonical_repo": "python-openapi/openapi-spec-validator", "ecosystems": {"pypi": ["openapi-spec-validator"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "asyncapi-parser", "display_name": "AsyncAPI parser", "phase_tags": ["P2"],
        "canonical_repo": "asyncapi/parser-js", "ecosystems": {"npm": ["@asyncapi/parser"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "reqif", "display_name": "ReqIF libraries", "phase_tags": ["P2"],
        "canonical_repo": "open-reqif/reqif", "ecosystems": {"pypi": ["reqif"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    # P2 Discovery additions
    {
        "id": "fastapi", "display_name": "FastAPI", "phase_tags": ["P2"],
        "canonical_repo": "fastapi/fastapi", "ecosystems": {"pypi": ["fastapi"]},
        "why_listed": "https://api.github.com/search/repositories?q=topic:openapi+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "bruno", "display_name": "Bruno", "phase_tags": ["P2"],
        "canonical_repo": "usebruno/bruno", "ecosystems": {"npm": ["@usebruno/cli"]},
        "why_listed": "https://api.github.com/search/repositories?q=topic:openapi+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "openapi-specification", "display_name": "OpenAPI Specification", "phase_tags": ["P2"],
        "canonical_repo": "OAI/OpenAPI-Specification", "ecosystems": {"none": []},
        "why_listed": "https://api.github.com/search/repositories?q=topic:openapi+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "swagger-ui", "display_name": "Swagger UI", "phase_tags": ["P2"],
        "canonical_repo": "swagger-api/swagger-ui", "ecosystems": {"npm": ["swagger-ui"]},
        "why_listed": "https://api.github.com/search/repositories?q=topic:openapi+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },

    # --- P3 Design ---
    {
        "id": "structurizr-dsl", "display_name": "Structurizr DSL", "phase_tags": ["P3"],
        "canonical_repo": "structurizr/dsl", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "plantuml", "display_name": "PlantUML", "phase_tags": ["P3"],
        "canonical_repo": "plantuml/plantuml", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "mermaid", "display_name": "Mermaid", "phase_tags": ["P3"],
        "canonical_repo": "mermaid-js/mermaid", "ecosystems": {"npm": ["mermaid"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "archunit", "display_name": "ArchUnit", "phase_tags": ["P3"],
        "canonical_repo": "TNG/ArchUnit", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "dependency-cruiser", "display_name": "dependency-cruiser", "phase_tags": ["P3"],
        "canonical_repo": "sverweij/dependency-cruiser", "ecosystems": {"npm": ["dependency-cruiser"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "deptry", "display_name": "deptry", "phase_tags": ["P3"],
        "canonical_repo": "fpgmaas/deptry", "ecosystems": {"pypi": ["deptry"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "pydeps", "display_name": "pydeps", "phase_tags": ["P3"],
        "canonical_repo": "thebjorn/pydeps", "ecosystems": {"pypi": ["pydeps"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "opa", "display_name": "OPA", "phase_tags": ["P3"],
        "canonical_repo": "open-policy-agent/opa", "ecosystems": {"go": ["github.com/open-policy-agent/opa"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "archi", "display_name": "Archi", "phase_tags": ["P3"],
        "canonical_repo": "archimatetool/archi", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    # P3 Discovery additions
    {
        "id": "excalidraw", "display_name": "Excalidraw", "phase_tags": ["P3"],
        "canonical_repo": "excalidraw/excalidraw", "ecosystems": {"npm": ["@excalidraw/excalidraw"]},
        "why_listed": "https://api.github.com/search/repositories?q=topic:diagrams+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "archify", "display_name": "Archify", "phase_tags": ["P3"],
        "canonical_repo": "tt-a1i/archify", "ecosystems": {"none": []},
        "why_listed": "https://api.github.com/search/repositories?q=topic:diagrams+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "jsoncrack", "display_name": "JSON Crack", "phase_tags": ["P3"],
        "canonical_repo": "AykutSarac/jsoncrack.com", "ecosystems": {"none": []},
        "why_listed": "https://api.github.com/search/repositories?q=topic:diagrams+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },

    # --- P4 Planning ---
    {
        "id": "taskmaster", "display_name": "Taskmaster", "phase_tags": ["P4", "X-workflow"],
        "canonical_repo": "eyurtsev/claude-task-master", "ecosystems": {"npm": ["task-master-ai"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "beads", "display_name": "Beads", "phase_tags": ["P4"],
        "canonical_repo": "steveyegge/beads", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "backlog-md", "display_name": "Backlog.md", "phase_tags": ["P4"],
        "canonical_repo": "mr-destiny/backlog.md", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "networkx", "display_name": "NetworkX", "phase_tags": ["P4", "X-graph"],
        "canonical_repo": "networkx/networkx", "ecosystems": {"pypi": ["networkx"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "openfeature-spec", "display_name": "OpenFeature", "phase_tags": ["P4"],
        "canonical_repo": "open-feature/spec", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    # P4 Discovery additions
    {
        "id": "appflowy", "display_name": "AppFlowy", "phase_tags": ["P4"],
        "canonical_repo": "AppFlowy-IO/AppFlowy", "ecosystems": {"none": []},
        "why_listed": "https://api.github.com/search/repositories?q=topic:task-management+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "mission-control", "display_name": "mission-control", "phase_tags": ["P4"],
        "canonical_repo": "builderz-labs/mission-control", "ecosystems": {"none": []},
        "why_listed": "https://api.github.com/search/repositories?q=topic:task-management+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "obsidian-tasks", "display_name": "obsidian-tasks", "phase_tags": ["P4"],
        "canonical_repo": "obsidian-tasks-group/obsidian-tasks", "ecosystems": {"none": []},
        "why_listed": "https://api.github.com/search/repositories?q=topic:task-management+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },

    # --- P5 Testing ---
    {
        "id": "cosmic-ray", "display_name": "Cosmic Ray", "phase_tags": ["P5"],
        "canonical_repo": "sixty-north/cosmic-ray", "ecosystems": {"pypi": ["cosmic-ray"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "stryker", "display_name": "Stryker", "phase_tags": ["P5"],
        "canonical_repo": "stryker-mutator/stryker-js", "ecosystems": {"npm": ["@stryker-mutator/core"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "pitest", "display_name": "PIT", "phase_tags": ["P5"],
        "canonical_repo": "hcoles/pitest", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "vitest", "display_name": "Vitest", "phase_tags": ["P5"],
        "canonical_repo": "vitest-dev/vitest", "ecosystems": {"npm": ["vitest"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "jest", "display_name": "Jest", "phase_tags": ["P5"],
        "canonical_repo": "jestjs/jest", "ecosystems": {"npm": ["jest"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "playwright", "display_name": "Playwright", "phase_tags": ["P5"],
        "canonical_repo": "microsoft/playwright", "ecosystems": {"npm": ["playwright"], "pypi": ["playwright"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "testcontainers-python", "display_name": "Testcontainers", "phase_tags": ["P5"],
        "canonical_repo": "testcontainers/testcontainers-python", "ecosystems": {"pypi": ["testcontainers"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "pact-python", "display_name": "Pact", "phase_tags": ["P5"],
        "canonical_repo": "pact-foundation/pact-python", "ecosystems": {"pypi": ["pact-python"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "pytest-cov", "display_name": "pytest-cov", "phase_tags": ["P5"],
        "canonical_repo": "pytest-dev/pytest-cov", "ecosystems": {"pypi": ["pytest-cov"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "tox", "display_name": "tox", "phase_tags": ["P5"],
        "canonical_repo": "tox-dev/tox", "ecosystems": {"pypi": ["tox"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "nox", "display_name": "nox", "phase_tags": ["P5"],
        "canonical_repo": "wntrblm/nox", "ecosystems": {"pypi": ["nox"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "syrupy", "display_name": "syrupy", "phase_tags": ["P5"],
        "canonical_repo": "tophat/syrupy", "ecosystems": {"pypi": ["syrupy"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "k6", "display_name": "k6", "phase_tags": ["P5"],
        "canonical_repo": "grafana/k6", "ecosystems": {"go": ["go.k6.io/k6"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "locust", "display_name": "Locust", "phase_tags": ["P5"],
        "canonical_repo": "locustio/locust", "ecosystems": {"pypi": ["locust"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "pytest-benchmark", "display_name": "pytest-benchmark", "phase_tags": ["P5"],
        "canonical_repo": "ionelmc/pytest-benchmark", "ecosystems": {"pypi": ["pytest-benchmark"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "atheris", "display_name": "Atheris", "phase_tags": ["P5"],
        "canonical_repo": "google/atheris", "ecosystems": {"pypi": ["atheris"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "flaky", "display_name": "flaky", "phase_tags": ["P5"],
        "canonical_repo": "box/flaky", "ecosystems": {"pypi": ["flaky"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    # P5 Discovery additions
    {
        "id": "cypress", "display_name": "Cypress", "phase_tags": ["P5"],
        "canonical_repo": "cypress-io/cypress", "ecosystems": {"npm": ["cypress"]},
        "why_listed": "https://api.github.com/search/repositories?q=topic:e2e-testing+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "puppeteer", "display_name": "Puppeteer", "phase_tags": ["P5"],
        "canonical_repo": "puppeteer/puppeteer", "ecosystems": {"npm": ["puppeteer"]},
        "why_listed": "https://api.github.com/search/repositories?q=topic:e2e-testing+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "webdriverio", "display_name": "WebdriverIO", "phase_tags": ["P5"],
        "canonical_repo": "webdriverio/webdriverio", "ecosystems": {"npm": ["webdriverio"]},
        "why_listed": "https://api.github.com/search/repositories?q=topic:e2e-testing+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },

    # --- P6 Implementation ---
    {
        "id": "aider", "display_name": "Aider", "phase_tags": ["P6", "P1"],
        "canonical_repo": "paul-gauthier/aider", "ecosystems": {"pypi": ["aider-chat"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "swe-agent", "display_name": "SWE-agent", "phase_tags": ["P6"],
        "canonical_repo": "SWE-agent/SWE-agent", "ecosystems": {"pypi": ["sweagent"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "openhands", "display_name": "OpenHands", "phase_tags": ["P6"],
        "canonical_repo": "All-Hands-AI/OpenHands", "ecosystems": {"pypi": ["openhands-ai"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "mini-swe-agent", "display_name": "mini-SWE-agent", "phase_tags": ["P6"],
        "canonical_repo": "SWE-agent/mini-swe-agent", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "goose", "display_name": "Goose", "phase_tags": ["P6"],
        "canonical_repo": "block/goose", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "codex-cli", "display_name": "Codex CLI", "phase_tags": ["P6"],
        "canonical_repo": "openai/codex", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "gemini-cli", "display_name": "Gemini CLI", "phase_tags": ["P6"],
        "canonical_repo": "google-gemini/gemini-cli", "ecosystems": {"npm": ["@google/gemini-cli"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "opencode", "display_name": "OpenCode", "phase_tags": ["P6"],
        "canonical_repo": "sst/opencode", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "cline", "display_name": "Cline", "phase_tags": ["P6"],
        "canonical_repo": "cline/cline", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "continue", "display_name": "Continue", "phase_tags": ["P6"],
        "canonical_repo": "continuedev/continue", "ecosystems": {"npm": ["@continuedev/core"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "pre-commit", "display_name": "pre-commit", "phase_tags": ["P6"],
        "canonical_repo": "pre-commit/pre-commit", "ecosystems": {"pypi": ["pre-commit"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "black", "display_name": "black", "phase_tags": ["P6"],
        "canonical_repo": "psf/black", "ecosystems": {"pypi": ["black"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "prettier", "display_name": "prettier", "phase_tags": ["P6"],
        "canonical_repo": "prettier/prettier", "ecosystems": {"npm": ["prettier"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "gvisor", "display_name": "gVisor", "phase_tags": ["P6"],
        "canonical_repo": "google/gvisor", "ecosystems": {"go": ["gvisor.dev/gvisor"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "firecracker", "display_name": "Firecracker", "phase_tags": ["P6"],
        "canonical_repo": "firecracker-microvm/firecracker", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "nsjail", "display_name": "nsjail", "phase_tags": ["P6"],
        "canonical_repo": "google/nsjail", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "firejail", "display_name": "firejail", "phase_tags": ["P6"],
        "canonical_repo": "netblue30/firejail", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "kata-containers", "display_name": "Kata Containers", "phase_tags": ["P6"],
        "canonical_repo": "kata-containers/kata-containers", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "moby", "display_name": "Docker rootless (Moby)", "phase_tags": ["P6"],
        "canonical_repo": "moby/moby", "ecosystems": {"go": ["github.com/moby/moby"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "microsandbox", "display_name": "microsandbox", "phase_tags": ["P6"],
        "canonical_repo": "microsandbox/microsandbox", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    # P6 Discovery additions
    {
        "id": "roo-code", "display_name": "Roo-Code", "phase_tags": ["P6"],
        "canonical_repo": "RooCodeInc/Roo-Code", "ecosystems": {"none": []},
        "why_listed": "https://api.github.com/search/repositories?q=topic:coding-assistant+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },

    # --- P7 Verification ---
    {
        "id": "pylint", "display_name": "pylint", "phase_tags": ["P7"],
        "canonical_repo": "pylint-dev/pylint", "ecosystems": {"pypi": ["pylint"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "flake8", "display_name": "flake8", "phase_tags": ["P7"],
        "canonical_repo": "pycqa/flake8", "ecosystems": {"pypi": ["flake8"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "eslint", "display_name": "eslint", "phase_tags": ["P7"],
        "canonical_repo": "eslint/eslint", "ecosystems": {"npm": ["eslint"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "golangci-lint", "display_name": "golangci-lint", "phase_tags": ["P7"],
        "canonical_repo": "golangci/golangci-lint", "ecosystems": {"go": ["github.com/golangci/golangci-lint"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "sonarqube", "display_name": "SonarQube Community", "phase_tags": ["P7", "P9"],
        "canonical_repo": "SonarSource/sonarqube", "ecosystems": {"docker": ["sonarqube"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "infer", "display_name": "Infer", "phase_tags": ["P7"],
        "canonical_repo": "facebook/infer", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "trivy", "display_name": "Trivy", "phase_tags": ["P7"],
        "canonical_repo": "aquasecurity/trivy", "ecosystems": {"go": ["github.com/aquasecurity/trivy"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "grype", "display_name": "Grype", "phase_tags": ["P7"],
        "canonical_repo": "anchore/grype", "ecosystems": {"go": ["github.com/anchore/grype"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "osv-scanner", "display_name": "OSV-Scanner", "phase_tags": ["P7"],
        "canonical_repo": "google/osv-scanner", "ecosystems": {"go": ["github.com/google/osv-scanner"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "trufflehog", "display_name": "TruffleHog", "phase_tags": ["P7"],
        "canonical_repo": "trufflesecurity/trufflehog", "ecosystems": {"go": ["github.com/trufflesecurity/trufflehog"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "checkov", "display_name": "Checkov", "phase_tags": ["P7"],
        "canonical_repo": "bridgecrewio/checkov", "ecosystems": {"pypi": ["checkov"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "hadolint", "display_name": "hadolint", "phase_tags": ["P7"],
        "canonical_repo": "hadolint/hadolint", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "actionlint", "display_name": "actionlint", "phase_tags": ["P7"],
        "canonical_repo": "rhysd/actionlint", "ecosystems": {"go": ["github.com/rhysd/actionlint"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "vulture", "display_name": "vulture", "phase_tags": ["P7"],
        "canonical_repo": "jendrikseipp/vulture", "ecosystems": {"pypi": ["vulture"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "radon", "display_name": "radon", "phase_tags": ["P7"],
        "canonical_repo": "rubik/radon", "ecosystems": {"pypi": ["radon"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "lizard", "display_name": "lizard", "phase_tags": ["P7"],
        "canonical_repo": "terryyin/lizard", "ecosystems": {"pypi": ["lizard"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "jscpd", "display_name": "jscpd", "phase_tags": ["P7"],
        "canonical_repo": "kucherenko/jscpd", "ecosystems": {"npm": ["jscpd"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "danger", "display_name": "Danger", "phase_tags": ["P7", "P9"],
        "canonical_repo": "danger/danger", "ecosystems": {"pypi": ["danger-python"], "npm": ["danger"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    # Addendum A Archived repos in P7
    {
        "id": "pyre-check", "display_name": "pyre-check", "phase_tags": ["P7"],
        "canonical_repo": "meta/pyre-check", "ecosystems": {"pypi": ["pyre-check"]},
        "why_listed": "CL list (Addendum A)", "is_fork": False, "parent_repo": None, "archived": True, "moved_to": None
    },
    {
        "id": "pyrit", "display_name": "PyRIT", "phase_tags": ["P7"],
        "canonical_repo": "Azure/PyRIT", "ecosystems": {"pypi": ["pyrit"]},
        "why_listed": "CL list (Addendum A)", "is_fork": False, "parent_repo": None, "archived": True, "moved_to": None
    },
    # P7 Discovery additions
    {
        "id": "ruff", "display_name": "ruff", "phase_tags": ["P7"],
        "canonical_repo": "astral-sh/ruff", "ecosystems": {"pypi": ["ruff"]},
        "why_listed": "https://api.github.com/search/repositories?q=topic:linter+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "oxc", "display_name": "oxc", "phase_tags": ["P7"],
        "canonical_repo": "oxc-project/oxc", "ecosystems": {"npm": ["oxc"]},
        "why_listed": "https://api.github.com/search/repositories?q=topic:linter+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "biome", "display_name": "biome", "phase_tags": ["P7"],
        "canonical_repo": "biomejs/biome", "ecosystems": {"npm": ["@biomejs/biome"]},
        "why_listed": "https://api.github.com/search/repositories?q=topic:linter+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },

    # --- P8 Repair ---
    {
        "id": "libcst", "display_name": "LibCST", "phase_tags": ["P8"],
        "canonical_repo": "Instagram/LibCST", "ecosystems": {"pypi": ["libcst"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "openrewrite", "display_name": "OpenRewrite", "phase_tags": ["P8"],
        "canonical_repo": "openrewrite/rewrite", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "comby", "display_name": "Comby", "phase_tags": ["P8"],
        "canonical_repo": "comby-tools/comby", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "jscodeshift", "display_name": "jscodeshift", "phase_tags": ["P8"],
        "canonical_repo": "facebook/jscodeshift", "ecosystems": {"npm": ["jscodeshift"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "rope", "display_name": "rope", "phase_tags": ["P8"],
        "canonical_repo": "python-rope/rope", "ecosystems": {"pypi": ["rope"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "agentless", "display_name": "Agentless", "phase_tags": ["P8"],
        "canonical_repo": "OpenAutoCoder/Agentless", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "coccinelle", "display_name": "Coccinelle", "phase_tags": ["P8"],
        "canonical_repo": "coccinelle/coccinelle", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "semgrep", "display_name": "Semgrep autofix", "phase_tags": ["P8"],
        "canonical_repo": "semgrep/semgrep", "ecosystems": {"pypi": ["semgrep"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    # P8 Discovery additions
    {
        "id": "sourcery", "display_name": "Sourcery", "phase_tags": ["P8"],
        "canonical_repo": "sourcery-ai/sourcery", "ecosystems": {"none": []},
        "why_listed": "https://api.github.com/search/repositories?q=topic:refactoring+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },

    # --- P9 Review ---
    {
        "id": "reviewdog", "display_name": "reviewdog", "phase_tags": ["P9"],
        "canonical_repo": "reviewdog/reviewdog", "ecosystems": {"go": ["github.com/reviewdog/reviewdog"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "gerrit", "display_name": "Gerrit", "phase_tags": ["P9"],
        "canonical_repo": "GerritCodeReview/gerrit", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "pr-agent", "display_name": "PR-Agent", "phase_tags": ["P9"],
        "canonical_repo": "The-PR-Agent/pr-agent", "ecosystems": {"pypi": ["pr-agent"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "kodus", "display_name": "Kodus", "phase_tags": ["P9"],
        "canonical_repo": "kodus-io/kodus", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    # Negative Control 2: no license repo
    {
        "id": "pr-af", "display_name": "PR-AF", "phase_tags": ["P9"],
        "canonical_repo": "Agent-Field/pr-af", "ecosystems": {"none": []},
        "why_listed": "CL list (Negative Control: no LICENSE)", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    # Closed tool
    {
        "id": "coderabbit", "display_name": "CodeRabbit", "phase_tags": ["P9"],
        "canonical_repo": "closed/coderabbit", "ecosystems": {"none": []},
        "why_listed": "CL list (closed/vendor)", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    # Negative Control 5: renamed repo
    {
        "id": "qodo-pr-agent", "display_name": "qodo-ai/pr-agent (renamed)", "phase_tags": ["P9"],
        "canonical_repo": "The-PR-Agent/pr-agent", "ecosystems": {"pypi": ["pr-agent"]},
        "why_listed": "CL list (Negative Control: renamed repo)", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": "The-PR-Agent/pr-agent"
    },

    # --- P10 Release ---
    {
        "id": "python-semantic-release", "display_name": "python-semantic-release", "phase_tags": ["P10"],
        "canonical_repo": "python-semantic-release/python-semantic-release", "ecosystems": {"pypi": ["python-semantic-release"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "release-please", "display_name": "release-please", "phase_tags": ["P10"],
        "canonical_repo": "googleapis/release-please", "ecosystems": {"npm": ["release-please"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "changesets", "display_name": "changesets", "phase_tags": ["P10"],
        "canonical_repo": "changesets/changesets", "ecosystems": {"npm": ["@changesets/cli"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "commitizen", "display_name": "commitizen", "phase_tags": ["P10"],
        "canonical_repo": "commitizen-tools/commitizen", "ecosystems": {"pypi": ["commitizen"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "git-cliff", "display_name": "git-cliff", "phase_tags": ["P10"],
        "canonical_repo": "orhun/git-cliff", "ecosystems": {"crates": ["git-cliff"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "towncrier", "display_name": "towncrier", "phase_tags": ["P10"],
        "canonical_repo": "twisted/towncrier", "ecosystems": {"pypi": ["towncrier"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "slsa-github-generator", "display_name": "slsa-github-generator", "phase_tags": ["P10"],
        "canonical_repo": "slsa-framework/slsa-github-generator", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "spdx-tools", "display_name": "spdx-tools", "phase_tags": ["P10"],
        "canonical_repo": "spdx/tools-python", "ecosystems": {"pypi": ["spdx-tools"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "reuse-tool", "display_name": "REUSE tool", "phase_tags": ["P10"],
        "canonical_repo": "fsfe/reuse-tool", "ecosystems": {"pypi": ["reuse"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "ort", "display_name": "OSS Review Toolkit", "phase_tags": ["P10"],
        "canonical_repo": "oss-review-toolkit/ort", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "licensee", "display_name": "licensee", "phase_tags": ["P10"],
        "canonical_repo": "licensee/licensee", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "dependency-track", "display_name": "Dependency-Track", "phase_tags": ["P10"],
        "canonical_repo": "DependencyTrack/dependency-track", "ecosystems": {"docker": ["dependencytrack/apiserver"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "guac", "display_name": "GUAC", "phase_tags": ["P10"],
        "canonical_repo": "guacsec/guac", "ecosystems": {"go": ["github.com/guacsec/guac"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    # P10 Discovery additions
    {
        "id": "semantic-release-js", "display_name": "semantic-release", "phase_tags": ["P10"],
        "canonical_repo": "semantic-release/semantic-release", "ecosystems": {"npm": ["semantic-release"]},
        "why_listed": "https://api.github.com/search/repositories?q=topic:semantic-release+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "cz-cli", "display_name": "commitizen cz-cli", "phase_tags": ["P10"],
        "canonical_repo": "commitizen/cz-cli", "ecosystems": {"npm": ["commitizen"]},
        "why_listed": "https://api.github.com/search/repositories?q=topic:semantic-release+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },

    # --- P11 Continuous ---
    {
        "id": "prometheus", "display_name": "Prometheus", "phase_tags": ["P11"],
        "canonical_repo": "prometheus/prometheus", "ecosystems": {"go": ["github.com/prometheus/prometheus"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "jaeger", "display_name": "Jaeger", "phase_tags": ["P11"],
        "canonical_repo": "jaegertracing/jaeger", "ecosystems": {"go": ["github.com/jaegertracing/jaeger"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "argo-cd", "display_name": "Argo CD", "phase_tags": ["P11"],
        "canonical_repo": "argoproj/argo-cd", "ecosystems": {"go": ["github.com/argoproj/argo-cd"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "flux2", "display_name": "Flux", "phase_tags": ["P11"],
        "canonical_repo": "fluxcd/flux2", "ecosystems": {"go": ["github.com/fluxcd/flux2"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "unleash", "display_name": "Unleash", "phase_tags": ["P11"],
        "canonical_repo": "Unleash/unleash", "ecosystems": {"npm": ["unleash-server"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "chaostoolkit", "display_name": "chaostoolkit", "phase_tags": ["P11"],
        "canonical_repo": "chaostoolkit/chaostoolkit", "ecosystems": {"pypi": ["chaostoolkit"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "litmus", "display_name": "Litmus", "phase_tags": ["P11"],
        "canonical_repo": "litmuschaos/litmus", "ecosystems": {"go": ["github.com/litmuschaos/litmus"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "keptn", "display_name": "Keptn", "phase_tags": ["P11"],
        "canonical_repo": "keptn/keptn", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    # P11 Discovery additions
    {
        "id": "chaos-mesh", "display_name": "Chaos Mesh", "phase_tags": ["P11"],
        "canonical_repo": "chaos-mesh/chaos-mesh", "ecosystems": {"go": ["github.com/chaos-mesh/chaos-mesh"]},
        "why_listed": "https://api.github.com/search/repositories?q=topic:chaos-engineering+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "chaosblade", "display_name": "ChaosBlade", "phase_tags": ["P11"],
        "canonical_repo": "chaosblade-io/chaosblade", "ecosystems": {"go": ["github.com/chaosblade-io/chaosblade"]},
        "why_listed": "https://api.github.com/search/repositories?q=topic:chaos-engineering+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },

    # --- X-graph ---
    {
        "id": "rdflib", "display_name": "RDFLib", "phase_tags": ["X-graph"],
        "canonical_repo": "RDFLib/rdflib", "ecosystems": {"pypi": ["rdflib"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "pyshacl", "display_name": "pyshacl", "phase_tags": ["X-graph"],
        "canonical_repo": "RDFLib/pySHACL", "ecosystems": {"pypi": ["pyshacl"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "kuzu", "display_name": "Kuzu", "phase_tags": ["X-graph"],
        "canonical_repo": "kuzudb/kuzu", "ecosystems": {"pypi": ["kuzu"], "npm": ["kuzu"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "cozo", "display_name": "Cozo", "phase_tags": ["X-graph"],
        "canonical_repo": "cozodb/cozo", "ecosystems": {"crates": ["cozo"], "pypi": ["pycozo"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "oxigraph", "display_name": "Oxigraph", "phase_tags": ["X-graph"],
        "canonical_repo": "oxigraph/oxigraph", "ecosystems": {"crates": ["oxigraph"], "pypi": ["pyoxigraph"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "sqlite", "display_name": "SQLite", "phase_tags": ["X-graph"],
        "canonical_repo": "sqlite/sqlite", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "prov-o-spec", "display_name": "W3C PROV-O spec", "phase_tags": ["X-graph"],
        "canonical_repo": "spec/w3c-prov-o", "ecosystems": {"none": []},
        "why_listed": "CL list (spec)", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "json-ld-spec", "display_name": "JSON-LD spec", "phase_tags": ["X-graph"],
        "canonical_repo": "spec/w3c-json-ld", "ecosystems": {"none": []},
        "why_listed": "CL list (spec)", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    # X-graph Discovery additions
    {
        "id": "understand-anything", "display_name": "Understand-Anything", "phase_tags": ["X-graph"],
        "canonical_repo": "Egonex-AI/Understand-Anything", "ecosystems": {"none": []},
        "why_listed": "https://api.github.com/search/repositories?q=topic:knowledge-graph+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "mirofish", "display_name": "MiroFish", "phase_tags": ["X-graph"],
        "canonical_repo": "666ghj/MiroFish", "ecosystems": {"none": []},
        "why_listed": "https://api.github.com/search/repositories?q=topic:knowledge-graph+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },

    # --- X-memory ---
    {
        "id": "graphiti", "display_name": "Graphiti", "phase_tags": ["X-memory"],
        "canonical_repo": "getzep/graphiti", "ecosystems": {"pypi": ["graphiti-core"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "mem0", "display_name": "mem0", "phase_tags": ["X-memory"],
        "canonical_repo": "mem0ai/mem0", "ecosystems": {"pypi": ["mem0ai"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "letta", "display_name": "Letta", "phase_tags": ["X-memory"],
        "canonical_repo": "letta-ai/letta", "ecosystems": {"pypi": ["letta"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "cognee", "display_name": "Cognee", "phase_tags": ["X-memory"],
        "canonical_repo": "topoteretes/cognee", "ecosystems": {"pypi": ["cognee"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "lightrag", "display_name": "LightRAG", "phase_tags": ["X-memory"],
        "canonical_repo": "HKUDS/LightRAG", "ecosystems": {"pypi": ["lightrag-hku"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "graphrag", "display_name": "Microsoft GraphRAG", "phase_tags": ["X-memory"],
        "canonical_repo": "microsoft/graphrag", "ecosystems": {"pypi": ["graphrag"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    # X-memory Discovery additions
    {
        "id": "milvus", "display_name": "Milvus", "phase_tags": ["X-memory"],
        "canonical_repo": "milvus-io/milvus", "ecosystems": {"go": ["github.com/milvus-io/milvus"]},
        "why_listed": "https://api.github.com/search/repositories?q=topic:vector-search+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "qdrant", "display_name": "Qdrant", "phase_tags": ["X-memory"],
        "canonical_repo": "qdrant/qdrant", "ecosystems": {"crates": ["qdrant"]},
        "why_listed": "https://api.github.com/search/repositories?q=topic:vector-search+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },

    # --- X-guard ---
    {
        "id": "nemo-guardrails", "display_name": "NeMo Guardrails", "phase_tags": ["X-guard"],
        "canonical_repo": "NVIDIA/NeMo-Guardrails", "ecosystems": {"pypi": ["nemoguardrails"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "guardrails-ai", "display_name": "Guardrails AI", "phase_tags": ["X-guard"],
        "canonical_repo": "guardrails-ai/guardrails", "ecosystems": {"pypi": ["guardrails-ai"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "llm-guard", "display_name": "LLM Guard", "phase_tags": ["X-guard"],
        "canonical_repo": "protectai/llm-guard", "ecosystems": {"pypi": ["llm-guard"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "llama-guard", "display_name": "Llama Guard", "phase_tags": ["X-guard"],
        "canonical_repo": "meta-llama/llama-guard", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "invariant", "display_name": "Invariant", "phase_tags": ["X-guard"],
        "canonical_repo": "invariantlabs-ai/invariant", "ecosystems": {"pypi": ["invariant"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    # X-guard Discovery additions
    {
        "id": "presidio", "display_name": "Presidio", "phase_tags": ["X-guard"],
        "canonical_repo": "data-privacy-stack/presidio", "ecosystems": {"pypi": ["presidio-analyzer"]},
        "why_listed": "https://api.github.com/search/repositories?q=topic:guardrails+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "bifrost", "display_name": "Bifrost", "phase_tags": ["X-guard", "X-portability"],
        "canonical_repo": "maximhq/bifrost", "ecosystems": {"none": []},
        "why_listed": "https://api.github.com/search/repositories?q=topic:guardrails+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },

    # --- X-eval ---
    {
        "id": "inspect-ai", "display_name": "inspect-ai", "phase_tags": ["X-eval"],
        "canonical_repo": "UKGovernmentBEIS/inspect_ai", "ecosystems": {"pypi": ["inspect-ai"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "deepeval", "display_name": "DeepEval", "phase_tags": ["X-eval"],
        "canonical_repo": "confident-ai/deepeval", "ecosystems": {"pypi": ["deepeval"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "ragas", "display_name": "Ragas", "phase_tags": ["X-eval"],
        "canonical_repo": "explodinggradients/ragas", "ecosystems": {"pypi": ["ragas"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "lm-evaluation-harness", "display_name": "lm-evaluation-harness", "phase_tags": ["X-eval"],
        "canonical_repo": "EleutherAI/lm-evaluation-harness", "ecosystems": {"pypi": ["lm-eval"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "swe-bench", "display_name": "SWE-bench", "phase_tags": ["X-eval"],
        "canonical_repo": "princeton-nlp/SWE-bench", "ecosystems": {"pypi": ["swebench"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "openllmetry", "display_name": "OpenLLMetry", "phase_tags": ["X-eval"],
        "canonical_repo": "traceloop/openllmetry", "ecosystems": {"pypi": ["traceloop-sdk"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "langfuse", "display_name": "Langfuse", "phase_tags": ["X-eval"],
        "canonical_repo": "langfuse/langfuse", "ecosystems": {"pypi": ["langfuse"], "npm": ["langfuse"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "phoenix", "display_name": "Phoenix", "phase_tags": ["X-eval"],
        "canonical_repo": "Arize-ai/phoenix", "ecosystems": {"pypi": ["arize-phoenix"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    # X-eval Discovery additions
    {
        "id": "promptfoo", "display_name": "Promptfoo", "phase_tags": ["X-eval"],
        "canonical_repo": "promptfoo/promptfoo", "ecosystems": {"npm": ["promptfoo"]},
        "why_listed": "https://api.github.com/search/repositories?q=topic:llm-evaluation+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "mlflow", "display_name": "MLflow", "phase_tags": ["X-eval"],
        "canonical_repo": "mlflow/mlflow", "ecosystems": {"pypi": ["mlflow"]},
        "why_listed": "https://api.github.com/search/repositories?q=topic:llm-evaluation+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "opik", "display_name": "Opik", "phase_tags": ["X-eval"],
        "canonical_repo": "comet-ml/opik", "ecosystems": {"pypi": ["opik"]},
        "why_listed": "https://api.github.com/search/repositories?q=topic:llm-evaluation+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },

    # --- X-portability ---
    {
        "id": "litellm", "display_name": "LiteLLM", "phase_tags": ["X-portability"],
        "canonical_repo": "BerriAI/litellm", "ecosystems": {"pypi": ["litellm"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "any-llm", "display_name": "any-llm", "phase_tags": ["X-portability"],
        "canonical_repo": "martian-ai/any-llm", "ecosystems": {"pypi": ["any-llm"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "instructor", "display_name": "Instructor", "phase_tags": ["X-portability"],
        "canonical_repo": "jxnl/instructor", "ecosystems": {"pypi": ["instructor"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "outlines", "display_name": "Outlines", "phase_tags": ["X-portability"],
        "canonical_repo": "dottxt-ai/outlines", "ecosystems": {"pypi": ["outlines"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "baml", "display_name": "BAML", "phase_tags": ["X-portability"],
        "canonical_repo": "BoundaryML/baml", "ecosystems": {"pypi": ["baml-py"], "npm": ["@boundaryml/baml"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "pydantic-ai", "display_name": "Pydantic AI", "phase_tags": ["X-portability"],
        "canonical_repo": "pydantic/pydantic-ai", "ecosystems": {"pypi": ["pydantic-ai"]},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "a2a-protocol", "display_name": "A2A protocol", "phase_tags": ["X-portability"],
        "canonical_repo": "a2aproject/A2A", "ecosystems": {"none": []},
        "why_listed": "CL list (protocol)", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "agents-md", "display_name": "AGENTS.md convention", "phase_tags": ["X-portability"],
        "canonical_repo": "agents-md/agents.md", "ecosystems": {"none": []},
        "why_listed": "CL list (convention)", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "mcp-spec", "display_name": "Model Context Protocol", "phase_tags": ["X-portability"],
        "canonical_repo": "modelcontextprotocol/specification", "ecosystems": {"none": []},
        "why_listed": "CL list (spec)", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    # X-portability Discovery additions
    {
        "id": "opencodex", "display_name": "opencodex", "phase_tags": ["X-portability"],
        "canonical_repo": "lidge-jun/opencodex", "ecosystems": {"none": []},
        "why_listed": "https://api.github.com/search/repositories?q=topic:llm-proxy+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "plano", "display_name": "Plano", "phase_tags": ["X-portability"],
        "canonical_repo": "katanemo/plano", "ecosystems": {"none": []},
        "why_listed": "https://api.github.com/search/repositories?q=topic:llm-proxy+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },

    # --- X-workflow (GSD, Ralph, Spec-driven, Closed) ---
    # GSD family
    {
        "id": "open-gsd", "display_name": "GSD Core (open-gsd)", "phase_tags": ["X-workflow"],
        "canonical_repo": "open-gsd/gsd-core", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    # Negative Control 1: archived repo pointing to open-gsd
    {
        "id": "gsd-build", "display_name": "get-shit-done (gsd-build)", "phase_tags": ["X-workflow"],
        "canonical_repo": "gsd-build/get-shit-done", "ecosystems": {"none": []},
        "why_listed": "CL list (Negative Control: archived repo)", "is_fork": False, "parent_repo": None, "archived": True, "moved_to": "open-gsd/gsd-core"
    },
    # Negative Control 4: fork repo
    {
        "id": "jmathai-gsd", "display_name": "get-shit-done (jmathai)", "phase_tags": ["X-workflow"],
        "canonical_repo": "jmathai/get-shit-done", "ecosystems": {"none": []},
        "why_listed": "CL list (Negative Control: fork)", "is_fork": True, "parent_repo": "gsd-build/get-shit-done", "archived": False, "moved_to": None
    },
    {
        "id": "ludicrypt-gsd", "display_name": "get-shit-done (ludicrypt)", "phase_tags": ["X-workflow"],
        "canonical_repo": "ludicrypt/get-shit-done", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": True, "parent_repo": "gsd-build/get-shit-done", "archived": False, "moved_to": None
    },
    {
        "id": "itsjwill-gsd", "display_name": "get-shit-done (itsjwill)", "phase_tags": ["X-workflow"],
        "canonical_repo": "itsjwill/get-shit-done", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": True, "parent_repo": "gsd-build/get-shit-done", "archived": False, "moved_to": None
    },

    # Ralph family
    {
        "id": "ghuntley-work", "display_name": "Geoffrey Huntley technique (ghuntley/work)", "phase_tags": ["X-workflow"],
        "canonical_repo": "ghuntley/work", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "snarktank-ralph", "display_name": "Ralph (snarktank)", "phase_tags": ["X-workflow"],
        "canonical_repo": "snarktank/ralph", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "claude-plugins-ralph", "display_name": "Claude Plugins ralph-loop", "phase_tags": ["X-workflow"],
        "canonical_repo": "anthropics/claude-plugins-official", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "frankbria-ralph", "display_name": "ralph-claude-code (frankbria)", "phase_tags": ["X-workflow"],
        "canonical_repo": "frankbria/ralph-claude-code", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "michaelshimeles-ralphy", "display_name": "Ralphy (michaelshimeles)", "phase_tags": ["X-workflow"],
        "canonical_repo": "michaelshimeles/ralphy", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "ralph-workflow", "display_name": "ralph-workflow", "phase_tags": ["X-workflow"],
        "canonical_repo": "ralph-workflow/ralph", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "ralphify", "display_name": "ralphify", "phase_tags": ["X-workflow"],
        "canonical_repo": "mikey-p/ralphify", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "open-ralph-wiggum", "display_name": "open-ralph-wiggum", "phase_tags": ["X-workflow"],
        "canonical_repo": "open-ralph/open-ralph-wiggum", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "awesome-ralph", "display_name": "awesome-ralph (dabit3 fork)", "phase_tags": ["X-workflow"],
        "canonical_repo": "dabit3/awesome-ralph", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": True, "parent_repo": "snwfdhmp/awesome-ralph", "archived": False, "moved_to": None
    },

    # Spec-driven
    {
        "id": "github-spec-kit", "display_name": "GitHub Spec Kit", "phase_tags": ["X-workflow"],
        "canonical_repo": "github/spec-kit", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "openspec", "display_name": "OpenSpec", "phase_tags": ["X-workflow"],
        "canonical_repo": "Fission-AI/OpenSpec", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "superpowers", "display_name": "Superpowers", "phase_tags": ["X-workflow"],
        "canonical_repo": "obra/superpowers", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "agent-os", "display_name": "Agent OS", "phase_tags": ["X-workflow"],
        "canonical_repo": "agent-os/agent-os", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "superclaude", "display_name": "SuperClaude", "phase_tags": ["X-workflow"],
        "canonical_repo": "SuperClaude-Org/SuperClaude", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "ruflo", "display_name": "ruflo", "phase_tags": ["X-workflow"],
        "canonical_repo": "ruvnet/ruflo", "ecosystems": {"none": []},
        "why_listed": "CL list", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    # X-workflow Discovery additions
    {
        "id": "paperclip", "display_name": "Paperclip", "phase_tags": ["X-workflow"],
        "canonical_repo": "paperclipai/paperclip", "ecosystems": {"none": []},
        "why_listed": "https://api.github.com/search/repositories?q=topic:autonomous-agents+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "pentagi", "display_name": "PentaGI", "phase_tags": ["X-workflow"],
        "canonical_repo": "vxcontrol/pentagi", "ecosystems": {"none": []},
        "why_listed": "https://api.github.com/search/repositories?q=topic:autonomous-agents+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "planning-with-files", "display_name": "planning-with-files", "phase_tags": ["X-workflow"],
        "canonical_repo": "OthmanAdi/planning-with-files", "ecosystems": {"none": []},
        "why_listed": "https://api.github.com/search/repositories?q=topic:autonomous-agents+stars:>=1000+archived:false",
        "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },

    # Closed / Vendor tools (record existence and license only)
    {
        "id": "aws-kiro", "display_name": "AWS Kiro", "phase_tags": ["X-workflow"],
        "canonical_repo": "closed/aws-kiro", "ecosystems": {"none": []},
        "why_listed": "CL list (vendor/closed)", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "tessl", "display_name": "Tessl", "phase_tags": ["X-workflow"],
        "canonical_repo": "closed/tessl", "ecosystems": {"none": []},
        "why_listed": "CL list (vendor/closed)", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "cursor-plan-mode", "display_name": "Cursor Plan Mode", "phase_tags": ["X-workflow"],
        "canonical_repo": "closed/cursor-plan-mode", "ecosystems": {"none": []},
        "why_listed": "CL list (vendor/closed)", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "greptile", "display_name": "Greptile", "phase_tags": ["P9"],
        "canonical_repo": "closed/greptile", "ecosystems": {"none": []},
        "why_listed": "CL list (vendor/closed)", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    {
        "id": "augment-intent", "display_name": "Augment Intent", "phase_tags": ["P0"],
        "canonical_repo": "closed/augment-intent", "ecosystems": {"none": []},
        "why_listed": "CL list (vendor/closed)", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },

    # --- Negative Controls explicitly specified in CL prompt ---
    # Negative Control 3: non-existent package
    {
        "id": "non-existent-pkg-control", "display_name": "sclass-does-not-exist-12345", "phase_tags": ["P7"],
        "canonical_repo": "sclass-test/non-existent-pkg", "ecosystems": {"pypi": ["sclass-does-not-exist-12345"]},
        "why_listed": "CL prompt (Negative Control: non-existent package)", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    },
    # Negative Control 6: identity mismatch (PyPI pyright vs microsoft/pyright)
    {
        "id": "pyright-mismatch-control", "display_name": "pyright (PyPI wrapper)", "phase_tags": ["P7"],
        "canonical_repo": "microsoft/pyright", "ecosystems": {"pypi": ["pyright"]},
        "why_listed": "CL prompt (Negative Control: identity mismatch)", "is_fork": False, "parent_repo": None, "archived": False, "moved_to": None
    }
]

def build():
    print(f"Building candidates.yaml from {len(RAW_CANDIDATES)} candidates...")
    candidates = []
    
    # Track statistics
    stats = {
        "total": len(RAW_CANDIDATES),
        "archived": 0,
        "forks": 0,
        "moved": 0,
        "closed": 0,
        "identity_true": 0,
        "identity_false": 0,
        "identity_na": 0
    }

    for idx, c in enumerate(RAW_CANDIDATES, 1):
        # Identity check
        match_result = check_identity(c["ecosystems"], c["canonical_repo"])
        
        # Build clean entry
        entry = {
            "id": c["id"],
            "display_name": c["display_name"],
            "phase_tags": c["phase_tags"],
            "canonical_repo": c["canonical_repo"],
            "ecosystems": c["ecosystems"],
            "why_listed": c["why_listed"],
            "is_fork": c["is_fork"],
            "parent_repo": c["parent_repo"],
            "archived": c["archived"],
            "moved_to": c["moved_to"],
            "identity_checks": {
                "pkg_home_url_matches_repo": match_result
            }
        }
        candidates.append(entry)

        # Update stats
        if c["archived"]: stats["archived"] += 1
        if c["is_fork"]: stats["forks"] += 1
        if c["moved_to"]: stats["moved"] += 1
        if c["canonical_repo"].startswith("closed/"): stats["closed"] += 1
        if match_result is True: stats["identity_true"] += 1
        elif match_result is False: stats["identity_false"] += 1
        else: stats["identity_na"] += 1

    out_data = {
        "metadata": {
            "generated_by": "product/oss-evidence/sweep/build_candidates.py",
            "task": "OSS-SWEEP-R32 Stage A",
            "total_candidates": len(candidates),
            "stats": stats
        },
        "candidates": candidates
    }

    with open(CANDIDATES_YAML, "w", encoding="utf-8") as f:
        yaml.dump(out_data, f, sort_keys=False, default_flow_style=False, allow_unicode=True)

    print(f"Successfully generated {CANDIDATES_YAML}")
    print(f"Summary stats: {json.dumps(stats, indent=2)}")

if __name__ == "__main__":
    build()
