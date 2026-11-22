"""The Foreman: turns one daily plan into 24 turns of low-level game commands.

The agent decides *what* the farm should do today (economics). The Foreman decides *how*:
it walks the farmer and hired hands around the grid and issues PLANT / WATER / HARVEST /
DIG / FEED / CARE / COLLECT_FERTILIZER / BUILD_* / PLACE commands, plus the day's market
orders. It is deterministic and has no strategy of its own beyond standing orders:

* water every plant every day, harvest when ripe, dig weeds,
* feed (buying wheat if needed), care for and collect fertiliser from every animal,
* on the last day, harvest everything sellable, drop it at the shed and sell it.
"""
from __future__ import annotations

from typing import Any

from .engine import kaggriculture as kg
from .plan import HARVEST_AGE

Pos = tuple[int, int]

# Lower number = more urgent.
PRIO = {"FEED": 0, "WATER": 1, "HARVEST": 1, "PLACE": 2, "FERTILIZE": 2, "PLANT": 3,
        "BUILD_COOP": 3, "BUILD_PASTURE": 3, "COLLECT_FERTILIZER": 4, "CARE": 5, "DIG": 6}
ITEM_FOR = {"FEED": "WHEAT", "FERTILIZE": "FERTILIZER"}


def plant_ready(tile: dict[str, Any], day: int, final_day: bool) -> bool:
    """Is a plant worth harvesting now?"""
    cd = kg.CROPS[tile["crop"]]
    age = day - tile["planted_day"]
    if tile.get("yield_units", 0) <= 0 or age < cd["first_yield_day"]:
        return False
    if cd["ongoing"] or final_day:
        return True
    if tile["yield_units"] >= cd["max_yield"]:
        return True
    target = HARVEST_AGE[tile["crop"]]
    return age > target or (age == target and tile["watered_today"])


def wants_fertiliser(tile: dict[str, Any], day: int) -> bool:
    """Would fertilising this plant today raise its yield?"""
    cd = kg.CROPS[tile["crop"]]
    if tile.get("fertilized_until_day", -1) >= day:
        return False
    age = day - tile["planted_day"]
    if cd["ongoing"]:
        first = cd["first_yield_day"] - 1
        last = first + (cd["max_yield"] - 1) * cd["interval"]
        return first <= age <= last
    start = (cd["max_yield_day"] + 1) // 2
    return start <= age < HARVEST_AGE[tile["crop"]] and tile.get("yield_units", 0) < cd["max_yield"]


