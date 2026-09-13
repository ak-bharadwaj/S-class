"""
S-Class Survival v0: Canonical Evidence Receipt Generation (sclass/survival/evidence.py)

Implements Phase 4:
Receipts capture independently observed execution and repository state.
The agent is NEVER authoritative for:
- exit_code
- files_changed
- test result
- verification status
"""

from __future__ import annotations
import os
import sys
import json
import uuid
import shlex
import shutil
import hashlib
import subprocess
import re
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple

from sclass.survival.models import (
    EvidenceReceipt,
    ObservedReceipt,
    ProposedEvidence,
    ClaimedEvidence,
    LIFECYCLE_OBSERVED,
    _OBSERVATION_TOKEN,
    ObservationIntegrityError,
)

KNOWN_TEST_VERIFIERS = {
    "pytest": "pytest",
    "unittest": "unittest",
    "jest": "jest",
    "vitest": "vitest",
    "mocha": "mocha",
    "playwright": "playwright",
    "cargo test": "cargo",
    "go test": "go",
}


def detect_execution_kind(command: str) -> Tuple[str, str]:
    """Detects execution kind ('test_runner' vs 'generic_command') and verifier name from command."""
    cmd_lower = (command or "").strip().lower()
    for pattern, verifier_name in KNOWN_TEST_VERIFIERS.items():
        if re.search(r"\b" + re.escape(pattern) + r"\b", cmd_lower):
            return "test_runner", verifier_name
    return "generic_command", ""


UNSAFE_SHELL_PATTERNS = [";", "&&", "||", "|", "`", "$(", "${", "\n", "\r", ">", "<"]


def sanitize_verification_command(command: str) -> List[str]:
    """
    Validates and securely tokenizes a verification command, preventing shell injection.
    """
    for pat in UNSAFE_SHELL_PATTERNS:
        if pat in command:
            raise ValueError(f"Security boundary violation: shell injection or chaining operator '{pat}' detected in verification command.")

    tokens = shlex.split(command, posix=(sys.platform != "win32"))
    if not tokens:
        raise ValueError("Empty verification command.")
    return tokens


def resolve_executable_tokens(cmd_tokens: List[str]) -> List[str]:
    """Resolves command tokens to ensure safe, cross-platform execution without shell=True."""
    if not cmd_tokens:
        return cmd_tokens
    resolved = list(cmd_tokens)
    first = resolved[0]
    if first == "pytest" and not shutil.which("pytest"):
        return [sys.executable, "-m", "pytest"] + resolved[1:]
    if first in ("python", "python3") and not shutil.which(first):
        return [sys.executable] + resolved[1:]
    return resolved


