"""
app/contracts.py
================
Shared, stable data contracts for the Swarm Debugger system.

Member 1 (agents / orchestrator) and Member 2 (sandbox / evaluation /
memory) BOTH import from this single module.  Keep types simple,
typed, and backwards-compatible.

Design decisions
----------------
* Full-source replacement is used for the MVP (not unified diffs).
* All IDs are plain strings (UUIDs chosen at creation time by the
  caller so they can be embedded in log messages before persistence).
* Pydantic v2 is used throughout; import from ``pydantic`` directly.
* Timestamps are UTC ISO-8601 strings stored/returned as ``datetime``
  objects; Pydantic coerces both.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ─────────────────────────────────────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────────────────────────────────────


class ExecutionStatus(str, Enum):
    """Terminal status of a sandboxed execution run."""

    PASSED = "passed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    INFRASTRUCTURE_ERROR = "infrastructure_error"


class SessionStatus(str, Enum):
    """Lifecycle status of a debugging session."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ConstraintStatus(str, Enum):
    """Lifecycle status of a constraint record."""

    ACTIVE = "active"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


# ─────────────────────────────────────────────────────────────────────────────
# Session
# ─────────────────────────────────────────────────────────────────────────────


class DebugSession(BaseModel):
    """A single debugging session submitted by the user."""

    session_id: str = Field(..., description="Unique session identifier (UUID).")
    language: str = Field(default="python", description="Programming language of the source.")
    bug_description: str = Field(..., description="Human-readable description of the bug.")
    original_source: str = Field(..., description="Full source code of the buggy program.")
    trusted_tests: str = Field(..., description="Full source code of the trusted test suite.")
    max_rounds: int = Field(default=3, ge=1, le=20, description="Maximum repair rounds allowed.")
    status: SessionStatus = Field(default=SessionStatus.PENDING)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ─────────────────────────────────────────────────────────────────────────────
# Candidate Patch
# ─────────────────────────────────────────────────────────────────────────────


class CandidatePatch(BaseModel):
    """
    A proposed fix produced by an AI agent.

    Member 1 creates this; Member 2 persists and executes it.
    """

    candidate_id: str = Field(..., description="Unique candidate identifier (UUID).")
    session_id: str = Field(..., description="Parent session identifier.")
    agent: str = Field(..., description="Name/identifier of the agent that produced this fix.")
    round_number: int = Field(..., ge=1, description="Repair round this candidate belongs to.")
    source_code: str = Field(..., description="Full replacement source code (MVP: not a diff).")
    explanation: str = Field(default="", description="Agent's natural-language explanation.")
    base_version: str | None = Field(
        default=None,
        description="Hash or version label of the source this patch was derived from.",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ─────────────────────────────────────────────────────────────────────────────
# Run Limits
# ─────────────────────────────────────────────────────────────────────────────


class RunLimits(BaseModel):
    """
    Security and resource limits applied to every sandbox execution.

    **These defaults are the MAXIMUM values accepted from callers.**
    The sandbox enforces them; callers cannot weaken them beyond these
    values.  Only the system administrator (via environment variables)
    may raise limits.
    """

    timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Wall-clock seconds before the execution is killed.",
    )
    memory_mb: int = Field(
        default=256,
        ge=32,
        le=2048,
        description="Maximum RAM (MiB) available to the candidate.",
    )
    cpu_limit: float = Field(
        default=0.5,
        gt=0.0,
        le=2.0,
        description="CPU share fraction (e.g. 0.5 = half a core).",
    )
    max_processes: int = Field(
        default=32,
        ge=1,
        le=256,
        description="Maximum number of OS processes inside the sandbox.",
    )
    max_output_bytes: int = Field(
        default=65_536,
        ge=1024,
        le=1_048_576,
        description="Maximum combined stdout+stderr bytes captured.",
    )
    max_source_bytes: int = Field(
        default=262_144,
        ge=1,
        le=2_097_152,
        description="Maximum source code size accepted.",
    )
    max_test_bytes: int = Field(
        default=262_144,
        ge=1,
        le=2_097_152,
        description="Maximum test suite size accepted.",
    )
    network_disabled: bool = Field(
        default=True,
        description="When True, the sandbox has no network access.",
    )

    @field_validator("timeout_seconds", "memory_mb", "cpu_limit", mode="before")
    @classmethod
    def _positive(cls, v: Any) -> Any:  # noqa: ANN401
        """Extra guard; Pydantic `ge`/`gt` constraints cover most cases."""
        if isinstance(v, (int, float)) and v <= 0:
            raise ValueError("Limit must be positive.")
        return v


