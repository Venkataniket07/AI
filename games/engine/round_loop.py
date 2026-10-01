"""Shared round loop skeleton. Implemented in P6 (Direction Sense), its first consumer."""

from dataclasses import dataclass

from core.profile_manager import ProfileManager
from games.engine.puzzle import Generator


@dataclass(frozen=True)
class GameSpec:
    game_id: str
    title: str
    instructions: str
    generator: Generator
    rounds: int = 4
    base_points: int = 25


def play_rounds(profile: ProfileManager, spec: GameSpec) -> None:
    raise NotImplementedError("play_rounds is implemented in P6")