def compute_file_hash(abs_path: str) -> Optional[str]:
    """Computes SHA256 of a file if it exists and is a regular file."""
    if not os.path.exists(abs_path) or os.path.isdir(abs_path):
        return None
    try:
        h = hashlib.sha256()
        with open(abs_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def compute_file_hashes(workspace_dir: str, files: List[str]) -> Dict[str, str]:
    """Computes path -> sha256 content hash mapping for given files in workspace."""
    hashes: Dict[str, str] = {}
    ws = os.path.abspath(workspace_dir)
    for rel_path in sorted(files):
        clean_rel = rel_path.replace("\\", "/").strip()
        if not clean_rel or clean_rel.startswith(".agents"):
            continue
        full_path = os.path.join(ws, clean_rel)
        f_hash = compute_file_hash(full_path)
        if f_hash is not None:
            hashes[clean_rel] = f_hash
    return hashes


def _get_git_commit_hash(workspace_dir: str) -> str:
    """Resolves current HEAD commit hash via git."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except Exception:
        pass
    return "0" * 40


def _get_git_changed_files(workspace_dir: str, base_commit: str) -> List[str]:
    """Resolves modified and untracked files relative to base_commit."""
    changed = set()
    try:
        if base_commit and base_commit != "0" * 40:
            proc_diff = subprocess.run(
                ["git", "diff", "--name-only", base_commit],
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            if proc_diff.returncode == 0:
                for line in proc_diff.stdout.splitlines():
                    if line.strip():
                        changed.add(line.strip().replace("\\", "/"))

        proc_status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc_status.returncode == 0:
            for line in proc_status.stdout.splitlines():
                if len(line) > 3:
                    file_part = line[3:].strip().replace("\\", "/")
                    if file_part:
                        changed.add(file_part)
    except Exception:
        pass
    return sorted(list(changed))


def canonical_json(data: Any) -> str:
    """Serializes data into canonical, deterministic JSON representation."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def _parse_git_status_porcelain(workspace_dir: str) -> Dict[str, List[str]]:
    """Extracts granular Git worktree and index modifications via porcelain output."""
    git_state: Dict[str, List[str]] = {
        "index_state": [],
        "tracked_modifications": [],
        "untracked_files": [],
        "deleted_files": [],
        "renamed_files": [],
    }
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain=v1", "-uall"],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                if len(line) < 4:
                    continue
                code = line[:2]
                path_part = line[3:].strip().replace("\\", "/")
                if path_part.startswith(".agents"):
                    continue
                index_col = code[0]
                worktree_col = code[1]

                if code == "??":
                    git_state["untracked_files"].append(path_part)
                else:
                    if index_col not in (" ", "?"):
                        git_state["index_state"].append(f"{index_col}:{path_part}")
                    if worktree_col in ("M", "A"):
                        git_state["tracked_modifications"].append(path_part)
                    if "D" in (index_col, worktree_col):
                        git_state["deleted_files"].append(path_part)
                    if "R" in (index_col, worktree_col):
                        git_state["renamed_files"].append(path_part)
    except Exception:
        pass
    for k in git_state:
        git_state[k] = sorted(list(set(git_state[k])))
    return git_state


def _is_symlink_or_reparse(path: str) -> bool:
    if os.path.islink(path):
        return True
    try:
        import stat
        st = os.lstat(path)
        if hasattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT") and hasattr(st, "st_file_attributes"):
            if st.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                return True
    except Exception:
        pass
    return False


def _safe_read_link(path: str) -> Optional[str]:
    try:
        target = os.readlink(path)
        if target:
            if target.startswith("\\\\?\\"):
                target = target[4:]
            return target.replace("\\", "/")
    except Exception:
        pass
    return None


def compute_workspace_snapshot(workspace_dir: str) -> Dict[str, Any]:
    """
    Captures a comprehensive filesystem and Git state snapshot of the workspace.
    Covers regular files, symlinks, directories, permissions/modes, sizes,
    and Git index/tracked/untracked/deleted/renamed state.
    Excludes .agents and .git directories.
    """
    ws_clean = os.path.abspath(workspace_dir)
    files: List[Dict[str, Any]] = []

    if os.path.exists(ws_clean):
        for root, dirs, filenames in os.walk(ws_clean, topdown=True, followlinks=False):
            # In-place filter out .git and .agents
            dirs[:] = [d for d in dirs if d not in (".git", ".agents")]
            rel_root = os.path.relpath(root, ws_clean).replace("\\", "/")
            if rel_root != ".":
                is_dir_link = _is_symlink_or_reparse(root)
                link_target = _safe_read_link(root) if is_dir_link else None
                try:
                    st = os.lstat(root) if is_dir_link else os.stat(root)
                    mode = oct(st.st_mode)[-4:]
                except Exception:
                    mode = "0000"
                files.append({
                    "path": rel_root,
                    "type": "symlink" if is_dir_link else "directory",
                    "content_hash": None,
                    "link_target": link_target,
                    "mode": mode,
                    "size": 0,
                })
                if is_dir_link:
                    dirs[:] = []
                    continue

            for fname in filenames:
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, ws_clean).replace("\\", "/")
                if rel.startswith(".agents/") or rel.startswith(".git/") or rel in (".agents", ".git"):
                    continue

                is_link = _is_symlink_or_reparse(full)
                link_target = _safe_read_link(full) if is_link else None
                c_hash = None
                size = 0
                mode = "0000"

                if not is_link:
                    c_hash = compute_file_hash(full)

                try:
                    st = os.lstat(full) if is_link else os.stat(full)
                    mode = oct(st.st_mode)[-4:]
                    size = st.st_size
                except Exception:
                    pass

                f_type = "symlink" if is_link else ("directory" if os.path.isdir(full) else "file")
                files.append({
                    "path": rel,
                    "type": f_type,
                    "content_hash": c_hash,
                    "link_target": link_target,
                    "mode": mode,
                    "size": size,
                })

    files.sort(key=lambda x: x["path"])

    git_state = _parse_git_status_porcelain(ws_clean)
    git_head = _get_git_commit_hash(ws_clean)

    return {
        "files": files,
        "git_state": {
            "head": git_head,
            "index_state": git_state["index_state"],
            "tracked_modifications": git_state["tracked_modifications"],
            "untracked_files": git_state["untracked_files"],
            "deleted_files": git_state["deleted_files"],
            "renamed_files": git_state["renamed_files"],
        },
    }


