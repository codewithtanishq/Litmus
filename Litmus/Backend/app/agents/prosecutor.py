"""
Prosecutor Agent scaffolding for Swarm Debugger.

Role:
- Analyzes the reported bug description and original buggy code.
- Reviews active constraints accumulated from previous rounds to avoid repeating failed patterns.
- Formulates a diagnosis and generates Candidate Patch A.
"""

from typing import List, Optional
from app.config import OllamaSettings, get_settings
from app.schemas.session import DebugSession
from app.schemas.patch import CandidatePatch, AgentRole
from app.schemas.interfaces import ConstraintRecord


class ProsecutorAgent:
    """
    Prosecutor Agent interface.
    Responsible for initial bug accusation, hypothesis formulation, and proposing Fix A.
    """

    def __init__(self, ollama_settings: Optional[OllamaSettings] = None) -> None:
        self.settings = ollama_settings or get_settings().ollama

    def build_prompt(
        self,
        session: DebugSession,
        constraints: Optional[List[ConstraintRecord]] = None,
    ) -> str:
        """
        Builds the prompt for the Prosecutor role incorporating active constraints.
        (Full prompt template will be refined in the agent implementation phase).
        """
        constraints_summary = (
            "\n".join([f"- Round {c.round_number}: {c.failure_reason}" for c in (constraints or [])])
            if constraints
            else "None (Initial round)"
        )
        return (
            f"You are the PROSECUTOR in a debugging courtroom.\n"
            f"Bug Description: {session.bug_description}\n"
            f"Active Constraints from Prior Rejections:\n{constraints_summary}\n"
            f"Original Code:\n{session.original_code}\n"
            f"Propose Fix A with diagnosis and corrected code."
        )

    def analyze_and_propose(
        self,
        session: DebugSession,
        constraints: Optional[List[ConstraintRecord]] = None,
    ) -> CandidatePatch:
        """
        Scaffolding interface for generating Candidate Patch A.
        In the subsequent agent implementation step, this method will query Ollama.
        """
        raise NotImplementedError(
            "Live LLM inference for Prosecutor is scheduled for subsequent agent implementation. "
            "Backend foundation scaffolding is active."
        )
