"""
Adversarial Test: Symlink Escape Defense.
Proves that path resolution outside the workspace boundary is strictly governed.
"""

from sclass.control.authority import get_path_authority, PathAuthorityLevel
from sclass.control.resources import classify_resource, AuthorityBoundary


def test_symlink_path_escape_outside_workspace(adv_workspace):
    """Verifies that paths escaping workspace boundary resolve to SCLASS_ONLY authority."""
    outside_path = "../../etc/passwd"
    authority = get_path_authority(outside_path, adv_workspace)
    assert authority == PathAuthorityLevel.SCLASS_ONLY

    _, boundary = classify_resource(outside_path, adv_workspace)
    assert boundary == AuthorityBoundary.SCLASS_TRUST_ROOT
