"""
S-Class Platform Optimization Archetypes

Provides empirical, working-hypothesis archetypes for:
- OpenAI Codex: "Let Codex run. Make the result more trustworthy."
- Anthropic Claude Code: "Let Claude spend intelligence on reasoning; S-Class handles control bookkeeping."
- Google Antigravity: "Let Antigravity maximize parallel intelligence; S-Class maximizes parallel integrity."
- Anysphere Cursor: "Preserve fluid IDE speed; verify multi-file diffs silently."
"""

from __future__ import annotations
from typing import Dict, Tuple, Callable, List, Optional

from sclass.platform.profile import PlatformProfile
from sclass.platform.policy import CompensationPolicy
from sclass.platform.archetypes.codex import get_codex_profile, get_codex_compensation_policy
from sclass.platform.archetypes.claude_code import (
    get_claude_code_profile,
    get_claude_code_compensation_policy,
)
from sclass.platform.archetypes.antigravity import (
    get_antigravity_profile,
    get_antigravity_compensation_policy,
)
from sclass.platform.archetypes.cursor import (
    get_cursor_profile,
    get_cursor_compensation_policy,
)

_ARCHETYPE_REGISTRY: Dict[str, Tuple[Callable[[], PlatformProfile], Callable[[], CompensationPolicy]]] = {
    "codex": (get_codex_profile, get_codex_compensation_policy),
    "claude_code": (get_claude_code_profile, get_claude_code_compensation_policy),
    "antigravity": (get_antigravity_profile, get_antigravity_compensation_policy),
    "cursor": (get_cursor_profile, get_cursor_compensation_policy),
}


def register_archetype(
    platform_id: str,
    profile_factory: Callable[[], PlatformProfile],
    policy_factory: Callable[[], CompensationPolicy],
) -> None:
    """Register or replace a platform archetype in the runtime registry."""
    key = platform_id.strip().lower()
    _ARCHETYPE_REGISTRY[key] = (profile_factory, policy_factory)


def list_archetypes() -> List[str]:
    """List all registered platform archetype identifiers."""
    return sorted(list(_ARCHETYPE_REGISTRY.keys()))


def get_archetype(platform_id: str) -> Tuple[PlatformProfile, CompensationPolicy]:
    """
    Retrieve the PlatformProfile and CompensationPolicy for a given platform.
    
    If unknown, constructs a sensible generic baseline.
    """
    key = platform_id.strip().lower()
    if key in _ARCHETYPE_REGISTRY:
        profile_fn, policy_fn = _ARCHETYPE_REGISTRY[key]
        return profile_fn(), policy_fn()

    # Generic fallback
    generic_profile = PlatformProfile(
        platform_id=key,
        version="1.0.0",
        capabilities=["general_execution"],
        native_strengths=["general_execution"],
    )
    generic_policy = CompensationPolicy(
        preserve=["general_execution"],
        compensate=["accuracy", "security"],
        avoid_interference=["unnecessary_interruptions"],
    )
    return generic_profile, generic_policy


def get_archetype_profile(platform_id: str) -> PlatformProfile:
    """Retrieve just the PlatformProfile for a given platform."""
    profile, _ = get_archetype(platform_id)
    return profile


def get_archetype_policy(platform_id: str) -> CompensationPolicy:
    """Retrieve just the CompensationPolicy for a given platform."""
    _, policy = get_archetype(platform_id)
    return policy


__all__ = [
    "get_codex_profile",
    "get_codex_compensation_policy",
    "get_claude_code_profile",
    "get_claude_code_compensation_policy",
    "get_antigravity_profile",
    "get_antigravity_compensation_policy",
    "get_cursor_profile",
    "get_cursor_compensation_policy",
    "get_archetype",
    "get_archetype_profile",
    "get_archetype_policy",
    "register_archetype",
    "list_archetypes",
]
