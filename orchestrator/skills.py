"""
S-Class Selectable Engineering Skill Registry.

Maintains canonical deterministic skill playbooks that structure model exploration,
testing, debugging, and refactoring without bypassing governance.
"""

from typing import Dict, Optional, Tuple
from orchestrator.models import SkillPlaybook


class EngineeringSkillRegistry:
    """Registry of pre-vetted, evidence-producing engineering procedures."""

    _PLAYBOOKS: Dict[str, SkillPlaybook] = {
        "skill-tdd-verification": SkillPlaybook(
            skill_id="skill-tdd-verification",
            name="Test-Driven Verification Playbook",
            purpose="Enforces red-green-refactor verification discipline for functional invariants.",
            guidelines=(
                "Formulate minimal isolated test asserting target invariant before modifying production code.",
                "Verify test executes in isolated D6 sandbox and reproduces expected failure.",
                "Emit minimal code patch satisfying assertion without collateral modifications.",
            ),
            required_capabilities=("CAP_EXEC_TEST", "CAP_PROPOSE_ACTION"),
            target_action_type="EXECUTE_TEST",
        ),
        "skill-systematic-debug": SkillPlaybook(
            skill_id="skill-systematic-debug",
            name="Systematic Root-Cause Debugging Playbook",
            purpose="Isolates defects through structured hypothesis testing rather than speculative trial-and-error.",
            guidelines=(
                "Parse stdout diagnostics and refuting evidence observations from AssessmentReceipt.",
                "Formulate single falsifiable hypothesis explaining the failure mode.",
                "Construct minimal reproduction harness before formulating repair patch.",
            ),
            required_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION"),
            target_action_type="PROPOSE_PATCH",
        ),
        "skill-ast-refactor": SkillPlaybook(
            skill_id="skill-ast-refactor",
            name="AST Contract-Preserving Refactoring Playbook",
            purpose="Restructures code architecture while preserving public symbol contracts and invariants.",
            guidelines=(
                "Verify all public function/class signatures and types remain invariant.",
                "Ensure zero breaking changes to existing dependent modules.",
                "Run regression suite immediately following refactoring action.",
            ),
            required_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION", "CAP_EXEC_TEST"),
            target_action_type="PROPOSE_PATCH",
        ),
        "skill-security-audit": SkillPlaybook(
            skill_id="skill-security-audit",
            name="Boundary Security & Capability Audit Playbook",
            purpose="Audits input validation, cryptographic signatures, and authority boundaries.",
            guidelines=(
                "Verify fail-closed validation on all external untrusted inputs.",
                "Enforce HMAC and Ed25519 signature verification on state receipts.",
                "Ensure zero unauthenticated execution paths or capability escalations.",
            ),
            required_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION"),
            target_action_type="EXECUTE_TEST",
        ),
        "skill-api-contract": SkillPlaybook(
            skill_id="skill-api-contract",
            name="API Schema & Invariant Contract Playbook",
            purpose="Verifies schema adherence, type signatures, and idempotency guarantees.",
            guidelines=(
                "Verify request and response schemas against OpenAPI/Pydantic models.",
                "Verify idempotency token replay protection on mutating endpoints.",
            ),
            required_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION"),
            target_action_type="EXECUTE_TEST",
        ),
        "skill-perf-benchmark": SkillPlaybook(
            skill_id="skill-perf-benchmark",
            name="Performance & Resource Soak Playbook",
            purpose="Measures execution latency distribution and memory drift under load.",
            guidelines=(
                "Execute multi-iteration benchmark and compute 95% confidence intervals.",
                "Verify P95 latency and throughput ratios satisfy preregistered thresholds.",
            ),
            required_capabilities=("CAP_EXEC_TEST",),
            target_action_type="EXECUTE_TEST",
        ),
    }

    @classmethod
    def get(cls, skill_id: str) -> Optional[SkillPlaybook]:
        """Retrieves a skill playbook by ID."""
        return cls._PLAYBOOKS.get(skill_id)

    @classmethod
    def all_skills(cls) -> Tuple[SkillPlaybook, ...]:
        """Returns all registered skill playbooks."""
        return tuple(cls._PLAYBOOKS.values())

    @classmethod
    def select_for_mode(cls, mode_name: str, has_refutation: bool = False) -> Optional[SkillPlaybook]:
        """Selects the canonical skill playbook for a given reasoning mode."""
        if mode_name in ("DIAGNOSE", "REPAIR") or has_refutation:
            return cls.get("skill-systematic-debug")
        elif mode_name == "VERIFY":
            return cls.get("skill-tdd-verification")
        elif mode_name == "REVIEW":
            return cls.get("skill-security-audit")
        elif mode_name == "ARCHITECT":
            return cls.get("skill-api-contract")
        return None
