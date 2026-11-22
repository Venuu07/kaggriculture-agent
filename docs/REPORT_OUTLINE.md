# Project report outline: Agentic AI for Farm Profit Maximisation

Chapter-wise content with real details from the code. Teammates: expand each section into
full prose, add figures from `results/` and `docs/img/`, and keep the honesty notes.

> Honesty note: the LLM-agent results in this report were produced with the **offline
> reasoner** (`kagri/llm/offline.py`), a deterministic rule-based reasoner that drives the same
> ReAct loop, tools, memory and guardrails as a real LLM but is not a language model. If a real
> Gemini evaluation is recorded (`python -m kagri.evaluate --provider gemini --seeds 1`), add
> its numbers in Table 7.1 and section 7.5 where marked.

---

## Abstract (about 250 words)

Farm management is a sequential decision problem under uncertainty: what to plant, when to
sell, how much labour to hire and when to invest, while prices react to supply and weather
adds risk. We study it with Kaggriculture, a Kaggle simulation competition (2026) in which an
agent runs a farm for a 30-day, 720-turn season and is scored on final cash. We vendor the
official game engine and wrap it as a gym-style environment, `FarmEnv`, where one step is one
day. A deterministic executor (the Foreman) turns each daily plan into per-turn commands. On
top we build an agentic AI manager: a ReAct-style agent that reasons, calls eight tools
(including a look-ahead simulator), keeps short-term and long-term memory, and can run as a
team of four specialised agents (Planner, Market Analyst, Agronomist, Manager). All plans pass
through guardrails that validate schema, budget, feed reserve and timing. The LLM layer
supports Gemini, Groq, OpenAI and Claude, and an offline reasoner keeps the system usable
without internet or an API key. Over five seeds, the multi-agent system (offline reasoner)
earned a mean profit of $88,794, the single agent $79,344, a Greedy heuristic $30,021 and a
random agent $11,060, about three times the heuristic. The main sources of advantage were
glut-aware crop diversification, animals as a fertiliser income stream, land expansion and
simulation-based look-ahead. A React dashboard shows the farm, the agent's reasoning trace and
the evaluation results.

Keywords: agentic AI, large language models, ReAct, tool use, multi-agent systems, reflection,
simulation, farm management.

---

## Chapter 1: Introduction

### 1.1 Background
- Agriculture decisions are economic: inputs cost money, outputs sell on markets whose prices
  move with supply.
- Decisions have delays (crops take 3 to 16 days, animals take days to pay back) and risk
  (weather, pests, price shocks).
- Large language models (LLMs) can now reason in natural language and call external tools,
  which makes them candidates for "agents" that act, observe and adapt.

### 1.2 Motivation
- Classic heuristics are fast but myopic: they ignore their own price impact.
- Reinforcement learning needs very many episodes and produces policies that are hard to explain.
- An LLM agent can explain each decision, test plans before acting and learn lessons in words.

### 1.3 Problem statement
Design and evaluate an autonomous agent that maximises end-of-season cash in the
Kaggriculture farm simulation, compare it against baseline strategies, and present its
reasoning transparently.

### 1.4 Objectives
1. Wrap the official Kaggriculture engine as a deterministic, gym-style environment.
2. Implement baseline agents (Random, Greedy heuristic).
3. Implement a ReAct tool-using agent with memory, reflection and guardrails.
4. Implement a multi-agent mode with a coordinating Manager.
5. Evaluate all agents over multiple seeds and report profit, behaviour, cost and latency.
6. Build a dashboard that works in replay mode with no internet or API key.

### 1.5 Scope and deviations from the competition
- One strategic decision per day instead of 720 turn-level decisions; the Foreman executes turns.
- We play against the built-in "starter" bot on a shared market instead of the Kaggle ladder.
- We add an optional weather and events layer (off with `--no-events`).

### 1.6 Organisation of the report
Short paragraph listing chapters 2 to 9.

---

## Chapter 2: Literature survey

Write one paragraph per item: what it proposes, what we take from it, how we differ.

- **ReAct (Yao et al., 2022):** interleaving reasoning traces and actions. Our daily loop
  (thought, tool, observation, ..., take_action) follows this pattern directly.
