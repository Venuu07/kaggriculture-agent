"""FarmEnv: a gym-style wrapper around the official Kaggriculture engine.

One `step()` = one in-game day (24 engine turns). The agent submits a daily plan
(see kagri/plan.py); the Foreman executes it turn by turn. Player 2 is a built-in
opponent that shares the market with us, exactly like a competition match.

    env = FarmEnv()
    obs = env.reset(seed=0)
    while not done:
        obs, reward, done, info = env.step(plan)

Reward = change in cash during the day. Score = final cash (competition rule);
profit = final cash - starting cash.
"""
from __future__ import annotations

import copy
import random
from typing import Any

from .config import load_config
from .engine import kaggriculture as kg
from .engine.driver import BUILTIN_OPPONENTS, GameDriver
from .economics import sale_proceeds
from .foreman import Foreman, plant_ready
from .plan import HARVEST_AGE, empty_plan, validate_plan

WEATHERS = ["sunny", "cloudy", "heavy_rain", "drought"]


class FarmEnv:
    """Gym-style farm environment. Deterministic given a seed."""

    def __init__(self, events: bool | None = None, opponent: str | None = None,
                 config: dict[str, Any] | None = None, weather: str | None = None,
                 scenario: dict[str, Any] | None = None) -> None:
        self.cfg = config or load_config()
        g = self.cfg["game"]
        self.turns_per_day = int(g["turns_per_day"])
        self.episode_steps = int(g["episode_steps"])
        self.n_days = self.episode_steps // self.turns_per_day
        self.last_day = self.n_days - 1
        self.starting_money = float(g["starting_money"])
        self.events_on = self.cfg["events"]["enabled"] if events is None else events
        self.opponent_name = opponent or g.get("opponent", "starter")
        self.game: GameDriver | None = None
        self.seed = 0
        self.price_history: list[dict[str, int]] = []
        self.event_log: list[dict[str, Any]] = []
        self.me = 0  # which seat this view controls (0 or 1); see view()
        # A scripted crisis (kagri/scenarios.py): fixed weather days, pest days and price shocks.
        # When set, random pests and shocks are switched off so the experiment is controlled.
        self.scenario: dict[str, Any] = scenario or {}
        if self.scenario:
            self.events_on = True
        self.real_weather: dict[str, Any] | None = None
        if weather:
            from .realweather import load_season
            self.real_weather = load_season(weather)
            self.events_on = True

    @property
    def them(self) -> int:
        return 1 - self.me

    def view(self, player: int) -> "FarmEnv":
        """A view of the same game from `player`'s seat (shares the game; used by the Arena)."""
        v = copy.copy(self)
        v.me = player
        return v

    # ------------------------------------------------------------------ api
    def reset(self, seed: int = 0) -> dict[str, Any]:
        """Start a new season. Returns the first observation."""
        self.seed = int(seed)
        g = self.cfg["game"]
        self.game = GameDriver(seed, self.episode_steps, int(g["starting_money"]), int(g["board_size"]),
                               self.turns_per_day)
        self._weather = self._roll_weather()
        self.price_history = [dict(self.game.obs0.market["prices"])]
        self.event_log = []
        self.today_events = self._apply_events(0)
        return self.observe()

    def step(self, plan: dict[str, Any], rival: Any = None) -> tuple[dict[str, Any], float, bool, dict[str, Any]]:
        """Run one day with `plan`. Returns (obs, reward, done, info).

        `rival` controls the other seat: None = the configured built-in opponent, a str = a built-in
        bot by name, or a dict = a daily plan executed by its own Foreman (two-agent Arena match).
        """
        assert self.game is not None, "call reset() first"
        if self.done:
            return self.observe(), 0.0, True, {"rejected": ["episode already finished"]}
        state = self.observe()
        clean, rejected = validate_plan(plan, state, self.cfg["foreman"]["max_hands"])
        cash0 = self.cash
        day = self.day
        sell_hour = self.cfg["foreman"]["final_day_sell_hour"]
        foreman = Foreman(clean, day, self.last_day, sell_hour)
        rival_info: dict[str, Any] = {}
        if isinstance(rival, dict):
            rview = self.view(self.them)
            rclean, rrej = validate_plan(rival, rview.observe(), self.cfg["foreman"]["max_hands"])
            rfore = Foreman(rclean, day, self.last_day, sell_hour)
            rival_cash0 = rview.cash
            rival_info = {"plan": rclean, "rejected": rrej}
            opp = rfore.act
        else:
            opp = BUILTIN_OPPONENTS.get(rival or self.opponent_name, BUILTIN_OPPONENTS["pass"])
        sales: dict[str, list[float]] = {}  # item -> [units sold, revenue]
        while not self.game.done and self.game.obs0.day == day:
            obs0 = self.game.observation(self.me)
            action = foreman.act(obs0)
            shed_before = dict(obs0["private"]["shed"])
            inv_before = dict(obs0["market"]["inventory"])
            other = opp(self.game.observation(self.them))
            self.game.step([action, other] if self.me == 0 else [other, action])
            shed_after = self.game.observation(self.me)["private"]["shed"]
            for item in {o[1] for o in action["market"] if o[0] == "SELL"}:
                sold = shed_before.get(item, 0) - shed_after.get(item, 0)
                if sold > 0:
                    s = sales.setdefault(item, [0, 0.0])
                    s[0] += sold
                    s[1] += sale_proceeds(item, sold, inv_before[item])[0]
        self.price_history.append(dict(self.game.obs0.market["prices"]))
        reward = self.cash - cash0
        info = {"day": day, "plan": clean, "rejected": rejected, "events": self.today_events,
                "sales": sales, "cash": self.cash}
        if rival_info:
            rival_info["reward"] = self.view(self.them).cash - rival_cash0
            info["rival"] = rival_info
        if not self.done:
            self.today_events = self._apply_events(self.day)
        return self.observe(), reward, self.done, info

    @property
    def done(self) -> bool:
        return self.game is None or self.game.done

    @property
    def day(self) -> int:
        return min(int(self.game.obs0.day), self.last_day) if self.game else 0

    @property
    def cash(self) -> float:
        return float(self.game.obs0.farms[self.me]["money"]) if self.game else 0.0

    @property
    def profit(self) -> float:
        return self.cash - self.starting_money

    def clone(self) -> "FarmEnv":
        """Independent copy for look-ahead (`simulate_action`)."""
        return copy.deepcopy(self)

    def simulate(self, plan: dict[str, Any], days: int = 3, follow_up: Any = None) -> dict[str, Any]:
        """Play `plan` today then `follow_up` (a plan, or a function obs -> plan; default: sell
        everything, plant nothing) on a copy of the environment.

        Returns cash and net-worth change so plans with delayed payoff can be compared fairly.
        """
        sim = self.clone()
        start_worth = sim.net_worth()
        start_cash = sim.cash
        follow = follow_up or {"sell": {p: "all" for p in kg.PRODUCTS}}
        rejected: list[str] = []
        obs = sim.observe()
        for i in range(days):
            if sim.done:
                break
            nxt = plan if i == 0 else (follow(obs) if callable(follow) else follow)
            obs, _, _, info = sim.step(nxt)
            if i == 0:
                rejected = info["rejected"]
        return {"days": days, "cash_change": round(sim.cash - start_cash, 1),
                "net_worth_change": round(sim.net_worth() - start_worth, 1), "rejected": rejected}

    # ------------------------------------------------------------ valuation
    def net_worth(self) -> float:
        """Cash + 80% market value of stock + expected value of growing crops and animals."""
        assert self.game is not None
        prices = self.game.obs0.market["prices"]
        priv = self.game.state[self.me].observation.private
        worth = self.cash
        for item, n in priv["shed"].items():
            if item in prices:
                worth += 0.8 * n * prices[item]
            elif item in kg.ANIMALS:
                worth += 0.5 * n * kg.ANIMALS[item]["cost"]
        days_left = self.last_day - self.day
        for row in self.game.obs0.farms[self.me]["tiles"]:
            for t in row:
                if not isinstance(t, dict):
                    continue
                if t.get("kind") == "PLANT":
                    worth += expected_plant_value(t, self.day, prices)
                elif "animal" in t:
                    a = kg.ANIMALS[t["animal"]]
                    worth += t["yield_units"] * prices[a["product"]] * 0.8
                    worth += min(days_left, 5) * (prices[a["product"]] / a["interval"] + 0.5 * prices["FERTILIZER"]
                                                  - prices["WHEAT"]) * 0.5
        return worth

    # ---------------------------------------------------------- observation
    def observe(self) -> dict[str, Any]:
        """Compact, JSON-friendly observation used by agents, tools and the UI."""
        assert self.game is not None
        o = self.game.obs0
        me = o.farms[self.me]
        priv = self.game.state[self.me].observation.private
        plots: list[dict[str, Any]] = []
        grid: list[list[str]] = []
        free = weeds = 0
        animals: dict[str, int] = {}
        crops: dict[str, int] = {}
        for y, row in enumerate(me["tiles"]):
            grow: list[str] = []
            for x, t in enumerate(row):
                if t == "LOCKED":
                    grow.append("#")
                    continue
                if t is None:
                    free += 1
                    grow.append(".")
                    continue
                kind = t.get("kind")
                if kind == "WEED":
                    weeds += 1
                    grow.append("x")
                elif kind == "PLANT":
                    age = self.day - t["planted_day"]
                    crops[t["crop"]] = crops.get(t["crop"], 0) + 1
                    target = HARVEST_AGE[t["crop"]]
                    plots.append({"x": x, "y": y, "crop": t["crop"], "age": age, "yield": t["yield_units"],
                                  "watered": t["watered_today"], "ready_in": max(0, target - age),
                                  "fertilised": t["fertilized_until_day"] >= self.day})
                    grow.append(t["crop"][:2])
                elif "animal" in t:
                    animals[t["animal"]] = animals.get(t["animal"], 0) + 1
                    grow.append(t["animal"][:2].lower())
                else:
                    grow.append(kind[0])
            grid.append(grow)
        n_extra = len(me["unlocked_quadrants"]) - 1
        prices = dict(o.market["prices"])
        return {
            "day": self.day, "last_day": self.last_day, "days_left": self.last_day - self.day,
            "cash": round(self.cash, 1), "profit": round(self.profit, 1),
            "opponent_cash": round(float(o.farms[self.them]["money"]), 1),
            "free_plots": free, "weeds": weeds, "crops_growing": crops, "animals": animals,
            "plots": plots, "grid": grid,
            "land_quadrants": list(me["unlocked_quadrants"]),
            "next_land_cost": kg.LAND_PRICES[n_extra] if n_extra < len(kg.LAND_PRICES) else None,
            "shed": {k: v for k, v in priv["shed"].items() if v},
            "shed_capacity_left": 100 - sum(priv["shed"].values()),
            "seeds": {k: v for k, v in priv["seeds"].items() if v},
            "prices": prices,
            "market_inventory": dict(o.market["inventory"]),
            "town_shops": list(o.town["unlocked_shops"]),
            "weather": self.today_events if hasattr(self, "today_events") else {},
            "forecast": self.forecast(),
            "done": self.done,
        }

    # --------------------------------------------------------------- events
    def _roll_weather(self) -> list[str]:
        if self.real_weather:
            days = [d["weather"] for d in self.real_weather["days"]]
            return (days + ["sunny"] * self.n_days)[: self.n_days]
        rng = random.Random(self.seed * 7919 + 17)
        probs = self.cfg["events"]["weather_probs"]
        names = list(probs)
        days = [rng.choices(names, weights=[probs[n] for n in names])[0] for _ in range(self.n_days)]
        if self.scenario:
            base = self.scenario.get("base_weather")
            if base:
                days = [base] * self.n_days
            for d, w in self.scenario.get("weather", {}).items():
                if 0 <= int(d) < self.n_days:
                    days[int(d)] = w
        return days

    def forecast(self) -> list[dict[str, Any]]:
        """Noisy weather forecast for the next few days (deterministic per seed)."""
        if not self.events_on or self.game is None:
            return []
        ev = self.cfg["events"]
        out = []
        for d in range(self.day + 1, min(self.n_days, self.day + 1 + ev["forecast_days"])):
            rng = random.Random(self.seed * 104729 + d)
            truth = self._weather[d]
            guess = truth if rng.random() < ev["forecast_accuracy"] else rng.choice(WEATHERS)
            out.append({"day": d, "weather": guess, "confidence": ev["forecast_accuracy"]})
        return out

    def _apply_events(self, day: int) -> dict[str, Any]:
        """Apply today's weather and random events to both farms (start of day)."""
        if not self.events_on or self.game is None:
            return {"weather": "n/a (events off)", "events": []}
        ev = self.cfg["events"]
        rng = random.Random(self.seed * 15485863 + day * 31 + 7)
        weather = self._weather[day]
        notes: list[str] = []
        o = self.game.obs0
        for farm in o.farms:
            for row in farm["tiles"]:
                for t in row:
                    if not (isinstance(t, dict) and t.get("kind") == "PLANT"):
                        continue
                    if weather == "heavy_rain" and not t["watered_today"]:
                        _rain_water(t, day)
                    elif weather == "drought":
                        t["consecutive_unwatered"] = max(1, t["consecutive_unwatered"])
        if weather == "heavy_rain":
            notes.append("Heavy rain watered every plant for free.")
        if weather == "drought":
            notes.append("Drought: any plant not watered today will die tonight.")
        scripted = bool(self.scenario)
        pest_today = (day in self.scenario.get("pests", [])) if scripted else rng.random() < ev["pest_outbreak_prob"]
        pest_rate = float(self.scenario.get("pest_rate", 0.15)) if scripted else 0.15
        if pest_today:
            killed = 0
            for farm in o.farms:
                for y, row in enumerate(farm["tiles"]):
                    for x, t in enumerate(row):
                        if (isinstance(t, dict) and t.get("kind") == "PLANT"
                                and t["fertilized_until_day"] < day and rng.random() < pest_rate):
                            farm["tiles"][y][x] = {"kind": "WEED"}
                            killed += 1
            notes.append(f"Pest outbreak destroyed {killed} unprotected plants (fertilised plants resist).")
        for item, mult in (self.scenario.get("shocks", {}).get(str(day), []) if scripted else []):
            o.market["inventory"][item] += int(kg.MARKET_PARAMS[item]["T"] * mult)
            kg._refresh_prices(o.market)
            kind = "glut" if mult > 0 else "shortage"
            notes.append(f"Market shock: {kind} of {item.lower()}, price now ${o.market['prices'][item]}.")
        if not scripted and rng.random() < ev["price_shock_prob"]:
            item = rng.choice([p for p in kg.PRODUCTS if p != "FERTILIZER"])
            params = kg.MARKET_PARAMS[item]
            glut = rng.random() < 0.5
            delta = int(params["T"] * (0.4 if glut else -0.5))
            o.market["inventory"][item] += delta
            kg._refresh_prices(o.market)
            notes.append(f"Price shock: {'glut' if glut else 'shortage'} of {item}, price now ${o.market['prices'][item]}.")
        record: dict[str, Any] = {"day": day, "weather": weather, "events": notes}
        if self.real_weather and day < len(self.real_weather["days"]):
            real = self.real_weather["days"][day]
            record["real"] = {"date": real["date"], "rain_mm": real["rain_mm"], "tmax_c": real["tmax_c"],
                              "place": self.real_weather["label"].split(" (")[0]}
        self.event_log.append(record)
        return record


