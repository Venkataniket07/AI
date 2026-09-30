"""Regression tests for the AI failures seen in a real session (see .log/ai.log, 2026-09-30):

* Gemini and nemotron spent the whole 512-token reply cap on hidden reasoning, so the coaching reply
  was cut off and rejected ("returned None or invalid data").
* gemini-2.5-flash's free tier allows only 20 requests/day; after that every call was a 429.
"""

import copy
import json

import httpx
import pytest

from ai import check, router
from ai.config import GeminiConfig, OpenRouterConfig
from ai.providers import base, gemini, openrouter
from ai.providers.base import extract_json_object, is_daily_quota_error, parse_model_json
from ai.schemas import SessionSummary

_RealClient = httpx.Client  # captured before tests patch httpx.Client


# ── response shapes (modelled on the real logged responses) ──────────────────

def gemini_ok(text='{"coaching": "Nice work!"}', thoughts=0):
    return 200, {"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}],
                 "usageMetadata": {"thoughtsTokenCount": thoughts, "candidatesTokenCount": 12}}


def gemini_truncated():
    """What gemini-2.5-flash returned: 489 of 512 tokens spent thinking, 8 tokens of answer."""
    return 200, {"candidates": [{"content": {"parts": [{"text": '{\n  "coaching": "'}]}, "finishReason": "MAX_TOKENS"}],
                 "usageMetadata": {"thoughtsTokenCount": 489, "candidatesTokenCount": 8}}


def quota_429(per):
    quota_id = f"GenerateRequests{per}PerProjectPerModel-FreeTier"
    return 429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "You exceeded your current quota.",
                           "details": [{"@type": "type.googleapis.com/google.rpc.QuotaFailure",
                                        "violations": [{"quotaId": quota_id, "quotaValue": "20"}]}]}}


def daily_429():
    return quota_429("PerDay")


def minute_429():
    return quota_429("PerMinute")


class FakeGemini:
    """Programmable Gemini endpoint. `script` maps model name -> list of (status, body) replies."""

    def __init__(self, script):
        self.script = {m: list(replies) for m, replies in script.items()}
        self.requests = []  # (model, request json)

    def client(self, **kwargs):
        def handler(request):
            model = request.url.path.split("/models/")[1].split(":")[0]
            self.requests.append((model, json.loads(request.content)))
            status, body = self.script[model].pop(0) if len(self.script[model]) > 1 else self.script[model][0]
            return httpx.Response(status, json=body)
        return _RealClient(transport=httpx.MockTransport(handler))

    def models_called(self):
        return [m for m, _ in self.requests]


def make_gemini(monkeypatch, script, model):
    fake = FakeGemini(script)
    monkeypatch.setattr(gemini.httpx, "Client", fake.client)
    provider = gemini.GeminiProvider()
    provider._cfg = GeminiConfig(enabled=True, api_key="secret-key", model=model)
    return provider, fake


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(base, "_sleep", lambda s: None)


# ── JSON extraction ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ('{"coaching": "hi"}', '{"coaching": "hi"}'),
    ('Sure! Here it is: {"coaching": "hi"} Hope that helps.', '{"coaching": "hi"}'),
    ('We need JSON with a {field} named coaching.\n{"coaching": "hi"}', '{"coaching": "hi"}'),
    ('{"coaching": "brace } inside { a string"}', '{"coaching": "brace } inside { a string"}'),
    ('{"coaching": "quote \\" and } here"}', '{"coaching": "quote \\" and } here"}'),
    ('{"a": {"b": 1}} trailing', '{"a": {"b": 1}}'),
])
def test_extract_json_object_finds_the_object(text, expected):
    assert extract_json_object(text) == expected


@pytest.mark.parametrize("text", ["", "no braces at all", '{"coaching": "cut off', '{\n  "coaching": "', "{not json}"])
def test_extract_json_object_returns_none_when_there_is_no_complete_object(text):
    assert extract_json_object(text) is None


