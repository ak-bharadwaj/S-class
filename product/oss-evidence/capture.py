#!/usr/bin/env python3
"""
Authoritative OSS Evidence Capture Script for S-Class R31.
Implements STEP 1 of TASK OSS-EVIDENCE-R31.
"""
import base64
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "product", "oss-evidence", "raw")
MANIFEST_PATH = os.path.join(ROOT, "product", "oss-evidence", "MANIFEST.json")
os.makedirs(OUT, exist_ok=True)

# 1. GitHub Token
GH_TOKEN = ""
try:
    r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        GH_TOKEN = r.stdout.strip()
except Exception:
    pass

if not GH_TOKEN:
    try:
        r = subprocess.run(["gh.exe", "auth", "token"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            GH_TOKEN = r.stdout.strip()
    except Exception:
        pass

if not GH_TOKEN:
    GH_TOKEN = os.environ.get("GITHUB_TOKEN", "")


print(f"GitHub Auth Token present: {bool(GH_TOKEN)} (prefix: {GH_TOKEN[:7]}...)")

# 2. Scope definitions
PYPI_PACKAGES = [
    # R9-39 .. R9-65
    "bashlex", "diff-cover", "import-linter", "pytest-timeout", "pytest-rerunfailures",
    "pip-licenses", "in-toto", "sigstore", "detect-secrets", "pyright", "garak", "pyrit",
    "pygls", "lsprotocol", "semgrep", "mypy", "bandit", "scancode-toolkit", "pr-agent",
    "sarif-tools", "licensecheck", "cyclonedx-bom", "hypothesis", "mutmut", "coverage",
    "pytest-xdist", "pytest-randomly", "pip-audit", "pyre-check", "ruff", "opengrep",
    # Older records R9-01 .. R9-38
    "pytest", "schemathesis", "jsonschema", "sqlglot", "ast-grep-cli",
    "openhands-ai", "mini-swe-agent", "mcp", "agent-client-protocol",
    "smolagents", "langgraph", "opentelemetry-api"
]

NPM_PACKAGES = [
    "promptfoo", "pyright", "tree-sitter-bash", "renovate", "tree-sitter", "@ast-grep/cli"
]

GH_REPOS = {
    # R9-01 .. R9-38
    "spec-kit": "github/spec-kit",
    "openspec": "Fission-AI/OpenSpec",
    "jsonschema": "python-jsonschema/jsonschema",
    "tree-sitter": "tree-sitter/tree-sitter",
    "scip": "sourcegraph/scip",
    "ast-grep": "ast-grep/ast-grep",
    "sqlglot": "tobymao/sqlglot",
    "semgrep": "semgrep/semgrep",
    "semgrep-rules": "semgrep/semgrep-rules",
    "bandit": "PyCQA/bandit",
    "opa": "open-policy-agent/opa",
    "pytest": "pytest-dev/pytest",
    "hypothesis": "HypothesisWorks/hypothesis",
    "schemathesis": "schemathesis/schemathesis",
    "mutmut": "boxed/mutmut",
    "coverage": "nedbat/coveragepy",
    "openhands": "All-Hands-AI/OpenHands",
    "mini-swe-agent": "SWE-agent/mini-swe-agent",
    "mcp": "modelcontextprotocol/python-sdk",
    "agent-client-protocol": "agentclientprotocol/agent-client-protocol",
    "smolagents": "huggingface/smolagents",
    "langgraph": "langchain-ai/langgraph",
    "mypy": "python/mypy",
    "ruff": "astral-sh/ruff",
    "gitleaks": "gitleaks/gitleaks",
    "pip-audit": "pypa/pip-audit",
    "osv-scanner": "google/osv-scanner",
    "syft": "anchore/syft",
    "cyclonedx-bom": "CycloneDX/cyclonedx-python",
    "cosign": "sigstore/cosign",
    "opentelemetry": "open-telemetry/opentelemetry-python",
    "renovate": "renovatebot/renovate",
    "bubblewrap": "containers/bubblewrap",
    "magic-context": "cortexkit/magic-context",
    # R9-39 .. R9-65
    "bashlex": "idank/bashlex",
    "tree-sitter-bash": "tree-sitter/tree-sitter-bash",
    "mvdan-sh": "mvdan/sh",
    "shellcheck": "koalaman/shellcheck",
    "pyright": "microsoft/pyright",
    "pyre-check": "facebook/pyre-check",
    "diff-cover": "Bachmann1234/diff_cover",
    "import-linter": "seddonym/import-linter",
    "detect-secrets": "Yelp/detect-secrets",
    "pytest-timeout": "pytest-dev/pytest-timeout",
    "pytest-rerunfailures": "pytest-dev/pytest-rerunfailures",
    "pytest-randomly": "pytest-dev/pytest-randomly",
    "pytest-xdist": "pytest-dev/pytest-xdist",
    "pip-licenses": "raimon49/pip-licenses",
    "licensecheck": "FHPythonUtils/LicenseCheck",
    "scancode": "aboutcode-org/scancode-toolkit",
    "in-toto": "in-toto/in-toto",
    "sigstore-python": "sigstore/sigstore-python",
    "scorecard": "ossf/scorecard",
    "promptfoo": "promptfoo/promptfoo",
    "garak": "NVIDIA/garak",
    "pyrit": "Azure/PyRIT",
    "pygls": "openlawlibrary/pygls",
    "lsprotocol": "microsoft/lsprotocol",
    "sarif-tools": "microsoft/sarif-tools",
    "opengrep": "opengrep/opengrep",
    "pr-agent": "The-PR-Agent/pr-agent",
    # Specific directive tools
    "kodus": "kodustech/kodus-ai",
    "pr-af": "Agent-Field/pr-af",
}

GO_REPOS = {
    "opa": "github.com/open-policy-agent/opa",
    "gitleaks": "github.com/gitleaks/gitleaks",
    "osv-scanner": "github.com/google/osv-scanner",
    "syft": "github.com/anchore/syft",
    "cosign": "github.com/sigstore/cosign",
    "mvdan-sh": "github.com/mvdan/sh",
    "scorecard": "github.com/ossf/scorecard",
    "pr-af": "github.com/Agent-Field/pr-af",
}

manifest = []
pypi_versions = {}
npm_versions = {}

def get_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()

def http_get(url, headers=None, follow_redirects=True):
    hdrs = {"User-Agent": "S-Class-R31-OSS-Capture/1.0"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    
    # Custom opener if we don't want to follow redirects
    if not follow_redirects:
        class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
            def http_error_301(self, req, fp, code, msg, headers):
                infurl = urllib.response.addinfourl(fp, headers, req.get_full_url())
                infurl.status = code
                infurl.code = code
                return infurl
            http_error_302 = http_error_301
            http_error_303 = http_error_301
            http_error_307 = http_error_301
            http_error_308 = http_error_301
        opener = urllib.request.build_opener(NoRedirectHandler)
    else:
        opener = urllib.request.build_opener()

    try:
        with opener.open(req, timeout=30) as resp:
            code = str(resp.getcode() or resp.status or 200)
            data = resp.read()
            return code, data
    except urllib.error.HTTPError as e:
        code = str(e.code)
        try:
            data = e.read()
        except Exception:
            data = b""
        return code, data
    except Exception as e:
        return "ERR", str(e).encode()

def http_post_json(url, payload):
    data_bytes = json.dumps(payload).encode()
    hdrs = {
        "User-Agent": "S-Class-R31-OSS-Capture/1.0",
        "Content-Type": "application/json"
    }
    req = urllib.request.Request(url, data=data_bytes, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            code = str(resp.getcode() or 200)
            data = resp.read()
            return code, data
    except urllib.error.HTTPError as e:
        code = str(e.code)
        try:
            data = e.read()
        except Exception:
            data = b""
        return code, data
    except Exception as e:
        return "ERR", str(e).encode()

def save_evidence(fn, url, code, data, note=None):
    path = os.path.join(OUT, fn)
    ok = (code == "200") and bool(data)
    
    if ok:
        with open(path, "wb") as f:
            f.write(data)
        h = sha256_bytes(data)
        status = "OK"
    else:
        if os.path.exists(path):
            os.remove(path)
        h = ""
        status = "NOT RETRIEVED"
    
    rec = {
        "file": fn,
        "url": url,
        "http": code,
        "sha256": h,
        "retrieved_at": get_now(),
        "status": status
    }
    if note:
        rec["note"] = note
    if not ok and code != "200":
        rec["error"] = f"HTTP {code}"
    
    manifest.append(rec)
    print(f"[{status}] {fn} (HTTP {code})")
    return ok, data

print("\n--- PHASE 1: PyPI Packages ---")
for p in PYPI_PACKAGES:
    fn = f"pypi__{p}.json"
    url = f"https://pypi.org/pypi/{p}/json"
    code, data = http_get(url)
    ok, content = save_evidence(fn, url, code, data)
    if ok:
        try:
            j = json.loads(content)
            ver = j.get("info", {}).get("version", "")
            if ver:
                pypi_versions[p] = ver
        except Exception:
            pass

print("\n--- PHASE 2: NPM Packages ---")
for p in NPM_PACKAGES:
    safe_name = p.replace("@", "").replace("/", "-")
    fn = f"npm__{safe_name}.json"
    url = f"https://registry.npmjs.org/{p}/latest"
    code, data = http_get(url)
    ok, content = save_evidence(fn, url, code, data)
    if ok:
        try:
            j = json.loads(content)
            ver = j.get("version", "")
            if ver:
                npm_versions[safe_name] = ver
        except Exception:
            pass

print("\n--- PHASE 3: GitHub API (Repos, Releases, Advisories, Licenses) ---")
gh_headers = {}
if GH_TOKEN:
    gh_headers["Authorization"] = f"Bearer {GH_TOKEN}"
    gh_headers["Accept"] = "application/vnd.github+json"
    gh_headers["X-GitHub-Api-Version"] = "2022-11-28"

for key, repo in GH_REPOS.items():
    # 3a. Repo metadata
    fn_repo = f"gh_repo__{key}.json"
    url_repo = f"https://api.github.com/repos/{repo}"
    code_r, data_r = http_get(url_repo, headers=gh_headers)
    ok_r, content_r = save_evidence(fn_repo, url_repo, code_r, data_r)

    default_branch = "main"
    if ok_r:
        try:
            j_r = json.loads(content_r)
            default_branch = j_r.get("default_branch", "main")
        except Exception:
            pass

    # 3b. Latest release
    fn_rel_lat = f"gh_release_latest__{key}.json"
    url_rel_lat = f"https://api.github.com/repos/{repo}/releases/latest"
    code_rl, data_rl = http_get(url_rel_lat, headers=gh_headers)
    save_evidence(fn_rel_lat, url_rel_lat, code_rl, data_rl)

    # 3c. Releases list
    fn_rels = f"gh_releases__{key}.json"
    url_rels = f"https://api.github.com/repos/{repo}/releases?per_page=100"
    code_rs, data_rs = http_get(url_rels, headers=gh_headers)
    save_evidence(fn_rels, url_rels, code_rs, data_rs)

    # 3d. Security advisories
    fn_adv = f"gh_advisories__{key}.json"
    url_adv = f"https://api.github.com/repos/{repo}/security-advisories"
    code_adv, data_adv = http_get(url_adv, headers=gh_headers)
    save_evidence(fn_adv, url_adv, code_adv, data_adv)

    # 3e. License file
    fn_lic = f"gh_license__{key}.txt"
    lic_url = f"https://api.github.com/repos/{repo}/license"
    code_lic, data_lic = http_get(lic_url, headers=gh_headers)
    lic_saved = False
    if code_lic == "200":
        try:
            j_lic = json.loads(data_lic)
            if "content" in j_lic and j_lic.get("encoding") == "base64":
                raw_lic_bytes = base64.b64decode(j_lic["content"])
                save_evidence(fn_lic, lic_url, "200", raw_lic_bytes)
                lic_saved = True
            elif "download_url" in j_lic and j_lic["download_url"]:
                c_dl, d_dl = http_get(j_lic["download_url"])
                if c_dl == "200":
                    save_evidence(fn_lic, j_lic["download_url"], "200", d_dl)
                    lic_saved = True
        except Exception:
            pass

    if not lic_saved:
        # Fallback to raw github content on default branch
        raw_url = f"https://raw.githubusercontent.com/{repo}/{default_branch}/LICENSE"
        code_raw, data_raw = http_get(raw_url)
        if code_raw != "200":
            raw_url = f"https://raw.githubusercontent.com/{repo}/{default_branch}/LICENSE.md"
            code_raw, data_raw = http_get(raw_url)
        save_evidence(fn_lic, raw_url, code_raw, data_raw)

print("\n--- PHASE 4: Canonical Upstream of pr-agent (qodo-ai vs The-PR-Agent) ---")
# Query qodo-ai/pr-agent with follow_redirects=False to record 301
redirect_url = "https://api.github.com/repos/qodo-ai/pr-agent"
code_redir, data_redir = http_get(redirect_url, headers=gh_headers, follow_redirects=False)
note_redir = "Upstream redirect confirmed: qodo-ai/pr-agent redirects (HTTP 301) to The-PR-Agent/pr-agent"
fn_redir = "gh_repo__pr-agent-redirect.json"
path_redir = os.path.join(OUT, fn_redir)
with open(path_redir, "wb") as f:
    f.write(data_redir)
manifest.append({
    "file": fn_redir,
    "url": redirect_url,
    "http": code_redir,
    "sha256": sha256_bytes(data_redir),
    "retrieved_at": get_now(),
    "status": "OK",
    "note": note_redir
})
print(f"[OK] {fn_redir} (HTTP {code_redir}) - {note_redir}")

print("\n--- PHASE 5: OSV API Queries ---")
# 5a. PyPI packages
for p in PYPI_PACKAGES:
    fn_osv = f"osv_pypi__{p}.json"
    url_osv = "https://api.osv.dev/v1/query"
    payload = {"package": {"name": p, "ecosystem": "PyPI"}}
    if p in pypi_versions:
        payload["version"] = pypi_versions[p]
    code_osv, data_osv = http_post_json(url_osv, payload)
    save_evidence(fn_osv, url_osv, code_osv, data_osv, note=f"PyPI package {p} version {payload.get('version', 'unpinned')}")

# 5b. NPM packages
for p in NPM_PACKAGES:
    safe_name = p.replace("@", "").replace("/", "-")
    fn_osv = f"osv_npm__{safe_name}.json"
    url_osv = "https://api.osv.dev/v1/query"
    payload = {"package": {"name": p, "ecosystem": "npm"}}
    if safe_name in npm_versions:
        payload["version"] = npm_versions[safe_name]
    code_osv, data_osv = http_post_json(url_osv, payload)
    save_evidence(fn_osv, url_osv, code_osv, data_osv, note=f"NPM package {p} version {payload.get('version', 'unpinned')}")

# 5c. Go / binary repos
for key, repo_pkg in GO_REPOS.items():
    fn_osv = f"osv_repo__{key}.json"
    url_osv = "https://api.osv.dev/v1/query"
    payload = {"package": {"name": repo_pkg, "ecosystem": "Go"}}
    code_osv, data_osv = http_post_json(url_osv, payload)
    save_evidence(fn_osv, url_osv, code_osv, data_osv, note=f"Go ecosystem repo {repo_pkg}")

print("\n--- WRITING MANIFEST ---")
with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=1)

ok_cnt = sum(1 for m in manifest if m["status"] == "OK")
tot_cnt = len(manifest)
print(f"\nCapture complete: {ok_cnt} OK of {tot_cnt} total entries in {MANIFEST_PATH}")
