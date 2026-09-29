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


def test_ctrl_c_during_a_game_returns_to_menu_without_saving(db, monkeypatch, capsys):
    from games.registry import Game

    def interrupted(profile):
        raise KeyboardInterrupt

    monkeypatch.setattr(main, "load_dotenv", lambda path: None)
    monkeypatch.setattr(main, "init_loggers", lambda: None)
    monkeypatch.setattr(main, "DBManager", lambda: db)
    monkeypatch.setattr(main, "_ai_enabled", lambda: False)
    monkeypatch.setattr(main, "available_games", lambda level: [Game("Boom", interrupted, 1, "X")])
    answers = iter(["kim", "1", "3"])  # login, play the game, exit (menu: 1 game, 2 stats, 3 exit)
    monkeypatch.setattr("builtins.input", lambda *a: next(answers))

    main.main()

    out = capsys.readouterr().out
    assert "Game cancelled" in out and "Goodbye!" in out
    assert db.get_user_stats(db.get_user("kim").id) == []
