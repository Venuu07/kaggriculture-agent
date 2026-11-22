"""ShopEnv: a 30-day kirana store. Same decision shape as the farm: buy stock today, sell later,
perishables spoil, prices move demand, and weather and events shift what customers want.

Daily plan:
    {"order": {"MILK": 60, ...},     # arrives tomorrow morning (supplier delays can add a day)
     "price": {"MILK": 32, ...}}     # today's shelf price, 0.7x to 1.5x the usual price

Score: cash after 30 days (start Rs 10,000). Deterministic for a seed.
"""
from __future__ import annotations

import copy
import math
import random
from typing import Any

PRODUCTS: dict[str, dict[str, Any]] = {
    #            cost  usual price  shelf life (days)  customers/day  price sensitivity
    "MILK":      {"cost": 22, "price": 30, "life": 2,   "demand": 40, "elasticity": 1.2, "label": "Milk (packet)"},
    "BREAD":     {"cost": 25, "price": 35, "life": 3,   "demand": 25, "elasticity": 1.5, "label": "Bread"},
    "RICE":      {"cost": 40, "price": 55, "life": 999, "demand": 30, "elasticity": 1.0, "label": "Rice (kg)"},
    "ICE_CREAM": {"cost": 30, "price": 50, "life": 999, "demand": 10, "elasticity": 2.0, "label": "Ice cream"},
    "SWEETS":    {"cost": 60, "price": 100, "life": 5,  "demand": 6,  "elasticity": 1.8, "label": "Sweets box"},
}
START_CASH = 10_000.0
CAPACITY = 450
HOLDING = 0.01
DAYS = 30
WEATHERS = ["normal", "heatwave", "rain"]


