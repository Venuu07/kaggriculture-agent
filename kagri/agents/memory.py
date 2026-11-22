"""Short-term memory (this season's log) and long-term memory (lessons across seasons)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .. import MEMORY_DIR


class ShortTermMemory:
    """Rolling log of the current season, rendered into each day's prompt."""

    def __init__(self, keep: int = 5) -> None:
        self.keep = keep
        self.days: list[dict[str, Any]] = []

    def add(self, day: int, plan: dict[str, Any], reward: float, events: dict[str, Any], rejected: list[str]) -> None:
        brief = {k: v for k, v in plan.items() if v}
        self.days.append({"day": day, "plan": brief, "cash_change": round(reward), "events": events.get("events", []),
                          "weather": events.get("weather"), "rejected": rejected[:3]})

    def render(self) -> str:
        if not self.days:
            return "(first day of the season)"
        return "\n".join(json.dumps(d, separators=(",", ":")) for d in self.days[-self.keep:])


class LongTermMemory:
    """Lessons learned after each season, stored as JSON on disk and fed into the next season."""

    def __init__(self, key: str, path: Path | None = None) -> None:
        self.path = path or (MEMORY_DIR / f"lessons_{key}.json")
        self.entries: list[dict[str, Any]] = []
        if self.path.exists():
            try:
                self.entries = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                self.entries = []

    def lessons(self, last: int = 8) -> list[str]:
        out: list[str] = []
        for e in self.entries:
            out.extend(e.get("lessons", []))
        return out[-last:]

    def params(self) -> dict[str, float]:
        """Accumulated numeric adjustments (used by the offline reasoner)."""
        merged: dict[str, float] = {}
        for e in self.entries:
            merged.update(e.get("params", {}))
        return merged

    def add(self, entry: dict[str, Any]) -> None:
        self.entries.append(entry)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.entries, indent=2), encoding="utf-8")

    def clear(self) -> None:
        self.entries = []
        if self.path.exists():
            self.path.unlink()

    def render(self) -> str:
        ls = self.lessons()
        return "\n".join(f"- {s}" for s in ls) if ls else "(no lessons yet)"
