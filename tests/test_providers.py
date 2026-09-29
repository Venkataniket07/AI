
import httpx
import pytest

from ai.config import GeminiConfig
from ai.providers import base, gemini
from ai.schemas import SessionSummary

_RealClient = httpx.Client  # captured before tests patch httpx.Client


def _client(statuses, calls, headers=None):
    """httpx client whose transport answers with `statuses` in order and records each request."""
    queue = list(statuses)

    def handler(request):
        calls.append(request)
        status = queue.pop(0)
        body = {"candidates": [{"content": {"parts": [{"text": '{"coaching": "ok"}'}]}}]} if status == 200 else {}
        return httpx.Response(status, json=body, headers=headers or {})

    return _RealClient(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    slept = []
    monkeypatch.setattr(base, "_sleep", slept.append)
    return slept


def test_retries_transient_status_then_succeeds(no_sleep):
    calls = []
    resp = base.post_with_retry(_client([503, 200], calls), "http://x", timeout=10)
    assert resp.status_code == 200 and len(calls) == 2 and len(no_sleep) == 1


def test_gives_up_after_retry_budget(no_sleep):
    calls = []
    resp = base.post_with_retry(_client([429, 429, 200], calls), "http://x", timeout=10)
    assert resp.status_code == 429 and len(calls) == 2  # one retry only


@pytest.mark.parametrize("status", [400, 401, 404])
def test_client_errors_are_not_retried(status):
    calls = []
    assert base.post_with_retry(_client([status], calls), "http://x", timeout=10).status_code == status
    assert len(calls) == 1


def test_no_retry_when_time_budget_is_too_small():
    calls = []
    assert base.post_with_retry(_client([503, 200], calls), "http://x", timeout=1).status_code == 503
    assert len(calls) == 1


def test_retry_after_header_is_honoured_but_capped(no_sleep):
    base.post_with_retry(_client([429, 200], [], {"Retry-After": "120"}), "http://x", timeout=10)
    assert no_sleep == [2.0]


def test_each_attempt_gets_only_the_remaining_budget():
    calls = []
    base.post_with_retry(_client([503, 200], calls), "http://x", timeout=10)
    timeouts = [r.extensions["timeout"]["read"] for r in calls]
    assert timeouts[0] <= 10 and timeouts[1] <= timeouts[0]


def test_gemini_provider_recovers_from_a_503(monkeypatch):
    calls = []
    monkeypatch.setattr(gemini.httpx, "Client", lambda **kw: _client([503, 200], calls))
    provider = gemini.GeminiProvider()
    provider._cfg = GeminiConfig(enabled=True, api_key="k", model="m")
    assert provider.generate("p", SessionSummary) == {"coaching": "ok"}
    assert len(calls) == 2


def test_gemini_key_is_sent_as_header_not_in_url(monkeypatch):
    calls = []
    monkeypatch.setattr(gemini.httpx, "Client", lambda **kw: _client([200], calls))
    provider = gemini.GeminiProvider()
    provider._cfg = GeminiConfig(enabled=True, api_key="secret-key", model="m")
    provider.generate("p", SessionSummary)
    assert "secret-key" not in str(calls[0].url)
    assert calls[0].headers["x-goog-api-key"] == "secret-key"
