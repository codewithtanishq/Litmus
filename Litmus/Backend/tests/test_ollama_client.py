"""
Unit tests for the local Ollama HTTP client with mocked network responses.
"""

import json
from unittest import mock
import httpx
import pytest

from app.config import OllamaSettings
from app.agents.ollama_client import (
    OllamaClient,
    OllamaConnectionError,
    OllamaTimeoutError,
    OllamaModelNotFoundError,
    OllamaResponseError,
    MalformedOutputError,
)


@pytest.fixture
def test_settings() -> OllamaSettings:
    return OllamaSettings(
        base_url="http://localhost:11434",
        model="qwen2.5-coder:7b",
        temperature=0.2,
        timeout_seconds=5.0,
    )


class TestOllamaClient:
    def test_successful_generate(self, test_settings: OllamaSettings):
        mock_response = httpx.Response(
            status_code=200,
            json={"model": "qwen2.5-coder:7b", "response": '{"proposed_code": "return 1"}', "done": True},
            request=httpx.Request("POST", "http://localhost:11434/api/generate"),
        )
        mock_http_client = mock.MagicMock(spec=httpx.Client)
        mock_http_client.post.return_value = mock_response

        client = OllamaClient(settings=test_settings, http_client=mock_http_client)
        result = client.generate("test prompt")

        assert result == '{"proposed_code": "return 1"}'
        mock_http_client.post.assert_called_once()
        call_kwargs = mock_http_client.post.call_args[1]
        assert call_kwargs["json"]["model"] == "qwen2.5-coder:7b"
        assert call_kwargs["json"]["prompt"] == "test prompt"
        assert call_kwargs["json"]["format"] == "json"

    def test_parse_json_response_raw_and_markdown(self, test_settings: OllamaSettings):
        client = OllamaClient(settings=test_settings)

        # Raw JSON
        data = client.parse_json_response('{"foo": "bar", "number": 42}')
        assert data == {"foo": "bar", "number": 42}

        # Markdown fenced JSON
        markdown_text = "Here is the patch:\n```json\n{\"root_cause\": \"typo\", \"proposed_code\": \"x = 1\"}\n```"
        data_fenced = client.parse_json_response(markdown_text)
        assert data_fenced["root_cause"] == "typo"
        assert data_fenced["proposed_code"] == "x = 1"

    def test_connection_failure(self, test_settings: OllamaSettings):
        mock_http_client = mock.MagicMock(spec=httpx.Client)
        mock_http_client.post.side_effect = httpx.ConnectError(
            "Connection refused",
            request=httpx.Request("POST", "http://localhost:11434/api/generate"),
        )

        client = OllamaClient(settings=test_settings, http_client=mock_http_client)
        with pytest.raises(OllamaConnectionError, match="Cannot connect to local Ollama server"):
            client.generate("test prompt")

    def test_timeout_failure(self, test_settings: OllamaSettings):
        mock_http_client = mock.MagicMock(spec=httpx.Client)
        mock_http_client.post.side_effect = httpx.TimeoutException(
            "Timed out",
            request=httpx.Request("POST", "http://localhost:11434/api/generate"),
        )

        client = OllamaClient(settings=test_settings, http_client=mock_http_client)
        with pytest.raises(OllamaTimeoutError, match="timed out after 5.0s"):
            client.generate("test prompt")

    def test_model_not_found_404(self, test_settings: OllamaSettings):
        mock_response = httpx.Response(
            status_code=404,
            text='{"error": "model \'qwen2.5-coder:7b\' not found"}',
            request=httpx.Request("POST", "http://localhost:11434/api/generate"),
        )
        mock_http_client = mock.MagicMock(spec=httpx.Client)
        mock_http_client.post.return_value = mock_response

        client = OllamaClient(settings=test_settings, http_client=mock_http_client)
        with pytest.raises(OllamaModelNotFoundError, match="Model 'qwen2.5-coder:7b' was not found"):
            client.generate("test prompt")

    def test_http_server_error_500(self, test_settings: OllamaSettings):
        mock_response = httpx.Response(
            status_code=500,
            text="Internal Server Error",
            request=httpx.Request("POST", "http://localhost:11434/api/generate"),
        )
        mock_http_client = mock.MagicMock(spec=httpx.Client)
        mock_http_client.post.return_value = mock_response

        client = OllamaClient(settings=test_settings, http_client=mock_http_client)
        with pytest.raises(OllamaResponseError, match="HTTP 500"):
            client.generate("test prompt")

    def test_malformed_empty_output(self, test_settings: OllamaSettings):
        mock_response = httpx.Response(
            status_code=200,
            json={"model": "qwen2.5-coder:7b", "response": "   ", "done": True},
            request=httpx.Request("POST", "http://localhost:11434/api/generate"),
        )
        mock_http_client = mock.MagicMock(spec=httpx.Client)
        mock_http_client.post.return_value = mock_response

        client = OllamaClient(settings=test_settings, http_client=mock_http_client)
        with pytest.raises(MalformedOutputError, match="empty response text"):
            client.generate("test prompt")

    def test_malformed_invalid_json_parsing(self, test_settings: OllamaSettings):
        client = OllamaClient(settings=test_settings)
        with pytest.raises(MalformedOutputError, match="Failed to parse model output as JSON"):
            client.parse_json_response("This is just plain text, not JSON at all.")
