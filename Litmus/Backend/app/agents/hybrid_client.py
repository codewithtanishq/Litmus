"""
Hybrid LLM Client for Swarm Debugger / Litmus.
==============================================
Primary: Google Gemini API (gemini-3.1-flash-lite)
Fallback: Local Ollama (qwen2.5-coder:7b)

Seamlessly falls back to Ollama when:
- GEMINI_API_KEY is not configured or empty.
- Gemini returns HTTP 429 (quota / rate limit exceeded).
- Gemini returns HTTP 500, 502, 503, 504 (service unavailable / high demand).
- Gemini requests time out or experience network drops.

Adheres strictly to the LLM client contract expected by Prosecutor, Defender, and Judge.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from typing import Any, Dict, Optional
import httpx

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def safe_print(*args: Any, **kwargs: Any) -> None:
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        clean_args = [
            str(a).encode("ascii", errors="replace").decode("ascii") for a in args
        ]
        print(*clean_args, **kwargs)


from app.config import GeminiSettings, OllamaSettings, get_settings
from app.agents.ollama_client import (
    OllamaClient,
    OllamaError,
    OllamaConnectionError,
    OllamaTimeoutError,
    OllamaModelNotFoundError,
    OllamaResponseError,
    MalformedOutputError,
)

logger = logging.getLogger(__name__)


class HybridLLMClient:
    """
    Hybrid inference client that uses Google Gemini as the primary high-speed
    cloud intelligence layer, and automatically falls back to local Ollama.
    """

    def __init__(
        self,
        gemini_settings: Optional[GeminiSettings] = None,
        ollama_settings: Optional[OllamaSettings] = None,
        ollama_client: Optional[OllamaClient] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        settings = get_settings()
        self.gemini_settings = gemini_settings or settings.gemini
        self.ollama_settings = ollama_settings or settings.ollama
        self.ollama_client = ollama_client or OllamaClient(
            settings=self.ollama_settings,
            http_client=http_client,
        )
        self._custom_client = http_client

        # Active provider tracking
        self.last_provider_used: str = "none"

    @property
    def model(self) -> str:
        """Expose current primary model name for events/logging."""
        if self.gemini_settings.api_key:
            return self.gemini_settings.model
        return self.ollama_settings.model

    @property
    def settings(self) -> Any:
        """Backward compatibility for agents accessing client.settings."""
        return self.ollama_settings

    def _get_http_client(self, timeout_seconds: float) -> httpx.Client:
        if self._custom_client is not None:
            return self._custom_client
        return httpx.Client(timeout=timeout_seconds)

    def _call_gemini(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        format_json: bool = True,
    ) -> str:
        """Executes API call to Google Gemini."""
        if not self.gemini_settings.api_key:
            raise OllamaError("Gemini API key is not configured.")

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.gemini_settings.model}:generateContent?key={self.gemini_settings.api_key}"
        )

        full_prompt = prompt
        if system_instruction:
            full_prompt = f"SYSTEM INSTRUCTIONS:\n{system_instruction}\n\nUSER PROMPT:\n{prompt}"

        gen_config: Dict[str, Any] = {
            "temperature": self.gemini_settings.temperature,
            "maxOutputTokens": 4096,
        }
        if format_json:
            gen_config["responseMimeType"] = "application/json"

        payload = {
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": gen_config,
        }

        client = self._get_http_client(self.gemini_settings.timeout_seconds)
        should_close = self._custom_client is None

        try:
            logger.debug(
                f"Calling primary Gemini model {self.gemini_settings.model}"
            )
            resp = client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )

            if resp.status_code == 429:
                raise OllamaResponseError(
                    f"Gemini rate limit exceeded (HTTP 429): {resp.text[:200]}"
                )
            if resp.status_code in (500, 502, 503, 504):
                raise OllamaResponseError(
                    f"Gemini service unavailable (HTTP {resp.status_code}): {resp.text[:200]}"
                )
            if resp.is_error:
                raise OllamaResponseError(
                    f"Gemini error (HTTP {resp.status_code}): {resp.text[:200]}"
                )

            res_json = resp.json()
            candidates = res_json.get("candidates", [])
            if not candidates:
                raise MalformedOutputError(
                    f"Gemini returned no candidates: {json.dumps(res_json)[:300]}"
                )

            text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            if not text or not text.strip():
                raise MalformedOutputError("Gemini returned empty text response.")

            return text.strip()

        except (httpx.TimeoutException, TimeoutError) as exc:
            raise OllamaTimeoutError(
                f"Gemini generation timed out after {self.gemini_settings.timeout_seconds}s"
            ) from exc
        except httpx.RequestError as exc:
            raise OllamaConnectionError(f"Network error contacting Gemini: {exc}") from exc
        finally:
            if should_close:
                client.close()

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        format_json: bool = True,
    ) -> str:
        """
        Attempts inference via Gemini first. If Gemini is unavailable, rate-limited,
        or errors out, falls back to local Ollama.
        """
        if bool(self.gemini_settings.api_key):
            try:
                safe_print(f"   🤖 [LLM Call] Invoking Google Gemini ({self.gemini_settings.model})...", flush=True)
                text = self._call_gemini(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    format_json=format_json,
                )
                self.last_provider_used = "gemini"
                safe_print(f"   ✨ [LLM Response] Gemini ({self.gemini_settings.model}) generated {len(text)} characters", flush=True)
                return text
            except (
                OllamaConnectionError,
                OllamaTimeoutError,
                OllamaResponseError,
                MalformedOutputError,
            ) as exc:
                safe_print(f"   ⚠️ [LLM Fallback] Gemini call failed ({exc}). Falling back to local Ollama ({self.ollama_settings.model})...", flush=True)

        # Fallback to local Ollama
        safe_print(f"   🤖 [LLM Call] Invoking local Ollama ({self.ollama_settings.model})...", flush=True)
        text = self.ollama_client.generate(
            prompt=prompt,
            system_instruction=system_instruction,
            format_json=format_json,
        )
        self.last_provider_used = "ollama"
        safe_print(f"   ✨ [LLM Response] Ollama ({self.ollama_settings.model}) generated {len(text)} characters", flush=True)
        return text

    def parse_json_response(self, raw_text: str) -> Dict[str, Any]:
        """Delegates to OllamaClient's robust JSON parser with fence & brace support."""
        return self.ollama_client.parse_json_response(raw_text)
