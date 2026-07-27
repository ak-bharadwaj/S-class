"""
S-Class EOS Multi-Stream Active Monitoring Engine (monitoring.py)

Ingests 6 active telemetry streams to detect post-release production anomalies:
1. Logs             -> Console stderr/stdout exception lines
2. Metrics          -> Memory utilization, HTTP 5xx error rate
3. User Reports     -> User feedback submission payloads
4. Crash Reports    -> Uncaught runtime process crashes
5. Performance      -> Render latency degradation (TTFB > threshold)
6. Security Events  -> Auth failure spikes, injection attempt alerts
"""

import os
import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

logger = logging.getLogger("sclass_monitoring")


@dataclass
class TelemetryEvent:
    stream: str  # logs | metrics | user_reports | crash_reports | performance | security_events
    severity: str  # CRITICAL | WARNING | INFO
    source: str
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class MultiStreamMonitor:
    """Ingests multi-stream telemetry data and evaluates production health."""

    def __init__(self):
        self.events: List[TelemetryEvent] = []

    def ingest_telemetry(self, stream: str, severity: str, source: str, message: str, metadata: Optional[Dict[str, Any]] = None) -> TelemetryEvent:
        """Ingests a telemetry event into the active monitoring pipeline."""
        event = TelemetryEvent(
            stream=stream,
            severity=severity,
            source=source,
            message=message,
            metadata=metadata or {}
        )
        self.events.append(event)
        logger.info(f"[MultiStreamMonitor] Telemetry Ingested [{stream.upper()} - {severity}]: {message}")
        return event

    def evaluate_production_health(self) -> Dict[str, Any]:
        """Evaluates active telemetry events to determine if an issue should be triggered."""
        critical_count = sum(1 for e in self.events if e.severity == "CRITICAL")
        warning_count = sum(1 for e in self.events if e.severity == "WARNING")

        has_anomaly = critical_count > 0 or warning_count >= 3
        anomaly_streams = list(set(e.stream for e in self.events if e.severity in ["CRITICAL", "WARNING"]))

        return {
            "healthy": not has_anomaly,
            "criticalCount": critical_count,
            "warningCount": warning_count,
            "anomalyStreams": anomaly_streams,
            "totalTelemetryCount": len(self.events)
        }
