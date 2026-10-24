"""S-Class product layer definitions, artifact models, and schema validation."""

from sclass.product.artifacts import (
    ArtifactType,
    Phase,
    AuthorityClass,
    WorkType,
    ArtifactClass,
    CommonPhaseArtifact,
    SchemaRegistry,
    ValidationError,
    ValidationResult,
    validate_artifact,
    compute_content_digest,
    evaluate_f1_representation,
)

__all__ = [
    "ArtifactType",
    "Phase",
    "AuthorityClass",
    "WorkType",
    "ArtifactClass",
    "CommonPhaseArtifact",
    "SchemaRegistry",
    "ValidationError",
    "ValidationResult",
    "validate_artifact",
    "compute_content_digest",
    "evaluate_f1_representation",
]