def test_parse_accepts_prose_wrapped_json_but_still_validates_the_schema():
    assert parse_model_json('Here you go:\n{"coaching": "ok"}', SessionSummary, "T") == {"coaching": "ok"}
    assert parse_model_json('Here you go:\n{"wrong": "field"}', SessionSummary, "T") is None
    assert parse_model_json('The answer needs {"coaching": ', SessionSummary, "T") is None


# ── Gemini: reply budget and thinking ────────────────────────────────────────

def test_truncated_reply_is_reported_as_cut_off_with_usage(monkeypatch):
    provider, _ = make_gemini(monkeypatch, {"m": [gemini_truncated()]}, "m")
    assert provider.generate("p", SessionSummary) is None
    assert "cut off" in provider.last_error and "489" in provider.last_error
    assert provider.last_usage == {"finish_reason": "MAX_TOKENS", "thinking_tokens": 489, "output_tokens": 8}


def test_reply_budget_is_large_and_thinking_is_off_for_flash_models(monkeypatch):
    provider, fake = make_gemini(monkeypatch, {"gemini-3.6-flash": [gemini_ok()]}, "gemini-3.6-flash")
    assert provider.generate("p", SessionSummary) == {"coaching": "Nice work!"}
    config = fake.requests[0][1]["generationConfig"]
    assert config["maxOutputTokens"] == base.MAX_OUTPUT_TOKENS >= 2048
    assert config["thinkingConfig"] == {"thinkingBudget": 0}
    assert provider.last_model == "gemini-3.6-flash" and provider.last_error is None


@pytest.mark.parametrize("model", ["gemini-2.5-pro", "gemma-4-31b-it"])
def test_thinking_setting_is_not_sent_to_models_that_cannot_disable_it(monkeypatch, model):
    provider, fake = make_gemini(monkeypatch, {model: [gemini_ok()]}, model)
    provider.generate("p", SessionSummary)
    assert "thinkingConfig" not in fake.requests[0][1]["generationConfig"]


def test_model_that_rejects_the_thinking_setting_is_retried_without_it_and_remembered(monkeypatch):
    provider, fake = make_gemini(monkeypatch, {"gemini-x-flash": [
        (400, {"error": {"message": "Thinking budget 0 is invalid for this model."}}), gemini_ok()]}, "gemini-x-flash")
    assert provider.generate("p", SessionSummary) == {"coaching": "Nice work!"}
    assert "thinkingConfig" in fake.requests[0][1]["generationConfig"]
    assert "thinkingConfig" not in fake.requests[1][1]["generationConfig"]
    provider.generate("p", SessionSummary)
    assert "thinkingConfig" not in fake.requests[2][1]["generationConfig"]  # remembered, no wasted request


def test_reply_with_no_content_is_reported(monkeypatch):
    blocked = (200, {"candidates": [{"finishReason": "SAFETY"}]})
    provider, _ = make_gemini(monkeypatch, {"m": [blocked]}, "m")
    assert provider.generate("p", SessionSummary) is None
    assert "no content" in provider.last_error and "SAFETY" in provider.last_error


def test_multi_part_replies_are_joined(monkeypatch):
    body = (200, {"candidates": [{"content": {"parts": [{"text": '{"coaching": '}, {"text": '"joined"}'}]},
                                  "finishReason": "STOP"}]})
    provider, _ = make_gemini(monkeypatch, {"m": [body]}, "m")
    assert provider.generate("p", SessionSummary) == {"coaching": "joined"}


# ── Gemini: several models and the daily quota ───────────────────────────────

def test_daily_quota_moves_on_to_the_next_model(monkeypatch):
    provider, fake = make_gemini(monkeypatch, {"a": [daily_429()], "b": [gemini_ok()]}, "a,b")
    assert provider.generate("p", SessionSummary) == {"coaching": "Nice work!"}
    assert fake.models_called() == ["a", "b"] and provider.last_model == "b"