class ShopEnv:
    """Gym-style store: reset(seed) -> obs; step(plan) -> obs, reward, done, info."""

    def __init__(self) -> None:
        self.seed = 0

    # --------------------------------------------------------------- setup
    def reset(self, seed: int = 0) -> dict[str, Any]:
        self.seed = seed
        rng = random.Random(seed * 7907 + 3)
        self.day = 0
        self.cash = START_CASH
        self.stock: dict[str, list[list[int]]] = {p: [] for p in PRODUCTS}  # batches [qty, age]
        self.pipeline: list[tuple[int, str, int]] = []  # (arrival_day, product, qty)
        self.prices = {p: d["price"] for p, d in PRODUCTS.items()}
        self.history: list[dict[str, Any]] = []
        self.weather = ["normal"] * DAYS
        for _ in range(2):
            start = rng.randint(3, 24)
            for d in range(start, min(DAYS, start + rng.randint(3, 5))):
                self.weather[d] = "heatwave"
        for _ in range(3):
            d = rng.randint(1, DAYS - 1)
            if self.weather[d] == "normal":
                self.weather[d] = "rain"
        fest = rng.randint(10, 24)
        self.festival = {fest, fest + 1}
        promo_start = rng.randint(5, 25)
        self.promo = {"product": rng.choice(list(PRODUCTS)), "days": set(range(promo_start, promo_start + 3))}
        self.delay_day = rng.randint(4, 26)
        # opening stock
        for p, d in PRODUCTS.items():
            self.stock[p].append([int(d["demand"] * min(2, d["life"])), 0])
        return self.observe()

    # ----------------------------------------------------------------- api
    @property
    def done(self) -> bool:
        return self.day >= DAYS

    @property
    def profit(self) -> float:
        return self.cash - START_CASH

    def step(self, plan: Any) -> tuple[dict[str, Any], float, bool, dict[str, Any]]:
        if self.done:
            return self.observe(), 0.0, True, {"rejected": ["season over"]}
        clean, rejected = self.validate(plan)
        cash0 = self.cash
        day = self.day
        for p, price in clean["price"].items():
            self.prices[p] = price
        rng = random.Random(self.seed * 104729 + day * 13)
        sold, demand, wasted = {}, {}, {}
        revenue = 0.0
        for p, d in PRODUCTS.items():
            want = self._expected_demand(p, day, self.prices[p]) * math.exp(rng.gauss(0, 0.15))
            want = int(round(want))
            have = sum(q for q, _ in self.stock[p])
            n = min(have, want)
            self._take(p, n)
            sold[p], demand[p] = n, want
            revenue += n * self.prices[p]
        self.cash += revenue
        # order: pay now, arrives tomorrow (or the day after during a supplier delay)
        order_cost = 0.0
        for p, q in clean["order"].items():
            if q > 0:
                order_cost += q * PRODUCTS[p]["cost"]
                lead = 2 if day == self.delay_day else 1
                self.pipeline.append((day + lead, p, q))
        self.cash -= order_cost
        # ageing, spoilage, holding cost
        for p, d in PRODUCTS.items():
            keep = []
            w = 0
            for q, age in self.stock[p]:
                if age + 1 >= d["life"]:
                    w += q
                else:
                    keep.append([q, age + 1])
            self.stock[p] = keep
            wasted[p] = w
        holding = HOLDING * sum(q * PRODUCTS[p]["cost"] for p in PRODUCTS for q, _ in self.stock[p])
        self.cash -= holding
        self.day += 1
        arrived = [x for x in self.pipeline if x[0] <= self.day]
        self.pipeline = [x for x in self.pipeline if x[0] > self.day]
        room = CAPACITY - self._units()
        for _, p, q in arrived:
            q = min(q, max(0, room))
            if q:
                self.stock[p].append([q, 0])
                room -= q
        reward = self.cash - cash0
        info = {"day": day, "plan": clean, "rejected": rejected, "sold": sold, "demand": demand, "wasted": wasted,
                "revenue": round(revenue), "order_cost": round(order_cost), "holding": round(holding, 1),
                "events": self._events(day)}
        self.history.append({"day": day, "sold": sold, "demand": demand, "wasted": wasted})
        return self.observe(), reward, self.done, info

    def validate(self, plan: Any) -> tuple[dict[str, Any], list[str]]:
        rej: list[str] = []
        clean: dict[str, Any] = {"order": {}, "price": {}}
        if not isinstance(plan, dict):
            return clean, ["plan must be a JSON object"]
        budget = self.cash
        room = CAPACITY - self._units() - sum(q for _, _, q in self.pipeline)
        for p, q in (plan.get("order") or {}).items():
            p = str(p).upper()
            try:
                q = int(q)
            except (TypeError, ValueError):
                rej.append(f"order {p}: quantity must be a number")
                continue
            if p not in PRODUCTS or q < 0:
                rej.append(f"order: invalid entry {p}={q}")
                continue
            fit = min(q, int(budget // PRODUCTS[p]["cost"]), max(0, room))
            if fit < q:
                rej.append(f"order {p}: trimmed {q}->{fit} (cash/shelf space)")
            if fit > 0:
                clean["order"][p] = fit
                budget -= fit * PRODUCTS[p]["cost"]
                room -= fit
        for p, price in (plan.get("price") or {}).items():
            p = str(p).upper()
            try:
                price = float(price)
            except (TypeError, ValueError):
                rej.append(f"price {p}: must be a number")
                continue
            if p not in PRODUCTS:
                rej.append(f"price: unknown product {p}")
                continue
            lo, hi = 0.7 * PRODUCTS[p]["price"], 1.5 * PRODUCTS[p]["price"]
            if not lo <= price <= hi:
                rej.append(f"price {p}: {price:.0f} outside {lo:.0f}-{hi:.0f}, clamped")
                price = min(hi, max(lo, price))
            clean["price"][p] = round(price)
        return clean, rej

    def clone(self) -> "ShopEnv":
        return copy.deepcopy(self)

    def simulate(self, plan: dict[str, Any], days: int = 3, follow_up: Any = None) -> dict[str, Any]:
        """Play `plan` today, then `follow_up` (function obs -> plan), on a copy. Values leftover stock at cost."""
        sim = self.clone()
        start = sim.cash + sim.stock_value()
        obs = sim.observe()
        for i in range(days):
            if sim.done:
                break
            obs, _, _, _ = sim.step(plan if i == 0 else (follow_up(obs) if callable(follow_up) else {}))
        end = sim.cash + sim.stock_value()
        return {"days": days, "worth_change": round(end - start), "cash_change": round(sim.cash - self.cash)}

    def stock_value(self) -> float:
        pipe = sum(q * PRODUCTS[p]["cost"] for _, p, q in self.pipeline)
        return pipe + sum(q * PRODUCTS[p]["cost"] * 0.9 for p in PRODUCTS for q, _ in self.stock[p])

    # ---------------------------------------------------------- observation
    def observe(self) -> dict[str, Any]:
        d = min(self.day, DAYS - 1)
        products = {}
        for p, meta in PRODUCTS.items():
            batches = [{"qty": q, "days_left": meta["life"] - age} for q, age in self.stock[p]]
            last = [h["sold"][p] for h in self.history[-5:]]
            products[p] = {"stock": sum(q for q, _ in self.stock[p]), "batches": batches if meta["life"] < 999 else [],
                           "on_order": sum(q for _, pp, q in self.pipeline if pp == p), "price": self.prices[p],
                           "usual_price": meta["price"], "cost": meta["cost"], "shelf_life": meta["life"],
                           "sold_last_days": last, "wasted_total": sum(h["wasted"][p] for h in self.history)}
        return {"day": d, "days_left": DAYS - 1 - d, "cash": round(self.cash, 1), "profit": round(self.profit, 1),
                "products": products, "shelf_space_left": CAPACITY - self._units(), "today": self._events(d),
                "forecast": self.forecast(), "done": self.done}

    def forecast(self) -> list[dict[str, Any]]:
        out = []
        for d in range(self.day + 1, min(DAYS, self.day + 4)):
            rng = random.Random(self.seed * 31337 + d)
            w = self.weather[d] if rng.random() < 0.8 else rng.choice(WEATHERS)
            out.append({"day": d, "weather": w, "festival": d in self.festival})
        return out

    # -------------------------------------------------------------- helpers
    def _events(self, day: int) -> dict[str, Any]:
        notes = []
        w = self.weather[min(day, DAYS - 1)]
        if w == "heatwave":
            notes.append("Heatwave: ice cream demand triples.")
        if w == "rain":
            notes.append("Rain: fewer customers today.")
        if day in self.festival:
            notes.append("Festival: sweets demand x5, milk x1.5.")
        if day in self.promo["days"]:
            notes.append(f"Rival shop promotion on {self.promo['product'].lower().replace('_', ' ')}: -30% demand.")
        if day == self.delay_day:
            notes.append("Supplier delay: today's order arrives a day late.")
        return {"day": day, "weather": w, "events": notes}

    def _expected_demand(self, p: str, day: int, price: float) -> float:
        meta = PRODUCTS[p]
        f = 1.3 if day % 7 in (5, 6) else 1.0
        w = self.weather[min(day, DAYS - 1)]
        if w == "heatwave":
            f *= 3.0 if p == "ICE_CREAM" else (1.1 if p == "MILK" else 1.0)
        elif w == "rain":
            f *= 0.8
        if day in self.festival:
            f *= 5.0 if p == "SWEETS" else (1.5 if p == "MILK" else 1.0)
        if day in self.promo["days"] and p == self.promo["product"]:
            f *= 0.7
        return meta["demand"] * f * (price / meta["price"]) ** (-meta["elasticity"])

    def _take(self, p: str, n: int) -> None:
        batches = sorted(self.stock[p], key=lambda b: -b[1])  # oldest first (FIFO)
        for b in batches:
            t = min(n, b[0])
            b[0] -= t
            n -= t
            if n == 0:
                break
        self.stock[p] = [b for b in batches if b[0] > 0]

    def _units(self) -> int:
        return sum(q for p in PRODUCTS for q, _ in self.stock[p])
