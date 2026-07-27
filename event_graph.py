"""
S-Class EOS Event-Driven Graph Architecture (event_graph.py)

Decouples system components into an asynchronous pub/sub event graph:
- TASK_STARTED
- TASK_COMPLETED
- QA_FAILED
- RECOVERY_REQUIRED
- RELEASE_CREATED
- MONITORING_ALERT
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Callable, Any, Optional

logger = logging.getLogger("sclass_event_graph")


class EventTopic:
    TASK_STARTED = "TASK_STARTED"
    TASK_COMPLETED = "TASK_COMPLETED"
    QA_FAILED = "QA_FAILED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    RELEASE_CREATED = "RELEASE_CREATED"
    MONITORING_ALERT = "MONITORING_ALERT"


@dataclass
class GraphEvent:
    topic: str
    sender: str
    payload: Dict[str, Any] = field(default_factory=dict)


class EventGraph:
    """Asynchronous Event Graph Broker for decoupled pub/sub subscription."""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[GraphEvent], None]]] = {}

    def subscribe(self, topic: str, handler: Callable[[GraphEvent], None]) -> None:
        """Subscribes a component handler to an Event Graph topic."""
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(handler)
        logger.info(f"[EventGraph] Subscribed handler to topic '{topic}'")

    def publish(self, topic: str, sender: str, payload: Optional[Dict[str, Any]] = None) -> GraphEvent:
        """Publishes an event to all subscribed handlers on the Event Graph."""
        event = GraphEvent(topic=topic, sender=sender, payload=payload or {})
        logger.info(f"[EventGraph] Event Published [{topic}] from '{sender}'")

        handlers = self._subscribers.get(topic, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"[EventGraph] Error in subscriber handler for '{topic}': {e}")

        return event


# Global Event Graph Broker Singleton
global_event_graph = EventGraph()
