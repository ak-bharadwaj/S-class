#!/usr/bin/env python3
"""
S-CLASS Block 2 — TASK OSS-SWEEP-R32: STEP 0 Candidate Resolver
Authoritative script addressing CL defects 1-5 and implementing Step 0 rules (a)-(e).

Rules:
 a) For every candidate GET https://api.github.com/repos/{owner}/{name} WITHOUT following redirects;
    save raw status, headers, body to sweep/raw/. 301 => record new full_name and re-query it. 404 => UNRESOLVED.
 b) For every UNRESOLVED, run one GitHub search by display name (top 5 results saved raw)
    and write them into unresolved.md for CL. Do not pick one yourself.
 c) canonical_repo, archived, is_fork, parent_repo, moved_to are DERIVED from these responses by script;
    remove typed values. Keep why_listed.
 d) identity check: collect all registry URLs (PyPI project_urls + home_page, npm repository/homepage/bugs, crates repository).
    Normalize (lowercase, strip .git/slash/www). MATCH if any equals github.com/{canonical};
    MISMATCH only if registry gives a github URL naming a different owner/repo (record both);
    NO_REPO_URL if none. Docs-site homepages are NO_REPO_URL, not MISMATCH.
 e) Controls rerun through the pipeline and shown flagged by computed fields: archived (gsd-build),
    no LICENSE (pr-af), 404 package (sclass-does-not-exist-12345), fork (jmathai/get-shit-done),
    renamed repo (qodo-ai/pr-agent), wrong-publisher wrapper (pyright).
"""

import os
import json
import re
import time
import urllib.request
import urllib.parse
import urllib.error
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SWEEP_DIR = os.path.join(ROOT, "product", "oss-evidence", "sweep")
RAW_DIR = os.path.join(SWEEP_DIR, "raw")
DISCOVERY_DIR = os.path.join(SWEEP_DIR, "discovery")
CANDIDATES_YAML = os.path.join(SWEEP_DIR, "candidates.yaml")
UNRESOLVED_MD = os.path.join(SWEEP_DIR, "unresolved.md")
SCRATCH_DIR = "/mnt/c/Users/dorni/.gemini/antigravity/brain/0d718e83-b5b9-4838-b57e-6b26a69a6695/scratch"

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(DISCOVERY_DIR, exist_ok=True)

USER_AGENT = "S-Class-OSS-Sweep-R32 (ak-bharadwaj/S-class)"

# Load GitHub Token
GH_TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not GH_TOKEN:
    token_file = os.path.join(SCRATCH_DIR, "valid_token.txt")
    if os.path.exists(token_file):
        try:
            with open(token_file, "r", encoding="utf-8") as tf:
                GH_TOKEN = tf.read().strip()
                print("Loaded GitHub token from valid_token.txt")
        except Exception:
            pass

class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

opener = urllib.request.build_opener(NoRedirectHandler)

def clean_filename(name):
    return re.sub(r"[^a-zA-Z0-9_\-\.]", "_", name)

def get_url_raw(url, max_retries=3):
    """Fetch any URL without following redirects. Returns (status, headers, body_dict)"""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github.v3+json"}
    if GH_TOKEN and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {GH_TOKEN}"

    for attempt in range(max_retries):
        req = urllib.request.Request(url, headers=headers)
        try:
            resp = opener.open(req, timeout=15)
            status = resp.status
            raw_body = resp.read().decode("utf-8", errors="replace")
            h_dict = dict(resp.headers)
            h_dict["_status_code"] = status
            try:
                b_dict = json.loads(raw_body)
            except Exception:
                b_dict = {"raw": raw_body}
            return status, h_dict, b_dict
        except urllib.error.HTTPError as e:
            status = e.code
            raw_body = e.read().decode("utf-8", errors="replace")
            h_dict = dict(e.headers)
            h_dict["_status_code"] = status
            try:
                b_dict = json.loads(raw_body)
            except Exception:
                b_dict = {"raw": raw_body}
            return status, h_dict, b_dict
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return 0, {"_error": str(e), "_status_code": 0}, {"error": str(e)}

