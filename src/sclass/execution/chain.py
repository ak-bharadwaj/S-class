"""
S-Class Execution: Authoritative Execution Chain.
Discovers and models multi-tier execution chains across platforms:
- requested
- launcher
- wrapper
- interpreter
- actual child
- verifier

Supports chains like:
npm -> node -> jest
python -> pytest
shell -> wrapper -> pytest
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

from sclass.execution.process_tree import ProcessTree, ProcessTreeNode


@dataclass(frozen=True)
class ExecutionChain:
    """
    Authoritative representation of process execution layers.
    Distinguishes requested command, launcher, wrapper, interpreter, child, and verifier.
    """
    requested: tuple[str, ...] = field(default_factory=tuple)
    launcher: Optional[str] = None
    wrapper: Optional[str] = None
    interpreter: Optional[str] = None
    actual_child: Optional[str] = None
    child: Optional[str] = None  # Backwards compatibility alias for actual_child
    verifier: Optional[str] = None
    tree_nodes: tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    is_authoritative: bool = True

    def __post_init__(self):
        if self.child is None and self.actual_child is not None:
            object.__setattr__(self, "child", self.actual_child)
        elif self.actual_child is None and self.child is not None:
            object.__setattr__(self, "actual_child", self.child)

    def describe_chain(self) -> str:
        """Returns human and auditor explanation of which executable actually produced this receipt."""
        parts = []
        if self.launcher:
            parts.append(f"launcher:{self.launcher}")
        if self.wrapper:
            parts.append(f"wrapper:{self.wrapper}")
        if self.interpreter:
            parts.append(f"interpreter:{self.interpreter}")
        if self.actual_child:
            parts.append(f"child:{self.actual_child}")
        if self.verifier:
            parts.append(f"verifier:{self.verifier}")
        return " -> ".join(parts) if parts else "unclassified_process"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requested": list(self.requested),
            "launcher": self.launcher,
            "wrapper": self.wrapper,
            "interpreter": self.interpreter,
            "actual_child": self.actual_child,
            "child": self.child,
            "verifier": self.verifier,
            "tree_nodes": list(self.tree_nodes),
            "is_authoritative": self.is_authoritative,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExecutionChain:
        req = tuple(data.get("requested", []))
        tree = tuple(data.get("tree_nodes", []))
        return cls(
            requested=req,
            launcher=data.get("launcher"),
            wrapper=data.get("wrapper"),
            interpreter=data.get("interpreter"),
            actual_child=data.get("actual_child") or data.get("child"),
            child=data.get("child") or data.get("actual_child"),
            verifier=data.get("verifier"),
            tree_nodes=tree,
            is_authoritative=data.get("is_authoritative", True),
        )


def analyze_execution_chain(
    argv: tuple[str, ...] | List[str],
    resolved_path: str = "",
    process_tree: Optional[ProcessTree] = None,
    requested_argv: Optional[tuple[str, ...] | List[str]] = None,
    launcher_identity: Optional[str] = None,
    wrapper_identity: Optional[str] = None,
) -> ExecutionChain:
    """
    Authoritatively analyzes and classifies multi-tier execution chains.
    Distinguishes requested, launcher, wrapper, interpreter, actual child, and verifier.
    """
    actual_tokens = tuple(argv)
    req_tokens = tuple(requested_argv) if requested_argv is not None else actual_tokens

    if not actual_tokens:
        return ExecutionChain(requested=req_tokens)

    raw_exe = resolved_path or actual_tokens[0]
    exe_base = os.path.basename(raw_exe).lower()
    if exe_base.endswith(".exe"):
        exe_base = exe_base[:-4]

    launcher: Optional[str] = launcher_identity
    wrapper: Optional[str] = wrapper_identity
    interpreter: Optional[str] = None
    actual_child: Optional[str] = None
    verifier: Optional[str] = None

    tokens_list = list(actual_tokens)

    # 1. Shell / Wrapper detection (e.g. bash run_tests.sh, sh wrapper.sh, cmd /c)
    if exe_base in ("sh", "bash", "zsh", "cmd", "powershell", "pwsh"):
        launcher = exe_base
        if len(tokens_list) > 1:
            sub = tokens_list[1]
            if sub.endswith((".sh", ".bash", ".bat", ".cmd", ".ps1")):
                wrapper = sub
                actual_child = sub
            elif sub in ("-c", "/c") and len(tokens_list) > 2:
                wrapper = "inline_script"
                actual_child = tokens_list[2]

    # 2. Modern Python / JS Package Runners & Tool Managers (uv, poetry, pipx, npx, bunx, mise, asdf, docker, podman)
    elif exe_base in ("uv", "poetry", "pipx"):
        launcher = exe_base
        interpreter = "python"
        sub_args = tokens_list[2:] if len(tokens_list) > 1 and tokens_list[1] in ("run", "exec") else tokens_list[1:]
        if sub_args:
            sub_exe = os.path.basename(sub_args[0]).lower()
            if sub_exe.endswith(".exe"):
                sub_exe = sub_exe[:-4]
            actual_child = sub_exe
            if sub_exe in ("pytest", "py.test", "unittest"):
                verifier = "pytest" if "pytest" in sub_exe else sub_exe

    elif exe_base in ("npx", "bunx"):
        launcher = exe_base
        interpreter = "node" if exe_base == "npx" else "bun"
        sub_args = tokens_list[1:]
        if sub_args:
            sub_exe = os.path.basename(sub_args[0]).lower()
            if sub_exe.endswith(".exe"):
                sub_exe = sub_exe[:-4]
            actual_child = sub_exe
            if sub_exe in ("jest", "vitest", "mocha", "playwright"):
                verifier = sub_exe

    elif exe_base in ("mise", "asdf"):
        launcher = exe_base
        sub_args = [t for t in tokens_list[1:] if t not in ("exec", "run", "--")]
        if sub_args:
            sub_exe = os.path.basename(sub_args[0]).lower()
            if sub_exe.endswith(".exe"):
                sub_exe = sub_exe[:-4]
            actual_child = sub_exe
            if sub_exe in ("pytest", "jest", "vitest", "cargo", "go"):
                verifier = sub_exe

    elif exe_base in ("docker", "podman"):
        launcher = exe_base
        sub_args = [t for t in tokens_list[1:] if not t.startswith("-") and t not in ("run", "exec")]
        if sub_args:
            sub_exe = os.path.basename(sub_args[-1]).lower() if len(sub_args) > 1 else sub_args[0]
            if sub_exe.endswith(".exe"):
                sub_exe = sub_exe[:-4]
            actual_child = sub_exe
            if sub_exe in ("pytest", "jest", "vitest"):
                verifier = sub_exe

    # 3. Python Chains (python -m pytest tests/)
    elif exe_base in ("python", "python3", "py"):
        interpreter = exe_base
        launcher = launcher or tokens_list[0]
        if len(tokens_list) > 2 and tokens_list[1] == "-m":
            mod = tokens_list[2].lower()
            actual_child = mod
            if mod in ("pytest", "unittest"):
                verifier = mod
        elif len(tokens_list) > 1 and tokens_list[1].startswith("-m"):
            mod = tokens_list[1][2:].lower()
            actual_child = mod
            if mod in ("pytest", "unittest"):
                verifier = mod
        elif len(tokens_list) > 1:
            script = tokens_list[1]
            actual_child = os.path.basename(script)
            if "wrapper" in script.lower():
                wrapper = script

    # 3. Node / NPM Package Runner Chains (npm run test, pnpm test, yarn test, bun test)
    elif exe_base in ("npm", "pnpm", "yarn", "bun"):
        launcher = tokens_list[0]
        interpreter = exe_base
        if len(tokens_list) > 1:
            sub = tokens_list[1].lower()
            actual_child = sub
            if sub in ("test", "run"):
                verifier = exe_base
        else:
            actual_child = "script"


    # 4. Node directly (node runner.js)
    elif exe_base in ("node", "deno"):
        interpreter = exe_base
        launcher = launcher or tokens_list[0]
        if len(tokens_list) > 1:
            target = tokens_list[1]
            actual_child = os.path.basename(target)
            if "jest" in target.lower():
                verifier = "jest"
            elif "mocha" in target.lower():
                verifier = "mocha"

    # 5. Direct Test Runner Binaries
    elif exe_base in ("pytest", "py.test"):
        launcher = launcher or tokens_list[0]
        actual_child = "pytest"
        verifier = "pytest"
    elif exe_base in ("jest", "vitest", "mocha"):
        launcher = launcher or tokens_list[0]
        actual_child = exe_base
        verifier = exe_base
    elif exe_base == "playwright":
        launcher = launcher or tokens_list[0]
        actual_child = tokens_list[1] if len(tokens_list) > 1 else "playwright"
        if actual_child.lower() == "test":
            verifier = "playwright"
    elif exe_base in ("cargo", "go"):
        launcher = launcher or tokens_list[0]
        actual_child = tokens_list[1] if len(tokens_list) > 1 else exe_base
        if actual_child.lower() == "test":
            verifier = f"{exe_base}-test"
    else:
        launcher = launcher or tokens_list[0]
        actual_child = exe_base

    tree_nodes_dicts = ()
    if process_tree:
        tree_nodes_dicts = tuple(n.to_dict() for n in process_tree.flatten())

    return ExecutionChain(
        requested=req_tokens,
        launcher=launcher,
        wrapper=wrapper,
        interpreter=interpreter,
        actual_child=actual_child,
        verifier=verifier,
        tree_nodes=tree_nodes_dicts,
        is_authoritative=True,
    )
