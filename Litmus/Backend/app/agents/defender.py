"""
Defender Agent for Swarm Debugger.

Role & Responsibilities:
- Independently inspects the bug and original source code.
- Critiques the Prosecutor's diagnosis and proposed Fix A using rigorous technical analysis.
- Identifies overlooked edge cases, regressions, or incorrect assumptions in Fix A.
- Proposes a distinct Fix B when a different valid solution is justified.
- If Fix A appears sound and no alternative solution is justified, provides an honest technical critique confirming the diagnosis without inventing an inferior patch.
- Emits real workflow events (`agent_started`, `patch_proposed`).
- Validates generated output strictly against the `CandidatePatch` contract.
- Never executes code inside the agent.
"""

import logging
from typing import List, Optional
from uuid import uuid4

from app.config import OllamaSettings, get_settings
from app.agents.ollama_client import OllamaClient, MalformedOutputError
from app.agents.prompt_utils import format_constraints_summary
from app.schemas.session import DebugSession
from app.schemas.patch import CandidatePatch, AgentRole
from app.schemas.interfaces import ConstraintRecord
from app.schemas.events import WorkflowEventType
from app.events.publisher import get_event_publisher, BaseEventPublisher

logger = logging.getLogger(__name__)

DEFENDER_SYSTEM_PROMPT = """You are the DEFENDER in the Swarm Debugger multi-agent debugging courtroom.
Your duty:
1. Conduct an independent code analysis of the reported bug and original code.
2. Critically scrutinize the PROSECUTOR's diagnosis and proposed Fix A.
3. Identify edge cases, hidden side effects, performance penalties, or flawed assumptions in Fix A.
4. If a better or distinct valid approach exists, formulate Fix B as your independent alternative patch.
5. If Fix A is already optimal and correct, explain why honestly without fabricating an inferior patch.
6. Review prior failure constraints: you MUST NOT repeat failed patches or invalid assumptions.
7. Return ONLY a single valid JSON object with the following schema:
{
    "critique": "<rigorous technical critique of Fix A's diagnosis and implementation>",
    "explanation": "<detailed rationale for Fix B or justification of your position>",
    "proposed_code": "<FULL revised source code for Fix B>",
    "diff": "<optional unified diff or null>"
}
Do NOT include markdown text outside the JSON object. Do NOT hallucinate tests."""


class DefenderAgent:
    """
    Defender Agent.
    Critiques Fix A and independently proposes Candidate Patch B.
    """

    def __init__(
        self,
        ollama_settings: Optional[OllamaSettings] = None,
        ollama_client: Optional[OllamaClient] = None,
        event_publisher: Optional[BaseEventPublisher] = None,
    ) -> None:
        self.settings = ollama_settings or get_settings().ollama
        self.client = ollama_client or OllamaClient(settings=self.settings)
        self.publisher = event_publisher or get_event_publisher()

    def build_prompt(
        self,
        session: DebugSession,
        prosecutor_patch: Optional[CandidatePatch] = None,
        constraints: Optional[List[ConstraintRecord]] = None,
    ) -> str:
        """
        Builds the prompt instructing the Defender to critique Fix A and propose Fix B.
        """
        constraints_block = format_constraints_summary(constraints)

        if prosecutor_patch:
            prosecutor_block = (
                f"Fix A Proposed by Prosecutor (Patch ID: {prosecutor_patch.patch_id}):\n"
                f"Explanation / Rationale:\n{prosecutor_patch.explanation}\n"
                f"Proposed Code:\n```\n{prosecutor_patch.proposed_code}\n```"
            )
        else:
            prosecutor_block = "Fix A: No Prosecutor patch was supplied for review."

        test_block = (
            f"Reproduction Test Suite:\n```\n{session.test_suite}\n```\n"
            if session.test_suite
            else "Reproduction Test Suite: Not explicitly provided.\n"
        )

        return (
            f"=== COURTROOM CASE DEFENSE (Round {session.current_round}) ===\n"
            f"Session ID: {session.session_id}\n\n"
            f"BUG DESCRIPTION:\n{session.bug_description}\n\n"
            f"ORIGINAL BUGGY SOURCE CODE:\n```\n{session.original_code}\n```\n\n"
            f"{test_block}\n"
            f"ACTIVE CONSTRAINTS FROM PRIOR REJECTED FIXES:\n{constraints_block}\n\n"
            f"PROSECUTOR'S PROPOSED FIX A FOR SCRUTINY:\n{prosecutor_block}\n\n"
            f"TASK FOR DEFENDER:\n"
            f"1. Scrutinize Prosecutor's Fix A: detail weaknesses, overlooked edge cases, or regressions.\n"
            f"2. Formulate Fix B and provide the COMPLETE revised code in 'proposed_code'.\n"
            f"3. Return your response as a strict JSON object with fields: 'critique', 'explanation', 'proposed_code', and optional 'diff'."
        )

    def critique_and_propose(
        self,
        session: DebugSession,
        prosecutor_patch: Optional[CandidatePatch] = None,
        constraints: Optional[List[ConstraintRecord]] = None,
        round_number: Optional[int] = None,
    ) -> CandidatePatch:
        """
        Runs the Defender role:
        1. Emits agent_started event.
        2. Queries Ollama with formatted prompt.
        3. Parses structured JSON response.
        4. Validates CandidatePatch schema.
        5. Emits patch_proposed event.

        Raises:
            OllamaError: If LLM call fails, times out, or cannot connect.
            MalformedOutputError: If model output cannot be converted into a valid CandidatePatch.
        """
        active_round = round_number if round_number is not None else session.current_round

        # Emit agent_started event
        self.publisher.emit(
            event_type=WorkflowEventType.AGENT_STARTED,
            session_id=session.session_id,
            round_number=active_round,
            data={
                "agent_role": AgentRole.DEFENDER.value,
                "model": self.settings.model,
            },
        )

        prompt = self.build_prompt(session, prosecutor_patch, constraints)

        # Call local Ollama client
        raw_response = self.client.generate(
            prompt=prompt,
            system_instruction=DEFENDER_SYSTEM_PROMPT,
            format_json=True,
        )

        parsed_data = self.client.parse_json_response(raw_response)

        # Extract and validate required fields
        proposed_code = parsed_data.get("proposed_code")
        if not proposed_code or not isinstance(proposed_code, str) or not proposed_code.strip():
            raise MalformedOutputError(
                "Defender model output missing or empty 'proposed_code' field."
            )

        explanation = parsed_data.get("explanation") or ""
        critique = parsed_data.get("critique") or ""
        if not explanation and not critique:
            raise MalformedOutputError(
                "Defender model output missing both 'critique' and 'explanation' fields."
            )

        full_explanation = (
            f"Critique of Fix A: {critique}\nFix B Rationale: {explanation}".strip()
            if critique and explanation
            else (explanation or critique)
        )

        diff = parsed_data.get("diff")
        if diff is not None and not isinstance(diff, str):
            diff = str(diff)

        # Instantiate and validate CandidatePatch
        patch = CandidatePatch(
            patch_id=str(uuid4()),
            agent_role=AgentRole.DEFENDER,
            proposed_code=proposed_code.strip(),
            explanation=full_explanation.strip(),
            round_number=active_round,
            diff=diff.strip() if diff else None,
        )

        # Emit patch_proposed event
        self.publisher.emit(
            event_type=WorkflowEventType.PATCH_PROPOSED,
            session_id=session.session_id,
            round_number=active_round,
            data={
                "agent_role": AgentRole.DEFENDER.value,
                "patch_id": patch.patch_id,
                "explanation": patch.explanation[:200],
            },
        )

        return patch
