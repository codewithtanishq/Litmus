"""
Judge Agent for Swarm Debugger / Litmus.

Role & Responsibilities:
- Reviews real, deterministic test evaluation evidence for Candidate Fix A and Fix B.
- Synthesizes an evidence-based courtroom ruling explaining which candidate performed better and why.
- Strictly adheres to the principle that the deterministic test evaluator is SUPREME.
- Cites actual test outcomes, assertions, exit codes, and stdout/stderr evidence.
- Explains when both candidates pass, both fail, or infrastructure errors occur.
- Never fabricates logs, assertions, or test results.
- Handles Ollama offline / failure gracefully without hallucinating or fabricating verdicts.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, Optional

from app.config import OllamaSettings, get_settings
from app.agents.ollama_client import OllamaClient, OllamaError, MalformedOutputError
from app.schemas.session import DebugSession
from app.schemas.patch import CandidatePatch
from app.schemas.interfaces import JudgeVerdict, VerdictDecision
from app.schemas.events import WorkflowEventType
from app.events.publisher import get_event_publisher, BaseEventPublisher

logger = logging.getLogger(__name__)

JUDGE_SYSTEM_PROMPT = """You are the JUDGE in the Litmus / Swarm Debugger multi-agent debugging courtroom.
Your role:
1. Review the empirical test results for Fix A (Prosecutor) and Fix B (Defender) against the trusted reproduction test suite.
2. The deterministic test evaluator is SUPREME. You interpret the evidence, but do NOT override the evaluator.
3. Cite actual test outcomes (passed/failed tests, exit codes, assertion errors, stdout/stderr).
4. Explain which candidate performed better and why:
   - If one candidate passed all tests and the other failed, the passing candidate wins.
   - If both candidates passed all tests, explain both succeeded on reproduction tests, compare code cleanliness/safety, and pick the better candidate.
   - If both candidates failed, explain what failed in each and rule to retry (or fail if max rounds reached).
   - If an infrastructure error or timeout occurred, clearly state that the execution environment prevented evaluation.
