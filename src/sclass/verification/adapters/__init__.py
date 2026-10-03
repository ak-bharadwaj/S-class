"""S-Class Extended Verification Adapters.

Normalizes heterogeneous external verification tools into the canonical
S-Class MultiEngineVerificationPlane and produces SignedEvidencePayload receipts.

Supported adapters:
- SchemathesisAdapter (OpenAPI / REST API property and fuzz testing)
- TestcontainersAdapter (Dockerized databases and service dependencies)
- PlaywrightAdapter (Headless browser UI and end-to-end testing)
- LocustAdapter (Load, concurrency, and performance SLA verification)
- CosmicRayAdapter (Mutation testing and test suite verification)
"""

from sclass.verification.adapters.cosmic_ray_adapter import CosmicRayAdapter
from sclass.verification.adapters.locust_adapter import LocustAdapter
from sclass.verification.adapters.playwright_adapter import PlaywrightAdapter
from sclass.verification.adapters.schemathesis_adapter import SchemathesisAdapter
from sclass.verification.adapters.testcontainers_adapter import TestcontainersAdapter

__all__ = [
    "CosmicRayAdapter",
    "LocustAdapter",
    "PlaywrightAdapter",
    "SchemathesisAdapter",
    "TestcontainersAdapter",
]