- **Reflexion (Shinn et al., 2023):** agents write verbal feedback after an episode and reuse
  it. Our `LongTermMemory` and `end_episode` reflection step implement this.
- **Toolformer (Schick et al., 2023):** models learn when to call APIs. We use prompted tool
  calling with a fixed, documented tool list instead of training.
- **Generative Agents (Park et al., 2023):** memory streams, retrieval and reflection for
  long-running agents. We use a simpler rolling log plus stored lessons.
- **Multi-agent LLM frameworks (AutoGen, Wu et al., 2023; CAMEL, Li et al., 2023):** agents with
  roles that converse. Our team uses fixed roles with restricted tools and a Manager that merges
  proposals, which is cheaper and easier to audit than free conversation.
- **RL for crop management (CropGym, Overweg et al., 2021):** gym environments for fertiliser
  and crop decisions. We follow the gym interface but use an LLM agent rather than training a
  policy.
- **Operations research and heuristics:** linear programming and rule-based decision support are
  the common baseline; our Greedy agent represents this family.
- **Kaggle simulation competitions (Kaggriculture, 2026):** the official engine and rules we build on.

Summary table suggestion: method, learns from data?, explainable?, handles delayed payoff?,
compute cost.

---

## Chapter 3: Requirements specification

### 3.1 Functional requirements
- FR1: Reset and step a farm season deterministically from a seed.
- FR2: Accept a daily plan (plant, sell, buy animals, fertilise, hands, buy land) and execute it.
- FR3: Reject invalid plan parts with a reason, never crash.
- FR4: Provide tools for state, weather, prices, profit estimates and look-ahead simulation.
- FR5: Run single-agent and multi-agent LLM modes with selectable provider.
- FR6: Store lessons after each season and load them into the next.
- FR7: Evaluate agents over N seeds and output CSV tables and PNG charts.
- FR8: Log every day (thought, tool calls, results, plan, reward) to JSONL for replay.
- FR9: Dashboard with live farm, reasoning trace, results and architecture views.

### 3.2 Non-functional requirements
- Reliability: demo must work with no internet and no API key (replay mode, offline reasoner).
- Safety: guardrails on budget and plan validity; bounded tool calls; fallback plan.
- Performance: a baseline episode runs in about 0.1 s; offline-reasoner decisions take about 0.1 to 0.2 s.
- Portability: runs on Windows, macOS and Linux with Python 3.11; `pathlib` paths only.
- Security: API keys only in `.env`, which is git-ignored; `.env.example` documents variables.
- Maintainability: typed Python, short docstrings, pytest suite, config in `kagri/config.yaml`.

### 3.3 Hardware requirements
- Any laptop with 4 GB RAM or more; no GPU needed.

### 3.4 Software requirements
- Python 3.11, pip; packages in `requirements.txt` (pyyaml, requests, python-dotenv, pandas,
  matplotlib, fastapi, uvicorn, pytest).
- A modern browser. Node.js 18+ only if the UI is rebuilt (`web/`).
- Optional: one API key (Gemini, Groq, OpenAI or Anthropic).

---

## Chapter 4: System design

### 4.1 Architecture
Insert `docs/img/architecture.png`. Describe the layers top to bottom:
React dashboard -> FastAPI (`kagri/server.py`) -> Agent (`kagri/agents/llm_agent.py` or
baselines) -> Guardrails (`kagri/plan.py`) -> Foreman (`kagri/foreman.py`) -> Official engine
(`kagri/engine/kaggriculture.py`) plus weather layer (`kagri/env.py`).

### 4.2 Data flow for one day
1. `FarmEnv.observe()` produces a compact JSON observation.
2. The agent's ReAct loop calls tools via `ToolBox.call` and ends with `take_action(plan)`.
3. `validate_plan` cleans the plan and lists rejections.
4. `Foreman.act` is called 24 times, one per turn, together with the opponent bot.
5. `FarmEnv.step` returns observation, reward (cash change), done and info (sales, events).
6. `run_episode` writes the day record to JSONL.

