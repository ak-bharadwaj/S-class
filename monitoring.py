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
from dataclasses import dataclass, field, asdict
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
    """Ingests multi-stream telemetry data, persists events to disk, and evaluates production health."""

    def __init__(self, workspace_dir: Optional[str] = None):
        self.workspace_dir = workspace_dir if workspace_dir else os.getcwd()
        self.events: List[TelemetryEvent] = []
        self._load_telemetry()
        self.register_event_graph_subscribers()

    def register_event_graph_subscribers(self) -> None:
        """Hooks MultiStreamMonitor as an active subscriber to EventGraph topics."""
        try:
            from event_graph import global_event_graph, EventTopic, GraphEvent

            def _handle_qa_failed(evt: GraphEvent) -> None:
                self.ingest_telemetry("crash_reports", "CRITICAL", evt.sender, f"QA Verification Failed: {evt.payload.get('event_name')}", metadata=evt.payload)

            def _handle_recovery(evt: GraphEvent) -> None:
                self.ingest_telemetry("logs", "WARNING", evt.sender, f"Recovery required from phase: {evt.payload.get('from_phase')}", metadata=evt.payload)

            def _handle_release(evt: GraphEvent) -> None:
                self.ingest_telemetry("metrics", "INFO", evt.sender, f"Release completed successfully to phase: {evt.payload.get('to_phase')}", metadata=evt.payload)

            def _handle_alert(evt: GraphEvent) -> None:
                self.ingest_telemetry("security_events", "CRITICAL", evt.sender, f"Monitoring alert triggered: {evt.payload.get('event_name')}", metadata=evt.payload)

            global_event_graph.subscribe(EventTopic.QA_FAILED, _handle_qa_failed)
            global_event_graph.subscribe(EventTopic.RECOVERY_REQUIRED, _handle_recovery)
            global_event_graph.subscribe(EventTopic.RELEASE_CREATED, _handle_release)
            global_event_graph.subscribe(EventTopic.MONITORING_ALERT, _handle_alert)
        except Exception as e:
            logger.warning(f"[MultiStreamMonitor] EventGraph subscription registration skipped: {e}")

    def _get_telemetry_file(self) -> str:
        state_dir = os.path.join(self.workspace_dir, ".agents")
        return os.path.join(state_dir, "telemetry_events.json")

    def _load_telemetry(self) -> None:
        tf = self._get_telemetry_file()
        if os.path.exists(tf):
            try:
                with open(tf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("events", []):
                    self.events.append(TelemetryEvent(
                        stream=item.get("stream", "logs"),
                        severity=item.get("severity", "INFO"),
                        source=item.get("source", "system"),
                        message=item.get("message", ""),
                        metadata=item.get("metadata", {})
                    ))
            except Exception as e:
                logger.warning(f"[MultiStreamMonitor] Failed to load persistent telemetry: {e}")

    def _persist_telemetry(self) -> None:
        tf = self._get_telemetry_file()
        try:
            state_dir = os.path.dirname(tf)
            os.makedirs(state_dir, exist_ok=True)
            payload = {
                "totalCount": len(self.events),
                "events": [asdict(e) for e in self.events]
            }
            tmp_path = tf + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            os.replace(tmp_path, tf)
        except Exception as e:
            logger.warning(f"[MultiStreamMonitor] Failed to persist telemetry events: {e}")

    def ingest_telemetry(self, stream: str, severity: str, source: str, message: str, metadata: Optional[Dict[str, Any]] = None, workspace_dir: Optional[str] = None) -> TelemetryEvent:
        """Ingests a telemetry event into the active monitoring pipeline and persists to disk."""
        if workspace_dir:
            self.workspace_dir = workspace_dir
            
        event = TelemetryEvent(
            stream=stream,
            severity=severity,
            source=source,
            message=message,
            metadata=metadata or {}
        )
        self.events.append(event)
        self._persist_telemetry()
        logger.info(f"[MultiStreamMonitor] Telemetry Ingested & Persisted [{stream.upper()} - {severity}]: {message}")
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
