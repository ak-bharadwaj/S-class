"""
S-Class Cross-Platform Rule Projector (rule_projector.py)

Adopts AGENTS.md as the canonical single source of truth for repository agent rules.
Projects synchronized rule files across development tooling:
  - CLAUDE.md (Claude Code)
  - .cursorrules (Cursor IDE)
  - .windsurfrules (Windsurf IDE)
  - .github/copilot-instructions.md (GitHub Copilot)

Includes CI drift detection and automated synchronization compatible with agentsync/syncmd.
"""

import os
import sys
import hashlib
from typing import Dict, Tuple, List, Optional

HEADER_TEMPLATE = """<!--
GENERATED AUTOMATICALLY BY S-CLASS RULE PROJECTOR FROM AGENTS.md
DO NOT EDIT DIRECTLY. MUTATIONS WILL BE OVERWRITTEN.
RUN: sclass rules --sync
CI DRIFT CHECK: sclass rules --check
-->\n\n"""

DEFAULT_CANONICAL_AGENTS_MD = """# AGENTS.md — S-Class Sovereign Agent Behavioral Standards

## 1. Epistemic Rigor & Anti-Hallucination Mandate
- Inspect before Infer: Always inspect existing schema, database models, and route definitions before proposing modifications.
- Never invent unrequested capabilities, mockup data, or phantom APIs.
- Enforce strict type validation and contractual verification on all changes.

## 2. Deterministic Execution & Safety Invariants
- Honor Layer-0 FileLock concurrency control.
- All state transitions must pass through the formal Kernel FSM.
- Release candidates require authentic cryptographic verification proofs.
"""


class RuleProjector:
    """
    Projects AGENTS.md into platform-specific configuration files and detects configuration drift in CI.
    """

    TARGET_FILES = [
        "CLAUDE.md",
        ".cursorrules",
        ".windsurfrules",
        os.path.join(".github", "copilot-instructions.md")
    ]

    def __init__(self, workspace_dir: Optional[str] = None):
        self.workspace_dir = os.path.abspath(workspace_dir if workspace_dir else os.getcwd())
        self.canonical_file = os.path.join(self.workspace_dir, "AGENTS.md")

    def get_canonical_content(self) -> str:
        """Loads canonical AGENTS.md content or creates default template."""
        if os.path.exists(self.canonical_file):
            with open(self.canonical_file, "r", encoding="utf-8") as f:
                return f.read()
        return DEFAULT_CANONICAL_AGENTS_MD

    def compute_projection(self, target_rel_path: str) -> str:
        """Computes expected projected file content from AGENTS.md."""
        canonical = self.get_canonical_content().strip()
        return HEADER_TEMPLATE + canonical + "\n"

    def check_drift(self) -> Tuple[bool, Dict[str, str]]:
        """
        Checks for drift between canonical AGENTS.md and projected target files.
        Returns (has_drift: bool, file_statuses: Dict[rel_path, status]).
        """
        statuses = {}
        has_drift = False

        if not os.path.exists(self.canonical_file):
            statuses["AGENTS.md"] = "MISSING"
            has_drift = True

        for rel_path in self.TARGET_FILES:
            target_path = os.path.join(self.workspace_dir, *rel_path.replace("\\", "/").split("/"))
            expected = self.compute_projection(rel_path)

            if not os.path.exists(target_path):
                statuses[rel_path] = "MISSING"
                has_drift = True
                continue

            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    actual = f.read()

                # Normalize line endings
                if actual.replace("\r\n", "\n").strip() != expected.replace("\r\n", "\n").strip():
                    statuses[rel_path] = "DRIFTED"
                    has_drift = True
                else:
                    statuses[rel_path] = "IN_SYNC"
            except Exception as e:
                statuses[rel_path] = f"ERROR: {e}"
                has_drift = True

        return has_drift, statuses

    def sync(self) -> List[str]:
        """
        Projects AGENTS.md to all target rule files.
        Returns list of successfully projected relative file paths.
        """
        canonical = self.get_canonical_content()
        os.makedirs(self.workspace_dir, exist_ok=True)
        # If AGENTS.md didn't exist, write it
        if not os.path.exists(self.canonical_file):
            with open(self.canonical_file, "w", encoding="utf-8") as f:
                f.write(canonical)

        synced = []
        for rel_path in self.TARGET_FILES:
            target_path = os.path.join(self.workspace_dir, rel_path)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            content = self.compute_projection(rel_path)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)
            synced.append(rel_path)

        return synced


def main():
    import argparse
    parser = argparse.ArgumentParser(
        prog="rule_projector",
        description="S-Class Cross-Platform Rule Projector & CI Drift Linter"
    )
    parser.add_argument("--check", action="store_true", help="Run CI drift check. Exits with 1 if drift detected.")
    parser.add_argument("--sync", action="store_true", help="Project AGENTS.md into target rule files.")
    parser.add_argument("--workspace", default=os.getcwd(), help="Target workspace directory")

    args = parser.parse_args()
    projector = RuleProjector(args.workspace)

    if args.check:
        has_drift, statuses = projector.check_drift()
        if has_drift:
            print("[!] CI Lint Failure: Rule drift detected against AGENTS.md:")
            for path, st in statuses.items():
                print(f"  - {path}: {st}")
            sys.exit(1)
        else:
            print("[OK] All projected rule files match AGENTS.md.")
            sys.exit(0)
    else:
        synced = projector.sync()
        print(f"[OK] Successfully projected AGENTS.md to {len(synced)} rule files:")
        for p in synced:
            print(f"  - {p}")
        sys.exit(0)


if __name__ == "__main__":
    main()
