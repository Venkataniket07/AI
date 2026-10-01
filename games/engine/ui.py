"""The result screen shared by the memory games."""

import time

CORRECT_PAUSE_S = 1.0
MAX_BLANK_RETRIES: int = 5


def sleep(seconds: float) -> None:
    time.sleep(seconds)


def read_line(prompt: str) -> str:
    return input(prompt)


def read_nonblank(prompt: str, max_tries: int = MAX_BLANK_RETRIES) -> str | None:
    for _ in range(max_tries):
        raw = read_line(prompt).strip()
        if raw:
            return raw
    return None


def pause(prompt: str = "Press Enter to continue...") -> None:
    read_line(f"\n{prompt}")


def show_result(correct: bool, yours: str, expected: str, *, wait: bool | None = None) -> None:
    """Right: say so and pause briefly. Wrong: show both answers and wait for Enter (`wait` overrides)."""
    if wait is None:
        wait = not correct
    if correct:
        print("Correct!")
    else:
        print("Incorrect.")
        print(f"  Yours:   {yours}")
        print(f"  Correct: {expected}")
    if wait:
        pause()
    else:
        sleep(CORRECT_PAUSE_S)
