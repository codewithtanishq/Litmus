import ast
import re
from typing import Any, List, Optional
from app.agents.ollama_client import MalformedOutputError
from app.schemas.interfaces import ConstraintRecord


def extract_python_code(text: str) -> str:
    """
    Extracts raw python code from model output, stripping markdown fences
    and surrounding prose, then validating with ast.parse.
    Raises MalformedOutputError on SyntaxError or empty code.
    """
    if not text or not text.strip():
        raise MalformedOutputError("Empty proposed code block received.")

    raw = text.strip()
    # Match fenced code blocks e.g. ```python ... ``` or ``` ... ```
    fence_pattern = r"```(?:python)?\s*\n(.*?)```"
    matches = re.findall(fence_pattern, raw, re.DOTALL | re.IGNORECASE)
    if matches:
        code = matches[0].strip()
    elif "```" in raw:
        # Fences might be incomplete or at ends
        parts = raw.split("```")
        if len(parts) >= 2:
            inner = parts[1]
            if inner.lower().startswith("python"):
                inner = inner[6:]
            code = inner.strip()
        else:
            code = raw
    else:
        code = raw

    if not code:
        raise MalformedOutputError("No python code found after stripping fences.")

    try:
        ast.parse(code)
    except SyntaxError as exc:
        raise MalformedOutputError(f"Proposed Python code has syntax error: {exc}") from exc

    return code


def format_constraints_summary(constraints: Optional[List[Any]]) -> str:
    """
    Formats the cumulative active constraints retrieved from Member 2's Constraint Ledger.
    Ensures empty constraints are properly represented for initial debugging rounds.
    Compatible with both Member 2 app.contracts.Constraint and Member 1 ConstraintRecord.
    Capped at ~6000 characters for token conservation.

    Args:
        constraints: Cumulative list of rejected hypotheses and test error evidence.

    Returns:
        Structured text block for inclusion in agent prompt.
    """
    if not constraints:
        return "None (Initial round — no prior rejected hypotheses)."

    formatted_entries = []
    for idx, c in enumerate(constraints, 1):
        if hasattr(c, "constraint_text"):
            # app.contracts.Constraint
            formatted_entries.append(
                f"Constraint #{idx} (Failed in Round {c.round_number}, Signature: {c.failure_signature}):\n"
                f"{c.constraint_text}\n"
                f"  -> RULE: Do NOT repeat this failed implementation or reasoning."
            )
        else:
            # app.schemas.interfaces.ConstraintRecord
            agent_role = getattr(c, "agent_role", "PROSECUTOR")
            role_label = agent_role.value.upper() if hasattr(agent_role, "value") else str(agent_role).upper()
            code_preview = getattr(c, "rejected_code", "").strip()
            if len(code_preview) > 300:
                code_preview = code_preview[:300] + "\n... [truncated]"

            stderr_preview = getattr(c, "test_stderr", "").strip()
            if len(stderr_preview) > 200:
                stderr_preview = stderr_preview[:200] + "... [truncated]"
            elif not stderr_preview:
                stderr_preview = "Execution assertion failure or non-zero exit code"

            reason = getattr(c, "failure_reason", "Test assertion failure")

            formatted_entries.append(
                f"Constraint #{idx} (Failed in Round {c.round_number}, Proposed by {role_label}):\n"
                f"  * Failure Reason: {reason}\n"
                f"  * Test Failure Evidence: {stderr_preview}\n"
                f"  * Rejected Code:\n```\n{code_preview}\n```\n"
                f"  -> RULE: Do NOT repeat this failed implementation or reasoning."
            )

    summary = "\n\n".join(formatted_entries)
    if len(summary) > 6000:
        return summary[:6000] + "\n... [Remaining constraints truncated for context window]"
    return summary

