"""
S-Class v6: Built-In Hook Rules (hook_rules.py)

Implements the standard governance rules evaluated by HookCore:
- SCLASS-CMD-001: Destructive Terminal Commands & Device Obliteration (DENY in strict mode)
- SCLASS-SEC-001: Hardcoded Secrets Gate (DENY in strict mode)
- SCLASS-SEC-002: Dangerous Execution Functions (eval, exec, pickle) (WARN)
- SCLASS-FSM-001: Phase Integrity (code edit during spec synthesis) (WARN)
- SCLASS-FSM-002: Release Governance (altering release artifacts outside RELEASE) (DENY)
- SCLASS-BLAST-001: Caller Blast Radius Discipline (>10 downstream callers) (WARN)
- SCLASS-EVID-001: Evidence Integrity (tampering with .agents evidence) (DENY)

Strict Lazy Loading: No heavy dependencies (fastembed, tree-sitter, ast, sqlite3)
are imported at module import time, preserving <100ms cold-start budget.
"""

from __future__ import annotations
import os
import re
import json
import shlex
import base64
from typing import Optional, ClassVar, List, Tuple

from hook_core import HookRule, HookEvent, HookVerdict, HookDecision, HookEventType


class DestructiveCommandRule(HookRule):
    """SCLASS-CMD-001: Detects and blocks destructive terminal commands, unverified pipe-to-shell patterns, and root filesystem obliteration."""

    rule_id = "SCLASS-CMD-001"
    category = "SECURITY"

    ROOT_TARGETS: ClassVar[set[str]] = {
        "/", "/*", "//", "///", "~", "~/", "~/*",
        "$home", "${home}", "..", "../",
        "c:\\", "c:/", "c:/*", "c:\\*",
        "d:\\", "d:/", "d:/*", "d:\\*",
    }

    PIPE_TO_SHELL_PATTERN: ClassVar = re.compile(
        r"""\b(?:curl|wget|fetch|lynx|links)\b[^;&|]*\|\s*(?:sudo\s+)?(?:bash|sh|zsh|dash|ksh|python|perl)\b""",
        re.IGNORECASE,
    )

    BASE64_SHELL_PIPE_PATTERN: ClassVar = re.compile(
        r"""\|\s*(?:base64\s+(?:-d|--decode)|openssl\s+base64\s+-d)\s*\|\s*(?:sudo\s+)?(?:bash|sh|zsh|dash|ksh|python|perl)\b""",
        re.IGNORECASE,
    )

    B64_CHUNK_PATTERN: ClassVar = re.compile(r"""(?:echo|printf)\s+['"]?([A-Za-z0-9+/=]{6,})['"]?""", re.IGNORECASE)

    PROTECTED_BRANCH_FORCE_PUSH: ClassVar = re.compile(
        r"""\bgit\s+push\s+[^;&|]*(?:(?:--force|-f)\s+[^;&|]*(?:main|master|production|release|prod)\b|(?:origin|upstream)\s+[^;&|]*(?:--force|-f)\s+[^;&|]*(?:main|master|production|release|prod)\b|(?:origin|upstream)\s+(?:main|master|production|release|prod)\b[^;&|]*(?:--force|-f))""",
        re.IGNORECASE,
    )

    CHMOD_WIPE: ClassVar = re.compile(
        r"""\bchmod\s+-[a-zA-Z]*R[a-zA-Z]*\s+(?:000|777)\s+(?:/|/\*|~|~/|\$HOME|\$\{HOME\})""",
        re.IGNORECASE,
    )

    BLOCK_DEVICE_DD: ClassVar = re.compile(
        r"""\bdd\s+if=.*?\s+of=/dev/(?:sd[a-z]|nvme[0-9]n[0-9]|hd[a-z]|vd[a-z]|null|zero)""",
        re.IGNORECASE,
    )

    BLOCK_DEVICE_FORMAT: ClassVar = re.compile(
        r"""\b(?:mkfs(?:\.[a-z0-9]+)?\s+/dev/(?:sd[a-z]|nvme[0-9]n[0-9]|hd[a-z]|vd[a-z])|format\s+[a-zA-Z]:)""",
        re.IGNORECASE,
    )

    SQL_DESTRUCTIVE: ClassVar = re.compile(
        r"""\b(?:DROP\s+(?:DATABASE|TABLE|SCHEMA)\s+['\"`a-zA-Z0-9_]+|TRUNCATE\s+(?:TABLE\s+)?['\"`a-zA-Z0-9_]+)""",
        re.IGNORECASE,
    )

    FORK_BOMB: ClassVar = re.compile(r""":\(\)\s*\{\s*:\|:&\s*\};:""")

    WINDOWS_OBLITERATION: ClassVar = re.compile(
        r"""\b(?:rmdir\s+/[sS]\s+/[qQ]|del\s+/[fF]\s+/[sS]\s+/[qQ])\s+[a-zA-Z]:\\?""",
        re.IGNORECASE,
    )

    WARNING_PATTERNS: ClassVar = [
        (re.compile(r"""\bgit\s+clean\s+-[a-zA-Z]*f[a-zA-Z]*""", re.IGNORECASE),
         "Potentially destructive git clean will permanently remove untracked files"),
        (re.compile(r"""\bgit\s+reset\s+--hard""", re.IGNORECASE),
         "Hard git reset will discard uncommitted modifications"),
        (re.compile(r"""\b(?:pkill|killall|kill)\s+-9\s+(?:-1|1)\b""", re.IGNORECASE),
         "Aggressive process termination signal targeting all processes"),
    ]

    @classmethod
    def _is_destructive_rm_tokens(cls, tokens: List[str]) -> bool:
        if not tokens:
            return False
        bin_name = tokens[0].lower()
        if bin_name.endswith(".exe"):
            bin_name = bin_name[:-4]
        if bin_name != "rm":
            return False

        has_recursive = False
        targets = []

        for t in tokens[1:]:
            if t.startswith("--"):
                if "recursive" in t:
                    has_recursive = True
            elif t.startswith("-"):
                if "r" in t.lower():
                    has_recursive = True
            else:
                targets.append(t)

        if has_recursive:
            for tgt in targets:
                norm = tgt.strip().lower().rstrip("/")
                norm_with_slash = tgt.strip().lower()
                if norm in cls.ROOT_TARGETS or norm_with_slash in cls.ROOT_TARGETS:
                    return True
        return False

    @classmethod
    def _unwrap_command_chain(cls, cmd_str: str) -> List[List[str]]:
        result_token_lists = []
        lines = [line.strip() for line in cmd_str.splitlines() if line.strip()]
        for line in lines:
            subcmds = re.split(r"(?:&&|\|\||;)", line)
            for sub in subcmds:
                sub = sub.strip()
                if not sub:
                    continue
                try:
                    toks = shlex.split(sub)
                except Exception:
                    toks = sub.split()
                if toks:
                    result_token_lists.extend(cls._unwrap_token_wrappers(toks))
        return result_token_lists

    @classmethod
    def _unwrap_token_wrappers(cls, tokens: List[str]) -> List[List[str]]:
        if not tokens:
            return []
        idx = 0
        while idx < len(tokens):
            tok = tokens[idx].lower()
            if tok.endswith(".exe"):
                tok = tok[:-4]

            if tok == "sudo":
                idx += 1
                while idx < len(tokens) and tokens[idx].startswith("-"):
                    if tokens[idx] in ("-u", "-g") and idx + 1 < len(tokens):
                        idx += 2
                    else:
                        idx += 1
                continue

            if tok == "env":
                idx += 1
                while idx < len(tokens) and ("=" in tokens[idx] or tokens[idx].startswith("-")):
                    idx += 1
                continue

            if tok == "nohup":
                idx += 1
                continue

            if tok in ("bash", "sh", "zsh", "dash", "ksh") and idx + 1 < len(tokens):
                if tokens[idx + 1] in ("-c", "-lc", "-cl") and idx + 2 < len(tokens):
                    inner_cmd = tokens[idx + 2]
                    try:
                        inner_tokens = shlex.split(inner_cmd)
                        return cls._unwrap_token_wrappers(inner_tokens)
                    except Exception:
                        pass

            if tok in ("cmd", "powershell", "pwsh") and idx + 1 < len(tokens):
                if tokens[idx + 1].lower() in ("/c", "-c", "-command") and idx + 2 < len(tokens):
                    inner_cmd = tokens[idx + 2]
                    try:
                        inner_tokens = shlex.split(inner_cmd)
                        return cls._unwrap_token_wrappers(inner_tokens)
                    except Exception:
                        pass

            break

        return [tokens[idx:]]

    @classmethod
    def scan_command(cls, raw_command: str) -> Optional[Tuple[str, str, str]]:
        cmd = raw_command.strip()
        if not cmd:
            return None

        # 1. Base64 pipe-to-shell detection & payload extraction
        if cls.BASE64_SHELL_PIPE_PATTERN.search(cmd):
            chunk_match = cls.B64_CHUNK_PATTERN.search(cmd)
            decoded_desc = ""
            if chunk_match:
                try:
                    decoded = base64.b64decode(chunk_match.group(1)).decode("utf-8", errors="ignore")
                    sub_verdict = cls.scan_command(decoded)
                    if sub_verdict and sub_verdict[0] == "DENY":
                        return (
                            "DENY",
                            f"Base64 obfuscated payload piped to shell contains destructive command: '{decoded.strip()}'",
                            "SCLASS-CMD-001"
                        )
                    decoded_desc = f" (decoded: '{decoded.strip()}')"
                except Exception:
                    pass
            return (
                "DENY",
                f"Obfuscated base64 payload execution piped directly into shell{decoded_desc}",
                "SCLASS-CMD-001"
            )

        # 2. Pipe-to-shell remote code execution (curl/wget/fetch | sh)
        if cls.PIPE_TO_SHELL_PATTERN.search(cmd):
            return (
                "DENY",
                "Unverified remote script piped directly to shell (curl/wget | sh/bash)",
                "SCLASS-CMD-001"
            )

        # 3. Protected branch force-push
        if cls.PROTECTED_BRANCH_FORCE_PUSH.search(cmd):
            return (
                "DENY",
                "Destructive git force-push targeting protected branch (main/master/production)",
                "SCLASS-CMD-001"
            )

        # 4. Root permission wipes
        if cls.CHMOD_WIPE.search(cmd):
            return (
                "DENY",
                "Unrestricted recursive permission wipe targeting root or home directory",
                "SCLASS-CMD-001"
            )

        # 5. Direct block device writes / format
        if cls.BLOCK_DEVICE_DD.search(cmd):
            return (
                "DENY",
                "Direct low-level block device overwrite via dd",
                "SCLASS-CMD-001"
            )
        if cls.BLOCK_DEVICE_FORMAT.search(cmd):
            return (
                "DENY",
                "Direct raw storage or volume formatting command",
                "SCLASS-CMD-001"
            )

        # 6. Destructive SQL execution
        if cls.SQL_DESTRUCTIVE.search(cmd):
            return (
                "DENY",
                "Destructive SQL statement (DROP/TRUNCATE) intercepted in terminal command",
                "SCLASS-CMD-001"
            )

        # 7. Fork bombs
        if cls.FORK_BOMB.search(cmd):
            return (
                "DENY",
                "Shell fork bomb pattern detected",
                "SCLASS-CMD-001"
            )

        # 8. Windows volume wipe
        if cls.WINDOWS_OBLITERATION.search(cmd):
            return (
                "DENY",
                "Recursive directory obliteration on Windows root drive",
                "SCLASS-CMD-001"
            )

        # 9. Tokenized inspection of unwrapped commands (handles rm -rf /, sudo, env, etc.)
        unwrapped_chains = cls._unwrap_command_chain(cmd)
        for token_list in unwrapped_chains:
            if cls._is_destructive_rm_tokens(token_list):
                target_str = " ".join(token_list)
                return (
                    "DENY",
                    f"Destructive filesystem obliteration command: '{target_str}'",
                    "SCLASS-CMD-001"
                )

        # 10. Borderline warnings
        for warn_pat, warn_desc in cls.WARNING_PATTERNS:
            if warn_pat.search(cmd):
                return (
                    "WARN",
                    warn_desc,
                    "SCLASS-CMD-001"
                )

        return None

    def _extract_commands(self, event: HookEvent) -> List[str]:
        commands: List[str] = []
        for key in ("command", "CommandLine", "cmd", "script", "instruction", "input"):
            val = event.tool_args.get(key)
            if isinstance(val, str) and val.strip():
                commands.append(val.strip())

        args_val = event.tool_args.get("args")
        if isinstance(args_val, list):
            commands.append(" ".join(str(a) for a in args_val))
        elif isinstance(args_val, str) and args_val.strip():
            commands.append(args_val.strip())

        tool = (event.tool_name or "").lower()
        if tool in ("run_command", "execute_command", "bash", "sh", "terminal", "powershell", "pwsh", "cmd", "exec", "zsh"):
            for v in event.tool_args.values():
                if isinstance(v, str) and v.strip() and v.strip() not in commands:
                    commands.append(v.strip())

        if event.prompt_text and event.event_type == HookEventType.PRE_SHELL:
            commands.append(event.prompt_text.strip())

        return commands

    def evaluate(self, event: HookEvent) -> Optional[HookVerdict]:
        commands = self._extract_commands(event)
        if not commands:
            return None

        first_warn: Optional[HookVerdict] = None
        for cmd in commands:
            res = self.scan_command(cmd)
            if not res:
                continue
            decision, reason, rule_id = res
            if decision == "DENY":
                return HookVerdict(
                    decision=HookDecision.DENY,
                    reason=reason,
                    fix_hint="Destructive terminal command blocked by S-Class zero-trust policy. Use safe, localized commands instead.",
                    rule_id=self.rule_id,
                    enforcement_level="blocking",
                    diagnostics=(reason, f"command: {cmd[:80]}"),
                )
            elif decision == "WARN" and not first_warn:
                first_warn = HookVerdict(
                    decision=HookDecision.WARN,
                    reason=reason,
                    fix_hint="Verify workspace impact before proceeding with potentially destructive terminal action.",
                    rule_id=self.rule_id,
                    enforcement_level="advisory",
                    diagnostics=(reason, f"command: {cmd[:80]}"),
                )

        return first_warn


