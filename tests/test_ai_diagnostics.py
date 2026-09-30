import httpx
import pytest

from ai import check, router
from ai.config import GeminiConfig, OpenRouterConfig
from ai.providers import gemini, openrouter
from ai.providers.base import describe_http_error
from ai.schemas import SessionSummary

_RealClient = httpx.Client  # captured before tests patch httpx.Client


def _client(status, body=None):
    def handler(request):
        return httpx.Response(status, json=body if body is not None else {})
    return _RealClient(transport=httpx.MockTransport(handler))


def _gemini(monkeypatch, status, body=None, key="secret-key"):
    monkeypatch.setattr(gemini.httpx, "Client", lambda **kw: _client(status, body))
    p = gemini.GeminiProvider()
    p._cfg = GeminiConfig(enabled=True, api_key=key, model="m")
    return p


OK_BODY = {"candidates": [{"content": {"parts": [{"text": '{"coaching": "fine"}'}]}}]}


# ── last_error on the providers ──────────────────────────────────────────────

def test_http_errors_are_described_and_the_key_is_redacted(monkeypatch):
    p = _gemini(monkeypatch, 404, {"error": {"message": "model secret-key is gone"}})
    assert p.generate("p", SessionSummary) is None
    assert p.last_error == "HTTP 404: model *** is gone"


def test_openrouter_401_is_described(monkeypatch):
    monkeypatch.setattr(openrouter.httpx, "Client", lambda **kw: _client(401, {"error": {"message": "User not found."}}))
    p = openrouter.OpenRouterProvider()
    p._cfg = OpenRouterConfig(enabled=True, api_key="k", model="m")
    assert p.generate("p", SessionSummary) is None
    assert p.last_error == "HTTP 401: User not found."


def test_invalid_json_is_reported(monkeypatch):
    body = {"candidates": [{"content": {"parts": [{"text": "not json"}]}}]}
    p = _gemini(monkeypatch, 200, body)
    assert p.generate("p", SessionSummary) is None
    assert "not valid JSON" in (p.last_error or "")


def test_success_clears_the_previous_error(monkeypatch):
    p = _gemini(monkeypatch, 404, {"error": {"message": "x"}})
    p.generate("p", SessionSummary)
    assert p.last_error
    monkeypatch.setattr(gemini.httpx, "Client", lambda **kw: _client(200, OK_BODY))
    assert p.generate("p", SessionSummary) == {"coaching": "fine"}
    assert p.last_error is None


def test_describe_http_error_handles_non_json_bodies():
    resp = httpx.Response(502, text="<html>Bad gateway</html>")
    assert describe_http_error(resp) == "HTTP 502: <html>Bad gateway</html>"
    assert describe_http_error(httpx.Response(500, json={})) == "HTTP 500"


# ── router notice ────────────────────────────────────────────────────────────

class FailingProvider:
    def __init__(self, error):
        self.last_error = error

    def is_available(self):
        return True

    def generate(self, prompt, schema, timeout=0):
        return None


@pytest.fixture
def notices(monkeypatch):
    seen = []
    monkeypatch.setattr(router.ai_config, "ai_enabled", True)
    monkeypatch.setattr(router, "_warned", set())
    monkeypatch.setattr(router, "notify", seen.append)
    return seen


def _route_with(monkeypatch, gemini_error):
    monkeypatch.setattr(router, "_PROVIDERS", {"gemini": FailingProvider(gemini_error),
                                               "openrouter": FailingProvider(None)})
    return router.route(router.TaskType.HINT, "p", SessionSummary)


def test_config_errors_are_announced_once_per_provider(monkeypatch, notices):
    _route_with(monkeypatch, "HTTP 404: model gone")
    _route_with(monkeypatch, "HTTP 404: model gone")
    assert len(notices) == 1
    assert "gemini" in notices[0] and "HTTP 404" in notices[0] and "python -m ai.check" in notices[0]


@pytest.mark.parametrize("error", ["HTTP 429: quota", "HTTP 503: overloaded", "request timed out",
                                   "response was not valid JSON for the expected schema"])
def test_transient_errors_stay_quiet(monkeypatch, notices, error):
    _route_with(monkeypatch, error)
    assert notices == []


# ── python -m ai.check ───────────────────────────────────────────────────────

class FakeProvider:
    def __init__(self, result=None, error=None, available=True, api_key="k", model="m1"):
        self._result, self.last_error, self._available = result, error, available
        self._cfg = type("Cfg", (), {"api_key": api_key, "model": model})()

    def is_available(self):
        return self._available

    def generate(self, prompt, schema, timeout=0):
        return self._result


@pytest.fixture
def ai_on(monkeypatch):
    monkeypatch.setattr(check.ai_config, "ai_enabled", True)


def _run(providers):
    lines = []
    code = check.run(providers, out=lines.append)
    return code, "\n".join(lines)


def test_check_passes_when_any_provider_works(ai_on):
    code, out = _run({"a": FakeProvider({"coaching": "x"}), "b": FakeProvider(error="HTTP 500: boom")})
    assert code == 0 and "PASS  a" in out and "FAIL  b" in out and "HTTP 500" in out


def test_check_fails_when_nothing_works(ai_on):
    code, out = _run({"a": FakeProvider(error="HTTP 500: boom")})
    assert code == 1 and "no provider works" in out


def test_check_explains_missing_keys_without_calling(ai_on):
    code, out = _run({"a": FakeProvider(available=False, api_key="")})
    assert code == 1 and "no API key set" in out


def test_check_gives_key_advice_on_401(ai_on):
    _, out = _run({"openrouter": FakeProvider(error="HTTP 401: User not found.")})
    assert "OPENROUTER_API_KEY" in out and "rejected" in out


def test_check_suggests_models_on_404(ai_on, monkeypatch):
    monkeypatch.setattr(check, "suggest_gemini_models", lambda key: ["gemini-9-flash"])
    _, out = _run({"gemini": FakeProvider(error="HTTP 404: gone", model="old")})
    assert "GEMINI_MODEL" in out and "gemini-9-flash" in out and "'old'" in out


def test_check_reports_when_ai_is_disabled(monkeypatch):
    monkeypatch.setattr(check.ai_config, "ai_enabled", False)
    code, out = _run({"a": FakeProvider({"coaching": "x"})})
    assert code == 1 and "disabled" in out


def test_check_never_crashes_on_a_provider_exception(ai_on):
    class Exploding(FakeProvider):
        def generate(self, *a, **k):
            raise RuntimeError("kaput")

    code, out = _run({"a": Exploding()})
    assert code == 1 and "RuntimeError: kaput" in out


def test_model_suggestions_filter_out_non_text_models(monkeypatch):
    listing = {"models": [
        {"name": "models/gemini-3-flash", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-3-flash-tts", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-3-pro", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-embed-flash", "supportedGenerationMethods": ["embedContent"]},
    ]}
    monkeypatch.setattr(check.httpx, "get", lambda *a, **k: httpx.Response(200, json=listing, request=httpx.Request("GET", "http://x")))
    assert check.suggest_gemini_models("k") == ["gemini-3-flash"]
    monkeypatch.setattr(check.httpx, "get", lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("down")))
    assert check.suggest_gemini_models("k") == []
