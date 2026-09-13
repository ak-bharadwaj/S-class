"""
Adversarial Test: Junction Escape Defense.
Proves that directory boundary containment checks prevent external junction/traversal escapes.
"""

import os
from sclass.storage.paths import WorkspacePaths


def test_directory_containment_prevents_escape(adv_workspace):
    paths = WorkspacePaths(adv_workspace)
    outside = os.path.abspath(os.path.join(adv_workspace, "..", "..", "system32"))
    assert not paths.is_contained(outside)