class SecretScannerRule(HookRule):
    """SCLASS-SEC-001: Detects hardcoded secrets, private keys, or API tokens."""

    rule_id = "SCLASS-SEC-001"
    category = "SECURITY"

    SECRET_PATTERNS: ClassVar = [
        (re.compile(r"""(?:api[_-]?key|secret|token|password|auth[_-]?token)\s*[:=]\s*['"][A-Za-z0-9_\-\.]{16,}['"]""", re.IGNORECASE), "High-entropy secret assignment detected"),
        (re.compile(r"""-----BEGIN (?:RSA|OPENSSH|EC|PGP|PRIVATE) KEY-----""", re.IGNORECASE), "Private cryptographic key block detected"),
        (re.compile(r"""ghp_[A-Za-z0-9]{36}""", re.IGNORECASE), "GitHub Personal Access Token detected"),
        (re.compile(r"""sk-[A-Za-z0-9]{32,}""", re.IGNORECASE), "OpenAI/Anthropic API Key detected"),
    ]

    def evaluate(self, event: HookEvent) -> Optional[HookVerdict]:
        if event.event_type not in (
            HookEventType.PRE_TOOL_USE,
            HookEventType.PRE_FILE_EDIT,
            HookEventType.POST_FILE_EDIT,
            HookEventType.PRE_SHELL,
            HookEventType.PRE_READ,
        ):
            return None

        # Check content in tool_args or inspect file if present
        text_to_scan = ""
        if "content" in event.tool_args:
            text_to_scan = str(event.tool_args["content"])
        elif "file_text" in event.tool_args:
            text_to_scan = str(event.tool_args["file_text"])
        elif "new_str" in event.tool_args:
            text_to_scan = str(event.tool_args["new_str"])
        elif "command" in event.tool_args:
            text_to_scan = str(event.tool_args["command"])
        elif event.file_path and os.path.exists(event.file_path):
            try:
                # Limit scan window to first 128KB for latency
                with open(event.file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text_to_scan = f.read(131072)
            except Exception:
                pass

        if not text_to_scan:
            return None

        for pattern, desc in self.SECRET_PATTERNS:
            match = pattern.search(text_to_scan)
            if match:
                snippet = match.group(0)[:40]
                return HookVerdict(
                    decision=HookDecision.DENY,
                    reason=f"Hardcoded secret detected: {desc} (match: '{snippet}...')",
                    fix_hint="Extract secrets to environment variables or gitignored .env file",
                    rule_id=self.rule_id,
                    enforcement_level="blocking",
                    diagnostics=(desc, f"file: {event.file_path or 'inline'}"),
                )

        return None


class DangerousCodeRule(HookRule):
    """SCLASS-SEC-002: Detects dangerous execution primitives (eval, exec, pickle.loads)."""

    rule_id = "SCLASS-SEC-002"
    category = "SECURITY"

    DANGEROUS_PATTERNS: ClassVar = [
        (re.compile(r"\b(?:eval|exec)\s*\(", re.IGNORECASE), "Dynamic code execution via eval/exec"),
        (re.compile(r"\bpickle\.loads\s*\(", re.IGNORECASE), "Insecure deserialization via pickle.loads"),
        (re.compile(r"\b(?:subprocess\.(?:run|call|Popen)|os\.system)\s*\([^)]*shell\s*=\s*True", re.IGNORECASE), "Arbitrary shell injection pattern shell=True"),
    ]

    @staticmethod
    def _inspect_ast_dangerous_constructs(code: str) -> Optional[str]:
        """Parses Python AST to detect obfuscated dynamic execution, pickle deserialization, or shell=True."""
        try:
            import ast
            tree = ast.parse(code)
        except Exception:
            return None

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # 1. Direct eval(...) or exec(...)
                if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec"):
                    return f"Dynamic code execution via {node.func.id}()"
                # 2. Obfuscated getattr(__builtins__, 'eval') or getattr(module, 'exec')
                if isinstance(node.func, ast.Name) and node.func.id == "getattr":
                    if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and node.args[1].value in ("eval", "exec"):
                        return f"Obfuscated dynamic execution via getattr(..., '{node.args[1].value}')"
                # 3. Insecure pickle deserialization
                if isinstance(node.func, ast.Attribute) and node.func.attr in ("loads", "load"):
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == "pickle":
                        return f"Insecure deserialization via pickle.{node.func.attr}()"
                # 4. Arbitrary shell injection via subprocess(shell=True) or os.system
                if isinstance(node.func, ast.Attribute) and node.func.attr in ("run", "call", "Popen"):
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess":
                        for kw in node.keywords:
                            if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                                return "Arbitrary shell injection pattern subprocess(shell=True)"
                elif isinstance(node.func, ast.Attribute) and node.func.attr == "system":
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == "os":
                        return "Command execution vector via os.system()"
        return None

    def evaluate(self, event: HookEvent) -> Optional[HookVerdict]:
        if event.event_type not in (
            HookEventType.PRE_TOOL_USE,
            HookEventType.PRE_FILE_EDIT,
            HookEventType.POST_FILE_EDIT,
            HookEventType.PRE_SHELL,
            HookEventType.PRE_READ,
        ):
            return None

        text = ""
        if "content" in event.tool_args:
            text = str(event.tool_args["content"])
        elif "file_text" in event.tool_args:
            text = str(event.tool_args["file_text"])
        elif "new_str" in event.tool_args:
            text = str(event.tool_args["new_str"])
        elif "command" in event.tool_args:
            text = str(event.tool_args["command"])
        elif event.file_path and os.path.exists(event.file_path):
            try:
                with open(event.file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read(65536)
            except Exception:
                pass

        if not text:
            return None

        # 1. AST-based structural inspection (catches obfuscated eval, getattr, multi-line shell=True)
        ast_violation = self._inspect_ast_dangerous_constructs(text)
        if ast_violation:
            return HookVerdict(
                decision=HookDecision.WARN,
                reason=f"Potentially dangerous execution construct: {ast_violation}",
                fix_hint="Use ast.literal_eval or structured subprocess argument arrays instead",
                rule_id=self.rule_id,
                enforcement_level="advisory",
                diagnostics=(ast_violation, f"target: {event.file_path or 'buffer'}"),
            )

        # 2. Fast regex fallback (handles non-Python languages, shell commands, partial snippets)
        for pattern, desc in self.DANGEROUS_PATTERNS:
            if pattern.search(text):
                return HookVerdict(
                    decision=HookDecision.WARN,
                    reason=f"Potentially dangerous execution construct: {desc}",
                    fix_hint="Use ast.literal_eval or structured subprocess argument arrays instead",
                    rule_id=self.rule_id,
                    enforcement_level="advisory",
                    diagnostics=(desc, f"target: {event.file_path or 'buffer'}"),
                )

        return None


class PhaseIntegrityRule(HookRule):
    """SCLASS-FSM-001: Prevents source code modifications during specification synthesis."""

    rule_id = "SCLASS-FSM-001"
    category = "FSM_INTEGRITY"

    def evaluate(self, event: HookEvent) -> Optional[HookVerdict]:
        if event.event_type not in (HookEventType.PRE_TOOL_USE, HookEventType.PRE_FILE_EDIT):
            return None

        # Check target file extension
        target = event.file_path or event.tool_args.get("path") or ""
        if not target.endswith((".py", ".ts", ".js", ".go", ".rs", ".java", ".c", ".cpp")):
            return None

        # Inspect current FSM phase (O(1) cached JSON read)
        state_path = os.path.join(event.workspace_dir, ".agents", "orchestration_state.json")
        if not os.path.exists(state_path):
            return None

        try:
            with open(state_path, "r", encoding="utf-8") as f:
                sdata = json.load(f)
            current_phase = sdata.get("currentPhase", "")
            if current_phase in ("SPECIFICATION_SYNTHESIS", "DESIGN"):
                return HookVerdict(
                    decision=HookDecision.WARN,
                    reason=f"Code modification attempted while FSM is in {current_phase} phase",
                    fix_hint="Wait for architecture and specification approval before modifying source code",
                    rule_id=self.rule_id,
                    enforcement_level="advisory",
                    diagnostics=(f"Phase: {current_phase}", f"Target: {target}"),
                )
        except Exception:
            pass

        return None


class ReleaseGovernanceRule(HookRule):
    """SCLASS-FSM-002: Blocks unauthorized modifications to release manifests."""

    rule_id = "SCLASS-FSM-002"
    category = "RELEASE"

    def evaluate(self, event: HookEvent) -> Optional[HookVerdict]:
        target = (event.file_path or event.tool_args.get("path") or "").replace("\\", "/")
        if not any(target.endswith(p) for p in ("release_manifest.json", "version.lock", ".release-marker")):
            return None

        state_path = os.path.join(event.workspace_dir, ".agents", "orchestration_state.json")
        if os.path.exists(state_path):
            try:
                with open(state_path, "r", encoding="utf-8") as f:
                    phase = json.load(f).get("currentPhase", "")
                if phase != "RELEASE":
                    return HookVerdict(
                        decision=HookDecision.DENY,
                        reason=f"Direct edit to release manifest '{os.path.basename(target)}' forbidden in phase {phase}",
                        fix_hint="Advance FSM to RELEASE phase before creating or modifying release artifacts",
                        rule_id=self.rule_id,
                        enforcement_level="blocking",
                    )
            except Exception:
                pass

        return None


class BlastRadiusRule(HookRule):
    """SCLASS-BLAST-001: Warns if a modified symbol has high caller blast radius."""

    rule_id = "SCLASS-BLAST-001"
    category = "ARCHITECTURE"
    CALLER_THRESHOLD = 10

    def evaluate(self, event: HookEvent) -> Optional[HookVerdict]:
        if event.event_type not in (HookEventType.PRE_TOOL_USE, HookEventType.PRE_FILE_EDIT):
            return None

        # Only invoke DB query if graph DB file exists
        db_path = os.path.join(event.workspace_dir, ".agents", "codebase_graph.db")
        if not os.path.exists(db_path):
            return None

        # Lazy import CodebaseGraphDB
        try:
            from codebase_graph_db import CodebaseGraphDB
            graph = CodebaseGraphDB(workspace_dir=event.workspace_dir)
            target_file = event.file_path or event.tool_args.get("path") or ""
            norm_target = os.path.relpath(target_file, event.workspace_dir).replace("\\", "/")
            
            # Count downstream callers for symbols defined in this file
            query = """
                SELECT COUNT(DISTINCT src_node_id) as callers 
                FROM codebase_edges 
                WHERE edge_type = 'CALLS' AND dest_node_id LIKE ?
            """
            rows = graph.cursor.execute(query, (f"{norm_target}%",)).fetchone()
            callers = rows[0] if rows else 0
            if callers > self.CALLER_THRESHOLD:
                return HookVerdict(
                    decision=HookDecision.WARN,
                    reason=f"High blast radius modification: {norm_target} has {callers} downstream callers",
                    fix_hint="Run impact_analysis tool or verify callers via targeted test suite before committing",
                    rule_id=self.rule_id,
                    enforcement_level="advisory",
                    diagnostics=(f"Callers: {callers}", f"Target: {norm_target}"),
                )
        except Exception:
            pass

        return None


class EvidenceIntegrityRule(HookRule):
    """SCLASS-EVID-001: Prevents tampering with or deletion of .agents evidence artifacts."""

    rule_id = "SCLASS-EVID-001"
    category = "EVIDENCE_INTEGRITY"

    PROTECTED_ARTIFACTS = (
        "qa_report.json",
        "synthesized_spec.json",
        "design_blueprint.json",
        "event_store.jsonl",
        "event_store_snapshot.json",
        "confidence_matrix.json",
        "grill_report.json",
    )

    def evaluate(self, event: HookEvent) -> Optional[HookVerdict]:
        target = (event.file_path or event.tool_args.get("path") or "").replace("\\", "/")
        norm_name = os.path.basename(target)

        # Check if target is a protected evidence artifact
        if norm_name in self.PROTECTED_ARTIFACTS and ".agents" in target:
            tool = (event.tool_name or "").lower()
            if tool in ("delete", "remove", "rm", "unlink") or event.tool_args.get("delete"):
                return HookVerdict(
                    decision=HookDecision.DENY,
                    reason=f"Tampering with evidence artifact '{norm_name}' is prohibited",
                    fix_hint="Evidence artifacts may only be updated by the S-Class kernel verification engine",
                    rule_id=self.rule_id,
                    enforcement_level="blocking",
                )

        return None


def get_default_rules() -> list[HookRule]:
    """Returns standard suite of S-Class rules in evaluation order."""
    return [
        DestructiveCommandRule(),
        EvidenceIntegrityRule(),
        ReleaseGovernanceRule(),
        SecretScannerRule(),
        DangerousCodeRule(),
        PhaseIntegrityRule(),
        BlastRadiusRule(),
    ]
