#!/usr/bin/env python3
"""GitHub API and Authentication helper for S-Class integration."""
import os
import sys
import json
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

REPO = "ak-bharadwaj/S-class"

def get_token() -> str:
    # 1. Environment variable
    if os.environ.get("GH_TOKEN"):
        return os.environ["GH_TOKEN"].strip()
    if os.environ.get("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"].strip()

    # 2. PowerShell CredManager
    ps_cmd = r"""
Add-Type @'
using System;
using System.Runtime.InteropServices;
using System.Text;

public class CredManager {
    [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    public static extern bool CredRead(string target, int type, int reservedFlag, out IntPtr credentialPtr);
    [DllImport("advapi32.dll", SetLastError = true)]
    public static extern void CredFree(IntPtr credentialPtr);

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct CREDENTIAL {
        public int Flags;
        public int Type;
        public string TargetName;
        public string Comment;
        public long LastWritten;
        public int CredentialBlobSize;
        public IntPtr CredentialBlob;
        public int Persist;
        public int AttributeCount;
        public IntPtr Attributes;
        public string TargetAlias;
        public string UserName;
    }

    public static string GetPassword(string target) {
        IntPtr ptr;
        if (CredRead(target, 1, 0, out ptr)) {
            var cred = (CREDENTIAL)Marshal.PtrToStructure(ptr, typeof(CREDENTIAL));
            byte[] bytes = new byte[cred.CredentialBlobSize];
            Marshal.Copy(cred.CredentialBlob, bytes, 0, cred.CredentialBlobSize);
            CredFree(ptr);
            return Encoding.Unicode.GetString(bytes);
        }
        return null;
    }
}
'@
$p = [CredManager]::GetPassword('git:https://x-access-token@github.com')
if (-not $p) { $p = [CredManager]::GetPassword('git:https://github.com') }
[Console]::Write($p.Trim())
"""
    try:
        res = subprocess.run(["powershell.exe", "-Command", ps_cmd], capture_output=True, text=True, check=True)
        token = res.stdout.strip()
        if token:
            return token
    except Exception as e:
        pass

    raise RuntimeError("GitHub token could not be retrieved from env or CredManager")

def get_gh_env() -> dict:
    token = get_token()
    env = os.environ.copy()
    env["GH_TOKEN"] = token
    env["GITHUB_TOKEN"] = token
    return env

def run_gh(args: list) -> subprocess.CompletedProcess:
    env = get_gh_env()
    gh_bin = "/mnt/c/Program Files/GitHub CLI/gh.exe"
    if not os.path.exists(gh_bin):
        gh_bin = "gh"
    return subprocess.run([gh_bin] + args, env=env, capture_output=True, text=True)

def api_request(method: str, endpoint: str, data: dict = None) -> dict:
    token = get_token()
    url = f"https://api.github.com/{endpoint.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "Antigravity-Agent"
    }
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="replace")
        print(f"HTTPError {e.code} for {url}: {err_msg}", file=sys.stderr)
        raise

if __name__ == "__main__":
    t = get_token()
    print(f"Token acquired! Length: {len(t)}, Prefix: {t[:4]}")
    res = run_gh(["auth", "status"])
    print("gh auth status:")
    print(res.stdout + res.stderr)
