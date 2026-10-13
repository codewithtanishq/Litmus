"""
Framework-independent event publisher interface and implementations for Swarm Debugger.

Used by the orchestration layer to emit real workflow events during actual execution.
These events form the audit trail for the Transparent Courtroom Visualizer.
"""

from abc import ABC, abstractmethod
import logging
import threading
from typing import Callable, List, Optional
from datetime import datetime, timezone

from app.schemas.events import WorkflowEvent, WorkflowEventType

logger = logging.getLogger(__name__)

EventCallback = Callable[[WorkflowEvent], None]


class BaseEventPublisher(ABC):
    """
    Abstract interface for publishing workflow events.
    Framework-independent to decouple orchestration from visualization engines.
    """

    @abstractmethod
    def publish(self, event: WorkflowEvent) -> None:
        """Publishes a structured workflow event to all active listeners."""
        pass

    @abstractmethod
    def subscribe(self, callback: EventCallback) -> None:
        """Registers a listener callback that receives every published event."""
        pass

    def emit(
        self,
        event_type: WorkflowEventType,
        session_id: str,
        round_number: int = 1,
        data: Optional[dict] = None,
    ) -> WorkflowEvent:
        """
        Convenience method to construct and publish a WorkflowEvent.
        """
        event = WorkflowEvent(
            session_id=session_id,
            round_number=round_number,
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            data=data or {},
        )
        self.publish(event)
        return event


class InMemoryEventPublisher(BaseEventPublisher):
    """
    Thread-safe in-memory event publisher.
    Stores all published events in an ordered buffer and broadcasts to registered subscribers.
    """

    def __init__(self) -> None:
        self._events: List[WorkflowEvent] = []
        self._subscribers: List[EventCallback] = []
        self._lock = threading.Lock()

    def publish(self, event: WorkflowEvent) -> None:
        """Appends event to memory store and notifies all subscribers."""
        with self._lock:
            self._events.append(event)
            callbacks = list(self._subscribers)

        for callback in callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in event subscriber callback: {e}", exc_info=True)

    def subscribe(self, callback: EventCallback) -> None:
        """Registers a new listener callback."""
        with self._lock:
            if callback not in self._subscribers:
                self._subscribers.append(callback)

    def unsubscribe(self, callback: EventCallback) -> None:
        """Removes a registered callback."""
        with self._lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

    def get_events(
        self,
        session_id: Optional[str] = None,
        event_type: Optional[WorkflowEventType] = None,
    ) -> List[WorkflowEvent]:
        """
        Retrieves matching events filtered by session_id and/or event_type.
        """
        with self._lock:
            events = list(self._events)

        if session_id:
            events = [e for e in events if e.session_id == session_id]
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events

    def clear(self) -> None:
        """Clears all stored events (primarily for testing)."""
        with self._lock:
            self._events.clear()


class ConsoleEventPublisher(BaseEventPublisher):
    """
    Publisher that prints formatted event summaries to console/stdout.
    Helpful for local debugging and CLI runs.
    """

    def __init__(self, fallback_publisher: Optional[BaseEventPublisher] = None) -> None:
        self._fallback = fallback_publisher
        self._subscribers: List[EventCallback] = []

    def publish(self, event: WorkflowEvent) -> None:
        timestamp_str = event.timestamp.strftime("%H:%M:%S")
        print(
            f"[{timestamp_str}] [Round {event.round_number}] "
            f"[{event.event_type.value.upper()}] session={event.session_id} data={event.data}"
        )
        if self._fallback:
            self._fallback.publish(event)
        for sub in self._subscribers:
            try:
                sub(event)
            except Exception as e:
                logger.error(f"Error notifying subscriber in console publisher: {e}")

    def subscribe(self, callback: EventCallback) -> None:
        self._subscribers.append(callback)


# Global default publisher instance
_default_publisher: BaseEventPublisher = InMemoryEventPublisher()


def get_event_publisher() -> BaseEventPublisher:
    """Returns the globally configured event publisher instance."""
    global _default_publisher
    return _default_publisher


def set_event_publisher(publisher: BaseEventPublisher) -> None:
    """Overrides the global event publisher instance."""
    global _default_publisher
    _default_publisher = publisher
