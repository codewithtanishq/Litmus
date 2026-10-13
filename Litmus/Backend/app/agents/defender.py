"""
Defender Agent scaffolding for Swarm Debugger.

Role:
- Critiques Prosecutor's diagnosis and proposed Fix A.
- Reviews active constraints accumulated from previous rounds.
- Independently formulates alternative hypothesis and generates Candidate Patch B.
"""

from typing import List, Optional
from app.config import OllamaSettings, get_settings
from app.schemas.session import DebugSession
from app.schemas.patch import CandidatePatch, AgentRole
from app.schemas.interfaces import ConstraintRecord


class DefenderAgent:
    """
    Defender Agent interface.
    Responsible for adversarial critique of Fix A and proposing alternative Fix B.
    """

    def __init__(self, ollama_settings: Optional[OllamaSettings] = None) -> None:
        self.settings = ollama_settings or get_settings().ollama

    def build_prompt(
        self,
        session: DebugSession,
        prosecutor_patch: Optional[CandidatePatch] = None,
        constraints: Optional[List[ConstraintRecord]] = None,
    ) -> str:
        """
        Builds the prompt for the Defender role incorporating Fix A and active constraints.
        (Full prompt template will be refined in the agent implementation phase).
        """
        constraints_summary = (
            "\n".join([f"- Round {c.round_number}: {c.failure_reason}" for c in (constraints or [])])
            if constraints
            else "None (Initial round)"
        )
        prosecutor_info = (
            f"Fix A Proposed Code:\n{prosecutor_patch.proposed_code}\nFix A Explanation:\n{prosecutor_patch.explanation}"
            if prosecutor_patch
            else "No Prosecutor patch provided."
        )
        return (
            f"You are the DEFENDER in a debugging courtroom.\n"
            f"Bug Description: {session.bug_description}\n"
            f"Active Constraints from Prior Rejections:\n{constraints_summary}\n"
            f"Prosecutor's Position:\n{prosecutor_info}\n"
            f"Critique Fix A and independently propose Fix B."
        )

    def critique_and_propose(
        self,
        session: DebugSession,
        prosecutor_patch: Optional[CandidatePatch] = None,
        constraints: Optional[List[ConstraintRecord]] = None,
    ) -> CandidatePatch:
        """
        Scaffolding interface for generating Candidate Patch B.
        In the subsequent agent implementation step, this method will query Ollama.
        """
        raise NotImplementedError(
            "Live LLM inference for Defender is scheduled for subsequent agent implementation. "
            "Backend foundation scaffolding is active."
        )
