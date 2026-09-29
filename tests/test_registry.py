from games.registry import GAMES, available_games


def test_titles_unique_and_callable():
    titles = [g.title for g in GAMES]
    assert len(titles) == len(set(titles))
    assert all(callable(g.play) for g in GAMES)


def test_levels_unlock_progressively():
    counts = [len(available_games(level)) for level in (1, 3, 6)]
    assert counts == sorted(counts) and counts[0] < counts[-1] == len(GAMES)


def test_games_in_a_category_are_contiguous():
    seen, last = set(), None
    for g in GAMES:
        if g.category != last:
            assert g.category not in seen, f"{g.category} split in the menu"
            seen.add(g.category)
            last = g.category
