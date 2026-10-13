"""
Unit tests for configuration loading and environment overrides.
"""

import os
from unittest import mock
from app.config import Settings, OllamaSettings, WorkflowSettings


class TestConfig:
    def test_default_settings(self):
        settings = Settings()
        assert settings.ollama.base_url == "http://localhost:11434"
        assert settings.ollama.model == "qwen2.5-coder:7b"
        assert settings.ollama.temperature == 0.2
        assert settings.workflow.max_rounds == 3
        assert settings.workflow.sandbox_timeout_seconds == 30.0

    def test_env_overrides(self):
        env_vars = {
            "OLLAMA_BASE_URL": "http://192.168.1.50:11434",
            "OLLAMA_MODEL": "qwen2.5-coder:14b",
            "OLLAMA_TEMPERATURE": "0.1",
            "OLLAMA_TIMEOUT_SECONDS": "120.0",
            "SWARM_MAX_ROUNDS": "5",
            "SWARM_SANDBOX_TIMEOUT_SECONDS": "45.0",
            "SWARM_LOG_LEVEL": "DEBUG",
        }
        with mock.patch.dict(os.environ, env_vars, clear=False):
            settings = Settings.load_from_env()
            assert settings.ollama.base_url == "http://192.168.1.50:11434"
            assert settings.ollama.model == "qwen2.5-coder:14b"
            assert settings.ollama.temperature == 0.1
            assert settings.ollama.timeout_seconds == 120.0
            assert settings.workflow.max_rounds == 5
            assert settings.workflow.sandbox_timeout_seconds == 45.0
            assert settings.workflow.log_level == "DEBUG"
