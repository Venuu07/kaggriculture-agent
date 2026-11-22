# Viva preparation: 25 likely questions

Numbers quoted below come from `results/summary.csv` (5 seeds, weather and events on).
Random $11,060 · Greedy $30,021 · LLM single-agent (offline reasoner) $79,344 · LLM multi-agent (offline reasoner) $88,794.
The two LLM rows were produced by the **offline reasoner**, not by a real language model. Say this clearly if asked.

---

### 1. What makes this project "agentic" and not just a normal ML model?
A normal ML model maps one input to one output: you give it features and it predicts a number or a class. Our agent pursues a goal (maximise cash on day 30) over 30 decisions. Each decision is a loop. It looks at the farm, calls tools to gather information, tests "what if" plans in a simulator, then commits an action. It remembers what happened earlier in the season, writes lessons after the season, and in multi-agent mode works with other specialist agents. Those properties are what people usually mean by "agentic AI": goal, tools, planning, memory, autonomy, plus a safety layer around the actions.

### 2. What is ReAct and how did you implement it?
ReAct means "Reason + Act". The model writes a short thought, picks one action (a tool call), reads the observation (the tool result), and repeats until it decides. In `kagri/agents/llm_agent.py`, `LLMAgent._react` runs this loop. Each model reply must be one JSON object `{"thought", "action", "args"}`. If `action` is a tool name we run it through `ToolBox.call` and append the result as the next user message. If `action` is `take_action` the loop ends and the plan is returned. Every thought, tool call and result is saved in a trace that the UI shows in the "Agent's mind" tab.

### 3. Which tools does the agent have, and why these?
Eight tools in `kagri/agents/tools.py`: `get_farm_state`, `get_weather_forecast`, `get_market_prices`, `estimate_crop_profit`, `estimate_animal_profit`, `estimate_sale`, `plan_crop_mix` and `simulate_action`. They cover the three questions a farmer must answer: what do I have, what will the market pay, and what happens if I do X. The most important one is `simulate_action`. It copies the whole environment, plays the candidate plan for a few days, and reports the change in net worth. That lets the agent see delayed payoffs, which a one-shot model cannot.

### 4. Why a JSON text protocol instead of native function calling?
We support four providers (Gemini, Groq, OpenAI, Claude) and each has a different function-calling format. A plain JSON reply works the same way on all of them and keeps `kagri/llm/providers.py` very small, just HTTPS calls through `requests`. It also let us build the offline reasoner, which emits the exact same JSON, so the loop, logs and UI do not care where the reply came from. The cost is that we must handle bad JSON ourselves. `parse_json` strips code fences and finds the first object, and the loop retries up to 2 times. With more time we would add native function calling per provider as an option.

### 5. Explain short-term and long-term memory.
Short-term memory (`ShortTermMemory` in `kagri/agents/memory.py`) is the log of the current season: for the last 5 days, the plan, the cash change, weather, events and rejected actions. It goes into every day's prompt so the agent knows what it just did. Long-term memory (`LongTermMemory`) is a JSON file in `memory/` holding lessons written after each season. Those lessons are inserted into the system prompt of the next season. Short-term is "what happened this week"; long-term is "what I learned last year".

### 6. Does reflection actually improve profit?
Honestly: with the offline reasoner, no measurable improvement. The reflection experiment replays the same seed 3 times with lessons carried forward, and the curve is flat (about $79k single, $89k multi). The offline reflector only writes evidence-based lessons (gluts, idle cash, late animal purchases, cheap fertiliser), and on our seeds those rules rarely change a decision. An earlier "hire more hands" lesson made profit worse, so we removed it rather than show a fake curve. The mechanism is designed for a real LLM, which reads the lessons as text; measuring that needs `python -m kagri.evaluate --provider gemini --seeds 1 --agents llm_single --reflection-episodes 3`.

### 7. How does the multi-agent mode work?
Three specialists each run their own short ReAct loop with a restricted tool set. The Planner decides land use (plant, buy_land, buy_animals) and compares options with `simulate_action`. The Market Analyst decides what to sell, using prices and `estimate_sale`. The Agronomist decides fertiliser and labour from the weather forecast. The Manager then merges the three proposals, fixes conflicts and checks the merged plan in the simulator before committing. This is in `LLMAgent._team`.

