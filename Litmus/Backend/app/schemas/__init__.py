"""
Schemas package for Swarm Debugger.

Contains shared data contracts for sessions, candidate patches, test results,
workflow events, and shared Member 1 / Member 2 interfaces.
"""

from app.schemas.session import DebugSession, SessionStatus
from app.schemas.patch import CandidatePatch, AgentRole
from app.schemas.test_result import TestResult, TestCaseResult, TestExecutionStatus
from app.schemas.events import WorkflowEvent, WorkflowEventType
from app.schemas.interfaces import (
    JudgeVerdict,
    ConstraintRecord,
    SandboxExecutionRequest,
    SandboxExecutionEvidence,
    ISandboxRunner,
    IEvaluator,
    IConstraintLedger,
)

__all__ = [
    "DebugSession",
    "SessionStatus",
    "CandidatePatch",
    "AgentRole",
    "TestResult",
    "TestCaseResult",
    "TestExecutionStatus",
    "WorkflowEvent",
    "WorkflowEventType",
    "JudgeVerdict",
    "ConstraintRecord",
    "SandboxExecutionRequest",
    "SandboxExecutionEvidence",
    "ISandboxRunner",
    "IEvaluator",
    "IConstraintLedger",
]