def test_exhausted_model_is_not_asked_again(monkeypatch):
    provider, fake = make_gemini(monkeypatch, {"a": [daily_429()], "b": [gemini_ok()]}, "a,b")
    provider.generate("p", SessionSummary)
    provider.generate("p", SessionSummary)
    provider.generate("p", SessionSummary)
    assert fake.models_called() == ["a", "b", "b", "b"]  # 'a' was asked exactly once


def test_exhausted_model_is_retried_after_the_skip_window(monkeypatch):
    provider, fake = make_gemini(monkeypatch, {"a": [daily_429(), gemini_ok()], "b": [gemini_ok('{"coaching": "from b"}')]}, "a,b")
    provider.generate("p", SessionSummary)
    provider._exhausted["a"] = 0  # window over
    assert provider.generate("p", SessionSummary) == {"coaching": "Nice work!"}
    assert fake.models_called() == ["a", "b", "a"]


def test_per_minute_limit_tries_the_next_model_but_does_not_mark_the_first_exhausted(monkeypatch):
    # 'a' keeps answering 429 (per minute); a per-minute limit is transient, so it is retried once
    provider, fake = make_gemini(monkeypatch, {"a": [minute_429()], "b": [gemini_ok('{"coaching": "from b"}')]}, "a,b")
    assert provider.generate("p", SessionSummary) == {"coaching": "from b"}
    assert provider._exhausted == {}
    assert provider.generate("p", SessionSummary) == {"coaching": "from b"}
    assert fake.models_called() == ["a", "a", "b", "a", "a", "b"]  # 'a' is still tried first on the next call


def test_all_models_exhausted_gives_one_clear_message(monkeypatch):
    provider, _ = make_gemini(monkeypatch, {"a": [daily_429()], "b": [daily_429()]}, "a,b")
    assert provider.generate("p", SessionSummary) is None
    assert provider.last_error.startswith("HTTP 429: daily free quota used up for a, b")
    assert provider.generate("p", SessionSummary) is None  # second call: both skipped without requests
    assert provider.last_error.startswith("HTTP 429: daily free quota used up for a, b")


def test_a_bad_model_name_is_reported_even_if_a_later_model_is_only_out_of_quota(monkeypatch):
    provider, _ = make_gemini(monkeypatch, {"gone": [(404, {"error": {"message": "model not found"}})],
                                            "b": [daily_429()]}, "gone,b")
    assert provider.generate("p", SessionSummary) is None
    assert provider.last_error == "HTTP 404: model not found"


def test_a_working_later_model_rescues_a_broken_first_one(monkeypatch):
    provider, fake = make_gemini(monkeypatch, {"gone": [(404, {"error": {"message": "nope"}})], "b": [gemini_ok()]}, "gone,b")
    assert provider.generate("p", SessionSummary) == {"coaching": "Nice work!"}


def test_single_model_error_text_is_unchanged(monkeypatch):
    provider, _ = make_gemini(monkeypatch, {"m": [(404, {"error": {"message": "model gone secret-key"}})]}, "m")
    provider.generate("p", SessionSummary)
    assert provider.last_error == "HTTP 404: model gone ***"


def test_daily_quota_429_is_not_retried_but_a_minute_limit_is(monkeypatch):
    fake = FakeGemini({"m": [daily_429()]})
    with _RealClient(transport=httpx.MockTransport(lambda r: httpx.Response(*[daily_429()[0]], json=daily_429()[1]))) as c:
        resp = base.post_with_retry(c, "http://x", timeout=10)
    assert is_daily_quota_error(resp)
    assert not is_daily_quota_error(httpx.Response(429, json=minute_429()[1]))
    assert not is_daily_quota_error(httpx.Response(500, json=daily_429()[1]))
    provider, fake = make_gemini(monkeypatch, {"m": [daily_429()]}, "m")
    provider.generate("p", SessionSummary)
    assert len(fake.requests) == 1  # no pointless retry


# ── OpenRouter ───────────────────────────────────────────────────────────────

