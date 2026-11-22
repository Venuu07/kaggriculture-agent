"""Run the vendored Kaggriculture interpreter without the kaggle-environments framework.

The upstream interpreter expects kaggle's `Struct` objects (attribute access on dicts),
so we provide a minimal equivalent and drive both players turn by turn.
"""
from __future__ import annotations

import copy
from typing import Any, Callable

from . import kaggriculture as kg

Action = dict[str, Any]


class Struct(dict):
    """Dict with attribute access, like kaggle_environments.utils.Struct."""

    def __getattr__(self, key: str) -> Any:
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc

    def __setattr__(self, key: str, value: Any) -> None:
        self[key] = value


class GameDriver:
    """Two-player Kaggriculture game, stepped one turn at a time."""

    def __init__(self, seed: int, episode_steps: int = 720, starting_money: int = 3000,
                 board_size: int = 10, turns_per_day: int = 24) -> None:
        self.env = Struct(
            configuration=Struct(
                episodeSteps=episode_steps, boardSize=board_size, startingMoney=starting_money,
                turnsPerDay=turns_per_day, maxMarketOrdersPerTurn=10, shedCapacity=100,
                weedSpawnChance=0.005, townShopUnlockInterval=3, townShopSellInterval=4,
                townCenterSellInterval=24, farmHandCostMult=1, marketParams={},
            ),
            info={"seed": int(seed)},
            done=False,
        )
        self.state = [Struct(observation=Struct(step=0), action={}, status="ACTIVE", reward=0)
                      for _ in range(2)]
        kg.interpreter(self.state, self.env)
        self.step_count = 0

    @property
    def obs0(self) -> Struct:
        return self.state[0].observation

    def observation(self, player: int) -> dict[str, Any]:
        """Observation dict in the official format for `player`."""
        o = self.obs0
        return {
            "player": player, "step": self.step_count, "day": o.day, "hour": o.hour,
            "farms": o.farms, "market": o.market, "town": o.town,
            "private": self.state[player].observation.private,
        }

    @property
    def done(self) -> bool:
        return self.state[0].status == "DONE"

    def step(self, actions: list[Action]) -> None:
        """Apply one turn of actions for both players."""
        for s, a in zip(self.state, actions):
            s.action = a
        self.obs0.step = self.step_count
        kg.interpreter(self.state, self.env)
        self.step_count += 1

    def clone(self) -> "GameDriver":
        """Deep copy (used for look-ahead simulation)."""
        return copy.deepcopy(self)


BUILTIN_OPPONENTS: dict[str, Callable[[dict[str, Any]], Action]] = dict(kg.agents)
