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
        format_json: bool = True,
    ) -> str:
        """
        Sends an inference request to the local Ollama /api/generate endpoint.

        Args:
            prompt: User/context prompt instructing the model.
            system_instruction: Optional system instruction for agent persona.
            format_json: If True, requests Ollama's constrained JSON output mode.

        Returns:
            The raw text string emitted by the model.

        Raises:
            OllamaConnectionError: If Ollama daemon is offline or unreachable.
            OllamaTimeoutError: If generation exceeds configured timeout.
            OllamaModelNotFoundError: If requested model is not pulled in Ollama.
            OllamaResponseError: If server responds with HTTP error.
        """
        endpoint = f"{self.base_url}/api/generate"
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
            },
        }
        if system_instruction:
            payload["system"] = system_instruction
        if format_json:
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

    def parse_json_response(self, raw_text: str) -> Dict[str, Any]:
        """
        Extracts and parses JSON object from model output text.
        Handles optional markdown code fences ```json ... ```.

        Raises:
            MalformedOutputError: If no valid JSON dictionary can be extracted.
        """
        cleaned = raw_text.strip()

        # Extract markdown json block if present
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if fence_match:
            cleaned = fence_match.group(1).strip()
        else:
            # Look for the outer-most curly braces
            brace_match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            if brace_match:
                cleaned = brace_match.group(1).strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            msg = f"Failed to parse model output as JSON: {exc}. Raw snippet: {raw_text[:150]}"
            logger.error(msg)
            raise MalformedOutputError(msg) from exc

        if not isinstance(parsed, dict):
            msg = f"Expected JSON object (dict) from model, got {type(parsed).__name__}"
            logger.error(msg)
            raise MalformedOutputError(msg)

        return parsed
