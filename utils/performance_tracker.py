import time

class PerformanceTracker:
    def __init__(self):
        self.start_time = 0
        self.total_time_ms = 0
        self.trials = 0
        self.correct = 0

    def start_trial(self):
        self.start_time = time.perf_counter()

    def end_trial(self, is_correct: bool):
        elapsed = (time.perf_counter() - self.start_time) * 1000
        self.total_time_ms += elapsed
        self.trials += 1
        if is_correct:
            self.correct += 1

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
