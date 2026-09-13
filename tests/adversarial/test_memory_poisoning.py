"""
Adversarial Test: Memory Poisoning Defense.
Proves that external memory or natural-language assertions cannot establish truth
or bypass authoritative project verification.
"""

from sclass.domain.project import VerifiedProjectState
from sclass.memory.local import LocalMemoryProvider
from sclass.memory.provider import MemoryItem, MemoryScope


def test_memory_cannot_certify_task_completion(adv_workspace):
    """
    Part XV:
    Agent injects a claim into memory: 'JWT auth was fixed and tests passed'.
    VerifiedProjectState must NOT mark the task verified unless backed by
    an authoritative verification event.
    """
    mem = LocalMemoryProvider(workspace_dir=adv_workspace)
    item = MemoryItem(
        key="task_42_status",
        content="JWT auth was fixed and tests passed",
        category="decision",
        metadata={"scope": MemoryScope.PROJECT.value},
    )
    mem.remember(item)

    retrieved = mem.retrieve("JWT auth")
    assert len(retrieved) > 0

    state = VerifiedProjectState(goal="Harden authentication")

    # State cannot be marked complete via memory recall alone
    assert "task_42" not in state.verified_tasks

    # Only an authoritative verification event can mark it complete
    state.mark_task_verified("task_42", verification_event_id="vevt_authentic_999")
    assert "task_42" in state.verified_tasks
    assert state.verification_checkpoint == "vevt_authentic_999"
