# Slide deck outline: Agentic AI for Farm Profit Maximisation

Ready to paste into slides. Each slide has a title, bullets and speaker notes.
Images live in `results/` (charts) and `docs/img/` (architecture and UI screenshots).

> Honesty note for the whole deck: the LLM-agent numbers below were produced with the
> **offline reasoner**, a deterministic rule-based stand-in that uses the same ReAct loop,
> tools, memory and guardrails as a real LLM but is not a language model. If Venu records a
> real Gemini run (`python -m kagri.evaluate --provider gemini --seeds 1`), add those numbers
> on slide 16 in the marked row.

---

## Slide 1: Title
- Agentic AI for Farm Profit Maximisation
- Based on the Kaggle simulation competition "Kaggriculture"
- B.Tech (CSE) Major Project, final review
- Team names, guide name, college, date

Speaker notes: Introduce the team and say in one sentence: "We built an AI agent that runs a virtual farm and makes about three times more profit than a classic rule-based farmer."

---

## Slide 2: The problem
- Farming is a long chain of decisions under uncertainty: what to plant, when to sell, how much labour to hire, when to invest
- Prices react to supply: if everyone sells melons, the melon price crashes
- Decisions have delayed payoffs: a melon takes 10 days, an animal takes a week to pay back
- Weather, pests and price shocks add risk
- Kaggriculture (Kaggle, 2026) models all of this as a 30-day, 720-turn game; the score is cash at the end

Speaker notes: Stress that this is a planning problem, not a prediction problem. There is no dataset to fit; the agent must act, observe and adapt.

---

## Slide 3: Objectives
- Wrap the official Kaggriculture simulator as a clean, gym-style environment
- Build baseline agents (Random, Greedy heuristic) to measure against
- Build an agentic AI manager: an LLM that reasons, calls tools, remembers and reflects
- Add a multi-agent mode: Planner, Market Analyst, Agronomist, coordinated by a Manager
- Evaluate all agents fairly over several seeds and explain the results
- Ship a demo that works with no internet and no API key

Speaker notes: Each objective maps to a module we will show later (environment, baselines, agent, evaluation, dashboard).

---

## Slide 4: Existing systems and literature
- ReAct (Yao et al., 2022): interleave reasoning ("thought") with actions (tool calls)
- Reflexion (Shinn et al., 2023): agents write verbal lessons after a failure and reuse them
- Toolformer (Schick et al., 2023): language models learn when to call external tools
- Generative Agents (Park et al., 2023): memory streams and reflection for long-running agents
- Multi-agent LLM frameworks: AutoGen (Wu et al., 2023), CAMEL (Li et al., 2023)
- Farm decision support: reinforcement learning environments such as CropGym (Overweg et al., 2021); classic operations research and rule-based heuristics

Speaker notes: Position the project: we combine ReAct, tool use, reflection and multi-agent coordination on a realistic economic simulation, and compare against heuristics, the approach used by most farm decision tools.

---

## Slide 5: Gap we address
- RL needs millions of simulated episodes and gives a black-box policy
- Rule-based heuristics are fast but ignore their own price impact (gluts)
- Most LLM agent papers use text games or web tasks, not economic planning with money at stake
- We need explainable decisions: why plant strawberries today, why hire 9 hands
- Our system: an LLM agent that explains every decision, tests plans in a simulator before acting, and is checked by guardrails

Speaker notes: The key selling point is explainability plus look-ahead. The panel can read exactly why the agent acted.

---

## Slide 6: Proposed system (overview)
- The agent makes one strategic decision per in-game day (30 per season)
- A deterministic "Foreman" turns that decision into the 24 per-turn moves of the real game
- Tools give the agent facts and a look-ahead simulator
- Guardrails validate every plan (schema, budget, feed reserve, timing)
- Memory: this season's log in the prompt, lessons from past seasons
- Dashboard: live farm, the agent's reasoning trace, results, architecture

Speaker notes: Explain the two-level design: the LLM is the manager, the Foreman is the farm hand. 720 LLM calls per game would be too slow and too costly.

---

## Slide 7: Architecture
- Image: `docs/img/architecture.png`
- React dashboard -> FastAPI server -> Agent (single or multi) -> Guardrails -> Foreman -> official engine
- LLM provider layer: Gemini, Groq, OpenAI, Claude, or the offline reasoner
- Baselines plug into the same interface
- Every day is logged to JSONL for replay and evaluation

Speaker notes: Walk top to bottom along one day: the UI asks for a step, the agent thinks and calls tools, the plan is validated, the Foreman plays 24 turns, the result comes back.

---

