from core.profile_manager import ProfileManager


def test_login_creates_user_once(db):
    p = ProfileManager(db)
    assert p.login("kim") and p.current_user.level == 1
    first_id = p.current_user.id
    assert p.login("KIM") and p.current_user.id == first_id


def test_xp_and_level_progression(profile):
    profile.add_xp(99)
    assert profile.current_user.level == 1
    profile.add_xp(1)
    assert (profile.current_user.xp, profile.current_user.level) == (100, 2)
    assert profile.db.get_user("tester").level == 2


def test_save_game_result_awards_xp_and_fires_hook(profile):
    calls = []
    profile.on_result = lambda: calls.append(1)
    profile.save_game_result("g", 120, 0.9, 500.0)
    assert profile.current_user.level == 2
    assert len(profile.db.get_user_stats(profile.current_user.id)) == 1
    assert calls == [1]


def test_failing_hook_does_not_break_saving(profile):
    def boom():
        raise RuntimeError("x")

    profile.on_result = boom
    profile.save_game_result("g", 10, 1.0, 1.0)
    assert profile.current_user.xp == 10


def test_refresh_reloads_from_db(profile):
    profile.db.update_user_xp(profile.current_user.id, 250, 3)
    profile.refresh()
    assert (profile.current_user.xp, profile.current_user.level) == (250, 3)