# ─────────────────────────────────────────────────────────────────────────────
# Per-test result (embedded in TestResult)
# ─────────────────────────────────────────────────────────────────────────────


class PerTestResult(BaseModel):
    """Result for a single test case within the trusted suite."""

    test_name: str
    status: str  # "passed" | "failed" | "error" | "skipped"
    message: str = ""  # truncated failure message / traceback head


# ─────────────────────────────────────────────────────────────────────────────
# Execution evidence (runner → evaluator)
# ─────────────────────────────────────────────────────────────────────────────


class ExecutionEvidence(BaseModel):
    """
    Raw evidence collected by the sandbox runner.

    This is an INTERNAL transfer object between runner and evaluator.
    It is NOT stored directly; the evaluator transforms it into a
    ``TestResult``.
    """

    candidate_id: str
    status: ExecutionStatus
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_ms: float = 0.0
    # Path (host-side) to the JUnit XML report, if produced.
    junit_xml_path: str | None = None
    # Raw JUnit XML content (used when path is not accessible post-run).
    junit_xml_content: str | None = None
    error_detail: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Test Result (evaluator output / persisted)
# ─────────────────────────────────────────────────────────────────────────────


class TestResult(BaseModel):
    """
    Structured, deterministic evaluation of one candidate.

    Created by the evaluator; persisted by the repository.
    Member 1 uses ``status`` and ``failure_signature`` to decide
    whether to record a constraint and plan the next round.
    """

    result_id: str = Field(..., description="Unique result identifier (UUID).")
    candidate_id: str = Field(..., description="Candidate this result belongs to.")
    session_id: str = Field(..., description="Session this result belongs to.")
    status: ExecutionStatus = Field(..., description="Overall terminal status.")
    exit_code: int | None = Field(default=None, description="Process exit code, if available.")
    stdout_excerpt: str = Field(default="", description="Truncated stdout (≤ 4096 bytes).")
    stderr_excerpt: str = Field(default="", description="Truncated stderr (≤ 4096 bytes).")
    per_test_results: list[PerTestResult] = Field(default_factory=list)
    duration_ms: float = Field(default=0.0, description="Wall-clock execution time in ms.")
    failure_signature: str | None = Field(
        default=None,
        description="Stable hash or label identifying this failure pattern.",
    )
    sandbox_id: str | None = Field(
        default=None,
        description="Docker container ID or other execution environment label.",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ─────────────────────────────────────────────────────────────────────────────
# Constraint
# ─────────────────────────────────────────────────────────────────────────────


class Constraint(BaseModel):
    """
    An evidence-backed constraint derived from a real test failure.

    Member 1 injects ``constraint_text`` into the next agent prompt.
    Every constraint links back to the candidate and test result that
    produced it so it can always be audited.
    """

    constraint_id: str = Field(..., description="Unique constraint identifier (UUID).")
    session_id: str = Field(..., description="Session this constraint belongs to.")
    round_number: int = Field(..., ge=1, description="Round in which this constraint was created.")
    source_candidate_id: str = Field(..., description="Candidate that triggered this constraint.")
    evidence_result_id: str = Field(..., description="TestResult that provides the evidence.")
    failure_signature: str = Field(..., description="Stable signature of the failure pattern.")
    constraint_text: str = Field(..., description="Concise, actionable constraint for the agent.")
    status: ConstraintStatus = Field(default=ConstraintStatus.ACTIVE)
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence level (1.0 = deterministic from test evidence).",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
