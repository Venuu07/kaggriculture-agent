# The Kaggriculture competition, and how this project models it

Source: the Kaggle competition page "Kaggriculture" (overview, evaluation, how to play, configuration),
plus the official simulator code shipped in `kaggle-environments` 1.33.3
(`envs/kaggriculture/kaggriculture.py`), which we vendored into `kagri/engine/kaggriculture.py`.

## 1. Goal

Two players each run a farm for one 30-day season (720 turns: 24 turns per day). Whoever has
**the most coins in the bank at the end** wins. Unsold stock counts for nothing. On Kaggle,
agents play each other on a ladder with a skill rating (win / loss / tie only; the coin margin
does not matter), and the final leaderboard is a Bradley-Terry tournament.

## 2. Farm state

| Part | Details |
|---|---|
| Money | Starts at **$3,000** |
| Land | 10x10 grid in four 5x5 quadrants. Only NW is owned at the start; NE, SW, SE cost **$1,000, $2,000, $4,000** |
| Tiles | empty, locked, plant, weed, coop/pasture (with or without an animal) |
| Shed | In the centre; holds up to 100 non-seed items. Overflow is lost |
| Seeds | Separate store, used directly by PLANT |
| Workers | The farmer, plus farm hands hired per day (cost Fibonacci: $1, 1, 2, 3, 5, 8, 13 ...) |
| Town | A new shop unlocks every 3 days (max 8). Shops and the town centre consume products, which raises prices |

## 3. Crops and animals

| Item | Seed / cost | Base price | Time to yield | Yield | Notes |
|---|---|---|---|---|---|
| Wheat | $10 | $25 | 2-4 days | 4 (6 fertilised) | also animal feed |
| Carrot | $20 | $35 | 2-3 days | 3 (4 fertilised) | |
| Tomato | $50 | $60 | 8-11 days | 4 harvests | ongoing crop |
| Strawberry | $100 | $120 | 10-16 days | 4 harvests (every other day) | ongoing crop |
| Melon | $80 | $250 | 10 days (8 fertilised) | 6 | premium, crashes on gluts |
| Goose | $300 | egg $50 | 4 days | 1 egg/day | coop |
| Cow | $400 | milk $160 | 8 days | 1 milk / 2 days | pasture |
| Sheep | $500 | wool $200 | 6 days | 1 wool / 3 days | pasture |
| Fertiliser | $100 (market) | $100 | - | - | every animal drops 1/day for free |

Rules that matter: plants must be watered every day (2 dry days and they become weeds), animals
must be fed 1 wheat per day (2 hungry days and they escape), and harvesting one-time crops at the
right age gives the most units.

## 4. Actions

Per turn, each worker gets one action: move (N/S/E/W), PLANT, WATER, HARVEST, FERTILIZE, DIG,
BUILD_COOP, BUILD_PASTURE, PLACE, FEED, CARE, COLLECT_FERTILIZER, PICKUP, DROP, PASS.
Plus up to 10 market orders per turn: BUY_SEED, BUY_ANIMAL, BUY_PRODUCT (wheat, fertiliser),
SELL, HIRE, BUY_LAND.

## 5. Prices

Each product has a market inventory (starts at 10,000). Selling adds to it and lowers the price;
town demand drains it and raises the price. The curve has a different shape on each side:

`price(inv) = base ± amp · f(|inv − 10000|)`, floored at $1.

Premium goods (melon, strawberry, milk, wool) fall to $1 after a modest glut. So **what you
plant and when you sell matter as much as how much you grow.**

## 6. Weather

**There is no weather in the competition.** See section 9 for the weather and events we added.

## 7. What is given vs what we assumed

| Topic | Given by the competition | Our choice / assumption |
|---|---|---|
| Rules engine | Official code in `kaggle-environments` | **Vendored unchanged** (only the framework import and HTML renderer were removed). The full package needs jax/open_spiel/transformers, which is too fragile on Windows |
| Opponent | Another submitted agent | The built-in **"starter" bot** plays player 2 on the shared market. We optimise our own profit, not win/loss |
| Decision frequency | One action per worker per turn (720 turns) | The agent makes **one strategic decision per day** (30 per season). A deterministic **Foreman** turns it into turn-by-turn commands. 720 LLM calls per game is too slow and costly on free tiers |
| What the agent controls | Everything | Economics: crop mix, sales, animals, fertiliser, labour, land. The Foreman always waters, harvests, weeds, feeds and cares (standing orders) |
| Score | Final coins | `profit = final cash − $3,000` (same ranking as final coins). Unsold stock counts for nothing, as in the competition |
| Weather / events | None | Optional layer, **on by default** in our runs (section 9). Turn off with `--no-events` for competition-faithful runs |
| Hands | No limit (cost rises) | Plans may hire up to 10 hands per day ($143 total) |

## 8. Scoring in this project

Every agent plays the same seeds. We report mean ± standard deviation of profit over 5 seeds
(`python -m kagri.evaluate`). The environment is deterministic for a given seed: the same plans
give the same result, which `tests/test_env.py` checks.

## 9. Our extension: weather and events (`kagri/env.py`)

Applied at the start of each day to both farms, decided by the seed:

| Event | Probability | Effect |
|---|---|---|
| Sunny / cloudy | 55% / 20% | none |
| Heavy rain | 12% | waters every plant for free (with the watering yield bonus) |
| Drought | 13% | no grace day: any plant not watered today dies tonight |
| Pest outbreak | 6% | ~15% of unfertilised plants become weeds |
| Price shock | 8% | a sudden glut (+40% of T) or shortage (−50% of T) of one product |

A noisy 3-day forecast (80% accurate) is part of every observation, so the agent can plan ahead.
All numbers live in `kagri/config.yaml`.