### 8. Why did multi-agent beat single-agent ($88.8k vs $79.3k)?
Two reasons, both measurable. First, more deliberation: the Planner tests three land-use candidates with an 8-day look-ahead, while the single agent has a 4-tool budget and tests two candidates over 5 days. Second, conflict resolution: the Agronomist sizes labour before it knows what the Planner will plant, and the Manager catches that ("3 hands cannot tend 25 new tiles, raising to 7"). Before we added that Manager check, multi-agent was actually worse than single. That is a good example of why coordination needs a referee, not just more agents.

### 9. Why does the agent beat the Greedy baseline by about 3x?
Greedy picks the crop with the best margin per plot at today's price and plants all of it. That is almost always melon, and selling 150 melons crashes the melon price (the official curve drops it towards $1). Our agent uses a glut-aware crop mix that counts its own price impact, so it diversifies into strawberries, tomatoes and wheat. It also buys animals (each animal drops one fertiliser a day, worth about $100), buys land when the simulation says it pays back, and hires enough hands so plants are not lost. Greedy does none of that.

### 10. What is the Foreman and why does the agent decide only once per day?
The real game has 720 turns, and each turn moves a farmer one tile or does one action. Calling an LLM 720 times per game, with several tool calls each, is too slow and far beyond a free tier. So the agent makes one economic decision per day (30 per season). The Foreman (`kagri/foreman.py`) turns that plan into 24 turns of low-level commands: walking, watering, harvesting, feeding, market orders. It is a deterministic executor with standing orders, like a farm supervisor who carries out the manager's instructions. This is a common hierarchical design: the LLM plans, simple code executes.

### 11. Did you build your own simulator?
No. The official Kaggriculture rules ship inside the `kaggle-environments` package. That package pulls in jax, open_spiel and transformers, which is risky to install on Windows, so we vendored the single engine file `kaggriculture.py` (Apache-2.0, with attribution) into `kagri/engine/`. We only removed the framework import and the HTML visualiser. `kagri/engine/driver.py` provides a tiny replacement for kaggle's `Struct` and steps both players. So crop yields, prices, the market curve, hiring costs and land prices are exactly the competition's.

### 12. The competition has no weather. Why did you add it?
Our project brief asked for weather and random events, and they make the agent's reasoning more interesting to show. They are an extension layer in `FarmEnv._apply_events`, switched on by `events.enabled` in `config.yaml` or off with `--no-events`. Heavy rain waters every plant, drought removes the one-day grace before a plant dies, pests turn about 15% of unfertilised plants into weeds, and price shocks create a sudden glut or shortage. There is also a noisy 3-day forecast (80% accurate). Everything is seeded, so runs stay reproducible.

### 13. What guardrails are there?
Every plan goes through `validate_plan` in `kagri/plan.py` before execution. It rejects unknown keys, crops and animals, trims quantities to what cash, seeds, free plots and shed stock allow, keeps a feed reserve for animals, caps hands at 10, and refuses crops that cannot be ready before the season ends. Each rejection gets a human-readable reason, shown in the UI. The agent loop adds more: at most 4 tool calls per turn, tools restricted per role, 2 retries on bad JSON, and a safe fallback plan if the reply is still unusable. The UI and logs mark fallback days clearly.

### 14. What exactly is the offline reasoner?
It is a deterministic, rule-based stand-in for an LLM (`kagri/llm/offline.py`). It speaks the same JSON protocol, calls the same tools through the same ReAct loop, and writes "thoughts" that quote real tool results. It is **not** a language model and does not generate free text by itself. It exists so the demo, the logs and the evaluation work with no internet and no API key, and the UI labels it "offline reasoner · no LLM". The LLM numbers in our results come from it, which is why we report them that way.

### 15. What does a real LLM run cost?
A single-agent day uses about 3-5 model calls (a few tool calls plus the final action), so a season is roughly 90-150 calls. Multi-agent is several times more because four roles each call the model. The token counter (`Decision.tokens`) and the cost estimate (`Provider.cost`, list prices per million tokens) are recorded per day and shown in the UI and `results.csv`. On Gemini's free tier the dollar cost is zero, but the limit is requests per minute and per day. We wait `LLM_MIN_INTERVAL_S` (4 seconds by default) between calls and retry with back-off on HTTP 429.

