"""Answer parsing and puzzle generation found wanting by a bot play-through of games 3-10."""

import builtins
import math
import random
import re

import pytest

from games.common import normalize_symbol, parse_int
from games.memory import n_back, number_recall, pattern_memory
from games.pattern import sequences


@pytest.mark.parametrize("text, expected", [
    ("12", 12), (" 12 ", 12), ("+5", 5), ("-7", -7), ("1,024", 1024), ("12.", 12), ("12.0", 12), ("1２", 12),
    ("", None), ("abc", None), ("12abc", None), ("3.5", None), ("1e3", None), ("1_0", None), (".", None), ("--1", None),
])
def test_parse_int(text, expected):
    assert parse_int(text) == expected


@pytest.mark.parametrize("text", ["b3", " B 3 ", "'B3'", '"b3"', "`B3`"])
def test_normalize_symbol_ignores_case_spaces_and_quotes(text):
    assert normalize_symbol(text) == "B3"


def test_normalize_symbol_keeps_symbols_apart():
    assert normalize_symbol("<>") != normalize_symbol("[]")


def _next_values(seq):
    """Every rule the generator can use that fits `seq`, with the number it predicts next."""
    n, out = len(seq), set()
    d = [b - a for a, b in zip(seq, seq[1:])]
    if len(set(d)) == 1:
        out.add(seq[-1] + d[0])
    if all(x > 0 for x in seq) and all(b % a == 0 for a, b in zip(seq, seq[1:])):
        ratios = {b // a for a, b in zip(seq, seq[1:])}
        if len(ratios) == 1 and ratios != {1}:
            out.add(seq[-1] * ratios.pop())
    if all(seq[i] == seq[i - 1] + seq[i - 2] for i in range(2, n)):
        out.add(seq[-1] + seq[-2])
    roots = [math.isqrt(max(x, 0)) for x in seq]
    if all(x >= 0 and r * r == x for r, x in zip(roots, seq)) and all(b - a == 1 for a, b in zip(roots, roots[1:])):
        out.add((roots[-1] + 1) ** 2)
    if len(set(d)) == 2 and all(d[i] == d[i % 2] for i in range(len(d))):
        out.add(seq[-1] + d[len(d) % 2])
    if all(_is_prime(x) for x in seq) and all(b == _next_prime(a) for a, b in zip(seq, seq[1:])):
        out.add(_next_prime(seq[-1]))
    return out


def _is_prime(n):
    return n > 1 and all(n % k for k in range(2, math.isqrt(n) + 1))


def _next_prime(n):
    n += 1
    while not _is_prime(n):
        n += 1
    return n


def test_generated_sequences_have_one_reading():
    """No sequence may fit two rules that disagree about the next number (11 13 17 19 23 did)."""
    for _ in range(4000):
        seq, ans = sequences.generate_sequence(random.randint(1, 10), set())
        assert _next_values(seq) == {ans}, seq


def _run(monkeypatch, capsys, game, profile, answer_for, prompt_key):
    """Play `game`; `answer_for(output_since_last_prompt)` answers the prompt containing `prompt_key`."""
    def fake_input(prompt=""):
        print(prompt, end="")
        return answer_for(capsys.readouterr().out) if prompt_key in prompt else ""
    monkeypatch.setattr(builtins, "input", fake_input)
    monkeypatch.setattr("time.sleep", lambda s: None)
    for mod in (number_recall, pattern_memory, n_back):
        monkeypatch.setattr(mod, "clear_screen", lambda: None)
    game(profile)


def test_pattern_completion_answers_are_always_letters(monkeypatch, capsys, profile):
    seen = []

    def answer(out):
        seen.append(out)
        return ""
    for _ in range(150):
        _run(monkeypatch, capsys, sequences.play_pattern_completion, profile, answer, "Next pattern")
    text = "".join(seen)
    for line in re.findall(r"Round \d/5: (.+) \?", text):
        assert all(re.fullmatch(r"[A-Z]\d*", t) for t in line.split()), line
    answers = re.findall(r"The correct answer was (\S+)\.", text)
    assert len(answers) > 500
    assert all(re.fullmatch(r"[A-Z]\d*", a) for a in answers), set(answers)


@pytest.mark.parametrize("fmt", [
    lambda coords: ", ".join(f"{r} {c}" for r, c in coords),
    lambda coords: ", ".join(f"{r},{c}" for r, c in coords),
    lambda coords: " ".join(f"{r} {c}" for r, c in coords),
    lambda coords: ", ".join(f"({r}, {c})" for r, c in coords),
    lambda coords: "; ".join(f"{r}-{c}" for r, c in coords),
])
def test_pattern_memory_accepts_common_coordinate_formats(monkeypatch, capsys, profile, fmt):
    def answer(out):
        grid = out[out.rfind("Memorize the pattern:"):]
        coords = []
        for m in re.finditer(r"^  (\d) (.*)$", grid, re.M):
            coords += [(int(m.group(1)), i) for i, cell in enumerate(re.findall(r"\[.\]", m.group(2))) if cell == "[X]"]
        return fmt(coords)
    _run(monkeypatch, capsys, pattern_memory.play_pattern_memory, profile, answer, "Your answer")
    assert profile.db.get_user_stats(profile.require_user().id, limit=1)[0].accuracy == 1.0


def test_pattern_memory_rejects_an_odd_number_of_coordinates(monkeypatch, capsys, profile):
    _run(monkeypatch, capsys, pattern_memory.play_pattern_memory, profile, lambda out: "0 1 2", "Your answer")
    assert profile.db.get_user_stats(profile.require_user().id, limit=1)[0].accuracy == 0.0


@pytest.mark.parametrize("group", ["-", " ", ",", ", ", ""])
def test_number_recall_ignores_separators(monkeypatch, capsys, profile, group):
    def answer(out):
        raw = re.findall(r"^ {6}([\d-]+)$", out, re.M)[-1].replace("-", "")
        return group.join(raw[i:i + 3] for i in range(0, len(raw), 3))
    _run(monkeypatch, capsys, number_recall.play_number_recall, profile, answer, "Your answer")
    assert profile.db.get_user_stats(profile.require_user().id, limit=1)[0].accuracy == 1.0


def test_number_recall_view_time_grows_with_length_and_keeps_a_floor():
    assert number_recall.view_seconds(12, 0) > number_recall.view_seconds(5, 0)
    assert number_recall.view_seconds(5, 20) == 1.5
    assert number_recall.MAX_LENGTH == 12


def test_matrix_puzzle_kinds_widen_with_difficulty():
    from games.logic import matrix
    assert set(matrix.pattern_types(1)) == {"rotation", "progression"}
    assert "addition" in matrix.pattern_types(3) and "latin" not in matrix.pattern_types(3)
    assert "latin" in matrix.pattern_types(6)


def test_matrix_latin_square_answer_completes_every_row_and_column():
    from games.logic import matrix
    random.seed(1)
    for _ in range(300):
        m, ans = matrix.generate_spatial_matrix(set(), 10)
        m[2][2] = ans
        if len({x for row in m for x in row}) == 3:  # a latin square, not another kind
            assert all(len(set(row)) == 3 for row in m)
            assert all(len({m[r][c] for r in range(3)}) == 3 for c in range(3))


def test_pattern_memory_layout_grows_with_difficulty_and_fits_the_grid():
    prev = (0, 0)
    for d in range(1, 16):
        size, xs = pattern_memory.layout(d)
        assert 3 <= size <= 5 and 2 <= xs <= size * size // 2
        assert size >= prev[0] and xs >= prev[1]
        prev = (size, xs)
    assert pattern_memory.layout(1) == (3, 3)
    assert pattern_memory.view_seconds(12, 0) > pattern_memory.view_seconds(3, 0)
    assert pattern_memory.view_seconds(3, 20) == 2.0


@pytest.mark.parametrize("game_name, game", [
    ("matrix", "matrix"), ("pattern_memory", "pattern_memory"),
])
def test_matrix_and_pattern_memory_store_their_difficulty(monkeypatch, capsys, profile, game_name, game):
    from games.logic import matrix
    fn = matrix.play_matrix_reasoning if game == "matrix" else pattern_memory.play_pattern_memory
    monkeypatch.setattr(matrix, "clear_screen", lambda: None, raising=False)
    _run(monkeypatch, capsys, fn, profile, lambda out: "", "Missing pattern" if game == "matrix" else "Your answer")
    assert profile.db.get_user_stats(profile.require_user().id, limit=1)[0].difficulty == 1


def test_answer_floor_grows_with_answer_and_question_length():
    from core.integrity import answer_floor_ms
    assert answer_floor_ms("5") < answer_floor_ms("55555") < answer_floor_ms("55555", "a long question " * 5)
    assert answer_floor_ms("") == 400


def _integrity_of_last_session(profile):
    return profile.db.get_user_stats(profile.require_user().id, limit=1)[0].integrity


@pytest.mark.parametrize("game", [
    sequences.play_sequence_prediction, sequences.play_pattern_completion, sequences.play_missing_number,
    number_recall.play_number_recall, pattern_memory.play_pattern_memory,
])
def test_games_now_judge_integrity(monkeypatch, capsys, profile, game):
    """Wrong answers are never 'too fast', so a session of them is judged ok (it used to be NULL)."""
    _run(monkeypatch, capsys, game, profile, lambda out: "x", "")
    assert _integrity_of_last_session(profile) == "ok"


def test_matrix_and_mental_math_judge_integrity(monkeypatch, capsys, profile):
    from games.logic import matrix
    from games.math import mental_math
    for game in (matrix.play_matrix_reasoning, mental_math.play_mental_math):
        _run(monkeypatch, capsys, game, profile, lambda out: "x", "")
        assert _integrity_of_last_session(profile) == "ok"


def test_instantly_typed_correct_recall_is_flagged_for_review(monkeypatch, capsys, profile):
    def answer(out):
        return re.findall(r"^ {6}([\d-]+)$", out, re.M)[-1].replace("-", "")
    _run(monkeypatch, capsys, number_recall.play_number_recall, profile, answer, "Your answer")
    assert _integrity_of_last_session(profile) == "review"
