"""
Configuration management for Swarm Debugger.

Loads settings from environment variables and optional .env files.
Keeps Ollama local model and endpoint dynamically configurable.
"""

import os
from functools import lru_cache
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load environment variables from .env if present
load_dotenv()


class OllamaSettings(BaseModel):
    """Configuration for local Ollama inference service."""
    base_url: str = Field(
        default="http://localhost:11434",
        description="Base URL where local Ollama server is running.",
    )
    model: str = Field(
        default="qwen2.5-coder:7b",
        description="Local Ollama model identifier (e.g. qwen2.5-coder:7b or qwen2.5-coder:latest).",
    )
    temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for deterministic code reasoning.",
    )
    timeout_seconds: float = Field(
        default=60.0,
        gt=0.0,
        description="Timeout in seconds for LLM generation queries.",
    )


class WorkflowSettings(BaseModel):
    """Configuration for the LangGraph debate and retry workflow."""
    max_rounds: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum debate and retry rounds before terminating session.",
    )
    sandbox_timeout_seconds: float = Field(
        default=30.0,
        gt=0.0,
        description="Maximum execution timeout for candidate sandbox runs.",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR).",
    )


class GeminiSettings(BaseModel):
    """Configuration for Google Gemini cloud inference service."""
    api_key: str = Field(
        default="",
        description="Google Gemini API key.",
    )
    model: str = Field(
        default="gemini-3.1-flash-lite",
        description="Gemini model identifier (e.g. gemini-3.1-flash-lite or gemini-2.5-flash).",
    )
    temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for deterministic code reasoning.",
    )
    timeout_seconds: float = Field(
        default=30.0,
        gt=0.0,
        description="Timeout in seconds for Gemini API queries.",
    )


class Settings(BaseModel):
    """Master application configuration."""
    gemini: GeminiSettings = Field(default_factory=GeminiSettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    workflow: WorkflowSettings = Field(default_factory=WorkflowSettings)

    @classmethod
    def load_from_env(cls) -> "Settings":
        """Builds configuration with environment variable overrides."""
        gemini_settings = GeminiSettings(
            api_key=os.getenv("GEMINI_API_KEY", os.getenv("API_KEY", "")),
            model=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"),
            temperature=float(os.getenv("GEMINI_TEMPERATURE", "0.2")),
            timeout_seconds=float(os.getenv("GEMINI_TIMEOUT_SECONDS", "30.0")),
        )
        ollama_settings = OllamaSettings(
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            model=os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b"),
            temperature=float(os.getenv("OLLAMA_TEMPERATURE", "0.2")),
            timeout_seconds=float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60.0")),
        )
        workflow_settings = WorkflowSettings(
            max_rounds=int(os.getenv("SWARM_MAX_ROUNDS", "3")),
            sandbox_timeout_seconds=float(os.getenv("SWARM_SANDBOX_TIMEOUT_SECONDS", "30.0")),
            log_level=os.getenv("SWARM_LOG_LEVEL", "INFO"),
        )
        return cls(gemini=gemini_settings, ollama=ollama_settings, workflow=workflow_settings)


@lru_cache()
def get_settings() -> Settings:
    """Returns cached application settings."""
    return Settings.load_from_env()
