"""Central registry of playable games.

To add a game: write a `play_<name>(profile)` function and add one `Game(...)` entry below.
The main menu is generated from this list.
"""

from dataclasses import dataclass
from typing import Callable

from core.profile_manager import ProfileManager
from games.language.anagrams import play_anagrams
from games.logic.matrix import play_matrix_reasoning
from games.math.mental_math import play_mental_math
from games.math.quick_calc import play_quick_calc
from games.memory.n_back import play_n_back
from games.memory.number_recall import play_number_recall
from games.memory.pattern_memory import play_pattern_memory
from games.pattern.sequences import play_missing_number, play_pattern_completion, play_sequence_prediction
from games.reasoning.blood_relations import play_blood_relations
from games.reasoning.coding import play_coding_decoding
from games.reasoning.direction import play_direction_sense
from games.reasoning.puzzle_grid import play_puzzle_grid
from games.reasoning.rankings import play_rankings
from games.reasoning.seating import play_circular_seating, play_linear_seating
from games.reasoning.syllogisms import play_syllogisms


@dataclass(frozen=True)
class Game:
    title: str
    play: Callable[[ProfileManager], None]
    min_level: int
    category: str


CORE = "CORE COGNITIVE TRAINING"
BEGINNER = "REASONING MASTER: Beginner (Req. Level 1)"
INTERMEDIATE = "REASONING MASTER: Intermediate (Req. Level 3)"
ADVANCED = "REASONING MASTER: Advanced (Req. Level 6)"

GAMES: list[Game] = [
    Game("Mental Arithmetic", play_mental_math, 1, CORE),
    Game("Word Anagrams", play_anagrams, 1, CORE),
    Game("Sequence Prediction", play_sequence_prediction, 1, CORE),
    Game("Matrix Reasoning", play_matrix_reasoning, 1, CORE),
    Game("Pattern Completion", play_pattern_completion, 1, CORE),
    Game("Missing Number", play_missing_number, 1, CORE),
    Game("Quick Calculation Duel", play_quick_calc, 1, CORE),
    Game("Number Recall", play_number_recall, 1, CORE),
    Game("N-Back Memory", play_n_back, 1, CORE),
    Game("Pattern Memory", play_pattern_memory, 1, CORE),
    Game("Blood Relations", play_blood_relations, 1, BEGINNER),
    Game("Direction Sense", play_direction_sense, 1, BEGINNER),
    Game("Coding-Decoding", play_coding_decoding, 1, BEGINNER),
    Game("Ranking Puzzles", play_rankings, 3, INTERMEDIATE),
    Game("Syllogisms", play_syllogisms, 3, INTERMEDIATE),
    Game("Linear Seating", play_linear_seating, 3, INTERMEDIATE),
    Game("Circular Seating", play_circular_seating, 6, ADVANCED),
    Game("Puzzle Grids (Zebra)", play_puzzle_grid, 6, ADVANCED),
]


def available_games(level: int) -> list[Game]:
    """Games unlocked at `level`, in menu order."""
    return [g for g in GAMES if level >= g.min_level]
