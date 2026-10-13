"""
tests/unit/test_limits.py
--------------------------
Unit tests for app/sandbox/limits.py
"""

from __future__ import annotations

import os

import pytest
from pydantic import ValidationError

from app.contracts import RunLimits
from app.sandbox.limits import apply_caller_limits, load_system_limits


class TestLoadSystemLimits:
    """Tests for loading system limits from environment variables."""

    def test_defaults_are_valid(self):
        """Default limits should load without errors."""
        limits = load_system_limits()
        assert isinstance(limits, RunLimits)
        assert limits.timeout_seconds == 30
        assert limits.memory_mb == 256
        assert limits.cpu_limit == 0.5
        assert limits.max_processes == 32
        assert limits.max_output_bytes == 65_536
        assert limits.network_disabled is True

    def test_env_override_timeout(self, monkeypatch):
        """SANDBOX_TIMEOUT_SECONDS env var overrides the default."""
        monkeypatch.setenv("SANDBOX_TIMEOUT_SECONDS", "60")
        limits = load_system_limits()
        assert limits.timeout_seconds == 60

    def test_env_override_memory(self, monkeypatch):
        monkeypatch.setenv("SANDBOX_MEMORY_MB", "512")
        limits = load_system_limits()
        assert limits.memory_mb == 512

    def test_env_override_cpu(self, monkeypatch):
        monkeypatch.setenv("SANDBOX_CPU_LIMIT", "1.0")
        limits = load_system_limits()
        assert limits.cpu_limit == 1.0

    def test_env_override_network_disabled_false(self, monkeypatch):
        monkeypatch.setenv("SANDBOX_NETWORK_DISABLED", "false")
        limits = load_system_limits()
        assert limits.network_disabled is False

    def test_invalid_env_timeout_raises(self, monkeypatch):
        monkeypatch.setenv("SANDBOX_TIMEOUT_SECONDS", "not_a_number")
        with pytest.raises(ValueError, match="must be an integer"):
            load_system_limits()

    def test_invalid_env_cpu_raises(self, monkeypatch):
        monkeypatch.setenv("SANDBOX_CPU_LIMIT", "banana")
        with pytest.raises(ValueError, match="must be a float"):
            load_system_limits()


class TestRunLimitsValidation:
    """Tests for RunLimits Pydantic validation."""

    def test_valid_custom_limits(self):
        limits = RunLimits(timeout_seconds=10, memory_mb=64, cpu_limit=0.25)
        assert limits.timeout_seconds == 10

    def test_timeout_below_minimum_raises(self):
        with pytest.raises(ValidationError):
            RunLimits(timeout_seconds=0)

    def test_timeout_above_maximum_raises(self):
        with pytest.raises(ValidationError):
            RunLimits(timeout_seconds=9999)

    def test_memory_below_minimum_raises(self):
        with pytest.raises(ValidationError):
            RunLimits(memory_mb=1)

    def test_cpu_below_zero_raises(self):
        with pytest.raises(ValidationError):
            RunLimits(cpu_limit=0.0)

    def test_cpu_above_maximum_raises(self):
        with pytest.raises(ValidationError):
            RunLimits(cpu_limit=99.0)

    def test_negative_processes_raises(self):
        with pytest.raises(ValidationError):
            RunLimits(max_processes=0)

    def test_output_below_minimum_raises(self):
        with pytest.raises(ValidationError):
            RunLimits(max_output_bytes=0)


class TestApplyCallerLimits:
    """Tests for the caller-limit ratchet function."""

    def test_none_caller_returns_policy(self):
        """With no caller limits, system policy is returned unchanged."""
        result = apply_caller_limits(None)
        policy = load_system_limits()
        assert result.timeout_seconds == policy.timeout_seconds
        assert result.memory_mb == policy.memory_mb

    def test_caller_tighter_timeout_is_honoured(self, monkeypatch):
        """Caller with a tighter timeout gets that tighter value."""
        monkeypatch.setenv("SANDBOX_TIMEOUT_SECONDS", "30")
        caller = RunLimits(timeout_seconds=10)
        result = apply_caller_limits(caller)
        assert result.timeout_seconds == 10

    def test_caller_looser_timeout_is_capped(self, monkeypatch):
        """Caller cannot loosen a 10s policy to 300s."""
        monkeypatch.setenv("SANDBOX_TIMEOUT_SECONDS", "10")
        caller = RunLimits(timeout_seconds=300)
        result = apply_caller_limits(caller)
        assert result.timeout_seconds == 10

    def test_caller_looser_memory_is_capped(self, monkeypatch):
        monkeypatch.setenv("SANDBOX_MEMORY_MB", "64")
        caller = RunLimits(memory_mb=2048)
        result = apply_caller_limits(caller)
        assert result.memory_mb == 64

    def test_network_disabled_is_sticky(self, monkeypatch):
        """If policy disables networking, the caller cannot re-enable it."""
        monkeypatch.setenv("SANDBOX_NETWORK_DISABLED", "true")
        caller = RunLimits(network_disabled=False)
        result = apply_caller_limits(caller)
        assert result.network_disabled is True

    def test_caller_can_disable_networking_when_policy_allows(self, monkeypatch):
        """If policy allows networking, the caller can still disable it."""
        monkeypatch.setenv("SANDBOX_NETWORK_DISABLED", "false")
        caller = RunLimits(network_disabled=True)
        result = apply_caller_limits(caller)
        assert result.network_disabled is True

    def test_all_fields_capped(self, monkeypatch):
        """Every numeric field is capped at the policy value."""
        monkeypatch.setenv("SANDBOX_TIMEOUT_SECONDS", "5")
        monkeypatch.setenv("SANDBOX_MEMORY_MB", "32")
        monkeypatch.setenv("SANDBOX_CPU_LIMIT", "0.1")
        monkeypatch.setenv("SANDBOX_MAX_PROCESSES", "4")
        monkeypatch.setenv("SANDBOX_MAX_OUTPUT_BYTES", "1024")

        caller = RunLimits(
            timeout_seconds=300,
            memory_mb=2048,
            cpu_limit=2.0,
            max_processes=256,
            max_output_bytes=1_048_576,
        )
        result = apply_caller_limits(caller)
        assert result.timeout_seconds == 5
        assert result.memory_mb == 32
        assert result.cpu_limit == 0.1
        assert result.max_processes == 4
        assert result.max_output_bytes == 1024
