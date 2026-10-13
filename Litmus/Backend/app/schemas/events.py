"""
WorkflowEvent data contract for Swarm Debugger Courtroom Visualizer.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict
from uuid import uuid4
from pydantic import BaseModel, Field, ConfigDict


class WorkflowEventType(str, Enum):
    """
    Standard event types emitted during the courtroom debugging lifecycle.
    Consumed by the Transparent Courtroom Visualizer.
    """
    SESSION_STARTED = "session_started"
    AGENT_STARTED = "agent_started"
    PATCH_PROPOSED = "patch_proposed"
    EXECUTION_STARTED = "execution_started"
    TESTS_COMPLETED = "tests_completed"
    VERDICT_CREATED = "verdict_created"
    CONSTRAINT_RECORDED = "constraint_recorded"
    RETRY_STARTED = "retry_started"
    SESSION_COMPLETED = "session_completed"
    SESSION_FAILED = "session_failed"


class WorkflowEvent(BaseModel):
    """
    Event record published during actual workflow execution.

    Attributes:
        event_id: Unique identifier for the emitted event.
        session_id: The active debugging session ID.
        round_number: The round number when this event occurred.
        event_type: Standardized type of the workflow event.
        timestamp: UTC timestamp when the event occurred.
        data: Structured event payload (agent role, patch metadata, test summary, etc.).
    """

    model_config = ConfigDict(use_enum_values=True)

    event_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for this specific event.",
    )
    session_id: str = Field(
        ...,
        description="ID of the debugging session emitting the event.",
    )
    round_number: int = Field(
        default=1,
        ge=1,
        description="The round in which this event occurred.",
    )
    event_type: WorkflowEventType = Field(
        ...,
        description="Classification type of the workflow event.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the event occurrence.",
    )
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured contextual payload for the event.",
    )
