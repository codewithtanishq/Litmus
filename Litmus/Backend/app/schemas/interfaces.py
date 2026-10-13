"""
Shared interfaces and contracts defining module boundaries between Member 1 and Member 2.

Member 1 Ownership:
- Agents (Prosecutor, Defender, Judge)
- Orchestration (LangGraph workflow, state, routing)
- Event Publishing (Transparent Courtroom Visualizer feed)

Member 2 Ownership:
- sandbox/: Restricted code execution engine
- evaluation/: Deterministic test evaluator
- memory/: Constraint Ledger and SQLite persistence
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from uuid import uuid4
from pydantic import BaseModel, Field, ConfigDict

from app.schemas.patch import AgentRole, CandidatePatch
from app.schemas.test_result import TestResult, TestExecutionStatus


class SandboxExecutionRequest(BaseModel):
    """
    Contract for invoking Member 2's sandbox execution module.
    """
    model_config = ConfigDict(use_enum_values=True)

    session_id: str = Field(..., description="Active session ID.")
    round_number: int = Field(..., ge=1, description="Current debugging round.")
    patch: CandidatePatch = Field(..., description="Validated candidate patch to execute.")
    test_suite: str = Field(..., description="Deterministic test code to execute against the patch.")
    timeout_seconds: float = Field(default=30.0, gt=0.0, description="Max execution time before kill.")
    environment_vars: Dict[str, str] = Field(default_factory=dict, description="Safe sandboxed env variables.")


class SandboxExecutionEvidence(BaseModel):
    """
    Raw execution evidence returned by Member 2's sandbox.
    """
    model_config = ConfigDict(use_enum_values=True)

    patch_id: str = Field(..., description="ID of the candidate patch executed.")
    stdout: str = Field(default="", description="Captured standard output.")
    stderr: str = Field(default="", description="Captured standard error.")
    exit_code: int = Field(..., description="Process exit code.")
    is_timeout: bool = Field(default=False, description="Whether execution was terminated due to timeout.")
    execution_time_seconds: float = Field(default=0.0, ge=0.0, description="Elapsed execution duration.")
    sandbox_metadata: Dict[str, Any] = Field(default_factory=dict, description="Resource limits or sandbox stats.")


@runtime_checkable
class ISandboxRunner(Protocol):
    """
    Interface provided by Member 2's sandbox module.
    Executes a candidate patch in an isolated environment and yields execution evidence.
    """
    def execute_candidate(self, request: SandboxExecutionRequest) -> SandboxExecutionEvidence:
        """
        Executes the candidate code in a sandbox container/process.
        Must catch OS errors and return structured evidence rather than unhandled crashes.
        """
        ...


@runtime_checkable
class IEvaluator(Protocol):
    """
    Interface provided by Member 2's evaluation module.
    Evaluates sandbox execution evidence against deterministic criteria to produce a TestResult.
    """
    def evaluate(self, evidence: SandboxExecutionEvidence, test_suite: str) -> TestResult:
        """
        Parses test outputs, exit codes, and assertions to create an explicit TestResult.
        Guarantees that unrun or errored tests are never marked as PASSED.
        """
        ...


class ConstraintRecord(BaseModel):
    """
    Structured record of a failed candidate patch and its failure reasons,
    stored in Member 2's Constraint Ledger to prevent recurring mistakes in subsequent rounds.
    """
    model_config = ConfigDict(use_enum_values=True)

    constraint_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str = Field(..., description="Session where the constraint was generated.")
    round_number: int = Field(..., ge=1, description="Round in which the patch failed.")
    agent_role: AgentRole = Field(..., description="Role that proposed the failed patch.")
    patch_id: str = Field(..., description="ID of the failed candidate patch.")
    rejected_code: str = Field(..., description="Code that was proven invalid.")
    failure_reason: str = Field(..., description="Explanation of why the patch failed.")
    test_stderr: str = Field(default="", description="Relevant error or trace evidence.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@runtime_checkable
class IConstraintLedger(Protocol):
    """
    Interface provided by Member 2's memory module.
    Persists rejected hypotheses and retrieves active constraints for subsequent rounds.
    """
    def record_constraint(self, constraint: ConstraintRecord) -> None:
        """Persists a rejected candidate and its failure evidence into the ledger."""
        ...

    def get_active_constraints(self, session_id: str) -> List[ConstraintRecord]:
        """Retrieves all cumulative constraints for the active session to inject into prompts."""
        ...


class VerdictDecision(str, Enum):
    """Decisions available to the Judge."""
    ACCEPT_PROSECUTOR = "accept_prosecutor"
    ACCEPT_DEFENDER = "accept_defender"
    RETRY_ROUND = "retry_round"
    EXHAUSTED_FAILURE = "exhausted_failure"


class JudgeVerdict(BaseModel):
    """
    The verdict produced by the Judge explaining the outcome based on empirical test evidence.
    """
    model_config = ConfigDict(use_enum_values=True)

    session_id: str = Field(..., description="Active session ID.")
    round_number: int = Field(..., ge=1, description="Current round.")
    winning_patch_id: Optional[str] = Field(default=None, description="ID of the winning patch, if any.")
    decision: VerdictDecision = Field(..., description="High-level courtroom ruling.")
    explanation: str = Field(..., description="Detailed justification grounded in test evidence.")
    prosecutor_evaluation: str = Field(default="", description="Critique of Fix A.")
    defender_evaluation: str = Field(default="", description="Critique of Fix B.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