## Slide 8: Modules
- `kagri/engine/`: vendored official rules (`kaggriculture.py`) and a standalone driver (`driver.py`)
- `kagri/env.py`: `FarmEnv` with `reset`, `step`, `simulate`, weather and events
- `kagri/foreman.py`: the executor (task allocation, movement, market orders)
- `kagri/plan.py`: plan schema and `validate_plan` guardrails
- `kagri/agents/`: baselines, strategy helpers, tools, memory, prompts, `llm_agent.py`
- `kagri/llm/`: providers and the offline reasoner; `kagri/evaluate.py`, `charts.py`, `server.py`, `web/`

Speaker notes: Mention the clean separation: the agent code has no UI code, so any front end can sit on top.

---

## Slide 9: Environment design
- Official Kaggriculture engine vendored from kaggle-environments (Apache-2.0), unchanged rules
- 10x10 farm, 4 quadrants (first free, then $1000, $2000, $4000); start with $3000
- 5 crops, 3 animals; every animal also drops 1 fertiliser per day
- Dynamic market: price curves react to every unit sold (melon and other premium goods crash to $1)
- `FarmEnv.step(plan)` = one day = 24 engine turns; reward = cash change; deterministic per seed
- Our extension (toggle): weather (sunny, cloudy, heavy rain, drought), pests, price shocks, noisy 3-day forecast

Speaker notes: Be clear the extension is ours and can be switched off with `--no-events` for competition-faithful runs.

---

## Slide 10: The Foreman (executor)
- Standing orders: water every plant daily, harvest when ripe, dig weeds, feed, care, collect fertiliser
- Allocates tasks to the farmer and hired hands by priority and distance
- Only the farmer carries items (wheat feed, fertiliser, animals) to keep it simple and safe
- Issues market orders: hires, land, seeds, animals, feed, sells (max 10 per turn)
- Last day: harvest everything, drop it at the shed, sell it all

Speaker notes: The Foreman has no strategy. All economic choices come from the agent, which is what we evaluate.

---

## Slide 11: Agent design: ReAct loop
- Observe: farm state, weather, prices, recent days (short-term memory)
- Think: the model writes a thought and picks one tool
- Act: tool runs, result returned as an observation
- Repeat up to 4 tool calls, then `take_action(plan)`
- Reply format is strict JSON: `{"thought", "action", "args"}`
- Image: `docs/img/ui_mind.png`

Speaker notes: Show the reasoning trace screenshot. Point at a `simulate_action` call and its net-worth result, then the decision that follows.

---

## Slide 12: Tools
- `get_farm_state`, `get_weather_forecast`, `get_market_prices`
- `estimate_crop_profit`: expected profit including the price drop our own harvest causes
- `estimate_animal_profit`, `estimate_sale` (walks the official price curve)
- `plan_crop_mix`: glut-aware allocation by marginal profit per plot-day
- `simulate_action`: plays a candidate plan on a copy of the farm and reports net-worth change
- Tools never crash the agent: errors come back as JSON messages

Speaker notes: `simulate_action` is the most important tool. It lets the agent see delayed payoffs before committing.

---

## Slide 13: Memory, reflection and guardrails
- Short-term memory: last 5 days (plan, cash change, weather, rejections) in every prompt
- Long-term memory: after each season the agent writes lessons to `memory/lessons_*.json`; they are added to the next season's prompt
- Guardrails: unknown keys dropped, budgets trimmed, feed reserve kept, late plantings rejected, hands capped at 10
- Max 4 tool calls per turn, 2 retries on bad JSON, safe fallback plan if the model fails
- Token, cost and latency counters on every decision

Speaker notes: The agent can never crash the game or overspend. Every rejection comes with a human-readable reason shown in the UI.

---

## Slide 14: Multi-agent mode
- Planner: what to plant, buy land, buy animals (8-day look-ahead, 3 candidates)
- Market Analyst: what and how much to sell without crashing prices
- Agronomist: fertiliser and labour, reacts to weather
- Manager: merges proposals, fixes conflicts (for example, too few hands for new land), checks with `simulate_action`, commits
- Each role sees only the tools it needs

Speaker notes: Give the concrete conflict example: the Agronomist sizes labour before knowing the Planner bought land; the Manager raises hands. This fix is part of why the team beats a single agent.

---

## Slide 15: Tech stack
- Python 3.11, pytest (14 tests)
- FastAPI + uvicorn (API and static UI server)
- React 18 + Vite + TypeScript, Recharts; fonts bundled locally (works offline)
- matplotlib + pandas for evaluation charts
- LLM providers over plain HTTPS: Gemini (default), Groq, OpenAI, Claude; switch in `.env`
- Offline reasoner for no-internet, no-key demos

Speaker notes: No heavy ML frameworks are needed. The whole demo runs on a laptop with one command.

---