### 4.3 Environment design
- Observation fields: day, days_left, cash, profit, opponent_cash, free_plots, weeds,
  crops_growing, animals, plots, grid, land_quadrants, next_land_cost, shed, seeds, prices,
  market_inventory, town_shops, weather, forecast.
- Action: the daily plan dictionary (see `kagri/plan.py` docstring).
- Reward: daily change in cash; score = final cash; profit = final cash minus $3,000.
- Weather and events: daily weather drawn from `weather_probs`; heavy rain waters all plants;
  drought removes the one-day grace for unwatered plants; pests turn about 15% of unfertilised
  plants into weeds; price shocks shift a product's market inventory.

### 4.4 Agent design
- ReAct protocol (`kagri/agents/prompts.py`: `PROTOCOL`, `RULES`, `PLAN_SCHEMA`, `ROLES`).
- Tools (`kagri/agents/tools.py`): eight tools plus `take_action`.
- Memory (`kagri/agents/memory.py`): `ShortTermMemory` (last 5 days), `LongTermMemory` (JSON file).
- Multi-agent: role-specific tool lists (`ROLE_TOOLS`) and plan keys (`ROLE_KEYS`).

### 4.5 Diagrams to include
- Use case diagram (user: run demo, choose agent, replay run, run evaluation).
- Sequence diagram for one day in multi-agent mode.
- Class diagram: `Agent`, `RandomAgent`, `GreedyAgent`, `LLMAgent`, `Provider` subclasses,
  `OfflineReasoner`, `FarmEnv`, `Foreman`, `ToolBox`.

---

## Chapter 5: Implementation

### 5.1 Engine and driver (`kagri/engine/`)
- `kaggriculture.py` vendored from kaggle-environments 1.33.3 (Apache-2.0); only the framework
  import and HTML renderer loading were removed.
- `driver.py`: `Struct` (dict with attribute access) and `GameDriver` (two players, `step`,
  `observation`, `clone`). A full 720-turn game runs in about 0.03 s.

### 5.2 Environment (`kagri/env.py`)
- `FarmEnv.reset(seed)`, `step(plan)`, `simulate(plan, days, follow_up)`, `net_worth()`, `observe()`.
- `_roll_weather`, `forecast`, `_apply_events` implement the extension deterministically per seed.
- `expected_plant_value` values growing crops for look-ahead comparisons.

### 5.3 Plans and guardrails (`kagri/plan.py`)
- `validate_plan` checks keys, hands (0 to 10), land cost, animal and seed budgets, free plots,
  late plantings and sell quantities; keeps a 3-day wheat feed reserve per animal.

### 5.4 Foreman (`kagri/foreman.py`)
- `Foreman.act` builds market orders once per day (`_build_orders`) and assigns each unit a task
  (`_tasks`, `_unit_cmd`) by priority and Manhattan distance.
- `plant_ready` and `wants_fertiliser` encode harvest and fertiliser timing from the rules.
- Final-day logic drops all stock at the shed and sells it.

### 5.5 Economics and strategy (`kagri/economics.py`, `kagri/agents/strategy.py`)
- `sale_proceeds` walks the official price curve unit by unit.
- `estimate_crop_profit` includes the price impact of crops already growing.
- `crop_mix` allocates plots by marginal profit per plot-day (glut-aware).
- `sell_orders`, `hands_needed`, `animal_purchase`, `fertiliser_targets`, `strategic_plan`.

### 5.6 Baselines (`kagri/agents/baselines.py`)
- `RandomAgent`: random but legal-looking plans.
- `GreedyAgent`: plants the best single-plot margin crop on all free plots, sells at or above
  the running average price.

### 5.7 LLM layer (`kagri/llm/`)
- `providers.py`: `Provider` base with rate limiting, retries (429/5xx back-off) and cost table;
  `GeminiProvider`, `OpenAICompatProvider` (OpenAI and Groq), `ClaudeProvider`; `get_provider`
  reads `LLM_PROVIDER` from `.env`.
- `offline.py`: `OfflineReasoner` produces the same JSON protocol from rules, per role
  (`_single`, `_planner`, `_market`, `_agronomist`, `_manager`, `_reflect`).