def make_openrouter(monkeypatch, status, body, seen=None):
    def handler(request):
        if seen is not None:
            seen.append(json.loads(request.content))
        return httpx.Response(status, json=body)
    monkeypatch.setattr(openrouter.httpx, "Client", lambda **kw: _RealClient(transport=httpx.MockTransport(handler)))
    provider = openrouter.OpenRouterProvider()
    provider._cfg = OpenRouterConfig(enabled=True, api_key="or-key", model="nvidia/x:free")
    return provider


def or_body(content, finish="stop", reasoning=212, reasoning_text=None):
    message = {"content": content}
    if reasoning_text:
        message["reasoning"] = reasoning_text
    return {"choices": [{"message": message, "finish_reason": finish}],
            "usage": {"completion_tokens": 300, "completion_tokens_details": {"reasoning_tokens": reasoning}}}


def test_openrouter_uses_a_large_reply_budget(monkeypatch):
    seen = []
    provider = make_openrouter(monkeypatch, 200, or_body('{"coaching": "ok"}'), seen)
    assert provider.generate("p", SessionSummary) == {"coaching": "ok"}
    assert seen[0]["max_tokens"] == base.MAX_OUTPUT_TOKENS >= 2048
    assert provider.last_usage == {"finish_reason": "stop", "thinking_tokens": 212, "output_tokens": 300}
    assert provider.last_model == "nvidia/x:free"


def test_openrouter_length_finish_is_reported_as_cut_off(monkeypatch):
    """Real case: nemotron used 419-500 of 512 tokens on reasoning and was cut off."""
    provider = make_openrouter(monkeypatch, 200, or_body('{\n  "coaching": "You showed strong', finish="length", reasoning=419))
    assert provider.generate("p", SessionSummary) is None
    assert "cut off" in provider.last_error and "419" in provider.last_error


def test_openrouter_never_uses_the_reasoning_field_as_the_answer(monkeypatch):
    body = or_body("", reasoning_text='We need JSON. {"coaching": "this came from the reasoning"}')
    provider = make_openrouter(monkeypatch, 200, body)
    assert provider.generate("p", SessionSummary) is None
    assert "no content" in provider.last_error


def test_openrouter_extracts_json_from_prose(monkeypatch):
    provider = make_openrouter(monkeypatch, 200, or_body('Sure! {"coaching": "wrapped"} Anything else?'))
    assert provider.generate("p", SessionSummary) == {"coaching": "wrapped"}


def test_openrouter_null_content_is_handled(monkeypatch):
    provider = make_openrouter(monkeypatch, 200, {"choices": [{"message": {"content": None}, "finish_reason": "stop"}]})
    assert provider.generate("p", SessionSummary) is None
    assert "no content" in provider.last_error


# ── router notice ────────────────────────────────────────────────────────────

class QuotaProvider:
    last_error = "HTTP 429: daily free quota used up for a, b (it resets about midnight Pacific time)"

    def is_available(self):
        return True

    def generate(self, prompt, schema, timeout=0):
        return None


def test_router_announces_a_used_up_daily_quota_once(monkeypatch):
    seen = []
    monkeypatch.setattr(router.ai_config, "ai_enabled", True)
    monkeypatch.setattr(router, "_warned", set())
    monkeypatch.setattr(router, "notify", seen.append)
    monkeypatch.setattr(router, "_PROVIDERS", {"gemini": QuotaProvider(), "openrouter": QuotaProvider()})
    router.route(router.TaskType.HINT, "p", SessionSummary)
    router.route(router.TaskType.HINT, "p", SessionSummary)
    assert len(seen) == 2  # once per provider, not once per call
    assert all("daily free quota used up" in m for m in seen)


# ── ai.check ─────────────────────────────────────────────────────────────────

