"""
S-Class Context: Cross-Platform Continuity Engine (Phase 13 / B.12).
Enables zero-drift cross-agent state transfers:
Codex -> VerifiedProjectState -> Claude Code -> Antigravity

Ensures that target agent begins execution with:
- Exact repository revision & verified filesystem fingerprint
- Proven work backed by independent OS receipts (not unverified memory)
- Remaining open tasks & known blockers
- Known failure modes & invalidated claims
- Tailored platform prompt projection without transcript bloat
"""

from __future__ import annotations
import os
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from sclass.domain.project import VerifiedProjectState
from sclass.context.handoff import HandoffPackage, HandoffAssembler
from sclass.observation.fingerprint import compute_workspace_snapshot, compute_workspace_fingerprint
from sclass.telemetry.tracing import get_local_tracer, SPAN_PLATFORM_ADAPT
from sclass.core.errors import HandoffIntegrityError


@dataclass(frozen=True)
class ContinuityTransferResult:
    """Result of cross-platform state handoff transfer."""
    success: bool
    source_platform: str
    target_platform: str
    handoff_package: HandoffPackage
    prompt_projection: str
    verified_work_count: int
    remaining_tasks_count: int
    known_risks_count: int
    working_tree_fingerprint: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "source_platform": self.source_platform,
            "target_platform": self.target_platform,
            "package_id": self.handoff_package.package_id,
            "verified_work_count": self.verified_work_count,
            "remaining_tasks_count": self.remaining_tasks_count,
            "known_risks_count": self.known_risks_count,
            "working_tree_fingerprint": self.working_tree_fingerprint,
            "prompt_projection": self.prompt_projection,
            "timestamp": self.timestamp,
        }


