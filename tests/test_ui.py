"""The shared result screen: wrong answers wait for Enter, right ones pause briefly."""

from games.engine import ui


def _patch(monkeypatch):
    calls = {"input": [], "sleep": []}
    monkeypatch.setattr(ui, "read_line", lambda prompt="": calls["input"].append(prompt) or "")
    monkeypatch.setattr(ui, "sleep", calls["sleep"].append)
    return calls


def test_wrong_answer_shows_both_and_waits_for_enter(monkeypatch, capsys):
    calls = _patch(monkeypatch)
    ui.show_result(False, "123", "124")
    out = capsys.readouterr().out
    assert "123" in out and "124" in out
    assert len(calls["input"]) == 1 and calls["sleep"] == []


def test_correct_answer_sleeps_one_second_without_input(monkeypatch, capsys):
    calls = _patch(monkeypatch)
    ui.show_result(True, "123", "123")
    assert "Correct" in capsys.readouterr().out
    assert calls["sleep"] == [1.0] and calls["input"] == []


def test_wait_overrides_the_default(monkeypatch):
    calls = _patch(monkeypatch)
    ui.show_result(True, "1", "1", wait=True)
    ui.show_result(False, "1", "2", wait=False)
    assert len(calls["input"]) == 1 and calls["sleep"] == [1.0]


def test_read_nonblank_gives_up_after_max_tries(monkeypatch):
    calls = []
    monkeypatch.setattr(ui, "read_line", lambda prompt="": calls.append(prompt) or "")
    assert ui.read_nonblank("prompt: ", max_tries=5) is None
    assert len(calls) == 5


def test_read_nonblank_returns_first_nonblank(monkeypatch):
    inputs = ["", "   ", "answer", "never reached"]
    monkeypatch.setattr(ui, "read_line", lambda prompt="": inputs.pop(0))
    assert ui.read_nonblank("prompt: ") == "answer"
    assert inputs == ["never reached"]


def test_mental_math_blank_input_terminates(monkeypatch, profile):
    import builtins
    import time
    from games.math import mental_math

    monkeypatch.setattr(builtins, "input", lambda *args, **kwargs: "")
    t0 = time.monotonic()
    mental_math.play_mental_math(profile)
    assert time.monotonic() - t0 < 5.0
    user = profile.require_user()
    stats = profile.db.get_user_stats(user.id, limit=1)
    assert len(stats) == 1
    assert stats[0].accuracy == 0.0
