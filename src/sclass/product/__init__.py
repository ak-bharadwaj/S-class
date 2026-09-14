"""
S-Class Product Package.
"""
from sclass.product.installation import verify_installation
from sclass.product.compatibility import check_compatibility
from sclass.product.diagnostics import run_diagnostics
from sclass.product.onboarding import initialize_workspace
from sclass.product.silent_governance import (
    SilentGovernanceController,
    SilentGovernanceMode,
    GovernanceEvent,
)
from sclass.product.provider_discovery import (
    ProviderDiscovery,
    DiscoveredProvider,
)
from sclass.product.config import (
    SClassConfig,
    GeneralConfig,
    PolicyConfig,
    ExecutionConfig,
    VerificationConfig,
    MemoryConfig,
    FleetConfig,
    PlatformConfig,
    LoggingConfig,
    load_config,
    save_config,
    validate_config,
    generate_default_config,
)
from sclass.product.installer import (
    ProductInstaller,
    ConfigMigrator,
    InstallationResult,
    MigrationResult,
    DetectedPlatformInfo,
)

__all__ = [
    "verify_installation",
    "check_compatibility",
    "run_diagnostics",
    "initialize_workspace",
    "SilentGovernanceController",
    "SilentGovernanceMode",
    "GovernanceEvent",
    "ProviderDiscovery",
    "DiscoveredProvider",
    "SClassConfig",
    "GeneralConfig",
    "PolicyConfig",
    "ExecutionConfig",
    "VerificationConfig",
    "MemoryConfig",
    "FleetConfig",
    "PlatformConfig",
    "LoggingConfig",
    "load_config",
    "save_config",
    "validate_config",
    "generate_default_config",
    "ProductInstaller",
    "ConfigMigrator",
    "InstallationResult",
    "MigrationResult",
    "DetectedPlatformInfo",
]
