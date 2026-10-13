"""
Unit tests for the framework-independent event publisher interface.
"""

from app.events.publisher import InMemoryEventPublisher
from app.schemas.events import WorkflowEvent, WorkflowEventType


class TestInMemoryEventPublisher:
    def test_publish_and_retrieve_events(self):
        publisher = InMemoryEventPublisher()
        event1 = WorkflowEvent(
            session_id="session-1",
            round_number=1,
            event_type=WorkflowEventType.SESSION_STARTED,
        )
        event2 = WorkflowEvent(
            session_id="session-1",
            round_number=1,
            event_type=WorkflowEventType.AGENT_STARTED,
            data={"agent_role": "prosecutor"},
        )
        event3 = WorkflowEvent(
            session_id="session-2",
            round_number=1,
            event_type=WorkflowEventType.SESSION_STARTED,
        )

        publisher.publish(event1)
        publisher.publish(event2)
        publisher.publish(event3)

        # Retrieve all
        all_events = publisher.get_events()
        assert len(all_events) == 3

        # Filter by session_id
        session_1_events = publisher.get_events(session_id="session-1")
        assert len(session_1_events) == 2

        # Filter by event_type
        session_started_events = publisher.get_events(event_type=WorkflowEventType.SESSION_STARTED)
        assert len(session_started_events) == 2

    def test_subscriber_callback_invoked(self):
        publisher = InMemoryEventPublisher()
        received_events = []

        def subscriber(event: WorkflowEvent):
            received_events.append(event)

        publisher.subscribe(subscriber)

        published_event = publisher.emit(
            event_type=WorkflowEventType.VERDICT_CREATED,
            session_id="session-10",
            round_number=1,
            data={"verdict": "passed"},
        )

        assert len(received_events) == 1
        assert received_events[0].event_id == published_event.event_id
        assert received_events[0].data["verdict"] == "passed"

    def test_subscriber_error_does_not_break_publisher(self):
        publisher = InMemoryEventPublisher()
        received = []

        def failing_subscriber(event: WorkflowEvent):
            raise RuntimeError("Boom!")

        def healthy_subscriber(event: WorkflowEvent):
            received.append(event)

        publisher.subscribe(failing_subscriber)
        publisher.subscribe(healthy_subscriber)

        # Should not raise exception
        publisher.emit(
            event_type=WorkflowEventType.RETRY_STARTED,
            session_id="session-99",
            round_number=2,
        )

        assert len(received) == 1
        assert received[0].round_number == 2