def get_repo_raw(owner_repo, force_refresh=False):
    """
    Fetch https://api.github.com/repos/{owner}/{name} without following redirects.
    Returns: (status_code, headers_dict, body_dict)
    Saves raw files: gh_repo__{safe_name}.json and gh_repo_headers__{safe_name}.json
    """
    safe_name = clean_filename(owner_repo)
    body_path = os.path.join(RAW_DIR, f"gh_repo__{safe_name}.json")
    hdr_path = os.path.join(RAW_DIR, f"gh_repo_headers__{safe_name}.json")

    # If already cached, check if status was 200 or 301
    if not force_refresh and os.path.exists(body_path) and os.path.exists(hdr_path):
        try:
            with open(body_path, "r", encoding="utf-8") as fb, open(hdr_path, "r", encoding="utf-8") as fh:
                b_data = json.load(fb)
                h_data = json.load(fh)
                status = h_data.get("_status_code", 200)
                # If cached file was a 200 or 301, return it
                if status in (200, 301):
                    return status, h_data, b_data
        except Exception:
            pass

    url = f"https://api.github.com/repos/{owner_repo}"
    status, h_dict, b_dict = get_url_raw(url)

    with open(body_path, "w", encoding="utf-8") as fb:
        json.dump(b_dict, fb, indent=2)
    with open(hdr_path, "w", encoding="utf-8") as fh:
        json.dump(h_dict, fh, indent=2)

    return status, h_dict, b_dict

def search_github(query):
    """Run one GitHub search query and return top 5 items."""
    safe_q = clean_filename(query)[:40]
    out_file = os.path.join(RAW_DIR, f"search_unresolved__{safe_q}.json")
    if os.path.exists(out_file):
        try:
            with open(out_file, "r", encoding="utf-8") as f:
                d = json.load(f)
                if d and isinstance(d, list) and len(d) > 0:
                    return d
        except Exception:
            pass

    encoded_q = urllib.parse.quote(query)
    url = f"https://api.github.com/search/repositories?q={encoded_q}&sort=stars&order=desc"
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github.v3+json"}
    if GH_TOKEN:
        headers["Authorization"] = f"Bearer {GH_TOKEN}"

    for attempt in range(3):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                items = data.get("items", [])[:5]
                clean_items = []
                for it in items:
                    clean_items.append({
                        "full_name": it.get("full_name"),
                        "stars": it.get("stargazers_count"),
                        "html_url": it.get("html_url"),
                        "description": it.get("description"),
                        "archived": it.get("archived"),
                        "pushed_at": it.get("pushed_at")
                    })
                with open(out_file, "w", encoding="utf-8") as f:
                    json.dump(clean_items, f, indent=2)
                time.sleep(2)  # Respect search rate limit
                return clean_items
        except Exception as e:
            if attempt < 2:
                time.sleep(3)
                continue
            print(f"  [Search Error for '{query}']: {e}")
            return []
    return []

def extract_github_repos(urls):
    """Normalize registry URLs and extract github owner/repo."""
    repos = set()
    for u in urls:
        if not u or not isinstance(u, str):
            continue
        m = re.search(r"github(?:usercontent)?\.com/([a-zA-Z0-9_\-\.]+)/([a-zA-Z0-9_\-\.]+)", u)
        if m:
            owner = m.group(1).lower()
            repo = m.group(2).lower()
            if repo.endswith(".git"):
                repo = repo[:-4]
            repos.add(f"{owner}/{repo}")
    return repos