### 5.8 Agentic manager (`kagri/agents/llm_agent.py`)
- `LLMAgent.decide` runs `_react` (single) or `_team` (multi), falls back to `strategic_plan` on failure.
- `_react` enforces max tool calls, tool permissions per role, and JSON retries; logs every step.
- `parse_json` extracts JSON from fenced or chatty replies.
- `end_episode` calls the model with `season_evidence(summary)` and stores lessons.

### 5.9 Evaluation (`kagri/evaluate.py`, `kagri/charts.py`, `kagri/runner.py`)
- `run_episode` logs header, day records and summary to JSONL; `load_run` reads them back.
- `evaluate.main` runs agents over seeds (parallel when offline), writes `results.csv`,
  `summary.csv`, `reflection.csv` and five charts.

### 5.10 Server and dashboard (`kagri/server.py`, `kagri/serve.py`, `web/`)
- Endpoints: `/api/runs`, `/api/runs/{name}`, `/api/results`, `/api/memory`, `/api/providers`,
  `POST /api/live`, `POST /api/live/{sid}/step`.
- React + Vite + TypeScript: `FarmGrid` (animated tiles, weather overlay), `MindFeed`
  (reasoning trace), `ResultsView` (Recharts), `HowItWorks`. Built files in `web/dist` are served
  by FastAPI, so the demo needs only `python -m kagri.serve`.

### 5.11 Configuration
- `kagri/config.yaml`: game settings, crop and animal tables (for explanation), events,
  foreman settings (max hands 10), LLM limits (4 tool calls, 2 JSON retries, temperature 0.2).

---

## Chapter 6: Testing

20 automated tests, run with `python -m pytest -q` (all pass). In addition to the table below: `tests/test_arena.py` (shared market, seat views, Bradley-Terry), `tests/test_reflection.py` (lesson hypotheses), `tests/test_realweather.py` (weather mapping, env hook).

| File | Test | What it checks |
|---|---|---|
| tests/test_env.py | test_reset_observation | day 0, $3,000 cash, 25 free plots, prices present |
| | test_episode_has_30_days_and_ends | exactly 30 steps per season |
| | test_deterministic_given_seed | same seed and plan give the same cash |
| | test_profitable_plan_makes_money | a sensible wheat plan ends above $3,000 |
| | test_invalid_actions_rejected_not_crash | bad crops, quantities, keys and non-dict plans are rejected with reasons |
| | test_budget_guardrail_trims_overspending | overspending plans are trimmed |
| | test_late_planting_rejected | crops that cannot ripen before day 29 are rejected |
| | test_simulate_does_not_change_real_env | look-ahead runs on a copy |
| tests/test_agents.py | test_baselines_run | baselines play 30 days and the JSONL log round-trips |
| | test_greedy_beats_random | sanity check of the baselines |
| tests/test_llm_agent.py | test_parse_json_handles_fences_and_chatter | robust JSON extraction |
| | test_react_loop_calls_tools_then_acts | scripted LLM: tool calls, a bad-JSON retry, final action, token counting |
| | test_bad_llm_falls_back_safely | an LLM that returns garbage triggers the safe fallback |
| | test_offline_multi_agent_and_reflection | all four roles act, profit above $30k, lessons stored |

Also describe manual testing: dashboard checked with Playwright screenshots in both themes,
live mode with a missing key (switches to offline with a notice), and no browser console errors.

---

## Chapter 7: Results and discussion

### 7.1 Experimental setup
- 5 seeds (0 to 4), weather and events on, starter-bot opponent, starting cash $3,000.
- LLM agents run with the offline reasoner.
- Command: `python -m kagri.evaluate`.

### 7.2 Profit (Table 7.1; figure `results/profit_by_agent.png`)

| Agent | Mean profit | Std | Min | Max | Tool calls / season |
|---|---|---|---|---|---|
| Random | $11,060 | $4,061 | $6,667 | $15,866 | 0 |
| Greedy heuristic | $30,021 | $980 | $28,484 | $30,866 | 0 |
| LLM single-agent (offline reasoner) | $79,344 | $16,126 | $61,166 | $104,187 | 108 |
| LLM multi-agent (offline reasoner) | $88,794 | $11,840 | $78,757 | $104,737 | 177 |
| [Real LLM, if recorded] | | | | | |

