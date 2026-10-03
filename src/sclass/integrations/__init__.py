"""S-Class Open-Source Software (OSS) Boundary Integrations.

Per 01-ARCHITECTURE and 02-OSS specs, S-Class consumes mature open-source capabilities
through narrow, replaceable Zone B/C adapters while retaining 100% of canonical semantic authority.

Included integrations:
- SCIPIndexer (Source Code Intelligence Protocol indexing)
- SQLGlotAnalyzer (SQL AST parsing, dialect validation, schema extraction)
- OpenTelemetryBridge (Diagnostic telemetry and tracing with secret redaction)
- ACPBridge (Agent Client Protocol JSON-RPC messaging)
"""

from sclass.integrations.acp_bridge import ACPBridge
from sclass.integrations.opentelemetry_bridge import OpenTelemetryBridge
from sclass.integrations.scip_indexer import SCIPIndexer
from sclass.integrations.sqlglot_analyzer import SQLGlotAnalyzer

__all__ = [
    "ACPBridge",
    "OpenTelemetryBridge",
    "SCIPIndexer",
    "SQLGlotAnalyzer",
]
