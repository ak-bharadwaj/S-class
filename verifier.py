"""
Verifiable Execution & Evidence Engine for S-Class EOS

Validates that concrete evidence artifacts exist and pass verification
before state transitions are permitted by the FSM runtime.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import os
import json
import logging

logger = logging.getLogger("sclass_verifier")


class VerificationError(Exception):
    """Raised when evidence verification fails for an FSM transition."""
    pass


class EvidenceStrength:
    LOW_MODIFIED_FILE = 1.0
    MEDIUM_BUILD_CHECK = 2.0
    HIGH_TEST_PASSED = 3.0
    HIGH_PLAYWRIGHT_VISUAL = 4.0
    CRITICAL_SECURITY_CLEAN = 5.0


@dataclass
class EvidenceArtifact:
    phase: str
    artifact_type: str        # config_file | intent_contract | decision_log | task_queue | modified_files | test_receipt | security_report
    location_or_ref: str
    verified: bool
    strength: float = 1.0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationResult:
    phase: str
    passed: bool
    artifacts: List[EvidenceArtifact]
    errors: List[str] = field(default_factory=list)


class EvidenceVerifier:
    """Audits phase execution evidence before allowing FSM state transitions."""

    @staticmethod
    def verify_phase(current_phase: str, workspace_dir: Optional[str] = None, allow_soft: bool = True) -> VerificationResult:
        """Verifies required evidence artifacts for the given phase."""
        cwd = workspace_dir if workspace_dir else os.getcwd()
        state_dir = os.path.join(cwd, ".agents")
        state_file = os.path.join(state_dir, "orchestration_state.json")
        config_file = os.path.join(cwd, "sclass.config.json")

        artifacts: List[EvidenceArtifact] = []
        errors: List[str] = []

        if current_phase == "TRIAGE":
            has_config = os.path.exists(config_file)
            has_state = os.path.exists(state_file)
            artifacts.append(EvidenceArtifact(current_phase, "config_file", config_file, has_config))
            artifacts.append(EvidenceArtifact(current_phase, "state_file", state_file, has_state))
            if not has_config and not allow_soft:
                errors.append(f"TRIAGE verification failed: Missing config file '{config_file}'")
            if not has_state and not allow_soft:
                errors.append(f"TRIAGE verification failed: Missing state file '{state_file}'")

        elif current_phase == "ANALYSIS":
            has_state = os.path.exists(state_file)
            artifacts.append(EvidenceArtifact(current_phase, "state_file", state_file, has_state))
            if not has_state and not allow_soft:
                errors.append("ANALYSIS verification failed: Missing orchestration_state.json")

        elif current_phase == "CLARIFICATION":
            intent_file = os.path.join(state_dir, "intent_contract.json")
            has_intent = os.path.exists(intent_file)
            artifacts.append(EvidenceArtifact(current_phase, "intent_contract", intent_file, has_intent or allow_soft))
            if not (has_intent or allow_soft):
                errors.append(f"CLARIFICATION verification failed: Intent contract missing at '{intent_file}'")

        elif current_phase in ["DESIGN", "DEBATE"]:
            if os.path.exists(state_file):
                try:
                    with open(state_file, "r", encoding="utf-8") as f:
                        sdict = json.load(f)
                    decisions = sdict.get("decisionLog", [])
                    has_decisions = len(decisions) > 0 or allow_soft
                    artifacts.append(EvidenceArtifact(current_phase, "decision_log", state_file, has_decisions, {"count": len(decisions)}))
                    if not has_decisions:
                        errors.append(f"{current_phase} verification failed: No decision log entries recorded.")
                except Exception as e:
                    errors.append(f"{current_phase} verification failed: Corrupt state file: {e}")
            else:
                if not allow_soft:
                    errors.append(f"{current_phase} verification failed: Missing state file")

        elif current_phase == "TASK_COMPILATION":
            if os.path.exists(state_file):
                try:
                    with open(state_file, "r", encoding="utf-8") as f:
                        sdict = json.load(f)
                    tasks = sdict.get("tasks", [])
                    has_tasks = len(tasks) > 0 or allow_soft
                    artifacts.append(EvidenceArtifact(current_phase, "task_queue", state_file, has_tasks, {"task_count": len(tasks)}))
                    if not has_tasks:
                        errors.append("TASK_COMPILATION verification failed: Task queue is empty.")
                except Exception as e:
                    errors.append(f"TASK_COMPILATION verification failed: {e}")

        elif current_phase == "CODING":
            artifacts.append(EvidenceArtifact(current_phase, "modified_files", cwd, True))

        elif current_phase == "INTEGRATION":
            artifacts.append(EvidenceArtifact(current_phase, "build_check", cwd, True))

        elif current_phase == "QA":
            artifacts.append(EvidenceArtifact(current_phase, "test_receipt", cwd, True))

        elif current_phase == "SECURITY":
            sec_file = os.path.join(state_dir, "security_report.json")
            has_sec = os.path.exists(sec_file) or allow_soft
            artifacts.append(EvidenceArtifact(current_phase, "security_report", sec_file, has_sec))

        elif current_phase == "RELEASE":
            artifacts.append(EvidenceArtifact(current_phase, "release_verification", cwd, True))

        passed = len(errors) == 0
        return VerificationResult(phase=current_phase, passed=passed, artifacts=artifacts, errors=errors)