The multi-agent system earns about 3.0 times the Greedy heuristic. The starter opponent ends
near $3.2k to $3.5k in every run.

### 7.3 Profit over time (`results/profit_over_time.png`)
- All agents are flat or slightly negative until day 10 while early crops grow.
- Greedy jumps once when its melons ripen, then stalls because melon prices crash.
- The agents keep rising after day 20 as animals, strawberries and diversified crops pay off.

### 7.4 Why the agent wins
- Greedy monocrops melons; the melon price curve falls with the square of oversupply, so later
  melons sell for very little.
- `crop_mix` spreads plots across crops by marginal profit, avoiding gluts.
- Animals add a daily fertiliser income (about $100 each) plus eggs, milk or wool.
- Land purchases add plots; look-ahead (`simulate_action`) shows when they pay back.
- Labour was a hidden bottleneck: raising the hands cap from 6 to 10 increased the single
  agent from about $71k to $79k, because unwatered plants turn into weeds.
- Multi-agent beats single because the Planner compares three candidates with an 8-day
  look-ahead and the Manager fixes labour conflicts.

### 7.5 Behaviour, cost and latency (`results/action_distribution.png`, `results/cost_latency.png`)
- Describe how often each agent plants, sells, buys animals, fertilises, hires, buys land.
- Offline reasoner: 0 tokens and about 0.1 to 0.2 s per decision.
- With a real LLM: report tokens per season, cost and seconds per decision here.

### 7.6 Reflection (`results/reflection.png`)
- Same seed replayed three times with lessons carried forward.
- With the offline reasoner the curve is flat: the lessons it derives did not change its
  decisions. We report this honestly; the mechanism is designed for real LLMs, whose effect
  must be measured with a real-LLM run.

### 7.7 Ablation study (RQ1; `results/ablation.png`, `kagri/ablation.py`)
- Table: full $88,794; no look-ahead −28.7%; no land −25.6%; no animals −19.1%; no team −10.6%;
  no glut-awareness −10.5%; max 4 hands −4.8%. Every component worse on 5/5 seeds (labour 4/5).

### 7.8 Verified reflection (RQ2; `results/reflection_verified.png`, `kagri/reflection.py`)
- Novice start (no land, no animals); 6 evidence-driven lesson templates; 4 validation and
  4 held-out test seasons; adopt only if validation profit rises by at least 1%.
- Held-out profit $53,273 → $67,626 (+27%) after adopting "buy land"; later lessons rejected
  (animals +0.4%, labour +0.9%, look-ahead −0.8%, glut −1.9%).

### 7.9 Arena: price of competition and head-to-head ratings (RQ3, RQ4; `kagri/arena.py`)
- Profit vs Kaggle starter bot vs a copy of itself: single $72,474 → $39,881 (−45%);
  multi $84,355 → $47,404 (−44%); Greedy −23%; Random −17%.
- Bradley-Terry ratings: single 2434, multi 2124, Greedy 1815, Random 979, starter 147.
- Single beats multi 6/6 head-to-head: the look-ahead models the rival as the starter bot.

### 7.10 Real-weather mode (`kagri/realweather.py`)
- Historical daily weather for Indian districts from the Open-Meteo archive, mapped to game weather.
- Insert a run here if fetched (e.g. Anantapur, July 2025) and compare with simulated weather.

### 7.11 Real LLM case study (RQ5; `runs/recorded_*.jsonl`, Research tab)

| Agent (seed 0, same farm and weather) | Profit | LLM calls | Days using tools | Simulations | Guardrail fixes | Cost (list price) |
|---|---|---|---|---|---|---|
| LLM multi-agent, offline reasoner | $98,156 | – | 30 / 30 | 76 | 0 | $0 |
| LLM single-agent, offline reasoner | $81,188 | – | 30 / 30 | 48 | 0 | $0 |
| **Gemini single-agent + test-before-act** | **$48,617** | 90 | 29 / 30 | 30 | 40 | $0.067 |
| **Gemini single-agent** | **$41,018** | 34 | 2 / 30 | **0** | 0 | $0.027 |
| **Gemini multi-agent team** | **$31,197** | 123 | 3 / 30 | 1 | 16 | $0.079 |
| Greedy heuristic | $29,709 | – | – | – | – | $0 |
| Random | $6,667 | – | – | – | – | $0 |

