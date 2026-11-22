"""Common agent interface."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..env import FarmEnv


@dataclass
class Decision:
    """What an agent returns each day: the plan plus an optional reasoning trace."""

    plan: dict[str, Any]
    trace: list[dict[str, Any]] = field(default_factory=list)  # thought / tool / result steps
    tokens: int = 0
    cost_usd: float = 0.0
    latency_s: float = 0.0
    llm_calls: int = 0
    fallback: bool = False


class Agent:
    """Base class. Subclasses implement `decide`."""

    name = "agent"
    label = "Agent"

    def begin_episode(self, seed: int) -> None:
        """Called before day 0."""

    def decide(self, obs: dict[str, Any], env: FarmEnv) -> Decision:
        raise NotImplementedError

    def end_episode(self, summary: dict[str, Any]) -> None:
        """Called after the last day (used for reflection)."""
