# Learn the project, step by step

This guide explains the whole project in plain words. Read it top to bottom once. Then follow
"Read the code in this order" with the files open next to you.

---

## 1. The game

Kaggriculture is a Kaggle competition. You run a small farm for one season of 30 days.
You start with $3,000 and a 5x5 field (25 plots). Whoever has the most cash on the last day wins.
Unsold stock is worth nothing.

You can grow five crops (wheat, carrot, tomato, strawberry, melon). You can keep three animals
(goose, cow, sheep). Animals eat one wheat a day and also drop one fertiliser a day. You can buy
more land, and you can hire farm hands for the day.

The tricky part is the market. When you sell a lot of one thing, its price falls. Think of a
village market: if you bring 150 melons, nobody pays full price for the last ones.

Each day has 24 turns, so a season is 720 turns. In each turn, the farmer walks one tile or does
one job (water, harvest, plant...).

## 2. The environment (`FarmEnv`)

An "environment" is the game wrapped in a simple interface that an agent can play.
Ours is gym-style, like many AI projects:

```python
env = FarmEnv()
obs = env.reset(seed=0)        # start a season
obs, reward, done, info = env.step(plan)   # play one day
```

- `reset(seed)` starts a new season. The same seed always gives the same season (same weather,
  same events). That makes experiments fair and repeatable.
- `step(plan)` plays **one whole day** (24 turns). `reward` is how much cash changed that day.
- `obs` (observation) is a dictionary describing the farm: cash, plots, prices, weather...

The real game rules are not ours. They are Kaggle's official engine file, copied into
`kagri/engine/kaggriculture.py`. We only wrapped it.

## 3. The Foreman

The agent does not decide every one of the 720 turns. That would be far too many LLM calls.
Instead it decides once a day, at the level of a manager: "plant 10 melons, sell all wheat,
hire 4 hands".

The **Foreman** is like a farm supervisor. It takes the manager's plan and works out the moves:
who walks where, who waters which plant, when to harvest, when to feed the cows. It also has
standing orders it always follows: water every plant, harvest when ripe, pull weeds, feed animals.
It is plain code with no intelligence about economics.

## 4. The plan and validation

A plan is a small JSON dictionary:

```json
{"plant": {"MELON": 6, "WHEAT": 4}, "sell": {"WHEAT": "all"}, "hands": 3, "buy_land": false}
```

Before the Foreman runs it, `validate_plan` checks it, like a bank checking a cheque.
Unknown crop? Rejected. Not enough cash? Trimmed. A melon that cannot be ready before day 29?
Rejected. Each problem gets a written reason. The rest of the plan still runs.
This means even a silly plan can never crash the game. That is our first guardrail.

## 5. Economics: price curves

The official engine has a price formula for each product. Selling one unit pushes the price
down a little; town shops buying slowly push it back up.

`kagri/economics.py` reuses that formula. `sale_proceeds` walks down the curve unit by unit to
say "selling 20 melons now would earn $X". `estimate_crop_profit` predicts what planting N plots
would earn, **including the price drop our own harvest will cause**. That last part is the key
idea that beats the baseline.

## 6. Baselines

To claim our agent is good, we need something to compare against.

- **Random agent**: picks random actions. Shows the floor. About $11k profit.
- **Greedy agent**: a classic rule of thumb. Plant the crop with the best margin on every free
  plot, sell when the price is above average. About $30k. It plants mostly melons and crashes
  the melon price.

## 7. The agent loop (ReAct)

ReAct means "Reason, then Act". Each day the agent does this:

1. Read the farm state (it is in the prompt).
2. Write a short thought: "I should check the weather first."
3. Call one tool: `get_weather_forecast`.
4. Read the result, think again, maybe call another tool.
5. When ready, call `take_action` with the plan.

It is like a person planning a shopping trip: check the fridge, check prices, then decide.
Every reply from the model must be a JSON object:

```json
{"thought": "Melons look crowded, test a mixed plan.", "action": "simulate_action", "args": {"plan": {...}, "days": 5}}
```

## 8. Tools