def compute_workspace_fingerprint(snapshot_or_workspace: Any) -> str:
    """Computes canonical SHA256 cryptographic digest of a workspace snapshot."""
    if isinstance(snapshot_or_workspace, str):
        snapshot = compute_workspace_snapshot(snapshot_or_workspace)
    elif isinstance(snapshot_or_workspace, dict):
        snapshot = snapshot_or_workspace
    else:
        snapshot = {}
    canonical_str = canonical_json(snapshot)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


def _create_observed_receipt(
    task_id: str,
    claim_id: str,
    agent: str,
    action: str,
    workspace: str,
    command: str,
    exit_code: int,
    started_at: str,
    finished_at: str,
    stdout_content: str,
    stderr_content: str,
    base_commit: Optional[str] = None,
    result_commit: Optional[str] = None,
    files_changed: Optional[List[str]] = None,
    file_hashes: Optional[Dict[str, str]] = None,
    evidence: Optional[List[Dict[str, Any]]] = None,
    verified: bool = False,
    metadata: Optional[Dict[str, Any]] = None,
    workspace_snapshot: Optional[Dict[str, Any]] = None,
    workspace_fingerprint: Optional[str] = None,
    workspace_snapshot_before: Optional[Dict[str, Any]] = None,
    workspace_fingerprint_before: Optional[str] = None,
    execution_kind: Optional[str] = None,
    verifier: Optional[str] = None,
    is_observed: bool = True,
    **kwargs: Any,
) -> ObservedReceipt:
    """
    Creates an authentic ObservedReceipt with cryptographic hashes of stdout/stderr,
    file states, and comprehensive workspace fingerprint.
    Private to the observation engine; ordinary callers cannot establish observation.
    """
    ws = os.path.abspath(workspace)
    b_commit = base_commit or _get_git_commit_hash(ws)
    r_commit = result_commit or _get_git_commit_hash(ws)
    f_changed = files_changed if files_changed is not None else _get_git_changed_files(ws, b_commit)
    f_hashes = file_hashes if file_hashes is not None else compute_file_hashes(ws, f_changed)

    stdout_hash = hashlib.sha256(stdout_content.encode("utf-8")).hexdigest()
    stderr_hash = hashlib.sha256(stderr_content.encode("utf-8")).hexdigest()

    if workspace_snapshot is None:
        workspace_snapshot = compute_workspace_snapshot(ws)
    if workspace_fingerprint is None:
        workspace_fingerprint = compute_workspace_fingerprint(workspace_snapshot)
    if workspace_snapshot_before is None:
        workspace_snapshot_before = workspace_snapshot
    if workspace_fingerprint_before is None:
        workspace_fingerprint_before = workspace_fingerprint

    if not execution_kind or not verifier:
        det_kind, det_ver = detect_execution_kind(command)
        if not execution_kind:
            execution_kind = det_kind
        if not verifier:
            verifier = det_ver

    receipt_id = f"rcpt_{uuid.uuid4().hex[:12]}"
    meta = dict(metadata or {})
    meta["workspace_snapshot"] = workspace_snapshot
    meta["workspace_fingerprint"] = workspace_fingerprint
    meta["workspace_snapshot_before"] = workspace_snapshot_before
    meta["workspace_fingerprint_before"] = workspace_fingerprint_before
    if stderr_content:
        meta["stderr"] = stderr_content

    receipt = ObservedReceipt(
        receipt_id=receipt_id,
        task_id=task_id,
        claim_id=claim_id,
        agent=agent,
        action=action,
        workspace=ws,
        base_commit=b_commit,
        result_commit=r_commit,
        command=command,
        exit_code=exit_code,
        started_at=started_at,
        finished_at=finished_at,
        stdout_hash=stdout_hash,
        stderr_hash=stderr_hash,
        files_changed=f_changed,
        file_hashes=f_hashes,
        evidence=evidence or [],
        metadata=meta,
        execution_kind=execution_kind,
        verifier=verifier,
        workspace_fingerprint=workspace_fingerprint,
        lifecycle_state=LIFECYCLE_OBSERVED,
        verified=False,
    )
    receipt.receipt_hash = receipt.compute_hash()

    # Save receipt to S-Class protected receipts directory
    save_receipt(receipt, ws)

    # Automatically anchor in local ledger if not explicitly skipped
    if not kwargs.get("skip_ledger", False):
        ledger = kwargs.get("ledger")
        if ledger is None and ws and os.path.exists(ws):
            try:
                from sclass.survival.ledger import LocalLedger
                ledger = LocalLedger(workspace_dir=ws)
            except Exception:
                ledger = None
        if ledger is not None:
            try:
                ledger.append(
                    "OBSERVATION",
                    {
                        "receipt_id": receipt.receipt_id,
                        "receipt_hash": receipt.receipt_hash,
                        "fingerprint_before": workspace_fingerprint_before or meta.get("workspace_fingerprint_before", ""),
                        "fingerprint_after": workspace_fingerprint,
                        "command": command,
                        "exit_code": exit_code,
                        "execution_kind": receipt.execution_kind,
                        "verifier": receipt.verifier,
                        "timestamp": finished_at,
                    },
                )
            except Exception as append_err:
                if kwargs.get("strict_ledger", False):
                    raise ObservationIntegrityError(f"Observation completed but provenance could not be anchored: {append_err}") from append_err

    return receipt


