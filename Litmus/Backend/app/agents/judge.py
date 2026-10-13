"""
Judge Agent scaffolding for Swarm Debugger.

Role:
- Evaluates the claims of Prosecutor (Fix A) and Defender (Fix B) against empirical test results.
- Synthesizes courtroom ruling and verdict explanation grounded strictly in test evidence.
- Explains why a patch succeeded or why both failed.
"""

from typing import Dict, Optional
from app.config import OllamaSettings, get_settings
from app.schemas.session import DebugSession
from app.schemas.patch import CandidatePatch
from app.schemas.test_result import TestResult
from app.schemas.interfaces import JudgeVerdict, VerdictDecision


class JudgeAgent:
    """
    Judge Agent interface.
    Synthesizes empirical evidence and issues a justified verdict.
    """

    def __init__(self, ollama_settings: Optional[OllamaSettings] = None) -> None:
        self.settings = ollama_settings or get_settings().ollama

    def build_prompt(
        self,
        session: DebugSession,
        prosecutor_patch: Optional[CandidatePatch],
        defender_patch: Optional[CandidatePatch],
        test_results: Dict[str, TestResult],
    ) -> str:
        """
        Builds the prompt for the Judge role summarizing empirical test outcomes.
        """
        summary_lines = []
        for patch_id, res in test_results.items():
            status_str = res.status.value if hasattr(res.status, "value") else str(res.status)
            summary_lines.append(
                f"- Patch {patch_id}: status={status_str}, exit_code={res.exit_code}, passed={res.passed}\n"
                f"  stdout: {res.stdout[:200]}\n  stderr: {res.stderr[:200]}"
            )
        evidence_summary = "\n".join(summary_lines) if summary_lines else "No test results available."

        return (
            f"You are the JUDGE in the Swarm Debugger courtroom.\n"
            f"Bug Description: {session.bug_description}\n"
            f"Empirical Test Evidence:\n{evidence_summary}\n"
            f"Rule: Rely strictly on empirical test execution evidence. Synthesize a verdict."
        )

    def evaluate_verdict(
        self,
        session: DebugSession,
        prosecutor_patch: Optional[CandidatePatch],
        defender_patch: Optional[CandidatePatch],
        test_results: Dict[str, TestResult],
    ) -> JudgeVerdict:
        """
        Scaffolding interface for generating JudgeVerdict.
        In the subsequent agent implementation step, this method will query Ollama.
        """
        raise NotImplementedError(
            "Live LLM inference for Judge is scheduled for subsequent agent implementation. "
            "Backend foundation scaffolding is active."
        )
