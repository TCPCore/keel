import pytest

from keel.api import ApiError, Client

OK = {
    "model": "muse-spark-1.3",
    "choices": [{"message": {"content": "ok"}}],
    "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
}


def test_missing_key_fails_with_instructions(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.delenv("META_API_KEY", raising=False)
    client = Client(api_key="")
    with pytest.raises(ApiError, match="no API key"):
        client.complete("hi")


def test_chat_builds_payload_and_parses_usage():
    seen = {}

    def transport(endpoint, payload, api_key, timeout):
        seen.update(endpoint=endpoint, payload=payload, key=api_key)
        return OK

    client = Client(api_key="secret", transport=transport)
    result = client.complete("hi", system="be brief", max_tokens=8)

    assert seen["endpoint"] == "https://api.meta.ai/v1/chat/completions"
    assert seen["key"] == "secret"
    assert seen["payload"]["messages"][0] == {"role": "system", "content": "be brief"}
    assert seen["payload"]["max_tokens"] == 8
    assert seen["payload"]["temperature"] == 0.0
    assert result.text == "ok"
    assert result.usage.total_tokens == 4


def test_empty_content_becomes_empty_string():
    def transport(endpoint, payload, api_key, timeout):
        return {"choices": [{"message": {"content": None}}], "usage": {}}

    result = Client(api_key="k", transport=transport).complete("hi")
    assert result.text == ""
    assert result.usage.total_tokens == 0


def test_retries_on_429(monkeypatch):
    monkeypatch.setattr("keel.api.time.sleep", lambda _seconds: None)
    attempts = {"n": 0}

    def transport(endpoint, payload, api_key, timeout):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise ApiError("rate limited", status=429)
        return OK

    result = Client(api_key="k", transport=transport).complete("hi")
    assert attempts["n"] == 3
    assert result.text == "ok"


def test_does_not_retry_client_errors(monkeypatch):
    monkeypatch.setattr("keel.api.time.sleep", lambda _seconds: None)
    attempts = {"n": 0}

    def transport(endpoint, payload, api_key, timeout):
        attempts["n"] += 1
        raise ApiError("bad request", status=400)

    with pytest.raises(ApiError):
        Client(api_key="k", transport=transport).complete("hi")
    assert attempts["n"] == 1


def test_retry_budget_is_finite(monkeypatch):
    monkeypatch.setattr("keel.api.time.sleep", lambda _seconds: None)

    def transport(endpoint, payload, api_key, timeout):
        raise ApiError("still down", status=503)

    with pytest.raises(ApiError):
        Client(api_key="k", retries=2, transport=transport).complete("hi")


def test_models_lists_ids():
    def transport(endpoint, payload, api_key, timeout):
        assert payload is None
        return {"data": [{"id": "muse-spark-1.3"}, {"id": "muse-voice-transcribe-1.0"}]}

    assert Client(api_key="k", transport=transport).models() == [
        "muse-spark-1.3",
        "muse-voice-transcribe-1.0",
    ]
