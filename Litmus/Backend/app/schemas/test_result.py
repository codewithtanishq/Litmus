"""
TestResult data contract for Swarm Debugger.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict, model_validator


class TestExecutionStatus(str, Enum):
    """
    Explicit status values for test runs.
    Distinguishes passes, assertions/logic failures, timeouts, and sandbox/infra issues.
    """
    __test__ = False

    PASSED = "passed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    INFRASTRUCTURE_ERROR = "infrastructure_error"
    NOT_RUN = "not_run"


class TestCaseResult(BaseModel):
    """
    Detailed outcome of an individual test case within a suite.
    """
    __test__ = False
    model_config = ConfigDict(use_enum_values=True)

    name: str = Field(..., description="Name or identifier of the test case.")
    status: TestExecutionStatus = Field(..., description="Outcome of this specific test case.")
    error_message: Optional[str] = Field(default=None, description="Failure trace or exception message.")
    duration_seconds: Optional[float] = Field(default=None, ge=0.0, description="Runtime duration in seconds.")


class TestResult(BaseModel):
    """
    Structured outcome of running a candidate patch against the deterministic test suite.

    Attributes:
        patch_id: Identifier of the evaluated candidate patch.
        status: Explicit execution status (PASSED, FAILED, TIMEOUT, INFRASTRUCTURE_ERROR, NOT_RUN).
        passed: Boolean indicator of whether all tests passed cleanly.
        test_cases: Detailed individual test outcomes.
        stdout: Standard output emitted during test execution.
        stderr: Standard error emitted during test execution.
        exit_code: Process exit code (0 usually indicates success).
        is_timeout: True if execution timed out before completion.
        timeout_seconds: Configured timeout limit in seconds if applicable.
        error_details: Traceback or error details if an infra or runner failure occurred.
        executed_at: UTC timestamp of test execution.
        duration_seconds: Total wall-clock execution time in seconds.
    """
    __test__ = False
    model_config = ConfigDict(use_enum_values=True)

    patch_id: str = Field(
        ...,
        description="ID of the candidate patch that was evaluated.",
    )
    status: TestExecutionStatus = Field(
        default=TestExecutionStatus.NOT_RUN,
        description="Explicit execution status.",
    )
    passed: bool = Field(
        default=False,
        description="Whether tests passed completely without errors or failures.",
    )
    test_cases: List[TestCaseResult] = Field(
        default_factory=list,
        description="Outcomes of individual test cases.",
    )
    stdout: str = Field(
        default="",
        description="Captured standard output.",
    )
    stderr: str = Field(
        default="",
        description="Captured standard error.",
    )
    exit_code: Optional[int] = Field(
        default=None,
        description="Process exit code from the sandbox execution.",
    )
    is_timeout: bool = Field(
        default=False,
        description="Whether the sandbox execution reached the timeout limit.",
    )
    timeout_seconds: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Maximum execution seconds permitted.",
    )
    error_details: Optional[str] = Field(
        default=None,
        description="Additional technical failure information or infrastructure stack trace.",
    )
    executed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when tests completed execution.",
    )
    duration_seconds: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Execution duration in seconds.",
    )

    @model_validator(mode="after")
    def validate_status_and_passed_consistency(self) -> "TestResult":
        """
        Guarantees rigorous consistency:
        - Never treat a missing, timed-out, or failed test run as successful.
        - `passed` can ONLY be True if status is strictly `PASSED` and exit_code is 0 (or None when not applicable).
        - If `is_timeout` is True, `status` must be `TIMEOUT`.
        """
        # If timeout occurred, status MUST reflect TIMEOUT
        if self.is_timeout and self.status != TestExecutionStatus.TIMEOUT:
            self.status = TestExecutionStatus.TIMEOUT

        # Never allow passed=True if status is not PASSED
        if self.status != TestExecutionStatus.PASSED:
            if self.passed:
                raise ValueError(
                    f"TestResult cannot have passed=True when status is '{self.status}'. "
                    f"Missing or non-passing test results must not be marked successful."
                )

        # If exit_code indicates failure (non-zero), status cannot be PASSED
        if self.exit_code is not None and self.exit_code != 0 and self.status == TestExecutionStatus.PASSED:
            raise ValueError(
                f"TestResult cannot have status='passed' when exit_code is non-zero ({self.exit_code})."
            )

        return self
