"""
Agents package for Swarm Debugger courtroom roles.

- Prosecutor: Analyzes the reported bug, prior constraints, and proposes Fix A.
- Defender: Critiques the Prosecutor's diagnosis and independently proposes Fix B.
- Judge: Explains the result using empirical execution and deterministic test evidence.
"""

from app.agents.prosecutor import ProsecutorAgent
from app.agents.defender import DefenderAgent
from app.agents.judge import JudgeAgent

__all__ = [
    "ProsecutorAgent",
    "DefenderAgent",
    "JudgeAgent",
]
