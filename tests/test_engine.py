import random

import pytest

from games.engine.puzzle import Puzzle, PuzzleError
from games.engine.variety import Variety
from games.engine.verify import assert_unique, count_solutions, drop_redundant
from games.reasoning import rankings, seating


def _puzzle(key, bucket="", family=None, answer=None) -> Puzzle:
    return Puzzle(
        game_id="stub",
        lines=("line",),
        question="?",
        answer=answer or key,
        answer_bucket=bucket,
        key=key,
        meta={"family": family} if family else {},
    )


def _random_ranking_clues(rng, items, k):
    pool = [("above", a, b) for a in items for b in items if a != b]
    pool += [("top", x, None) for x in items] + [("bottom", x, None) for x in items]
    return rng.sample(pool, k)


def _random_seating_clues(rng, items, circular, k):
    pool = [("left_of", a, b) for a in items for b in items if a != b]
    pool += [("opposite", a, b) for a in items for b in items if a != b]
    if not circular:
        pool += [("left_end", x, None) for x in items] + [("right_end", x, None) for x in items]
    return rng.sample(pool, k)


def test_count_solutions_matches_legacy():
    rng = random.Random(0)
    for i in range(200):
        if i % 2 == 0:
            items = list("ABCDE")
            clues = _random_ranking_clues(rng, items, rng.randint(0, 6))
            assert count_solutions(items, clues, rankings._satisfies) == rankings._count_solutions(items, clues)
        else:
            circular = i % 4 == 1
            items = list("ABCDEF" if circular else "ABCDE")
            clues = _random_seating_clues(rng, items, circular, rng.randint(0, 6))
            new = count_solutions(items, clues, lambda o, c: seating._satisfies(o, c, circular), fix_first=circular)
            assert new == seating._count_solutions(items, clues, circular)


def test_assert_unique_raises_on_zero_and_many():
    items = list("ABC")
    with pytest.raises(PuzzleError):
        assert_unique(items, [], rankings._satisfies)  # many
    contradiction = [("above", "A", "B"), ("above", "B", "A")]
    with pytest.raises(PuzzleError):
        assert_unique(items, contradiction, rankings._satisfies)  # none
    assert_unique(items, [("above", "A", "B"), ("above", "B", "C")], rankings._satisfies)


def test_drop_redundant_keeps_uniqueness():
    rng = random.Random(1)
    for _ in range(100):
        items = list("ABCDE")
        rng.shuffle(items)
        pool = [("above", items[i], items[j]) for i in range(5) for j in range(i + 1, 5)]
        pool += [("top", items[0], None), ("bottom", items[-1], None)]
        rng.shuffle(pool)
        clues = []
        for c in pool:
            clues.append(c)
            if count_solutions(items, clues, rankings._satisfies) == 1:
                break
        slim = drop_redundant(items, clues, rankings._satisfies)
        assert len(slim) <= len(clues)
        assert_unique(items, slim, rankings._satisfies)
        for c in slim:  # nothing left to drop
            assert count_solutions(items, [x for x in slim if x is not c], rankings._satisfies) != 1


def test_variety_no_duplicate_keys():
    keys = [f"k{i}" for i in range(6)]

    def gen(level, rng):
        return _puzzle(rng.choice(keys))

    v = Variety(random.Random(0), tries=500)
    drawn = [v.draw(gen, 1).key for _ in range(6)]
    assert sorted(drawn) == sorted(keys)


def test_variety_max_run():
    counter = iter(range(10_000))

    def mostly_t(level, rng):
        return _puzzle(f"p{next(counter)}", bucket="T" if rng.random() < 0.9 else "F")

    v = Variety(random.Random(0))
    buckets = [v.draw(mostly_t, 1).answer_bucket for _ in range(30)]
    longest = run = 0
    prev = None
    for b in buckets:
        run = run + 1 if b == prev else 1
        prev = b
        longest = max(longest, run)
    assert longest <= 2

    calls = []

    def single_bucket(level, rng):
        calls.append(1)
        return _puzzle(f"s{next(counter)}", bucket="T")

    v = Variety(random.Random(0), tries=7)
    for _ in range(5):
        v.draw(single_bucket, 1)
    assert len(calls) <= 5 * 7  # terminates, bounded by tries per draw


def test_variety_reset():
    def gen(level, rng):
        return _puzzle("only")

    v = Variety(random.Random(0), tries=3)
    v.draw(gen, 1)
    assert "only" in v._seen
    v.reset()
    assert not v._seen
    calls = []

    def counting(level, rng):
        calls.append(1)
        return _puzzle("only")

    v.draw(counting, 1)
    assert len(calls) == 1  # not rerolled: the seen set was cleared