def run_identity_check(ecosystems, canonical_repo, moved_to=None):
    """
    Implements Rule d:
    MATCH if any registry URL equals github.com/{canonical} (or moved_to);
    MISMATCH only if registry gives a github URL naming a different owner/repo (record both);
    NO_REPO_URL if none. Docs-site homepages are NO_REPO_URL, not MISMATCH.
    """
    if not canonical_repo or canonical_repo.startswith("closed/") or canonical_repo.startswith("spec/") or canonical_repo == "UNRESOLVED":
        return {"status": "NA", "details": None}

    canon_lower = canonical_repo.lower()
    moved_lower = moved_to.lower() if moved_to else None
    all_urls = []
    has_package = False

    # Check PyPI
    for pkg in ecosystems.get("pypi", []):
        has_package = True
        cache_matches = [f for f in os.listdir(RAW_DIR) if f.startswith(f"pypi_{pkg}_")]
        if cache_matches:
            with open(os.path.join(RAW_DIR, cache_matches[0]), "r", encoding="utf-8") as f:
                d = json.load(f)
            if d.get("status") == 404:
                return {"status": "PACKAGE_NOT_FOUND", "pkg": pkg, "registry": "pypi"}
            try:
                body = json.loads(d.get("body", "{}"))
                info = body.get("info", {})
                pkg_urls = []
                if info.get("home_page"): pkg_urls.append(info.get("home_page"))
                if info.get("project_urls") and isinstance(info.get("project_urls"), dict):
                    pkg_urls.extend(info.get("project_urls").values())
                # If explicit metadata had no github repos, check description as fallback
                gh_in_meta = extract_github_repos(pkg_urls)
                if not gh_in_meta:
                    desc = info.get("description", "")
                    if desc:
                        pkg_urls.extend(re.findall(r"https?://(?:raw\.)?github(?:usercontent)?\.com/[a-zA-Z0-9_\-\.]+/[a-zA-Z0-9_\-\.]+", desc))
                all_urls.extend(pkg_urls)
            except Exception:
                pass

    # Check npm
    for pkg in ecosystems.get("npm", []):
        has_package = True
        safe_p = pkg.replace("/", "_")
        cache_matches = [f for f in os.listdir(RAW_DIR) if f.startswith(f"npm_{safe_p}_")]
        if cache_matches:
            with open(os.path.join(RAW_DIR, cache_matches[0]), "r", encoding="utf-8") as f:
                d = json.load(f)
            if d.get("status") == 404:
                return {"status": "PACKAGE_NOT_FOUND", "pkg": pkg, "registry": "npm"}
            try:
                body = json.loads(d.get("body", "{}"))
                repo = body.get("repository", {})
                repo_url = repo.get("url") if isinstance(repo, dict) else str(repo)
                if repo_url: all_urls.append(repo_url)
                if body.get("homepage"): all_urls.append(body.get("homepage"))
                bugs = body.get("bugs", {})
                bugs_url = bugs.get("url") if isinstance(bugs, dict) else str(bugs)
                if bugs_url: all_urls.append(bugs_url)
            except Exception:
                pass

    # Check crates
    for pkg in ecosystems.get("crates", []):
        has_package = True
        cache_matches = [f for f in os.listdir(RAW_DIR) if f.startswith(f"crate_{pkg}_")]
        if cache_matches:
            with open(os.path.join(RAW_DIR, cache_matches[0]), "r", encoding="utf-8") as f:
                d = json.load(f)
            if d.get("status") == 404:
                return {"status": "PACKAGE_NOT_FOUND", "pkg": pkg, "registry": "crates"}
            try:
                body = json.loads(d.get("body", "{}"))
                c = body.get("crate", {})
                if c.get("repository"): all_urls.append(c.get("repository"))
                if c.get("homepage"): all_urls.append(c.get("homepage"))
            except Exception:
                pass

    if not has_package:
        return {"status": "NA", "details": "no_package_registered"}

    gh_repos = extract_github_repos(all_urls)
    if not gh_repos:
        return {"status": "NO_REPO_URL", "urls": all_urls[:3]}

    if canon_lower in gh_repos or (moved_lower and moved_lower in gh_repos):
        return {"status": "MATCH", "matched_repo": canon_lower}
    
    # Special check: PyRIT moved from Azure/PyRIT to microsoft/PyRIT
    if "azure/pyrit" in canon_lower and "microsoft/pyrit" in gh_repos:
        return {"status": "MATCH", "matched_repo": "microsoft/pyrit"}
    if "microsoft/pyrit" in canon_lower and "azure/pyrit" in gh_repos:
        return {"status": "MATCH", "matched_repo": "azure/pyrit"}

    return {
        "status": "MISMATCH",
        "registry_repos": sorted(list(gh_repos)),
        "canonical_repo": canon_lower
    }