Tools are Python functions the agent may call. They live in `kagri/agents/tools.py` inside a
`ToolBox`. The agent cannot touch the farm directly. It can only look, estimate and simulate.

The most powerful tool is `simulate_action`. It **copies** the whole environment, plays the
candidate plan on the copy for a few days, and reports how much net worth changed. Like a chess
player thinking a few moves ahead on a second board. The real farm is not changed.

## 9. Prompts

A prompt is the text we send to the LLM. `kagri/agents/prompts.py` builds it from pieces:

- the role ("You are the Market Analyst..."),
- a short summary of the game rules,
- the plan format,
- the list of tools,
- the protocol (reply with one JSON object),
- lessons from earlier seasons.

The user message for the day (`day_message`) holds today's state and the last few days.

## 10. Memory

- **Short-term memory**: a diary of this season (last 5 days). It goes into every prompt so the
  agent remembers what it did yesterday.
- **Long-term memory**: lessons written after each season, saved as JSON in `memory/`. They are
  put into the next season's prompt. Like notes a farmer writes at the end of a year.

## 11. Reflection

After a season ends, `end_episode` gathers facts (`season_evidence`): average sale prices,
when land was bought, how many animals, unsold stock. The model writes 3-5 lessons from those
facts. Being honest: with the offline reasoner, these lessons did not change profit in our
tests. It needs a real LLM to measure properly.

## 12. Multi-agent mode

Instead of one manager, a small team:

- **Planner**: what to plant, whether to buy land or animals.
- **Market Analyst**: what to sell and how much.
- **Agronomist**: fertiliser and how many hands, based on the weather.
- **Manager**: merges the three proposals, fixes conflicts, checks with a simulation, decides.

Like a company meeting where each expert speaks and the boss decides. A real example: the
Agronomist did not know the Planner was buying new land, so it hired too few hands. The Manager
noticed and raised the number. Adding that check is what made the team beat the single agent.

## 13. The offline reasoner

LLM APIs need internet and a key. For a safe demo we built `OfflineReasoner`. It pretends to be
an LLM: it replies with the same JSON, calls the same tools, and writes thoughts using the real
tool results. But inside it is just rules, **not a language model**. The UI labels it clearly.

Our published LLM numbers ($79k single, $89k multi) come from this offline reasoner.

## 14. Evaluation

`python -m kagri.evaluate` plays each agent on 5 seeds and writes:

- `results/results.csv` (one row per season), `results/summary.csv` (mean and std),
- charts as PNG files,
- recorded runs in `runs/` that the dashboard can replay.

We use the same seeds for every agent so the comparison is fair. Mean ± std shows how much the
result varies from season to season.

## 15. Server and React UI

- `kagri/server.py` is a FastAPI app. It answers web requests like `/api/runs` (list recorded
  runs) and `/api/live/{id}/step` (play one live day).
- `web/` is the React app. It is built into `web/dist/` and the Python server serves those files.
  So on demo day you only run `python -m kagri.serve`.

---

## Read the code in this order

Open each file and read the named functions. Each step builds on the one before.

1. `kagri/config.yaml`: all the numbers in one place. Skim it.
2. `kagri/engine/driver.py`: `GameDriver`. How we run the official engine without Kaggle's
   framework. Look at `__init__`, `observation` and `step`.
3. `kagri/env.py`: `FarmEnv.reset`, `FarmEnv.step`, `FarmEnv.observe`, `FarmEnv.simulate`,
   then `_apply_events` (weather) and `net_worth`.
4. `kagri/plan.py`: `validate_plan`. Notice it never raises an error.
5. `kagri/foreman.py`: `Foreman.act`, then `_tasks` (find work on every tile), then
   `_unit_cmd` (pick the best task for one worker and walk there). Also `plant_ready`.
6. `kagri/economics.py`: `sale_proceeds`, `estimate_crop_profit`, `estimate_animal_profit`.
7. `kagri/agents/base.py`: the `Agent` interface and the `Decision` dataclass.
8. `kagri/agents/baselines.py`: `RandomAgent.decide`, `GreedyAgent.decide`.
9. `kagri/agents/strategy.py`: `crop_mix` (marginal allocation), `sell_orders`,
   `hands_needed`, `strategic_plan`.
