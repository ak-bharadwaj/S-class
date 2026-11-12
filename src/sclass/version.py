"""S-Class Authoritative Version Contract (F10).

One authoritative source for product/package version and kernel baseline version.
Product/package version: 6.0.2
Kernel baseline version: 6.0.1
"""
from __future__ import annotations

PRODUCT_VERSION: str = "6.0.2"
KERNEL_BASELINE_VERSION: str = "6.0.1"

__version__: str = PRODUCT_VERSION
VERSION: str = PRODUCT_VERSION

__all__ = [
    "PRODUCT_VERSION",
    "KERNEL_BASELINE_VERSION",
    "__version__",
    "VERSION",
]
