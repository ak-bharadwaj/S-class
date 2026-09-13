"""
S-Class Product Package.
"""
from sclass.product.installation import verify_installation
from sclass.product.compatibility import check_compatibility
from sclass.product.diagnostics import run_diagnostics
from sclass.product.onboarding import initialize_workspace

__all__ = [
    "verify_installation",
    "check_compatibility",
    "run_diagnostics",
    "initialize_workspace",
]