class ModelListProvider:
    """Stands in for GeminiProvider: several models; only the ones in `working` succeed."""

    def __init__(self, models, working, log):
        self._cfg = GeminiConfig(enabled=True, api_key="k", model=",".join(models))
        self.working, self.log = set(working), log
        self.last_error, self.last_usage = None, {}

    def _models(self):
        return [m.strip() for m in self._cfg.model.split(",")]

    def is_available(self):
        return True

    def generate(self, prompt, schema, timeout=0):
        self.log.append((self._cfg.model, prompt))
        if self._cfg.model in self.working:
            self.last_usage = {"finish_reason": "STOP", "thinking_tokens": 0, "output_tokens": 42}
            return {"ok": True}
        self.last_error = "HTTP 429: daily free quota used up for " + self._cfg.model
        return None


@pytest.fixture
def ai_on(monkeypatch):
    monkeypatch.setattr(check.ai_config, "ai_enabled", True)


def run_check(providers, **kw):
    lines = []
    code = check.run(providers, out=lines.append, **kw)
    return code, "\n".join(lines)


def test_check_stops_at_the_first_passing_model_by_default(ai_on):
    log = []
    code, out = run_check({"gemini": ModelListProvider(["a", "b", "c"], ["a", "b", "c"], log)})
    assert [m for m, _ in log] == ["a"]  # one request only: free quotas are small
    assert code == 0 and "not tested" in out and "finish=STOP" in out and "output=42" in out


def test_check_moves_on_to_the_next_model_when_one_fails(ai_on):
    log = []
    code, out = run_check({"gemini": ModelListProvider(["a", "b"], ["b"], log)})
    assert [m for m, _ in log] == ["a", "b"]
    assert code == 0 and "FAIL  gemini      model=a" in out and "PASS  gemini      model=b" in out
    assert "daily free quota" in out and "GEMINI_MODEL" in out  # advice for the failed model


def test_check_all_models_tests_every_model(ai_on):
    log = []
    run_check({"gemini": ModelListProvider(["a", "b", "c"], ["a", "b", "c"], log)}, all_models=True)
    assert [m for m, _ in log] == ["a", "b", "c"]


def test_check_uses_the_real_coaching_prompt_not_a_toy_one(ai_on):
    log = []
    run_check({"gemini": ModelListProvider(["a"], ["a"], log)})
    prompt = log[0][1]
    assert "mental_math" in prompt and "anagrams" in prompt and "accuracy=" in prompt
    assert prompt != check.CHECK_PROMPT


def test_check_full_runs_every_task_prompt(ai_on):
    assert [name for name, _, _ in check.build_tasks(full=False)] == ["session_summary"]
    assert [name for name, _, _ in check.build_tasks(full=True)] == ["session_summary", "stats_analysis", "hint", "explain"]
    log = []
    run_check({"gemini": ModelListProvider(["a"], ["a"], log)}, full=True)
    assert len(log) == 4


def test_check_advice_for_cut_off_and_quota_errors():
    provider = ModelListProvider(["a"], [], [])
    assert "reply budget" in " ".join(check.advice_for("gemini", "reply cut off (MAX_TOKENS; 489 thinking tokens used)", provider))
    assert "comma-separated" in " ".join(check.advice_for("gemini", "HTTP 429: daily free quota used up for a", provider))


# ── coaching that arrives late ───────────────────────────────────────────────

def test_late_coaching_is_kept_and_shown_at_the_next_menu(profile, capsys):
    import main
    from concurrent.futures import Future

    coach = main.CoachingPrefetcher(profile)
    coach.pending = future = Future()

    coach.show(wait=0)  # not ready: nothing printed, nothing lost
    assert capsys.readouterr().out == "" and coach.pending is future

    future.set_result("You improved a lot.")
    coach.show(wait=0, late=True)
    out = capsys.readouterr().out
    assert "Coach (about your last game): You improved a lot." in out and coach.pending is None


def test_failed_coaching_is_dropped_quietly(profile, capsys):
    import main
    from concurrent.futures import Future

    coach = main.CoachingPrefetcher(profile)
    coach.pending = future = Future()
    future.set_exception(RuntimeError("provider exploded"))
    coach.show(wait=0)
    assert capsys.readouterr().out == "" and coach.pending is None


