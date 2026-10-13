"""
app/sandbox/limits.py
=====================
Centralized, validated sandbox resource limits.

Design decisions
----------------
* Limits are loaded ONCE from environment variables (or defaults) and
  are treated as a read-only system policy.
* Callers may supply a ``RunLimits`` with *lower* values than the
  system policy (useful for quick tests).  They may never exceed it.
* ``apply_caller_limits`` is the main public helper: it takes a
  caller-supplied ``RunLimits`` and returns the tightest (most
  restrictive) limits, so a misbehaving caller cannot loosen security.
* Docker image name is also managed here because it is part of the
  sandbox configuration, not the execution logic.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

from app.contracts import RunLimits

load_dotenv()


# ─────────────────────────────────────────────────────────────────────────────
# System-level policy (from environment / defaults)
# ─────────────────────────────────────────────────────────────────────────────


def _env_int(key: str, default: int) -> int:
    """Read an integer from the environment, falling back to *default*."""
    raw = os.environ.get(key, "")
    if raw.strip():
        try:
            return int(raw)
        except ValueError as exc:
            raise ValueError(f"Environment variable {key}={raw!r} must be an integer.") from exc
    return default


def _env_float(key: str, default: float) -> float:
    """Read a float from the environment, falling back to *default*."""
    raw = os.environ.get(key, "")
    if raw.strip():
        try:
            return float(raw)
        except ValueError as exc:
            raise ValueError(f"Environment variable {key}={raw!r} must be a float.") from exc
    return default


def _env_bool(key: str, default: bool) -> bool:  # noqa: FBT001
    """Read a boolean from the environment (true/1/yes → True)."""
    raw = os.environ.get(key, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes"}


def load_system_limits() -> RunLimits:
    """
    Build the system-level ``RunLimits`` from environment variables.

    This is the **maximum** that any caller may request.  It is safe to
    call multiple times; each call re-reads the environment so tests can
    override ``os.environ`` between calls.

    Returns
    -------
    RunLimits
        Validated system policy limits.

    Raises
    ------
    ValueError
        If any environment variable contains an invalid value.
    pydantic.ValidationError
        If constructed values violate ``RunLimits`` field constraints.
    """
    return RunLimits(
        timeout_seconds=_env_int("SANDBOX_TIMEOUT_SECONDS", 30),
        memory_mb=_env_int("SANDBOX_MEMORY_MB", 256),
        cpu_limit=_env_float("SANDBOX_CPU_LIMIT", 0.5),
        max_processes=_env_int("SANDBOX_MAX_PROCESSES", 32),
        max_output_bytes=_env_int("SANDBOX_MAX_OUTPUT_BYTES", 65_536),
        max_source_bytes=_env_int("SANDBOX_MAX_SOURCE_BYTES", 262_144),
        max_test_bytes=_env_int("SANDBOX_MAX_TEST_BYTES", 262_144),
        network_disabled=_env_bool("SANDBOX_NETWORK_DISABLED", True),
    )


def get_docker_image() -> str:
    """Return the Docker image name to use for candidate execution."""
    return os.environ.get("SANDBOX_DOCKER_IMAGE", "python:3.12-slim")


# ─────────────────────────────────────────────────────────────────────────────
# Limit merging (caller cannot loosen system limits)
# ─────────────────────────────────────────────────────────────────────────────


def apply_caller_limits(caller: RunLimits | None = None) -> RunLimits:
    """
    Return the *most restrictive* limits from the system policy and the
    caller's request.

    If *caller* is ``None`` the system limits are returned unchanged.

    The ``network_disabled`` flag is treated as a one-way ratchet: once
    the system policy disables networking it stays disabled regardless of
    what the caller requests.

    Parameters
    ----------
    caller:
        Optional caller-supplied limits.  Any field that is *stricter*
        than the system policy is honoured; any field that is *looser* is
        capped at the system policy.

    Returns
    -------
    RunLimits
        The effective limits the sandbox will enforce.
    """
    policy = load_system_limits()
    if caller is None:
        return policy

    return RunLimits(
        timeout_seconds=min(caller.timeout_seconds, policy.timeout_seconds),
        memory_mb=min(caller.memory_mb, policy.memory_mb),
        cpu_limit=min(caller.cpu_limit, policy.cpu_limit),
        max_processes=min(caller.max_processes, policy.max_processes),
        max_output_bytes=min(caller.max_output_bytes, policy.max_output_bytes),
        max_source_bytes=min(caller.max_source_bytes, policy.max_source_bytes),
        max_test_bytes=min(caller.max_test_bytes, policy.max_test_bytes),
        # network_disabled can only be True once the policy says True
        network_disabled=policy.network_disabled or caller.network_disabled,
    )