10. `kagri/agents/tools.py`: `ToolBox.__init__` (the tool list), `call`, `simulate_action`.
11. `kagri/agents/prompts.py`: `system_prompt`, `day_message`.
12. `kagri/agents/memory.py`: `ShortTermMemory`, `LongTermMemory`.
13. `kagri/agents/llm_agent.py`: `parse_json`, `LLMAgent.decide`, `LLMAgent._react` (the core
    loop), `LLMAgent._team` (multi-agent), `LLMAgent.end_episode` and `season_evidence`.
14. `kagri/llm/providers.py`: `Provider.respond` (rate limit, retries), `GeminiProvider._call`,
    `get_provider`.
15. `kagri/llm/offline.py`: `OfflineReasoner._single`, `_planner`, `_manager`, `_reflect`.
16. `kagri/runner.py`: `run_episode` (plays a season and writes JSONL), `load_run`.
17. `kagri/evaluate.py`: `main`, `make_agent`, `_row`. Then `kagri/charts.py`.
18. `kagri/server.py`: `runs`, `run`, `live_start`, `live_step`. Then `kagri/serve.py`.
19. `web/src/App.tsx`: state for replay/live, `advance` (playback), the tabs.
20. `web/src/components/`: `FarmGrid.tsx`, `MindFeed.tsx`, `PlanChips.tsx`,
    `ResultsView.tsx`, `HowItWorks.tsx`.
21. `tests/`: see how each part is tested.

---

## Five small exercises

1. **Change a prompt.** In `kagri/agents/prompts.py`, add a sentence to `RULES` such as
   "Never let cash fall below $300." Run one real-LLM day and see if the thought mentions it.
   Hint: `python -m kagri.record --agent llm_single --provider gemini` needs a key in `.env`.

2. **Add a tool.** Add `get_shed_value` to `ToolBox` that returns the value of everything in the
   shed at today's prices. Hint: add an entry to `self.tools` in `__init__` and a method that
   loops over `self.obs["shed"]` and `self.obs["prices"]`.

3. **Tune the look-ahead.** In `kagri/llm/offline.py`, change the single agent's simulation from
   5 days to 8 (`lookahead_days`). Re-run `python -m kagri.evaluate --seeds 2 --agents llm_single
   --reflection-episodes 0` and compare profit. Hint: the default comes from
   `params.get("lookahead_days", 5)`.

4. **Make Greedy smarter.** In `GreedyAgent.decide`, plant at most 10 plots of the best crop and
   fill the rest with the second best. Does profit go up? Hint: sort crops by margin first.

5. **Add a guardrail.** In `validate_plan`, reject `buy_land` when fewer than 8 days are left,
   with a clear reason. Then add a test in `tests/test_env.py`. Hint: compare
   `state["last_day"] - state["day"]`.

Run `pytest` after each change. All tests should still pass.

---

## Useful commands

```bash
python -m kagri.serve
```

```bash
python -m kagri.evaluate
```

```bash
python -m kagri.record --agent llm_single --provider gemini
```

```bash
pytest
```

## Bonus: the research layer (read after everything above)

Think of these as science experiments you run on the farm:

1. **Ablation** (`kagri/ablation.py`). Like checking what a car is worth without its engine, then
   without its wheels. `VARIANTS` lists each switch; the offline reasoner reads switches such as
   `no_lookahead` and `allow_land` from its params (`kagri/llm/offline.py`, `_candidates`).
2. **Verified reflection** (`kagri/reflection.py`). A student writes down a lesson after a test,
   but only keeps it if it helps on practice papers. `HYPOTHESES` are the lesson templates; `main`
   runs train, validate, test.
3. **Arena** (`kagri/arena.py`). Two farmers, one market. `FarmEnv.view(player)` lets the same game
   be seen from either seat; `FarmEnv.step(plan, rival=...)` runs both Foremen in the same turns.
   `bradley_terry` turns wins into ratings.
4. **Real weather** (`kagri/realweather.py`). `classify_day` turns real rain and heat into the
   game's weather; `FarmEnv(weather=...)` uses it instead of random weather.

