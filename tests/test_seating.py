import pytest

from games.reasoning.seating import _count_solutions, _is_valid_answer, generate_seating_puzzle


@pytest.mark.parametrize("is_circular", [False, True])
def test_generated_puzzles_have_exactly_one_solution(is_circular):
    for _ in range(50):
        texts, clues, answer = generate_seating_puzzle(is_circular)
        assert len(texts) == len(clues)
        assert _count_solutions(list(answer), clues, is_circular) == 1
        assert _is_valid_answer(answer, clues, is_circular)


def test_circular_answer_accepts_any_rotation():
    _, clues, answer = generate_seating_puzzle(True)
    for shift in range(len(answer)):
        assert _is_valid_answer(answer[shift:] + answer[:shift], clues, True)


def test_wrong_or_malformed_answers_rejected():
    _, clues, answer = generate_seating_puzzle(False)
    assert not _is_valid_answer("", clues, False)
    assert not _is_valid_answer(answer[:-1], clues, False)
    assert not _is_valid_answer("AAAAA", clues, False)
    assert not _is_valid_answer(answer[1:] + answer[0], clues, False)


def test_circular_left_is_as_seen_facing_the_centre():
    # seated clockwise A B C D E F, B is A's left-hand neighbour (next clockwise) when facing the centre
    clues = [("left_of", "B", "A")]
    assert _is_valid_answer("ABCDEF", clues, True)
    assert _is_valid_answer("CDEFAB", clues, True)
    assert not _is_valid_answer("BACDEF", clues, True)
    assert not _is_valid_answer("FEDCBA", clues, True)
