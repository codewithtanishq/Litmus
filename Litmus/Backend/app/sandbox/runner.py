"""
app/sandbox/runner.py
=====================
Execute one candidate patch inside a restricted Docker container and
collect raw execution evidence.

SAFETY GUARANTEES
-----------------
1. Docker is **required** for real sandbox isolation.  If Docker is not
   available or not properly configured this module raises
   ``SandboxUnavailableError`` rather than silently falling back to
   unrestricted host execution.
2. Candidate source code is written to a fresh temporary directory and
   never executed via shell string interpolation.  All subprocess calls
   use argument lists.
3. The Docker socket is never mounted into candidate containers.
4. Networking is disabled by default (``--network none``).
5. The container runs as a non-root user (``--user nobody`` via the
   image's ``nobody`` uid 65534).
6. Memory and PID limits are enforced at the container level.
7. stdout+stderr are captured and truncated to ``max_output_bytes``.
8. Trusted tests are mounted read-only so candidate code cannot modify
   them.
9. Temporary directories and containers are always cleaned up, even on
   failure.

RUNNING WITHOUT DOCKER (tests only)
------------------------------------
Set ``SWARM_ALLOW_HOST_EXECUTION=1`` in the environment to enable the
host-process runner.  This mode is **unsafe** and intended **only** for
unit tests on CI systems without Docker.  It is clearly labelled in the
returned ``ExecutionEvidence``.  Never use it in production.

PUBLIC INTERFACE
----------------
``run_candidate(source_code, trusted_tests, limits, candidate_id)``
    → ``ExecutionEvidence``

Raises
------
SandboxUnavailableError
    Docker is absent and ``SWARM_ALLOW_HOST_EXECUTION`` is not set.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Final

from app.contracts import ExecutionEvidence, ExecutionStatus, RunLimits
from app.sandbox.limits import apply_caller_limits, get_docker_image

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

_CANDIDATE_FILENAME: Final[str] = "solution.py"
_TESTS_FILENAME: Final[str] = "test_solution.py"
_JUNIT_FILENAME: Final[str] = "junit_report.xml"
_EXCERPT_BYTES: Final[int] = 4096  # per stream excerpt stored in evidence


# ─────────────────────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────────────────────


class SandboxUnavailableError(RuntimeError):
    """
    Raised when Docker is not available and unrestricted host execution
    has not been explicitly allowed via ``SWARM_ALLOW_HOST_EXECUTION=1``.

    This is a hard stop — callers should surface this as an
    ``infrastructure_error`` result rather than attempting an unsafe
    fallback.
    """


# ─────────────────────────────────────────────────────────────────────────────
# Docker availability probe (cached for 60 seconds)
# ─────────────────────────────────────────────────────────────────────────────

_DOCKER_AVAILABLE_CACHE: tuple[float, bool] | None = None


def _docker_available() -> bool:
    """Return True if the Docker CLI is reachable and the daemon responds (cached for 60s)."""
    global _DOCKER_AVAILABLE_CACHE
    now = time.monotonic()
    if _DOCKER_AVAILABLE_CACHE is not None:
        cached_time, cached_val = _DOCKER_AVAILABLE_CACHE
        if now - cached_time < 60.0:
            return cached_val
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        val = result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        val = False
    _DOCKER_AVAILABLE_CACHE = (now, val)
    return val


def _allow_host_execution() -> bool:
    """True when the environment explicitly opts in to unsafe host execution."""
    return os.environ.get("SWARM_ALLOW_HOST_EXECUTION", "").strip() in {"1", "true", "yes"}


# ─────────────────────────────────────────────────────────────────────────────
# Test normalization & Workspace helpers
# ─────────────────────────────────────────────────────────────────────────────


def prepare_test_source(test_src: str) -> str:
    """
    Normalizes test source code for sandbox execution:
    1. If there is no def test_ or class Test, wraps the statements in def test_reproduction(): (indented).
    2. If the source has no from solution import or import solution line, prepends from solution import *  # auto-injected.
    3. Keeps user's own imports unchanged.
    """
    cleaned = (test_src or "").strip()
    if not cleaned:
        return "from solution import *  # auto-injected\n\ndef test_reproduction():\n    pass\n"

    lines = test_src.splitlines()
    has_import = any(
        re.match(r"^\s*(from\s+solution\s+import|import\s+solution\b)", line)
        for line in lines
    )
    has_test_def = any(
        re.match(r"^\s*(def\s+test_|class\s+Test)", line)
        for line in lines
    )

    if not has_test_def:
        indented = "\n".join("    " + line if line.strip() else "" for line in lines)
        body = f"def test_reproduction():\n{indented}\n"
    else:
        body = test_src

    if not has_import:
        body = f"from solution import *  # auto-injected\n{body}"

    return body


def _write_workspace(
    workspace: Path,
    source_code: str,
    trusted_tests: str,
    limits: RunLimits,
) -> None:
    """
    Populate *workspace* with the candidate and normalized trusted test files.

    Raises
    ------
    ValueError
        If source or test content exceeds configured size limits.
    """
    prepared_tests = prepare_test_source(trusted_tests)
    source_bytes = source_code.encode("utf-8")
    test_bytes = prepared_tests.encode("utf-8")

    if len(source_bytes) > limits.max_source_bytes:
        raise ValueError(
            f"Source code ({len(source_bytes)} bytes) exceeds "
            f"max_source_bytes ({limits.max_source_bytes})."
        )
    if len(test_bytes) > limits.max_test_bytes:
        raise ValueError(
            f"Test suite ({len(test_bytes)} bytes) exceeds "
            f"max_test_bytes ({limits.max_test_bytes})."
        )

    (workspace / _CANDIDATE_FILENAME).write_bytes(source_bytes)
    (workspace / _TESTS_FILENAME).write_bytes(test_bytes)

    try:
        workspace.chmod(0o777)
        (workspace / _CANDIDATE_FILENAME).chmod(0o644)
        (workspace / _TESTS_FILENAME).chmod(0o644)
    except Exception:
        pass


def _truncate(data: bytes, max_bytes: int) -> str:
    """Decode bytes to UTF-8 (replacing errors) and truncate."""
    text = data.decode("utf-8", errors="replace")
    if len(data) > max_bytes:
        text = text[:max_bytes] + f"\n[... truncated at {max_bytes} bytes ...]"
    return text


# ─────────────────────────────────────────────────────────────────────────────
# Docker runner
# ─────────────────────────────────────────────────────────────────────────────


def _run_in_docker(
    workspace: Path,
    limits: RunLimits,
    candidate_id: str,
) -> ExecutionEvidence:
    """
    Execute the candidate inside a Docker container.

    The container:
    - mounts the workspace read-write for the candidate file and report,
    - mounts the trusted test file read-only (separate bind),
    - has no network access,
    - runs as ``nobody`` (uid 65534),
    - is removed automatically (``--rm``),
    - has CPU, memory, and PID limits applied.

    The pytest JUnit XML report is written to ``workspace/junit_report.xml``
    so the evaluator can parse it after the container exits.
    """
    image = get_docker_image()
    container_workdir = "/sandbox"

    # Bind mounts: workspace rw, trusted tests ro (prevents candidate overwrite)
    candidate_mount = f"{workspace}:{container_workdir}:rw"
    # Separate read-only bind for the test file (overrides the rw mount for it)
    test_src = workspace / _TESTS_FILENAME
    test_dest = f"{container_workdir}/{_TESTS_FILENAME}"

    # pytest command — uses argument list, no shell interpolation
    pytest_cmd = [
        "python", "-m", "pytest",
        f"{container_workdir}/{_TESTS_FILENAME}",
        "--tb=short",
        f"--junitxml={container_workdir}/{_JUNIT_FILENAME}",
        "-q",
        "--no-header",
        "-p", "no:cacheprovider",
    ]

    memory_limit = f"{limits.memory_mb}m"
    cpu_period = 100_000
    cpu_quota = int(limits.cpu_limit * cpu_period)

    docker_cmd = [
        "docker", "run",
        "--rm",
        "--name", f"swarm-{candidate_id[:12]}",
        "--network", "none",
        "--user", "65534:65534",
        f"--memory={memory_limit}",
        f"--memory-swap={memory_limit}",
        f"--cpu-period={cpu_period}",
        f"--cpu-quota={cpu_quota}",
        f"--pids-limit={limits.max_processes}",
        "--read-only",
        "--tmpfs", "/tmp:rw,size=64m",
        "-e", "HOME=/tmp",
        "-e", "PYTHONDONTWRITEBYTECODE=1",
        "-v", candidate_mount,
        "--mount", f"type=bind,source={test_src},target={test_dest},readonly",
        "--workdir", container_workdir,
        image,
        *pytest_cmd,
    ]

    start = time.monotonic()
    container_id: str | None = None

    try:
        proc = subprocess.run(
            docker_cmd,
            capture_output=True,
            timeout=limits.timeout_seconds + 5,  # extra for Docker startup
        )
        duration_ms = (time.monotonic() - start) * 1000

        stdout = _truncate(proc.stdout, limits.max_output_bytes // 2)
        stderr = _truncate(proc.stderr, limits.max_output_bytes // 2)

        # Read JUnit XML if present
        junit_path = workspace / _JUNIT_FILENAME
        junit_content: str | None = None
        if junit_path.exists():
            try:
                junit_content = junit_path.read_text(encoding="utf-8")
            except OSError:
                pass

        if proc.returncode == 0:
            status = ExecutionStatus.PASSED
            error_detail = ""
        elif proc.returncode in (125, 126, 127):
            status = ExecutionStatus.INFRASTRUCTURE_ERROR
            error_detail = f"Docker infrastructure error (exit code {proc.returncode}): {stderr}"
        elif proc.returncode == 137:
            status = ExecutionStatus.FAILED
            error_detail = "Execution killed (exit code 137), likely exceeded memory limit."
        else:
            status = ExecutionStatus.FAILED
            error_detail = ""

        return ExecutionEvidence(
            candidate_id=candidate_id,
            status=status,
            exit_code=proc.returncode,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
            junit_xml_content=junit_content,
            error_detail=error_detail,
        )

    except subprocess.TimeoutExpired:
        duration_ms = (time.monotonic() - start) * 1000
        # Best-effort container kill
        _kill_container(f"swarm-{candidate_id[:12]}")
        return ExecutionEvidence(
            candidate_id=candidate_id,
            status=ExecutionStatus.TIMED_OUT,
            duration_ms=duration_ms,
            error_detail=f"Execution timed out after {limits.timeout_seconds}s.",
        )

    except Exception as exc:  # noqa: BLE001
        duration_ms = (time.monotonic() - start) * 1000
        return ExecutionEvidence(
            candidate_id=candidate_id,
            status=ExecutionStatus.INFRASTRUCTURE_ERROR,
            duration_ms=duration_ms,
            error_detail=f"Docker execution error: {exc}",
        )


def _kill_container(name: str) -> None:
    """Best-effort container kill; errors are silently ignored."""
    try:
        subprocess.run(["docker", "kill", name], capture_output=True, timeout=10)
    except Exception:  # noqa: BLE001
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Host runner (UNSAFE — tests only)
# ─────────────────────────────────────────────────────────────────────────────


def _run_on_host(
    workspace: Path,
    limits: RunLimits,
    candidate_id: str,
) -> ExecutionEvidence:
    """
    Execute the candidate directly on the host Python process.

    ⚠️  WARNING: This provides NO isolation.  Use only for unit tests.
    ⚠️  This function is only reachable when ``SWARM_ALLOW_HOST_EXECUTION=1``.
    """
    pytest_cmd = [
        sys.executable, "-m", "pytest",
        str(workspace / _TESTS_FILENAME),
        "--tb=short",
        f"--junitxml={workspace / _JUNIT_FILENAME}",
        "-q",
        "--no-header",
        "-p", "no:cacheprovider",
    ]

    start = time.monotonic()
    try:
        proc = subprocess.run(
            pytest_cmd,
            capture_output=True,
            timeout=limits.timeout_seconds,
            cwd=str(workspace),
        )
        duration_ms = (time.monotonic() - start) * 1000

        stdout = _truncate(proc.stdout, limits.max_output_bytes // 2)
        stderr = _truncate(proc.stderr, limits.max_output_bytes // 2)

        junit_path = workspace / _JUNIT_FILENAME
        junit_content: str | None = None
        if junit_path.exists():
            try:
                junit_content = junit_path.read_text(encoding="utf-8")
            except OSError:
                pass

        status = ExecutionStatus.PASSED if proc.returncode == 0 else ExecutionStatus.FAILED

        return ExecutionEvidence(
            candidate_id=candidate_id,
            status=status,
            exit_code=proc.returncode,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
            junit_xml_content=junit_content,
            error_detail="[HOST EXECUTION — NO SANDBOX ISOLATION]",
        )

    except subprocess.TimeoutExpired:
        duration_ms = (time.monotonic() - start) * 1000
        return ExecutionEvidence(
            candidate_id=candidate_id,
            status=ExecutionStatus.TIMED_OUT,
            duration_ms=duration_ms,
            error_detail=f"Host execution timed out after {limits.timeout_seconds}s.",
        )

    except Exception as exc:  # noqa: BLE001
        duration_ms = (time.monotonic() - start) * 1000
        return ExecutionEvidence(
            candidate_id=candidate_id,
            status=ExecutionStatus.INFRASTRUCTURE_ERROR,
            duration_ms=duration_ms,
            error_detail=f"Host execution error: {exc}",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def run_candidate(
    source_code: str,
    trusted_tests: str,
    candidate_id: str,
    limits: RunLimits | None = None,
) -> ExecutionEvidence:
    """
    Execute *source_code* against *trusted_tests* in a sandboxed environment.

    Steps
    -----
    1. Apply caller limits (caller cannot exceed system policy).
    2. Validate input sizes.
    3. Write source and tests to a fresh temporary workspace.
    4. Run inside Docker (preferred) or raise ``SandboxUnavailableError``.
       If ``SWARM_ALLOW_HOST_EXECUTION=1`` is set, fall back to the unsafe
       host runner (unit tests only).
    5. Clean up the workspace unconditionally.
    6. Return ``ExecutionEvidence``.

    Parameters
    ----------
    source_code:
        Full replacement source code of the candidate (UTF-8 string).
    trusted_tests:
        Full source of the trusted pytest test suite (UTF-8 string).
    candidate_id:
        Unique identifier for this candidate (used in container name).
    limits:
        Optional caller-supplied limits.  They are merged with the
        system policy — callers can only *tighten*, not loosen limits.

    Returns
    -------
    ExecutionEvidence
        Raw execution evidence.  Pass to ``evaluate_candidate`` to
        obtain a structured ``TestResult``.

    Raises
    ------
    SandboxUnavailableError
        Docker is absent and unsafe host execution is not enabled.
    ValueError
        Source or test content exceeds size limits.
    """
    effective_limits = apply_caller_limits(limits)
    workspace = Path(tempfile.mkdtemp(prefix="swarm_"))

    try:
        # May raise ValueError for size violations
        _write_workspace(workspace, source_code, trusted_tests, effective_limits)

        if _docker_available():
            return _run_in_docker(workspace, effective_limits, candidate_id)
        elif _allow_host_execution():
            return _run_on_host(workspace, effective_limits, candidate_id)
        else:
            raise SandboxUnavailableError(
                "Docker is not available and SWARM_ALLOW_HOST_EXECUTION is not set. "
                "Install Docker or set SWARM_ALLOW_HOST_EXECUTION=1 for testing only.\n"
                "See .env.example for configuration details."
            )

    finally:
        # Always clean up the workspace, even on error
        shutil.rmtree(workspace, ignore_errors=True)


def compute_source_hash(source_code: str) -> str:
    """Return a stable SHA-256 hex digest of *source_code* (UTF-8)."""
    return hashlib.sha256(source_code.encode()).hexdigest()