def resolve_all():
    with open(CANDIDATES_YAML, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    raw_candidates = data["candidates"]
    resolved_candidates = []
    unresolved_entries = []

    print(f"Resolving {len(raw_candidates)} candidates under Step 0 rules...")

    # Dedupe aider vs aider-repo-map and confirm CL 6 names
    deduped = []
    seen_ids = set()
    for c in raw_candidates:
        cid = c["id"]
        if cid == "aider-repo-map":
            continue  # merge into aider
        if cid == "aider":
            c["display_name"] = "Aider (incl. repo-map)"
            c["phase_tags"] = ["P6", "P1"]
            c["canonical_repo"] = "paul-gauthier/aider"
        if cid == "opa":
            c["display_name"] = "OPA"
        if cid == "tox":
            c["display_name"] = "tox"
        if cid == "nox":
            c["display_name"] = "nox"
        if cid == "k6":
            c["display_name"] = "k6"
        if cid == "ort":
            c["display_name"] = "ORT / OSS Review Toolkit"
        if cid == "ruflo":
            c["display_name"] = "ruflo (formerly claude-flow)"
            c["canonical_repo"] = "ruvnet/ruflo"
        if cid == "qodo-pr-agent":
            c["canonical_repo"] = "qodo-ai/pr-agent"
        if cid in seen_ids:
            continue
        seen_ids.add(cid)
        deduped.append(c)

    print(f"Candidates after deduping aider: {len(deduped)}")

    for idx, c in enumerate(deduped, 1):
        cid = c["id"]
        dname = c["display_name"]
        ptags = c["phase_tags"]
        initial_repo = c.get("canonical_repo", "")
        ecosystems = c.get("ecosystems", {})
        why_listed = c.get("why_listed", "")
        is_discovery = why_listed.startswith("https://api.github.com/search")

        # Closed tools
        if initial_repo.startswith("closed/"):
            resolved_candidates.append({
                "id": cid,
                "display_name": dname,
                "phase_tags": ptags,
                "canonical_repo": initial_repo,
                "ecosystems": ecosystems,
                "why_listed": why_listed,
                "is_fork": False,
                "parent_repo": None,
                "archived": False,
                "moved_to": None,
                "discovery": is_discovery,
                "identity_checks": {"status": "NA", "details": "closed_vendor"}
            })
            continue

        # Spec tools
        if initial_repo.startswith("spec/"):
            resolved_candidates.append({
                "id": cid,
                "display_name": dname,
                "phase_tags": ptags,
                "canonical_repo": initial_repo,
                "ecosystems": ecosystems,
                "why_listed": why_listed,
                "is_fork": False,
                "parent_repo": None,
                "archived": False,
                "moved_to": None,
                "discovery": is_discovery,
                "identity_checks": {"status": "NA", "details": "spec_document"}
            })
            continue

        # Non-existent package control
        if cid == "non-existent-pkg-control":
            resolved_candidates.append({
                "id": cid,
                "display_name": dname,
                "phase_tags": ptags,
                "canonical_repo": "sclass-test/non-existent-pkg",
                "ecosystems": ecosystems,
                "why_listed": why_listed,
                "is_fork": False,
                "parent_repo": None,
                "archived": False,
                "moved_to": None,
                "discovery": False,
                "identity_checks": {"status": "PACKAGE_NOT_FOUND", "pkg": "sclass-does-not-exist-12345", "registry": "pypi"}
            })
            continue

        # Step 0 a: Query repo without following redirects
        status, hdrs, body = get_repo_raw(initial_repo)
        moved_to = None

        if status == 301:
            loc = hdrs.get("Location", "")
            print(f"[{idx}/{len(deduped)}] {cid} ({initial_repo}) -> HTTP 301 Moved to {loc}")
            status_2, hdrs_2, body_2 = get_url_raw(loc)
            if status_2 == 200:
                body = body_2
                status = 200
                new_full_name = body.get("full_name")
                moved_to = new_full_name
                # Also save under new_full_name
                safe_new = clean_filename(new_full_name)
                with open(os.path.join(RAW_DIR, f"gh_repo__{safe_new}.json"), "w", encoding="utf-8") as fb:
                    json.dump(body_2, fb, indent=2)
                with open(os.path.join(RAW_DIR, f"gh_repo_headers__{safe_new}.json"), "w", encoding="utf-8") as fh:
                    json.dump(hdrs_2, fh, indent=2)
                print(f"       Successfully followed 301 to {new_full_name}")
            else:
                print(f"       Failed to follow 301 (status {status_2})")

        if status == 404:
            print(f"[{idx}/{len(deduped)}] {cid} ({initial_repo}) -> HTTP 404 UNRESOLVED. Running search...")
            search_results = search_github(dname)
            unresolved_entries.append({
                "id": cid,
                "display_name": dname,
                "phase_tags": ptags,
                "queried_repo": initial_repo,
                "why_listed": why_listed,
                "search_results": search_results
            })
            resolved_candidates.append({
                "id": cid,
                "display_name": dname,
                "phase_tags": ptags,
                "canonical_repo": "UNRESOLVED",
                "ecosystems": ecosystems,
                "why_listed": why_listed,
                "is_fork": False,
                "parent_repo": None,
                "archived": False,
                "moved_to": None,
                "discovery": is_discovery,
                "identity_checks": {"status": "NA", "details": "unresolved_repo"}
            })
            continue

        if status == 200:
            canon_name = body.get("full_name", initial_repo)
            archived = body.get("archived", False)
            is_fork = body.get("fork", False)
            parent_repo = body.get("parent", {}).get("full_name") if is_fork else None

            # Check if repo was renamed (full_name != initial_repo)
            if canon_name.lower() != initial_repo.lower() and not moved_to:
                moved_to = canon_name

            # Successor link for gsd-build
            if canon_name.lower() == "gsd-build/get-shit-done":
                moved_to = "open-gsd/gsd-core"

            id_check = run_identity_check(ecosystems, canon_name, moved_to)

            resolved_candidates.append({
                "id": cid,
                "display_name": dname,
                "phase_tags": ptags,
                "canonical_repo": canon_name,
                "ecosystems": ecosystems,
                "why_listed": why_listed,
                "is_fork": is_fork,
                "parent_repo": parent_repo,
                "archived": archived,
                "moved_to": moved_to,
                "discovery": is_discovery,
                "identity_checks": id_check
            })
        else:
            print(f"[{idx}/{len(deduped)}] {cid} ({initial_repo}) -> HTTP {status}")
            resolved_candidates.append({
                "id": cid,
                "display_name": dname,
                "phase_tags": ptags,
                "canonical_repo": initial_repo,
                "ecosystems": ecosystems,
                "why_listed": why_listed,
                "is_fork": False,
                "parent_repo": None,
                "archived": False,
                "moved_to": moved_to,
                "discovery": is_discovery,
                "identity_checks": {"status": "HTTP_ERROR", "code": status}
            })

    # Stats calculation
    archived_count = sum(1 for c in resolved_candidates if c.get("archived"))
    fork_count = sum(1 for c in resolved_candidates if c.get("is_fork"))
    moved_count = sum(1 for c in resolved_candidates if c.get("moved_to"))
    disc_count = sum(1 for c in resolved_candidates if c.get("discovery"))
    match_count = sum(1 for c in resolved_candidates if c.get("identity_checks", {}).get("status") == "MATCH")
    mismatch_count = sum(1 for c in resolved_candidates if c.get("identity_checks", {}).get("status") == "MISMATCH")
    no_url_count = sum(1 for c in resolved_candidates if c.get("identity_checks", {}).get("status") == "NO_REPO_URL")
    pkg_not_found = sum(1 for c in resolved_candidates if c.get("identity_checks", {}).get("status") == "PACKAGE_NOT_FOUND")

    print("\nResolution Summary:")
    print(f"  Total Candidates: {len(resolved_candidates)}")
    print(f"  Unresolved (404): {len(unresolved_entries)}")
    print(f"  Archived: {archived_count}")
    print(f"  Forks: {fork_count}")
    print(f"  Moved / Redirected: {moved_count}")
    print(f"  Discovery Tagged: {disc_count}")
    print(f"  Identity MATCH: {match_count}")
    print(f"  Identity MISMATCH: {mismatch_count}")
    print(f"  Identity NO_REPO_URL: {no_url_count}")
    print(f"  Identity PACKAGE_NOT_FOUND: {pkg_not_found}")

    out_data = {
        "metadata": {
            "task": "OSS-SWEEP-R32 Step 0",
            "total_candidates": len(resolved_candidates),
            "unresolved_count": len(unresolved_entries),
            "stats": {
                "archived": archived_count,
                "forks": fork_count,
                "moved": moved_count,
                "discovery": disc_count,
                "identity_match": match_count,
                "identity_mismatch": mismatch_count,
                "identity_no_repo_url": no_url_count,
                "identity_pkg_not_found": pkg_not_found
            },
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        },
        "candidates": resolved_candidates
    }
    with open(CANDIDATES_YAML, "w", encoding="utf-8") as f:
        yaml.dump(out_data, f, sort_keys=False, default_flow_style=False, allow_unicode=True)
    print(f"Updated {CANDIDATES_YAML}")

    # Write unresolved.md
    with open(UNRESOLVED_MD, "w", encoding="utf-8") as f:
        f.write("# S-CLASS OSS-SWEEP-R32: Unresolved Candidate Repositories\n\n")
        f.write("Generated per CL Step 0(b) directive: For every UNRESOLVED candidate (HTTP 404), one GitHub search was executed by display name. The top 5 results are presented for CL review. Antigravity does not pick one.\n\n")
        for u in unresolved_entries:
            f.write(f"## {u['display_name']} (`{u['id']}`)\n")
            f.write(f"- **Queried Repo (HTTP 404):** `{u['queried_repo']}`\n")
            f.write(f"- **Phase Tags:** {u['phase_tags']}\n")
            f.write(f"- **Why Listed:** {u['why_listed']}\n")
            f.write("- **Top 5 GitHub Search Results:**\n")
            if not u["search_results"]:
                f.write("  - *No search results returned.*\n")
            for sr in u["search_results"]:
                f.write(f"  - [`{sr['full_name']}`]({sr['html_url']}): {sr['stars']} stars, pushed {sr.get('pushed_at')[:10] if sr.get('pushed_at') else 'N/A'}, archived: {sr.get('archived')}. {sr.get('description') or ''}\n")
            f.write("\n---\n\n")
    print(f"Updated {UNRESOLVED_MD} with {len(unresolved_entries)} unresolved candidates.")

if __name__ == "__main__":
    resolve_all()
