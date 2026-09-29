"""Per-round hints and explanations shared by the reasoning games.

Hints cost points: 15% / 30% / 50% off the round's score after the 1st / 2nd / 3rd hint.
Games supply deterministic hints and explanations that are correct by construction. AI is used
in two ways: to write hints/explanations for games that have no deterministic version, and never
to judge whether an answer is right.
"""

from typing import Optional, Sequence

from utils.logger import get_app_logger

HINT_PENALTIES = (0.15, 0.30, 0.50)  # cumulative fraction of the round's points lost
HINT_WAIT = 8.0       # seconds to wait for an AI hint before falling back
EXPLAIN_WAIT = 12.0   # seconds to wait for an AI explanation

HINT_TIP = "Tip: type 'hint' at any prompt for a hint (costs points)."


def _ai_enabled() -> bool:
    try:
        from ai.config import config
        return config.ai_enabled
    except Exception:
        get_app_logger().error("AI configuration could not be loaded.", exc_info=True)
        return False


class RoundHelper:
    def __init__(
        self,
        game_type: str,
        puzzle_text: str,
        answer: str,
        db=None,
        static_hints: Sequence[str] = (),
        explanation: Optional[str] = None,
        ai_hints: bool = False,
        forbidden: Sequence[str] = (),
    ):
        """
        Args:
            puzzle_text:  the puzzle as shown to the player (given to the AI).
            answer:       the correct answer (given to the AI so it explains correctly).
            static_hints: deterministic hints, gentlest first.
            explanation:  deterministic explanation shown after a wrong answer.
            ai_hints:     try an AI hint first (falls back to `static_hints`).
            forbidden:    extra strings an AI hint must not contain.
        """
        self.game_type = game_type
        self.puzzle_text = puzzle_text
        self.answer = answer
        self.db = db
        self.static_hints = list(static_hints)
        self.explanation = explanation
        self.ai_hints = ai_hints
        self.forbidden = list(forbidden)
        self.hints_used = 0
        self._explain_future = None

    # ── hints ────────────────────────────────────────────────────────────────

    @property
    def penalty(self) -> float:
        return HINT_PENALTIES[self.hints_used - 1] if self.hints_used else 0.0

    def points(self, base: int) -> int:
        """`base` points reduced by the hint penalty."""
        return round(base * (1 - self.penalty))

    def _next_hint(self) -> Optional[str]:
        if self.ai_hints and _ai_enabled():
            try:
                from ai.background import result_or_none, submit
                from ai.services.assist_service import hint
                print("Thinking of a hint...")
                text = result_or_none(
                    submit(hint, self.game_type, self.puzzle_text, self.answer, self.hints_used, self.forbidden),
                    timeout=HINT_WAIT,
                )
                if text:
                    return text
            except Exception:
                get_app_logger().warning("AI hint failed; using a built-in hint.", exc_info=True)
        if self.hints_used < len(self.static_hints):
            return self.static_hints[self.hints_used]
        return None

    def give_hint(self) -> bool:
        """Print the next hint. Returns False (and charges nothing) if none was available."""
        if self.hints_used >= len(HINT_PENALTIES):
            print("No more hints for this puzzle.")
            return False
        text = self._next_hint()
        if text is None:
            print("No hint available for this puzzle.")
            return False
        self.hints_used += 1
        print(f"💡 Hint {self.hints_used}: {text}  (-{round(self.penalty * 100)}% points this round)")
        return True

    def ask(self, prompt: str = "> ") -> str:
        """input() that treats the word 'hint' as a request for a hint."""
        while True:
            raw = input(prompt).strip()
            if raw.lower() != "hint":
                return raw
            self.give_hint()

    # ── explanations ─────────────────────────────────────────────────────────

    def _start_ai_explanation(self, user_answer: str) -> None:
        try:
            from ai.background import submit
            from ai.services.assist_service import explain
            self._explain_future = submit(explain, self.game_type, self.puzzle_text, user_answer, self.answer)
        except Exception:
            get_app_logger().warning("Could not start AI explanation.", exc_info=True)

    def offer_explanation(self, user_answer: str) -> None:
        """After a wrong answer: offer an explanation (deterministic if available, else AI)."""
        use_ai = self.explanation is None and _ai_enabled()
        if self.explanation is None and not use_ai:
            return
        if use_ai:
            self._start_ai_explanation(user_answer)  # runs while the player decides

        if input("Show explanation? (y/N): ").strip().lower() not in ("y", "yes"):
            return

        if self.explanation is not None:
            print(f"📘 {self.explanation}")
            return

        from ai.background import result_or_none
        result = result_or_none(self._explain_future, timeout=EXPLAIN_WAIT)
        if result is None:
            print("Explanation unavailable right now.")
            return
        print("📘 Explanation:")
        for i, step in enumerate(result.steps, 1):
            print(f"  {i}. {step}")
        print(f"  {result.summary}")