- Gemini under-uses tools (2/30 days, 0 simulations); test-before-act raises profit 18.5%.
- The real multi-agent team is the weakest LLM agent: more calls, no simulations.
- Guardrails repaired 16-40 plans per season; 0 fallback days; 3-8 cents per season.

### 7.12 Robustness: Scenario Lab (`kagri/scenarios.py`, `results/scenarios.json`)
- Six scripted crises vs a calm control on seed 0. Melon crash: AI $34,930 vs Greedy −$755.
- Drought 91% of calm, pest wave 75%, monsoon 91%, festival 92% (AI). Weakness: full shed sells at $1.

### 7.13 Generalisation: the shop world (`kagri/shop/`, `kagri/agents/core.py`)
- The same ReAct core in a kirana store: AI ₹61,815 vs fixed rule ₹35,653 (+73%), 5 seeds;
  customers turned away 237 vs 1,671; units wasted 5 vs 3.

### 7.14 Interactive system: Play vs AI (`kagri/play.py`)
- Human seat on the shared market, plan builder with a budget check, suggested plans, the AI's reasoning.

### 7.15 Threats to validity
- Small number of seeds; high variance for the agents.
- Offline reasoner is hand-designed, so its strength reflects our domain rules.
- Weak opponent; weather layer is our own.

---

## Chapter 8: Conclusion

- We built a complete agentic system on the official Kaggriculture engine: environment,
  executor, guardrails, tools, memory, multi-agent coordination, evaluation and dashboard.
- Tool use with look-ahead simulation and glut-aware planning gives about three times the
  profit of a classic heuristic, with every decision explained.
- The design keeps the agent safe: plans are validated, failures fall back to a safe plan,
  and the demo runs without internet.

---

## Chapter 9: Future work

- Evaluate real LLMs (Gemini, Groq, Claude, OpenAI) over many seeds and compare cost against profit.
- Train an RL agent (for example PPO) on `FarmEnv` and compare with the LLM agent.
- Per-turn control and head-to-head play against strong opponents; submit to the Kaggle ladder.
- Better reflection: verify lessons with simulation before adopting them.
- Deploy the dashboard as a hosted service; apply the pattern to real supply-chain planning.

---

## References

1. S. Yao, J. Zhao, D. Yu, N. Du, I. Shafran, K. Narasimhan, Y. Cao, "ReAct: Synergizing Reasoning and Acting in Language Models," arXiv:2210.03629, 2022 (ICLR 2023).
2. N. Shinn, F. Cassano, A. Gopinath, K. Narasimhan, S. Yao, "Reflexion: Language Agents with Verbal Reinforcement Learning," NeurIPS 2023.
3. T. Schick et al., "Toolformer: Language Models Can Teach Themselves to Use Tools," NeurIPS 2023.
4. J. S. Park et al., "Generative Agents: Interactive Simulacra of Human Behavior," UIST 2023.
5. Q. Wu et al., "AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation," arXiv:2308.08155, 2023.
6. G. Li et al., "CAMEL: Communicative Agents for Mind Exploration of Large Language Model Society," NeurIPS 2023.
7. H. Overweg, H. N. C. Berghuijs, I. N. Athanasiadis, "CropGym: a Reinforcement Learning Environment for Crop Management," arXiv:2104.04326, 2021.
8. G. Brockman et al., "OpenAI Gym," arXiv:1606.01540, 2016.
9. B. Doerschuk-Tiberi, D. Weir, M. Cruz, "Kaggriculture," Kaggle, 2026. https://www.kaggle.com/competitions/kaggriculture
10. Kaggle, "kaggle-environments," Apache License 2.0. https://github.com/Kaggle/kaggle-environments
