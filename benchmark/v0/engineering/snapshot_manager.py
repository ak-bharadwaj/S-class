#!/usr/bin/env python3
"""
S-Class EOS - Gate 1.6B Immutable Repository Snapshot Manager
(benchmark/v0/engineering/snapshot_manager.py)

Responsibilities:
- Materialize immutable task repository starting states into isolated temporary workdirs.
- Compute SHA-256 tree hashes for initial and final repository states.
- Extract python code blocks or unified diff patches from raw LLM responses and apply them to target files.
- Execute real `pytest` suites inside materialized workdirs and capture complete execution stdout/stderr.
"""

import os
import re
import sys
import shutil
import hashlib
import tempfile
import subprocess
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional, Tuple

@dataclass
class PytestRunResult:
    exit_code: int
    passed_count: int
    failed_count: int
    total_count: int
    stdout: str
    stderr: str
    duration_sec: float
    all_passed: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class RepositorySnapshotManager:
    @staticmethod
    def compute_tree_hash(directory_path: str) -> str:
        """Computes a deterministic SHA-256 tree hash of all files in a directory."""
        hasher = hashlib.sha256()
        if not os.path.exists(directory_path):
            return hasher.hexdigest()

        for root, dirs, files in os.walk(directory_path):
            # Sort to ensure deterministic hash traversal
            dirs.sort()
            files.sort()
            for filename in files:
                if filename.startswith(".") or filename.endswith(".pyc") or filename == "__pycache__":
                    continue
                filepath = os.path.join(root, filename)
                relpath = os.path.relpath(filepath, directory_path).replace("\\", "/")
                hasher.update(relpath.encode("utf-8"))
                try:
                    with open(filepath, "rb") as f:
                        hasher.update(f.read())
                except OSError:
                    pass
        return hasher.hexdigest()

    @staticmethod
    def materialize_task(task_dir: str, workdir: str) -> str:
        """Copies starter code & tests into workdir and returns the initial tree hash."""
        starter_dir = os.path.join(task_dir, "starter_code")
        if os.path.exists(starter_dir):
            for item in os.listdir(starter_dir):
                s = os.path.join(starter_dir, item)
                d = os.path.join(workdir, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)

        # Copy tests into workdir
        tests_src = os.path.join(task_dir, "tests")
        tests_dst = os.path.join(workdir, "tests")
        if os.path.exists(tests_src):
            shutil.copytree(tests_src, tests_dst, dirs_exist_ok=True)

        return RepositorySnapshotManager.compute_tree_hash(workdir)

    @staticmethod
    def extract_code_blocks(raw_text: str) -> List[Tuple[str, str]]:
        """
        Extracts python code blocks from markdown fences with optional target filename header.
        Format example:
        ```python filename="target_module.py"
        # code...
        ```
        Returns list of (filename, code_content). Default filename is target_module.py.
        """
        blocks = []
        pattern = r"```(?:python)?(?:\s+filename=[\"']?([^\s\"']+)[\"']?)?\n(.*?)```"
        matches = re.findall(pattern, raw_text, re.DOTALL | re.IGNORECASE)
        
        if matches:
            for fname, code in matches:
                target_fname = fname.strip() if fname and fname.strip() else "target_module.py"
                blocks.append((target_fname, code.strip()))
        else:
            # Fallback: if no markdown fences, treat entire response as code if it looks like python
            if "def " in raw_text or "class " in raw_text or "import " in raw_text:
                blocks.append(("target_module.py", raw_text.strip()))
        return blocks

    @staticmethod
    def apply_llm_response_to_workdir(workdir: str, raw_response_text: str) -> List[str]:
        """Applies code blocks extracted from LLM text output into workdir."""
        modified_files = []
        code_blocks = RepositorySnapshotManager.extract_code_blocks(raw_response_text)
        
        for filename, code in code_blocks:
            filepath = os.path.join(workdir, filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(code + "\n")
            modified_files.append(filename)
            
        return modified_files

    @staticmethod
    def run_pytest(workdir: str, test_rel_path: str = "tests/test_oracle.py") -> PytestRunResult:
        """Executes pytest in workdir and parses results."""
        test_full_path = os.path.join(workdir, test_rel_path)
        if not os.path.exists(test_full_path):
            tests_dir = os.path.join(workdir, "tests")
            if os.path.exists(tests_dir):
                t_files = [os.path.join(tests_dir, f) for f in os.listdir(tests_dir) if f.startswith("test_") and f.endswith(".py")]
                if t_files:
                    test_full_path = t_files[0]
                else:
                    return PytestRunResult(
                        exit_code=1,
                        passed_count=0,
                        failed_count=1,
                        total_count=1,
                        stdout="",
                        stderr=f"Test file not found: {test_rel_path}",
                        duration_sec=0.0,
                        all_passed=False
                    )
            else:
                return PytestRunResult(
                    exit_code=1,
                    passed_count=0,
                    failed_count=1,
                    total_count=1,
                    stdout="",
                    stderr=f"Test file not found: {test_rel_path}",
                    duration_sec=0.0,
                    all_passed=False
                )

        cmd = [sys.executable, "-m", "pytest", test_full_path, "-v", "--tb=short"]
        
        import time
        start_t = time.time()
        try:
            res = subprocess.run(
                cmd,
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=30
            )
            duration = round(time.time() - start_t, 3)
            stdout = res.stdout or ""
            stderr = res.stderr or ""
            exit_code = res.returncode
            
            # Parse passed / failed count from pytest output
            passed_match = re.search(r"(\d+)\s+passed", stdout)
            failed_match = re.search(r"(\d+)\s+failed", stdout)
            error_match = re.search(r"(\d+)\s+error", stdout)
            
            passed = int(passed_match.group(1)) if passed_match else 0
            failed = int(failed_match.group(1)) if failed_match else 0
            errors = int(error_match.group(1)) if error_match else 0
            total_failed = failed + errors
            total = passed + total_failed
            if total == 0:
                total = 1
                
            all_passed = (exit_code == 0 and total_failed == 0 and passed > 0)
            
            return PytestRunResult(
                exit_code=exit_code,
                passed_count=passed,
                failed_count=total_failed,
                total_count=total,
                stdout=stdout,
                stderr=stderr,
                duration_sec=duration,
                all_passed=all_passed
            )
        except subprocess.TimeoutExpired:
            return PytestRunResult(
                exit_code=-1,
                passed_count=0,
                failed_count=1,
                total_count=1,
                stdout="",
                stderr="Pytest execution timed out after 30 seconds.",
                duration_sec=30.0,
                all_passed=False
            )
