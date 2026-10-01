"""Answer parsing and puzzle generation found wanting by a bot play-through of games 3-10."""

import builtins
import json
import math
import random
import re

import pytest

from games.common import normalize_symbol, parse_int
from games.memory import n_back, number_recall, pattern_memory
from games.pattern import sequences
from tests.direction_solver import solve_round


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


def test_number_recall_starts_at_four_digits_for_a_game_never_played(monkeypatch, capsys, profile):
    from core.progression import xp_to_reach
    profile.db.add_game_progress(profile.current_user.id, "mental_math", xp_to_reach(7), sessions=0)  # strong elsewhere
    seen = []

    def answer(out):
        seen.append(re.findall(r"^ {6}([\d-]+)$", out, re.M)[-1].replace("-", ""))
        return ""
    _run(monkeypatch, capsys, number_recall.play_number_recall, profile, answer, "Your answer")
    assert len(seen[0]) == 4


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


# ── answer formats, blank lines, hints in the trial log, word list (games 1, 2 and 11-16) ──────────────

def _direction_answer(state):
    """Answers Direction Sense from the round text; asks for one hint first when state['hint'] is set."""
    buf = []

    def answer(out):
        if not state.get("asked"):
            buf.clear()
        buf.append(out)
        if state.get("hint") and not state.get("asked"):
            state["asked"] = True
            return "hint"
        state["asked"] = False
        solved = solve_round("".join(buf))
        return state["fmt"](int(solved)) if solved.isdigit() else solved
    return answer


@pytest.mark.parametrize("fmt", [
    str, lambda n: f"{n}m", lambda n: f"{n} m", lambda n: f"{n} meters", lambda n: f"{n} Metres", lambda n: f"{n}.", lambda n: f"{n}.0",
])
def test_direction_sense_accepts_units_and_decimal_points(monkeypatch, capsys, profile, fmt):
    from games.reasoning import direction
    _run(monkeypatch, capsys, direction.play_direction_sense, profile, _direction_answer({"fmt": fmt}), "> ")
    assert profile.db.get_user_stats(profile.require_user().id, limit=1)[0].accuracy == 1.0


def test_hints_asked_in_a_reasoning_game_are_logged_and_not_judged_as_fast(monkeypatch, capsys, profile):
    """An instant answer right after a hint used to be stored as an unhinted, implausibly fast one ("review")."""
    from games.reasoning import direction
    _run(monkeypatch, capsys, direction.play_direction_sense, profile, _direction_answer({"fmt": str, "hint": True}), "> ")
    s = profile.db.get_user_stats(profile.require_user().id, limit=1)[0]
    assert s.accuracy == 1.0 and s.integrity == "ok"
    assert [t[2] for t in json.loads(s.trial_data)] == [1] * 5


@pytest.mark.parametrize("fmt", [str, lambda n: f"{n}.", lambda n: f"{n}.0", lambda n: f"+{n}", lambda n: f" {n} "])
def test_mental_math_accepts_common_number_formats(monkeypatch, capsys, profile, fmt):
    from games.math import mental_math

    def answer(out):
        q = re.findall(r"\]: (.+) = \?", out)[-1]
        return fmt(eval(q.replace("/", "//")))
    _run(monkeypatch, capsys, mental_math.play_mental_math, profile, answer, "Your answer")
    assert profile.db.get_user_stats(profile.require_user().id, limit=1)[0].accuracy == 1.0


def test_mental_math_asks_again_after_a_blank_line(monkeypatch, capsys, profile):
    from games.math import mental_math
    state = {"blank": True, "q": ""}

    def answer(out):
        state["q"] = (re.findall(r"\]: (.+) = \?", out) or [state["q"]])[-1]  # a re-asked prompt shows no question
        if state["blank"]:
            state["blank"] = False
            return ""
        state["blank"] = True
        return str(eval(state["q"].replace("/", "//")))
    _run(monkeypatch, capsys, mental_math.play_mental_math, profile, answer, "Your answer")
    assert profile.db.get_user_stats(profile.require_user().id, limit=1)[0].accuracy == 1.0


def test_round_helper_ignores_blank_lines(monkeypatch):
    from games.assist import RoundHelper
    replies = iter(["", "   ", "x"])
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(replies))
    assert RoundHelper("g", "p", "a").ask() == "x"


@pytest.mark.parametrize("text", ["ABCDE", "abcde", "A B C D E", "A,B,C,D,E", "A, B, C, D, E", "A-B-C-D-E", "A > B > C > D > E", "'ABCDE'", "ABCDE."])
def test_letters_only_reads_an_arrangement_however_it_is_typed(text):
    from games.common import letters_only
    assert letters_only(text) == "ABCDE"


@pytest.mark.parametrize("text", ["MOUSE", "mouse", "M O U S E", "M,O,U,S,E", "M-O-U-S-E", "'mouse'", "mouse."])
def test_compact_answer_ignores_separators_quotes_and_dots(text):
    from games.common import compact_answer
    assert compact_answer(text) == "MOUSE"


@pytest.mark.parametrize("text, option", [
    ("1", "1"), (" 1 ", "1"), ("1.", "1"), ("(1)", "1"), ("True", "1"), ("t", "1"),
    ("2", "2"), ("false", "2"), ("F", "2"),
    ("3", "3"), ("Cannot be determined", "3"), ("cannot", "3"), ("c", "3"),
    ("", ""), ("4", ""), ("maybe", ""), ("12", ""),
])
def test_syllogism_options_can_be_typed_as_words(text, option):
    from games.reasoning.syllogisms import parse_option
    assert parse_option(text) == option


def test_anagram_hints_do_not_repeat_and_a_blank_line_is_not_a_wrong_answer(monkeypatch, capsys, profile):
    from games.language import anagrams
    words = ["lamp", "desk", "pond", "milk", "farm"]
    monkeypatch.setattr(anagrams, "build_word_pool",
                        lambda lengths: ([{"word": w, "clue": f"clue {i}", "freq": 40.0} for i, w in enumerate(words)], False))
    monkeypatch.setattr(anagrams, "fetch_dictionary_clues", lambda w: {})  # the dictionary service is down
    steps = {"n": 0}
    seen = []

    def answer(out):
        seen.append(out)
        scrambled = re.findall(r"\[ (\w+) \]", "".join(seen))[-1]
        word = next(w for w in words if sorted(w) == sorted(scrambled))
        steps["n"] += 1
        return ["", "hint", "hint", "hint"][(steps["n"] - 1) % 5] if (steps["n"] - 1) % 5 < 4 else word
    _run(monkeypatch, capsys, anagrams.play_anagrams, profile, answer, "Your guess")
    text = "".join(seen)
    hint2 = re.findall(r"HINT 2: (.*)", text)[0]
    hint3 = re.findall(r"HINT 3: (.*)", text)[0]
    assert hint2 != hint3 and "ends with the letter" in hint2 and "letters," in hint3
    assert profile.db.get_user_stats(profile.require_user().id, limit=1)[0].accuracy == 1.0


def test_offline_word_list_holds_no_surnames_given_names_or_abbreviations():
    from games.language.wordlist import is_junk_definition
    from games.language.wordlist_data import WORDS
    assert [w for w, _, clue in WORDS if is_junk_definition([clue])] == []


def test_the_speaker_in_the_only_son_story_is_said_to_be_a_man():
    """Without it the speaker could be a woman, and "my father's only son" would be her brother."""
    from games.reasoning.blood_relations import EASY_TEMPLATES
    story = next(t for t in EASY_TEMPLATES if "only son" in t["setup"])
    assert "{P2} is a man." in story["setup"]
