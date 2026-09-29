import main
from ai.services import summary_service


def test_coaching_is_prefetched_when_result_saved_and_shown_after_game(profile, monkeypatch, capsys):
    monkeypatch.setattr(main, "_ai_enabled", lambda: True)
    monkeypatch.setattr(summary_service, "summarize_session", lambda *a, **k: "Nice work!")
    coach = main.CoachingPrefetcher(profile)

    profile.save_game_result("g", 10, 1.0, 100.0)  # fires the hook -> background request
    coach.show()

    assert "Coach: Nice work!" in capsys.readouterr().out
    coach.show()  # already consumed: prints nothing
    assert capsys.readouterr().out == ""


def test_no_coaching_when_ai_disabled(profile, monkeypatch, capsys):
    monkeypatch.setattr(main, "_ai_enabled", lambda: False)
    coach = main.CoachingPrefetcher(profile)
    profile.save_game_result("g", 10, 1.0, 100.0)
    coach.show()
    assert capsys.readouterr().out == ""


def test_coaching_failure_is_silent(profile, monkeypatch, capsys):
    monkeypatch.setattr(main, "_ai_enabled", lambda: True)

    def boom(*a, **k):
        raise RuntimeError("provider down")

    monkeypatch.setattr(summary_service, "summarize_session", boom)
    coach = main.CoachingPrefetcher(profile)
    profile.save_game_result("g", 10, 1.0, 100.0)
    coach.show()
    assert capsys.readouterr().out == ""
