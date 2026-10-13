"""
Agents package for Swarm Debugger courtroom roles.

- Prosecutor: Analyzes the reported bug, prior constraints, and proposes Fix A.
- Defender: Critiques the Prosecutor's diagnosis and independently proposes Fix B.
- Judge: Explains the result using empirical execution and deterministic test evidence.
"""

from app.agents.prosecutor import ProsecutorAgent
from app.agents.defender import DefenderAgent
from app.agents.judge import JudgeAgent
from app.agents.ollama_client import (
    OllamaClient,
    OllamaError,
    OllamaConnectionError,
    OllamaTimeoutError,
    OllamaModelNotFoundError,
    OllamaResponseError,
    MalformedOutputError,
)

__all__ = [
    "ProsecutorAgent",
    "DefenderAgent",
    "JudgeAgent",
    "OllamaClient",
    "OllamaError",
    "OllamaConnectionError",
    "OllamaTimeoutError",
    "OllamaModelNotFoundError",
    "OllamaResponseError",
    "MalformedOutputError",
]
