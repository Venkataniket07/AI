import pytest
from pydantic import BaseModel

from ai import router
from ai.router import TaskType, route


class Out(BaseModel):
    text: str


class FakeProvider:
    def __init__(self, result=None, available=True, error=None):
        self.result, self.available, self.error, self.calls = result, available, error, 0

    def is_available(self):
        return self.available

    def generate(self, prompt, schema, timeout=0):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


@pytest.fixture
def providers(monkeypatch):
    monkeypatch.setattr(router.ai_config, "ai_enabled", True)
    table = {}
    monkeypatch.setattr(router, "_PROVIDERS", table)
    return table


def test_first_provider_wins(providers):
    providers["gemini"] = FakeProvider({"text": "g"})
    providers["openrouter"] = FakeProvider({"text": "o"})
    assert route(TaskType.HINT, "p", Out) == {"text": "g"}
    assert providers["openrouter"].calls == 0


@pytest.mark.parametrize("first", [
    FakeProvider(None),
    FakeProvider(error=RuntimeError("boom")),
    FakeProvider({"text": "x"}, available=False),
])
def test_falls_back_to_next_provider(providers, first):
    providers["gemini"] = first
    providers["openrouter"] = FakeProvider({"text": "o"})
    assert route(TaskType.HINT, "p", Out) == {"text": "o"}


def test_all_failing_returns_none(providers):
    providers["gemini"] = FakeProvider(None)
    providers["openrouter"] = FakeProvider(None)
    assert route(TaskType.HINT, "p", Out) is None


def test_disabled_ai_skips_providers(providers, monkeypatch):
    monkeypatch.setattr(router.ai_config, "ai_enabled", False)
    providers["gemini"] = FakeProvider({"text": "g"})
    assert route(TaskType.HINT, "p", Out) is None
    assert providers["gemini"].calls == 0
