from core.profile_manager import ProfileManager


def test_login_creates_user_once(db):
    p = ProfileManager(db)
    assert p.login("kim") and p.require_user().level == 1
    first_id = p.require_user().id
    assert p.login("KIM") and p.require_user().id == first_id


def test_xp_and_level_progression(profile):
    profile.add_xp(99)
    assert profile.require_user().level == 1
    profile.add_xp(1)
    assert (profile.require_user().xp, profile.require_user().level) == (100, 2)
    assert profile.db.get_user("tester").level == 2  # type: ignore[union-attr]
    profile.add_xp(199)   # 299 total: level 3 needs 300
    assert profile.require_user().level == 2
    profile.add_xp(1)
    assert profile.require_user().level == 3


def test_an_existing_higher_level_is_never_lowered(profile):
    profile.db.update_user_xp(profile.require_user().id, 600, 7)  # level earned under the old 100-XP rule
    profile.refresh()
    profile.add_xp(10)
    assert (profile.require_user().xp, profile.require_user().level) == (610, 7)


def test_save_game_result_awards_xp_and_fires_hook(profile):
    calls = []
    profile.on_result = lambda: calls.append(1)
    profile.save_game_result("g", 120, 0.9, 500.0)
    assert profile.require_user().level == 2
    assert len(profile.db.get_user_stats(profile.require_user().id)) == 1
    assert calls == [1]


def test_failing_hook_does_not_break_saving(profile):
    def boom():
        raise RuntimeError("x")

    profile.on_result = boom
    profile.save_game_result("g", 10, 1.0, 1.0)
    assert profile.require_user().xp == 10


def test_refresh_reloads_from_db(profile):
    profile.db.update_user_xp(profile.require_user().id, 250, 3)
    profile.refresh()
    assert (profile.require_user().xp, profile.require_user().level) == (250, 3)