### 16. How long does a decision take?
With the offline reasoner, about 0.1 to 0.2 seconds per day, most of it spent in `simulate_action`. A full 30-day episode of the engine alone takes about 0.1 seconds. With a real LLM, latency is dominated by the model: a few seconds per call plus the rate-limit spacing, so a single-agent season takes roughly 8-12 minutes on a free tier. That is why the demo uses replays and why one decision per day was the right granularity.

### 17. What are the main limitations?
The LLM results were measured with the offline reasoner, not a real model, so we cannot yet claim how much a real LLM adds. The opponent is the simple built-in "starter" bot, not a strong competitor. The Foreman's task assignment is greedy and not optimal (weeds can pile up). The look-ahead uses a fixed follow-up policy, so it can undervalue long-term investments. Reflection shows no measurable gain yet. Weather and events are our extension, so results with events on are not directly comparable to the Kaggle leaderboard.

### 18. How would you scale this up?
Run seasons in parallel (evaluation already uses a process pool when offline). Cache tool results within a day and batch independent specialist calls. Use a cheap small model for routine days and a stronger model only when the situation changes (an event, a big purchase). Store memory in a database instead of JSON files. For the competition, export the policy as a Kaggle `main.py` and train or distil it into a fast policy that does not need an API at match time.

### 19. Why not reinforcement learning (PPO or DQN)?
RL could work, and is a fair comparison. But the action space is large (crop mix, quantities, land, animals, labour), rewards are delayed by 10+ days, and an RL agent needs thousands to millions of episodes to learn. An LLM agent brings prior knowledge, uses tools such as a simulator, and works from the first episode. It is also explainable: you can read why it decided. RL would likely run faster at decision time once trained. A strong future design would combine both, for example an RL policy for routine choices with an LLM planner on top.

### 20. How did you evaluate the agents?
`python -m kagri.evaluate` runs every agent on the same 5 seeds (0-4), a full 30-day season each, with the same opponent and the same events. We report mean, standard deviation, min and max profit, plus tool calls, tokens and latency per decision. The environment is deterministic given a seed, so a result can be reproduced exactly. With only 5 seeds the standard deviation is large (about $12-16k for the LLM agents), so we describe the gap to Greedy as clear and the multi-vs-single gap as encouraging, not proven.

### 21. How did you test the code?
There are 14 pytest tests in `tests/`. They cover environment basics (reset, 30 steps, determinism, invalid actions rejected without crashing, budget trimming, late planting rejected, simulate does not change the real env), baselines running end to end and producing replayable logs, and the agent loop. A scripted fake LLM tests that tools are called, bad JSON is retried, a hopeless model falls back safely and tokens are counted. Another test checks that multi-agent mode produces all four roles and writes lessons. We also ran the UI in a headless browser with Playwright and checked for console errors.

### 22. Why React and FastAPI instead of Streamlit?
The core of the project is the agent, but the demo is how people see it. React let us build an animated farm grid, a step-by-step reasoning feed and interactive charts that look like a real product. FastAPI is a thin layer (`kagri/server.py`) that serves recorded runs, results and live seasons to the browser. The React app is built once into static files and committed, so on demo day only `python -m kagri.serve` is needed: no Node.js and no internet. Fonts are bundled, nothing loads from a CDN.

### 23. How do you know the agent did not just get lucky?
All agents play the same seeds, so they face the same weather and events. The multi-agent was better than Greedy on every one of the 5 seeds (its minimum of $78.8k is far above Greedy's maximum of $30.9k). The improvement also has a clear cause you can see in the traces: diversified crops, animals, look-ahead and enough labour. For multi vs single, the seeds overlap more, so we would want more seeds before claiming a firm difference.

### 24. What happens if the API fails in the middle of a run?
The provider retries network errors and rate limits with back-off. If it still fails, `LLMError` is caught in `LLMAgent.decide` and that day uses the deterministic safe plan, marked `fallback: true` in the log and shown as "Fallback plan used" in the UI. The season continues and never crashes. In the live UI, a missing key switches to the offline reasoner and shows a notice. For the demo, replay mode needs no network at all.

### 25. What would you do with more time?
Record and evaluate real-LLM runs (Gemini, Claude) on more seeds, and measure reflection properly. Add native function calling per provider. Use a better follow-up policy in `simulate_action`, or several, to value long-term investments. Improve the Foreman with proper task scheduling. Play against stronger opponents, or against itself, and package the agent as a Kaggle submission. Then compare against an RL baseline trained on the same environment.