def create_receipt(
    task_id: str = "task_default",
    claim_id: str = "claim_default",
    agent: str = "agent",
    action: str = "custom",
    workspace: str = "",
    command: str = "",
    exit_code: int = 0,
    started_at: Optional[str] = None,
    finished_at: Optional[str] = None,
    stdout_content: str = "",
    stderr_content: str = "",
    base_commit: Optional[str] = None,
    result_commit: Optional[str] = None,
    files_changed: Optional[List[str]] = None,
    file_hashes: Optional[Dict[str, str]] = None,
    evidence: Optional[List[Dict[str, Any]]] = None,
    verified: bool = False,
    metadata: Optional[Dict[str, Any]] = None,
    workspace_snapshot: Optional[Dict[str, Any]] = None,
    workspace_fingerprint: Optional[str] = None,
    is_observed: bool = False,
    **kwargs: Any,
) -> EvidenceReceipt:
    """
    Deprecated and privatized creation path. Public callers cannot establish observation capability.
    Strictly returns an unobserved EvidenceReceipt (is_observed is False).
    External callers must use observe_command() for authentic observation
    or create_proposed_evidence() for untrusted assertions.
    """
    ws = os.path.abspath(workspace or os.getcwd())
    b_commit = base_commit or _get_git_commit_hash(ws)
    r_commit = result_commit or _get_git_commit_hash(ws)
    f_changed = files_changed if files_changed is not None else _get_git_changed_files(ws, b_commit)
    f_hashes = file_hashes if file_hashes is not None else compute_file_hashes(ws, f_changed)

    stdout_hash = hashlib.sha256((stdout_content or "").encode("utf-8")).hexdigest()
    stderr_hash = hashlib.sha256((stderr_content or "").encode("utf-8")).hexdigest()

    if workspace_snapshot is None and ws and os.path.exists(ws):
        workspace_snapshot = compute_workspace_snapshot(ws)
    if workspace_fingerprint is None and workspace_snapshot:
        workspace_fingerprint = compute_workspace_fingerprint(workspace_snapshot)

    receipt_id = f"rcpt_{uuid.uuid4().hex[:12]}"
    meta = dict(metadata or {})
    if workspace_snapshot:
        meta["workspace_snapshot"] = workspace_snapshot
    if workspace_fingerprint:
        meta["workspace_fingerprint"] = workspace_fingerprint
    if stderr_content:
        meta["stderr"] = stderr_content

    now = datetime.now(timezone.utc).isoformat()
    receipt = EvidenceReceipt(
        receipt_id=receipt_id,
        task_id=task_id,
        claim_id=claim_id,
        agent=agent,
        action=action,
        workspace=ws,
        base_commit=b_commit,
        result_commit=r_commit,
        command=command,
        exit_code=exit_code,
        started_at=started_at or now,
        finished_at=finished_at or now,
        stdout_hash=stdout_hash,
        stderr_hash=stderr_hash,
        files_changed=f_changed,
        file_hashes=f_hashes,
        evidence=evidence or [],
        metadata=meta,
        workspace_fingerprint=workspace_fingerprint or "",
        lifecycle_state=LIFECYCLE_OBSERVED,
        verified=False,
        is_observed=False,
        _observation_token=None,
    )
    receipt.receipt_hash = receipt.compute_hash()
    return receipt


