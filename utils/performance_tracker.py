import time
from typing import Optional


class PerformanceTracker:
    def __init__(self):
        self.start_time = 0
        self.total_time_ms = 0
        self.trials = 0
        self.correct = 0
        # One (elapsed_ms, correct, hints_used, min_plausible_ms) per trial, kept for integrity checks.
        self.trial_log: list[tuple[int, bool, int, Optional[int]]] = []
        self.assisted = False  # the player said they used outside help this game

    def start_trial(self):
        self.start_time = time.perf_counter()

    def end_trial(self, is_correct: bool, hints_used: int = 0, min_plausible_ms: Optional[int] = None):
        """`min_plausible_ms`: the fastest an honest answer to this question could be given, if the game knows."""
        elapsed = (time.perf_counter() - self.start_time) * 1000
        self.total_time_ms += elapsed
        self.trials += 1
        if is_correct:
            self.correct += 1
        self.trial_log.append((round(elapsed), bool(is_correct), hints_used, min_plausible_ms))

    @property
    def accuracy(self) -> float:
        if self.trials == 0:
            return 0.0
        return self.correct / self.trials

    @property
    def avg_reaction_time_ms(self) -> float:
        if self.trials == 0:
            return 0.0
        return self.total_time_ms / self.trials
