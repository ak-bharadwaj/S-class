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

    def _clean_exe(name: str) -> str:
        base = os.path.basename(name).lower()
        return base[:-4] if base.endswith(".exe") else base

    def _is_python(name: str) -> bool:
        base = _clean_exe(name)
        return (
            base in ("python", "python3", "py", "pypy", "pypy3")
            or base.startswith("python3.")
            or base.startswith("python2.")
            or base.startswith("pypy3.")
        )


    def _unwrap_python_tokens(p_tokens: List[str]) -> Tuple[Optional[str], Optional[str]]:
        """Given tokens starting with python (or sub-args), extracts (actual_child, verifier)."""
        if len(p_tokens) > 2 and p_tokens[1] == "-m":
            mod = _clean_exe(p_tokens[2])
            v = "pytest" if "pytest" in mod else (mod if mod in ("unittest",) else None)
            return mod, v
        elif len(p_tokens) > 1 and p_tokens[1].startswith("-m"):
            mod = _clean_exe(p_tokens[1][2:])
            v = "pytest" if "pytest" in mod else (mod if mod in ("unittest",) else None)
            return mod, v
        elif len(p_tokens) > 1:
            script = os.path.basename(p_tokens[1])
            return script, None
        return "python", None

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
                script_body = tokens_list[2].strip()
                actual_child = script_body
                body_parts = script_body.split()
                if body_parts:
                    b_exe = _clean_exe(body_parts[0])
                    if b_exe in ("pytest", "py.test"):
                        actual_child = "pytest"
                        verifier = "pytest"
                    elif _is_python(b_exe):
                        interpreter = b_exe
                        c_child, c_ver = _unwrap_python_tokens(body_parts)
                        actual_child = c_child or actual_child
                        verifier = c_ver

    # 2. Modern Python Package Runners & Tool Managers (uv, poetry, pipx)
    elif exe_base in ("uv", "poetry", "pipx"):
        launcher = exe_base
        interpreter = "python"
        # Skip 'run' or 'exec' and any option flags (like --isolated, -v, --extra dev, etc.)
        idx = 1
        flags_with_val = {"-e", "-p", "-m", "--extra", "--with", "--python", "--env-file", "--directory", "-C"}
        while idx < len(tokens_list):
            tok = tokens_list[idx]
            if tok in ("run", "exec", "--"):
                idx += 1
            elif tok in flags_with_val and idx + 1 < len(tokens_list):
                idx += 2
            elif tok.startswith("-"):
                idx += 1
            else:
                break

        sub_args = tokens_list[idx:]
        if sub_args:
            sub_exe = _clean_exe(sub_args[0])
            if _is_python(sub_exe):
                c_child, c_ver = _unwrap_python_tokens(sub_args)
                actual_child = c_child
                verifier = c_ver
            elif sub_exe in ("pytest", "py.test", "unittest"):
                actual_child = "pytest" if "pytest" in sub_exe else sub_exe
                verifier = actual_child
            else:
                actual_child = sub_exe

    # 3. Modern JS Package Runners (npx, bunx)
    elif exe_base in ("npx", "bunx"):
        launcher = exe_base
        interpreter = "node" if exe_base == "npx" else "bun"
        idx = 1
        flags_with_val = {"-p", "--package", "-c"}
        while idx < len(tokens_list):
            tok = tokens_list[idx]
            if tok in flags_with_val and idx + 1 < len(tokens_list):
                idx += 2
            elif tok.startswith("-"):
                idx += 1
            else:
                break
        sub_args = tokens_list[idx:]
        if sub_args:
            sub_exe = _clean_exe(sub_args[0])
            actual_child = sub_exe
            if sub_exe in ("jest", "vitest", "mocha", "playwright"):
                verifier = sub_exe

    # 4. Environment managers (mise, asdf)
    elif exe_base in ("mise", "asdf"):
        launcher = exe_base
        idx = 1
        while idx < len(tokens_list):
            tok = tokens_list[idx]
            if tok in ("exec", "run", "--"):
                idx += 1
            elif tok.startswith("-"):
                idx += 1
            else:
                break
        sub_args = tokens_list[idx:]
        if sub_args:
            sub_exe = _clean_exe(sub_args[0])
            if _is_python(sub_exe):
                interpreter = sub_exe
                c_child, c_ver = _unwrap_python_tokens(sub_args)
                actual_child = c_child
                verifier = c_ver
            elif sub_exe in ("pytest", "jest", "vitest", "cargo", "go"):
                actual_child = sub_exe
                verifier = sub_exe
            else:
                actual_child = sub_exe

    # 5. Containers (docker, podman)
    elif exe_base in ("docker", "podman"):
        launcher = exe_base
        idx = 1
        flags_with_val = {
            "-v", "--volume", "-p", "--publish", "-e", "--env", "--env-file",
            "-w", "--workdir", "-u", "--user", "--name", "--network", "--mount", "--entrypoint"
        }
        while idx < len(tokens_list):
            tok = tokens_list[idx]
            if tok in ("run", "exec"):
                idx += 1
            elif tok in flags_with_val and idx + 1 < len(tokens_list):
                idx += 2
            elif tok.startswith("-"):
                idx += 1
            else:
                break

        # idx is now the image token
        if idx < len(tokens_list):
            _image = tokens_list[idx]
            cmd_args = tokens_list[idx + 1:]
            if cmd_args:
                cmd_exe = _clean_exe(cmd_args[0])
                if _is_python(cmd_exe):
                    interpreter = "python"
                    c_child, c_ver = _unwrap_python_tokens(cmd_args)
                    actual_child = c_child
                    verifier = c_ver
                elif cmd_exe in ("pytest", "py.test", "jest", "vitest", "mocha"):
                    actual_child = "pytest" if "pytest" in cmd_exe else cmd_exe
                    verifier = actual_child
                else:
                    actual_child = cmd_exe
            else:
                actual_child = _image

    # 6. Python Chains (python -m pytest tests/)
    elif _is_python(exe_base):
        interpreter = exe_base
        launcher = launcher or tokens_list[0]
        c_child, c_ver = _unwrap_python_tokens(tokens_list)
        actual_child = c_child
        verifier = c_ver
        if len(tokens_list) > 1 and "wrapper" in tokens_list[1].lower():
            wrapper = tokens_list[1]

    # 7. Node / NPM Package Runner Chains (npm run test, pnpm test, yarn test, bun test)
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

    # 8. Node directly (node runner.js)
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

    # 9. Direct Test Runner Binaries
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