def create_proposed_evidence(
    statement: str = "",
    exit_code: Optional[int] = None,
    files_changed: Optional[List[str]] = None,
    evidence: Optional[List[Dict[str, Any]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> ProposedEvidence:
    """Creates caller- or agent-proposed evidence (explicitly unobserved and non-authoritative)."""
    return ProposedEvidence(
        statement=statement,
        exit_code=exit_code,
        files_changed=tuple(files_changed or []),
        evidence=tuple(evidence or []),
        metadata=dict(metadata or {}),
        is_observed=False,
    )


def save_receipt(receipt: EvidenceReceipt, workspace_dir: str) -> str:
    """Saves receipt to .agents/receipts/{receipt_id}.json (SCLASS_ONLY)."""
    receipts_dir = os.path.join(workspace_dir, ".agents", "receipts")
    os.makedirs(receipts_dir, exist_ok=True)
    target = os.path.join(receipts_dir, f"{receipt.receipt_id}.json")
    with open(target, "w", encoding="utf-8") as f:
        json.dump(receipt.to_dict(), f, indent=2)
    return target


def load_receipt(receipt_id: str, workspace_dir: str) -> Optional[EvidenceReceipt]:
    """
    Loads and validates a receipt from .agents/receipts/{receipt_id}.json.
    Strictly forbids absolute paths and directory traversal.
    Missing, invalid, or forged hash returns None.
    """
    if not receipt_id or not isinstance(receipt_id, str):
        return None
    # Reject path traversal and absolute path attempts
    if ".." in receipt_id or "/" in receipt_id or "\\" in receipt_id or os.path.isabs(receipt_id):
        return None

    clean_id = receipt_id[:-5] if receipt_id.endswith(".json") else receipt_id
    receipts_dir = os.path.abspath(os.path.join(workspace_dir, ".agents", "receipts"))
    target = os.path.abspath(os.path.join(receipts_dir, f"{clean_id}.json"))

    # Canonical containment check: ensure target stays strictly within receipts_dir
    try:
        if os.path.commonpath([receipts_dir, target]) != receipts_dir:
            return None
    except ValueError:
        return None

    if not os.path.exists(target) or not os.path.isfile(target):
        return None
    try:
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)

        recorded_hash = data.get("receipt_hash") or (data.get("metadata", {}).get("receipt_hash") if isinstance(data.get("metadata"), dict) else None)
        if not recorded_hash:
            return None

        receipt = EvidenceReceipt.from_dict(data)
        # Validate integrity hash
        if receipt.compute_hash() != recorded_hash:
            return None
        return receipt
    except Exception:
        return None


def observe_command(
    command: str,
    workspace_dir: str,
    task_id: str = "task_default",
    claim_id: str = "claim_default",
    agent: str = "agent",
    action: str = "run_command",
    timeout: float = 60.0,
    allow_shell: bool = False,
    ledger: Optional[Any] = None,
    execution_kind: Optional[str] = None,
    verifier: Optional[str] = None,
) -> ObservedReceipt:
    """
    Independently executes and observes a command, recording its true exit code,
    runtime, stdout/stderr hashes, and comprehensive workspace state fingerprints.
    Uses strict tokenization to prevent uncontrolled shell injection.
    Shell execution is strictly governed by explicit policy authorization.
    """
    ws = os.path.abspath(workspace_dir)
    started_at = datetime.now(timezone.utc).isoformat()
    base_commit = _get_git_commit_hash(ws)

    # Phase 9 & Requirement 4: Snapshot workspace state before execution (TOCTOU protection)
    snapshot_before = compute_workspace_snapshot(ws)
    fingerprint_before = compute_workspace_fingerprint(snapshot_before)

    try:
        if allow_shell:
            # Policy authorization decision for shell execution
            from sclass.survival.authority import authorize
            from sclass.survival.models import AuthorizationRequest
            auth_req = AuthorizationRequest(
                agent=agent,
                platform="sclass",
                action="execute",
                target=command,
                parameters={"execution_mode": "shell", "command": command},
                workspace=ws,
                task_id=task_id,
            )
            decision = authorize(auth_req, mode="enforce", workspace_dir=ws)
            if not decision.is_allowed:
                raise ValueError(f"Shell execution rejected by S-Class security policy: {decision.reason}")

            proc = subprocess.run(
                command,
                cwd=ws,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        else:
            cmd_tokens = sanitize_verification_command(command)
            resolved_tokens = resolve_executable_tokens(cmd_tokens)
            proc = subprocess.run(
                resolved_tokens,
                cwd=ws,
                shell=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        exit_code = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except ValueError as ve:
        exit_code = 126
        stdout = ""
        stderr = f"Command execution rejected by S-Class security policy: {str(ve)}"
    except subprocess.TimeoutExpired as te:
        exit_code = 124
        stdout = te.stdout or "" if isinstance(te.stdout, str) else ""
        stderr = (te.stderr or "") + "\nCommand timed out after timeout limit"
    except FileNotFoundError as fnf:
        exit_code = 127
        stdout = ""
        stderr = f"Command executable not found: {str(fnf)}"
    except Exception as e:
        exit_code = 1
        stdout = ""
        stderr = f"Execution exception: {str(e)}"

    finished_at = datetime.now(timezone.utc).isoformat()
    result_commit = _get_git_commit_hash(ws)
    files_changed = _get_git_changed_files(ws, base_commit)
    file_hashes = compute_file_hashes(ws, files_changed)

    # Capture after snapshot and compute fingerprint
    snapshot_after = compute_workspace_snapshot(ws)
    fingerprint_after = compute_workspace_fingerprint(snapshot_after)

    receipt = _create_observed_receipt(
        task_id=task_id,
        claim_id=claim_id,
        agent=agent,
        action=action,
        workspace=ws,
        command=command,
        exit_code=exit_code,
        started_at=started_at,
        finished_at=finished_at,
        stdout_content=stdout,
        stderr_content=stderr,
        base_commit=base_commit,
        result_commit=result_commit,
        files_changed=files_changed,
        file_hashes=file_hashes,
        workspace_snapshot=snapshot_after,
        workspace_fingerprint=fingerprint_after,
        workspace_snapshot_before=snapshot_before,
        workspace_fingerprint_before=fingerprint_before,
        execution_kind=execution_kind,
        verifier=verifier,
        skip_ledger=True,
    )

    if ledger is None:
        try:
            from sclass.survival.ledger import LocalLedger
            ledger = LocalLedger(workspace_dir=ws)
        except Exception as l_err:
            raise ObservationIntegrityError(
                f"Observation completed but local ledger could not be initialized: {l_err}"
            ) from l_err

    try:
        ledger.append(
            "OBSERVATION",
            {
                "receipt_id": receipt.receipt_id,
                "receipt_hash": receipt.receipt_hash,
                "fingerprint_before": fingerprint_before,
                "fingerprint_after": fingerprint_after,
                "command": command,
                "exit_code": exit_code,
                "execution_kind": receipt.execution_kind,
                "verifier": receipt.verifier,
                "timestamp": finished_at,
            },
        )
    except Exception as append_err:
        raise ObservationIntegrityError(
            f"Observation completed but provenance could not be anchored in ledger: {append_err}"
        ) from append_err

    return receipt