def test_copy_of_provider_shares_learned_quota_state(monkeypatch):
    """ai.check tests models through per-model copies; what one copy learns must not be lost."""
    provider, _ = make_gemini(monkeypatch, {"a": [daily_429()]}, "a")
    clone = copy.copy(provider)
    clone.generate("p", SessionSummary)
    assert "a" in provider._exhausted


# ── OpenRouter: errors reported inside an HTTP 200 body ──────────────────────

UPSTREAM_OVERLOADED = {"id": "gen-1", "error": {"message": "Upstream error from Nvidia: Service temporarily overloaded",
                                                "code": 503, "metadata": {"error_type": "provider_overloaded"}}}


def make_openrouter_sequence(monkeypatch, bodies):
    """OpenRouter endpoint that always answers HTTP 200 with the next body in `bodies`."""
    queue, calls = list(bodies), []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json=queue.pop(0) if len(queue) > 1 else queue[0])

    monkeypatch.setattr(openrouter.httpx, "Client", lambda **kw: _RealClient(transport=httpx.MockTransport(handler)))
    provider = openrouter.OpenRouterProvider()
    provider._cfg = OpenRouterConfig(enabled=True, api_key="or-key", model="nvidia/x:free")
    return provider, calls


def test_openrouter_upstream_overload_in_a_200_body_is_retried_once_and_succeeds(monkeypatch):
    provider, calls = make_openrouter_sequence(monkeypatch, [UPSTREAM_OVERLOADED, or_body('{"coaching": "second try"}')])
    assert provider.generate("p", SessionSummary, timeout=20) == {"coaching": "second try"}
    assert len(calls) == 2 and provider.last_error is None


def test_openrouter_persistent_upstream_error_reports_the_real_reason(monkeypatch):
    provider, calls = make_openrouter_sequence(monkeypatch, [UPSTREAM_OVERLOADED])
    assert provider.generate("p", SessionSummary, timeout=20) is None
    assert provider.last_error == "HTTP 503: Upstream error from Nvidia: Service temporarily overloaded"
    assert len(calls) == 2  # one retry, then give up (not "no content returned")


def test_openrouter_non_transient_error_in_a_200_body_is_not_retried(monkeypatch):
    body = {"error": {"message": "No auth credentials found for or-key", "code": 401}}
    provider, calls = make_openrouter_sequence(monkeypatch, [body])
    assert provider.generate("p", SessionSummary, timeout=20) is None
    assert provider.last_error == "HTTP 401: No auth credentials found for ***"  # key redacted
    assert len(calls) == 1


def test_openrouter_error_without_a_code_and_a_null_error_field(monkeypatch):
    provider, _ = make_openrouter_sequence(monkeypatch, [{"error": {"message": "something odd"}}])
    assert provider.generate("p", SessionSummary, timeout=20) is None
    assert provider.last_error == "provider error: something odd"
    provider, _ = make_openrouter_sequence(monkeypatch, [{**or_body('{"coaching": "fine"}'), "error": None}])
    assert provider.generate("p", SessionSummary, timeout=20) == {"coaching": "fine"}


def test_router_announces_an_upstream_401_in_a_200_body(monkeypatch):
    seen = []
    monkeypatch.setattr(router.ai_config, "ai_enabled", True)
    monkeypatch.setattr(router, "_warned", set())
    monkeypatch.setattr(router, "notify", seen.append)
    provider, _ = make_openrouter_sequence(monkeypatch, [{"error": {"message": "bad key", "code": 401}}])
    monkeypatch.setattr(router, "_PROVIDERS", {"gemini": type("Off", (), {"is_available": lambda s: False})(),
                                               "openrouter": provider})
    router.route(router.TaskType.HINT, "p", SessionSummary)
    assert len(seen) == 1 and "openrouter" in seen[0] and "HTTP 401" in seen[0]
