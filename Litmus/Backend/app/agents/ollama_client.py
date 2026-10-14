"""
Local Ollama HTTP client implementation using httpx for Swarm Debugger.

Features:
- Free local HTTP inference (POST /api/generate)
- Configurable base URL, model name, temperature, and timeout
- Strict local-only design (never uses external LLM services or paid APIs)
- Actionable error messages on connection loss, timeout, missing model, and malformed JSON
- Supports dependency injection of httpx.Client for clean unit test mocking
"""

import json
import logging
import re
from typing import Any, Dict, Optional
import httpx

from app.config import OllamaSettings, get_settings

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    """Base exception for all Ollama-related failures."""
    pass


class OllamaConnectionError(OllamaError):
    """Raised when the local Ollama server cannot be reached."""
    pass


class OllamaTimeoutError(OllamaError):
    """Raised when Ollama request exceeds configured timeout threshold."""
    pass


class OllamaModelNotFoundError(OllamaError):
    """Raised when the specified model is not downloaded/available in Ollama."""
    pass


class OllamaResponseError(OllamaError):
    """Raised when Ollama returns an HTTP error or unexpected payload."""
    pass


class MalformedOutputError(OllamaError):
    """Raised when the model's response cannot be parsed into the required structured format."""
    pass


class OllamaClient:
    """
    Client for interacting with local Ollama HTTP API.
    """

    def __init__(
        self,
        settings: Optional[OllamaSettings] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self.settings = settings or get_settings().ollama
        self.base_url = self.settings.base_url.rstrip("/")
        self.model = self.settings.model
        self.temperature = self.settings.temperature
        self.timeout_seconds = self.settings.timeout_seconds
        self._custom_client = http_client

    def _get_client(self) -> httpx.Client:
        """Returns injected HTTP client or creates a new configured one."""
        if self._custom_client is not None:
            return self._custom_client
        return httpx.Client(timeout=self.timeout_seconds)

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        format_json: Any = True,
    ) -> str:
        """
        Sends an inference request to the local Ollama /api/generate endpoint.

        Args:
            prompt: User/context prompt instructing the model.
            system_instruction: Optional system instruction for agent persona.
            format_json: If True, requests Ollama's constrained JSON output mode.
                         Can also be a dictionary representing a JSON schema.

        Returns:
            The raw text string emitted by the model.

        Raises:
            OllamaConnectionError: If Ollama daemon is offline or unreachable.
            OllamaTimeoutError: If generation exceeds configured timeout.
            OllamaModelNotFoundError: If requested model is not pulled in Ollama.
            OllamaResponseError: If server responds with HTTP error.
        """
        endpoint = f"{self.base_url}/api/generate"
        options: Dict[str, Any] = {
            "temperature": self.temperature,
            "num_ctx": getattr(self.settings, "num_ctx", 8192),
            "num_predict": getattr(self.settings, "num_predict", 4096),
        }
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": options,
            "keep_alive": getattr(self.settings, "keep_alive", "10m"),
        }
        if system_instruction:
            payload["system"] = system_instruction
        if isinstance(format_json, dict):
            payload["format"] = format_json
        elif format_json:
            payload["format"] = "json"

        client = self._get_client()
        # If client was dynamically created, manage its lifecycle via context manager
        should_close = self._custom_client is None

        try:
            logger.debug(f"Sending generation request to Ollama endpoint: {endpoint} for model {self.model}")
            response = client.post(endpoint, json=payload)
        except httpx.ConnectError as exc:
            msg = (
                f"Cannot connect to local Ollama server at '{self.base_url}'. "
                f"Please ensure Ollama is installed and running locally ('ollama serve')."
            )
            logger.error(msg)
            raise OllamaConnectionError(msg) from exc
        except httpx.TimeoutException as exc:
            msg = (
                f"Ollama inference timed out after {self.timeout_seconds}s for model '{self.model}'. "
                f"Consider increasing OLLAMA_TIMEOUT_SECONDS or using a smaller model."
            )
            logger.error(msg)
            raise OllamaTimeoutError(msg) from exc
        except httpx.RequestError as exc:
            msg = f"Network communication error contacting Ollama at '{self.base_url}': {exc}"
            logger.error(msg)
            raise OllamaConnectionError(msg) from exc
        finally:
            if should_close:
                client.close()

        # Handle HTTP status codes
        if response.status_code == 404:
            msg = (
                f"Model '{self.model}' was not found on local Ollama server at '{self.base_url}'. "
                f"Please run 'ollama pull {self.model}' to download the required weights."
            )
            logger.error(msg)
            raise OllamaModelNotFoundError(msg)

        if response.is_error:
            msg = (
                f"Ollama server returned HTTP {response.status_code}: {response.text[:200]}"
            )
            logger.error(msg)
            raise OllamaResponseError(msg)

        try:
            data = response.json()
        except Exception as exc:
            msg = f"Ollama returned non-JSON HTTP response body: {response.text[:200]}"
            logger.error(msg)
            raise OllamaResponseError(msg) from exc

        if not isinstance(data, dict) or "response" not in data:
            msg = f"Malformed Ollama response payload missing 'response' field: {data}"
            logger.error(msg)
            raise OllamaResponseError(msg)

        raw_text = data["response"]
        if not raw_text or not raw_text.strip():
            msg = "Ollama model returned empty response text."
            logger.warning(msg)
            raise MalformedOutputError(msg)

        return raw_text.strip()

    @staticmethod
    def _extract_first_balanced_json(text: str) -> str:
        """Find the first balanced '{...}' structure in text."""
        start = text.find("{")
        if start == -1:
            return text
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                if in_string:
                    escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if not in_string:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return text[start : i + 1]
        return text[start:]

    def parse_json_response(self, raw_text: str) -> Dict[str, Any]:
        """
        Extracts and parses JSON object from model output text.
        Handles optional markdown code fences and extracts first balanced JSON object.

        Raises:
            MalformedOutputError: If no valid JSON dictionary can be extracted.
        """
        cleaned = raw_text.strip()

        # Extract markdown json block if present
        fence_match = re.search(r"```(?:json)?\s*(\{.*)", cleaned, re.DOTALL)
        if fence_match:
            candidate_str = fence_match.group(1).strip()
        else:
            candidate_str = cleaned

        extracted = self._extract_first_balanced_json(candidate_str)

        try:
            parsed = json.loads(extracted)
        except json.JSONDecodeError as exc:
            msg = f"Failed to parse model output as JSON: {exc}. Raw snippet: {raw_text[:150]}"
            logger.error(msg)
            raise MalformedOutputError(msg) from exc

        if not isinstance(parsed, dict):
            msg = f"Expected JSON object (dict) from model, got {type(parsed).__name__}"
            logger.error(msg)
            raise MalformedOutputError(msg)

        return parsed

    def generate_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        max_attempts: int = 3,
    ) -> Dict[str, Any]:
        """
        Generates and parses structured JSON output, retrying on MalformedOutputError.
        """
        current_prompt = prompt
        last_error: Optional[MalformedOutputError] = None
        for attempt in range(1, max_attempts + 1):
            try:
                raw_text = self.generate(
                    current_prompt,
                    system_instruction=system_instruction,
                    format_json=schema if schema is not None else True,
                )
                return self.parse_json_response(raw_text)
            except MalformedOutputError as exc:
                last_error = exc
                logger.warning(
                    f"Ollama JSON generation attempt {attempt}/{max_attempts} failed: {exc}. Retrying..."
                )
                if attempt < max_attempts:
                    current_prompt = (
                        f"{prompt}\n\nYour previous reply was invalid: {exc}. "
                        "Return ONLY valid JSON matching the schema."
                    )
        raise last_error or MalformedOutputError("Failed to generate valid JSON after retries.")

