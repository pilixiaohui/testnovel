import json
import httpx
import pytest

import app.services.topone_client as topone_client
from app.services.topone_client import ToponeClient


@pytest.mark.asyncio
async def test_generate_content_builds_payload():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["json"] = json.loads(request.content.decode())
        mock_response = {
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [
                            {"text": "thought text", "thought": True},
                            {"text": "final text"},
                        ],
                    },
                    "finishReason": "STOP",
                }
            ]
        }
        return httpx.Response(200, json=mock_response)

    transport = httpx.MockTransport(handler)
    client = ToponeClient(
        api_key="test-key",
        base_url="https://api.toponeapi.top",
        default_model="gemini-3-pro-preview-11-2025",
        secondary_model="gemini-3-flash-preview",
    )

    data = await client.generate_content(
        messages=[{"role": "user", "text": "hello"}],
        system_instruction="sys",
        generation_config={"temperature": 0.5},
        model="gemini-3-flash-preview",
        transport=transport,
    )

    assert data["candidates"][0]["content"]["parts"] == [{"text": "final text"}]
    assert "gemini-3-flash-preview" in captured["url"]
    assert captured["json"]["contents"][0]["role"] == "user"
    assert captured["json"]["contents"][0]["parts"][0]["text"] == "hello"
    assert captured["json"]["systemInstruction"]["parts"][0]["text"] == "sys"
    assert captured["json"]["generationConfig"]["temperature"] == 0.5


def test_strip_thoughts_skips_missing_content():
    payload = {"candidates": [{"content": None}]}
    result = ToponeClient._strip_thoughts(payload)
    assert result["candidates"][0]["content"] is None


@pytest.mark.asyncio
async def test_generate_content_rejects_unsupported_model():
    client = ToponeClient(api_key="k")
    with pytest.raises(ValueError):
        await client.generate_content(
            messages=[{"role": "user", "text": "hi"}],
            model="unknown-model",
        )


@pytest.mark.asyncio
async def test_generate_content_requires_api_key():
    client = ToponeClient(api_key="")  # force missing key even if .env provides placeholder
    with pytest.raises(ValueError):
        await client.generate_content(messages=[{"role": "user", "text": "hi"}])



@pytest.mark.asyncio
async def test_generate_content_rejects_timeout_less_than_600_seconds():
    client = ToponeClient(api_key="test-key")

    with pytest.raises(ValueError, match="timeout must be >= 600"):
        await client.generate_content(
            messages=[{"role": "user", "text": "hello"}],
            timeout=30,
        )


def test_topone_client_uses_config_defaults(monkeypatch):
    monkeypatch.setattr(topone_client, "TOPONE_API_KEY", "test-key")
    monkeypatch.setattr(topone_client, "TOPONE_BASE_URL", "https://example.com")
    monkeypatch.setattr(topone_client, "TOPONE_DEFAULT_MODEL", "model-primary")
    monkeypatch.setattr(topone_client, "TOPONE_SECONDARY_MODEL", "model-secondary")
    monkeypatch.setattr(topone_client, "TOPONE_TIMEOUT_SECONDS", 600.0)

    client = topone_client.ToponeClient()

    assert client.api_key == "test-key"
    assert client.base_url == "https://example.com"
    assert client.default_model == "model-primary"
    assert client.secondary_model == "model-secondary"
    assert client.timeout_seconds == 600.0
    assert client.allowed_models == ("model-primary", "model-secondary")