class Foreman:
    """Executes a validated plan over one day for one player."""

    def __init__(self, plan: dict[str, Any], day: int, last_day: int, final_sell_hour: int = 12) -> None:
        self.plan = plan
        self.day = day
        self.final_day = day >= last_day
        self.final_sell_hour = final_sell_hour
        self.to_plant: dict[str, int] = dict(plan.get("plant", {}))
        self.to_place: dict[str, int] = dict(plan.get("buy_animals", {}))
        self.fertilise = set(plan.get("fertilise", []))
        self.orders: list[list[Any]] = []
        self.orders_built = False

    # ---------------------------------------------------------------- market
    def _build_orders(self, obs: dict[str, Any]) -> None:
        me = obs["farms"][obs["player"]]
        shed = obs["private"]["shed"]
        seeds = obs["private"]["seeds"]
        orders: list[list[Any]] = [["HIRE"] for _ in range(self.plan.get("hands", 0))]
        if self.plan.get("buy_land"):
            orders.append(["BUY_LAND"])
        for crop, n in self.to_plant.items():
            need = n - seeds.get(crop, 0)
            if need > 0:
                orders.append(["BUY_SEED", crop, need])
        for animal, n in self.to_place.items():
            orders.append(["BUY_ANIMAL", animal, n])
        n_animals = sum(1 for row in me["tiles"] for t in row if isinstance(t, dict) and "animal" in t)
        n_animals += sum(shed.get(a, 0) for a in kg.ANIMALS) + sum(self.to_place.values())
        feed_reserve = 2 * n_animals
        wheat_short = n_animals - shed.get("WHEAT", 0)
        if wheat_short > 0:
            orders.append(["BUY_PRODUCT", "WHEAT", wheat_short])
        if self.fertilise:
            targets = sum(1 for row in me["tiles"] for t in row
                          if isinstance(t, dict) and t.get("kind") == "PLANT"
                          and t["crop"] in self.fertilise and wants_fertiliser(t, self.day))
            short = targets - shed.get("FERTILIZER", 0)
            if short > 0:
                orders.append(["BUY_PRODUCT", "FERTILIZER", short])
        for item, q in self.plan.get("sell", {}).items():
            if item == "WHEAT":
                q = min(q, max(0, shed.get("WHEAT", 0) - feed_reserve))
            if q > 0:
                orders.append(["SELL", item, q])
        self.orders = orders
        self.orders_built = True

    def _market(self, obs: dict[str, Any]) -> list[list[Any]]:
        if not self.orders_built:
            self._build_orders(obs)
        out, self.orders = self.orders[:10], self.orders[10:]
        if self.final_day and obs["hour"] >= self.final_sell_hour:
            shed = obs["private"]["shed"]
            out += [["SELL", item, n] for item, n in shed.items() if n > 0 and item in kg.PRODUCTS]
            out = out[:10]
        return out

    # ----------------------------------------------------------------- units
    def act(self, obs: dict[str, Any]) -> dict[str, Any]:
        """Return the full action for this turn."""
        market = self._market(obs)
        me = obs["farms"][obs["player"]]
        priv = obs["private"]
        units: list[Pos] = [tuple(me["farmer"])] + [tuple(h) for h in me["hands"]]
        tasks = self._tasks(obs)
        claimed: set[Pos] = set()
        seeds_left = dict(priv["seeds"])
        cmds: list[list[Any]] = []
        for idx, pos in enumerate(units):
            inv = priv["inventories"][idx] if idx < len(priv["inventories"]) else {}
            cmds.append(self._unit_cmd(idx, pos, inv, tasks, claimed, seeds_left, obs))
        return {"farmer": cmds[0], "hands": cmds[1:], "market": market}

    def _tasks(self, obs: dict[str, Any]) -> dict[Pos, tuple[int, list[Any]]]:
        me = obs["farms"][obs["player"]]
        shed = obs["private"]["shed"]
        day = self.day
        tasks: dict[Pos, tuple[int, list[Any]]] = {}
        empty: list[Pos] = []
        empty_structs: dict[str, list[Pos]] = {"COOP": [], "PASTURE": []}
        for y, row in enumerate(me["tiles"]):
            for x, t in enumerate(row):
                p = (x, y)
                if t == "LOCKED":
                    continue
                if t is None:
                    empty.append(p)
                    continue
                kind = t.get("kind")
                if kind == "WEED":
                    tasks[p] = (PRIO["DIG"], ["DIG"])
                elif kind == "PLANT":
                    if not t["watered_today"]:
                        tasks[p] = (PRIO["WATER"], ["WATER"])
                    elif plant_ready(t, day, self.final_day):
                        tasks[p] = (PRIO["HARVEST"], ["HARVEST"])
                    elif t["crop"] in self.fertilise and wants_fertiliser(t, day):
                        tasks[p] = (PRIO["FERTILIZE"], ["FERTILIZE"])
                elif "animal" in t:
                    if not t["fed_today"]:
                        tasks[p] = (PRIO["FEED"], ["FEED"])
                    elif t["yield_units"] > 0:
                        tasks[p] = (PRIO["HARVEST"], ["HARVEST"])
                    elif t["fertilizer_available"]:
                        tasks[p] = (PRIO["COLLECT_FERTILIZER"], ["COLLECT_FERTILIZER"])
                    elif not t["cared_today"]:
                        tasks[p] = (PRIO["CARE"], ["CARE"])
                elif kind in empty_structs:
                    empty_structs[kind].append(p)
        # Animals waiting in the shed / inventories go onto empty structures, building if needed.
        held = {a: shed.get(a, 0) + sum(inv.get(a, 0) for inv in obs["private"]["inventories"])
                for a in kg.ANIMALS}
        for animal, n in held.items():
            struct = kg.ANIMALS[animal]["structure"]
            for p in empty_structs[struct][:n]:
                tasks[p] = (PRIO["PLACE"], ["PLACE", animal])
            n -= min(n, len(empty_structs[struct]))
            empty_structs[struct] = empty_structs[struct][len(empty_structs[struct]):]
            for _ in range(n):
                if not empty:
                    break
                p = self._pop_near_shed(empty, obs)
                tasks[p] = (PRIO["BUILD_" + struct], ["BUILD_" + struct])
        # Sow the plan's crops on the remaining empty plots, nearest the shed first.
        for crop, n in self.to_plant.items():
            for _ in range(n):
                if not empty:
                    break
                p = self._pop_near_shed(empty, obs)
                tasks[p] = (PRIO["PLANT"], ["PLANT", crop])
        return tasks

    @staticmethod
    def _pop_near_shed(empty: list[Pos], obs: dict[str, Any]) -> Pos:
        half = len(obs["farms"][obs["player"]]["tiles"]) // 2
        empty.sort(key=lambda p: abs(p[0] - half + 0.5) + abs(p[1] - half + 0.5))
        return empty.pop(0)

    def _unit_cmd(self, idx: int, pos: Pos, inv: dict[str, int], tasks: dict[Pos, tuple[int, list[Any]]],
                  claimed: set[Pos], seeds_left: dict[str, int], obs: dict[str, Any]) -> list[Any]:
        board = len(obs["farms"][obs["player"]]["tiles"])
        shed_tiles = kg._shed_access_tiles(board)
        at_shed = pos in shed_tiles
        shed = obs["private"]["shed"]

        if self.final_day and obs["hour"] >= self.final_sell_hour:
            if any(v > 0 for v in inv.values()):
                return ["DROP"] if at_shed else _step_toward(pos, _nearest(pos, shed_tiles))
        here = tasks.get(pos)
        if here and pos not in claimed and self._can_do(idx, here[1], inv, seeds_left):
            return self._commit(pos, here[1], claimed, seeds_left)
        # The farmer (unit 0) fetches items needed for item tasks.
        if idx == 0 and at_shed:
            places = sum(1 for _, (_, c) in tasks.items() if c[0] == "PLACE")
            for animal in kg.ANIMALS:
                pending = sum(1 for _, (_, c) in tasks.items() if c == ["PLACE", animal])
                if pending and inv.get(animal, 0) < pending and shed.get(animal, 0) > 0:
                    return ["PICKUP", animal, min(pending - inv.get(animal, 0), shed[animal])]
            for need, item, extra in (("FEED", "WHEAT", places), ("FERTILIZE", "FERTILIZER", 0)):
                pending = sum(1 for _, (_, c) in tasks.items() if c[0] == need) + extra
                if pending and inv.get(item, 0) < pending and shed.get(item, 0) > 0:
                    return ["PICKUP", item, min(pending - inv.get(item, 0), shed[item])]

        best: tuple[float, Pos, list[Any]] | None = None
        for p, (prio, cmd) in tasks.items():
            if p in claimed or not self._can_do(idx, cmd, inv, seeds_left):
                continue
            if idx == 0 and (cmd[0] in ITEM_FOR or cmd[0] == "PLACE"):
                prio = 0  # only the farmer carries items, so these come first for him
            score = prio * 3 + abs(p[0] - pos[0]) + abs(p[1] - pos[1])
            if best is None or score < best[0]:
                best = (score, p, cmd)

        # The farmer fetches feed / fertiliser / animals first: hands cover the watering.
        if idx == 0 and not at_shed and self._needs_fetch(tasks, inv, shed):
            if best is None or best[0] > PRIO["FEED"] * 3 + 1:
                return _step_toward(pos, _nearest(pos, shed_tiles))
        if best is None:
            return ["PASS"]
        _, target, cmd = best
        if target != pos:
            claimed.add(target)
            return _step_toward(pos, target)
        return self._commit(pos, cmd, claimed, seeds_left)

    def _commit(self, pos: Pos, cmd: list[Any], claimed: set[Pos], seeds_left: dict[str, int]) -> list[Any]:
        claimed.add(pos)
        if cmd[0] == "PLANT":
            seeds_left[cmd[1]] -= 1
            self.to_plant[cmd[1]] = max(0, self.to_plant.get(cmd[1], 0) - 1)
        return list(cmd)

    @staticmethod
    def _can_do(idx: int, cmd: list[Any], inv: dict[str, int], seeds_left: dict[str, int]) -> bool:
        op = cmd[0]
        if op in ITEM_FOR or op == "PLACE":
            item = cmd[1] if op == "PLACE" else ITEM_FOR[op]
            return idx == 0 and inv.get(item, 0) > 0
        if op == "PLANT":
            return seeds_left.get(cmd[1], 0) > 0
        return True

    @staticmethod
    def _needs_fetch(tasks: dict[Pos, tuple[int, list[Any]]], inv: dict[str, int], shed: dict[str, int]) -> bool:
        for _, (_, cmd) in tasks.items():
            op = cmd[0]
            item = cmd[1] if op == "PLACE" else ITEM_FOR.get(op)
            if item and inv.get(item, 0) <= 0 and shed.get(item, 0) > 0:
                return True
        return False


def _nearest(pos: Pos, targets: list[Pos]) -> Pos:
    return min(targets, key=lambda t: abs(t[0] - pos[0]) + abs(t[1] - pos[1]))


def _step_toward(pos: Pos, target: Pos) -> list[Any]:
    if target[0] > pos[0]:
        return ["EAST"]
    if target[0] < pos[0]:
        return ["WEST"]
    if target[1] > pos[1]:
        return ["SOUTH"]
    if target[1] < pos[1]:
        return ["NORTH"]
    return ["PASS"]
