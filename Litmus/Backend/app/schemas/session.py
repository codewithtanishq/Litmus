"""
DebugSession data contract for Swarm Debugger.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4
from pydantic import BaseModel, Field, ConfigDict


class SessionStatus(str, Enum):
    """Explicit lifecycle status for a debugging session."""
    PENDING = "pending"
    INVESTIGATING = "investigating"
    EVALUATING = "evaluating"
    JUDGING = "judging"
    RESOLVED = "resolved"
    MAX_ROUNDS_REACHED = "max_rounds_reached"
    FAILED = "failed"


class DebugSession(BaseModel):
    """
    Core data model representing a single multi-agent debugging session.

    Attributes:
        session_id: Unique identifier for the debugging session.
        original_code: The buggy source code submitted for analysis.
        bug_description: Human or automated description of the observed bug.
        test_suite: Reproduction test code or instructions to deterministically verify fixes.
        current_round: The active round number in the debate/retry cycle (1-indexed).
        status: Current lifecycle status of the session.
        created_at: UTC timestamp when the session was initiated.
        updated_at: UTC timestamp of the last status update.
        metadata: Arbitrary structured metadata (e.g. language, submitter info).
    """

    model_config = ConfigDict(use_enum_values=True)

    session_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the session.",
    )
    original_code: str = Field(
        ...,
        min_length=1,
        description="The original source code exhibiting the bug.",
    )
    bug_description: str = Field(
        ...,
        min_length=1,
        description="Natural language description of the bug or failure behavior.",
    )
    test_suite: str = Field(
        default="",
        description="Deterministic test script or suite verifying the bug reproduction.",
    )
    current_round: int = Field(
        default=1,
        ge=1,
        description="Current round index (1-indexed).",
    )
    status: SessionStatus = Field(
        default=SessionStatus.PENDING,
        description="Current lifecycle status of the debugging session.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the session was created.",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the session was last updated.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional session context and operational metadata.",
    )

    def mark_status(self, new_status: SessionStatus) -> None:
        """Update session status and refresh the updated_at timestamp."""
        self.status = new_status
        self.updated_at = datetime.now(timezone.utc)
