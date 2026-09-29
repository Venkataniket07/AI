from games.reasoning import puzzle_grid, rankings


def test_ranking_puzzles_have_one_solution_and_no_redundant_clue():
    for _ in range(40):
        texts, answer = rankings.generate_ranking_puzzle()
        items = sorted(answer)
        clues = _parse_ranking(texts)
        assert rankings._count_solutions(items, clues) == 1
        assert all(rankings._satisfies(answer, c) for c in clues)
        for i in range(len(clues)):  # every clue is needed
            assert rankings._count_solutions(items, clues[:i] + clues[i + 1:]) > 1


def _parse_ranking(texts):
    clues = []
    for t in texts:
        if t.endswith("ranks at the top."):
            clues.append(("top", t[0], None))
        elif t.endswith("ranks at the bottom."):
            clues.append(("bottom", t[0], None))
        else:
            clues.append(("above", t[0], t.split(" ranks above ")[1][0]))
    return clues


def test_grid_puzzles_have_one_solution_and_no_redundant_clue():
    for _ in range(25):
        solution, texts = puzzle_grid.generate_grid_puzzle()
        assert len(texts) >= 3
        colors = {p: solution[p]["Color"] for p in puzzle_grid.PERSONS}
        pets = {p: solution[p]["Pet"] for p in puzzle_grid.PERSONS}
        assert sorted(colors.values()) == sorted(puzzle_grid.COLORS)
        assert sorted(pets.values()) == sorted(puzzle_grid.PETS)
        # the generator's own clue tuples must hold for the stored solution and identify it uniquely
        pool_clues = _regenerate_clues(texts)
        assert puzzle_grid._count_solutions(pool_clues) == 1
        assert all(puzzle_grid._holds(c, colors, pets) for c in pool_clues)
        for i in range(len(pool_clues)):
            assert puzzle_grid._count_solutions(pool_clues[:i] + pool_clues[i + 1:]) > 1


def _regenerate_clues(texts):
    """Invert puzzle_grid._clue_text for the tests."""
    clues = []
    for t in texts:
        words = t.rstrip(".").split()
        if t.startswith("The ") and " house owner has a " in t:
            clues.append(("owner_has", words[1], words[-1]))
        elif " lives in the " in t:
            clues.append(("lives_in", words[0], words[4]))
        elif " owns the " in t:
            clues.append(("owns", words[0], words[-1]))
        elif " owner is not " in t:
            clues.append(("not_pet", words[1], words[-1]))
        else:
            clues.append(("not_color", words[0], words[6]))
    return clues