class CrossPlatformContinuityEngine:
    """
    Coordinates verified handoffs across heterogeneous agent harnesses.
    Eliminates prompt drift, hallucinated continuity, and lost failure context.
    """

    @classmethod
    def transfer(
        cls,
        source_platform: str,
        target_platform: str,
        state: VerifiedProjectState,
        workspace_dir: Optional[str] = None,
        next_action: Optional[str] = None,
        strict_fingerprint_check: bool = True,
    ) -> ContinuityTransferResult:
        """
        Transfers verified state from source platform to target platform with cryptographic anchoring.
        """
        ws = os.path.abspath(workspace_dir or state.workspace or os.getcwd())

        # 1. Compute and verify current workspace fingerprint
        snap = compute_workspace_snapshot(ws)
        curr_fp = compute_workspace_fingerprint(snap)

        if strict_fingerprint_check and state.current_revision:
            if state.current_revision != curr_fp:
                raise HandoffIntegrityError(
                    f"CONTINUITY REJECTED: Workspace divergence detected. "
                    f"Expected revision '{state.current_revision[:12]}...', but observed '{curr_fp[:12]}...'. "
                    "Cannot hand off mutated, unobserved workspace to target agent."
                )

        # 2. Assemble authoritative handoff package
        pkg = HandoffAssembler.assemble_from_verified_state(
            state=state,
            workspace_dir=ws,
            target_platform=target_platform,
            next_action=next_action,
        )

        state.handoff = pkg.to_dict()

        # 3. Format platform-tailored projection
        projection = cls.synthesize_platform_projection(
            target_platform=target_platform,
            state=state,
            pkg=pkg,
        )
        state.agent_context_summary = projection

        # 4. Record telemetry span
        tracer = get_local_tracer(ws)
        with tracer.span(SPAN_PLATFORM_ADAPT, attributes={
            "source_platform": source_platform,
            "target_platform": target_platform,
            "package_id": pkg.package_id,
            "verified_tasks_count": len(state.verified_claims) or len(state.verified_tasks),
            "invalidated_claims_count": len(state.invalidated_claims) or len(state.rejected_claims),
        }) as span:
            span.set_attributes({
                "continuity_status": "SUCCESS",
                "revision": curr_fp,
            })

        return ContinuityTransferResult(
            success=True,
            source_platform=source_platform,
            target_platform=target_platform,
            handoff_package=pkg,
            prompt_projection=projection,
            verified_work_count=len(state.verified_claims) or len(state.verified_tasks),
            remaining_tasks_count=len(state.pending_verification) or (1 if state.active_task else 0),
            known_risks_count=len(state.invalidated_claims) or len(state.rejected_claims),
            working_tree_fingerprint=curr_fp,
        )

    @classmethod
    def synthesize_platform_projection(
        cls,
        target_platform: str,
        state: VerifiedProjectState,
        pkg: HandoffPackage,
    ) -> str:
        """Synthesizes high-fidelity context projection tailored to target platform harness."""
        p_norm = target_platform.lower()

        lines = [
            f"# S-Class Universal Truth Handoff: {target_platform.upper()}",
            f"- Working Tree Fingerprint: `{pkg.checkpoint.working_tree_fingerprint[:16]}`",
            f"- Handoff Package ID: `{pkg.package_id[:16]}`",
            "",
            "## 1. Verified Prior Work (Cryptographically Observed)",
        ]

        if state.verified_claims:
            for c in state.verified_claims:
                stmt = c.get("statement") or c.get("claim_id") or "verified item"
                rcpt = c.get("evidence_receipt_id", "observed")
                lines.append(f"- [x] {stmt} (proof: `{rcpt}`)")
        elif state.verified_tasks:
            for t in state.verified_tasks:
                lines.append(f"- [x] Task `{t}` verified.")
        else:
            lines.append("- No tasks verified yet.")

        lines.extend(["", "## 2. Active Focus & Next Action"])
        act = pkg.task_context.get("task_id") or state.active_task or "None"
        next_act = pkg.next_action or state.next_action or "Inspect pending tasks."
        lines.append(f"- Active Task: `{act}`")
        lines.append(f"- Authoritative Next Step: {next_act}")

        lines.extend(["", "## 3. Known Risks & Invalidated Claims"])
        if state.invalidated_claims:
            for inv in state.invalidated_claims:
                cid = inv.get("claim_id", "unknown")
                reason = inv.get("reason", "Verification rejected")
                lines.append(f"- [!] `{cid}`: {reason}")
        elif state.rejected_claims:
            for r in state.rejected_claims:
                lines.append(f"- [!] Rejected: `{r}`")
        else:
            lines.append("- Zero known failure modes.")

        if "claude" in p_norm:
            lines.extend([
                "",
                "## 4. Claude Code Protocol Directive",
                "- Reasoning Preservation: Focus deep inference on resolving active task blockers.",
                "- Tool Efficiency: Rely on verified receipts rather than re-running passed suites.",
            ])
        elif "codex" in p_norm:
            lines.extend([
                "",
                "## 4. OpenAI Codex Protocol Directive",
                "- Long-Horizon Session: Resume uninterrupted multi-turn loop from active focus.",
                "- Verification Gating: Conclude with clean test run matching S-Class verification plan.",
            ])
        elif "antigravity" in p_norm or "gemini" in p_norm:
            lines.extend([
                "",
                "## 4. Google Antigravity Protocol Directive",
                "- Parallel Swarm Coordination: Parallelize subtasks across isolated boundaries.",
                "- Concurrency Safety: Respect verified file locks to avoid state conflict.",
            ])

        return "\n".join(lines)

    @classmethod
    def validate_law_l9_compliance(cls, pkg: HandoffPackage) -> bool:
        """
        Validates Invariant Law L9: Handoff carries verified truth and observed receipts,
        never chat transcripts, conversation histories, or prompt bloat.
        """
        forbidden_keys = {"chat_transcript", "conversation_history", "messages", "dialogue", "chat_log", "raw_prompt"}
        pkg_dict = pkg.to_dict()

        def scan_keys(obj: Any, path: str = ""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k in forbidden_keys:
                        raise HandoffIntegrityError(
                            f"Law L9 Violation: Handoff package contains conversational transcript data at '{path}.{k}'."
                        )
                    scan_keys(v, f"{path}.{k}")
            elif isinstance(obj, (list, tuple)):
                for i, item in enumerate(obj):
                    scan_keys(item, f"{path}[{i}]")

        scan_keys(pkg_dict, "package")
        return True

    @classmethod
    def execute_agent_handoff(
        cls,
        workspace_dir: str,
        source_agent_id: str,
        target_agent_id: str,
        source_platform: str = "generic",
        target_platform: str = "generic",
        next_action: Optional[str] = None,
        project_state: Optional[VerifiedProjectState] = None,
    ) -> ContinuityTransferResult:
        """
        Executes a complete verified cross-agent handoff under Law L9.
        Creates a durable checkpoint, packages verified state, validates L9 compliance,
        and hands off cleanly to target agent without conversational bloat.
        """
        ws = os.path.abspath(workspace_dir)
        snap = compute_workspace_snapshot(ws)
        curr_fp = compute_workspace_fingerprint(snap)

        if project_state is None:
            project_state = VerifiedProjectState(
                workspace=ws,
                current_revision=curr_fp,
                active_task=None,
                next_action=next_action,
            )

        # Assemble and transfer
        result = cls.transfer(
            source_platform=source_platform,
            target_platform=target_platform,
            state=project_state,
            workspace_dir=ws,
            next_action=next_action,
            strict_fingerprint_check=False,
        )

        # Verify Law L9 compliance
        cls.validate_law_l9_compliance(result.handoff_package)

        # Record handoff transition in ledger
        try:
            from sclass.trust.ledger import LocalLedger
            ledger = LocalLedger(workspace_dir=ws)
            ledger.append(
                event="HANDOFF",
                payload={
                    "source_agent_id": source_agent_id,
                    "target_agent_id": target_agent_id,
                    "source_platform": source_platform,
                    "target_platform": target_platform,
                    "package_id": result.handoff_package.package_id,
                    "verified_work_count": result.verified_work_count,
                    "working_tree_fingerprint": curr_fp,
                },
            )
        except Exception:
            pass

        return result

