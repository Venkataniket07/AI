from core.textguard import leaks, themed_consistent
from games.assist import RoundHelper
from games.engine.puzzle import Puzzle

ORIG = ["B sits immediately left of C.", "D sits at the extreme left end."]


def test_leaks_ignores_case_and_punctuation():
    assert leaks("It is an uncle, I think", "Uncle")
    assert leaks("UNCLE!", "Uncle")
    assert not leaks("Think about generations.", "Uncle")


def test_leaks_catches_separated_letters_and_digits():
    assert leaks("The order is A-B-C-D-E", "ABCDE")
    assert leaks("A B C D E", "ABCDE")
    assert leaks("1, 2, 3, 4, 5", "12345")
    assert not leaks("A-B-C-D-F", "ABCDE")


def test_leaks_forbidden_phrase():
    assert leaks("So it Cannot be determined.", "True", forbidden=["cannot be determined"])
    assert not leaks("Look at the premises.", "True", forbidden=["cannot be determined", ""])


def test_short_answer_matches_whole_tokens_only():
    assert not leaks("a cat sat", "son")
    assert not leaks("every person", "son")
    assert leaks("the son of", "son")
    assert not leaks("cat", "A")
    assert leaks("the answer is a", "A")


def test_themed_consistent_cases_from_theme_tests():
    assert themed_consistent(ORIG, ["Detective B stands beside C, on the left.", "D holds the far left post."])
    assert not themed_consistent(ORIG, ["C sits immediately left of B.", "D sits at the extreme left end."])
    assert not themed_consistent(ORIG, ["B sits immediately left of C."])
    assert not themed_consistent(ORIG, ["B sits immediately left of E.", "D sits at the extreme left end."])
    assert themed_consistent(ORIG, ["A quiet B sits immediately left of C.", "D sits at the extreme left end."])


def test_themed_consistent_rejects_swapped_labels():
    assert not themed_consistent(["B is left of C."], ["C stands left of B."])


def test_round_helper_from_puzzle_populates_hints_explanation_forbidden():
    puzzle = Puzzle(
        game_id="g",
        lines=("Line one.", "Line two."),
        question="Who?",
        answer="Uncle",
        answer_bucket="",
        key="k",
        static_hints=("h1", "h2"),
        explanation="because",
        forbidden=("nope",),
    )
    helper = RoundHelper.from_puzzle(puzzle, None, True)
    assert helper.game_type == "g"
    assert helper.answer == "Uncle"
    assert helper.static_hints == ["h1", "h2"]
    assert helper.explanation == "because"
    assert helper.forbidden == ["nope"]
    assert helper.ai_hints is True
    assert "Line one." in helper.puzzle_text and "Who?" in helper.puzzle_text