## Slide 16: Results: profit per agent
- Image: `results/profit_by_agent.png`
- 5 seeds, weather and events on, starting cash $3,000
- Random: $11,060 ± 4,061
- Greedy heuristic: $30,021 ± 980
- LLM single-agent (offline reasoner): $79,344 ± 16,126
- LLM multi-agent (offline reasoner): $88,794 ± 11,840, about 3.0x Greedy
- [Insert real Gemini result here if recorded: agent, seeds, mean profit, tokens, cost]

Speaker notes: The built-in "starter" opponent ends near $3.2k to $3.5k, so every agent wins the match; the comparison that matters is between our agents.

---

## Slide 17: Why the agent wins
- Image: `results/profit_over_time.png`
- Greedy plants only melons and crashes the melon price (square-shaped glut curve)
- Agent diversifies: glut-aware crop mix (strawberries, melons, tomatoes, wheat)
- Agent buys animals: each drops fertiliser worth about $100 per day plus eggs, milk or wool
- Agent buys land and uses look-ahead to judge delayed payoffs
- Hidden bottleneck found: labour. Raising the hands cap from 6 to 10 lifted the single agent from about $71k to $79k

Speaker notes: The curves are flat until day 10 (first melon harvest), then the agent pulls away as animals and diversified crops pay off.

---

## Slide 18: Behaviour, cost and reflection
- Image: `results/action_distribution.png`: what each agent does per season
- Image: `results/cost_latency.png`: tool calls, tokens and seconds per decision
- Single agent: about 108 tool calls per season; multi-agent: about 177
- Offline reasoner: 0 tokens, about 0.1 to 0.2 s per decision
- Image: `results/reflection.png`: with the offline reasoner, reflection did not change profit (flat line). Measuring it on a real LLM needs a real-LLM run

Speaker notes: Be upfront about the flat reflection curve. The mechanism works (lessons are written and loaded); its benefit must be measured with a real LLM.

---

## Slide 19: Demo
- Images: `docs/img/ui_farm.png`, `docs/img/ui_mind.png`, `docs/img/ui_results.png`, `docs/img/ui_how.png`
- Command: `python -m kagri.serve`, then open http://localhost:8000
- Replay mode: recorded seasons, no internet needed
- Live mode: pick agent, seed, provider; step day by day
- A missing API key switches to the offline reasoner automatically, with a visible notice

Speaker notes: Switch to the live demo here (see docs/DEMO_SCRIPT.md).

---

## Slide 20: Limitations
- LLM numbers reported here come from the offline reasoner, not a language model
- Daily granularity: the agent cannot micro-manage individual turns
- Opponent is a simple built-in bot; the real competition is head-to-head against strong agents
- Weather and events are our own extension, not part of the official game
- Reflection effect not demonstrated with the offline reasoner
- Free-tier LLM rate limits make full real-LLM evaluation slow

Speaker notes: Showing limitations openly builds trust with the panel.

---

## Slide 21: Conclusion and future scope
- An agentic design (tools + look-ahead + guardrails + coordination) beats a classic heuristic by about 3x
- Every decision is explainable and auditable in the reasoning trace
- Future: evaluate real LLMs over many seeds; compare with an RL policy (PPO) on the same environment
- Future: per-turn control, a stronger opponent, submission to the Kaggle ladder
- Future: deploy the dashboard as a hosted service; apply the same pattern to real supply-chain decisions

Speaker notes: End on the general lesson: give an LLM good tools and a simulator, keep it inside guardrails, and it plans better than fixed rules.

---

## Slide 22: References
1. S. Yao et al., "ReAct: Synergizing Reasoning and Acting in Language Models," ICLR 2023 (arXiv:2210.03629, 2022).
2. N. Shinn et al., "Reflexion: Language Agents with Verbal Reinforcement Learning," NeurIPS 2023.
3. T. Schick et al., "Toolformer: Language Models Can Teach Themselves to Use Tools," NeurIPS 2023.
4. J. S. Park et al., "Generative Agents: Interactive Simulacra of Human Behavior," UIST 2023.
5. Q. Wu et al., "AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation," 2023.
6. G. Li et al., "CAMEL: Communicative Agents for Mind Exploration of Large Language Model Society," NeurIPS 2023.
7. H. Overweg, H. Berghuijs, I. Athanasiadis, "CropGym: a Reinforcement Learning Environment for Crop Management," 2021.
8. B. Doerschuk-Tiberi, D. Weir, M. Cruz, "Kaggriculture," Kaggle, 2026. https://www.kaggle.com/competitions/kaggriculture
9. Kaggle, kaggle-environments (Apache-2.0). https://github.com/Kaggle/kaggle-environments

Speaker notes: Thank the panel and invite questions.