def _rain_water(t: dict[str, Any], day: int) -> None:
    """Same effect as the WATER command, applied by rain."""
    t["watered_today"] = True
    cd = kg.CROPS[t["crop"]]
    if not cd["ongoing"]:
        age = day - t["planted_day"]
        start = (cd["max_yield_day"] + 1) // 2
        if start <= age <= cd["max_yield_day"]:
            bonus = 2 if t["fertilized_until_day"] >= day else 1
            t["yield_units"] = min(cd["max_yield"], t["yield_units"] + bonus)


def expected_plant_value(t: dict[str, Any], day: int, prices: dict[str, int]) -> float:
    """Rough value of a growing plant: expected units x price x progress."""
    cd = kg.CROPS[t["crop"]]
    age = day - t["planted_day"]
    target = HARVEST_AGE[t["crop"]]
    if cd["ongoing"]:
        units = max(t["yield_units"], 0) + max(0, cd["max_yield"] - max(0, age - cd["first_yield_day"] + 1))
    else:
        units = max(t["yield_units"], 1 + max(0, (cd["max_yield_day"] - (cd["max_yield_day"] + 1) // 2 + 1)))
        units = min(units, cd["max_yield"])
    progress = min(1.0, (age + 1) / (target + 1))
    return 0.8 * units * prices[t["crop"]] * progress


__all__ = ["FarmEnv", "empty_plan", "plant_ready"]