5. NEVER claim a candidate is universally correct merely because it passed the supplied reproduction tests.
6. NEVER invent or hallucinate test names, logs, error messages, or assertions.
7. Return ONLY a single valid JSON object with the following schema:
{
    "decision": "accept_prosecutor" | "accept_defender" | "retry_round" | "exhausted_failure",
    "winning_patch_id": "<patch_id of winner or null>",
    "explanation": "<detailed empirical explanation citing test evidence>",
    "prosecutor_evaluation": "<assessment of Fix A test outcomes>",
    "defender_evaluation": "<assessment of Fix B test outcomes>"
}
Do NOT include markdown text outside the JSON object."""


class JudgeAgent:
    """
    Judge Agent.
    Evaluates empirical test evidence and produces a justified verdict.
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

    def _format_test_result_summary(self, result: Any, label: str) -> str:
        """Helper to format a test result into human-readable evidence summary."""
        if not result:
            return f"{label}: No evaluation evidence available."

        if isinstance(result, dict):
            status = result.get("status", "unknown")
            exit_code = result.get("exit_code")
            stdout = result.get("stdout_excerpt") or result.get("stdout") or ""
            stderr = result.get("stderr_excerpt") or result.get("stderr") or ""
            per_tests = result.get("per_test_results") or result.get("test_cases") or []
            duration = result.get("duration_ms") or (result.get("duration_seconds", 0) * 1000)
            sig = result.get("failure_signature") or ""
        else:
            status = getattr(result, "status", "unknown")
            exit_code = getattr(result, "exit_code", None)
            stdout = getattr(result, "stdout_excerpt", getattr(result, "stdout", ""))
            stderr = getattr(result, "stderr_excerpt", getattr(result, "stderr", ""))
            per_tests = getattr(result, "per_test_results", getattr(result, "test_cases", []))
            duration = getattr(result, "duration_ms", 0.0)
            sig = getattr(result, "failure_signature", "")

        status_str = status.value if hasattr(status, "value") else str(status)

        test_lines = []
        for pt in per_tests:
            if isinstance(pt, dict):
                t_name = pt.get("test_name") or pt.get("name")
                t_status = pt.get("status")
                t_msg = pt.get("message") or pt.get("error_message") or ""
            else:
                t_name = getattr(pt, "test_name", getattr(pt, "name", ""))
                t_status = getattr(pt, "status", "")
                t_msg = getattr(pt, "message", getattr(pt, "error_message", ""))

            t_status_str = t_status.value if hasattr(t_status, "value") else str(t_status)
            line = f"    - {t_name}: {t_status_str.upper()}"
            if t_msg:
                line += f" -> {t_msg[:150]}"
            test_lines.append(line)

        per_test_str = "\n".join(test_lines) if test_lines else "    (No individual test breakdown)"

        return (
            f"=== {label} Empirical Test Evidence ===\n"
            f"Overall Status: {status_str.upper()}\n"
            f"Process Exit Code: {exit_code}\n"
            f"Execution Duration: {duration:.1f}ms\n"
            f"Failure Signature: {sig or 'None'}\n"
            f"Individual Test Outcomes:\n{per_test_str}\n"
            f"Captured stdout excerpt:\n```\n{stdout[:300] or '(empty)'}\n```\n"
            f"Captured stderr excerpt:\n```\n{stderr[:300] or '(empty)'}\n```"
        )

    def build_prompt(
        self,
        session: DebugSession,
        prosecutor_patch: Optional[CandidatePatch],
        defender_patch: Optional[CandidatePatch],
        test_results: Dict[str, Any],
    ) -> str:
        """
        Builds the prompt summarizing candidate implementations and deterministic test evidence.
        """
        patch_id_a = prosecutor_patch.patch_id if prosecutor_patch else "prosecutor"
        patch_id_b = defender_patch.patch_id if defender_patch else "defender"

        res_a = test_results.get("prosecutor") or test_results.get(patch_id_a)
        res_b = test_results.get("defender") or test_results.get(patch_id_b)

        evidence_a = self._format_test_result_summary(res_a, "Fix A (Prosecutor)")
        evidence_b = self._format_test_result_summary(res_b, "Fix B (Defender)")

        code_a = (prosecutor_patch.proposed_code if prosecutor_patch else "N/A")[:500]
        code_b = (defender_patch.proposed_code if defender_patch else "N/A")[:500]
        expl_a = (prosecutor_patch.explanation if prosecutor_patch else "N/A")[:300]
        expl_b = (defender_patch.explanation if defender_patch else "N/A")[:300]

        return (
            f"=== COURTROOM CASE DELIBERATION (Round {session.current_round}) ===\n"
            f"Session ID: {session.session_id}\n\n"
            f"REPORTED BUG:\n{session.bug_description}\n\n"
            f"CANDIDATE FIX A (Prosecutor - ID: {patch_id_a}):\n"
            f"Explanation: {expl_a}\n"
            f"Code:\n```\n{code_a}\n```\n\n"
            f"{evidence_a}\n\n"
            f"--------------------------------------------------\n\n"
            f"CANDIDATE FIX B (Defender - ID: {patch_id_b}):\n"
            f"Critique & Explanation: {expl_b}\n"
            f"Code:\n```\n{code_b}\n```\n\n"
            f"{evidence_b}\n\n"
            f"JUDICIAL INSTRUCTIONS:\n"
            f"1. Rely strictly on the test evidence above. The test outcomes are empirical ground truth.\n"
            f"2. Cite specific test names, pass/fail status, and observed error messages in your explanation.\n"
            f"3. Return your verdict as a strict JSON object with: 'decision', 'winning_patch_id', 'explanation', 'prosecutor_evaluation', 'defender_evaluation'."
        )

    def evaluate_verdict(
        self,
        session: DebugSession,
        prosecutor_patch: Optional[CandidatePatch],
        defender_patch: Optional[CandidatePatch],
        test_results: Dict[str, Any],
        round_number: Optional[int] = None,
    ) -> JudgeVerdict:
        """
        Synthesizes an empirical, evidence-grounded verdict.
        If Ollama is available, uses the model to formulate nuanced legal explanation.
        If Ollama is unavailable or fails, synthesizes a deterministic verdict based
        strictly on test outcomes without fabricating logs.
        """
        active_round = round_number if round_number is not None else session.current_round
        patch_id_a = prosecutor_patch.patch_id if prosecutor_patch else "prosecutor"
        patch_id_b = defender_patch.patch_id if defender_patch else "defender"

        res_a = test_results.get("prosecutor") or test_results.get(patch_id_a)
        res_b = test_results.get("defender") or test_results.get(patch_id_b)

        # Helper to determine pass status
        def _is_passed(res: Any) -> bool:
            if not res:
                return False
            status = res.get("status") if isinstance(res, dict) else getattr(res, "status", None)
            status_str = status.value if hasattr(status, "value") else str(status)
            return status_str in ("passed", "PASSED")

        passed_a = _is_passed(res_a)
        passed_b = _is_passed(res_b)

        # Baseline deterministic decision
        if passed_a and not passed_b:
            deterministic_decision = VerdictDecision.ACCEPT_PROSECUTOR
            deterministic_winner = patch_id_a
        elif passed_b and not passed_a:
            deterministic_decision = VerdictDecision.ACCEPT_DEFENDER
            deterministic_winner = patch_id_b
        elif passed_a and passed_b:
            deterministic_decision = VerdictDecision.ACCEPT_PROSECUTOR
            deterministic_winner = patch_id_a
        else:
            deterministic_decision = VerdictDecision.RETRY_ROUND
            deterministic_winner = None

        # Emit agent_started
        self.publisher.emit(
            event_type=WorkflowEventType.AGENT_STARTED,
            session_id=session.session_id,
            round_number=active_round,
            data={"agent_role": "judge", "model": self.settings.model},
        )

        prompt = self.build_prompt(session, prosecutor_patch, defender_patch, test_results)
        verdict = None

        # Attempt LLM synthesis
        try:
            raw_response = self.client.generate(
                prompt=prompt,
                system_instruction=JUDGE_SYSTEM_PROMPT,
                format_json=True,
            )
            parsed = self.client.parse_json_response(raw_response)

            decision_str = parsed.get("decision", "").lower()
            explanation = parsed.get("explanation", "").strip()
            eval_a = parsed.get("prosecutor_evaluation", "").strip()
            eval_b = parsed.get("defender_evaluation", "").strip()
            winning_id = parsed.get("winning_patch_id")

            # Validate that LLM does not contradict deterministic reality
            if passed_a and not passed_b:
                final_decision = VerdictDecision.ACCEPT_PROSECUTOR
                final_winner = patch_id_a
            elif passed_b and not passed_a:
                final_decision = VerdictDecision.ACCEPT_DEFENDER
                final_winner = patch_id_b
            elif passed_a and passed_b:
                if winning_id == patch_id_b or "defender" in decision_str:
                    final_decision = VerdictDecision.ACCEPT_DEFENDER
                    final_winner = patch_id_b
                else:
                    final_decision = VerdictDecision.ACCEPT_PROSECUTOR
                    final_winner = patch_id_a
            else:
                final_decision = VerdictDecision.RETRY_ROUND
                final_winner = None

            verdict = JudgeVerdict(
                session_id=session.session_id,
                round_number=active_round,
                winning_patch_id=final_winner,
                decision=final_decision,
                explanation=explanation or f"Evidence-based verdict: ruling {final_decision.value}.",
                prosecutor_evaluation=eval_a,
                defender_evaluation=eval_b,
                created_at=datetime.now(timezone.utc),
            )

        except (OllamaError, MalformedOutputError, Exception) as exc:
            logger.info(f"Ollama unavailable or failed during Judge evaluation: {exc}. Using deterministic evidence synthesis.")
            # Deterministic evidence-backed fallback explanation
            stat_a_str = "PASSED" if passed_a else "FAILED"
            stat_b_str = "PASSED" if passed_b else "FAILED"

            if passed_a and not passed_b:
                expl = (
                    f"Candidate Fix A (Prosecutor) passed all deterministic tests ({stat_a_str}), "
                    f"while Candidate Fix B (Defender) failed ({stat_b_str}). Fix A accepted on test evidence."
                )
            elif passed_b and not passed_a:
                expl = (
                    f"Candidate Fix B (Defender) passed all deterministic tests ({stat_b_str}), "
                    f"while Candidate Fix A (Prosecutor) failed ({stat_a_str}). Fix B accepted on test evidence."
                )
            elif passed_a and passed_b:
                expl = (
                    f"Both candidates passed reproduction tests. Fix A accepted as the primary clean patch."
                )
            else:
                expl = (
                    f"Both candidates failed deterministic test execution (Fix A: {stat_a_str}, Fix B: {stat_b_str}). "
                    f"No candidate resolved the bug in round {active_round}. Ruling: retry round."
                )

            verdict = JudgeVerdict(
                session_id=session.session_id,
                round_number=active_round,
                winning_patch_id=deterministic_winner,
                decision=deterministic_decision,
                explanation=expl,
                prosecutor_evaluation=f"Fix A outcome: {stat_a_str}",
                defender_evaluation=f"Fix B outcome: {stat_b_str}",
                created_at=datetime.now(timezone.utc),
            )

        # Emit verdict_created event
        self.publisher.emit(
            event_type=WorkflowEventType.VERDICT_CREATED,
            session_id=session.session_id,
            round_number=active_round,
            data={
                "decision": verdict.decision.value if hasattr(verdict.decision, "value") else str(verdict.decision),
                "winning_patch_id": verdict.winning_patch_id,
                "explanation": verdict.explanation[:300],
            },
        )

        return verdict
