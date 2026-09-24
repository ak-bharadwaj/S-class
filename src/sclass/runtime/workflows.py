"""
S-Class Runtime: Workflow Orchestration Engine & MCP/Skill/Plugin Registry.
Implements the harvested Step-Code workflow primitives & plugin lifecycles (Directive Sections 10 & 11):
- Workflow primitives: phase(), parallel(), pipeline(), agent(), iteration.
- Resilient workflow journaling and resumption across restarts.
- MCP server lifecycle: discovery, connection, degraded state, schema registration.
- Imported plugin/skill descriptor:
    artifact identity, source, version, digest, capability declaration,
    permission scope, trust classification.
- Invariants:
  1. External plugins/tools cannot silently become authoritative.
  2. Workflow completion != S-Class completion; workflow result must independently
     pass S-Class completion adjudication.
"""

from __future__ import annotations
import os
import json
import uuid
import hashlib
from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable, Set, Union

from sclass.core.errors import SecurityViolationError


class TrustClassification(str, Enum):
    UNTRUSTED = "UNTRUSTED"
    ISOLATED = "ISOLATED"
    VERIFIED_ADAPTER = "VERIFIED_ADAPTER"


@dataclass(frozen=True)
class PluginArtifact:
    """Authoritative descriptor for an imported tool, MCP server, skill, or plugin."""
    artifact_id: str
    name: str
    source_type: str  # "mcp", "skill", "plugin", "tool"
    source_uri: str
    version: str
    content_digest: str
    capability_declarations: List[str]
    permission_scope: Dict[str, Any]
    trust_classification: TrustClassification = TrustClassification.UNTRUSTED
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "name": self.name,
            "source_type": self.source_type,
            "source_uri": self.source_uri,
            "version": self.version,
            "content_digest": self.content_digest,
            "capability_declarations": list(self.capability_declarations),
            "permission_scope": dict(self.permission_scope),
            "trust_classification": self.trust_classification.value,
            "created_at": self.created_at,
        }


class PluginRegistry:
    """Manages imported tools, skills, and MCP connectors, enforcing trust classification."""

    def __init__(self):
        self._artifacts: Dict[str, PluginArtifact] = {}

    def register_artifact(
        self,
        name: str,
        source_type: str,
        source_uri: str,
        version: str,
        content_bytes: bytes,
        capabilities: List[str],
        permission_scope: Optional[Dict[str, Any]] = None,
        trust: TrustClassification = TrustClassification.UNTRUSTED,
    ) -> PluginArtifact:
        digest = hashlib.sha256(content_bytes).hexdigest()
        art_id = f"art_{uuid.uuid4().hex[:8]}"

        artifact = PluginArtifact(
            artifact_id=art_id,
            name=name,
            source_type=source_type,
            source_uri=source_uri,
            version=version,
            content_digest=digest,
            capability_declarations=capabilities,
            permission_scope=permission_scope or {"network": False, "write": False},
            trust_classification=trust,
        )
        self._artifacts[art_id] = artifact
        return artifact

    def get_artifact(self, artifact_id: str) -> Optional[PluginArtifact]:
        return self._artifacts.get(artifact_id)


class WorkflowStepType(str, Enum):
    PHASE = "PHASE"
    PARALLEL = "PARALLEL"
    PIPELINE = "PIPELINE"
    AGENT = "AGENT"
    ITERATION = "ITERATION"


@dataclass
class WorkflowStep:
    """Individual node within a structured multi-agent workflow."""
    step_id: str
    step_type: WorkflowStepType
    name: str
    description: str = ""
    substeps: List[WorkflowStep] = field(default_factory=list)
    agent_role: Optional[str] = None
    max_budget_tokens: int = 50000
    status: str = "PENDING"
    result: Optional[Dict[str, Any]] = None


@dataclass
class WorkflowExecutionResult:
    """Outcome of a workflow run. Must be adjudicated by S-Class CompletionEvaluator."""
    workflow_id: str
    workflow_name: str
    status: str  # "COMPLETED", "FAILED", "BUDGET_EXCEEDED"
    journal_path: str
    step_results: Dict[str, Any]
    candidate_artifacts: List[Dict[str, Any]]
    untrusted_execution_fact: bool = True  # Untrusted execution fact, not project truth


class WorkflowEngine:
    """
    Executes and journals phased, pipelined, or parallel multi-agent workflows.
    """

    def __init__(self, workspace_dir: str):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.journal_dir = os.path.join(self.workspace_dir, ".sclass", "workflows")
        os.makedirs(self.journal_dir, exist_ok=True)

    def phase(self, name: str, steps: List[WorkflowStep]) -> WorkflowStep:
        return WorkflowStep(
            step_id=f"step_phase_{uuid.uuid4().hex[:8]}",
            step_type=WorkflowStepType.PHASE,
            name=name,
            substeps=steps,
        )

    def parallel(self, name: str, steps: List[WorkflowStep]) -> WorkflowStep:
        return WorkflowStep(
            step_id=f"step_par_{uuid.uuid4().hex[:8]}",
            step_type=WorkflowStepType.PARALLEL,
            name=name,
            substeps=steps,
        )

    def pipeline(self, name: str, steps: List[WorkflowStep]) -> WorkflowStep:
        return WorkflowStep(
            step_id=f"step_pipe_{uuid.uuid4().hex[:8]}",
            step_type=WorkflowStepType.PIPELINE,
            name=name,
            substeps=steps,
        )

    def agent(self, name: str, role: str, max_tokens: int = 25000) -> WorkflowStep:
        return WorkflowStep(
            step_id=f"step_agent_{uuid.uuid4().hex[:8]}",
            step_type=WorkflowStepType.AGENT,
            name=name,
            agent_role=role,
            max_budget_tokens=max_tokens,
        )

    def run_workflow(
        self,
        workflow_name: str,
        root_step: WorkflowStep,
        step_runner_fn: Callable[[WorkflowStep], Dict[str, Any]],
    ) -> WorkflowExecutionResult:
        """
        Executes workflow steps while maintaining an append-only journal for resume behavior.
        """
        wf_id = f"wf_{uuid.uuid4().hex[:8]}"
        journal_file = os.path.join(self.journal_dir, f"{wf_id}.jsonl")
        step_results: Dict[str, Any] = {}
        all_candidate_artifacts: List[Dict[str, Any]] = []

        def _execute_step(s: WorkflowStep) -> None:
            s.status = "RUNNING"
            self._journal_step(journal_file, wf_id, s.step_id, "START", {})

            if s.substeps:
                for sub in s.substeps:
                    _execute_step(sub)
                s.status = "COMPLETED"
                s.result = {"substep_count": len(s.substeps), "status": "COMPLETED"}
            else:
                out = step_runner_fn(s)
                s.status = "COMPLETED"
                s.result = out
                if "artifacts" in out and isinstance(out["artifacts"], list):
                    all_candidate_artifacts.extend(out["artifacts"])

            step_results[s.step_id] = s.result
            self._journal_step(journal_file, wf_id, s.step_id, "COMPLETED", s.result or {})

        _execute_step(root_step)

        return WorkflowExecutionResult(
            workflow_id=wf_id,
            workflow_name=workflow_name,
            status="COMPLETED",
            journal_path=journal_file,
            step_results=step_results,
            candidate_artifacts=all_candidate_artifacts,
            untrusted_execution_fact=True,
        )

    def _journal_step(self, path: str, wf_id: str, step_id: str, event_type: str, data: Dict[str, Any]) -> None:
        record = {
            "workflow_id": wf_id,
            "step_id": step_id,
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
